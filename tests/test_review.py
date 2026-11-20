"""Daily review (ZDAY): every module compared with a normal working day, an opinion per module
(good / improving / needs attention / quiet) with the reason and what to do; only authorized modules."""
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm import util as clock  # noqa: E402
from mm.db import connect  # noqa: E402


def system():
    c = connect(":memory:")
    seed.seed(c)
    return c


class Verdicts(unittest.TestCase):
    def test_rules(self):
        from ai import review as R
        mon = "2026-11-09"                                           # a Monday
        fri = "2026-11-06"
        self.assertEqual(R._verdict(10, 10, 1, [], mon), R.GOOD)
        self.assertEqual(R._verdict(12, 10, 1, [], mon), R.UP)
        self.assertEqual(R._verdict(5, 10, 1, [], mon), R.ATTN)
        self.assertEqual(R._verdict(5, 10, 1, [], fri), R.GOOD)       # Friday off: low is fine
        self.assertEqual(R._verdict(5, 10, 1, [], mon, early=True), R.GOOD)
        self.assertEqual(R._verdict(0, 10, 1, [], mon), R.ATTN)
        self.assertEqual(R._verdict(0, 0.3, 1, [], mon), R.QUIET)     # not a daily event
        self.assertEqual(R._verdict(50, 10, 1, ["problem"], mon), R.ATTN)   # a problem beats volume
        self.assertEqual(R._verdict(0, 2, -1, [], mon), R.GOOD)       # no breakdowns
        self.assertEqual(R._verdict(1, 2, -1, [], mon), R.UP)
        self.assertEqual(R._verdict(5, 2, -1, [], mon), R.ATTN)
        self.assertIn("أعلى من المعتاد بـ 20%", R._compare(12, 10, 1, "الفواتير"))
        self.assertIn("👎", R._compare(5, 10, 1, "الفواتير"))
        self.assertIn("أضعاف", R._compare(30, 10, 1, "الفواتير"))
        self.assertIn("مرة كل 4 يوم", R._compare(0, 0.25, 1, "أوامر الشراء"))


class Review(unittest.TestCase):
    def test_every_module_with_figures_opinion_and_authorization(self):
        from ai import review as R
        c = system()
        day = (clock.today() - datetime.timedelta(days=4)).isoformat()
        r = R.day_review(c, day)
        self.assertEqual([m["code"] for m in r["modules"]], [x[0] for x in R.MODULES])
        for m in r["modules"]:
            self.assertIn(m["verdict"], R.VERDICT)
            self.assertTrue(m["opinion"])
            self.assertEqual(len(m["series"]), 7)
            self.assertEqual(m["series"][-1]["value"], m["main"]["today"])
            if m["problems"]:
                self.assertEqual(m["verdict"], R.ATTN)
        bill = c.execute("SELECT COALESCE(SUM(netwr),0) FROM billing WHERE fkdat=? AND cancelled=0 AND vbtyp IN ('M','O','P')",
                         (day,)).fetchone()[0] / 100.0
        sd = next(m for m in r["modules"] if m["code"] == "SD")
        self.assertAlmostEqual(sd["main"]["today"], round(bill, 2), places=2)   # the same figure as the books
        self.assertEqual(sum(r["counts"].values()), len(r["modules"]))
        names = [m["name"] for m in r["modules"] if m["verdict"] == R.ATTN]
        for n in names:
            self.assertIn(n, r["overall"])
        only = R.day_review(c, day, allowed=lambda a: a in ("SD", "FI"))
        self.assertEqual([m["code"] for m in only["modules"]], ["SD", "FI", "TAX"])
        # the current day before 4 pm: low volume is not called bad, the day is not over
        noon = datetime.datetime.combine(clock.today(), datetime.time(11, 0))
        with mock.patch.object(clock, "now", lambda: noon):
            r = R.day_review(c, clock.today().isoformat())
            self.assertTrue(r["early"])
            self.assertTrue(all(m["verdict"] != R.ATTN or m["problems"] for m in r["modules"]))
            self.assertNotEqual(R.default_day(), clock.today().isoformat())     # morning: yesterday's review

    def test_english_and_arabic(self):
        import json
        import re
        from ai import review as R
        c = system()
        day = (clock.today() - datetime.timedelta(days=4)).isoformat()
        ar, en = R.day_review(c, day), R.day_review(c, day, lang="en")
        self.assertEqual((ar["lang"], en["lang"]), ("ar", "en"))
        self.assertEqual(R.day_review(c, day, lang="xx")["lang"], "ar")              # unknown language: Arabic
        self.assertFalse(re.search("[\u0600-\u06FF]", json.dumps(en, ensure_ascii=False)), "Arabic text in the English review")
        self.assertTrue(re.search("[\u0600-\u06FF]", ar["overall"]))
        self.assertEqual([m["name"] for m in en["modules"]][:3], ["Sales", "Production", "Inventory"])
        for a, e in zip(ar["modules"], en["modules"]):                           # same figures and verdicts
            self.assertEqual((a["verdict"], a["main"]["today"], a["main"]["normal"], len(a["problems"]) + len(a["watch"])),
                             (e["verdict"], e["main"]["today"], e["main"]["normal"], len(e["problems"]) + len(e["watch"])))
        self.assertEqual(en["legend"]["ATTN"]["text"], "Needs attention")


if __name__ == "__main__":
    unittest.main()
