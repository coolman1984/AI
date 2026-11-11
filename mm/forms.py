"""Print forms (output): one HTML renderer with A4 print CSS and the company
header, and an output log (message status: printed / e-mailed) per document.

Forms: purchase order, RFQ, delivery note / picking list, invoice and credit
memo (with the e-invoice UUID), dunning letter, payment advice, inventory
count sheet, production order paper.
"""
import html
import json

from mm.db import atomic, rows
from mm.util import MMError, now_ts, rdiv

OUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS output_log (     -- NAST: message status per document
    id INTEGER PRIMARY KEY AUTOINCREMENT, form TEXT, objkey TEXT, medium TEXT,
    ts TEXT, usnam TEXT);
"""
FORMS = {"PO": "Purchase order", "RFQ": "Request for quotation", "DELIVERY": "Delivery note / picking list",
         "INVOICE": "Invoice", "DUNNING": "Dunning letter", "PAYADVICE": "Payment advice",
         "COUNT": "Inventory count sheet", "PRODORDER": "Production order", "PAYSLIP": "Payslip"}

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font: 11pt/1.35 Arial, sans-serif; color: #111; margin: 0; }
.hdr { display: flex; justify-content: space-between; border-bottom: 2px solid #0a3d8f; padding-bottom: 8px; }
.co b { font-size: 15pt; color: #0a3d8f; } .co div { font-size: 9pt; color: #444; }
h1 { font-size: 17pt; margin: 14px 0 4px; } .meta td { padding: 1px 12px 1px 0; }
table.it { width: 100%; border-collapse: collapse; margin-top: 12px; }
table.it th { background: #e9eef7; text-align: left; border-bottom: 1px solid #889; padding: 4px; font-size: 9.5pt; }
table.it td { border-bottom: 1px solid #ddd; padding: 4px; font-size: 10pt; } .n { text-align: right; }
.tot { margin-top: 10px; text-align: right; font-size: 12pt; } .tot b { font-size: 13pt; }
.foot { margin-top: 28px; font-size: 9pt; color: #555; border-top: 1px solid #ccc; padding-top: 6px; }
.sign { margin-top: 40px; display: flex; gap: 60px; } .sign div { border-top: 1px solid #333; width: 200px; padding-top: 4px; font-size: 9pt; }
.box { border: 1px solid #ccc; padding: 6px 8px; margin-top: 8px; font-size: 9.5pt; }
@media screen { body { max-width: 190mm; margin: 12px auto; } }
"""
e = lambda x: html.escape("" if x is None else str(x))      # noqa: E731


def _a(c):
    return "{:,.2f}".format((c or 0) / 100.0)


def _q(m):
    return "{:,.3f}".format((m or 0) / 1000.0).rstrip("0").rstrip(".")


def _company():
    from fi.config import BUTXT
    return BUTXT


def _page(title, number, meta, partner, head, lines, total="", extra="", sign=None):
    meta_rows = "".join("<tr><td>%s</td><td><b>%s</b></td></tr>" % (e(k), e(v)) for k, v in meta)
    th = "".join("<th%s>%s</th>" % (' class="n"' if n else "", e(h)) for h, n in head)
    tr = "".join("<tr>%s</tr>" % "".join("<td%s>%s</td>" % (' class="n"' if head[i][1] else "", e(v))
                                         for i, v in enumerate(l)) for l in lines)
    sg = "".join("<div>%s</div>" % e(s) for s in (sign or []))
    return ("<!doctype html><html><head><meta charset='utf-8'><title>%s %s</title><style>%s</style></head><body>"
            "<div class='hdr'><div class='co'><b>%s</b><div>Company code 1000 - Cairo, Egypt</div>"
            "<div>Tax registration 100-200-300</div></div><div class='box'>%s</div></div>"
            "<h1>%s %s</h1><table class='meta'>%s</table>"
            "<table class='it'><thead><tr>%s</tr></thead><tbody>%s</tbody></table>"
            "<div class='tot'>%s</div>%s<div class='sign'>%s</div>"
            "<div class='foot'>Printed by MM Core - %s</div></body></html>"
            % (e(title), e(number), CSS, e(_company()), partner, e(title), e(number), meta_rows, th, tr,
               total, extra, sg, e(now_ts())))


