"""
API tests. They run against an in-memory SQLite database, so no MySQL server
is needed.   Run:  python -m pytest -v
"""

import os
import sys

import tempfile

os.environ["DB_ENGINE"] = "sqlite"
os.environ["MODEL_DIR"] = tempfile.mkdtemp()   # never overwrite the real model files
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import db  # noqa: E402
from app import create_app  # noqa: E402
from classifier import classify, detect_priority  # noqa: E402


@pytest.fixture
def client():
    db.DB_ENGINE = "sqlite"
    db.reset_sqlite()
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def new_ticket(client, title, description, email="user@company.com"):
    return client.post("/api/tickets", json={
        "title": title, "description": description, "requester_email": email})


# ---------- classifier ----------

@pytest.mark.parametrize("text,expected", [
    ("I forgot my password and my account is locked out of SAP", "Access"),
    ("The printer on floor two is jammed and shows paper feed error", "Printer"),
    ("VPN keeps disconnecting every few minutes", "Network"),
    ("I clicked a suspicious link in a phishing email", "Security"),
    ("MySQL database query returns a deadlock error", "Database"),
    ("My laptop battery does not charge and the laptop overheats", "Hardware"),
    ("Not receiving any emails in my Outlook mailbox", "Email"),
    ("MS Excel crashes every time I open it after the update", "Software"),
])
def test_classifier_predicts_expected_category(text, expected):
    assert classify(text)["category"] == expected


def test_priority_rules():
    assert detect_priority("The VPN is down for the whole team", "Network") == "Critical"
    assert detect_priority("Unable to open Excel", "Software") == "High"
    assert detect_priority("Please install Zoom when possible", "Software") == "Low"
    assert detect_priority("Monitor brightness looks odd", "Hardware") == "Medium"
    # Security tickets are never below High
    assert detect_priority("Saw an odd attachment", "Security") == "High"


def test_classify_empty_text_raises():
    with pytest.raises(ValueError):
        classify("   ")


# ---------- API ----------

def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_classify_endpoint(client):
    res = client.post("/api/classify", json={"text": "WiFi keeps disconnecting"})
    body = res.get_json()
    assert res.status_code == 200
    assert body["category"] == "Network"
    assert body["assigned_team"] == "Network Operations"
    assert 0 < body["confidence"] <= 1
    assert len(body["alternatives"]) == 3


def test_create_and_get_ticket(client):
    res = new_ticket(client, "Account locked", "My account is locked out of Jira, cannot log in")
    assert res.status_code == 201
    ticket = res.get_json()
    assert ticket["category"] == "Access"
    assert ticket["priority"] == "High"
    assert ticket["status"] == "Open"
    assert ticket["assigned_team"] == "Identity & Access Management"

    fetched = client.get(f"/api/tickets/{ticket['id']}").get_json()
    assert fetched["title"] == "Account locked"


def test_create_ticket_validation(client):
    assert new_ticket(client, "", "desc").status_code == 400
    assert new_ticket(client, "Title", "desc", email="not-an-email").status_code == 400


def test_list_and_filter_tickets(client):
    new_ticket(client, "Printer jam", "The printer on floor 2 is jammed")
    new_ticket(client, "VPN issue", "Cannot connect to the VPN from home")
    new_ticket(client, "Phishing", "I received a phishing email, please investigate")

    assert len(client.get("/api/tickets").get_json()) == 3
    printers = client.get("/api/tickets?category=Printer").get_json()
    assert len(printers) == 1 and printers[0]["title"] == "Printer jam"
    assert len(client.get("/api/tickets?search=VPN").get_json()) == 1


def test_update_ticket_and_manual_correction(client):
    ticket = new_ticket(client, "Slow PC", "My desktop PC is very slow").get_json()

    res = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "In Progress"})
    assert res.get_json()["status"] == "In Progress"

    res = client.patch(f"/api/tickets/{ticket['id']}", json={"category": "Software"})
    updated = res.get_json()
    assert updated["category"] == "Software"
    assert updated["assigned_team"] == "Application Support"
    assert updated["manually_corrected"] is True

    assert client.patch(f"/api/tickets/{ticket['id']}", json={"status": "Done"}).status_code == 400
    assert client.patch("/api/tickets/999", json={"status": "Closed"}).status_code == 404


def test_delete_ticket(client):
    ticket = new_ticket(client, "Toner", "Need toner replacement for the printer").get_json()
    assert client.delete(f"/api/tickets/{ticket['id']}").status_code == 204
    assert client.get(f"/api/tickets/{ticket['id']}").status_code == 404


def test_reports(client):
    new_ticket(client, "Printer jam", "The printer is jammed")
    new_ticket(client, "Printer offline", "Network printer shows offline")
    new_ticket(client, "Locked", "Account locked out of SAP")

    categories = client.get("/api/reports/categories").get_json()
    printer_row = next(r for r in categories if r["category"] == "Printer")
    assert printer_row["total_tickets"] == 2

    summary = client.get("/api/reports/summary").get_json()
    assert summary["total_tickets"] == 3
    assert summary["by_status"]["Open"] == 3


