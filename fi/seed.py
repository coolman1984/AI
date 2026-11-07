"""FI demo: configuration, master data, opening balance, history of invoices
and payments, and the FI part of the sample month (A -> Z, see co/seed.py).

History (before the sample month)
  OB52 / OB08 settings, vendors & customers with payment terms and credit
  limits, AS91 legacy assets + opening balance sheet, MIRO for the purchase
  orders of the MM history, AFAB per month, billing in AR with partial
  payment and residual item, F110 payment runs.

Sample month - before CO closing (because they create costs in CO)
  FB60 vendor invoices (energy, rent, services, marketing, freight, trade
  fair), F-90 asset purchases in USD, AFAB, ABAVN scrapping, MIRO with a
  price difference, FBS1 audit fee accrual, F110 runs with cash discount,
  F-53 USD payment (realized FX loss), F-28 customer payment with discount,
  FF67 bank statement (partial payment + bank charges), salary payment.

Sample month - after CO closing
  FAGL_FCV foreign currency valuation, F.13 GR/IR clearing, FB41 VAT
  settlement, F150 dunning, then F.81 reverses accrual and valuation on the
  1st of the next month. OB52: only sample month .. current month open.
"""
import datetime

from mm import master as mmm

from . import aa, ap, ar, gl
from .ap import open_items

USER = "DEMO"


def _months_between(d1, d2):
    return (d2.year - d1.year) * 12 + d2.month - d1.month


