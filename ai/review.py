"""Daily review (ZDAY): what happened today in every module, compared with a normal working day,
with a plain-language opinion per module - good, improving or needs attention - and what to do.

"Normal" = the average of the working days (Friday off) of the 28 days before the chosen day.
Read only: nothing here writes to the database. Amounts in EGP, quantities in units.
"""
import datetime
import threading

from mm import util as clock
from mm.util import parse_date

GOOD, UP, ATTN, QUIET = "GOOD", "UP", "ATTN", "QUIET"
VERDICT = {GOOD: ("جيد", "🟢"), UP: ("في تقدم", "🚀"), ATTN: ("محتاج تعديل", "🔴"), QUIET: ("يوم هادي", "⚪")}
DAYS_BACK = 28
WEEKEND = (4,)                                     # Friday


def _fmt(v, unit=""):
    s = "{:,.0f}".format(v) if abs(v) >= 100 or float(v).is_integer() else "{:,.1f}".format(v)
    return s + ((" " + unit) if unit else "")


def _days(day, n):
    d = datetime.date.fromisoformat(day)
    return [(d - datetime.timedelta(days=i)).isoformat() for i in range(n, 0, -1)]


def _series(conn, sql, day, n=7):
    """value per day for the last n days up to the chosen day (sql has one ? for the day)"""
    return [{"day": d, "value": _one(conn, sql, d)} for d in _days(day, n - 1) + [day]]


def _one(conn, sql, d):
    r = conn.execute(sql, (d,)).fetchone()
    return float((r[0] if r else 0) or 0)


def _normal(conn, sql, day):
    """average per working day over the 28 days before the day"""
    vals = [_one(conn, sql, d) for d in _days(day, DAYS_BACK) if datetime.date.fromisoformat(d).weekday() not in WEEKEND]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _verdict(today, normal, better, red, day, early=False):
    """better = +1 higher is better (sales, output), -1 lower is better (breakdowns, scrap)"""
    if red:
        return ATTN
    off = datetime.date.fromisoformat(day).weekday() in WEEKEND
    if better < 0:                                 # breakdowns, rejects, overtime
        if not today:
            return GOOD
        if normal >= 1 and today <= normal * 0.7:
            return UP
        return ATTN if today > max(normal * 1.3, 1) else GOOD
    if not today:
        if not normal or normal < 1 or off or early:
            return QUIET                           # not a daily event / day off / day not over yet
        return ATTN
    if not normal or today >= normal * 1.15:
        return UP
    if today >= normal * 0.7 or off or early:
        return GOOD
    return ATTN


def _compare(today, normal, better, what, unit=""):
    if not normal and not today:
        return "مافيش %s النهارده ولا في الأيام اللي فاتت." % what
    if not today and better < 0:
        return "مافيش %s النهارده 👍 (المعتاد %s)." % (what, _fmt(normal, unit))
    if not normal:
        return "%s النهارده %s، والأيام اللي فاتت ماكانش فيه حاجة." % (what, _fmt(today, unit))
    if not today and normal < 1:
        return "مافيش %s النهارده - ده بيحصل تقريباً مرة كل %d يوم." % (what, max(2, round(1 / normal)))
    pct = round(100.0 * (today - normal) / normal)
    if abs(pct) < 10:
        rel = "قريب من المعتاد"
    elif normal < 1 and today >= 1:
        rel = "أكتر من المعتاد (مش بيحصل كل يوم)"
    elif pct >= 100:
        rel = "حوالي %s أضعاف المعتاد" % ("{:.1f}".format(today / normal).rstrip("0").rstrip("."))
    elif pct > 0:
        rel = "أعلى من المعتاد بـ %d%%" % pct
    else:
        rel = "أقل من المعتاد بـ %d%%" % -pct
    good = (pct > 0) == (better > 0)
    return "%s النهارده %s، %s (المعتاد %s)%s." % (what, _fmt(today, unit), rel, _fmt(normal, unit),
                                                  "" if abs(pct) < 10 else (" 👍" if good else " 👎"))


