/* NERP - Human Resources: personnel administration (PA40 / PA30 / PA20), organization
   (PPOME), time (PA61, PT50, ZLEAVE self-service), Egyptian payroll (PC00_M99_*),
   HR cockpit, headcount and customizing. */
"use strict";
(() => {
const { h, api, msg, run, register, go, toolbar, field, inp, sel, val, up, alv, today, confirmBox, fmtAmt, fmtDate } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
let META = null;
const meta = async () => (META = META || await api("/api/hr/meta"));
const STATUS = { R: "Requested", A: "Approved", X: "Rejected", C: "Cancelled" };
const PSTAT = { REL: "Released", POST: "Posted", PAID: "Paid" };
const ymNow = () => { const t = today(); return { y: t.slice(0, 4), p: String(+t.slice(5, 7)) }; };

// ------------------------------------------------------------------ cockpit
register("ZHR_COCKPIT", { title: "HR Cockpit", async render(app) {
  const d = await run(() => api("/api/hr/cockpit?currency=" + App.dispCur())); if (!d) return;
  const hc = d.headcount, last = d.last || {};
  app.append(panel(null, grid(field("Display currency", App.curSel(() => App.render()))), d.currency_note ? note(d.currency_note) : null));
  app.append(h("div.kpis", null, kpi("Headcount", hc.total, `${hc.male} men · ${hc.female} women`),
    kpi("Monthly salary cost", fmtAmt(hc.monthly_cost), `contractual, ${d.currency} · pay currencies ${(hc.by_currency || []).join(" / ")}`),
    kpi("Last payroll gross", last.gross !== undefined ? fmtAmt(last.gross) : "-", last.gjahr ? `${last.gjahr}/${last.perio} · ${last.employees} employees` : ""),
    kpi("Employer social insurance", last.si_er !== undefined ? fmtAmt(last.si_er) : "-", "last payroll"),
    kpi("On leave today", d.on_leave.length, d.on_leave.map(a => a.name).join(", ").slice(0, 60)),
    kpi("Open leave requests", d.open_requests, "approve in ZINBOX / PA61", d.open_requests ? "neg" : ""),
    kpi("Average age / service", `${hc.avg_age ?? "-"} / ${hc.avg_service ?? "-"}`, "years"),
    kpi("Hires / leavers this year", `${d.hires_ytd} / ${d.leavers_ytd}`, `turnover ${d.turnover_pct} %`)));
  app.append(h("div.ams-cols", null,
    alv({ rows: hc.by_org.map(([k, n]) => ({ org: k, n })), title: "Headcount by organizational unit", columns: [{ key: "org", label: "Unit" }, { key: "n", label: "Employees", type: "int", sum: true }] }),
    alv({ rows: d.trend, title: `Payroll by month (${d.currency})`, columns: [{ key: "gjahr", label: "Year", type: "int" }, { key: "perio", label: "Month", type: "int" },
      { key: "employees", label: "Employees", type: "int" }, { key: "gross", label: "Gross", type: "amt" }, { key: "overtime", label: "Overtime", type: "amt" },
      { key: "tax", label: "Income tax", type: "amt" }, { key: "si_er", label: "Employer SI", type: "amt" }, { key: "net", label: "Net pay", type: "amt" }] })));
  toolbar([{ label: "Employees", onClick: () => go("ZHR_EMPLOYEES") }, { label: "Hire (PA40)", primary: true, onClick: () => go("PA40") },
    { label: "Payroll run", onClick: () => go("PC00_M99_CALC") }]);
} });

// ------------------------------------------------------------------ employee list
register("ZHR_EMPLOYEES", { title: "Employee List", async render(app) {
  const m = await run(meta); if (!m) return;
  const txt = inp({ w: "m", ph: "name or number" }), org = sel([["", "(all units)"]].concat(m.orgunits.map(o => [o.orgeh, `${o.orgeh} ${o.text}`])), "", { w: "l" });
  const st = sel([["A", "Active"], ["W", "Left"], ["all", "All"]], "A"), out = h("div");
  app.append(panel(null, grid(field("Search", txt), field("Organizational unit", org), field("Status", st))), out);
  const exec = async () => {
    const rows = await run(() => api("/api/hr/employees?" + new URLSearchParams({ text: val(txt), orgeh: org.value, status: st.value }))); if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ rows, title: "Employees", columns: [{ key: "pernr", label: "Pers. no.", link: r => go("PA20", { id: r.pernr }) },
      { key: "name", label: "Name" }, { key: "name_ar", label: "Name (Arabic)" }, { key: "org_text", label: "Unit" }, { key: "job", label: "Job" },
      { key: "kostl", label: "Cost center" }, { key: "persk", label: "Subgroup" }, { key: "hire_date", label: "Hired", type: "date" },
      { key: "basic", label: "Basic salary", type: "amt" }, { key: "waers", label: "Crcy" }, { key: "status", label: "St" }] }));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }, { label: "Hire (PA40)", onClick: () => go("PA40") }]);
  exec();
} });

