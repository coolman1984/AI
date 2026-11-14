/* NERP - Controlling in depth: configuration (ZCO_CONF), period lock (OKP1), closing
   management (ZCO_CLOSE), budget and availability control (ZBUD_PROF, ZBUD01, ZBUD02,
   ZBUD_REL, ZBUD_RPT), sales adjustment (KE21N), accruals (ZACR_DEF, ZACR_RUN, ZACR_RPT),
   plan copy (KP97) and profit simulation (ZCO_SIM). */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, field, inp, sel, val, up, alv, register, go, toolbar, fmtAmt, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const ypFields = params => { const n = now(); return { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }; };
const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not needed", ""] };

// ------------------------------------------------------------------ 1-1 ZCO_CONF
register("ZCO_CONF", { title: "Controlling - Basic Configuration (display)", async render(app) {
  const c = await run(() => api("/api/co/config")); if (!c) return;
  app.append(h("div.kpis", null, kpi("Controlling area", c.kokrs, c.kokrs_name), kpi("Company code", c.bukrs, c.currency),
    kpi("Operating concern", c.erkrs, "costing-based CO-PA"), kpi("Fiscal year variant", "K4", c.fiscal_variant),
    kpi("Budget control", `${c.budget_profile.warn_pct} % / ${c.budget_profile.err_pct} %`, "warning / refused (ZBUD_PROF)")),
  h("div.ams-cols", null,
    alv({ rows: c.versions, title: "Versions", columns: [{ key: "version", label: "Version" }, { key: "text", label: "Text" }] }),
    alv({ rows: c.ce_categories, title: "Cost element categories", columns: [{ key: "katyp", label: "Cat." }, { key: "text", label: "Text" }] }),
    alv({ rows: c.cc_categories, title: "Cost center categories", columns: [{ key: "kosar", label: "Cat." }, { key: "text", label: "Text" }] }),
    alv({ rows: c.order_types, title: "Order types", columns: [{ key: "auart", label: "Type" }, { key: "text", label: "Text" }] }),
    alv({ rows: c.vrgng, title: "Business transactions (CO)", columns: [{ key: "vrgng", label: "Transaction" }, { key: "text", label: "Text" }] }),
    alv({ rows: c.cost_components, title: "Cost component structure 01", columns: [{ key: "comp", label: "No." }, { key: "text", label: "Cost component" }] }),
    alv({ rows: c.value_fields, title: "CO-PA value fields", columns: [{ key: "vv", label: "Field" }, { key: "text", label: "Text" }] }),
    alv({ rows: c.characteristics, title: "CO-PA characteristics", columns: [{ key: "char", label: "Field" }, { key: "text", label: "Text" }] }),
    alv({ rows: c.number_ranges, title: "Number ranges", columns: [{ key: "object", label: "Object" }, { key: "start", label: "From", type: "int" }] }),
    alv({ rows: Object.entries(c.counts).map(([k, n]) => ({ k, n })), title: "Master data", columns: [{ key: "k", label: "Table" }, { key: "n", label: "Records", type: "int" }] })));
} });

