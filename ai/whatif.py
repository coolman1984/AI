"""What-If simulator (ZWHATIF - "ماذا لو"): change prices, volumes, costs, the dollar rate, salaries,
staff, payment terms, interest or an investment and see at once what happens to profit, margin,
break-even and cash - on the company's own figures from the books.

Model (one year, EGP): the year so far from the financial statements, annualised.
  revenue      = R10 sales revenue + R20 sales deductions
  material     = R30 cost of goods sold + R40 material consumption + R80 factory output / price differences
  personnel    = R50, other = R60, depreciation = R70, financial = R85 + R90
  result       = revenue + material + personnel + other + depreciation + financial   (costs negative)
Every lever changes one part; the result is linear in each lever, so the goal seek is exact.
Reads the books; writes only saved scenarios (whatif_scn).
"""
import json
import threading

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_int

WHATIF_SCHEMA = """
CREATE TABLE IF NOT EXISTS whatif_scn (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, params TEXT NOT NULL,
    usnam TEXT, ts TEXT
);
"""

# lever: (min, max, default, unit) - percentages as whole numbers, days, pieces, EGP
LEVERS = {
    "price": (-50, 100, 0, "%"), "volume": (-80, 200, 0, "%"), "material": (-50, 100, 0, "%"),
    "fx": (-50, 200, 0, "%"), "imported_pct": (0, 100, None, "%"), "salaries": (-50, 100, 0, "%"),
    "staff": (-500, 1000, 0, "people"), "other": (-80, 200, 0, "%"), "dso": (0, 365, None, "days"),
    "dpo": (0, 365, None, "days"), "rate": (-30, 30, 0, "pp"), "capex": (0, 10 ** 9, 0, "EGP"),
    "capex_years": (1, 30, 5, "years"), "capex_volume": (0, 200, 0, "%"),
}
LOAN_ACCOUNTS = ("070000",)
_L = threading.local()


def t(ar, en):
    return en if getattr(_L, "lang", "ar") == "en" else ar


def install(conn):
    conn.executescript(WHATIF_SCHEMA)


def _r(x):
    return round(x, 2)


# ------------------------------------------------------------------ baseline from the books
def baseline(conn):
    from fi.reports import cockpit, statements
    today = clock.today()
    y, m = today.year, today.month
    s = statements(conn, y, 1, m)
    n = {r["node"]: r for r in s["rows"]}
    first = conn.execute("SELECT MIN(budat) FROM acc_doc WHERE budat>=?", ("%04d-01-01" % y,)).fetchone()[0]
    months = (m - int(first[5:7]) + 1) if first else m
    months = max(1, months)
    k = 12.0 / months
    v = lambda *nodes: sum(n[x]["cur"] for x in nodes if x in n)  # noqa: E731
    revenue = v("R10", "R20")
    export = sum(a["cur"] for a in (n.get("R10") or {}).get("accounts", []) if a["hkont"] == "800100")
    loans = sum(a["cur"] for a in (n.get("P05") or {}).get("accounts", []) if a["hkont"] in LOAN_ACCOUNTS)
    payables = (n.get("P20") or {}).get("cur", 0)
    foreign = sum(a["cur"] for a in (n.get("P20") or {}).get("accounts", []) if a["hkont"] == "161000")
    kp = cockpit(conn, y, m)["kpi"]
    staff = conn.execute("SELECT COUNT(*), COALESCE(AVG(basic+allow_transport+allow_housing+allow_other),0) FROM hr_employee "
                         "WHERE COALESCE(leave_date,'')='' OR leave_date>?", (today.isoformat(),)).fetchone()
    pl = dict(revenue=revenue * k, material=v("R30", "R40", "R80") * k, personnel=v("R50") * k, other=v("R60") * k,
              depreciation=v("R70") * k, financial=v("R85", "R90") * k)
    return dict(year=y, months=months, period="01-%02d/%d" % (m, y), annualised=months != 12,
                pl={a: _r(b) for a, b in pl.items()}, result=_r(sum(pl.values())),
                export_share=_r(100.0 * export / revenue) if revenue else 0.0,
                imported_pct=_r(100.0 * foreign / payables) if payables else 0.0,
                loans=_r(loans), cash=_r(kp.get("cash") or 0), ar=_r(kp.get("ar") or 0), ap=_r(kp.get("ap") or 0),
                dso=_r(kp.get("dso") or 0), dpo=_r(kp.get("dpo") or 0),
                staff=staff[0], staff_cost_month=_r((staff[1] or 0) / 100.0 * 1.1875))   # + employer social insurance


