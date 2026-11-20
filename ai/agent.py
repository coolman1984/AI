"""Ask NERP - an agent that answers questions about the company's data.

AI mode (an Anthropic API key is configured): the question goes to Claude through the Messages
API (plain HTTPS with urllib - NERP uses the Python standard library only). Claude decides which
read-only tools (ai/tools.py) it needs, NERP runs them on the local database with the user's
authorizations, sends the results back, and Claude writes the answer - in Egyptian Arabic when
the question is Arabic. Only the tool results of the question leave the computer, never the
whole database.

Basic mode (no key, no internet, or the AI service unreachable): keywords pick the matching tool
and a fixed template answers. Fewer questions are understood, but it never needs the internet.

Every question is logged (ai_log) with the user, the tools used and the answer.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts

from . import tools as T

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"      # a declined request is retried on a fallback model
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2")
MAX_STEPS = 8                                         # tool rounds per question
MAX_TOKENS = 16000

SYSTEM = """You are "Ask NERP", the assistant inside NERP, the ERP of an Egyptian manufacturing company.
You answer questions of managers and staff about the company's own data: sales, customers and receivables,
finance, purchasing, stock, production, quality, maintenance, Egyptian taxes and HR.

Rules:
- Every figure in your answer must come from a tool result of this conversation. Never estimate or invent
  numbers; if no tool gives the information, say so and name the screen where the user can look.
- Call the tools you need (several at once when the question has several parts), then answer.
- Answer in the language of the question. For Arabic questions use clear, friendly Egyptian Arabic
  that a non-technical manager understands.
- Start with the direct answer in one or two sentences, then at most a few short bullet points with the
  key numbers, then one practical recommendation when the numbers show a problem.
- Amounts are Egyptian pounds (EGP / جنيه); format thousands with commas. Dates as DD/MM/YYYY.
- At the end, name the NERP screen (T-code from the tool result, e.g. ZSD_COCKPIT) to open for details.
- You can only read data. If the user asks you to post, change or delete something, explain which screen
  does it - you cannot do it yourself.
