"""SQLite database (built into Python). Table names follow SAP where useful."""
import os
import sqlite3
import threading

from .config import NUMBER_RANGES

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "mm.db")

# One writer at a time, like an SAP enqueue on the whole stock.
WRITE_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS plant (          -- T001W
    werks TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT);
CREATE TABLE IF NOT EXISTS sloc (           -- T001L
    werks TEXT, lgort TEXT, name TEXT NOT NULL,
    bin_managed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (werks, lgort));
CREATE TABLE IF NOT EXISTS bin (            -- LAGP (simplified)
    werks TEXT, lgort TEXT, lgpla TEXT, bin_type TEXT,
    blocked INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (werks, lgort, lgpla));
CREATE TABLE IF NOT EXISTS material (       -- MARA + MAKT
    matnr TEXT PRIMARY KEY, maktx TEXT NOT NULL, mtart TEXT NOT NULL,
    meins TEXT NOT NULL, matkl TEXT, bklas TEXT NOT NULL,
    ersda TEXT, ernam TEXT);
CREATE TABLE IF NOT EXISTS material_plant ( -- MARC
    matnr TEXT, werks TEXT,
    minbe INTEGER NOT NULL DEFAULT 0,   -- reorder point (milli)
    eisbe INTEGER NOT NULL DEFAULT 0,   -- safety stock (milli)
    PRIMARY KEY (matnr, werks));
CREATE TABLE IF NOT EXISTS valuation (      -- MBEW
    matnr TEXT, bwkey TEXT,
    vprsv TEXT NOT NULL,                -- V = moving average, S = standard
    verpr INTEGER NOT NULL DEFAULT 0,   -- moving average price (cents / peinh)
    stprs INTEGER NOT NULL DEFAULT 0,   -- standard price (cents / peinh)
    peinh INTEGER NOT NULL DEFAULT 1,   -- price unit
    lbkum INTEGER NOT NULL DEFAULT 0,   -- total valuated stock (milli)
    salk3 INTEGER NOT NULL DEFAULT 0,   -- total stock value (cents)
    PRIMARY KEY (matnr, bwkey));
CREATE TABLE IF NOT EXISTS quant (          -- LQUA: stock per bin with GR date
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matnr TEXT, werks TEXT, lgort TEXT, lgpla TEXT NOT NULL DEFAULT '',
    insmk TEXT NOT NULL,                -- U / Q / B
    qty INTEGER NOT NULL,               -- milli
    wdatu TEXT NOT NULL,                -- goods receipt date (FIFO key)
    mblnr TEXT, mjahr INTEGER);
CREATE INDEX IF NOT EXISTS ix_quant ON quant (matnr, werks, lgort, insmk, wdatu);
CREATE TABLE IF NOT EXISTS vendor (lifnr TEXT PRIMARY KEY, name TEXT, city TEXT);
CREATE TABLE IF NOT EXISTS cost_center (
    kostl TEXT PRIMARY KEY, name TEXT,
    kosar TEXT, khinr TEXT, verak TEXT);   -- category, hierarchy node, owner
CREATE TABLE IF NOT EXISTS po_header (      -- EKKO
    ebeln TEXT PRIMARY KEY, lifnr TEXT, bedat TEXT, ernam TEXT, erdat TEXT);
CREATE TABLE IF NOT EXISTS po_item (        -- EKPO
    ebeln TEXT, ebelp INTEGER, matnr TEXT, werks TEXT, lgort TEXT,
    menge INTEGER NOT NULL,             -- ordered (milli)
    netpr INTEGER NOT NULL,             -- cents per peinh
    peinh INTEGER NOT NULL DEFAULT 1,
    wemng INTEGER NOT NULL DEFAULT 0,   -- received (milli)
    elikz INTEGER NOT NULL DEFAULT 0,   -- delivery completed
    PRIMARY KEY (ebeln, ebelp));
CREATE TABLE IF NOT EXISTS mat_doc (        -- MKPF
    mblnr TEXT, mjahr INTEGER, budat TEXT, bldat TEXT, cpudt TEXT,
    usnam TEXT, bktxt TEXT, xblnr TEXT, tcode TEXT,
    PRIMARY KEY (mblnr, mjahr));
