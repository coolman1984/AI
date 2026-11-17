"""Quality management - from the goods receipt to the released stock.

1. Inspection plan (QP01): the characteristics of a material - a measured value with lower /
   upper limit, or an attribute (OK / not OK).
2. Inspection lot (QA32): created automatically when a goods receipt of a QM-active material
   (material master: 'post to inspection stock') is posted - from a purchase order (origin 01)
   or a production order (04) - or manually for stock (08, moves it to inspection stock).
   The stock stays in quality-inspection stock: it cannot be used, sold or released by hand.
3. Results (QE51N): every value is valuated against its limits.
4. Usage decision (QA11): accepted quantity -> unrestricted stock (321), rejected quantity ->
   blocked stock (350). A rejection from a vendor opens a vendor complaint automatically.
5. Quality notification (QM01): complaint / non-conformance with cause and corrective action.
"""
import datetime

from mm import util as clock
from mm.db import _next_number, transaction
from mm.util import MMError, now_ts, parse_date, parse_measure, parse_qty, qty_out

ORIGINS = {"01": "Goods receipt (purchase order)", "04": "Goods receipt (production order)",
           "08": "Stock (manual)"}
DEFECTS = {"DIM": "Dimension out of tolerance", "SURF": "Surface / scratches", "DMG": "Damaged in transport",
           "COL": "Colour / finish", "FUNC": "Function failure", "DOC": "Certificate / document missing",
           "CONT": "Contamination", "PACK": "Packaging", "OTH": "Other"}
NOTIF_TYPES = {"Q1": "Customer complaint", "Q2": "Vendor complaint", "Q3": "Internal non-conformance"}
STATUS = {"OPEN": "Open", "RESULTS": "Results recorded", "UD": "Usage decision made", "CANCELLED": "Cancelled"}


def _m(v):
    return None if v is None else v / 1000.0


# ------------------------------------------------------------------ inspection plan
def save_plan(conn, matnr, werks, chars, user):
    matnr, werks = (matnr or "").strip().upper(), (werks or "1000").strip().upper()
    if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?", (matnr, werks)).fetchone():
        raise MMError("Material %s does not exist in plant %s" % (matnr or "''", werks), "QP", "901")
    rows = []
    for n, c in enumerate(chars or [], start=1):
        name = (c.get("name") or "").strip()
        if not name:
            continue
        kind = (c.get("kind") or "N").upper()
        if kind not in ("N", "A"):
            raise MMError("Characteristic %d: type must be N (measured) or A (attribute)" % n, "QP", "902")
        lsl = usl = None
        if kind == "N":
            lsl = parse_measure(c["lsl"], "lower limit") if str(c.get("lsl") or "").strip() else None
            usl = parse_measure(c["usl"], "upper limit") if str(c.get("usl") or "").strip() else None
            if lsl is None and usl is None:
                raise MMError("Characteristic %s: enter a lower and / or upper limit" % name, "QP", "903")
            if lsl is not None and usl is not None and lsl >= usl:
                raise MMError("Characteristic %s: the lower limit must be below the upper limit" % name, "QP", "904")
        rows.append((name[:60], kind, lsl, usl, (c.get("unit") or "")[:10]))
    if not rows:
        raise MMError("Enter at least one characteristic", "QP", "905")
    with transaction(conn):
        conn.execute("DELETE FROM qm_char WHERE matnr=? AND werks=?", (matnr, werks))
        for i, (name, kind, lsl, usl, unit) in enumerate(rows, start=1):
            conn.execute("INSERT INTO qm_char VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (matnr, werks, i * 10, name, kind, lsl, usl, unit, user, now_ts()))
    return {"message": "Inspection plan of %s: %d characteristic(s)" % (matnr, len(rows))}


def plan(conn, matnr, werks="1000"):
    out = []
    for r in conn.execute("SELECT * FROM qm_char WHERE matnr=? AND werks=? ORDER BY seq",
                          ((matnr or "").upper(), werks)):
        out.append(dict(r, lsl=_m(r["lsl"]), usl=_m(r["usl"])))
    return out


def qm_active(conn, matnr, werks):
    r = conn.execute("SELECT insmk FROM material_plant WHERE matnr=? AND werks=?", (matnr, werks)).fetchone()
    return bool(r and r["insmk"])


def set_active(conn, matnr, werks, active, user):
    with transaction(conn):
        if not conn.execute("UPDATE material_plant SET insmk=? WHERE matnr=? AND werks=?",
                            (1 if active else 0, (matnr or "").upper(), werks)).rowcount:
            raise MMError("Material %s does not exist in plant %s" % (matnr, werks), "QP", "901")
    return {"message": "Inspection at goods receipt %s for %s" % ("active" if active else "off", matnr.upper())}


# ------------------------------------------------------------------ inspection lots
def _new_lot(conn, origin, line, user, day):
    no = str(_next_number(conn, "QLOT"))
    conn.execute("INSERT INTO qm_lot (prueflos,origin,matnr,werks,lgort,lgpla,qty,meins,lifnr,ebeln,aufnr,mblnr,"
                 "mjahr,zeile,created,usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (no, origin, line["matnr"], line["werks"], line["lgort"], line.get("lgpla") or "", line["menge"],
                  line.get("meins"), line.get("lifnr"), line.get("ebeln"), line.get("aufnr"), line.get("mblnr"),
                  line.get("mjahr"), line.get("zeile"), day, user, now_ts()))
    return no


