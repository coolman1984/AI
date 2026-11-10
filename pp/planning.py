"""Sales & operations planning, demand management and MRP.

MC84        product group with proportional factors
MC81/MC82   rough-cut plan: sales -> production with a target days' supply
MC75        transfer to demand management (disaggregation by factors)
MD61/62/63  planned independent requirements (PIR); strategy 40 PIRs are
            consumed by sales (billing), strategy 10 PIRs by the goods issue
MD01/02/03  MRP: low-level codes, net requirements, lot sizes, safety stock,
            lead-time offsetting, BOM explosion (dependent requirements),
            planned orders (in-house / subcontracting) and purchase
            requisitions (external), exception messages
MD04/MD05   stock/requirements list, MD06/MD07 collective lists
MD11-MD16   planned orders; CO40/CO41 convert to production orders
MD09        pegging (where does a requirement come from)
"""
import calendar
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, rdiv

from .config import EXCEPTIONS, PIR_VERSION, SOP_VERSION, SUBCON_SLOC
from .master import add_workdays, explode, low_level_codes, select_version
from mm import util as mmclock  # noqa: E402


def _month_start(m):
    return m + "-01"


def _months(start, n):
    y, mo = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(n):
        out.append("%04d-%02d" % (y, mo))
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


def _month_end(m):
    y, mo = int(m[:4]), int(m[5:7])
    return "%s-%02d" % (m, calendar.monthrange(y, mo)[1])


# ====================================================================== SOP
def save_group(conn, prgrp, ktext, members, user=""):
    """MC84: members [{matnr, factor %}] - factors must add up to 100 %."""
    prgrp = prgrp.upper()
    if sum(int(m.get("factor") or 0) for m in members) != 100:
        raise MMError("Proportional factors must add up to 100 %", "MA", "010")
    with transaction(conn):
        conn.execute("DELETE FROM pp_sop_group WHERE prgrp=?", (prgrp,))
        for m in members:
            mat = (m.get("matnr") or "").upper()
            if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks='1000'",
                                (mat,)).fetchone():
                raise MMError("Member %s is not maintained in plant 1000" % mat, "MA", "011")
            conn.execute("INSERT INTO pp_sop_group VALUES (?,?,?,?,?)",
                         (prgrp, ktext, mat, "1000", int(m["factor"])))


def group(conn, prgrp):
    return rows(conn.execute("SELECT g.*, m.maktx, m.meins FROM pp_sop_group g JOIN material m "
                             "USING (matnr) WHERE prgrp=? ORDER BY factor DESC", (prgrp.upper(),)))


def sop_plan(conn, prgrp, months, target_days=10, user="", vers=SOP_VERSION):
    """MC81: months [{month 'YYYY-MM', sales}] -> production = sales + change
    of stock to reach target_days of the next month's sales."""
    mem = group(conn, prgrp)
    if not mem:
        raise MMError("Product group %s does not exist (MC84)" % prgrp, "MA", "012")
    from .order import stock_unrestricted
    stock = sum(stock_unrestricted(conn, m["matnr"], "1000") for m in mem)
    sales = [(m["month"], parse_qty(str(m["sales"]))) for m in months]
    out = []
    with transaction(conn):
        conn.execute("DELETE FROM pp_sop_plan WHERE prgrp=? AND vers=?", (prgrp.upper(), vers))
        for i, (mo, s) in enumerate(sales):
            nxt = sales[i + 1][1] if i + 1 < len(sales) else s
            days = calendar.monthrange(int(mo[:4]), int(mo[5:7]))[1]
            target = rdiv(nxt * int(target_days), days)
            prod = max(0, s + target - stock)
            prod = (prod + 999) // 1000 * 1000                 # whole units
            close = stock + prod - s
            conn.execute("INSERT INTO pp_sop_plan VALUES (?,?,?,?,?,?,?)",
                         (prgrp.upper(), vers, mo, s, prod, close, int(target_days)))
            out.append(dict(month=mo, sales=s, production=prod, opening=stock, stock=close,
                            days=round(close / (nxt / days), 1) if nxt else 0))
            stock = close
    return out


def sop_get(conn, prgrp, vers=SOP_VERSION):
    return rows(conn.execute("SELECT * FROM pp_sop_plan WHERE prgrp=? AND vers=? ORDER BY month",
                             (prgrp.upper(), vers)))


