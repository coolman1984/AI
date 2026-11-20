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
VERDICT = {GOOD: ("جيد", "🟢", "Good"), UP: ("في تقدم", "🚀", "Improving"), ATTN: ("محتاج تعديل", "🔴", "Needs attention"),
           QUIET: ("يوم هادي", "⚪", "Quiet day")}
LANGS = ("ar", "en")
_L = threading.local()


def t(ar, en):
    """the text in the language of this review (Arabic or English)"""
    return en if getattr(_L, "lang", "ar") == "en" else ar


def _vt(v):
    return VERDICT[v][2] if getattr(_L, "lang", "ar") == "en" else VERDICT[v][0]
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
    w = what[0].lower() + what[1:] if getattr(_L, "lang", "ar") == "en" else what     # "No purchase orders today"
    if not normal and not today:
        return t("مافيش %s النهارده ولا في الأيام اللي فاتت.", "No %s today and none in the last weeks.") % w
    if not today and better < 0:
        return t("مافيش %s النهارده 👍 (المعتاد %s).", "No %s today 👍 (normal %s).") % (w, _fmt(normal, unit))
    if not normal:
        return t("%s النهارده %s، والأيام اللي فاتت ماكانش فيه حاجة.", "%s today: %s; nothing in the last weeks.") % (what, _fmt(today, unit))
    if not today and normal < 1:
        return t("مافيش %s النهارده - ده بيحصل تقريباً مرة كل %d يوم.", "No %s today - this happens about once every %d days.") % (w, max(2, round(1 / normal)))
    pct = round(100.0 * (today - normal) / normal)
    if abs(pct) < 10:
        rel = t("قريب من المعتاد", "close to normal")
    elif normal < 1 and today >= 1:
        rel = t("أكتر من المعتاد (مش بيحصل كل يوم)", "more than usual (not a daily event)")
    elif pct >= 100:
        rel = t("حوالي %s أضعاف المعتاد", "about %s times normal") % ("{:.1f}".format(today / normal).rstrip("0").rstrip("."))
    elif pct > 0:
        rel = t("أعلى من المعتاد بـ %d%%", "%d%% above normal") % pct
    else:
        rel = t("أقل من المعتاد بـ %d%%", "%d%% below normal") % -pct
    good = (pct > 0) == (better > 0)
    return t("%s النهارده %s، %s (المعتاد %s)%s.", "%s today: %s, %s (normal %s)%s.") % (what, _fmt(today, unit), rel, _fmt(normal, unit),
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
        opinion.append(t("ده تقدم كويس - حافظوا على نفس الإيقاع.", "Good progress - keep the same pace.") if better > 0
                       else t("أحسن من المعتاد - استمروا.", "Better than usual - keep it up."))
    elif v == GOOD:
        opinion.append(t("الأداء طبيعي ومستقر.", "Normal and stable."))
    elif v == QUIET:
        opinion.append(t("يوم إجازة.", "Day off.") if datetime.date.fromisoformat(day).weekday() in WEEKEND else
                       t("اليوم لسه ماخلصش - استنى لآخر اليوم.", "The day is not over yet - check again in the evening.") if early else
                       t("وده عادي.", "That is normal.") if normal < 1 else
                       t("لو فيه شغل حصل فعلاً، اتأكد إنه اتسجل في البرنامج.", "If work was done, make sure it is posted in NERP."))
    elif not red:
        opinion.append(t("الأداء أضعف من المعتاد - اعرف السبب النهارده.", "Weaker than usual - find the reason today.") if better > 0
                       else t("أعلى من المعتاد - محتاج متابعة.", "Higher than usual - follow it up."))
    advice = [x for x in red + yellow] or ([advice_ok] if advice_ok and v in (GOOD, UP) else [])
    return dict(code=code, name=name, icon=icon, tcode=tcode, verdict=v, verdict_text=_vt(v), emoji=VERDICT[v][1],
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
    red = [t("%d أمر بيع واقف على حد الائتمان - راجعهم في VKM3.", "%d sales orders blocked on the credit limit - review them in VKM3.") % len(blocked)] if blocked else []
    yellow = []
    if total > 0 and overdue / total > 0.3:
        yellow.append(t("%d%% من فلوس العملاء متأخرة (%s جنيه) - ابدأ التحصيل من أكبر عميل (S_ALR_87012168).",
                        "%d%% of the receivables are overdue (%s EGP) - start collecting from the largest customer (S_ALR_87012168).")
                      % (round(100 * overdue / total), _fmt(overdue)))
    return _module(conn, day, "SD", t("المبيعات", "Sales"), "🛒", "ZSD_COCKPIT",
                   (t("الفواتير", "Invoiced"), "SELECT COALESCE(SUM(netwr),0) FROM billing WHERE fkdat=? AND cancelled=0 AND vbtyp IN ('M','O','P')",
                    1, t("جنيه", "EGP"), 100.0),
                   [(t("أوامر بيع جديدة", "New sales orders"), o[0], t("أمر", "orders")),
                    (t("قيمة الأوامر", "Order value"), round(o[1] / 100.0), t("جنيه", "EGP")),
                    (t("فلوس متأخرة عند العملاء", "Overdue receivables"), round(overdue), t("جنيه", "EGP"))],
                   red, yellow, t("تابع تسليم الأوامر الجديدة في ميعادها.", "Follow up that the new orders are delivered on time."))


def _stock(conn, day, al):
    low = [a for a in al if a["cat"] == "STOCK"]
    n = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat=? AND tcode IN ('MIGO','MB1A','MBST','VL02N')", (day,)).fetchone()[0]
    yellow = [t("%d صنف تحت حد الأمان - اعمل طلبات شراء (MMBE / ME51N).", "%d materials below safety stock - create purchase requisitions (MMBE / ME51N).") % len(low)] if low else []
    return _module(conn, day, "MM", t("المخازن", "Inventory"), "📦", "ZMM_COCKPIT",
                   (t("حركات المخزن", "Stock movements"), "SELECT COUNT(*) FROM mat_doc WHERE budat=?", 1, t("حركة", "documents"), 1.0),
                   [(t("استلام وصرف وتسليم", "Receipts, issues, deliveries"), n, t("حركة", "documents")),
                    (t("أصناف تحت حد الأمان", "Below safety stock"), len(low), t("صنف", "materials"))],
                   [], yellow, "")


def _purchasing(conn, day, al):
    from pur.analytics import cockpit
    c = cockpit(conn, day[:8] + "01", day)
    late = c["overdue"]
    gr = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat=? AND tcode='MIGO'", (day,)).fetchone()[0]
    yellow = [t("%d بند شراء متأخر عن ميعاد التوريد - كلّم الموردين (ME2M / ZPUR_REMIND).", "%d PO items are late - remind the vendors (ME2M / ZPUR_REMIND).") % len(late)] if late else []
    return _module(conn, day, "PUR", t("المشتريات", "Purchasing"), "🧾", "ZPUR_COCKPIT",
                   (t("أوامر الشراء", "Purchase orders"), "SELECT COUNT(*) FROM po_header WHERE bedat=?", 1, t("أمر", "orders"), 1.0),
                   [(t("استلام بضاعة من موردين", "Goods receipts"), gr, t("استلام", "receipts")),
                    (t("بنود متأخرة", "Late PO items"), len(late), t("بند", "items"))],
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
        red.append(t("نسبة الهالك %s%% - أعلى من 3%%، راجع السبب مع الجودة (ZPP_DM_PDEFECT).", "Scrap %s%% - above 3%%, find the cause with quality (ZPP_DM_PDEFECT).") % scrap_pct)
    if p["late"]:
        yellow.append(t("%d أمر إنتاج متأخر - راجع الأولويات في اجتماع الصبح (ZPP_DM_PENDING).", "%d production orders are late - set priorities in the morning meeting (ZPP_DM_PENDING).") % p["late"])
    if loss >= 120:
        yellow.append(t("%s دقيقة توقف النهارده - شوف الأسباب (ZPP_LOSS).", "%s minutes of downtime - check the reasons (ZPP_LOSS).") % _fmt(loss))
    return _module(conn, day, "PP", t("الإنتاج", "Production"), "🏭", "ZPP_BOARD",
                   (t("الإنتاج السليم", "Good output"), "SELECT COALESCE(SUM(lmnga),0) FROM confirmation WHERE budat=? AND COALESCE(stokz,0)=0",
                    1, t("وحدة", "units"), 1000.0),
                   [(t("الهالك", "Scrap"), round(scrap, 1), t("وحدة", "units")), (t("نسبة الهالك", "Scrap rate"), scrap_pct, "%"),
                    (t("دقايق توقف", "Downtime"), loss, t("دقيقة", "min")), (t("أوامر متأخرة", "Late orders"), p["late"], t("أمر", "orders"))],
                   red, yellow, t("خلي الخطة بكره على نفس المعدل.", "Keep tomorrow's plan at the same rate."))


def _quality(conn, day, al):
    rej = [a for a in al if a["cat"] == "QUAL"]
    dec = conn.execute("SELECT COUNT(*), COALESCE(SUM(qty_rej),0) FROM qm_lot WHERE ud_date=?", (day,)).fetchone()
    waiting = conn.execute("SELECT COUNT(*) FROM qm_lot WHERE status<>'UD' AND created<=?",
                           ((datetime.date.fromisoformat(day) - datetime.timedelta(days=3)).isoformat(),)).fetchone()[0]
    red = [t("فيه %d دفعة اترفضت - اعمل شكوى للمورد وتابع الإجراء (QM01).", "%d lots rejected - raise a complaint to the vendor and follow the action (QM01).") % len(rej)] if rej else []
    yellow = [t("%d دفعة مستنية فحص أكتر من 3 أيام - البضاعة واقفة (QA32).", "%d lots waiting for inspection over 3 days - the goods are blocked (QA32).") % waiting] if waiting else []
    return _module(conn, day, "QM", t("الجودة", "Quality"), "✅", "ZQM_COCKPIT",
                   (t("الكمية المرفوضة", "Rejected quantity"), "SELECT COALESCE(SUM(qty_rej),0) FROM qm_lot WHERE ud_date=?", -1, t("وحدة", "units"), 1000.0),
                   [(t("دفعات اتفحصت", "Lots decided"), dec[0], t("دفعة", "lots")),
                    (t("مستنية فحص +3 أيام", "Waiting 3+ days"), waiting, t("دفعة", "lots"))],
                   red, yellow, "")


def _maintenance(conn, day, al):
    down = [a for a in al if a["cat"] == "MACH"]
    opn = conn.execute("SELECT COUNT(*) FROM pm_order WHERE status NOT IN ('TECO','CLSD','CLOSED')").fetchone()[0]
    red = [t("%d ماكينة واقفة دلوقتي - أولوية لأمر الصيانة (ZPM_ORDERS).", "%d machines are down now - maintenance order first (ZPM_ORDERS).") % len(down)] if down else []
    return _module(conn, day, "PM", t("الصيانة", "Maintenance"), "🔧", "ZPM_COCKPIT",
                   (t("أعطال الماكينات", "Breakdowns"), "SELECT COUNT(*) FROM pm_notif WHERE qmart='M2' AND substr(start,1,10)=?", -1, t("عطل", "breakdowns"), 1.0),
                   [(t("ماكينات واقفة الآن", "Machines down now"), len(down), t("ماكينة", "machines")),
                    (t("أوامر صيانة مفتوحة", "Open maintenance orders"), opn, t("أمر", "orders"))],
                   red, [], "")


def _finance(conn, day, al):
    from fi.reports import cockpit
    d = datetime.date.fromisoformat(day)
    k = cockpit(conn, d.year, d.month)["kpi"]
    yellow = []
    if k.get("cash") is not None and k.get("ap") and k["cash"] < k["ap"] * 0.2:
        yellow.append(t("النقدية (%s) أقل من 20%% من فلوس الموردين (%s) - راجع التدفق النقدي.", "Cash (%s) is below 20%% of the payables (%s) - review the cash flow.") % (_fmt(k["cash"]), _fmt(k["ap"])))
    red = [] if k.get("balanced", True) else [t("الميزانية مش متزنة - راجع القيود (F.01).", "The balance sheet does not balance - check the postings (F.01).")]
    return _module(conn, day, "FI", t("الحسابات", "Finance"), "💰", "ZFI_COCKPIT",
                   (t("القيود المتسجلة", "Journal entries"), "SELECT COUNT(*) FROM acc_doc WHERE budat=?", 1, t("قيد", "entries"), 1.0),
                   [(t("النقدية والبنوك", "Cash and banks"), round(k.get("cash") or 0), t("جنيه", "EGP")),
                    (t("عند العملاء", "Receivables"), round(k.get("ar") or 0), t("جنيه", "EGP")),
                    (t("للموردين", "Payables"), round(k.get("ap") or 0), t("جنيه", "EGP")),
                    (t("نتيجة الشهر", "Result of the month"), round(k.get("result") or 0), t("جنيه", "EGP"))],
                   red, yellow, "")


def _hr(conn, day, al):
    leave = conn.execute("SELECT COUNT(*) FROM hr_absence WHERE status='A' AND begda<=? AND endda>=?", (day, day)).fetchone()[0]
    req = conn.execute("SELECT COUNT(*) FROM hr_absence WHERE status='R'").fetchone()[0]
    staff = conn.execute("SELECT COUNT(*) FROM hr_employee WHERE COALESCE(leave_date,'')='' OR leave_date>?", (day,)).fetchone()[0]
    yellow = [t("%d طلب إجازة مستني رد - ردّ عليهم (ZLEAVE).", "%d leave requests waiting for a decision (ZLEAVE).") % req] if req else []
    if staff and leave / staff > 0.15:
        yellow.append(t("%d%% من الموظفين في إجازة النهارده - راجع تغطية الورديات.", "%d%% of the staff are on leave today - check the shift cover.") % round(100 * leave / staff))
    return _module(conn, day, "HR", t("الموارد البشرية", "Human Resources"), "👥", "ZHR_COCKPIT",
                   (t("ساعات الإضافي", "Overtime"), "SELECT COALESCE(SUM(hours),0) FROM hr_overtime WHERE datum=?", -1, t("ساعة", "hours"), 1000.0),
                   [(t("الموظفين", "Employees"), staff, t("موظف", "people")), (t("في إجازة النهارده", "On leave today"), leave, t("موظف", "people")),
                    (t("طلبات إجازة مفتوحة", "Open leave requests"), req, t("طلب", "requests"))],
                   [], yellow, "")


def _tax(conn, day, al):
    from tax.returns import calendar_year
    d = datetime.date.fromisoformat(day)
    rows = calendar_year(conn, d.year)["rows"]
    late = [r for r in rows if r["status"] == "overdue"]
    soon = [r for r in rows if r["status"] not in ("paid", "overdue") and 0 <= r["days"] <= 7]
    red = [t("%d إقرار متأخر عن ميعاده - قدّمه فوراً عشان الغرامة (ZTAX_CAL).", "%d tax returns are overdue - file them now to limit the penalty (ZTAX_CAL).") % len(late)] if late else []
    yellow = [t("%s مطلوب خلال %d يوم.", "%s due in %d days.") % (r["label"], r["days"]) for r in soon[:3]]
    m = _module(conn, day, "TAX", t("الضرائب", "Taxes"), "🏛️", "ZTAX_CAL",
                (t("الفواتير الإلكترونية المبعوتة", "E-invoices sent"), "SELECT COUNT(*) FROM sd_einv WHERE substr(ts,1,10)=?", 1, t("فاتورة", "invoices"), 1.0),
                [(t("إقرارات متأخرة", "Overdue returns"), len(late), t("إقرار", "returns")),
                 (t("مطلوب خلال أسبوع", "Due within a week"), len(soon), t("إقرار", "returns"))],
                red, yellow, "")
    if not red and not yellow and m["verdict"] in (ATTN, QUIET):
        m.update(verdict=GOOD, verdict_text=_vt(GOOD), emoji=VERDICT[GOOD][1],
                 opinion=t("كل المواعيد الضريبية متغطية - مافيش حاجة متأخرة.", "All tax deadlines are covered - nothing overdue."))
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


def day_review(conn, day=None, user=None, allowed=None, lang="ar"):
    """allowed(area) -> bool (None = everything); lang: ar (Egyptian Arabic) or en"""
    _L.lang = lang if lang in LANGS else "ar"
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
        overall = t("النهارده فيه %d موديول محتاج تعديل: %s. ابدأ بيهم.", "%d modules need attention today: %s. Start with them.") % (
            n[ATTN], t("، ", ", ").join(m["name"] for m in out if m["verdict"] == ATTN))
    elif n[UP]:
        overall = t("يوم كويس: %s في تقدم، والباقي طبيعي.", "A good day: %s improving, the rest normal.") % t("، ", ", ").join(
            m["name"] for m in out if m["verdict"] == UP)
    else:
        overall = t("يوم طبيعي ومستقر في كل الموديولات.", "A normal, stable day in every module.")
    wd = datetime.date.fromisoformat(day).weekday()
    weekday = t(["الاتنين", "التلات", "الأربع", "الخميس", "الجمعة", "السبت", "الحد"][wd],
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][wd])
    return {"day": day, "lang": _L.lang, "weekday": weekday, "early": early, "modules": out, "counts": n, "overall": overall,
            "legend": {k: dict(text=_vt(k), emoji=v[1]) for k, v in VERDICT.items()},
            "note": t("المقارنة مع متوسط أيام الشغل في آخر %d يوم (الجمعة إجازة).",
                      "Compared with the average working day of the last %d days (Friday off).") % DAYS_BACK}
