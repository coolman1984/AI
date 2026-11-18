/* NERP - Ask NERP (ZAI): ask questions about the company's data in Arabic or English.
   AI mode: Claude chooses read-only tools that NERP runs locally with the user's authorizations.
   Basic mode (no key / no internet): keywords pick the tool and a fixed template answers.
   ZAI_CONF: API key, model, effort; the question log. */
"use strict";
(() => {
const { h, api, msg, run, field, inp, sel, alv, register, go, toolbar } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const CSS = `
.ai{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.ai-head{display:flex;align-items:center;gap:12px;background:linear-gradient(90deg,#0f4a8c,#0a2a55);color:#fff;border-radius:12px;padding:14px 18px}
.ai-head .t{font-size:22px;font-weight:800;flex:1}.ai-head .s{font-size:13px;opacity:.85}
.ai-mode{padding:5px 12px;border-radius:999px;font-weight:700;font-size:12px;background:#2ee59d;color:#06301d}.ai-mode.basic{background:#ffc94d;color:#3a2a00}
.ai-log{background:#f6f8fb;border:1px solid #dde4ee;border-radius:12px;padding:14px;min-height:340px;max-height:58vh;overflow:auto;display:flex;flex-direction:column;gap:12px}
.ai-msg{max-width:85%;padding:11px 15px;border-radius:14px;line-height:1.65;font-size:15px;white-space:normal;unicode-bidi:plaintext}
.ai-msg.q{align-self:flex-end;background:#0b5cad;color:#fff;border-bottom-right-radius:4px}
.ai-msg.a{align-self:flex-start;background:#fff;border:1px solid #dde4ee;border-bottom-left-radius:4px;box-shadow:0 2px 6px rgba(0,0,0,.04)}
.ai-msg.a ul{margin:6px 0;padding-inline-start:20px}.ai-msg .meta{margin-top:8px;font-size:12px;color:#6b7a8c;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ai-chip{background:#eef3fb;border:1px solid #cbd8ec;color:#0b4f96;border-radius:999px;padding:3px 10px;font-size:12px;cursor:pointer}
.ai-chip.deny{background:#fdecee;border-color:#f3b9c1;color:#a3182c;cursor:default}
.ai-note{background:#fff7e0;border:1px solid #f2d27a;border-radius:8px;padding:6px 10px;font-size:13px;margin-top:6px}
.ai-sug{display:flex;flex-wrap:wrap;gap:8px}
.ai-sug button{background:#fff;border:1px solid #cbd8ec;border-radius:999px;padding:7px 14px;cursor:pointer;font-size:14px;color:#123}
.ai-sug button:hover{background:#eef3fb}
.ai-in{display:flex;gap:8px}.ai-in textarea{flex:1;min-height:52px;max-height:160px;padding:10px 12px;border-radius:10px;border:1px solid #b9c6d8;font-size:15px;font-family:inherit;resize:vertical;unicode-bidi:plaintext}
.ai-in button{min-width:110px;border-radius:10px;border:0;background:#0b5cad;color:#fff;font-weight:700;font-size:15px;cursor:pointer}
.ai-in button:disabled{background:#8aa4c4;cursor:wait}
.ai-typing{align-self:flex-start;color:#6b7a8c;font-style:italic}`;
const style = () => { if (!document.getElementById("ai-css")) { const s = document.createElement("style"); s.id = "ai-css"; s.textContent = CSS; document.head.append(s); } };
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function md(text) {           // tiny, safe markdown: **bold**, bullet lines, line breaks
  const lines = esc(text).split(/\n/); let html = "", list = false;
  for (const l of lines) {
    const b = l.match(/^\s*[-•*]\s+(.*)$/);
    if (b) { if (!list) { html += "<ul>"; list = true; } html += `<li>${b[1]}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    html += l.trim() ? `<div>${l}</div>` : "<div style='height:6px'></div>";
  }
  if (list) html += "</ul>";
  return html.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
}
const SUG = ["بعنا كام الشهر ده؟", "مين العملاء اللي عليهم فلوس متأخرة؟", "إيه حالة الإنتاج النهارده؟", "عندنا كام زجاج في المخزن؟",
  "إيه أخبار الجودة والموردين؟", "الماكينات عاملة إيه؟", "إيه الإقرارات الضريبية المطلوبة قريب؟", "لخّصلي اجتماع الإنتاج النهارده",
  "What were our sales and margin this month?"];

register("ZAI", { title: "Ask NERP (AI assistant)", async render(app) {
  style();
  const st = await run(() => api("/api/ai/status")) || { mode: "basic" };
  const mode = h("span.ai-mode" + (st.mode === "ai" ? "" : ".basic"), null, st.mode === "ai" ? "AI · " + st.model : "Basic mode (no AI key)");
  const log = h("div.ai-log"), box = h("textarea", { placeholder: "اكتب سؤالك هنا… مثلاً: بعنا كام الشهر ده؟  /  Ask about sales, stock, production…", dir: "auto" });
  const send = h("button", { type: "button" }, "اسأل ▶");
  const history = [];
  const add = (cls, node) => { log.append(node); log.scrollTop = log.scrollHeight; return node; };
  add("a", h("div.ai-msg.a", { dir: "auto" }, h("div", { html: md("أهلاً! أنا **مساعد NERP**. اسألني عن المبيعات، العملاء، المخزون، الإنتاج، الجودة، الصيانة، الضرايب أو الموظفين — وأنا أرد من أرقام البرنامج الحقيقية.") })));
  const ask = async text => {
    text = (text || box.value).trim(); if (!text) return;
    box.value = ""; send.disabled = true;
    add("q", h("div.ai-msg.q", { dir: "auto" }, text));
    const typing = add("t", h("div.ai-typing", null, "بيدوّر في البيانات…"));
    const r = await run(() => api("/api/ai/ask", { question: text, history: history.slice(-6) }));
    typing.remove(); send.disabled = false; box.focus();
    if (!r) return;
    history.push({ q: text, a: r.answer });
    const meta = h("div.meta", null, h("span", null, r.mode === "ai" ? "🤖 AI" : "⚙ basic"), h("span", null, `${(r.ms / 1000).toFixed(1)} s`),
      ...(r.tools || []).map(t => t.denied ? h("span.ai-chip.deny", null, `🔒 ${t.tool}`)
        : h("span.ai-chip", { title: "Open the screen", on: { click: () => t.screen && go(t.screen) } }, `📊 ${t.screen || t.tool}`)));
    add("a", h("div.ai-msg.a", { dir: "auto" }, h("div", { html: md(r.answer) }), r.note ? h("div.ai-note", null, r.note) : null, meta));
  };
  send.addEventListener("click", () => ask());
  box.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
  app.append(h("div.ai", null,
    h("div.ai-head", null, h("div", { style: { flex: 1 } }, h("div.t", null, "اسأل NERP"), h("div.s", null, "Ask about your company's data · read-only · answers from the books")), mode),
    h("div.ai-sug", null, ...SUG.map(s => h("button", { type: "button", dir: "auto", on: { click: () => ask(s) } }, s))),
    log, h("div.ai-in", null, box, send),
    note(st.mode === "ai" ? "The assistant reads only what you are authorized to display. Only the figures needed for your question are sent to the AI service; nothing is changed in NERP."
      : "Basic mode: answers common questions without internet. An administrator can add an Anthropic API key in ZAI_CONF for full AI answers.")));
  toolbar([{ label: "Settings (ZAI_CONF)", onClick: () => go("ZAI_CONF") }]);
  box.focus();
} });

register("ZAI_CONF", { title: "Ask NERP - Settings and Log", async render(app) {
  const out = h("div");
  app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/ai/settings")); if (!d) return;
    out.innerHTML = "";
    const f = { key: inp({ type: "password", w: "l", ph: d.key_masked ? `saved: ${d.key_masked}` : "sk-ant-…" }), model: inp({ value: d.model, w: "m" }),
      effort: sel([["low", "low - fastest"], ["medium", "medium (recommended)"], ["high", "high - most thorough"]], d.effort),
      enabled: sel([["1", "On"], ["0", "Off (basic mode only)"]], d.enabled ? "1" : "0") };
    out.append(panel("AI service", grid(field("Anthropic API key", f.key), field("Model", f.model), field("Effort", f.effort), field("AI answers", f.enabled)),
      h("div", null, `Mode now: ${d.mode === "ai" ? "AI" : "basic"} · key ${d.key_masked || "not set"}${d.key_source === "environment" ? " (from ANTHROPIC_API_KEY)" : ""}`),
      note("Leave the key empty to keep the saved one; enter - (minus) to remove it. The environment variable ANTHROPIC_API_KEY takes priority. The key is stored in the NERP database of this computer - protect the database file like the books. Requests use the Claude model above; if the service declines a question, it is automatically retried on a fallback model.")),
      alv({ rows: d.tools, title: "What the assistant can read (read-only tools)", columns: [{ key: "name", label: "Tool" }, { key: "area", label: "Authorization area" }, { key: "description", label: "Reads" }] }),
      alv({ rows: d.log.map(r => Object.assign({}, r, { used: r.tools.map(t => t.tool).join(", ") })), title: "Last questions (audit log)", columns: [{ key: "ts", label: "Time" },
        { key: "usnam", label: "User" }, { key: "mode", label: "Mode" }, { key: "question", label: "Question" }, { key: "used", label: "Data used" }, { key: "ms", label: "ms", type: "int" }, { key: "error", label: "Error" }] }));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/ai/settings", { api_key: f.key.value, model: f.model.value, effort: f.effort.value, enabled: f.enabled.value === "1" }));
      if (r) { msg("S", r.message); load(); } } }, { label: "Ask NERP", onClick: () => go("ZAI") }]);
  };
  load();
} });
})();

/* ===================================================================== NERP Copilot
   A floating assistant on every screen: round button at the bottom right opens a chat window
   with a greeting and four services - ask about the data (agent), find a screen (local search
   over the menu), today's briefing and help for the screen that is open. */
(() => {
const { h, api, go, S } = App;
const ICON = `<svg viewBox="0 0 64 64" width="100%" height="100%" aria-hidden="true"><defs><linearGradient id="cpg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#4cc3ff"/><stop offset="1" stop-color="#0b5cad"/></linearGradient></defs>
<circle cx="32" cy="32" r="30" fill="url(#cpg)"/><rect x="15" y="20" width="34" height="24" rx="9" fill="#fff"/>
<circle cx="25" cy="32" r="3.6" fill="#0b5cad"/><circle cx="39" cy="32" r="3.6" fill="#0b5cad"/><path d="M26 39q6 4 12 0" stroke="#0b5cad" stroke-width="2.4" fill="none" stroke-linecap="round"/>
<path d="M32 12v8" stroke="#fff" stroke-width="3" stroke-linecap="round"/><circle cx="32" cy="11" r="3.4" fill="#ffc94d"/>
<path d="M47 14l1.6 3.4 3.4 1.6-3.4 1.6L47 24l-1.6-3.4L42 19l3.4-1.6z" fill="#ffc94d"/></svg>`;
const CSS = `
.cp-fab{position:fixed;right:22px;bottom:44px;z-index:9000;display:flex;align-items:center;gap:10px;flex-direction:row-reverse}
.cp-btn{width:62px;height:62px;border-radius:50%;border:0;padding:0;cursor:pointer;background:transparent;box-shadow:0 10px 26px rgba(11,92,173,.45);
  transition:transform .15s;position:relative}
.cp-btn:hover{transform:scale(1.07)}
.cp-badge{position:absolute;top:-4px;right:-4px;min-width:20px;height:20px;padding:0 5px;border-radius:10px;background:#e5484d;color:#fff;font:700 12px/20px Arial,sans-serif;
  box-shadow:0 1px 4px rgba(0,0,0,.3);display:none}
.cp-tile.wide{grid-column:1/-1;display:flex;align-items:center;justify-content:center;gap:8px;padding:10px}.cp-tile.wide .e{display:inline;margin:0;font-size:20px}
.cp-btn .dot{position:absolute;right:3px;bottom:5px;width:13px;height:13px;border-radius:50%;background:#2ee59d;border:2px solid #fff}
.cp-tip{background:#0b2a55;color:#fff;font:600 13px Inter,"Segoe UI",Arial,sans-serif;padding:7px 12px;border-radius:999px;box-shadow:0 4px 14px rgba(0,0,0,.2);opacity:0;
  transform:translateX(8px);transition:.2s;pointer-events:none;white-space:nowrap}
.cp-fab:hover .cp-tip{opacity:1;transform:none}
.cp-hide{position:absolute;top:-6px;left:-6px;width:20px;height:20px;border-radius:50%;border:0;background:#fff;color:#557;font-size:13px;line-height:20px;
  box-shadow:0 1px 4px rgba(0,0,0,.25);cursor:pointer;display:none}
.cp-btn:hover .cp-hide{display:block}
.cp-win{position:fixed;right:22px;bottom:44px;z-index:9001;width:400px;max-width:calc(100vw - 32px);height:min(660px,calc(100vh - 110px));background:#fff;border-radius:16px;
  box-shadow:0 18px 50px rgba(10,30,60,.35);display:flex;flex-direction:column;overflow:hidden;font-family:Inter,"Segoe UI",Arial,sans-serif;
  animation:cpin .18s ease-out}
.cp-win.max{width:min(760px,calc(100vw - 32px));height:calc(100vh - 110px)}
@keyframes cpin{from{opacity:0;transform:translateY(16px) scale(.98)}to{opacity:1;transform:none}}
.cp-top{display:flex;align-items:center;gap:6px;padding:8px 10px;background:linear-gradient(90deg,#0f4a8c,#0a2a55);color:#fff}
.cp-top .ic{width:34px;height:34px;flex:none}.cp-top .nm{flex:1;font-weight:800;font-size:16px;line-height:1.1}.cp-top .nm small{display:block;font-weight:500;font-size:11px;opacity:.8}
.cp-top button{background:transparent;border:0;color:#fff;font-size:17px;width:30px;height:30px;border-radius:8px;cursor:pointer}
.cp-top button:hover{background:rgba(255,255,255,.15)}
.cp-info{background:#eef3fb;color:#4a5b75;font-size:11.5px;padding:5px 12px;border-bottom:1px solid #dde4ee}
.cp-body{flex:1;overflow:auto;padding:12px;background:#f6f8fb;display:flex;flex-direction:column;gap:10px}
.cp-card{background:#fff;border:1px solid #e1e7f0;border-radius:14px;padding:14px;box-shadow:0 2px 6px rgba(0,0,0,.03)}
.cp-card h3{margin:0 0 4px;font-size:17px;color:#0b2a55}.cp-card p{margin:0 0 10px;color:#46566e;font-size:13.5px;line-height:1.55}
.cp-tiles{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.cp-tile{background:#f3f6fb;border:1px solid #e1e7f0;border-radius:12px;padding:12px 8px;cursor:pointer;text-align:center;color:#0b2a55;font-weight:700;font-size:13.5px;line-height:1.3}
.cp-tile:hover{background:#e7f0fc;border-color:#b9cdea}.cp-tile .e{font-size:26px;display:block;margin-bottom:6px}.cp-tile small{display:block;font-weight:500;color:#6b7a8c;font-size:11.5px;margin-top:3px}
.cp-m{max-width:88%;padding:9px 13px;border-radius:14px;font-size:14px;line-height:1.6;unicode-bidi:plaintext;word-wrap:break-word}
.cp-m.q{align-self:flex-end;background:#0b5cad;color:#fff;border-bottom-right-radius:4px}
.cp-m.a{align-self:flex-start;background:#fff;border:1px solid #e1e7f0;border-bottom-left-radius:4px}
.cp-m.a ul{margin:4px 0;padding-inline-start:18px}
.cp-t{font-size:10.5px;color:#8a97ab;margin-top:4px}
.cp-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.cp-chip{background:#eef3fb;border:1px solid #cbd8ec;color:#0b4f96;border-radius:999px;padding:4px 10px;font-size:12.5px;cursor:pointer}
.cp-chip:hover{background:#dfeafa}.cp-chip.deny{background:#fdecee;border-color:#f3b9c1;color:#a3182c}
.cp-res{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid #eef1f6}.cp-res:last-child{border:0}
.cp-res b{font-family:ui-monospace,Consolas,monospace;color:#0b5cad;font-size:12.5px;min-width:96px}.cp-res span{flex:1;font-size:13px;color:#2a3a52}
.cp-res button{border:1px solid #b9cdea;background:#fff;color:#0b5cad;border-radius:8px;padding:3px 10px;cursor:pointer;font-size:12px}
.cp-note{background:#fff7e0;border:1px solid #f2d27a;border-radius:8px;padding:5px 9px;font-size:12px;margin-top:6px}
.cp-typing{align-self:flex-start;color:#8a97ab;font-size:13px;font-style:italic}
.cp-foot{border-top:1px solid #e1e7f0;padding:8px 10px;background:#fff}
.cp-modes{display:flex;gap:6px;margin-bottom:6px}.cp-modes button{border:1px solid #cbd8ec;background:#fff;border-radius:999px;padding:3px 10px;font-size:12px;cursor:pointer;color:#46566e}
.cp-modes button.on{background:#0b5cad;color:#fff;border-color:#0b5cad}
.cp-in{display:flex;gap:6px;align-items:flex-end}
.cp-in textarea{flex:1;resize:none;height:44px;max-height:120px;border:1px solid #c3cfe0;border-radius:12px;padding:10px 12px;font:14px Inter,"Segoe UI",Arial,sans-serif;unicode-bidi:plaintext}
.cp-in button{width:44px;height:44px;border-radius:12px;border:0;background:#0b5cad;color:#fff;font-size:18px;cursor:pointer}.cp-in button:disabled{background:#8aa4c4}
@media print{.cp-fab,.cp-win{display:none!important}}`;
const AR = { "أمر شراء": "purchase order", "شراء": "purchase", "مشتريات": "purchas", "فاتور": "billing invoice", "مخزون": "stock", "مخزن": "stock warehouse",
  "جرد": "physical inventory", "استلام": "goods receipt", "صرف": "goods issue", "عميل": "customer", "عملاء": "customer", "مورد": "vendor",
  "أمر بيع": "sales order", "مبيعات": "sales", "تسليم": "delivery", "شحن": "delivery shipping", "إنتاج": "production", "انتاج": "production",
  "تأكيد": "confirmation", "قائمة مواد": "bill of material bom", "ماكين": "machine maintenance", "صيان": "maintenance", "عطل": "breakdown",
  "جود": "quality inspection", "فحص": "inspection", "شكو": "notification complaint", "ضريب": "tax", "ضرايب": "tax", "قيمة مضافة": "vat",
  "خصم وإضافة": "withholding", "مرتب": "payroll", "موظف": "employee", "إجاز": "leave", "سلف": "loan", "ميزاني": "balance sheet",
  "قيد": "journal entry posting", "شيك": "cheque", "خزن": "cash", "بنك": "bank", "أصول": "asset", "تكلف": "cost", "ربحي": "profitability",
  "تقارير": "report bi", "تقرير": "report", "مستخدم": "user", "صلاحي": "role authorization", "إكسيل": "excel import", "لوحة": "board" };
const HINT = { "استلام": ["MIGO", "MB03"], "بضاع": ["MIGO"], "أمر شراء": ["ME21N"], "طلب شراء": ["ME51N"], "قيمة مضافة": ["ZTAX_VAT"], "القيمة المضافة": ["ZTAX_VAT"],
  "إقرار": ["ZTAX_VAT", "ZTAX_41", "ZTAX_SAL"], "اقرار": ["ZTAX_VAT", "ZTAX_41", "ZTAX_SAL"], "خصم وإضافة": ["ZTAX_41"], "جرد": ["MI01", "MI04", "MI07"],
  "فاتورة إلكترونية": ["ZTAX_EINV"], "فاتورة": ["VF01", "VF03"], "أمر بيع": ["VA01", "VA05"], "عرض سعر": ["VA21"], "مرتب": ["PC00_M99_CALC"],
  "موظف جديد": ["PA40"], "قيد": ["FB50", "F-02"], "شيك": ["ZCHQ_IN", "ZCHQ_OUT"], "عطل": ["ZPM_NOTIF"], "صيان": ["ZPM_COCKPIT", "ZPM_ORDERS"],
  "فحص": ["QA32", "QA11"], "جود": ["ZQM_COCKPIT"], "مخزون": ["MMBE", "MB52"], "رصيد": ["MMBE"], "إنتاج": ["ZPP_BOARD", "CO01"], "انتاج": ["ZPP_BOARD", "CO01"],
  "ميزانية": ["S_ALR_87012284"], "تقارير": ["ZBI"], "مستخدم": ["SU01"], "صلاحي": ["PFCG"], "إكسيل": ["ZIMPORT"], "اسأل": ["ZAI"] };
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const md = text => { let html = "", list = false;
  for (const l of esc(text).split(/\n/)) { const b = l.match(/^\s*[-•*]\s+(.*)$/);
    if (b) { if (!list) { html += "<ul>"; list = true; } html += `<li>${b[1]}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; } html += l.trim() ? `<div>${l}</div>` : "<div style='height:5px'></div>"; }
  return (list ? html + "</ul>" : html).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); };
const now = () => new Date().toTimeString().slice(0, 5);
const cur = () => (location.hash.match(/^#\/([^?]+)/) || [])[1] || "";
const store = { get(k, d) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } } };

function menuPaths() {           // tcode -> "Top › Group"
  const out = {};
  const walk = (node, path) => { if (typeof node === "string") { if (!out[node]) out[node] = path.join(" › "); return; }
    const [name, kids] = node; (kids || []).forEach(k => walk(k, path.concat(name))); };
  (App.MENU || []).forEach(m => walk(m, []));
  return out;
}
function searchScreens(q) {
  let words = q.toLowerCase();
  const phrases = [];
  for (const [a, e] of Object.entries(AR)) if (q.includes(a)) { words += " " + e; phrases.push(e); }
  if (/أعمل|اعمل|إنشاء|انشاء|جديد|create|new/i.test(q)) { words += " create"; phrases.push("create"); }
  const terms = words.split(/[^a-z0-9_\-\u0600-\u06ff]+/).filter(w => w.length > 1);
  const paths = menuPaths(), res = [];
  for (const [code, sc] of Object.entries(S.screens)) {
    if (code === "HOME" || !App.allowed(code)) continue;
    const title = (sc.title || "").toLowerCase(), path = (paths[code] || "").toLowerCase();
    let score = 0;
    for (const t of terms) {
      if (code.toLowerCase() === t) score += 12;
      else if (title.includes(t)) score += t.length > 3 ? 3 : 1;
      else if (path.includes(t)) score += 1;
    }
    for (const ph of phrases) if (ph.includes(" ") && title.includes(ph)) score += 8;
    for (const [a, codes] of Object.entries(HINT)) if (q.includes(a) && codes.includes(code)) score += 15 - codes.indexOf(code);
    if (phrases.includes("create") && /^(create|new)\b/.test(title)) score += 4;
    if (score) res.push({ code, title: sc.title || code, path: paths[code] || "", score });
  }
  return res.sort((a, b) => b.score - a.score || a.code.localeCompare(b.code)).slice(0, 7);
}
const RELATED = [[/^(V|ZSD|KE|VK|VF)/, ["بعنا كام الشهر ده؟", "مين العملاء اللي عليهم فلوس متأخرة؟"]], [/^(ME|ZPUR|ML)/, ["إيه أخبار المشتريات والموردين المتأخرين؟"]],
  [/^(M[BIM]|ZMM|MIGO|LT)/, ["عندنا كام زجاج في المخزن؟"]], [/^(CO|ZPP|MD|CS|CR)/, ["إيه حالة الإنتاج النهارده؟", "لخّصلي اجتماع الإنتاج النهارده"]],
  [/^(Q|ZQM)/, ["إيه أخبار الجودة والموردين؟"]], [/^(ZPM|IW|IE|IP)/, ["الماكينات عاملة إيه؟"]], [/^(ZTAX|FB41|ZWHT)/, ["إيه الإقرارات الضريبية المطلوبة قريب؟"]],
  [/^(F|S_ALR|ZFI|ZCHQ)/, ["إيه وضع النقدية والربح الشهر ده؟"]], [/^(P[ACT]|ZHR|PPOM)/, ["عندنا كام موظف وتكلفة المرتبات كام؟"]]];

let win = null, fab = null, mode = "data", busy = false;
const hist = store.get("cp_hist", []);

function ensureStyle() { if (!document.getElementById("cp-css")) { const s = document.createElement("style"); s.id = "cp-css"; s.textContent = CSS; document.head.append(s); } }

function build() {
  ensureStyle();
  fab = h("div.cp-fab", null, h("button.cp-btn", { type: "button", title: "NERP Copilot", html: ICON + '<span class="dot"></span>' }),
    h("span.cp-tip", null, "NERP Copilot · اسأل"));
  const hide = h("button.cp-hide", { type: "button", title: "Hide until reload" }, "×");
  fab.querySelector(".cp-btn").append(hide, h("span.cp-badge"));
  hide.addEventListener("click", e => { e.stopPropagation(); fab.remove(); fab = null; });
  fab.querySelector(".cp-btn").addEventListener("click", open);
  document.body.append(fab);
}

async function open() {
  if (win) { win.style.display = ""; if (fab) fab.style.display = "none"; win.querySelector("textarea").focus(); return; }
  ensureStyle();
  const st = await api("/api/ai/status").catch(() => ({ mode: "basic" }));
  const name = (S.me && S.me.name) || S.user || "";
  const body = h("div.cp-body"), box = h("textarea", { dir: "auto", placeholder: "اكتب رسالتك… / Enter a message" });
  const send = h("button", { type: "button", title: "Send" }, "➤");
  const modeBtns = [["data", "📊 بيانات"], ["search", "🔎 شاشة"]].map(([k, t]) => {
    const b = h("button", { type: "button" }, t); b.addEventListener("click", () => setMode(k)); b.dataset.k = k; return b; });
  const setMode = k => { mode = k; modeBtns.forEach(b => b.classList.toggle("on", b.dataset.k === k));
    box.placeholder = k === "search" ? "اكتب اللي عايز تعمله… مثلاً: أعمل أمر شراء" : "اسأل عن بيانات الشركة… مثلاً: بعنا كام؟"; box.focus(); };
  const scroll = () => { body.scrollTop = body.scrollHeight; };
  const bubble = (cls, content, keep = true) => { const m = h("div.cp-m." + cls, { dir: "auto" }, content, h("div.cp-t", null, now())); body.append(m); scroll(); return m; };
  const welcome = () => {
    body.innerHTML = "";
    const tile = (e, t, s, fn) => { const x = h("div.cp-tile", null, h("span.e", null, e), t, h("small", null, s)); x.addEventListener("click", fn); return x; };
    body.append(h("div.cp-card", { dir: "auto" }, h("h3", null, `أهلاً يا ${name} 👋`),
      h("p", null, "أنا NERP Copilot. بساعدك تلاقي أي رقم أو شاشة في البرنامج بسرعة. اختار خدمة أو اكتب سؤالك تحت."),
      h("div.cp-tiles", null,
        tile("📊", "اسأل عن البيانات", "مبيعات، مخزون، إنتاج…", () => { setMode("data"); suggest(["بعنا كام الشهر ده؟", "مين العملاء اللي عليهم فلوس متأخرة؟", "عندنا كام زجاج في المخزن؟", "الماكينات عاملة إيه؟"]); }),
        tile("🔎", "دوّر على شاشة", "قولّي عايز تعمل إيه", () => { setMode("search"); bubble("a", h("div", { html: md("قولّي عايز تعمل إيه وأنا أوديك للشاشة. مثلاً: **أعمل أمر شراء**، **استلام بضاعة**، **إقرار القيمة المضافة**.") })); }),
        tile("📋", "ملخص اليوم", "أهم أرقام النهارده", () => askData("اديني ملخص اليوم: المبيعات والإنتاج والفلوس المتأخرة والجودة والصيانة")),
        tile("❓", "الشاشة اللي فاتحها", "شرح وأسئلة مرتبطة", screenHelp),
        (() => { const w = tile("🔔", "الملخص والتنبيهات على موبايلك", "", () => go("ZNOTIF")); w.classList.add("wide"); return w; })())));
    for (const m of hist.slice(-8)) restore(m);
  };
  const suggest = list => bubble("a", h("div", null, "جرّب تسأل:", h("div.cp-chips", null, ...list.map(s => { const c = h("span.cp-chip", { dir: "auto" }, s); c.addEventListener("click", () => askData(s)); return c; }))));
  const chipsFor = tools => (tools || []).map(t => { const c = h("span.cp-chip" + (t.denied ? ".deny" : ""), null, t.denied ? `🔒 ${t.tool}` : `📊 ${t.screen || t.tool}`);
    if (!t.denied && t.screen) c.addEventListener("click", () => go(t.screen)); return c; });
  const restore = m => { bubble("q", m.q); bubble("a", h("div", null, h("div", { html: md(m.a) }), h("div.cp-chips", null, ...chipsFor(m.tools)))); };
  async function askData(text) {
    if (busy) return; busy = true; send.disabled = true;
    bubble("q", text);
    const typing = h("div.cp-typing", null, "بيدوّر في البيانات…"); body.append(typing); scroll();
    let r = null;
    try { r = await api("/api/ai/ask", { question: text, history: hist.slice(-6).map(x => ({ q: x.q, a: x.a })) }); }
    catch (e) { r = { answer: "حصلت مشكلة: " + (e.message || e), tools: [] }; }
    typing.remove(); busy = false; send.disabled = false;
    hist.push({ q: text, a: r.answer, tools: (r.tools || []).map(t => ({ tool: t.tool, screen: t.screen, denied: t.denied })) });
    store.set("cp_hist", hist.slice(-20));
    bubble("a", h("div", null, h("div", { html: md(r.answer) }), r.note ? h("div.cp-note", null, r.note) : null, h("div.cp-chips", null, ...chipsFor(r.tools))));
  }
  function findScreen(text) {
    bubble("q", text);
    const res = searchScreens(text);
    bubble("a", res.length ? h("div", null, h("div", null, "الشاشات اللي ممكن تفيدك:"), ...res.map(x => h("div.cp-res", null, h("b", null, x.code),
      h("span", { title: x.path }, x.title), h("button", { type: "button", on: { click: () => go(x.code) } }, "افتح"))))
      : h("div", null, "مش لاقي شاشة مناسبة. جرّب كلمة تانية، أو اسألني عن البيانات."));
  }
  function screenHelp() {
    const code = cur(), sc = S.screens[code];
    if (!code || !sc || code === "HOME") return bubble("a", h("div", null, "إنت في الصفحة الرئيسية. افتح أي شاشة وأنا أقولك هي بتعمل إيه والشاشات اللي مرتبطة بيها."));
    const paths = menuPaths(), path = paths[code] || "";
    const sib = Object.entries(paths).filter(([c, p]) => p === path && c !== code && App.allowed(c)).slice(0, 6);
    const qs = (RELATED.find(([rx]) => rx.test(code)) || [null, []])[1];
    bubble("a", h("div", null, h("div", { html: md(`إنت فاتح **${code}** — ${esc(sc.title || "")}` + (path ? `\nمكانها في المنيو: ${esc(path)}` : "")) }),
      sib.length ? h("div", null, h("div", { style: { marginTop: "6px" } }, "شاشات مرتبطة:"), ...sib.map(([c]) => h("div.cp-res", null, h("b", null, c),
        h("span", null, (S.screens[c] || {}).title || c), h("button", { type: "button", on: { click: () => go(c) } }, "افتح")))) : null,
      qs.length ? h("div.cp-chips", null, ...qs.map(s => { const c = h("span.cp-chip", { dir: "auto" }, s); c.addEventListener("click", () => askData(s)); return c; })) : null));
  }
  const submit = () => { const t = box.value.trim(); if (!t || busy) return; box.value = ""; if (mode === "search") findScreen(t); else askData(t); };
  send.addEventListener("click", submit);
  box.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } });
  const btn = (t, title, fn) => { const b = h("button", { type: "button", title }, t); b.addEventListener("click", fn); return b; };
  win = h("div.cp-win", { role: "dialog", "aria-label": "NERP Copilot" },
    h("div.cp-top", null, h("span.ic", { html: ICON }), h("div.nm", null, "NERP Copilot", h("small", null, st.mode === "ai" ? "AI · " + st.model : "Basic mode")),
      btn("⌂", "Start", welcome), btn("⤢", "Bigger", () => win.classList.toggle("max")), btn("⧉", "Open full screen (ZAI)", () => { close(); go("ZAI"); }),
      btn("–", "Minimize", close), btn("×", "Close and clear", () => { hist.length = 0; store.set("cp_hist", []); close(); win.remove(); win = null; })),
    h("div.cp-info", null, `${st.mode === "ai" ? "🟢 متصل بالذكاء الاصطناعي" : "🟡 الوضع الأساسي - بدون إنترنت"} · ${new Date().toLocaleDateString("en-GB")} ${now()}`),
    body, h("div.cp-foot", null, h("div.cp-modes", null, ...modeBtns), h("div.cp-in", null, box, send)));
  document.body.append(win);
  if (fab) fab.style.display = "none";
  setMode("data"); welcome(); box.focus();
}
async function poll() {                // unread messages -> red counter on the button
  if (!fab || (S.auth && !S.me)) return;
  try { const d = await api("/api/notif/my"); const b = fab.querySelector(".cp-badge");
    if (b) { b.textContent = d.unseen > 9 ? "9+" : String(d.unseen || ""); b.style.display = d.unseen ? "block" : "none"; } } catch (e) { /* offline */ }
}
function close() { if (win) win.style.display = "none"; if (fab) fab.style.display = ""; }
function sync() {                      // hidden on the full-screen assistant and before logon
  const off = cur() === "ZAI" || (S.auth && !S.me);
  if (fab) fab.style.display = off || (win && win.style.display !== "none") ? "none" : "";
  if (off && win) win.style.display = "none";
}
const boot = () => { if (!document.getElementById("app") && !document.querySelector("#app-toolbar")) return; build(); sync();
  window.addEventListener("hashchange", sync); setInterval(sync, 1500); setTimeout(poll, 4000); setInterval(poll, 60000); };
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
App.copilot = { open, close, searchScreens };
})();
