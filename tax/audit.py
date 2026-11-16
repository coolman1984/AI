"""Tax audit readiness (الفحص الضريبي) - Unified Tax Procedures Law 206/2020 and the tax laws.

ZTAX_AUDIT     checklist of a fiscal year: every point the tax inspector checks, computed from the
               data (ok / issue / manual) with the transaction to fix it
ZTAX_REVREC    revenue reconciliation per month: books (revenue accounts) = invoices issued =
               e-invoices accepted by the ETA = VAT return (output tax base)
ZTAX_AUDITFILE the audit file (Excel): trial balance, journal, sales and purchase VAT registers,
               withholding register, salary tax register, fixed asset register, e-invoice log,
               revenue reconciliation, related-party transactions
NERP never deletes a posted document (only reversals), every change is in the audit log and the
documents stay electronic and readable - the retention period is in the law register.
"""
import calendar

from mm import util as clock
from mm.util import parse_int

from . import rules

REV_FSV = ("R10",)


def _rev_accounts(conn):
    return [r[0] for r in conn.execute("SELECT hkont FROM gl_account WHERE typ='PL' AND fsv IN (%s) AND hkont NOT IN "
                                       "('830000','831000')" % ",".join("?" * len(REV_FSV)), REV_FSV)]


def revenue_reconciliation(conn, y):
    from fi.gl import vat_report
    y = parse_int(y, "year", 2000, 2100)
    accs = _rev_accounts(conn)
    rows = []
    for m in range(1, 13):
        d1 = "%04d-%02d-01" % (y, m)
        d2 = "%04d-%02d-%02d" % (y, m, calendar.monthrange(y, m)[1])
        if d1 > clock.today().isoformat():
            break
        books = -conn.execute("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM "
                              "acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.budat "
                              "BETWEEN ? AND ? AND i.hkont IN (%s)" % ",".join("?" * len(accs)), [d1, d2] + accs).fetchone()[0]
        inv = conn.execute("SELECT COALESCE(SUM(b.netwr),0), COUNT(*) FROM billing b WHERE b.cancelled=0 AND b.fkart<>'S1' "
                           "AND b.fkdat BETWEEN ? AND ?", (d1, d2)).fetchone()
        einv = conn.execute("SELECT COALESCE(SUM(b.netwr),0), COUNT(*) FROM billing b JOIN eta_out o ON o.vbeln=b.vbeln "
                            "WHERE b.cancelled=0 AND o.status='Valid' AND b.fkdat BETWEEN ? AND ?", (d1, d2)).fetchone()
        v = vat_report(conn, d1, d2)
        vat_base = sum(r["base"] for r in v["rows"] if r["typ"] == "O")
        if not (books or inv[0] or vat_base):
            continue
        rows.append(dict(month="%04d-%02d" % (y, m), books=books, invoices=inv[0], invoice_count=inv[1],
                         einvoices=einv[0], einvoice_count=einv[1], vat_base=vat_base,
                         diff_books=books - inv[0], diff_einv=inv[0] - einv[0], diff_vat=inv[0] - vat_base,
                         ok=books == inv[0] == vat_base and inv[0] == einv[0]))
    tot = {k: sum(r[k] for r in rows) for k in ("books", "invoices", "einvoices", "vat_base", "diff_books",
                                                 "diff_einv", "diff_vat")}
    return {"year": y, "rows": rows, "total": tot, "ok": all(r["ok"] for r in rows)}


def related_parties(conn, y):
    """transactions with affiliated companies (customer account assignment group 03 / vendors marked as group
    companies by the reconciliation account) against the transfer pricing threshold"""
    y = parse_int(y, "year", 2000, 2100)
    d1, d2 = "%04d-01-01" % y, "%04d-12-31" % y
    sales = conn.execute("SELECT COALESCE(SUM(b.netwr),0) FROM billing b JOIN md_knvv k ON k.kunnr=b.kunnr WHERE "
                         "k.ktgrd='03' AND b.cancelled=0 AND b.fkdat BETWEEN ? AND ?", (d1, d2)).fetchone()[0]
    limit = int(rules.num(conn, "TP_THRESHOLD", d2) * 100)
    return {"year": y, "sales": sales, "threshold": limit, "local_file": sales > limit}


