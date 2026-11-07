/* MM Core - Controlling (CO) screens */
"use strict";
(() => {
const { h, $, $$, api, msg, run, ask, confirmBox, field, inp, sel, val, up, alv, register,
  go, toolbar, fmtQty, fmtAmt, fmtDate, fmtShort, today, enc, S } = App;

// ------------------------------------------------------------------ helpers
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null,
  h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const out = () => h("div");
let CO = null;
async function meta(force) {
  if (!CO || force) {
    CO = await api("/api/co/meta");
    App.datalist("dl-kostl", CO.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
    App.datalist("dl-kstar", CO.cost_elements.map(k => [k.kstar, `${k.kstar} ${k.ktext} (${k.katyp})`]));
    App.datalist("dl-kstar1", CO.cost_elements.filter(k => k.katyp === 1).map(k => [k.kstar, `${k.kstar} ${k.ktext}`]));
    App.datalist("dl-lstar", CO.activity_types.map(a => [a.lstar, `${a.lstar} ${a.ktext}`]));
    App.datalist("dl-stagr", CO.skf.map(a => [a.stagr, `${a.stagr} ${a.ktext}`]));
    App.datalist("dl-aufnr", CO.orders.map(o => [o.aufnr, `${o.aufnr} ${o.ktext} (${o.stat})`]));
    App.datalist("dl-kunnr", CO.customers.map(c => [c.kunnr, `${c.kunnr} ${c.name}`]));
    App.datalist("dl-khinr", CO.groups.map(g => [g.khinr, `${g.khinr} ${g.ktext}`]));
    App.datalist("dl-hkont", Object.entries(CO.gl_accounts).map(([k, v]) => [k, `${k} ${v}`]));
  }
  return CO;
}
const ccName = k => (CO.cost_centers.find(c => c.kostl === k) || {}).name || "";
const ceText = k => (CO.cost_elements.find(c => c.kstar === k) || {}).ktext || "";
function periodFields(p) {
  const y = inp({ value: p.gjahr || CO.sample.gjahr, w: "s" });
  const m = inp({ value: p.perio || CO.sample.perio, w: "s" });
  return { y, m, fields: [field("Fiscal year", y, { req: true }), field("Period", m, { req: true, hint: "1-12" })] };
}
const ccIn = v => inp({ value: v || "", list: "dl-kostl", upper: true, w: "m" });
const sampleNote = () => h("div.note", { style: { marginBottom: "10px" } },
  `Sample month with a complete closing: period ${CO.sample.perio}/${CO.sample.gjahr}. Controlling area ${CO.kokrs} · company code ${CO.bukrs} · operating concern ${CO.erkrs}.`);
function msgLink(type, text, label, tcode, params) {
  msg(type, text);
  const a = h("a", { href: "#", style: { marginLeft: "10px" } }, label);
  a.addEventListener("click", e => { e.preventDefault(); go(tcode, params); });
  $("#status-msg").append(a);
}
const neg = v => (typeof v === "number" && v < 0) ? "neg" : "";
const pctTxt = v => v === null || v === undefined ? "" : `${v > 0 ? "+" : ""}${v.toFixed(1)} %`;
const mon = (y, p) => `${String(p).padStart(2, "0")}/${y}`;

// ================================================================== CO cockpit
register("ZCO_COCKPIT", { title: "Controlling Cockpit - Management P&L", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const body = out();
  app.append(panel("Period", grid(...pf.fields)), body);
  const exec = async () => {
    const d = await run(() => api(`/api/co/cockpit?gjahr=${val(pf.y)}&perio=${val(pf.m)}`));
    if (!d) return;
    body.innerHTML = "";
    const k = d.kpi, cur = S.meta.currency;
    const kpi = (l, v, s, goTo, cls) => h("div.kpi", { dataset: goTo ? { go: goTo } : null,
      on: goTo ? { click: () => go(goTo) } : null }, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
    const var_ = (a, p) => p ? `${a >= p ? "▲" : "▼"} ${((a - p) / Math.abs(p) * 100).toFixed(1)} % vs plan` : "";
    body.append(h("div.kpis", null,
      kpi("Net revenue", h("span", null, fmtShort(k.net), " ", h("small", null, cur)), var_(k.revenue, k.revenue_plan), "KE30"),
      kpi("Contribution margin I", h("span", null, fmtShort(k.cm1)), `${(k.cm1 / (k.net || 1) * 100).toFixed(1)} % of net revenue`, "KE30"),
      kpi("Gross profit (CM II)", h("span", null, fmtShort(k.cm2)), `${(k.cm2 / (k.net || 1) * 100).toFixed(1)} % margin`, "KE30"),
      kpi("Operating result (EBIT)", h("span", null, fmtShort(k.ebit)), var_(k.ebit, k.ebit_plan), "KE30", k.ebit < k.ebit_plan ? "crit" : "pos"),
      kpi("Production variances", fmtShort(k.prod_var), "Settled from orders (KO88)", "KKBC_ORD", k.prod_var > 0 ? "neg" : "pos"),
      kpi("Under/over absorption", fmtShort(k.absorption), "Production cost centers → CO-PA", "S_ALR_87013625", k.absorption > 0 ? "crit" : ""),
      kpi("Units sold", fmtQty(k.qty), `plan ${fmtQty(k.qty_plan)}`, "KE24"),
      kpi("FI = CO-PA ?", k.recon_ok ? "✔ Yes" : "✖ No", `FI ${fmtShort(d.recon.fi_result)} · CO-PA ${fmtShort(d.recon.copa_ebit)}`, "ZCO_RECON", k.recon_ok ? "pos" : "neg")));
    const wide = el => { el.classList.add("wide"); return el; };
    const card = (t, sub, ...b) => h("div.card", null, h("h3", null, t), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...b));
    body.append(h("div.cards", null,
      card("P&L bridge - actual " + mon(d.gjahr, d.perio), "From net revenue to operating result", waterfall(d.pnl)),
      wide(card("Plan vs actual", "Contribution margin scheme", pnlTable(d.pnl, false, true))),
      card("Profitability by product", "CO-PA, record types F/C/D", alv({ compact: true, rows: d.products, columns: [
        { key: "matnr", label: "Product", link: r => go("KE30", { drill: "matnr", matnr: r.matnr }) },
        { key: "qty", label: "Qty", type: "qty" }, { key: "net", label: "Net revenue", type: "amt", sum: true },
        { key: "cm1", label: "CM I", type: "amt", sum: true }, { key: "ebit", label: "EBIT", type: "amt", sum: true, signed: true },
        { key: "m", label: "EBIT %", render: r => h("span", null, r.net ? (r.ebit / r.net * 100).toFixed(1) + " %" : "") }] })),
      card("Profitability by customer", null, alv({ compact: true, rows: d.customers.map(c => ({ ...c,
        name: (CO.customers.find(x => x.kunnr === c.kunnr) || {}).name })), columns: [
        { key: "kunnr", label: "Customer", link: r => go("KE30", { drill: "matnr", kunnr: r.kunnr }) }, { key: "name", label: "Name" },
        { key: "net", label: "Net revenue", type: "amt", sum: true }, { key: "ebit", label: "EBIT", type: "amt", sum: true, signed: true },
        { key: "m", label: "EBIT %", render: r => h("span", null, r.net ? (r.ebit / r.net * 100).toFixed(1) + " %" : "") }] })),
      card("Cost centers - plan vs actual (debits)", "Primary + allocated costs before credits", alv({ compact: true,
        rows: d.cost_centers.filter(c => c.plan || c.actual), columns: [
          { key: "kostl", label: "Cost ctr", link: r => go("S_ALR_87013611", { kostl: r.kostl }) }, { key: "name", label: "Name" },
          { key: "kosar", label: "Cat." }, { key: "plan", label: "Plan", type: "amt", sum: true },
          { key: "actual", label: "Actual", type: "amt", sum: true },
          { key: "variance", label: "Variance", type: "amt", sum: true, cls: r => r.variance > 0 ? "neg" : "pos" },
          { key: "var_pct", label: "Var %", render: r => h("span", { class: r.var_pct > 5 ? "neg" : "" }, pctTxt(r.var_pct)) }] }))));
    msg("S", `Cockpit ${mon(d.gjahr, d.perio)} · EBIT ${fmtAmt(k.ebit)} ${cur} (plan ${fmtAmt(k.ebit_plan)})`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec },
    { label: "Process map", ghost: true, onClick: () => go("ZCO_PROCESS") }, { label: "Print", ghost: true, onClick: () => window.print() }]);
  exec();
}});

function waterfall(rows) {
  const r = Object.fromEntries(rows.map(x => [x.code, x.actual]));
  const steps = [["Net rev.", r["=NET"], "t"], ["Var. costs", -(r.vv030 + r.vv050 + r.vv060), "d"],
    ["CM I", r["=CM1"], "t"], ["Fixed prod.", -(r.vv040 + r.vv051 + r.vv061 + r.vv070), "d"],
    ["CM II", r["=CM2"], "t"], ["Variances", -(r.vv080 + r.vv090), "d"], ["CM III", r["=CM3"], "t"],
    ["Sales", -r.vv100, "d"], ["Admin", -r.vv110, "d"], ["EBIT", r["=EBIT"], "t"]];
  const W = 560, H = 230, P = { l: 8, r: 8, t: 18, b: 34 };
  const max = Math.max(...steps.map(s => Math.abs(s[1])), r["=NET"], 1);
  const bw = (W - P.l - P.r) / steps.length, Y = v => P.t + (1 - v / max) * (H - P.t - P.b);
  let level = 0, svg = "";
  steps.forEach(([lbl, v, t], i) => {
    const x = P.l + i * bw + 6, w = bw - 12;
    let y0, y1, col;
    if (t === "t") { y0 = 0; y1 = v; level = v; col = "#0a6ed1"; }
    else { y0 = level; y1 = level + v; level = y1; col = v < 0 ? "#e9730c" : "#107e3e"; }
    const top = Y(Math.max(y0, y1)), bot = Y(Math.min(y0, y1));
    svg += `<rect x="${x}" y="${top}" width="${w}" height="${Math.max(bot - top, 1)}" fill="${col}" rx="2"><title>${lbl}: ${fmtAmt(v)}</title></rect>` +
      `<text x="${x + w / 2}" y="${top - 4}" font-size="10" text-anchor="middle" fill="#32363a">${fmtShort(v)}</text>` +
      `<text x="${x + w / 2}" y="${H - 18}" font-size="10" text-anchor="middle" fill="#6a6d70">${lbl}</text>`;
  });
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", `0 0 ${W} ${H}`); s.style.width = "100%"; s.innerHTML = svg;
  return s;
}

function pnlTable(rows, drill, compact, drillCols, qty) {
  const t = h("table.grid.pnl");
  const head = ["", "Actual", "Plan", "Variance", "Var %"];
  if (!compact) head.push("% of net rev.");
  const dcols = drillCols || [];
  t.append(h("thead", null, h("tr", null, head.map((x, i) => h("th" + (i ? ".num" : ""), null, x)),
    dcols.map(c => h("th.num", null, c)))));
  const tb = h("tbody");
  if (qty) tb.append(h("tr", null, h("td.muted", null, "Sales quantity"), h("td.num", null, fmtQty(qty.a)), h("td.num", null, fmtQty(qty.p)),
    h("td.num", null, fmtQty(qty.a - qty.p)), h("td"), compact ? null : h("td"), dcols.map(c => h("td.num", null, fmtQty(qty.by[c] || 0)))));
  for (const r of rows) {
    const sub = r.kind === "=";
    const varCls = r.kind === "-" ? (r.variance > 0 ? "neg" : r.variance < 0 ? "pos" : "") : (r.variance < 0 ? "neg" : r.variance > 0 ? "pos" : "");
    tb.append(h("tr" + (sub ? ".sub" : ""), null, h("td", { style: sub ? null : { paddingLeft: "18px" } }, r.text),
      h("td.num", { class: "num " + neg(r.actual) }, fmtAmt(r.actual)), h("td.num", null, fmtAmt(r.plan)),
      h("td.num", { class: "num " + varCls }, fmtAmt(r.variance)), h("td.num", null, pctTxt(r.var_pct)),
      compact ? null : h("td.num", null, r.pct_rev === null ? "" : r.pct_rev.toFixed(1) + " %"),
      dcols.map(c => h("td.num", { class: "num " + neg((r.by || {})[c]) }, fmtAmt((r.by || {})[c] || 0)))));
  }
  t.append(tb);
  return h("div.alv-scroll", null, t);
}

// ================================================================== process map
register("ZCO_PROCESS", { title: "CO Process Map & Closing Cockpit", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const body = out();
  app.append(sampleNote(), panel("Period", grid(...pf.fields)), body);
  const exec = async () => {
    const s = await run(() => api(`/api/co/closing?gjahr=${val(pf.y)}&perio=${val(pf.m)}`));
    if (!s) return;
    body.innerHTML = "";
    const ok = (c, txt) => c ? badge("✔ " + (txt || "Done"), "U") : badge("Open", "Q");
    const run_ = c => s.runs[c] ? badge(`✔ run ${s.runs[c].run_id}`, "U") : badge("Open", "Q");
    const phases = [
      ["1. Master data", "Organisation and master data of Controlling", [
        ["OKEON", "Standard hierarchy & cost centers (KS01)", "KSH1", true],
        ["KA03", "Cost elements (primary = G/L, secondary cat. 21/41/42/43)", "KA03", true],
        ["KL01", "Activity types (machine, labor, maintenance hours)", "KL01", true],
        ["KK01", "Statistical key figures (m2, kWh, employees)", "KK01", true],
        ["CS03", "BOM, routing, work centers (quantity structure)", "CS03", true],
        ["KZS2", "Costing sheet: material 5 %, production 10 % overhead", "KZS2", true],
        ["KSU1", "Allocation cycles (distribution, assessment, CO-PA)", "KSU3", true]]],
      ["2. Planning", "Budget of the period (version 0)", [
        ["KP06", "Cost center planning: primary costs fixed / variable", "KP06", true],
        ["KP26", "Activity type planning: hours and capacity", "KP26", true],
        ["KP46", "Statistical key figure planning", "KP46", true],
        ["KSPI", "Plan price calculation (iterative)", "KSPI", s.plan_prices > 0, `${s.plan_prices} prices`],
        ["CK11N", "Standard cost estimate of products", "CK11N", s.estimates > 0],
        ["CK24", "Mark & release → new standard price", "CK24", s.estimates > 0, `${s.estimates} released`],
        ["KE11", "Sales & profit plan (CO-PA)", "KE11", s.copa_plan > 0, `${s.copa_plan} lines`]]],
      ["3. Actual postings during the month", "Logistics and FI postings flow into CO automatically", [
        ["CO01", "Production orders (create & release)", "CO01", true],
        ["MIGO 261", "Material issue to production order", "MIGO", true],
        ["CO11N", "Confirmations: machine & labor hours", "CO11N", s.confirmations > 0, `${s.confirmations} confirmations`],
        ["MIGO 101", "Goods receipt of finished products (credit order at standard)", "MIGO", true],
        ["FB50", "Payroll, energy, rent, depreciation to cost centers", "FB50", true],
        ["KB21N", "Maintenance hours to production cost centers", "KB21N", true],
        ["KB31N", "Actual statistical key figures (kWh)", "KB31N", true],
        ["VF01", "Billing: goods issue 601, revenue, CO-PA line items", "VF01", s.billing > 0, `${s.billing} lines`]]],
      ["4. Period-end closing", "In this order - each step needs the one before", [
        ["KSV5", "Distribution: rent by m2", "KSV5", s.runs.DIST01, null, run_("DIST01")],
        ["KSU5", "Assessment: energy by kWh", "KSU5", s.runs.ASSESS01, null, run_("ASSESS01")],
        ["KGI2", "Overhead on production orders", "KGI2", s.kgi2 > 0, `${s.kgi2} documents`],
        ["KKS2", "Variance calculation", "KKS2", s.kks2 > 0, `${s.kks2} orders`],
        ["KO88", "Settlement of orders", "KO88", s.ko88 > 0, `${s.ko88} documents`],
        ["KEU5", "Assessment of cost centers to CO-PA", "KEU5", s.runs.COPA01, null, run_("COPA01")]]],
      ["5. Reporting & decisions", "", [
        ["KE30", "Management P&L: contribution margins, plan vs actual", "KE30", true],
        ["S_ALR_87013611", "Cost centers: actual / plan / variance", "S_ALR_87013611", true],
        ["S_ALR_87013625", "Cost centers: target / actual (fixed vs variable)", "S_ALR_87013625", true],
        ["KKBC_ORD", "Order analysis: target / actual / variances", "KKBC_ORD", true],
        ["ZCO_RECON", "FI = CO-PA reconciliation", "ZCO_RECON", s.recon_ok, s.recon_ok ? "Balanced" : "Difference"]]],
    ];
    for (const [title, sub, steps] of phases) {
      body.append(h("div.panel", null, h("div.panel-head", null, title, h("span.muted", { style: { fontWeight: 400 } }, sub)),
        h("div.process", null, steps.map(([code, text, tcode, done, txt, custom]) => h("div.step", { on: { click: () => go(tcode) } },
          h("div.step-code", null, code), h("div.step-text", null, text), custom || ok(done, txt))))));
    }
    const all = s.open_cc === 0 && s.open_orders === 0 && s.recon_ok;
    body.append(panel("Closing result", h("div", { class: all ? "pos" : "crit", style: { fontSize: "15px" } },
      all ? "✔ Period closed: all cost centers and orders are zero and FI equals CO-PA."
        : `Open: ${s.open_cc} cost center(s) with balance, ${s.open_orders} order(s) with balance.`)));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: exec }]);
  exec();
}});

