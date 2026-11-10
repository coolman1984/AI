"""General ledger, bank, tax and closing functions.

FS00        G/L account master          OB52  open / close posting periods
OB08        exchange rates              F-02  general posting with posting keys
FB08        reverse document            FBS1  accrual with reversal date
F.81        reverse accruals            FAGL_FCV foreign currency valuation
F.13        automatic GR/IR clearing    FB41  VAT settlement (tax payable)
FF67        manual bank statement (incoming payments + bank charges)
"""
import datetime

from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date

from .ap import open_items, pay
from .config import (CHART, FX_ACCOUNTS, LOCAL_CURRENCY, POSTING_KEYS, TAX_CODES,
                     VAT_PAYABLE)
from .document import RATE_SCALE, rate, signed, signed_fc, to_local, write


# ---------------------------------------------------------------- FS00
def save_gl_account(conn, hkont, txt, typ, fsv, recon="", oi=0, tax="", blocked=0):
    hkont = (hkont or "").strip()
    if not hkont.isdigit() or len(hkont) != 6:
        raise MMError("G/L account number must have 6 digits", "FH", "001")
    if typ not in ("BS", "PL"):
        raise MMError("Account type must be BS (balance sheet) or PL (profit & loss)")
    with transaction(conn):
        conn.execute("INSERT INTO gl_account (hkont,txt,typ,fsv,recon,oi,tax,blocked) VALUES "
                     "(?,?,?,?,?,?,?,?) ON CONFLICT(hkont) DO UPDATE SET txt=excluded.txt,"
                     " fsv=excluded.fsv, oi=excluded.oi, tax=excluded.tax, "
                     "blocked=excluded.blocked", (hkont, txt, typ, fsv, recon or "",
                                                  int(oi), tax or "", int(blocked)))
    from mm.config import GL_ACCOUNTS, PNL_ACCOUNTS
    GL_ACCOUNTS[hkont] = txt
    if typ == "PL":
        PNL_ACCOUNTS.add(hkont)


# ---------------------------------------------------------------- F.16
def carry_forward(conn, gjahr, user, test=False):
    """F.16 / FAGLGVTR: carry the P&L result of gjahr forward to retained earnings.
    The balance itself is always derived from the postings (reports stay correct even
    for late postings into a closed year); the run confirms the year and is repeatable."""
    from mm import util
    from .reports import RETAINED_EARNINGS, _accounts, _sums
    gjahr = int(gjahr)
    if gjahr >= util.today().year:
        raise MMError("Fiscal year %s is not yet over" % gjahr, "F5", "210")
    accs = _accounts(conn)
    sums = _sums(conn, "%04d-01-01" % gjahr, "%04d-12-31" % gjahr)
    rows = [dict(hkont=k, txt=accs[k]["txt"], balance=(dc[0] - dc[1]) / 100.0)
            for k, dc in sorted(sums.items()) if accs.get(k, {}).get("typ") == "PL" and dc[0] != dc[1]]
    amount = sum(int(round(r["balance"] * 100)) for r in rows)
    if not test:
        with transaction(conn):
            conn.execute("INSERT OR REPLACE INTO fi_carry_forward (gjahr,amount,hkont,run_at,usnam) "
                         "VALUES (?,?,?,?,?)", (gjahr, amount, RETAINED_EARNINGS, now_ts(), user))
    return {"gjahr": gjahr, "to_year": gjahr + 1, "account": RETAINED_EARNINGS, "test": test,
            "result": -amount / 100.0, "accounts": rows,
            "message": "Balance carried forward from %s to %s: result %.2f to account %s"
                       % (gjahr, gjahr + 1, -amount / 100.0, RETAINED_EARNINGS)}


# ---------------------------------------------------------------- OB52 / OB08
def set_periods(conn, y1, p1, y2, p2):
    if (int(y1), int(p1)) > (int(y2), int(p2)):
        raise MMError("Period interval is not valid", "F5", "205")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO posting_period VALUES (1,?,?,?,?)",
                     (int(y1), int(p1), int(y2), int(p2)))