def transfer_to_demand(conn, prgrp, user="", vers=SOP_VERSION):
    """MC75: production plan of the group -> PIRs per member (factor %)."""
    plan = sop_get(conn, prgrp, vers)
    if not plan:
        raise MMError("No rough-cut plan for %s (MC81)" % prgrp, "MA", "013")
    out = []
    for p in plan:
        for m in group(conn, prgrp):
            q = rdiv(p["production"] * m["factor"], 100)
            q = (q + 500) // 1000 * 1000
            save_pir(conn, m["matnr"], "1000", p["month"], q, user)
            out.append(dict(matnr=m["matnr"], month=p["month"], qty=q))
    return out


# ====================================================================== PIR
def save_pir(conn, matnr, werks, month, qty, user="", versb=PIR_VERSION):
    matnr = matnr.upper()
    q = qty if isinstance(qty, int) else parse_qty(qty, allow_zero=True)
    with transaction(conn):
        mp = conn.execute("SELECT strgr, dismm FROM material_plant WHERE matnr=? AND werks=?",
                          (matnr, werks)).fetchone()
        if not mp:
            raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "6P", "001")
        if not mp["strgr"]:
            raise MMError("Material %s has no planning strategy (MRP 3 view)" % matnr, "6P", "002")
        bedae = "VSF" if mp["strgr"] == "40" else "LSF"
        if q:
            conn.execute("INSERT OR REPLACE INTO pp_pir VALUES (?,?,?,?,?,?,?)",
                         (matnr, werks, versb, month, q, bedae, user))
        else:
            conn.execute("DELETE FROM pp_pir WHERE matnr=? AND werks=? AND versb=? AND month=?",
                         (matnr, werks, versb, month))


def pirs(conn, matnr=None, werks="1000"):
    sql = "SELECT p.*, m.maktx, m.meins FROM pp_pir p JOIN material m USING (matnr) WHERE werks=?"
    args = [werks]
    if matnr:
        sql += " AND p.matnr=?"
        args.append(matnr.upper())
    out = rows(conn.execute(sql + " ORDER BY p.matnr, p.month", args))
    for p in out:
        p["consumed"] = consumption(conn, p["matnr"], p["werks"], p["month"], p["bedae"])
        p["open"] = max(0, p["plnmg"] - p["consumed"])
    return out


def consumption(conn, matnr, werks, month, bedae):
    """Strategy 40 (VSF): sales quantity of the month; strategy 10 (LSF):
    goods issues for delivery (601) of the month."""
    if bedae == "VSF":
        return conn.execute("SELECT COALESCE(SUM(i.fkimg),0) FROM billing_item i JOIN billing b "
                            "USING (vbeln) WHERE i.matnr=? AND i.werks=? AND b.cancelled=0 AND COALESCE(b.fkart,'F2')='F2' AND "
                            "substr(b.fkdat,1,7)=?", (matnr, werks, month)).fetchone()[0]
    return conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='H' THEN i.menge ELSE -i.menge END),0) "
                        "FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr "
                        "WHERE i.matnr=? AND i.werks=? AND i.bwart IN ('601','602') AND "
                        "substr(h.budat,1,7)=?", (matnr, werks, month)).fetchone()[0]