// ================================================================== master data
register("KSH1", { title: "Standard Hierarchy & Cost Centers (OKEON / KS01)", async render(app) {
  await meta(true);
  const tree = h("div.tree-box");
  const draw = () => {
    tree.innerHTML = "";
    const node = (g, lvl) => {
      const kids = CO.groups.filter(x => x.parent === g.khinr);
      const ccs = CO.cost_centers.filter(c => c.khinr === g.khinr);
      return h("div", { style: { marginLeft: lvl ? "22px" : 0 } },
        h("div.tree-node", null, "▾ ", h("b", null, g.khinr), " ", g.ktext),
        ccs.map(c => h("div.tree-leaf", null, h("a", { href: `#/S_ALR_87013611?kostl=${c.kostl}` }, c.kostl), ` ${c.name} `,
          badge(c.kosar || "-", ""), h("span.muted", null, ` ${CO.cc_categories[c.kosar] || ""} · ${c.verak || ""}`))),
        kids.map(k => node(k, lvl + 1)));
    };
    CO.groups.filter(g => !g.parent).forEach(g => tree.append(node(g, 0)));
  };
  const f = { kostl: inp({ upper: true, w: "s" }), name: inp({ w: "l" }), kosar: sel([["", ""], ...Object.entries(CO.cc_categories).map(([k, v]) => [k, `${k} ${v}`])], "", { w: "l" }),
    khinr: inp({ list: "dl-khinr", upper: true, w: "m" }), verak: inp({ w: "l" }) };
  const g = { khinr: inp({ upper: true, w: "m" }), ktext: inp({ w: "l" }), parent: inp({ list: "dl-khinr", upper: true, w: "m" }) };
  app.append(h("div.two-col", null, panel("Standard hierarchy H1000", tree),
    h("div", null, panel("Create cost center (KS01)", grid(field("Cost center", f.kostl, { req: true }), field("Name", f.name, { req: true }),
      field("Category", f.kosar), field("Hierarchy area", f.khinr), field("Person responsible", f.verak)),
      h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
        const r = await run(() => api("/api/co/costcenter", { kostl: up(f.kostl), name: val(f.name), kosar: f.kosar.value, khinr: up(f.khinr), verak: val(f.verak) }));
        if (r) { msg("S", r.message); await meta(true); await App.refreshMeta(); draw(); } } } }, "Save cost center"))),
    panel("Create hierarchy node", grid(field("Node", g.khinr, { req: true }), field("Text", g.ktext), field("Parent node", g.parent)),
      h("div.row-actions", null, h("button.btn", { type: "button", on: { click: async () => {
        const r = await run(() => api("/api/co/group", { khinr: up(g.khinr), ktext: val(g.ktext), parent: up(g.parent) }));
        if (r) { msg("S", r.message); await meta(true); draw(); } } } }, "Save node"))))));
  draw();
}});
register("OKEON", { title: "Standard Hierarchy", render: () => go("KSH1") });
register("KS01", { title: "Create Cost Center", render: () => go("KSH1") });

register("KS03", { title: "Display Cost Centers", async render(app) {
  await meta(true);
  app.append(alv({ title: "Cost centers - controlling area " + CO.kokrs, rows: CO.cost_centers.map(c => ({ ...c, cat: CO.cc_categories[c.kosar] || "" })), columns: [
    { key: "kostl", label: "Cost center", link: r => go("S_ALR_87013611", { kostl: r.kostl }) }, { key: "name", label: "Name" },
    { key: "kosar", label: "Cat." }, { key: "cat", label: "Category" }, { key: "khinr", label: "Hierarchy area" },
    { key: "verak", label: "Person responsible" }] }));
}});

