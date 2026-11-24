"""ZENERGY: gas and power per square metre.

Meters (kiln gas, spray dryer gas, dryers gas, electricity) are read once a day; consumption of a
day = reading - previous reading. Divided by the m2 sorted that day (grade 1 + 2) it gives m3 gas
and kWh per m2 and the energy cost per m2. A day more than 10 % above the average of the 28 days
before is flagged. Prices are per unit (EGP per m3 / kWh) and set by the user."""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_qty, value_of

KINDS = {"GAS": "m3", "POWER": "kWh"}
LIMIT_PCT = 10


def save_meter(conn, meter, text, kind, area, price, active=True):
    m = str(meter or "").strip().upper()
    if not m or len(m) > 12:
        raise MMError("Enter the meter (up to 12 characters)", "TL", "040")
    k = str(kind or "").strip().upper()
    if k not in KINDS:
        raise MMError("Kind %s is unknown (GAS, POWER)" % str(kind or ""), "TL", "041")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO energy_meter VALUES (?,?,?,?,?,?,?)",
                     (m, str(text or m).strip()[:60], k, KINDS[k], str(area or "").strip()[:30], parse_amount(price),
                      1 if active else 0))
    return m


def meters(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM energy_meter ORDER BY kind, meter")]


def save_reading(conn, meter, day, reading, user):
    m = str(meter or "").strip().upper()
    if not conn.execute("SELECT 1 FROM energy_meter WHERE meter=?", (m,)).fetchone():
        raise MMError("Meter %s does not exist (ZENERGY settings)" % str(meter or ""), "TL", "042")
    d = parse_date(day)
    if d > clock.today().isoformat():
        raise MMError("A reading cannot be in the future", "TL", "043")
    v = parse_qty(reading, allow_zero=True)
    before = conn.execute("SELECT day, reading FROM energy_reading WHERE meter=? AND day<? ORDER BY day DESC LIMIT 1",
                          (m, d)).fetchone()
    after = conn.execute("SELECT day, reading FROM energy_reading WHERE meter=? AND day>? ORDER BY day LIMIT 1",
                         (m, d)).fetchone()
    if before and v < before["reading"]:
        raise MMError("Reading %s is lower than %s of %s - a meter does not run backwards" % (
            v / 1000.0, before["reading"] / 1000.0, before["day"]), "TL", "044")
    if after and v > after["reading"]:
        raise MMError("Reading %s is higher than %s of %s" % (v / 1000.0, after["reading"] / 1000.0, after["day"]),
                      "TL", "045")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO energy_reading VALUES (?,?,?,?,?)", (m, d, v, user, now_ts()))
    return {"message": "Reading of %s on %s saved" % (m, d)}


def _consumption(conn, frm, to):
    """{day: {meter: milli units}} from the readings (first reading of the range needs one before it)"""
    out = {}
    for m in conn.execute("SELECT meter FROM energy_meter").fetchall():
        rs = conn.execute("SELECT day, reading FROM energy_reading WHERE meter=? AND day<=? ORDER BY day",
                          (m[0], to)).fetchall()
        for a, b in zip(rs, rs[1:]):
            if b["day"] >= frm:
                out.setdefault(b["day"], {})[m[0]] = b["reading"] - a["reading"]
    return out


def report(conn, frm=None, to=None):
    to = parse_date(to)
    frm = parse_date(frm) if frm else (datetime.date.fromisoformat(to) - datetime.timedelta(days=29)).isoformat()
    base_from = (datetime.date.fromisoformat(frm) - datetime.timedelta(days=28)).isoformat()
    ms = {r["meter"]: r for r in meters(conn)}
    cons = _consumption(conn, base_from, to)
    m2 = {r[0]: r[1] for r in conn.execute("SELECT day, SUM(grade1+grade2) FROM tile_sort WHERE day BETWEEN ? AND ? "
                                           "GROUP BY day", (base_from, to))}
    rows = []
    for day in sorted(set(cons) | set(m2)):
        c = cons.get(day, {})
        gas = sum(q for k, q in c.items() if ms[k]["kind"] == "GAS")
        power = sum(q for k, q in c.items() if ms[k]["kind"] == "POWER")
        cost = sum(value_of(q, ms[k]["price"], 1) for k, q in c.items())
        sq = m2.get(day, 0)
        rows.append(dict(day=day, m2=sq, gas=gas, power=power, cost=cost, meters=c,
                         gas_m2=round(gas / sq, 3) if sq else None, kwh_m2=round(power / sq, 3) if sq else None,
                         cost_m2=round(cost / 100.0 / (sq / 1000.0), 2) if sq else None))
    for i, r in enumerate(rows):                       # baseline = average of the 28 days before
        d0 = (datetime.date.fromisoformat(r["day"]) - datetime.timedelta(days=28)).isoformat()
        prev = [x for x in rows[:i] if x["day"] >= d0 and x["m2"] and x["gas"]]
        r["base_gas_m2"] = round(sum(x["gas"] for x in prev) / sum(x["m2"] for x in prev), 3) if prev else None
        r["high"] = bool(r["gas_m2"] and r["base_gas_m2"] and r["gas_m2"] > r["base_gas_m2"] * (100 + LIMIT_PCT) / 100.0)
    shown = [r for r in rows if r["day"] >= frm]
    tot_m2 = sum(r["m2"] for r in shown)
    tot = dict(m2=tot_m2, gas=sum(r["gas"] for r in shown), power=sum(r["power"] for r in shown),
               cost=sum(r["cost"] for r in shown))
    tot.update(gas_m2=round(tot["gas"] / tot_m2, 3) if tot_m2 else None,
               kwh_m2=round(tot["power"] / tot_m2, 3) if tot_m2 else None,
               cost_m2=round(tot["cost"] / 100.0 / (tot_m2 / 1000.0), 2) if tot_m2 else None)
    per_meter = []
    for k, m in ms.items():
        q = sum(r["meters"].get(k, 0) for r in shown)
        per_meter.append(dict(meter=k, text=m["text"], kind=m["kind"], unit=m["unit"], qty=q,
                              cost=value_of(q, m["price"], 1), per_m2=round(q / tot_m2, 3) if tot_m2 else None))
    return dict(frm=frm, to=to, rows=shown, total=tot, meters=per_meter, limit_pct=LIMIT_PCT,
                missing=[k for k in ms if ms[k]["active"] and not conn.execute(
                    "SELECT 1 FROM energy_reading WHERE meter=? AND day=?", (k, to)).fetchone()])


def day_text(conn, day=None):
    """one line for the morning briefing: gas per m2 of the last day with production"""
    d = parse_date(day) if day else (clock.today() - datetime.timedelta(days=1)).isoformat()
    if not conn.execute("SELECT 1 FROM energy_meter").fetchone():
        return ""
    r = report(conn, (datetime.date.fromisoformat(d) - datetime.timedelta(days=6)).isoformat(), d)
    days = [x for x in r["rows"] if x["gas_m2"]]
    if not days:
        return ""
    x = days[-1]
    note = " ⚠️ أعلى من المعتاد (%.2f)" % x["base_gas_m2"] if x["high"] else (
        " (المعتاد %.2f)" % x["base_gas_m2"] if x["base_gas_m2"] else "")
    return "- الغاز يوم %s: %.2f م3 لكل م2، والطاقة %.2f جنيه لكل م2%s" % (
        x["day"][8:10] + "/" + x["day"][5:7], x["gas_m2"], x["cost_m2"], note)