def lots_from_document(conn, mblnr, mjahr, user, day):
    """called by the goods movement engine: a GR into inspection stock of a QM-active material"""
    made = []
    for l in conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=? AND bwart='101' AND shkzg='S' "
                          "AND insmk='Q'", (mblnr, mjahr)).fetchall():
        if l["matnr"] and qm_active(conn, l["matnr"], l["werks"]):
            made.append(_new_lot(conn, "01" if l["ebeln"] else "04", dict(l), user, day))
    return made


def check_manual_release(conn, line, bwart, tcode):
    """stock of an open inspection lot is released only by the usage decision"""
    if bwart in ("321", "350") and tcode != "QA11" and line.get("matnr"):
        r = conn.execute("SELECT prueflos FROM qm_lot WHERE matnr=? AND werks=? AND lgort=? AND status IN "
                         "('OPEN','RESULTS')", (line["matnr"], line["werks"], line["lgort"])).fetchone()
        if r:
            raise MMError("Stock of %s is in inspection lot %s - release it with the usage decision (QA11)"
                          % (line["matnr"], r["prueflos"]), "QA", "910")


def on_reversal(conn, mblnr, mjahr):
    """MBST of a goods receipt: its open lot is cancelled; after the usage decision it cannot be reversed"""
    for lot in conn.execute("SELECT * FROM qm_lot WHERE mblnr=? AND mjahr=?", (mblnr, mjahr)).fetchall():
        if lot["status"] == "UD":
            raise MMError("Inspection lot %s already has a usage decision - return the goods to the vendor "
                          "(movement 122) instead" % lot["prueflos"], "QA", "911")
        conn.execute("UPDATE qm_lot SET status='CANCELLED', ts=? WHERE prueflos=?", (now_ts(), lot["prueflos"]))


def create_lot(conn, data, user):
    """QA01: inspection of stock - the quantity is moved to inspection stock (322)"""
    from mm.posting import post_goods_movement
    matnr = (data.get("matnr") or "").strip().upper()
    werks = (data.get("werks") or "1000").strip().upper()
    lgort = (data.get("lgort") or "").strip().upper()
    qty = parse_qty(data.get("qty"))
    day = parse_date(data.get("datum"))
    with transaction(conn):
        res = post_goods_movement(conn, {"budat": day, "bktxt": "Inspection of stock"},
                                  [{"bwart": "322", "matnr": matnr, "werks": werks, "lgort": lgort,
                                    "qty": qty_out(qty)}], user, tcode="QA01")
        l = conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=? AND insmk='Q' AND shkzg='S'",
                         (res["mblnr"], res["mjahr"])).fetchone()
        no = _new_lot(conn, "08", dict(l), user, day)
    return {"prueflos": no, "message": "Inspection lot %s created - %s moved to inspection stock" % (no, qty_out(qty))}


