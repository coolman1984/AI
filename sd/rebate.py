"""Customer rebate agreements (2-2): the distributor earns a rebate % on the sales of a period
when the sales reach a target - common with Egyptian dealers and distributors.

ZREB01   agreement: customer, validity (e.g. a quarter or the year), scale of targets
         e.g. from 1,000,000 EGP 2 %, from 2,000,000 EGP 3.5 % (the reached tier applies to
         all sales of the period)
ZREB02   status: sales so far (net billed, credit memos reduce), reached tier, rebate earned,
         sales still needed for the next tier, accrued and settled
ZREB_ACR monthly accrual of the earned rebate (only the difference to what is already accrued):
             Dr 881000 customer rebates  / Cr 291000 accrued customer rebates
ZREB03   settlement at the end: the customer gets a credit (open item) for the earned rebate
             Dr 291000 (accrued) + 881000 (difference) / Cr customer
"""
import json

from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_pct, rdiv

EXPENSE, ACCRUAL = "881000", "291000"
STATUS = {"A": "Active", "S": "Settled", "X": "Cancelled"}


def _get(conn, knuma):
    r = conn.execute("SELECT * FROM sd_rebate WHERE knuma=?", (str(knuma),)).fetchone()
    if not r:
        raise MMError("Rebate agreement %s does not exist" % knuma, "VB", "961")
    return r


def create(conn, data, user):
    kunnr = (data.get("kunnr") or "").strip().upper()
    datab, datbi = parse_date(data.get("datab")), parse_date(data.get("datbi"))
    if datbi < datab:
        raise MMError("Valid-to is before valid-from", "VB", "962")
    scale = []
    for row in data.get("scale") or []:
        if not row or row[0] in (None, "") or row[1] in (None, ""):
            continue
        scale.append([parse_amount(row[0], allow_zero=True), parse_pct(row[1])])
    if not scale:
        raise MMError("Enter at least one target with its rebate %", "VB", "963")
    scale.sort()
    for i in range(1, len(scale)):
        if scale[i][0] == scale[i - 1][0] or scale[i][1] <= scale[i - 1][1]:
            raise MMError("Each higher target needs a higher rebate %", "VB", "964")
    if any(p <= 0 or p > 5000 for _, p in scale):
        raise MMError("Rebate % must be between 0 and 50", "VB", "965")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM customer WHERE kunnr=?", (kunnr,)).fetchone():
            raise MMError("Customer %s does not exist" % kunnr, "VB", "966")
        if conn.execute("SELECT 1 FROM sd_rebate WHERE kunnr=? AND status='A' AND datab<=? AND datbi>=?",
                        (kunnr, datbi, datab)).fetchone():
            raise MMError("Customer %s already has an active agreement in this period" % kunnr, "VB", "967")
        knuma = str(next_number(conn, "REBATE"))
        conn.execute("INSERT INTO sd_rebate (knuma,kunnr,text,datab,datbi,scale,usnam,ts) VALUES (?,?,?,?,?,?,?,?)",
                     (knuma, kunnr, (data.get("text") or "")[:60], datab, datbi, json.dumps(scale), user, now_ts()))
    return {"knuma": knuma, "message": "Rebate agreement %s created for customer %s" % (knuma, kunnr)}


def _basis(conn, r, upto):
    """net billed sales of the customer in the agreement period up to a date (credit memos reduce)"""
    return conn.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE cancelled=0 AND COALESCE(kunrg,kunnr)=? "
                        "AND fkdat BETWEEN ? AND ?", (r["kunnr"], r["datab"], min(upto, r["datbi"]))).fetchone()[0]


def status(conn, knuma, upto=None):
    from mm import util as clock
    r = _get(conn, knuma)
    upto = parse_date(upto) if upto else clock.today().isoformat()
    basis = _basis(conn, r, upto)
    scale = json.loads(r["scale"])
    rate = 0
    nxt = None
    for t, p in scale:
        if basis >= t:
            rate = p
        elif nxt is None:
            nxt = dict(target=t, rate=p, missing=t - basis)
    earned = rdiv(basis * rate, 10000) if basis > 0 else 0
    n = conn.execute("SELECT name FROM customer WHERE kunnr=?", (r["kunnr"],)).fetchone()
    return dict(knuma=r["knuma"], kunnr=r["kunnr"], name=n["name"] if n else "", text=r["text"], datab=r["datab"],
                datbi=r["datbi"], scale=[dict(target=t, rate=p) for t, p in scale], basis=basis, rate=rate,
                earned=earned, next=nxt, accrued=r["accrued"], settled=r["settled"], to_accrue=earned - r["accrued"],
                status=r["status"], status_text=STATUS[r["status"]], set_belnr=r["set_belnr"], upto=upto)


