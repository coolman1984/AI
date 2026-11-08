"""Billing.

VF04   billing due list (deliveries with goods issue, order-related items)
VF01   create: F2 invoice (from delivery), RE credit for returns (from returns
       delivery), G2 credit memo / L2 debit memo (from the request, after the
       billing block is removed), ZSRV service invoice (DP90)
       FI: customer (gross) / revenue per VKOA (customer AAG x material AAG) /
       deductions 880000 / freight 805000 / output VAT
       CO-PA record type F: revenue, deductions, cost of sales from the real
       goods issue value (VPRS) split into cost components
VF11   cancellation (S1): FI document mirrored, CO-PA reversed, the delivery
       becomes billable again
VF31   invoice output (form) + e-invoice for the Egyptian Tax Authority (ETA)
VF05   list of billing documents
"""
import datetime
import hashlib
import json

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, rdiv

from .config import (BILLING_TYPES, DOC_TYPES, REVENUE_ACCOUNTS, DEDUCTION_ACCOUNT, FREIGHT_ACCOUNT,
                     SERVICE_ACCOUNT, ITEM_CATS)
from .order import flow, _status

COMPANY_TAX_ID = "204-114-007"
COMPANY_NAME = "MM Core Egypt S.A.E."


def due_list(conn, until=None):
    out = []
    for h in conn.execute("SELECT h.*, k.auart, c.name FROM sd_likp h JOIN sd_vbak k ON k.vbeln=h.vgbel JOIN "
                          "customer c ON c.kunnr=h.kunag WHERE h.wbstk='C' AND h.fkstk<>'C' AND "
                          "k.auart NOT IN ('FD','ZWR')"):
        if until and h["wadat_ist"] > until:
            continue
        val = conn.execute("SELECT COALESCE(SUM(p.netwr*l.lfimg/p.kwmeng),0) FROM sd_lips l JOIN sd_vbap p ON "
                           "p.vbeln=l.vgbel AND p.posnr=l.vgpos WHERE l.vbeln=?", (h["vbeln"],)).fetchone()[0]
        out.append(dict(ref=h["vbeln"], kind="delivery", fkart="RE" if h["lfart"] == "LR" else "F2",
                        kunnr=h["kunag"], name=h["name"], date=h["wadat_ist"], value=int(val), order=h["vgbel"]))
    for k in conn.execute("SELECT k.*, c.name FROM sd_vbak k JOIN customer c USING (kunnr) WHERE k.auart IN "
                          "('CR','DR') AND k.gbstk<>'C'"):
        out.append(dict(ref=k["vbeln"], kind="order", fkart=DOC_TYPES[k["auart"]]["fkart"], kunnr=k["kunnr"],
                        name=k["name"], date=k["audat"], value=k["netwr"], order=k["vbeln"],
                        blocked=k["faksk"]))
    return out