def lots(conn, status=None, matnr=None, lifnr=None):
    q, a = "SELECT l.*, v.name vendor FROM qm_lot l LEFT JOIN vendor v ON v.lifnr=l.lifnr WHERE 1=1", []
    if status == "open":
        q += " AND l.status IN ('OPEN','RESULTS')"
    elif status:
        q += " AND l.status=?"
        a.append(status)
    if matnr:
        q += " AND l.matnr=?"
        a.append(matnr.upper())
    if lifnr:
        q += " AND l.lifnr=?"
        a.append(lifnr)
    today = clock.today()
    out = []
    for r in conn.execute(q + " ORDER BY l.created DESC, l.prueflos DESC", a).fetchall():
        d = dict(r)
        d["qty"], d["qty_ok"], d["qty_rej"] = qty_out(r["qty"]), qty_out(r["qty_ok"]), qty_out(r["qty_rej"])
        d["origin_text"], d["status_text"] = ORIGINS.get(r["origin"], r["origin"]), STATUS.get(r["status"])
        d["age"] = (today - datetime.date.fromisoformat(r["created"])).days if r["created"] else 0
        out.append(d)
    return out


def lot(conn, prueflos):
    r = conn.execute("SELECT l.*, v.name vendor, m.maktx FROM qm_lot l LEFT JOIN vendor v ON v.lifnr=l.lifnr "
                     "LEFT JOIN material m ON m.matnr=l.matnr WHERE prueflos=?", (str(prueflos),)).fetchone()
    if not r:
        raise MMError("Inspection lot %s does not exist" % prueflos, "QA", "901")
    d = dict(r)
    d["qty_m"] = r["qty"]
    d["qty"], d["qty_ok"], d["qty_rej"] = qty_out(r["qty"]), qty_out(r["qty_ok"]), qty_out(r["qty_rej"])
    d["origin_text"], d["status_text"] = ORIGINS.get(r["origin"], r["origin"]), STATUS.get(r["status"])
    res = {x["seq"]: x for x in conn.execute("SELECT * FROM qm_result WHERE prueflos=?", (r["prueflos"],))}
    d["chars"] = []
    for c in conn.execute("SELECT * FROM qm_char WHERE matnr=? AND werks=? ORDER BY seq", (r["matnr"], r["werks"])):
        x = res.get(c["seq"])
        d["chars"].append(dict(c, lsl=_m(c["lsl"]), usl=_m(c["usl"]), value=_m(x["value"]) if x else None,
                               ok=x["ok"] if x else None, valuation=x["valuation"] if x else None,
                               note=x["note"] if x else ""))
    d["defects"] = [dict(x, qty=qty_out(x["qty"]), text_d=DEFECTS.get(x["code"], x["code"]))
                    for x in conn.execute("SELECT * FROM qm_defect WHERE prueflos=?", (r["prueflos"],))]
    return d


def record(conn, prueflos, values, user):
    """QE51N: values = {seq: value} - a number for measured characteristics, OK / NOK for attributes"""
    L = lot(conn, prueflos)
    if L["status"] not in ("OPEN", "RESULTS"):
        raise MMError("Inspection lot %s is closed (%s)" % (prueflos, L["status_text"]), "QA", "902")
    chars = {c["seq"]: c for c in L["chars"]}
    if not chars:
        raise MMError("Material %s has no inspection plan (QP01) - make the usage decision directly" % L["matnr"],
                      "QA", "903")
    n = 0
    with transaction(conn):
        for k, v in (values or {}).items():
            seq = int(k)
            c = chars.get(seq)
            if not c or str(v).strip() == "":
                continue
            if c["kind"] == "A":
                t = str(v).strip().upper()
                if t not in ("OK", "NOK"):
                    raise MMError("%s: enter OK or NOK" % c["name"], "QA", "904")
                val, ok = None, 1 if t == "OK" else 0
            else:
                val = parse_measure(v, c["name"])
                lo = None if c["lsl"] is None else int(round(c["lsl"] * 1000))
                hi = None if c["usl"] is None else int(round(c["usl"] * 1000))
                ok = 1 if (lo is None or val >= lo) and (hi is None or val <= hi) else 0
            conn.execute("INSERT OR REPLACE INTO qm_result VALUES (?,?,?,?,?,?,?,?)",
                         (L["prueflos"], seq, val, ok, "A" if ok else "R", "", user, now_ts()))
            n += 1
        done = conn.execute("SELECT COUNT(*) FROM qm_result WHERE prueflos=?", (L["prueflos"],)).fetchone()[0]
        if done >= len(chars):
            conn.execute("UPDATE qm_lot SET status='RESULTS' WHERE prueflos=?", (L["prueflos"],))
    bad = conn.execute("SELECT COUNT(*) FROM qm_result WHERE prueflos=? AND valuation='R'", (L["prueflos"],)).fetchone()[0]
    return {"recorded": n, "rejected": bad,
            "message": "%d result(s) recorded%s" % (n, " - %d characteristic(s) out of tolerance" % bad if bad else "")}


