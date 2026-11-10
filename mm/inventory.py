"""Physical inventory (MI01 / MI03 / MI04 / MI11 / MI20 / MI07 / MICN).

MI01  create a count document for a storage location (all or selected
      materials); with "freeze" the book quantity is taken now and goods
      movements of those materials in that storage location are blocked
      until the document is posted (posting block, message M7 140).
MI04  enter the count (quantity or "zero"); MI11 recount selected items
      (new document, the old items are closed).
MI20  difference list: book vs count, valued at the current price.
MI07  post the differences: 701 surplus / 702 shortage to the inventory
      difference account (233000) with reference to the count document.
MICN  cycle counting proposal by ABC class (A 30, B 90, C 180 days).
"""
import datetime

from mm.db import atomic, next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, value_of
from mm import util as mmclock

INV_SCHEMA = """
CREATE TABLE IF NOT EXISTS inv_doc (        -- IKPF
    iblnr TEXT PRIMARY KEY, gjahr INTEGER, werks TEXT, lgort TEXT, plan_date TEXT,
    count_date TEXT, status TEXT DEFAULT 'CRTD', freeze INTEGER DEFAULT 1, ernam TEXT,
    erdat TEXT, posted_by TEXT, mblnr TEXT, mjahr INTEGER, reason TEXT DEFAULT '',
    ref_iblnr TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS inv_doc_item (   -- ISEG
    iblnr TEXT, zeili INTEGER, matnr TEXT, lgpla TEXT DEFAULT '', insmk TEXT DEFAULT 'U',
    buchm INTEGER DEFAULT 0, menge INTEGER, xnull INTEGER DEFAULT 0, counted INTEGER DEFAULT 0,
    counted_by TEXT, recount INTEGER DEFAULT 0, diff_qty INTEGER DEFAULT 0,
    diff_value INTEGER DEFAULT 0, mblnr TEXT, zeile INTEGER, PRIMARY KEY (iblnr, zeili));
CREATE INDEX IF NOT EXISTS inv_item_mat ON inv_doc_item (matnr);
"""
STATUS = {"CRTD": "Created (not counted)", "CNTD": "Counted", "POST": "Posted", "RCNT": "Recounted"}
CYCLE_DAYS = {"A": 30, "B": 90, "C": 180}


def check_block(conn, matnr, werks, lgort, tcode=""):
    """Posting block during a frozen count (called by every goods movement)."""
    if tcode == "MI07" or not matnr:
        return
    r = conn.execute("SELECT d.iblnr FROM inv_doc d JOIN inv_doc_item i ON i.iblnr=d.iblnr WHERE "
                     "d.status IN ('CRTD','CNTD') AND d.freeze=1 AND d.werks=? AND d.lgort=? AND "
                     "i.matnr=? AND i.recount=0 LIMIT 1", (werks, lgort, matnr)).fetchone()
    if r:
        raise MMError("Material %s in %s/%s is blocked by physical inventory document %s "
                      "(post or delete the count first)" % (matnr, werks, lgort, r[0]), "M7", "140")


def _doc(conn, iblnr):
    d = conn.execute("SELECT * FROM inv_doc WHERE iblnr=?", (str(iblnr or ""),)).fetchone()
    if not d:
        raise MMError("Physical inventory document %s does not exist" % iblnr, "M7", "141")
    return d


def _book(conn, matnr, werks, lgort):
    """Book quantity per bin and stock type (unrestricted, quality, blocked)."""
    return rows(conn.execute("SELECT lgpla, insmk, SUM(qty) AS qty FROM quant WHERE matnr=? AND "
                             "werks=? AND lgort=? GROUP BY lgpla, insmk HAVING SUM(qty)<>0",
                             (matnr, werks, lgort)))


@atomic
def create(conn, werks, lgort, matnrs=None, plan_date=None, user="", freeze=True, _ref=""):
    """MI01. matnrs: list of materials (empty = every material with stock in the location)."""
    werks, lgort = (werks or "").upper(), (lgort or "").upper()
    if not conn.execute("SELECT 1 FROM sloc WHERE werks=? AND lgort=?", (werks, lgort)).fetchone():
        raise MMError("Storage location %s/%s does not exist" % (werks, lgort), "M7", "018")
    mats = [m.strip().upper() for m in (matnrs or []) if m and m.strip()]
    if not mats:
        mats = [r[0] for r in conn.execute("SELECT DISTINCT matnr FROM quant WHERE werks=? AND lgort=? "
                                           "AND qty<>0 ORDER BY matnr", (werks, lgort))]
    if not mats:
        raise MMError("No stock in %s/%s - enter the materials to count" % (werks, lgort), "M7", "142")
    for m in mats:
        if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (m,)).fetchone():
            raise MMError("Material %s does not exist" % m, "M7", "002")
        r = conn.execute("SELECT d.iblnr FROM inv_doc d JOIN inv_doc_item i ON i.iblnr=d.iblnr WHERE "
                         "d.status IN ('CRTD','CNTD') AND d.werks=? AND d.lgort=? AND i.matnr=? AND "
                         "i.recount=0", (werks, lgort, m)).fetchone()
        if r and r[0] != _ref:
            raise MMError("Material %s is already in open count document %s" % (m, r[0]), "M7", "143")
    iblnr = str(next_number(conn, "PHYSINV"))
    pd = parse_date(plan_date)
    conn.execute("INSERT INTO inv_doc (iblnr,gjahr,werks,lgort,plan_date,status,freeze,ernam,erdat,ref_iblnr) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?)", (iblnr, int(pd[:4]), werks, lgort, pd, "CRTD",
                                                  1 if freeze else 0, user, now_ts(), _ref))
    n = 0
    for m in mats:
        book = _book(conn, m, werks, lgort) or [dict(lgpla="", insmk="U", qty=0)]
        for b in book:
            n += 1
            conn.execute("INSERT INTO inv_doc_item (iblnr,zeili,matnr,lgpla,insmk,buchm) VALUES "
                         "(?,?,?,?,?,?)", (iblnr, n, m, b["lgpla"] or "", b["insmk"], b["qty"]))
    return iblnr