def create(conn, ref, user, fkdat=None):
    """VF01 with reference to a delivery or a credit / debit memo request."""
    fkdat = parse_date(fkdat)
    with transaction(conn):
        h = conn.execute("SELECT * FROM sd_likp WHERE vbeln=?", (ref,)).fetchone()
        if h:
            k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (h["vgbel"],)).fetchone()
            if h["wbstk"] != "C":
                raise MMError("Delivery %s: goods issue not posted - not relevant for billing" % ref,
                              "VF", "016")
            if h["fkstk"] == "C":
                raise MMError("Delivery %s is already billed" % ref, "VF", "017")
            fkart = "RE" if h["lfart"] == "LR" else "F2"
            if not DOC_TYPES[k["auart"]]["fkart"]:
                raise MMError("%s %s is free of charge - not relevant for billing" % (
                    DOC_TYPES[k["auart"]]["text"], k["vbeln"]), "VF", "018")
            src = []
            for l in conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (ref,)).fetchall():
                p = conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND posnr=?", (l["vgbel"], l["vgpos"])).fetchone()
                if not ITEM_CATS[p["pstyv"]]["billing"]:
                    continue
                src.append((p, l["lfimg"], l["cogs"], l["posnr"]))
        else:
            k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (ref,)).fetchone()
            if not k:
                raise MMError("Document %s does not exist" % ref, "VF", "001")
            fkart = DOC_TYPES[k["auart"]]["fkart"]
            if DOC_TYPES[k["auart"]]["lfart"] or not fkart:
                raise MMError("%s is billed with reference to its delivery" % ref, "VF", "019")
            if k["faksk"]:
                raise MMError("%s has billing block %s - remove it with VA02 (approval)" % (ref, k["faksk"]),
                              "VF", "020")
            if k["cmgst"] == "B":
                raise MMError("%s is blocked for credit (VKM1)" % ref, "VF", "021")
            from .order import billed_qty
            src = [(p, p["kwmeng"] - billed_qty(conn, ref, p["posnr"]), 0, None)
                   for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND COALESCE(abgru,'')=''",
                                         (ref,)).fetchall()]
            src = [s for s in src if s[1] > 0]
        if not src:
            raise MMError("Nothing to bill for %s" % ref, "VF", "022")
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k["kunrg"] or k["kunnr"],)).fetchone()
        if c["faksd"]:
            raise MMError("Payer %s has billing block %s (XD05)" % (c["kunnr"], c["faksd"]), "VF", "039")
        items = []
        for p, q, cogs, lpos in src:
            f = q / p["kwmeng"] if p["kwmeng"] else 0
            items.append(dict(matnr=p["matnr"], werks=p["werks"], lgort=p["lgort"], qty=q, arktx=p["arktx"],
                              gross=round(p["kzwi1"] * f), disc=round(p["kzwi2"] * f),
                              freight=round(p["freight"] * f), cogs=cogs, pstyv=p["pstyv"],
                              aubel=p["vbeln"], aupos=p["posnr"], vgbel=ref, vgpos=lpos or p["posnr"],
                              mwskz="A1" if p["mwsbp"] else "A0"))
        r = post(conn, fkart, k, c, items, fkdat, user, ref)
        if h:
            conn.execute("UPDATE sd_likp SET fkstk='C' WHERE vbeln=?", (ref,))
        _status(conn, k["vbeln"])
    return r


