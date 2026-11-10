"""LMS ID registration state per user (e-Learning, ZLMS)."""
import json

from mm.db import transaction


def get(conn, user):
    row = conn.execute("SELECT value FROM settings WHERE key=?", ("lms_" + user,)).fetchone()
    return json.loads(row[0]) if row else {"user": user, "status": "NONE"}


def put(conn, user, d):
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("lms_" + user, json.dumps(d)))