// ------------------------------------------------------------------ employee form (PA40 / PA30 / PA20)
function empForm(m, e, ro) {
  e = e || {};
  const f = {
    name: inp({ value: e.name, w: "l" }), name_ar: inp({ value: e.name_ar, w: "l" }), national_id: inp({ value: e.national_id, w: "m" }),
    birth_date: inp({ type: "date", value: e.birth_date }), gender: sel([["M", "Male"], ["F", "Female"]], e.gender || "M"),
    orgeh: sel(m.orgunits.map(o => [o.orgeh, `${o.orgeh} ${o.text}`]), e.orgeh || (m.orgunits[1] || m.orgunits[0] || {}).orgeh, { w: "l" }),
    plans: sel([["", "(no position)"]].concat(m.positions.filter(p => !p.holder || p.holder === e.pernr).map(p => [p.plans, `${p.plans} ${p.text}`])), e.plans || "", { w: "l" }),
    kostl: inp({ value: e.kostl, w: "s", list: "dl-kostl" }), job: inp({ value: e.job, w: "l" }),
    persg: sel(Object.entries(m.groups), e.persg || "1"), persk: sel(Object.entries(m.subgroups), e.persk || "S"),
    basic: inp({ value: e.basic, w: "m" }), allow_transport: inp({ value: e.allow_transport, w: "m" }),
    allow_housing: inp({ value: e.allow_housing, w: "m" }), allow_other: inp({ value: e.allow_other, w: "m" }),
    ins_wage: inp({ value: e.ins_wage || "", w: "m", ph: "= contractual wage" }), iban: inp({ value: e.iban, w: "l", ph: "EG.. (29 characters)" }),
    si_no: inp({ value: e.si_no, w: "m" }), phone: inp({ value: e.phone, w: "m" }), email: inp({ value: e.email, w: "l" }),
    bname: inp({ value: e.bname, w: "s", upper: true, ph: "NERP user" }),
    waers: sel([["EGP", "EGP - Egyptian pound"], ["USD", "USD - US dollar"]], e.waers || "EGP") };
  if (ro) Object.values(f).forEach(x => { x.disabled = true; });
  const body = h("div", null,
    panel("Personal data (IT0002)", grid(field("Name", f.name, { req: true }), field("Name (Arabic)", f.name_ar), field("National ID (14 digits)", f.national_id),
      field("Birth date", f.birth_date), field("Gender", f.gender), field("Phone", f.phone), field("E-mail", f.email), field("NERP user", f.bname))),
    panel("Organizational assignment (IT0001)", grid(field("Organizational unit", f.orgeh, { req: true }), field("Position", f.plans), field("Cost center", f.kostl),
      field("Job title", f.job), field("Employee group", f.persg), field("Employee subgroup", f.persk))),
    panel("Basic pay (IT0008) - per month in the pay currency", grid(field("Pay currency", f.waers), field("Basic salary", f.basic, { req: true }), field("Transport allowance", f.allow_transport),
      field("Housing allowance", f.allow_housing), field("Other allowance", f.allow_other), field("Insurable wage (optional)", f.ins_wage)),
      note("USD salaries: social insurance and income tax are calculated on the EGP amount at the month-end rate (OB08); the net pay is transferred in USD.")),
    panel("Bank and social insurance (IT0009)", grid(field("IBAN", f.iban), field("Social insurance no.", f.si_no))));
  const data = () => { const o = {}; for (const [k, x] of Object.entries(f)) o[k] = k === "bname" ? up(x) : val(x); return o; };
  return { body, data, f };
}

