/* NERP - What-If simulator (ZWHATIF, "ماذا لو"): move prices, volumes, costs, the dollar, salaries,
   staff, payment terms, interest or an investment and see the year's profit, margin, break-even and
   cash change at once - on the company's own figures. Arabic / English. */
"use strict";
(() => {
const { h, api, run, msg, register, go, toolbar, ask } = App;
const CSS = `.wi{direction:rtl;font-family:Cairo,"Segoe UI",Tahoma,sans-serif;max-width:1500px}.wi.en{direction:ltr;font-family:Inter,"Segoe UI",Tahoma,sans-serif}
.wi-head{display:flex;flex-wrap:wrap;align-items:center;gap:14px;background:linear-gradient(120deg,#3b1f6e,#1f5fae);color:#fff;border-radius:16px;padding:16px 22px;margin-bottom:14px}
.wi-head h2{margin:0;font-size:24px}.wi-head p{margin:2px 0 0;opacity:.85;font-size:14px}.wi-head .sp{flex:1}
.wi-lang{display:inline-flex;border:1px solid rgba(255,255,255,.5);border-radius:999px;overflow:hidden}.wi-lang button{border:0;background:transparent;color:#fff;padding:6px 16px;font-weight:700;cursor:pointer}
.wi-lang button.on{background:#fff;color:#1f5fae}
.wi-body{display:grid;grid-template-columns:minmax(300px,390px) 1fr;gap:14px}@media(max-width:980px){.wi-body{grid-template-columns:1fr}}
.wi-card{background:#fff;border:1px solid #e1e7f0;border-radius:16px;padding:14px 16px;box-shadow:0 2px 8px rgba(11,42,85,.05)}
.wi-card h3{margin:0 0 10px;font-size:16px;color:#0b2a55}
.wi-grp{margin-bottom:12px}.wi-grp b{display:block;color:#5d6b7c;font-size:12.5px;margin:6px 0}
.wi-lv{display:grid;grid-template-columns:1fr 82px;gap:2px 10px;align-items:center;margin-bottom:8px}
.wi-lv label{font-size:14px;color:#1d2a3a;font-weight:600}.wi-lv .v{font-weight:800;color:#1f5fae;text-align:end;font-size:14px}
.wi-lv input[type=range]{grid-column:1/-1;width:100%;accent-color:#1f5fae}.wi-lv input[type=number]{grid-column:1/-1;width:100%;padding:6px 8px;border:1px solid #c9d6e8;border-radius:8px}
.wi-lv.chg label{color:#1f5fae}
.wi-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.wi-chips button{border:1px solid #c9d6e8;background:#f3f6fb;border-radius:999px;padding:5px 11px;cursor:pointer;font-size:13px;color:#0b2a55}
.wi-chips button:hover{background:#e4efff}
.wi-kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:12px}
.wi-k{background:#f7f9fc;border-radius:12px;padding:10px 12px}.wi-k .l{font-size:12.5px;color:#5d6b7c}.wi-k .n{font-size:24px;font-weight:800;color:#0b2a55;line-height:1.2}
.wi-k .o{font-size:12.5px;color:#7a889c}.wi-k .d{font-size:13px;font-weight:700}.pos{color:#11713e}.neg{color:#b3261e}
.wi-op{background:#eef4ff;border-radius:12px;padding:12px 14px;font-size:15.5px;line-height:1.8;color:#0b2a55;margin-bottom:12px}
.wi-tbl{width:100%;border-collapse:collapse;font-size:14px}.wi-tbl th,.wi-tbl td{padding:7px 8px;border-bottom:1px solid #eef1f6;text-align:start}
.wi-tbl td.num,.wi-tbl th.num{text-align:end;font-variant-numeric:tabular-nums}.wi-tbl tr.tot td{font-weight:800;border-top:2px solid #c9d6e8}
.wi-bar{display:grid;grid-template-columns:1fr auto;gap:3px 8px;align-items:center;margin:8px 0;font-size:13.5px}.wi-bar .tr{grid-column:1/-1}
.wi-bar .tr{display:block;height:14px;background:#f0f3f8;border-radius:7px;position:relative}.wi-bar .fl{position:absolute;top:0;height:14px;border-radius:7px}
.wi-goal{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.wi-goal input,.wi-goal select{padding:6px 8px;border:1px solid #c9d6e8;border-radius:8px}
.wi-btn{border:1px solid #1f5fae;color:#1f5fae;background:#fff;border-radius:9px;padding:6px 14px;cursor:pointer;font-weight:700}
.wi-btn.p{background:#1f5fae;color:#fff}.wi-note{color:#6b7a8c;font-size:12.5px;margin-top:8px;line-height:1.6}
.wi-two{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:1200px){.wi-two{grid-template-columns:1fr}}`;
const TX = {
  ar: { title: "🔮 ماذا لو؟", sub: "حرّك أي مؤشر وشوف حالاً يحصل إيه في ربح السنة والفلوس - على أرقام شركتك الحقيقية",
    sell: "البيع", cost: "التكاليف", people: "الناس", money: "الفلوس والبنك", inv: "استثمار جديد", quick: "سيناريوهات جاهزة",
    reset: "رجّع كله زي ما هو", result: "ربح / خسارة السنة", margin: "هامش الربح", revenue: "المبيعات", be: "نقطة التعادل", cash: "كاش السنة (تقريبي)",
    now: "دلوقتي", none: "مفيش", pl: "قائمة الدخل للسنة", line: "البند", today: "الحالي", after: "بعد التغيير", diff: "الفرق",
    lines: { revenue: "المبيعات", material: "الخامات وتكلفة البضاعة", personnel: "المرتبات", other: "مصاريف التشغيل", depreciation: "الإهلاك", financial: "فوائد وفروق عملة" },
    total: "صافي الربح / الخسارة", tornado: "مين بيأثر أكتر؟", goal: "عايز توصل لربح كام؟", goalBtn: "احسب", by: "بتغيير",
    save: "احفظ السيناريو", saved: "السيناريوهات المحفوظة", cmp: "قارن", del: "امسح", name: "اسم السيناريو", best: "الأفضل",
    basis: (b) => `الأساس: أرقام ${b.period} من الحسابات${b.annualised ? ` (${b.months} شهور محسوبة على سنة كاملة)` : ""} · الخامات المستوردة ${b.imported_pct}% · صادرات ${b.export_share}% · قروض ${fmt(b.loans)} جنيه`,
    egp: "جنيه", ppl: "موظف", days: "يوم", yrs: "سنة", pp: "نقطة" },
  en: { title: "🔮 What if?", sub: "Move any lever and see at once what happens to the year's profit and cash - on your company's real figures",
    sell: "Sales", cost: "Costs", people: "People", money: "Cash and bank", inv: "New investment", quick: "Ready scenarios",
    reset: "Reset everything", result: "Profit / loss of the year", margin: "Profit margin", revenue: "Sales", be: "Break-even", cash: "Cash of the year (approx.)",
    now: "now", none: "none", pl: "Income statement for the year", line: "Line", today: "Today", after: "After the change", diff: "Difference",
    lines: { revenue: "Sales", material: "Material and cost of goods", personnel: "Salaries", other: "Operating expenses", depreciation: "Depreciation", financial: "Interest and FX" },
    total: "Net profit / loss", tornado: "What moves the result most?", goal: "Which profit do you want?", goalBtn: "Calculate", by: "by changing",
    save: "Save scenario", saved: "Saved scenarios", cmp: "Compare", del: "Delete", name: "Scenario name", best: "Best",
    basis: (b) => `Basis: figures ${b.period} from the books${b.annualised ? ` (${b.months} months scaled to a full year)` : ""} · imported material ${b.imported_pct}% · exports ${b.export_share}% · loans EGP ${fmt(b.loans)}`,
    egp: "EGP", ppl: "people", days: "days", yrs: "years", pp: "pp" } };
const GROUPS = [["sell", ["price", "volume", "fx"]], ["cost", ["material", "imported_pct", "other"]], ["people", ["salaries", "staff"]],
  ["money", ["dso", "dpo", "rate"]], ["inv", ["capex", "capex_years", "capex_volume"]]];
const STEP = { staff: 1, dso: 1, dpo: 1, rate: 0.5, capex_years: 1 };
const fmt = v => v === null || v === undefined ? "-" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
const getLang = () => { try { return localStorage.getItem("wi_lang") || "ar"; } catch (e) { return "ar"; } };
register("ZWHATIF", { title: "What-If Simulator", async render(app) {
  if (!document.getElementById("wi-css")) document.head.append(h("style#wi-css", { html: CSS }));
  let lang = getLang(), P = {}, timer = null, last = null, cmpIds = [];
  const root = h("div.wi"); app.append(root);
  const levers = h("div"), results = h("div"), savedBox = h("div");
  const bAr = h("button", { type: "button" }, "عربي"), bEn = h("button", { type: "button" }, "English");
  const setLang = l => { lang = l; try { localStorage.setItem("wi_lang", l); } catch (e) { /* private */ } build(); };
  bAr.addEventListener("click", () => setLang("ar")); bEn.addEventListener("click", () => setLang("en"));
  const q = () => `p=${encodeURIComponent(JSON.stringify(P))}&lang=${lang}`;
  const schedule = () => { clearTimeout(timer); timer = setTimeout(sim, 180); };
  async function sim() {
    const d = await run(() => api("/api/whatif/sim?" + q())); if (!d) return;
    last = d; drawResults(d);
  }
  function lever(k, L, b) {
    const T = TX[lang], unit = { "%": "%", people: " " + T.ppl, days: " " + T.days, years: " " + T.yrs, EGP: " " + T.egp, pp: " " + T.pp }[L.unit] || "";
    const base = k === "dso" ? b.dso : k === "dpo" ? b.dpo : k === "imported_pct" ? b.imported_pct : L.default;
    const cur = P[k] !== undefined ? P[k] : base;
    const v = h("span.v"), row = h("div.wi-lv" + (P[k] !== undefined ? ".chg" : ""));
    const show = x => { v.textContent = (k === "capex" ? fmt(x) : (L.unit === "%" || k === "rate") && k !== "imported_pct" && x > 0 ? "+" + x : String(x)) + unit; };
    let input;
    if (k === "capex") input = h("input", { type: "number", min: 0, step: 100000, value: cur });
    else input = h("input", { type: "range", min: k === "staff" ? -b.staff : L.min, max: k === "dso" || k === "dpo" ? 180 : L.max, step: STEP[k] || 1, value: cur });
    input.addEventListener("input", () => { const x = Number(input.value); if (x === base) delete P[k]; else P[k] = x;
      row.classList.toggle("chg", P[k] !== undefined); show(x); schedule(); });
    show(cur);
    row.append(h("label", null, L.name), v, input);
    return row;
  }
  function drawLevers(d) {
    const T = TX[lang], b = d.baseline;
    levers.innerHTML = "";
    const chips = h("div.wi-chips");
    api("/api/whatif/scenarios?lang=" + lang).then(r => { for (const p of r.presets) { const c = h("button", { type: "button" }, p.name);
      c.addEventListener("click", () => { P = Object.assign({}, p.params); drawLevers(last); sim(); }); chips.append(c); } drawSaved(r); }).catch(() => {});
    levers.append(h("div.wi-card", null, h("h3", null, "⚡ " + T.quick), chips,
      ...GROUPS.map(([g, ks]) => h("div.wi-grp", null, h("b", null, T[g]), ...ks.map(k => lever(k, d.levers[k], b)))),
      h("button.wi-btn", { type: "button", on: { click: () => { P = {}; drawLevers(last); sim(); } } }, "↺ " + T.reset)));
  }
  function kpi(label, base, now, better) {
    const T = TX[lang], d = (now ?? 0) - (base ?? 0), good = better ? d >= 0 : d <= 0;
    return h("div.wi-k", null, h("div.l", null, label), h("div.n" + ((now ?? 0) < 0 && better ? ".neg" : ""), null, now === null ? T.none : fmt(now)),
      h("div.o", null, `${T.now}: ${base === null ? T.none : fmt(base)}`), Math.abs(d) >= 1 ? h("div.d." + (good ? "pos" : "neg"), null, (d > 0 ? "▲ +" : "▼ ") + fmt(d)) : null);
  }
  function drawResults(d) {
    const T = TX[lang], b = d.base, s = d.sim;
    const max = Math.max(1, ...d.impact.map(x => Math.abs(x.effect)));
    results.innerHTML = "";
    const tgt = h("input", { type: "number", step: 100000, value: Math.round(Math.max(0, b.result)) || 0 }), lv = h("select", null,
      ...["price", "volume", "material", "salaries", "other"].map(k => h("option", { value: k }, d.levers[k].name))), out = h("div.wi-note");
    const goalBtn = h("button.wi-btn.p", { type: "button" }, T.goalBtn);
    goalBtn.addEventListener("click", async () => { const r = await run(() => api(`/api/whatif/goal?target=${tgt.value}&lever=${lv.value}&` + q())); if (!r) return;
      out.innerHTML = ""; out.append(h("b", null, r.text), " ");
      if (r.possible) out.append(h("button.wi-btn", { type: "button", on: { click: () => { P[r.lever] = Math.round(r.value * 10) / 10; drawLevers(last); sim(); } } }, "✓ " + T.goalBtn)); });
    results.append(
      h("div.wi-kpis", null, kpi(T.result, b.result, s.result, true), kpi(T.margin + " %", b.margin, s.margin, true), kpi(T.revenue, b.pl.revenue, s.pl.revenue, true),
        kpi(T.be, b.breakeven, s.breakeven, false), kpi(T.cash, b.cash_year, s.cash_year, true)),
      h("div.wi-op", null, "💡 " + d.opinion),
      h("div.wi-two", null,
        h("div.wi-card", null, h("h3", null, "📊 " + T.pl), h("table.wi-tbl", null,
          h("thead", null, h("tr", null, h("th", null, T.line), h("th.num", null, T.today), h("th.num", null, T.after), h("th.num", null, T.diff))),
          h("tbody", null, ...Object.keys(T.lines).map(k => { const df = s.pl[k] - b.pl[k];
            return h("tr", null, h("td", null, T.lines[k]), h("td.num", null, fmt(b.pl[k])), h("td.num", null, fmt(s.pl[k])),
              h("td.num." + (df >= 0 ? "pos" : "neg"), null, Math.abs(df) >= 1 ? (df > 0 ? "+" : "") + fmt(df) : "")); }),
            h("tr.tot", null, h("td", null, T.total), h("td.num", null, fmt(b.result)), h("td.num" + (s.result < 0 ? ".neg" : ".pos"), null, fmt(s.result)),
              h("td.num." + (d.diff >= 0 ? "pos" : "neg"), null, Math.abs(d.diff) >= 1 ? (d.diff > 0 ? "+" : "") + fmt(d.diff) : ""))))),
        h("div", null,
          h("div.wi-card", { style: { marginBottom: "14px" } }, h("h3", null, "🌪️ " + T.tornado), ...(d.impact.length ? d.impact.map(x => {
            const w = 50 * Math.abs(x.effect) / max, pos = x.effect >= 0;
            const fill = h("span.fl", { style: { width: w + "%", background: pos ? "#1a9a55" : "#d0342c", [lang === "en" ? (pos ? "left" : "right") : (pos ? "right" : "left")]: "50%" } });
            return h("div.wi-bar", null, h("span", null, x.name), h("b." + (pos ? "pos" : "neg"), null, (pos ? "+" : "") + fmt(x.effect)), h("span.tr", null, fill)); })
            : [h("div.wi-note", null, "-")])),
          h("div.wi-card", null, h("h3", null, "🎯 " + T.goal), h("div.wi-goal", null, tgt, h("span", null, T.egp + " " + T.by), lv, goalBtn), out))),
      h("div.wi-note", null, T.basis(d.baseline)));
  }
  function drawSaved(r) {
    const T = TX[lang];
    savedBox.innerHTML = "";
    const cmpBtn = h("button.wi-btn", { type: "button" }, "⚖️ " + T.cmp);
    const cmpOut = h("div");
    cmpBtn.addEventListener("click", async () => { if (!cmpIds.length) return; const x = await run(() => api(`/api/whatif/scenarios?lang=${lang}&ids=${cmpIds.join(",")}`)); if (!x || !x.compare) return;
      const c = x.compare; cmpOut.innerHTML = "";
      cmpOut.append(h("table.wi-tbl", null, h("thead", null, h("tr", null, h("th", null, ""), ...c.columns.map(k => h("th.num", null, k.name + (k.name === c.best ? " ⭐" : ""))))),
        h("tbody", null, ...[["result", T.result], ["margin", T.margin + " %"], ["revenue", T.revenue], ["breakeven", T.be], ["cash", T.cash]].map(([key, lab]) =>
          h("tr", null, h("td", null, lab), ...c.columns.map(k => h("td.num", null, fmt(k[key])))))))); });
    savedBox.append(h("div.wi-card", { style: { marginTop: "14px" } }, h("h3", null, "💾 " + T.saved),
      h("button.wi-btn.p", { type: "button", on: { click: async () => { const x = await ask(T.save, [{ name: "name", label: T.name, value: "" }]); if (!x) return;
        const s = await run(() => api("/api/whatif/save", { name: x.name, params: P })); if (s) { msg("S", s.message); drawLevers(last); } } } }, "💾 " + T.save), " ", cmpBtn,
      h("table.wi-tbl", null, h("tbody", null, ...r.rows.map(s => { const cb = h("input", { type: "checkbox", checked: cmpIds.includes(s.id) });
        cb.addEventListener("change", () => { cmpIds = cb.checked ? cmpIds.concat(s.id) : cmpIds.filter(i => i !== s.id); });
        return h("tr", null, h("td", null, cb), h("td", null, h("a", { href: "#", on: { click: e => { e.preventDefault(); P = Object.assign({}, s.params);
          Object.keys(P).forEach(k => { if (P[k] === null || P[k] === (last.levers[k] || {}).default) delete P[k]; }); drawLevers(last); sim(); } } }, s.name)),
          h("td", null, s.usnam || ""), h("td", null, (s.ts || "").slice(0, 16)),
          h("td", null, h("button.wi-btn", { type: "button", on: { click: async () => { const x = await run(() => api("/api/whatif/delete", { id: s.id })); if (x) { msg("S", x.message); drawLevers(last); } } } }, T.del))); }))),
      cmpOut));
  }
  async function build() {
    const T = TX[lang];
    bAr.classList.toggle("on", lang === "ar"); bEn.classList.toggle("on", lang === "en");
    root.className = "wi" + (lang === "en" ? " en" : "");
    root.innerHTML = "";
    root.append(h("div.wi-head", null, h("div", null, h("h2", null, T.title), h("p", null, T.sub)), h("span.sp"), h("div.wi-lang", null, bAr, bEn)),
      h("div.wi-body", null, h("div", null, levers, savedBox), results));
    const d = await run(() => api("/api/whatif/sim?" + q())); if (!d) return;
    last = d; drawLevers(d); drawResults(d);
  }
  toolbar([{ label: "Reset", onClick: () => { P = {}; build(); } }, { label: "Daily Review", onClick: () => go("ZDAY") }]);
  build();
} });
})();