def _module(conn, day, code, name, icon, tcode, main, facts, red, yellow, advice_ok, early=False):
    """main = (label, sql_one_day, better, unit, scale); facts = [(label, value, unit)]"""
    label, sql, better, unit, scale = main
    early = early or getattr(_EARLY, "day", None) == day
    today = round(_one(conn, sql, day) / scale, 2)
    normal = round(_normal(conn, sql, day) / scale, 2)
    series = [dict(s, value=round(s["value"] / scale, 2)) for s in _series(conn, sql, day)]
    v = _verdict(today, normal, better, red, day, early)
    opinion = [_compare(today, normal, better, label, unit)]
    if v == UP:
        opinion.append("ده تقدم كويس - حافظوا على نفس الإيقاع." if better > 0 else "أحسن من المعتاد - استمروا.")
    elif v == GOOD:
        opinion.append("الأداء طبيعي ومستقر.")
    elif v == QUIET:
        opinion.append("يوم إجازة." if datetime.date.fromisoformat(day).weekday() in WEEKEND else
                       "اليوم لسه ماخلصش - استنى لآخر اليوم." if early else
                       "وده عادي." if normal < 1 else
                       "لو فيه شغل حصل فعلاً، اتأكد إنه اتسجل في البرنامج.")
    elif not red:
        opinion.append("الأداء أضعف من المعتاد - اعرف السبب النهارده." if better > 0 else "أعلى من المعتاد - محتاج متابعة.")
    advice = [x for x in red + yellow] or ([advice_ok] if advice_ok and v in (GOOD, UP) else [])
    return dict(code=code, name=name, icon=icon, tcode=tcode, verdict=v, verdict_text=VERDICT[v][0], emoji=VERDICT[v][1],
                main=dict(label=label, today=today, normal=normal, unit=unit, better=better), series=series,
                facts=[dict(label=a, value=b, unit=c) for a, b, c in facts], problems=red, watch=yellow,
                opinion=" ".join(opinion), advice=advice)


# ------------------------------------------------------------------ the modules
def _sales(conn, day, al):
    q = lambda s: conn.execute(s, (day,)).fetchone()  # noqa: E731
    o = q("SELECT COUNT(*), COALESCE(SUM(netwr),0) FROM sd_vbak WHERE substr(erdat,1,10)=? AND vbtyp='C'")
    blocked = [a for a in al if a["cat"] == "CREDIT"]
    from fi.reports import aging
    a = aging(conn, "D", day)
    overdue = sum(r["total"] - r["not_due"] for r in a["rows"])
    total = sum(r["total"] for r in a["rows"])
    red = ["%d أمر بيع واقف على حد الائتمان - راجعهم في VKM3." % len(blocked)] if blocked else []
    yellow = []
    if total > 0 and overdue / total > 0.3:
        yellow.append("%d%% من فلوس العملاء متأخرة (%s جنيه) - ابدأ التحصيل من أكبر عميل (S_ALR_87012168)."
                      % (round(100 * overdue / total), _fmt(overdue)))
    return _module(conn, day, "SD", "المبيعات", "🛒", "ZSD_COCKPIT",
                   ("الفواتير", "SELECT COALESCE(SUM(netwr),0) FROM billing WHERE fkdat=? AND cancelled=0 AND vbtyp IN ('M','O','P')",
                    1, "جنيه", 100.0),
                   [("أوامر بيع جديدة", o[0], "أمر"), ("قيمة الأوامر", round(o[1] / 100.0), "جنيه"),
                    ("فلوس متأخرة عند العملاء", round(overdue), "جنيه")],
                   red, yellow, "تابع تسليم الأوامر الجديدة في ميعادها.")


