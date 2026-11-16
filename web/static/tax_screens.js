/* NERP - Egyptian taxes (ZTAX_*): law register, tax calendar, returns (VAT form 10, WHT form 41,
   salary tax, corporate tax estimate, simplified regime), e-invoice with the ETA (manual mode:
   generate, export, record results, cancel; received documents), tax audit readiness and the
   tax month-end. */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, ask, field, inp, sel, val, alv, register, go, toolbar, fmtAmt, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const yp = params => { const n = now(); return { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }; };
const fileText = (onText, accept) => { const f = h("input", { type: "file", accept: accept || ".csv,text/csv" });
  f.addEventListener("change", () => { const x = f.files[0]; if (!x) return; const rd = new FileReader(); rd.onload = () => onText(rd.result, x.name); rd.readAsText(x, "utf-8"); }); return f; };
const save = (name, data, type) => { const a = h("a", { href: URL.createObjectURL(new Blob([data], { type })), download: name }); document.body.append(a); a.click(); a.remove(); };
const b64save = (name, b64) => { const bin = atob(b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  save(name, u8, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); };
const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not needed", ""], ok: ["OK", "U"], issue: ["Fix", "B"], manual: ["Check", "Q"],
  paid: ["Paid", "U"], filed: ["Filed", "U"], overdue: ["Overdue", "B"], "due soon": ["Due soon", "Q"] };
const stb = s => badge((ST[s] || [s])[0], (ST[s] || ["", ""])[1]);
const filing = (typ, period, amount) => h("button.btn", { type: "button", on: { click: async () => {
  const x = await ask(`File / pay ${typ} ${period}`, [{ name: "filed_on", label: "Filed on (date, empty = only payment)", value: today() },
    { name: "ref_no", label: "Reference no. of the return (ETA portal)", value: "" }, { name: "paid_on", label: "Paid on (empty = not yet)", value: "" },
    { name: "pay_ref", label: "Payment reference", value: "" }]); if (!x) return;
  const r = await run(() => api("/api/tax/mark", Object.assign({ typ, period, amount }, x))); if (r) msg("S", r.message); } } }, "Record filing / payment");