def agreements(conn, kunnr=None, upto=None):
    sql, a = "SELECT knuma FROM sd_rebate", []
    if kunnr:
        sql += " WHERE kunnr=?"
        a.append(kunnr.upper())
    return [status(conn, k[0], upto) for k in conn.execute(sql + " ORDER BY knuma DESC", a).fetchall()]


def accrue(conn, budat, user, knuma=None, test=False):
    """ZREB_ACR: accrue the earned rebate of the active agreements up to the posting date"""
    from fi import gl
    budat = parse_date(budat)
    keys = [knuma] if knuma else [k[0] for k in conn.execute("SELECT knuma FROM sd_rebate WHERE status='A' AND "
                                                              "datab<=? ORDER BY knuma", (budat,))]
    out = []
    with transaction(conn):
        for k in keys:
            s = status(conn, k, budat)
            if s["status"] != "A" or not s["to_accrue"]:
                continue
            row = dict(knuma=k, kunnr=s["kunnr"], name=s["name"], basis=s["basis"], earned=s["earned"],
                       amount=s["to_accrue"], belnr=None)
            if not test:
                amt = s["to_accrue"]
                m = "%.2f" % (abs(amt) / 100.0)
                txt = "Rebate accrual %s %s" % (k, s["kunnr"])
                lines = [{"bschl": "40", "account": EXPENSE, "amount": m, "sgtxt": txt},
                         {"bschl": "50", "account": ACCRUAL, "amount": m, "sgtxt": txt}]
                if amt < 0:                                   # sales fell (credit memos): release
                    lines = [dict(lines[0], bschl="50"), dict(lines[1], bschl="40")]
                row["belnr"] = gl.general_posting(conn, {"budat": budat, "bktxt": txt[:25]}, lines, user)
                conn.execute("UPDATE sd_rebate SET accrued=accrued+? WHERE knuma=?", (amt, k))
                conn.execute("INSERT INTO sd_rebate_acr (knuma,budat,basis,earned,amount,belnr,usnam) VALUES "
                             "(?,?,?,?,?,?,?)", (k, budat, s["basis"], s["earned"], amt, row["belnr"], user))
            out.append(row)
    total = sum(r["amount"] for r in out)
    return {"rows": out, "total": total, "test": test,
            "message": "%s: %d agreement(s), %.2f EGP" % ("Test run" if test else "Accrued", len(out), total / 100.0)}


def settle(conn, knuma, budat, user):
    """ZREB03: credit the earned rebate to the customer and clear the accrual"""
    from fi import gl
    budat = parse_date(budat)
    with transaction(conn):
        r = _get(conn, knuma)
        if r["status"] != "A":
            raise MMError("Agreement %s is already %s" % (knuma, STATUS[r["status"]].lower()), "VB", "968")
        if budat < r["datbi"]:
            raise MMError("Settle after the end of the agreement (%s)" % r["datbi"], "VB", "969")
        s = status(conn, knuma, r["datbi"])
        belnr = None
        if s["earned"]:
            txt = "Rebate %s %s" % (knuma, r["kunnr"])
            lines = []
            if s["accrued"] > 0:
                lines.append({"bschl": "40", "account": ACCRUAL, "amount": "%.2f" % (s["accrued"] / 100.0), "sgtxt": txt})
            diff = s["earned"] - max(s["accrued"], 0)
            if diff:
                lines.append({"bschl": "40" if diff > 0 else "50", "account": EXPENSE,
                              "amount": "%.2f" % (abs(diff) / 100.0), "sgtxt": txt})
            lines.append({"bschl": "11", "account": r["kunnr"], "amount": "%.2f" % (s["earned"] / 100.0), "sgtxt": txt})
            belnr = gl.general_posting(conn, {"budat": budat, "blart": "DG", "bktxt": txt[:25], "xblnr": knuma}, lines,
                                       user)
        elif s["accrued"]:
            m = "%.2f" % (abs(s["accrued"]) / 100.0)
            belnr = gl.general_posting(conn, {"budat": budat, "bktxt": "Rebate %s released" % knuma}, [
                {"bschl": "40", "account": ACCRUAL, "amount": m}, {"bschl": "50", "account": EXPENSE, "amount": m}], user)
        conn.execute("UPDATE sd_rebate SET status='S', settled=?, accrued=0, set_belnr=? WHERE knuma=?",
                     (s["earned"], belnr, r["knuma"]))
    return {"belnr": belnr, "earned": s["earned"],
            "message": "Agreement %s settled - credit %.2f EGP to customer %s%s" % (
                knuma, s["earned"] / 100.0, r["kunnr"], " (document %s)" % belnr if belnr else "")}
