"""Asset accounting (chart of depreciation 1EG, book depreciation area 01).

AS01   asset master: class, cost center, useful life, depreciation key LINS
AS91   legacy data transfer: acquisition value + accumulated depreciation
F-90   acquisition from vendor (with input VAT)        transaction type 100
ABZON  acquisition with automatic offset (199900)      transaction type 100
AFAB   depreciation run: straight line, monthly, starting the month after
       capitalization; expense 470000 to the asset's cost center (-> CO)
ABAVN  retirement by scrapping (loss = net book value) transaction type 200
F-92   sale to a customer (gain / loss vs book value)  transaction type 210
AW01N  asset explorer, AR01 asset balances, S_ALR_87011990 history sheet
"""
from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, rdiv

from .ap import _tax_lines, tax_amount
from .config import ASSET_CLASSES, LOCAL_CURRENCY, TAX_CODES
from .document import rate, to_local, write


def create_asset(conn, anlkl, txt, kostl, ndjar=None, invnr="", user=""):
    if anlkl not in ASSET_CLASSES:
        raise MMError("Asset class %s does not exist (OAOA)" % anlkl, "AA", "001")
    if not (txt or "").strip():
        raise MMError("Enter a description", "AA", "002")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
        obj = "AA_" + anlkl
        conn.execute("INSERT OR IGNORE INTO number_range VALUES (?,?)",
                     (obj, ASSET_CLASSES[anlkl][5] - 1))
        anln1 = str(next_number(conn, obj))
        conn.execute("INSERT INTO asset (anln1,anlkl,txt,kostl,afasl,ndjar,invnr,erdat,ernam)"
                     " VALUES (?,?,?,?,?,?,?,?,?)",
                     (anln1, anlkl, txt.strip(), kostl, ASSET_CLASSES[anlkl][3],
                      int(ndjar or ASSET_CLASSES[anlkl][4]), invnr, now_ts()[:10], user))
    return anln1


def _asset(conn, anln1):
    a = conn.execute("SELECT * FROM asset WHERE anln1=?", (anln1,)).fetchone()
    if not a:
        raise MMError("Asset %s does not exist" % anln1, "AA", "003")
    return a


def values(conn, anln1, upto=None):
    sql = "SELECT COALESCE(SUM(apc),0) AS apc, COALESCE(SUM(dep),0) AS dep FROM " \
          "asset_item WHERE anln1=?"
    args = [anln1]
    if upto:
        sql += " AND budat<=?"
        args.append(upto)
    r = conn.execute(sql, args).fetchone()
    return r["apc"], r["dep"], r["apc"] + r["dep"]


def legacy_transfer(conn, anln1, aktiv, apc, accdep, takeover_date):
    """AS91: values at go-live (no FI document - part of the opening balance)."""
    with transaction(conn):
        _asset(conn, anln1)
        conn.execute("UPDATE asset SET aktiv=? WHERE anln1=?", (aktiv, anln1))
        conn.execute("INSERT INTO asset_item (anln1,belnr,gjahr,perio,budat,bwasl,apc,dep,"
                     "txt) VALUES (?,?,?,?,?,?,?,?,?)",
                     (anln1, "LEGACY", int(takeover_date[:4]), int(takeover_date[5:7]),
                      takeover_date, "900", parse_amount(apc),
                      -parse_amount(accdep, allow_zero=True), "Legacy data transfer"))