- If a tool returns an authorization error, tell the user they are not authorized for that area."""


# ------------------------------------------------------------------ settings
def settings(conn):
    s = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM ai_setting")}
    key = os.environ.get("ANTHROPIC_API_KEY") or s.get("api_key") or ""
    return {"model": s.get("model") or "claude-opus-5-5", "effort": s.get("effort") or "medium",
            "enabled": s.get("enabled", "1") == "1", "key": key,
            "key_source": "environment" if os.environ.get("ANTHROPIC_API_KEY") else ("saved" if s.get("api_key") else "")}


def public_settings(conn):
    s = settings(conn)
    k = s.pop("key")
    s["key_masked"] = (k[:7] + "…" + k[-4:]) if len(k) > 12 else ("set" if k else "")
    s["mode"] = "ai" if (k and s["enabled"]) else "basic"
    return s


def save_settings(conn, data, user):
    model = (data.get("model") or "claude-opus-5-5").strip()
    if not re.fullmatch(r"claude-[a-z0-9\-]+", model):
        raise MMError("Model id looks wrong (e.g. claude-opus-5-5)", "AI", "901")
    effort = (data.get("effort") or "medium").lower()
    if effort not in ("low", "medium", "high"):
        raise MMError("Effort must be low, medium or high", "AI", "902")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO ai_setting VALUES ('model',?)", (model,))
        conn.execute("INSERT OR REPLACE INTO ai_setting VALUES ('effort',?)", (effort,))
        conn.execute("INSERT OR REPLACE INTO ai_setting VALUES ('enabled',?)", ("1" if data.get("enabled", True) else "0",))
        key = (data.get("api_key") or "").strip()
        if key == "-":                                    # remove the saved key
            conn.execute("DELETE FROM ai_setting WHERE key='api_key'")
        elif key:
            if not key.startswith("sk-ant-"):
                raise MMError("This is not an Anthropic API key (it starts with sk-ant-)", "AI", "903")
            conn.execute("INSERT OR REPLACE INTO ai_setting VALUES ('api_key',?)", (key,))
    return {"message": "Assistant settings saved"}


# ------------------------------------------------------------------ the API call (stdlib HTTPS)
class AIError(Exception):
    def __init__(self, msg, kind="api"):
        super().__init__(msg)
        self.kind = kind


def http_post(payload, key, timeout=120):
    """POST /v1/messages; retries 429 / 5xx / connection errors twice with backoff"""
    data = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", "x-api-key": key, "anthropic-version": API_VERSION}
    if "fallbacks" in payload:
        headers["anthropic-beta"] = FALLBACK_BETA
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            if e.code in (401, 403):
                raise AIError("The API key was refused (%d) - check it in ZAI_CONF" % e.code, "auth")
            if e.code == 400:
                raise AIError("The AI service rejected the request: %s" % body, "request")
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < 2:
                last = AIError("The AI service is busy (%d)" % e.code, "busy")
                time.sleep(float(e.headers.get("retry-after") or 2 * (attempt + 1)))
                continue
            raise AIError("The AI service answered %d: %s" % (e.code, body), "busy" if e.code >= 429 else "api")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = AIError("No connection to the AI service (%s)" % getattr(e, "reason", e), "network")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
    raise last


# ------------------------------------------------------------------ the agent loop
def _allowed_fn(conn, user, check_auth):
    if not check_auth:
        return None
    from sec import auth as A
    prof = A.profile(conn, user)
    return lambda area: A.area_allowed(prof, area, "03")


def run_agent(conn, question, user, history=None, post=None, check_auth=False):
    """Claude chooses the tools; NERP runs them. post(payload, key) is the HTTP call (tests inject a fake)."""
    s = settings(conn)
    post = post or http_post
    allowed = _allowed_fn(conn, user, check_auth)
    today = clock.today().isoformat()
    messages = []
    for h in (history or [])[-6:]:                      # short memory of the chat: text only
        if h.get("q") and h.get("a"):
            messages += [{"role": "user", "content": str(h["q"])[:2000]},
                         {"role": "assistant", "content": str(h["a"])[:4000]}]
    messages.append({"role": "user", "content": "Today is %s. Question: %s" % (today, question)})
    used = []
    for _ in range(MAX_STEPS):
        payload = {"model": s["model"], "max_tokens": MAX_TOKENS, "system": SYSTEM, "tools": T.definitions(),
                   "messages": messages, "output_config": {"effort": s["effort"]}}
        if s["model"] in FALLBACK_MODELS:
            payload["fallbacks"] = "default"
        r = post(payload, s["key"])
        stop = r.get("stop_reason")
        content = r.get("content") or []
        if stop == "refusal":
            return {"answer": "The AI service declined to answer this question. Please rephrase it.", "tools": used}
        messages.append({"role": "assistant", "content": content})      # unchanged: thinking blocks included
        if stop == "pause_turn":
            continue
        if stop == "tool_use":
            results = []
            for b in content:
                if b.get("type") != "tool_use":
                    continue
                name, args = b.get("name"), b.get("input") or {}
                try:
                    out = T.run(conn, name, args, allowed)
                    results.append({"type": "tool_result", "tool_use_id": b["id"],
                                    "content": json.dumps(out, ensure_ascii=False, default=str)})
                    used.append({"tool": name, "args": args, "screen": out.get("screen") or (out.get("screens") or [""])[0]})
                except PermissionError as e:
                    results.append({"type": "tool_result", "tool_use_id": b["id"], "content": str(e), "is_error": True})
                    used.append({"tool": name, "args": args, "denied": True})
                except (MMError, KeyError, ValueError) as e:
                    results.append({"type": "tool_result", "tool_use_id": b["id"],
                                    "content": "Error: %s" % (getattr(e, "msg", None) or e), "is_error": True})
            messages.append({"role": "user", "content": results})        # all results in one message
            continue
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
        if stop == "max_tokens" and not text:
            text = "The answer was too long - please ask a narrower question."
        return {"answer": text or "No answer.", "tools": used, "model": r.get("model")}
    return {"answer": "The question needed too many steps - please split it into smaller questions.", "tools": used}


# ------------------------------------------------------------------ basic mode (no internet)
INTENTS = [   # (tool, keywords) - first match wins; Arabic and English
    ("receivables", r"مديون|متأخر.*(دفع|سداد)|فلوس.*(عملا|عند|متأخر)|عليهم فلوس|تحصيل|receivab|overdue|owes|collection"),
    ("tax_calendar", r"ضريب|ضرايب|إقرار|اقرار|tax|vat|form 41"),
    ("quality_overview", r"جود|رفض|مرفوض|عيوب.*خام|فحص|quality|reject|inspection|ppm"),
    ("maintenance_overview", r"صيان|عطل|أعطال|ماكين|maintenance|breakdown|machine|mttr|mtbf"),
    ("daily_meeting", r"اجتماع|هالك|فاقد|meeting|scrap|loss"),
    ("production_today", r"النهارده.*(إنتاج|انتاج|خط)|خطوط|line|shop.?floor|board"),
    ("production_overview", r"إنتاج|انتاج|أوامر.*إنتاج|تصنيع|production|manufactur|work order"),
    ("purchasing_overview", r"مشتري|مورد|شراء|purchas|vendor|supplier|po\b"),
    ("stock_lookup", r"مخزون|مخزن|رصيد|كام.*(قطعة|عندنا)|stock|inventory|on hand"),
    ("hr_overview", r"موظف|عمال|مرتب|رواتب|أجور|hr\b|employee|headcount|payroll|salar"),
    ("finance_overview", r"نقدي|كاش|سيول|ربح|خسار|ميزاني|حسابات|cash|profit|loss|balance|finance"),
    ("sales_overview", r"مبيع|بعنا|بيع|إيراد|ايراد|عميل|عملاء|sales|sell|sold|revenue|customer"),
]


def _arabic(s):
    return bool(re.search(r"[؀-ۿ]", s or ""))


def _n(v, d=0):
    if v is None:
        return "-"
    return ("{:,.%df}" % d).format(v)


AR_WORDS = {"زجاج": "glass", "صاج": "steel", "حديد": "steel", "دهان": "paint", "بوية": "paint", "نحاس": "copper",
            "سلك": "wire", "كرتون": "carton", "مقبض": "handle", "دولاب": "cabinet", "مطبخ": "kitchen", "رولمان": "bearing",
            "سير": "belt", "زيت": "oil", "بلاستيك": "polypropylene"}
STOP = {"مخزون", "المخزون", "مخزن", "المخزن", "رصيد", "عندنا", "كام", "فيه", "في", "من", "قد", "ايه", "إيه", "اية",
        "stock", "inventory", "how", "much", "many", "what", "the", "our", "have", "hand", "of", "is", "do", "we"}


def _stock_query(q):
    m = re.search(r"\b([A-Z]{2,4}-\d{3,5})\b", q.upper())
    if m:
        return m.group(1)
    for w in re.findall(r"[A-Za-z\u0600-\u06FF0-9\-]{3,}", q):
        w = w.strip("؟?")
        base = re.sub(r"^ال", "", w)
        if w.lower() in STOP or base in STOP:
            continue
        return AR_WORDS.get(base, AR_WORDS.get(w, w))
    return ""


BRIEFING = r"ملخص.*(اليوم|النهارده|سريع)|ملخص اليوم|briefing|daily summary|summary of (the|to)day"


def _briefing(conn, allowed, ar):
    """several tools in one answer (daily briefing) - each part only if the user may see it"""
    parts, used = [], []
    for tool in ("sales_overview", "production_today", "receivables", "quality_overview", "maintenance_overview"):
        try:
            d = T.run(conn, tool, {}, allowed)
        except PermissionError:
            continue
        parts.append(_template(tool, d, ar).split("\n" + ("للتفاصيل" if ar else "Details"))[0])
        used.append({"tool": tool, "args": {}, "screen": d.get("screen")})
    head = "**ملخص اليوم:**" if ar else "**Today's briefing:**"
    return {"answer": head + "\n\n" + "\n\n".join(parts), "tools": used}


def basic_answer(conn, question, user, check_auth=False):
    allowed = _allowed_fn(conn, user, check_auth)
    q = question or ""
    ar = _arabic(q)
    if re.search(BRIEFING, q, re.I):
        return _briefing(conn, allowed, ar)
    tool = next((t for t, rx in INTENTS if re.search(rx, q, re.I)), None)
    if not tool:
        return {"answer": ("مش قادر أفهم السؤال في الوضع الأساسي. جرّب تسأل عن: المبيعات، الفلوس المتأخرة عند العملاء، "
                           "المخزون، الإنتاج، الجودة، الصيانة، الضرايب أو الموظفين." if ar else
                           "Basic mode did not understand the question. Ask about sales, receivables, stock, "
                           "production, quality, maintenance, taxes or HR."), "tools": []}
    args = {"query": _stock_query(q)} if tool == "stock_lookup" else {}
    try:
        d = T.run(conn, tool, args, allowed)
    except PermissionError:
        return {"answer": "مش مسموح لك تشوف البيانات دي." if ar else "You are not authorized to see this data.",
                "tools": [{"tool": tool, "denied": True}]}
    return {"answer": _template(tool, d, ar), "tools": [{"tool": tool, "args": args, "screen": d.get("screen") or
                                                          (d.get("screens") or [""])[0]}]}


def _template(tool, d, ar):
    sc = d.get("screen") or (d.get("screens") or [""])[0]
    if tool == "sales_overview":
        top = d["top_customers"][0] if d["top_customers"] else None
        return (("المبيعات من %s لـ %s: **%s جنيه**، والهامش %s%%.\n- طلبات جديدة: %s جنيه (%s أمر)\n- لسه ما اتسلّمش: %s جنيه\n"
                 "- التسليم في الميعاد: %s%%%s\nللتفاصيل افتح %s.") % (d["period"][0], d["period"][1], _n(d["revenue_egp"]),
                 d["margin_pct"], _n(d["incoming_orders_egp"]), d["orders"], _n(d["backlog_egp"]), d["on_time_in_full_pct"],
                 ("\n- أكبر عميل: %s (%s جنيه)" % (top["name"], _n(top["net_egp"]))) if top else "", sc)) if ar else \
            ("Sales %s to %s: **EGP %s**, margin %s%%. New orders EGP %s, backlog EGP %s. Details: %s." % (
                d["period"][0], d["period"][1], _n(d["revenue_egp"]), d["margin_pct"], _n(d["incoming_orders_egp"]),
                _n(d["backlog_egp"]), sc))
    if tool == "receivables":
        lines = "\n".join("- %s: %s جنيه متأخرة" % (c["name"], _n(c["overdue"])) for c in d["customers"][:5] if c["overdue"])
        return ("الفلوس المتأخرة عند العملاء: **%s جنيه**، منها %s جنيه متأخرة أكتر من 90 يوم.\n%s\nللتفاصيل افتح %s."
                % (_n(d["overdue_total"]), _n(d["totals"].get("d90p")), lines, sc)) if ar else \
            ("Overdue receivables: **EGP %s** (over 90 days: EGP %s). Details: %s." % (
                _n(d["overdue_total"]), _n(d["totals"].get("d90p")), sc))
    if tool == "stock_lookup":
        if not d["materials"]:
            return ("مش لاقي صنف بالاسم ده. اكتب جزء من رقم الصنف أو اسمه." if ar else d["note"])
        rows = "\n".join(("- %s %s: %s %s متاح، %s تحت الفحص، %s محجوز (قيمة %s جنيه)" if ar else
                          "- %s %s: %s %s unrestricted, %s in inspection, %s blocked (EGP %s)") % (
            m["material"], m["text"], _n(m["unrestricted"]), m["unit"], _n(m["quality_inspection"]), _n(m["blocked"]),
            _n(m["value_egp"])) for m in d["materials"][:5])
        return rows + ("\nللتفاصيل افتح %s." % sc if ar else "\nDetails: %s." % sc)
    if tool == "production_today":
        t = d["total"]
        return ("الإنتاج يوم %s: اتنتج **%s** من مخطط %s (إنجاز %s%%)، ووقت التوقف %s دقيقة.\nللتفاصيل افتح %s." % (
            d["date"], _n(t["produced"]), _n(t["plan"]), t["achievement_pct"], t["downtime_min"], sc)) if ar else \
            ("Production %s: %s produced of %s planned (%s%%), downtime %s min. Details: %s." % (
                d["date"], _n(t["produced"]), _n(t["plan"]), t["achievement_pct"], t["downtime_min"], sc))
    if tool == "production_overview":
        return ("الإنتاج من %s لـ %s: %s أمر إنتاج، منهم %s مفتوح و%s متأخر. الإنتاج السليم %s والهالك %s (%s%%).\n"
                "أوامر ناقصها خامات: %s.\nللتفاصيل افتح %s." % (d["period"][0], d["period"][1], d["orders"], d["open_orders"],
                d["late_orders"], _n(d["yield_units"]), _n(d["scrap_units"]), d["scrap_pct"], d["orders_missing_components"], sc)) \
            if ar else ("Production %s-%s: %s orders, %s open, %s late; yield %s, scrap %s (%s%%). Details: %s." % (
                d["period"][0], d["period"][1], d["orders"], d["open_orders"], d["late_orders"], _n(d["yield_units"]),
                _n(d["scrap_units"]), d["scrap_pct"], sc))
    if tool == "quality_overview":
        return ("الجودة: %s دفعة تحت الفحص، نسبة الدفعات المقبولة %s%%، والمرفوض %s ppm، و%s شكوى مفتوحة.\nللتفاصيل افتح %s." % (
            d["lots_in_inspection"], d["accepted_lots_pct"], d["rejected_ppm"], d["open_complaints"], sc)) if ar else \
            ("Quality: %s lots in inspection, accepted lots %s%%, rejected %s ppm, %s open complaints. Details: %s." % (
                d["lots_in_inspection"], d["accepted_lots_pct"], d["rejected_ppm"], d["open_complaints"], sc))
    if tool == "maintenance_overview":
        return ("الصيانة: %s أمر مفتوح (%s متأخر)، %s عطل بإجمالي توقف %s دقيقة، والماكينات شغالة %s%% من الوقت. "
                "تكلفة الصيانة %s جنيه.\nللتفاصيل افتح %s." % (d["open_orders"], d["overdue_orders"], d["breakdowns"],
                d["downtime_min"], d["availability_pct"], _n(d["cost_egp"]), sc)) if ar else \
            ("Maintenance: %s open orders (%s overdue), %s breakdowns, %s min downtime, availability %s%%, cost EGP %s. "
             "Details: %s." % (d["open_orders"], d["overdue_orders"], d["breakdowns"], d["downtime_min"],
                               d["availability_pct"], _n(d["cost_egp"]), sc))
    if tool == "daily_meeting":
        return ("ملخص الاجتماع: %s أمر متأخر، %s أمر ناقصه خامات، الهالك الشهر ده %s قطعة (%s%%)، والفاقد %s جنيه، "
                "والبضاعة المستنية إعدام %s جنيه.\nللتفاصيل افتح %s." % (d["orders_late"], d["orders_missing_components"],
                _n(d["scrap_month_units"]), d["defect_month_pct"], _n(d["material_loss_month_egp"]), _n(d["pending_scrap_egp"]), sc)) \
            if ar else ("Meeting: %s late orders, %s missing components, scrap %s units (%s%%), loss EGP %s, pending scrap "
                        "EGP %s. Details: %s." % (d["orders_late"], d["orders_missing_components"], _n(d["scrap_month_units"]),
                                                  d["defect_month_pct"], _n(d["material_loss_month_egp"]),
                                                  _n(d["pending_scrap_egp"]), sc))
    if tool == "purchasing_overview":
        k = d["kpi"]
        return ("المشتريات: اتصرف %s جنيه في %s أمر شراء، وفيه %s بند متأخر من الموردين بقيمة %s جنيه.\nللتفاصيل افتح %s." % (
            _n(k.get("spend")), k.get("po_count"), k.get("overdue_items"), _n(k.get("overdue_value")), sc)) if ar else \
            ("Purchasing: spend EGP %s in %s POs, %s overdue items worth EGP %s. Details: %s." % (
                _n(k.get("spend")), k.get("po_count"), k.get("overdue_items"), _n(k.get("overdue_value")), sc))
    if tool == "finance_overview":
        return ("الحسابات (%s/%s): النقدية %s جنيه، فلوس عند العملاء %s، علينا للموردين %s، ونتيجة الشهر %s جنيه.\n"
                "للتفاصيل افتح %s." % (d["period"], d["year"], _n(d.get("cash")), _n(d.get("ar")), _n(d.get("ap")),
                                       _n(d.get("result")), sc)) if ar else \
            ("Finance %s/%s: cash EGP %s, receivables %s, payables %s, result of the month %s. Details: %s." % (
                d["period"], d["year"], _n(d.get("cash")), _n(d.get("ar")), _n(d.get("ap")), _n(d.get("result")), sc))
    if tool == "tax_calendar":
        nxt = d["due_next_30_days"][:3]
        return ("الضرايب: %s إقرار/دفعة متأخرة، و%s مطلوبة خلال 30 يوم%s.\nللتفاصيل افتح %s." % (
            len(d["overdue"]), len(d["due_next_30_days"]),
            ("، أقربها: " + "، ".join("%s (%s)" % (x["label"], x["due"]) for x in nxt)) if nxt else "", sc)) if ar else \
            ("Taxes: %s overdue, %s due within 30 days. Details: %s." % (len(d["overdue"]), len(d["due_next_30_days"]), sc))
    if tool == "hr_overview":
        return ("الموظفين: %s موظف، وتكلفة المرتبات الشهرية حوالي %s جنيه، و%s في إجازة النهارده.\nللتفاصيل افتح %s." % (
            d["headcount"], _n(d["monthly_personnel_cost_egp"]), d["on_leave_today"] if not isinstance(d["on_leave_today"], list)
            else len(d["on_leave_today"]), sc)) if ar else \
            ("HR: %s employees, monthly personnel cost EGP %s. Details: %s." % (d["headcount"], _n(d["monthly_personnel_cost_egp"]), sc))
    return json.dumps(d, ensure_ascii=False, default=str)[:1500]


# ------------------------------------------------------------------ entry point
def ask(conn, question, user, history=None, post=None, check_auth=False):
    question = (question or "").strip()
    if not question:
        raise MMError("Write your question", "AI", "904")
    if len(question) > 2000:
        raise MMError("The question is too long (max 2,000 characters)", "AI", "905")
    s = settings(conn)
    t0 = time.time()
    mode, err = "basic", ""
    if s["key"] and s["enabled"]:
        try:
            res = run_agent(conn, question, user, history, post, check_auth)
            mode = "ai"
        except AIError as e:
            err = str(e)
            res = basic_answer(conn, question, user, check_auth)
            res["note"] = ("الذكاء الاصطناعي مش متاح دلوقتي (%s) - دي إجابة الوضع الأساسي." if _arabic(question) else
                           "AI is not available right now (%s) - this is the basic-mode answer.") % err
    else:
        res = basic_answer(conn, question, user, check_auth)
    ms = int((time.time() - t0) * 1000)
    with transaction(conn):
        conn.execute("INSERT INTO ai_log (usnam,ts,question,answer,tools,mode,ms,error) VALUES (?,?,?,?,?,?,?,?)",
                     (user, now_ts(), question, res["answer"][:8000], json.dumps(res.get("tools") or [], ensure_ascii=False),
                      mode, ms, err))
    res.update(mode=mode, ms=ms)
    return res


def log(conn, limit=50):
    return [dict(r, tools=json.loads(r["tools"] or "[]")) for r in
            conn.execute("SELECT * FROM ai_log ORDER BY id DESC LIMIT ?", (int(limit),))]