def _addr(r, keys=("name", "street", "pstlz", "city", "land")):
    if not r:
        return ""
    r = dict(r)
    return "<br>".join(e(r.get(k)) for k in keys if r.get(k))


def _po(conn, key):
    h = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (key,)).fetchone()
    if not h:
        raise MMError("Purchase order %s does not exist" % key, "06", "019")
    v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (h["lifnr"],)).fetchone()
    its = conn.execute("SELECT i.*, m.maktx, m.meins FROM po_item i LEFT JOIN material m USING (matnr) "
                       "WHERE ebeln=? AND loekz=0 ORDER BY ebelp", (key,)).fetchall()
    from mm.util import value_of
    lines, tot = [], 0
    for i in its:
        val = value_of(i["menge"], i["netpr"], i["peinh"])
        tot += val
        lines.append((i["ebelp"], i["matnr"] or "", i["maktx"] or i["txz01"] if "txz01" in i.keys() else i["maktx"],
                      _q(i["menge"]), i["meins"] or "", i["eindt"] if "eindt" in i.keys() else "",
                      _a(i["netpr"]), _a(val)))
    rel = "Released" if h["frgke"] != "B" else "NOT RELEASED - not valid as an order"
    return _page("Purchase order", key, [("Date", h["bedat"]), ("Vendor", h["lifnr"]), ("Currency", h["waers"]),
                                         ("Payment terms", h["zterm"]), ("Release", rel)],
                 _addr(v), [("Item", 0), ("Material", 0), ("Description", 0), ("Quantity", 1), ("Unit", 0),
                            ("Delivery", 0), ("Price", 1), ("Value", 1)], lines,
                 "Total net value: <b>%s %s</b>" % (_a(tot), e(h["waers"])),
                 "<div class='box'>Please quote the order number on delivery note and invoice. Deliver to plant "
                 "1000, goods receipt Mon-Thu and Sat 08:00-15:00.</div>", ["Purchasing", "Purchasing manager"])


def _rfq(conn, key):
    r = conn.execute("SELECT q.*, m.maktx, m.meins FROM rfq q LEFT JOIN material m USING (matnr) WHERE anfnr=?",
                     (key,)).fetchone()
    if not r:
        raise MMError("RFQ %s does not exist" % key, "06", "019")
    v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (r["lifnr"],)).fetchone()
    return _page("Request for quotation", key, [("Collective number", r["submi"]), ("Quotation deadline", r["angdt"]),
                                                ("Delivery date", r["lfdat"])], _addr(v),
                 [("Material", 0), ("Description", 0), ("Quantity", 1), ("Unit", 0), ("Your price", 1)],
                 [(r["matnr"], r["maktx"], _q(r["menge"]), r["meins"], "")], "",
                 "<div class='box'>Please send your quotation with price, delivery time and payment terms "
                 "before the deadline.</div>", ["Purchasing"])


def _delivery(conn, key):
    h = conn.execute("SELECT * FROM sd_likp WHERE vbeln=?", (key,)).fetchone()
    if not h:
        raise MMError("Delivery %s does not exist" % key, "VL", "001")
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (h["kunnr"],)).fetchone()
    its = conn.execute("SELECT l.*, m.meins FROM sd_lips l LEFT JOIN material m USING (matnr) WHERE vbeln=? "
                       "ORDER BY posnr", (key,)).fetchall()
    return _page("Delivery note", key, [("Delivery date", h["lfdat"]), ("Sales order", h["vgbel"]),
                                        ("Goods issue", h["wadat_ist"] or "not yet")], _addr(c),
                 [("Item", 0), ("Material", 0), ("Description", 0), ("Quantity", 1), ("Unit", 0),
                  ("Storage loc.", 0), ("Bin (picking)", 0)],
                 [(i["posnr"], i["matnr"], i["arktx"], _q(i["lfimg"]), i["meins"], i["lgort"], i["lgpla"])
                  for i in its], "", "", ["Warehouse", "Received by customer"])


