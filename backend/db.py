"""
Database layer.

Production uses MySQL (mysql-connector-python). For automated tests the same
queries run on an in-memory SQLite database (set DB_ENGINE=sqlite), so the
test suite does not need a MySQL server.

Connection settings are read from environment variables (see .env.example).
"""

import os
import sqlite3

DB_ENGINE = os.getenv("DB_ENGINE", "mysql")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requester_email TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Medium',
    status TEXT NOT NULL DEFAULT 'Open',
    assigned_team TEXT NOT NULL,
    manually_corrected INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    due_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ticket_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP NOT NULL
);
"""

_sqlite_conn = None


def get_connection():
    global _sqlite_conn
    if DB_ENGINE == "sqlite":
        if _sqlite_conn is None:
            _sqlite_conn = sqlite3.connect(os.getenv("SQLITE_PATH", ":memory:"), check_same_thread=False)
            _sqlite_conn.execute("PRAGMA foreign_keys = ON")   # enables ON DELETE CASCADE
            _sqlite_conn.executescript(SQLITE_SCHEMA)
        return _sqlite_conn

    import mysql.connector  # imported here so tests don't need the MySQL driver
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ticket_classifier"),
    )


def _sql(query: str) -> str:
    """MySQL uses %s placeholders, SQLite uses ?."""
    return query.replace("%s", "?") if DB_ENGINE == "sqlite" else query


def _rows_to_dicts(cursor, rows):
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def query_all(query: str, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql(query), params)
        return _rows_to_dicts(cursor, cursor.fetchall())
    finally:
        cursor.close()
        if DB_ENGINE != "sqlite":
            conn.close()


def query_one(query: str, params=()):
    rows = query_all(query, params)
    return rows[0] if rows else None


def execute(query: str, params=()) -> int:
    """Run INSERT/UPDATE/DELETE and return the new row id (for inserts)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(_sql(query), params)
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        if DB_ENGINE != "sqlite":
            conn.close()


def reset_sqlite():
    """Used by tests to start each test with an empty database."""
    global _sqlite_conn
    if _sqlite_conn is not None:
        _sqlite_conn.close()
    _sqlite_conn = None