# ====================================================================== MRP
def _elements(conn, matnr, werks, today):
    """Requirements (negative) and receipts (positive) of a material."""
    el = []
    for p in pirs(conn, matnr, werks):
        if p["month"] >= today[:7] and p["open"]:
            d = max(add_workdays(_month_start(p["month"]), 0), today)
            el.append(dict(dat=d, typ="PIR", txt="Indep. requirement %s (%s)" % (p["month"], p["bedae"]),
                           qty=-p["open"], ref=p["month"]))
    for r in conn.execute("SELECT d.*, p.matnr AS head FROM pp_depreq d JOIN pp_plaf p USING (plnum) "
                          "WHERE d.matnr=? AND d.werks=?", (matnr, werks)):
        el.append(dict(dat=r["bdter"], typ="DEPREQ", txt="Dep. req. planned order %s (%s)"
                       % (r["plnum"], r["head"]), qty=-r["bdmng"], ref=r["plnum"]))
    for r in conn.execute("SELECT r.*, o.matnr AS head, o.stat FROM pp_resb r LEFT JOIN orders o "
                          "ON o.aufnr=r.aufnr WHERE r.matnr=? AND r.werks=? AND r.kzear=0 AND "
                          "r.xloek=0 AND r.bdmng>r.enmng AND (o.aufnr IS NULL OR o.stat IN "
                          "('CRTD','REL'))", (matnr, werks)):
        if r["aufnr"] and r["head"] == matnr:
            continue                                # rework: own material
        el.append(dict(dat=r["bdter"] or today, typ="AR" if r["aufnr"] else "MR",
                       txt=("Order reservation %s (%s)" % (r["aufnr"], r["head"])) if r["aufnr"]
                       else "Reservation %s" % r["rsnum"], qty=-(r["bdmng"] - r["enmng"]),
                       ref=r["aufnr"] or r["rsnum"]))
    for r in conn.execute("SELECT * FROM pp_forecast WHERE matnr=? AND werks=? AND kind='F' AND "
                          "month>=?", (matnr, werks, today[:7])):
        el.append(dict(dat=max(_month_start(r["month"]), today), typ="FC",
                       txt="Forecast requirement %s" % r["month"], qty=-r["value"], ref=r["month"]))
    # receipts
    for r in conn.execute("SELECT * FROM pp_plaf WHERE matnr=? AND werks=? AND conv=''",
                          (matnr, werks)):
        el.append(dict(dat=r["pedtr"], typ="PLORD", txt="Planned order %s%s" % (
            r["plnum"], " (firmed)" if r["auffx"] else ""), qty=r["gsmng"], ref=r["plnum"],
            firm=r["auffx"], start=r["psttr"]))
    for r in conn.execute("SELECT aufnr, gltrp, gamng-wemng-COALESCE(iasmg,0) AS q, stat FROM orders "
                          "WHERE matnr=? AND werks=? AND stat IN ('CRTD','REL') AND auart='PP01'",
                          (matnr, werks)):
        if r["q"] > 0:
            el.append(dict(dat=r["gltrp"] or today, typ="PRDORD", txt="Production order %s (%s)"
                           % (r["aufnr"], r["stat"]), qty=r["q"], ref=r["aufnr"], firm=1))
    for r in conn.execute("SELECT i.ebeln, i.ebelp, i.eindt, i.menge-i.wemng AS q, i.pstyp FROM "
                          "po_item i WHERE i.matnr=? AND i.werks=? AND i.elikz=0 AND i.wemng<i.menge "
                          "AND COALESCE(i.loekz,0)=0", (matnr, werks)):
        el.append(dict(dat=r["eindt"] or today, typ="POITEM", txt="Purchase order %s/%s%s" % (
            r["ebeln"], r["ebelp"], " (subcontracting)" if r["pstyp"] == "L" else ""),
            qty=r["q"], ref=r["ebeln"], firm=1))
    for r in conn.execute("SELECT banfn, bnfpo, lfdat, menge, estkz FROM pr_item WHERE matnr=? AND "
                          "werks=? AND ebeln IS NULL AND statu IN ('N','B')", (matnr, werks)):
        el.append(dict(dat=r["lfdat"], typ="PURRQS", txt="Purchase requisition %s/%s" % (
            r["banfn"], r["bnfpo"]), qty=r["menge"], ref=r["banfn"], firm=r["estkz"] != "B"))
    return el


def stock_requirements(conn, matnr, werks="1000", today=None):
    """MD04: elements with running available quantity + last MRP messages."""
    today = today or mmclock.today().isoformat()
    m = conn.execute("SELECT m.matnr, m.maktx, m.meins, m.mtart, p.* FROM material m JOIN "
                     "material_plant p ON p.matnr=m.matnr WHERE m.matnr=? AND p.werks=?",
                     (matnr.upper(), werks)).fetchone()
    if not m:
        raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "61", "001")
    from .order import stock_unrestricted
    stock = stock_unrestricted(conn, m["matnr"], werks)
    qi = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? AND "
                      "insmk='Q'", (m["matnr"], werks)).fetchone()[0]
    el = sorted(_elements(conn, m["matnr"], werks, today), key=lambda e: (e["dat"], -e["qty"]))
    avail = stock + qi
    lines = [dict(dat=today, typ="STOCK", txt="Plant stock (unrestricted + QI %s)" % (qi / 1000.0),
                  qty=stock + qi, avail=avail)]
    if m["eisbe"]:
        avail -= m["eisbe"]
        lines.append(dict(dat=today, typ="SAFE", txt="Safety stock", qty=-m["eisbe"], avail=avail))
    for e in el:
        avail += e["qty"]
        e["avail"] = avail
        lines.append(e)
    msgs = rows(conn.execute("SELECT * FROM pp_mrp_msg WHERE matnr=? AND werks=? AND run=(SELECT "
                             "MAX(id) FROM pp_mrp_run) ORDER BY dat", (m["matnr"], werks)))
    head = dict(m)
    head["stock"] = stock
    head["final_avail"] = avail
    return {"material": head, "lines": lines, "messages": msgs}