# ------------------------------------------------------------------ the simulation
def _params(raw):
    raw = raw or {}
    out = {}
    for k, (lo, hi, dflt, _u) in LEVERS.items():
        v = raw.get(k)
        if v is None or str(v).strip() == "":
            out[k] = dflt
            continue
        try:
            x = float(str(v).replace(",", ""))
        except ValueError:
            raise MMError(t("قيمة غير صحيحة لـ %s: %s", "Invalid value for %s: %s") % (k, v), "WI", "901")
        if not lo <= x <= hi:
            raise MMError(t("%s لازم يكون بين %s و %s", "%s must be between %s and %s") % (k, lo, hi), "WI", "902")
        out[k] = x
    return out


def _check(b, p):
    if p["staff"] < -b["staff"]:
        raise MMError(t("مينفعش تقلل أكتر من عدد الموظفين الحالي (%d)", "Cannot remove more than the current head count (%d)")
                      % b["staff"], "WI", "908")


def _calc(b, p):
    """the simulated year: P&L lines, result, break-even, cash effects"""
    pl0 = b["pl"]
    imported = (b["imported_pct"] if p["imported_pct"] is None else p["imported_pct"]) / 100.0
    export = b["export_share"] / 100.0
    vol = (1 + p["volume"] / 100.0) * (1 + p["capex_volume"] / 100.0)
    fx = p["fx"] / 100.0
    rev = pl0["revenue"] * vol * (1 + p["price"] / 100.0) * (1 + export * fx)
    mat = pl0["material"] * vol * (1 + p["material"] / 100.0) * (1 + imported * fx)
    pers = pl0["personnel"] * (1 + p["salaries"] / 100.0) - p["staff"] * b["staff_cost_month"] * 12 * (1 + p["salaries"] / 100.0)
    oth = pl0["other"] * (1 + p["other"] / 100.0)
    dep = pl0["depreciation"] - (p["capex"] / p["capex_years"] if p["capex"] else 0)
    fin = pl0["financial"] - b["loans"] * p["rate"] / 100.0
    pl = dict(revenue=rev, material=mat, personnel=pers, other=oth, depreciation=dep, financial=fin)
    result = sum(pl.values())
    fixed = -(pers + oth + dep + fin)
    cm_ratio = (rev + mat) / rev if rev else 0
    breakeven = fixed / cm_ratio if cm_ratio > 0 else None
    dso = b["dso"] if p["dso"] is None else p["dso"]
    dpo = b["dpo"] if p["dpo"] is None else p["dpo"]
    cash_wc = (b["dso"] - dso) * rev / 365.0 + (dpo - b["dpo"]) * (-mat) / 365.0
    return dict(pl={k: _r(v) for k, v in pl.items()}, result=_r(result), margin=_r(100.0 * result / rev) if rev else 0.0,
                gross_margin=_r(100.0 * (rev + mat) / rev) if rev else 0.0, breakeven=_r(breakeven) if breakeven else None,
                cash_working_capital=_r(cash_wc), cash_capex=_r(-p["capex"]),
                cash_year=_r(result - dep + cash_wc - p["capex"]),      # profit + depreciation (no cash) + terms - investment
                dso=_r(dso), dpo=_r(dpo))


def _name(k):
    return {"price": t("سعر البيع", "Selling price"), "volume": t("الكمية المباعة", "Volume sold"),
            "material": t("تكلفة الخامات", "Material cost"), "fx": t("سعر الدولار", "Dollar rate"),
            "imported_pct": t("نسبة الخامات المستوردة", "Imported share of material"), "salaries": t("المرتبات", "Salaries"),
            "staff": t("عدد الموظفين", "Head count"), "other": t("مصاريف التشغيل", "Operating expenses"),
            "dso": t("أيام التحصيل", "Collection days"), "dpo": t("أيام الدفع للموردين", "Days to pay vendors"),
            "rate": t("سعر الفايدة", "Interest rate"), "capex": t("استثمار (ماكينة / خط)", "Investment (machine / line)"),
            "capex_years": t("عمر الاستثمار", "Investment life"),
            "capex_volume": t("زيادة الإنتاج من الاستثمار", "Extra volume from the investment")}[k]