def test_model_metrics(client):
    body = client.get("/api/model/metrics").get_json()
    assert body["accuracy"] > 0.85
    assert len(body["labels"]) == 8


# ---------- SLA, overdue, history, retraining ----------

def test_sla_due_time_matches_priority(client):
    from datetime import datetime
    t = new_ticket(client, "WiFi down", "WiFi is down for the whole team").get_json()
    assert t["priority"] == "Critical"
    created = datetime.fromisoformat(t["created_at"].rstrip("Z"))
    due = datetime.fromisoformat(t["due_at"].rstrip("Z"))
    assert (due - created).total_seconds() == 4 * 3600      # Critical SLA = 4 hours
    assert t["is_overdue"] is False


def test_priority_change_moves_sla_deadline(client):
    from datetime import datetime
    t = new_ticket(client, "Monitor", "Monitor brightness looks odd").get_json()
    assert t["priority"] == "Medium"
    updated = client.patch(f"/api/tickets/{t['id']}", json={"priority": "Low"}).get_json()
    created = datetime.fromisoformat(updated["created_at"].rstrip("Z"))
    due = datetime.fromisoformat(updated["due_at"].rstrip("Z"))
    assert (due - created).total_seconds() == 72 * 3600     # Low SLA = 72 hours


def test_overdue_tickets(client):
    t = new_ticket(client, "Printer jam", "The printer is jammed").get_json()
    new_ticket(client, "Toner", "Need toner for the printer")
    # Push the first ticket's deadline into the past
    db.execute("UPDATE tickets SET due_at = %s WHERE id = %s", ("2020-01-01 00:00:00", t["id"]))

    overdue = client.get("/api/tickets?overdue=true").get_json()
    assert [x["id"] for x in overdue] == [t["id"]]
    assert overdue[0]["is_overdue"] is True
    assert client.get("/api/reports/summary").get_json()["overdue"] == 1

    # A resolved ticket is no longer overdue
    client.patch(f"/api/tickets/{t['id']}", json={"status": "Resolved"})
    assert client.get("/api/tickets?overdue=true").get_json() == []


def test_sla_compliance(client):
    a = new_ticket(client, "Excel", "MS Excel crashes on start").get_json()
    b = new_ticket(client, "VPN", "Cannot connect to the VPN").get_json()
    db.execute("UPDATE tickets SET due_at = %s WHERE id = %s", ("2020-01-01 00:00:00", b["id"]))
    client.patch(f"/api/tickets/{a['id']}", json={"status": "Resolved"})   # on time
    client.patch(f"/api/tickets/{b['id']}", json={"status": "Resolved"})   # late
    assert client.get("/api/reports/summary").get_json()["sla_compliance_pct"] == 50.0


def test_resolved_at_set_and_cleared(client):
    t = new_ticket(client, "Mouse", "Mouse not detected").get_json()
    assert t["resolved_at"] is None
    resolved = client.patch(f"/api/tickets/{t['id']}", json={"status": "Resolved"}).get_json()
    assert resolved["resolved_at"] is not None
    reopened = client.patch(f"/api/tickets/{t['id']}", json={"status": "Open"}).get_json()
    assert reopened["resolved_at"] is None


def test_history_audit_trail(client):
    t = new_ticket(client, "Slow PC", "My desktop PC is very slow").get_json()
    client.patch(f"/api/tickets/{t['id']}", json={"status": "In Progress"})
    client.patch(f"/api/tickets/{t['id']}", json={"category": "Software"})
    client.patch(f"/api/tickets/{t['id']}", json={"status": "In Progress"})   # no change, not logged

    history = client.get(f"/api/tickets/{t['id']}/history").get_json()
    assert [h["action"] for h in history] == ["created", "status_changed", "category_corrected"]
    assert history[1]["old_value"] == "Open" and history[1]["new_value"] == "In Progress"
    assert history[2]["new_value"] == "Software"
    assert client.get("/api/tickets/999/history").status_code == 404


def test_delete_cascades_history(client):
    t = new_ticket(client, "Laptop", "Laptop overheating").get_json()
    client.patch(f"/api/tickets/{t['id']}", json={"status": "Closed"})
    client.delete(f"/api/tickets/{t['id']}")
    rows = db.query_all("SELECT * FROM ticket_history WHERE ticket_id = %s", (t["id"],))
    assert rows == []


def test_update_with_nothing_valid(client):
    t = new_ticket(client, "Laptop", "Laptop overheating").get_json()
    assert client.patch(f"/api/tickets/{t['id']}", json={"colour": "red"}).status_code == 400


def test_retrain_uses_agent_corrections(client):
    t = new_ticket(client, "Badge reader", "Office door badge reader not opening the door").get_json()
    client.patch(f"/api/tickets/{t['id']}", json={"category": "Hardware"})
    res = client.post("/api/model/retrain")
    body = res.get_json()
    assert res.status_code == 200
    assert body["corrections_used"] == 1
    assert body["accuracy"] > 0.85
    assert client.get("/api/model/metrics").get_json()["corrections_used"] == 1
