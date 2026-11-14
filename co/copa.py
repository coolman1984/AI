"""Profitability analysis (costing-based CO-PA, operating concern EG01).

VF01  billing: goods issue 601 (COGS at standard), FI revenue posting and a
      CO-PA line item. Cost of sales is valued with the released standard
      cost estimate and split into cost components (material, labor fixed /
      variable, machine, overheads) -> value fields, like SAP's material cost
      estimate valuation (KE40).
KE11  sales and profit planning: quantity, price and discount per customer /
      product / period; valued with the cost estimate as well.
"""
from mm.db import next_number, transaction
from mm.posting import _write_acc_doc, post_goods_movement
from mm.util import (MMError, now_ts, parse_amount, parse_date, parse_qty, rdiv,
                     value_of)

from .config import CCOMP_TO_VV
from .core import period_of
from .costing import component_split
from .period_end import _copa_post
from mm.util import parse_year, parse_period  # noqa: E402


def _pct(text):
    if text in (None, ""):
        return 0
    v = float(str(text).replace(",", "."))
    if not 0 <= v < 100:
        raise MMError("Discount must be between 0 and 100 %", "V1", "010")
    return int(round(v * 100))


def _cost_values(conn, matnr, werks, qty, cogs=None):
    """Value fields for the cost of sales of qty (milli) of a product. If the
    real COGS of the goods issue is known, the split is adjusted to it so
    CO-PA always agrees with FI to the cent."""
    comp = component_split(conn, matnr, werks, qty)
    vals = {}
    if comp:
        for c, (var, fix) in comp.items():
            fv, ff = CCOMP_TO_VV[c]
            vals[fv] = vals.get(fv, 0) + var
            vals[ff] = vals.get(ff, 0) + fix
    if cogs is not None:
        diff = cogs - sum(vals.values())
        vals["vv030"] = vals.get("vv030", 0) + diff
    return vals


