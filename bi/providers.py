"""Info providers: each returns facts (one dict per record) with characteristics
and key figures, read straight from the operational tables - no copy, always
up to date. Amounts in cents, quantities in milli, like the rest of MM Core."""
import datetime

from mm import util as mmclock

AMT, QTY, NUM, PCT = "amt", "qty", "num", "pct"


def _ym(d):
    return (d or "")[:7]


def _age_bucket(days):
    for lim, txt in ((30, "0-30"), (60, "31-60"), (90, "61-90"), (180, "91-180"), (365, "181-365")):
        if days <= lim:
            return txt
    return ">365"


def _texts(conn, sql):
    return {r[0]: r[1] for r in conn.execute(sql)}


# ------------------------------------------------------------------ CO-PA / P&L
def copa(conn):
    cust = _texts(conn, "SELECT kunnr, name FROM customer")
    mat = _texts(conn, "SELECT matnr, maktx FROM material")
    from co.config import CHANNELS, CUSTOMER_GROUPS, REGIONS
    out = []
    for r in conn.execute("SELECT * FROM copa_item"):
        f = dict(version="PLAN" if r["plikz"] else "ACT", gjahr=r["gjahr"], perio=r["perio"],
                 month="%04d-%02d" % (r["gjahr"], r["perio"]), kunnr=r["kunnr"] or "#",
                 customer=cust.get(r["kunnr"], "Not assigned"), matnr=r["matnr"] or "#",
                 material=mat.get(r["matnr"], "Not assigned"), matkl=r["matkl"] or "#",
                 region=REGIONS.get(r["region"], r["region"] or "#"),
                 kdgrp=CUSTOMER_GROUPS.get(r["kdgrp"], r["kdgrp"] or "#"),
                 vtweg=CHANNELS.get(r["vtweg"], r["vtweg"] or "#"), werks=r["werks"] or "#",
                 qty=r["qty"] if r["vrgar"] in ("F", "0") else 0)
        for k in ("vv010", "vv020", "vv030", "vv040", "vv050", "vv051", "vv060", "vv061", "vv070",
                  "vv080", "vv090", "vv100", "vv110"):
            f[k] = r[k]
        out.append(f)
    return out


# ------------------------------------------------------------------ sales
def sales(conn):
    from co.config import CHANNELS, CUSTOMER_GROUPS, REGIONS
    out = []
    for r in conn.execute(
            "SELECT b.fkdat, b.vbeln, COALESCE(b.fkart,'F2') AS fkart, c.kunnr, c.name, c.region, c.kdgrp, "
            "c.vtweg, m.matnr, m.maktx, m.matkl, i.fkimg, i.gross, i.disc, i.net, i.cogs, i.werks "
            "FROM billing_item i JOIN billing b USING (vbeln) LEFT JOIN customer c ON c.kunnr=COALESCE(b.kunrg,b.kunnr) "
            "LEFT JOIN material m ON m.matnr=i.matnr WHERE b.cancelled=0"):
        sign = -1 if r["fkart"] in ("G2", "RE", "S1") else 1
        net, cogs = sign * (r["net"] or 0), sign * (r["cogs"] or 0)
        out.append(dict(version="ACT", month=_ym(r["fkdat"]), kunnr=r["kunnr"], customer=r["name"],
                        region=REGIONS.get(r["region"], r["region"]), kdgrp=CUSTOMER_GROUPS.get(r["kdgrp"], r["kdgrp"]),
                        vtweg=CHANNELS.get(r["vtweg"], r["vtweg"]), matnr=r["matnr"], material=r["maktx"],
                        matkl=r["matkl"], werks=r["werks"], fkart=r["fkart"],
                        doc_type="Credit memo / return" if sign < 0 else "Invoice",
                        qty=sign * (r["fkimg"] or 0), gross=sign * (r["gross"] or 0), disc=sign * (r["disc"] or 0),
                        net=net, cogs=cogs, margin=net - cogs, docs=1))
    return out