# ====================================================================== history
def history(conn, start, anchor):
    """start = first day of the MM history month, anchor = last day before
    the sample month."""
    gl.set_periods(conn, start.year, start.month, datetime.date.today().year, 12)
    # ---------------------------------------------------------------- OB08
    rates = [(start, "47.80"), (datetime.date(anchor.year, anchor.month, 1) -
                                datetime.timedelta(days=40), "48.10"),
             (anchor.replace(day=1), "48.30")]
    for d, r in rates:
        gl.set_rate(conn, "USD", d.isoformat(), r)
    gl.set_rate(conn, "EUR", start.isoformat(), "52.00")
    # ---------------------------------------------------------------- vendors
    terms = {"100001": "Z210", "100002": "NT30", "100003": "Z210", "100004": "NT30",
             "100005": "NT30", "100006": "NT60"}
    for k, t in terms.items():
        conn.execute("UPDATE vendor SET zterm=?, akont='160000', waers='EGP', land='EG' "
                     "WHERE lifnr=?", (t, k))
    for v in [("200001", "Egyptian Electricity Distribution", "Cairo", "160000", "NT30"),
              ("200002", "Nasr City Properties", "Cairo", "160000", "0001"),
              ("200003", "Delta Facility Services", "Tanta", "160000", "Z210"),
              ("200004", "Cairo IT Solutions", "Cairo", "160000", "Z210"),
              ("200005", "Nile Media Agency", "Giza", "160000", "NT30"),
              ("200006", "Express Freight Egypt", "Cairo", "160000", "NT30"),
              ("200007", "Expo Events Co.", "Cairo", "160000", "NT30"),
              ("200008", "Mansour & Partners Audit", "Cairo", "160000", "NT30")]:
        mmm.create_vendor(conn, v[0], v[1], v[2], akont=v[3], zterm=v[4])
    mmm.create_vendor(conn, "300001", "Anatolia Machinery A.S.", "Istanbul",
                      akont="161000", zterm="NT30", waers="USD", land="TR")
    mmm.create_vendor(conn, "300002", "TechSource FZE", "Dubai", akont="161000",
                      zterm="NT60", waers="USD", land="AE")
    for k, t, lim in (("C1001", "NT30", 1500000), ("C1002", "Z210", 1200000),
                      ("C1003", "NT60", 800000)):
        conn.execute("UPDATE customer SET zterm=?, klimk=?, akont='140000', land=? WHERE "
                     "kunnr=?", (t, lim * 100, "SA" if k == "C1003" else "EG", k))
    # ---------------------------------------------------------------- assets AS91
    take = start.isoformat()
    assets = [("2000", "CNC machining line", "4100", 10, "2024-03-15", "7200000"),
              ("2000", "Assembly line equipment", "4120", 10, "2025-01-10", "727500"),
              ("3000", "Delivery truck Isuzu NPR", "4400", 5, "2025-06-20", "1200000"),
              ("4000", "Office IT equipment", "9100", 4, "2025-09-05", "240000"),
              ("4000", "Old laptop pool", "9100", 4, "2023-01-01", "36000")]
    open_lines, nr = [], []
    for cls, txt, k, life, aktiv, apc in assets:
        n = aa.create_asset(conn, cls, txt, k, life, user=USER)
        a0 = datetime.date.fromisoformat(aktiv)
        months = max(_months_between(a0, start) - 1, 0)     # from month after cap.
        monthly = int(float(apc) * 100) // (life * 12)
        accdep = min(monthly * months, int(float(apc) * 100))
        aa.legacy_transfer(conn, n, aktiv, apc, "%.2f" % (accdep / 100.0), take)
        c = __import__("fi.config", fromlist=["ASSET_CLASSES"]).ASSET_CLASSES[cls]
        open_lines += [dict(hkont=c[1], anln1=n, koart="A", anbwa="900",
                            amount=int(float(apc) * 100), sgtxt="Legacy APC " + txt),
                       dict(hkont=c[2], anln1=n, koart="A", anbwa="900", amount=-accdep,
                            sgtxt="Legacy acc. depreciation " + txt)]
        nr.append(n)
    # ---------------------------------------------------------------- opening balance
    init_stock = -conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE "
                               "-dmbtr END),0) FROM acc_doc_item WHERE hkont='399999'"
                               ).fetchone()[0]
    open_lines += [dict(hkont="113100", amount=450000000, sgtxt="Opening bank balance"),
                   dict(hkont="070000", amount=-400000000, sgtxt="Bank loan NBE"),
                   dict(hkont="399999", amount=init_stock, sgtxt="Takeover of stock"),
                   dict(hkont="080000", amount=-1000000000, sgtxt="Share capital")]
    open_lines.append(dict(hkont="081000", amount=-sum(l["amount"] for l in open_lines),
                           sgtxt="Retained earnings"))
    from .document import write
    write(conn, "AB", take, USER, "OPEN", "Opening balance sheet", open_lines, tcode="OB")
    # ---------------------------------------------------------------- MIRO history
    grs = conn.execute(
        "SELECT i.ebeln, i.ebelp, h.budat, SUM(i.menge) AS q FROM mat_doc_item i JOIN "
        "mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE i.bwart='101' AND "
        "i.ebeln IS NOT NULL AND h.budat<=? GROUP BY i.ebeln, i.ebelp, h.budat ORDER BY "
        "h.budat", (anchor.isoformat(),)).fetchall()
    for n, g in enumerate(grs):
        d = datetime.date.fromisoformat(g["budat"])
        if (anchor - d).days < 10:
            continue                                    # invoice not received yet
        po = conn.execute("SELECT * FROM po_item WHERE ebeln=? AND ebelp=?",
                          (g["ebeln"], g["ebelp"])).fetchone()
        from mm.util import value_of
        net = value_of(g["q"], po["netpr"], po["peinh"])
        if n % 4 == 3:
            net = net * 1015 // 1000                    # supplier charged +1.5 %
        inv = (d + datetime.timedelta(days=3)).isoformat()
        ap.miro(conn, {"ebeln": g["ebeln"], "bldat": inv, "budat": inv,
                       "xblnr": "INV-%s" % g["ebeln"][-4:], "mwskz": "V1"},
                [{"ebelp": g["ebelp"], "qty": str(g["q"] / 1000.0),
                  "amount": "%.2f" % (net / 100.0)}], USER)
    # ---------------------------------------------------------------- AFAB history
    y, m = start.year, start.month
    while (y, m) <= (anchor.year, anchor.month):
        aa.depreciation_run(conn, y, m, USER, test=False)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    # ---------------------------------------------------------------- AR history
    from co import copa
    a1 = anchor.replace(day=1)
    aug = (a1 - datetime.timedelta(days=20)).replace(day=12)
    copa.create_billing(conn, {"kunnr": "C1002", "fkdat": aug.isoformat(), "items": [
        dict(matnr="FG-3001", qty="20", price="4200", disc="8", lgort="0003"),
        dict(matnr="FG-3002", qty="30", price="2600", disc="8", lgort="0003")]}, USER)
    copa.create_billing(conn, {"kunnr": "C1001", "fkdat": a1.replace(day=10).isoformat(),
                               "items": [dict(matnr="FG-3001", qty="15", price="4200",
                                              lgort="0003"),
                                         dict(matnr="FG-3002", qty="25", price="2600",
                                              lgort="0003")]}, USER)
    copa.create_billing(conn, {"kunnr": "C1003", "fkdat": a1.replace(day=18).isoformat(),
                               "items": [dict(matnr="FG-3002", qty="20", price="2500",
                                              lgort="0003")]}, USER)
    items = [(r["belnr"], r["gjahr"], r["buzei"]) for r in open_items(conn, "D", "C1002")]
    ap.pay(conn, "D", "C1002", a1.replace(day=20).isoformat(), items, USER,
           amount="120000", residual=True, take_discount=False)
    # ---------------------------------------------------------------- F110 + FB41
    import calendar
    y, m = start.year, start.month
    while (y, m) <= (anchor.year, anchor.month):
        laufd = datetime.date(y, m, 25)
        ap.payment_run(conn, laufd.isoformat(), "M%02d" % m,
                       (laufd + datetime.timedelta(days=14)).isoformat(), USER,
                       execute=True)
        e = datetime.date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        try:
            gl.vat_settlement(conn, "%04d-%02d-01" % (y, m), e, e, USER)
        except Exception:
            pass                                    # no tax in that month
        m += 1
        if m > 12:
            y, m = y + 1, 1
    # migration clearing: production output booked before CO go-live
    out = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr "
                       "END),0) FROM acc_doc_item WHERE hkont='399990'").fetchone()[0]
    if out:
        write(conn, "SA", anchor.isoformat(), USER, "OPEN", "Takeover production output",
              [dict(hkont="399990", amount=-out, sgtxt="Clearing receipts w/o PO"),
               dict(hkont="081000", amount=out, sgtxt="Takeover production output")])