def checklist(conn, y):
    from fi.reports import trial_balance
    from . import eta, returns
    y = parse_int(y, "year", 2000, 2100)
    d1, d2 = "%04d-01-01" % y, "%04d-12-31" % y
    today = clock.today().isoformat()
    last_m = 12 if d2 < today else clock.today().month
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]          # noqa: E731
    items = []

    def add(area, check, status, info, tcode, law=""):
        items.append(dict(no=len(items) + 1, area=area, check=check, status=status, info=info, tcode=tcode, law=law))
    # 1 books and records
    tb = trial_balance(conn, y, 1, 12)                       # rows in EGP (not cents)
    bal = round(sum(r["closing"] or 0 for r in tb), 2)
    add("Books", "General ledger balanced (trial balance debit = credit)", "ok" if bal == 0 else "issue",
        "difference %.2f EGP" % bal if bal else "balanced (%d accounts)" % len(tb), "S_ALR_87012277", "Law 206/2020")
    oldest = one("SELECT MIN(budat) FROM acc_doc") or ""
    add("Books", "Documents kept electronically and readable; never deleted (reversal only)", "ok",
        "oldest posting %s - keep at least %s years" % (oldest or "-", rules.get(conn, "AUD_RETENTION")["value"]),
        "FB03", "Law 206/2020 - retention")
    n = one("SELECT COUNT(*) FROM audit_log")
    add("Books", "Audit trail of changes and postings (who, when, what)", "ok" if n else "manual",
        "%d log entries" % n, "SM20", "Law 206/2020")
    # 2 revenue and e-invoices
    rec = revenue_reconciliation(conn, y)
    add("Revenue", "Revenue in the books = invoices issued = VAT return base", "ok" if all(
        r["diff_books"] == 0 and r["diff_vat"] == 0 for r in rec["rows"]) else "issue",
        "differences in %d month(s)" % sum(1 for r in rec["rows"] if r["diff_books"] or r["diff_vat"]), "ZTAX_REVREC",
        "Law 67/2016, Law 91/2005")
    out = eta.outbound(conn, d1, d2)
    notsent = sum(n for s, n in out["counts"].items() if s not in ("Valid", "Cancelled"))
    add("E-invoice", "Every invoice issued as e-invoice and accepted (Valid) by the ETA", "ok" if not notsent else "issue",
        "%d invoice(s) not valid at the ETA" % notsent, "ZTAX_EINV", "Law 206/2020 art. 35 / 71 - fine from %s EGP" %
        rules.get(conn, "EINV_FINE_MIN")["value"])
    risk = eta.input_vat_at_risk(conn, d1, d2)
    add("E-invoice", "Input VAT only on purchases with a valid received e-invoice", "ok" if not risk["count"] else "issue",
        "%d vendor invoice(s), %.2f EGP input VAT at risk" % (risk["count"], risk["amount"] / 100.0), "ZTAX_EIN",
        "Law 67/2016 - deduction needs the tax invoice")
    # 3 returns filed
    for typ, text, periods in (("VAT", "Monthly VAT returns (form 10) filed", ["%04d-%02d" % (y, m) for m in range(1, last_m + 1)]),
                               ("SAL", "Monthly salary tax returns filed", ["%04d-%02d" % (y, m) for m in range(1, last_m + 1)]),
                               ("WHT", "Quarterly withholding returns (form 41) filed",
                                ["%04d-Q%d" % (y, q) for q in range(1, last_m // 3 + 1)])):
        filed = one("SELECT COUNT(*) FROM tax_filing WHERE typ=? AND filed_on IS NOT NULL AND period IN (%s)" %
                    ",".join("?" * len(periods)), typ, *periods) if periods else 0
        add("Returns", text, "ok" if filed == len(periods) else "issue", "%d of %d filed" % (filed, len(periods)),
            "ZTAX_CAL", returns.TYPES[typ])
    # 4 partners
    nv = one("SELECT COUNT(DISTINCT k.lifnr) FROM acc_doc_item k JOIN acc_doc h ON h.belnr=k.belnr AND h.gjahr=k.gjahr "
             "JOIN vendor v ON v.lifnr=k.lifnr WHERE k.koart='K' AND h.budat BETWEEN ? AND ? AND COALESCE(v.land,'EG')='EG' "
             "AND COALESCE(v.stcd1,'')=''", d1, d2)
    add("Partners", "Egyptian vendors with tax registration number (form 41, e-invoice matching)",
        "ok" if not nv else "issue", "%d vendor(s) without tax number" % nv, "XK02", "Law 91/2005 art. 59")
    nc = one("SELECT COUNT(DISTINCT b.kunnr) FROM billing b JOIN customer c ON c.kunnr=b.kunnr WHERE b.fkdat BETWEEN ? AND ? "
             "AND COALESCE(c.land,'EG')='EG' AND COALESCE(c.stcd1,'')=''", d1, d2)
    add("Partners", "Egyptian business customers with tax registration number (B2B e-invoice)", "ok" if not nc else "issue",
        "%d customer(s) without tax number" % nc, "XD02", "ETA e-invoice")
    # 5 withholding and payroll
    wht = one("SELECT COALESCE(SUM(CASE WHEN i.shkzg='H' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM acc_doc_item i JOIN acc_doc h "
              "ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE i.ktosl='WIT' AND h.budat BETWEEN ? AND ?", d1, d2)
    add("Withholding", "Tax withheld from vendors in the year", "manual", "%.2f EGP - pay with form 41" % (wht / 100.0),
        "ZTAX_41", "Law 91/2005 art. 59")
    pc = rules.payroll_check(conn, d2 if d2 < today else today)["differences"]
    add("Payroll", "Payroll uses the legal rates (exemption, brackets, social insurance)", "ok" if not pc else "issue",
        "%d parameter(s) differ from the law register" % len(pc), "ZTAX_LAW", "Law 7/2024, Law 148/2019")
    # 6 assets and inventory
    na = one("SELECT COUNT(*) FROM asset WHERE COALESCE(deakt,'')=''")
    add("Assets", "Fixed asset register with cost and depreciation per asset", "ok" if na else "manual",
        "%d active asset(s); tax depreciation (Law 91/2005 art. 25) may differ from the books" % na, "AR01",
        "Law 91/2005 art. 25 - reconcile with the adviser")
    inv = one("SELECT COUNT(*) FROM inv_doc WHERE status='POST' AND substr(COALESCE(count_date,''),1,4)=?", str(y))
    add("Inventory", "Physical inventory counted and posted in the year (count sheets kept)", "ok" if inv else "issue",
        "%d count document(s)" % inv, "MI01", "Law 91/2005 - inventory valuation")
    # 7 related parties
    rp = related_parties(conn, y)
    add("Related parties", "Transfer pricing documentation if related-party transactions exceed the threshold",
        "issue" if rp["local_file"] else "ok", "%.2f EGP sales to affiliated companies (threshold %.0f)" % (
            rp["sales"] / 100.0, rp["threshold"] / 100.0), "ZTAX_AUDITFILE", "Income Tax Law art. 30")
    to_verify = one("SELECT COUNT(*) FROM tax_rule WHERE status='VERIFY' AND valid_to>=?", today)
    add("Law register", "Tax rates and rules confirmed with the tax adviser", "ok" if not to_verify else "manual",
        "%d rule(s) still to verify" % to_verify, "ZTAX_LAW", "")
    score = round(sum(1 for i in items if i["status"] == "ok") * 100.0 / len(items))
    return {"year": y, "items": items, "score": score, "issues": sum(1 for i in items if i["status"] == "issue")}


def audit_file(conn, y):
    """Excel workbook with the registers the inspector asks for"""
    from fi.gl import vat_report  # noqa: F401 - registers below use the same tax lines
    from fi.reports import trial_balance
    from fi.wht import report as wht_report
    from mm.xlsx import HEADER, TITLE, Workbook
    from . import eta, returns
    y = parse_int(y, "year", 2000, 2100)
    d1, d2 = "%04d-01-01" % y, "%04d-12-31" % y
    wb = Workbook()

    def sheet(name, title, head, rows):
        s = wb.add(name)
        s.set(0, 0, title, TITLE)
        s.row(2, head, HEADER)
        for i, r in enumerate(rows, start=3):
            s.row(i, ["" if v is None else v for v in r])
        for c in range(len(head)):
            s.widths[c] = 14
        s.widths[1] = max(s.widths.get(1, 14), 28)
        return s
    a = lambda c: round((c or 0) / 100.0, 2)                    # noqa: E731
    tb = trial_balance(conn, y, 1, 12)
    sheet("01 Trial balance", "Trial balance %d" % y, ["Account", "Name", "Opening", "Debit", "Credit", "Closing"],
          [[r["hkont"], r["txt"], r["opening"], r["debit"], r["credit"], r["closing"]] for r in tb])
    jr = conn.execute("SELECT h.belnr, h.budat, h.blart, h.xblnr, h.bktxt, i.buzei, i.hkont, i.koart, i.kunnr, i.lifnr, "
                      "i.shkzg, i.dmbtr, i.mwskz, i.sgtxt, h.usnam FROM acc_doc h JOIN acc_doc_item i ON i.belnr=h.belnr AND "
                      "i.gjahr=h.gjahr WHERE h.budat BETWEEN ? AND ? ORDER BY h.budat, h.belnr, i.buzei", (d1, d2)).fetchall()
    sheet("02 Journal", "Journal (all postings) %d" % y, ["Document", "Date", "Type", "Reference", "Text", "Line", "Account",
                                                          "Acct type", "Customer", "Vendor", "D/C", "Amount", "Tax code",
                                                          "Line text", "User"],
          [[r["belnr"], r["budat"], r["blart"], r["xblnr"], r["bktxt"], r["buzei"], r["hkont"], r["koart"], r["kunnr"],
            r["lifnr"], r["shkzg"], a(r["dmbtr"]), r["mwskz"], r["sgtxt"], r["usnam"]] for r in jr])
    sales = conn.execute("SELECT b.vbeln, b.fkdat, b.kunnr, c.name, c.stcd1, b.netwr, b.mwsbk, o.uuid, o.status FROM billing "
                         "b JOIN customer c ON c.kunnr=b.kunnr LEFT JOIN eta_out o ON o.vbeln=b.vbeln WHERE b.cancelled=0 "
                         "AND b.fkdat BETWEEN ? AND ? ORDER BY b.fkdat", (d1, d2)).fetchall()
    sheet("03 Sales VAT register", "Sales register (output VAT) %d" % y, ["Invoice", "Date", "Customer", "Name",
                                                                          "Tax no.", "Net", "VAT", "Total", "ETA UUID",
                                                                          "ETA status"],
          [[r["vbeln"], r["fkdat"], r["kunnr"], r["name"], r["stcd1"], a(r["netwr"]), a(r["mwsbk"]),
            a((r["netwr"] or 0) + (r["mwsbk"] or 0)), r["uuid"], r["status"]] for r in sales])
    pur = conn.execute("SELECT h.belnr, h.budat, h.xblnr, k.lifnr, v.name, v.stcd1, SUM(CASE WHEN t.shkzg='S' THEN t.dmbtr "
                       "ELSE -t.dmbtr END) vat, SUM(CASE WHEN t.shkzg='S' THEN t.txbase ELSE -t.txbase END) base, e.uuid, "
                       "e.status FROM acc_doc h JOIN acc_doc_item t ON t.belnr=h.belnr AND t.gjahr=h.gjahr AND t.hkont='154000' "
                       "JOIN acc_doc_item k ON k.belnr=h.belnr AND k.gjahr=h.gjahr AND k.koart='K' JOIN vendor v ON "
                       "v.lifnr=k.lifnr LEFT JOIN eta_in e ON e.belnr=h.belnr AND e.gjahr=h.gjahr WHERE h.budat BETWEEN ? "
                       "AND ? GROUP BY h.belnr, h.gjahr ORDER BY h.budat", (d1, d2)).fetchall()
    sheet("04 Purchase VAT register", "Purchase register (input VAT) %d" % y, ["Document", "Date", "Vendor invoice",
                                                                              "Vendor", "Name", "Tax no.", "Base",
                                                                              "Input VAT", "ETA UUID", "ETA status"],
          [[r["belnr"], r["budat"], r["xblnr"], r["lifnr"], r["name"], r["stcd1"], a(r["base"]), a(r["vat"]), r["uuid"],
            r["status"] or "no e-invoice"] for r in pur])
    sheet("05 Withholding register", "Withholding tax (form 41) %d" % y, ["Vendor", "Name", "Tax no.", "Code", "Rate %",
                                                                          "Base", "Withheld", "Documents"],
          [[r["lifnr"], r["name"], r.get("taxid"), r["code"], r["pct"], a(r["base"]), a(r["amount"]), r["docs"]]
           for r in wht_report(conn, d1, d2)])
    sal = [returns.salary_return(conn, y, m) for m in range(1, 13)]
    sheet("06 Salary tax register", "Salary tax %d" % y, ["Month", "Employees", "Gross", "Employee SI", "Taxable",
                                                          "Salary tax", "Martyrs' fund", "Payroll status"],
          [[s["period"], s["employees"], a(s["gross"]), a(s["si_ee"]), a(s["taxable"]), a(s["tax"]), a(s["martyrs"]),
            s["payroll"]] for s in sal if s["employees"]])
    assets = conn.execute("SELECT a.anln1, a.txt, a.anlkl, a.kostl, a.aktiv, a.ndjar, COALESCE(SUM(i.apc),0) apc, "
                          "COALESCE(SUM(i.dep),0) dep FROM asset a LEFT JOIN asset_item i ON i.anln1=a.anln1 AND i.budat<=? "
                          "GROUP BY a.anln1 ORDER BY a.anln1", (d2,)).fetchall()
    sheet("07 Fixed assets", "Fixed asset register at %s" % d2, ["Asset", "Description", "Class", "Cost center",
                                                                 "Capitalized", "Life", "Cost", "Acc. depreciation",
                                                                 "Net book value"],
          [[r["anln1"], r["txt"], r["anlkl"], r["kostl"], r["aktiv"], r["ndjar"], a(r["apc"]), a(-r["dep"]),
            a(r["apc"] + r["dep"])] for r in assets])
    out = eta.outbound(conn, d1, d2)
    sheet("08 E-invoice log", "E-invoices issued %d" % y, ["Invoice", "Date", "Customer", "Net", "ETA status", "UUID",
                                                           "Submitted", "Mode"],
          [[r["vbeln"], r["fkdat"], r["name"], a(r["netwr"]), r["eta_status"], r["uuid"], r["submitted"], r["mode"]]
           for r in out["rows"]])
    rec = revenue_reconciliation(conn, y)
    sheet("09 Revenue reconciliation", "Revenue: books = invoices = e-invoices = VAT return %d" % y,
          ["Month", "Books", "Invoices", "E-invoices valid", "VAT return base", "Books - invoices",
           "Invoices - e-invoices", "Invoices - VAT base"],
          [[r["month"], a(r["books"]), a(r["invoices"]), a(r["einvoices"]), a(r["vat_base"]), a(r["diff_books"]),
            a(r["diff_einv"]), a(r["diff_vat"])] for r in rec["rows"]])
    chk = checklist(conn, y)
    sheet("10 Audit checklist", "Audit readiness %d - score %d %%" % (y, chk["score"]),
          ["No.", "Check", "Area", "Status", "Result", "Transaction", "Law"],
          [[i["no"], i["check"], i["area"], i["status"], i["info"], i["tcode"], i["law"]] for i in chk["items"]])
    return wb.save()


def close_status(conn, y, m):
    """ZTAX_CLOSE: the tax work of a month in order"""
    from . import eta, returns
    y = parse_int(y, "year", 2000, 2100)
    m = parse_int(m, "month", 1, 12)
    d1 = "%04d-%02d-01" % (y, m)
    d2 = "%04d-%02d-%02d" % (y, m, calendar.monthrange(y, m)[1])
    period = "%04d-%02d" % (y, m)
    steps = []

    def add(step, tcode, ok, info, needed=True):
        steps.append(dict(no=len(steps) + 1, step=step, tcode=tcode, info=info,
                          status="done" if ok else ("open" if needed else "n/a")))
    out = eta.outbound(conn, d1, d2)
    bad = sum(n for s, n in out["counts"].items() if s not in ("Valid", "Cancelled"))
    add("E-invoices of the month submitted and valid", "ZTAX_EINV", bad == 0, "%d not valid at the ETA" % bad)
    rec = conn.execute("SELECT COUNT(*) FROM eta_in WHERE issued BETWEEN ? AND ?", (d1, d2)).fetchone()[0]
    add("Received e-invoices imported from the ETA portal", "ZTAX_EIN", rec > 0, "%d document(s)" % rec)
    risk = eta.input_vat_at_risk(conn, d1, d2)
    add("Input VAT backed by valid e-invoices", "ZTAX_EIN", risk["count"] == 0,
        "%d invoice(s), %.2f EGP at risk" % (risk["count"], risk["amount"] / 100.0))
    rr = [r for r in revenue_reconciliation(conn, y)["rows"] if r["month"] == period]
    add("Revenue = invoices = VAT return base", "ZTAX_REVREC", not rr or (rr[0]["diff_books"] == 0 and rr[0]["diff_vat"] == 0),
        "books - invoices %.2f / invoices - VAT base %.2f" % ((rr[0]["diff_books"] / 100.0, rr[0]["diff_vat"] / 100.0)
                                                             if rr else (0, 0)))
    pc = rules.payroll_check(conn, d2)["differences"]
    add("Payroll rates = law register", "ZTAX_LAW", not pc, "%d difference(s)" % len(pc))
    for typ, tcode, per, needed in (("VAT", "ZTAX_VAT", period, True), ("SAL", "ZTAX_SAL", period, True),
                                    ("WHT", "ZTAX_41", "%04d-Q%d" % (y, (m + 2) // 3), m % 3 == 0)):
        f = conn.execute("SELECT * FROM tax_filing WHERE typ=? AND period=?", (typ, per)).fetchone()
        add("%s filed and paid (%s)" % (returns.TYPES[typ], per), tcode, bool(f and f["paid_on"]),
            ("paid %s" % f["paid_on"]) if f and f["paid_on"] else ("filed %s - not paid" % f["filed_on"]) if f else
            "due %s" % returns._due(conn, typ, y, m), needed)
    done = sum(1 for s in steps if s["status"] == "done")
    return {"gjahr": y, "perio": m, "steps": steps, "done": done,
            "needed": sum(1 for s in steps if s["status"] != "n/a")}
