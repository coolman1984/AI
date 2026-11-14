"""Import purchasing (5-x): import file with letter of credit (LC) and landed cost.

ZIMP01  import file for a purchase order from a foreign vendor: LC number, bank, LC amount,
        cash cover (margin) %, port, ETA, bill of lading
ZLC01   open the LC: the margin goes from the bank account to "LC margin deposits"
            Dr 116000 LC margin   / Cr 113100 bank
ZIMP_COST  costs of the shipment (customs duty, sea freight, insurance, clearing agent,
        bank charges, ...), paid from the bank or owed to a service provider (vendor):
            Dr 193500 import costs clearing / Cr 113100 bank  (or Cr vendor)
ZIMP_LAND  landed cost: after the goods receipt, the collected costs are added to the
        stock value of the received materials, in proportion to their PO value
        (moving average price: to stock as far as the quantity is still in stock, the
        rest to price differences; cost center items: to the expense account)
            Dr 300100 stock / 231500 price differences / Cr 193500
ZLC_REL  release the margin when the LC is settled:  Dr 113100 bank / Cr 116000
ZIMP03  import files with LC, costs, landed costs and landed cost % of the goods value
"""
from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_pct, rdiv, value_of

LC_MARGIN, IMP_CLEARING, BANK, PRD = "116000", "193500", "113100", "231500"
COST_TYPES = {"CUSTOMS": "Customs duty", "FREIGHT": "Sea / air freight", "INSURANCE": "Marine insurance",
              "CLEARING": "Clearing agent & port charges", "BANK": "LC bank charges & commission",
              "INLAND": "Inland transport", "OTHER": "Other import costs"}
STATUS = {"OPEN": "Open - LC not opened", "LC": "LC opened", "LANDED": "Costs landed", "CLOSED": "Closed"}


def _get(conn, impno):
    r = conn.execute("SELECT * FROM imp_file WHERE impno=?", (str(impno),)).fetchone()
    if not r:
        raise MMError("Import file %s does not exist" % impno, "ZIM", "901")
    return r


def create(conn, data, user):
    ebeln = (data.get("ebeln") or "").strip()
    with transaction(conn):
        h = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
        if not h:
            raise MMError("Purchase order %s does not exist" % ebeln, "ZIM", "902")
        if conn.execute("SELECT 1 FROM imp_file WHERE ebeln=?", (ebeln,)).fetchone():
            raise MMError("Purchase order %s already has an import file" % ebeln, "ZIM", "903")
        po_value = sum(value_of(i["menge"], i["netpr"], i["peinh"]) for i in conn.execute(
            "SELECT * FROM po_item WHERE ebeln=? AND COALESCE(loekz,0)=0", (ebeln,)))
        lc_amount = parse_amount(data["lc_amount"]) if data.get("lc_amount") not in (None, "") else po_value
        pct = parse_pct(data.get("margin_pct") or "0")
        if pct < 0 or pct > 10000:
            raise MMError("Cash cover must be between 0 and 100 %", "ZIM", "904")
        impno = str(next_number(conn, "IMPORT"))
        conn.execute("INSERT INTO imp_file (impno,ebeln,lifnr,waers,lcno,lcbank,lc_amount,margin_pct,port,eta,"
                     "bl_no,status,text,usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (impno, ebeln, h["lifnr"], h["waers"] or "EGP", (data.get("lcno") or "").strip(),
                      (data.get("lcbank") or "").strip().upper(), lc_amount, pct, (data.get("port") or "").strip(),
                      parse_date(data["eta"]) if data.get("eta") else None, (data.get("bl_no") or "").strip(),
                      "OPEN", (data.get("text") or "")[:80], user, now_ts()))
    return {"impno": impno, "message": "Import file %s created for purchase order %s" % (impno, ebeln)}


def open_lc(conn, impno, data, user):
    """ZLC01: LC opened at the bank - the cash cover is blocked on the margin account"""
    from fi import gl
    from fi.document import rate, to_local
    with transaction(conn):
        f = _get(conn, impno)
        if f["status"] != "OPEN":
            raise MMError("The LC of import file %s is already opened" % impno, "ZIM", "905")
        lcno = (data.get("lcno") or f["lcno"] or "").strip()
        if not lcno:
            raise MMError("Enter the LC number of the bank", "ZIM", "906")
        budat = parse_date(data.get("budat"))
        cover = rdiv(f["lc_amount"] * f["margin_pct"], 10000)
        margin = cover if f["waers"] == "EGP" else to_local(cover, rate(conn, f["waers"], budat))
        belnr = None
        if margin:
            m = "%.2f" % (margin / 100.0)
            txt = "LC %s margin" % lcno
            belnr = gl.general_posting(conn, {"budat": budat, "bktxt": txt[:25], "xblnr": lcno[:16]}, [
                {"bschl": "40", "account": LC_MARGIN, "amount": m, "sgtxt": txt},
                {"bschl": "50", "account": BANK, "amount": m, "sgtxt": txt}], user)
        conn.execute("UPDATE imp_file SET status='LC', lcno=?, margin=?, margin_belnr=? WHERE impno=?",
                     (lcno, margin, belnr, f["impno"]))
    return {"belnr": belnr, "margin": margin,
            "message": "LC %s opened - margin %.2f EGP blocked at the bank" % (lcno, margin / 100.0)}