def display(conn, iblnr):
    d = dict(_doc(conn, iblnr))
    d["status_text"] = STATUS.get(d["status"], d["status"])
    d["items"] = rows(conn.execute("SELECT i.*, m.maktx, m.meins FROM inv_doc_item i JOIN material m "
                                   "USING (matnr) WHERE iblnr=? ORDER BY zeili", (d["iblnr"],)))
    return d


def documents(conn, werks=None, status=None):
    sql, a = ("SELECT d.*, (SELECT COUNT(*) FROM inv_doc_item i WHERE i.iblnr=d.iblnr) AS items "
              "FROM inv_doc d WHERE 1=1"), []
    if werks:
        sql += " AND werks=?"
        a.append(werks)
    if status:
        sql += " AND status=?"
        a.append(status)
    out = rows(conn.execute(sql + " ORDER BY iblnr DESC", a))
    for r in out:
        r["status_text"] = STATUS.get(r["status"], r["status"])
    return out


@atomic
def count(conn, iblnr, items, user="", count_date=None):
    """MI04. items: [{zeili, qty, zero}] - qty empty and zero false = not counted yet."""
    d = _doc(conn, iblnr)
    if d["status"] not in ("CRTD", "CNTD"):
        raise MMError("Document %s is %s - no count possible" % (iblnr, STATUS[d["status"]]), "M7", "144")
    for it in items or []:
        z = int(it.get("zeili") or 0)
        row = conn.execute("SELECT * FROM inv_doc_item WHERE iblnr=? AND zeili=?", (d["iblnr"], z)).fetchone()
        if not row:
            raise MMError("Item %s does not exist in document %s" % (z, iblnr), "M7", "145")
        if row["recount"]:
            continue
        zero = bool(it.get("zero"))
        if not zero and str(it.get("qty") or "").strip() == "":
            continue
        q = 0 if zero else parse_qty(it.get("qty"), allow_zero=True)
        conn.execute("UPDATE inv_doc_item SET menge=?, xnull=?, counted=1, counted_by=?, diff_qty=? "
                     "WHERE iblnr=? AND zeili=?", (q, 1 if zero else 0, user, q - row["buchm"], d["iblnr"], z))
    open_ = conn.execute("SELECT COUNT(*) FROM inv_doc_item WHERE iblnr=? AND counted=0 AND recount=0",
                         (d["iblnr"],)).fetchone()[0]
    conn.execute("UPDATE inv_doc SET status=?, count_date=? WHERE iblnr=?",
                 ("CRTD" if open_ else "CNTD", parse_date(count_date), d["iblnr"]))
    return open_


def _price(conn, matnr, werks):
    v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?", (matnr, werks)).fetchone()
    if not v:
        return 0, 1
    return (v["stprs"] if v["vprsv"] == "S" else v["verpr"]), v["peinh"] or 1


def differences(conn, iblnr, threshold=None):
    """MI20: book vs count with value; threshold (cents) marks large differences."""
    d = display(conn, iblnr)
    for it in d["items"]:
        p, pe = _price(conn, it["matnr"], d["werks"])
        it["price"] = p
        it["diff_value"] = value_of(abs(it["diff_qty"]), p, pe) * (1 if it["diff_qty"] >= 0 else -1) \
            if it["counted"] else 0
        it["big"] = bool(threshold and abs(it["diff_value"]) >= threshold)
    d["total"] = sum(i["diff_value"] for i in d["items"])
    return d


