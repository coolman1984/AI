"""Tables of the notifications."""
NOTIFY_SCHEMA = """
CREATE TABLE IF NOT EXISTS notif_setting (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS notif_sub (         -- who gets what on which channel
    id INTEGER PRIMARY KEY AUTOINCREMENT, usnam TEXT NOT NULL, channel TEXT NOT NULL, address TEXT,
    daily INTEGER DEFAULT 1, daily_time TEXT DEFAULT '08:00', cats TEXT DEFAULT 'MACH,STOCK,CREDIT,QUAL,TAX,APPR',
    active INTEGER DEFAULT 1, created TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS notif_sent (        -- an alert / a daily briefing is sent once
    key TEXT PRIMARY KEY, ts TEXT);
CREATE TABLE IF NOT EXISTS notif_log (         -- every message, also the in-app inbox
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, usnam TEXT, channel TEXT, address TEXT, kind TEXT,
    cat TEXT, title TEXT, text TEXT, tcode TEXT, status TEXT, error TEXT DEFAULT '', seen INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS notif_log_user ON notif_log (usnam, id);
"""


def install(conn):
    for k, v in (("enabled", "1"), ("alert_minutes", "15"), ("smtp_port", "587"), ("smtp_tls", "1")):
        conn.execute("INSERT OR IGNORE INTO notif_setting VALUES (?,?)", (k, v))