def acquire(conn, anln1, budat, amount, user, lifnr=None, mwskz="V1", bldat=None,
            xblnr="", text=""):
    """F-90 (with vendor) or ABZON (lifnr None -> offset 199900)."""
    budat = parse_date(budat)
    bldat = parse_date(bldat or budat)
    with transaction(conn):
        a = _asset(conn, anln1)
        if a["deakt"]:
            raise MMError("Asset %s is retired" % anln1, "AA", "004")
        net = parse_amount(amount)
        cls = ASSET_CLASSES[a["anlkl"]]
        if lifnr:
            v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
            if not v:
                raise MMError("Vendor %s does not exist" % lifnr, "F2", "103")
            waers = v["waers"] or LOCAL_CURRENCY
            kursf = rate(conn, waers, budat)
            lines = [dict(hkont=cls[1], anln1=anln1, anbwa="100", koart="A", wrbtr=net,
                          amount=to_local(net, kursf), mwskz=mwskz,
                          sgtxt=text or a["txt"])]
            lines += _tax_lines({mwskz: net}, kursf, 1) if mwskz else []
            lines.append(dict(lifnr=lifnr, koart="K", zfbdt=bldat,
                              wrbtr=-sum(l["wrbtr"] for l in lines),
                              amount=-sum(l["amount"] for l in lines), sgtxt=text or a["txt"]))
            blart, tcode = "KR", "F-90"
        else:
            waers, kursf = LOCAL_CURRENCY, 100000
            lines = [dict(hkont=cls[1], anln1=anln1, anbwa="100", koart="A", amount=net,
                          sgtxt=text or a["txt"]),
                     dict(hkont="199900", amount=-net, sgtxt="Asset acquisition clearing")]
            blart, tcode = "AA", "ABZON"
        belnr = write(conn, blart, budat, user, tcode, text or "Acquisition %s" % anln1,
                      lines, bldat=bldat, xblnr=xblnr, waers=waers, kursf=kursf, tcode=tcode)
        apc = lines[0]["amount"]
        conn.execute("INSERT INTO asset_item (anln1,belnr,gjahr,perio,budat,bwasl,apc,dep,"
                     "txt) VALUES (?,?,?,?,?,?,?,0,?)",
                     (anln1, belnr, int(budat[:4]), int(budat[5:7]), budat, "100", apc,
                      "Acquisition"))
        if not a["aktiv"]:
            conn.execute("UPDATE asset SET aktiv=? WHERE anln1=?", (budat, anln1))
    return belnr


def _months(y, p):
    return y * 12 + (p - 1)


def planned_dep(conn, a, gjahr, perio):
    """Planned ordinary depreciation of one period (straight line)."""
    if a["afasl"] != "LINS" or not a["aktiv"]:
        return 0
    start = _months(int(a["aktiv"][:4]), int(a["aktiv"][5:7])) + 1   # next month
    if _months(gjahr, perio) < start:
        return 0
    if a["deakt"] and a["deakt"][:7] < "%04d-%02d" % (gjahr, perio):
        return 0
    period_end = "%04d-%02d-31" % (gjahr, perio)
    apc, dep_total, _ = values(conn, a["anln1"], period_end)
    posted_before = conn.execute(
        "SELECT COALESCE(SUM(dep),0) FROM asset_item WHERE anln1=? AND (gjahr*12+perio-1)"
        "<? ", (a["anln1"], _months(gjahr, perio))).fetchone()[0]
    remaining = apc + posted_before                       # NBV before this period
    if remaining <= 0:
        return 0
    return min(rdiv(apc, a["ndjar"] * 12), remaining)


def depreciation_run(conn, gjahr, perio, user, test=True):
    """AFAB: posts planned minus already posted depreciation for the period."""
    gjahr, perio = int(gjahr), int(perio)
    budat = ("%04d-%02d-28" % (gjahr, perio))
    import calendar
    budat = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    out, lines = [], []
    with transaction(conn):
        for a in conn.execute("SELECT * FROM asset ORDER BY anln1").fetchall():
            plan = planned_dep(conn, a, gjahr, perio)
            posted = -conn.execute("SELECT COALESCE(SUM(dep),0) FROM asset_item WHERE "
                                   "anln1=? AND gjahr=? AND perio=? AND bwasl='AFA'",
                                   (a["anln1"], gjahr, perio)).fetchone()[0]
            delta = plan - posted
            if not delta:
                continue
            cls = ASSET_CLASSES[a["anlkl"]]
            out.append(dict(anln1=a["anln1"], txt=a["txt"], anlkl=a["anlkl"],
                            kostl=a["kostl"], planned=plan, posted=posted, amount=delta))
            lines.append(dict(hkont="470000", amount=delta, kostl=a["kostl"],
                              sgtxt="Depreciation %s %s" % (a["anln1"], a["txt"])[:50]))
            lines.append(dict(hkont=cls[2], anln1=a["anln1"], koart="A", anbwa="AFA",
                              amount=-delta, sgtxt="Depreciation %02d/%s" % (perio, gjahr)))
        belnr = None
        if lines and not test:
            belnr = write(conn, "AF", budat, user, "AFAB", "Depreciation %02d/%s"
                          % (perio, gjahr), lines, tcode="AFAB")
            for o in out:
                conn.execute("INSERT INTO asset_item (anln1,belnr,gjahr,perio,budat,bwasl,"
                             "apc,dep,txt) VALUES (?,?,?,?,?,?,0,?,?)",
                             (o["anln1"], belnr, gjahr, perio, budat, "AFA", -o["amount"],
                              "Ordinary depreciation"))
    return {"belnr": belnr, "test": test, "lines": out,
            "total": sum(o["amount"] for o in out)}


