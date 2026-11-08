"""Service parts: forecasting, reservations, refurbishment support, WIP.

MP30 / MP38  forecast (single / mass) from the monthly consumption history:
             D moving average, G exponential smoothing (alpha), T trend (Holt)
             ex-post forecast -> MAD, MAPE, tracking signal
             safety stock = z(service level) x 1.25 x MAD x sqrt(lead time in months)
             reorder point = demand during lead time + safety stock
MP33         forecast results display
MB21 / MB25  reservations for cost centers; goods issue 201 against reservation
KKAX / KKAO  work in process at actual costs for orders not yet delivered
"""
import calendar
import datetime
import math

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_date, parse_qty, rdiv

from .config import SERVICE_Z, WIP_ACCOUNT, WIP_CHANGE


def _months_back(today, n):
    y, m = int(today[:4]), int(today[5:7])
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append("%04d-%02d" % (y, m))
    return list(reversed(out))


def _months_fwd(today, n):
    y, m = int(today[:4]), int(today[5:7])
    out = []
    for _ in range(n):
        out.append("%04d-%02d" % (y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def history(conn, matnr, werks, months):
    """Consumption per month (201/261/601/551 net of reversals)."""
    out = {}
    for r in conn.execute("SELECT substr(h.budat,1,7) mo, SUM(CASE WHEN i.shkzg='H' THEN i.menge "
                          "ELSE -i.menge END) q FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr "
                          "AND h.mjahr=i.mjahr WHERE i.matnr=? AND i.werks=? AND i.bwart IN "
                          "('201','202','261','262','601','602','551','552') GROUP BY mo",
                          (matnr, werks)):
        out[r["mo"]] = max(0, r["q"] or 0)
    return [(m, out.get(m, 0)) for m in months]


def forecast(conn, matnr, werks="1000", model="G", periods_hist=6, periods_fc=6, alpha=0.3,
             beta=0.2, service=95, today=None, user="", apply=False):
    today = today or datetime.date.today().isoformat()
    matnr = matnr.upper()
    if model not in ("D", "G", "T"):
        raise MMError("Forecast model %s not allowed (D, G, T)" % model, "MP", "001")
    if service not in SERVICE_Z:
        raise MMError("Service level %s %% not allowed (%s)" % (service, sorted(SERVICE_Z)), "MP", "002")
    mp = conn.execute("SELECT * FROM material_plant WHERE matnr=? AND werks=?", (matnr, werks)).fetchone()
    if not mp:
        raise MMError("Material %s is not maintained in plant %s" % (matnr, werks), "MP", "003")
    hist = history(conn, matnr, werks, _months_back(today, int(periods_hist)))
    vals = [q for _, q in hist]
    if sum(1 for v in vals if v) < 2:
        raise MMError("Not enough consumption history for %s (at least 2 periods)" % matnr, "MP", "004")
    # ex-post forecast over the history
    expost = []
    level = vals[0]
    trend = 0.0
    for i, v in enumerate(vals):
        if model == "D":
            f = sum(vals[:i]) / i if i else vals[0]
        else:
            f = level + trend
        expost.append(f)
        if model == "G":
            level = alpha * v + (1 - alpha) * level
        elif model == "T":
            prev = level
            level = alpha * v + (1 - alpha) * (level + trend)
            trend = beta * (level - prev) + (1 - beta) * trend
    errs = [v - f for v, f in zip(vals[1:], expost[1:])]
    mad = sum(abs(e) for e in errs) / len(errs) if errs else 0
    mape = (sum(abs(e) / v for e, v in zip(errs, vals[1:]) if v) /
            max(1, sum(1 for v in vals[1:] if v)) * 100) if errs else 0
    tsig = (sum(errs) / mad) if mad else 0
    base = sum(vals) / len(vals) if model == "D" else level
    fc = []
    for i, mo in enumerate(_months_fwd(today, int(periods_fc))):
        val = base + (trend * (i + 1) if model == "T" else 0)
        fc.append((mo, int(round(max(0, val), -3))))          # whole units
    lead_days = mp["plifz"] or 7
    lt_months = lead_days / 30.0
    z = SERVICE_Z[service]
    ss = int(round(z * 1.25 * mad * math.sqrt(lt_months), -3))
    daily = (sum(v for _, v in fc[:3]) / 3.0) / 30.0
    rop = int(round(daily * lead_days + ss, -3))
    with transaction(conn):
        conn.execute("DELETE FROM pp_forecast WHERE matnr=? AND werks=?", (matnr, werks))
        for mo, v in hist:
            conn.execute("INSERT INTO pp_forecast VALUES (?,?,?,?,?)", (matnr, werks, mo, "H", v))
        for (mo, _), e in zip(hist, expost):
            conn.execute("INSERT INTO pp_forecast VALUES (?,?,?,?,?)",
                         (matnr, werks, mo, "X", int(round(e))))
        for mo, v in fc:
            conn.execute("INSERT INTO pp_forecast VALUES (?,?,?,?,?)", (matnr, werks, mo, "F", v))
        conn.execute("INSERT OR REPLACE INTO pp_fc_param VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (matnr, werks, model, int(alpha * 100), int(beta * 100), int(periods_fc),
                      int(round(mad)), int(round(mape * 100)), int(round(tsig * 100)), ss, rop,
                      now_ts()))
        conn.execute("UPDATE material_plant SET prmod=?, lgrad=? WHERE matnr=? AND werks=?",
                     (model, service, matnr, werks))
        if apply:
            from md.material import change_material
            change_material(conn, matnr, {"plants": [{"werks": werks, "eisbe": "%.3f" % (ss / 1000.0),
                                                      "minbe": "%.3f" % (max(rop, ss) / 1000.0)}]},
                            user, "MP30")
    return dict(matnr=matnr, model=model, history=hist, expost=[int(round(e)) for e in expost],
                forecast=fc, mad=round(mad), mape=round(mape, 1), tsig=round(tsig, 2),
                safety_stock=ss, reorder_point=rop, service=service, lead_days=lead_days,
                warning="Tracking signal %.1f outside +-4: model does not fit" % tsig
                if abs(tsig) > 4 else "")


def mass_forecast(conn, werks="1000", user="", apply=False, today=None):
    out = []
    for m in conn.execute("SELECT p.matnr, p.prmod, p.lgrad FROM material_plant p WHERE p.werks=? AND "
                          "p.dismm='VV'", (werks,)).fetchall():
        try:
            r = forecast(conn, m["matnr"], werks, m["prmod"] or "G", service=m["lgrad"] or 95,
                         user=user, apply=apply, today=today)
            out.append(dict(matnr=m["matnr"], ok=True, mad=r["mad"], mape=r["mape"],
                            ss=r["safety_stock"], rop=r["reorder_point"], warning=r["warning"]))
        except MMError as e:
            out.append(dict(matnr=m["matnr"], ok=False, warning=str(e)))
    return out


def forecast_result(conn, matnr, werks="1000"):
    p = conn.execute("SELECT * FROM pp_fc_param WHERE matnr=? AND werks=?", (matnr.upper(), werks)).fetchone()
    vals = rows(conn.execute("SELECT * FROM pp_forecast WHERE matnr=? AND werks=? ORDER BY month, kind",
                             (matnr.upper(), werks)))
    return {"param": dict(p) if p else None, "values": vals}


# ====================================================================== MB21 / MB25
def create_reservation(conn, kostl, items, bdter, user, bwart="201"):
    kostl = (kostl or "").upper()
    if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
        raise MMError("Cost center %s does not exist" % kostl, "KI", "248")
    if not items:
        raise MMError("Enter at least one item", "M7", "101")
    d = parse_date(bdter)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM number_range WHERE object='RESB'").fetchone() is None:
            conn.execute("INSERT INTO number_range VALUES ('RESB', 1999999)")
        rsnum = str(next_number(conn, "RESB"))
        for i, it in enumerate(items, start=1):
            m = (it.get("matnr") or "").upper()
            if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                                (m, it.get("werks") or "1000")).fetchone():
                raise MMError("Item %d: material %s not in plant" % (i, m), "M7", "102")
            conn.execute("INSERT INTO pp_resb (rsnum,rspos,kostl,matnr,werks,lgort,bdmng,bdter,bwart,"
                         "usnam) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (rsnum, i, kostl, m, it.get("werks") or "1000", it.get("lgort") or "0004",
                          parse_qty(it.get("menge")), d, bwart, user))
    return rsnum


