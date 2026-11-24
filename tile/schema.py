"""Tables of the ceramic tile functions (quantities in milli, money in cents)."""

TILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tile_product (      -- tile master: format, ISO 13006 group, grade 2 material
    matnr TEXT PRIMARY KEY, grade2 TEXT, fmt TEXT, bgroup TEXT,
    m2_box INTEGER NOT NULL DEFAULT 1440,         -- m2 per box (milli)
    boxes_pal INTEGER NOT NULL DEFAULT 40);
CREATE TABLE IF NOT EXISTS tile_lot (           -- lot = one shade + one caliber of one sorting
    lot TEXT PRIMARY KEY, matnr TEXT, werks TEXT, lgort TEXT, aufnr TEXT, sort_id INTEGER,
    prod_date TEXT, grade TEXT, shade TEXT, caliber TEXT,
    qty INTEGER NOT NULL, issued INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'OK',            -- OK / HOLD (lab pending) / BLOCK (failed)
    note TEXT);
CREATE INDEX IF NOT EXISTS ix_tile_lot ON tile_lot (matnr, status);
CREATE TABLE IF NOT EXISTS tile_sort (          -- sorting result of one shift / day of an order
    id INTEGER PRIMARY KEY AUTOINCREMENT, aufnr TEXT, day TEXT, matnr TEXT, arbpl TEXT,
    grade1 INTEGER, grade2 INTEGER, grade3 INTEGER, broken INTEGER,
    mblnr TEXT, usnam TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS ix_tile_sort ON tile_sort (day);
CREATE TABLE IF NOT EXISTS tile_defect (
    sort_id INTEGER, code TEXT, qty INTEGER, PRIMARY KEY (sort_id, code));
CREATE TABLE IF NOT EXISTS tile_test (          -- lab test of a lot
    id INTEGER PRIMARY KEY AUTOINCREMENT, lot TEXT, day TEXT,
    water_abs INTEGER,                            -- % x 100
    strength INTEGER,                             -- breaking strength N
    planarity INTEGER,                            -- deviation % x 100
    size_dev INTEGER,                             -- deviation of the work size % x 100
    result TEXT, failed TEXT, usnam TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS tile_pick (          -- lots given to a delivery item
    vbeln TEXT, posnr INTEGER, lot TEXT, qty INTEGER, done INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (vbeln, posnr, lot));
CREATE TABLE IF NOT EXISTS energy_meter (
    meter TEXT PRIMARY KEY, text TEXT, kind TEXT, unit TEXT, area TEXT,
    price INTEGER NOT NULL,                       -- cents per 1000 units (5 decimals of money per unit)
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS energy_reading (
    meter TEXT, day TEXT, reading INTEGER,        -- meter reading x 1000
    usnam TEXT, ts TEXT, PRIMARY KEY (meter, day));
"""


COLUMN_ADDS = {"tile_product": [("kg_m2", "INTEGER NOT NULL DEFAULT 20000")]}   # weight per m2 (milli kg)


def install(conn):
    conn.executescript(TILE_SCHEMA)
    for table, cols in COLUMN_ADDS.items():
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        for col, typ in cols:
            if col not in have:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, typ))