def _lot(m, short, reqs_in_bucket):
    if m["disls"] == "FX" and m["bstfe"]:
        return -(-short // m["bstfe"]) * m["bstfe"]
    if m["disls"] == "HB" and m["mabst"]:
        return max(short, m["mabst"])
    if m["disls"] in ("WB", "MB"):
        return max(short, reqs_in_bucket)
    return short


def mrp_run(conn, user, matnr=None, werks="1000", today=None, single_level=False,
            include_vb=True):
    """MD01 (total, matnr None) / MD02 (multi-level single item) / MD03 (single level).
    Regenerative: unfirmed planned orders and MRP requisitions are deleted and
    planned again from the requirements."""
    today = today or mmclock.today().isoformat()
    with transaction(conn):
        cur = conn.execute("INSERT INTO pp_mrp_run (ts,usnam,scope) VALUES (?,?,?)",
                           (now_ts(), user, matnr or "PLANT %s" % werks))
        run = cur.lastrowid
        vb = []
        if include_vb and not matnr:          # reorder point materials (VB) first
            from pur import mrp as reorder
            vb = reorder.run(conn, werks, today, user)
        llc = low_level_codes(conn, werks)
        sql = ("SELECT m.matnr, m.meins, m.mtart, p.* FROM material m JOIN material_plant p ON "
               "p.matnr=m.matnr WHERE p.werks=? AND p.dismm IN ('PD','VV') AND p.lvorm=0")
        mats = conn.execute(sql, (werks,)).fetchall()
        if matnr:
            scope = {matnr.upper()}
            if not single_level:
                scope |= {x["idnrk"] for x in explode(conn, matnr.upper(), werks, 1000)}
            mats = [m for m in mats if m["matnr"] in scope]
            if not mats:
                raise MMError("Material %s is not planned by MRP (MRP type PD / VV)" % matnr,
                              "61", "002")
        mats = sorted(mats, key=lambda m: (llc.get(m["matnr"], 0), m["matnr"]))
        n_plaf = n_pr = n_msg = 0
        for m in mats:
            k = m["matnr"]
            # delete old unfirmed planning results
            for p in conn.execute("SELECT plnum FROM pp_plaf WHERE matnr=? AND werks=? AND auffx=0 "
                                  "AND conv=''", (k, werks)).fetchall():
                conn.execute("DELETE FROM pp_depreq WHERE plnum=?", (p["plnum"],))
                conn.execute("DELETE FROM pp_plaf WHERE plnum=?", (p["plnum"],))
            conn.execute("DELETE FROM pr_item WHERE matnr=? AND werks=? AND estkz='B' AND ebeln IS "
                         "NULL AND statu IN ('N','B')", (k, werks))
            conn.execute("DELETE FROM pp_mrp_msg WHERE matnr=? AND werks=?", (k, werks))
            from .order import stock_unrestricted
            stock = stock_unrestricted(conn, k, werks) + conn.execute(
                "SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? AND insmk='Q'",
                (k, werks)).fetchone()[0]
            el = sorted(_elements(conn, k, werks, today), key=lambda e: (e["dat"], -e["qty"]))
            avail = stock - (m["eisbe"] or 0)
            msgs = []
            if stock < (m["eisbe"] or 0):
                msgs.append((today, "96", "Stock %.3f below safety stock %.3f" % (
                    stock / 1000.0, (m["eisbe"] or 0) / 1000.0)))
            reqs = [e for e in el if e["qty"] < 0]
            fixed = [e for e in el if e["qty"] > 0]
            # reschedule messages for fixed receipts
            for f in fixed:
                need = next((r for r in reqs if r["dat"] < f["dat"]), None)
                if f["dat"] < today and f["typ"] != "PLORD":
                    msgs.append((f["dat"], "07", "%s: finish date in the past" % f["txt"]))
            lead = (m["dzeit"] or 1) if m["beskz"] == "E" or m["sobsl"] == "30" else (m["plifz"] or 7)
            for e in el:
                avail += e["qty"]
                if e["qty"] > 0:
                    continue
                if avail >= 0:
                    continue
                short = -avail
                bucket = e["dat"][:7] if m["disls"] == "MB" else None
                inb = sum(-r["qty"] for r in reqs if bucket and r["dat"][:7] == bucket
                          and r["dat"] >= e["dat"]) if bucket else 0
                lot = _lot(m, short, inb)
                finish = add_workdays(e["dat"], 0)
                start = add_workdays(finish, -lead)
                if start < today:
                    msgs.append((start, "06", "Start date %s in the past for %.3f %s" % (
                        start, lot / 1000.0, m["meins"])))
                if m["beskz"] == "E" or m["sobsl"] == "30":
                    plnum = str(next_number(conn, "PLAF")) if conn.execute(
                        "SELECT 1 FROM number_range WHERE object='PLAF'").fetchone() else None
                    if not plnum:
                        conn.execute("INSERT INTO number_range VALUES ('PLAF', 9999)")
                        plnum = str(next_number(conn, "PLAF"))
                    conn.execute("INSERT INTO pp_plaf (plnum,matnr,werks,gsmng,psttr,pedtr,paart,"
                                 "beskz,sobsl,dispo,run,pir_month,ersda) VALUES "
                                 "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (plnum, k, werks, lot, start, finish,
                                  "NB" if m["sobsl"] == "30" else "LA", m["beskz"], m["sobsl"] or "",
                                  m["dispo"], run, e["dat"][:7], today))
                    n_plaf += 1
                    _explode_depreq(conn, plnum, k, werks, lot, start)
                    if m["beskz"] == "E" and not m["sobsl"]:
                        if not conn.execute("SELECT 1 FROM routing WHERE matnr=? AND werks=?",
                                            (k, werks)).fetchone():
                            msgs.append((start, "52", "No routing - planned order %s cannot be "
                                         "converted" % plnum))
                        if conn.execute("SELECT 1 FROM pp_prodver WHERE matnr=? AND werks=?",
                                        (k, werks)).fetchone() and not select_version(
                                            conn, k, werks, lot, start):
                            msgs.append((start, "52", "No valid production version for %s" % plnum))
                else:
                    from pur.pr import create_pr
                    pr = create_pr(conn, [dict(matnr=k, menge="%.3f" % (lot / 1000.0), werks=werks,
                                               lfdat=finish, ekgrp=m["ekgrp"] or "001",
                                               lgort=m["lgfsb"] or "")],
                                   "MRP", estkz="B", badat=today)
                    n_pr += 1
                    _ = pr
                avail += lot
            if m["mabst"] and avail + (m["eisbe"] or 0) > m["mabst"] * 2 and not any(
                    e["qty"] < 0 for e in el):
                msgs.append((today, "26", "Excess stock: %.3f available without requirements"
                             % ((avail + (m["eisbe"] or 0)) / 1000.0)))
            for d, code, txt in msgs:
                conn.execute("INSERT INTO pp_mrp_msg VALUES (?,?,?,?,?,?,?)",
                             (run, k, werks, d, code, "", "%s - %s" % (EXCEPTIONS.get(code, ""), txt)))
            n_msg += len(msgs)
        conn.execute("UPDATE pp_mrp_run SET planned=?, prs=?, exceptions=?, materials=? WHERE id=?",
                     (n_plaf, n_pr, n_msg, len(mats), run))
    return {"run": run, "materials": len(mats), "planned_orders": n_plaf, "requisitions": n_pr,
            "exceptions": n_msg, "reorder_point": vb}


