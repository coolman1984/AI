"""Daily briefing and alerts.

Daily briefing: at the time each subscriber chose (e.g. 08:00) NERP sends one message with sales,
production, receivables, quality and maintenance - only the parts the user may display - and the
open alerts. Sent once per day.

Alerts: every few minutes NERP checks the rules below; a new event is sent once to every subscriber
who chose its category and may display its area:
  MACH   a machine is down (breakdown notification not closed)
  STOCK  a material is below its safety stock
  CREDIT a sales order is blocked by the credit check
  QUAL   an inspection lot was rejected (fully or partly)
  TAX    a tax return / payment is due within 3 days and not done
  APPR   something waits for the user's approval (inbox)
Every message is also written to the in-app inbox (ZNOTIF), whatever the channel.
"""
import datetime
import threading
import time

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts

from . import channels as ch

CATS = {"MACH": ("Machine breakdown", "PP"), "STOCK": ("Stock below safety stock", "MM"),
        "CREDIT": ("Sales order on credit block", "SD"), "QUAL": ("Inspection lot rejected", "MM"),
        "TAX": ("Tax deadline in 3 days", "FI"), "APPR": ("Waiting for my approval", "CA")}
SECRET = ("telegram_token", "smtp_password", "wa_token")


# ------------------------------------------------------------------ settings and subscriptions
def settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM notif_setting")}


def public_settings(conn):
    s = settings(conn)
    for k in SECRET:
        if s.get(k):
            s[k] = "••••" + s[k][-4:]
    return s


def save_settings(conn, data, user):
    keys = ("enabled", "alert_minutes", "telegram_token", "smtp_host", "smtp_port", "smtp_user", "smtp_password",
            "smtp_from", "smtp_tls", "wa_phone_id", "wa_token", "wa_mode", "wa_template", "wa_lang")
    if "wa_mode" in data and (data["wa_mode"] or "auto") not in ch.WA_MODES:
        raise MMError("WhatsApp sending must be one of: %s" % ", ".join(ch.WA_MODES), "NT", "909")
    if data.get("wa_template") is not None:
        n = "".join(c if c.isalnum() else "_" for c in str(data["wa_template"]).strip().lower()).strip("_")
        data = dict(data, wa_template="_".join(x for x in n.split("_") if x) or "nerp_alert")
    if data.get("wa_lang") is not None:
        data = dict(data, wa_lang=str(data["wa_lang"]).strip().replace("-", "_") or "ar")
    if "alert_minutes" in data:
        m = clock.parse_int(data["alert_minutes"], "minutes between alert checks", 5, 1440)
        data = dict(data, alert_minutes=str(m))
    if data.get("smtp_port"):
        data = dict(data, smtp_port=str(clock.parse_int(data["smtp_port"], "SMTP port", 1, 65535)))
    with transaction(conn):
        for k in keys:
            if k not in data:
                continue
            v = "" if data[k] is None else str(data[k]).strip()
            if k in SECRET:
                if v == "" or v.startswith("••••"):
                    continue                                   # empty / masked = keep the saved secret
                if v == "-":
                    v = ""                                     # "-" removes it
            if k in ("enabled", "smtp_tls"):
                v = "1" if v in ("1", "true", "True", "on") else "0"
            conn.execute("INSERT OR REPLACE INTO notif_setting VALUES (?,?)", (k, v))
    return {"message": "Notification settings saved"}


def subs(conn, user=None):
    q, a = "SELECT * FROM notif_sub", ()
    if user:
        q, a = q + " WHERE usnam=?", (user,)
    return [dict(r, cats=[c for c in (r["cats"] or "").split(",") if c]) for r in conn.execute(q + " ORDER BY usnam, id", a)]


