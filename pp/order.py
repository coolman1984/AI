"""Production order (shop floor control).

CO01 / CO07  create order (BOM explosion -> reservations, routing -> operations,
             scheduling with work center capacity and the factory calendar)
CO02         change quantity / dates (operations and reservations follow)
CO05N        release: availability check (MACM / MSPT), external operations ->
             purchase requisitions (account assignment F to the order)
CO09/COMAC   availability: stock - committed reservations + receipts by date
CO11N        confirmation: activities -> order (CO), backflush components (261),
             automatic goods receipt (101) for control key PP03, scrap, final conf.
CO13         cancel confirmation (activities and goods movements reversed)
CO27         picking list (open reservations) -> goods issue 261
COHV / TECO  technical completion
CO03 / COOIS order display and order information system
"""
import datetime

from mm.db import rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, rdiv, qty_out

from .config import ORDER_TYPES, CONTROL_KEYS, EXT_COST_ELEMENT, SUBCON_SLOC, STATUS
from .master import add_workdays, op_duration_days, select_version

STAT_ORDER = ["CRTD", "REL", "PCNF", "CNF", "PDLV", "DLV", "TECO", "CLSD", "MSPT", "MACM",
              "GMPS", "EXTP", "PRC", "SETC"]


def _q(v):
    return "%.3f" % (v / 1000.0)


def _a(v):
    return "%.2f" % (v / 100.0)


def sysstat(conn, aufnr, add=(), remove=()):
    r = conn.execute("SELECT sysst FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
    s = set((r["sysst"] or "").split()) if r else set()
    s |= set(add)
    s -= set(remove)
    conn.execute("UPDATE orders SET sysst=? WHERE aufnr=?",
                 (" ".join(sorted(s, key=lambda x: STAT_ORDER.index(x) if x in STAT_ORDER else 99)),
                  aufnr))


def _order(conn, aufnr):
    o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (str(aufnr),)).fetchone()
    if not o or o["auart"] not in ORDER_TYPES:
        raise MMError("Production order %s does not exist" % aufnr, "CO", "001")
    return o