# ====================================================================== sample month
def sample_before_closing(conn, y, p, internal_order, paint_po):
    d = lambda day: datetime.date(y, p, day).isoformat()   # noqa: E731
    import calendar
    eom = d(calendar.monthrange(y, p)[1])
    gl.set_rate(conn, "USD", d(1), "48.50")
    gl.set_rate(conn, "USD", d(20), "49.20")
    gl.set_rate(conn, "USD", eom, "49.80")
    inv = lambda lifnr, day, lines, ref, text, code="V1": ap.vendor_invoice(  # noqa: E731
        conn, {"lifnr": lifnr, "bldat": d(day), "budat": d(day), "xblnr": ref,
               "bktxt": text, "mwskz": code},
        [dict(hkont=h, amount=a, kostl=k, aufnr=o, sgtxt=text) for h, a, k, o in lines],
        USER)
    inv("200001", 10, [("450000", "21800", "4210", None)], "EE-%02d%s" % (p, y), "Electricity")
    inv("200002", 1, [("460000", "30000", "9900", None)], "RENT-%02d" % p, "Factory rent",
        "V0")
    inv("200003", 10, [("475000", "5400", "4100", None), ("475000", "4600", "4200", None)],
        "DFS-881", "Maintenance services")
    inv("200004", 10, [("476000", "11200", "9100", None)], "CIT-2207", "IT services")
    inv("200005", 10, [("477000", "18500", "8100", None)], "NMA-512", "Marketing campaign")
    inv("200006", 10, [("478000", "5900", "8100", None)], "EXF-77", "Freight out")
    inv("200007", 16, [("477000", "12000", None, internal_order)], "EXPO-26",
        "Trade fair booth")
    # assets bought in USD (depreciation starts next month)
    laser = aa.create_asset(conn, "2000", "Fiber laser cutter 3 kW", "4100", 10, user=USER)
    aa.acquire(conn, laser, d(6), "20000", USER, lifnr="300001", mwskz="V0",
               xblnr="AM-2026-114", text="Fiber laser cutter")
    server = aa.create_asset(conn, "4000", "Application server", "9100", 4, user=USER)
    aa.acquire(conn, server, d(12), "3000", USER, lifnr="300002", mwskz="V0",
               xblnr="TS-55021", text="Application server")
    # depreciation of the month, then scrapping of the old laptops
    aa.depreciation_run(conn, y, p, USER, test=False)
    old = conn.execute("SELECT anln1 FROM asset WHERE txt='Old laptop pool'").fetchone()
    aa.retire(conn, old["anln1"], eom, USER, text="Scrapping old laptops")
    # invoice verification with a price difference (196 instead of 195 per L)
    ap.miro(conn, {"ebeln": paint_po, "bldat": d(26), "budat": d(26), "xblnr": "PP-9031",
                   "mwskz": "V1"}, [{"ebelp": 10, "qty": "300", "amount": "58800"}], USER)
    # audit fee accrual (reversed on the 1st of next month)
    nxt = (datetime.date.fromisoformat(eom) + datetime.timedelta(days=1)).isoformat()
    gl.accrual(conn, eom, nxt, [dict(hkont="479500", debit="15000", kostl="9100"),
                                dict(hkont="190000", credit="15000")],
               "Accrual audit fee", USER)
    # payment runs (15th) - USD payment (20th) - payment run (29th)
    ap.payment_run(conn, d(15), "PR1", d(29), USER, execute=True)
    # USD invoice of the laser cutter paid at a higher rate -> FX loss
    items = [(r["belnr"], r["gjahr"], r["buzei"]) for r in open_items(conn, "K", "300001")]
    ap.pay(conn, "K", "300001", d(20), items, USER, bktxt="Transfer USD Anatolia")

    ap.payment_run(conn, d(29), "PR2", (datetime.date.fromisoformat(d(29)) +
                                        datetime.timedelta(days=14)).isoformat(),
                   USER, execute=True)
    # customer C1002 pays the invoice of this month within 10 days -> 2 % discount
    it = [r for r in open_items(conn, "D", "C1002") if r["budat"] >= d(1) and
          r["shkzg"] == "S"]
    ap.pay(conn, "D", "C1002", d(30), [(r["belnr"], r["gjahr"], r["buzei"]) for r in it],
           USER, bktxt="Payment Delta Kitchens")
    # salaries paid
    from co.fi import post_gl_document
    post_gl_document(conn, {"budat": eom, "bktxt": "Salary transfer"}, [
        dict(hkont="176000", debit="221700"), dict(hkont="113100", credit="221700")], USER)
    # bank statement: C1001 pays part of the old invoice, bank charges
    sep = [r for r in open_items(conn, "D", "C1001") if r["budat"] < d(1)]
    bal = __import__("fi.reports", fromlist=["gl_balance"]).gl_balance(conn, "113100", eom)
    gl.bank_statement(conn, "NBE", eom, "%02d/%s" % (p, y), "%.2f" % (bal / 100.0),
                      "%.2f" % ((bal + 10000000 - 35000) / 100.0),
                      [dict(type="D", amount="100000", kunnr="C1001", ref=sep[0]["belnr"],
                            text="Cairo Home Center"),
                       dict(type="CHG", amount="-350", text="Bank charges")], USER)


def sample_after_closing(conn, y, p):
    import calendar
    eom = datetime.date(y, p, calendar.monthrange(y, p)[1])
    nxt = eom + datetime.timedelta(days=1)
    gl.fx_valuation(conn, eom.isoformat(), USER, test=False)
    gl.grir_clearing(conn, eom.isoformat(), USER, test=False)
    gl.vat_settlement(conn, datetime.date(y, p, 1).isoformat(), eom.isoformat(),
                      eom.isoformat(), USER)
    ar.dunning_run(conn, eom.isoformat(), USER, execute=True)
    gl.reverse_accruals(conn, nxt.isoformat(), nxt.isoformat(), USER)
    today = datetime.date.today()
    gl.set_periods(conn, y, p, today.year, today.month)
