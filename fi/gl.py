"""General ledger, bank, tax and closing functions.

FS00        G/L account master          OB52  open / close posting periods
OB08        exchange rates              F-02  general posting with posting keys
FB08        reverse document            FBS1  accrual with reversal date
F.81        reverse accruals            FAGL_FCV foreign currency valuation
F.13        automatic GR/IR clearing    FB41  VAT settlement (tax payable)
FF67        manual bank statement (incoming payments + bank charges)
"""
import datetime
import json

from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_key, parse_rate

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
    v = parse_rate(ukurs)
    waers = parse_key(waers, "currency")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO exch_rate VALUES (?,?,?)", (waers, gdatu, v))


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
SOURCE_REVERSAL = {"MIGO": "MBST", "VL02N": "VL09", "CO27": "MBST", "CO11N": "CO13",
                   "VF01": "VF11", "MIRO": "MR8M", "AFAB": "AFAB reversal (ZAFAB_REV)",
                   "F-90": "ABAVN", "ABZON": "ABAVN", "F-92": "-", "ABAVN": "-"}


def reverse(conn, belnr, gjahr, budat=None, reason="01", user="", _from_source=False):
    gjahr = int(gjahr)
    with transaction(conn):
        h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?",
                         (belnr, gjahr)).fetchone()
        if not h:
            raise MMError("Document %s %s does not exist" % (belnr, gjahr), "F5", "800")
        if h["stblg"]:
            raise MMError("Document %s was already reversed by %s" % (belnr, h["stblg"]),
                          "F5", "805")
        src = h["tcode"] or ""
        if not _from_source and (src in SOURCE_REVERSAL or (h["awkey"] or "")[:2] == "49" or
                                 h["blart"] in ("WE", "WA", "RV", "RE")):
            raise MMError("Document %s comes from %s - reverse it there (%s)"
                          % (belnr, src or h["blart"], SOURCE_REVERSAL.get(src, "source document")),
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


# ---------------------------------------------------------------- FBRA
def reset_clearing(conn, augbl, gjahr, user, reverse_doc=False, budat=None):
    """FBRA: reopen all items cleared by clearing document augbl; with reverse_doc the
    clearing document itself (payment, manual clearing) is reversed as well."""
    gjahr = int(gjahr)
    with transaction(conn):
        items = conn.execute("SELECT i.*, h.tcode FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr "
                             "AND h.gjahr=i.gjahr WHERE i.augbl=?", (augbl,)).fetchall()
        if not items:
            raise MMError("No items are cleared with document %s" % augbl, "F5", "821")
        h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?", (augbl, gjahr)).fetchone()
        if h and h["tcode"] in ("MR8M", "FB08", "VF11") or (h and h["stblg"]):
            raise MMError("Clearing %s comes from a reversal - it cannot be reset" % augbl,
                          "F5", "822")
        # a residual item created by this payment must still be open
        for r in conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=? AND rebzg IS NOT "
                              "NULL", (augbl, gjahr)).fetchall():
            if r["augbl"]:
                raise MMError("Residual item of %s is cleared by %s - reset that clearing first"
                              % (augbl, r["augbl"]), "F5", "820")
        conn.execute("UPDATE acc_doc_item SET augbl=NULL, augdt=NULL WHERE augbl=?", (augbl,))
        rev = None
        if reverse_doc:
            if not h:
                raise MMError("%s is a clearing number without document - nothing to reverse"
                              % augbl, "F5", "823")
            rev = reverse(conn, augbl, gjahr, budat or h["budat"], "01", user, _from_source=True)
        pr = conn.execute("SELECT * FROM payrun WHERE ','||docs||',' LIKE ?", ("%," + augbl + ",%",)
                          ).fetchone()
        if pr:
            conn.execute("UPDATE payrun SET status='PAID/RESET' WHERE laufd=? AND laufi=?",
                         (pr["laufd"], pr["laufi"]))
        conn.execute("UPDATE vat_run SET belnr=belnr||' (reset)' WHERE belnr=?", (augbl,))
        conn.execute("DELETE FROM vat_run WHERE belnr=? ", (augbl,))
        from md.changes import log
        log(conn, "BELEG", "%s/%s" % (augbl, gjahr), "FBRA", user,
            [("BSEG", augbl, "augbl", augbl, "reset" + (" + reversed %s" % rev if rev else ""))])
    return {"augbl": augbl, "reopened": len(items), "reversal": rev,
            "message": "Clearing %s reset: %d items open again%s" % (
                augbl, len(items), ", document reversed by %s" % rev if rev else "")}


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
        if not test:
            prev = conn.execute("SELECT * FROM fx_run WHERE key_date=?", (key_date,)).fetchone()
            if prev and prev["belnr"] and not prev["reversal"]:
                raise MMError("Key date %s was already valued (document %s) - reverse it first"
                              % (key_date, prev["belnr"]), "F5", "830")
        if lines and not test:
            next_day = (datetime.date.fromisoformat(key_date) +
                        datetime.timedelta(days=1)).isoformat()
            belnr = write(conn, "SA", key_date, user, "FAGL_FCV",
                          "FX valuation %s" % key_date, lines, tcode="FAGL_FCV")
            gj = int(key_date[:4])
            conn.execute("UPDATE acc_doc SET stodt=? WHERE belnr=? AND gjahr=?",
                         (next_day, belnr, gj))
            from .document import period_open
            rev = None
            if period_open(conn, next_day):       # SAP: reversal on the next day right away
                rev = reverse(conn, belnr, gj, next_day, "05", user)
            conn.execute("INSERT OR REPLACE INTO fx_run (key_date,belnr,gjahr,reversal,usnam,ts) "
                         "VALUES (?,?,?,?,?,?)", (key_date, belnr, gj, rev, user, now_ts()))
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
            augbl = str(next_number(conn, "FI_01"))       # clearing number, no document
            n = 0
            for o in out:
                if o["cleared"]:
                    for i in groups[o["zuonr"]]:
                        conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE "
                                     "belnr=? AND gjahr=? AND buzei=?",
                                     (augbl, budat, i["belnr"], i["gjahr"], i["buzei"]))
                        n += 1
            conn.execute("INSERT INTO grir_run (augbl,budat,items,usnam,ts) VALUES (?,?,?,?,?)",
                         (augbl, budat, n, user, now_ts()))
            return {"augbl": augbl, "lines": out, "test": False}
    return {"augbl": None, "lines": out, "test": test}


