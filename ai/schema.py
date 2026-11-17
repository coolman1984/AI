"""Tables of the assistant: settings and the question log (audit)."""
AI_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_setting (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ai_log (           -- every question, the data used and the answer
    id INTEGER PRIMARY KEY AUTOINCREMENT, usnam TEXT, ts TEXT, question TEXT, answer TEXT,
    tools TEXT, mode TEXT, ms INTEGER DEFAULT 0, error TEXT DEFAULT '');
"""


def install(conn):
    conn.execute("INSERT OR IGNORE INTO ai_setting VALUES ('model','claude-opus-5-5')")
    conn.execute("INSERT OR IGNORE INTO ai_setting VALUES ('effort','medium')")
    conn.execute("INSERT OR IGNORE INTO ai_setting VALUES ('enabled','1')")
