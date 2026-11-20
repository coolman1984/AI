"""Ask NERP (ZAI): read-only tools equal the screens, basic mode (no internet), the AI agent
loop with a fake API (tool calls, results, thinking blocks passed back, authorization,
refusal, fallback to basic mode when the service is unreachable) and the settings."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fixture  # noqa: E402,F401
from mm import seed  # noqa: E402
from mm.db import connect  # noqa: E402
from mm.util import MMError  # noqa: E402

T = fixture.T
_C = {}


def system():
    if "c" not in _C:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        c = connect(":memory:")
        seed.seed(c)
        _C["c"] = c
    return _C["c"]


def err(test, fn, no):
    with test.assertRaises(MMError) as x:
        fn()
    test.assertEqual(x.exception.msg_no, no, str(x.exception))


class Tools(unittest.TestCase):
    def test_tools_read_the_same_figures_as_the_screens(self):
        from ai import tools
        from sd.reports import cockpit
        c = system()
        s = tools.run(c, "sales_overview", {})
        k = cockpit(c, s["period"][0], s["period"][1])["kpi"]
        self.assertEqual(s["revenue_egp"], round(k["revenue"] / 100.0, 2))
        st = tools.run(c, "stock_lookup", {"query": "glass"})
        g = [m for m in st["materials"] if m["material"] == "RM-1005"][0]
        q = c.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr='RM-1005' AND insmk='U'").fetchone()[0]
        self.assertEqual(g["unrestricted"], q / 1000.0)
        for name in tools.TOOLS:                                     # every tool answers and names a screen
            r = tools.run(c, name, {"query": "FG"} if name == "stock_lookup" else {})
            self.assertTrue(r.get("screen") or r.get("screens"), name)
            json.dumps(r, default=str)
        self.assertEqual(len(tools.definitions()), len(tools.TOOLS))
        with self.assertRaises(PermissionError):
            tools.run(c, "hr_overview", {}, allowed=lambda area: area != "HR")


class BasicMode(unittest.TestCase):
    def test_keywords_answer_without_internet_and_are_logged(self):
        from ai import agent
        c = system()
        n0 = c.execute("SELECT COUNT(*) FROM ai_log").fetchone()[0]
        for q, tool in (("بعنا كام الشهر ده؟", "sales_overview"), ("مين العملاء اللي عليهم فلوس متأخرة؟", "receivables"),
                        ("عندنا كام زجاج في المخزن؟", "stock_lookup"), ("إيه حالة الصيانة؟", "maintenance_overview"),
                        ("What is our stock of FG-3001?", "stock_lookup")):
            r = agent.ask(c, q, "T")
            self.assertEqual(r["mode"], "basic")
            self.assertEqual([t["tool"] for t in r["tools"]], [tool], q)
        self.assertIn("RM-1005", agent.ask(c, "عندنا كام زجاج في المخزن؟", "T")["answer"])
        self.assertEqual(agent.ask(c, "الطقس عامل إيه؟", "T")["tools"], [])
        b = agent.ask(c, "اديني ملخص اليوم", "T")                         # daily briefing: several tools
        self.assertEqual([t["tool"] for t in b["tools"]], ["sales_overview", "production_today", "receivables",
                                                             "quality_overview", "maintenance_overview"])
        self.assertGreaterEqual(c.execute("SELECT COUNT(*) FROM ai_log").fetchone()[0], n0 + 8)
        err(self, lambda: agent.ask(c, "  ", "T"), "904")


class Languages(unittest.TestCase):
    def test_copilot_questions_in_english_and_arabic(self):
        """the suggested questions of the Copilot widget reach the right data and answer in the question's language"""
        import re
        from ai import agent
        c = system()
        js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "static", "ai_screens.js"),
                  encoding="utf-8").read()
        for q, tool in [("How much did we sell this month?", "sales_overview"), ("Which customers have overdue receivables?", "receivables"),
                        ("How much glass do we have in stock?", "stock_lookup"), ("How are the machines doing?", "maintenance_overview"),
                        ("How is quality, any rejected lots?", "quality_overview"), ("Which tax returns are due soon?", "tax_calendar"),
                        ("What are cash and profit this month?", "finance_overview"),
                        ("How many employees and what is the payroll cost?", "hr_overview"),
                        ("بعنا كام الشهر ده؟", "sales_overview"), ("الماكينات عاملة إيه؟", "maintenance_overview")]:
            self.assertIn(q, js, "question not offered in the Copilot")
            r = agent.basic_answer(c, q, "OWNER")
            self.assertEqual(r["tools"][0]["tool"], tool, q)
            arabic = bool(re.search("[\u0600-\u06FF]", r["answer"]))
            self.assertEqual(arabic, agent._arabic(q), q)
        b = agent.basic_answer(c, "Give me today's briefing: sales, production, overdue receivables, quality and maintenance", "OWNER")
        self.assertTrue(b["answer"].startswith("**Today's briefing:**"))
        self.assertGreaterEqual(len(b["tools"]), 3)