def _fmt(v):
    return "{:,.0f}".format(v)


def _pl_word(v):
    return (t("ربح %s جنيه", "a profit of EGP %s") if v >= 0 else t("خسارة %s جنيه", "a loss of EGP %s")) % _fmt(abs(v))


def simulate(conn, raw=None, lang="ar"):
    _L.lang = "en" if lang == "en" else "ar"
    p = _params(raw)
    b = baseline(conn)
    _check(b, p)
    base = _calc(b, _params({}))
    sim = _calc(b, p)
    # what each lever does on its own (tornado), biggest first
    impact = []
    for k in ("price", "volume", "material", "fx", "salaries", "staff", "other", "rate", "capex"):
        single = dict((x, None) for x in LEVERS)
        if k == "capex":
            single.update(capex=p["capex"], capex_years=p["capex_years"], capex_volume=p["capex_volume"])
            if not p["capex"]:
                continue
        elif p[k] in (0, None):
            continue
        else:
            single[k] = p[k]
            if k == "fx":
                single["imported_pct"] = p["imported_pct"]
        d = _calc(b, _params(single))["result"] - base["result"]
        impact.append(dict(lever=k, name=_name(k), effect=_r(d)))
    impact.sort(key=lambda x: -abs(x["effect"]))
    diff = sim["result"] - base["result"]
    if not impact and p["dso"] is None and p["dpo"] is None:
        opinion = t("حرّك أي مؤشر وأنا أقولك يحصل إيه في الربح والفلوس.", "Move any lever and I tell you what happens to profit and cash.")
    else:
        parts = [t("السنة هتقفل على %s بدل %s - يعني %s %s جنيه.", "The year closes with %s instead of %s - %s by EGP %s.")
                 % (_pl_word(sim["result"]), _pl_word(base["result"]), t("أحسن", "better") if diff >= 0 else t("أسوأ", "worse"),
                    _fmt(abs(diff)))]
        if impact:
            top = impact[0]
            parts.append(t("أكبر تأثير من %s: %s جنيه.", "Biggest effect: %s, EGP %s.") % (top["name"], _fmt(top["effect"])))
        if sim["cash_working_capital"]:
            parts.append(t("وشروط الدفع والتحصيل %s %s جنيه كاش مرة واحدة.", "Payment terms %s EGP %s of cash once.")
                         % (t("بتوفّر", "free") if sim["cash_working_capital"] > 0 else t("بتسحب", "tie up"),
                            _fmt(abs(sim["cash_working_capital"]))))
        if sim["result"] < 0 <= base["result"]:
            parts.append(t("⚠️ السيناريو ده بيقلب الربح لخسارة.", "⚠️ This scenario turns the profit into a loss."))
        elif sim["result"] >= 0 > base["result"]:
            parts.append(t("✅ السيناريو ده بيقلب الخسارة لربح.", "✅ This scenario turns the loss into a profit."))
        if sim["breakeven"] is None and sim["pl"]["revenue"] > 0:
            parts.append(t("⚠️ تكلفة الخامات أكبر من المبيعات - مفيش نقطة تعادل مهما بعت؛ لازم ترفع السعر أو تقلل تكلفة الخامات.",
                           "⚠️ Material cost exceeds sales - no break-even at any volume; raise prices or cut material cost."))
        elif sim["breakeven"] and sim["pl"]["revenue"] < sim["breakeven"]:
            parts.append(t("المبيعات أقل من نقطة التعادل (%s جنيه) - لازم تبيع أكتر أو تقلل المصاريف الثابتة.",
                           "Sales are below break-even (EGP %s) - sell more or cut fixed costs.") % _fmt(sim["breakeven"]))
        opinion = " ".join(parts)
    return dict(baseline=b, base=base, sim=sim, diff=_r(diff), impact=impact, params=p, opinion=opinion, lang=_L.lang,
                levers={k: dict(name=_name(k), min=v[0], max=v[1], default=v[2], unit=v[3]) for k, v in LEVERS.items()})