def save_sub(conn, data, user, admin=False):
    channel = (data.get("channel") or "").lower()
    if channel not in ch.CHANNELS:
        raise MMError("Channel must be one of: %s" % ", ".join(ch.CHANNELS), "NT", "901")
    address = (data.get("address") or "").strip()
    if channel == "email" and "@" not in address:
        raise MMError("Enter a valid e-mail address", "NT", "902")
    if channel == "telegram" and not address.lstrip("-").isdigit():
        raise MMError("Enter the Telegram chat id (a number - use 'Find my chat id')", "NT", "903")
    if channel == "whatsapp":
        try:
            address = ch.wa_number(address)
        except ch.NotifyError:
            raise MMError("Enter the mobile number, e.g. 01001234567 or 201001234567", "NT", "904")
    t = (data.get("daily_time") or "08:00").strip()
    try:
        datetime.datetime.strptime(t, "%H:%M")
    except ValueError:
        raise MMError("Daily time as HH:MM, e.g. 08:00", "NT", "905")
    cats = [c for c in (data.get("cats") or []) if c in CATS] if isinstance(data.get("cats"), list) else \
        [c for c in str(data.get("cats") or "").split(",") if c in CATS]
    owner = (data.get("usnam") or user).upper() if admin else user
    with transaction(conn):
        if data.get("id"):
            r = conn.execute("SELECT * FROM notif_sub WHERE id=?", (int(data["id"]),)).fetchone()
            if not r or (not admin and r["usnam"] != user):
                raise MMError("Subscription %s does not exist" % data["id"], "NT", "906")
            conn.execute("UPDATE notif_sub SET channel=?, address=?, daily=?, daily_time=?, cats=?, active=?, ts=? "
                         "WHERE id=?", (channel, address, 1 if data.get("daily", True) else 0, t, ",".join(cats),
                                        0 if data.get("active") is False else 1, now_ts(), r["id"]))
            sid = r["id"]
        else:
            sid = conn.execute("INSERT INTO notif_sub (usnam,channel,address,daily,daily_time,cats,active,created,ts) "
                               "VALUES (?,?,?,?,?,?,1,?,?)", (owner, channel, address, 1 if data.get("daily", True) else 0,
                                                             t, ",".join(cats), clock.today().isoformat(), now_ts())).lastrowid
    return {"id": sid, "message": "Subscription saved - %s%s" % (ch.CHANNELS[channel], (" " + address) if address else "")}


def delete_sub(conn, sid, user, admin=False):
    with transaction(conn):
        r = conn.execute("SELECT * FROM notif_sub WHERE id=?", (int(sid),)).fetchone()
        if not r or (not admin and r["usnam"] != user):
            raise MMError("Subscription %s does not exist" % sid, "NT", "906")
        conn.execute("DELETE FROM notif_sub WHERE id=?", (r["id"],))
    return {"message": "Subscription removed"}


# ------------------------------------------------------------------ authorization of a subscriber
def _allowed(conn, user):
    """None = everything (user not in the user master: logon switched off / developer mode)"""
    if not conn.execute("SELECT 1 FROM usr WHERE bname=?", (user,)).fetchone():
        return None
    from sec import auth
    prof = auth.profile(conn, user)
    return lambda area: auth.area_allowed(prof, area, "03")


# ------------------------------------------------------------------ the alert rules
def alerts(conn, user=None):
    """current alert events: dict(cat, key, title, text, tcode)"""
    today = clock.today()
    out = []
    for n in conn.execute("SELECT n.*, e.eqktx, e.arbpl FROM pm_notif n JOIN pm_equi e ON e.equnr=n.equnr WHERE "
                          "n.qmart='M2' AND n.status<>'CLOSED'"):
        out.append(dict(cat="MACH", key="MACH:%s" % n["qmnum"], tcode="ZPM_ORDERS",
                        title="⚠️ ماكينة واقفة: %s" % n["eqktx"],
                        text="الماكينة **%s** (%s) واقفة من %s.\nالمشكلة: %s\nأمر الصيانة: %s" % (
                            n["eqktx"], n["arbpl"] or "-", n["start"] or "-", n["text"], n["aufnr"] or "لسه ما اتعملش")))
    from mm.board import board as mmboard
    for r in mmboard(conn)["reorder"]:
        if r["below_safety"]:
            out.append(dict(cat="STOCK", key="STOCK:%s:%s:%s" % (r["matnr"], r["werks"], today.isoformat()), tcode="MMBE",
                            title="📦 مخزون تحت حد الأمان: %s" % r["matnr"],
                            text="**%s** %s\nالرصيد %s %s، وحد الأمان %s. محتاج طلب شراء." % (
                                r["matnr"], r["maktx"] or "", clock.qty_out(r["stock"]), r["meins"] or "",
                                clock.qty_out(r["safety"]))))
    for k in conn.execute("SELECT k.vbeln, k.kunnr, c.name, k.netwr, k.audat FROM sd_vbak k LEFT JOIN customer c ON "
                          "c.kunnr=k.kunnr WHERE k.cmgst='B'"):
        out.append(dict(cat="CREDIT", key="CREDIT:%s" % k["vbeln"], tcode="VKM3",
                        title="💳 أمر بيع موقوف ائتمانياً: %s" % k["vbeln"],
                        text="أمر البيع **%s** للعميل %s بقيمة %s جنيه واقف على حد الائتمان. محتاج موافقة مدير الائتمان." % (
                            k["vbeln"], k["name"] or k["kunnr"], "{:,.0f}".format((k["netwr"] or 0) / 100.0))))
    for l in conn.execute("SELECT l.*, v.name vendor FROM qm_lot l LEFT JOIN vendor v ON v.lifnr=l.lifnr WHERE l.status='UD' "
                          "AND l.ud_code IN ('R','P') AND l.ud_date>=?", ((today - datetime.timedelta(days=1)).isoformat(),)):
        out.append(dict(cat="QUAL", key="QUAL:%s" % l["prueflos"], tcode="QM01",
                        title="🔴 رفض جودة: %s" % l["matnr"],
                        text="الدفعة %s من %s: اترفض **%s** من %s.\n%s" % (
                            l["prueflos"], l["vendor"] or "الإنتاج", clock.qty_out(l["qty_rej"]), clock.qty_out(l["qty"]),
                            l["note"] or "")))
    from tax.returns import calendar_year
    for r in calendar_year(conn, today.year)["rows"]:
        if r["status"] not in ("paid", "overdue") and 0 <= r["days"] <= 3:
            out.append(dict(cat="TAX", key="TAX:%s:%s" % (r["typ"], r["period"]), tcode="ZTAX_CAL",
                            title="🧾 ميعاد ضريبي: %s" % r["label"],
                            text="**%s** مطلوب يوم %s (فاضل %d يوم). المبلغ حوالي %s جنيه." % (
                                r["label"], r["due"], r["days"], "{:,.0f}".format((r["amount"] or 0) / 100.0))))
    if user:
        from sec.inbox import inbox
        for i in inbox(conn, user, everything=not conn.execute("SELECT 1 FROM usr WHERE bname=?", (user,)).fetchone()):
            out.append(dict(cat="APPR", key="APPR:%s:%s:%s" % (user, i["typ"], i["key"]), tcode=i["tcode"],
                            title="✅ مستني موافقتك: %s" % i["typ"],
                            text="%s %s\n%s" % (i["typ"], i["key"], i["text"])))
    return out


