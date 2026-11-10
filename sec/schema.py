"""Tables of the user and authorisation administration (USR02, AGR_*, SM20)."""

SEC_SCHEMA = """
CREATE TABLE IF NOT EXISTS usr (            -- USR02 / USR21: logon data and address
    bname TEXT PRIMARY KEY, name TEXT, company TEXT DEFAULT '', busarea TEXT DEFAULT '',
    kostl TEXT DEFAULT '', email TEXT DEFAULT '',
    pw_salt TEXT, pw_hash TEXT, must_change INTEGER DEFAULT 0,
    locked TEXT DEFAULT '',                  -- '' open, F failed logons, A administrator, U long-term unused
    failed INTEGER DEFAULT 0, valid_from TEXT, valid_to TEXT DEFAULT '9999-12-31',
    last_login TEXT, created TEXT, created_by TEXT, pw_changed TEXT);
CREATE TABLE IF NOT EXISTS role (           -- AGR_DEFINE
    name TEXT PRIMARY KEY, text TEXT, changed TEXT, changed_by TEXT);
CREATE TABLE IF NOT EXISTS role_tcode (     -- AGR_TCODES: transaction, '*', 'VA*' or '@SD' (menu area)
    role TEXT, tcode TEXT, PRIMARY KEY (role, tcode));
CREATE TABLE IF NOT EXISTS role_auth (      -- AGR_1251: object, value, activity (02 change, 03 display, *)
    role TEXT, object TEXT, value TEXT, actvt TEXT, PRIMARY KEY (role, object, value, actvt));
CREATE TABLE IF NOT EXISTS usr_role (       -- AGR_USERS: assignment with validity
    bname TEXT, role TEXT, valid_from TEXT, valid_to TEXT DEFAULT '9999-12-31',
    PRIMARY KEY (bname, role));
CREATE TABLE IF NOT EXISTS usr_session (    -- SM04
    token TEXT PRIMARY KEY, bname TEXT, created TEXT, last_seen TEXT, ip TEXT);
CREATE TABLE IF NOT EXISTS access_request ( -- AMS: access / unlock / password requests
    reqid INTEGER PRIMARY KEY AUTOINCREMENT, bname TEXT, typ TEXT, role TEXT DEFAULT '',
    valid_to TEXT DEFAULT '', reason TEXT DEFAULT '', status TEXT DEFAULT 'O',
    created TEXT, decided_by TEXT DEFAULT '', decided TEXT DEFAULT '', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS audit_log (      -- SM20 security audit log
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, bname TEXT, ip TEXT DEFAULT '',
    tcode TEXT DEFAULT '', object TEXT DEFAULT '', objkey TEXT DEFAULT '', action TEXT,
    detail TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS audit_ts ON audit_log (ts);
CREATE INDEX IF NOT EXISTS audit_user ON audit_log (bname, ts);
"""