register("KA03", { title: "Cost Elements (KA01 / KA06)", async render(app) {
  await meta(true);
  const k = inp({ w: "m" }), t = inp({ w: "l" });
  const c = sel(Object.entries(CO.ce_categories).map(([a, b]) => [a, `${a} ${b}`]), "1", { w: "l" });
  app.append(panel("Create cost element", grid(field("Cost element", k, { req: true }), field("Name", t, { req: true }), field("Category", c)),
    h("div.note", null, "Primary (1, 11, 12) must exist as a G/L account. Secondary (21, 41, 42, 43) exist only in CO."),
    h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
      const r = await run(() => api("/api/co/costelement", { kstar: val(k), ktext: val(t), katyp: c.value }));
      if (r) { msg("S", r.message); go("KA03"); } } } }, "Save"))),
  alv({ title: "Cost elements", rows: CO.cost_elements.map(e => ({ ...e, cat: CO.ce_categories[e.katyp], type: e.katyp <= 12 ? "Primary" : "Secondary",
    gl: e.katyp <= 12 ? (CO.gl_accounts[e.kstar] || "") : "" })), columns: [
    { key: "kstar", label: "Cost element", link: r => go("KSB1", { kstar: r.kstar }) }, { key: "ktext", label: "Name" },
    { key: "type", label: "Type" }, { key: "katyp", label: "CElem cat.", type: "int" }, { key: "cat", label: "Category" },
    { key: "gl", label: "G/L account text" }] }),
  h("div", { style: { height: "12px" } }),
  alv({ title: "Default account assignment (OKB9)", rows: CO.default_aa, columns: [
    { key: "kstar", label: "Cost element" }, { key: "kostl", label: "Default cost center" }] }));
}});
register("KA01", { title: "Create Cost Element", render: () => go("KA03") });
register("KA06", { title: "Create Secondary Cost Element", render: () => go("KA03") });

register("KL01", { title: "Activity Types", async render(app) {
  await meta(true);
  const l = inp({ upper: true, w: "s" }), t = inp({ w: "l" }), u = inp({ value: "H", upper: true, w: "s" }), k = inp({ list: "dl-kstar", w: "m" });
  const cc = sel(Object.entries(CO.cost_components).map(([a, b]) => [a, `${a} ${b}`]), "30", { w: "l" });
  app.append(panel("Create activity type", grid(field("Activity type", l, { req: true }), field("Name", t), field("Unit", u),
    field("Allocation cost element (43)", k, { req: true }), field("Cost component", cc)),
    h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
      const r = await run(() => api("/api/co/activitytype", { lstar: up(l), ktext: val(t), meinh: up(u), kstar: val(k), ccomp: cc.value }));
      if (r) { msg("S", r.message); go("KL01"); } } } }, "Save"))),
  alv({ title: "Activity types", rows: CO.activity_types.map(a => ({ ...a, cc: CO.cost_components[a.ccomp], ce: ceText(a.kstar) })), columns: [
    { key: "lstar", label: "Activity type" }, { key: "ktext", label: "Name" }, { key: "meinh", label: "Unit" },
    { key: "kstar", label: "Alloc. cost element" }, { key: "ce", label: "Cost element text" }, { key: "cc", label: "Cost component" }] }));
}});

register("KK01", { title: "Statistical Key Figures", async render(app) {
  await meta(true);
  const s = inp({ upper: true, w: "s" }), t = inp({ w: "l" }), u = inp({ upper: true, w: "s" }), fx = h("input", { type: "checkbox", checked: true });
  app.append(panel("Create statistical key figure", grid(field("Stat. key figure", s, { req: true }), field("Name", t), field("Unit", u),
    field("Key figure category", h("label.checkbox", null, fx, "Fixed value (carried forward to later periods)"))),
    h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
      const r = await run(() => api("/api/co/skf", { stagr: up(s), ktext: val(t), meinh: up(u), fixed: fx.checked }));
      if (r) { msg("S", r.message); go("KK01"); } } } }, "Save"))),
  alv({ title: "Statistical key figures", rows: CO.skf.map(x => ({ ...x, cat: x.fixed ? "1 Fixed value" : "2 Totals value" })), columns: [
    { key: "stagr", label: "Key figure" }, { key: "ktext", label: "Name" }, { key: "meinh", label: "Unit" }, { key: "cat", label: "Category" }] }));
}});

register("CS03", { title: "BOM, Routing & Work Centers", async render(app, params) {
  await meta();
  const m = inp({ value: params.id || "FG-3001", list: "dl-mat", upper: true, w: "m" });
  const o = out();
  app.append(panel("Material", grid(field("Material", m))), o);
  const exec = async () => {
    const d = await run(() => api("/api/co/bom/" + enc(up(m))));
    if (!d) return;
    o.innerHTML = "";
    o.append(alv({ title: "Bill of material (CS03) - quantities per 1 piece", rows: d.bom, columns: [
      { key: "posnr", label: "Item", type: "int" }, { key: "idnrk", label: "Component" }, { key: "maktx", label: "Description" },
      { key: "menge", label: "Quantity", type: "qty" }, { key: "meins", label: "Un" }] }), h("div", { style: { height: "12px" } }),
    alv({ title: "Routing (CA03) - standard values per 1 piece", rows: d.routing, columns: [
      { key: "vornr", label: "Op." }, { key: "arbpl", label: "Work center" }, { key: "wtext", label: "Work center text" },
      { key: "ltxa1", label: "Operation" }, { key: "vgw", label: "Std value", type: "qty" }, { key: "lstar", label: "Activity" },
      { key: "kostl", label: "Cost center" }] }), h("div", { style: { height: "12px" } }),
    alv({ title: "Work centers (CR03)", rows: CO.work_centers, columns: [
      { key: "arbpl", label: "Work center" }, { key: "ktext", label: "Text" }, { key: "werks", label: "Plant" },
      { key: "kostl", label: "Cost center" }, { key: "lstar", label: "Activity type" }] }));
  };
  execBar(exec); exec();
}});
function execBar(fn, extra) { toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }, ...(extra || [])]); }

register("KZS2", { title: "Costing Sheet COGS01 (Overhead)", async render(app) {
  await meta(true);
  app.append(alv({ title: "Costing sheet rows", rows: CO.costing_sheet.map(r => ({ ...r, pct: (r.pct_fix + r.pct_var) / 100,
    fixp: r.pct_fix / 100, base_t: r.base === "MAT" ? "Material costs (BOM components)" : "Activity costs (labor + machine)",
    cc: CO.cost_components[r.ccomp] })), columns: [
    { key: "zeile", label: "Row", type: "int" }, { key: "ktext", label: "Description" }, { key: "base_t", label: "Base" },
    { key: "pct", label: "Overhead %", type: "amt" }, { key: "fixp", label: "of which fixed %", type: "amt" },
    { key: "kstar", label: "Overhead cost element" }, { key: "kostl", label: "Credit cost center" }, { key: "cc", label: "Cost component" }] }),
  h("div.note", { style: { marginTop: "10px" } }, "Used in the standard cost estimate (CK11N) and on production orders at period end (KGI2)."));
}});

// ================================================================== cycles
register("KSU3", { title: "Allocation Cycles (KSV1 / KSU1 / KEU1)", async render(app) {
  await meta(true);
  const T = { D: "Distribution (KSV5)", A: "Assessment (KSU5)", P: "Assessment to CO-PA (KEU5)" };
  for (const c of CO.cycles) {
    app.append(alv({ title: `${c.cycle} - ${c.ktext} · ${T[c.typ]}`, rows: c.segments.map(s => ({ ...s,
      tr: s.tracing.startsWith("SKF:") ? `Stat. key figure ${s.tracing.slice(4)}` : s.tracing.startsWith("VV:") ? `CO-PA value field ${s.tracing.slice(3)}` : s.tracing,
      rec: c.typ === "P" ? `CO-PA → ${s.vv}` : s.receivers })), columns: [
      { key: "seg", label: "Seg.", type: "int" }, { key: "ktext", label: "Segment" }, { key: "senders", label: "Sender cost centers" },
      { key: "sender_kstar", label: "Sender cost elements" }, { key: "kstar", label: "Assessment CE" },
      { key: "rec", label: "Receivers" }, { key: "tr", label: "Tracing factor" }] }), h("div", { style: { height: "12px" } }));
  }
}});

function cycleScreen(code, typ, title) {
  register(code, { title, async render(app, params) {
    await meta(true);
    const cs = CO.cycles.filter(c => c.typ === typ);
    const pf = periodFields(params);
    const c = sel(cs.map(x => [x.cycle, `${x.cycle} ${x.ktext}`]), cs[0] && cs[0].cycle, { w: "l" });
    const plan = sel([["04", "Actual"], ["01", "Plan (version 0)"]], "04", { w: "m" });
    const test = h("input", { type: "checkbox", checked: true });
    const o = out(), runsBox = out();
    app.append(panel("Parameters", grid(field("Cycle", c), ...pf.fields, field("Value type", plan),
      field("Processing", h("label.checkbox", null, test, "Test run (nothing is posted)")))), o, runsBox);
    const runs = async () => {
      const r = await run(() => api("/api/co/cycle/runs"));
      if (!r) return;
      runsBox.innerHTML = "";
      runsBox.append(h("div", { style: { height: "12px" } }), alv({ title: "Previous runs", rows: r.filter(x => cs.some(y => y.cycle === x.cycle)),
        rowClass: x => x.reversed ? ".canceled" : "", columns: [
          { key: "run_id", label: "Run", type: "int" }, { key: "cycle", label: "Cycle" }, { key: "wrttp", label: "Type", render: x => h("span", null, x.wrttp === "01" ? "Plan" : "Actual") },
          { key: "perio", label: "Per.", type: "int" }, { key: "gjahr", label: "Year", type: "int" }, { key: "belnr", label: "CO documents" },
          { key: "ts", label: "Executed" }, { key: "usnam", label: "User" },
          { key: "x", label: "", render: x => x.reversed ? h("span.muted", null, "reversed") : h("a", { href: "#", on: { click: async e => {
            e.preventDefault(); if (!await confirmBox("Reverse run", `Reverse run ${x.run_id} of cycle ${x.cycle}?`, "Reverse")) return;
            const rr = await run(() => api("/api/co/cycle/reverse", { run_id: x.run_id })); if (rr) { msg("S", rr.message); runs(); } } } }, "Reverse") }] }));
    };
    const exec = async () => {
      const r = await run(() => api("/api/co/cycle/run", { cycle: c.value, gjahr: val(pf.y), perio: val(pf.m), wrttp: plan.value, test: test.checked }));
      if (!r) return;
      o.innerHTML = "";
      o.append(alv({ title: (r.test ? "TEST RUN - " : "") + "Sender / receiver list", rows: r.lines, columns: [
        { key: "seg", label: "Seg.", type: "int" }, { key: "sender", label: "Sender", link: x => go("S_ALR_87013611", { kostl: x.sender }) },
        { key: "kstar", label: "Cost element" }, { key: "receiver", label: "Receiver" },
        { key: "vv", label: "Value field" }, { key: "amount", label: "Amount", type: "amt", sum: true }] }));
      msg(r.test ? "I" : "S", r.message + (r.test ? " - remove the test-run flag to post" : ""));
      runs();
    };
    execBar(exec);
    runs();
  }});
}
cycleScreen("KSV5", "D", "Execute Actual Distribution");
cycleScreen("KSU5", "A", "Execute Actual Assessment");
cycleScreen("KEU5", "P", "Execute Assessment to CO-PA");