def _explode_depreq(conn, plnum, matnr, werks, qty, start):
    for b in conn.execute("SELECT * FROM bom WHERE matnr=? AND werks=?", (matnr, werks)).fetchall():
        q = rdiv(b["menge"] * qty, b["basis"])
        q += rdiv(q * (b["ausch"] or 0), 10000)
        conn.execute("INSERT INTO pp_depreq VALUES (?,?,?,?,?)", (plnum, b["idnrk"], werks, q, start))


# ====================================================================== planned orders
def planned_orders(conn, matnr=None, open_only=True):
    sql = ("SELECT p.*, m.maktx, m.meins FROM pp_plaf p JOIN material m USING (matnr) WHERE 1=1")
    args = []
    if matnr:
        sql += " AND p.matnr=?"
        args.append(matnr.upper())
    if open_only:
        sql += " AND p.conv=''"
    return rows(conn.execute(sql + " ORDER BY p.psttr, p.plnum", args))


def save_planned_order(conn, data, user):
    """MD11 (create, firmed) / MD12 (change qty / dates / firming)."""
    with transaction(conn):
        if data.get("plnum"):
            p = conn.execute("SELECT * FROM pp_plaf WHERE plnum=?", (data["plnum"],)).fetchone()
            if not p or p["conv"]:
                raise MMError("Planned order %s does not exist or is converted" % data["plnum"],
                              "61", "010")
            q = parse_qty(data.get("gsmng") or "%.3f" % (p["gsmng"] / 1000.0))
            s = parse_date(data.get("psttr") or p["psttr"])
            f = parse_date(data.get("pedtr") or p["pedtr"])
            conn.execute("UPDATE pp_plaf SET gsmng=?, psttr=?, pedtr=?, auffx=? WHERE plnum=?",
                         (q, s, f, 1 if data.get("auffx", True) else 0, p["plnum"]))
            conn.execute("DELETE FROM pp_depreq WHERE plnum=?", (p["plnum"],))
            _explode_depreq(conn, p["plnum"], p["matnr"], p["werks"], q, s)
            return p["plnum"]
        matnr = (data.get("matnr") or "").upper()
        werks = data.get("werks") or "1000"
        m = conn.execute("SELECT * FROM material_plant WHERE matnr=? AND werks=?",
                         (matnr, werks)).fetchone()
        if not m:
            raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "61", "001")
        q = parse_qty(data.get("gsmng"))
        f = parse_date(data.get("pedtr"))
        s = parse_date(data["psttr"]) if data.get("psttr") else add_workdays(f, -(m["dzeit"] or 1))
        if conn.execute("SELECT 1 FROM number_range WHERE object='PLAF'").fetchone() is None:
            conn.execute("INSERT INTO number_range VALUES ('PLAF', 9999)")
        plnum = str(next_number(conn, "PLAF"))
        conn.execute("INSERT INTO pp_plaf (plnum,matnr,werks,gsmng,psttr,pedtr,paart,beskz,sobsl,"
                     "auffx,dispo,run,pir_month,ersda) VALUES (?,?,?,?,?,?,?,?,?,1,?,0,'',?)",
                     (plnum, matnr, werks, q, s, f, "NB" if m["sobsl"] == "30" else "LA",
                      m["beskz"], m["sobsl"] or "", m["dispo"], now_ts()[:10]))
        _explode_depreq(conn, plnum, matnr, werks, q, s)
        return plnum


