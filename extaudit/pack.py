"""ZAUD_PACK - the audit pack: one Excel workbook with the schedules the audit firm requests at year end,
each sheet named after the PBC item it answers and referenced to the Egyptian Accounting Standards."""
from fi.config import BUTXT

from . import analytics as A
from . import engagement as E
from .standards import EAS, ESA


def build(conn, y):
    from mm.xlsx import HEADER, NOTE, NUMBER, TITLE, WRAP, Workbook
    e = E.engagement(conn, y)
    y = e["gjahr"]
    ye = "%04d-12-31" % y
    wb = Workbook()

    def sheet(name, title, head, rows, widths=None, note=None, rtl=False):
        s = wb.add(name, rtl=rtl)
        s.set(0, 0, title, TITLE)
        s.set(1, 0, "%s - fiscal year %d - prepared by NERP%s" % (BUTXT, y, (" - " + note) if note else ""), NOTE)
        s.row(3, head, HEADER)
        s.heights[3] = 32
        for i, r in enumerate(rows, start=4):
            for c, v in enumerate(r):
                if v is None:
                    continue
                s.set(i, c, v, NUMBER if isinstance(v, float) else WRAP)
        for c, w in enumerate(widths or [16] * len(head)):
            s.widths[c] = w
        s.freeze = (4, 0)
        return s

    # 00 index: the PBC list with status and standards
    items = E.pbc(conn, y)
    sheet("00 PBC index", "Audit requests (PBC list) and status", ["Code", "Area", "Request", "الطلب", "EAS", "ESA", "Status",
                                                                   "Prepared in sheet", "Comment"],
          [[i["code"], i["area"], i["text"], i["text_ar"], i["eas_text"], i["esa"], i["status_text"], i["auto"] or "manual",
            i["comment"]] for i in items], [8, 12, 50, 44, 22, 10, 16, 22, 30])
    sheet("01 Materiality", "Materiality (ESA 320)", ["Item", "Value (EGP)", "Basis"],
          [["Base: " + e["base_text"], float(e["base"]), ""], ["Overall materiality", float(e["overall"]), "%.2f %% of the base" % (e["pct"] / 100.0)],
           ["Performance materiality", float(e["performance"]), "%.0f %% of overall" % (e["pm_pct"] / 100.0)],
           ["Clearly trivial", float(e["trivial"]), "%.0f %% of overall" % (e["trivial_pct"] / 100.0)],
           ["Audit firm", e["firm"] or "-", "Partner: %s" % (e["partner"] or "-")]], [36, 18, 30])
    from fi.reports import trial_balance
    tb = trial_balance(conn, y, 1, 12)
    sheet("02 Trial balance", "Trial balance %s" % ye, ["Account", "Name", "Type", "FS line", "Opening", "Debit", "Credit", "Closing"],
          [[r["hkont"], r["txt"], r["typ"], r["fsv"], float(r["opening"]), float(r["debit"]), float(r["credit"]), float(r["closing"])]
           for r in tb], [10, 40, 6, 8, 16, 16, 16, 16], "debit +, credit -")
    st = A.statements(conn, y)
    sheet("03 Statements", "Draft statement of financial position and income statement (EAS 1)", ["Line", "Description", "This year", "Comparison", "Change", "%"],
          [[r["node"], ("   " * r["level"]) + r["text"], float(r["cur"]), float(r["cmp"]), float(r["diff"]), r["pct"]] for r in st["rows"]],
          [8, 46, 18, 18, 18, 8], "balanced: %s - cash flow statement (EAS 4) and notes are prepared by the accountant" % st.get("balanced"))
    lead = []
    for r in A.lead_schedules(conn, y):
        lead.append([r["node"], r["text"], float(r["cur"]), float(r["cmp"]), float(r["diff"]), r["pct"]])
        for a in r["accounts"]:
            lead.append(["", "   %s %s" % (a["hkont"], a["txt"]), float(a["cur"]), float(a["cmp"]), None, None])
    sheet("04 Lead schedules", "Lead schedules per financial statement line", ["Line", "Line / account", "This year", "Comparison", "Change", "%"],
          lead, [8, 50, 18, 18, 18, 8])
    jr = conn.execute("SELECT h.belnr, h.budat, h.blart, h.tcode, h.usnam, h.bktxt, i.buzei, i.hkont, i.shkzg, i.dmbtr, i.sgtxt "
                      "FROM acc_doc h JOIN acc_doc_item i ON i.belnr=h.belnr AND i.gjahr=h.gjahr WHERE h.budat BETWEEN ? AND ? "
                      "ORDER BY h.budat, h.belnr, i.buzei", ("%04d-01-01" % y, ye)).fetchall()
    sheet("05 Journal", "Journal of all postings", ["Document", "Date", "Type", "Transaction", "User", "Header text", "Line", "Account",
                                                    "D/C", "Amount", "Line text"],
          [[r["belnr"], r["budat"], r["blart"], r["tcode"] or "", r["usnam"], r["bktxt"] or "", r["buzei"], r["hkont"], r["shkzg"],
            round(r["dmbtr"] / 100.0, 2), r["sgtxt"] or ""] for r in jr], [12, 11, 6, 12, 10, 30, 6, 10, 5, 15, 30])
    j = A.jet(conn, y, int(e["performance"] * 100) or None)
    sheet("06 Journal entry testing", "Journal entry testing (ESA 240) - %d of %d documents flagged" % (j["flagged"], j["documents"]),
          ["Document", "Date", "Type", "Transaction", "User", "Text", "Amount", "Score", "Why"],
          [[r["belnr"], r["budat"], r["blart"], r["tcode"], r["usnam"], r["text"], r["amount"], r["score"], "; ".join(r["flags"])]
           for r in j["rows"]], [12, 11, 6, 12, 10, 30, 15, 7, 60])
    b = A.bank(conn, y)
    sheet("07 Bank", "Bank balances at %s - confirm with the banks (ESA 505)" % ye, ["Bank", "Account", "Description", "G/L", "Currency", "Book balance"],
          [[r["bank"], r["account"], r["text"], r["gl"], r["currency"], r["balance"]] for r in b["rows"]], [10, 12, 44, 10, 8, 18])
    for no, koart, label in (("08", "D", "Receivables"), ("09", "K", "Payables")):
        p = A.partners(conn, y, koart)
        rows = [[r["partner"], r["name"], r["total"], r["not_due"], r["d30"], r["d60"], r["d90"], r["d90p"], "YES" if r["sample"] else "",
                 r["why"]] for r in p["rows"]]
        if koart == "D":
            ec = A.ecl(conn, y)
            rows += [[], ["Expected credit loss (EAS 47) - simplified matrix, calibrate the rates", "", None, None, None, None, None, None, "", ""]]
            rows += [["", x["bucket"], x["balance"], None, None, None, None, None, "rate %s %%" % x["rate"], "allowance %.2f" % x["allowance"]]
                     for x in ec["lines"]]
            rows.append(["", "Allowance", ec["allowance"], None, None, None, None, None, "", ""])
        sheet("%s %s" % (no, label), "%s aging at %s and confirmation sample (coverage %s %%)" % (label, ye, p["coverage_pct"]),
              ["Partner", "Name", "Balance", "Not due", "1-30", "31-60", "61-90", "> 90", "Confirm", "Selection"], rows,
              [10, 34, 16, 14, 14, 14, 14, 14, 9, 24])
    u = A.unrecorded(conn, y)
    sheet("10 Unrecorded liabilities", "Search for unrecorded liabilities - payments %s to %s" % (u["from"], u["to"]),
          ["Document", "Date", "Vendor", "Amount", "Text"], [[r["belnr"], r["budat"], r["vendor"], r["amount"], r["text"]] for r in u["payments"]]
          + [[], ["GR/IR balance at year end", "", "", u["grir_balance"], u["note"]]], [12, 11, 34, 16, 50])
    inv = A.inventory(conn, y)
    sheet("11 Inventory", "Inventory at %s (EAS 2): valuation, net realisable value, slow-moving" % ye,
          ["Plant", "Material", "Description", "Qty", "Unit", "Value", "Unit cost", "Last selling price", "NRV write-down", "Last movement",
           "Idle days", "Flags"],
          [[r["werks"], r["matnr"], r["text"], r["qty"], r["unit"], r["value"], r["unit_cost"], r["last_price"], r["nrv_writedown"],
            r["last_move"], r["idle_days"], "; ".join(r["flags"])] for r in inv["rows"]]
          + [[], ["Total", "", "", None, "", inv["total"], None, None, inv["nrv_writedown"], "", None, ""]]
          + [["Count differences", d["movement"], "%d document(s)" % d["documents"], None, "", d["value"]] for d in inv["count_differences"]],
          [7, 10, 30, 10, 6, 15, 12, 12, 14, 11, 8, 34])
    fa = A.fixed_assets(conn, y)
    t = fa["total"]
    sheet("12 Fixed assets", "Fixed asset roll-forward (EAS 10)", ["Asset", "Description", "Class", "Cost opening", "Additions", "Disposals",
                                                                     "Cost closing", "Dep. opening", "Dep. charge", "Dep. closing", "Net book value"],
          [[r["anln1"], r["text"], r["cls"], r["cost_open"], r["additions"], r["disposals"], r["cost_close"], r["dep_open"], r["dep_charge"],
            r["dep_close"], r["nbv"]] for r in fa["rows"]]
          + [["Total", "", "", t["cost_open"], t["additions"], t["disposals"], t["cost_close"], t["dep_open"], t["dep_charge"], t["dep_close"], t["nbv"]]],
          [10, 34, 7, 15, 15, 13, 15, 15, 15, 15, 15])
    c = A.cutoff(conn, y)
    sheet("13 Revenue cut-off", "Revenue cut-off %s to %s (EAS 48) - %d issue(s)" % (c["window"][0], c["window"][1], c["issues"]),
          ["Invoice", "Invoice date", "Goods issue", "Customer", "Net", "Cut-off issue"],
          [[r["vbeln"], r["invoice_date"], r["goods_issue"], r["customer"], r["net"], "YES" if r["issue"] else ""] for r in c["rows"]],
          [12, 12, 12, 34, 15, 12])
    pr = A.payroll(conn, y)
    sheet("14 Payroll", "Payroll reconciliation with the ledger (EAS 38)", ["Month", "Employees", "Gross", "Employer SI", "Payroll cost",
                                                                            "Posted in ledger", "Difference", "Net paid"],
          [[r["month"], r["employees"], r["gross"], r["employer_si"], r["payroll_cost"], r["ledger"], r["difference"], r["net"]] for r in pr["rows"]],
          [10, 10, 15, 15, 15, 15, 15, 15], "a difference = payroll not yet posted or posted elsewhere")
    from tax import audit as ta, returns as tr
    rr = ta.revenue_reconciliation(conn, y)
    cit = tr.cit_estimate(conn, y)
    sheet("15 Tax", "Tax: revenue = invoices = e-invoices = VAT base; corporate tax estimate (EAS 24)",
          ["Month", "Revenue in books", "Invoices", "E-invoices valid", "VAT base", "Books - invoices", "Not e-invoiced", "OK"],
          [[r["month"], round(r["books"] / 100.0, 2), round(r["invoices"] / 100.0, 2), round(r["einvoices"] / 100.0, 2), round(r["vat_base"] / 100.0, 2),
            round(r["diff_books"] / 100.0, 2), round(r["diff_einv"] / 100.0, 2), "OK" if r["ok"] else "CHECK"] for r in rr["rows"]]
          + [[], ["Corporate tax estimate", "profit %.2f" % (cit["profit"] / 100.0), "rate %s %%" % cit["rate"], "tax %.2f" % (cit["tax"] / 100.0),
                  "deferred tax: prepared by the accountant"]], [12, 15, 15, 15, 15, 15, 15, 8])
    rp = ta.related_parties(conn, y)
    sheet("16 Related parties", "Related parties (EAS 15)", ["Item", "Value"],
          [[k, (round(v / 100.0, 2) if isinstance(v, int) and k in ("sales", "threshold") else str(v))] for k, v in rp.items()], [30, 30])
    sb = A.subsequent(conn, y, int(e["performance"] * 100) or 1)
    sheet("17 Subsequent events", "Subsequent events %s to %s (EAS 7, ESA 560)" % (sb["from"], sb["to"]),
          ["Document", "Date", "Type", "Text", "Amount", "Why"], [[r["belnr"], r["budat"], r["blart"], r["text"], r["amount"], r["why"]] for r in sb["rows"]],
          [12, 11, 6, 40, 15, 12])
    aj = E.adjustments(conn, y)
    sheet("18 Adjustments", "Audit adjustments and summary of uncorrected misstatements (ESA 450)",
          ["No.", "Description", "EAS", "Status", "Effect on profit", "Debit total", "Decided by", "Reason / document"],
          [[r["id"], r["text"], r["eas"], r["status"], r["pl_effect"], r["dr"], r["decided_by"], r["reason"] or r["belnr"]] for r in aj["rows"]]
          + [[], ["", "Uncorrected (gross)", "", "", aj["uncorrected_gross"]], ["", "Overall materiality", "", "", aj["overall"]],
             ["", "Performance materiality", "", "", aj["performance"]], ["", aj["conclusion"]]], [6, 46, 8, 11, 16, 16, 12, 30])
    # confirmation letters (Arabic) - customers and vendors in the sample, banks
    letters = []
    for koart, who in (("D", "عميل"), ("K", "مورد")):
        for r in A.partners(conn, y, koart)["rows"]:
            if r["sample"]:
                letters.append([who, r["partner"], r["name"], abs(r["total"]),
                                "السادة / %s\nتحية طيبة وبعد،\nبرجاء التكرم بمصادقة مراقب حساباتنا (%s) مباشرة على رصيد حسابكم لدينا في %s والبالغ %s جنيه %s. "
                                "في حالة الاختلاف برجاء إرسال كشف حساب بالتفاصيل.\nمع خالص الشكر،\n%s"
                                % (r["name"], e["firm"] or "مراقب الحسابات", ye, "{:,.2f}".format(abs(r["total"])),
                                   "مدين" if r["total"] > 0 else "دائن", BUTXT)])
    for r in b["rows"]:
        letters.append(["بنك", r["account"], r["text"], r["balance"],
                        "السادة / %s\nبرجاء التكرم بإرسال المصادقة مباشرة إلى مراقب حساباتنا (%s) على أرصدة جميع حساباتنا وودائعنا وتسهيلاتنا "
                        "والضمانات لديكم في %s.\nمع خالص الشكر،\n%s" % (r["text"], e["firm"] or "مراقب الحسابات", ye, BUTXT)])
    sheet("19 Confirmation letters", "خطابات المصادقة (معيار المراجعة 505)", ["النوع", "الكود", "الاسم", "الرصيد", "نص الخطاب"], letters,
          [8, 10, 30, 15, 100], rtl=True)
    sheet("20 Standards", "Egyptian Accounting Standards referenced", ["EAS", "Title", "العنوان", "Status"],
          [[n, t[0], t[1], "confirmed" if t[2] else "verify the number with the auditor"] for n, t in EAS.items()]
          + [[], ["ESA", "Egyptian Standards on Auditing (ISA numbering)"]] + [[n, t] for n, t in ESA.items()], [8, 60, 50, 30])
    return wb.save()
