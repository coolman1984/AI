/* NERP - External audit (ZAUD_*): engagement and materiality, the PBC list the audit firm requests
   (Egyptian Accounting Standards), queries and answers, audit analytics, lead schedules, proposed
   adjustments with the summary of uncorrected misstatements, and the audit pack in Excel. */
"use strict";
(() => {
const { h, api, msg, run, ask, confirmBox, field, inp, sel, val, alv, register, go, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const egp = v => v === null || v === undefined ? "-" : Number(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const year = p => inp({ value: p.gjahr || today().slice(0, 4), w: "s" });
const PST = { REQ: ["Requested", "Q"], PREP: ["In preparation", "Q"], SUB: ["Submitted", ""], RET: ["Returned", "B"], OK: ["Accepted", "U"] };
const b64save = (name, b64) => { const bin = atob(b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const a = h("a", { href: URL.createObjectURL(new Blob([u8], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })), download: name });
  document.body.append(a); a.click(); a.remove(); };

// ------------------------------------------------------------------ 1-1 ZAUD_COCKPIT
register("ZAUD_COCKPIT", { title: "External Audit Cockpit", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/cockpit?gjahr=${val(y)}`)); if (!d) return;
    const e = d.engagement, a = d.adjustments, s = d.pbc_by_status;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Audit firm", e.firm || "not set", e.partner ? "Partner " + e.partner : "ZAUD_ENG"),
      kpi("Overall materiality", egp(e.overall), `${e.base_text}: ${egp(e.base)}`), kpi("Performance materiality", egp(e.performance), `trivial ${egp(e.trivial)}`),
      kpi("PBC accepted", `${d.pbc_done_pct} %`, `${s.OK || 0} of ${d.pbc_total} · ${s.RET || 0} returned`, s.RET ? "neg" : ""),
      kpi("Open queries", String((d.queries.OPEN || 0)), `${d.queries.ANSWERED || 0} answered`, d.queries.OPEN ? "neg" : "pos"),
      kpi("Uncorrected misstatements", egp(a.uncorrected_gross), a.uncorrected_gross >= e.overall ? "above materiality" : "", a.uncorrected_gross >= e.overall ? "neg" : "pos")),
      note(a.conclusion),
      alv({ rows: [
        { area: "Statements balanced (EAS 1)", value: d.statements_balanced ? "Yes" : "NO", go: "ZAUD_LEAD", bad: !d.statements_balanced },
        { area: "Journal entries flagged for testing (ESA 240)", value: `${d.jet_flagged} of ${d.jet_documents}`, go: "ZAUD_TESTS", bad: d.jet_flagged > 0 },
        { area: "Inventory below net realisable value (EAS 2)", value: egp(d.nrv_writedown) + " EGP write-down", go: "ZAUD_TESTS", bad: d.nrv_writedown > e.trivial },
        { area: "Expected credit loss on receivables (EAS 47)", value: egp(d.ecl) + " EGP allowance (matrix)", go: "ZAUD_TESTS", bad: d.ecl > e.trivial },
        { area: "Payroll vs ledger (EAS 38)", value: egp(d.payroll_difference) + " EGP difference", go: "ZAUD_TESTS", bad: Math.abs(d.payroll_difference) > e.trivial }],
        title: "What the auditor will look at first", columns: [{ key: "area", label: "Area" }, { key: "value", label: "Result" },
          { key: "bad", label: "", render: r => badge(r.bad ? "Review" : "OK", r.bad ? "B" : "U") }, { key: "go", label: "", render: r => btn("Open", () => go(r.go, { gjahr: val(y) })) }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Audit pack (Excel)", onClick: () => go("ZAUD_PACK", { gjahr: val(y) }) }]);
  load();
} });

// ------------------------------------------------------------------ 1-2 ZAUD_ENG
register("ZAUD_ENG", { title: "Engagement, Materiality and Auditor Access", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const e = await run(() => api(`/api/audit/eng?gjahr=${val(y)}`)); if (!e) return;
    out.innerHTML = "";
    const f = { firm: inp({ value: e.firm, w: "l" }), partner: inp({ value: e.partner, w: "m" }), manager: inp({ value: e.manager, w: "m" }),
      fieldwork: inp({ value: e.fieldwork, w: "m", ph: "e.g. 10-28 Feb" }), report: inp({ type: "date", value: e.report_date }),
      basis: sel(Object.entries(e.bases), e.basis), pct: inp({ value: e.pct / 100, w: "s" }), pm: inp({ value: e.pm_pct / 100, w: "s" }), tr: inp({ value: e.trivial_pct / 100, w: "s" }),
      notes: inp({ value: e.notes, w: "l" }) };
    const acc = { b: inp({ w: "m", ph: "AUD_FIRM1", upper: true }), n: inp({ w: "l" }), mail: inp({ w: "m" }), until: inp({ type: "date" }) };
    out.append(panel("Engagement", grid(field("Audit firm", f.firm), field("Partner", f.partner), field("Manager", f.manager), field("Fieldwork", f.fieldwork),
      field("Report date", f.report), field("Notes", f.notes))),
      panel("Materiality (ESA 320)", grid(field("Base", f.basis), field("% of the base", f.pct), field("Performance (% of overall)", f.pm), field("Trivial (% of overall)", f.tr)),
        h("div.kpis", null, kpi("Base", egp(e.base), e.base_text), kpi("Overall", egp(e.overall)), kpi("Performance", egp(e.performance)), kpi("Clearly trivial", egp(e.trivial))),
        note("Common practice: 5 % of profit before tax, 0.5-1 % of revenue or 1-2 % of total assets; performance materiality 50-75 %. Agree the figures with the audit firm.")),
      panel("Access for the audit firm", grid(field("User", acc.b), field("Name", acc.n), field("E-mail", acc.mail), field("Access until", acc.until)),
        btn("Create auditor user", async () => { const r = await run(() => api("/api/audit/access", { bname: val(acc.b), name: val(acc.n), email: val(acc.mail), valid_to: acc.until.value, firm: val(f.firm) }));
          if (r) msg("S", r.message, null, null, true); }),
        note("The auditor user may display all books (no salaries) and works only in this audit area: PBC review, queries, proposed adjustments. Access ends automatically on the date. Needs logon switched on.")));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/audit/eng", { gjahr: val(y), firm: val(f.firm), partner: val(f.partner), manager: val(f.manager), fieldwork: val(f.fieldwork),
        report_date: f.report.value, basis: f.basis.value, pct: val(f.pct), pm_pct: val(f.pm), trivial_pct: val(f.tr), notes: val(f.notes) })); if (r) { msg("S", r.message); load(); } } },
      { label: "PBC list", onClick: () => go("ZAUD_PBC", { gjahr: val(y) }) }]);
  };
  load();
} });

// ------------------------------------------------------------------ 2-1 ZAUD_PBC
register("ZAUD_PBC", { title: "PBC List - What the Auditor Requests", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/pbc?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    if (!d.rows.length) { out.append(note("No engagement yet - create it in ZAUD_ENG; the standard PBC list of an Egyptian year-end audit is created with it.")); return; }
    const set = async (r, status) => { let comment = r.comment;
      if (status === "RET") { const x = await ask(`Return ${r.code}`, [{ name: "c", label: "What is missing", value: "" }]); if (!x) return; comment = x.c; }
      const res = await run(() => api("/api/audit/pbc", { gjahr: val(y), code: r.code, status, comment })); if (res) { msg("S", res.message); load(); } };
    out.append(alv({ rows: d.rows, title: "Requests of the audit firm", rowClass: r => r.status === "RET" ? ".neg" : "", columns: [
      { key: "code", label: "Code" }, { key: "area", label: "Area" }, { key: "text", label: "Request" }, { key: "text_ar", label: "الطلب" },
      { key: "eas_text", label: "EAS", render: r => h("span", { title: r.eas_titles }, r.eas_text) }, { key: "esa", label: "ESA" },
      { key: "auto", label: "NERP prepares", render: r => r.auto ? badge("✓ " + r.auto, "U") : "manual" }, { key: "owner", label: "Owner" }, { key: "due", label: "Due", type: "date" },
      { key: "status", label: "Status", render: r => badge(...(PST[r.status] || [r.status, ""])) }, { key: "queries", label: "Open queries", type: "int" }, { key: "comment", label: "Comment" },
      { key: "x", label: "", render: r => h("span", null, ...(r.status === "OK" ? [] : [btn("Submitted", () => set(r, "SUB"))]),
        ...(d.auditor && r.status !== "OK" ? [" ", btn("Accept", () => set(r, "OK")), " ", btn("Return", () => set(r, "RET"))] : [])) }] }),
      note("✓ = NERP builds it in the audit pack (ZAUD_PACK). EAS = Egyptian Accounting Standard; numbers marked (verify) are confirmed with the auditor. ESA = Egyptian Standard on Auditing."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Audit pack", onClick: () => go("ZAUD_PACK", { gjahr: val(y) }) }]);
  load();
} });

// ------------------------------------------------------------------ 2-2 ZAUD_QUERY
register("ZAUD_QUERY", { title: "Auditor Queries and Answers", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/queries?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Queries", rowClass: r => r.status === "OPEN" ? ".neg" : "", columns: [{ key: "id", label: "No.", type: "int" }, { key: "pbc", label: "PBC" },
      { key: "raised_on", label: "Raised", type: "date" }, { key: "raised_by", label: "By" }, { key: "question", label: "Question" }, { key: "answer", label: "Answer" },
      { key: "answered_by", label: "Answered by" }, { key: "status", label: "Status", render: r => badge(r.status, r.status === "CLOSED" ? "U" : r.status === "OPEN" ? "B" : "Q") },
      { key: "x", label: "", render: r => r.status === "CLOSED" ? "" : h("span", null, btn("Answer", async () => {
        const x = await ask(`Query ${r.id}`, [{ name: "a", label: "Answer", value: r.answer || "" }]); if (!x) return;
        const res = await run(() => api("/api/audit/answer", { id: r.id, answer: x.a })); if (res) { msg("S", res.message); load(); } }),
        ...(d.auditor && r.status === "ANSWERED" ? [" ", btn("Close", async () => { const res = await run(() => api("/api/audit/answer", { id: r.id, close: true })); if (res) { msg("S", res.message); load(); } })] : [])) }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "New query", onClick: async () => {
    const x = await ask("New query to the company", [{ name: "pbc", label: "PBC code (optional)", value: "" }, { name: "question", label: "Question", value: "" }]); if (!x) return;
    const r = await run(() => api("/api/audit/query", Object.assign({ gjahr: val(y) }, x))); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 3-1 ZAUD_TESTS
const TESTS = [["jet", "Journal entry testing (ESA 240)"], ["ar", "Receivables + confirmations"], ["ecl", "Expected credit loss (EAS 47)"], ["ap", "Payables + confirmations"],
  ["bank", "Bank balances"], ["unrec", "Unrecorded liabilities"], ["inv", "Inventory, NRV, slow-moving (EAS 2)"], ["fa", "Fixed assets roll-forward (EAS 10)"],
  ["cutoff", "Revenue cut-off (EAS 48)"], ["payroll", "Payroll vs ledger (EAS 38)"], ["subsequent", "Subsequent events (EAS 7)"]];
const COLS = {
  jet: [["belnr", "Document"], ["budat", "Date", "date"], ["blart", "Type"], ["tcode", "Transaction"], ["usnam", "User"], ["text", "Text"], ["amount", "Amount", "amt"], ["score", "Score", "int"], ["flags", "Why"]],
  ar: [["partner", "Customer"], ["name", "Name"], ["total", "Balance", "amt"], ["not_due", "Not due", "amt"], ["d30", "1-30", "amt"], ["d60", "31-60", "amt"], ["d90", "61-90", "amt"], ["d90p", "> 90", "amt"], ["sample", "Confirm"], ["why", "Selection"]],
  ecl: [["bucket", "Age"], ["balance", "Balance", "amt"], ["rate", "Loss rate %"], ["allowance", "Allowance", "amt"]],
  bank: [["bank", "Bank"], ["account", "Account"], ["text", "Description"], ["gl", "G/L"], ["currency", "Currency"], ["balance", "Book balance", "amt"]],
  unrec: [["belnr", "Document"], ["budat", "Date", "date"], ["vendor", "Vendor"], ["amount", "Amount", "amt"], ["text", "Text"]],
  inv: [["werks", "Plant"], ["matnr", "Material"], ["text", "Description"], ["qty", "Qty", "qty"], ["value", "Value", "amt"], ["unit_cost", "Unit cost", "amt"], ["last_price", "Last price", "amt"], ["nrv_writedown", "NRV write-down", "amt"], ["idle_days", "Idle days", "int"], ["flags", "Flags"]],
  fa: [["anln1", "Asset"], ["text", "Description"], ["cost_open", "Cost open", "amt"], ["additions", "Additions", "amt"], ["disposals", "Disposals", "amt"], ["cost_close", "Cost close", "amt"], ["dep_charge", "Depreciation", "amt"], ["dep_close", "Acc. dep.", "amt"], ["nbv", "NBV", "amt"]],
  cutoff: [["vbeln", "Invoice"], ["invoice_date", "Invoice date", "date"], ["goods_issue", "Goods issue", "date"], ["customer", "Customer"], ["net", "Net", "amt"], ["issue", "Issue"]],
  payroll: [["month", "Month"], ["employees", "Employees", "int"], ["payroll_cost", "Payroll cost", "amt"], ["ledger", "Ledger", "amt"], ["difference", "Difference", "amt"], ["note", "Remark"]],
  subsequent: [["belnr", "Document"], ["budat", "Date", "date"], ["blart", "Type"], ["text", "Text"], ["amount", "Amount", "amt"], ["why", "Why"]] };
register("ZAUD_TESTS", { title: "Audit Analytics (year-end tests)", async render(app, params) {
  const y = year(params), t = sel(TESTS, params.test || "jet"), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y), field("Test", t))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/test/${t.value}?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    const rows = (d.rows || d.payments || d.lines || []).map(r => Object.assign({}, r, { flags: Array.isArray(r.flags) ? r.flags.join("; ") : r.flags,
      sample: r.sample === undefined ? undefined : (r.sample ? "YES" : ""), issue: r.issue === undefined ? undefined : (r.issue ? "YES" : "") }));
    const info = { jet: `${d.flagged} of ${d.documents} documents flagged - test the high scores first`, ar: `confirmation sample ${d.sampled} customers, coverage ${d.coverage_pct} %`,
      ap: `confirmation sample ${d.sampled} vendors, coverage ${d.coverage_pct} %`, ecl: `allowance ${egp(d.allowance)} EGP (simplified matrix - calibrate the rates on the loss history)`,
      unrec: `GR/IR balance ${egp(d.grir_balance)} EGP - ${d.note}`, inv: `stock ${egp(d.total)} EGP, NRV write-down ${egp(d.nrv_writedown)}, slow-moving ${egp(d.slow_value)}`,
      fa: d.total ? `net book value ${egp(d.total.nbv)} EGP` : "", cutoff: `${d.issues} cut-off issue(s) in ${(d.window || []).join(" - ")}`,
      payroll: `total difference ${egp(d.difference)} EGP`, subsequent: `${(d.from || "")} - ${(d.to || "")}` }[t.value] || "";
    out.append(note(info), alv({ rows, title: (TESTS.find(x => x[0] === t.value) || [])[1], columns: COLS[t.value].map(([key, label, type]) => ({ key, label, type })) }));
  };
  t.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Propose adjustment", onClick: () => go("ZAUD_AJE", { gjahr: val(y) }) }]);
  load();
} });

// ------------------------------------------------------------------ 3-2 ZAUD_LEAD
register("ZAUD_LEAD", { title: "Draft Statements and Lead Schedules (EAS 1)", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/test/lead?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    const s = d.statements;
    out.append(h("div.kpis", null, kpi("Total assets", egp(s.assets)), kpi("Liabilities + equity", egp(s.liabilities)), kpi("Result of the year", egp(s.result), "", s.result < 0 ? "neg" : "pos"),
      kpi("Balanced", s.balanced ? "Yes" : "NO", "", s.balanced ? "pos" : "neg")),
      alv({ rows: s.rows.map(r => Object.assign({}, r, { text: "  ".repeat(r.level) + r.text })), title: "Statement of financial position and income statement",
        columns: [{ key: "node", label: "Line" }, { key: "text", label: "Description" }, { key: "cur", label: "This year", type: "amt" }, { key: "cmp", label: "Comparison", type: "amt" },
          { key: "diff", label: "Change", type: "amt" }, { key: "pct", label: "%" }] }),
      note("Cash flow statement (EAS 4), statement of changes in equity and the notes are completed by the accountant from these figures."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 4-1 ZAUD_AJE
register("ZAUD_AJE", { title: "Audit Adjustments and Uncorrected Misstatements (ESA 450)", async render(app, params) {
  const y = year(params), out = h("div");
  app.append(panel(null, grid(field("Fiscal year", y))), out);
  const load = async () => {
    const d = await run(() => api(`/api/audit/aje?gjahr=${val(y)}`)); if (!d) return;
    out.innerHTML = "";
    const lines = [0, 1, 2, 3].map(() => ({ a: inp({ w: "s", ph: "account" }), k: inp({ w: "s", ph: "cost ctr", upper: true }), d: inp({ w: "s", ph: "debit" }), c: inp({ w: "s", ph: "credit" }) }));
    const text = inp({ w: "l" }), eas = inp({ w: "s", ph: "e.g. 47" });
    out.append(h("div.kpis", null, kpi("Uncorrected (gross)", egp(d.uncorrected_gross), "effect on profit", d.uncorrected_gross >= d.overall ? "neg" : ""), kpi("Overall materiality", egp(d.overall)),
      kpi("Performance materiality", egp(d.performance)), kpi("Corrected (posted)", egp(d.corrected))), note(d.conclusion),
      alv({ rows: d.rows.map(r => Object.assign({}, r, { acc: r.lines.map(l => `${l.hkont} ${l.amount > 0 ? "Dr" : "Cr"} ${egp(Math.abs(l.amount) / 100)}`).join(" | ") })), title: "Proposed adjustments",
        columns: [{ key: "id", label: "No.", type: "int" }, { key: "text", label: "Misstatement" }, { key: "eas", label: "EAS" }, { key: "acc", label: "Entry" },
          { key: "pl_effect", label: "Effect on profit", type: "amt" }, { key: "status", label: "Status", render: r => badge(r.status, r.status === "POSTED" ? "U" : r.status === "REJECTED" ? "B" : "Q") },
          { key: "belnr", label: "Document / reason", render: r => r.belnr || r.reason || "" },
          { key: "x", label: "", render: r => r.status !== "PROPOSED" ? "" : h("span", null, btn("Post (accept)", async () => {
            const x = await ask(`Post adjustment ${r.id}`, [{ name: "budat", label: "Posting date", value: `${val(y)}-12-31` }]); if (!x) return;
            const res = await run(() => api("/api/audit/aje/post", { id: r.id, budat: x.budat })); if (res) { msg("S", res.message); load(); } }), " ",
            btn("Not correct", async () => { const x = await ask(`Adjustment ${r.id} not corrected`, [{ name: "reason", label: "Management's reason", value: "" }]); if (!x) return;
              const res = await run(() => api("/api/audit/aje/reject", { id: r.id, reason: x.reason })); if (res) { msg("S", res.message); load(); } })) }] }),
      panel("Propose an adjustment (auditor)", grid(field("Misstatement", text), field("EAS", eas)),
        h("table.grid", null, h("thead", null, h("tr", null, ...["G/L account", "Cost center (P&L)", "Debit", "Credit"].map(x => h("th", null, x)))),
          h("tbody", null, ...lines.map(l => h("tr", null, h("td", null, l.a), h("td", null, l.k), h("td", null, l.d), h("td", null, l.c))))),
        btn("Propose", async () => { const r = await run(() => api("/api/audit/aje", { gjahr: val(y), text: val(text), eas: val(eas),
          lines: lines.map(l => ({ hkont: val(l.a), kostl: val(l.k), debit: val(l.d), credit: val(l.c) })).filter(l => l.hkont) })); if (r) { msg("S", r.message); load(); } }),
        note("Posting needs an accountant with FI authorization (the auditor can only propose). Not corrected items stay in the summary that is compared with materiality.")));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 4-2 ZAUD_PACK
register("ZAUD_PACK", { title: "Audit Pack (Excel)", async render(app, params) {
  const y = year(params);
  app.append(panel(null, grid(field("Fiscal year", y))),
    note("One Excel file for the audit firm: PBC index, materiality, trial balance, draft statements, lead schedules, journal, journal entry testing, bank, receivables and payables with confirmation samples and expected credit loss, unrecorded liabilities, inventory with NRV and slow-moving, fixed asset roll-forward, revenue cut-off, payroll reconciliation, tax, related parties, subsequent events, adjustments, confirmation letters (Arabic) and the list of Egyptian Accounting Standards."));
  toolbar([{ label: "Create audit pack", key: "F8", primary: true, onClick: async () => {
    const r = await run(() => api(`/api/audit/pack?gjahr=${val(y)}`)); if (r) { b64save(r.name, r.xlsx); msg("S", `${r.name} created`); } } }]);
} });

// ------------------------------------------------------------------ 4-3 ZAUD_EAS
register("ZAUD_EAS", { title: "Egyptian Accounting and Auditing Standards (reference)", async render(app) {
  const d = await run(() => api("/api/audit/standards")); if (!d) return;
  app.append(alv({ rows: d.eas, title: "Egyptian Accounting Standards used in the audit area", columns: [{ key: "no", label: "EAS" }, { key: "title", label: "Title" },
    { key: "title_ar", label: "العنوان" }, { key: "verified", label: "Number", render: r => badge(r.verified ? "Confirmed" : "Verify", r.verified ? "U" : "Q") }] }),
    alv({ rows: d.esa, title: "Egyptian Standards on Auditing (same numbering as ISA)", columns: [{ key: "no", label: "ESA" }, { key: "title", label: "Subject" }] }),
    note("'Verify' = the commonly used number was not confirmed in an official source here - confirm with the audit firm or the FRA text."));
} });
})();
