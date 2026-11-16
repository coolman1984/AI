/* NERP - HR in depth: loans and salary advances (ZHR_LOAN), one-time payments and penalties
   (ZHR_ADDPAY), follow-up events (ZHR_EVENTS), leave balances (ZHR_LEAVEBAL), payroll cost per
   cost center (ZHR_COST) and the HR / payroll month-end (ZHR_CLOSE). */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, field, inp, sel, val, alv, register, go, toolbar, fmtAmt, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// ------------------------------------------------------------------ ZHR_LOAN
register("ZHR_LOAN", { title: "Employee Loans & Salary Advances", async render(app, params) {
  const n = now();
  const f = { pernr: inp({ value: params.id || "", w: "s" }), typ: sel([["ADV", "Salary advance"], ["LOAN", "Employee loan"]], "ADV"), amount: inp({ w: "m" }),
    installment: inp({ w: "m", ph: "monthly deduction" }), y: inp({ value: n.y, w: "s" }), p: inp({ value: n.p, w: "s" }), budat: inp({ type: "date", value: today() }), text: inp({ w: "l" }) };
  const out = h("div");
  app.append(panel("New loan / advance", grid(field("Employee", f.pernr, { req: true }), field("Type", f.typ), field("Amount (EGP)", f.amount, { req: true }),
    field("Monthly installment", f.installment), field("First deduction - year", f.y), field("month", f.p), field("Payment date", f.budat), field("Reason", f.text))),
    note("The amount is paid from the bank now (Dr 117000 employee loans / Cr bank). The payroll deducts the installment every month until it is repaid - never more than the net pay."), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/loans")); if (!d) return;
    out.innerHTML = "";
    const act = d.rows.filter(r => r.status === "A");
    out.append(h("div.kpis", null, kpi("Open loans", act.length), kpi("Outstanding", fmtAmt(act.reduce((a, r) => a + r.balance, 0)), "EGP owed by employees")),
      alv({ rows: d.rows, title: "Loans and advances", emptyText: "No loans", columns: [{ key: "id", label: "No.", type: "int" }, { key: "pernr", label: "Employee" },
        { key: "name", label: "Name" }, { key: "typ_text", label: "Type" }, { key: "amount", label: "Amount", type: "amt", sum: true },
        { key: "installment", label: "Installment", type: "amt" }, { key: "start", label: "From" }, { key: "repaid", label: "Repaid", type: "amt", sum: true },
        { key: "balance", label: "Balance", type: "amt", sum: true }, { key: "status", label: "Status", render: r => badge(r.status === "A" ? "Open" : "Repaid", r.status === "A" ? "Q" : "U") },
        { key: "belnr", label: "Payment doc." }, { key: "text", label: "Reason" }] }));
  };
  toolbar([{ label: "Pay out", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!await confirmBox("Loan", `Pay ${val(f.amount)} EGP to employee ${val(f.pernr)} from the bank?`)) return;
    const r = await run(() => api("/api/hr/loan", { pernr: val(f.pernr), typ: f.typ.value, amount: val(f.amount), installment: val(f.installment),
      gjahr: val(f.y), perio: val(f.p), budat: f.budat.value, text: val(f.text) }));
    if (r) { msg("S", r.message); f.amount.value = ""; f.installment.value = ""; load(); } } }, { label: "Refresh", key: "F8", onClick: () => load() }]);
  load();
} });