class Agent(unittest.TestCase):
    def setUp(self):
        from ai import agent
        self.c = system()
        agent.save_settings(self.c, {"api_key": "sk-ant-test-0000000000", "model": "claude-opus-5-5"}, "T")

    def tearDown(self):
        from ai import agent
        agent.save_settings(self.c, {"api_key": "-"}, "T")

    def test_tool_loop_passes_results_and_thinking_back(self):
        from ai import agent
        calls = []
        thinking = {"type": "thinking", "thinking": "", "signature": "sig-1"}

        def fake(payload, key):
            calls.append(json.loads(json.dumps(payload)))
            if len(calls) == 1:
                return {"stop_reason": "tool_use", "model": "claude-opus-5-5", "content": [thinking,
                        {"type": "tool_use", "id": "tu_1", "name": "sales_overview", "input": {}},
                        {"type": "tool_use", "id": "tu_2", "name": "stock_lookup", "input": {"query": "glass"}}]}
            return {"stop_reason": "end_turn", "model": "claude-opus-5-5",
                    "content": [{"type": "text", "text": "المبيعات كويسة. افتح ZSD_COCKPIT."}]}
        r = agent.ask(self.c, "بعنا كام وعندنا زجاج قد إيه؟", "T", post=fake)
        self.assertEqual((r["mode"], r["answer"]), ("ai", "المبيعات كويسة. افتح ZSD_COCKPIT."))
        self.assertEqual([t["tool"] for t in r["tools"]], ["sales_overview", "stock_lookup"])
        p1, p2 = calls
        self.assertEqual(p1["model"], "claude-opus-5-5")
        self.assertEqual(p1["fallbacks"], "default")                        # refusal fallback on
        self.assertNotIn("temperature", p1)
        self.assertEqual(p1["output_config"], {"effort": "medium"})
        self.assertEqual(len(p1["tools"]), len(agent.T.TOOLS))
        self.assertEqual(p2["messages"][-2]["content"][0], thinking)         # assistant turn unchanged
        res = p2["messages"][-1]["content"]                                 # all results in ONE user message
        self.assertEqual([x["tool_use_id"] for x in res], ["tu_1", "tu_2"])
        sales = json.loads(res[0]["content"])
        self.assertEqual(sales["screen"], "ZSD_COCKPIT")
        self.assertIn("RM-1005", res[1]["content"])

    def test_authorization_refusal_and_unreachable_service(self):
        from ai import agent

        def asks_hr(payload, key):
            if payload["messages"][-1]["role"] == "user" and isinstance(payload["messages"][-1]["content"], str):
                return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "h1", "name": "hr_overview", "input": {}}]}
            last = payload["messages"][-1]["content"][0]
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "denied" if last.get("is_error") else "ok"}]}
        from sec import auth
        users = [r[0] for r in self.c.execute("SELECT DISTINCT bname FROM usr_role ORDER BY bname")]
        no_hr = [u for u in users if not auth.area_allowed(auth.profile(self.c, u), "HR", "03")]
        self.assertTrue(no_hr)                                              # e.g. a sales user
        r = agent.ask(self.c, "عدد الموظفين؟", no_hr[0], post=asks_hr, check_auth=True)
        self.assertEqual(r["answer"], "denied")                             # personnel data stays closed
        self.assertTrue(r["tools"][0]["denied"])
        r = agent.ask(self.c, "x?", "T", post=lambda p, k: {"stop_reason": "refusal", "content": []})
        self.assertIn("declined", r["answer"])

        def down(payload, key):
            raise agent.AIError("No connection", "network")
        r = agent.ask(self.c, "بعنا كام الشهر ده؟", "T", post=down)
        self.assertEqual(r["mode"], "basic")                                # falls back to basic mode
        self.assertTrue(r["note"])
        self.assertEqual(r["tools"][0]["tool"], "sales_overview")
        e = self.c.execute("SELECT error FROM ai_log ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertIn("No connection", e)

    def test_settings(self):
        from ai import agent
        s = agent.public_settings(self.c)
        self.assertEqual(s["mode"], "ai")
        self.assertNotIn("key", s)
        self.assertNotIn("0000000000", s["key_masked"])
        err(self, lambda: agent.save_settings(self.c, {"api_key": "abc"}, "T"), "903")
        err(self, lambda: agent.save_settings(self.c, {"effort": "extreme"}, "T"), "902")
        agent.save_settings(self.c, {"enabled": False}, "T")
        self.assertEqual(agent.public_settings(self.c)["mode"], "basic")


if __name__ == "__main__":
    unittest.main()