def set_rate(conn, waers, gdatu, ukurs):
    gdatu = parse_date(gdatu)
    v = float(str(ukurs).replace(",", "."))
    if v <= 0:
        raise MMError("Exchange rate must be positive", "SG", "100")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO exch_rate VALUES (?,?,?)",
                     (waers.upper(), gdatu, int(round(v * RATE_SCALE))))


# ---------------------------------------------------------------- F-02
def general_posting(conn, header, lines, user):
    """lines: [{bschl, account, amount, kostl, aufnr, sgtxt}] posting keys
    40/50 G/L, 01/11/15 customer, 21/31/25 vendor."""
    budat = parse_date(header.get("budat"))
    blart = (header.get("blart") or "SA").upper()
    acc = []
    for n, l in enumerate(lines, start=1):
        k = str(l.get("bschl") or "").strip()
        pk = POSTING_KEYS.get(k)
        if not pk or pk[1] not in "SKD":
            raise MMError("Line %d: posting key %s is not allowed here" % (n, k), "F5", "103")
        amt = parse_amount(l.get("amount"))
        sign = 1 if pk[2] == "S" else -1
        a = str(l.get("account") or "").strip().upper()
        line = dict(amount=sign * amt, sgtxt=l.get("sgtxt") or "", kostl=l.get("kostl"),
                    aufnr=l.get("aufnr"))
        if pk[1] == "K":
            line.update(lifnr=a, koart="K")
        elif pk[1] == "D":
            line.update(kunnr=a, koart="D")
        else:
            line.update(hkont=a)
        acc.append(line)
    with transaction(conn):
        return write(conn, blart, budat, user, "F-02", header.get("bktxt") or "", acc,
                     bldat=header.get("bldat"), xblnr=header.get("xblnr"), tcode="F-02")


# ---------------------------------------------------------------- FB08
def reverse(conn, belnr, gjahr, budat=None, reason="01", user=""):
    with transaction(conn):
        h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?",
                         (belnr, gjahr)).fetchone()
        if not h:
            raise MMError("Document %s %s does not exist" % (belnr, gjahr), "F5", "800")
        if h["stblg"]:
            raise MMError("Document %s was already reversed by %s" % (belnr, h["stblg"]),
                          "F5", "805")
        if h["awkey"] and (h["awkey"][:2] in ("49",) or h["tcode"] in (
                "MIGO", "VF01", "MIRO", "AFAB", "F110") or h["blart"] in ("WE", "WA", "RV",
                                                                          "RE", "AF")):
            raise MMError("Document %s comes from %s - reverse it there (MBST, VF11, "
                          "MR8M, AFAB repeat)" % (belnr, h["tcode"] or h["blart"]),
                          "F5", "807")
        items = conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=? ORDER "
                             "BY buzei", (belnr, gjahr)).fetchall()
        if any(i["augbl"] for i in items):
            raise MMError("Document %s contains cleared items - reset clearing first "
                          "(FBRA)" % belnr, "F5", "806")
        budat = parse_date(budat or h["budat"])
        lines = []
        for i in items:
            lines.append(dict(hkont=i["hkont"], amount=-signed(i), wrbtr=-signed_fc(i),
                              koart=i["koart"], lifnr=i["lifnr"], kunnr=i["kunnr"],
                              anln1=i["anln1"], anbwa=i["anbwa"], mwskz=i["mwskz"],
                              txbase=i["txbase"], kostl=i["kostl"], aufnr=i["aufnr"],
                              paobj=i["paobj"], matnr=i["matnr"], werks=i["werks"],
                              zfbdt=i["zfbdt"], zterm=i["zterm"], ktosl=i["ktosl"],
                              sgtxt="Reversal %s" % belnr))
        new = write(conn, h["blart"], budat, user, "FB08", "Reversal of %s" % belnr, lines,
                    xblnr=h["xblnr"], waers=h["waers"], kursf=h["kursf"], tcode="FB08")
        conn.execute("UPDATE acc_doc SET stblg=?, stgrd=? WHERE belnr=? AND gjahr=?",
                     (new, reason, belnr, gjahr))
        conn.execute("UPDATE acc_doc SET stblg=?, stgrd=? WHERE belnr=? AND gjahr=?",
                     (belnr, reason, new, int(budat[:4])))
        # open items of both documents clear each other
        for i in items:
            if i["koart"] in ("K", "D") or (CHART.get(i["hkont"], ("", "", "", "", 0))[4]):
                conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND "
                             "gjahr=? AND buzei=?", (new, budat, belnr, gjahr, i["buzei"]))
                conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND "
                             "gjahr=? AND buzei=?", (new, budat, new, int(budat[:4]),
                                                     i["buzei"]))
        # asset values and CO-PA follow the reversal
        conn.execute("INSERT INTO asset_item (anln1,belnr,gjahr,perio,budat,bwasl,apc,dep,"
                     "txt) SELECT anln1, ?, ?, ?, ?, bwasl, -apc, -dep, 'Reversal' FROM "
                     "asset_item WHERE belnr=?", (new, int(budat[:4]), int(budat[5:7]),
                                                  budat, belnr))
        from co.period_end import _reverse_copa
        _reverse_copa(conn, belnr, user)
    return new