CREATE TABLE IF NOT EXISTS mat_doc_item (   -- MSEG
    mblnr TEXT, mjahr INTEGER, zeile INTEGER,
    bwart TEXT, xauto INTEGER NOT NULL DEFAULT 0,
    matnr TEXT, werks TEXT, lgort TEXT, lgpla TEXT, insmk TEXT,
    shkzg TEXT,                         -- S = plus (debit), H = minus (credit)
    menge INTEGER, meins TEXT,
    dmbtr INTEGER,                      -- movement value (cents)
    salk INTEGER,                       -- change of stock value (cents)
    ebeln TEXT, ebelp INTEGER, lifnr TEXT, kostl TEXT, aufnr TEXT,
    sgtxt TEXT,
    smbln TEXT, sjahr INTEGER, smblp INTEGER,   -- reference to reversed doc
    canceled INTEGER NOT NULL DEFAULT 0,
    belnr TEXT,
    PRIMARY KEY (mblnr, mjahr, zeile));
CREATE TABLE IF NOT EXISTS mat_doc_piece ( -- which quants a line touched
    mblnr TEXT, mjahr INTEGER, zeile INTEGER, lgpla TEXT, wdatu TEXT,
    qty INTEGER);
CREATE INDEX IF NOT EXISTS ix_piece ON mat_doc_piece (mblnr, mjahr, zeile);
CREATE INDEX IF NOT EXISTS ix_mseg_mat ON mat_doc_item (matnr, werks);
CREATE TABLE IF NOT EXISTS acc_doc (        -- BKPF
    belnr TEXT, gjahr INTEGER, blart TEXT, budat TEXT, usnam TEXT,
    awkey TEXT, bktxt TEXT, PRIMARY KEY (belnr, gjahr));
CREATE TABLE IF NOT EXISTS acc_doc_item (   -- BSEG
    belnr TEXT, gjahr INTEGER, buzei INTEGER, hkont TEXT, shkzg TEXT,
    dmbtr INTEGER, ktosl TEXT, matnr TEXT, werks TEXT, menge INTEGER,
    zeile INTEGER,
    kostl TEXT, aufnr TEXT, paobj TEXT,     -- CO account assignment
    PRIMARY KEY (belnr, gjahr, buzei));
CREATE TABLE IF NOT EXISTS price_history (  -- like MBEWH / CKM3 view
    id INTEGER PRIMARY KEY AUTOINCREMENT, matnr TEXT, bwkey TEXT,
    ts TEXT, budat TEXT, ref TEXT, reason TEXT,
    old_price INTEGER, new_price INTEGER, peinh INTEGER,
    lbkum INTEGER, salk3 INTEGER);
CREATE TABLE IF NOT EXISTS number_range (object TEXT PRIMARY KEY, current INTEGER);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


_MIGRATED = set()


def open_db(path=None):
    """Open the database (no schema work): WAL journal, sensible pragmas."""
    path = path or os.environ.get("MM_DB") or DEFAULT_DB
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30,
                           isolation_level=None)  # we manage transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")      # readers never wait for a writer
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect(path=None):
    """Open the database; the schema and data migrations run once per database file
    and process (every time for in-memory databases)."""
    path = path or os.environ.get("MM_DB") or DEFAULT_DB
    conn = open_db(path)
    if path == ":memory:" or os.path.abspath(path) not in _MIGRATED:
        migrate_schema(conn)
        if path != ":memory:":
            _MIGRATED.add(os.path.abspath(path))
    return conn