def _stock(conn, day, al):
    low = [a for a in al if a["cat"] == "STOCK"]
    n = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat=? AND tcode IN ('MIGO','MB1A','MBST','VL02N')", (day,)).fetchone()[0]
    yellow = ["%d صنف تحت حد الأمان - اعمل طلبات شراء (MMBE / ME51N)." % len(low)] if low else []
    return _module(conn, day, "MM", "المخازن", "📦", "ZMM_COCKPIT",
                   ("حركات المخزن", "SELECT COUNT(*) FROM mat_doc WHERE budat=?", 1, "حركة", 1.0),
                   [("استلام وصرف وتسليم", n, "حركة"), ("أصناف تحت حد الأمان", len(low), "صنف")],
                   [], yellow, "")


def _purchasing(conn, day, al):
    from pur.analytics import cockpit
    c = cockpit(conn, day[:8] + "01", day)
    late = c["overdue"]
    gr = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat=? AND tcode='MIGO'", (day,)).fetchone()[0]
    yellow = ["%d بند شراء متأخر عن ميعاد التوريد - كلّم الموردين (ME2M / ZPUR_REMIND)." % len(late)] if late else []
    return _module(conn, day, "PUR", "المشتريات", "🧾", "ZPUR_COCKPIT",
                   ("أوامر الشراء", "SELECT COUNT(*) FROM po_header WHERE bedat=?", 1, "أمر", 1.0),
                   [("استلام بضاعة من موردين", gr, "استلام"), ("بنود متأخرة", len(late), "بند")],
                   [], yellow, "")


def _production(conn, day, al):
    q = conn.execute("SELECT COALESCE(SUM(lmnga),0), COALESCE(SUM(xmnga),0) FROM confirmation WHERE budat=? AND "
                     "COALESCE(stokz,0)=0", (day,)).fetchone()
    good, scrap = q[0] / 1000.0, q[1] / 1000.0
    scrap_pct = round(100.0 * scrap / (good + scrap), 1) if good + scrap else 0.0
    loss = conn.execute("SELECT COALESCE(SUM(minutes),0) FROM pp_loss WHERE datum=?", (day,)).fetchone()[0]
    from pp.daily import pending
    p = pending(conn, day)
    red, yellow = [], []
    if scrap_pct > 3:
        red.append("نسبة الهالك %s%% - أعلى من 3%%، راجع السبب مع الجودة (ZPP_DM_PDEFECT)." % scrap_pct)
    if p["late"]:
        yellow.append("%d أمر إنتاج متأخر - راجع الأولويات في اجتماع الصبح (ZPP_DM_PENDING)." % p["late"])
    if loss >= 120:
        yellow.append("%s دقيقة توقف النهارده - شوف الأسباب (ZPP_LOSS)." % _fmt(loss))
    return _module(conn, day, "PP", "الإنتاج", "🏭", "ZPP_BOARD",
                   ("الإنتاج السليم", "SELECT COALESCE(SUM(lmnga),0) FROM confirmation WHERE budat=? AND COALESCE(stokz,0)=0",
                    1, "وحدة", 1000.0),
                   [("الهالك", round(scrap, 1), "وحدة"), ("نسبة الهالك", scrap_pct, "%"), ("دقايق توقف", loss, "دقيقة"),
                    ("أوامر متأخرة", p["late"], "أمر")],
                   red, yellow, "خلي الخطة بكره على نفس المعدل.")