@atomic
def recount(conn, iblnr, zeilis, user=""):
    """MI11: new count document for the selected items; the old items are closed."""
    d = _doc(conn, iblnr)
    if d["status"] == "POST":
        raise MMError("Document %s is already posted" % iblnr, "M7", "146")
    sel = [int(z) for z in zeilis or []]
    its = [r for r in conn.execute("SELECT * FROM inv_doc_item WHERE iblnr=? AND recount=0",
                                   (d["iblnr"],)).fetchall() if r["zeili"] in sel]
    if not its:
        raise MMError("Select the items to recount", "M7", "147")
    for m in {r["matnr"] for r in its}:      # the whole material is counted again (all its bins)
        conn.execute("UPDATE inv_doc_item SET recount=1 WHERE iblnr=? AND matnr=?", (d["iblnr"], m))
    new = create(conn, d["werks"], d["lgort"], sorted({r["matnr"] for r in its}), mmclock.today().isoformat(),
                 user, bool(d["freeze"]), _ref=d["iblnr"])
    left = conn.execute("SELECT COUNT(*) FROM inv_doc_item WHERE iblnr=? AND recount=0",
                        (d["iblnr"],)).fetchone()[0]
    if not left:
        conn.execute("UPDATE inv_doc SET status='RCNT' WHERE iblnr=?", (d["iblnr"],))
    return new


def post(conn, iblnr, budat=None, user="", reason=""):
    """MI07: post 701 / 702 for every counted difference."""
    from mm.posting import post_goods_movement
    with transaction(conn):
        d = _doc(conn, iblnr)
        if d["status"] == "POST":
            raise MMError("Document %s is already posted" % iblnr, "M7", "146")
        its = conn.execute("SELECT * FROM inv_doc_item WHERE iblnr=? AND recount=0 ORDER BY zeili",
                           (d["iblnr"],)).fetchall()
        if any(not i["counted"] for i in its):
            raise MMError("Not every item of %s is counted (MI04)" % iblnr, "M7", "148")
        lines, keys = [], []
        for i in its:
            diff = i["menge"] - i["buchm"]
            if diff:
                lines.append(dict(bwart="701" if diff > 0 else "702", matnr=i["matnr"], werks=d["werks"],
                                  lgort=d["lgort"], lgpla=i["lgpla"], insmk=i["insmk"],
                                  qty="%.3f" % (abs(diff) / 1000.0),
                                  sgtxt=("Phys. inventory %s %s" % (d["iblnr"], reason or ""))[:50]))
                keys.append(i["zeili"])
        mb = None
        if lines:
            mb = post_goods_movement(conn, {"budat": parse_date(budat), "xblnr": d["iblnr"],
                                            "bktxt": "Phys. inv. %s" % d["iblnr"]}, lines, user, tcode="MI07")
            for z, (zeile, salk) in zip(keys, conn.execute(
                    "SELECT zeile, salk FROM mat_doc_item WHERE mblnr=? AND mjahr=? ORDER BY zeile",
                    (mb["mblnr"], mb["mjahr"])).fetchall()):
                conn.execute("UPDATE inv_doc_item SET mblnr=?, zeile=?, diff_value=? WHERE iblnr=? AND zeili=?",
                             (mb["mblnr"], zeile, salk, d["iblnr"], z))
        conn.execute("UPDATE inv_doc SET status='POST', posted_by=?, mblnr=?, mjahr=?, reason=? WHERE iblnr=?",
                     (user, mb and mb["mblnr"], mb and mb["mjahr"], (reason or "")[:60], d["iblnr"]))
    return {"iblnr": d["iblnr"], "mblnr": mb and mb["mblnr"], "lines": len(lines),
            "message": "Differences of %s posted%s" % (d["iblnr"], " (material document %s)" % mb["mblnr"]
                                                       if mb else " - no differences, document closed")}


@atomic
def delete(conn, iblnr, user=""):
    d = _doc(conn, iblnr)
    if d["status"] == "POST":
        raise MMError("Document %s is posted and cannot be deleted" % iblnr, "M7", "146")
    conn.execute("UPDATE inv_doc SET status='RCNT', reason='deleted by ' || ? WHERE iblnr=?", (user, d["iblnr"]))
    conn.execute("UPDATE inv_doc_item SET recount=1 WHERE iblnr=?", (d["iblnr"],))


def cycle_proposal(conn, werks, today=None):
    """MICN: materials with stock whose last count is older than the ABC interval."""
    t = today or mmclock.today()
    out = []
    for r in conn.execute("SELECT q.matnr, q.lgort, SUM(q.qty) AS qty, m.maktx, COALESCE(mp.abcin,'') AS abcin "
                          "FROM quant q JOIN material m USING (matnr) LEFT JOIN material_plant mp ON "
                          "mp.matnr=q.matnr AND mp.werks=q.werks WHERE q.werks=? GROUP BY q.matnr, q.lgort "
                          "HAVING SUM(q.qty)>0 ORDER BY q.matnr", (werks,)).fetchall():
        abc = r["abcin"] or "C"
        last = conn.execute("SELECT MAX(d.count_date) FROM inv_doc d JOIN inv_doc_item i ON i.iblnr=d.iblnr "
                            "WHERE d.werks=? AND d.lgort=? AND i.matnr=? AND d.status='POST'",
                            (werks, r["lgort"], r["matnr"])).fetchone()[0]
        due = (datetime.date.fromisoformat(last) + datetime.timedelta(days=CYCLE_DAYS[abc])) if last else t
        if due <= t:
            out.append(dict(matnr=r["matnr"], maktx=r["maktx"], lgort=r["lgort"], qty=r["qty"], abc=abc,
                            last=last or "", due=due.isoformat()))
    return out