def orders(conn):
    out = []
    for r in conn.execute(
            "SELECT k.vbeln, k.auart, k.audat, k.cmgst, k.gbstk, c.name, k.kunnr, p.matnr, p.arktx, p.kwmeng, p.netwr, "
            "p.abgru, (SELECT COALESCE(SUM(l.lfimg),0) FROM sd_lips l JOIN sd_likp h USING (vbeln) WHERE l.vgbel=p.vbeln "
            "AND l.vgpos=p.posnr AND h.wbstk='C') AS dlv FROM sd_vbap p JOIN sd_vbak k USING (vbeln) "
            "LEFT JOIN customer c USING (kunnr) WHERE k.vbtyp='C'"):
        open_q = 0 if r["abgru"] else max((r["kwmeng"] or 0) - (r["dlv"] or 0), 0)
        open_v = (r["netwr"] or 0) * open_q // r["kwmeng"] if r["kwmeng"] else 0
        out.append(dict(version="ACT", month=_ym(r["audat"]), auart=r["auart"], kunnr=r["kunnr"], customer=r["name"],
                        matnr=r["matnr"], material=r["arktx"],
                        status={"A": "Open", "B": "Partly processed", "C": "Completed"}.get(r["gbstk"], r["gbstk"]),
                        credit="Blocked" if r["cmgst"] == "B" else "Released",
                        rejected="Rejected" if r["abgru"] else "Active",
                        qty=r["kwmeng"] or 0, order_value=r["netwr"] or 0, open_qty=open_q, backlog=open_v, docs=1))
    return out


# ------------------------------------------------------------------ overhead (cost centers)
def overhead(conn):
    cc = _texts(conn, "SELECT kostl, name FROM cost_center")
    ce = _texts(conn, "SELECT kstar, ktext FROM cost_element")
    out = []
    for r in conn.execute("SELECT gjahr, perio, wrttp, objnr, kstar, SUM(wtg) AS wtg FROM co_item WHERE "
                          "objnr LIKE 'KS%' AND wrttp IN ('01','04') GROUP BY 1,2,3,4,5"):
        k = r["objnr"][2:]
        out.append(dict(version="PLAN" if r["wrttp"] == "01" else "ACT", gjahr=r["gjahr"], perio=r["perio"],
                        month="%04d-%02d" % (r["gjahr"], r["perio"]), kostl=k, cost_center="%s %s" % (k, cc.get(k, "")),
                        kstar=r["kstar"], cost_element="%s %s" % (r["kstar"], ce.get(r["kstar"], "")),
                        category="Primary" if (r["kstar"] or "").startswith(("4", "6", "7")) else "Secondary",
                        amount=r["wtg"] or 0))
    return out


