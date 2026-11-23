"""Daily briefing and alerts to the mobile (ZNOTIF): subscriptions, the daily briefing once a day at
the chosen time, alerts sent once per event, approvals combined, categories and authorizations
respected, failed sends retried, channel formatting and masked secrets. A fake sender - no network."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class Sender:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def __call__(self, channel, cfg, address, title, text):
        from notify.channels import NotifyError
        if self.fail:
            raise NotifyError("network down")
        self.sent.append((channel, address, title, text))


class Subscriptions(unittest.TestCase):
    def test_validation_and_ownership(self):
        from notify import engine as e
        c = system()
        err(self, lambda: e.save_sub(c, {"channel": "sms"}, "U1"), "901")
        err(self, lambda: e.save_sub(c, {"channel": "email", "address": "x"}, "U1"), "902")
        err(self, lambda: e.save_sub(c, {"channel": "telegram", "address": "abc"}, "U1"), "903")
        err(self, lambda: e.save_sub(c, {"channel": "whatsapp", "address": "0100"}, "U1"), "904")
        err(self, lambda: e.save_sub(c, {"channel": "inapp", "daily_time": "8am"}, "U1"), "905")
        sid = e.save_sub(c, {"channel": "telegram", "address": "123456789", "cats": ["MACH", "XX"]}, "U1")["id"]
        self.assertEqual(e.subs(c, "U1")[0]["cats"], ["MACH"])
        err(self, lambda: e.delete_sub(c, sid, "U2"), "906")                  # not his subscription
        e.save_settings(c, {"telegram_token": "123:SECRETTOKEN", "alert_minutes": "10"}, "ADMIN")
        self.assertTrue(e.public_settings(c)["telegram_token"].startswith("••••"))
        e.save_settings(c, {"telegram_token": ""}, "ADMIN")                    # empty keeps it
        self.assertEqual(e.settings(c)["telegram_token"], "123:SECRETTOKEN")
        err(self, lambda: e.save_settings(c, {"alert_minutes": "1"}, "ADMIN"), "089")


class Daily(unittest.TestCase):
    def test_once_a_day_at_the_chosen_time_and_retry_after_failure(self):
        from notify import engine as e
        c = system()
        sid = e.save_sub(c, {"channel": "telegram", "address": "111", "daily_time": "08:00", "cats": []}, "OWNER")["id"]
        early = datetime.datetime.combine(T, datetime.time(7, 30))
        on = datetime.datetime.combine(T, datetime.time(8, 5))
        s = Sender()
        self.assertEqual(e.run_daily(c, early, s), 0)
        bad = Sender(fail=True)
        self.assertEqual(e.run_daily(c, on, bad), 0)                          # failure is logged, not marked
        self.assertEqual(c.execute("SELECT status FROM notif_log ORDER BY id DESC").fetchone()[0], "failed")
        self.assertEqual(e.run_daily(c, on, s), 1)                            # retried on the next run
        self.assertEqual(e.run_daily(c, on, s), 0)                            # once per day
        self.assertEqual(e.run_daily(c, on + datetime.timedelta(days=1), s), 1)
        title, text = s.sent[0][2], s.sent[0][3]
        self.assertIn("ملخص", title)
        self.assertIn("المبيعات", text)
        self.assertEqual(s.sent[0][:2], ("telegram", "111"))
        self.assertEqual(e.run_daily(c, early, s, force_sub=sid), 1)           # "send now" ignores the time
        self.assertTrue(e.inbox(c, "OWNER")["rows"])


class DailyReview(unittest.TestCase):
    def test_briefing_carries_the_daily_review_for_the_allowed_modules(self):
        from unittest import mock
        from ai import review as R
        from mm import util as clock
        from notify import engine as e
        c = system()
        morning = datetime.datetime.combine(clock.today(), datetime.time(8, 0))
        with mock.patch.object(clock, "now", lambda: morning):
            title, text = e.daily_message(c, "OWNER")
            r = R.day_review(c)                                                # yesterday's review (before 4 pm)
        self.assertIn("تقرير امبارح", text)
        self.assertIn("ZDAY", text)
        for m in r["modules"]:
            if m["verdict"] == R.ATTN:
                self.assertIn("🔴 %s" % m["name"], text)                    # every module that needs attention
        counts = " · ".join("%s %d" % (R.VERDICT[k][1], r["counts"][k]) for k in (R.ATTN, R.UP, R.GOOD, R.QUIET) if r["counts"][k])
        self.assertIn(counts, text)
        # a user without HR authorization does not get the HR module
        no_hr = next(u for u in c.execute("SELECT bname FROM usr").fetchall()
                     if e._allowed(c, u[0]) and not e._allowed(c, u[0])("HR"))[0]
        with mock.patch.object(clock, "now", lambda: morning):
            r2 = R.day_review(c, user=no_hr, allowed=e._allowed(c, no_hr))
            _, text2 = e.daily_message(c, no_hr)
        self.assertNotIn("HR", [m["code"] for m in r2["modules"]])
        self.assertNotIn("الموارد البشرية", text2.split("تقرير امبارح")[1])
        self.assertNotIn("النهارده", text.split("تقرير امبارح")[1])          # yesterday's review speaks of yesterday
        self.assertLess(len(text), 3800)                                        # fits a Telegram message


class Alerts(unittest.TestCase):
    def test_alerts_once_per_event_categories_and_authorization(self):
        from notify import engine as e
        from qm import maintenance as pm
        c = system()
        e.save_sub(c, {"channel": "inapp", "daily": False, "cats": ["MACH", "APPR", "STOCK"]}, "OWNER")
        e.save_sub(c, {"channel": "inapp", "daily": False, "cats": ["TAX"]}, "TAXONLY")
        from mm import util as clock
        start = clock.now() - datetime.timedelta(hours=2)                     # not tied to the real time of day
        n = pm.create_notification(c, {"qmart": "M2", "equnr": "PRS-01", "text": "Hydraulic leak",
                                       "start": start.strftime("%Y-%m-%d %H:%M")}, "T")
        s = Sender()
        e.run_alerts(c, s)
        titles = [x[2] for x in s.sent]
        self.assertEqual(sum("ماكينة واقفة" in t for t in titles), 1)
        self.assertEqual(sum("مستنية موافقتك" in t for t in titles), 1)      # approvals in ONE message
        self.assertFalse(c.execute("SELECT 1 FROM notif_log WHERE usnam='TAXONLY' AND cat<>'TAX'").fetchone())
        k = len(s.sent)
        e.run_alerts(c, s)
        self.assertEqual(len(s.sent), k)                                    # nothing twice
        pm.complete(c, n["aufnr"], {"finish": (start + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")}, "T")
        self.assertFalse([a for a in e.alerts(c) if a["key"] == "MACH:%s" % n["qmnum"]])
        from unittest import mock
        real = e._allowed                                                   # a user without PP display
        e.save_sub(c, {"channel": "inapp", "daily": False, "cats": ["MACH"]}, "NOPP")
        pm.create_notification(c, {"qmart": "M2", "equnr": "ROB-01", "text": "Sensor",
                                    "start": start.strftime("%Y-%m-%d %H:%M")}, "T")
        with mock.patch.object(e, "_allowed", lambda conn, u: (lambda area: area != "PP") if u == "NOPP" else real(conn, u)):
            e.run_alerts(c, s)
        self.assertFalse(c.execute("SELECT 1 FROM notif_log WHERE usnam='NOPP' AND cat='MACH'").fetchone())
        self.assertTrue(c.execute("SELECT 1 FROM notif_log WHERE usnam='OWNER' AND cat='MACH' AND title LIKE ?",
                                  ("%Assembly robot%",)).fetchone())                # the others got the new breakdown

class Channels(unittest.TestCase):
    def test_formatting_and_missing_configuration(self):
        from notify import channels as ch
        self.assertEqual(ch.to_html("a <b> **x** & y"), "a &lt;b&gt; <b>x</b> &amp; y")
        ch.send("inapp", {}, "", "t", "x")                                  # nothing to send
        for fn in (lambda: ch.send("sms", {}, "1", "t", "x"), lambda: ch.send("telegram", {}, "1", "t", "x"),
                   lambda: ch.send("email", {}, "a@b.c", "t", "x"), lambda: ch.send("whatsapp", {}, "2010", "t", "x"),
                   lambda: ch.send("telegram", {"telegram_token": "1:a"}, " ", "t", "x")):
            with self.assertRaises(ch.NotifyError):
                fn()

    def test_whatsapp_numbers_and_approved_templates(self):
        from unittest import mock
        from notify import channels as ch
        from notify import engine as e
        self.assertEqual(ch.wa_number("01001234567"), "201001234567")           # Egyptian mobile as dialled
        self.assertEqual(ch.wa_number("+20 100 123 4567"), "201001234567")
        self.assertEqual(ch.wa_number("00201001234567"), "201001234567")
        self.assertEqual(ch.wa_number("1001234567"), "201001234567")
        with self.assertRaises(ch.NotifyError):
            ch.wa_number("12345")
        # template parameters: no line breaks / tabs / 5+ spaces, limited length
        p = ch.wa_param("**Sales**\n\tline  2" + "     x" + "y" * 2000, 900)
        self.assertNotIn("\n", p)
        self.assertNotIn("\t", p)
        self.assertNotIn("     ", p)
        self.assertNotIn("**", p)
        self.assertLessEqual(len(p), 900)
        cfg = {"wa_phone_id": "111", "wa_token": "tok"}
        sent = []

        def outside_window(url, payload, headers=None, timeout=20):
            sent.append(payload)
            if payload["type"] == "text":
                raise ch.NotifyError('graph.facebook.com answered 400: {"error":{"code":131047,"message":"Re-engagement message"}}')
            return {"messages": [{"id": "wamid.1"}]}
        with mock.patch.object(ch, "_post_json", outside_window):
            ch.send("whatsapp", cfg, "01001234567", "ملخص اليوم", "**المبيعات**\n100")     # auto: text, then template
            self.assertEqual([x["type"] for x in sent], ["text", "template"])
            t = sent[1]
            self.assertEqual(t["to"], "201001234567")
            self.assertEqual((t["template"]["name"], t["template"]["language"]["code"]), ("nerp_alert", "ar"))
            self.assertEqual([x["text"] for x in t["template"]["components"][0]["parameters"]], ["ملخص اليوم", "المبيعات | 100"])
            sent.clear()
            ch.send("whatsapp", dict(cfg, wa_mode="template", wa_template="daily_brief", wa_lang="en"), "201001234567", "T", "x")
            self.assertEqual([(x["type"], x["template"]["name"], x["template"]["language"]["code"]) for x in sent],
                             [("template", "daily_brief", "en")])
            sent.clear()
            with self.assertRaises(ch.NotifyError):                              # text only: no fallback
                ch.send("whatsapp", dict(cfg, wa_mode="text"), "201001234567", "T", "x")
            self.assertEqual(len(sent), 1)

        def other_error(url, payload, headers=None, timeout=20):
            sent.append(payload)
            raise ch.NotifyError("graph.facebook.com answered 401: invalid token")
        sent.clear()
        with mock.patch.object(ch, "_post_json", other_error):
            with self.assertRaises(ch.NotifyError):
                ch.send("whatsapp", cfg, "201001234567", "T", "x")
            self.assertEqual(len(sent), 1)                                       # other errors are not retried as template
        c = system()
        e.save_settings(c, {"wa_mode": "template", "wa_template": "Nerp Alert!", "wa_lang": "ar"}, "ADMIN")
        err(self, lambda: e.save_settings(c, {"wa_mode": "sms"}, "ADMIN"), "909")
        self.assertEqual(e.settings(c)["wa_template"], "nerp_alert")              # Meta template names: a-z 0-9 _
        sid = e.save_sub(c, {"channel": "whatsapp", "address": "0100 123 4567"}, "U1")["id"]
        self.assertEqual(c.execute("SELECT address FROM notif_sub WHERE id=?", (sid,)).fetchone()[0], "201001234567")
        self.assertIn("{{1}}", ch.WA_TEMPLATE_AR)


if __name__ == "__main__":
    unittest.main()
