"""Sales documents.

VA11/VA21/VA01  inquiry, quotation, order (OR, RO rush, FD free of charge, ZSP spare
                parts, ZWR warranty replacement), returns RE, credit / debit memo
                requests CR / DR - with reference (copy control VTAA)
VA02 / VA03     change (reject items, remove blocks, re-ATP) / display
availability    ATP per schedule line: stock - confirmed sales - order reservations
                + receipts; delivery date proposal (pick time 1 working day);
                partial confirmation + backorder date from the next receipt
credit (OVA8)   dynamic check: open items + open orders + deliveries not billed;
                oldest item overdue > 30 days -> credit block, VKM1 releases
V.02            incompletion log        VB01  material listing / exclusion
VA05 / V.15     order list / backorders          VKM1  blocked SD documents
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_int, parse_price, parse_qty, rdiv

from . import pricing
from .config import (DOC_TYPES, ITEM_CATS, COPY_CONTROL, ORDER_REASONS, CREDIT, VBTYP,
                     REJECTION_REASONS, PICK_DAYS)


def _wd(day, n):
    from pp.master import add_workdays
    return add_workdays(day, n)


def area_of(conn, kunnr, vtweg=None):
    sql = "SELECT * FROM md_knvv WHERE kunnr=? AND vkorg='1000'"
    args = [kunnr]
    if vtweg:
        sql += " AND vtweg=?"
        args.append(vtweg)
    r = conn.execute(sql + " ORDER BY vtweg LIMIT 1", args).fetchone()
    return dict(r) if r else None


# ====================================================================== availability
def committed_sales(conn, matnr, werks, exclude=None):
    """Confirmed sales quantity not yet delivered (other documents)."""
    conf = conn.execute(
        "SELECT COALESCE(SUM(e.bmeng),0) FROM sd_vbep e JOIN sd_vbap p ON p.vbeln=e.vbeln AND "
        "p.posnr=e.posnr JOIN sd_vbak k ON k.vbeln=e.vbeln WHERE p.matnr=? AND p.werks=? AND "
        "k.vbtyp='C' AND COALESCE(p.abgru,'')='' AND e.vbeln<>?", (matnr, werks, exclude or "")
    ).fetchone()[0]
    dlv = conn.execute(
        "SELECT COALESCE(SUM(l.lfimg),0) FROM sd_lips l JOIN sd_vbak k ON k.vbeln=l.vgbel JOIN sd_vbap p "
        "ON p.vbeln=l.vgbel AND p.posnr=l.vgpos JOIN sd_likp h ON h.vbeln=l.vbeln WHERE p.matnr=? AND "
        "p.werks=? AND k.vbtyp='C' AND h.wbstk='C' AND COALESCE(p.abgru,'')='' AND k.vbeln<>?",
        (matnr, werks, exclude or "")).fetchone()[0]
    return max(0, conf - dlv)


def atp(conn, matnr, werks, qty, mbdat, exclude=None):
    """Returns list of (date, confirmed qty)."""
    from pp.order import stock_unrestricted
    stock = stock_unrestricted(conn, matnr, werks)
    resv = conn.execute("SELECT COALESCE(SUM(r.bdmng-r.enmng),0) FROM pp_resb r LEFT JOIN orders o "
                        "ON o.aufnr=r.aufnr WHERE r.matnr=? AND r.werks=? AND r.kzear=0 AND "
                        "r.bdmng>r.enmng AND (r.aufnr IS NULL OR o.stat='REL')",
                        (matnr, werks)).fetchone()[0]
    free = stock - resv - committed_sales(conn, matnr, werks, exclude)
    rec = []
    for r in conn.execute("SELECT eindt d, menge-wemng q FROM po_item WHERE matnr=? AND werks=? AND "
                          "elikz=0 AND wemng<menge AND COALESCE(loekz,0)=0", (matnr, werks)):
        rec.append((r["d"] or mbdat, r["q"]))
    for r in conn.execute("SELECT gltrp d, gamng-wemng-COALESCE(iasmg,0) q FROM orders WHERE matnr=? "
                          "AND werks=? AND stat IN ('CRTD','REL') AND auart='PP01'", (matnr, werks)):
        if r["q"] > 0:
            rec.append((r["d"] or mbdat, r["q"]))
    rec.sort()
    now_ok = max(0, min(qty, free + sum(q for d, q in rec if d <= mbdat)))
    out = [(mbdat, now_ok)] if now_ok else []
    rest = qty - now_ok
    cum = free + sum(q for d, q in rec if d <= mbdat) - now_ok
    for d, q in rec:
        if rest <= 0:
            break
        if d > mbdat:
            cum += q
            take = min(rest, max(0, cum))
            if take > 0:
                out.append((d, take))
                rest -= take
                cum -= take
    return out, rest


# ====================================================================== credit
def exposure(conn, kunnr, exclude=None):
    from fi.ar import credit_exposure
    open_items = credit_exposure(conn, kunnr)
    orders = 0
    for p in conn.execute("SELECT p.*, k.vbtyp FROM sd_vbap p JOIN sd_vbak k USING (vbeln) WHERE "
                          "k.kunnr=? AND k.vbtyp IN ('C','L') AND COALESCE(p.abgru,'')='' AND "
                          "k.vbeln<>? AND p.netwr>0", (kunnr, exclude or "")):
        billed = conn.execute("SELECT COALESCE(SUM(i.fkimg),0) FROM billing_item i JOIN billing b USING "
                              "(vbeln) WHERE i.aubel=? AND i.aupos=? AND b.cancelled=0",
                              (p["vbeln"], p["posnr"])).fetchone()[0]
        open_q = max(0, p["kwmeng"] - billed)
        if p["kwmeng"]:
            orders += rdiv((p["netwr"] + p["mwsbp"] + p["freight"]) * open_q, p["kwmeng"])
    return dict(open_items=open_items, open_orders=orders, total=open_items + orders)


def credit_check(conn, kunnr, value, today, exclude=None, with_overdue=True):
    """Returns (ok, reason)."""
    c = conn.execute("SELECT klimk FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
    e = exposure(conn, kunnr, exclude)
    if c and c["klimk"] and e["total"] + value > c["klimk"]:
        return False, "Credit limit exceeded: limit %.2f, exposure %.2f + document %.2f" % (
            c["klimk"] / 100.0, e["total"] / 100.0, value / 100.0)
    if not with_overdue:
        return True, ""
    lim = (datetime.date.fromisoformat(today) - datetime.timedelta(days=CREDIT["oldest_days"])).isoformat()
    od = conn.execute("SELECT MIN(i.netdt) FROM acc_doc_item i WHERE i.koart='D' AND i.kunnr=? AND "
                      "i.augbl IS NULL AND i.shkzg='S' AND i.netdt<?", (kunnr, lim)).fetchone()[0]
    if od:
        return False, "Oldest open item overdue since %s (more than %d days)" % (od, CREDIT["oldest_days"])
    return True, ""


# ====================================================================== create
def create(conn, data, user):
    auart = (data.get("auart") or "OR").upper()
    t = DOC_TYPES.get(auart)
    if not t:
        raise MMError("Sales document type %s is not defined (VOV8)" % auart, "V1", "001")
    audat = parse_date(data.get("audat"))
    kunnr = (data.get("kunnr") or "").upper()
    ref = None
    if data.get("vgbel"):
        ref = _reference(conn, auart, data["vgbel"], audat)
        kunnr = kunnr or ref["kunnr"]
    elif t["ref"]:
        raise MMError("Document type %s must be created with reference to a billing document"
                      % auart, "V1", "012")
    with transaction(conn):
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
        if not c:
            raise MMError("Sold-to party %s does not exist" % kunnr, "V1", "002")
        if c["loevm"] or c["aufsd"]:
            raise MMError("Sold-to party %s is %s" % (kunnr, "flagged for deletion" if c["loevm"]
                                                      else "blocked for orders (%s)" % c["aufsd"]),
                          "V1", "058")
        area = area_of(conn, kunnr, data.get("vtweg"))
        if not area:
            raise MMError("Sold-to party %s is not defined for sales area 1000/%s (VD01)"
                          % (kunnr, data.get("vtweg") or "-"), "V1", "003")
        if t["reason"] and not data.get("augru") and auart not in ("FD",):
            raise MMError("Enter an order reason for %s" % t["text"], "V1", "014")
        augru = data.get("augru") or ("001" if auart == "FD" else "")
        if augru and augru not in ORDER_REASONS:
            raise MMError("Order reason %s does not exist" % augru, "V1", "015")
        kunwe = (data.get("kunwe") or "").upper() or kunnr
        if kunwe != kunnr and not conn.execute(
                "SELECT 1 FROM md_knvp WHERE kunnr=? AND parvw='WE' AND kunn2=?", (kunnr, kunwe)).fetchone():
            raise MMError("%s is not a ship-to party of %s (partner functions)" % (kunwe, kunnr),
                          "V1", "004")
        vdatu = parse_date(data.get("vdatu") or _wd(audat, PICK_DAYS + 2))
        if vdatu < audat:
            raise MMError("Requested delivery date is before the document date", "V1", "016")
        vbeln = str(next_number(conn, t["nr"]))
        items = data.get("items") or []
        if ref:
            items = ref["items"] if not items else items
        if not items:
            raise MMError("Enter at least one item", "V1", "005")
        conn.execute("INSERT INTO sd_vbak (vbeln,auart,vbtyp,vkorg,vtweg,spart,kunnr,kunwe,kunrg,bstnk,"
                     "audat,vdatu,prsdt,bnddt,zterm,inco1,inco2,kalsm,vgbel,vgtyp,augru,faksk,lifsk,"
                     "prob,kostl,ernam,erdat) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (vbeln, auart, t["vbtyp"], "1000", area["vtweg"], area["spart"], kunnr, kunwe,
                      kunnr, data.get("bstnk") or "", audat, vdatu, audat,
                      parse_date(data["bnddt"]) if data.get("bnddt") else
                      (_wd(audat, 22) if auart == "QT" else None),
                      area["zterm"] or c["zterm"], area["inco1"], area["inco2"],
                      "RVAA02" if area["kalks"] == "2" else "RVAA01", ref["vbeln"] if ref else None,
                      ref["vbtyp"] if ref else None, augru, t["faksk"], "",
                      int(data.get("prob") or (50 if auart == "QT" else 0)),
                      (data.get("kostl") or ("4500" if auart == "FD" else "")).upper() or None,
                      user, audat))
        msgs = []
        for n, it in enumerate(items, start=1):
            msgs += _add_item(conn, vbeln, n * 10, it, c, area, auart, t, audat, vdatu, ref)
        _totals(conn, vbeln)
        k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
        if t["credit"]:
            ok, why = credit_check(conn, kunnr, k["netwr"] + k["mwsbk"], audat, vbeln)
            conn.execute("UPDATE sd_vbak SET cmgst=?, credit_note=? WHERE vbeln=?",
                         ("A" if ok else "B", why, vbeln))
            if not ok:
                msgs.append("Credit block: " + why)
        if ref:
            for it in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=?", (vbeln,)).fetchall():
                if it["vgbel"]:
                    flow(conn, it["vgbel"], it["vgpos"], vbeln, it["posnr"], ref["vbtyp"], t["vbtyp"],
                         it["kwmeng"], it["netwr"])
            if auart in ("OR", "RO", "ZSP") and ref["vbtyp"] == "B":
                full = all(referenced(conn, ref["vbeln"], q["posnr"], ("OR", "RO", "ZSP"))[0] >= q["kwmeng"]
                           for q in conn.execute("SELECT posnr, kwmeng FROM sd_vbap WHERE vbeln=? AND "
                                                 "COALESCE(abgru,'')=''", (ref["vbeln"],)).fetchall())
                conn.execute("UPDATE sd_vbak SET gbstk=? WHERE vbeln=?", ("C" if full else "B",
                                                                        ref["vbeln"]))
        inc = incompletion(conn, vbeln)
        if inc:
            msgs.append("Document is incomplete: " + ", ".join(inc))
        result = {"vbeln": vbeln, "messages": msgs, "incomplete": inc}
        if auart == "RO" and not inc:           # rush order: delivery at once, same transaction
            k = conn.execute("SELECT cmgst FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
            if k["cmgst"] != "B":
                from .delivery import create as create_delivery
                try:
                    result["delivery"] = create_delivery(conn, vbeln, user, audat)["vbeln"]
                except MMError as e:
                    msgs.append("Delivery could not be created: %s" % e.msg)
    return result


def _reference(conn, auart, vgbel, audat):
    src = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vgbel,)).fetchone()
    if src:
        if src["auart"] not in COPY_CONTROL.get(auart, []):
            raise MMError("Copying from %s to %s is not allowed (VTAA)" % (src["auart"], auart),
                          "V1", "011")
        if src["auart"] == "QT" and src["bnddt"] and src["bnddt"] < audat:
            raise MMError("Quotation %s was valid until %s" % (vgbel, src["bnddt"]), "V1", "013")
        if src["auart"] == "QT" and src["gbstk"] == "C":
            raise MMError("Quotation %s is already completely referenced" % vgbel, "V1", "017")
        items = []
        for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND COALESCE(abgru,'')=''", (vgbel,)):
            open_q = p["kwmeng"] - (referenced(conn, vgbel, p["posnr"], ("OR", "RO", "ZSP"))[0]
                                    if src["auart"] == "QT" else 0)
            if open_q > 0:
                items.append(dict(matnr=p["matnr"], qty="%.3f" % (open_q / 1000.0), vgbel=vgbel,
                                  vgpos=p["posnr"], price="%.2f" % (p["netpr"] / 100.0)
                                  if src["auart"] == "QT" else None))
        return dict(vbeln=vgbel, vbtyp=src["vbtyp"], kunnr=src["kunnr"], items=items)
    b = conn.execute("SELECT * FROM billing WHERE vbeln=?", (vgbel,)).fetchone()
    if not b:
        raise MMError("Reference document %s does not exist" % vgbel, "V1", "010")
    if "M" not in COPY_CONTROL.get(auart, []):
        raise MMError("Copying from a billing document to %s is not allowed (VTAA)" % auart, "V1", "011")
    if b["cancelled"]:
        raise MMError("Billing document %s is cancelled" % vgbel, "V1", "018")
    items = [dict(matnr=i["matnr"], qty="%.3f" % (i["fkimg"] / 1000.0), vgbel=vgbel, vgpos=i["posnr"],
                  price="%.2f" % (rdiv(i["gross"] * 1000, i["fkimg"]) / 100.0) if i["fkimg"] else None,
                  werks=i["werks"], lgort=i["lgort"])
             for i in conn.execute("SELECT * FROM billing_item WHERE vbeln=? AND matnr IS NOT NULL",
                                   (vgbel,))]
    return dict(vbeln=vgbel, vbtyp="M", kunnr=b["kunnr"], items=items)


def _add_item(conn, vbeln, posnr, it, c, area, auart, t, audat, vdatu, ref):
    msgs = []
    matnr = (it.get("matnr") or "").upper()
    if not matnr and it.get("kdmat"):
        r = conn.execute("SELECT matnr FROM sd_custmat WHERE kunnr=? AND kdmat=?",
                         (c["kunnr"], it["kdmat"])).fetchone()
        if not r:
            raise MMError("Customer material %s is not known (VD51)" % it["kdmat"], "V1", "020")
        matnr = r["matnr"]
    m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        raise MMError("Item %d: material %s does not exist" % (posnr, matnr), "V1", "021")
    werks = it.get("werks") or "1000"
    from md import checks as mdc
    if auart not in ("RE", "CR", "DR"):
        mdc.material_for_sales(conn, matnr, "1000", area["vtweg"], werks)
    ex = conn.execute("SELECT 1 FROM sd_listing WHERE kunnr=? AND matnr=? AND kind='B' AND datab<=? "
                      "AND datbi>=?", (c["kunnr"], matnr, audat, audat)).fetchone()
    if ex:
        raise MMError("Material %s is excluded for customer %s (VB01 exclusion)" % (matnr, c["kunnr"]),
                      "V1", "022")
    qty = parse_qty(it.get("qty"))
    if ref and ref["vbtyp"] == "M" and it.get("vgbel") and it.get("vgpos"):
        _check_reference_limit(conn, auart, it["vgbel"], int(it["vgpos"]), qty, it.get("price"), posnr)
    pstyv = t["pstyv"]
    ic = ITEM_CATS[pstyv]
    price = None
    if it.get("price") not in (None, ""):
        price = parse_price(it["price"])
    pr = pricing.price_item(conn, c, area, matnr, qty, audat, werks, it.get("disc"), price,
                            free=not ic["pricing"], inco1=area["inco1"], vbtyp=t["vbtyp"])
    lgort = it.get("lgort") or _sloc(conn, matnr, werks)
    kd = conn.execute("SELECT kdmat FROM sd_custmat WHERE kunnr=? AND matnr=?", (c["kunnr"], matnr)).fetchone()
    conn.execute("INSERT INTO sd_vbap (vbeln,posnr,matnr,arktx,pstyv,kwmeng,vrkme,werks,lgort,netwr,netpr,"
                 "mwsbp,wavwr,kzwi1,kzwi2,freight,vgbel,vgpos,kdmat,equnr) VALUES "
                 "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (vbeln, posnr, matnr, m["maktx"], pstyv, qty, m["meins"], werks, lgort, pr["net"],
                  pr["netpr"], pr["tax"], pr["cost"], pr["gross"], pr["disc"], pr["freight"],
                  it.get("vgbel"), it.get("vgpos"), kd["kdmat"] if kd else None, it.get("equnr")))
    pricing.store(conn, vbeln, posnr, pr["conds"])
    if pr["net"] and pr["net"] < pr["cost"]:
        msgs.append("Item %d: net price below cost (margin %.2f)" % (posnr, (pr["net"] - pr["cost"]) / 100.0))
    # schedule lines
    if t["vbtyp"] == "C" and ic["delivery"]:
        mbdat = _wd(vdatu, -PICK_DAYS)
        today = audat
        if mbdat < today:
            mbdat = today
        conf, rest = atp(conn, matnr, werks, qty, mbdat, vbeln)
        e = 0
        if not conf:
            e += 1
            conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                         (vbeln, posnr, e, vdatu, qty, 0, mbdat, "CP"))
        for d, q in conf:
            e += 1
            conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                         (vbeln, posnr, e, max(vdatu, _wd(d, PICK_DAYS)), qty if e == 1 else 0, q, d, "CP"))
        if rest and conf:
            msgs.append("Item %d: only %.3f of %.3f confirmed on %s - rest %s" % (
                posnr, conf[0][1] / 1000.0, qty / 1000.0, vdatu,
                "on " + conf[-1][0] if len(conf) > 1 else "not confirmed (backorder)"))
        elif not conf:
            msgs.append("Item %d: no availability - not confirmed (backorder)" % posnr)
    elif t["vbtyp"] == "H":
        conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                     (vbeln, posnr, 1, vdatu, qty, qty, vdatu, "DN"))
    else:
        conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                     (vbeln, posnr, 1, vdatu, qty, 0, vdatu, "CN"))
    return msgs


def referenced(conn, vgbel, vgpos, auarts):
    """Quantity and net value of non-rejected items of open documents of the given
    types that reference item vgpos of document vgbel."""
    r = conn.execute("SELECT COALESCE(SUM(p.kwmeng),0), COALESCE(SUM(p.netwr),0) FROM sd_vbap p JOIN "
                     "sd_vbak k USING (vbeln) WHERE p.vgbel=? AND p.vgpos=? AND COALESCE(p.abgru,'')='' "
                     "AND k.auart IN (%s)" % ",".join("?" * len(auarts)),
                     [vgbel, vgpos] + list(auarts)).fetchone()
    return r[0], r[1]


def _check_reference_limit(conn, auart, vgbel, vgpos, qty, price, posnr):
    """Returns / credit memos may not exceed what was billed (minus what was already
    returned or credited with reference to the same billing item)."""
    bi = conn.execute("SELECT * FROM billing_item WHERE vbeln=? AND posnr=?", (vgbel, vgpos)).fetchone()
    if not bi:
        raise MMError("Item %d: billing item %s/%s does not exist" % (posnr, vgbel, vgpos), "V1", "024")
    ret_q, ret_v = referenced(conn, vgbel, vgpos, ("RE",))
    cr_q, cr_v = referenced(conn, vgbel, vgpos, ("CR",))
    if auart == "RE" and ret_q + qty > bi["fkimg"]:
        raise MMError("Item %d: quantity %.3f exceeds the billed quantity %.3f minus already returned "
                      "%.3f" % (posnr, qty / 1000.0, bi["fkimg"] / 1000.0, ret_q / 1000.0), "V1", "019")
    if auart == "CR":
        value = rdiv(parse_price(price) * qty, 1000) if price not in (None, "") else \
            rdiv(bi["net"] * qty, bi["fkimg"]) if bi["fkimg"] else 0
        net_item = bi["net"]
        returned_value = rdiv(net_item * ret_q, bi["fkimg"]) if bi["fkimg"] else 0
        if cr_v + value > net_item - returned_value:
            raise MMError("Item %d: credit %.2f exceeds the billed value %.2f minus returned %.2f and "
                          "already credited %.2f" % (posnr, value / 100.0, net_item / 100.0,
                                                     returned_value / 100.0, cr_v / 100.0), "V1", "023")


def _sloc(conn, matnr, werks):
    m = conn.execute("SELECT p.lgfsb, x.mtart FROM material_plant p JOIN material x USING (matnr) WHERE "
                     "p.matnr=? AND p.werks=?", (matnr, werks)).fetchone()
    if m and m["lgfsb"]:
        return m["lgfsb"]
    return "0003" if m and m["mtart"] == "FERT" else "0001"


def _totals(conn, vbeln):
    r = conn.execute("SELECT COALESCE(SUM(netwr+freight),0) n, COALESCE(SUM(mwsbp),0) t FROM sd_vbap "
                     "WHERE vbeln=? AND COALESCE(abgru,'')=''", (vbeln,)).fetchone()
    conn.execute("UPDATE sd_vbak SET netwr=?, mwsbk=? WHERE vbeln=?", (r["n"], r["t"], vbeln))


def flow(conn, vbelv, posnv, vbeln, posnn, tv, tn, qty, value):
    conn.execute("INSERT INTO sd_vbfa VALUES (?,?,?,?,?,?,?,?,?)",
                 (vbelv, posnv, vbeln, posnn, tv, tn, qty, value, now_ts()))


def incompletion(conn, vbeln):
    k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
    miss = []
    if k["vbtyp"] == "C" and k["auart"] in ("OR", "RO", "ZSP") and not k["bstnk"]:
        miss.append("Customer purchase order number")
    if DOC_TYPES[k["auart"]]["reason"] and not k["augru"]:
        miss.append("Order reason")
    for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=?", (vbeln,)):
        if ITEM_CATS[p["pstyv"]]["pricing"] and not p["netwr"] and not p["abgru"]:
            miss.append("Item %d: net value" % p["posnr"])
    return miss


# ====================================================================== VA02
def change(conn, vbeln, data, user):
    with transaction(conn):
        k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
        if not k:
            raise MMError("Sales document %s does not exist" % vbeln, "V1", "302")
        log = []
        for f in ("bstnk", "faksk", "lifsk", "augru", "vdatu", "prob"):
            if f in data and str(data[f]) != str(k[f] or ""):
                v = parse_date(data[f]) if f == "vdatu" else data[f]
                if f == "faksk" and k["faksk"] == "08" and v == "" and k["ernam"] == user:
                    raise MMError("Billing block 08 must be removed by a second person (approval)",
                                  "V1", "060")
                conn.execute("UPDATE sd_vbak SET %s=? WHERE vbeln=?" % f, (v, vbeln))
                log.append(("VBAK", vbeln, f, k[f], v))
        for it in data.get("items") or []:
            p = conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND posnr=?",
                             (vbeln, parse_int(it.get("posnr"), "item"))).fetchone()
            if not p:
                raise MMError("Item %s does not exist" % it["posnr"], "V1", "303")
            if it.get("abgru"):
                if it["abgru"] not in REJECTION_REASONS:
                    raise MMError("Reason for rejection %s does not exist" % it["abgru"], "V1", "304")
                dl = conn.execute("SELECT vbeln FROM sd_lips WHERE vgbel=? AND vgpos=? LIMIT 1",
                                  (vbeln, p["posnr"])).fetchone()
                if dl:
                    raise MMError("Item %d has delivery %s - delete or reduce the delivery first "
                                  "(VL02N)" % (p["posnr"], dl["vbeln"]), "V1", "306")
                conn.execute("UPDATE sd_vbap SET abgru=? WHERE vbeln=? AND posnr=?",
                             (it["abgru"], vbeln, p["posnr"]))
                conn.execute("UPDATE sd_vbep SET bmeng=0 WHERE vbeln=? AND posnr=?", (vbeln, p["posnr"]))
                log.append(("VBAP", "%s/%s" % (vbeln, p["posnr"]), "abgru", "", it["abgru"]))
                continue
            if it.get("delete"):
                if conn.execute("SELECT 1 FROM sd_lips WHERE vgbel=? AND vgpos=?", (vbeln, p["posnr"])).fetchone() \
                        or billed_qty(conn, vbeln, p["posnr"]):
                    raise MMError("Item %d has follow-on documents - reject it instead" % p["posnr"],
                                  "V1", "307")
                for t in ("sd_vbep", "sd_vbap"):
                    conn.execute("DELETE FROM %s WHERE vbeln=? AND posnr=?" % t, (vbeln, p["posnr"]))
                conn.execute("DELETE FROM sd_konv WHERE knumv=? AND kposn=?", (vbeln, p["posnr"]))
                log.append(("VBAP", "%s/%s" % (vbeln, p["posnr"]), "deleted", "", "X"))
                continue
            if any(it.get(f) not in (None, "") for f in ("qty", "price", "disc")):
                log += _change_item(conn, k, p, it, user)
        for n, it in enumerate(data.get("new_items") or [], start=1):     # add items
            nxt = (conn.execute("SELECT COALESCE(MAX(posnr),0) FROM sd_vbap WHERE vbeln=?",
                                (vbeln,)).fetchone()[0] // 10 + 1) * 10
            c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k["kunnr"],)).fetchone()
            area = area_of(conn, k["kunnr"], k["vtweg"])
            _add_item(conn, vbeln, nxt, it, c, area, k["auart"], DOC_TYPES[k["auart"]], k["audat"],
                      k["vdatu"], None)
            log.append(("VBAP", "%s/%s" % (vbeln, nxt), "created", "", it.get("matnr")))
        old_value = k["netwr"] + k["mwsbk"]
        _totals(conn, vbeln)
        k2 = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
        if "vdatu" in data or data.get("new_items") or any(i.get("qty") for i in data.get("items") or []):
            reschedule(conn, vbeln)
        elif data.get("reschedule"):
            reschedule(conn, vbeln)
        # higher value -> new credit check (SAP: credit check at order change)
        if DOC_TYPES[k["auart"]]["credit"] and k2["netwr"] + k2["mwsbk"] > old_value:
            ok, why = credit_check(conn, k["kunnr"], k2["netwr"] + k2["mwsbk"], now_ts()[:10], vbeln)
            if not ok:
                conn.execute("UPDATE sd_vbak SET cmgst='B', credit_note=? WHERE vbeln=?", (why, vbeln))
                log.append(("VBUK", vbeln, "cmgst", k["cmgst"], "B"))
        from md.changes import log as cdlog
        cdlog(conn, "VERKBELEG", vbeln, "VA02", user, log)
        _status(conn, vbeln)


def _change_item(conn, k, p, it, user):
    """VA02 item: quantity, manual price or discount -> new pricing, PIR consumption
    follows automatically (it is derived from the order quantity)."""
    log = []
    qty = parse_qty(it["qty"]) if it.get("qty") not in (None, "") else p["kwmeng"]
    done = conn.execute("SELECT COALESCE(SUM(lfimg),0) FROM sd_lips WHERE vgbel=? AND vgpos=?",
                        (k["vbeln"], p["posnr"])).fetchone()[0]
    if qty < done:
        raise MMError("Item %d: quantity cannot be below the delivered quantity %.3f"
                      % (p["posnr"], done / 1000.0), "V1", "308")
    if billed_qty(conn, k["vbeln"], p["posnr"]) and it.get("price") not in (None, ""):
        raise MMError("Item %d is already billed - price changes need a credit / debit memo"
                      % p["posnr"], "V1", "309")
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k["kunnr"],)).fetchone()
    area = area_of(conn, k["kunnr"], k["vtweg"])
    t = DOC_TYPES[k["auart"]]
    ic = ITEM_CATS[p["pstyv"]]
    price = parse_price(it["price"]) if it.get("price") not in (None, "") else None
    pr = pricing.price_item(conn, c, area, p["matnr"], qty, k["audat"], p["werks"],
                            it.get("disc") if it.get("disc") not in (None, "") else None, price,
                            free=not ic["pricing"], inco1=area["inco1"], vbtyp=t["vbtyp"])
    conn.execute("UPDATE sd_vbap SET kwmeng=?, netwr=?, netpr=?, mwsbp=?, wavwr=?, kzwi1=?, kzwi2=?, "
                 "freight=? WHERE vbeln=? AND posnr=?",
                 (qty, pr["net"], pr["netpr"], pr["tax"], pr["cost"], pr["gross"], pr["disc"],
                  pr["freight"], k["vbeln"], p["posnr"]))
    pricing.store(conn, k["vbeln"], p["posnr"], pr["conds"])
    key = "%s/%s" % (k["vbeln"], p["posnr"])
    if qty != p["kwmeng"]:
        log.append(("VBAP", key, "kwmeng", p["kwmeng"], qty))
    if pr["netpr"] != p["netpr"]:
        log.append(("VBAP", key, "netpr", p["netpr"], pr["netpr"]))
    return log


def reschedule(conn, vbeln, today=None):
    """V_V2: new availability check for open schedule lines."""
    k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
    if not k:
        raise MMError("Sales document %s does not exist" % vbeln, "V1", "302")
    today = today or k["audat"]
    for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND pstyv IN ('TAN','TANN') AND "
                          "COALESCE(abgru,'')=''", (vbeln,)).fetchall():
        open_q = p["kwmeng"] - delivered_qty(conn, vbeln, p["posnr"])
        if open_q <= 0:
            continue
        conn.execute("DELETE FROM sd_vbep WHERE vbeln=? AND posnr=?", (vbeln, p["posnr"]))
        mbdat = max(_wd(k["vdatu"], -PICK_DAYS), today)
        conf, rest = atp(conn, p["matnr"], p["werks"], open_q, mbdat, vbeln)
        e = 0
        done = p["kwmeng"] - open_q
        if done:
            e += 1
            conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                         (vbeln, p["posnr"], e, k["vdatu"], done, done, mbdat, "CP"))
        if not conf:
            e += 1
            conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                         (vbeln, p["posnr"], e, k["vdatu"], open_q, 0, mbdat, "CP"))
        for d, q in conf:
            e += 1
            conn.execute("INSERT INTO sd_vbep VALUES (?,?,?,?,?,?,?,?)",
                         (vbeln, p["posnr"], e, max(k["vdatu"], _wd(d, PICK_DAYS)),
                          open_q if e == 1 + (1 if done else 0) else 0, q, d, "CP"))


def release_credit(conn, vbeln, user):
    """VKM1 / VKM3: release a credit-blocked document (not by its creator)."""
    with transaction(conn):
        k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
        if not k:
            raise MMError("Document %s does not exist" % vbeln, "V1", "302")
        if k["cmgst"] != "B":
            from .credit import open_value
            ok, _ = credit_check(conn, k["kunnr"], open_value(conn, vbeln), now_ts()[:10], vbeln)
            if ok or k["cmgst"] not in ("A", "D"):
                raise MMError("Document %s is not blocked for credit" % vbeln, "V1", "070")
        if k["ernam"] == user:
            raise MMError("Credit release must be done by the credit manager, not by %s" % user,
                          "V1", "071")
        conn.execute("UPDATE sd_vbak SET cmgst='D', cmfre=?, credit_note=? WHERE vbeln=?",
                     (now_ts()[:10], "Released by %s on %s" % (user, now_ts()[:10]), vbeln))
        from md.changes import log as cdlog
        cdlog(conn, "VERKBELEG", vbeln, "VKM1", user, [("VBUK", vbeln, "cmgst", "B", "D")])


# ====================================================================== status
def delivered_qty(conn, vbeln, posnr):
    return conn.execute("SELECT COALESCE(SUM(l.lfimg),0) FROM sd_lips l JOIN sd_likp h USING (vbeln) "
                        "WHERE l.vgbel=? AND l.vgpos=? AND h.wbstk='C'", (vbeln, posnr)).fetchone()[0]


def billed_qty(conn, vbeln, posnr):
    return conn.execute("SELECT COALESCE(SUM(i.fkimg),0) FROM billing_item i JOIN billing b USING (vbeln) "
                        "WHERE i.aubel=? AND i.aupos=? AND b.cancelled=0 AND b.fkart NOT IN ('S1')",
                        (vbeln, posnr)).fetchone()[0]


def _status(conn, vbeln):
    k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (vbeln,)).fetchone()
    if k["vbtyp"] in ("A", "B"):
        return
    done = True
    for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=?", (vbeln,)):
        if p["abgru"]:
            continue
        ic = ITEM_CATS[p["pstyv"]]
        if ic["delivery"] and delivered_qty(conn, vbeln, p["posnr"]) < p["kwmeng"]:
            done = False
        if ic["billing"] and DOC_TYPES[k["auart"]]["fkart"] and \
                billed_qty(conn, vbeln, p["posnr"]) < p["kwmeng"]:
            done = False
    conn.execute("UPDATE sd_vbak SET gbstk=? WHERE vbeln=?", ("C" if done else "B", vbeln))


def detail(conn, vbeln):
    k = conn.execute("SELECT k.*, c.name FROM sd_vbak k JOIN customer c USING (kunnr) WHERE vbeln=?",
                     (vbeln,)).fetchone()
    if not k:
        raise MMError("Sales document %s does not exist" % vbeln, "V1", "302")
    d = dict(k)
    d["type_text"] = DOC_TYPES[k["auart"]]["text"]
    d["items"] = rows(conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? ORDER BY posnr", (vbeln,)))
    for p in d["items"]:
        p["delivered"] = delivered_qty(conn, vbeln, p["posnr"])
        p["billed"] = billed_qty(conn, vbeln, p["posnr"])
        p["confirmed"] = conn.execute("SELECT COALESCE(SUM(bmeng),0) FROM sd_vbep WHERE vbeln=? AND "
                                      "posnr=?", (vbeln, p["posnr"])).fetchone()[0]
        p["margin"] = p["netwr"] - p["wavwr"] if p["netwr"] else 0
        p["schedule"] = rows(conn.execute("SELECT * FROM sd_vbep WHERE vbeln=? AND posnr=? ORDER BY etenr",
                                          (vbeln, p["posnr"])))
        p["conditions"] = pricing.item_conditions(conn, vbeln, p["posnr"])
    d["flow"] = docflow(conn, vbeln)
    d["incomplete"] = incompletion(conn, vbeln)
    d["exposure"] = exposure(conn, k["kunnr"])
    c = conn.execute("SELECT klimk FROM customer WHERE kunnr=?", (k["kunnr"],)).fetchone()
    d["klimk"] = c["klimk"]
    d["reason_text"] = ORDER_REASONS.get(k["augru"] or "", "")
    return d


def docflow(conn, vbeln):
    """All predecessors and successors (document flow, VA03 -> environment)."""
    seen, out = set(), []

    def walk(v, depth):
        if v in seen or depth > 6:
            return
        seen.add(v)
        for r in conn.execute("SELECT DISTINCT vbelv, vbeln, vbtyp_v, vbtyp_n FROM sd_vbfa WHERE vbelv=? "
                              "OR vbeln=?", (v, v)).fetchall():
            for doc, typ in ((r["vbelv"], r["vbtyp_v"]), (r["vbeln"], r["vbtyp_n"])):
                if doc not in [o["doc"] for o in out]:
                    out.append(dict(doc=doc, vbtyp=typ, text=VBTYP.get(typ, typ)))
                walk(doc, depth + 1)
    walk(vbeln, 0)
    if not out:
        out.append(dict(doc=vbeln, vbtyp="", text="Document"))
    order = "ABCHKLJTMOPNS"
    for o in out:
        o["info"] = _doc_info(conn, o["doc"], o["vbtyp"])
    return sorted(out, key=lambda o: (order.index(o["vbtyp"]) if o["vbtyp"] in order else 99, o["doc"]))


def _doc_info(conn, doc, typ):
    if typ in ("J", "T"):
        r = conn.execute("SELECT wbstk, wadat_ist, mblnr FROM sd_likp WHERE vbeln=?", (doc,)).fetchone()
        return ("GI posted %s, mat. doc %s" % (r["wadat_ist"], r["mblnr"])) if r and r["wbstk"] == "C" \
            else "Goods issue open"
    if typ in ("M", "O", "P", "N", "S"):
        r = conn.execute("SELECT netwr, belnr, cancelled FROM billing WHERE vbeln=?", (doc,)).fetchone()
        return ("%.2f EGP, FI doc %s%s" % (r["netwr"] / 100.0, r["belnr"], " (cancelled)" if r["cancelled"]
                                           else "")) if r else ""
    r = conn.execute("SELECT netwr, gbstk, cmgst FROM sd_vbak WHERE vbeln=?", (doc,)).fetchone()
    return ("%.2f EGP, %s" % (r["netwr"] / 100.0, {"A": "open", "B": "in process", "C": "completed"}
                              .get(r["gbstk"], ""))) if r else ""


def va05(conn, auart="", kunnr="", matnr="", d1="", d2="", open_only=False):
    sql = ("SELECT k.*, c.name FROM sd_vbak k JOIN customer c USING (kunnr) WHERE 1=1")
    args = []
    for col, v in (("k.auart", auart), ("k.kunnr", kunnr)):
        if v:
            sql += " AND %s=?" % col
            args.append(v.upper())
    if matnr:
        sql += " AND k.vbeln IN (SELECT vbeln FROM sd_vbap WHERE matnr=?)"
        args.append(matnr.upper())
    if d1:
        sql += " AND k.audat>=?"
        args.append(d1)
    if d2:
        sql += " AND k.audat<=?"
        args.append(d2)
    if open_only:
        sql += " AND k.gbstk<>'C'"
    out = rows(conn.execute(sql + " ORDER BY k.vbeln DESC", args))
    for r in out:
        r["type_text"] = DOC_TYPES[r["auart"]]["text"]
        r["blocked"] = " ".join(x for x in (("CREDIT" if r["cmgst"] == "B" else ""),
                                            ("BILL:" + r["faksk"]) if r["faksk"] else "",
                                            ("DLV:" + r["lifsk"]) if r["lifsk"] else "") if x)
    return out


def backorders(conn):
    """V.15: order items whose confirmed quantity is below the order quantity."""
    out = []
    for p in conn.execute("SELECT p.*, k.kunnr, k.vdatu, k.audat, c.name FROM sd_vbap p JOIN sd_vbak k "
                          "USING (vbeln) JOIN customer c ON c.kunnr=k.kunnr WHERE k.vbtyp='C' AND "
                          "p.pstyv IN ('TAN','TANN') AND COALESCE(p.abgru,'')=''"):
        conf = conn.execute("SELECT COALESCE(SUM(bmeng),0), MAX(edatu) FROM sd_vbep WHERE vbeln=? AND "
                            "posnr=?", (p["vbeln"], p["posnr"])).fetchone()
        first = conn.execute("SELECT COALESCE(SUM(bmeng),0) FROM sd_vbep WHERE vbeln=? AND posnr=? AND "
                             "edatu<=?", (p["vbeln"], p["posnr"], p["vdatu"])).fetchone()[0]
        dl = delivered_qty(conn, p["vbeln"], p["posnr"])
        if dl >= p["kwmeng"]:
            continue
        if conf[0] < p["kwmeng"] or first < p["kwmeng"]:
            d = dict(p)
            d.update(confirmed=conf[0], on_time=first, last_date=conf[1], delivered=dl,
                     missing=p["kwmeng"] - conf[0])
            out.append(d)
    return out


def blocked(conn):
    """VKM1 + documents with delivery / billing block."""
    out = rows(conn.execute("SELECT k.*, c.name, c.klimk FROM sd_vbak k JOIN customer c USING (kunnr) WHERE "
                            "(k.cmgst='B' OR COALESCE(k.faksk,'')<>'' OR COALESCE(k.lifsk,'')<>'') AND "
                            "k.gbstk<>'C' ORDER BY k.vbeln"))
    for r in out:
        r["exposure"] = exposure(conn, r["kunnr"])["total"]
    return out


def incomplete_docs(conn):
    out = []
    for k in conn.execute("SELECT k.vbeln, k.auart, k.kunnr, c.name, k.audat FROM sd_vbak k JOIN customer c "
                          "USING (kunnr) WHERE k.gbstk<>'C'"):
        miss = incompletion(conn, k["vbeln"])
        if miss:
            out.append(dict(k, missing=", ".join(miss)))
    return out