// ================================================================== planning
register("KP06", { title: "Change Cost Element/Activity Input Planning", async render(app, params) {
  await meta();
  const f = { y: inp({ value: CO.sample.gjahr, w: "s" }), pf: inp({ value: CO.sample.perio, w: "s" }), pt: inp({ value: 12, w: "s" }),
    k: ccIn(params.kostl || "4100"), ce: inp({ list: "dl-kstar1", w: "m" }), la: inp({ list: "dl-lstar", upper: true, w: "s", ph: "blank = independent" }),
    fix: inp({ w: "m" }), var: inp({ w: "m" }), dist: h("input", { type: "checkbox" }) };
  const o = out();
  app.append(panel("Primary cost planning - version 0", grid(field("Fiscal year", f.y), field("From period", f.pf), field("To period", f.pt),
    field("Cost center", f.k, { req: true }), field("Cost element", f.ce, { req: true }), field("Activity type", f.la),
    field("Fixed costs", f.fix), field("Variable costs", f.var),
    field("Distribution key", h("label.checkbox", null, f.dist, "Values are totals → distribute equally (key 2)"))),
    h("div.note", null, "Variable costs must be planned activity-dependent (with an activity type). Values apply to every period unless distribution key 2 is set.")), o);
  const show = async () => {
    const rows = await run(() => api(`/api/co/plan/costs?kostl=${up(f.k)}&gjahr=${val(f.y)}&perio=${val(f.pf)}`));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: `Plan of cost center ${up(f.k)} ${ccName(up(f.k))} - period ${val(f.pf)}/${val(f.y)}`, rows, columns: [
      { key: "vrgng", label: "Bus. trans." }, { key: "vrgng_text", label: "Origin" }, { key: "kstar", label: "Cost element" },
      { key: "ktext", label: "Name" }, { key: "lstar", label: "Activity" }, { key: "fix", label: "Fixed", type: "amt", sum: true },
      { key: "var", label: "Variable", type: "amt", sum: true }, { key: "total", label: "Total", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Show plan", key: "F8", onClick: show }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/plan/costs", { gjahr: val(f.y), pfrom: val(f.pf), pto: val(f.pt), kostl: up(f.k), kstar: val(f.ce),
      lstar: up(f.la), fix: val(f.fix) || "0", var: val(f.var) || "0", distribute: f.dist.checked }));
    if (r) { msg("S", r.message + " - run KSPI to update the plan prices"); show(); } } }]);
  show();
}});

register("KP26", { title: "Change Activity Type/Price Planning", async render(app) {
  await meta();
  const f = { y: inp({ value: CO.sample.gjahr, w: "s" }), pf: inp({ value: CO.sample.perio, w: "s" }), pt: inp({ value: 12, w: "s" }),
    k: ccIn("4100"), la: inp({ list: "dl-lstar", upper: true, w: "s" }), q: inp({ w: "m" }), cap: inp({ w: "m" }),
    pfix: inp({ w: "m", ph: "blank = calculated" }), pvar: inp({ w: "m", ph: "blank = calculated" }) };
  const o = out();
  app.append(panel("Activity planning - version 0", grid(field("Fiscal year", f.y), field("From period", f.pf), field("To period", f.pt),
    field("Cost center", f.k, { req: true }), field("Activity type", f.la, { req: true }), field("Plan activity", f.q, { req: true }),
    field("Capacity", f.cap), field("Fixed price (manual)", f.pfix), field("Variable price (manual)", f.pvar))), o);
  const show = async () => { o.innerHTML = ""; o.append(await pricesTable(val(f.y), val(f.pf))); };
  toolbar([{ label: "Show", key: "F8", onClick: show }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/plan/activity", { gjahr: val(f.y), pfrom: val(f.pf), pto: val(f.pt), kostl: up(f.k), lstar: up(f.la),
      qty: val(f.q), capacity: val(f.cap), price_fix: val(f.pfix), price_var: val(f.pvar) }));
    if (r) { msg("S", r.message); show(); } } }]);
  show();
}});

async function pricesTable(y, p) {
  const rows = await api(`/api/co/rep/prices?gjahr=${y}&perio=${p}`);
  return alv({ title: `Activity prices and quantities - period ${p}/${y} (KSBT)`, rows, columns: [
    { key: "kostl", label: "Cost ctr", link: r => go("S_ALR_87013625", { kostl: r.kostl }) }, { key: "name", label: "Name" },
    { key: "lstar", label: "Act. type" }, { key: "ktext", label: "Activity" }, { key: "meinh", label: "Un" },
    { key: "plan_qty", label: "Plan qty", type: "qty" }, { key: "capacity", label: "Capacity", type: "qty" },
    { key: "actual_qty", label: "Actual qty", type: "qty" }, { key: "rate", label: "Op. rate %", type: "amt" },
    { key: "price_fix", label: "Price fixed", type: "amt" }, { key: "price_var", label: "Price variable", type: "amt" },
    { key: "price_tot", label: "Price total", type: "amt" }, { key: "price_ind", label: "Ind.", render: r => h("span", { title: r.price_ind === "1" ? "Calculated by KSPI" : "Manual price" }, r.price_ind) },
    { key: "plan_cost", label: "Plan costs credited", type: "amt", sum: true }] });
}
register("KSBT", { title: "Cost Centers: Activity Prices", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const o = out();
  app.append(panel("Period", grid(...pf.fields)), o);
  const exec = async () => { const t = await run(() => pricesTable(val(pf.y), val(pf.m))); if (t) { o.innerHTML = ""; o.append(t); } };
  execBar(exec); exec();
}});

register("KP46", { title: "Statistical Key Figures: Planning (KP46) / Actual (KB31N)", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const k = ccIn(""), s = inp({ list: "dl-stagr", upper: true, w: "s" }), v = inp({ w: "m" });
  const typ = sel([["01", "Plan (KP46)"], ["04", "Actual (KB31N)"]], params.actual ? "04" : "01", { w: "m" });
  const o = out();
  app.append(panel("Statistical key figure", grid(...pf.fields, field("Value type", typ), field("Cost center", k, { req: true }),
    field("Stat. key figure", s, { req: true }), field("Value", v, { req: true }))), o);
  const show = async () => {
    const rows = await run(() => api(`/api/co/skf?gjahr=${val(pf.y)}&perio=${val(pf.m)}`));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: "Values of the period", rows: rows.map(r => ({ ...r, t: r.wrttp === "01" ? "Plan" : "Actual", name: ccName(r.kostl) })), columns: [
      { key: "stagr", label: "Key figure" }, { key: "t", label: "Type" }, { key: "kostl", label: "Cost center" }, { key: "name", label: "Name" },
      { key: "value", label: "Value", type: "qty", sum: true }] }));
  };
  toolbar([{ label: "Show", key: "F8", onClick: show }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/plan/skf", { gjahr: val(pf.y), pfrom: val(pf.m), pto: val(pf.m), kostl: up(k), stagr: up(s), value: val(v), actual: typ.value === "04" }));
    if (r) { msg("S", r.message); show(); } } }]);
  show();
}});
register("KB31N", { title: "Enter Statistical Key Figures", render: () => go("KP46", { actual: 1 }) });

register("KSPI", { title: "Plan Price Calculation", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const o = out();
  app.append(panel("Parameters", grid(...pf.fields), h("div.note", null,
    "Iterative: senders (e.g. maintenance) are priced first, then their price flows into the receivers' plan costs (activity input) until all prices are stable. Price = plan costs / plan activity, split fixed / variable.")), o);
  const exec = async () => {
    const r = await run(() => api("/api/co/kspi", { gjahr: val(pf.y), perio: val(pf.m) }));
    if (!r) return;
    msg("S", r.message);
    o.innerHTML = ""; o.append(await pricesTable(val(pf.y), val(pf.m)));
  };
  execBar(exec);
  o.append(await pricesTable(val(pf.y), val(pf.m)));
}});

// ================================================================== actual postings
register("FB50", { title: "Enter G/L Account Document", async render(app) {
  await meta();
  const bud = inp({ type: "date", value: today(), w: "m" }), txt = inp({ w: "l" });
  const lines = [{ hkont: "", dc: "S", amt: "", kostl: "", aufnr: "", sgtxt: "" }, { hkont: "113100", dc: "H", amt: "", kostl: "", aufnr: "", sgtxt: "" }];
  const box = h("div.panel"), bal = h("span.badge");
  app.append(panel("Header", grid(field("Posting date", bud, { req: true }), field("Header text", txt))), box,
    h("div.note", null, "Expense accounts are cost elements: they need a cost center or an order (message KI 235). Revenue accounts need a profitability segment (use VF01)."));
  const draw = () => {
    box.innerHTML = "";
    const tb = h("tbody");
    const calc = () => { const b = lines.reduce((a, l) => a + (parseFloat(l.amt) || 0) * (l.dc === "S" ? 1 : -1), 0);
      bal.textContent = `Balance ${fmtAmt(b)}`; bal.className = "badge " + (Math.abs(b) < 0.005 ? "U" : "B"); };
    lines.forEach((l, i) => {
      const s = k => e => { l[k] = e.target.value; calc(); };
      tb.append(h("tr", null, h("td.ln", null, String(i + 1)),
        h("td", null, inp({ value: l.hkont, list: "dl-hkont", w: "m", oninput: s("hkont") })),
        h("td", null, sel([["S", "S Debit"], ["H", "H Credit"]], l.dc, { onchange: s("dc") })),
        h("td", null, inp({ value: l.amt, w: "m", oninput: s("amt") })),
        h("td", null, inp({ value: l.kostl, list: "dl-kostl", upper: true, w: "s", oninput: s("kostl") })),
        h("td", null, inp({ value: l.aufnr, list: "dl-aufnr", w: "m", oninput: s("aufnr") })),
        h("td", null, inp({ value: l.sgtxt, w: "l", oninput: s("sgtxt") })),
        h("td", null, h("button.alv-tb-btn", { type: "button", on: { click: () => { lines.splice(i, 1); draw(); } } }, "✕"))));
    });
    box.append(h("div.panel-head", null, "Items", h("span.spacer"), bal, h("button.btn.ghost", { type: "button", on: { click: () => {
      lines.push({ hkont: "", dc: "S", amt: "", kostl: "", aufnr: "", sgtxt: "" }); draw(); } } }, "+ Line")),
    h("div.items-wrap", null, h("table.grid.items", null, h("thead", null, h("tr", null, ["#", "G/L account", "D/C", "Amount", "Cost center", "Order", "Text", ""].map(x => h("th", null, x)))), tb)));
    calc();
  };
  draw();
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/fb50", { header: { budat: bud.value, bktxt: val(txt) }, lines: lines.filter(l => l.hkont).map(l => ({
      hkont: l.hkont.trim(), debit: l.dc === "S" ? l.amt : "", credit: l.dc === "H" ? l.amt : "", kostl: l.kostl, aufnr: l.aufnr, sgtxt: l.sgtxt })) }));
    if (r) { msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: r.gjahr }); lines.forEach(l => { l.amt = ""; }); draw(); } } }]);
}});