def usage_decision(conn, prueflos, data, user):
    """QA11: accepted quantity -> unrestricted (321), rejected -> blocked (350)"""
    from mm.posting import post_goods_movement
    L = lot(conn, prueflos)
    if L["status"] not in ("OPEN", "RESULTS"):
        raise MMError("Inspection lot %s is closed (%s)" % (prueflos, L["status_text"]), "QA", "902")
    if L["chars"] and any(c["valuation"] is None for c in L["chars"]):
        raise MMError("Record all results first (QE51N) - %d characteristic(s) open"
                      % sum(1 for c in L["chars"] if c["valuation"] is None), "QA", "905")
    ok = parse_qty(data.get("qty_ok") if str(data.get("qty_ok") or "").strip() else "0", allow_zero=True)
    rej = parse_qty(data.get("qty_rej") if str(data.get("qty_rej") or "").strip() else "0", allow_zero=True)
    if ok + rej != L["qty_m"]:
        raise MMError("Accepted + rejected must equal the lot quantity %s" % L["qty"], "QA", "906")
    if rej and not data.get("defect"):
        raise MMError("Enter the defect of the rejected quantity", "QA", "907")
    defect = (data.get("defect") or "").upper()
    if defect and defect not in DEFECTS:
        raise MMError("Defect code %s does not exist" % defect, "QA", "908")
    if ok and any(c["valuation"] == "R" for c in L["chars"]) and not data.get("override"):
        raise MMError("Characteristics are out of tolerance - accept only with a reason (deviation release)",
                      "QA", "909")
    day = parse_date(data.get("datum"))
    code = "A" if not rej else "R" if not ok else "P"
    with transaction(conn):
        items = []
        base = {"matnr": L["matnr"], "werks": L["werks"], "lgort": L["lgort"], "lgpla": L["lgpla"] or ""}
        if ok:
            items.append(dict(base, bwart="321", qty=qty_out(ok), sgtxt="Lot %s accepted" % L["prueflos"]))
        if rej:
            items.append(dict(base, bwart="350", qty=qty_out(rej), sgtxt="Lot %s rejected" % L["prueflos"]))
        res = post_goods_movement(conn, {"budat": day, "bktxt": "Usage decision lot %s" % L["prueflos"],
                                         "xblnr": L["prueflos"]}, items, user, tcode="QA11")
        if defect:
            conn.execute("INSERT INTO qm_defect (prueflos,code,qty,text) VALUES (?,?,?,?)",
                         (L["prueflos"], defect, rej, (data.get("note") or "")[:120]))
        note = (data.get("note") or "")[:200]
        if data.get("override"):
            note = ("Deviation release: %s. " % str(data["override"])[:120]) + note
        conn.execute("UPDATE qm_lot SET status='UD', ud_code=?, qty_ok=?, qty_rej=?, ud_date=?, ud_by=?, ud_mblnr=?, "
                     "note=?, ts=? WHERE prueflos=?", (code, ok, rej, day, user, res["mblnr"], note, now_ts(),
                                                       L["prueflos"]))
        qmnum = None
        if rej:
            qmnum = _notif(conn, {"qmart": "Q2" if L["lifnr"] else "Q3", "matnr": L["matnr"], "werks": L["werks"],
                                  "lifnr": L["lifnr"], "prueflos": L["prueflos"], "qty": rej, "defect": defect,
                                  "text": "Lot %s: %s rejected - %s" % (L["prueflos"], qty_out(rej),
                                                                         DEFECTS[defect])}, user, day)
    txt = {"A": "accepted", "R": "rejected", "P": "partly accepted"}[code]
    return {"mblnr": res["mblnr"], "qmnum": qmnum,
            "message": "Lot %s %s: %s to unrestricted, %s to blocked stock%s" % (
                L["prueflos"], txt, qty_out(ok), qty_out(rej),
                " - complaint %s opened" % qmnum if qmnum else "")}