def create_billing(conn, data, user):
    """data: kunnr, fkdat, items: [{matnr, qty, price, disc, werks, lgort, lgpla}]"""
    fkdat = parse_date(data.get("fkdat"))
    gjahr, perio = period_of(fkdat)
    items = data.get("items") or []
    if not items:
        raise MMError("Enter at least one item", "VF", "001")
    with transaction(conn):
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?",
                         ((data.get("kunnr") or "").upper(),)).fetchone()
        if not c:
            raise MMError("Customer %s does not exist" % data.get("kunnr"), "VF", "002")
        from md import checks as mdc
        mdc.customer_for_billing(conn, c)
        vbeln = str(next_number(conn, "BILL"))
        prepared = []
        for n, it in enumerate(items, start=1):
            matnr = (it.get("matnr") or "").upper()
            m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
            if not m:
                raise MMError("Item %d: material %s does not exist" % (n, matnr))
            mdc.material_for_sales(conn, matnr, "1000", c["vtweg"] or "10",
                                   it.get("werks") or "1000")
            qty = parse_qty(it.get("qty"))
            price = parse_amount(it.get("price"))
            disc_bp = _pct(it.get("disc"))
            gross = value_of(qty, price, 1)
            disc = rdiv(gross * disc_bp, 10000)
            prepared.append(dict(posnr=n * 10, matnr=matnr, m=m, qty=qty, price=price,
                                 disc_bp=disc_bp, gross=gross, disc=disc,
                                 net=gross - disc, werks=it.get("werks") or "1000",
                                 lgort=it.get("lgort") or "0003",
                                 lgpla=it.get("lgpla") or ""))
        # 0. credit check (FD32) before anything is delivered
        from fi.ar import check_credit as _cc
        net_total = sum(p["net"] for p in prepared)
        _cc(conn, c["kunnr"], net_total + (0 if c["vtweg"] == "20" else
                                           rdiv(net_total * 1400, 10000)), with_overdue=False)
        # 1. goods issue for delivery (movement type 601) -> COGS
        gi = post_goods_movement(conn, {"budat": fkdat, "xblnr": vbeln,
                                        "bktxt": "Delivery %s" % c["name"][:14]},
                                 [{"bwart": "601", "matnr": p["matnr"],
                                   "werks": p["werks"], "lgort": p["lgort"],
                                   "lgpla": p["lgpla"], "qty": str(p["qty"] / 1000.0)}
                                  for p in prepared], user, tcode="VL02N")
        for p, line in zip(prepared, conn.execute(
                "SELECT salk FROM mat_doc_item WHERE mblnr=? AND mjahr=? ORDER BY zeile",
                (gi["mblnr"], gi["mjahr"])).fetchall()):
            p["cogs"] = line["salk"]
        # 2. revenue posting in FI with profitability segment, output VAT and
        #    the customer open item (payment terms from the customer master)
        rev_acct = "800100" if c["vtweg"] == "20" else "800000"
        mwskz = "A0" if c["vtweg"] == "20" else "A1"
        from fi.ap import _tax_lines
        acc = []
        for p in prepared:
            pa = "%s/%s" % (vbeln, p["posnr"])
            acc.append(dict(ktosl="ERL", hkont=rev_acct, amount=-p["gross"],
                            matnr=p["matnr"], werks=p["werks"], menge=p["qty"],
                            zeile=p["posnr"], paobj=pa, mwskz=mwskz))
            if p["disc"]:
                acc.append(dict(ktosl="ERS", hkont="880000", amount=p["disc"],
                                matnr=p["matnr"], werks=p["werks"], menge=p["qty"],
                                zeile=p["posnr"], paobj=pa, mwskz=mwskz))
        for a in acc:
            a["wrbtr"] = a["amount"]
        acc += _tax_lines({mwskz: sum(p["net"] for p in prepared)}, 100000, -1)
        total = -sum(a["amount"] for a in acc)
        acc.append(dict(kunnr=c["kunnr"], koart="D", amount=total, wrbtr=total,
                        zfbdt=fkdat, sgtxt="Billing %s" % vbeln))
        belnr = _write_acc_doc(conn, "RV", fkdat, user, "VF%s" % vbeln,
                               "Billing %s" % vbeln, acc, xblnr=vbeln, tcode="VF01")
        # 3. CO-PA line items (record type F)
        copa = []
        for p in prepared:
            vals = {"vv010": p["gross"], "vv020": p["disc"]}
            vals.update(_cost_values(conn, p["matnr"], p["werks"], p["qty"], p["cogs"]))
            copa.append(_copa_post(conn, "F", 0, gjahr, perio, dict(
                kunnr=c["kunnr"], matnr=p["matnr"], matkl=p["m"]["matkl"],
                region=c["region"], kdgrp=c["kdgrp"], vtweg=c["vtweg"],
                werks=p["werks"]), vals, refdoc=vbeln, user=user, qty=p["qty"],
                budat=fkdat))
        conn.execute("INSERT INTO billing (vbeln,fkdat,kunnr,netwr,usnam,mblnr,mjahr,"
                     "belnr,copa) VALUES (?,?,?,?,?,?,?,?,?)",
                     (vbeln, fkdat, c["kunnr"], sum(p["net"] for p in prepared), user,
                      gi["mblnr"], gi["mjahr"], belnr, ",".join(copa)))
        for p in prepared:
            conn.execute("INSERT INTO billing_item (vbeln,posnr,matnr,werks,lgort,fkimg,price,disc_pct,"
                         "gross,disc,net,cogs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (vbeln, p["posnr"], p["matnr"], p["werks"], p["lgort"],
                          p["qty"], p["price"], p["disc_bp"], p["gross"], p["disc"],
                          p["net"], p["cogs"]))
    return {"vbeln": vbeln, "mblnr": gi["mblnr"], "belnr": belnr, "gjahr": gjahr,
            "message": "Billing document %s saved (goods issue %s, accounting doc. %s)"
                       % (vbeln, gi["mblnr"], belnr)}