# ---------------------------------------------------------------- VAT
def vat_report(conn, d1, d2, open_only=False):
    """S_ALR_87012357: tax base and tax per tax code. open_only: only tax lines not yet
    settled (FB41 clears the lines it settles)."""
    out = {}
    for r in conn.execute("SELECT i.mwskz, i.shkzg, i.dmbtr, i.txbase, i.hkont FROM "
                          "acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr "
                          "WHERE i.hkont IN ('154000','175000') AND i.mwskz IS NOT NULL AND "
                          "h.budat BETWEEN ? AND ? AND COALESCE(h.tcode,'')<>'FB41'%s"
                          % (" AND i.augbl IS NULL" if open_only else ""), (d1, d2)):
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
    """FB41: move the not yet settled output and input tax of the period to the tax
    payable account and clear the settled tax lines (a second run finds nothing)."""
    d1, d2, budat = parse_date(d1), parse_date(d2), parse_date(budat)
    with transaction(conn):
        rep = vat_report(conn, d1, d2, open_only=True)
        if not rep["output"] and not rep["input"]:
            raise MMError("No tax postings to settle in %s - %s (already settled?)" % (d1, d2),
                          "FF", "010")
        lines = [dict(hkont="175000", amount=rep["output"], sgtxt="VAT settlement output"),
                 dict(hkont="154000", amount=-rep["input"], sgtxt="VAT settlement input"),
                 dict(hkont=VAT_PAYABLE, amount=-(rep["output"] - rep["input"]),
                      sgtxt="VAT payable %s - %s" % (d1, d2))]
        belnr = write(conn, "SA", budat, user, "FB41", "VAT settlement %s" % d1[:7], lines,
                      tcode="FB41")
        gj = int(budat[:4])
        conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE augbl IS NULL AND hkont IN "
                     "('154000','175000') AND mwskz IS NOT NULL AND (belnr, gjahr) IN (SELECT belnr, "
                     "gjahr FROM acc_doc WHERE budat BETWEEN ? AND ? AND COALESCE(tcode,'')<>'FB41')",
                     (belnr, budat, d1, d2))
        conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND gjahr=? AND hkont IN "
                     "('154000','175000')", (belnr, budat, belnr, gj))
        conn.execute("INSERT OR REPLACE INTO vat_run (d1,d2,belnr,gjahr,payable,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?)", (d1, d2, belnr, gj, rep["payable"], user, now_ts()))
    return belnr


# ---------------------------------------------------------------- FF67
def bank_statement(conn, hbkid, azdat, aznum, opening, closing, lines, user):
    """lines: [{type: 'D' incoming customer payment | 'CHG' bank charges,
    amount (+ in / - out), kunnr, ref (document / reference), text}]"""
    azdat = parse_date(azdat)
    op, cl = parse_amount(opening, allow_zero=True), parse_amount(closing, allow_zero=True)
    def _signed(x):
        t = str(x).strip()
        return -parse_amount(t[1:]) if t.startswith("-") else parse_amount(t)
    total = sum(_signed(l["amount"]) for l in lines)
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
                     (hbkid, azdat, aznum, op, cl, json.dumps(lines), ",".join(docs), user, now_ts()))
    return {"docs": docs, "message": "Bank statement %s posted: %d documents"
            % (aznum, len(docs))}