def migrate_schema(conn):
    conn.executescript(SCHEMA)
    from co.schema import CO_SCHEMA, CO_NUMBER_RANGES, MM_COLUMN_ADDS
    from fi.schema import FI_SCHEMA, FI_COLUMN_ADDS
    from fi.config import CHART, NUMBER_RANGES as FI_RANGES
    from pur.schema import PUR_SCHEMA, PUR_COLUMN_ADDS, PUR_NUMBER_RANGES
    from md.schema import MD_SCHEMA, MD_COLUMN_ADDS
    from pp.schema import PP_SCHEMA, PP_COLUMN_ADDS
    from sd.schema import SD_SCHEMA, SD_COLUMN_ADDS, SD_NUMBER_RANGES
    conn.executescript(CO_SCHEMA)
    conn.executescript(PUR_SCHEMA)
    conn.executescript(MD_SCHEMA)
    conn.executescript(PP_SCHEMA)
    conn.executescript(SD_SCHEMA)
    for adds in (MM_COLUMN_ADDS, FI_COLUMN_ADDS, PUR_COLUMN_ADDS, MD_COLUMN_ADDS,
                 PP_COLUMN_ADDS, SD_COLUMN_ADDS):   # upgrades
        for table, cols in adds.items():
            have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
            for col, typ in cols:
                if col not in have:
                    conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, typ))
    conn.executescript(FI_SCHEMA)
    from sec.schema import SEC_SCHEMA
    conn.executescript(SEC_SCHEMA)
    ranges = list(NUMBER_RANGES.items()) + list(CO_NUMBER_RANGES.items()) + \
        [("FI_" + k, v) for k, v in FI_RANGES.items()] + \
        list(PUR_NUMBER_RANGES.items()) + list(SD_NUMBER_RANGES.items())
    for obj, start in ranges:
        conn.execute("INSERT OR IGNORE INTO number_range VALUES (?, ?)",
                     (obj, start - 1))
    for k, v in CHART.items():                      # FS00 initial chart
        conn.execute("INSERT OR IGNORE INTO gl_account (hkont,txt,typ,fsv,recon,oi,tax)"
                     " VALUES (?,?,?,?,?,?,?)", (k, v[0], v[1], v[2], v[3], v[4], v[5]))
    from .migrations import migrate
    migrate(conn)
    # FS00 accounts created by the user are known to the MM texts / P&L classification
    from .config import GL_ACCOUNTS, PNL_ACCOUNTS
    for r in conn.execute("SELECT hkont, txt, typ FROM gl_account"):
        GL_ACCOUNTS.setdefault(r["hkont"], r["txt"])
        if r["typ"] == "PL":
            PNL_ACCOUNTS.add(r["hkont"])
    return conn


def backup(path=None, target_dir=None, keep=14):
    """Copy the database with SQLite's online backup (safe while the server runs)."""
    import glob
    import time
    path = path or os.environ.get("MM_DB") or DEFAULT_DB
    if not os.path.exists(path):
        return None
    target_dir = target_dir or os.path.join(os.path.dirname(path), "backup")
    os.makedirs(target_dir, exist_ok=True)
    dst = os.path.join(target_dir, "mm_%s.db" % time.strftime("%Y%m%d_%H%M%S"))     # real time, not business date
    src = sqlite3.connect(path)
    out = sqlite3.connect(dst)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    files = sorted(glob.glob(os.path.join(target_dir, "mm_*.db")))
    for old in files[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


def restore(backup_file, path=None):
    path = path or os.environ.get("MM_DB") or DEFAULT_DB
    src = sqlite3.connect(backup_file)
    if src.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        src.close()
        raise ValueError("Backup %s is damaged" % backup_file)
    out = sqlite3.connect(path)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()
    _MIGRATED.discard(os.path.abspath(path))
    return path


def integrity_ok(conn):
    return conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def next_number(conn, obj):
    with transaction(conn):
        return _next_number(conn, obj)


def _next_number(conn, obj):
    conn.execute("UPDATE number_range SET current = current + 1 WHERE object = ?",
                 (obj,))
    return conn.execute("SELECT current FROM number_range WHERE object = ?",
                        (obj,)).fetchone()[0]


_DEPTH = {}


class transaction:
    """with transaction(conn): ... -> commit, or rollback on any error.
    Nested use (e.g. billing posts a goods issue inside its own transaction)
    joins the outer transaction through a SAVEPOINT: if the inner block fails,
    only its own writes are undone, even when the caller catches the error and
    continues; everything is committed (or rolled back) by the outermost block."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        WRITE_LOCK.acquire()
        k = id(self.conn)
        try:
            depth = _DEPTH.get(k, 0)
            if depth == 0:
                self.conn.execute("BEGIN IMMEDIATE")
            else:
                self.conn.execute("SAVEPOINT sp%d" % depth)
            _DEPTH[k] = depth + 1
        except BaseException:
            WRITE_LOCK.release()
            raise
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        k = id(self.conn)
        try:
            _DEPTH[k] -= 1
            depth = _DEPTH[k]
            if depth == 0:
                del _DEPTH[k]
                self.conn.execute("COMMIT" if exc_type is None else "ROLLBACK")
            else:
                if exc_type is not None:
                    self.conn.execute("ROLLBACK TO sp%d" % depth)
                self.conn.execute("RELEASE sp%d" % depth)
        finally:
            WRITE_LOCK.release()
        return False


def atomic(fn):
    """Decorator: the function always runs inside a transaction (joins the caller's)."""
    import functools

    @functools.wraps(fn)
    def wrapper(conn, *args, **kw):
        with transaction(conn):
            return fn(conn, *args, **kw)
    return wrapper


def rows(cur):
    return [dict(r) for r in cur.fetchall()]
