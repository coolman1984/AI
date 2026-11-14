"""FI closing management (1-5 ZFI_CLOSE): every month-end step of Accounting in the order it
should run, with its status - recurring entries, parked documents, cheques due, accrual
reversals, depreciation, FX valuation, GR/IR, VAT return, financial statements, period."""
import calendar

from mm.util import parse_int


def status(conn, gjahr, perio):
    gjahr = parse_int(gjahr, "fiscal year", 2000, 2100)
    perio = parse_int(perio, "period", 1, 12)
    p1 = "%04d-%02d-01" % (gjahr, perio)
    p2 = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    steps = []

    def add(step, tcode, done, info, needed=True):
        steps.append(dict(no=len(steps) + 1, step=step, tcode=tcode,
                          status="done" if done else ("open" if needed else "n/a"), info=info))
    one = lambda sql, a: conn.execute(sql, a).fetchone()[0]                # noqa: E731
    due = one("SELECT COUNT(*) FROM fi_recurring WHERE active=1 AND first<=? AND (last='' OR last IS NULL OR "
              "last>=?)", (p2, p1))
    ran = one("SELECT COUNT(*) FROM fi_recurring_run WHERE gjahr=? AND perio=?", (gjahr, perio))
    add("Recurring entries", "F.14", ran >= due and due > 0, "%d due, %d posted" % (due, ran), due > 0)
    parked = one("SELECT COUNT(*) FROM fi_parked WHERE status='P' AND budat<=?", (p2,))
    add("Parked documents", "FBV0", parked == 0, "%d waiting for posting" % parked)
    chq = one("SELECT COUNT(*) FROM fi_cheque WHERE status IN ('REC','ISS') AND due<=?", (p2,))
    add("Cheques due (collect / cashed)", "ZCHQ", chq == 0, "%d cheque(s) due and still open" % chq)
    acr = one("SELECT COUNT(*) FROM acc_doc WHERE tcode='FBS1' AND stodt BETWEEN ? AND ? AND stblg IS NULL",
              (p1, p2))
    add("Accrual reversals", "F.81", acr == 0, "%d accrual document(s) to reverse in the period" % acr)
    assets = one("SELECT COUNT(*) FROM asset", ())
    dep = one("SELECT COUNT(*) FROM acc_doc WHERE tcode='AFAB' AND budat BETWEEN ? AND ? AND stblg IS NULL", (p1, p2))
    add("Depreciation run", "AFAB", dep > 0, "%d document(s)" % dep, assets > 0)
    fx = one("SELECT COUNT(*) FROM fx_run WHERE key_date BETWEEN ? AND ?", (p1, p2))
    add("Foreign currency valuation", "FAGL_FCV", fx > 0, "%d run(s)" % fx)
    gr = one("SELECT COUNT(*) FROM grir_run WHERE budat BETWEEN ? AND ?", (p1, p2))
    add("GR/IR clearing", "F.13", gr > 0, "%d run(s)" % gr)
    vat = one("SELECT COUNT(*) FROM vat_run WHERE d1<=? AND d2>=?", (p2, p1))
    add("VAT return", "FB41", vat > 0, "%d settlement(s)" % vat)
    try:
        from fi.reports import statements
        st = statements(conn, gjahr, perio, perio)
        add("Financial statements balanced", "F.01", st["balanced"], "assets = equity and liabilities"
            if st["balanced"] else "not balanced")
    except Exception as e:  # noqa - shown in the cockpit
        add("Financial statements balanced", "F.01", False, str(e))
    from fi.document import period_open
    is_open = period_open(conn, p2)
    add("Posting period", "OB52", not is_open, "open for postings" if is_open else "closed")
    done = sum(1 for s in steps if s["status"] == "done")
    needed = sum(1 for s in steps if s["status"] != "n/a")
    return {"gjahr": gjahr, "perio": perio, "steps": steps, "done": done, "needed": needed,
            "message": "%d of %d closing steps done for %02d/%04d" % (done, needed, perio, gjahr)}