def delete_planned_order(conn, plnum):
    with transaction(conn):
        conn.execute("DELETE FROM pp_depreq WHERE plnum=?", (plnum,))
        if not conn.execute("DELETE FROM pp_plaf WHERE plnum=? AND conv=''", (plnum,)).rowcount:
            raise MMError("Planned order %s does not exist or is already converted" % plnum,
                          "61", "010")


def convert(conn, plnum, user, release=False, lifnr=None, today=None):
    """CO40 (in-house -> production order) / MD14-like for subcontracting
    (-> subcontracting purchase order)."""
    p = conn.execute("SELECT * FROM pp_plaf WHERE plnum=?", (plnum,)).fetchone()
    if not p or p["conv"]:
        raise MMError("Planned order %s does not exist or is already converted" % plnum, "61", "010")
    if p["sobsl"] == "30":
        from .subcon import create_po
        from pur.sourcing import determine_source
        if not lifnr:
            src = determine_source(conn, p["matnr"], p["werks"], p["gsmng"], p["psttr"])
            lifnr = src["lifnr"] if src else None
        if not lifnr:
            raise MMError("No subcontractor found for %s (info record / source list)" % p["matnr"],
                          "06", "453")
        e = create_po(conn, lifnr, p["matnr"], "%.3f" % (p["gsmng"] / 1000.0), p["pedtr"], user,
                      werks=p["werks"], bedat=p["psttr"] if p["psttr"] > now_ts()[:10] else None,
                      plnum=plnum)
        return {"type": "PO", "number": e}
    from .order import create
    a = create(conn, {"auart": "PP01", "matnr": p["matnr"], "werks": p["werks"],
                      "gamng": "%.3f" % (p["gsmng"] / 1000.0),
                      # start in the past -> scheduling from today (OPU3)
                      "gstrp": max(p["psttr"], add_workdays(today or now_ts()[:10], 0)),
                      "plnum": plnum, "lgort": _gr_sloc(conn, p["matnr"], p["werks"]),
                      "release": release}, user)
    return {"type": "ORDER", "number": a}