# ---------------------------------------------------------------- FBS1 / F.81
def accrual(conn, budat, stodt, lines, text, user):
    """FBS1: accrual document with a planned reversal date."""
    budat, stodt = parse_date(budat), parse_date(stodt)
    if stodt <= budat:
        raise MMError("Reversal date must be after the posting date", "F5", "810")
    acc = [dict(hkont=l["hkont"], amount=parse_amount(l["debit"]) if l.get("debit")
                else -parse_amount(l["credit"]), kostl=l.get("kostl"),
                aufnr=l.get("aufnr"), sgtxt=text) for l in lines]
    with transaction(conn):
        belnr = write(conn, "SA", budat, user, "FBS1", text, acc, tcode="FBS1")
        conn.execute("UPDATE acc_doc SET stodt=? WHERE belnr=? AND gjahr=?",
                     (stodt, belnr, int(budat[:4])))
    return belnr


def reverse_accruals(conn, d1, d2, user):
    """F.81: reverse all documents whose planned reversal date is in [d1, d2]."""
    d1, d2 = parse_date(d1), parse_date(d2)
    out = []
    with transaction(conn):
        for h in conn.execute("SELECT * FROM acc_doc WHERE stodt BETWEEN ? AND ? AND "
                              "stblg IS NULL ORDER BY belnr", (d1, d2)).fetchall():
            out.append(dict(belnr=h["belnr"], reversal=reverse(conn, h["belnr"], h["gjahr"],
                                                               h["stodt"], "05", user),
                            budat=h["stodt"], text=h["bktxt"]))
    return out