# ------------------------------------------------------------------ inventory
def inventory(conn):
    today = mmclock.today()
    val = {(r["matnr"], r["bwkey"]): r for r in conn.execute("SELECT * FROM valuation")}
    out = []
    for r in conn.execute("SELECT q.*, m.maktx, m.matkl, m.mtart, m.meins FROM quant q JOIN material m USING (matnr) "
                          "WHERE q.qty>0"):
        v = val.get((r["matnr"], r["werks"]))
        value = (v["salk3"] * r["qty"] // v["lbkum"]) if v and v["lbkum"] else 0
        days = (today - datetime.date.fromisoformat(r["wdatu"][:10])).days if r["wdatu"] else 0
        out.append(dict(version="ACT", werks=r["werks"], lgort=r["lgort"], lgpla=r["lgpla"] or "#", matnr=r["matnr"],
                        material=r["maktx"], matkl=r["matkl"], mtart=r["mtart"],
                        stock_type={"U": "Unrestricted", "Q": "Quality inspection", "B": "Blocked"}.get(r["insmk"], r["insmk"]),
                        aging=_age_bucket(days), gr_month=_ym(r["wdatu"]), qty=r["qty"], value=value,
                        days=days, value_days=value * days))
    return out


def inventory_monthly(conn):
    """Stock at each month end (MB5B logic) for the last 6 months."""
    from mm.periods import stock_at
    t = mmclock.today()
    mat = {r["matnr"]: r for r in conn.execute("SELECT matnr, maktx, matkl, mtart FROM material")}
    out = []
    y, m = t.year, t.month
    for _ in range(6):
        nm = datetime.date(y + (m == 12), m % 12 + 1, 1)
        end = min(nm - datetime.timedelta(days=1), t)
        for w in [r[0] for r in conn.execute("SELECT werks FROM plant")]:
            for s in stock_at(conn, w, end.isoformat()):
                mm = mat.get(s["matnr"], {})
                out.append(dict(version="ACT", month="%04d-%02d" % (y, m), werks=w, matnr=s["matnr"],
                                material=s["maktx"], matkl=mm["matkl"] if mm else "", mtart=mm["mtart"] if mm else "",
                                qty=s["qty"], value=s["value"]))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


# ------------------------------------------------------------------ receivables / payables
def open_items(conn):
    today = mmclock.today().isoformat()
    out = []
    for r in conn.execute(
            "SELECT i.*, h.budat, h.xblnr, COALESCE(c.name, v.name) AS pname, c.klimk FROM acc_doc_item i JOIN acc_doc h "
            "ON h.belnr=i.belnr AND h.gjahr=i.gjahr LEFT JOIN customer c ON c.kunnr=i.kunnr LEFT JOIN vendor v ON "
            "v.lifnr=i.lifnr WHERE i.koart IN ('D','K') AND i.augbl IS NULL"):
        amt = r["dmbtr"] if r["shkzg"] == "S" else -r["dmbtr"]
        due = r["netdt"] or r["zfbdt"] or r["budat"]
        od = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(due[:10])).days if due else 0
        bucket = "Not due" if od <= 0 else _age_bucket(od).replace("0-30", "1-30")
        out.append(dict(version="ACT", koart="Customers" if r["koart"] == "D" else "Vendors",
                        partner=r["kunnr"] or r["lifnr"], name=r["pname"], bucket=bucket,
                        special="Down payment" if r["umskz"] else "Invoice / payment",
                        blocked="Blocked (%s)" % r["zlspr"] if r["zlspr"] else "Free",
                        month=_ym(r["budat"]), amount=amt if r["koart"] == "D" else -amt,
                        overdue=(amt if r["koart"] == "D" else -amt) if od > 0 else 0, items=1))
    return out


def credit(conn):
    from fi.ar import credit_exposure
    out = []
    for c in conn.execute("SELECT kunnr, name, klimk, kdgrp, region FROM customer"):
        exp = credit_exposure(conn, c["kunnr"]) or 0
        orders_open = conn.execute("SELECT COALESCE(SUM(netwr),0) FROM sd_vbak WHERE kunnr=? AND vbtyp='C' AND "
                                   "gbstk<>'C'", (c["kunnr"],)).fetchone()[0]
        lim = c["klimk"] or 0
        tot = exp + orders_open
        util = tot * 100 // lim if lim else 0
        out.append(dict(version="ACT", kunnr=c["kunnr"], customer=c["name"],
                        risk="No limit" if not lim else "Over limit" if tot > lim else "> 80 %" if util > 80 else "OK",
                        limit=lim, receivables=exp, open_orders=orders_open, exposure=tot, free=lim - tot if lim else 0,
                        customers=1))
    return out


# ------------------------------------------------------------------ purchasing
def purchasing(conn):
    from mm.util import value_of
    out = []
    for r in conn.execute(
            "SELECT h.ebeln, h.bedat, h.lifnr, v.name, h.ekgrp, h.frgke, i.matnr, COALESCE(m.maktx, i.txz01) AS txt, "
            "COALESCE(i.matkl, m.matkl) AS matkl, i.menge, i.netpr, i.peinh, i.wemng, i.remng, i.reewr, i.knttp, i.konnr, "
            "i.infnr FROM po_item i JOIN po_header h USING (ebeln) LEFT JOIN vendor v USING (lifnr) "
            "LEFT JOIN material m ON m.matnr=i.matnr WHERE i.loekz=0"):
        ordered = value_of(r["menge"], r["netpr"], r["peinh"])
        rec = value_of(r["wemng"] or 0, r["netpr"], r["peinh"])
        out.append(dict(version="ACT", month=_ym(r["bedat"]), lifnr=r["lifnr"], vendor=r["name"], ekgrp=r["ekgrp"],
                        matnr=r["matnr"] or "#", material=r["txt"], matkl=r["matkl"] or "#",
                        acct="Cost center / order" if r["knttp"] else "Stock",
                        source="Contract" if r["konnr"] else "Info record" if r["infnr"] else "Single / new source",
                        release="Waiting for release" if r["frgke"] == "B" else "Released",
                        qty=r["menge"], ordered=ordered, received=rec, invoiced=r["reewr"] or 0,
                        open_value=max(ordered - rec, 0), items=1))
    return out