// ------------------------------------------------------------------ ZHR_ADDPAY
register("ZHR_ADDPAY", { title: "Bonuses, Incentives & Penalties (one-time)", async render(app) {
  const n = now();
  const TYPES = [["BONUS", "Bonus"], ["INCENT", "Production incentive"], ["ADDOTH", "Other addition"], ["PENALTY", "Penalty (days of pay)"], ["DEDOTH", "Other deduction"]];
  const f = { y: inp({ value: n.y, w: "s" }), p: inp({ value: n.p, w: "s" }), pernr: inp({ w: "s" }), wtype: sel(TYPES, "BONUS"), amount: inp({ w: "m", ph: "EGP" }),
    days: inp({ w: "s", ph: "days" }), text: inp({ w: "l" }) };
  const out = h("div");
  app.append(panel("Entry for the payroll month", grid(field("Year", f.y), field("Month", f.p), field("Employee", f.pernr, { req: true }), field("Type", f.wtype),
    field("Amount (EGP)", f.amount), field("Penalty days", f.days), field("Reason", f.text))),
    note("Bonus and incentive are added to the gross pay (taxed). A penalty is days of pay deducted from the net and goes to the workers' penalties fund (177500), as the labour law requires. Other deductions (damaged tools, mobile bill) are recovered by the company."), out);
  const load = async () => {
    const d = await run(() => api(`/api/hr/addpay?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: `Entries for payroll ${String(val(f.p)).padStart(2, "0")}/${val(f.y)}`, emptyText: "No entries", columns: [
      { key: "pernr", label: "Employee" }, { key: "name", label: "Name" }, { key: "text_wt", label: "Type" }, { key: "kind", label: "+/-", render: r => badge(r.kind === "+" ? "addition" : "deduction", r.kind === "+" ? "U" : "B") },
      { key: "amount", label: "Amount", type: "amt", sum: true }, { key: "days", label: "Days" }, { key: "text", label: "Reason" }, { key: "usnam", label: "By" },
      { key: "x", label: "", render: r => h("button.btn", { type: "button", on: { click: async () => { const x = await run(() => api("/api/hr/addpay/delete", { id: r.id })); if (x) { msg("S", x.message); load(); } } } }, "Delete") }] }));
  };
  f.y.addEventListener("change", load); f.p.addEventListener("change", load);
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/hr/addpay/add", { gjahr: val(f.y), perio: val(f.p), pernr: val(f.pernr), wtype: f.wtype.value, amount: val(f.amount), days: val(f.days), text: val(f.text) }));
    if (r) { msg("S", r.message); f.amount.value = ""; f.days.value = ""; f.text.value = ""; load(); } } }, { label: "Display", key: "F8", onClick: () => load() },
    { label: "Payroll run", onClick: () => go("PC00_M99_CALC") }]);
  load();
} });

// ------------------------------------------------------------------ ZHR_EVENTS
register("ZHR_EVENTS", { title: "HR Follow-up (probation, contracts, retirement)", async render(app) {
  const f = { kd: inp({ type: "date", value: today() }), days: inp({ value: "60", w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("From", f.kd), field("Next days", f.days))), out);
  const TB = { "Probation ends": "Q", "Contract ends": "B", "Retirement age": "Q" };
  const load = async () => {
    const d = await run(() => api(`/api/hr/events?key_date=${f.kd.value}&days=${val(f.days)}`)); if (!d) return;
    out.innerHTML = "";
    const cnt = t => d.rows.filter(r => r.typ === t).length;
    out.append(h("div.kpis", null, kpi("Act now", d.urgent, "within 14 / 30 days", d.urgent ? "neg" : "pos"), kpi("Probation ends", cnt("Probation ends")),
      kpi("Contracts end", cnt("Contract ends")), kpi("Retirement", cnt("Retirement age"), "within 12 months")),
      alv({ rows: d.rows, title: `Events until ${d.horizon}`, rowClass: r => r.urgent ? ".neg" : "", emptyText: "Nothing to follow up", columns: [
        { key: "date", label: "Date", type: "date" }, { key: "days", label: "In days", type: "int" }, { key: "typ", label: "Event", render: r => badge(r.typ, TB[r.typ] || "U") },
        { key: "pernr", label: "Employee", link: r => go("PA20", { id: r.pernr }) }, { key: "name", label: "Name" }, { key: "org", label: "Department" }, { key: "text", label: "What to do" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ ZHR_LEAVEBAL
register("ZHR_LEAVEBAL", { title: "Leave Balances (all employees)", async render(app) {
  const f = { y: inp({ value: now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/hr/leavebal?year=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Entitlement", d.entitlement, "days"), kpi("Taken", d.taken, "days"), kpi("Remaining", d.remaining, "days - plan the leave before year end", d.remaining ? "neg" : "")),
      alv({ rows: d.rows, title: `Annual leave ${d.year}`, columns: [{ key: "pernr", label: "Employee" }, { key: "name", label: "Name" }, { key: "org", label: "Department" },
        { key: "entitlement", label: "Entitlement", type: "int", sum: true }, { key: "taken", label: "Taken", type: "int", sum: true }, { key: "requested", label: "Requested", type: "int", sum: true },
        { key: "remaining", label: "Remaining", type: "int", sum: true }, { key: "casual_taken", label: "Casual taken", type: "int" }, { key: "used_pct", label: "Used %" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Leave requests", onClick: () => go("ZLEAVE") }]);
  load();
} });

// ------------------------------------------------------------------ ZHR_COST
register("ZHR_COST", { title: "Payroll Cost per Cost Center", async render(app) {
  const f = { y: inp({ value: now().y, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Year", f.y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/hr/cost?year=${val(f.y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Payroll cost", fmtAmt(d.total), `${d.year} - gross + employer insurance`)),
      alv({ rows: d.rows, title: `Payroll cost ${d.year} (EGP)`, emptyText: "No payroll results", columns: [{ key: "kostl", label: "Cost center" }, { key: "ktext", label: "Name" },
        { key: "heads", label: "Employees", type: "int" }, ...d.months.map(m => ({ key: "m" + String(m).padStart(2, "0"), label: MON[m - 1], type: "amt", sum: true })),
        { key: "total", label: "Total", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ ZHR_CLOSE
register("ZHR_CLOSE", { title: "HR & Payroll - Closing Management", async render(app, params) {
  const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
  const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not needed", ""] };
  app.append(panel(null, grid(field("Year", f.y), field("Month", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/hr/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
      alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Payroll month-end - in this order",
        columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode) },
          { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }),
      note("Enter everything of the month (leave, overtime, bonuses, penalties) before the payroll run; after posting, nothing of the month can change."));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });
})();
