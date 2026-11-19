"""Tables of the external audit."""
AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS aud_eng (           -- ZAUD_ENG engagement of a fiscal year
    gjahr INTEGER PRIMARY KEY, firm TEXT, partner TEXT, manager TEXT, fieldwork TEXT, report_date TEXT,
    basis TEXT DEFAULT 'PBT', pct INTEGER DEFAULT 500, pm_pct INTEGER DEFAULT 7500, trivial_pct INTEGER DEFAULT 500,
    status TEXT DEFAULT 'PLANNING', notes TEXT DEFAULT '', usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS aud_pbc (           -- ZAUD_PBC what the auditor requests, who prepares it, status
    id INTEGER PRIMARY KEY AUTOINCREMENT, gjahr INTEGER, code TEXT, area TEXT, text TEXT, text_ar TEXT,
    eas TEXT DEFAULT '', esa TEXT DEFAULT '', auto TEXT DEFAULT '', due TEXT, owner TEXT DEFAULT '',
    status TEXT DEFAULT 'REQ', comment TEXT DEFAULT '', usnam TEXT, ts TEXT, UNIQUE (gjahr, code));
CREATE TABLE IF NOT EXISTS aud_query (         -- ZAUD_QUERY questions of the auditor and answers
    id INTEGER PRIMARY KEY AUTOINCREMENT, gjahr INTEGER, pbc TEXT DEFAULT '', question TEXT, raised_by TEXT,
    raised_on TEXT, answer TEXT DEFAULT '', answered_by TEXT DEFAULT '', answered_on TEXT DEFAULT '',
    status TEXT DEFAULT 'OPEN');
CREATE TABLE IF NOT EXISTS aud_aje (           -- ZAUD_AJE proposed audit adjustments
    id INTEGER PRIMARY KEY AUTOINCREMENT, gjahr INTEGER, text TEXT, eas TEXT DEFAULT '', lines TEXT,
    pl_effect INTEGER DEFAULT 0, status TEXT DEFAULT 'PROPOSED', proposed_by TEXT, proposed_on TEXT,
    decided_by TEXT DEFAULT '', decided_on TEXT DEFAULT '', reason TEXT DEFAULT '', belnr TEXT DEFAULT '');
"""


def install(conn):
    """the auditor role may work in the audit area (queries, adjustments, PBC review);
    the G/L accountant prepares the PBC and answers the queries"""
    for role in ("AUDITOR", "GL_ACCOUNTANT"):
        if conn.execute("SELECT 1 FROM role WHERE name=?", (role,)).fetchone() and not conn.execute(
                "SELECT 1 FROM role_auth WHERE role=? AND object='S_AREA' AND value='AU'", (role,)).fetchone():
            conn.execute("INSERT INTO role_auth (role, object, value, actvt) VALUES (?,?,?,?)", (role, "S_AREA", "AU", "02"))