# ====================================================================== CO01
def create(conn, data, user):
    auart = (data.get("auart") or "PP01").upper()
    ot = ORDER_TYPES.get(auart)
    if not ot:
        raise MMError("Order type %s is not defined for production (OPL8)" % auart, "CO", "002")
    werks = data.get("werks") or "1000"
    matnr = (data.get("matnr") or "").upper() or None
    gamng = parse_qty(data.get("gamng") or "1")
    gstrp = parse_date(data["gstrp"]) if data.get("gstrp") else None
    gltrp = parse_date(data["gltrp"]) if data.get("gltrp") else None
    if not gstrp and not gltrp:
        gstrp = add_workdays(datetime.date.today().isoformat(), 0)
    with transaction(conn):
        verid = None
        if auart == "PP01":
            from md.checks import material as status_check
            status_check(conn, matnr, werks, "inv")
            mp = conn.execute("SELECT * FROM material_plant WHERE matnr=? AND werks=?",
                              (matnr, werks)).fetchone()
            if not mp:
                raise MMError("Material %s is not maintained in plant %s" % (matnr, werks),
                              "CO", "006")
            if mp["beskz"] == "F":
                raise MMError("Material %s is procured externally (procurement type F) - "
                              "no production order" % matnr, "CO", "007")
            has_ver = conn.execute("SELECT 1 FROM pp_prodver WHERE matnr=? AND werks=?",
                                   (matnr, werks)).fetchone()
            verid = data.get("verid") or select_version(conn, matnr, werks, gamng,
                                                        gstrp or gltrp)
            if has_ver and not verid:
                raise MMError("No valid production version for %s on %s / lot size %s (C223)"
                              % (matnr, gstrp or gltrp, _q(gamng)), "C2", "004")
        kostl = (data.get("kostl") or "").upper() or None
        aufnr = _create_co(conn, dict(auart=auart, matnr=matnr, werks=werks, gamng=_q(gamng),
                                      lgort=data.get("lgort") or "", kostl=kostl,
                                      ktext=data.get("ktext"), erdat=gstrp or gltrp,
                                      rules=data.get("rules")), user)
        ops = []
        if auart == "PP01":
            for r in conn.execute("SELECT * FROM routing WHERE matnr=? AND werks=? ORDER BY "
                                  "vornr", (matnr, werks)):
                ops.append(dict(vornr=r["vornr"], arbpl=r["arbpl"], steus=r["steus"] or "PP01",
                                ltxa1=r["ltxa1"], vgw=rdiv(r["vgw"] * gamng, r["basis"]),
                                setup=r["vgw_setup"] or 0, lifnr=r["lifnr"], preis=r["preis"] or 0,
                                plifz=r["plifz"] or 0))
        for o in data.get("ops") or []:
            steus = (o.get("steus") or "PP01").upper()
            arbpl = (o.get("arbpl") or "").upper()
            if not conn.execute("SELECT 1 FROM work_center WHERE arbpl=?", (arbpl,)).fetchone():
                raise MMError("Work center %s does not exist" % arbpl, "CR", "001")
            ops.append(dict(vornr=str(o.get("vornr") or "%04d" % ((len(ops) + 1) * 10)).zfill(4),
                            arbpl=arbpl, steus=steus, ltxa1=o.get("ltxa1") or "",
                            vgw=parse_qty(o.get("vgw") or "1"), setup=0, lifnr=None, preis=0,
                            plifz=0))
        if not ops and auart in ("ZP03", "ZREF"):
            raise MMError("Enter at least one operation (no standard routing for %s)"
                          % ORDER_TYPES[auart]["text"], "CO", "008")
        for o in ops:
            conn.execute("INSERT INTO pp_oper (aufnr,vornr,arbpl,steus,ltxa1,mgvrg,vgw,vgw_setup,"
                         "lifnr,preis) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (aufnr, o["vornr"], o["arbpl"], o["steus"], o["ltxa1"], gamng, o["vgw"],
                          o["setup"], o["lifnr"], o["preis"]))
        first_op = ops[0]["vornr"] if ops else ""
        pos = 0
        if auart == "PP01":
            for b in conn.execute("SELECT b.*, p.lgpro, p.rgekz AS mrgekz FROM bom b LEFT JOIN "
                                  "material_plant p ON p.matnr=b.idnrk AND p.werks=b.werks WHERE "
                                  "b.matnr=? AND b.werks=? ORDER BY posnr", (matnr, werks)):
                q = rdiv(b["menge"] * gamng, b["basis"])
                q += rdiv(q * (b["ausch"] or 0), 10000)
                pos += 1
                conn.execute("INSERT INTO pp_resb (rsnum,rspos,aufnr,matnr,werks,lgort,bdmng,"
                             "vornr,rgekz,usnam) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (aufnr, pos, aufnr, b["idnrk"], werks,
                              b["lgort"] or b["lgpro"] or "0001", q, b["vornr"] or first_op,
                              1 if (b["rgekz"] or b["mrgekz"]) else 0, user))
        elif auart in ("ZP03", "ZREF"):
            pos += 1
            conn.execute("INSERT INTO pp_resb (rsnum,rspos,aufnr,matnr,werks,lgort,bdmng,vornr,"
                         "usnam) VALUES (?,?,?,?,?,?,?,?,?)",
                         (aufnr, pos, aufnr, matnr, werks, data.get("comp_lgort") or
                          data.get("lgort") or "0001", gamng, first_op, user))
        for c in data.get("comps") or []:
            pos += 1
            cm = (c.get("matnr") or "").upper()
            if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                                (cm, werks)).fetchone():
                raise MMError("Component %s is not maintained in plant %s" % (cm, werks),
                              "CO", "009")
            conn.execute("INSERT INTO pp_resb (rsnum,rspos,aufnr,matnr,werks,lgort,bdmng,vornr,"
                         "usnam) VALUES (?,?,?,?,?,?,?,?,?)",
                         (aufnr, pos, aufnr, cm, werks, c.get("lgort") or "0001",
                          parse_qty(c.get("menge")), first_op, user))
        dispo = conn.execute("SELECT dispo FROM material_plant WHERE matnr=? AND werks=?",
                             (matnr, werks)).fetchone() if matnr else None
        conn.execute("UPDATE orders SET verid=?, plnum=?, rsnum=?, dispo=? WHERE aufnr=?",
                     (verid, data.get("plnum"), aufnr, dispo["dispo"] if dispo else "", aufnr))
        schedule(conn, aufnr, gstrp, gltrp)
        flags = ["CRTD", "SETC"]
        if conn.execute("SELECT estimate_id FROM orders WHERE aufnr=?", (aufnr,)).fetchone()[0]:
            flags.append("PRC")
        sysstat(conn, aufnr, flags)
        if data.get("plnum"):
            conn.execute("UPDATE pp_plaf SET conv=? WHERE plnum=?", (aufnr, data["plnum"]))
            conn.execute("DELETE FROM pp_depreq WHERE plnum=?", (data["plnum"],))
        if data.get("release"):
            release(conn, aufnr, user, gstrp or gltrp)
    return aufnr


def _create_co(conn, d, user):
    from co.master import create_order
    return create_order(conn, d, user)