function objIn(label) {
  const t = sel([["KS", "Cost center"], ["OR", "Order"]], "KS", { w: "m" });
  const v = inp({ list: "dl-kostl", upper: true, w: "m" });
  t.addEventListener("change", () => v.setAttribute("list", t.value === "KS" ? "dl-kostl" : "dl-aufnr"));
  return { el: field(label, h("span.split", null, t, v), { req: true }), get: () => t.value === "KS" ? { kostl: up(v) } : { aufnr: val(v) } };
}

register("KB11N", { title: "Enter Manual Reposting of Primary Costs", async render(app) {
  await meta();
  const b = inp({ type: "date", value: today(), w: "m" }), s = objIn("Sender (old)"), r = objIn("Receiver (new)");
  const k = inp({ list: "dl-kstar1", w: "m" }), a = inp({ w: "m" }), t = inp({ w: "l" });
  app.append(panel("Reposting", grid(field("Posting date", b), s.el, r.el, field("Cost element", k, { req: true }), field("Amount", a, { req: true }), field("Text", t))));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const x = await run(() => api("/api/co/kb11n", { budat: b.value, sender: s.get(), receiver: r.get(), kstar: val(k), amount: val(a), text: val(t) }));
    if (x) msgLink("S", x.message, "Display", "KSB5", { id: x.belnr }); } }]);
}});

register("KB21N", { title: "Enter Direct Activity Allocation", async render(app) {
  await meta();
  const b = inp({ type: "date", value: today(), w: "m" }), sk = ccIn("4200"), la = inp({ value: "MAINT", list: "dl-lstar", upper: true, w: "s" });
  const q = inp({ w: "s" }), r = objIn("Receiver"), t = inp({ w: "l" });
  app.append(panel("Activity allocation (valued at plan price)", grid(field("Posting date", b), field("Sender cost center", sk, { req: true }),
    field("Sender activity type", la, { req: true }), field("Quantity", q, { req: true }), r.el, field("Text", t))));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const x = await run(() => api("/api/co/kb21n", { budat: b.value, skostl: up(sk), lstar: up(la), qty: val(q), receiver: r.get(), text: val(t) }));
    if (x) msgLink("S", x.message, "Display", "KSB5", { id: x.belnr }); } }]);
}});

register("CO11N", { title: "Enter Time Ticket for Production Order", async render(app, params) {
  await meta(true);
  const o = inp({ value: params.id || "", list: "dl-aufnr", w: "m" }), v = sel([["0010", "0010 Machining"], ["0020", "0020 Assembly"]], "0010", { w: "l" });
  const y = inp({ w: "s" }), q = inp({ w: "s" }), b = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Confirmation", grid(field("Order", o, { req: true }), field("Operation", v), field("Yield", y), field("Activity (hours)", q, { req: true }), field("Posting date", b)),
    h("div.note", null, "Posts the activity from the work center's cost center to the order at the plan price (fixed + variable).")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const x = await run(() => api("/api/co/co11n", { aufnr: val(o), vornr: v.value, yield: val(y), qty: val(q), budat: b.value }));
    if (x) msgLink("S", x.message, "Order analysis", "KKBC_ORD", { id: val(o) }); } }]);
}});

register("KSB5", { title: "Display CO Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" }), o = out();
  app.append(panel("Document", grid(field("CO document", d, { req: true }))), o);
  const exec = async () => {
    const doc = await run(() => api("/api/co/doc/" + enc(val(d))));
    if (!doc) return;
    o.innerHTML = "";
    o.append(h("div.panel", null, h("div.obj-header", null, [["Document", doc.belnr], ["Business transaction", `${doc.vrgng} ${doc.vrgng_text}`],
      ["Value type", doc.wrttp === "04" ? "04 Actual" : "01 Plan"], ["Period", mon(doc.gjahr, doc.perio)], ["Posting date", fmtDate(doc.budat)],
      ["User", doc.usnam], ["Text", doc.bltxt], ["Reference", doc.refbn || "-"], ["Reversed", doc.stflg ? `yes (${doc.stokz})` : "no"]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, String(v)))))));
    o.append(alv({ title: "Line items", rows: doc.items, columns: [
      { key: "buzei", label: "Itm", type: "int" }, { key: "otype", label: "Object type" }, { key: "object", label: "Object" },
      { key: "kstar", label: "Cost element" }, { key: "ktext", label: "Name" }, { key: "wtg", label: "Value", type: "amt", sum: true, signed: true },
      { key: "wkf", label: "Fixed", type: "amt" }, { key: "qty", label: "Quantity", type: "qty" }, { key: "lstar", label: "Activity" },
      { key: "parob", label: "Partner" }, { key: "matnr", label: "Material" }, { key: "sgtxt", label: "Text" }] }));
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, !doc.stflg ? { label: "Reverse (KB24N)", danger: true, onClick: async () => {
      if (!await confirmBox("Reverse", `Reverse CO document ${doc.belnr}?`, "Reverse")) return;
      const r = await run(() => api("/api/co/reverse", { belnr: doc.belnr })); if (r) { msg("S", r.message); exec(); } } } : null]);
  };
  execBar(exec);
  if (params.id) exec();
}});

// ================================================================== orders
register("KO01", { title: "Create Internal Order", async render(app) {
  await meta();
  const t = inp({ w: "l" }), k = ccIn("8100"), typ = sel([["ZINT", "ZINT Overhead order"], ["ZINV", "ZINV Investment / project"]], "ZINT", { w: "l" });
  const rt = sel([["KS", "KS Cost center"], ["PA", "PA Profitability segment"]], "KS", { w: "m" }), rr = ccIn("8100"), rel = h("input", { type: "checkbox", checked: true });
  app.append(panel("Order", grid(field("Order type", typ), field("Description", t, { req: true }), field("Responsible cost center", k),
    field("Settlement receiver", h("span.split", null, rt, rr)), field("Release immediately", h("label.checkbox", null, rel, "Status REL")))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/order", { auart: typ.value, ktext: val(t), kostl: up(k), release: rel.checked,
      rules: [{ konty: rt.value, receiver: rt.value === "PA" ? "" : up(rr), prozs: 100 }] }));
    if (r) { await meta(true); msgLink("S", r.message, "Display", "KKBC_ORD", { id: r.aufnr }); } } }]);
}});

register("CO01", { title: "Create Production Order", async render(app) {
  await meta();
  const m = inp({ value: "FG-3001", list: "dl-mat", upper: true, w: "m" }), q = inp({ value: "100", w: "s" });
  const l = inp({ value: "0003", upper: true, w: "s" }), rel = h("input", { type: "checkbox", checked: true });
  app.append(panel("Production order PP01 - plant 1000", grid(field("Material", m, { req: true }), field("Total quantity", q, { req: true }),
    field("Storage location (GR)", l), field("Release", h("label.checkbox", null, rel, "Release order (status REL)"))),
    h("div.note", null, "The order uses the released standard cost estimate (CK24) for plan and target costs. Settlement rule: 100 % to CO-PA (product).")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/order", { auart: "PP01", matnr: up(m), werks: "1000", lgort: up(l), gamng: val(q), release: rel.checked }));
    if (r) { await meta(true); msgLink("S", `Production order ${r.aufnr} saved`, "Order analysis", "KKBC_ORD", { id: r.aufnr }); } } }]);
}});

register("KOK5", { title: "Order List (KOK5 / COOIS)", async render(app) {
  await meta(true);
  const o = out(); app.append(o);
  const exec = async () => {
    const rows = await run(() => api("/api/co/rep/orders"));
    if (!rows) return;
    o.innerHTML = "";
    const act = (r, a, l) => h("a", { href: "#", style: { marginRight: "8px" }, on: { click: async e => { e.preventDefault();
      const x = await run(() => api("/api/co/order/status", { aufnr: r.aufnr, action: a })); if (x) { msg("S", x.message); exec(); } } } }, l);
    o.append(alv({ title: "Orders", rows: rows.map(r => ({ ...r, st: CO.order_status[r.stat] })), columns: [
      { key: "aufnr", label: "Order", link: r => go("KKBC_ORD", { id: r.aufnr }) }, { key: "auart", label: "Type" }, { key: "ktext", label: "Description" },
      { key: "matnr", label: "Material" }, { key: "gamng", label: "Order qty", type: "qty" }, { key: "wemng", label: "Delivered", type: "qty" },
      { key: "stat", label: "Status", render: r => badge(r.stat, r.stat === "REL" ? "S" : r.stat === "CLSD" ? "" : r.stat === "TECO" || r.stat === "DLV" ? "U" : "Q") },
      { key: "debits", label: "Debits", type: "amt", sum: true }, { key: "balance", label: "Balance", type: "amt", sum: true },
      { key: "x", label: "Actions", render: r => h("span", null, r.stat === "CRTD" ? act(r, "REL", "Release") : null,
        ["REL", "DLV"].includes(r.stat) ? act(r, "TECO", "TECO") : null, ["TECO", "DLV"].includes(r.stat) && !r.balance ? act(r, "CLSD", "Close") : null) }] }));
  };
  execBar(exec); exec();
}});
register("COOIS", { title: "Production Order Information System", render: () => go("KOK5") });
register("KO03", { title: "Display Internal Order", render: (a, p) => go("KKBC_ORD", p) });