// ------------------------------------------------------------------ 1-1 ZTAX_LAW
register("ZTAX_LAW", { title: "Egyptian Tax Law Register (rates, limits, deadlines)", async render(app) {
  const f = { day: inp({ type: "date", value: today() }), area: sel([["", "All"], ["VAT", "VAT"], ["WHT", "Withholding"], ["SAL", "Salary tax"], ["SI", "Social insurance"],
    ["CIT", "Corporate tax"], ["SIMP", "Simplified regime"], ["EINV", "E-invoice"], ["CAL", "Deadlines"], ["AUD", "Tax audit"]], "") }, out = h("div");
  app.append(panel(null, grid(field("Valid on", f.day), field("Area", f.area))),
    note("Every rate and limit with its validity and legal reference. When a law or decree changes, add a new version with its effective date - the old one stays as history. 'Verify' = to be confirmed with your tax adviser / the official ETA text before relying on it."), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/law?day=${f.day.value}&area=${f.area.value}`)); if (!d) return;
    out.innerHTML = "";
    const ver = d.rows.filter(r => r.status === "VERIFY").length;
    out.append(h("div.kpis", null, kpi("Rules", d.rows.length), kpi("To verify", ver, "with the tax adviser", ver ? "neg" : "pos"),
      kpi("Payroll vs law", d.payroll.differences.length ? `${d.payroll.differences.length} difference(s)` : "✓ same", "", d.payroll.differences.length ? "neg" : "pos"),
      kpi("WHT codes vs law", d.wht.differences.length ? `${d.wht.differences.length} difference(s)` : "✓ same", "", d.wht.differences.length ? "neg" : "pos")));
    if (d.payroll.differences.length) out.append(panel("Payroll configuration differs from the law", alv({ rows: d.payroll.differences, title: "Payroll (PC00) uses its configuration",
      columns: [{ key: "key", label: "Parameter" }, { key: "payroll", label: "In the payroll" }, { key: "law", label: "Law valid on " + d.payroll.day }] }),
      h("button.btn", { type: "button", on: { click: async () => { if (!await confirmBox("Payroll", "Update the payroll parameters to the law register?")) return;
        const r = await run(() => api("/api/tax/law/apply_payroll", { day: f.day.value })); if (r) { msg("S", r.message); load(); } } } }, "Apply to payroll")));
    if (d.wht.differences.length) out.append(panel("Withholding tax codes differ from the law", alv({ rows: d.wht.differences, title: "WHT codes",
      columns: [{ key: "code", label: "Code" }, { key: "key", label: "Rule" }, { key: "system", label: "In the system %" }, { key: "law", label: "Law %" }] }),
      h("button.btn", { type: "button", on: { click: async () => { const r = await run(() => api("/api/tax/law/apply_wht", { day: f.day.value })); if (r) { msg("S", r.message); load(); } } } }, "Apply to WHT codes")));
    out.append(alv({ rows: d.rows, title: "Rules valid on " + f.day.value, columns: [{ key: "area", label: "Area" }, { key: "key", label: "Rule" }, { key: "text", label: "Description" },
      { key: "value", label: "Value" }, { key: "unit", label: "Unit" }, { key: "valid_from", label: "From", type: "date" }, { key: "legal_ref", label: "Legal reference" },
      { key: "status", label: "Status", render: r => badge(r.status === "VERIFIED" ? "Verified" : "Verify", r.status === "VERIFIED" ? "U" : "Q") },
      { key: "next_value", label: "Next change", render: r => r.next_value ? `${r.next_value} from ${r.next_from}` : "" }, { key: "note", label: "Note" },
      { key: "x", label: "", render: r => h("span", null,
        h("button.btn", { type: "button", on: { click: async () => {
          const x = await ask(`New version of ${r.key} (now ${r.value} ${r.unit})`, [{ name: "value", label: "New value", value: r.value }, { name: "valid_from", label: "Effective from", value: today() },
            { name: "legal_ref", label: "Law / decree / resolution", value: "" }, { name: "note", label: "Note", value: "" }]); if (!x) return;
          const res = await run(() => api("/api/tax/law/version", Object.assign({ key: r.key }, x))); if (res) { msg("S", res.message); load(); } } } }, "New version"), " ",
        r.status !== "VERIFIED" ? h("button.btn", { type: "button", on: { click: async () => { const res = await run(() => api("/api/tax/law/verify", { id: r.id })); if (res) { msg("S", res.message); load(); } } } }, "Verified") : "") }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Tax adviser review", onClick: () => go("ZTAX_REVIEW") }]);
  load();
} });

// ------------------------------------------------------------------ 1-5 ZTAX_REVIEW (tax adviser)
register("ZTAX_REVIEW", { title: "Tax Adviser Review of the Law Register", async render(app) {
  const out = h("div"), res = h("div"), file = h("input", { type: "file", accept: ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  let xlsx = null;
  file.addEventListener("change", () => { const x = file.files[0]; if (!x) return; const rd = new FileReader();
    rd.onload = () => { const u8 = new Uint8Array(rd.result); let s = ""; for (let i = 0; i < u8.length; i += 8192) s += String.fromCharCode.apply(null, u8.subarray(i, i + 8192)); xlsx = btoa(s); msg("S", `${x.name} ready - simulate first`); };
    rd.readAsArrayBuffer(x); });
  app.append(note("1. Make the Excel sheet and send it to your tax adviser. 2. The adviser answers every rule with OK or CHANGE (correct value, effective date, law / decree) and writes the name on top. 3. Load the answered sheet: simulate first, then load. OK = the rule becomes Verified; CHANGE with the same date corrects the rule, with a later date it becomes a new version - the old value stays as history."),
    out, panel("Answered sheet from the adviser", h("div", null, "Excel file: ", file)), res);
  const load = async () => {
    const d = await run(() => api("/api/tax/review")); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("To verify", d.to_verify, "rule versions", d.to_verify ? "neg" : "pos"), kpi("Verified", d.verified, "", "pos")),
      alv({ rows: d.rows, title: "Rules waiting for the tax adviser", columns: [{ key: "key", label: "Rule" }, { key: "text", label: "Description" }, { key: "text_ar", label: "الوصف" },
        { key: "readable", label: "Value" }, { key: "unit", label: "Unit" }, { key: "valid_from", label: "From", type: "date" }, { key: "legal_ref", label: "Legal reference" }, { key: "note", label: "Why to verify" }] }));
  };
  const send = async simulate => {
    if (!xlsx) return msg("E", "Choose the answered Excel sheet", "TX", "940");
    const r = await run(() => api("/api/tax/review", { xlsx, simulate })); if (!r) return;
    res.innerHTML = "";
    res.append(h("div.kpis", null, kpi("Adviser", r.adviser || "-", r.date || ""), kpi("Answers", r.answered, `${r.unanswered} not answered`), kpi("Errors", r.errors, simulate ? "simulation" : "", r.errors ? "neg" : "pos")),
      alv({ rows: r.rows, title: simulate ? "Simulation - nothing changed" : "Loaded", rowClass: x => x.ok ? "" : ".neg", columns: [{ key: "row", label: "Row", type: "int" }, { key: "key", label: "Rule" },
        { key: "decision", label: "Decision" }, { key: "ok", label: "", render: x => badge(x.ok ? "OK" : "Error", x.ok ? "U" : "B") }, { key: "result", label: "Result" }] }));
    msg(r.errors ? "E" : "S", r.message); if (!simulate && !r.errors) load();
  };
  toolbar([{ label: "Sheet for the tax adviser (Excel)", key: "F8", primary: true, onClick: async () => {
    const r = await run(() => api("/api/tax/review?file=1")); if (r) { b64save(r.name, r.xlsx); msg("S", `${r.name} created - send it to your tax adviser`); } } },
    { label: "Simulate answers", onClick: () => send(true) }, { label: "Load answers", onClick: async () => { if (await confirmBox("Adviser answers", "Update the law register with the adviser's answers?")) send(false); } },
    { label: "Law register", onClick: () => go("ZTAX_LAW") }]);
  load();
} });

// ------------------------------------------------------------------ 1-2 ZTAX_CONF (ETA settings)
register("ZTAX_CONF", { title: "E-Invoice Settings (ETA)", async render(app) {
  const s = await run(() => api("/api/tax/einv/settings")); if (!s) return;
  const f = { mode: sel([["MANUAL", "MANUAL - export, sign and submit with the ETA tools, record the result"], ["API", "API - direct submission (needs credentials + signer)"]], s.mode, { w: "l" }),
    env: sel([["preprod", "Pre-production (test)"], ["prod", "Production"]], s.env), client_id: inp({ value: s.client_id || "", w: "l" }), signer: inp({ value: s.signer || "", w: "l", ph: "e.g. local signer service URL" }) };
  app.append(panel(null, grid(field("Mode", f.mode), field("ETA environment", f.env), field("ERP client ID", f.client_id), field("Signing service (USB token)", f.signer))),
    note("Manual mode works now: NERP builds every e-invoice in the ETA format (JSON v1.0); you export them, sign and submit them with the ETA signer / portal, then record the UUID and status (one by one or as a result file). API mode needs the ERP registration on the ETA portal (client ID and secret), a signing service for the USB token and network access - not connected in this version. The client secret is never stored here."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/tax/einv/settings", { mode: f.mode.value, env: f.env.value, client_id: val(f.client_id), signer: val(f.signer) })); if (r) msg("S", r.message); } }]);
} });

// ------------------------------------------------------------------ 1-3 ZTAX_CAL
register("ZTAX_CAL", { title: "Tax Calendar (returns and payments)", async render(app, params) {
  const f = { y: inp({ value: params.gjahr || now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/cal?gjahr=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Overdue", d.overdue, "not filed after the due date", d.overdue ? "neg" : "pos"), kpi("Due in 10 days", d.due_soon, "", d.due_soon ? "neg" : "")),
      alv({ rows: d.rows, title: `Tax returns ${d.year}`, rowClass: r => r.status === "overdue" ? ".neg" : "", columns: [{ key: "due", label: "Due", type: "date" }, { key: "days", label: "Days", type: "int" },
        { key: "label", label: "Return" }, { key: "amount", label: "Amount (EGP)", type: "amt" }, { key: "status", label: "Status", render: r => stb(r.status) },
        { key: "ref_no", label: "Reference" }, { key: "filed_on", label: "Filed", type: "date" }, { key: "paid_on", label: "Paid", type: "date" },
        { key: "x", label: "", render: r => r.status === "paid" ? "" : filing(r.typ, r.period, r.amount) }] }),
      note("Amounts come from the books (VAT payable, salary tax of the payroll, withholding of the quarter, corporate tax estimate). Due dates come from the law register (CAL rules)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 1-4 ZTAX_CLOSE
register("ZTAX_CLOSE", { title: "Taxes - Month-End", async render(app, params) {
  const f = yp(params), out = h("div");
  app.append(panel(null, grid(field("Year", f.y), field("Month", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/close?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
      alv({ rows: d.steps, title: "Tax work of the month - in this order", columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" },
        { key: "tcode", label: "Transaction", link: r => go(r.tcode) }, { key: "status", label: "Status", render: r => stb(r.status) }, { key: "info", label: "Result" }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 2-1 ZTAX_VAT
register("ZTAX_VAT", { title: "VAT Return (form 10)", async render(app, params) {
  const f = yp(params), out = h("div");
  app.append(panel(null, grid(field("Year", f.y), field("Month", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/vat?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi(d.payable >= 0 ? "VAT payable" : "Credit to carry forward", fmtAmt(Math.abs(d.payable)), `due ${d.due}`, d.payable > 0 ? "neg" : "pos"),
      kpi("Input VAT at risk", fmtAmt(d.input_at_risk), `${d.input_at_risk_docs} purchase invoice(s) without a valid e-invoice`, d.input_at_risk ? "neg" : "pos"),
      kpi("Return", d.filing && d.filing.filed_on ? `filed ${d.filing.filed_on}` : "not filed", d.filing && d.filing.ref_no ? d.filing.ref_no : "")),
      alv({ rows: d.lines, title: `VAT return ${d.period} - as in the ETA form`, columns: [{ key: "no", label: "Line" }, { key: "text", label: "Description" },
        { key: "base", label: "Taxable amount", type: "amt" }, { key: "tax", label: "Tax", type: "amt" }] }),
      h("div", null, filing("VAT", d.period, d.payable)),
      note("Enter these lines in the VAT return on the ETA portal, then record the filing. Input VAT on purchases without a valid e-invoice of the vendor can be refused in the audit (ZTAX_EIN)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "VAT settlement (FB41)", onClick: () => go("FB41") }]);
  load();
} });

// ------------------------------------------------------------------ 3-1 ZTAX_41
register("ZTAX_41", { title: "Withholding Tax Return (form 41)", async render(app) {
  const n = now(), f = { y: inp({ value: n.y, w: "s" }), q: sel([["1", "Q1"], ["2", "Q2"], ["3", "Q3"], ["4", "Q4"]], String(Math.ceil(n.p / 3))) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y), field("Quarter", f.q))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/f41?gjahr=${val(f.y)}&q=${f.q.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Withheld", fmtAmt(d.amount), `on ${fmtAmt(d.base)} - due ${d.due}`), kpi("Vendors without tax no.", d.missing_taxid, "complete them before filing", d.missing_taxid ? "neg" : "pos")),
      alv({ rows: d.rows, title: `Form 41 ${d.period}`, emptyText: "No withholding in the quarter", columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
        { key: "taxid", label: "Tax registration no.", render: r => r.taxid || badge("missing", "B") }, { key: "code", label: "Code" }, { key: "pct", label: "Rate %" },
        { key: "base", label: "Base", type: "amt", sum: true }, { key: "amount", label: "Withheld", type: "amt", sum: true }, { key: "docs", label: "Docs", type: "int" }] }),
      h("div", null, filing("WHT", d.period, d.amount)));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "WHT codes (ZWHT)", onClick: () => go("ZWHT") }]);
  load();
} });

// ------------------------------------------------------------------ 4-1 ZTAX_SAL
register("ZTAX_SAL", { title: "Salary Tax Return (form 4)", async render(app, params) {
  const f = yp(params), out = h("div");
  app.append(panel(null, grid(field("Year", f.y), field("Month", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/sal?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Salary tax", fmtAmt(d.tax), `due ${d.due}`), kpi("Employees", d.employees, `payroll ${d.payroll || "not run"}`),
      kpi("Martyrs' fund", fmtAmt(d.martyrs)), kpi("Social insurance", fmtAmt(d.si_ee + d.si_er), "employee + employer")),
      alv({ rows: [d], title: `Salary tax ${d.period}`, columns: [{ key: "employees", label: "Employees", type: "int" }, { key: "gross", label: "Gross", type: "amt" },
        { key: "si_ee", label: "Employee SI", type: "amt" }, { key: "taxable", label: "Taxable", type: "amt" }, { key: "tax", label: "Salary tax", type: "amt" }, { key: "martyrs", label: "Martyrs", type: "amt" }] }),
      h("div", null, filing("SAL", d.period, d.tax)), note("Salary tax uses the brackets of Law 7/2024 including the high-income rule; the parameters come from the law register (ZTAX_LAW → Apply to payroll)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Payroll run", onClick: () => go("PC00_M99_CALC") }]);
  load();
} });

// ------------------------------------------------------------------ 5-1 ZTAX_CIT, 5-2 ZTAX_SIMP
register("ZTAX_CIT", { title: "Corporate Income Tax (estimate)", async render(app) {
  const f = { y: inp({ value: now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/cit?gjahr=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Accounting profit", fmtAmt(d.profit), String(d.year)), kpi(`Tax ${d.rate} %`, fmtAmt(d.tax), `return due ${d.due}`)), note(d.note), h("div", null, filing("CIT", String(d.year), d.tax)));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });
register("ZTAX_SIMP", { title: "Simplified Tax Regime (Law 6/2025)", async render(app) {
  const f = { t: inp({ w: "m", ph: "annual turnover EGP" }) }, out = h("div");
  app.append(panel(null, grid(field("Annual turnover (EGP)", f.t))), out);
  const load = async () => {
    if (!val(f.t)) return msg("E", "Enter the turnover");
    const d = await run(() => api(`/api/tax/simp?turnover=${encodeURIComponent(val(f.t))}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Eligible", d.eligible ? "Yes" : d.within_tolerance ? "Within the 20 % tolerance" : "No", `limit ${fmtAmt(d.limit)}`, d.eligible ? "pos" : "neg"),
      kpi(`Tax ${d.rate} % of turnover`, fmtAmt(d.tax), "instead of tax on profit")),
      alv({ rows: d.bands, title: "Bands (law register SIMP_BANDS)", columns: [{ key: "upto", label: "Turnover up to", type: "amt" }, { key: "rate", label: "Rate %" }] }), note(d.note));
  };
  toolbar([{ label: "Calculate", key: "F8", primary: true, onClick: load }]);
} });