// ------------------------------------------------------------------ OKP1 period lock
register("OKP1", { title: "Controlling Period Lock", async render(app, params) {
  const f = ypFields(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))),
    note("A locked period refuses every actual CO posting (FI / MM postings with a cost center or order, CO allocations, closing runs) - lock the month when the closing is finished (ZCO_CLOSE)."), out);
  const load = async () => {
    const d = await run(() => api(`/api/co/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    const locked = new Set(d.locks.map(l => l.perio));
    out.append(alv({ rows: Array.from({ length: 12 }, (_, i) => { const l = d.locks.find(x => x.perio === i + 1) || {}; return { perio: i + 1, st: locked.has(i + 1) ? "🔒 Locked" : "Open", usnam: l.usnam || "", ts: l.ts || "" }; }),
      title: `Actual postings ${val(f.y)}`, columns: [{ key: "perio", label: "Period", type: "int" }, { key: "st", label: "Status" }, { key: "usnam", label: "By" }, { key: "ts", label: "When" }] }));
  };
  const set = async on => { const r = await run(() => api("/api/co/period_lock", { gjahr: val(f.y), perio: val(f.p), lock: on })); if (r) { msg("S", r.message); load(); } };
  toolbar([{ label: "Display", key: "F8", onClick: load }, { label: "Lock period", primary: true, onClick: () => set(true) }, { label: "Unlock period", onClick: () => set(false) }]);
  load();
} });

// ------------------------------------------------------------------ 1-5 ZCO_CLOSE
register("ZCO_CLOSE", { title: "Controlling - Closing Management", async render(app, params) {
  const f = ypFields(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/co/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Closing steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : ""),
      kpi("Period", d.locked ? "🔒 Locked" : "Open", d.locked ? "no more actual postings" : "lock it at the end (OKP1)")));
    out.append(alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Period-end closing - run the steps in this order",
      columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode, { gjahr: val(f.y), perio: val(f.p) }) },
        { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }));
    out.append(note("Click a transaction to run the step, then come back and press Refresh. Steps marked 'Not needed' have nothing to do in this period (e.g. no accrual rules)."));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 2-x budget
register("ZBUD_PROF", { title: "Budget - Availability Control Settings", async render(app) {
  const d = await run(() => api("/api/co/budget")); if (!d) return;
  const p = d.profile;
  const f = { warn: inp({ value: p.warn_pct, w: "s" }), err: inp({ value: p.err_pct, w: "s" }), po: h("input", { type: "checkbox", checked: !!p.check_po }) };
  app.append(panel("Budget profile 0001", grid(field("Warning from (% of released budget)", f.warn), field("Refused from (%)", f.err), field("Check purchase orders (commitments)", f.po))),
    note("Every cost center or internal order with a budget is checked: actual costs (FI / MM postings) and - for purchase orders - open commitments may not exceed the error limit of the released budget. Above the warning limit the posting is allowed and a warning is written to the budget log. Objects without a budget are not checked."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/budget/profile", { warn_pct: val(f.warn), err_pct: val(f.err), check_po: f.po.checked })); if (r) msg("S", r.message); } }]);
} });

function budgetScreen(title, types, intro) {
  return { title, async render(app, params) {
    const n = now();
    const f = { obj: inp({ value: params.obj || "", w: "m", list: "dl-kostl", ph: "cost center or OR+order" }), y: inp({ value: params.gjahr || n.y, w: "s" }),
      typ: sel(types.map(([k, t]) => [k, t]), types[0][0]), amt: inp({ w: "m" }), text: inp({ w: "l" }) };
    const out = h("div");
    app.append(panel(null, grid(field("Cost center / order", f.obj, { req: true }), field("Fiscal year", f.y), field("Transaction", f.typ), field("Amount (EGP)", f.amt, { req: true }), field("Text", f.text))), note(intro), out);
    const load = async () => {
      const d = await run(() => api(`/api/co/budget?gjahr=${val(f.y)}`)); if (!d) return;
      out.innerHTML = "";
      out.append(budgetTable(d.rows, `Budgets ${d.gjahr}`));
    };
    toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
      const o = up(f.obj), objnr = /^(KS|OR)/.test(o) ? o : (/^\d{7,}$/.test(o) ? "OR" + o : "KS" + o);
      const r = await run(() => api("/api/co/budget/post", { objnr, gjahr: val(f.y), typ: f.typ.value, amount: val(f.amt), text: val(f.text) }));
      if (r) { msg("S", r.message); f.amt.value = ""; load(); } } }, { label: "Budget report", onClick: () => go("ZBUD_RPT") }]);
    load();
  } };
}
function budgetTable(rows, title) {
  return alv({ rows, title, rowClass: r => r.available < 0 ? ".neg" : "", columns: [{ key: "typ", label: "Type" }, { key: "obj", label: "Object" }, { key: "name", label: "Name" },
    { key: "orig", label: "Original", type: "amt", sum: true }, { key: "supp", label: "Supplement", type: "amt", sum: true }, { key: "ret", label: "Return", type: "amt", sum: true },
    { key: "budget", label: "Budget", type: "amt", sum: true }, { key: "released", label: "Released", type: "amt", sum: true }, { key: "actual", label: "Actual", type: "amt", sum: true },
    { key: "commitment", label: "Commitment", type: "amt", sum: true }, { key: "available", label: "Available", type: "amt", sum: true },
    { key: "used_pct", label: "Used %", render: r => r.used_pct === null ? "-" : badge(r.used_pct + " %", r.used_pct > 100 ? "B" : r.used_pct > 90 ? "Q" : "U") }] });
}
register("ZBUD01", budgetScreen("Budget - Original Budget", [["ORIG", "Original budget"]],
  "The original budget of the year for a cost center (e.g. 4200) or an internal order. It is spendable after the release (ZBUD_REL)."));
register("ZBUD02", budgetScreen("Budget - Supplement / Return", [["SUPP", "Supplement (more budget)"], ["RET", "Return (less budget)"]],
  "A supplement increases the budget (release it afterwards), a return gives unused budget back - only the part that is not yet spent or committed."));
register("ZBUD_REL", budgetScreen("Budget - Release", [["REL", "Release"]],
  "Only released budget can be spent. Release the whole budget at once or step by step (e.g. per quarter); the release cannot exceed the budget."));
register("ZBUD_RPT", { title: "Budget - Budget / Actual / Commitment Report", async render(app, params) {
  const y = inp({ value: params.gjahr || now().y, w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/co/budget?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    const t = d.rows.reduce((a, r) => ({ b: a.b + r.released, u: a.u + r.actual + r.commitment }), { b: 0, u: 0 });
    out.append(h("div.kpis", null, kpi("Released budget", fmtAmt(t.b)), kpi("Actual + commitment", fmtAmt(t.u)), kpi("Available", fmtAmt(t.b - t.u), "", t.b - t.u < 0 ? "neg" : "pos"),
      kpi("Control", `${d.profile.warn_pct} % / ${d.profile.err_pct} %`, "warning / refused")),
      budgetTable(d.rows, `Budget report ${d.gjahr}`),
      alv({ rows: d.log, title: "Budget documents and availability-control messages", columns: [{ key: "ts", label: "When" }, { key: "objnr", label: "Object" }, { key: "typ_text", label: "Transaction" },
        { key: "amount", label: "Amount", type: "amt" }, { key: "text", label: "Text" }, { key: "usnam", label: "User" }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Original budget", onClick: () => go("ZBUD01") }, { label: "Release", onClick: () => go("ZBUD_REL") }]);
  load();
} });

// ------------------------------------------------------------------ 3-1 KE21N
register("KE21N", { title: "CO-PA Line Item - Sales Adjustment", async render(app) {
  const vv = [["vv010", "Gross revenue"], ["vv020", "Sales deductions (rebate, discount)"], ["vv030", "Material costs"], ["vv100", "Sales & marketing costs"], ["vv110", "Administration costs"]];
  const f = { budat: inp({ type: "date", value: today() }), kunnr: inp({ w: "m", list: "dl-kunnr", upper: true }), matnr: inp({ w: "m", upper: true }), text: inp({ w: "l", ph: "e.g. year-end rebate" }) };
  const amts = vv.map(([k, t]) => [k, t, inp({ w: "m", ph: "0.00" })]);
  app.append(panel("Characteristics", grid(field("Posting date", f.budat), field("Customer", f.kunnr, { req: true }), field("Product", f.matnr), field("Reason (text)", f.text, { req: true }))),
    panel("Value fields (EGP; a minus reduces the field)", grid(...amts.map(([, t, i]) => field(t, i)))),
    note("A manual CO-PA line (record type B) corrects the profitability report - e.g. a year-end rebate or a quality claim agreed with the customer. It is not an FI posting, so it appears as an explained difference in the reconciliation ZCO_RECON."));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const b = { budat: f.budat.value, kunnr: up(f.kunnr), matnr: up(f.matnr), text: val(f.text) };
    amts.forEach(([k, , i]) => { if (val(i)) b[k] = val(i); });
    const r = await run(() => api("/api/co/ke21n", b)); if (r) msg("S", r.message); } }, { label: "Line items (KE24)", onClick: () => go("KE24") }]);
} });

// ------------------------------------------------------------------ 5-x accruals
register("ZACR_DEF", { title: "Accrual - Rules (annual costs per month)", async render(app, params) {
  const n = now(), out = h("div");
  const f = { text: inp({ w: "l", ph: "e.g. annual bonus" }), kostl: inp({ w: "s", list: "dl-kostl", upper: true }), hkont: inp({ w: "s", ph: "e.g. 430000" }),
    annual: inp({ w: "m" }), y: inp({ value: params.gjahr || n.y, w: "s" }) };
  app.append(panel("New rule", grid(field("Description", f.text, { req: true }), field("Cost center", f.kostl, { req: true }), field("Expense account (cost element)", f.hkont, { req: true }),
    field("Annual amount (EGP)", f.annual, { req: true }), field("Fiscal year", f.y))),
    note("Each month the run (ZACR_RUN) charges one twelfth of the annual amount to the cost center (Dr expense / Cr 190000 accrued expenses). When the real payment is made, post it against 190000."), out);
  const load = async () => {
    const d = await run(() => api(`/api/co/accruals?gjahr=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rules, title: `Accrual rules ${d.gjahr}`, columns: [{ key: "id", label: "Rule", type: "int" }, { key: "text", label: "Description" }, { key: "kostl", label: "Cost center" },
      { key: "kostl_name", label: "Name" }, { key: "hkont", label: "Expense account" }, { key: "annual", label: "Annual", type: "amt", sum: true }, { key: "active", label: "Active", render: r => r.active ? "✔" : "" }] }));
  };
  toolbar([{ label: "Save rule", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/co/accrual/rule", { text: val(f.text), kostl: up(f.kostl), hkont: val(f.hkont), annual: val(f.annual), gjahr: val(f.y) }));
    if (r) { msg("S", r.message); load(); } } }, { label: "Run accruals", onClick: () => go("ZACR_RUN") }]);
  load();
} });
register("ZACR_RUN", { title: "Accrual - Monthly Run", async render(app, params) {
  const f = ypFields(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const exec = async act => {
    if (act !== "test" && !await confirmBox("Accruals", act === "run" ? "Post the accruals of this period?" : "Reverse the accrual documents of this period?")) return;
    const r = await run(() => api("/api/co/accrual/" + act, { gjahr: val(f.y), perio: val(f.p) })); if (!r) return;
    msg("S", r.message); out.innerHTML = "";
    if (r.docs) out.append(alv({ rows: r.docs, title: r.test ? "Test run - nothing posted" : "Posted", columns: [{ key: "rule", label: "Rule", type: "int" }, { key: "text", label: "Description" },
      { key: "kostl", label: "Cost center" }, { key: "hkont", label: "Account" }, { key: "amount", label: "Amount", type: "amt", sum: true }, { key: "belnr", label: "FI document" }] }));
  };
  toolbar([{ label: "Test run", key: "F8", onClick: () => exec("test") }, { label: "Post", primary: true, onClick: () => exec("run") }, { label: "Reverse run", danger: true, onClick: () => exec("reverse") },
    { label: "Overview", onClick: () => go("ZACR_RPT") }]);
} });
register("ZACR_RPT", { title: "Accrual - Overview", async render(app, params) {
  const y = inp({ value: params.gjahr || now().y, w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/co/accruals?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rules, title: `Accrued so far ${d.gjahr}`, columns: [{ key: "id", label: "Rule", type: "int" }, { key: "text", label: "Description" }, { key: "kostl", label: "Cost center" },
      { key: "annual", label: "Annual", type: "amt", sum: true }, { key: "accrued", label: "Accrued", type: "amt", sum: true }, { key: "rest", label: "Still to accrue", type: "amt", sum: true },
      { key: "months", label: "Months", type: "int" }, { key: "periods", label: "Periods" }] }),
      alv({ rows: d.runs, title: "Runs", columns: [{ key: "perio", label: "Period", type: "int" }, { key: "text", label: "Rule" }, { key: "kostl", label: "Cost center" },
        { key: "amount", label: "Amount", type: "amt", sum: true }, { key: "belnr", label: "FI document" }, { key: "reversed", label: "Reversed", render: r => r.reversed ? "✔" : "" }, { key: "usnam", label: "User" }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ KP97 plan copy
register("KP97", { title: "Copy Cost Center Plan", async render(app) {
  const n = now();
  const f = { from: inp({ value: n.y, w: "s" }), to: inp({ value: n.y + 1, w: "s" }), pct: inp({ value: "0", w: "s" }) };
  app.append(panel(null, grid(field("From fiscal year", f.from), field("To fiscal year", f.to), field("Change %", f.pct))),
    note("Copies the primary cost plan (KP06) and the activity plan (KP26) of every cost center, changed by the percentage (e.g. 10 = +10 % inflation). The target plan of the same cost centers / cost elements is replaced. Afterwards calculate the activity prices (KSPI)."));
  toolbar([{ label: "Copy", primary: true, onClick: async () => {
    if (!await confirmBox("Copy plan", `Copy the plan ${val(f.from)} to ${val(f.to)} (${val(f.pct)} %)?`)) return;
    const r = await run(() => api("/api/co/kp97", { from_year: val(f.from), to_year: val(f.to), pct: val(f.pct) })); if (r) msg("S", r.message); } }]);
} });

// ------------------------------------------------------------------ E-1 ZCO_SIM
register("ZCO_SIM", { title: "Profit Simulation (what if)", async render(app, params) {
  const n = now();
  const f = { y: inp({ value: params.gjahr || n.y, w: "s" }), pf: inp({ value: "1", w: "s" }), pt: inp({ value: "12", w: "s" }), ver: sel([["ACT", "Actual"], ["PLAN", "Plan"]], "ACT"),
    price: inp({ value: "0", w: "s" }), volume: inp({ value: "0", w: "s" }), material: inp({ value: "0", w: "s" }), labor: inp({ value: "0", w: "s" }), overhead: inp({ value: "0", w: "s" }) };
  const out = h("div");
  app.append(panel("Basis", grid(field("Fiscal year", f.y), field("Period from", f.pf), field("Period to", f.pt), field("Version", f.ver))),
    panel("Drivers (% change)", grid(field("Sales price %", f.price), field("Volume %", f.volume), field("Material price %", f.material), field("Labor %", f.labor), field("Fixed overhead %", f.overhead))),
    note("Nothing is posted. Volume moves sales and variable costs; fixed costs stay. Try e.g. price -5 % and volume +10 % to see if a price cut pays off."), out);
  const exec = async () => {
    const q = new URLSearchParams({ gjahr: val(f.y), pfrom: val(f.pf), pto: val(f.pt), version: f.ver.value, price: val(f.price), volume: val(f.volume), material: val(f.material), labor: val(f.labor), overhead: val(f.overhead) });
    const d = await run(() => api("/api/co/simulation?" + q)); if (!d) return;
    msg("S", d.message); out.innerHTML = "";
    const op = d.rows.find(r => r.node === "OP");
    out.append(h("div.kpis", null, kpi("Operating profit - basis", fmtAmt(op.base), d.margin_base === null ? "" : `margin ${d.margin_base} %`),
      kpi("Operating profit - simulated", fmtAmt(op.sim), d.margin_sim === null ? "" : `margin ${d.margin_sim} %`, op.sim >= op.base ? "pos" : "neg"),
      kpi("Change", fmtAmt(op.diff), op.pct === null ? "" : `${op.pct} %`, op.diff >= 0 ? "pos" : "neg"),
      kpi("Break-even volume", d.breakeven_volume_pct === null ? "-" : `${d.breakeven_volume_pct} %`, "of the basis volume")),
      alv({ rows: d.rows, title: `P&L ${d.version} ${d.gjahr} ${d.pfrom}-${d.pto}`, rowClass: r => r.kind === "t" ? ".total" : "",
        columns: [{ key: "text", label: "Line" }, { key: "base", label: "Basis", type: "amt" }, { key: "sim", label: "Simulated", type: "amt" }, { key: "diff", label: "Change", type: "amt" }, { key: "pct", label: "%", render: r => r.pct === null ? "" : r.pct + " %" }] }));
  };
  toolbar([{ label: "Simulate", key: "F8", primary: true, onClick: exec }]);
  exec();
} });
})();