register("KKBC_ORD", { title: "Analyze Order: Plan / Target / Actual", async render(app, params) {
  await meta();
  const a = inp({ value: params.id || "", list: "dl-aufnr", w: "m" }), o = out();
  app.append(panel("Order", grid(field("Order", a, { req: true }))), o);
  const exec = async () => {
    const d = await run(() => api("/api/co/rep/order/" + enc(val(a))));
    if (!d) return;
    o.innerHTML = "";
    o.append(h("div.panel", null, h("div.obj-header", null, [["Order", `${d.aufnr} (${d.auart})`], ["Description", d.ktext],
      ["Material", d.matnr ? `${d.matnr} ${d.maktx}` : "-"], ["Quantity", d.matnr ? `${fmtQty(d.gamng)} / delivered ${fmtQty(d.wemng)} ${d.meins}` : "-"],
      ["Status", `${d.stat} ${CO.order_status[d.stat]}`], ["Cost estimate", d.estimate_id || "-"],
      ["Settlement rule", d.rules.map(r => `${r.prozs} % ${r.konty} ${r.receiver}`).join(", ") || "-"]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, String(v)))))));
    o.append(alv({ title: "Cost analysis by cost element / resource", rows: d.lines, columns: [
      { key: "kstar", label: "Cost element" }, { key: "ce_text", label: "Cost element text" }, { key: "res", label: "Origin" },
      { key: "plan", label: "Plan costs", type: "amt", sum: true }, { key: "target", label: "Target costs", type: "amt", sum: true },
      { key: "actual", label: "Actual costs", type: "amt", sum: true, signed: true },
      { key: "variance", label: "Target/actual var.", type: "amt", sum: true, cls: r => r.variance > 0 ? "neg" : r.variance < 0 ? "pos" : "" },
      { key: "plan_qty", label: "Plan qty", type: "qty" }, { key: "act_qty", label: "Actual qty", type: "qty" }] }));
    if (d.variances.length) {
      o.append(h("div", { style: { height: "12px" } }), alv({ title: "Variance categories (KKS2): input price, quantity, resource-usage, remaining", rows: d.variances, columns: [
        { key: "perio", label: "Per.", type: "int" }, { key: "kstar", label: "Cost element" }, { key: "ressource", label: "Origin" },
        { key: "target", label: "Target", type: "amt" }, { key: "actual", label: "Actual", type: "amt" },
        { key: "price_var", label: "Price var.", type: "amt", sum: true, signed: true }, { key: "qty_var", label: "Quantity var.", type: "amt", sum: true, signed: true },
        { key: "res_var", label: "Resource-usage", type: "amt", sum: true }, { key: "rem_var", label: "Remaining / output", type: "amt", sum: true, signed: true }] }));
    }
    if (d.confirmations.length) o.append(h("div", { style: { height: "12px" } }), alv({ title: "Confirmations (CO11N)", rows: d.confirmations, columns: [
      { key: "rueck", label: "Conf.", type: "int" }, { key: "vornr", label: "Op." }, { key: "arbpl", label: "Work center" },
      { key: "lmnga", label: "Yield", type: "qty" }, { key: "ism", label: "Activity", type: "qty" }, { key: "budat", label: "Date", type: "date" },
      { key: "codoc", label: "CO doc.", link: r => go("KSB5", { id: r.codoc }) }] }));
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, { label: "Line items (KOB1)", onClick: () => go("KSB1", { otype: "OR", obj: d.aufnr, pfrom: 1 }) },
      d.auart === "PP01" && ["REL", "DLV"].includes(d.stat) ? { label: "Confirm (CO11N)", ghost: true, onClick: () => go("CO11N", { id: d.aufnr }) } : null,
      d.auart === "PP01" && d.stat === "REL" ? { label: "Goods receipt (MIGO)", ghost: true, onClick: () => go("MIGO", { order: d.aufnr }) } : null]);
  };
  execBar(exec);
  if (params.id) exec(); else { const r = await api("/api/co/rep/orders"); if (r.length) { a.value = r.find(x => x.auart === "PP01")?.aufnr || r[0].aufnr; exec(); } }
}});

// ================================================================== product costing
register("CK11N", { title: "Create Material Cost Estimate", async render(app) {
  await meta();
  const m = inp({ value: "FG-3001", list: "dl-mat", upper: true, w: "m" }), d = inp({ type: "date", value: today(), w: "m" }), l = inp({ value: "100", w: "s" });
  app.append(panel("Costing data - costing variant PPC1 (standard)", grid(field("Material", m, { req: true }), field("Plant", inp({ value: "1000", readonly: true, w: "s" })),
    field("Costing date", d), field("Costing lot size", l)), h("div.note", null,
    "Materials from the BOM × current price, + material overhead, + activities from the routing × plan activity price (KSPI), + production overhead.")));
  toolbar([{ label: "Cost", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/ck11n", { matnr: up(m), werks: "1000", kadky: d.value, losgr: val(l) }));
    if (r) { msg("S", r.message); go("CK13N", { id: r.id }); } } }]);
}});

register("CK13N", { title: "Display Material Cost Estimate", async render(app, params) {
  await meta();
  const m = inp({ value: params.matnr || "FG-3001", list: "dl-mat", upper: true, w: "m" }), o = out();
  app.append(panel("Material", grid(field("Material", m))), o);
  const show = async id => {
    const e = await run(() => api(id ? `/api/co/estimate?id=${id}` : `/api/co/estimate?matnr=${enc(up(m))}`));
    if (!e) return;
    m.value = e.matnr;
    o.innerHTML = "";
    const st = { KA: "KA Costed", VO: "VO Marked", FR: "FR Released" }[e.status];
    o.append(h("div.panel", null, h("div.obj-header", null, [["Cost estimate", e.id], ["Material", `${e.matnr} ${e.maktx}`], ["Costing date", fmtDate(e.kadky)],
      ["Lot size", `${fmtQty(e.losgr_v)} ${e.meins}`], ["Status", st], ["Total (lot)", fmtAmt(e.total_v)],
      ["of which fixed", fmtAmt(e.fixed_v)], ["Cost per unit", h("b", null, fmtAmt(e.unit_cost))]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
    const tot = e.components.reduce((a, c) => a + c.total, 0) || 1;
    const colors = ["#0a6ed1", "#5899da", "#e9730c", "#107e3e", "#945ecf"];
    o.append(h("div.panel", null, h("h2", null, "Cost component split (per lot)"), h("div.panel-body", null,
      h("div.stackbar", null, e.components.map((c, i) => h("span", { style: { width: (c.total / tot * 100) + "%", background: colors[i % 5] }, title: `${c.text} ${fmtAmt(c.total)}` }))),
      alv({ compact: true, rows: e.components.map(c => ({ ...c, pct: c.total / tot * 100 })), columns: [
        { key: "ccomp", label: "Comp.", type: "int" }, { key: "text", label: "Cost component" }, { key: "total", label: "Total", type: "amt", sum: true },
        { key: "fixed", label: "Fixed", type: "amt", sum: true }, { key: "variable", label: "Variable", type: "amt", sum: true },
        { key: "per_unit", label: "Per unit", type: "amt", sum: true }, { key: "pct", label: "%", type: "amt" }] }))));
    o.append(alv({ title: "Itemization", rows: e.items, columns: [
      { key: "posnr", label: "Item", type: "int" }, { key: "typ", label: "Cat.", render: r => h("span", { title: { M: "Material", E: "Internal activity", G: "Overhead" }[r.typ] }, r.typ) },
      { key: "ressource", label: "Resource" }, { key: "ktext", label: "Description" }, { key: "menge", label: "Quantity", type: "qty" },
      { key: "meinh", label: "Un" }, { key: "price", label: "Price / %", type: "amt" }, { key: "wert", label: "Value", type: "amt", sum: true },
      { key: "wkf", label: "Fixed", type: "amt", sum: true }, { key: "wkv", label: "Variable", type: "amt", sum: true },
      { key: "kstar", label: "Cost element" }, { key: "ccomp", label: "Comp.", type: "int" }] }));
    toolbar([{ label: "Show", key: "F8", onClick: () => show() }, e.status !== "FR" ? { label: "Mark & release (CK24)", primary: true, onClick: async () => {
      if (!await confirmBox("Release cost estimate", `Release estimate ${e.id}? The standard price of ${e.matnr} becomes ${fmtAmt(e.unit_cost)} and the stock is revalued.`, "Release")) return;
      const r = await run(() => api("/api/co/ck24", { id: e.id })); if (r) { msg("S", r.message); show(e.id); } } } : null]);
  };
  execBar(() => show());
  show(params.id);
}});

register("CK24", { title: "Price Update: Mark & Release Standard Price", async render(app) {
  const o = out(); app.append(o);
  const exec = async () => {
    const rows = await run(() => api("/api/co/estimates"));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: "Cost estimates", rows, columns: [
      { key: "id", label: "Estimate", link: r => go("CK13N", { id: r.id }) }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
      { key: "kadky", label: "Costing date", type: "date" }, { key: "losgr", label: "Lot size", type: "qty" }, { key: "total", label: "Total", type: "amt" },
      { key: "unit_cost", label: "Per unit", type: "amt" },
      { key: "status", label: "Status", render: r => badge(r.status, r.status === "FR" ? "U" : "Q") },
      { key: "x", label: "", render: r => r.status === "FR" ? h("span.muted", null, "current standard") : h("a", { href: "#", on: { click: async e => {
        e.preventDefault(); const x = await run(() => api("/api/co/ck24", { id: r.id })); if (x) { msg("S", x.message); exec(); } } } }, "Release") }] }));
  };
  execBar(exec); exec();
}});

// ================================================================== period-end (orders)
function orderRun(code, path, title, cols, note, withTest) {
  register(code, { title, async render(app, params) {
    await meta();
    const pf = periodFields(params);
    const a = inp({ list: "dl-aufnr", w: "m", ph: "blank = all" });
    const test = h("input", { type: "checkbox", checked: !!withTest });
    const o = out();
    app.append(panel("Parameters", grid(...pf.fields, field("Order", a),
      withTest !== undefined ? field("Processing", h("label.checkbox", null, test, "Test run")) : null), note ? h("div.note", null, note) : null), o);
    const exec = async () => {
      const r = await run(() => api(path, { gjahr: val(pf.y), perio: val(pf.m), aufnr: val(a), test: test.checked }));
      if (!r) return;
      o.innerHTML = "";
      o.append(alv({ title: "Result", rows: r.lines, columns: cols }));
      msg(test.checked ? "I" : "S", r.message);
    };
    execBar(exec);
  }});
}
orderRun("KGI2", "/api/co/kgi2", "Actual Overhead Calculation: Production Orders", [
  { key: "aufnr", label: "Order", link: r => go("KKBC_ORD", { id: r.aufnr }) }, { key: "matnr", label: "Material" }, { key: "row", label: "Costing sheet row" },
  { key: "base", label: "Base", type: "amt" }, { key: "pct", label: "%", type: "amt" }, { key: "amount", label: "Overhead", type: "amt", sum: true },
  { key: "kstar", label: "Cost element" }, { key: "credit", label: "Credit cost center" }],
  "Material overhead = 5 % of material costs (credit 4400), production overhead = 10 % of activity costs (credit 4300). A repeat run reverses the previous one.", true);
orderRun("KKS2", "/api/co/kks2", "Variance Calculation: Production Orders", [
  { key: "aufnr", label: "Order", link: r => go("KKBC_ORD", { id: r.aufnr }) }, { key: "matnr", label: "Material" }, { key: "wemng", label: "Delivered", type: "qty" },
  { key: "target", label: "Target costs", type: "amt", sum: true }, { key: "actual", label: "Actual costs", type: "amt", sum: true },
  { key: "variance", label: "Total variance", type: "amt", sum: true, signed: true }, { key: "price_var", label: "Price", type: "amt", sum: true },
  { key: "qty_var", label: "Quantity", type: "amt", sum: true }, { key: "res_var", label: "Resource-usage", type: "amt", sum: true },
  { key: "rem_var", label: "Remaining", type: "amt", sum: true }],
  "Only orders with status DLV (fully delivered) or TECO. Target costs = cost estimate × delivered quantity.");
orderRun("KO88", "/api/co/ko88", "Actual Settlement: Orders", [
  { key: "aufnr", label: "Order", link: r => go("KKBC_ORD", { id: r.aufnr }) }, { key: "note", label: "Description" },
  { key: "receiver", label: "Receiver" }, { key: "amount", label: "Amount", type: "amt", sum: true, signed: true }],
  "Production orders settle their variance to CO-PA (value field vv080). Internal orders settle to their cost center. Orders not yet delivered stay as work in process.", true);
register("CO88", { title: "Actual Settlement: Production Orders", render: () => go("KO88") });

// ================================================================== CO-PA
register("VF01", { title: "Create Billing Document (Sales, Delivery & Billing)", async render(app) {
  await meta();
  const k = inp({ list: "dl-kunnr", upper: true, w: "m" }), d = inp({ type: "date", value: today(), w: "m" });
  const items = [{ matnr: "FG-3001", qty: "", price: "4200", disc: "0", lgort: "0003" }];
  const box = h("div.panel");
  app.append(panel("Header", grid(field("Customer", k, { req: true }), field("Billing date", d))), box,
    h("div.note", null, "One step: goods issue 601 (FIFO, cost of sales at standard price) → FI revenue → CO-PA line item with cost component split."));
  const draw = () => {
    box.innerHTML = "";
    const tb = h("tbody");
    items.forEach((it, i) => {
      const s = key => e => { it[key] = e.target.value; };
      tb.append(h("tr", null, h("td.ln", null, String((i + 1) * 10)), h("td", null, inp({ value: it.matnr, list: "dl-mat", upper: true, w: "m", oninput: s("matnr") })),
        h("td", null, inp({ value: it.qty, w: "s", oninput: s("qty") })), h("td", null, inp({ value: it.price, w: "m", oninput: s("price") })),
        h("td", null, inp({ value: it.disc, w: "s", oninput: s("disc") })), h("td", null, inp({ value: it.lgort, w: "s", upper: true, oninput: s("lgort") })),
        h("td", null, h("button.alv-tb-btn", { type: "button", on: { click: () => { items.splice(i, 1); draw(); } } }, "✕"))));
    });
    box.append(h("div.panel-head", null, "Items", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: () => { items.push({ matnr: "", qty: "", price: "", disc: "0", lgort: "0003" }); draw(); } } }, "+ Item")),
      h("div.items-wrap", null, h("table.grid.items", null, h("thead", null, h("tr", null, ["Item", "Material", "Quantity", "Price / unit", "Discount %", "SLoc", ""].map(x => h("th", null, x)))), tb)));
  };
  draw();
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/vf01", { kunnr: up(k), fkdat: d.value, items: items.filter(i => i.matnr).map(i => ({ ...i, werks: "1000" })) }));
    if (r) { msgLink("S", r.message, "Profitability (KE30)", "KE30"); items.forEach(i => { i.qty = ""; }); draw(); } } }]);
}});