// ------------------------------------------------------------------ 6-1 ZTAX_EINV
register("ZTAX_EINV", { title: "E-Invoices Issued (ETA)", async render(app) {
  const n = now(), f = { d1: inp({ type: "date", value: `${n.y}-${String(n.p).padStart(2, "0")}-01` }), d2: inp({ type: "date", value: today() }) }, out = h("div");
  let rows = [], picks = new Set();
  app.append(panel(null, grid(field("Invoices from", f.d1), field("to", f.d2))), out);
  const SB = { Valid: "U", "Ready to submit": "Q", "Not generated": "B", "Not valid (fix data)": "B", Invalid: "B", Rejected: "B", Cancelled: "", Submitted: "Q", "Cancel requested": "Q" };
  const load = async () => {
    const d = await run(() => api(`/api/tax/einv?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    rows = d.rows; picks = new Set(); out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Mode", d.mode, d.mode === "MANUAL" ? "export → sign / submit → record result" : "API"),
      ...Object.entries(d.counts).map(([k, v]) => kpi(k, v, "", k === "Valid" ? "pos" : ["Not generated", "Invalid", "Rejected", "Not valid (fix data)"].includes(k) ? "neg" : ""))),
      alv({ rows: rows.map((r, i) => Object.assign({ i }, r)), title: "Invoices and their e-invoice status", columns: [
        { key: "pick", label: "Sel.", render: r => { const cb = h("input", { type: "checkbox" }); cb.addEventListener("change", () => cb.checked ? picks.add(r.i) : picks.delete(r.i)); return cb; } },
        { key: "vbeln", label: "Invoice" }, { key: "fkdat", label: "Date", type: "date" }, { key: "name", label: "Customer" }, { key: "stcd1", label: "Tax no." },
        { key: "netwr", label: "Net", type: "amt", sum: true }, { key: "mwsbk", label: "VAT", type: "amt", sum: true },
        { key: "eta_status", label: "ETA status", render: r => badge(r.eta_status, SB[r.eta_status]) }, { key: "uuid", label: "UUID", render: r => r.uuid ? r.uuid.slice(0, 14) + "…" : "" },
        { key: "submitted", label: "Submitted" }, { key: "cancel_until", label: "Cancel until", type: "date" },
        { key: "x", label: "", render: r => h("span", null,
          ["Ready to submit", "Submitted"].includes(r.eta_status) ? h("button.btn", { type: "button", on: { click: async () => {
            const x = await ask(`ETA result for ${r.vbeln}`, [{ name: "uuid", label: "UUID", value: "" }, { name: "status", label: "Status (Valid / Invalid / Rejected / Submitted)", value: "Valid" },
              { name: "date", label: "Date", value: today() }, { name: "long_id", label: "Long ID (optional)", value: "" }]); if (!x) return;
            const res = await run(() => api("/api/tax/einv/record", Object.assign({ vbeln: r.vbeln }, x))); if (res) { msg("S", res.message); load(); } } } }, "Record result") : "",
          r.eta_status === "Valid" ? h("button.btn", { type: "button", on: { click: async () => {
            const x = await ask(`Cancel e-invoice ${r.vbeln}`, [{ name: "reason", label: "Reason", value: "" }]); if (!x) return;
            const res = await run(() => api("/api/tax/einv/cancel", { vbeln: r.vbeln, reason: x.reason })); if (res) { msg("S", res.message); load(); } } } }, "Request cancel") : "") }] }));
  };
  const sel_ = () => [...picks].map(i => rows[i].vbeln);
  const resIn = fileText(async text => { const r = await run(() => api("/api/tax/einv/results", { text })); if (r) { msg(r.errors ? "W" : "S", r.message); load(); } });
  app.append(panel("Manual mode - result file", h("div", null, "Result file from the ETA (CSV: internal_id, uuid, status, date): ", resIn)));
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Generate e-invoice", onClick: async () => { const v = sel_(); if (!v.length) return msg("E", "Select invoices");
      const r = await run(() => api("/api/tax/einv/generate", { vbelns: v })); if (r) { msg("S", r.message); load(); } } },
    { label: "Export for signing (JSON)", onClick: async () => { const v = sel_(); if (!v.length) return msg("E", "Select invoices");
      const r = await run(() => api("/api/tax/einv/export", { vbelns: v })); if (r) { save(r.file, r.json, "application/json"); msg("S", `${r.count} document(s) exported - sign and submit them with the ETA tools`); } } },
    { label: "Submit via API", onClick: async () => { const v = sel_(); if (!v.length) return msg("E", "Select invoices"); await run(() => api("/api/tax/einv/submit", { vbelns: v })); } },
    { label: "Settings", onClick: () => go("ZTAX_CONF") }]);
  load();
} });

// ------------------------------------------------------------------ 6-2 ZTAX_EIN
register("ZTAX_EIN", { title: "E-Invoices Received (from vendors)", async render(app) {
  const n = now(), f = { d1: inp({ type: "date", value: `${n.y}-01-01` }), d2: inp({ type: "date", value: today() }) }, out = h("div");
  const imp = fileText(async text => { const r = await run(() => api("/api/tax/ein/import", { text })); if (r) { msg(r.errors ? "W" : "S", r.message); load(); } });
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), panel("Import from the ETA portal", h("div", null, "Received documents (CSV: uuid, issuer_id, issuer_name, internal_id, issued, net, tax, total, status): ", imp)), out);
  const MB = { matched: "U", "invoice missing in NERP": "Q", "vendor unknown": "B" };
  const load = async () => {
    const d = await run(() => api(`/api/tax/ein?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Matched", d.matched, "e-invoice = vendor invoice in NERP", "pos"), kpi("Not matched", d.unmatched, "record the invoice or the vendor tax no.", d.unmatched ? "neg" : "pos"),
      kpi("Input VAT at risk", fmtAmt(d.at_risk.amount), `${d.at_risk.count} invoice(s) without a valid e-invoice`, d.at_risk.count ? "neg" : "pos")),
      alv({ rows: d.rows, title: "Received e-invoices", emptyText: "Nothing imported yet", columns: [{ key: "issued", label: "Date", type: "date" }, { key: "issuer_name", label: "Vendor" },
        { key: "issuer_id", label: "Tax no." }, { key: "internal_id", label: "Invoice no." }, { key: "total", label: "Total", type: "amt", sum: true }, { key: "tax", label: "VAT", type: "amt", sum: true },
        { key: "status", label: "ETA status" }, { key: "match", label: "In NERP", render: r => badge(r.match, MB[r.match]) }, { key: "belnr", label: "Document" },
        { key: "reject_until", label: "Reject until", type: "date" }] }),
      alv({ rows: d.at_risk.rows, title: "Vendor invoices with input VAT but no valid e-invoice (claim at risk)", emptyText: "None", columns: [{ key: "budat", label: "Date", type: "date" },
        { key: "belnr", label: "Document" }, { key: "xblnr", label: "Vendor invoice" }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "vat", label: "Input VAT", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 7-x audit
register("ZTAX_AUDIT", { title: "Tax Audit Readiness (الفحص الضريبي)", async render(app) {
  const f = { y: inp({ value: now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Fiscal year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/audit?gjahr=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Readiness", d.score + " %", `${d.issues} point(s) to fix`, d.score >= 80 ? "pos" : "neg")),
      alv({ rows: d.items, title: `What the tax inspector checks - ${d.year}`, rowClass: r => r.status === "issue" ? ".neg" : "", columns: [{ key: "no", label: "No.", type: "int" },
        { key: "area", label: "Area" }, { key: "check", label: "Check" }, { key: "status", label: "Status", render: r => stb(r.status) }, { key: "info", label: "Result" },
        { key: "tcode", label: "Fix with", link: r => go(r.tcode) }, { key: "law", label: "Legal basis" }] }),
      note("Audits are risk-based samples: a complete, reconciled file lowers the risk. Give the inspector the audit file (ZTAX_AUDITFILE)."));
  };
  toolbar([{ label: "Check", key: "F8", primary: true, onClick: load }, { label: "Audit file (Excel)", onClick: () => go("ZTAX_AUDITFILE", { gjahr: val(f.y) }) }]);
  load();
} });
register("ZTAX_REVREC", { title: "Revenue Reconciliation (books - invoices - e-invoices - VAT)", async render(app) {
  const f = { y: inp({ value: now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/tax/revrec?gjahr=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Reconciled", d.ok ? "Yes" : "Differences", "", d.ok ? "pos" : "neg")),
      alv({ rows: d.rows, title: "Per month (EGP)", rowClass: r => r.ok ? "" : ".neg", columns: [{ key: "month", label: "Month" }, { key: "books", label: "Revenue in books", type: "amt", sum: true },
        { key: "invoices", label: "Sales invoices", type: "amt", sum: true }, { key: "einvoices", label: "E-invoices valid", type: "amt", sum: true }, { key: "vat_base", label: "VAT return base", type: "amt", sum: true },
        { key: "diff_books", label: "Books - invoices", type: "amt", sum: true }, { key: "diff_einv", label: "Not e-invoiced", type: "amt", sum: true }, { key: "diff_vat", label: "Not in VAT base", type: "amt", sum: true }] }),
      note("Books - invoices = revenue posted outside sales billing (FB70, journal entries) - it needs its own e-invoice. Not in VAT base = invoices without a tax code. Not e-invoiced = invoices without a valid ETA status."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });
register("ZTAX_AUDITFILE", { title: "Tax Audit File (Excel)", async render(app, params) {
  const f = { y: inp({ value: params.gjahr || now().y, w: "s" }) };
  app.append(panel(null, grid(field("Fiscal year", f.y))),
    note("One Excel file with what the inspector asks for: trial balance, journal of all postings, sales and purchase VAT registers (with ETA UUID), withholding register (form 41), salary tax register, fixed asset register, e-invoice log, revenue reconciliation and the audit checklist."));
  toolbar([{ label: "Create file", key: "F8", primary: true, onClick: async () => {
    const r = await run(() => api(`/api/tax/auditfile?gjahr=${val(f.y)}`)); if (r) { b64save(r.name, r.xlsx); msg("S", `${r.name} created`); } } }]);
} });
})();