register("PA40", { title: "Personnel Actions", async render(app, params) {
  const m = await run(meta); if (!m) return;
  const act = sel([["01", "01 Hiring"], ["02", "02 Organizational change"], ["03", "03 Pay change"], ["10", "10 Leaving"]], params.act || "01", { w: "l" });
  const pernr = inp({ value: params.id || "", w: "m" }), begda = inp({ type: "date", value: today() }), area = h("div");
  app.append(panel("Action", grid(field("Personnel action", act), field("Personnel no.", pernr), field("Valid from", begda))), area);
  let form = null;
  const draw = async () => {
    area.innerHTML = ""; form = null;
    if (act.value === "01") { form = empForm(m, {}); area.append(form.body); return; }
    if (!val(pernr)) { area.append(note("Enter the personnel number and press Enter / Display.")); return; }
    const e = await run(() => api("/api/hr/employee/" + encodeURIComponent(val(pernr)))); if (!e) return;
    if (act.value === "10") {
      const reason = sel(Object.entries(m.leave_reasons), "01", { w: "l" });
      form = { leave: true, reason };
      area.append(panel(`Leaving: ${e.pernr} ${e.name}`, grid(field("Reason", reason)), note("The position becomes vacant; payroll stops after the leaving date.")));
      return;
    }
    form = empForm(m, e);
    area.append(form.body);
  };
  act.addEventListener("change", draw); pernr.addEventListener("change", draw);
  toolbar([{ label: "Display", onClick: draw }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!form) return draw();
    let r;
    if (act.value === "01") r = await run(() => api("/api/hr/hire", Object.assign(form.data(), { hire_date: begda.value })));
    else if (form.leave) {
      if (!await confirmBox("Leaving", `Save the leaving of ${val(pernr)} on ${fmtDate(begda.value)}?`)) return;
      r = await run(() => api(`/api/hr/employee/${encodeURIComponent(val(pernr))}/leave`, { leave_date: begda.value, reason: form.reason.value }));
    } else r = await run(() => api(`/api/hr/employee/${encodeURIComponent(val(pernr))}/change`, Object.assign(form.data(), { begda: begda.value, massn: act.value })));
    if (r) { msg("S", r.message); META = null; if (r.pernr) go("PA20", { id: r.pernr }); }
  } }]);
  draw();
} });

function empDisplay(edit) {
  return async (app, params) => {
    const m = await run(meta); if (!m) return;
    const pernr = inp({ value: params.id || "", w: "m" }), out = h("div");
    let form = null;
    app.append(panel(null, grid(field("Personnel no.", pernr, { req: true }))), out);
    const load = async () => {
      if (!val(pernr)) return msg("E", "Enter the personnel number", "PG", "001");
      const e = await run(() => api("/api/hr/employee/" + encodeURIComponent(val(pernr)))); if (!e) return;
      out.innerHTML = "";
      form = empForm(m, e, !edit);
      out.append(h("div.kpis", null, kpi(e.name, e.pernr, `${e.org_text} · ${e.position_text || e.job}`),
        kpi("Status", e.status === "A" ? "Active" : "Left", e.leave_date ? "left " + fmtDate(e.leave_date) : "since " + fmtDate(e.hire_date)),
        kpi("Service", `${e.service_years} years`), kpi("Leave " + e.quota.year, `${e.quota.remaining} of ${e.quota.entitlement}`, "days remaining")), form.body);
      if (!edit) out.append(
        alv({ rows: e.actions, title: "Personnel actions", columns: [{ key: "begda", label: "Date", type: "date" }, { key: "massn", label: "Action", render: r => h("span", null, m.actions[r.massn] || r.massn) },
          { key: "detail", label: "Detail" }, { key: "usnam", label: "By" }] }),
        alv({ rows: e.changes, title: "Change documents", columns: [{ key: "ts", label: "Time" }, { key: "field", label: "Field" }, { key: "old", label: "Old" }, { key: "new", label: "New" }, { key: "usnam", label: "By" }] }));
    };
    pernr.addEventListener("change", load);
    const btns = [{ label: "Display", key: "F8", primary: !edit, onClick: load }];
    if (edit) btns.push({ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      if (!form) return load();
      const r = await run(() => api(`/api/hr/employee/${encodeURIComponent(val(pernr))}/change`, form.data())); if (r) { msg("S", r.message); META = null; load(); } } });
    else btns.push({ label: "Change (PA30)", onClick: () => go("PA30", { id: val(pernr) }) }, { label: "Absences (PA61)", onClick: () => go("PA61", { id: val(pernr) }) });
    toolbar(btns);
    if (params.id) load();
  };
}
register("PA30", { title: "Maintain HR Master Data", render: empDisplay(true) });
register("PA20", { title: "Display HR Master Data", render: empDisplay(false) });