# ------------------------------------------------------------------ quality notifications
def _notif(conn, d, user, day):
    no = str(_next_number(conn, "QMEL"))
    due = (datetime.date.fromisoformat(day) + datetime.timedelta(days=14)).isoformat()
    conn.execute("INSERT INTO qm_notif (qmnum,qmart,matnr,werks,lifnr,kunnr,prueflos,qty,defect,text,due,created,"
                 "usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (no, d["qmart"], d.get("matnr"), d.get("werks") or "1000", d.get("lifnr"), d.get("kunnr"),
                  d.get("prueflos"), d.get("qty") or 0, d.get("defect"), (d.get("text") or "")[:200], due, day,
                  user, now_ts()))
    return no


def create_notification(conn, data, user):
    qmart = (data.get("qmart") or "").upper()
    if qmart not in NOTIF_TYPES:
        raise MMError("Notification type must be Q1, Q2 or Q3", "QM", "920")
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Describe the problem", "QM", "921")
    defect = (data.get("defect") or "OTH").upper()
    if defect not in DEFECTS:
        raise MMError("Defect code %s does not exist" % defect, "QM", "922")
    lifnr = (data.get("lifnr") or "").strip() or None
    kunnr = (data.get("kunnr") or "").strip().upper() or None
    if qmart == "Q2" and not (lifnr and conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()):
        raise MMError("A vendor complaint needs a valid vendor", "QM", "923")
    if qmart == "Q1" and not (kunnr and conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone()):
        raise MMError("A customer complaint needs a valid customer", "QM", "924")
    qty = parse_qty(data["qty"], allow_zero=True) if str(data.get("qty") or "").strip() else 0
    day = parse_date(data.get("datum"))
    with transaction(conn):
        no = _notif(conn, dict(data, qmart=qmart, lifnr=lifnr, kunnr=kunnr, qty=qty, defect=defect,
                               matnr=(data.get("matnr") or "").upper() or None), user, day)
    return {"qmnum": no, "message": "Quality notification %s (%s) created" % (no, NOTIF_TYPES[qmart])}


def update_notification(conn, qmnum, data, user):
    r = conn.execute("SELECT * FROM qm_notif WHERE qmnum=?", (str(qmnum),)).fetchone()
    if not r:
        raise MMError("Notification %s does not exist" % qmnum, "QM", "925")
    if r["status"] == "CLOSED":
        raise MMError("Notification %s is closed" % qmnum, "QM", "926")
    cause = (data.get("cause") if data.get("cause") is not None else r["cause"]) or ""
    action = (data.get("action") if data.get("action") is not None else r["action"]) or ""
    close = bool(data.get("close"))
    if close and (not cause.strip() or not action.strip()):
        raise MMError("Enter the root cause and the corrective action before closing (8D / CAPA)", "QM", "927")
    status = "CLOSED" if close else ("IN PROCESS" if cause or action else "OPEN")
    with transaction(conn):
        conn.execute("UPDATE qm_notif SET cause=?, action=?, status=?, closed=?, usnam=?, ts=? WHERE qmnum=?",
                     (cause[:300], action[:300], status, clock.today().isoformat() if close else None, user,
                      now_ts(), r["qmnum"]))
    return {"message": "Notification %s %s" % (qmnum, "closed" if close else "updated")}


