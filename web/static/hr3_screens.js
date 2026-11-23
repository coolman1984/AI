/* NERP - HR: time clock (ZHR_CLOCK), daily time evaluation (ZHR_TIMEEVAL), monthly attendance (ZHR_ATTEND),
   overtime notice Law 14/2025 (ZHR_OTNOTICE), shifts and holidays (ZHR_SHIFTS), training (ZHR_TRAINING),
   appraisal (ZHR_APPRAISAL), end-of-service settlement (ZHR_EOS) and HR analytics (ZHR_ANALYTICS). */
"use strict";
(() => {
const { h, api, msg, run, ask, field, inp, sel, val, alv, register, go, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const hm = m => m ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}` : "";
const STC = { PRESENT: "U", LATE: "Q", ABSENT: "B", LEAVE: "", OFF: "", HOLIDAY: "", INCOMPLETE: "B" };
const CSS = `.hr-clock{max-width:560px}.hr-clock input{font-size:28px;padding:12px;width:100%;border:2px solid #1f5fae;border-radius:12px;text-align:center;letter-spacing:2px}
.hr-clock .b{display:flex;gap:10px;margin-top:12px}.hr-clock .b button{flex:1;font-size:24px;font-weight:800;padding:20px;border:0;border-radius:12px;color:#fff;cursor:pointer}
.hr-in{background:#1a9a55}.hr-out{background:#b3261e}.hr-time{font-size:44px;font-weight:800;color:#0b2a55;text-align:center;margin:4px 0 12px}`;

// ------------------------------------------------------------------ time clock
register("ZHR_CLOCK", { title: "Time Clock - Clock In / Out", async render(app) {
  if (!document.getElementById("hr3-css")) document.head.append(h("style#hr3-css", { html: CSS }));
  const tm = h("div.hr-time"), p = h("input", { placeholder: "personnel number" }), last = h("div");
  const tick = () => { if (!document.body.contains(tm)) return; tm.textContent = new Date().toTimeString().slice(0, 8); setTimeout(tick, 1000); };
  const load = async () => { const d = await run(() => api("/api/hr/time/setup")); if (!d) return; last.innerHTML = "";
    last.append(alv({ rows: d.punches, compact: true, title: "Last clockings", columns: [{ key: "ts", label: "Time" }, { key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" },
      { key: "kind", label: "", render: r => badge(r.kind === "IN" ? "IN" : "OUT", r.kind === "IN" ? "U" : "B") }, { key: "source", label: "Source" }] })); };
  const go_ = async kind => { if (!val(p)) { msg("E", "Enter the personnel number"); return; }
    const r = await run(() => api("/api/hr/time/punch", { pernr: val(p), kind })); if (r) { msg("S", r.message); p.value = ""; p.focus(); load(); } };
  p.addEventListener("keydown", e => { if (e.key === "Enter") go_(null); });
  app.append(h("div.hr-clock", null, panel(null, tm, p, h("div.b", null, h("button.hr-in", { type: "button", on: { click: () => go_("IN") } }, "▶ IN"),
    h("button.hr-out", { type: "button", on: { click: () => go_("OUT") } }, "■ OUT")), note("Enter = the next clocking (IN after OUT). On the factory gate this screen runs on a tablet or a badge reader."))), last);
  tick(); load(); p.focus();
} });

// ------------------------------------------------------------------ daily evaluation
register("ZHR_TIMEEVAL", { title: "Daily Time Evaluation", async render(app, params) {
  const dt = inp({ type: "date", value: params.day || today() }), out = h("div");
  app.append(panel(null, grid(field("Day", dt))), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/time/day?day=" + dt.value)); if (!d) return;
    out.innerHTML = "";
    const c = d.counts;
    out.append(h("div.kpis", null, kpi("Present", String(c.PRESENT + c.LATE), `${c.LATE} late`, c.LATE ? "neg" : "pos"), kpi("Absent (unexcused)", String(c.ABSENT), "", c.ABSENT ? "neg" : "pos"),
      kpi("On leave", String(c.LEAVE)), kpi("Clock-out missing", String(c.INCOMPLETE), "", c.INCOMPLETE ? "neg" : ""),
      kpi("Overtime", hm(d.rows.reduce((a, r) => a + r.ot_min, 0)) || "0:00", `${d.rows.filter(r => r.ot_min && !r.ot_posted).length} not approved`),
      kpi("Over the daily limit", String(d.rows.filter(r => r.over_limit).length), "", d.rows.some(r => r.over_limit) ? "neg" : "")),
      d.rows.length ? alv({ rows: d.rows, title: "Evaluation", rowClass: r => r.status === "ABSENT" || r.over_limit ? ".neg" : "", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" },
        { key: "shift", label: "Shift" }, { key: "status", label: "Status", render: r => badge(d.status[r.status], STC[r.status]) }, { key: "first_in", label: "In" }, { key: "last_out", label: "Out" },
        { key: "worked_min", label: "Worked", render: r => hm(r.worked_min) }, { key: "late_min", label: "Late (min)", type: "int" }, { key: "early_min", label: "Early (min)", type: "int" },
        { key: "ot_min", label: "Overtime", render: r => r.ot_min ? `${hm(r.ot_min)} ${r.ot_type}` : "" }, { key: "ot_posted", label: "Approved", render: r => r.ot_min ? (r.ot_posted ? "✓" : "open") : "" },
        { key: "absence", label: "Absence" }] }) : note("Not evaluated yet - press Evaluate."));
  };
  dt.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Evaluate", onClick: async () => { const r = await run(() => api("/api/hr/time/evaluate", { day: dt.value })); if (r) { msg("S", `${r.rows.length} employees evaluated`); load(); } } },
    { label: "Approve overtime", onClick: async () => { const r = await run(() => api("/api/hr/time/approve", { day: dt.value })); if (r) { msg("S", r.message); load(); } } },
    { label: "Time clock", onClick: () => go("ZHR_CLOCK") }]);
  load();
} });

// ------------------------------------------------------------------ monthly attendance
register("ZHR_ATTEND", { title: "Monthly Attendance Report", async render(app) {
  const mo = inp({ value: today().slice(0, 7), w: "s", ph: "YYYY-MM" }), out = h("div");
  app.append(panel(null, grid(field("Month", mo))), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/time/month?month=" + val(mo))); if (!d) return;
    out.innerHTML = "";
    const s = k => d.rows.reduce((a, r) => a + (r[k] || 0), 0);
    out.append(h("div.kpis", null, kpi("Employees", String(d.rows.length)), kpi("Absent days", String(s("absent")), "", s("absent") ? "neg" : "pos"),
      kpi("Late arrivals", String(s("late_days")), `${s("late_min")} minutes`), kpi("Overtime", (s("ot") / 60).toFixed(1) + " h"), kpi("Missing clock-outs", String(s("incomplete")), "", s("incomplete") ? "neg" : "")),
      alv({ rows: d.rows, title: "Per employee", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "present", label: "Present", type: "int" },
        { key: "late_days", label: "Late days", type: "int" }, { key: "late_min", label: "Late min", type: "int" }, { key: "absent", label: "Absent", type: "int" }, { key: "leave", label: "Leave", type: "int" },
        { key: "planned_h", label: "Planned h" }, { key: "worked_h", label: "Worked h" }, { key: "ot_h", label: "Overtime h" }, { key: "punctuality", label: "Punctuality %" }, { key: "attendance", label: "Attendance %" },
        { key: "over_limit", label: "Days over limit", type: "int" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ overtime notice (Law 14/2025)
register("ZHR_OTNOTICE", { title: "Overtime Notice to the Labour Office (Law 14/2025)", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/hr/time/notices")); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Overdue notices", String(d.overdue), `more than ${d.days} days after the overtime`, d.overdue ? "neg" : "pos"), kpi("Due", String(d.due), "notify in time", d.due ? "neg" : "")),
      alv({ rows: d.rows, title: "Days with overtime", rowClass: r => r.state === "overdue" ? ".neg" : "", columns: [{ key: "day", label: "Day" }, { key: "people", label: "People", type: "int" },
        { key: "hours", label: "Hours" }, { key: "due", label: "Notify by" }, { key: "state", label: "Status", render: r => badge(r.state, r.state === "notified" ? "U" : r.state === "overdue" ? "B" : "Q") },
        { key: "ref", label: "Reference" }, { key: "x", label: "", render: r => r.state === "notified" ? "" : btn("Mark notified", async () => {
          const x = await ask("Notice of " + r.day, [{ name: "ref", label: "Reference of the notice", value: "" }]); if (!x) return;
          const res = await run(() => api("/api/hr/time/notify", { day: r.day, ref: x.ref })); if (res) { msg("S", res.message); load(); } }) }] }),
      note("Labour Law 14/2025 replaced the prior approval of overtime by a notice to the labour office within 7 days (secondary sources - confirm with the labour lawyer)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ shifts and holidays
register("ZHR_SHIFTS", { title: "Shifts, Public Holidays and Shift Assignment", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/hr/time/setup")); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.shifts, title: "Shifts", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Shift" }, { key: "start", label: "Start" }, { key: "end", label: "End" },
      { key: "break_min", label: "Break (min)", type: "int" }, { key: "night", label: "Night", render: r => r.night ? "✓" : "" }, { key: "grace_min", label: "Grace (min)", type: "int" },
      { key: "ot_after_min", label: "Overtime after (min)", type: "int" }] }),
      alv({ rows: d.employees, title: "Shift per employee", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "job", label: "Job" }, { key: "shift", label: "Shift" },
        { key: "time_rec", label: "Time clock", render: r => r.time_rec ? "✓" : "exempt" }] }),
      alv({ rows: d.holidays, title: "Public holidays", columns: [{ key: "day", label: "Day", type: "date" }, { key: "text", label: "Holiday" }] }),
      note("Religious holidays move with the lunar calendar - enter them each year (Holiday button)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Shift", onClick: async () => { const x = await ask("Shift", [{ name: "code", label: "Code" }, { name: "text", label: "Text" }, { name: "start", label: "Start HH:MM", value: "08:00" },
      { name: "end", label: "End HH:MM", value: "16:30" }, { name: "break_min", label: "Break (min)", value: "30" }, { name: "night", label: "Night shift (1 / 0)", value: "0" },
      { name: "grace_min", label: "Grace (min)", value: "10" }, { name: "ot_after_min", label: "Overtime after (min)", value: "30" }]); if (!x) return;
      const r = await run(() => api("/api/hr/time/shift", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Assign shift", onClick: async () => { const x = await ask("Assign shift", [{ name: "pernr", label: "Personnel no." }, { name: "shift", label: "Shift code" }]); if (!x) return;
      const r = await run(() => api("/api/hr/time/assign", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Holiday", onClick: async () => { const x = await ask("Public holiday", [{ name: "day", label: "Day (YYYY-MM-DD)" }, { name: "text", label: "Name" }]); if (!x) return;
      const r = await run(() => api("/api/hr/time/holiday", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ training
register("ZHR_TRAINING", { title: "Training Plan and Results", async render(app) {
  const y = inp({ value: today().slice(0, 4), w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Year", y))), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/training?year=" + val(y))); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Trainings", String(d.rows.length)), kpi("Training hours", String(d.hours)), kpi("Hours per employee", String(d.hours_per_employee)), kpi("Cost", d.cost.toLocaleString("en-US") + " EGP")),
      alv({ rows: d.rows, title: "Trainings", columns: [{ key: "id", label: "No.", type: "int" }, { key: "datum", label: "Date", type: "date" }, { key: "title", label: "Training" }, { key: "skill", label: "Certifies skill" },
        { key: "trainer", label: "Trainer" }, { key: "participants", label: "Participants", type: "int" }, { key: "passed", label: "Passed", type: "int" }, { key: "names", label: "Names" },
        { key: "hours_total", label: "Hours" }, { key: "cost_egp", label: "Cost" }, { key: "status", label: "Status", render: r => badge(r.status, r.status === "DONE" ? "U" : "Q") },
        { key: "x", label: "", render: r => r.status === "DONE" ? "" : btn("Complete", async () => {
          const x = await ask("Complete training " + r.id, [{ name: "failed", label: "Personnel no. who FAILED (comma separated, empty = all passed)", value: "" }]); if (!x) return;
          const res = await run(() => api("/api/hr/training/complete", { id: r.id, failed: x.failed })); if (res) { msg("S", res.message); load(); } }) }] }),
      note("Passing a training with a skill certifies the participant in the skills matrix (ZHR_SKILLS) - the GMES stations accept him at once."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Plan training", onClick: async () => {
    const x = await ask("Plan training", [{ name: "title", label: "Title" }, { name: "skill", label: "Certifies skill (optional)" }, { name: "datum", label: "Date (YYYY-MM-DD)", value: today() },
      { name: "hours", label: "Hours", value: "8" }, { name: "trainer", label: "Trainer" }, { name: "cost", label: "Cost EGP", value: "0" }, { name: "participants", label: "Participants (personnel no., comma separated)" }]); if (!x) return;
    const r = await run(() => api("/api/hr/training/plan", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ appraisal
register("ZHR_APPRAISAL", { title: "Performance Appraisal", async render(app) {
  const y = inp({ value: String(Number(today().slice(0, 4)) - 1), w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Year", y))), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/appraisal?year=" + val(y))); if (!d) return;
    out.innerHTML = "";
    const mx = Math.max(1, ...d.distribution.map(x => Math.max(x.pct, x.guide)));
    out.append(h("div.kpis", null, kpi("Appraised", `${d.done} / ${d.employees}`, `${d.final} final`), kpi("Average rating", String(d.average ?? "-"))),
      panel("Rating distribution vs guideline", ...d.distribution.map(x => h("div", { style: { display: "grid", gridTemplateColumns: "210px 1fr 90px", gap: "8px", alignItems: "center", margin: "4px 0" } },
        h("span", null, `${x.rating} - ${x.text}`), h("div", { style: { position: "relative", height: "16px", background: "#eef1f5", borderRadius: "8px" } },
          h("span", { style: { position: "absolute", inset: "0 auto 0 0", width: (100 * x.pct / mx) + "%", background: "#1f5fae", borderRadius: "8px" } }),
          h("span", { style: { position: "absolute", top: "-3px", bottom: "-3px", left: (100 * x.guide / mx) + "%", width: "3px", background: "#e08a00" } })),
        h("span", null, `${x.count} (${x.pct}%)`)))),
      alv({ rows: d.rows, title: "Appraisals", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "job", label: "Job" }, { key: "goals", label: "Goals", type: "int" },
        { key: "competencies", label: "Competencies", type: "int" }, { key: "attendance", label: "Attendance", type: "int" }, { key: "rating", label: "Rating", type: "int" }, { key: "rating_text", label: "" },
        { key: "status", label: "Status", render: r => badge(r.status, r.status === "FINAL" ? "U" : "Q") }, { key: "comment", label: "Comment" }] }),
      note("Rating = goals 50 % + competencies 30 % + attendance 20 % (the attendance score comes from the time evaluation). Ratings 1-2 need an improvement plan. Orange mark = guideline."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Appraise", onClick: async () => {
    const x = await ask("Appraisal " + val(y), [{ name: "pernr", label: "Personnel no." }, { name: "goals", label: "Goals 1-5", value: "3" }, { name: "competencies", label: "Competencies 1-5", value: "3" },
      { name: "attendance", label: "Attendance 1-5 (empty = from time evaluation)", value: "" }, { name: "comment", label: "Comment / improvement plan" }, { name: "final", label: "Final (1 / 0)", value: "0" }]); if (!x) return;
    const r = await run(() => api("/api/hr/appraisal", Object.assign({ year: val(y) }, x, { final: x.final === "1" }))); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ end of service
register("ZHR_EOS", { title: "End-of-Service Settlement (Law 14/2025)", async render(app, params) {
  const p = inp({ w: "m", value: params.pernr || "" }), d = inp({ type: "date", value: today() }), r = sel([["01", "Resignation"], ["02", "End of contract"], ["03", "Dismissal"], ["04", "Retirement"], ["05", "Death"]], "01"),
    n = sel([["1", "Notice given"], ["0", "Notice NOT given"]], "1"), out = h("div");
  app.append(panel(null, grid(field("Personnel no.", p), field("Leaving date", d), field("Reason", r), field("Notice", n))), out);
  const load = async () => {
    if (!val(p)) return;
    const x = await run(() => api(`/api/hr/eos?pernr=${val(p)}&date=${d.value}&reason=${r.value}&notice=${n.value}`)); if (!x) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Employee", x.name, `${x.contract} · hired ${x.hire_date}`), kpi("Service", `${x.years_exact} years`), kpi("Monthly pay", x.monthly_pay.toLocaleString("en-US") + " EGP"),
      kpi("Settlement", x.total.toLocaleString("en-US") + " EGP", "", "pos"), x.contingent ? kpi("If the dismissal is found unlawful", "+" + x.contingent.toLocaleString("en-US") + " EGP", "court risk", "neg") : null),
      alv({ rows: x.lines, title: "Components", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Component" }, { key: "amount", label: "EGP", type: "amt" },
        { key: "contingent", label: "", render: l => l.contingent ? "contingent" : "" }] }), note(x.note));
  };
  toolbar([{ label: "Calculate", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ analytics
register("ZHR_ANALYTICS", { title: "HR Analytics", async render(app) {
  const y = inp({ value: today().slice(0, 4), w: "s" }), out = h("div");
  app.append(panel(null, grid(field("Year", y))), out);
  const load = async () => {
    const d = await run(() => api("/api/hr/analytics?year=" + val(y))); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Headcount", String(d.headcount), `${d.women_pct}% women`), kpi("Turnover (year, annualised)", d.turnover_annualised + " %", `${d.turnover_ytd}% so far`, d.turnover_annualised > 15 ? "neg" : "pos"),
      kpi("Absenteeism", d.absenteeism_avg + " %", "unplanned absence", d.absenteeism_avg > 3 ? "neg" : "pos"), kpi("Overtime ratio", d.overtime_ratio_avg + " %", "of planned hours", d.overtime_ratio_avg > 10 ? "neg" : ""),
      kpi("Average tenure", d.avg_tenure + " years", `average age ${d.avg_age}`), kpi("Training", d.training_hours_per_employee + " h", "per employee this year"),
      kpi("Certificates", `${d.certs_expired} expired`, `${d.certs_expiring} expiring · single-person skills: ${d.single_skill_risk.join(", ") || "none"}`, d.certs_expired ? "neg" : "pos"),
      kpi("Appraisal average", String(d.appraisal_average ?? "-"), `${d.appraisals_done} appraised`)),
      alv({ rows: d.months, title: "Month by month", columns: [{ key: "month", label: "Month" }, { key: "headcount", label: "Headcount", type: "int" }, { key: "hires", label: "Hires", type: "int" },
        { key: "leavers", label: "Leavers", type: "int" }, { key: "voluntary", label: "Voluntary", type: "int" }, { key: "turnover", label: "Turnover %" }, { key: "unplanned_days", label: "Unplanned absence days", type: "int" },
        { key: "absenteeism", label: "Absenteeism %" }, { key: "overtime_h", label: "Overtime h" }, { key: "overtime_ratio", label: "Overtime %" }, { key: "punctuality", label: "Punctuality %" },
        { key: "production_cost", label: "Production labour cost", type: "amt" }, { key: "units", label: "Good units" }, { key: "cost_per_unit", label: "Labour cost / unit" }] }),
      alv({ rows: d.by_org, title: "By department", columns: [{ key: "org", label: "Department" }, { key: "n", label: "Employees", type: "int" }, { key: "women", label: "Women", type: "int" }] }),
      note("Turnover = leavers / average headcount; absenteeism = unplanned absence days (sick, unexcused, unpaid, absent in the time evaluation) / (working days x average headcount); labour cost per unit = payroll cost of the production cost centers / good units confirmed."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });
})();