def plan_sales(conn, gjahr, perio, kunnr, matnr, qty, price, disc="0", werks="1000",
               user=""):
    """KE11: plan one customer / product / period and value it."""
    gjahr, perio = parse_year(gjahr), parse_period(perio)
    q = parse_qty(qty, allow_zero=True)
    pr = parse_amount(price, allow_zero=True)
    bp = _pct(disc)
    with transaction(conn):
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
        m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
        if not c or not m:
            raise MMError("Customer or product does not exist", "KE", "001")
        conn.execute("INSERT OR REPLACE INTO copa_plan_qty VALUES (?,?,?,?,?,?,?)",
                     (gjahr, perio, kunnr, matnr, q, pr, bp))
        conn.execute("DELETE FROM copa_item WHERE plikz=1 AND vrgar='0' AND gjahr=? AND "
                     "perio=? AND kunnr=? AND matnr=?", (gjahr, perio, kunnr, matnr))
        if q:
            gross = value_of(q, pr, 1)
            vals = {"vv010": gross, "vv020": rdiv(gross * bp, 10000)}
            v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                             (matnr, werks)).fetchone()
            std = value_of(q, v["stprs"] if v["vprsv"] == "S" else v["verpr"],
                           v["peinh"]) if v else 0
            vals.update(_cost_values(conn, matnr, werks, q, std))
            _copa_post(conn, "0", 1, gjahr, perio, dict(
                kunnr=kunnr, matnr=matnr, matkl=m["matkl"], region=c["region"],
                kdgrp=c["kdgrp"], vtweg=c["vtweg"], werks=werks), vals,
                refdoc="KE11", user=user, qty=q)
    return True


def revalue_plan(conn, gjahr, perio, user=""):
    """Re-value all KE11 plan lines (after a new standard cost estimate)."""
    for r in conn.execute("SELECT * FROM copa_plan_qty WHERE gjahr=? AND perio=?",
                          (gjahr, perio)).fetchall():
        plan_sales(conn, gjahr, perio, r["kunnr"], r["matnr"], str(r["qty"] / 1000.0),
                   "%.2f" % (r["price"] / 100.0), str(r["disc_pct"] / 100.0),
                   user=user)


def manual_line(conn, data, user):
    """KE21N (3-1 sales adjustment): a manual CO-PA line item, e.g. a year-end rebate, a
    price correction or a quality claim for a customer / product. Amounts are entered
    positive for the value field (revenue vv010, deductions vv020, costs vv030 ...).
    The line is a CO-PA posting only (record type B) - it is not in FI and shows up as
    an explained difference in the reconciliation (ZCO_RECON)."""
    from .config import VV_KEYS
    budat = parse_date(data.get("budat"))
    gjahr, perio = period_of(budat)
    kunnr = (data.get("kunnr") or "").strip().upper()
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
    if not c:
        raise MMError("Customer %s does not exist" % kunnr, "KE", "102")
    matnr = (data.get("matnr") or "").strip().upper() or None
    m = None
    if matnr:
        m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
        if not m:
            raise MMError("Material %s does not exist" % matnr, "KE", "103")
    vals = {}
    for k in VV_KEYS:
        if str(data.get(k) or "").strip():
            v = parse_amount(str(data[k]).lstrip("-"), allow_zero=True)
            vals[k] = -v if str(data[k]).strip().startswith("-") else v
    if not any(vals.values()):
        raise MMError("Enter at least one amount (value field)", "KE", "104")
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Enter the reason of the adjustment (text)", "KE", "105")
    from .closing import check as period_check
    period_check(conn, gjahr, perio)
    with transaction(conn):
        return _copa_post(conn, "B", 0, gjahr, perio, dict(
            kunnr=kunnr, matnr=matnr, matkl=m["matkl"] if m else None, region=c["region"], kdgrp=c["kdgrp"],
            vtweg=c["vtweg"], werks=data.get("werks") or "1000"), vals, refdoc=text[:30], user=user,
            budat=budat)