def post(conn, fkart, k, c, items, fkdat, user, ref, service_order=None):
    """Billing document + FI + CO-PA. items: matnr, qty, gross, disc, freight, cogs, mwskz, ..."""
    bt = BILLING_TYPES[fkart]
    s = bt["sign"]
    from co.core import period_of
    gjahr, perio = period_of(fkdat)
    vbeln = str(next_number(conn, "BILL"))
    area = conn.execute("SELECT * FROM md_knvv WHERE kunnr=? AND vtweg=?", (k["kunnr"], k["vtweg"])).fetchone()
    ktgrd = (area["ktgrd"] if area else "01") or "01"
    from fi.ap import _tax_lines
    acc = []
    tax_base = {}
    for n, it in enumerate(items, start=1):
        it["posnr"] = n * 10
        mv = conn.execute("SELECT ktgrm FROM md_mvke WHERE matnr=? AND vtweg=?", (it.get("matnr"), k["vtweg"])
                          ).fetchone() if it.get("matnr") else None
        ktgrm = it.get("ktgrm") or (mv["ktgrm"] if mv else "01") or "01"
        rev = SERVICE_ACCOUNT if fkart == "ZSRV" else REVENUE_ACCOUNTS.get((ktgrd, ktgrm), "800000")
        pa = "%s/%s" % (vbeln, it["posnr"])
        base = dict(matnr=it.get("matnr"), werks=it.get("werks") or "1000", menge=it["qty"],
                    zeile=it["posnr"], paobj=pa, mwskz=it["mwskz"])
        acc.append(dict(base, ktosl="ERL", hkont=rev, amount=-s * it["gross"]))
        if it["disc"]:
            acc.append(dict(base, ktosl="ERS", hkont=DEDUCTION_ACCOUNT, amount=s * it["disc"]))
        if it["freight"]:
            acc.append(dict(base, ktosl="ERF", hkont=FREIGHT_ACCOUNT, amount=-s * it["freight"]))
        net = it["gross"] - it["disc"] + it["freight"]
        tax_base[it["mwskz"]] = tax_base.get(it["mwskz"], 0) + net
        it["net"] = net
        it["tax"] = rdiv(net * (1400 if it["mwskz"] == "A1" else 0), 10000)
    for a in acc:
        a["wrbtr"] = a["amount"]
    acc += _tax_lines(tax_base, 100000, -s)
    total = -sum(a["amount"] for a in acc)
    acc.append(dict(kunnr=c["kunnr"], koart="D", amount=total, wrbtr=total, zfbdt=fkdat,
                    zterm=k["zterm"], sgtxt="%s %s" % (bt["text"], vbeln)))
    from fi.document import write
    belnr = write(conn, "RV", fkdat, user, "VF%s" % vbeln, "%s %s" % (bt["text"], vbeln), acc,
                  xblnr=vbeln, tcode="VF01")
    # CO-PA
    from co.copa import _cost_values
    from co.period_end import _copa_post
    copa = []
    for it in items:
        vals = {"vv010": s * (it["gross"] + it["freight"]), "vv020": s * it["disc"]}
        if bt["cost"] and it.get("matnr") and it.get("cogs") is not None:
            cv = _cost_values(conn, it["matnr"], it["werks"] or "1000", it["qty"], it["cogs"])
            for kk, v in cv.items():
                vals[kk] = vals.get(kk, 0) + s * v
        m = conn.execute("SELECT matkl FROM material WHERE matnr=?", (it.get("matnr"),)).fetchone() \
            if it.get("matnr") else None
        copa.append(_copa_post(conn, "F", 0, gjahr, perio, dict(
            kunnr=c["kunnr"], matnr=it.get("matnr"), matkl=m["matkl"] if m else None, region=c["region"],
            kdgrp=c["kdgrp"], vtweg=k["vtweg"], werks=it.get("werks") or "1000"), vals, refdoc=vbeln,
            user=user, qty=s * it["qty"], budat=fkdat, aufnr=service_order))
    netwr = sum(it["net"] for it in items)
    mwsbk = abs(total) - netwr
    conn.execute("INSERT INTO billing (vbeln,fkdat,kunnr,netwr,usnam,belnr,copa,cancelled,fkart,vbtyp,vgbel,"
                 "kunrg,zterm,mwsbk,waerk,rfbsk,vkorg,vtweg,aubel) VALUES "
                 "(?,?,?,?,?,?,?,0,?,?,?,?,?,?,'EGP','C','1000',?,?)",
                 (vbeln, fkdat, k["kunnr"], s * netwr, user, belnr, ",".join(copa), fkart, bt["vbtyp"],
                  ref, c["kunnr"], k["zterm"], mwsbk, k["vtweg"], k["vbeln"]))
    for it in items:
        conn.execute("INSERT INTO billing_item (vbeln,posnr,matnr,werks,lgort,fkimg,price,disc_pct,gross,disc,"
                     "net,cogs,vgbel,vgpos,aubel,aupos,pstyv,mwsbp,freight,arktx) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (vbeln, it["posnr"], it.get("matnr"), it.get("werks") or "1000", it.get("lgort"), it["qty"],
                      rdiv(it["gross"] * 1000, it["qty"]) if it["qty"] else 0,
                      rdiv(it["disc"] * 10000, it["gross"]) if it["gross"] else 0, it["gross"], it["disc"],
                      it["net"], it.get("cogs") or 0, it.get("vgbel"), it.get("vgpos"), it.get("aubel"),
                      it.get("aupos"), it.get("pstyv"), it["tax"], it["freight"], it.get("arktx")))
        if it.get("aubel"):
            flow(conn, it["vgbel"], it["vgpos"], vbeln, it["posnr"],
                 "J" if it["vgbel"] != it.get("aubel") else k["vbtyp"], bt["vbtyp"], it["qty"], it["net"])
    return {"vbeln": vbeln, "belnr": belnr, "netwr": s * netwr, "tax": mwsbk, "fkart": fkart,
            "message": "%s %s saved - accounting document %s" % (bt["text"], vbeln, belnr)}


