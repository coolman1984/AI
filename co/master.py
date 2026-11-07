"""CO master data: cost elements (KA01/KA06), standard hierarchy (OKEON),
activity types (KL01), statistical key figures (KK01), default account
assignment (OKB9), orders (KO01/CO01) + settlement rules (KO02), BOM (CS01),
work centers (CR01), routings (CA01), costing sheet (KZS2), customers (XD01),
allocation cycles (KSV1 / KSU1 / KEU1)."""
from mm.config import GL_ACCOUNTS
from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_qty

from .config import CC_CATEGORIES, CE_CATEGORIES, ORDER_TYPES
from .core import first_day


def _need(conn, sql, args, msg, cls="KI", no="100"):
    if not conn.execute(sql, args).fetchone():
        raise MMError(msg, cls, no)


def _key(v, what):
    v = (v or "").strip().upper()
    if not v:
        raise MMError("Enter a %s" % what, "00", "055")
    return v


# ------------------------------------------------------------ cost elements
def create_cost_element(conn, kstar, ktext, katyp):
    kstar = _key(kstar, "cost element")
    katyp = int(katyp)
    if katyp not in CE_CATEGORIES:
        raise MMError("Cost element category %s does not exist" % katyp, "KS", "021")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM cost_element WHERE kstar=?", (kstar,)).fetchone():
            raise MMError("Cost element %s already exists" % kstar, "KS", "022")
        if katyp in (1, 11, 12) and kstar not in GL_ACCOUNTS:
            raise MMError("Primary cost element %s must exist as a G/L account"
                          % kstar, "KS", "023")
        conn.execute("INSERT INTO cost_element VALUES (?,?,?)", (kstar, ktext, katyp))


def create_cc_group(conn, khinr, ktext, parent=""):
    khinr = _key(khinr, "hierarchy node")
    with transaction(conn):
        if parent:
            _need(conn, "SELECT 1 FROM cc_group WHERE khinr=?", (parent,),
                  "Parent node %s does not exist" % parent)
        conn.execute("INSERT OR REPLACE INTO cc_group VALUES (?,?,?)",
                     (khinr, ktext, parent or ""))


def change_cost_center(conn, kostl, name=None, kosar=None, khinr=None, verak=None):
    with transaction(conn):
        _need(conn, "SELECT 1 FROM cost_center WHERE kostl=?", (kostl,),
              "Cost center %s does not exist" % kostl, "KS", "004")
        if kosar is not None and kosar and kosar not in CC_CATEGORIES:
            raise MMError("Cost center category %s does not exist" % kosar)
        for f, v in (("name", name), ("kosar", kosar), ("khinr", khinr),
                     ("verak", verak)):
            if v is not None:
                conn.execute("UPDATE cost_center SET %s=? WHERE kostl=?" % f, (v, kostl))


def create_activity_type(conn, lstar, ktext, meinh, kstar, ccomp=30):
    lstar = _key(lstar, "activity type")
    with transaction(conn):
        ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                          (kstar,)).fetchone()
        if not ce or ce["katyp"] != 43:
            raise MMError("Allocation cost element %s must have category 43" % kstar,
                          "KL", "001")
        conn.execute("INSERT INTO activity_type VALUES (?,?,?,?,?)",
                     (lstar, ktext, meinh, kstar, int(ccomp)))


def create_skf(conn, stagr, ktext, meinh, fixed=True):
    stagr = _key(stagr, "statistical key figure")
    with transaction(conn):
        conn.execute("INSERT INTO stat_kf VALUES (?,?,?,?)",
                     (stagr, ktext, meinh, 1 if fixed else 0))


def set_default_aa(conn, kstar, kostl):
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO default_aa VALUES (?,?)", (kstar, kostl))