def _gr_sloc(conn, matnr, werks):
    m = conn.execute("SELECT m.mtart, p.lgfsb FROM material m JOIN material_plant p ON "
                     "p.matnr=m.matnr WHERE m.matnr=? AND p.werks=?", (matnr, werks)).fetchone()
    return (m["lgfsb"] if m and m["lgfsb"] else ("0003" if m and m["mtart"] == "FERT" else "0002"))


# ====================================================================== lists
def mrp_list(conn, werks="1000", dispo=None):
    """MD06/MD07: one line per planned material with stock, coverage and exceptions."""
    out = []
    last = conn.execute("SELECT MAX(id) FROM pp_mrp_run").fetchone()[0]
    sql = ("SELECT m.matnr, m.maktx, m.meins, m.mtart, p.* FROM material m JOIN material_plant p "
           "ON p.matnr=m.matnr WHERE p.werks=? AND p.dismm<>'ND'")
    args = [werks]
    if dispo:
        sql += " AND p.dispo=?"
        args.append(dispo)
    from .order import stock_unrestricted
    for m in conn.execute(sql + " ORDER BY m.matnr", args):
        d = stock_requirements(conn, m["matnr"], werks)
        reqs = -sum(l["qty"] for l in d["lines"] if l["typ"] in ("PIR", "DEPREQ", "AR", "MR", "FC"))
        stock = stock_unrestricted(conn, m["matnr"], werks)
        msgs = [x for x in d["messages"]] if last else []
        daily = reqs / 60.0 if reqs else 0
        out.append(dict(matnr=m["matnr"], maktx=m["maktx"], meins=m["meins"], dismm=m["dismm"],
                        dispo=m["dispo"], stock=stock, eisbe=m["eisbe"], requirements=reqs,
                        receipts=sum(l["qty"] for l in d["lines"] if l["typ"] in
                                     ("PLORD", "PRDORD", "POITEM", "PURRQS")),
                        final=d["material"]["final_avail"],
                        coverage=round(stock / daily, 1) if daily else None,
                        exceptions=", ".join(sorted({x["ausk"] for x in msgs})),
                        light="R" if stock < (m["eisbe"] or 0) or d["material"]["final_avail"] < 0
                        else "Y" if msgs else "G"))
    return out


def pegging(conn, matnr, werks="1000"):
    """MD09: dependent requirements traced back to the planned order / PIR."""
    out = []
    for r in conn.execute("SELECT d.*, p.matnr AS head, p.pir_month FROM pp_depreq d JOIN pp_plaf p "
                          "USING (plnum) WHERE d.matnr=? AND d.werks=?", (matnr.upper(), werks)):
        out.append(dict(qty=r["bdmng"], dat=r["bdter"], source="Planned order %s" % r["plnum"],
                        head=r["head"], origin="PIR %s %s" % (r["head"], r["pir_month"])
                        if r["pir_month"] else "Planned order (manual)"))
    for r in conn.execute("SELECT r.*, o.matnr AS head, o.plnum FROM pp_resb r JOIN orders o ON "
                          "o.aufnr=r.aufnr WHERE r.matnr=? AND r.werks=? AND r.bdmng>r.enmng AND "
                          "r.kzear=0 AND o.stat IN ('CRTD','REL')", (matnr.upper(), werks)):
        out.append(dict(qty=r["bdmng"] - r["enmng"], dat=r["bdter"],
                        source="Production order %s" % r["aufnr"], head=r["head"],
                        origin="Planned order %s" % r["plnum"] if r["plnum"] else "Manual order"))
    return out