def schedule(conn, aufnr, start=None, finish=None):
    """Lead-time scheduling: operations one after the other, duration from the
    standard values and the work center capacity (external: delivery days)."""
    ops = conn.execute("SELECT * FROM pp_oper WHERE aufnr=? ORDER BY vornr", (aufnr,)).fetchall()
    durs = []
    for o in ops:
        if o["steus"] == "PP02":
            r = conn.execute("SELECT plifz FROM routing r JOIN orders x ON x.matnr=r.matnr AND "
                             "x.werks=r.werks WHERE x.aufnr=? AND r.vornr=?",
                             (aufnr, o["vornr"])).fetchone()
            durs.append(max(r["plifz"] if r and r["plifz"] else 3, 1))
        else:
            durs.append(op_duration_days(conn, o["arbpl"], o["vgw"] + (o["vgw_setup"] or 0)))
    total = sum(durs) or 1
    if not start:
        start = add_workdays(finish, -(total - 1))
    cur = add_workdays(start, 0)
    for o, d in zip(ops, durs):
        end = add_workdays(cur, d - 1)
        conn.execute("UPDATE pp_oper SET ssavd=?, ssedd=? WHERE aufnr=? AND vornr=?",
                     (cur, end, aufnr, o["vornr"]))
        cur = add_workdays(end, 1)
    gltrp = add_workdays(start, total - 1)
    conn.execute("UPDATE orders SET gstrp=?, gltrp=? WHERE aufnr=?", (start, gltrp, aufnr))
    for r in conn.execute("SELECT r.rspos, p.ssavd FROM pp_resb r LEFT JOIN pp_oper p ON "
                          "p.aufnr=r.aufnr AND p.vornr=r.vornr WHERE r.rsnum=?", (aufnr,)).fetchall():
        conn.execute("UPDATE pp_resb SET bdter=? WHERE rsnum=? AND rspos=?",
                     (r["ssavd"] or start, aufnr, r["rspos"]))
    return start, gltrp


# ====================================================================== CO02
def change(conn, aufnr, data, user):
    with transaction(conn):
        o = _order(conn, aufnr)
        if o["stat"] in ("TECO", "CLSD", "DLV"):
            raise MMError("Order %s has status %s - no changes" % (aufnr, o["stat"]), "CO", "030")
        items = []
        if data.get("gamng"):
            new = parse_qty(data["gamng"])
            if new < o["wemng"]:
                raise MMError("New quantity is below the delivered quantity %s" % _q(o["wemng"]),
                              "CO", "031")
            old = o["gamng"]
            conn.execute("UPDATE orders SET gamng=? WHERE aufnr=?", (new, aufnr))
            conn.execute("UPDATE pp_oper SET mgvrg=?, vgw=vgw*?/? WHERE aufnr=?",
                         (new, new, old, aufnr))
            conn.execute("UPDATE pp_resb SET bdmng=MAX(enmng, bdmng*?/?) WHERE rsnum=? AND "
                         "kzear=0", (new, old, aufnr))
            items.append(("AFKO", aufnr, "gamng", old, new))
        if data.get("gstrp") or data.get("gltrp") or items:
            schedule(conn, aufnr, parse_date(data["gstrp"]) if data.get("gstrp") else
                     (None if data.get("gltrp") else o["gstrp"]),
                     parse_date(data["gltrp"]) if data.get("gltrp") else None)
            items.append(("AFKO", aufnr, "gstrp", o["gstrp"], data.get("gstrp") or o["gstrp"]))
        from md.changes import log
        log(conn, "ORDER", aufnr, "CO02", user, items)


# ====================================================================== availability
def stock_unrestricted(conn, matnr, werks):
    return conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? AND "
                        "insmk='U' AND lgort<>?", (matnr, werks, SUBCON_SLOC)).fetchone()[0]


def availability(conn, matnr, werks, qty, day, exclude=None):
    """ATP (checking rule PP): unrestricted stock - open reservations of other
    released orders + receipts (POs, production orders) until the date."""
    stock = stock_unrestricted(conn, matnr, werks)
    committed = conn.execute(
        "SELECT COALESCE(SUM(r.bdmng-r.enmng),0) FROM pp_resb r LEFT JOIN orders o ON "
        "o.aufnr=r.aufnr WHERE r.matnr=? AND r.werks=? AND r.kzear=0 AND r.xloek=0 AND "
        "r.bdmng>r.enmng AND (r.aufnr IS NULL OR o.stat='REL') AND r.rsnum<>?",
        (matnr, werks, exclude or "")).fetchone()[0]
    rec = []
    for r in conn.execute("SELECT i.eindt AS d, i.menge-i.wemng AS q FROM po_item i WHERE "
                          "i.matnr=? AND i.werks=? AND i.elikz=0 AND i.wemng<i.menge AND "
                          "COALESCE(i.loekz,0)=0", (matnr, werks)):
        rec.append((r["d"] or day, r["q"]))
    for r in conn.execute("SELECT gltrp AS d, gamng-wemng-COALESCE(iasmg,0) AS q FROM orders "
                          "WHERE matnr=? AND werks=? AND stat='REL' AND aufnr<>?",
                          (matnr, werks, exclude or "")):
        if r["q"] > 0:
            rec.append((r["d"] or day, r["q"]))
    until = sum(q for d, q in rec if d <= day)
    atp = stock - committed + until
    short = max(0, qty - atp)
    commit_date = day
    if short:
        cum = atp
        commit_date = None
        for d, q in sorted(rec):
            if d > day:
                cum += q
                if cum >= qty:
                    commit_date = d
                    break
    return dict(matnr=matnr, werks=werks, required=qty, stock=stock, committed=committed,
                receipts=until, atp=atp, short=short, ok=short == 0, commit_date=commit_date)