def cancel(conn, vbeln, user, budat=None):
    """VF11: cancellation document S1, FI reversed, CO-PA reversed."""
    budat = parse_date(budat)
    with transaction(conn):
        b = conn.execute("SELECT * FROM billing WHERE vbeln=?", (vbeln,)).fetchone()
        if not b:
            raise MMError("Billing document %s does not exist" % vbeln, "VF", "001")
        if b["cancelled"]:
            raise MMError("Billing document %s is already cancelled" % vbeln, "VF", "045")
        cleared = conn.execute("SELECT 1 FROM acc_doc_item WHERE belnr=? AND koart='D' AND augbl IS NOT NULL",
                               (b["belnr"],)).fetchone()
        if cleared:
            raise MMError("Billing document %s is already paid (cleared) - reset clearing first" % vbeln,
                          "VF", "046")
        new = str(next_number(conn, "BILL"))
        lines = []
        from fi.document import signed, write
        for i in conn.execute("SELECT * FROM acc_doc_item i JOIN acc_doc h USING (belnr, gjahr) WHERE "
                              "i.belnr=? ORDER BY buzei", (b["belnr"],)).fetchall():
            lines.append(dict(hkont=i["hkont"], amount=-signed(i), wrbtr=-signed(i), koart=i["koart"],
                              kunnr=i["kunnr"], mwskz=i["mwskz"], txbase=i["txbase"], paobj=i["paobj"],
                              matnr=i["matnr"], werks=i["werks"], zfbdt=budat, zterm=i["zterm"],
                              ktosl=i["ktosl"], sgtxt="Cancellation %s" % vbeln))
        belnr = write(conn, "RV", budat, user, "VF%s" % new, "Cancellation of %s" % vbeln, lines,
                      xblnr=new, tcode="VF11")
        from co.core import period_of
        gjahr, perio = period_of(budat)
        from co.config import VV_KEYS
        copa = []
        for r in conn.execute("SELECT * FROM copa_item WHERE refdoc=? AND vrgar='F'", (vbeln,)).fetchall():
            from co.period_end import _copa_post
            copa.append(_copa_post(conn, "F", 0, gjahr, perio, dict(
                kunnr=r["kunnr"], matnr=r["matnr"], matkl=r["matkl"], region=r["region"], kdgrp=r["kdgrp"],
                vtweg=r["vtweg"], werks=r["werks"]), {k: -(r[k] or 0) for k in VV_KEYS if r[k]},
                refdoc=new, user=user, qty=-r["qty"], budat=budat))
        # clear the two open items against each other
        inv = conn.execute("SELECT buzei FROM acc_doc_item WHERE belnr=? AND koart='D'", (b["belnr"],)).fetchone()
        can = conn.execute("SELECT buzei, gjahr FROM acc_doc_item WHERE belnr=? AND koart='D'", (belnr,)).fetchone()
        if inv and can:
            conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND koart='D'",
                         (belnr, budat, b["belnr"]))
            conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND koart='D'",
                         (belnr, budat, belnr))
        conn.execute("INSERT INTO billing (vbeln,fkdat,kunnr,netwr,usnam,belnr,copa,cancelled,fkart,vbtyp,vgbel,"
                     "kunrg,zterm,mwsbk,sfakn,vtweg,aubel) VALUES (?,?,?,?,?,?,?,1,'S1','N',?,?,?,?,?,?,?)",
                     (new, budat, b["kunnr"], -b["netwr"], user, belnr, ",".join(copa), b["vgbel"], b["kunrg"],
                      b["zterm"], b["mwsbk"], vbeln, b["vtweg"], b["aubel"]))
        conn.execute("UPDATE billing SET cancelled=1, sfakn=? WHERE vbeln=?", (new, vbeln))
        conn.execute("UPDATE sd_likp SET fkstk='A' WHERE vbeln=?", (b["vgbel"],))
        flow(conn, vbeln, 0, new, 0, b["vbtyp"] or "M", "N", 0, -b["netwr"])
        if b["aubel"]:
            _status(conn, b["aubel"])
    return {"vbeln": new, "belnr": belnr, "message": "Cancellation document %s saved (FI %s)" % (new, belnr)}