def _quality(conn, day, al):
    rej = [a for a in al if a["cat"] == "QUAL"]
    dec = conn.execute("SELECT COUNT(*), COALESCE(SUM(qty_rej),0) FROM qm_lot WHERE ud_date=?", (day,)).fetchone()
    waiting = conn.execute("SELECT COUNT(*) FROM qm_lot WHERE status<>'UD' AND created<=?",
                           ((datetime.date.fromisoformat(day) - datetime.timedelta(days=3)).isoformat(),)).fetchone()[0]
    red = ["فيه %d دفعة اترفضت - اعمل شكوى للمورد وتابع الإجراء (QM01)." % len(rej)] if rej else []
    yellow = ["%d دفعة مستنية فحص أكتر من 3 أيام - البضاعة واقفة (QA32)." % waiting] if waiting else []
    return _module(conn, day, "QM", "الجودة", "✅", "ZQM_COCKPIT",
                   ("الكمية المرفوضة", "SELECT COALESCE(SUM(qty_rej),0) FROM qm_lot WHERE ud_date=?", -1, "وحدة", 1000.0),
                   [("دفعات اتفحصت", dec[0], "دفعة"), ("مستنية فحص +3 أيام", waiting, "دفعة")],
                   red, yellow, "")


def _maintenance(conn, day, al):
    down = [a for a in al if a["cat"] == "MACH"]
    opn = conn.execute("SELECT COUNT(*) FROM pm_order WHERE status NOT IN ('TECO','CLSD','CLOSED')").fetchone()[0]
    red = ["%d ماكينة واقفة دلوقتي - أولوية لأمر الصيانة (ZPM_ORDERS)." % len(down)] if down else []
    return _module(conn, day, "PM", "الصيانة", "🔧", "ZPM_COCKPIT",
                   ("أعطال الماكينات", "SELECT COUNT(*) FROM pm_notif WHERE qmart='M2' AND substr(start,1,10)=?", -1, "عطل", 1.0),
                   [("ماكينات واقفة الآن", len(down), "ماكينة"), ("أوامر صيانة مفتوحة", opn, "أمر")],
                   red, [], "")


def _finance(conn, day, al):
    from fi.reports import cockpit
    d = datetime.date.fromisoformat(day)
    k = cockpit(conn, d.year, d.month)["kpi"]
    yellow = []
    if k.get("cash") is not None and k.get("ap") and k["cash"] < k["ap"] * 0.2:
        yellow.append("النقدية (%s) أقل من 20%% من فلوس الموردين (%s) - راجع التدفق النقدي." % (_fmt(k["cash"]), _fmt(k["ap"])))
    red = [] if k.get("balanced", True) else ["الميزانية مش متزنة - راجع القيود (F.01)."]
    return _module(conn, day, "FI", "الحسابات", "💰", "ZFI_COCKPIT",
                   ("القيود المتسجلة", "SELECT COUNT(*) FROM acc_doc WHERE budat=?", 1, "قيد", 1.0),
                   [("النقدية والبنوك", round(k.get("cash") or 0), "جنيه"), ("عند العملاء", round(k.get("ar") or 0), "جنيه"),
                    ("للموردين", round(k.get("ap") or 0), "جنيه"), ("نتيجة الشهر", round(k.get("result") or 0), "جنيه")],
                   red, yellow, "")


def _hr(conn, day, al):
    leave = conn.execute("SELECT COUNT(*) FROM hr_absence WHERE status='A' AND begda<=? AND endda>=?", (day, day)).fetchone()[0]
    req = conn.execute("SELECT COUNT(*) FROM hr_absence WHERE status='R'").fetchone()[0]
    staff = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE COALESCE(leave_date,'')='' OR leave_date>?", (day,)).fetchone()[0]
    yellow = ["%d طلب إجازة مستني رد - ردّ عليهم (ZLEAVE)." % req] if req else []
    if staff and leave / staff > 0.15:
        yellow.append("%d%% من الموظفين في إجازة النهارده - راجع تغطية الورديات." % round(100 * leave / staff))
    return _module(conn, day, "HR", "الموارد البشرية", "👥", "ZHR_COCKPIT",
                   ("ساعات الإضافي", "SELECT COALESCE(SUM(hours),0) FROM hr_overtime WHERE datum=?", -1, "ساعة", 1000.0),
                   [("الموظفين", staff, "موظف"), ("في إجازة النهارده", leave, "موظف"), ("طلبات إجازة مفتوحة", req, "طلب")],
                   [], yellow, "")