def reservations(conn, open_only=True):
    sql = ("SELECT r.*, m.maktx, m.meins, c.name AS kname FROM pp_resb r JOIN material m USING (matnr) "
           "LEFT JOIN cost_center c ON c.kostl=r.kostl WHERE r.aufnr IS NULL")
    if open_only:
        sql += " AND r.bdmng>r.enmng AND r.kzear=0 AND r.xloek=0"
    return rows(conn.execute(sql + " ORDER BY r.bdter, r.rsnum, r.rspos"))


def issue_reservation(conn, rsnum, budat, user, items=None):
    lines = []
    for r in conn.execute("SELECT * FROM pp_resb WHERE rsnum=? AND bdmng>enmng AND kzear=0",
                          (str(rsnum),)).fetchall():
        q = parse_qty(items[str(r["rspos"])]) if items and str(r["rspos"]) in items else \
            r["bdmng"] - r["enmng"]
        if q <= 0:
            continue
        lines.append({"bwart": r["bwart"], "matnr": r["matnr"], "werks": r["werks"],
                      "lgort": r["lgort"], "qty": "%.3f" % (q / 1000.0), "kostl": r["kostl"],
                      "rsnum": r["rsnum"], "rspos": r["rspos"]})
    if not lines:
        raise MMError("Reservation %s has no open items" % rsnum, "M7", "103")
    from mm.posting import post_goods_movement
    return post_goods_movement(conn, {"budat": budat, "bktxt": "Reservation %s" % rsnum}, lines,
                               user, tcode="MB1A")