def _invoice(conn, key):
    h = conn.execute("SELECT * FROM billing WHERE vbeln=?", (key,)).fetchone()
    if not h:
        raise MMError("Billing document %s does not exist" % key, "VF", "001")
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (h["kunrg"] or h["kunnr"],)).fetchone()
    its = conn.execute("SELECT b.*, m.maktx FROM billing_item b LEFT JOIN material m USING (matnr) WHERE vbeln=? "
                       "ORDER BY posnr", (key,)).fetchall()
    credit = (h["vbtyp"] or "") in ("O", "N") or (h["fkart"] or "") in ("G2", "RE", "S1")
    title = "Credit memo" if credit else "Tax invoice"
    tax = h["mwsbk"] or 0
    extra = "<div class='box'>E-invoice UUID (Egyptian Tax Authority): <b>%s</b> - status %s</div>" % (
        e(h["eta_uuid"] or "not yet submitted (ZEINV)"), e(h["eta_status"] or "-"))
    if h["cancelled"]:
        extra += "<div class='box'><b>CANCELLED</b></div>"
    waerk = h["waerk"] or "EGP"
    fc = waerk != "EGP" and h["netwr_fc"] is not None
    if fc:
        # foreign-currency invoice: the amounts the customer pays (document currency)
        net, tax = h["netwr_fc"] or 0, h["mwsbk_fc"] or 0
        extra += "<div class='box'>Exchange rate %.5f EGP per %s - net %s EGP, VAT %s EGP</div>" % (
            (h["kurrf"] or 100000) / 100000.0, e(waerk), _a(h["netwr"]), _a(h["mwsbk"]))
        lines = [(i["posnr"], i["matnr"], i["arktx"] or i["maktx"], _q(i["fkimg"]),
                  _a(rdiv((i["gross_fc"] or 0) * 1000, i["fkimg"]) if i["fkimg"] else 0), _a(i["disc_fc"]),
                  _a(i["net_fc"] if i["net_fc"] is not None else 0)) for i in its]
    else:
        net = h["netwr"] or 0
        lines = [(i["posnr"], i["matnr"], i["arktx"] or i["maktx"], _q(i["fkimg"]), _a(i["price"]), _a(i["disc"]),
                  _a(i["net"])) for i in its]
    return _page(title, key, [("Date", h["fkdat"]), ("Customer", h["kunnr"]), ("Payment terms", h["zterm"]),
                              ("Currency", waerk), ("Order", h["aubel"])], _addr(c),
                 [("Item", 0), ("Material", 0), ("Description", 0), ("Quantity", 1), ("Price", 1), ("Discount", 1),
                  ("Net", 1)], lines,
                 "Net %s - VAT %s - <b>Total %s %s</b>" % (_a(net), _a(tax), _a(net + tax), e(waerk)),
                 extra, ["Accounting"])


def _dunning(conn, key):
    run_id, _, kunnr = str(key).partition("-")
    r = conn.execute("SELECT * FROM dunning_run WHERE id=?", (run_id,)).fetchone()
    if not r:
        raise MMError("Dunning run %s does not exist" % run_id, "F1", "001")
    L = next((x for x in json.loads(r["result"] or "[]") if x["kunnr"] == kunnr), None)
    if not L:
        raise MMError("Customer %s is not in dunning run %s" % (kunnr, run_id), "F1", "002")
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
    return _page("Dunning letter - %s" % L.get("level_text", ""), "%s/%s" % (run_id, kunnr),
                 [("Date", r["ausdt"]), ("Customer", kunnr), ("Dunning level", L["level"])], _addr(c),
                 [("Document", 0), ("Reference", 0), ("Due", 0), ("Days overdue", 1), ("Amount", 1)],
                 [(i["belnr"], i["xblnr"], i["netdt"], i["overdue"], _a(i["amount"])) for i in L["items"]],
                 "Overdue total: <b>%s EGP</b>" % _a(L["total"]),
                 "<div class='box'>Please pay the overdue amount within 7 days. Dunning charges: %s EGP. If you have "
                 "already paid, please ignore this letter.</div>" % e(L.get("charges", 0)), ["Accounts receivable"])