def goal_seek(conn, target, lever, raw=None, lang="ar"):
    """the value of ONE lever (others as given) that gives the target profit for the year"""
    _L.lang = "en" if lang == "en" else "ar"
    if lever not in ("price", "volume", "material", "salaries", "other"):
        raise MMError(t("المؤشر ده مش متاح للهدف", "This lever cannot be used for the goal"), "WI", "903")
    try:
        target = float(str(target).replace(",", ""))
    except ValueError:
        raise MMError(t("اكتب الربح المطلوب رقم", "Enter the target profit as a number"), "WI", "904")
    p = _params(raw)
    b = baseline(conn)
    p0, p1 = dict(p, **{lever: 0}), dict(p, **{lever: 10})
    r0, r1 = _calc(b, p0)["result"], _calc(b, p1)["result"]
    if abs(r1 - r0) < 1e-6:
        raise MMError(t("المؤشر ده مالوش تأثير على الربح هنا", "This lever has no effect on the profit here"), "WI", "905")
    x = (target - r0) / ((r1 - r0) / 10.0)          # the result is linear in every single lever
    lo, hi = LEVERS[lever][0], LEVERS[lever][1]
    ok = lo <= x <= hi
    return dict(lever=lever, name=_name(lever), value=_r(x), possible=ok, target=_r(target),
                text=(t("عشان توصل لربح %s جنيه لازم %s يتغير %s%%.", "To reach a profit of EGP %s, %s must change by %s%%.")
                      % (_fmt(target), _name(lever), "{:+.1f}".format(x))) +
                     ("" if ok else t(" (ده خارج المدى المعقول %s..%s%%)", " (outside the sensible range %s..%s%%)") % (lo, hi)))


# ------------------------------------------------------------------ saved scenarios
def scenarios(conn):
    return [dict(r, params=json.loads(r["params"])) for r in conn.execute("SELECT * FROM whatif_scn ORDER BY id DESC")]


def save(conn, data, user):
    name = (data.get("name") or "").strip()
    if not name:
        raise MMError(t("اكتب اسم للسيناريو", "Enter a name for the scenario"), "WI", "906")
    p = _params(data.get("params"))
    with transaction(conn):
        sid = conn.execute("INSERT INTO whatif_scn (name, params, usnam, ts) VALUES (?,?,?,?)",
                           (name[:60], json.dumps(p), user, now_ts())).lastrowid
    return {"id": sid, "message": t("السيناريو \"%s\" اتحفظ", "Scenario \"%s\" saved") % name[:60]}


def delete(conn, sid, user):
    sid = parse_int(sid, "scenario")
    with transaction(conn):
        n = conn.execute("DELETE FROM whatif_scn WHERE id=?", (sid,)).rowcount
    if not n:
        raise MMError(t("السيناريو %s مش موجود", "Scenario %s does not exist") % sid, "WI", "907")
    return {"message": t("السيناريو اتمسح", "Scenario deleted")}


def compare(conn, ids, lang="ar"):
    _L.lang = "en" if lang == "en" else "ar"
    b = baseline(conn)
    base = _calc(b, _params({}))
    cols = [dict(name=t("الوضع الحالي", "Today"), result=base["result"], margin=base["margin"], revenue=base["pl"]["revenue"],
                 breakeven=base["breakeven"], cash=base["cash_year"])]
    for s in scenarios(conn):
        if s["id"] in ids:
            r = _calc(b, _params(s["params"]))
            cols.append(dict(id=s["id"], name=s["name"], result=r["result"], margin=r["margin"], revenue=r["pl"]["revenue"],
                             breakeven=r["breakeven"], cash=r["cash_year"]))
    best = max(cols[1:], key=lambda c: c["result"], default=None)
    return {"columns": cols, "best": best["name"] if best else None}


PRESETS = [
    ("fx20", ("الدولار زاد 20%", "Dollar +20%"), {"fx": 20}),
    ("price10", ("رفع الأسعار 10% وخسارة 5% من الكمية", "Prices +10%, volume -5%"), {"price": 10, "volume": -5}),
    ("cost5", ("تخفيض تكلفة الخامات 5%", "Material cost -5%"), {"material": -5}),
    ("raise15", ("زيادة المرتبات 15%", "Salaries +15%"), {"salaries": 15}),
    ("collect", ("تحصيل أسرع: 45 يوم", "Faster collection: 45 days"), {"dso": 45}),
    ("machine", ("ماكينة جديدة 2 مليون تزوّد الإنتاج 20%", "New machine EGP 2m, +20% output"),
     {"capex": 2000000, "capex_years": 5, "capex_volume": 20}),
]


def presets(lang="ar"):
    return [dict(code=c, name=n[1] if lang == "en" else n[0], params=p) for c, n, p in PRESETS]