# ====================================================================== KKAX / KKAO
def wip(conn, gjahr, perio, user="", test=False):
    """WIP at actual costs: orders with costs that are not delivered / TECO.
    The change against the previous period is posted to FI (Dr WIP, Cr change
    in WIP); delivered orders get their WIP cancelled."""
    gjahr, perio = int(gjahr), int(perio)
    budat = "%04d-%02d-%02d" % (gjahr, perio, calendar.monthrange(gjahr, perio)[1])
    out = []
    with transaction(conn):
        for o in conn.execute("SELECT * FROM orders WHERE auart IN ('PP01','ZP03','ZREF','ZP07') AND "
                              "stat NOT IN ('CRTD')").fetchall():
            bal = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? AND wrttp='04' "
                               "AND (gjahr<? OR (gjahr=? AND perio<=?)) AND vrgng<>'KOAO'",
                               ("OR" + o["aufnr"], gjahr, gjahr, perio)).fetchone()[0]
            new = bal if o["stat"] == "REL" and bal > 0 else 0
            prev = conn.execute("SELECT wip FROM pp_wip WHERE aufnr=? AND (gjahr<? OR (gjahr=? AND "
                                "perio<?)) ORDER BY gjahr DESC, perio DESC LIMIT 1",
                                (o["aufnr"], gjahr, gjahr, perio)).fetchone()
            prev = prev["wip"] if prev else 0
            delta = new - prev
            if not new and not prev:
                continue
            belnr = None
            if delta and not test:
                from fi.document import write
                belnr = write(conn, "SA", budat, user, "KKAO%s" % o["aufnr"],
                              "WIP order %s" % o["aufnr"], [
                                  dict(hkont=WIP_ACCOUNT, amount=delta, sgtxt="WIP %s" % o["aufnr"]),
                                  dict(hkont=WIP_CHANGE, amount=-delta,
                                       sgtxt="Change in WIP %s" % o["aufnr"])], tcode="KKAO")
            if not test:
                conn.execute("INSERT OR REPLACE INTO pp_wip VALUES (?,?,?,?,?)",
                             (o["aufnr"], gjahr, perio, new, belnr))
            out.append(dict(aufnr=o["aufnr"], matnr=o["matnr"], stat=o["stat"], wip=new,
                            previous=prev, delta=delta, belnr=belnr,
                            note="WIP" if new else "WIP cancelled (delivered / TECO)"))
    return out