def check_order(conn, aufnr):
    o = _order(conn, aufnr)
    out = []
    for r in conn.execute("SELECT r.*, m.maktx, m.meins FROM pp_resb r JOIN material m ON "
                          "m.matnr=r.matnr WHERE r.rsnum=? AND r.kzear=0 AND r.xloek=0 ORDER BY "
                          "rspos", (aufnr,)):
        need = r["bdmng"] - r["enmng"]
        if need <= 0:
            continue
        if o["auart"] in ("ZP03", "ZREF") and r["matnr"] == o["matnr"]:
            st = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? "
                              "AND insmk='B'", (r["matnr"], r["werks"])).fetchone()[0]
            a = dict(matnr=r["matnr"], werks=r["werks"], required=need, stock=st, committed=0,
                     receipts=0, atp=st, short=max(0, need - st), ok=st >= need,
                     commit_date=r["bdter"], note="blocked stock (defective)")
        else:
            a = availability(conn, r["matnr"], r["werks"], need, r["bdter"] or o["gstrp"], aufnr)
        a.update(rspos=r["rspos"], maktx=r["maktx"], meins=r["meins"], bdter=r["bdter"],
                 lgort=r["lgort"])
        out.append(a)
    return out


# ====================================================================== CO05N
def release(conn, aufnr, user, budat=None):
    budat = parse_date(budat)
    with transaction(conn):
        o = _order(conn, aufnr)
        if o["stat"] != "CRTD":
            raise MMError("Order %s is already released" % aufnr, "CO", "020")
        av = check_order(conn, aufnr)
        missing = [a for a in av if not a["ok"]]
        if missing and ORDER_TYPES[o["auart"]]["release_missing"] == "E":
            raise MMError("Order %s cannot be released - missing parts: %s" % (
                aufnr, ", ".join(a["matnr"] for a in missing)), "CO", "260")
        from co.master import set_order_status
        set_order_status(conn, aufnr, "REL")
        conn.execute("UPDATE orders SET ftrmi=? WHERE aufnr=?", (budat, aufnr))
        conn.execute("UPDATE pp_oper SET status='REL' WHERE aufnr=? AND status='CRTD'", (aufnr,))
        sysstat(conn, aufnr, ["REL", "MSPT" if missing else "MACM"], ["CRTD"])
        prs = []
        for op in conn.execute("SELECT p.*, r.ekgrp, r.plifz FROM pp_oper p LEFT JOIN routing r "
                               "ON r.matnr=? AND r.werks=? AND r.vornr=p.vornr WHERE p.aufnr=? "
                               "AND p.steus='PP02' AND p.banfn IS NULL",
                               (o["matnr"], o["werks"], aufnr)).fetchall():
            from pur.pr import create_pr
            r = create_pr(conn, [dict(txz01=("%s ord.%s/%s" % (op["ltxa1"], aufnr, op["vornr"]))[:40],
                                      matkl="SERVICE", meins="PC", menge=_q(op["mgvrg"]),
                                      werks=o["werks"], knttp="F", aufnr=aufnr,
                                      sakto=EXT_COST_ELEMENT, preis=_a(op["preis"]),
                                      flief=op["lifnr"], lfdat=op["ssedd"],
                                      ekgrp=op["ekgrp"] or "003", afnam="CO-" + aufnr)],
                          user, estkz="F", badat=budat)
            conn.execute("UPDATE pp_oper SET banfn=? WHERE aufnr=? AND vornr=?",
                         (r["banfn"], aufnr, op["vornr"]))
            prs.append(r["banfn"])
        if prs:
            sysstat(conn, aufnr, ["EXTP"])
    return {"aufnr": aufnr, "missing": missing, "prs": prs}