# ---------------------------------------------------------------- FAGL_FCV
def fx_valuation(conn, key_date, user, test=True):
    """Value open vendor / customer items in foreign currency at the key date
    rate. Posting is reversed on the next day (via F.81)."""
    key_date = parse_date(key_date)
    out, lines = [], []
    with transaction(conn):
        for koart in ("K", "D"):
            for r in open_items(conn, koart, key_date=key_date):
                if (r["waers"] or LOCAL_CURRENCY) == LOCAL_CURRENCY:
                    continue
                k = rate(conn, r["waers"], key_date)
                new_lc = to_local(signed_fc(r), k)
                diff = new_lc - signed(r)
                if not diff:
                    continue
                out.append(dict(koart=koart, partner=r["lifnr"] or r["kunnr"],
                                belnr=r["belnr"], waers=r["waers"],
                                amount_fc=signed_fc(r) / 100.0, booked=signed(r) / 100.0,
                                rate=k / RATE_SCALE, valued=new_lc / 100.0,
                                difference=diff / 100.0))
                adj = FX_ACCOUNTS["adjust_K"] if koart == "K" else FX_ACCOUNTS["adjust_D"]
                lines.append(dict(hkont=FX_ACCOUNTS["valuation"], amount=-diff,
                                  sgtxt="FX valuation %s" % r["belnr"]))
                lines.append(dict(hkont=adj, amount=diff,
                                  sgtxt="FX valuation %s" % r["belnr"]))
        belnr = None
        if lines and not test:
            next_day = (datetime.date.fromisoformat(key_date) +
                        datetime.timedelta(days=1)).isoformat()
            belnr = write(conn, "SA", key_date, user, "FAGL_FCV",
                          "FX valuation %s" % key_date, lines, tcode="FAGL_FCV")
            conn.execute("UPDATE acc_doc SET stodt=? WHERE belnr=? AND gjahr=?",
                         (next_day, belnr, int(key_date[:4])))
    return {"belnr": belnr, "test": test, "lines": out,
            "total": sum(o["difference"] for o in out)}


# ---------------------------------------------------------------- F.13
def grir_clearing(conn, budat, user, test=True):
    """Clear GR/IR open items per purchase order item when GR = IR."""
    budat = parse_date(budat)
    groups = {}
    for r in conn.execute("SELECT i.* FROM acc_doc_item i JOIN acc_doc h ON h.belnr="
                          "i.belnr AND h.gjahr=i.gjahr WHERE i.hkont='191100' AND "
                          "i.augbl IS NULL AND h.budat<=?", (budat,)).fetchall():
        groups.setdefault(r["zuonr"] or "-", []).append(r)
    out = []
    with transaction(conn):
        for key, items in sorted(groups.items()):
            bal = sum(signed(i) for i in items)
            out.append(dict(zuonr=key, items=len(items), balance=bal / 100.0,
                            cleared=bal == 0 and key != "-"))
        if not test and any(o["cleared"] for o in out):
            augbl = str(next_number(conn, "FI_01"))
            conn.execute("INSERT INTO acc_doc (belnr,gjahr,blart,budat,usnam,awkey,bktxt,"
                         "waers,monat,tcode,bldat) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (augbl, int(budat[:4]), "AB", budat, user, "F.13",
                          "Automatic clearing GR/IR", LOCAL_CURRENCY, int(budat[5:7]),
                          "F.13", budat))
            for o in out:
                if o["cleared"]:
                    for i in groups[o["zuonr"]]:
                        conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE "
                                     "belnr=? AND gjahr=? AND buzei=?",
                                     (augbl, budat, i["belnr"], i["gjahr"], i["buzei"]))
            return {"augbl": augbl, "lines": out, "test": False}
    return {"augbl": None, "lines": out, "test": test}


# ---------------------------------------------------------------- VAT
def vat_report(conn, d1, d2):
    """S_ALR_87012357: tax base and tax per tax code."""
    out = {}
    for r in conn.execute("SELECT i.mwskz, i.shkzg, i.dmbtr, i.txbase, i.hkont FROM "
                          "acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND "
                          "h.gjahr=i.gjahr WHERE i.hkont IN ('154000','175000') AND "
                          "i.mwskz IS NOT NULL AND h.budat BETWEEN ? AND ? AND "
                          "COALESCE(h.tcode,'')<>'FB41'", (d1, d2)):
        t = TAX_CODES[r["mwskz"]]
        o = out.setdefault(r["mwskz"], dict(mwskz=r["mwskz"], text=t[0], typ=t[2],
                                            base=0, tax=0, pct=t[1] / 100.0))
        sgn = 1 if r["shkzg"] == "S" else -1
        o["tax"] += sgn * r["dmbtr"]
        o["base"] += sgn * (r["txbase"] or 0)
    rows = list(out.values())
    for r in rows:                      # output tax is a credit: show positive
        if r["typ"] == "O":
            r["tax"], r["base"] = -r["tax"], -r["base"]
    out_tax = sum(r["tax"] for r in rows if r["typ"] == "O")
    in_tax = sum(r["tax"] for r in rows if r["typ"] == "I")
    return {"rows": rows, "output": out_tax, "input": in_tax, "payable": out_tax - in_tax}