# ------------------------------------------------------------------ messages
def _deliver(conn, sub, kind, cat, title, text, tcode, sender):
    cfg = settings(conn)
    status, error = "sent", ""
    try:
        (sender or ch.send)(sub["channel"], cfg, sub["address"], title, text + ("\n\nNERP: %s" % tcode if tcode else ""))
        if sub["channel"] == "inapp":
            status = "inapp"
    except ch.NotifyError as e:
        status, error = "failed", str(e)
    with transaction(conn):
        conn.execute("INSERT INTO notif_log (ts,usnam,channel,address,kind,cat,title,text,tcode,status,error) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?)", (now_ts(), sub["usnam"], sub["channel"], sub["address"], kind, cat, title,
                                                 text, tcode, status, error))
    return status != "failed", error


def daily_message(conn, user):
    from ai.agent import _briefing
    allowed = _allowed(conn, user)
    b = _briefing(conn, allowed, True)
    al = [a for a in alerts(conn, user) if allowed is None or allowed(CATS[a["cat"]][1])]
    text = b["answer"].replace("**ملخص اليوم:**\n\n", "")
    appr = [a for a in al if a["cat"] == "APPR"]
    lines = ["- " + a["title"] for a in al if a["cat"] != "APPR"][:8]
    if appr:
        lines.append("- ✅ %d حاجة مستنية موافقتك (ZINBOX)" % len(appr))
    if lines:
        text += "\n\n**تنبيهات مفتوحة:**\n" + "\n".join(lines)
    fx = fx_text(conn)
    if fx:
        text += "\n\n" + fx
    tl = tile_text(conn, allowed)
    if tl:
        text += "\n\n" + tl
    cu = customs_text(conn, allowed)
    if cu:
        text += "\n\n" + cu
    rv = review_text(conn, user, allowed)
    if rv:
        text += "\n\n" + rv
    return "☀️ صباح الخير - ملخص NERP %s" % clock.today().strftime("%d/%m/%Y"), text


def tile_text(conn, allowed=None, day=None):
    """ceramics: yesterday's first-choice rate and gas per m2 (only when the factory sorts tiles)"""
    if allowed is not None and not allowed("PP"):
        return ""
    from tile import energy, lots
    try:
        lines = [x for x in (lots.day_text(conn, day), energy.day_text(conn, day)) if x]
    except Exception:                              # the briefing must always arrive
        return ""
    return ("**🧱 المصنع:**\n" + "\n".join(lines)) if lines else ""


def customs_text(conn, allowed=None):
    """customs: shipments in port (over the free days), duties to pay, exports not cleared"""
    if allowed is not None and not allowed("PUR"):
        return ""
    try:
        from customs.engine import day_text
        return day_text(conn)
    except Exception:                              # the briefing must always arrive
        return ""