def add_cost(conn, impno, data, user):
    """ZIMP_COST: a cost of the shipment, paid from the bank or owed to a service provider"""
    from fi import gl
    typ = (data.get("typ") or "").upper()
    if typ not in COST_TYPES:
        raise MMError("Cost type %s does not exist" % typ, "ZIM", "907")
    amount = parse_amount(data.get("amount"))
    budat = parse_date(data.get("budat"))
    lifnr = (data.get("lifnr") or "").strip().upper()
    with transaction(conn):
        f = _get(conn, impno)
        if f["status"] == "CLOSED":
            raise MMError("Import file %s is closed" % impno, "ZIM", "908")
        if lifnr and not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
            raise MMError("Vendor %s does not exist" % lifnr, "ZIM", "909")
        txt = ("%s - import %s" % (COST_TYPES[typ], f["impno"]))[:50]
        m = "%.2f" % (amount / 100.0)
        credit = {"bschl": "31", "account": lifnr, "amount": m, "sgtxt": txt} if lifnr else \
            {"bschl": "50", "account": BANK, "amount": m, "sgtxt": txt}
        belnr = gl.general_posting(conn, {"budat": budat, "blart": "KR" if lifnr else "SA", "bktxt": txt[:25],
                                          "xblnr": (data.get("xblnr") or f["impno"])[:16]}, [
            {"bschl": "40", "account": IMP_CLEARING, "amount": m, "sgtxt": txt}, credit], user)
        cid = conn.execute("INSERT INTO imp_cost (impno,typ,amount,budat,lifnr,belnr,gjahr,text,usnam,ts) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?)", (f["impno"], typ, amount, budat, lifnr or None, belnr,
                                                            int(budat[:4]), (data.get("text") or "")[:80], user,
                                                            now_ts())).lastrowid
    return {"id": cid, "belnr": belnr,
            "message": "%s %.2f posted to import file %s (document %s)" % (COST_TYPES[typ], amount / 100.0,
                                                                          f["impno"], belnr)}


def _received_items(conn, ebeln):
    """received PO items with the local (EGP) value of their goods receipts"""
    out = []
    for r in conn.execute("SELECT i.*, m.bklas FROM po_item i LEFT JOIN material m ON m.matnr=i.matnr "
                          "WHERE i.ebeln=? AND i.wemng>0 ORDER BY i.ebelp", (ebeln,)):
        d = dict(r)
        d["gr_value"] = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) FROM mat_doc_item "
            "WHERE ebeln=? AND ebelp=? AND bwart IN ('101','102','122','123')", (ebeln, r["ebelp"])).fetchone()[0]
        out.append(d)
    return out