# ====================================================================== output
def document(conn, vbeln):
    b = conn.execute("SELECT b.*, c.name, c.street, c.city, c.land, c.stcd1, c.stceg FROM billing b JOIN customer c "
                     "ON c.kunnr=b.kunnr WHERE b.vbeln=?", (vbeln,)).fetchone()
    if not b:
        raise MMError("Billing document %s does not exist" % vbeln, "VF", "001")
    d = dict(b)
    d["items"] = rows(conn.execute("SELECT i.*, m.maktx, m.meins FROM billing_item i LEFT JOIN material m "
                                   "USING (matnr) WHERE i.vbeln=? ORDER BY posnr", (vbeln,)))
    d["type_text"] = BILLING_TYPES.get(d["fkart"] or "F2", {}).get("text", "Invoice")
    ai = conn.execute("SELECT netdt, augbl FROM acc_doc_item WHERE belnr=? AND koart='D'", (d["belnr"],)).fetchone()
    d["netdt"], d["paid"] = (ai["netdt"], bool(ai["augbl"])) if ai else (None, False)
    d["einv"] = conn.execute("SELECT * FROM sd_einv WHERE vbeln=?", (vbeln,)).fetchone()
    d["einv"] = dict(d["einv"]) if d["einv"] else None
    d["flow"] = rows(conn.execute("SELECT * FROM sd_vbfa WHERE vbeln=? OR vbelv=?", (vbeln, vbeln)))
    d["company"] = dict(name=COMPANY_NAME, tax=COMPANY_TAX_ID, city="Cairo")
    return d


def _ser(name, v):
    if isinstance(v, dict):
        return "".join('"%s"%s' % (k.upper(), _ser(k, x)) if not isinstance(x, list) else _ser(k, x)
                       for k, x in v.items())
    if isinstance(v, list):
        return "".join('"%s"%s' % (name.upper(), _ser(name, x)) for x in v)
    return '"%s"' % v