def retire(conn, anln1, budat, user, revenue=None, kunnr=None, mwskz="A1", text=""):
    """ABAVN (scrapping, no revenue) or F-92 (sale to customer)."""
    budat = parse_date(budat)
    with transaction(conn):
        a = _asset(conn, anln1)
        if a["deakt"]:
            raise MMError("Asset %s is already retired" % anln1, "AA", "005")
        cls = ASSET_CLASSES[a["anlkl"]]
        apc, dep, nbv = values(conn, anln1)
        if apc == 0:
            raise MMError("Asset %s has no acquisition value" % anln1, "AA", "006")
        lines = [dict(hkont=cls[1], anln1=anln1, koart="A",
                      anbwa="210" if kunnr else "200", amount=-apc,
                      sgtxt="Retirement APC"),
                 dict(hkont=cls[2], anln1=anln1, koart="A",
                      anbwa="210" if kunnr else "200", amount=-dep,
                      sgtxt="Retirement acc. depreciation")]
        if kunnr:
            proceeds = parse_amount(revenue)
            tx = tax_amount(proceeds, mwskz)
            lines.append(dict(hkont=TAX_CODES[mwskz][3], amount=-tx, mwskz=mwskz,
                              txbase=proceeds, ktosl="MWS"))
            lines.append(dict(kunnr=kunnr, koart="D", amount=proceeds + tx,
                              zfbdt=budat, sgtxt=text or "Asset sale %s" % anln1))
            result = proceeds - nbv
        else:
            result = -nbv
        if result > 0:
            lines.append(dict(hkont="820000", amount=-result, sgtxt="Gain on asset sale"))
        elif result < 0:
            lines.append(dict(hkont="821000", amount=-result, sgtxt="Loss on retirement"))
        tcode = "F-92" if kunnr else "ABAVN"
        belnr = write(conn, "AA", budat, user, tcode, text or "Retirement %s" % anln1,
                      lines, tcode=tcode)
        conn.execute("INSERT INTO asset_item (anln1,belnr,gjahr,perio,budat,bwasl,apc,dep,"
                     "txt) VALUES (?,?,?,?,?,?,?,?,?)",
                     (anln1, belnr, int(budat[:4]), int(budat[5:7]), budat,
                      "210" if kunnr else "200", -apc, -dep, "Retirement"))
        conn.execute("UPDATE asset SET deakt=? WHERE anln1=?", (budat, anln1))
    return {"belnr": belnr, "nbv": nbv, "result": result}