// ------------------------------------------------------------------ organization (PPOME)
register("PPOME", { title: "Change Organization and Staffing", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const units = await run(() => api("/api/hr/org")); if (!units) return;
    META = null; out.innerHTML = "";
    const byParent = {}; units.forEach(u => { (byParent[u.parent || ""] = byParent[u.parent || ""] || []).push(u); });
    const tree = h("div.hr-tree");
    const walk = (parent, depth) => (byParent[parent] || []).forEach(u => {
      tree.append(h("div.hr-unit", { style: { marginLeft: depth * 22 + "px" } }, h("b", null, `▣ ${u.orgeh} ${u.text}`),
        h("span.hr-meta", null, ` cost center ${u.kostl || "-"} · ${u.headcount} employees`)));
      u.positions.forEach(p => tree.append(h("div.hr-pos", { style: { marginLeft: depth * 22 + 22 + "px" } },
        `◦ ${p.plans} ${p.text} `, p.pernr ? h("a", { href: "#/PA20?id=" + p.pernr }, `👤 ${p.pernr} ${p.name}`) : h("span.neg", null, "vacant"))));
      walk(u.orgeh, depth + 1);
    });
    walk("", 0);
    const uo = { orgeh: inp({ w: "m" }), text: inp({ w: "l" }), parent: sel([["", "(top)"]].concat(units.map(u => [u.orgeh, `${u.orgeh} ${u.text}`])), "", { w: "l" }), kostl: inp({ w: "s", list: "dl-kostl" }) };
    const po = { plans: inp({ w: "m" }), text: inp({ w: "l" }), orgeh: sel(units.map(u => [u.orgeh, `${u.orgeh} ${u.text}`]), (units[0] || {}).orgeh, { w: "l" }), kostl: inp({ w: "s", list: "dl-kostl" }) };
    out.append(h("div.ams-cols", null, panel("Organizational plan", tree),
      h("div", null,
        panel("Create / change organizational unit", grid(field("Unit no.", uo.orgeh, { req: true }), field("Name", uo.text, { req: true }), field("Superior unit", uo.parent), field("Cost center", uo.kostl)),
          h("button.btn.primary", { type: "button", on: { click: async () => { const r = await run(() => api("/api/hr/orgunit", { orgeh: val(uo.orgeh), text: val(uo.text), parent: uo.parent.value, kostl: up(uo.kostl) })); if (r) { msg("S", r.message); load(); } } } }, "Save unit")),
        panel("Create / change position", grid(field("Position no.", po.plans, { req: true }), field("Name", po.text, { req: true }), field("Unit", po.orgeh), field("Cost center", po.kostl)),
          h("button.btn.primary", { type: "button", on: { click: async () => { const r = await run(() => api("/api/hr/position", { plans: val(po.plans), text: val(po.text), orgeh: po.orgeh.value, kostl: up(po.kostl) })); if (r) { msg("S", r.message); load(); } } } }, "Save position")))));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ time (PA61 / PT50)
register("PA61", { title: "Maintain Time Data (Absences, Overtime)", async render(app, params) {
  const m = await run(meta); if (!m) return;
  const pernr = inp({ value: params.id || "", w: "m" }), out = h("div");
  const a = { awart: sel(Object.entries(m.absence_types), "ANN", { w: "l" }), begda: inp({ type: "date", value: today() }), endda: inp({ type: "date", value: today() }), reason: inp({ w: "l" }) };
  const o = { datum: inp({ type: "date", value: today() }), ottype: sel(Object.entries(m.overtime_types), "D", { w: "l" }), hours: inp({ w: "s", value: "2" }) };
  app.append(panel(null, grid(field("Personnel no. (empty = all)", pernr))),
    h("div.ams-cols", null,
      panel("Absence / leave", grid(field("Type", a.awart), field("From", a.begda), field("To", a.endda), field("Reason", a.reason)),
        h("button.btn.primary", { type: "button", on: { click: async () => {
          if (!val(pernr)) return msg("E", "Enter the personnel number", "PG", "001");
          const r = await run(() => api("/api/hr/absence", { pernr: val(pernr), awart: a.awart.value, begda: a.begda.value, endda: a.endda.value, reason: val(a.reason) }));
          if (r) { msg("S", r.message); load(); } } } }, "Save absence"), note("Annual and casual leave are checked against the quota (PT50). Every absence needs an approval (P_ABSENCE).")),
      panel("Overtime", grid(field("Date", o.datum), field("Type", o.ottype), field("Hours", o.hours)),
        h("button.btn.primary", { type: "button", on: { click: async () => {
          if (!val(pernr)) return msg("E", "Enter the personnel number", "PG", "001");
          const r = await run(() => api("/api/hr/overtime", { pernr: val(pernr), datum: o.datum.value, ottype: o.ottype.value, hours: val(o.hours) }));
          if (r) { msg("S", r.message); load(); } } } }, "Save overtime"), note("Paid with the next payroll: +35 % day, +70 % night, +100 % rest day on the hourly rate."))), out);
  const decide = async (r, yes) => { const x = await run(() => api("/api/hr/absence/decide", { id: r.id, approve: yes })); if (x) { msg("S", x.message); load(); } };
  const load = async () => {
    const q = new URLSearchParams({ pernr: val(pernr) });
    const [ab, ot] = await Promise.all([run(() => api("/api/hr/absences?" + q)), run(() => api("/api/hr/overtime?" + q))]);
    out.innerHTML = "";
    if (ab) out.append(alv({ rows: ab.map(x => Object.assign(x, { st: STATUS[x.status] })), title: "Absences", rowClass: x => x.status === "R" ? ".hr-open" : "",
      columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "type_text", label: "Type" }, { key: "begda", label: "From", type: "date" },
        { key: "endda", label: "To", type: "date" }, { key: "days", label: "Days", type: "int" }, { key: "st", label: "Status" }, { key: "reason", label: "Reason" },
        { key: "act", label: "", render: x => x.status === "R" ? h("span", null, h("button.btn.primary", { type: "button", on: { click: () => decide(x, true) } }, "Approve"), " ",
          h("button.btn", { type: "button", on: { click: () => decide(x, false) } }, "Reject")) : x.status === "A" ? h("button.btn", { type: "button", on: { click: async () => {
            if (!await confirmBox("Cancel absence", "Cancel this approved absence?")) return; const y = await run(() => api("/api/hr/absence/cancel", { id: x.id })); if (y) { msg("S", y.message); load(); } } } }, "Cancel") : null }] }));
    if (ot) out.append(alv({ rows: ot, title: "Overtime", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "datum", label: "Date", type: "date" },
      { key: "ottype", label: "Type", render: x => h("span", null, m.overtime_types[x.ottype]) }, { key: "hours", label: "Hours", type: "qty", sum: true }] }));
  };
  pernr.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Quota overview (PT50)", onClick: () => go("PT50") }]);
  load();
} });