# ------------------------------------------------------------------ production
def production(conn):
    from pp.config import SCRAP_REASONS
    mat = _texts(conn, "SELECT matnr, maktx FROM material")
    var = {}
    for r in conn.execute("SELECT aufnr, SUM(target) t, SUM(actual) a, SUM(price_var) pv, SUM(qty_var) qv, "
                          "SUM(res_var+rem_var) ov FROM order_variance GROUP BY aufnr"):
        var[r["aufnr"]] = r
    scrap = {}
    for r in conn.execute("SELECT aufnr, COALESCE(grund,'') g, SUM(xmnga) x, SUM(lmnga) y FROM confirmation WHERE "
                          "COALESCE(stokz,'')='' GROUP BY aufnr, g"):
        scrap.setdefault(r["aufnr"], []).append(r)
    out = []
    for o in conn.execute("SELECT * FROM orders WHERE matnr IS NOT NULL AND matnr<>''"):
        v = var.get(o["aufnr"])
        base = dict(version="ACT", month=_ym(o["gstrp"] or o["erdat"]), aufnr=o["aufnr"], auart=o["auart"],
                    matnr=o["matnr"], material=mat.get(o["matnr"], ""), werks=o["werks"],
                    status=(o["sysst"] or o["stat"] or "").split(" ")[0] or "CRTD")
        sc = scrap.get(o["aufnr"]) or [dict(g="", x=0, y=0)]
        for i, s in enumerate(sc):
            out.append(dict(base, scrap_reason=SCRAP_REASONS.get(s["g"], "No scrap") if s["x"] else "No scrap",
                            planned=o["gamng"] if i == 0 else 0, delivered=(o["wemng"] or 0) if i == 0 else 0,
                            yield_qty=s["y"] or 0, scrap=s["x"] or 0,
                            target_cost=(v["t"] if v and i == 0 else 0), actual_cost=(v["a"] if v and i == 0 else 0),
                            variance=((v["a"] - v["t"]) if v and i == 0 else 0), orders=1 if i == 0 else 0))
    return out


# ------------------------------------------------------------------ general ledger
def ledger(conn):
    from fi.config import FSV_NODES
    node_txt = {n: t for n, t, _, _ in FSV_NODES}
    acc = {r["hkont"]: r for r in conn.execute("SELECT hkont, txt, typ, fsv FROM gl_account")}
    out = []
    for r in conn.execute("SELECT i.hkont, h.gjahr, h.monat, SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END) a "
                          "FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr GROUP BY 1,2,3"):
        a = acc.get(r["hkont"])
        out.append(dict(version="ACT", gjahr=r["gjahr"], perio=r["monat"], month="%04d-%02d" % (r["gjahr"], min(r["monat"], 12)),
                        hkont=r["hkont"], account="%s %s" % (r["hkont"], a["txt"] if a else ""),
                        fsv=node_txt.get(a["fsv"], a["fsv"]) if a else "#", typ="Balance sheet" if a and a["typ"] == "BS"
                        else "Profit and loss", amount=r["a"]))
    return out