# ====================================================================== reservations
def withdrawn(conn, line, raw, bwart, qty):
    """Goods issue / reversal against a reservation (called by MIGO)."""
    sign = 1 if bwart in ("261", "201") else -1
    if raw.get("rsnum"):
        conn.execute("UPDATE pp_resb SET enmng=MAX(0, enmng+?) WHERE rsnum=? AND rspos=?",
                     (sign * qty, str(raw["rsnum"]), int(raw.get("rspos") or 1)))
    elif line.get("aufnr"):
        r = conn.execute("SELECT rspos FROM pp_resb WHERE rsnum=? AND matnr=? AND xloek=0 "
                         "ORDER BY (bdmng>enmng) DESC, rspos LIMIT 1",
                         (line["aufnr"], line["matnr"])).fetchone()
        if r:
            conn.execute("UPDATE pp_resb SET enmng=MAX(0, enmng+?) WHERE rsnum=? AND rspos=?",
                         (sign * qty, line["aufnr"], r["rspos"]))
        if conn.execute("SELECT 1 FROM orders WHERE aufnr=?", (line["aufnr"],)).fetchone():
            sysstat(conn, line["aufnr"], ["GMPS"])


def picking_list(conn, werks="1000"):
    """CO27: open reservations of released orders that are not backflushed."""
    out = []
    for r in conn.execute("SELECT r.*, o.matnr AS header, o.gstrp, m.maktx, m.meins FROM pp_resb r "
                          "JOIN orders o ON o.aufnr=r.aufnr JOIN material m ON m.matnr=r.matnr "
                          "WHERE o.stat='REL' AND r.rgekz=0 AND r.kzear=0 AND r.xloek=0 AND "
                          "r.bdmng>r.enmng AND r.werks=? ORDER BY r.bdter, r.aufnr, r.rspos",
                          (werks,)):
        d = dict(r)
        d["open"] = r["bdmng"] - r["enmng"]
        d["stock"] = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND "
                                  "werks=? AND lgort=? AND insmk=?",
                                  (r["matnr"], werks, r["lgort"],
                                   "B" if r["matnr"] == r["header"] else "U")).fetchone()[0]
        b = conn.execute("SELECT lgpla, wdatu FROM quant WHERE matnr=? AND werks=? AND lgort=? "
                         "AND qty>0 ORDER BY wdatu, lgpla LIMIT 1",
                         (r["matnr"], werks, r["lgort"])).fetchone()
        d["bin"] = b["lgpla"] if b else ""
        out.append(d)
    return out


def post_picking(conn, items, budat, user):
    """items: [{rsnum, rspos, qty}] -> 261 goods issue to the orders."""
    lines = []
    for it in items:
        r = conn.execute("SELECT r.*, o.matnr AS header, o.auart FROM pp_resb r JOIN orders o ON "
                         "o.aufnr=r.aufnr WHERE r.rsnum=? AND r.rspos=?",
                         (str(it["rsnum"]), int(it["rspos"]))).fetchone()
        if not r:
            raise MMError("Reservation %s/%s does not exist" % (it["rsnum"], it["rspos"]),
                          "M7", "101")
        q = parse_qty(it.get("qty") or _q(r["bdmng"] - r["enmng"]))
        line = {"bwart": "261", "matnr": r["matnr"], "werks": r["werks"], "lgort": r["lgort"],
                "qty": _q(q), "aufnr": r["aufnr"], "rsnum": r["rsnum"], "rspos": r["rspos"],
                "lgpla": it.get("lgpla") or ""}
        if r["auart"] in ("ZP03", "ZREF") and r["matnr"] == r["header"]:
            line["insmk"] = "B"              # defective units come from blocked stock
        lines.append(line)
    from mm.posting import post_goods_movement
    return post_goods_movement(conn, {"budat": budat, "bktxt": "Picking list CO27"}, lines,
                               user, tcode="CO27")