FX_MAIN = ("USD", "EUR", "GBP", "SAR", "AED", "CNY")
FX_AR = {"USD": "الدولار الأمريكي", "EUR": "اليورو", "GBP": "الجنيه الإسترليني", "SAR": "الريال السعودي",
         "AED": "الدرهم الإماراتي", "CNY": "اليوان الصيني", "KWD": "الدينار الكويتي", "CHF": "الفرنك السويسري"}


def fx_text(conn, limit=6):
    """exchange rates for the briefing: the main currencies and those used in the books (rate, change),
    old rates, currencies used without a rate and a failed central bank update of today"""
    try:
        from fi import currency as fxm
        o = fxm.overview(conn)
    except Exception:                                  # never stop the briefing because of the rates
        return ""
    rows = {r["waers"]: r for r in o["rows"] if r["rate"] is not None}
    used = [r[0] for r in conn.execute("SELECT DISTINCT waers FROM exch_rate")]
    order = [c for c in FX_MAIN if c in rows] + [c for c in sorted(used) if c in rows and c not in FX_MAIN]
    out = []
    for c in order[:limit]:
        r = rows[c]
        name = FX_AR.get(c) or r["ltext_ar"] or c
        if r["factor"] > 1:
            name = "%d %s" % (r["factor"], name)
        ch = ""
        if r["change_pct"]:
            ch = " (%s %.2f%%)" % ("▲" if r["change_pct"] > 0 else "▼", abs(r["change_pct"]))
        old = " ⚠️ سعر قديم من %s" % r["gdatu"][8:10] + "/" + r["gdatu"][5:7] if r["stale"] else ""
        out.append("- %s %.2f%s%s" % (name, r["rate"], ch, old))
    if o["missing"]:
        out.append("- ⚠️ عملات مستخدمة من غير سعر: %s" % ", ".join(m["waers"] for m in o["missing"]))
    try:
        last = conn.execute("SELECT status, message FROM fx_update_log WHERE run_day=? ORDER BY id DESC LIMIT 1",
                            (clock.today().isoformat(),)).fetchone()
    except Exception:
        last = None
    if last and last["status"] == "failed":
        out.append("- ⚠️ تحديث البنك المركزي النهارده ما نجحش: %s" % (last["message"] or "")[:80])
    if not out:
        return ""
    return "**أسعار الصرف (جنيه):**\n" + "\n".join(out) + "\nكل العملات والمحوّل: افتح ZFX"


def review_text(conn, user, allowed=None):
    """the daily review (ZDAY) in a few lines: counts, every module that needs attention with the reason,
    the improving ones; yesterday's review before 4 pm (the morning briefing)"""
    from ai import review as R
    try:
        r = R.day_review(conn, None, user, allowed)
    except Exception:                                  # the briefing must never fail because of the review
        return ""
    if not r["modules"]:
        return ""
    d = datetime.date.fromisoformat(r["day"])
    today = clock.today()
    head = ("تقرير النهارده" if d == today else "تقرير امبارح" if d == today - datetime.timedelta(days=1)
            else "تقرير يوم %s %s" % (r["weekday"], d.strftime("%d/%m")))
    counts = " · ".join("%s %d" % (R.VERDICT[k][1], r["counts"][k]) for k in (R.ATTN, R.UP, R.GOOD, R.QUIET) if r["counts"][k])
    out = ["**%s:** %s" % (head, counts)]
    for m in r["modules"]:
        if m["verdict"] == R.ATTN:
            why = (m["problems"] or m["watch"] or [m["opinion"].split(". ")[0].rstrip(".")])[0]
            if d != today:                             # the module texts speak of "today"
                why = why.replace("النهارده", "امبارح" if d == today - datetime.timedelta(days=1) else "اليوم ده")
            out.append("- 🔴 %s: %s" % (m["name"], why))
    up = [m["name"] for m in r["modules"] if m["verdict"] == R.UP]
    if up:
        out.append("- 🚀 في تقدم: %s" % "، ".join(up))
    out.append("التفاصيل كاملة: افتح ZDAY")
    return "\n".join(out)


def run_daily(conn, now=None, sender=None, force_sub=None):
    now = now or clock.now()
    day, hm = now.date().isoformat(), now.strftime("%H:%M")
    sent = 0
    for s in subs(conn):
        if force_sub is not None and s["id"] != force_sub:
            continue
        if force_sub is None and (not s["active"] or not s["daily"] or s["daily_time"] > hm):
            continue
        key = "DAILY:%s:%s" % (s["id"], day)
        if force_sub is None and conn.execute("SELECT 1 FROM notif_sent WHERE key=?", (key,)).fetchone():
            continue
        title, text = daily_message(conn, s["usnam"])
        ok, _ = _deliver(conn, s, "daily", "", title, text, "ZAI", sender)
        if ok and force_sub is None:
            with transaction(conn):
                conn.execute("INSERT OR IGNORE INTO notif_sent VALUES (?,?)", (key, now_ts()))
        sent += ok
    return sent


