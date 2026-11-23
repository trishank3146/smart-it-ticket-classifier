"""
Ticket classification and priority logic.

- Category: predicted by the trained ML model (TF-IDF + Logistic Regression).
- Confidence: the model's probability for the predicted category.
- Priority: rule-based, from urgency keywords in the ticket text.
- Team: each category is routed to the support team that owns it.
"""

import os
import re

import joblib

from train_model import MODEL_PATH, train

# Which support team handles each category (ticket routing)
TEAM_ROUTING = {
    "Hardware": "Desktop Support",
    "Software": "Application Support",
    "Network": "Network Operations",
    "Access": "Identity & Access Management",
    "Email": "Messaging Team",
    "Printer": "Desktop Support",
    "Security": "Security Operations Centre",
    "Database": "Database Administration",
}

# Keyword rules for priority, checked from most to least urgent
PRIORITY_RULES = [
    ("Critical", ["outage", "down for", "whole team", "all users", "breach", "ransomware",
                  "encrypted", "production", "data leak", "entire office"]),
    ("High", ["urgent", "asap", "blocking", "cannot", "can't", "unable", "locked out",
              "failed", "not working", "crash", "malware", "virus", "phishing", "deadlock"]),
    ("Low", ["request", "would like", "please install", "how to", "add me", "new joiner",
             "when possible", "signature"]),
]

# Security tickets are never lower than High
MIN_PRIORITY = {"Security": "High"}
PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]

# SLA: how many hours the team has to resolve a ticket, by priority
SLA_HOURS = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}

_model = None


def get_model():
    """Load the trained model once (trains it first if the file doesn't exist)."""
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            train(verbose=False)
        _model = joblib.load(MODEL_PATH)
    return _model


def reload_model():
    """Forget the cached model so the next prediction loads the newly trained one."""
    global _model
    _model = None


def detect_priority(text: str, category: str) -> str:
    lowered = text.lower()
    priority = "Medium"
    for level, keywords in PRIORITY_RULES:
        # \b only at the start, so "crash" also matches "crashes"/"crashed"
        if any(re.search(r"\b" + re.escape(k), lowered) for k in keywords):
            priority = level
            break
    minimum = MIN_PRIORITY.get(category)
    if minimum and PRIORITY_ORDER.index(priority) < PRIORITY_ORDER.index(minimum):
        priority = minimum
    return priority


def classify(text: str) -> dict:
    """Classify a ticket and return category, confidence, priority and team."""
    if not text or not text.strip():
        raise ValueError("Ticket text is empty")

    model = get_model()
    probabilities = model.predict_proba([text])[0]
    classes = model.classes_
    best = int(probabilities.argmax())
    category = str(classes[best])

    top3 = sorted(zip(classes, probabilities), key=lambda p: p[1], reverse=True)[:3]
    return {
        "category": category,
        "confidence": round(float(probabilities[best]), 4),
        "priority": detect_priority(text, category),
        "assigned_team": TEAM_ROUTING[category],
        "alternatives": [{"category": str(c), "confidence": round(float(p), 4)} for c, p in top3],
    }