def land(conn, impno, data, user, test=False):
    """ZIMP_LAND: distribute the costs not yet landed to the received PO items"""
    from fi.ap import _diff_to_stock
    from fi.document import write
    from mm.config import gl_for
    budat = parse_date((data or {}).get("budat"))
    with transaction(conn):
        f = _get(conn, impno)
        costs = conn.execute("SELECT * FROM imp_cost WHERE impno=? AND land_belnr IS NULL",
                             (f["impno"],)).fetchall()
        total = sum(c["amount"] for c in costs)
        if not total:
            raise MMError("Import file %s has no costs to land" % impno, "ZIM", "910")
        items = _received_items(conn, f["ebeln"])
        if not items:
            raise MMError("Post the goods receipt of purchase order %s first (MIGO)" % f["ebeln"], "ZIM", "911")
        base = [max(i["gr_value"], 0) for i in items]
        shares, rest = [], total
        for n, b in enumerate(base):
            s = rest if n == len(base) - 1 else (rdiv(total * b, sum(base)) if sum(base) else rdiv(total, len(base)))
            shares.append(s)
            rest -= s
        out, acc = [], []
        for i, s in zip(items, shares):
            row = dict(ebelp=i["ebelp"], matnr=i["matnr"] or "", text=i["txz01"] or "", qty=i["wemng"],
                       goods=i["gr_value"], share=s, to_stock=0, to_prd=0)
            if i["knttp"]:
                acc.append(dict(hkont=i["sakto"] or "400000", amount=s, kostl=i["kostl"], aufnr=i["aufnr"],
                                ebeln=f["ebeln"], ebelp=i["ebelp"], sgtxt="Landed cost import %s" % f["impno"]))
                row["to_prd"] = s
            else:
                st, _ = _diff_to_stock(conn, i, i["wemng"], s, budat, "ZIMP_LAND", test)
                row["to_stock"], row["to_prd"] = st, s - st
                if st:
                    acc.append(dict(hkont=gl_for("BSX", i["bklas"]), amount=st, ktosl="BSX", matnr=i["matnr"],
                                    werks=i["werks"], ebeln=f["ebeln"], ebelp=i["ebelp"],
                                    sgtxt="Landed cost import %s" % f["impno"]))
                if s - st:
                    acc.append(dict(hkont=PRD, amount=s - st, ktosl="PRD", matnr=i["matnr"], werks=i["werks"],
                                    ebeln=f["ebeln"], ebelp=i["ebelp"], sgtxt="Landed cost (not in stock)"))
            row["pct"] = round(s * 100.0 / row["goods"], 2) if row["goods"] else None
            out.append(row)
        res = {"impno": f["impno"], "total": total, "items": out, "test": test}
        if test:
            res["message"] = "Test run: %.2f EGP would be added to %d item(s)" % (total / 100.0, len(out))
            return res
        acc.append(dict(hkont=IMP_CLEARING, amount=-total, ebeln=f["ebeln"],
                        sgtxt="Import costs landed - file %s" % f["impno"]))
        belnr = write(conn, "WE", budat, user, "ZIMP-%s" % f["impno"], "Landed cost %s" % f["impno"], acc,
                      xblnr=f["impno"], tcode="ZIMP_LAND")
        conn.execute("UPDATE imp_cost SET land_belnr=? WHERE impno=? AND land_belnr IS NULL", (belnr, f["impno"]))
        conn.execute("UPDATE imp_file SET status='LANDED' WHERE impno=? AND status IN ('OPEN','LC')", (f["impno"],))
    res["belnr"] = belnr
    res["message"] = "Landed cost %.2f EGP added to the stock value (document %s)" % (total / 100.0, belnr)
    return res


def release_margin(conn, impno, data, user):
    """ZLC_REL: LC settled - the margin comes back from the margin account; the file is closed"""
    from fi import gl
    budat = parse_date((data or {}).get("budat"))
    with transaction(conn):
        f = _get(conn, impno)
        if f["status"] in ("OPEN", "CLOSED"):
            raise MMError("Import file %s: no opened LC to settle" % impno, "ZIM", "912")
        if conn.execute("SELECT 1 FROM imp_cost WHERE impno=? AND land_belnr IS NULL", (f["impno"],)).fetchone():
            raise MMError("Land the remaining costs of import file %s first (ZIMP_LAND)" % impno, "ZIM", "913")
        belnr = None
        if f["margin"]:
            m = "%.2f" % (f["margin"] / 100.0)
            txt = "LC %s settled" % f["lcno"]
            belnr = gl.general_posting(conn, {"budat": budat, "bktxt": txt[:25], "xblnr": (f["lcno"] or "")[:16]}, [
                {"bschl": "40", "account": BANK, "amount": m, "sgtxt": txt},
                {"bschl": "50", "account": LC_MARGIN, "amount": m, "sgtxt": txt}], user)
        conn.execute("UPDATE imp_file SET status='CLOSED', release_belnr=? WHERE impno=?", (belnr, f["impno"]))
    return {"belnr": belnr, "message": "Import file %s closed - margin %.2f EGP released" % (
        f["impno"], f["margin"] / 100.0)}


def files(conn, status=None):
    sql, a = ("SELECT f.*, v.name FROM imp_file f LEFT JOIN vendor v ON v.lifnr=f.lifnr", [])
    if status:
        sql += " WHERE f.status=?"
        a.append(status)
    out = []
    for r in conn.execute(sql + " ORDER BY f.impno DESC", a):
        d = dict(r)
        c = conn.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(CASE WHEN land_belnr IS NOT NULL "
                         "THEN amount ELSE 0 END),0) FROM imp_cost WHERE impno=?", (r["impno"],)).fetchone()
        d["costs"], d["landed"] = c[0], c[1]
        goods = sum(i["gr_value"] for i in _received_items(conn, r["ebeln"]))
        d["goods_received"] = goods
        d["landed_pct"] = round(c[1] * 100.0 / goods, 2) if goods else None
        d["status_text"] = STATUS[r["status"]]
        out.append(d)
    return out


def costs(conn, impno):
    _get(conn, impno)
    out = []
    for r in conn.execute("SELECT c.*, v.name FROM imp_cost c LEFT JOIN vendor v ON v.lifnr=c.lifnr "
                          "WHERE impno=? ORDER BY id", (str(impno),)):
        d = dict(r)
        d["typ_text"] = COST_TYPES.get(r["typ"], r["typ"])
        out.append(d)
    return out