register("PT50", { title: "Quota Overview (Annual Leave)", async render(app) {
  const y = inp({ value: today().slice(0, 4), w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Year", y))), out);
  const exec = async () => { const rows = await run(() => api("/api/hr/quotas?year=" + val(y))); if (!rows) return; out.innerHTML = "";
    out.append(alv({ rows, title: "Leave entitlement and balance", rowClass: r => r.remaining < 3 ? ".neg" : "", columns: [{ key: "pernr", label: "Pers. no.", link: r => go("PA61", { id: r.pernr }) },
      { key: "name", label: "Name" }, { key: "org_text", label: "Unit" }, { key: "entitlement", label: "Entitlement", type: "int" }, { key: "taken", label: "Taken", type: "int" },
      { key: "requested", label: "Requested", type: "int" }, { key: "remaining", label: "Remaining", type: "int" }, { key: "casual_taken", label: "Casual taken", type: "int" }] })); };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]);
  exec();
} });

// ------------------------------------------------------------------ self-service
register("ZLEAVE", { title: "My Leave and Payslips (Self-Service)", async render(app) {
  const d = await run(() => api("/api/hrself")); if (!d) return app.append(note("Your NERP user must be entered in your employee record (PA30, field 'NERP user')."));
  const m = { ANN: "Annual leave", CAS: "Casual leave", SIC: "Sick leave", UNP: "Unpaid leave" };
  const f = { awart: sel(Object.entries(m), "ANN"), begda: inp({ type: "date", value: today() }), endda: inp({ type: "date", value: today() }), reason: inp({ w: "l" }) };
  app.append(h("div.kpis", null, kpi(d.name, d.pernr, `${d.org_text} · ${d.position_text}`), kpi(`Leave ${d.quota.year}`, `${d.quota.remaining} days`, `of ${d.quota.entitlement} · requested ${d.quota.requested}`),
    kpi("Casual leave", `${d.quota.casual_taken} / ${d.quota.casual_max}`, "days taken")),
    panel("Request leave", grid(field("Type", f.awart), field("From", f.begda), field("To", f.endda), field("Reason", f.reason)),
      h("button.btn.primary", { type: "button", on: { click: async () => { const r = await run(() => api("/api/hrself/leave", { awart: f.awart.value, begda: f.begda.value, endda: f.endda.value, reason: val(f.reason) })); if (r) { msg("S", r.message); go("ZLEAVE"); App.render(); } } } }, "Send request")),
    alv({ rows: d.absences.map(x => Object.assign(x, { st: STATUS[x.status] })), title: "My absences", columns: [{ key: "type_text", label: "Type" }, { key: "begda", label: "From", type: "date" },
      { key: "endda", label: "To", type: "date" }, { key: "days", label: "Days", type: "int" }, { key: "st", label: "Status" }] }),
    alv({ rows: d.payslips, title: "My payslips", columns: [{ key: "gjahr", label: "Year", type: "int" }, { key: "perio", label: "Month", type: "int" }, { key: "net", label: "Net pay", type: "amt" },
      { key: "p", label: "", render: r => h("button.btn", { type: "button", on: { click: async () => { const x = await run(() => api(`/api/hrself/payslip?gjahr=${r.gjahr}&perio=${r.perio}`)); if (x) { const w = window.open("", "_blank"); w.document.write(x.html); w.document.close(); } } } }, "Payslip") }] }));
} });