# ====================================================================== CO11N
def confirm(conn, aufnr, vornr, yield_qty, scrap="0", act=None, budat=None, final=None,
            user="", lgpla=None):
    budat = parse_date(budat)
    with transaction(conn):
        o = _order(conn, aufnr)
        if o["stat"] not in ("REL", "DLV"):
            raise MMError("Order %s has status %s - confirmation not possible" % (aufnr, o["stat"]),
                          "RU", "100")
        op = conn.execute("SELECT * FROM pp_oper WHERE aufnr=? AND vornr=?",
                          (aufnr, str(vornr).zfill(4))).fetchone()
        if not op:
            raise MMError("Operation %s does not exist in order %s" % (vornr, aufnr), "RU", "001")
        if CONTROL_KEYS[op["steus"]]["external"]:
            raise MMError("Operation %s is processed externally - it is confirmed by the goods "
                          "receipt of the purchase order" % op["vornr"], "RU", "102")
        if op["status"] == "CNF":
            raise MMError("Operation %s is already finally confirmed" % op["vornr"], "RU", "103")
        y = parse_qty(yield_qty or "0", allow_zero=True)
        x = parse_qty(scrap or "0", allow_zero=True)
        if op["lmnga"] + op["xmnga"] + y + x > op["mgvrg"] * 11 // 10:
            raise MMError("Confirmed quantity exceeds the operation quantity %s by more than 10 %%"
                          % _q(op["mgvrg"]), "RU", "005")
        setup = op["vgw_setup"] if not op["ism"] else 0
        a = parse_qty(act) if act not in (None, "") else \
            setup + rdiv(op["vgw"] * (y + x), op["mgvrg"])
        wc = conn.execute("SELECT * FROM work_center WHERE arbpl=?", (op["arbpl"],)).fetchone()
        from co.actual import allocate_activity
        codoc = allocate_activity(conn, budat, wc["kostl"], wc["lstar"], _q(a), {"aufnr": aufnr},
                                  "Confirmation %s/%s" % (aufnr, op["vornr"]), user) if a else None
        done = op["lmnga"] + op["xmnga"] + y + x
        fin = final if final is not None else done >= op["mgvrg"]
        conn.execute("UPDATE pp_oper SET ism=ism+?, lmnga=lmnga+?, xmnga=xmnga+?, status=? WHERE "
                     "aufnr=? AND vornr=?", (a, y, x, "CNF" if fin else "PCNF", aufnr, op["vornr"]))
        items = []
        ops = conn.execute("SELECT vornr FROM pp_oper WHERE aufnr=? ORDER BY vornr",
                           (aufnr,)).fetchall()
        first = ops[0]["vornr"]
        last = ops[-1]["vornr"]
        for r in conn.execute("SELECT * FROM pp_resb WHERE rsnum=? AND rgekz=1 AND kzear=0 AND "
                              "xloek=0 AND bdmng>enmng AND (vornr=? OR (COALESCE(vornr,'')='' "
                              "AND ?=?))", (aufnr, op["vornr"], op["vornr"], first)).fetchall():
            q = min(rdiv(r["bdmng"] * (y + x), o["gamng"]), r["bdmng"] - r["enmng"])
            if fin and op["vornr"] == last:
                q = max(q, 0)
            if q > 0:
                items.append({"bwart": "261", "matnr": r["matnr"], "werks": r["werks"],
                              "lgort": r["lgort"], "qty": _q(q), "aufnr": aufnr,
                              "rsnum": aufnr, "rspos": r["rspos"],
                              "sgtxt": "Backflush op. %s" % op["vornr"]})
        if CONTROL_KEYS[op["steus"]]["auto_gr"] and y:
            gr = {"bwart": "101", "aufnr": aufnr, "qty": _q(y), "lgort": o["lgort"],
                  "sgtxt": "Automatic GR op. %s" % op["vornr"]}
            if lgpla:
                gr["lgpla"] = lgpla
            else:
                from mm.posting import propose_bin
                pb = propose_bin(conn, o["matnr"], o["werks"], o["lgort"] or "")
                if pb:
                    gr["lgpla"] = pb["lgpla"]
            items.append(gr)
        mblnr = None
        if items:
            from mm.posting import post_goods_movement
            mblnr = post_goods_movement(conn, {"budat": budat, "bktxt": "Confirmation %s/%s"
                                               % (aufnr, op["vornr"])}, items, user,
                                        tcode="CO11N")["mblnr"]
        if op["vornr"] == last:
            conn.execute("UPDATE orders SET igmng=igmng+? WHERE aufnr=?", (y, aufnr))
        conn.execute("UPDATE orders SET iasmg=iasmg+? WHERE aufnr=?", (x, aufnr))
        cur = conn.execute("INSERT INTO confirmation (aufnr,vornr,arbpl,lmnga,ism,budat,codoc,"
                           "usnam,xmnga,aueru,mblnr,ersda) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (aufnr, op["vornr"], op["arbpl"], y, a, budat, codoc, user, x,
                            1 if fin else 0, mblnr, now_ts()))
        _conf_status(conn, aufnr)
    return {"rueck": cur.lastrowid, "codoc": codoc, "mblnr": mblnr, "activity": a,
            "backflush": len([i for i in items if i["bwart"] == "261"]),
            "auto_gr": any(i["bwart"] == "101" for i in items), "final": bool(fin)}