def notifications(conn, status=None):
    today = clock.today().isoformat()
    q = ("SELECT n.*, v.name vendor, c.name customer FROM qm_notif n LEFT JOIN vendor v ON v.lifnr=n.lifnr "
         "LEFT JOIN customer c ON c.kunnr=n.kunnr")
    a = []
    if status == "open":
        q += " WHERE n.status<>'CLOSED'"
    q += " ORDER BY n.created DESC, n.qmnum DESC"
    out = []
    for r in conn.execute(q, a):
        d = dict(r)
        d["qty"] = qty_out(r["qty"])
        d["type_text"], d["defect_text"] = NOTIF_TYPES.get(r["qmart"]), DEFECTS.get(r["defect"], r["defect"])
        d["overdue"] = r["status"] != "CLOSED" and (r["due"] or "9") < today
        out.append(d)
    return out


# ------------------------------------------------------------------ analysis
def vendor_quality(conn, d1, d2):
    """per vendor: lots, accepted lots, quantity received / rejected, ppm, quality score"""
    out = []
    for r in conn.execute("SELECT l.lifnr, v.name, COUNT(*) lots, SUM(l.ud_code='A') ok_lots, SUM(l.qty) qty, "
                          "SUM(l.qty_rej) rej FROM qm_lot l LEFT JOIN vendor v ON v.lifnr=l.lifnr WHERE l.status='UD' "
                          "AND l.lifnr IS NOT NULL AND l.ud_date BETWEEN ? AND ? GROUP BY l.lifnr ORDER BY rej DESC",
                          (parse_date(d1), parse_date(d2))):
        ppm = round(r["rej"] * 1000000 / r["qty"]) if r["qty"] else 0
        acc = round(100.0 * r["ok_lots"] / r["lots"], 1) if r["lots"] else 0
        cmp = conn.execute("SELECT COUNT(*) FROM qm_notif WHERE lifnr=? AND qmart='Q2' AND created BETWEEN ? AND ?",
                           (r["lifnr"], d1, d2)).fetchone()[0]
        qty_q = 100.0 * (1 - r["rej"] / r["qty"]) if r["qty"] else 100.0
        score = max(0, round(0.5 * acc + 0.5 * qty_q - 5 * cmp))     # lots + quantity, minus complaints
        out.append(dict(lifnr=r["lifnr"], name=r["name"], lots=r["lots"], ok_lots=r["ok_lots"], qty=qty_out(r["qty"]),
                        rej=qty_out(r["rej"]), ppm=ppm, accept_pct=acc, complaints=cmp, score=score,
                        grade="A" if score >= 90 else "B" if score >= 75 else "C"))
    return out


def cockpit(conn, d1, d2):
    d1, d2 = parse_date(d1), parse_date(d2)
    today = clock.today()
    open_lots = lots(conn, "open")
    ud = conn.execute("SELECT COUNT(*) n, SUM(ud_code='A') a, SUM(qty) q, SUM(qty_rej) r FROM qm_lot WHERE "
                      "status='UD' AND ud_date BETWEEN ? AND ?", (d1, d2)).fetchone()
    pareto = [dict(code=r["code"], text=DEFECTS.get(r["code"], r["code"]), count=r["n"], qty=qty_out(r["q"]))
              for r in conn.execute("SELECT d.code, COUNT(*) n, SUM(d.qty) q FROM qm_defect d JOIN qm_lot l ON "
                                    "l.prueflos=d.prueflos WHERE l.ud_date BETWEEN ? AND ? GROUP BY d.code ORDER BY "
                                    "n DESC, q DESC", (d1, d2))]
    notifs = notifications(conn, "open")
    return {"d1": d1, "d2": d2, "open_lots": len(open_lots),
            "overdue_lots": sum(1 for x in open_lots if x["age"] > 3),
            "stock_in_qi": sum(float(x["qty"]) for x in open_lots),
            "decided": ud["n"] or 0, "accept_pct": round(100.0 * (ud["a"] or 0) / ud["n"], 1) if ud["n"] else None,
            "ppm": round((ud["r"] or 0) * 1000000 / ud["q"]) if ud["q"] else 0,
            "open_notifs": len(notifs), "overdue_notifs": sum(1 for n in notifs if n["overdue"]),
            "pareto": pareto, "vendors": vendor_quality(conn, d1, d2), "lots": open_lots[:50],
            "today": today.isoformat()}