def _payadvice(conn, key):
    belnr, _, gjahr = str(key).partition("-")
    h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?", (belnr, gjahr or 0)).fetchone()
    if not h:
        raise MMError("Payment document %s does not exist" % key, "F5", "001")
    cl = conn.execute("SELECT i.*, d.xblnr FROM acc_doc_item i JOIN acc_doc d ON d.belnr=i.belnr AND d.gjahr=i.gjahr "
                      "WHERE i.augbl=? AND i.koart IN ('K','D') AND NOT (i.belnr=? AND i.gjahr=?)",
                      (belnr, belnr, gjahr)).fetchall()
    p = conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=? AND koart IN ('K','D')",
                     (belnr, gjahr)).fetchone()
    partner = None
    if p:
        partner = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (p["lifnr"],)).fetchone() if p["koart"] == "K" \
            else conn.execute("SELECT * FROM customer WHERE kunnr=?", (p["kunnr"],)).fetchone()
    tot = sum((i["dmbtr"] if i["shkzg"] == "H" else -i["dmbtr"]) for i in cl)
    return _page("Payment advice", belnr, [("Payment date", h["budat"]), ("Document", "%s/%s" % (belnr, gjahr))],
                 _addr(partner), [("Document", 0), ("Your reference", 0), ("Date", 0), ("Amount", 1)],
                 [(i["belnr"], i["xblnr"], i["zfbdt"], _a(i["dmbtr"] if i["shkzg"] == "H" else -i["dmbtr"]))
                  for i in cl], "Paid: <b>%s EGP</b>" % _a(abs(tot)), "", ["Accounts payable"])


def _count(conn, key):
    from mm.inventory import display
    d = display(conn, key)
    return _page("Inventory count sheet", key, [("Plant / storage location", "%s / %s" % (d["werks"], d["lgort"])),
                                                ("Planned count date", d["plan_date"]),
                                                ("Posting block", "yes" if d["freeze"] else "no")], "",
                 [("Item", 0), ("Material", 0), ("Description", 0), ("Bin", 0), ("Stock type", 0), ("Unit", 0),
                  ("Counted quantity", 1)],
                 [(i["zeili"], i["matnr"], i["maktx"], i["lgpla"], i["insmk"], i["meins"], "______________")
                  for i in d["items"] if not i["recount"]],
                 "", "<div class='box'>Book quantities are not printed (blind count). Write zero if the bin is "
                 "empty.</div>", ["Counted by", "Checked by"])


def _prodorder(conn, key):
    o = conn.execute("SELECT o.*, m.maktx, m.meins FROM orders o LEFT JOIN material m USING (matnr) WHERE aufnr=?",
                     (key,)).fetchone()
    if not o:
        raise MMError("Order %s does not exist" % key, "CO", "001")
    ops = conn.execute("SELECT * FROM pp_oper WHERE aufnr=? ORDER BY vornr", (key,)).fetchall()
    comps = conn.execute("SELECT r.*, m.maktx, m.meins FROM pp_resb r LEFT JOIN material m USING (matnr) WHERE "
                         "aufnr=? ORDER BY rspos", (key,)).fetchall()
    extra = "<h3>Components</h3><table class='it'><tr><th>Material</th><th>Description</th><th class='n'>Required" \
            "</th><th>Unit</th><th>Storage loc.</th></tr>%s</table>" % "".join(
                "<tr><td>%s</td><td>%s</td><td class='n'>%s</td><td>%s</td><td>%s</td></tr>" % (
                    e(c["matnr"]), e(c["maktx"]), _q(c["bdmng"]), e(c["meins"]), e(c["lgort"])) for c in comps)
    keys = ops[0].keys() if ops else []
    return _page("Production order", key, [("Material", "%s %s" % (o["matnr"] or "", o["maktx"] or "")),
                                           ("Quantity", "%s %s" % (_q(o["gamng"]), o["meins"] or "")),
                                           ("Start", o["gstrp"]), ("Finish", o["gltrp"] if "gltrp" in o.keys() else ""),
                                           ("Status", o["status"] if "status" in o.keys() else "")], "",
                 [("Operation", 0), ("Work center", 0), ("Description", 0), ("Confirmed yield", 1)],
                 [(p["vornr"], p["arbpl"], p["ltxa1"] if "ltxa1" in keys else "", _q(p["lmnga"] if "lmnga" in keys else 0))
                  for p in ops], "", extra, ["Production planner", "Shop floor"])