def run_alerts(conn, sender=None):
    sent = 0
    for s in subs(conn):
        if not s["active"] or not s["cats"]:
            continue
        allowed = _allowed(conn, s["usnam"])
        new = []
        for a in alerts(conn, s["usnam"]):
            if a["cat"] not in s["cats"] or (allowed is not None and not allowed(CATS[a["cat"]][1])):
                continue
            key = "ALERT:%s:%s" % (s["id"], a["key"])
            if not conn.execute("SELECT 1 FROM notif_sent WHERE key=?", (key,)).fetchone():
                new.append((key, a))
        appr = [x for x in new if x[1]["cat"] == "APPR"]
        msgs = [([k], a) for k, a in new if a["cat"] != "APPR"]
        if appr:                                         # approvals: one message for all new items
            msgs.append(([k for k, _ in appr], dict(cat="APPR", tcode="ZINBOX", title="✅ عندك %d حاجة مستنية موافقتك" % len(appr),
                                                     text="\n".join("- " + a["text"].split("\n")[0] for _, a in appr[:15]))))
        for keys, a in msgs:
            ok, _ = _deliver(conn, s, "alert", a["cat"], a["title"], a["text"], a["tcode"], sender)
            if ok:
                with transaction(conn):
                    for key in keys:
                        conn.execute("INSERT OR IGNORE INTO notif_sent VALUES (?,?)", (key, now_ts()))
                sent += 1
    return sent


def test_message(conn, sid, user, admin=False, sender=None):
    s = conn.execute("SELECT * FROM notif_sub WHERE id=?", (int(sid),)).fetchone()
    if not s or (not admin and s["usnam"] != user):
        raise MMError("Subscription %s does not exist" % sid, "NT", "906")
    ok, err = _deliver(conn, dict(s), "test", "", "✅ NERP - رسالة تجربة",
                       "لو الرسالة دي وصلتك، يبقى ملخص الصبح والتنبيهات هيوصلوا هنا.", "", sender)
    if not ok:
        raise MMError("Sending failed: %s" % err, "NT", "907")
    return {"message": "Test message sent (%s)" % ch.CHANNELS[s["channel"]]}


def inbox(conn, user, limit=50):
    rows = [dict(r) for r in conn.execute("SELECT * FROM notif_log WHERE usnam=? AND kind<>'test' ORDER BY id DESC LIMIT ?",
                                          (user, int(limit)))]
    return {"rows": rows, "unseen": sum(1 for r in rows if not r["seen"])}


def mark_seen(conn, user):
    with transaction(conn):
        conn.execute("UPDATE notif_log SET seen=1 WHERE usnam=? AND seen=0", (user,))
    return {"message": "Marked as read"}


def log(conn, limit=100):
    return [dict(r) for r in conn.execute("SELECT * FROM notif_log ORDER BY id DESC LIMIT ?", (int(limit),))]


# ------------------------------------------------------------------ scheduler (thread in the server)
STATE = {"last_alerts": 0.0, "running": False, "last_error": ""}


def tick(conn, now=None, sender=None):
    s = settings(conn)
    if s.get("enabled", "1") != "1":
        return {"daily": 0, "alerts": 0}
    d = run_daily(conn, now, sender)
    a = 0
    every = 60 * int(s.get("alert_minutes") or 15)
    if time.time() - STATE["last_alerts"] >= every:
        STATE["last_alerts"] = time.time()
        a = run_alerts(conn, sender)
    return {"daily": d, "alerts": a}


def start(db_fn, interval=60):
    """background thread: every minute the daily briefings that are due and, every few minutes, the alerts"""
    if STATE["running"]:
        return
    STATE["running"] = True

    def loop():
        time.sleep(20)
        while True:
            try:
                tick(db_fn())
                STATE["last_error"] = ""
            except Exception as e:              # never stop the server because of a message
                STATE["last_error"] = "%s: %s" % (type(e).__name__, e)
            try:                                # daily exchange rates from the central bank (ZFX), if switched on
                from fi import cbe
                cbe.tick(db_fn())
            except Exception as e:
                STATE["fx_error"] = "%s: %s" % (type(e).__name__, e)
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True, name="nerp-notify").start()