register("VF03", { title: "Billing Documents", async render(app) {
  const o = out(); app.append(o);
  const rows = await run(() => api("/api/co/billing"));
  if (!rows) return;
  const flat = [];
  for (const b of rows) for (const i of b.items) flat.push({ ...i, kunnr: b.kunnr, name: b.name, fkdat: b.fkdat, mblnr: b.mblnr, mjahr: b.mjahr, belnr: b.belnr });
  o.append(alv({ title: "Billing items", rows: flat, columns: [
    { key: "vbeln", label: "Billing doc." }, { key: "posnr", label: "Item", type: "int" }, { key: "fkdat", label: "Date", type: "date" },
    { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "matnr", label: "Material" },
    { key: "fkimg", label: "Qty", type: "qty", sum: true }, { key: "price", label: "Price", type: "amt" }, { key: "gross", label: "Gross", type: "amt", sum: true },
    { key: "disc_pct", label: "Disc %", type: "amt" }, { key: "disc", label: "Discount", type: "amt", sum: true }, { key: "net", label: "Net", type: "amt", sum: true },
    { key: "cogs", label: "COGS", type: "amt", sum: true }, { key: "mblnr", label: "Goods issue", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) },
    { key: "belnr", label: "Acc. doc." }] }));
}});

register("KE11", { title: "Sales and Profit Planning (CO-PA)", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const k = inp({ list: "dl-kunnr", upper: true, w: "m" }), m = inp({ list: "dl-mat", upper: true, w: "m" });
  const q = inp({ w: "s" }), p = inp({ w: "m" }), d = inp({ value: "0", w: "s" });
  const o = out();
  app.append(panel("Planning level: customer / product / period", grid(...pf.fields, field("Customer", k, { req: true }), field("Product", m, { req: true }),
    field("Sales quantity", q, { req: true }), field("Price / unit", p, { req: true }), field("Discount %", d)),
    h("div.note", null, "Plan revenue, discount and cost of sales (valued with the standard cost estimate) are written as CO-PA plan line items.")), o);
  const show = async () => {
    const rows = await run(() => api(`/api/co/ke11?gjahr=${val(pf.y)}&perio=${val(pf.m)}`));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: "Sales plan", rows, onRow: r => { k.value = r.kunnr; m.value = r.matnr; q.value = r.qty; p.value = r.price; d.value = r.disc_pct; }, columns: [
      { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "matnr", label: "Product" }, { key: "maktx", label: "Description" },
      { key: "qty", label: "Qty", type: "qty", sum: true }, { key: "price", label: "Price", type: "amt" }, { key: "disc_pct", label: "Disc %", type: "amt" },
      { key: "revenue", label: "Gross revenue", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Show", key: "F8", onClick: show }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/ke11", { gjahr: val(pf.y), perio: val(pf.m), kunnr: up(k), matnr: up(m), qty: val(q), price: val(p), disc: val(d) }));
    if (r) { msg("S", r.message + " - run KEU5 (plan) to update planned cost center costs in CO-PA"); show(); } } }]);
  show();
}});

register("KE30", { title: "Execute Profitability Report", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const pt = inp({ value: params.perio || CO.sample.perio, w: "s" });
  const drill = sel([["", "(none - total)"], ...Object.entries(CO.characteristics)], params.drill || "", { w: "l" });
  const fm = inp({ value: params.matnr || "", list: "dl-mat", upper: true, w: "m" }), fk = inp({ value: params.kunnr || "", list: "dl-kunnr", upper: true, w: "m" });
  const fr = sel([["", "(all)"], ...Object.entries(CO.regions)], "", { w: "m" }), fg = sel([["", "(all)"], ...Object.entries(CO.customer_groups)], "", { w: "m" });
  const o = out();
  app.append(panel("Selection - operating concern " + CO.erkrs + ", form: contribution margin scheme", grid(pf.fields[0], field("From period", pf.m), field("To period", pt),
    field("Drill-down by", drill), field("Product", fm), field("Customer", fk), field("Region", fr), field("Customer group", fg))), o);
  const exec = async () => {
    const qs = `gjahr=${val(pf.y)}&pfrom=${val(pf.m)}&pto=${val(pt)}&drill=${drill.value}&matnr=${up(fm)}&kunnr=${up(fk)}&region=${fr.value}&kdgrp=${fg.value}`;
    const d = await run(() => api("/api/co/rep/ke30?" + qs));
    if (!d) return;
    o.innerHTML = "";
    const labels = d.drill.map(x => x === "#" ? "# Not assigned" : drill.value === "kunnr" ? `${x} ${(CO.customers.find(c => c.kunnr === x) || {}).name || ""}` :
      drill.value === "region" ? `${x} ${CO.regions[x] || ""}` : drill.value === "kdgrp" ? `${x} ${CO.customer_groups[x] || ""}` : x);
    const rows = d.rows.map(r => ({ ...r, by: Object.fromEntries(d.drill.map((k, i) => [labels[i], (r.by || {})[k]])) }));
    o.append(h("div.alv", null, h("div.alv-toolbar", null, h("span.title", null, `Contribution margin P&L ${mon(val(pf.y), val(pf.m))}${val(pt) !== val(pf.m) ? " - " + mon(val(pf.y), val(pt)) : ""}`),
      h("button.alv-tb-btn", { type: "button", on: { click: () => App.exportRows({ exportName: "KE30", columns: [{ key: "text", label: "Line" }, { key: "actual", label: "Actual" }, { key: "plan", label: "Plan" },
        { key: "variance", label: "Variance" }, { key: "var_pct", label: "Var %" }, ...labels.map(l => ({ key: "c_" + l, label: l }))] },
        rows.map(r => ({ ...r, ...Object.fromEntries(labels.map(l => ["c_" + l, r.by[l]])) }))) } }, "⇩ Excel"),
      h("button.alv-tb-btn", { type: "button", on: { click: () => window.print() } }, "⎙ Print"),
      h("span.count", null, `Sales qty actual ${fmtQty(d.qty_actual)} · plan ${fmtQty(d.qty_plan)}`)),
      pnlTable(rows, !!drill.value, false, labels, { a: d.qty_actual, p: d.qty_plan, by: Object.fromEntries(d.drill.map((k, i) => [labels[i], d.drill_qty[k]])) })));
    msg("S", "Report executed");
  };
  execBar(exec, [{ label: "Line items (KE24)", ghost: true, onClick: () => go("KE24") }]);
  exec();
}});

register("KE24", { title: "Display CO-PA Line Items", async render(app, params) {
  await meta();
  const pf = periodFields(params), plan = sel([["0", "Actual"], ["1", "Plan"]], "0", { w: "m" });
  const o = out();
  app.append(panel("Selection", grid(...pf.fields, field("Plan/actual", plan))), o);
  const RT = { F: "Billing", C: "Settlement", D: "Assessment", B: "Direct", 0: "Plan" };
  const exec = async () => {
    const rows = await run(() => api(`/api/co/rep/ke24?gjahr=${val(pf.y)}&pfrom=${val(pf.m)}&pto=${val(pf.m)}&plikz=${plan.value}`));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: "CO-PA line items (costing-based)", rows: rows.map(r => ({ ...r, rt: `${r.vrgar} ${RT[r.vrgar] || ""}` })), columns: [
      { key: "belnr", label: "Doc." }, { key: "rt", label: "Record type" }, { key: "budat", label: "Date", type: "date" }, { key: "refdoc", label: "Reference" },
      { key: "kunnr", label: "Customer" }, { key: "matnr", label: "Product" }, { key: "region", label: "Region" }, { key: "kdgrp", label: "Cust.grp" },
      { key: "kostl", label: "Sender CC" }, { key: "aufnr", label: "Order" }, { key: "qty", label: "Qty", type: "qty", sum: true },
      ...CO.value_fields.map(([k, t]) => ({ key: k, label: `${k} ${t}`, type: "amt", sum: true }))] }));
  };
  execBar(exec); exec();
}});

