"""Calendar test: the demo seeds and the books stay correct on awkward dates
(month ends, February, leap day, year change). Each date runs on a fresh system."""
import datetime
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)
from mm import seed, util  # noqa: E402
from mm.db import connect, transaction  # noqa: E402

DATES = ["2026-01-01", "2026-01-02", "2026-01-31", "2026-02-28", "2026-03-01", "2026-03-31",
         "2026-04-30", "2026-06-01", "2026-12-31", "2027-01-01", "2028-02-29", "2028-03-01"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Calendar(unittest.TestCase):
    def test_seed_and_books_on_awkward_dates(self):
        from co.reports import reconcile
        from fi.reports import statements, trial_balance
        from mm.reports import consistency_check
        old = util.set_clock(None)
        try:
            for d in DATES:
                with self.subTest(date=d):
                    D = datetime.date.fromisoformat(d)
                    util.set_clock(D)
                    c = connect(":memory:")
                    self.assertEqual(seed.seed(c), [], "demo postings failed")
                    self.assertTrue(statements(c, D.year, D.month, D.month)["balanced"])
                    self.assertTrue(reconcile(c, D.year, D.month, D.month)["ok"], "FI = CO-PA")
                    pm = D.replace(day=1) - datetime.timedelta(days=1)
                    self.assertTrue(reconcile(c, pm.year, pm.month, pm.month)["ok"])
                    self.assertTrue(consistency_check(c)["ok"], "stock = G/L")
                    tb = sum(x["closing"] for x in trial_balance(c, D.year, 1, D.month))
                    self.assertAlmostEqual(tb, 0, 2, "trial balance")
                    for tab, cond in (("acc_doc", ""), ("mat_doc", ""), ("co_doc", " AND wrttp='04'")):
                        n = c.execute("SELECT COUNT(*) FROM %s WHERE budat>?%s" % (tab, cond),
                                      (d,)).fetchone()[0]
                        self.assertEqual(n, 0, "actual %s dated after %s (plan values may be)" % (tab, d))
                    c.close()
        finally:
            util.set_clock(old)


class Platform(unittest.TestCase):
    def test_no_direct_date_calls(self):
        """Every 'today' must come from the business clock (mm.util.today/now)."""
        bad = []
        for pkg in ("mm", "co", "fi", "pur", "md", "pp", "sd", "web", "qa"):
            for dp, _, files in os.walk(os.path.join(ROOT, pkg)):
                for f in files:
                    if not f.endswith(".py") or (pkg == "mm" and f == "util.py"):
                        continue
                    src = open(os.path.join(dp, f), encoding="utf-8").read()
                    for m in re.finditer(r"date\.today\(\)|datetime\.now\(\)", src):
                        bad.append("%s/%s" % (os.path.relpath(dp, ROOT), f))
        self.assertEqual(bad, [])

    def test_savepoint_rolls_back_inner_block_only(self):
        c = connect(":memory:")
        with transaction(c):
            c.execute("INSERT INTO settings VALUES ('sp_a', '1')")
            try:
                with transaction(c):
                    c.execute("INSERT INTO settings VALUES ('sp_b', '1')")
                    raise ValueError("inner failure")
            except ValueError:
                pass
            c.execute("INSERT INTO settings VALUES ('sp_c', '1')")
        keys = {r[0] for r in c.execute("SELECT key FROM settings WHERE key LIKE 'sp_%'")}
        self.assertEqual(keys, {"sp_a", "sp_c"})

    def test_seed_is_atomic(self):
        """A failing seed leaves an empty database (seeded again on the next start)."""
        from mm import seed as s
        c = connect(":memory:")
        orig = s._seed

        def boom(conn):
            orig.__globals__["master"].create_plant(conn, "9999", "x", "x")
            raise RuntimeError("crash in the middle")
        s._seed = boom
        try:
            with self.assertRaises(RuntimeError):
                s.seed(c)
        finally:
            s._seed = orig
        self.assertEqual(c.execute("SELECT COUNT(*) FROM plant").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