def einvoice(conn, vbeln, user=""):
    """Egyptian Tax Authority e-invoice v1.0 document; UUID = SHA-256 of the
    ETA serialization. Offline: the document is built and validated, not sent."""
    d = document(conn, vbeln)
    if d["fkart"] == "S1":
        raise MMError("Cancellation documents are reported as credit notes", "EI", "001")
    errors = []
    rtype = "B" if d["land"] == "EG" else "F"
    rid = (d["stcd1"] or d["stceg"] or "").replace("-", "")
    if rtype == "B" and not rid:
        errors.append("Receiver tax registration number missing (XD02 tax number 1)")
    lines = []
    for i in d["items"]:
        q = i["fkimg"] / 1000.0
        sales = i["gross"] / 100.0
        disc = i["disc"] / 100.0
        net = (i["gross"] - i["disc"] + (i["freight"] or 0)) / 100.0
        tax = (i["mwsbp"] or 0) / 100.0
        lines.append({"description": i["arktx"] or i["maktx"] or "Service",
                      "itemType": "EGS", "itemCode": "EG-%s-%s" % (COMPANY_TAX_ID.replace("-", ""),
                                                                    i["matnr"] or "SRV"),
                      "unitType": "KGM" if (i["meins"] or "") == "KG" else "EA",
                      "quantity": "%.3f" % q, "internalCode": i["matnr"] or "SRV",
                      "salesTotal": "%.2f" % sales, "total": "%.2f" % (net + tax),
                      "valueDifference": "0.00", "totalTaxableFees": "0.00", "netTotal": "%.2f" % net,
                      "itemsDiscount": "0.00",
                      "unitValue": {"currencySold": "EGP", "amountEGP": "%.5f" % (sales / q if q else 0)},
                      "discount": {"rate": "%.2f" % (disc / sales * 100 if sales else 0), "amount": "%.2f" % disc},
                      "taxableItems": [{"taxType": "T1", "amount": "%.2f" % tax, "subType": "V009",
                                        "rate": "14" if tax else "0"}]})
    total = sum(float(l["total"]) for l in lines)
    doc = {"issuer": {"type": "B", "id": COMPANY_TAX_ID.replace("-", ""), "name": COMPANY_NAME,
                      "address": {"branchID": "0", "country": "EG", "governate": "Cairo",
                                  "regionCity": "Cairo", "street": "Industrial Zone", "buildingNumber": "1"}},
           "receiver": {"type": rtype, "id": rid, "name": d["name"],
                        "address": {"country": d["land"] or "EG", "regionCity": d["city"] or "",
                                    "street": d["street"] or ""}},
           "documentType": {"F2": "I", "L2": "D", "ZSRV": "I"}.get(d["fkart"], "C"),
           "documentTypeVersion": "1.0",
           "dateTimeIssued": "%sT10:00:00Z" % d["fkdat"], "taxpayerActivityCode": "3100",
           "internalID": vbeln, "invoiceLines": lines,
           "totalSalesAmount": "%.2f" % sum(float(l["salesTotal"]) for l in lines),
           "totalDiscountAmount": "%.2f" % sum(float(l["discount"]["amount"]) for l in lines),
           "netAmount": "%.2f" % sum(float(l["netTotal"]) for l in lines),
           "taxTotals": [{"taxType": "T1", "amount": "%.2f" % sum(float(l["taxableItems"][0]["amount"])
                                                                for l in lines)}],
           "totalAmount": "%.2f" % total, "extraDiscountAmount": "0.00", "totalItemsDiscountAmount": "0.00"}
    uuid = hashlib.sha256(_ser("document", doc).encode("utf-8")).hexdigest()
    status = "Invalid" if errors else "Valid (offline - ready to submit)"
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO sd_einv VALUES (?,?,?,?,?)",
                     (vbeln, uuid, json.dumps(doc, ensure_ascii=False, indent=1), status, now_ts()))
        conn.execute("UPDATE billing SET eta_uuid=?, eta_status=? WHERE vbeln=?", (uuid, status, vbeln))
    return {"vbeln": vbeln, "uuid": uuid, "status": status, "errors": errors, "document": doc}


def vf05(conn, d1="", d2="", kunnr="", fkart=""):
    sql = "SELECT b.*, c.name FROM billing b JOIN customer c ON c.kunnr=b.kunnr WHERE 1=1"
    args = []
    for col, v in (("b.kunnr", kunnr.upper()), ("b.fkart", fkart)):
        if v:
            sql += " AND %s=?" % col
            args.append(v)
    if d1:
        sql += " AND b.fkdat>=?"
        args.append(d1)
    if d2:
        sql += " AND b.fkdat<=?"
        args.append(d2)
    out = rows(conn.execute(sql + " ORDER BY b.vbeln DESC", args))
    for r in out:
        r["fkart"] = r["fkart"] or "F2"
        r["type_text"] = BILLING_TYPES.get(r["fkart"], {}).get("text", "")
        r["gross"] = r["netwr"] + (r["mwsbk"] or 0) * (1 if r["netwr"] >= 0 else -1)
    return out


def _today():
    return datetime.date.today().isoformat()