register("ZCO_RECON", { title: "Reconciliation FI ↔ CO ↔ CO-PA", async render(app, params) {
  await meta();
  const pf = periodFields(params), o = out();
  app.append(panel("Period", grid(...pf.fields)), o);
  const exec = async () => {
    const r = await run(() => api(`/api/co/rep/recon?gjahr=${val(pf.y)}&perio=${val(pf.m)}`));
    if (!r) return;
    o.innerHTML = "";
    const line = (t, v, b) => h("tr" + (b ? ".sub" : ""), null, h("td", null, t), h("td.num", { class: "num " + neg(v) }, fmtAmt(v)));
    o.append(h("div.two-col", null,
      panel("Bridge: FI result = CO-PA result − costs still in CO ± FI-only items", h("table.grid.pnl", null, h("tbody", null,
        line("CO-PA operating result (EBIT)", r.copa_ebit, true),
        line("− costs still on cost centers (not yet assessed)", -r.cc_open),
        line("− costs still on orders (WIP / not settled)", -r.orders_open),
        line("± P&L postings outside CO (price differences, revaluation)", r.fi_only),
        line("± COGS difference CO-PA vs FI", r.cogs_copa - r.cogs_fi),
        line("= expected FI result", r.explained, true),
        line("FI result (revenues − expenses, from G/L)", r.fi_result, true),
        line("Difference", r.difference, true))),
        h("div", { style: { marginTop: "12px", fontSize: "15px" }, class: r.ok ? "pos" : "neg" },
          r.ok ? "✔ Reconciled to the cent" : "✖ Not reconciled - check the open items")),
      h("div", null, alv({ title: "FI profit & loss accounts", rows: r.fi_pnl, columns: [
        { key: "hkont", label: "G/L account" }, { key: "txt", label: "Name" }, { key: "co", label: "CO relevance" },
        { key: "balance", label: "Balance (debit +)", type: "amt", sum: true, signed: true }] }))),
    h("div", { style: { height: "12px" } }),
    alv({ title: "CO-PA value fields", rows: r.value_fields, columns: [{ key: "vv", label: "Value field" }, { key: "text", label: "Name" }, { key: "value", label: "Value", type: "amt" }] }),
    r.cc_detail.length ? alv({ title: "Cost centers with a balance", rows: r.cc_detail, columns: [{ key: "kostl", label: "Cost center" }, { key: "name", label: "Name" }, { key: "balance", label: "Balance", type: "amt", sum: true }] }) : null);
    msg(r.ok ? "S" : "W", r.ok ? "FI and CO-PA are reconciled" : "Difference found");
  };
  execBar(exec); exec();
}});

// ================================================================== CCA reports
register("S_ALR_87013611", { title: "Cost Centers: Actual/Plan/Variance", async render(app, params) {
  await meta();
  const y = inp({ value: params.gjahr || CO.sample.gjahr, w: "s" }), pfr = inp({ value: params.pfrom || CO.sample.perio, w: "s" }), pto = inp({ value: params.pto || CO.sample.perio, w: "s" });
  const k = ccIn(params.kostl || ""), g = inp({ value: params.kostl ? "" : (params.khinr || "H1000"), list: "dl-khinr", upper: true, w: "m" });
  const o = out();
  app.append(panel("Selection - version 0", grid(field("Fiscal year", y), field("From period", pfr), field("To period", pto),
    field("Cost center(s)", k, { hint: "or a group →" }), field("Cost center group", g))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/co/rep/cc?gjahr=${val(y)}&pfrom=${val(pfr)}&pto=${val(pto)}&kostl=${up(k)}&khinr=${up(k) ? "" : up(g)}`));
    if (!d) return;
    o.innerHTML = "";
    o.append(h("div.note", { style: { marginBottom: "8px" } }, "Cost centers: " + d.cost_centers.map(c => `${c.kostl} ${c.name}`).join(" · ")),
      alv({ title: `Actual / plan / variance ${mon(val(y), val(pfr))}${val(pto) !== val(pfr) ? " - " + mon(val(y), val(pto)) : ""}`, rows: d.rows, columns: [
        { key: "section", label: "Section" }, { key: "kstar", label: "Cost element", link: r => go("KSB1", { kstar: r.kstar, obj: up(k), pfrom: val(pfr), pto: val(pto) }) },
        { key: "ktext", label: "Name" }, { key: "katyp", label: "Cat.", type: "int" },
        { key: "actual", label: "Actual", type: "amt", sum: true, signed: true }, { key: "plan", label: "Plan", type: "amt", sum: true, signed: true },
        { key: "variance", label: "Variance", type: "amt", sum: true, cls: r => r.variance > 0 ? "neg" : r.variance < 0 ? "pos" : "" },
        { key: "var_pct", label: "Var %", render: r => h("span", null, pctTxt(r.var_pct)) }] }));
  };
  execBar(exec, [{ label: "Target/actual", ghost: true, onClick: () => go("S_ALR_87013625", { kostl: up(k) || "4100" }) }]);
  exec();
}});

register("S_ALR_87013625", { title: "Cost Centers: Actual/Target/Variance", async render(app, params) {
  await meta();
  const pf = periodFields(params), k = ccIn(params.kostl || "4100"), o = out();
  app.append(panel("Selection", grid(...pf.fields, field("Cost center", k, { req: true }))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/co/rep/target?gjahr=${val(pf.y)}&perio=${val(pf.m)}&kostl=${up(k)}`));
    if (!d) return;
    o.innerHTML = "";
    o.append(h("div.panel", null, h("div.obj-header", null, [["Cost center", `${d.kostl} ${ccName(d.kostl)}`], ["Operating rate", d.rate + " %"],
      ["Logic", "Target = plan fixed + plan variable × operating rate"]].map(([a, b]) => h("div.attr", null, h("span.k", null, a), h("span.v", null, b))))));
    if (d.activities.length) o.append(alv({ compact: true, rows: d.activities, columns: [
      { key: "lstar", label: "Activity" }, { key: "plan_qty", label: "Plan qty", type: "qty" }, { key: "actual_qty", label: "Actual qty", type: "qty" },
      { key: "capacity", label: "Capacity", type: "qty" }, { key: "rate", label: "Op. rate %", type: "amt" }, { key: "price_fix", label: "Price fix", type: "amt" },
      { key: "price_var", label: "Price var", type: "amt" }] }), h("div", { style: { height: "10px" } }));
    o.append(alv({ title: "Target/actual comparison", rows: d.rows, columns: [
      { key: "kstar", label: "Cost element" }, { key: "ktext", label: "Name" },
      { key: "plan_fix", label: "Plan fixed", type: "amt", sum: true }, { key: "plan_var", label: "Plan variable", type: "amt", sum: true },
      { key: "plan", label: "Plan total", type: "amt", sum: true }, { key: "target", label: "Target", type: "amt", sum: true },
      { key: "actual", label: "Actual", type: "amt", sum: true, signed: true },
      { key: "tgt_var", label: "Target/actual var.", type: "amt", sum: true, cls: r => r.tgt_var > 0 ? "neg" : r.tgt_var < 0 ? "pos" : "" },
      { key: "var_pct", label: "Var %", render: r => h("span", null, pctTxt(r.var_pct)) }] }),
    h("div.note", { style: { marginTop: "8px" } }, "Before KEU5 the balance shows the under/over absorption. After KEU5 (assessment to CO-PA) the cost center is zero."));
  };
  execBar(exec); exec();
}});

register("KSB1", { title: "Display Actual/Plan Line Items (KSB1 / KSBP / KOB1)", async render(app, params) {
  await meta();
  const pf = periodFields(params);
  const pt = inp({ value: params.pto || CO.sample.perio, w: "s" });
  if (params.pfrom) pf.m.value = params.pfrom;
  const ot = sel([["KS", "Cost centers (KSB1)"], ["OR", "Orders (KOB1)"]], params.otype || "KS", { w: "l" });
  const ob = inp({ value: params.obj || "", upper: true, w: "m", ph: "all" }), ce = inp({ value: params.kstar || "", list: "dl-kstar", w: "m" });
  const wt = sel([["04", "Actual"], ["01", "Plan (KSBP)"]], params.wrttp || "04", { w: "m" });
  const o = out();
  app.append(panel("Selection", grid(pf.fields[0], field("From period", pf.m), field("To period", pt), field("Objects", ot), field("Object(s)", ob, { hint: "comma list" }),
    field("Cost element", ce), field("Value type", wt))), o);
  const exec = async () => {
    const rows = await run(() => api(`/api/co/rep/lineitems?gjahr=${val(pf.y)}&pfrom=${val(pf.m)}&pto=${val(pt)}&otype=${ot.value}&obj=${up(ob)}&kstar=${val(ce)}&wrttp=${wt.value}`));
    if (!rows) return;
    o.innerHTML = "";
    o.append(alv({ title: "Line items", rows, rowClass: r => r.stflg ? ".canceled" : "", columns: [
      { key: "object", label: ot.value === "KS" ? "Cost center" : "Order" }, { key: "kstar", label: "Cost element" }, { key: "ktext", label: "Cost element name" },
      { key: "wtg", label: "Value", type: "amt", sum: true, signed: true }, { key: "wkf", label: "Fixed", type: "amt", sum: true },
      { key: "wkv", label: "Variable", type: "amt", sum: true }, { key: "qty", label: "Quantity", type: "qty" }, { key: "meinh", label: "Un" },
      { key: "lstar", label: "Activity" }, { key: "parob", label: "Partner object" }, { key: "vrgng", label: "BusTr" },
      { key: "vrgng_text", label: "Business transaction" }, { key: "belnr", label: "Document", link: r => go("KSB5", { id: r.belnr }) },
      { key: "budat", label: "Date", type: "date" }, { key: "matnr", label: "Material" }, { key: "refbn", label: "Reference" },
      { key: "sgtxt", label: "Text" }, { key: "usnam", label: "User" }] }));
    msg("S", `${rows.length} line items`);
  };
  execBar(exec); exec();
}});
register("KSBP", { title: "Cost Centers: Plan Line Items", render: () => go("KSB1", { wrttp: "01" }) });
register("KOB1", { title: "Orders: Actual Line Items", render: () => go("KSB1", { otype: "OR" }) });
})();
