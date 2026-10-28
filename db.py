"""Saved check history (SQLite). No ML or pipeline code lives here."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("history.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                answer TEXT NOT NULL,
                score INTEGER NOT NULL,
                n_claims INTEGER NOT NULL,
                report_json TEXT NOT NULL)"""
        )


def save_check(answer, report, score, n_claims):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO checks (answer, score, n_claims, report_json) VALUES (?, ?, ?, ?)",
            (answer, score, n_claims, json.dumps(report)),
        )
        return cur.lastrowid


def get_check(check_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    return dict(row) if row else None


def list_checks(limit=100):
    with _conn() as c:
        rows = c.execute(
            "SELECT id, created_at, substr(answer, 1, 140) AS snippet, score, n_claims "
            "FROM checks ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_check(check_id):
    """Delete one saved report from history."""
    with _conn() as c:
        cur = c.execute("DELETE FROM checks WHERE id = ?", (check_id,))
        return cur.rowcount > 0
