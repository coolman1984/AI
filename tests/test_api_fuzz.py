"""API robustness: every route answers an empty or nonsense request with a business
message (MMError -> HTTP 422) - never with an internal error - and never leaves a
database transaction open."""
import os
import sys
import traceback
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401  (fixed business date)
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

SKIP = ("shutdown", "bye", "ping", "qa/run", "/office/", "/com/")
BODIES = [({}, {}),
          ({"items": [{}], "lines": [{}], "matnr": "ZZZ", "qty": "abc", "budat": "99", "id": "x",
            "gjahr": "x", "perio": "y", "amount": "-x", "kunnr": "NOPE", "lifnr": "NOPE"},
           {"id": "x", "matnr": "ZZZ", "gjahr": "x", "perio": "y", "d1": "q", "d2": "q", "date": "q"})]


class Req:
    def __init__(self, body):
        self.user = "FUZZ"
        self.body = body
        self.headers = {}


class Fuzz(unittest.TestCase):
    def test_all_routes(self):
        import web.server as S
        c = connect(":memory:")
        seed.seed(c)
        S._local.conn = c
        bad = []
        for method, rx, fn in S.ROUTES:
            pat = rx.pattern.strip("^$")
            if any(w in pat for w in SKIP):
                continue
            import re
            kw = {}
            for k in rx.groupindex:      # enumerated groups (a|b|c) get their first value
                m = re.search(r"\(\?P<%s>([^)]*)\)" % k, pat)
                alt = m.group(1) if m else ""
                kw[k] = alt.split("|")[0] if "|" in alt and "[" not in alt else "1"
            for body, q in BODIES:
                try:
                    fn(Req(dict(body)), dict(q), **kw)
                except MMError:
                    pass
                except Exception as e:
                    tb = traceback.extract_tb(e.__traceback__)[-1]
                    bad.append("%s %s: %s %s at %s:%s" % (method, pat, type(e).__name__, str(e)[:60],
                                                         os.path.relpath(tb.filename), tb.lineno))
                if c.in_transaction:
                    bad.append("%s %s: transaction left open" % (method, pat))
                    c.execute("ROLLBACK")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()


class Layers(unittest.TestCase):
    def test_no_sql_writes_in_api_handlers(self):
        """Writes belong in the engines (transaction, checks, change documents)."""
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
        bad = []
        for f in os.listdir(root):
            if f.endswith(".py"):
                src = open(os.path.join(root, f), encoding="utf-8").read()
                for m in re.finditer(r"execute\(\s*\"(INSERT|UPDATE|DELETE)", src):
                    bad.append("%s: %s" % (f, src[m.start():m.start() + 60]))
        self.assertEqual(bad, [])