PROVIDERS = {
    # id: (text, function, characteristics, key figures)
    "COPA": ("Profitability (CO-PA, plan and actual)", copa,
             {"version": "Version", "month": "Month", "gjahr": "Year", "perio": "Period", "customer": "Customer",
              "material": "Product", "matkl": "Material group", "region": "Region", "kdgrp": "Customer group",
              "vtweg": "Channel", "werks": "Plant"},
             {"qty": ("Sales qty", QTY), "vv010": ("Gross sales", AMT), "vv020": ("Sales deduction", AMT)}),
    "SALES": ("Billing (invoices and credit memos)", sales,
              {"month": "Month", "customer": "Customer", "material": "Product", "matkl": "Material group",
               "region": "Region", "kdgrp": "Customer group", "vtweg": "Channel", "werks": "Plant", "doc_type": "Document type"},
              {"qty": ("Billed qty", QTY), "gross": ("Gross sales", AMT), "disc": ("Discount", AMT),
               "net": ("Net sales", AMT), "cogs": ("Cost of sales", AMT), "margin": ("Gross margin", AMT),
               "docs": ("Items", NUM)}),
    "ORDERS": ("Sales orders and backlog", orders,
               {"month": "Month", "customer": "Customer", "material": "Product", "auart": "Order type",
                "status": "Status", "credit": "Credit status", "rejected": "Rejection"},
               {"qty": ("Order qty", QTY), "order_value": ("Order value", AMT), "open_qty": ("Open qty", QTY),
                "backlog": ("Backlog value", AMT), "docs": ("Items", NUM)}),
    "OVH": ("Overhead (cost centers, plan and actual)", overhead,
            {"version": "Version", "month": "Month", "cost_center": "Cost center", "cost_element": "Cost element",
             "category": "Cost type"},
            {"amount": ("Cost", AMT)}),
    "INV": ("Inventory status and aging", inventory,
            {"werks": "Plant", "lgort": "Storage location", "material": "Material", "matkl": "Material group",
             "mtart": "Material type", "stock_type": "Stock type", "aging": "Age (days)", "gr_month": "GR month"},
            {"qty": ("Stock qty", QTY), "value": ("Stock value", AMT), "value_days": ("Value x days", NUM)}),
    "INVM": ("Inventory at month end", inventory_monthly,
             {"month": "Month", "werks": "Plant", "material": "Material", "matkl": "Material group",
              "mtart": "Material type"},
             {"qty": ("Stock qty", QTY), "value": ("Stock value", AMT)}),
    "OI": ("Open receivables and payables", open_items,
           {"koart": "Account type", "name": "Partner", "bucket": "Overdue (days)", "special": "Item type",
            "blocked": "Payment block", "month": "Posting month"},
           {"amount": ("Open amount", AMT), "overdue": ("Overdue", AMT), "items": ("Items", NUM)}),
    "CREDIT": ("Credit exposure", credit,
               {"customer": "Customer", "risk": "Risk"},
               {"limit": ("Credit limit", AMT), "receivables": ("Receivables", AMT), "open_orders": ("Open orders", AMT),
                "exposure": ("Exposure", AMT), "free": ("Free limit", AMT), "customers": ("Customers", NUM)}),
    "PUR": ("Purchasing (orders, receipts, invoices)", purchasing,
            {"month": "Month", "vendor": "Vendor", "material": "Material", "matkl": "Material group", "ekgrp": "Purch. group",
             "acct": "Account assignment", "source": "Source", "release": "Release"},
            {"qty": ("Ordered qty", QTY), "ordered": ("PO value", AMT), "received": ("Received value", AMT),
             "invoiced": ("Invoiced value", AMT), "open_value": ("Open value", AMT), "items": ("Items", NUM)}),
    "PROD": ("Production orders", production,
             {"month": "Month", "material": "Product", "auart": "Order type", "status": "Status",
              "scrap_reason": "Scrap reason", "werks": "Plant"},
             {"planned": ("Planned qty", QTY), "delivered": ("Delivered qty", QTY), "yield_qty": ("Confirmed yield", QTY),
              "scrap": ("Scrap qty", QTY), "target_cost": ("Target cost", AMT), "actual_cost": ("Actual cost", AMT),
              "variance": ("Variance", AMT), "orders": ("Orders", NUM)}),
    "GL": ("General ledger", ledger,
           {"month": "Month", "account": "G/L account", "fsv": "Financial statement item", "typ": "Statement"},
           {"amount": ("Amount", AMT)}),
}