// ------------------------------------------------------------------ payroll
function periodSel(params) {
  const n = ymNow();
  return { y: inp({ value: params.year || n.y, w: "s" }), p: inp({ value: params.period || n.p, w: "s" }) };
}
const payCols = [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "kostl", label: "Cost ctr" }, { key: "paid_days", label: "Days", type: "int" },
  { key: "basic", label: "Basic", type: "amt", sum: true }, { key: "allowances", label: "Allowances", type: "amt", sum: true }, { key: "overtime", label: "Overtime", type: "amt", sum: true },
  { key: "unpaid", label: "Unpaid", type: "amt", sum: true }, { key: "gross", label: "Gross", type: "amt", sum: true }, { key: "si_ee", label: "SI 11 %", type: "amt", sum: true },
  { key: "tax", label: "Income tax", type: "amt", sum: true }, { key: "martyrs", label: "Martyrs", type: "amt", sum: true }, { key: "net", label: "Net pay", type: "amt", sum: true },
  { key: "si_er", label: "Employer SI", type: "amt", sum: true },
  { key: "waers", label: "Pay crcy" }, { key: "net_fc", label: "Net pay (pay currency)", type: "amt" }];

function payrollScreen(mode) {
  return async (app, params) => {
    const s = periodSel(params), out = h("div");
    app.append(panel(null, grid(field("Year", s.y), field("Month", s.p))), out);
    const body = () => ({ gjahr: val(s.y), perio: val(s.p) });
    const load = async (res) => {
      const d = await run(() => api("/api/hr/payroll?" + new URLSearchParams(body()))); if (!d) return;
      out.innerHTML = "";
      const st = d.status;
      out.append(h("div.kpis", null, kpi("Status", st ? PSTAT[st.status] : "not run", st ? `${st.employees} employees · ${st.usnam}` : ""),
        kpi("Gross", fmtAmt((d.totals || {}).gross || 0)), kpi("Net pay", fmtAmt((d.totals || {}).net || 0)), kpi("Income tax", fmtAmt((d.totals || {}).tax || 0)),
        kpi("Social insurance", fmtAmt(((d.totals || {}).si_ee || 0) + ((d.totals || {}).si_er || 0)), "employee + employer"),
        st && st.belnr ? kpi("Posting document", st.belnr, st.pay_belnr ? "payment " + st.pay_belnr : "") : null));
      const rows = res || d.results || [];
      out.append(alv({ rows, title: res ? "Simulation (nothing saved)" : "Payroll results", columns: mode === "cedt" ? payCols.slice(0, 2).concat([{ key: "net", label: "Net pay", type: "amt" },
        { key: "slip", label: "", render: r => h("button.btn", { type: "button", on: { click: () => App.printForm("PAYSLIP", `${val(s.y)}-${String(val(s.p)).padStart(2, "0")}-${r.pernr}`) } }, "Payslip") }]) : payCols,
        emptyText: "No payroll results - run the payroll (PC00_M99_CALC)" }));
      if (mode === "dta" && st && st.status === "PAID") out.append(note("Paid. The bank transfer list: employee, IBAN and net pay (above)."));
    };
    const act = async (a, text) => {
      if (text && !await confirmBox(text, `${text} for ${val(s.y)}/${val(s.p)}?`)) return;
      const r = await run(() => api("/api/hr/payroll/" + a, body())); if (!r) return;
      msg("S", r.message); load(a === "simulate" ? r.results : null);
    };
    const btns = [{ label: "Display", key: "F8", onClick: () => load() }];
    if (mode === "calc") btns.push({ label: "Simulate", onClick: () => act("simulate") }, { label: "Run payroll (release)", primary: true, onClick: () => act("run", "Run the payroll") });
    if (mode === "cipe") btns.push({ label: "Post to accounting", primary: true, onClick: () => act("post", "Post the payroll") }, { label: "Reverse posting", danger: true, onClick: () => act("reverse", "Reverse the payroll posting") });
    if (mode === "dta") btns.push({ label: "Transfer net pay", primary: true, onClick: () => act("pay", "Transfer the net pay to the employees") });
    toolbar(btns);
    load();
  };
}
register("PC00_M99_CALC", { title: "Payroll Run (Egypt)", render: payrollScreen("calc") });
register("PC00_M99_CIPE", { title: "Payroll Posting to Accounting", render: payrollScreen("cipe") });
register("PC00_M99_DTA", { title: "Salary Bank Transfer", render: payrollScreen("dta") });
register("PC00_M99_CEDT", { title: "Remuneration Statement (Payslip)", render: payrollScreen("cedt") });
register("PC00_M99_CWTR", { title: "Payroll Journal", render: payrollScreen("cwtr") });

