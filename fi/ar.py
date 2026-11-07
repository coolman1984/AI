"""Accounts receivable.

FB70 / FB75  customer invoice / credit memo; revenue accounts flow to CO-PA
             as record type B (FI direct posting), like SAP
F-28         incoming payment (shared logic in ap.pay)
FD32         credit limit + credit exposure check (used by billing VF01)
F150         dunning run: levels 1-4, 14-day interval, 3 grace days, charges
"""
import datetime
import json

from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date

from .ap import _balance_partner, _tax_lines, open_items
from .config import DUNNING, LOCAL_CURRENCY, TAX_CODES
from .document import signed, write


def credit_exposure(conn, kunnr):
    return sum(signed(r) for r in open_items(conn, "D", kunnr))


def check_credit(conn, kunnr, add_amount):
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
    if not c or not c["klimk"]:
        return
    exp = credit_exposure(conn, kunnr)
    if exp + add_amount > c["klimk"]:
        raise MMError("Credit limit of customer %s exceeded: limit %.2f, open items "
                      "%.2f, this document %.2f - document blocked (FD32)"
                      % (kunnr, c["klimk"] / 100.0, exp / 100.0, add_amount / 100.0),
                      "VF", "035")


def customer_invoice(conn, header, lines, user, credit_memo=False):
    """header: kunnr, bldat, budat, xblnr, bktxt, mwskz, zterm
    lines: [{hkont, amount (net), matnr (for CO-PA), sgtxt}]"""
    from co.period_end import _copa_post
    budat = parse_date(header.get("budat"))
    bldat = parse_date(header.get("bldat") or budat)
    kunnr = (header.get("kunnr") or "").upper()
    with transaction(conn):
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (kunnr,)).fetchone()
        if not c:
            raise MMError("Customer %s does not exist" % kunnr, "F2", "102")
        sign = 1 if credit_memo else -1          # revenue is a credit
        acc, base, copa = [], {}, []
        ce = {r["kstar"]: r["katyp"] for r in conn.execute("SELECT * FROM cost_element")}
        for n, l in enumerate(lines, start=1):
            net = parse_amount(l.get("amount"))
            code = l.get("mwskz") or header.get("mwskz") or ""
            if code:
                if TAX_CODES.get(code, ("", 0, ""))[2] != "O":
                    raise MMError("Line %d: %s is not an output tax code" % (n, code))
                base[code] = base.get(code, 0) + net
            hk = str(l.get("hkont") or "").strip()
            line = dict(hkont=hk, wrbtr=sign * net, amount=sign * net, mwskz=code or None,
                        matnr=(l.get("matnr") or "").upper() or None,
                        sgtxt=l.get("sgtxt") or header.get("bktxt"))
            if ce.get(hk) in (11, 12):
                line["paobj"] = "FB70/%s/%s" % (kunnr, n)
                copa.append((line, net))
            acc.append(line)
        acc += _tax_lines(base, 100000, sign)
        acc = _balance_partner(acc, dict(kunnr=kunnr, koart="D", zfbdt=bldat,
                                         zterm=header.get("zterm") or None,
                                         sgtxt=header.get("bktxt")))
        if not credit_memo:
            check_credit(conn, kunnr, acc[-1]["amount"])
        belnr = write(conn, "DG" if credit_memo else "DR", budat, user,
                      "FB75" if credit_memo else "FB70", header.get("bktxt") or "", acc,
                      bldat=bldat, xblnr=header.get("xblnr"),
                      tcode="FB75" if credit_memo else "FB70")
        y, p = int(budat[:4]), int(budat[5:7])
        for line, net in copa:                     # CO-PA record type B
            m = conn.execute("SELECT matkl FROM material WHERE matnr=?",
                             (line["matnr"],)).fetchone() if line["matnr"] else None
            vv = "vv010" if ce[line["hkont"]] == 11 else "vv020"
            val = net if vv == "vv010" else -net
            _copa_post(conn, "B", 0, y, p, dict(
                kunnr=kunnr, matnr=line["matnr"], matkl=m["matkl"] if m else None,
                region=c["region"], kdgrp=c["kdgrp"], vtweg=c["vtweg"], werks="1000"),
                {vv: -val if credit_memo else val}, refdoc=belnr, user=user, budat=budat)
        return belnr


# ====================================================================== F150
def dunning_run(conn, ausdt, user, execute=False):
    ausdt = parse_date(ausdt)
    d0 = datetime.date.fromisoformat(ausdt)
    letters = {}
    with transaction(conn):
        for r in open_items(conn, "D", key_date=ausdt):
            if r["shkzg"] != "S":
                continue
            overdue = (d0 - datetime.date.fromisoformat(r["netdt"])).days
            if overdue <= DUNNING["grace_days"]:
                continue
            level = r["manst"] or 0
            if level and r["madat"] and (d0 - datetime.date.fromisoformat(r["madat"])).days \
                    < DUNNING["interval_days"]:
                new = level                          # not dunned again yet
                due_again = False
            else:
                new = min(level + 1, 4)
                due_again = True
            c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (r["kunnr"],)).fetchone()
            L = letters.setdefault(r["kunnr"], dict(kunnr=r["kunnr"], name=c["name"],
                                                    city=c["city"], items=[], level=0,
                                                    total=0))
            L["items"].append(dict(belnr=r["belnr"], gjahr=r["gjahr"], buzei=r["buzei"],
                                   xblnr=r["xblnr"], netdt=r["netdt"], overdue=overdue,
                                   amount=signed(r), old_level=level, level=new,
                                   dunned=due_again))
            L["level"] = max(L["level"], new)
            L["total"] += signed(r)
        out = []
        for L in letters.values():
            if not any(i["dunned"] for i in L["items"]):
                continue
            lv = DUNNING["levels"][L["level"]]
            L["level_text"], L["charges"] = lv[0], lv[1]
            out.append(L)
            if execute:
                for i in L["items"]:
                    if i["dunned"]:
                        conn.execute("UPDATE acc_doc_item SET manst=?, madat=? WHERE "
                                     "belnr=? AND gjahr=? AND buzei=?",
                                     (i["level"], ausdt, i["belnr"], i["gjahr"], i["buzei"]))
        if execute:
            conn.execute("INSERT INTO dunning_run (ausdt,status,result,usnam,ts) VALUES "
                         "(?,?,?,?,?)", (ausdt, "PRINTED", json.dumps(out), user, now_ts()))
    return {"ausdt": ausdt, "executed": execute, "letters": out,
            "currency": LOCAL_CURRENCY}
