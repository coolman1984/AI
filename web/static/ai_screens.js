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