def vat_settlement(conn, d1, d2, budat, user):
    """FB41: move output and input tax of the period to the tax payable account."""
    rep = vat_report(conn, d1, d2)
    if not rep["output"] and not rep["input"]:
        raise MMError("No tax postings in the period", "FF", "010")
    lines = [dict(hkont="175000", amount=rep["output"], sgtxt="VAT settlement output"),
             dict(hkont="154000", amount=-rep["input"], sgtxt="VAT settlement input"),
             dict(hkont=VAT_PAYABLE, amount=-(rep["output"] - rep["input"]),
                  sgtxt="VAT payable %s - %s" % (d1, d2))]
    with transaction(conn):
        return write(conn, "SA", parse_date(budat), user, "FB41",
                     "VAT settlement %s" % d1[:7], lines, tcode="FB41")


# ---------------------------------------------------------------- FF67
def bank_statement(conn, hbkid, azdat, aznum, opening, closing, lines, user):
    """lines: [{type: 'D' incoming customer payment | 'CHG' bank charges,
    amount (+ in / - out), kunnr, ref (document / reference), text}]"""
    azdat = parse_date(azdat)
    op, cl = parse_amount(opening, allow_zero=True), parse_amount(closing, allow_zero=True)
    total = sum((1 if float(str(l["amount"]).replace(",", "")) >= 0 else -1) *
                parse_amount(str(l["amount"]).lstrip("-")) for l in lines)
    if op + total != cl:
        raise MMError("Opening balance %.2f + statement lines %.2f <> closing balance "
                      "%.2f" % (op / 100.0, total / 100.0, cl / 100.0), "FV", "010")
    docs = []
    with transaction(conn):
        for l in lines:
            amt = parse_amount(str(l["amount"]).lstrip("-"))
            if l["type"] == "D":
                ref = (l.get("ref") or "").strip()
                items = [r for r in open_items(conn, "D", l["kunnr"])
                         if r["shkzg"] == "S" and (not ref or ref in (
                             r["belnr"], r["xblnr"], (r["awkey"] or "")[2:]))]
                if not items:
                    raise MMError("Statement line %s: no open item of customer %s with "
                                  "reference %s" % (l.get("text") or "", l["kunnr"], ref),
                                  "FV", "020")
                due = sum(signed(r) for r in items)
                r = pay(conn, "D", l["kunnr"], azdat, [(i["belnr"], i["gjahr"], i["buzei"])
                                                       for i in items], user,
                        amount="%.2f" % (amt / 100.0), residual=amt < due,
                        take_discount=False, bktxt="Bank statement %s" % aznum,
                        tcode="FF67")
                docs.append(r["belnr"])
            elif l["type"] == "CHG":
                docs.append(write(conn, "SA", azdat, user, "FF67", "Bank charges %s" % aznum,
                                  [dict(hkont="479000", amount=amt, sgtxt=l.get("text")),
                                   dict(hkont="113100", amount=-amt, sgtxt=l.get("text"))],
                                  tcode="FF67"))
            else:
                raise MMError("Unknown statement line type %s" % l["type"], "FV", "030")
        conn.execute("INSERT INTO bank_statement (hbkid,azdat,aznum,ssbtr,esbtr,lines,docs,"
                     "usnam,ts) VALUES (?,?,?,?,?,?,?,?,?)",
                     (hbkid, azdat, aznum, op, cl, str(lines), ",".join(docs), user, now_ts()))
    return {"docs": docs, "message": "Bank statement %s posted: %d documents"
            % (aznum, len(docs))}