def _tax(conn, day, al):
    from tax.returns import calendar_year
    d = datetime.date.fromisoformat(day)
    rows = calendar_year(conn, d.year)["rows"]
    late = [r for r in rows if r["status"] == "overdue"]
    soon = [r for r in rows if r["status"] not in ("paid", "overdue") and 0 <= r["days"] <= 7]
    red = ["%d إقرار متأخر عن ميعاده - قدّمه فوراً عشان الغرامة (ZTAX_CAL)." % len(late)] if late else []
    yellow = ["%s مطلوب خلال %d يوم." % (r["label"], r["days"]) for r in soon[:3]]
    m = _module(conn, day, "TAX", "الضرائب", "🏛️", "ZTAX_CAL",
                ("الفواتير الإلكترونية المبعوتة", "SELECT COUNT(*) FROM sd_einv WHERE substr(ts,1,10)=?", 1, "فاتورة", 1.0),
                [("إقرارات متأخرة", len(late), "إقرار"), ("مطلوب خلال أسبوع", len(soon), "إقرار")],
                red, yellow, "")
    if not red and not yellow and m["verdict"] in (ATTN, QUIET):
        m.update(verdict=GOOD, verdict_text=VERDICT[GOOD][0], emoji=VERDICT[GOOD][1],
                 opinion="كل المواعيد الضريبية متغطية - مافيش حاجة متأخرة.")
    return m


_EARLY = threading.local()


def default_day():
    """after 4 pm today, before that the last working day (the review of a finished day)"""
    n = clock.now()
    d = n.date()
    if n.hour >= 16:
        return d.isoformat()
    d -= datetime.timedelta(days=1)
    while d.weekday() in WEEKEND:
        d -= datetime.timedelta(days=1)
    return d.isoformat()


MODULES = [("SD", _sales), ("PP", _production), ("MM", _stock), ("PUR", _purchasing), ("QM", _quality), ("PM", _maintenance),
           ("FI", _finance), ("TAX", _tax), ("HR", _hr)]
AREA = {"SD": "SD", "PP": "PP", "MM": "MM", "PUR": "PUR", "QM": "MM", "PM": "PP", "FI": "FI", "TAX": "FI", "HR": "HR"}


def day_review(conn, day=None, user=None, allowed=None):
    """allowed(area) -> bool (None = everything)"""
    from notify.engine import alerts
    day = parse_date(day) if day else default_day()
    n_ = clock.now()
    early = day == n_.date().isoformat() and n_.hour < 16
    _EARLY.day = day if early else None
    al = alerts(conn, user)
    out = []
    for code, fn in MODULES:
        if allowed is not None and not allowed(AREA[code]):
            continue
        out.append(fn(conn, day, al))
    n = {k: sum(1 for m in out if m["verdict"] == k) for k in VERDICT}
    if n[ATTN]:
        overall = "النهارده فيه %d موديول محتاج تعديل: %s. ابدأ بيهم." % (
            n[ATTN], "، ".join(m["name"] for m in out if m["verdict"] == ATTN))
    elif n[UP]:
        overall = "يوم كويس: %s في تقدم، والباقي طبيعي." % "، ".join(m["name"] for m in out if m["verdict"] == UP)
    else:
        overall = "يوم طبيعي ومستقر في كل الموديولات."
    weekday = ["الاتنين", "التلات", "الأربع", "الخميس", "الجمعة", "السبت", "الحد"][datetime.date.fromisoformat(day).weekday()]
    return {"day": day, "weekday": weekday, "early": early, "modules": out, "counts": n, "overall": overall,
            "legend": {k: dict(text=v[0], emoji=v[1]) for k, v in VERDICT.items()},
            "note": "المقارنة مع متوسط أيام الشغل في آخر %d يوم (الجمعة إجازة)." % DAYS_BACK}
