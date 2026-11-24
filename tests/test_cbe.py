"""Automatic exchange rates from the Central Bank of Egypt (ZFX): the page is read with a tolerant parser
(rates table found by the currency names in English or Arabic, buy / sell -> average type M, quotation per
100 units), a plausibility check against the last rate, the daily run at the chosen time (once a day, retry
after a failure), settings and the update log. A fake fetcher - no network."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm import util as clock  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

EN = """<html><body><h2>CBE Exchange Rates</h2><p class="date">Last update: 24/11/2026</p>
<table class="table"><thead><tr><th>Currency</th><th>Buy</th><th>Sell</th></tr></thead><tbody>
<tr><td>US Dollar</td><td>49.7500</td><td>49.8500</td></tr>
<tr><td>Euro</td><td>57.6512</td><td>57.7843</td></tr>
<tr><td>Pound Sterling</td><td>65.9810</td><td>66.1342</td></tr>
<tr><td>Swiss Franc</td><td>62.3000</td><td>62.4500</td></tr>
<tr><td>Japanese Yen 100</td><td>32.8500</td><td>32.9300</td></tr>
<tr><td>Saudi Riyal</td><td>13.2600</td><td>13.2900</td></tr>
<tr><td>Kuwaiti Dinar</td><td>161.9000</td><td>162.3000</td></tr>
<tr><td>UAE Dirham</td><td>13.5400</td><td>13.5700</td></tr>
<tr><td>Chinese yuan</td><td>6.9800</td><td>6.9900</td></tr>
<tr><td>Some Unknown Unit</td><td>1.0</td><td>1.1</td></tr>
</tbody></table></body></html>"""
AR = """<table><tr><th>العملة</th><th>شراء</th><th>بيع</th></tr>
<tr><td> دولار أمريكى </td><td>49,7500</td><td>49,8500</td></tr>
<tr><td>يورو</td><td>57.65</td><td>57.78</td></tr>
<tr><td>ين يابانى 100</td><td>32.85</td><td>32.93</td></tr>
<tr><td>ريال سعودى</td><td>13.26</td><td>13.29</td></tr></table><div>تاريخ: 2026-11-24</div>"""


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class Fetch:
    def __init__(self, html=EN, fail=False):
        self.html, self.fail, self.calls = html, fail, 0

    def __call__(self, url, timeout=20):
        from fi.cbe import FetchError
        self.calls += 1
        if self.fail:
            raise FetchError("No connection to www.cbe.org.eg")
        return self.html


class Parser(unittest.TestCase):
    def test_english_and_arabic_tables(self):
        from fi import cbe
        r = cbe.parse(EN)
        got = {x["waers"]: x for x in r["rates"]}
        self.assertEqual(set(got), {"USD", "EUR", "GBP", "CHF", "JPY", "SAR", "KWD", "AED", "CNY"})
        self.assertEqual(got["USD"]["mid"], 49.8)                                   # (buy + sell) / 2
        self.assertEqual((got["JPY"]["per"], got["JPY"]["mid"]), (100, 32.89))
        self.assertEqual(r["date"], "2026-11-24")
        self.assertEqual(r["unknown"], ["Some Unknown Unit"])
        a = {x["waers"]: x for x in cbe.parse(AR)["rates"]}
        self.assertEqual(set(a), {"USD", "EUR", "JPY", "SAR"})
        self.assertEqual(a["USD"]["mid"], 49.8)                                     # Arabic decimal comma
        self.assertEqual(a["JPY"]["per"], 100)
        with self.assertRaises(cbe.FetchError):
            cbe.parse("<html><body>maintenance</body></html>")
        with self.assertRaises(cbe.FetchError):                                     # the tests never use the network
            cbe.fetch_url(cbe.DEFAULT_URL)


class Update(unittest.TestCase):
    def test_update_plausibility_schedule_and_log(self):
        from fi import cbe, currency as fx
        c = system()
        t = clock.today()
        page = EN.replace("24/11/2026", t.strftime("%d/%m/%Y"))
        r = cbe.update(c, "T", fetch=Fetch(page))
        self.assertEqual(r["saved"], 9)
        usd = next(x for x in fx.overview(c)["rows"] if x["waers"] == "USD")
        self.assertEqual((usd["rate"], usd["gdatu"]), (49.8, t.isoformat()))
        jpy = c.execute("SELECT ukurs FROM exch_rate WHERE waers='JPY' AND gdatu=?", (t.isoformat(),)).fetchone()[0]
        self.assertEqual(jpy, 32890)                                                # 0.3289 EGP per yen
        # plausibility: a jump of more than the limit is not saved, the rest is
        bad = page.replace("<td>49.7500</td><td>49.8500</td>", "<td>4.9750</td><td>4.9850</td>")   # a wrong read
        r = cbe.update(c, "T", fetch=Fetch(bad))
        self.assertEqual(r["saved"], 8)
        self.assertIn("USD", [x["waers"] for x in r["rejected"]])
        self.assertEqual(c.execute("SELECT ukurs FROM exch_rate WHERE waers='USD' AND gdatu=?", (t.isoformat(),)).fetchone()[0], 4980000)
        future = EN.replace("24/11/2026", (t + datetime.timedelta(days=3)).strftime("%d/%m/%Y"))
        self.assertEqual(cbe.update(c, "T", fetch=Fetch(future))["day"], t.isoformat())   # never a rate in the future
        # settings and errors
        err(self, lambda: cbe.save_settings(c, {"time": "25:00"}, "ADMIN"), "111")
        err(self, lambda: cbe.save_settings(c, {"url": "ftp://x"}, "ADMIN"), "112")
        err(self, lambda: cbe.save_settings(c, {"max_change": "0"}, "ADMIN"), "089")
        err(self, lambda: cbe.update(c, "T", fetch=Fetch(fail=True)), "110")
        self.assertEqual(cbe.log(c)[0]["status"], "failed")
        # the daily run: off by default, then once a day after the chosen time, retried after a failure
        early = datetime.datetime.combine(t, datetime.time(8, 0))
        late = datetime.datetime.combine(t, datetime.time(10, 0))
        f = Fetch()
        self.assertIsNone(cbe.tick(c, late, fetch=f))
        cbe.save_settings(c, {"auto": "1", "time": "09:30"}, "ADMIN")
        self.assertIsNone(cbe.tick(c, early, fetch=f))
        self.assertEqual(cbe.tick(c, late, fetch=Fetch(fail=True))["status"], "failed")
        self.assertIsNone(cbe.tick(c, late + datetime.timedelta(minutes=5), fetch=f))      # no hammering: wait 15 min
        self.assertEqual(cbe.tick(c, late + datetime.timedelta(minutes=20), fetch=f)["status"], "ok")
        self.assertIsNone(cbe.tick(c, late + datetime.timedelta(minutes=60), fetch=f))     # once a day
        self.assertEqual(cbe.tick(c, late + datetime.timedelta(days=1), fetch=f)["status"], "ok")
        s = cbe.settings(c)
        self.assertEqual((s["auto"], s["time"]), ("1", "09:30"))


if __name__ == "__main__":
    unittest.main()
