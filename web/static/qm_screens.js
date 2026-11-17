/* NERP - Quality management (inspection plan, lots, results, usage decision, notifications,
   vendor quality) and plant maintenance of the factory machines (machines, preventive plans,
   breakdowns, orders with spare parts and hours, MTBF / MTTR). */
"use strict";
(() => {
const { h, api, msg, run, ask, confirmBox, field, inp, sel, val, alv, register, go, toolbar, fmtAmt, fmtQty, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const first = () => today().slice(0, 8) + "01";
const btn = (label, fn) => h("button.btn", { type: "button", on: { click: fn } }, label);
const back = n => { const d = new Date(today() + "T12:00:00"); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };
const range = (params, days) => ({ d1: inp({ type: "date", value: params.d1 || (days ? back(days) : first()) }), d2: inp({ type: "date", value: params.d2 || today() }) });
const LST = { OPEN: ["Open", "Q"], RESULTS: ["Results", "Q"], UD: ["Decided", "U"], CANCELLED: ["Cancelled", ""] };
const UD = { A: ["Accepted", "U"], R: ["Rejected", "B"], P: ["Partly accepted", "Q"] };
const lotBadge = r => r.status === "UD" ? badge(...(UD[r.ud_code] || ["Decided", "U"])) : badge(...(LST[r.status] || [r.status, ""]));
const lotCols = [{ key: "prueflos", label: "Lot", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); go("QA11", { prueflos: r.prueflos }); } } }, r.prueflos) },
  { key: "created", label: "Created", type: "date" }, { key: "origin_text", label: "Origin" }, { key: "matnr", label: "Material" }, { key: "qty", label: "Quantity", type: "qty" },
  { key: "vendor", label: "Vendor" }, { key: "ebeln", label: "PO / order", render: r => r.ebeln || r.aufnr || "" }, { key: "age", label: "Days", type: "int" },
  { key: "status", label: "Status", render: lotBadge }, { key: "qty_rej", label: "Rejected", type: "qty" }];

