"""
Smart IT Support Ticket Classifier - Flask REST API
Author: Segu Gopi Trishank

Endpoints
---------
GET    /api/health                     service health check
POST   /api/classify                   classify text without saving it
POST   /api/tickets                    create a ticket (auto category, priority, team, SLA)
GET    /api/tickets                    list tickets (filters: category, status, priority, search, overdue)
GET    /api/tickets/<id>               get one ticket
GET    /api/tickets/<id>/history       audit trail of every change to a ticket
PATCH  /api/tickets/<id>               update status / priority / category (manual correction)
DELETE /api/tickets/<id>               delete a ticket (its history is deleted by ON DELETE CASCADE)
GET    /api/reports/categories         ticket counts and confidence per category
GET    /api/reports/summary            totals by status and priority, overdue and SLA figures
GET    /api/model/metrics              accuracy of the trained model
POST   /api/model/retrain              retrain the model including agents' corrections
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

import db
from classifier import SLA_HOURS, TEAM_ROUTING, classify, get_model, reload_model
from train_model import METRICS_PATH, train

VALID_STATUS = ["Open", "In Progress", "Resolved", "Closed"]
VALID_PRIORITY = ["Low", "Medium", "High", "Critical"]
OPEN_STATUSES = ("Open", "In Progress")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- helpers

def load_env_file(path=".env"):
    """Minimal .env loader so no extra package is needed."""
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def utc_now() -> datetime:
    """Current UTC time without timezone info (how it is stored in the database)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_datetime(value):
    """MySQL returns datetime objects, SQLite returns text. Normalise both."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def db_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def is_overdue(ticket: dict, now: datetime) -> bool:
    return ticket["status"] in OPEN_STATUSES and to_datetime(ticket["due_at"]) < now


def serialize(row: dict) -> dict:
    """Convert DB values (Decimal, datetime, 0/1) into JSON-friendly values."""
    out = {}
    for key, value in row.items():
        if key in ("created_at", "due_at", "resolved_at", "changed_at"):
            value = to_datetime(value)
        if isinstance(value, datetime):
            value = value.isoformat() + "Z"          # stored as UTC
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        elif value.__class__.__name__ == "Decimal":
            value = float(value)
        if key == "manually_corrected":
            value = bool(value)
        out[key] = value
    return out


def serialize_ticket(ticket: dict, now: datetime = None) -> dict:
    now = now or utc_now()
    out = serialize(ticket)
    out["is_overdue"] = is_overdue(ticket, now)
    return out


def log_history(ticket_id: int, action: str, old=None, new=None):
    db.execute(
        """INSERT INTO ticket_history (ticket_id, action, old_value, new_value, changed_at)
           VALUES (%s, %s, %s, %s, %s)""",
        (ticket_id, action, old, new, db_time(utc_now())),
    )


def error(message, status=400):
    return jsonify({"error": message}), status


# ---------------------------------------------------------------- app

def create_app():
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        # Allow the React dev server (different port) to call this API
        response.headers["Access-Control-Allow-Origin"] = os.getenv("FRONTEND_ORIGIN", "*")
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        return response

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # ---------- classification ----------

    @app.post("/api/classify")
    def classify_text():
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return error("'text' is required")
        return jsonify(classify(text))

    # ---------- tickets ----------

    @app.post("/api/tickets")
    def create_ticket():
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        email = (data.get("requester_email") or "").strip()

        if not title or not description:
            return error("'title' and 'description' are required")
        if len(title) > 200:
            return error("'title' must be 200 characters or fewer")
        if not EMAIL_RE.match(email):
            return error("A valid 'requester_email' is required")

        result = classify(f"{title}. {description}")
        created = utc_now()
        due = created + timedelta(hours=SLA_HOURS[result["priority"]])
        ticket_id = db.execute(
            """INSERT INTO tickets
               (title, description, requester_email, category, confidence, priority,
                assigned_team, created_at, due_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (title, description, email, result["category"], result["confidence"],
             result["priority"], result["assigned_team"], db_time(created), db_time(due)),
        )
        log_history(ticket_id, "created", None,
                    f"{result['category']} / {result['priority']}")
        ticket = db.query_one("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        out = serialize_ticket(ticket)
        out["alternatives"] = result["alternatives"]
        return jsonify(out), 201

    @app.get("/api/tickets")
    def list_tickets():
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []
        for field in ("category", "status", "priority"):
            value = request.args.get(field)
            if value:
                query += f" AND {field} = %s"   # field name comes from our fixed list, not the user
                params.append(value)
        search = (request.args.get("search") or "").strip()
        if search:
            query += " AND (title LIKE %s OR description LIKE %s OR requester_email LIKE %s)"
            params += [f"%{search}%"] * 3
        if request.args.get("overdue") == "true":
            query += " AND status IN ('Open', 'In Progress') AND due_at < %s"
            params.append(db_time(utc_now()))
        # Open work first, then most urgent priority, then nearest SLA deadline
        query += """ ORDER BY CASE WHEN status IN ('Open', 'In Progress') THEN 0 ELSE 1 END,
                        CASE priority
                        WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3 ELSE 4 END, due_at, id DESC"""
        now = utc_now()
        return jsonify([serialize_ticket(t, now) for t in db.query_all(query, tuple(params))])

    @app.get("/api/tickets/<int:ticket_id>")
    def get_ticket(ticket_id):
        ticket = db.query_one("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        if not ticket:
            return error("Ticket not found", 404)
        return jsonify(serialize_ticket(ticket))

    @app.get("/api/tickets/<int:ticket_id>/history")
    def ticket_history(ticket_id):
        if not db.query_one("SELECT id FROM tickets WHERE id = %s", (ticket_id,)):
            return error("Ticket not found", 404)
        rows = db.query_all(
            """SELECT h.id, h.action, h.old_value, h.new_value, h.changed_at
               FROM ticket_history h
               JOIN tickets t ON t.id = h.ticket_id
               WHERE t.id = %s
               ORDER BY h.changed_at, h.id""",
            (ticket_id,),
        )
        return jsonify([serialize(r) for r in rows])

    @app.patch("/api/tickets/<int:ticket_id>")
    def update_ticket(ticket_id):
        ticket = db.query_one("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        if not ticket:
            return error("Ticket not found", 404)

        data = request.get_json(silent=True) or {}
        updates, params, changes = [], [], []

        if "status" in data:
            status = data["status"]
            if status not in VALID_STATUS:
                return error(f"status must be one of {VALID_STATUS}")
            if status != ticket["status"]:
                updates.append("status = %s")
                params.append(status)
                # Record when a ticket is resolved; clear it if the ticket is reopened
                updates.append("resolved_at = %s")
                params.append(db_time(utc_now()) if status in ("Resolved", "Closed") else None)
                changes.append(("status_changed", ticket["status"], status))

        if "priority" in data:
            priority = data["priority"]
            if priority not in VALID_PRIORITY:
                return error(f"priority must be one of {VALID_PRIORITY}")
            if priority != ticket["priority"]:
                # New priority means a new SLA deadline, counted from creation time
                due = to_datetime(ticket["created_at"]) + timedelta(hours=SLA_HOURS[priority])
                updates += ["priority = %s", "due_at = %s"]
                params += [priority, db_time(due)]
                changes.append(("priority_changed", ticket["priority"], priority))

        if "category" in data:
            category = data["category"]
            if category not in TEAM_ROUTING:
                return error(f"category must be one of {list(TEAM_ROUTING)}")
            if category != ticket["category"]:
                # A support agent corrected the model: re-route to the right team
                updates += ["category = %s", "assigned_team = %s", "manually_corrected = %s"]
                params += [category, TEAM_ROUTING[category], 1]
                changes.append(("category_corrected", ticket["category"], category))

        if not data or not any(k in data for k in ("status", "priority", "category")):
            return error("Nothing to update. Send status, priority or category.")

        if updates:
            db.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = %s",
                       (*params, ticket_id))
            for action, old, new in changes:
                log_history(ticket_id, action, old, new)

        return jsonify(serialize_ticket(
            db.query_one("SELECT * FROM tickets WHERE id = %s", (ticket_id,))))

    @app.delete("/api/tickets/<int:ticket_id>")
    def delete_ticket(ticket_id):
        if not db.query_one("SELECT id FROM tickets WHERE id = %s", (ticket_id,)):
            return error("Ticket not found", 404)
        db.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
        return "", 204

    # ---------- reports ----------

    @app.get("/api/reports/categories")
    def category_report():
        rows = db.query_all(
            """SELECT category,
                      COUNT(*) AS total_tickets,
                      SUM(CASE WHEN status IN ('Open', 'In Progress') THEN 1 ELSE 0 END) AS open_tickets,
                      SUM(CASE WHEN priority IN ('High', 'Critical') THEN 1 ELSE 0 END) AS urgent_tickets,
                      SUM(CASE WHEN status IN ('Open', 'In Progress') AND due_at < %s
                               THEN 1 ELSE 0 END) AS overdue_tickets,
                      ROUND(AVG(confidence) * 100, 1) AS avg_confidence_pct
               FROM tickets
               GROUP BY category
               ORDER BY total_tickets DESC""",
            (db_time(utc_now()),),
        )
        return jsonify([{k: (int(v) if k.endswith("_tickets") else v)
                         for k, v in serialize(r).items()} for r in rows])

    @app.get("/api/reports/summary")
    def summary_report():
        now = utc_now()
        by_status = db.query_all("SELECT status, COUNT(*) AS count FROM tickets GROUP BY status")
        by_priority = db.query_all("SELECT priority, COUNT(*) AS count FROM tickets GROUP BY priority")
        total = db.query_one("SELECT COUNT(*) AS total FROM tickets")["total"]
        corrected = db.query_one(
            "SELECT COUNT(*) AS n FROM tickets WHERE manually_corrected = 1")["n"]
        overdue = db.query_one(
            "SELECT COUNT(*) AS n FROM tickets WHERE status IN ('Open', 'In Progress') AND due_at < %s",
            (db_time(now),))["n"]

        # SLA compliance: share of resolved tickets that were resolved before their deadline
        resolved = db.query_all(
            "SELECT due_at, resolved_at FROM tickets WHERE resolved_at IS NOT NULL")
        met = sum(1 for r in resolved if to_datetime(r["resolved_at"]) <= to_datetime(r["due_at"]))
        sla_pct = round(100 * met / len(resolved), 1) if resolved else None

        return jsonify({
            "total_tickets": int(total),
            "by_status": {r["status"]: int(r["count"]) for r in by_status},
            "by_priority": {r["priority"]: int(r["count"]) for r in by_priority},
            "overdue": int(overdue),
            "manually_corrected": int(corrected),
            "sla_compliance_pct": sla_pct,
        })

    # ---------- model ----------

    @app.get("/api/model/metrics")
    def model_metrics():
        get_model()  # makes sure the model (and its metrics file) exists
        with open(METRICS_PATH) as f:
            metrics = json.load(f)
        keys = ("accuracy", "train_size", "test_size", "labels", "corrections_used")
        return jsonify({k: metrics.get(k, 0) for k in keys})

    @app.post("/api/model/retrain")
    def retrain_model():
        """Human-in-the-loop learning: tickets that agents corrected become extra
        training examples, so the model learns from its mistakes."""
        corrected = db.query_all(
            "SELECT title, description, category FROM tickets WHERE manually_corrected = 1")
        extra = [{"text": f"{r['title']}. {r['description']}", "category": r["category"]}
                 for r in corrected]
        metrics = train(verbose=False, extra_rows=extra)
        reload_model()
        return jsonify({
            "message": f"Model retrained with {len(extra)} agent correction(s)",
            "accuracy": metrics["accuracy"],
            "train_size": metrics["train_size"],
            "corrections_used": metrics["corrections_used"],
        })

    return app


if __name__ == "__main__":
    load_env_file()
    db.DB_ENGINE = os.getenv("DB_ENGINE", "mysql")
    create_app().run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")),
                     debug=os.getenv("FLASK_DEBUG", "0") == "1")