def _payslip(conn, key):
    """key: YYYY-MM-PERNR (e.g. 2026-10-10001)"""
    from hr import payroll
    try:
        y, p, pernr = str(key).split("-", 2)
        y, p = int(y), int(p)
    except ValueError:
        raise MMError("Enter the payslip as YYYY-MM-personnel number (e.g. 2026-10-10001)", "PY", "010")
    r = payroll.results(conn, y, p, pernr)
    if not r:
        raise MMError("No payroll result for %s in %04d/%02d" % (pernr, y, p), "PY", "011")
    r = r[0]
    lines = [("Basic salary", _a(r["basic"]), ""), ("Allowances", _a(r["allowances"]), ""),
             ("Overtime", _a(r["overtime"]), ""), ("Unpaid absence", "", _a(r["unpaid"])),
             ("Social insurance (employee 11 %)", "", _a(r["si_ee"])), ("Salary income tax", "", _a(r["tax"])),
             ("Martyrs' fund", "", _a(r["martyrs"]))]
    return _page("Payslip", "%04d/%02d - %s" % (y, p, r["pernr"]),
                 [("Employee", "%s %s" % (r["pernr"], r["name"])), ("Organizational unit", r["org_text"]),
                  ("Position", r["job"]), ("Paid days", r["paid_days"]), ("Insurable wage", _a(r["ins_wage"])),
                  ("Bank account", r["iban"])], "<b>%s</b><br>%s" % (e(r["name"]), e(r["name_ar"] or "")),
                 [("Wage type", 0), ("Earnings", 1), ("Deductions", 1)], lines,
                 "Gross %s - Deductions %s - <b>Net pay %s EGP</b>" % (_a(r["gross"]), _a(r["gross"] - r["net"]),
                                                                       _a(r["net"])) + _fc_pay(r),
                 "<div class='box'>Employer social insurance (18.75 %%): %s EGP - not deducted from your pay.</div>"
                 % _a(r["si_er"]), ["HR department"])


def _fc_pay(r):
    """pay currency USD: amounts in EGP (insurance and tax law), paid in USD"""
    w = r["waers"] if "waers" in r and r["waers"] else "EGP"
    if w == "EGP":
        return ""
    return ("<br>Pay currency %s at %.5f EGP: gross %s %s - <b>net pay transferred %s %s</b>"
            % (w, (r["kurs"] or 100000) / 100000.0, _a(r["gross_fc"] or 0), w, _a(r["net_fc"] or 0), w))


_R = {"PO": _po, "RFQ": _rfq, "DELIVERY": _delivery, "INVOICE": _invoice, "DUNNING": _dunning,
      "PAYADVICE": _payadvice, "COUNT": _count, "PRODORDER": _prodorder, "PAYSLIP": _payslip}


def render(conn, form, key):
    f = (form or "").upper()
    if f not in _R:
        raise MMError("Form %s does not exist" % form, "VN", "001")
    return _R[f](conn, str(key or "").strip())


@atomic
def log_output(conn, form, key, medium, user):
    if (medium or "").upper() not in ("PRINT", "EMAIL"):
        raise MMError("Medium must be PRINT or EMAIL", "VN", "002")
    render(conn, form, key)                          # the document must exist
    conn.execute("INSERT INTO output_log (form,objkey,medium,ts,usnam) VALUES (?,?,?,?,?)",
                 (form.upper(), str(key), medium.upper(), now_ts(), user))
    if form.upper() == "PO" and medium.upper() == "PRINT":
        conn.execute("UPDATE po_header SET printed=1 WHERE ebeln=?", (str(key),))


def outputs(conn, form=None, key=None):
    sql, a = "SELECT * FROM output_log WHERE 1=1", []
    if form:
        sql += " AND form=?"
        a.append(form.upper())
    if key:
        sql += " AND objkey=?"
        a.append(str(key))
    return rows(conn.execute(sql + " ORDER BY id DESC LIMIT 200", a))