# ---------------------------------------------------------------- reports
def explorer(conn, anln1, gjahr):
    """AW01N: values of the fiscal year + period plan."""
    a = dict(_asset(conn, anln1))
    y0 = "%04d-01-01" % gjahr
    apc0 = conn.execute("SELECT COALESCE(SUM(apc),0) FROM asset_item WHERE anln1=? AND "
                        "budat<?", (anln1, y0)).fetchone()[0]
    dep0 = conn.execute("SELECT COALESCE(SUM(dep),0) FROM asset_item WHERE anln1=? AND "
                        "budat<?", (anln1, y0)).fetchone()[0]
    items = [dict(r) for r in conn.execute("SELECT * FROM asset_item WHERE anln1=? AND "
                                           "gjahr=? ORDER BY budat, id", (anln1, gjahr))]
    periods = []
    for p in range(1, 13):
        posted = -sum(i["dep"] for i in items if i["perio"] == p and i["bwasl"] == "AFA")
        periods.append(dict(perio=p, planned=planned_dep(conn, a, gjahr, p), posted=posted))
    apc0 += sum(i["apc"] for i in items if i["bwasl"] == "900")   # takeover = opening
    acq = sum(i["apc"] for i in items if i["bwasl"] in ("100", "110"))
    ret = sum(i["apc"] for i in items if i["bwasl"] in ("200", "210"))
    dep_ret = sum(i["dep"] for i in items if i["bwasl"] in ("200", "210"))
    dep_year = sum(i["dep"] for i in items if i["bwasl"] == "AFA")
    leg_dep = sum(i["dep"] for i in items if i["bwasl"] == "900")
    a.update(gjahr=gjahr, apc_start=apc0, acquisitions=acq, retirements=ret,
             apc_end=apc0 + acq + ret, dep_start=dep0 + leg_dep, dep_year=dep_year,
             dep_retired=dep_ret, dep_end=dep0 + leg_dep + dep_year + dep_ret,
             planned_year=sum(x["planned"] for x in periods), items=items,
             periods=periods, cls=ASSET_CLASSES[a["anlkl"]][0])
    a["nbv_start"] = a["apc_start"] + a["dep_start"]
    a["nbv_end"] = a["apc_end"] + a["dep_end"]
    return a


def history_sheet(conn, gjahr, upto=None):
    """S_ALR_87011990 per asset class."""
    rows = {}
    for a in conn.execute("SELECT anln1, anlkl FROM asset").fetchall():
        e = explorer(conn, a["anln1"], gjahr)
        r = rows.setdefault(a["anlkl"], dict(anlkl=a["anlkl"], txt=ASSET_CLASSES[
            a["anlkl"]][0], apc_start=0, acquisitions=0, retirements=0, apc_end=0,
            dep_start=0, dep_year=0, dep_retired=0, dep_end=0, nbv_start=0, nbv_end=0,
            count=0))
        r["count"] += 1
        for k in ("apc_start", "acquisitions", "retirements", "apc_end", "dep_start",
                  "dep_year", "dep_retired", "dep_end", "nbv_start", "nbv_end"):
            r[k] += e[k]
    return [rows[k] for k in sorted(rows)]


def reverse_depreciation(conn, gjahr, perio, user):
    """Reverse the depreciation run of the last posted period (then AFAB can post again)."""
    gjahr, perio = int(gjahr), int(perio)
    with transaction(conn):
        last = conn.execute("SELECT MAX(gjahr*12+perio) FROM asset_item WHERE bwasl='AFA' AND "
                            "belnr IN (SELECT belnr FROM acc_doc WHERE tcode='AFAB' AND stblg IS NULL)"
                            ).fetchone()[0]
        if last is None or last != gjahr * 12 + perio:
            raise MMError("Only the depreciation of the last posted period can be reversed", "AA", "020")
        docs = [r[0] for r in conn.execute(
            "SELECT DISTINCT a.belnr FROM asset_item a JOIN acc_doc h ON h.belnr=a.belnr AND "
            "h.gjahr=a.gjahr WHERE a.bwasl='AFA' AND a.gjahr=? AND a.perio=? AND h.tcode='AFAB' AND "
            "h.stblg IS NULL", (gjahr, perio))]
        from .gl import reverse
        out = []
        for b in docs:
            h = conn.execute("SELECT budat FROM acc_doc WHERE belnr=? AND gjahr=?", (b, gjahr)).fetchone()
            out.append(reverse(conn, b, gjahr, h["budat"], "01", user, _from_source=True))
    return {"reversed": docs, "documents": out,
            "message": "Depreciation %02d/%s reversed (%s)" % (perio, gjahr, ", ".join(out))}