def _conf_status(conn, aufnr):
    ops = conn.execute("SELECT steus, status, lmnga FROM pp_oper WHERE aufnr=?",
                       (aufnr,)).fetchall()
    internal = [p for p in ops if p["steus"] != "PP02"]
    if internal and all(p["status"] == "CNF" for p in internal):
        sysstat(conn, aufnr, ["CNF"], ["PCNF"])
    elif any(p["status"] in ("PCNF", "CNF") for p in internal):
        sysstat(conn, aufnr, ["PCNF"], ["CNF"])
    else:
        sysstat(conn, aufnr, [], ["PCNF", "CNF"])
    o = conn.execute("SELECT gamng, wemng FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
    if 0 < o["wemng"] < o["gamng"]:
        sysstat(conn, aufnr, ["PDLV"])
    elif o["wemng"] >= o["gamng"] and o["gamng"]:
        sysstat(conn, aufnr, ["DLV"], ["PDLV", "MSPT"])


def cancel_confirmation(conn, rueck, user, budat=None):
    budat = parse_date(budat)
    with transaction(conn):
        c = conn.execute("SELECT * FROM confirmation WHERE rueck=?", (int(rueck),)).fetchone()
        if not c:
            raise MMError("Confirmation %s does not exist" % rueck, "RU", "010")
        if c["stokz"]:
            raise MMError("Confirmation %s is already cancelled" % rueck, "RU", "011")
        if c["codoc"]:
            from co.core import reverse_co_doc
            reverse_co_doc(conn, c["codoc"], user, "Cancel confirmation %s" % rueck)
        if c["mblnr"]:
            from mm.posting import cancel_document
            mj = conn.execute("SELECT mjahr FROM mat_doc WHERE mblnr=?", (c["mblnr"],)).fetchone()
            cancel_document(conn, c["mblnr"], mj["mjahr"], budat, user,
                            "Cancel confirmation %s" % rueck)
            for l in conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND bwart='261'",
                                  (c["mblnr"],)).fetchall():
                withdrawn(conn, dict(l), {}, "262", l["menge"])
        conn.execute("UPDATE pp_oper SET ism=ism-?, lmnga=lmnga-?, xmnga=xmnga-?, status=CASE "
                     "WHEN lmnga-?+xmnga-?>0 THEN 'PCNF' ELSE 'REL' END WHERE aufnr=? AND vornr=?",
                     (c["ism"], c["lmnga"], c["xmnga"], c["lmnga"], c["xmnga"], c["aufnr"],
                      c["vornr"]))
        last = conn.execute("SELECT MAX(vornr) FROM pp_oper WHERE aufnr=?",
                            (c["aufnr"],)).fetchone()[0]
        if c["vornr"] == last:
            conn.execute("UPDATE orders SET igmng=igmng-? WHERE aufnr=?", (c["lmnga"], c["aufnr"]))
        conn.execute("UPDATE orders SET iasmg=iasmg-? WHERE aufnr=?", (c["xmnga"], c["aufnr"]))
        conn.execute("UPDATE confirmation SET stokz=1 WHERE rueck=?", (int(rueck),))
        _conf_status(conn, c["aufnr"])
    return {"rueck": rueck}


# ====================================================================== TECO
def teco(conn, aufnr, user):
    with transaction(conn):
        o = _order(conn, aufnr)
        from co.master import set_order_status
        set_order_status(conn, aufnr, "TECO")
        conn.execute("UPDATE pp_resb SET kzear=1 WHERE rsnum=?", (aufnr,))
        sysstat(conn, aufnr, ["TECO"], ["MSPT", "MACM"])
        from md.changes import log
        log(conn, "ORDER", aufnr, "CO02", user, [("AUFK", aufnr, "stat", o["stat"], "TECO")])


def status_text(o):
    flags = [o["stat"]] + [s for s in (o["sysst"] or "").split() if s != o["stat"]]
    return " ".join(dict.fromkeys(flags))