// ------------------------------------------------------------------ 1-1 ZQM_COCKPIT
register("ZQM_COCKPIT", { title: "Quality Cockpit", async render(app, params) {
  const f = range(params, 30), out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/qm/cockpit?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Lots in inspection", d.open_lots, `${fmtQty(d.stock_in_qi)} in inspection stock`, d.overdue_lots ? "neg" : ""),
      kpi("Waiting > 3 days", d.overdue_lots, "lots", d.overdue_lots ? "neg" : "pos"),
      kpi("Accepted lots", d.accept_pct === null ? "-" : d.accept_pct + " %", `${d.decided} decisions`, d.accept_pct !== null && d.accept_pct < 95 ? "neg" : "pos"),
      kpi("Rejected ppm", d.ppm, "parts per million", d.ppm > 5000 ? "neg" : "pos"),
      kpi("Open complaints / NCR", d.open_notifs, `${d.overdue_notifs} overdue`, d.overdue_notifs ? "neg" : "")),
      alv({ rows: d.lots, title: "Lots waiting for the usage decision", columns: lotCols }),
      alv({ rows: d.pareto, title: "Defects (Pareto)", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Defect" }, { key: "count", label: "Lots", type: "int" }, { key: "qty", label: "Quantity", type: "qty" }] }),
      alv({ rows: d.vendors, title: "Vendor quality", columns: [{ key: "name", label: "Vendor" }, { key: "lots", label: "Lots", type: "int" }, { key: "accept_pct", label: "Accepted lots %" },
        { key: "ppm", label: "ppm", type: "int" }, { key: "complaints", label: "Complaints", type: "int" }, { key: "score", label: "Score", type: "int" },
        { key: "grade", label: "Grade", render: r => badge(r.grade, r.grade === "A" ? "U" : r.grade === "B" ? "Q" : "B") }] }),
      note("A goods receipt of a material with 'inspection at goods receipt' goes to quality-inspection stock: it cannot be used or sold until the usage decision (QA11) releases it."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Inspection lots", onClick: () => go("QA32") }, { label: "Notifications", onClick: () => go("QM01") }]);
  load();
} });

// ------------------------------------------------------------------ 1-2 QP01
register("QP01", { title: "Inspection Plan (characteristics per material)", async render(app, params) {
  const m = inp({ value: params.matnr || "", w: "m" }), out = h("div"), list = h("div");
  app.append(panel(null, grid(field("Material", m))), out, list);
  const rowsBox = h("tbody");
  const addRow = c => rowsBox.append(h("tr", null, h("td", null, inp({ value: c.name || "", w: "l" })),
    h("td", null, sel([["N", "Measured value"], ["A", "OK / not OK"]], c.kind || "N")), h("td", null, inp({ value: c.lsl ?? "", w: "s" })),
    h("td", null, inp({ value: c.usl ?? "", w: "s" })), h("td", null, inp({ value: c.unit || "", w: "s" }))));
  const load = async () => {
    const d = await run(() => api(`/api/qm/plan?matnr=${encodeURIComponent(val(m))}`)); if (!d) return;
    out.innerHTML = ""; list.innerHTML = ""; rowsBox.innerHTML = "";
    list.append(alv({ rows: d.materials, title: "Materials with quality inspection", columns: [{ key: "matnr", label: "Material", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); m.value = r.matnr; load(); } } }, r.matnr) },
      { key: "maktx", label: "Description" }, { key: "insmk", label: "Inspection at GR", render: r => r.insmk ? badge("Active", "U") : "" }, { key: "chars", label: "Characteristics", type: "int" }] }));
    if (!d.matnr) return;
    const act = h("input", { type: "checkbox" }); act.checked = d.active;
    (d.chars.length ? d.chars : [{}, {}]).forEach(addRow);
    out.append(panel(`Characteristics of ${d.matnr}`, h("table.grid", null, h("thead", null, h("tr", null, ...["Characteristic", "Type", "Lower limit", "Upper limit", "Unit"].map(x => h("th", null, x)))), rowsBox),
      h("div", null, btn("+ Characteristic", () => addRow({})), " ", h("label", null, act, " Inspection at goods receipt (stock goes to quality inspection)"))),
      note("Measured value: the result must lie between the limits. OK / not OK: a visual or document check."));
    out._act = act;
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Save", key: "Ctrl+S", onClick: async () => {
    const chars = [...rowsBox.children].map(tr => { const x = tr.querySelectorAll("input,select"); return { name: x[0].value, kind: x[1].value, lsl: x[2].value, usl: x[3].value, unit: x[4].value }; });
    const r = await run(() => api("/api/qm/plan", { matnr: val(m), chars, active: out._act ? out._act.checked : undefined })); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 2-1 QA32
register("QA32", { title: "Inspection Lots (worklist)", async render(app, params) {
  const f = { st: sel([["open", "Open (waiting)"], ["UD", "Decided"], ["", "All"]], params.status ?? "open"), m: inp({ value: params.matnr || "", w: "m" }) }, out = h("div");
  app.append(panel(null, grid(field("Status", f.st), field("Material", f.m))), out);
  const load = async () => {
    const d = await run(() => api(`/api/qm/lots?status=${f.st.value}&matnr=${encodeURIComponent(val(f.m))}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Inspection lots", columns: lotCols.concat([{ key: "x", label: "", render: r => r.status === "OPEN" || r.status === "RESULTS" ? btn("Results / decision", () => go("QA11", { prueflos: r.prueflos })) : "" }]) }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Inspect stock (QA01)", onClick: () => go("QA01") }]);
  load();
} });

// ------------------------------------------------------------------ 2-2 QA11 results + usage decision
register("QA11", { title: "Results and Usage Decision", async render(app, params) {
  const lotIn = inp({ value: params.prueflos || "", w: "m" }), out = h("div");
  app.append(panel(null, grid(field("Inspection lot", lotIn))), out);
  const load = async () => {
    if (!val(lotIn)) { out.innerHTML = ""; out.append(note("Enter an inspection lot or choose one in QA32.")); return; }
    const d = await run(() => api(`/api/qm/lot?prueflos=${encodeURIComponent(val(lotIn))}`)); if (!d) return;
    out.innerHTML = "";
    const open = d.status === "OPEN" || d.status === "RESULTS";
    out.append(h("div.kpis", null, kpi("Material", d.matnr, d.maktx || ""), kpi("Quantity", fmtQty(d.qty), d.meins || ""), kpi("Origin", d.origin_text, d.vendor || d.aufnr || ""),
      kpi("Status", d.status === "UD" ? (UD[d.ud_code] || ["Decided"])[0] : d.status_text, d.ud_date || d.created, d.status === "UD" ? (d.ud_code === "A" ? "pos" : "neg") : "")));
    const inputs = {};
    out.append(alv({ rows: d.chars, title: "Characteristics", columns: [{ key: "seq", label: "No.", type: "int" }, { key: "name", label: "Characteristic" },
      { key: "lim", label: "Limits", render: r => r.kind === "A" ? "OK / not OK" : `${r.lsl ?? "-"} … ${r.usl ?? "-"} ${r.unit || ""}` },
      { key: "value", label: "Result", render: r => { if (!open) return r.kind === "A" ? (r.ok ? "OK" : r.ok === 0 ? "NOK" : "") : (r.value ?? "");
        const e = r.kind === "A" ? sel([["", ""], ["OK", "OK"], ["NOK", "Not OK"]], r.ok === 1 ? "OK" : r.ok === 0 ? "NOK" : "") : inp({ value: r.value ?? "", w: "s" }); inputs[r.seq] = e; return e; } },
      { key: "valuation", label: "Valuation", render: r => r.valuation ? badge(r.valuation === "A" ? "In tolerance" : "Out of tolerance", r.valuation === "A" ? "U" : "B") : "" }] }));
    if (d.defects.length) out.append(alv({ rows: d.defects, title: "Defects", columns: [{ key: "code", label: "Code" }, { key: "text_d", label: "Defect" }, { key: "qty", label: "Quantity", type: "qty" }, { key: "text", label: "Note" }] }));
    if (!open) { if (d.note) out.append(note(d.note)); return; }
    if (d.chars.length) out.append(h("div", null, btn("Save results", async () => {
      const values = {}; Object.entries(inputs).forEach(([k, e]) => { values[k] = e.value; });
      const r = await run(() => api("/api/qm/record", { prueflos: d.prueflos, values })); if (r) { msg(r.rejected ? "W" : "S", r.message); load(); } })));
    const u = { ok: inp({ value: d.qty, w: "s" }), rej: inp({ value: "0", w: "s" }), defect: sel([["", ""]].concat(Object.entries(d.defect_codes)), ""), dev: inp({ w: "l", ph: "only if accepting out-of-tolerance goods" }), note: inp({ w: "l" }) };
    out.append(panel("Usage decision", grid(field("Accepted → unrestricted stock", u.ok), field("Rejected → blocked stock", u.rej), field("Defect", u.defect), field("Deviation release (reason)", u.dev), field("Note", u.note)),
      btn("Make usage decision", async () => {
        if (!await confirmBox("Usage decision", `Accept ${val(u.ok)} and reject ${val(u.rej)} of lot ${d.prueflos}?`)) return;
        const r = await run(() => api("/api/qm/ud", { prueflos: d.prueflos, qty_ok: val(u.ok), qty_rej: val(u.rej), defect: u.defect.value, override: val(u.dev), note: val(u.note) }));
        if (r) { msg("S", r.message); load(); } }),
      note("Rejected goods go to blocked stock and a vendor complaint is opened; return them to the vendor with movement 122.")));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Worklist", onClick: () => go("QA32") }]);
  load();
} });

// ------------------------------------------------------------------ 2-3 QA01
register("QA01", { title: "Inspection of Stock (manual lot)", async render(app) {
  const f = { m: inp({ w: "m" }), l: inp({ w: "s", value: "0001" }), q: inp({ w: "s" }) };
  app.append(panel(null, grid(field("Material", f.m), field("Storage location", f.l), field("Quantity", f.q))),
    note("The quantity is moved from unrestricted to quality-inspection stock (movement 322) and an inspection lot is created - e.g. for a suspicion or an expiry check."));
  toolbar([{ label: "Create lot", key: "F8", primary: true, onClick: async () => {
    const r = await run(() => api("/api/qm/lot", { matnr: val(f.m), lgort: val(f.l), qty: val(f.q) })); if (r) { msg("S", r.message); go("QA11", { prueflos: r.prueflos }); } } }]);
} });

// ------------------------------------------------------------------ 3-1 QM01
register("QM01", { title: "Quality Notifications (complaints, NCR, corrective actions)", async render(app) {
  const f = { st: sel([["open", "Open"], ["", "All"]], "open") }, out = h("div");
  app.append(panel(null, grid(field("Status", f.st))), out);
  let meta = { types: {}, defects: {} };
  const load = async () => {
    const d = await run(() => api(`/api/qm/notif?status=${f.st.value}`)); if (!d) return; meta = d;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Quality notifications", rowClass: r => r.overdue ? ".neg" : "", columns: [{ key: "qmnum", label: "Notification" }, { key: "type_text", label: "Type" },
      { key: "created", label: "Created", type: "date" }, { key: "matnr", label: "Material" }, { key: "vendor", label: "Vendor / customer", render: r => r.vendor || r.customer || "" },
      { key: "defect_text", label: "Defect" }, { key: "qty", label: "Quantity", type: "qty" }, { key: "text", label: "Problem" }, { key: "cause", label: "Root cause" }, { key: "action", label: "Corrective action" },
      { key: "due", label: "Due", type: "date" }, { key: "status", label: "Status", render: r => badge(r.status, r.status === "CLOSED" ? "U" : r.overdue ? "B" : "Q") },
      { key: "x", label: "", render: r => r.status === "CLOSED" ? "" : btn("Cause / action", async () => {
        const x = await ask(`Notification ${r.qmnum}`, [{ name: "cause", label: "Root cause", value: r.cause || "" }, { name: "action", label: "Corrective action", value: r.action || "" },
          { name: "close", label: "Close (yes / empty)", value: "" }]); if (!x) return;
        const res = await run(() => api("/api/qm/notif", { qmnum: r.qmnum, cause: x.cause, action: x.action, close: /^(y|yes|x|1|نعم)$/i.test(x.close || "") })); if (res) { msg("S", res.message); load(); } }) }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "New notification", onClick: async () => {
    const x = await ask("New quality notification", [{ name: "qmart", label: "Type: Q1 customer, Q2 vendor, Q3 internal", value: "Q3" }, { name: "matnr", label: "Material", value: "" },
      { name: "lifnr", label: "Vendor (Q2)", value: "" }, { name: "kunnr", label: "Customer (Q1)", value: "" }, { name: "defect", label: "Defect (" + Object.keys(meta.defects).join(", ") + ")", value: "OTH" },
      { name: "qty", label: "Quantity", value: "" }, { name: "text", label: "Problem", value: "" }]); if (!x) return;
    const r = await run(() => api("/api/qm/notif", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 4-1 ZQM_VENDOR
register("ZQM_VENDOR", { title: "Vendor Quality Rating", async render(app, params) {
  const f = range(params, 90), out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/qm/vendors?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Quality per vendor", columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "lots", label: "Lots", type: "int" },
      { key: "ok_lots", label: "Accepted", type: "int" }, { key: "accept_pct", label: "Accepted lots %" }, { key: "qty", label: "Received", type: "qty" }, { key: "rej", label: "Rejected", type: "qty" },
      { key: "ppm", label: "ppm", type: "int" }, { key: "complaints", label: "Complaints", type: "int" }, { key: "score", label: "Score (0-100)", type: "int" },
      { key: "grade", label: "Grade", render: r => badge(r.grade, r.grade === "A" ? "U" : r.grade === "B" ? "Q" : "B") }] }),
      note("Score = half accepted lots %, half good quantity %, minus 5 points per complaint. A ≥ 90, B ≥ 75, C below - use it in the vendor evaluation and before the next order."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ================================================================== maintenance
const OST = { REL: ["Released", "Q"], TECO: ["Completed", "U"] };
// ------------------------------------------------------------------ 1-1 ZPM_COCKPIT
register("ZPM_COCKPIT", { title: "Maintenance Cockpit", async render(app, params) {
  const f = range(params, 90), out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pm/cockpit?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Open orders", d.open_orders, `${d.overdue_orders} overdue`, d.overdue_orders ? "neg" : ""),
      kpi("Preventive overdue", d.overdue_plans, "plans past due", d.overdue_plans ? "neg" : "pos"),
      kpi("Breakdowns", d.breakdowns, `${d.downtime} min downtime`, d.breakdowns ? "neg" : "pos"),
      kpi("MTTR", d.mttr === null ? "-" : d.mttr + " min", "mean time to repair"),
      kpi("Availability", d.availability === null ? "-" : d.availability + " %", "of the machines", d.availability !== null && d.availability < 98 ? "neg" : "pos"),
      kpi("Planned work", d.planned_share === null ? "-" : d.planned_share + " %", "preventive share of completed orders"), kpi("Maintenance cost", fmtAmt(d.cost), "parts + labour")),
      alv({ rows: d.machines, title: "Machines", columns: [{ key: "equnr", label: "Machine" }, { key: "eqktx", label: "Description" }, { key: "arbpl", label: "Line" }, { key: "crit", label: "Criticality" },
        { key: "breakdowns", label: "Breakdowns", type: "int" }, { key: "downtime", label: "Downtime min", type: "int" }, { key: "mttr", label: "MTTR min" }, { key: "mtbf", label: "MTBF h" },
        { key: "availability", label: "Availability %" }, { key: "cost", label: "Cost (EGP)", type: "amt" }] }),
      alv({ rows: d.orders, title: "Open maintenance orders", rowClass: r => r.overdue ? ".neg" : "", columns: [{ key: "aufnr", label: "Order" }, { key: "type_text", label: "Type" }, { key: "eqktx", label: "Machine" },
        { key: "text", label: "Work" }, { key: "due", label: "Due", type: "date" }, { key: "total", label: "Cost so far", type: "amt" }] }),
      note("Breakdown downtime is written to the production line's downtime log automatically - the production board and OEE show it."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Report breakdown", onClick: () => go("ZPM_NOTIF") }, { label: "Orders", onClick: () => go("ZPM_ORDERS") }]);
  load();
} });

// ------------------------------------------------------------------ 1-2 ZPM_EQUI
register("ZPM_EQUI", { title: "Machines (technical objects)", async render(app) {
  const out = h("div"); app.append(out);
  let meta = { crit: {}, lines: [] };
  const edit = async r => {
    const x = await ask(r ? `Machine ${r.equnr}` : "New machine", [{ name: "equnr", label: "Machine number", value: r ? r.equnr : "" }, { name: "eqktx", label: "Description", value: r ? r.eqktx : "" },
      { name: "arbpl", label: "Production line (" + meta.lines.map(l => l.arbpl).join(", ") + ")", value: r ? r.arbpl || "" : "" }, { name: "kostl", label: "Cost center (empty = of the line)", value: r ? r.kostl : "" },
      { name: "crit", label: "Criticality A / B / C", value: r ? r.crit : "B" }, { name: "inbdt", label: "In service since", value: r ? r.inbdt || "" : "" }]); if (!x) return;
    const res = await run(() => api("/api/pm/equi", x)); if (res) { msg("S", res.message); load(); } };
  const load = async () => {
    const d = await run(() => api("/api/pm/equi")); if (!d) return; meta = d;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Machines", columns: [{ key: "equnr", label: "Machine" }, { key: "eqktx", label: "Description" }, { key: "arbpl", label: "Line" }, { key: "line", label: "Line name" },
      { key: "kostl", label: "Cost center" }, { key: "crit_text", label: "Criticality" }, { key: "inbdt", label: "In service", type: "date" }, { key: "x", label: "", render: r => btn("Change", () => edit(r)) }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "New machine", onClick: () => edit(null) }]);
  load();
} });

// ------------------------------------------------------------------ 2-1 ZPM_PLAN
register("ZPM_PLAN", { title: "Preventive Maintenance Plans", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/pm/plans")); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Plans", rowClass: r => r.overdue ? ".neg" : "", columns: [{ key: "warpl", label: "Plan" }, { key: "equnr", label: "Machine" }, { key: "eqktx", label: "Description" },
      { key: "text", label: "Task" }, { key: "interval_days", label: "Every (days)", type: "int" }, { key: "minutes", label: "Minutes", type: "int" }, { key: "last_done", label: "Last done", type: "date" },
      { key: "next_due", label: "Next due", type: "date" }, { key: "overdue", label: "", render: r => r.overdue ? badge("Overdue", "B") : "" }] }),
      note("'Schedule' creates a preventive order (PM02) for every plan that is due; completing the order moves the next due date by the interval."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "New plan", onClick: async () => {
    const x = await ask("New preventive plan", [{ name: "equnr", label: "Machine", value: "" }, { name: "text", label: "Task", value: "" }, { name: "interval_days", label: "Every (days)", value: "30" },
      { name: "minutes", label: "Planned minutes", value: "60" }, { name: "next_due", label: "First due date", value: today() }]); if (!x) return;
    const r = await run(() => api("/api/pm/plan", x)); if (r) { msg("S", r.message); load(); } } },
  { label: "Schedule due orders", onClick: async () => { const r = await run(() => api("/api/pm/schedule", { horizon: 7 })); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 2-2 ZPM_NOTIF
register("ZPM_NOTIF", { title: "Breakdown / Maintenance Request", async render(app) {
  const f = { t: sel([["M2", "Breakdown - machine stopped"], ["M1", "Request - machine still running"]], "M2"), e: inp({ w: "m" }),
    s: inp({ type: "datetime-local", value: today() + "T" + new Date().toTimeString().slice(0, 5) }), x: inp({ w: "l" }) }, out = h("div");
  app.append(panel(null, grid(field("Type", f.t), field("Machine", f.e), field("Stopped at", f.s), field("Problem", f.x))), out);
  const load = async () => {
    const d = await run(() => api("/api/pm/orders")); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.notifs, title: "Notifications", columns: [{ key: "qmnum", label: "Notification" }, { key: "type_text", label: "Type" }, { key: "eqktx", label: "Machine" }, { key: "text", label: "Problem" },
      { key: "start", label: "Stopped" }, { key: "finish", label: "Running again" }, { key: "minutes", label: "Downtime min", type: "int" }, { key: "aufnr", label: "Order" },
      { key: "status", label: "Status", render: r => badge(r.status, r.status === "CLOSED" ? "U" : "Q") },
      { key: "y", label: "", render: r => !r.aufnr && r.status !== "CLOSED" ? btn("Create order", async () => { const x = await run(() => api("/api/pm/order", { qmnum: r.qmnum })); if (x) { msg("S", x.message); load(); } }) : "" }] }));
  };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pm/notif", { qmart: f.t.value, equnr: val(f.e), start: f.s.value, text: val(f.x) })); if (r) { msg("S", r.message); f.x.value = ""; load(); } } },
  { label: "Orders", onClick: () => go("ZPM_ORDERS") }]);
  load();
} });

// ------------------------------------------------------------------ 3-1 ZPM_ORDERS
register("ZPM_ORDERS", { title: "Maintenance Orders (parts, hours, completion)", async render(app) {
  const f = { st: sel([["open", "Open"], ["", "All"]], "open") }, out = h("div");
  app.append(panel(null, grid(field("Status", f.st))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pm/orders?status=${f.st.value}`)); if (!d) return;
    out.innerHTML = "";
    const act = (path, body) => async () => { const r = await run(() => api(path, body())); if (r) { msg("S", r.message); load(); } };
    out.append(alv({ rows: d.rows, title: "Maintenance orders", rowClass: r => r.overdue ? ".neg" : "", columns: [{ key: "aufnr", label: "Order" }, { key: "type_text", label: "Type" },
      { key: "equnr", label: "Machine" }, { key: "text", label: "Work" }, { key: "due", label: "Due", type: "date" }, { key: "minutes", label: "Minutes", type: "int" },
      { key: "parts", label: "Parts", type: "amt" }, { key: "labour", label: "Labour", type: "amt" }, { key: "total", label: "Total", type: "amt" },
      { key: "status", label: "Status", render: r => badge(...(OST[r.status] || [r.status, ""])) },
      { key: "x", label: "", render: r => r.status === "TECO" ? "" : h("span", null,
        btn("Spare parts", async () => { const x = await ask(`Spare parts for ${r.aufnr}`, [{ name: "matnr", label: "Material", value: "" }, { name: "qty", label: "Quantity", value: "1" }, { name: "lgort", label: "Storage location", value: "0004" }]); if (!x) return;
          act("/api/pm/parts", () => ({ aufnr: r.aufnr, items: [x] }))(); }), " ",
        btn("Hours", async () => { const x = await ask(`Confirm time on ${r.aufnr}`, [{ name: "minutes", label: "Minutes", value: "60" }, { name: "text", label: "Work done", value: "" }]); if (!x) return;
          act("/api/pm/confirm", () => Object.assign({ aufnr: r.aufnr }, x))(); }), " ",
        btn("Complete", async () => { const x = await ask(`Complete ${r.aufnr}`, [{ name: "finish", label: "Machine running again (YYYY-MM-DD HH:MM, breakdowns only)", value: "" }]); if (!x) return;
          act("/api/pm/complete", () => Object.assign({ aufnr: r.aufnr }, x))(); })) }] }),
      note("Spare parts are a real goods issue (201) to the machine's cost center - stock and accounting are updated. Labour = minutes × hourly rate."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "New order", onClick: async () => {
    const x = await ask("New maintenance order", [{ name: "auart", label: "PM01 corrective / PM02 preventive", value: "PM01" }, { name: "equnr", label: "Machine", value: "" },
      { name: "text", label: "Work", value: "" }, { name: "due", label: "Due", value: today() }]); if (!x) return;
    const r = await run(() => api("/api/pm/order", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 4-1 ZPM_REL
register("ZPM_REL", { title: "Machine Reliability (MTBF / MTTR / availability)", async render(app, params) {
  const f = range(params, 90), out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pm/reliability?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Reliability per machine", columns: [{ key: "equnr", label: "Machine" }, { key: "eqktx", label: "Description" }, { key: "arbpl", label: "Line" },
      { key: "breakdowns", label: "Breakdowns", type: "int" }, { key: "downtime", label: "Downtime min", type: "int" }, { key: "mttr", label: "MTTR min" }, { key: "mtbf", label: "MTBF hours" },
      { key: "availability", label: "Availability %" }, { key: "orders", label: "Orders", type: "int" }, { key: "parts", label: "Parts", type: "amt" }, { key: "labour", label: "Labour", type: "amt" },
      { key: "cost", label: "Total cost", type: "amt" }] }),
      note("MTTR = downtime ÷ breakdowns. MTBF = running time ÷ breakdowns. A short MTBF on a critical machine = more preventive maintenance or a replacement decision."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });
})();