# ------------------------------------------------------------ orders
def create_order(conn, data, user):
    """KO01 (internal order) / CO01 (production order).
    data: auart, ktext, kostl, matnr, werks, lgort, gamng, rules=[{konty,
    receiver, prozs}], release"""
    auart = (data.get("auart") or "ZINT").upper()
    if auart not in ORDER_TYPES:
        raise MMError("Order type %s does not exist" % auart, "KO", "002")
    with transaction(conn):
        aufnr = str(next_number(conn, "ORD_PP" if auart == "PP01" else "ORD_INT"))
        matnr = werks = lgort = None
        gamng = 0
        est = None
        if auart == "PP01":
            matnr = (data.get("matnr") or "").upper()
            werks = data.get("werks") or "1000"
            lgort = data.get("lgort") or ""
            gamng = parse_qty(data.get("gamng"))
            _need(conn, "SELECT 1 FROM routing WHERE matnr=? AND werks=?",
                  (matnr, werks), "No routing for material %s in plant %s"
                  % (matnr, werks), "CO", "004")
            _need(conn, "SELECT 1 FROM bom WHERE matnr=? AND werks=?",
                  (matnr, werks), "No BOM for material %s in plant %s"
                  % (matnr, werks), "CO", "005")
            e = conn.execute("SELECT id FROM cost_estimate WHERE matnr=? AND "
                             "werks=? AND status='FR' ORDER BY id DESC LIMIT 1",
                             (matnr, werks)).fetchone()
            est = e["id"] if e else None
            ktext = data.get("ktext") or "Production %s" % matnr
        else:
            ktext = (data.get("ktext") or "").strip()
            if not ktext:
                raise MMError("Enter a description", "KO", "003")
        kostl = (data.get("kostl") or "").upper() or None
        if kostl:
            _need(conn, "SELECT 1 FROM cost_center WHERE kostl=?", (kostl,),
                  "Cost center %s does not exist" % kostl)
        conn.execute("INSERT INTO orders (aufnr,auart,ktext,kostl,matnr,werks,lgort,"
                     "gamng,wemng,stat,erdat,ernam,estimate_id) VALUES "
                     "(?,?,?,?,?,?,?,?,0,'CRTD',?,?,?)",
                     (aufnr, auart, ktext, kostl, matnr, werks, lgort, gamng,
                      (data.get("erdat") or now_ts()[:10]), user, est))
        rules = data.get("rules")
        if rules is None:
            rules = [{"konty": "PA", "receiver": matnr, "prozs": 100}] \
                if auart == "PP01" else []
        _set_rules(conn, aufnr, rules)
        if data.get("release"):
            conn.execute("UPDATE orders SET stat='REL' WHERE aufnr=?", (aufnr,))
    return aufnr


def _set_rules(conn, aufnr, rules):
    conn.execute("DELETE FROM settle_rule WHERE aufnr=?", (aufnr,))
    total = 0
    for i, r in enumerate(rules, start=1):
        konty = (r.get("konty") or "").upper()
        rec = (r.get("receiver") or "").upper()
        pct = int(r.get("prozs") or 0)
        if konty == "KS":
            _need(conn, "SELECT 1 FROM cost_center WHERE kostl=?", (rec,),
                  "Settlement receiver cost center %s does not exist" % rec)
        elif konty == "PA":
            pass
        else:
            raise MMError("Settlement receiver type %s not supported (KS, PA)"
                          % konty, "KD", "001")
        total += pct
        conn.execute("INSERT INTO settle_rule VALUES (?,?,?,?,?)",
                     (aufnr, i, konty, rec, pct))
    if rules and total != 100:
        raise MMError("Settlement rule percentages must add up to 100 %% (now %s)"
                      % total, "KD", "002")


def change_settlement_rule(conn, aufnr, rules):
    with transaction(conn):
        _need(conn, "SELECT 1 FROM orders WHERE aufnr=?", (aufnr,),
              "Order %s does not exist" % aufnr, "KO", "001")
        _set_rules(conn, aufnr, rules)


def set_order_status(conn, aufnr, action):
    """REL release, TECO technically complete, CLSD close (balance must be 0)."""
    with transaction(conn):
        o = conn.execute("SELECT * FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
        if not o:
            raise MMError("Order %s does not exist" % aufnr, "KO", "001")
        if action == "REL":
            if o["stat"] != "CRTD":
                raise MMError("Order %s is already released" % aufnr, "KO", "020")
            new = "REL"
        elif action == "TECO":
            if o["stat"] not in ("REL", "DLV"):
                raise MMError("Order %s must be released first" % aufnr, "KO", "021")
            new = "TECO"
        elif action == "CLSD":
            bal = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE "
                               "objnr=? AND wrttp='04'", ("OR" + aufnr,)).fetchone()[0]
            if bal:
                raise MMError("Order %s still has a balance of %.2f - settle first"
                              % (aufnr, bal / 100.0), "KO", "022")
            new = "CLSD"
        else:
            raise MMError("Unknown status action %s" % action)
        conn.execute("UPDATE orders SET stat=? WHERE aufnr=?", (new, aufnr))
    return new