# ====================================================================== CO03
def detail(conn, aufnr):
    o = dict(_order(conn, aufnr))
    o["status"] = status_text(o)
    o["status_texts"] = [dict(code=s, text=STATUS.get(s, "")) for s in o["status"].split()]
    o["type_text"] = ORDER_TYPES[o["auart"]]["text"]
    m = conn.execute("SELECT maktx, meins FROM material WHERE matnr=?", (o["matnr"],)).fetchone()
    o["maktx"], o["meins"] = (m["maktx"], m["meins"]) if m else (o["ktext"], "")
    o["ops"] = rows(conn.execute(
        "SELECT p.*, w.ktext AS wtext, v.name AS vname FROM pp_oper p LEFT JOIN work_center w ON "
        "w.arbpl=p.arbpl LEFT JOIN vendor v ON v.lifnr=p.lifnr WHERE p.aufnr=? ORDER BY vornr",
        (aufnr,)))
    for p in o["ops"]:
        if p["banfn"]:
            ext = ext_status(conn, p["banfn"])
            p.update(ext)
            if ext["ext_done"]:
                p["status"] = "CNF"
    o["comps"] = rows(conn.execute(
        "SELECT r.*, m.maktx, m.meins FROM pp_resb r JOIN material m ON m.matnr=r.matnr WHERE "
        "r.rsnum=? ORDER BY rspos", (aufnr,)))
    o["confirmations"] = rows(conn.execute(
        "SELECT * FROM confirmation WHERE aufnr=? ORDER BY rueck", (aufnr,)))
    o["movements"] = rows(conn.execute(
        "SELECT i.mblnr, i.zeile, h.budat, i.bwart, i.matnr, i.menge, i.meins, i.dmbtr, i.shkzg, "
        "i.lgort, i.insmk FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr "
        "WHERE i.aufnr=? ORDER BY h.budat, i.mblnr, i.zeile", (aufnr,)))
    o["costs"] = costs(conn, o)
    o["availability"] = check_order(conn, aufnr) if o["stat"] in ("CRTD", "REL") else []
    o["wip"] = rows(conn.execute("SELECT * FROM pp_wip WHERE aufnr=? ORDER BY gjahr, perio",
                                 (aufnr,)))
    o["rules"] = rows(conn.execute("SELECT * FROM settle_rule WHERE aufnr=?", (aufnr,)))
    return o


def ext_status(conn, banfn):
    pr = conn.execute("SELECT ebeln, ebelp, menge FROM pr_item WHERE banfn=?", (banfn,)).fetchone()
    po = conn.execute("SELECT menge, wemng FROM po_item WHERE ebeln=? AND ebelp=?",
                      (pr["ebeln"], pr["ebelp"])).fetchone() if pr and pr["ebeln"] else None
    return dict(ebeln=pr["ebeln"] if pr else None, ext_received=po["wemng"] if po else 0,
                ext_done=bool(po and po["wemng"] >= po["menge"]))


def costs(conn, o):
    """Plan (cost estimate x order qty), target (x delivered qty) and actual by cost element."""
    plan = {}
    if o.get("estimate_id"):
        e = conn.execute("SELECT * FROM cost_estimate WHERE id=?", (o["estimate_id"],)).fetchone()
        for i in conn.execute("SELECT kstar, SUM(wert) w FROM cost_estimate_item WHERE id=? "
                              "GROUP BY kstar", (e["id"],)):
            plan[i["kstar"]] = [rdiv(i["w"] * o["gamng"], e["losgr"]),
                                rdiv(i["w"] * o["wemng"], e["losgr"])]
    act = {r["kstar"]: r["w"] for r in conn.execute(
        "SELECT kstar, SUM(wtg) w FROM co_item WHERE objnr=? AND wrttp='04' GROUP BY kstar",
        ("OR" + o["aufnr"],))}
    names = {r["kstar"]: r["ktext"] for r in conn.execute("SELECT kstar, ktext FROM cost_element")}
    out = []
    for k in sorted(set(plan) | set(act)):
        p = plan.get(k, [0, 0])
        out.append(dict(kstar=k, ktext=names.get(k, ""), plan=p[0], target=p[1],
                        actual=act.get(k, 0), variance=act.get(k, 0) - p[1]))
    return out


def coois(conn, auart="", stat="", matnr="", d1="", d2=""):
    sql = "SELECT o.*, m.maktx, m.meins FROM orders o LEFT JOIN material m ON m.matnr=o.matnr " \
          "WHERE o.auart IN ('PP01','ZP03','ZREF','ZP07')"
    args = []
    for col, v in (("o.auart", auart), ("o.stat", stat), ("o.matnr", matnr.upper())):
        if v:
            sql += " AND %s=?" % col
            args.append(v)
    if d1:
        sql += " AND COALESCE(o.gstrp,o.erdat)>=?"
        args.append(d1)
    if d2:
        sql += " AND COALESCE(o.gstrp,o.erdat)<=?"
        args.append(d2)
    out = rows(conn.execute(sql + " ORDER BY o.aufnr DESC", args))
    for r in out:
        r["status"] = status_text(r)
        r["actual"] = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? AND "
                                   "wrttp='04' AND kstar<>'895000'", ("OR" + r["aufnr"],)).fetchone()[0]
        r["progress"] = round(100.0 * (r["igmng"] or 0) / r["gamng"], 1) if r["gamng"] else 0
        r["late"] = 1 if (r["gltrp"] and r["stat"] in ("CRTD", "REL") and
                          r["gltrp"] < datetime.date.today().isoformat()) else 0
        r["type_text"] = ORDER_TYPES.get(r["auart"], {}).get("text", "")
    return out


def qty_txt(v):
    return qty_out(v)