// ------------------------------------------------------------------ headcount, customizing
register("ZHR_HEADCOUNT", { title: "Headcount Report", async render(app) {
  const d = await run(() => api("/api/hr/cockpit?currency=" + App.dispCur())); if (!d) return;
  const hc = d.headcount;
  app.append(h("div.kpis", null, kpi("Headcount", hc.total), kpi("Men / women", `${hc.male} / ${hc.female}`), kpi("Average age", hc.avg_age), kpi("Average service", `${hc.avg_service} years`)),
    h("div.ams-cols", null,
      alv({ rows: hc.by_org.map(([k, n]) => ({ k, n })), title: "By organizational unit", columns: [{ key: "k", label: "Unit" }, { key: "n", label: "Employees", type: "int", sum: true }] }),
      alv({ rows: hc.by_cc.map(([k, n]) => ({ k, n })), title: "By cost center", columns: [{ key: "k", label: "Cost center" }, { key: "n", label: "Employees", type: "int", sum: true }] }),
      alv({ rows: hc.by_group.map(([k, n]) => ({ k: { W: "Workers", S: "Staff", M: "Management" }[k] || k, n })), title: "By employee subgroup", columns: [{ key: "k", label: "Subgroup" }, { key: "n", label: "Employees", type: "int", sum: true }] })));
} });

register("ZHR_CONF", { title: "HR Customizing (Egypt: social insurance, tax, overtime, leave)", async render(app) {
  const rows = await run(() => api("/api/hr/config")); if (!rows) return;
  const ins = {};
  const tb = h("tbody", null, rows.map(r => { ins[r.key] = inp({ value: r.value, w: r.key === "tax_brackets" ? "xl" : "m" }); return h("tr", null, h("td", null, h("b", null, r.key)), h("td", null, r.text), h("td", null, ins[r.key])); }));
  app.append(panel(null, h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Setting"), h("th", null, "Meaning"), h("th", null, "Value"))), tb)),
    note("Delivered with the rules of social insurance law 148/2019 and the salary tax brackets of law 7/2023. Confirm every value with your payroll / tax adviser before go-live."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const values = {}; for (const [k, x] of Object.entries(ins)) values[k] = val(x);
    const r = await run(() => api("/api/hr/config", { values })); if (r) msg("S", r.message); } }]);
} });
})();