# ------------------------------------------------------------ logistics data
def create_bom(conn, matnr, werks, basis, items):
    """CS01. items: [(component, qty per base)]"""
    with transaction(conn):
        conn.execute("DELETE FROM bom WHERE matnr=? AND werks=?", (matnr, werks))
        b = parse_qty(basis)
        for i, (comp, q) in enumerate(items, start=1):
            _need(conn, "SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                  (comp, werks), "Component %s not in plant %s" % (comp, werks),
                  "29", "001")
            conn.execute("INSERT INTO bom VALUES (?,?,?,?,?,?)",
                         (matnr, werks, i * 10, comp, parse_qty(q), b))


def create_work_center(conn, arbpl, werks, ktext, kostl, lstar):
    with transaction(conn):
        _need(conn, "SELECT 1 FROM cost_center WHERE kostl=?", (kostl,),
              "Cost center %s does not exist" % kostl)
        _need(conn, "SELECT 1 FROM activity_type WHERE lstar=?", (lstar,),
              "Activity type %s does not exist" % lstar)
        conn.execute("INSERT OR REPLACE INTO work_center VALUES (?,?,?,?,?)",
                     (arbpl.upper(), werks, ktext, kostl, lstar))


def create_routing(conn, matnr, werks, basis, ops):
    """CA01. ops: [(vornr, arbpl, text, std value per base qty)]"""
    with transaction(conn):
        conn.execute("DELETE FROM routing WHERE matnr=? AND werks=?", (matnr, werks))
        b = parse_qty(basis)
        for vornr, arbpl, txt, vgw in ops:
            _need(conn, "SELECT 1 FROM work_center WHERE arbpl=?", (arbpl,),
                  "Work center %s does not exist" % arbpl, "CR", "001")
            conn.execute("INSERT INTO routing VALUES (?,?,?,?,?,?,?)",
                         (matnr, werks, vornr, arbpl, txt, parse_qty(vgw), b))


def set_costing_sheet(conn, rows_):
    """KZS2: [(zeile, text, base 'MAT'|'ACT', pct_fix, pct_var, credit kostl,
    overhead cost element, cost component)] percentages in 1/100 %."""
    with transaction(conn):
        conn.execute("DELETE FROM costing_sheet")
        for r in rows_:
            ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                              (r[6],)).fetchone()
            if not ce or ce["katyp"] != 41:
                raise MMError("Overhead cost element %s must have category 41" % r[6])
            conn.execute("INSERT INTO costing_sheet VALUES (?,?,?,?,?,?,?,?)", r)


def create_customer(conn, kunnr, name, city, region, kdgrp, vtweg):
    with transaction(conn):
        if conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
            raise MMError("Customer %s already exists" % kunnr, "F2", "001")
        conn.execute("INSERT INTO customer VALUES (?,?,?,?,?,?)",
                     (kunnr.upper(), name, city, region, kdgrp, vtweg))


# ------------------------------------------------------------ cycles
def save_cycle(conn, cycle, ktext, typ, seq, segments):
    """segments: [dict(seg, ktext, senders, sender_kstar, kstar, receivers,
    tracing, vv)]"""
    cycle = _key(cycle, "cycle")
    if typ not in ("D", "A", "P"):
        raise MMError("Cycle type must be D (distribution), A (assessment) or "
                      "P (assessment to CO-PA)")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO cycle VALUES (?,?,?,?)",
                     (cycle, ktext, typ, int(seq)))
        conn.execute("DELETE FROM cycle_segment WHERE cycle=?", (cycle,))
        for s in segments:
            for k in (s.get("senders") or "").split(","):
                _need(conn, "SELECT 1 FROM cost_center WHERE kostl=?", (k.strip(),),
                      "Sender cost center %s does not exist" % k.strip())
            if typ in ("A", "P"):
                ce = conn.execute("SELECT katyp FROM cost_element WHERE kstar=?",
                                  (s.get("kstar"),)).fetchone()
                if not ce or ce["katyp"] != 42:
                    raise MMError("Assessment cost element %s must have category 42"
                                  % s.get("kstar"), "GA", "001")
            conn.execute("INSERT INTO cycle_segment VALUES (?,?,?,?,?,?,?,?,?)",
                         (cycle, int(s["seg"]), s.get("ktext") or "",
                          s["senders"], s.get("sender_kstar") or "",
                          s.get("kstar") or "", s.get("receivers") or "",
                          s["tracing"], s.get("vv") or ""))


def get_cycles(conn):
    out = rows(conn.execute("SELECT * FROM cycle ORDER BY seq, cycle"))
    for c in out:
        c["segments"] = rows(conn.execute("SELECT * FROM cycle_segment WHERE "
                                          "cycle=? ORDER BY seg", (c["cycle"],)))
    return out


def period_start(gjahr, perio):
    return first_day(gjahr, perio)
