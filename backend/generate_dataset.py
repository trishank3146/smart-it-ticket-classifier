"""
Generates a labelled training dataset of IT support tickets.

Each ticket is built from realistic phrase templates for one of eight
categories. Some tickets get extra "noise" words borrowed from other
categories so the model has to learn the real signal, not just one keyword.

Usage:
    python generate_dataset.py            # writes data/tickets_dataset.csv
"""

import csv
import os
import random

CATEGORIES = {
    "Hardware": {
        "subjects": ["laptop", "monitor", "keyboard", "mouse", "docking station", "desktop PC",
                     "laptop battery", "webcam", "headset", "charger", "hard disk", "RAM"],
        "templates": [
            "My {s} is not working since this morning",
            "The {s} stopped responding and makes a strange noise",
            "{s} is physically damaged, need a replacement",
            "Requesting a new {s} because the old one is broken",
            "My {s} keeps overheating and shuts down",
            "The {s} does not power on even when plugged in",
            "Screen flickering and the {s} is very slow to start",
            "Blue screen error appears after connecting the {s}",
            "{s} not detected when I connect it to the system",
            "Need a hardware check for my {s}, it crashes frequently",
        ],
    },
    "Software": {
        "subjects": ["MS Excel", "MS Word", "Outlook client", "Teams", "Chrome", "Zoom", "Adobe Reader",
                     "the ERP application", "Visual Studio Code", "Java runtime", "antivirus agent", "the HR portal app"],
        "templates": [
            "{s} crashes every time I open it",
            "Please install {s} on my machine",
            "{s} shows an error after the latest update",
            "Unable to open files in {s}, it freezes",
            "Need license activation for {s}",
            "{s} is very slow and not responding",
            "Getting an application error code when launching {s}",
            "Please update {s} to the latest version",
            "{s} closes unexpectedly while saving work",
            "Plugin missing in {s}, need it reinstalled",
        ],
    },
    "Network": {
        "subjects": ["WiFi", "VPN", "LAN connection", "internet", "office network", "ethernet port",
                     "network drive", "wireless access point", "DNS", "proxy"],
        "templates": [
            "{s} keeps disconnecting every few minutes",
            "No {s} access on the third floor",
            "Very slow {s} speed, pages take forever to load",
            "Cannot connect to the {s} from home",
            "{s} is down for the whole team",
            "Getting a timeout when trying to reach the {s}",
            "{s} shows connected but no internet access",
            "Packet loss and high latency on the {s}",
            "Unable to map the {s}, connection refused",
            "{s} authentication fails and drops the connection",
        ],
    },
    "Access": {
        "subjects": ["SAP", "the shared folder", "Jira", "the finance dashboard", "Active Directory",
                     "the admin portal", "GitHub organisation", "the CRM", "SharePoint site", "the database server"],
        "templates": [
            "I forgot my password and cannot log in to {s}",
            "Please grant me access to {s}",
            "My account is locked out of {s}",
            "Need permission to edit files in {s}",
            "Password reset required for {s}",
            "New joiner needs an account created for {s}",
            "Access denied error when opening {s}",
            "Please remove access to {s} for an employee who left",
            "Two-factor authentication not working for {s}",
            "My login credentials for {s} expired",
        ],
    },
    "Email": {
        "subjects": ["Outlook mailbox", "email", "mailbox", "shared mailbox", "distribution list",
                     "email signature", "calendar invites", "mail rules", "email attachments", "inbox"],
        "templates": [
            "Not receiving any {s} since yesterday",
            "{s} is full and I cannot send messages",
            "Emails are bouncing back with a delivery failure from my {s}",
            "Please add me to the {s}",
            "Cannot send {s} to external domains",
            "{s} not syncing on my mobile phone",
            "Need to recover deleted messages from my {s}",
            "Large {s} are being blocked when I send them",
            "Out of office reply not working in my {s}",
            "Spam filter is moving important mails out of my {s}",
        ],
    },
    "Printer": {
        "subjects": ["printer", "scanner", "network printer", "photocopier", "label printer",
                     "colour printer", "print queue", "printer driver"],
        "templates": [
            "The {s} on floor two is jammed",
            "{s} shows offline and nothing prints",
            "Need toner replacement for the {s}",
            "Documents stuck in the {s}",
            "Unable to add the {s} to my laptop",
            "{s} prints blank pages",
            "Scanning to email not working on the {s}",
            "{s} is printing with faded and streaky output",
            "Please install the {s} on my system",
            "Paper feed error on the {s}",
        ],
    },
    "Security": {
        "subjects": ["phishing email", "suspicious link", "virus alert", "malware", "ransomware message",
                     "unknown login attempt", "data leak", "lost company laptop", "suspicious attachment", "firewall alert"],
        "templates": [
            "I received a {s}, please investigate",
            "Antivirus reported a {s} on my machine",
            "Reporting a possible {s} in our department",
            "I clicked a {s} by mistake, what should I do",
            "Security team please check this {s}",
            "Got a notification about an {s} on my account",
            "Urgent: {s} detected, files may be encrypted",
            "Need to report a {s} immediately",
            "Possible security breach, saw a {s}",
            "Our system flagged a {s} this morning",
        ],
    },
    "Database": {
        "subjects": ["MySQL database", "SQL query", "database table", "Oracle DB", "stored procedure",
                     "database backup", "reporting database", "DB connection", "database index", "SQL Server"],
        "templates": [
            "The {s} is running very slowly",
            "{s} returns a deadlock error",
            "Need a new {s} created for our project",
            "{s} failed last night",
            "Cannot connect to the {s} from the application",
            "Data missing after the {s} job ran",
            "Please restore data from the {s}",
            "{s} timeout in production",
            "Need read access rights on the {s}",
            "{s} storage is almost full",
        ],
    },
}

OPENERS = ["", "Hi team, ", "Hello, ", "Urgent: ", "Please help, ", "Good morning, ", "Hi IT support, "]
CLOSERS = ["", " Thanks.", " Please help asap.", " This is blocking my work.", " Kindly look into it.",
           " Regards.", " It started after the update."]

# Words that appear across categories, used to add realistic overlap/noise.
NOISE = ["laptop", "error", "not working", "slow", "access", "update", "urgent", "login", "network"]


def make_ticket(category: str, rng: random.Random) -> str:
    spec = CATEGORIES[category]
    text = rng.choice(spec["templates"]).format(s=rng.choice(spec["subjects"]))
    if rng.random() < 0.25:                         # 25% get a confusing extra word
        text += f" ({rng.choice(NOISE)})"
    text = rng.choice(OPENERS) + text[0].lower() + text[1:] if rng.random() < 0.6 else text
    text = text[0].upper() + text[1:] + rng.choice(CLOSERS)
    return text


def generate(per_category: int = 150, seed: int = 42, label_noise: float = 0.06):
    """label_noise: share of tickets given a wrong category, like real helpdesk
    data where agents sometimes file tickets under the wrong queue."""
    rng = random.Random(seed)
    names = list(CATEGORIES)
    rows = []
    for category in names:
        for _ in range(per_category):
            label = category
            if rng.random() < label_noise:
                label = rng.choice([c for c in names if c != category])
            rows.append({"text": make_ticket(category, rng), "category": label})
    rng.shuffle(rows)
    return rows


def main():
    rows = generate()
    out_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "tickets_dataset.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "category"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} tickets across {len(CATEGORIES)} categories to {path}")


if __name__ == "__main__":
    main()
