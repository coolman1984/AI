/* MM Core - Financial Accounting (FI) screens */
"use strict";
(() => {
const { h, $, $$, api, msg, run, confirmBox, field, inp, sel, val, up, alv, register, go,
  toolbar, fmtQty, fmtAmt, fmtDate, fmtShort, today, enc, S } = App;

// ------------------------------------------------------------------ helpers
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const out = () => h("div");
const gap = () => h("div", { style: { height: "12px" } });
let FI = null;
async function meta(force) {
  if (!FI || force) {
    FI = await api("/api/fi/meta");
    App.datalist("dl-hkont", FI.gl.map(a => [a.hkont, `${a.hkont} ${a.txt}`]));
    App.datalist("dl-lifnr", FI.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name} (${v.waers || "EGP"})`]));
    App.datalist("dl-kunnr", FI.customers.map(c => [c.kunnr, `${c.kunnr} ${c.name}`]));
    App.datalist("dl-anln1", FI.assets.map(a => [a.anln1, `${a.anln1} ${a.txt}${a.deakt ? " (retired)" : ""}`]));
    if (!document.getElementById("dl-kostl") || !document.getElementById("dl-kostl").options.length) {
      const co = await api("/api/co/meta");
      App.datalist("dl-kostl", co.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
      App.datalist("dl-aufnr", co.orders.map(o => [o.aufnr, `${o.aufnr} ${o.ktext}`]));
    }
  }
  return FI;
}
const glText = k => (FI.gl.find(a => a.hkont === k) || {}).txt || "";
const vName = k => (FI.vendors.find(v => v.lifnr === k) || {}).name || "";
const cName = k => (FI.customers.find(v => v.kunnr === k) || {}).name || "";
const eop = (y, p) => new Date(Date.UTC(y, p, 0)).toISOString().slice(0, 10);
const sampleEnd = () => eop(FI.sample.gjahr, FI.sample.perio);
const sampleStart = () => `${FI.sample.gjahr}-${String(FI.sample.perio).padStart(2, "0")}-01`;
const mon = (y, p) => `${String(p).padStart(2, "0")}/${y}`;
const termsSel = (v, w) => sel(FI.terms.map(t => [t.zterm, `${t.zterm} ${t.text}`]), v || "NT30", { w: w || "l" });
const taxSel = (typ, v) => sel([["", "(no tax)"], ...FI.tax.filter(t => t.typ === typ).map(t => [t.mwskz, `${t.mwskz} ${t.text}`])], v, { w: "l" });
function msgLink(type, text, label, tcode, params) {
  msg(type, text);
  const a = h("a", { href: "#", style: { marginLeft: "10px" } }, label);
  a.addEventListener("click", e => { e.preventDefault(); go(tcode, params); });
  $("#status-msg").append(a);
}
function execBar(fn, extra) { toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }, ...(extra || [])]); }
const docLink = r => go("FB03", { id: r.belnr, year: r.gjahr });
const sdot = open => h("span", { title: open ? "Open item" : "Cleared item",
  style: { display: "inline-block", width: "10px", height: "10px", borderRadius: "50%", background: open ? "#bb0000" : "#107e3e" } });
function kpi(l, v, s, goTo, cls) {
  return h("div.kpi", { dataset: goTo ? { go: goTo } : null, on: goTo ? { click: () => go(goTo) } : null },
    h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
}
const card = (t, sub, ...b) => h("div.card", null, h("h3", null, t), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...b));
function bars(items, labelFn, valFn, fmt) {
  const max = Math.max(...items.map(i => Math.abs(valFn(i))), 1);
  return h("div", null, items.map(i => h("div.hbar", null, h("span.lbl", null, labelFn(i)),
    h("span.track", null, h("span.fill", { style: { width: Math.abs(valFn(i)) / max * 100 + "%", display: "block",
      background: valFn(i) < 0 ? "#bb0000" : "" } })), h("span.num", null, (fmt || fmtShort)(valFn(i))))));
}

// ================================================================== cockpit
register("ZFI_COCKPIT", { title: "Finance Cockpit - Balance Sheet, Cash & Working Capital", async render(app, params) {
  await meta();
  const y = inp({ value: params.gjahr || FI.sample.gjahr, w: "s" }), p = inp({ value: params.perio || FI.sample.perio, w: "s" });
  const body = out();
  app.append(panel("Period", grid(field("Fiscal year", y), field("Period", p))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/fi/cockpit?gjahr=${val(y)}&perio=${val(p)}`));
    if (!d) return;
    body.innerHTML = "";
    const k = d.kpi, cur = d.currency;
    body.append(h("div.kpis", null,
      kpi("Cash & bank", h("span", null, fmtShort(k.cash), " ", h("small", null, cur)), "Bank NBE + petty cash", "FF7A"),
      kpi("Receivables", fmtShort(k.ar), `overdue ${fmtShort(k.overdue)}`, "FBL5N", k.overdue > 0 ? "crit" : ""),
      kpi("Payables", fmtShort(k.ap), "open vendor items", "FBL1N"),
      kpi("Inventory", fmtShort(k.inventory), "MM stock value", "MB52"),
      kpi("DSO", k.dso === null ? "-" : `${k.dso} d`, "days sales outstanding", "S_ALR_87012168"),
      kpi("DPO", k.dpo === null ? "-" : `${k.dpo} d`, "days payables outstanding", "S_ALR_87012078"),
      kpi("Working capital", fmtShort(k.working_capital), `current ratio ${k.current_ratio ?? "-"}`, "F.01"),
      kpi("Equity ratio", k.equity_ratio === null ? "-" : k.equity_ratio + " %", "equity / total assets", "F.01"),
      kpi("Result of the period", fmtShort(k.result), `operating ${fmtShort(k.operating)} · EBITDA ${fmtShort(k.ebitda)}`, "F.01", k.result < 0 ? "neg" : "pos"),
      kpi("Balance sheet", k.balanced ? "✔ Balanced" : "✖ Error", `total ${fmtShort(k.assets_total)}`, "F.01", k.balanced ? "pos" : "neg")));
    const st = d.statements.rows, node = Object.fromEntries(st.map(r => [r.node, r]));
    const W = 560, cf = d.cash.weeks, maxv = Math.max(...cf.map(c => Math.max(c.inflow, -c.outflow, c.balance)), 1);
    let svg = "";
    cf.forEach((c, i) => {
      const x = 40 + i * 64, s = 150 / maxv;
      svg += `<rect x="${x}" y="${170 - c.inflow * s}" width="22" height="${c.inflow * s}" fill="#107e3e"><title>In ${fmtAmt(c.inflow)}</title></rect>` +
        `<rect x="${x + 24}" y="${170 + c.outflow * s}" width="22" height="${-c.outflow * s}" fill="#e9730c"><title>Out ${fmtAmt(c.outflow)}</title></rect>` +
        `<text x="${x + 22}" y="198" font-size="10" text-anchor="middle" fill="#6a6d70">W${c.week}</text>`;
    });
    const pts = cf.map((c, i) => `${40 + i * 64 + 23},${170 - c.balance * 150 / maxv}`).join(" ");
    svg += `<polyline points="${pts}" fill="none" stroke="#0a6ed1" stroke-width="2"/>`;
    const chart = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chart.setAttribute("viewBox", `0 0 ${W} 205`); chart.style.width = "100%"; chart.innerHTML = svg;
    body.append(h("div.cards", null,
      card("Balance sheet " + mon(d.gjahr, d.perio), "Financial statement version FSEG", bars(
        st.filter(r => r.level === 1), r => r.text, r => r.cur)),
      card("Cash forecast - next 8 weeks (FF7A)", `Bank today ${fmtAmt(d.cash.bank)} · overdue receivables ${fmtAmt(d.cash.overdue_in)}`,
        h("div.legend", null, h("span", null, h("i", { style: { background: "#107e3e" } }), "Customer receipts"),
          h("span", null, h("i", { style: { background: "#e9730c" } }), "Vendor payments"),
          h("span", null, h("i", { style: { background: "#0a6ed1" } }), "Projected balance")), chart),
      card("Profit & loss " + mon(d.gjahr, d.perio), null, bars(st.filter(r => r.level === 1 && r.node.startsWith("R")),
        r => r.text, r => r.cur)),
      card("Receivables aging", "Due date analysis at period end", alv({ compact: true, rows: d.aging.rows, columns: [
        { key: "partner", label: "Customer", link: r => go("FBL5N", { key: r.partner }) }, { key: "name", label: "Name" },
        { key: "not_due", label: "Not due", type: "amt", sum: true }, { key: "d30", label: "1-30", type: "amt", sum: true },
        { key: "d60", label: "31-60", type: "amt", sum: true }, { key: "d90p", label: "> 90", type: "amt", sum: true },
        { key: "total", label: "Total", type: "amt", sum: true }] })),
      card("VAT of the period", "Output - input = payable (FB41)", h("table.grid.pnl", null, h("tbody", null,
        h("tr", null, h("td", null, "Output VAT"), h("td.num", null, fmtAmt(d.vat.output))),
        h("tr", null, h("td", null, "Input VAT"), h("td.num", null, fmtAmt(d.vat.input))),
        h("tr.sub", null, h("td", null, "VAT payable"), h("td.num", null, fmtAmt(d.vat.payable))))))));
    msg("S", `Finance cockpit ${mon(d.gjahr, d.perio)} - result ${fmtAmt(k.result)} ${cur}`);
  };
  execBar(exec, [{ label: "Closing cockpit", ghost: true, onClick: () => go("ZFI_PROCESS") }]);
  exec();
}});

// ================================================================== closing cockpit
register("ZFI_PROCESS", { title: "FI Process Map & Closing Cockpit", async render(app, params) {
  await meta();
  const y = inp({ value: params.gjahr || FI.sample.gjahr, w: "s" }), p = inp({ value: params.perio || FI.sample.perio, w: "s" });
  const body = out();
  app.append(h("div.note", { style: { marginBottom: "10px" } },
    `Company code ${FI.bukrs} ${FI.butxt} · chart of accounts ${FI.ktopl} · sample month ${mon(FI.sample.gjahr, FI.sample.perio)} closed A → Z together with MM and CO.`),
    panel("Period", grid(field("Fiscal year", y), field("Period", p))), body);
  const exec = async () => {
    const s = await run(() => api(`/api/fi/closing?gjahr=${val(y)}&perio=${val(p)}`));
    if (!s) return;
    body.innerHTML = "";
    const st = (n, txt) => n ? badge(`✔ ${txt || n}`, "U") : badge("Open", "Q");
    const phases = [
      ["1. Settings & master data", [["OX02", "Company code 1000, chart INT, fiscal year K4", "OX02", 1],
        ["FS00", "G/L accounts with FS version, reconciliation & open item", "FS00", 1],
        ["OBA7/FBN1", "Document types and number ranges", "OBA7", 1], ["OBB8/FTXP", "Payment terms, tax codes (14 % VAT)", "OBB8", 1],
        ["XK01/XD01", "Vendors & customers (terms, credit limit)", "XK03", 1], ["AS01", "Assets with cost center and useful life", "AR01", 1],
        ["OB08", "Exchange rates USD / EUR", "OB08", 1]]],
      ["2. Daily postings", [["MIRO", "Invoice verification against PO / GR", "MIRO", s.miro, `${s.miro} invoices`],
        ["FB60", "Vendor invoices with cost centers", "FB60", s.fb60, `${s.fb60} docs`],
        ["VF01", "Billing: customer open items + VAT", "VF03", s.billing, `${s.billing} docs`],
        ["F-90", "Asset purchases (USD)", "AR01", s.assets, `${s.assets} docs`],
        ["F-28/F-53", "Incoming / outgoing payments", "FBL5N", s.payments, `${s.payments} docs`],
        ["FF67", "Bank statement", "FF67", s.ff67, `${s.ff67} docs`]]],
      ["3. Periodic processing", [["F110", "Payment run with cash discount", "F110", s.f110, `${s.f110} payments`],
        ["AFAB", "Depreciation run → cost centers", "AFAB", s.afab], ["FBS1", "Accruals (auto-reversed)", "FBS1", s.fbs1],
        ["F150", "Dunning run", "F150", s.f150]]],
      ["4. Closing", [["FAGL_FCV", "Foreign currency valuation", "FAGL_FCV", s.fcv],
        ["F.13", "GR/IR clearing", "F.13", s.f13, `${s.grir_open} PO items still open`],
        ["FB41", "VAT settlement", "FB41", s.fb41], ["CO", "CO period-end closing (see ZCO_PROCESS)", "ZCO_PROCESS", s.co_recon, "reconciled"],
        ["OB52", "Close period", "OB52", 1, s.period.y1 ? `open ${s.period.p1}/${s.period.y1} - ${s.period.p2}/${s.period.y2}` : "all open"]]],
      ["5. Reporting", [["F.01", "Balance sheet & P&L", "F.01", s.balanced, s.balanced ? "balanced" : "not balanced"],
        ["S_ALR_87012277", "Trial balance", "S_ALR_87012277", 1], ["FF7A", "Cash position & forecast", "FF7A", 1],
        ["S_ALR_87012168", "Customer aging", "S_ALR_87012168", 1], ["S_ALR_87012357", "VAT return", "S_ALR_87012357", 1]]],
    ];
    for (const [t, steps] of phases)
      body.append(h("div.panel", null, h("div.panel-head", null, t), h("div.process", null, steps.map(([c, txt, tc, ok, lbl]) =>
        h("div.step", { on: { click: () => go(tc) } }, h("div.step-code", null, c), h("div.step-text", null, txt), st(ok, lbl))))));
    body.append(panel("Result", h("div", { class: s.balanced ? "pos" : "neg", style: { fontSize: "15px" } },
      `Result of the period ${fmtAmt(s.result)} ${S.meta.currency} · balance sheet ${s.balanced ? "balanced" : "NOT balanced"} · FI ↔ CO-PA ${s.co_recon ? "reconciled" : "difference"}`)));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: exec }]);
  exec();
}});

// ================================================================== config displays
const simpleList = (code, title, rowsFn, cols, note) => register(code, { title, async render(app) {
  await meta();
  app.append(alv({ title, rows: rowsFn(), columns: cols }), note ? h("div.note", { style: { marginTop: "10px" } }, note) : null);
}});
register("OX02", { title: "Company Code", async render(app) {
  await meta();
  app.append(panel("Company code " + FI.bukrs, h("div.obj-header", { style: { padding: 0 } }, [["Company code", FI.bukrs], ["Name", FI.butxt],
    ["Country", "EG Egypt"], ["Currency", S.meta.currency], ["Chart of accounts", FI.ktopl], ["Fiscal year variant", "K4 (calendar year)"],
    ["Controlling area", "1000"], ["Operating concern", "EG01"], ["VAT", "14 %"]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
}});
simpleList("OBA7", "Document Types", () => FI.doc_types, [{ key: "blart", label: "Type" }, { key: "text", label: "Description" },
  { key: "nr", label: "Number range" }, { key: "koart", label: "Account types allowed" }], "S = G/L, K = vendor, D = customer, A = asset, M = material.");
simpleList("FBN1", "Number Ranges (Accounting Documents)", () => FI.number_ranges, [{ key: "nr", label: "No." },
  { key: "start", label: "From number" }, { key: "current", label: "Current number" }]);
simpleList("OB41", "Posting Keys", () => FI.posting_keys, [{ key: "bschl", label: "PK" }, { key: "text", label: "Name" },
  { key: "koart", label: "Account type" }, { key: "shkzg", label: "Debit/credit" }]);
simpleList("OBB8", "Terms of Payment", () => FI.terms, [{ key: "zterm", label: "Terms" }, { key: "text", label: "Explanation" },
  { key: "disc_days", label: "Discount days", type: "int" }, { key: "disc_pct", label: "Discount %", type: "amt" }, { key: "net_days", label: "Net days", type: "int" }]);
simpleList("FTXP", "Tax Codes", () => FI.tax, [{ key: "mwskz", label: "Code" }, { key: "text", label: "Description" },
  { key: "typ", label: "Type", render: r => h("span", null, r.typ === "I" ? "Input tax" : "Output tax") }, { key: "pct", label: "Rate %", type: "amt" }, { key: "hkont", label: "G/L account" }]);
simpleList("FI12", "House Banks", () => FI.banks, [{ key: "hbkid", label: "House bank" }, { key: "hktid", label: "Account ID" },
  { key: "text", label: "Description" }, { key: "hkont", label: "G/L account", link: r => go("FS10N", { hkont: r.hkont }) }, { key: "waers", label: "Crcy" },
  { key: "balance", label: "G/L balance", type: "amt" }]);
simpleList("OAOA", "Asset Classes & Depreciation", () => FI.asset_classes.map(c => ({ ...c, key: FI.dep_keys[c.afasl] })), [
  { key: "anlkl", label: "Class" }, { key: "text", label: "Description" }, { key: "apc", label: "APC account" }, { key: "accdep", label: "Acc. dep. account" },
  { key: "afasl", label: "Dep. key" }, { key: "key", label: "Method" }, { key: "ndjar", label: "Useful life (years)", type: "int" }, { key: "numbers", label: "Numbers from" }]);

register("OB52", { title: "Open and Close Posting Periods", async render(app) {
  await meta(true);
  const pr = FI.period;
  const f = { y1: inp({ value: pr.y1, w: "s" }), p1: inp({ value: pr.p1, w: "s" }), y2: inp({ value: pr.y2, w: "s" }), p2: inp({ value: pr.p2, w: "s" }) };
  app.append(panel("Variant 1000 · account type + (all)", grid(field("From period", h("span.split", null, f.p1, "/", f.y1)),
    field("To period", h("span.split", null, f.p2, "/", f.y2))), h("div.note", null,
    "Postings outside this interval are rejected with message F5 201 - in every module (MM, CO, FI).")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/ob52", { y1: val(f.y1), p1: val(f.p1), y2: val(f.y2), p2: val(f.p2) })); if (r) msg("S", r.message); } }]);
}});

register("OB08", { title: "Exchange Rates (type M)", async render(app) {
  await meta(true);
  const w = sel(Object.keys(FI.currencies).filter(c => c !== "EGP"), "USD", { w: "s" }), d = inp({ type: "date", value: today(), w: "m" }), r = inp({ w: "s" });
  app.append(panel("New rate", grid(field("From currency", w), field("Valid from", d), field("Rate (EGP per unit)", r))), alv({ title: "Exchange rates", rows: FI.rates, columns: [
    { key: "waers", label: "From" }, { key: "gdatu", label: "Valid from", type: "date" }, { key: "ukurs", label: "Rate", type: "amt" }] }));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const x = await run(() => api("/api/fi/ob08", { waers: w.value, gdatu: d.value, ukurs: val(r) })); if (x) { msg("S", x.message); go("OB08"); } } }]);
}});

// ================================================================== G/L
register("FS00", { title: "G/L Account Centrally", async render(app, params) {
  await meta(true);
  const k = inp({ value: params.id || "", list: "dl-hkont", w: "m" }), t = inp({ w: "l" }), typ = sel([["PL", "P&L statement account"], ["BS", "Balance sheet account"]], "PL", { w: "l" });
  const fsv = sel(FI.fsv.filter(n => n.parent).map(n => [n.node, `${n.node} ${n.text}`]), "R60", { w: "l" });
  const oi = h("input", { type: "checkbox" }), blk = h("input", { type: "checkbox" }), tax = sel([["", "none"], ["<", "< input tax"], [">", "> output tax"], ["*", "* all"]], "", { w: "m" });
  const fill = () => { const a = FI.gl.find(x => x.hkont === val(k)); if (!a) return; t.value = a.txt; typ.value = a.typ; fsv.value = a.fsv; oi.checked = !!a.oi; blk.checked = !!a.blocked; tax.value = a.tax || ""; };
  k.addEventListener("change", fill);
  app.append(panel("G/L account in chart of accounts INT / company code 1000", grid(field("G/L account", k, { req: true }), field("Short text", t, { req: true }),
    field("Account type", typ), field("FS version item", fsv), field("Tax category", tax),
    field("Open item management", h("label.checkbox", null, oi, "line items can be cleared")), field("Blocked for posting", h("label.checkbox", null, blk, "blocked")))),
  alv({ title: "Chart of accounts INT", rows: FI.gl.map(a => ({ ...a, rec: { K: "Vendors", D: "Customers", A: "Assets" }[a.recon] || "" })), onRow: r => { k.value = r.hkont; fill(); }, columns: [
    { key: "hkont", label: "G/L acct", link: r => go("FS10N", { hkont: r.hkont }) }, { key: "txt", label: "Short text" }, { key: "typ", label: "BS/PL" },
    { key: "fsv", label: "FSV item" }, { key: "rec", label: "Reconciliation acct for" }, { key: "oi", label: "OI", render: r => r.oi ? badge("OI", "S") : "" },
    { key: "tax", label: "Tax" }, { key: "blocked", label: "Blocked", render: r => r.blocked ? badge("blocked", "B") : "" }] }));
  if (params.id) fill();
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/fs00", { hkont: val(k), txt: val(t), typ: typ.value, fsv: fsv.value, oi: oi.checked ? 1 : 0, tax: tax.value, blocked: blk.checked ? 1 : 0 }));
    if (r) { msg("S", r.message); await meta(true); } } }]);
}});

register("FS10N", { title: "Display G/L Account Balances", async render(app, params) {
  await meta();
  const k = inp({ value: params.hkont || "113100", list: "dl-hkont", w: "m" }), y = inp({ value: FI.sample.gjahr, w: "s" }), o = out();
  app.append(panel("Selection - company code 1000", grid(field("G/L account", k, { req: true }), field("Fiscal year", y))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/fi/fs10n?hkont=${val(k)}&gjahr=${val(y)}`));
    if (!d) return;
    o.innerHTML = "";
    o.append(alv({ title: `Balance display: ${d.hkont} ${d.txt} (${d.typ === "BS" ? "balance sheet" : "P&L"})`, rows: d.rows,
      onDbl: r => typeof r.perio === "number" && go("FBL3N", { key: d.hkont, status: "all", d1: `${val(y)}-${String(r.perio).padStart(2, "0")}-01`, d2: eop(+val(y), r.perio) }),
      columns: [{ key: "perio", label: "Period" }, { key: "debit", label: "Debit", type: "amt", sum: true }, { key: "credit", label: "Credit", type: "amt", sum: true },
        { key: "balance", label: "Balance", type: "amt", signed: true }, { key: "cumulative", label: "Cumulative balance", type: "amt", signed: true }] }),
    h("div.note", { style: { marginTop: "8px" } }, "Double-click a period to see its line items (FBL3N)."));
  };
  execBar(exec, [{ label: "Line items", ghost: true, onClick: () => go("FBL3N", { key: val(k), status: "all" }) }]);
  exec();
}});
register("FAGLB03", { title: "G/L Account Balances (New GL)", render: (a, p) => go("FS10N", p) });

function lineItems(code, koart, title) {
  register(code, { title, async render(app, params) {
    await meta();
    const lst = koart === "S" ? "dl-hkont" : koart === "K" ? "dl-lifnr" : "dl-kunnr";
    const k = inp({ value: params.key || "", list: lst, upper: true, w: "m", ph: koart === "S" ? "e.g. 191100" : "blank = all" });
    const st = sel([["open", "Open items at key date"], ["cleared", "Cleared items"], ["all", "All items"]], params.status || (koart === "S" ? "all" : "open"), { w: "l" });
    const kd = inp({ type: "date", value: params.key_date || today(), w: "m" });
    const d1 = inp({ type: "date", value: params.d1 || "", w: "m" }), d2 = inp({ type: "date", value: params.d2 || "", w: "m" });
    const o = out();
    app.append(panel("Selection", grid(field(koart === "S" ? "G/L account(s)" : koart === "K" ? "Vendor" : "Customer", k), field("Line item selection", st),
      field("Open at key date", kd), field("Posting date from", d1), field("Posting date to", d2))), o);
    const exec = async () => {
      const rows = await run(() => api(`/api/fi/fbl?koart=${koart}&key=${enc(up(k))}&status=${st.value}&key_date=${kd.value}&d1=${d1.value}&d2=${d2.value}`));
      if (!rows) return;
      o.innerHTML = "";
      const cols = [{ key: "status", label: "S", render: r => sdot(r.open), exportValue: r => r.status },
        ...(koart === "S" ? [{ key: "hkont", label: "G/L acct" }, { key: "txt", label: "Account name" }] :
          [{ key: "partner", label: koart === "K" ? "Vendor" : "Customer" }, { key: "name", label: "Name" }]),
        { key: "belnr", label: "DocumentNo", link: docLink }, { key: "blart", label: "Type" }, { key: "bschl", label: "PK" },
        { key: "budat", label: "Pstng date", type: "date" }, { key: "bldat", label: "Doc. date", type: "date" },
        { key: "xblnr", label: "Reference" }, { key: "zuonr", label: "Assignment" },
        { key: "amount", label: "Amount in LC", type: "amt", sum: true, signed: true }];
      if (koart !== "S") cols.push({ key: "waers", label: "Crcy" }, { key: "amount_fc", label: "Amount in DC", type: "amt", signed: true },
        { key: "zterm", label: "Terms" }, { key: "netdt", label: "Net due", type: "date" },
        { key: "arrears", label: "Arrears", type: "int", cls: r => r.arrears > 0 ? "neg" : "" },
        { key: "disc_date", label: "Disc. date", type: "date" }, { key: "manst", label: "Dunn.", type: "int" });
      if (koart === "S") cols.push({ key: "kostl", label: "Cost ctr" }, { key: "aufnr", label: "Order" }, { key: "mwskz", label: "Tx" }, { key: "matnr", label: "Material" });
      cols.push({ key: "augbl", label: "Clrng doc." }, { key: "augdt", label: "Clearing", type: "date" }, { key: "sgtxt", label: "Text" });
      o.append(alv({ title: `${title} - ${rows.length} items`, exportName: code, rows, columns: cols }));
      msg("S", `${rows.length} items selected`);
    };
    execBar(exec); exec();
  }});
}
lineItems("FBL3N", "S", "G/L Account Line Items");
lineItems("FBL1N", "K", "Vendor Line Items");
lineItems("FBL5N", "D", "Customer Line Items");

function itemGrid(cols, lines, onChange) {
  const box = h("div.items-wrap");
  const draw = () => {
    box.innerHTML = "";
    const tb = h("tbody");
    lines.forEach((l, i) => {
      tb.append(h("tr", null, h("td.ln", null, String(i + 1)), cols.map(c => {
        let el;
        if (c.options) el = sel(c.options, l[c.key], { onchange: e => { l[c.key] = e.target.value; onChange && onChange(); } });
        else el = inp({ value: l[c.key] || "", list: c.list, upper: c.upper, w: c.w || "m", oninput: e => { l[c.key] = e.target.value; onChange && onChange(); } });
        return h("td", null, el);
      }), h("td", null, h("button.alv-tb-btn", { type: "button", on: { click: () => { lines.splice(i, 1); draw(); onChange && onChange(); } } }, "✕"))));
    });
    box.append(h("table.grid.items", null, h("thead", null, h("tr", null, h("th", null, "#"), cols.map(c => h("th", null, c.label)), h("th"))), tb));
  };
  draw();
  box.redraw = draw;
  return box;
}

register("F-02", { title: "Enter G/L Account Posting (General Posting)", async render(app) {
  await meta();
  const f = { bldat: inp({ type: "date", value: today(), w: "m" }), budat: inp({ type: "date", value: today(), w: "m" }),
    blart: sel(FI.doc_types.filter(d => ["SA", "KR", "DR", "AB"].includes(d.blart)).map(d => [d.blart, `${d.blart} ${d.text}`]), "SA", { w: "l" }),
    xblnr: inp({ w: "m" }), bktxt: inp({ w: "l" }) };
  const pks = FI.posting_keys.filter(k => ["40", "50", "01", "11", "15", "21", "31", "25"].includes(k.bschl)).map(k => [k.bschl, `${k.bschl} ${k.text} (${k.koart}/${k.shkzg})`]);
  const lines = [{ bschl: "40", account: "", amount: "" }, { bschl: "50", account: "", amount: "" }];
  const bal = h("span.badge");
  const calc = () => { const b = lines.reduce((a, l) => a + (parseFloat(l.amount) || 0) * (((FI.posting_keys.find(k => k.bschl === l.bschl) || {}).shkzg === "S") ? 1 : -1), 0);
    bal.textContent = `Balance ${fmtAmt(b)}`; bal.className = "badge " + (Math.abs(b) < 0.005 ? "U" : "B"); };
  const g = itemGrid([{ key: "bschl", label: "PK", options: pks }, { key: "account", label: "Account (G/L, vendor, customer)", upper: true },
    { key: "amount", label: "Amount" }, { key: "kostl", label: "Cost center", list: "dl-kostl", upper: true, w: "s" },
    { key: "aufnr", label: "Order", list: "dl-aufnr" }, { key: "sgtxt", label: "Text", w: "l" }], lines, calc);
  calc();
  app.append(panel("Header", grid(field("Document date", f.bldat), field("Posting date", f.budat, { req: true }), field("Type", f.blart),
    field("Reference", f.xblnr), field("Doc. header text", f.bktxt))),
    h("div.panel", null, h("div.panel-head", null, "Items", h("span.spacer"), bal, h("button.btn.ghost", { type: "button", on: { click: () => { lines.push({ bschl: "40", account: "", amount: "" }); g.redraw(); } } }, "+ Line")), g),
    h("div.note", null, "Posting keys decide debit/credit and account type: 40/50 G/L, 31/21/25 vendor, 01/11/15 customer. SA documents allow G/L accounts only (OBA7)."));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/f02", { header: { bldat: f.bldat.value, budat: f.budat.value, blart: f.blart.value, xblnr: val(f.xblnr), bktxt: val(f.bktxt) },
      lines: lines.filter(l => l.account) }));
    if (r) msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: f.budat.value.slice(0, 4) }); } }]);
}});

register("FB08", { title: "Reverse Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" }), y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const b = inp({ type: "date", value: today(), w: "m" });
  const rs = sel([["01", "01 Reversal in current period"], ["02", "02 Reversal in closed period"], ["05", "05 Accrual reversal"]], "01", { w: "l" });
  app.append(panel("Document", grid(field("Document number", d, { req: true }), field("Fiscal year", y), field("Reversal reason", rs), field("Posting date", b))),
    h("div.note", null, "Documents from logistics are reversed in their own transaction (MBST, VF11, MR8M). Cleared items must be reset first."));
  toolbar([{ label: "Display before reversal", onClick: () => go("FB03", { id: val(d), year: val(y) }) },
    { label: "Reverse", key: "Ctrl+S", primary: true, onClick: async () => {
      if (!await confirmBox("Reverse document", `Reverse document ${val(d)} / ${val(y)}?`, "Reverse")) return;
      const r = await run(() => api("/api/fi/fb08", { belnr: val(d), gjahr: val(y), budat: b.value, reason: rs.value }));
      if (r) msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: b.value.slice(0, 4) }); } }]);
}});

register("MR8M", { title: "Cancel Invoice Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" }), y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const b = inp({ type: "date", value: today(), w: "m" });
  const rs = sel([["01", "01 Wrong posting"], ["02", "02 Wrong price"], ["03", "03 Wrong quantity"]], "01", { w: "l" });
  app.append(panel("Invoice document", grid(field("Invoice document", d, { req: true }), field("Fiscal year", y), field("Reversal reason", rs), field("Posting date", b))),
    h("div.note", null, "Every line is reversed and the PO history (invoiced quantity) is restored. A price difference that went to stock comes back from stock only as far as the stock is still there; the rest goes to price differences. A paid invoice needs FBRA first."));
  toolbar([{ label: "Display invoice", onClick: () => go("FB03", { id: val(d), year: val(y) }) },
    { label: "Cancel invoice", key: "Ctrl+S", primary: true, onClick: async () => {
      if (!await confirmBox("Cancel invoice", `Cancel invoice document ${val(d)} / ${val(y)}?`, "Cancel invoice")) return;
      const r = await run(() => api("/api/fi/mr8m", { belnr: val(d), gjahr: val(y), budat: b.value, reason: rs.value }));
      if (r) msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: String(r.gjahr) }); } }]);
}});

register("MRBR", { title: "Release Blocked Invoices", async render(app) {
  const body = out(); app.append(body);
  const load = async () => {
    const rows = await run(() => api("/api/fi/mrbr")); if (!rows) return; body.innerHTML = "";
    body.append(panel(null, h("p.muted", null, "Invoices with a price variance above the tolerance are blocked for payment (R). They must be released by another person than the one who posted them.")),
      alv({ rows, columns: [{ key: "belnr", label: "Document", link: r => go("FB03", { id: r.belnr, year: String(r.gjahr) }) }, { key: "gjahr", label: "Year" },
        { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "xblnr", label: "Reference" }, { key: "budat", label: "Posted", type: "date" },
        { key: "usnam", label: "Posted by" }, { key: "wrbtr", label: "Amount", type: "amt" }, { key: "waers", label: "Curr." },
        { key: "rel", label: "", render: r => h("button.btn.ghost", { type: "button", on: { click: async () => {
          const x = await run(() => api("/api/fi/mrbr", { belnr: r.belnr, gjahr: r.gjahr })); if (x) { msg("S", x.message); load(); } } } }, "Release") }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]); load();
}});

register("FBRA", { title: "Reset Cleared Items", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" }), y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const rv = h("input", { type: "checkbox" }), list = out();
  app.append(panel("Clearing document", grid(field("Clearing document", d, { req: true }), field("Fiscal year", y),
    field("Reset and reverse", rv))), h("div.note", null, "All items cleared with this document are open again. With 'reverse' the clearing document itself (e.g. a payment) is reversed too."), list);
  const show = async () => {
    const rows = await run(() => api(`/api/fi/fbra?augbl=${enc(val(d))}`)); if (!rows) return; list.innerHTML = "";
    list.append(alv({ rows, columns: [{ key: "belnr", label: "Document" }, { key: "buzei", label: "Item" }, { key: "koart", label: "Type" },
      { key: "lifnr", label: "Vendor" }, { key: "kunnr", label: "Customer" }, { key: "hkont", label: "Account" }, { key: "budat", label: "Posted", type: "date" },
      { key: "tcode", label: "T-code" }, { key: "amount", label: "Amount", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Items", onClick: show }, { label: "Reset clearing", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!await confirmBox("Reset clearing", `Reset clearing ${val(d)}${rv.checked ? " and reverse the document" : ""}?`, "Reset")) return;
    const r = await run(() => api("/api/fi/fbra", { augbl: val(d), gjahr: val(y), reverse: rv.checked })); if (r) { msg("S", r.message); show(); } } }]);
  if (params.id) show();
}});

register("F.16", { title: "Balance Carry-Forward (Year End)", async render(app) {
  const y = inp({ value: String(Number(today().slice(0, 4)) - 1), w: "s" }), body = out();
  app.append(panel("Fiscal year to close", grid(field("Carry forward from year", y, { req: true }))),
    h("div.note", null, "The P&L result of the year is carried to retained earnings (081000). The balance is always derived from the postings, so a late posting into the old year is carried automatically; the run confirms the year and can be repeated."), body);
  const exec = async test => {
    const r = await run(() => api("/api/fi/f16", { gjahr: val(y), test })); if (!r) return; msg("S", r.message);
    body.innerHTML = ""; body.append(panel(test ? "Test run" : "Carried forward", h("p", null, `Result ${fmtAmt(r.result)} to account ${r.account} for ${r.to_year}`)),
      alv({ rows: r.accounts, columns: [{ key: "hkont", label: "Account" }, { key: "txt", label: "Text" }, { key: "balance", label: "Year balance", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Test run", onClick: () => exec(true) }, { label: "Execute", key: "F8", primary: true, onClick: () => exec(false) }]);
  const st = await api("/api/fi/f16"); if (st && st.missing && st.missing.length) msg("W", `Balance carry-forward not yet run for: ${st.missing.join(", ")}`);
}});

register("ZAFAB_REV", { title: "Reverse Depreciation Run", async render(app) {
  const y = inp({ value: today().slice(0, 4), w: "s" }), p = inp({ value: String(Number(today().slice(5, 7))), w: "s" });
  app.append(panel("Period", grid(field("Fiscal year", y, { req: true }), field("Period", p, { req: true }))),
    h("div.note", null, "Only the last posted depreciation period can be reversed. Afterwards AFAB posts the period again."));
  toolbar([{ label: "Reverse", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!await confirmBox("Reverse depreciation", `Reverse depreciation ${val(p)}/${val(y)}?`, "Reverse")) return;
    const r = await run(() => api("/api/fi/afab-reverse", { gjahr: val(y), perio: val(p) })); if (r) msg("S", r.message); } }]);
}});

register("FBS1", { title: "Enter Accrual / Deferral Document", async render(app) {
  await meta();
  const b = inp({ type: "date", value: today(), w: "m" }), r = inp({ type: "date", w: "m" }), t = inp({ w: "l", value: "Accrual" });
  const lines = [{ hkont: "", dc: "S", amt: "", kostl: "" }, { hkont: "190000", dc: "H", amt: "", kostl: "" }];
  const g = itemGrid([{ key: "hkont", label: "G/L account", list: "dl-hkont" }, { key: "dc", label: "D/C", options: [["S", "Debit"], ["H", "Credit"]] },
    { key: "amt", label: "Amount" }, { key: "kostl", label: "Cost center", list: "dl-kostl", upper: true, w: "s" }], lines);
  app.append(panel("Header", grid(field("Posting date", b, { req: true }), field("Reversal date", r, { req: true }), field("Text", t))),
    h("div.panel", null, h("div.panel-head", null, "Items"), g), h("div.note", null, "F.81 reverses the document on the reversal date (e.g. accrued audit fee)."));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const x = await run(() => api("/api/fi/fbs1", { budat: b.value, stodt: r.value, text: val(t), lines: lines.filter(l => l.hkont).map(l => ({ hkont: l.hkont,
      debit: l.dc === "S" ? l.amt : "", credit: l.dc === "H" ? l.amt : "", kostl: l.kostl })) }));
    if (x) msgLink("S", x.message, "Display", "FB03", { id: x.belnr, year: b.value.slice(0, 4) }); } }]);
}});

register("F.81", { title: "Reverse Accrual / Deferral Documents", async render(app) {
  const d1 = inp({ type: "date", value: today(), w: "m" }), d2 = inp({ type: "date", value: today(), w: "m" }), o = out();
  app.append(panel("Reversal date interval", grid(field("From", d1), field("To", d2))), o);
  execBar(async () => {
    const r = await run(() => api("/api/fi/f81", { d1: d1.value, d2: d2.value }));
    if (!r) return; o.innerHTML = "";
    o.append(alv({ title: "Reversed documents", rows: r.lines, columns: [{ key: "belnr", label: "Original", link: x => go("FB03", { id: x.belnr }) },
      { key: "reversal", label: "Reversal doc.", link: x => go("FB03", { id: x.reversal }) }, { key: "budat", label: "Date", type: "date" }, { key: "text", label: "Text" }] }));
    msg("S", r.message);
  });
}});

register("S_ALR_87012277", { title: "G/L Account Balances (Trial Balance)", async render(app, params) {
  await meta();
  const y = inp({ value: FI.sample.gjahr, w: "s" }), p1 = inp({ value: params.pfrom || 1, w: "s" }), p2 = inp({ value: params.pto || FI.sample.perio, w: "s" }), o = out();
  app.append(panel("Selection", grid(field("Fiscal year", y), field("From period", p1), field("To period", p2))), o);
  const exec = async () => {
    const rows = await run(() => api(`/api/fi/tb?gjahr=${val(y)}&pfrom=${val(p1)}&pto=${val(p2)}`));
    if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: `Trial balance ${mon(val(y), val(p1))} - ${mon(val(y), val(p2))}`, exportName: "TrialBalance", rows, columns: [
      { key: "hkont", label: "G/L acct", link: r => go("FS10N", { hkont: r.hkont }) }, { key: "txt", label: "Name" }, { key: "typ", label: "BS/PL" },
      { key: "opening", label: "Carryfwd / opening", type: "amt", sum: true, signed: true }, { key: "debit", label: "Debit", type: "amt", sum: true },
      { key: "credit", label: "Credit", type: "amt", sum: true }, { key: "period", label: "Period balance", type: "amt", sum: true, signed: true },
      { key: "closing", label: "Closing balance", type: "amt", sum: true, signed: true }] }),
    h("div.note", { style: { marginTop: "8px" } }, "Debit total = credit total; the sum of all closing balances is zero."));
  };
  execBar(exec); exec();
}});

register("F.01", { title: "Financial Statements (Balance Sheet / P&L)", async render(app, params) {
  await meta();
  const y = inp({ value: params.gjahr || FI.sample.gjahr, w: "s" }), p1 = inp({ value: params.pfrom || FI.sample.perio, w: "s" }), p2 = inp({ value: params.pto || FI.sample.perio, w: "s" });
  const det = h("input", { type: "checkbox" }), o = out();
  app.append(panel("Financial statement version FSEG · company code 1000", grid(field("Fiscal year", y), field("From period", p1), field("To period", p2),
    field("Detail", h("label.checkbox", null, det, "Show G/L accounts")))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/fi/fs?gjahr=${val(y)}&pfrom=${val(p1)}&pto=${val(p2)}`));
    if (!d) return; o.innerHTML = "";
    const t = h("table.grid.pnl");
    t.append(h("thead", null, h("tr", null, ["Item", `Reporting period ${d.period}`, `Comparison ${d.cmp_period}`, "Abs. difference", "Rel. %"].map((x, i) => h("th" + (i ? ".num" : ""), null, x)))));
    const tb = h("tbody");
    for (const r of d.rows) {
      const top = r.level === 0;
      tb.append(h("tr" + (top || r.level === 1 ? ".sub" : ""), null, h("td", { style: { paddingLeft: (8 + r.level * 18) + "px", fontWeight: top ? 700 : r.level === 1 ? 600 : 400 } }, r.text),
        h("td.num", null, fmtAmt(r.cur)), h("td.num", null, fmtAmt(r.cmp)), h("td.num", { class: "num " + (r.diff < 0 ? "neg" : "") }, fmtAmt(r.diff)),
        h("td.num", null, r.pct === null ? "" : r.pct.toFixed(1) + " %")));
      if (det.checked) for (const a of r.accounts) tb.append(h("tr", null, h("td", { style: { paddingLeft: (26 + r.level * 18) + "px" }, class: "muted" },
        h("a", { href: `#/FS10N?hkont=${a.hkont}` }, a.hkont), " ", a.txt), h("td.num.muted", null, fmtAmt(a.cur)), h("td.num.muted", null, fmtAmt(a.cmp)), h("td"), h("td")));
    }
    t.append(tb);
    o.append(h("div.panel", null, h("div.obj-header", null, [["Total assets", fmtAmt(d.assets)], ["Equity & liabilities", fmtAmt(d.liabilities)],
      ["Balance check", h("span", { class: d.balanced ? "pos" : "neg" }, d.balanced ? "✔ balanced" : "✖ difference")],
      ["Operating result", fmtAmt(d.operating)], ["Financial result", fmtAmt(d.financial)], ["Result of the period", h("b", null, fmtAmt(d.result))]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))), h("div.alv", null, h("div.alv-scroll", null, t)),
    h("div.note", { style: { marginTop: "8px" } }, "Liabilities, equity and revenues are shown positive, expenses negative. The result of the period is the balance of all P&L accounts (not yet carried forward)."));
  };
  det.addEventListener("change", exec);
  execBar(exec, [{ label: "Print", ghost: true, onClick: () => window.print() }]); exec();
}});
register("S_ALR_87012284", { title: "Balance Sheet / P&L Statement", render: (a, p) => go("F.01", p) });

register("FAGL_FCV", { title: "Foreign Currency Valuation", async render(app) {
  await meta();
  const kd = inp({ type: "date", value: sampleEnd(), w: "m" }), test = h("input", { type: "checkbox", checked: true }), o = out();
  app.append(panel("Parameters", grid(field("Key date", kd), field("Processing", h("label.checkbox", null, test, "Test run"))),
    h("div.note", null, "Open vendor/customer items in foreign currency are valued at the key-date rate (OB08). The posting is reversed on the next day (F.81).")), o);
  execBar(async () => {
    const r = await run(() => api("/api/fi/fcv", { key_date: kd.value, test: test.checked }));
    if (!r) return; o.innerHTML = "";
    o.append(alv({ title: "Valuated items", rows: r.lines, columns: [{ key: "koart", label: "Type" }, { key: "partner", label: "Partner" },
      { key: "belnr", label: "Document", link: x => go("FB03", { id: x.belnr }) }, { key: "waers", label: "Crcy" }, { key: "amount_fc", label: "Amount FC", type: "amt" },
      { key: "booked", label: "Booked LC", type: "amt" }, { key: "rate", label: "Key date rate", type: "amt" }, { key: "valued", label: "Valued LC", type: "amt" },
      { key: "difference", label: "Valuation diff.", type: "amt", sum: true, signed: true }] }));
    msg(test.checked ? "I" : "S", r.message);
  });
}});

register("F.13", { title: "Automatic Clearing (GR/IR Account)", async render(app) {
  await meta();
  const d = inp({ type: "date", value: today(), w: "m" }), test = h("input", { type: "checkbox", checked: true }), o = out();
  app.append(panel("Parameters - account 191100, grouping by purchase order item", grid(field("Clearing date", d), field("Processing", h("label.checkbox", null, test, "Test run")))), o);
  execBar(async () => {
    const r = await run(() => api("/api/fi/f13", { budat: d.value, test: test.checked }));
    if (!r) return; o.innerHTML = "";
    o.append(alv({ title: "GR/IR groups", rows: r.lines, rowClass: x => x.cleared ? "" : "", columns: [{ key: "zuonr", label: "Assignment (PO + item)" },
      { key: "items", label: "Items", type: "int" }, { key: "balance", label: "Balance", type: "amt", signed: true },
      { key: "cleared", label: "Result", render: x => x.cleared ? badge("clearable", "U") : badge("GR ≠ IR", "Q") }] }));
    msg(test.checked ? "I" : "S", r.message);
  });
}});

// ================================================================== vendors / customers
function partnerCreate(code, koart) {
  register(code, { title: koart === "K" ? "Create Vendor (Accounting & Purchasing)" : "Create Customer (Accounting & Sales)", async render(app) {
    await meta();
    const f = { id: inp({ upper: true, w: "m" }), name: inp({ w: "l" }), city: inp({ w: "m" }), land: inp({ value: "EG", upper: true, w: "s" }),
      zterm: termsSel(koart === "K" ? "NT30" : "NT30"), stcd1: inp({ w: "m" }) };
    const extra = koart === "K" ? { akont: sel([["160000", "160000 Vendors domestic"], ["161000", "161000 Vendors foreign"]], "160000", { w: "l" }),
      waers: sel(Object.keys(FI.currencies), "EGP", { w: "s" }), bankn: inp({ w: "l" }) } :
      { region: sel([["CAI", "CAI Cairo"], ["ALX", "ALX Alexandria"], ["DLT", "DLT Delta"], ["EXP", "EXP Export"]], "CAI", { w: "m" }),
        kdgrp: sel([["01", "01 Retail"], ["02", "02 Wholesale"], ["03", "03 Export"]], "01", { w: "m" }),
        vtweg: sel([["10", "10 Domestic"], ["20", "20 Export"]], "10", { w: "m" }), klimk: inp({ value: "500000", w: "m" }) };
    app.append(panel("General data", grid(field(koart === "K" ? "Vendor" : "Customer", f.id, { req: true }), field("Name", f.name, { req: true }),
      field("City", f.city), field("Country", f.land), field("Tax number", f.stcd1))),
    panel("Company code 1000 / " + (koart === "K" ? "purchasing" : "sales area & credit"), grid(
      koart === "K" ? field("Reconciliation acct", extra.akont) : field("Reconciliation acct", inp({ value: "140000", readonly: true, w: "m" })),
      field("Terms of payment", f.zterm), ...(koart === "K" ? [field("Currency", extra.waers), field("Bank account", extra.bankn)] :
        [field("Sales district", extra.region), field("Customer group", extra.kdgrp), field("Distribution channel", extra.vtweg), field("Credit limit (EGP)", extra.klimk)]))));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const body = { name: val(f.name), city: val(f.city), land: up(f.land), zterm: f.zterm.value, stcd1: val(f.stcd1) };
      if (koart === "K") Object.assign(body, { lifnr: up(f.id), akont: extra.akont.value, waers: extra.waers.value, bankn: val(extra.bankn) });
      else Object.assign(body, { kunnr: up(f.id), region: extra.region.value, kdgrp: extra.kdgrp.value, vtweg: extra.vtweg.value, klimk: val(extra.klimk) });
      const r = await run(() => api(koart === "K" ? "/api/fi/xk01" : "/api/fi/xd01", body));
      if (r) { msg("S", r.message); await meta(true); } } }]);
  }});
}
partnerCreate("XK01", "K");
partnerCreate("XD01", "D");
register("FK01", { title: "Create Vendor (Accounting)", render: () => go("XK01") });
register("FD01", { title: "Create Customer (Accounting)", render: () => go("XD01") });

register("XK03", { title: "Display / Change Vendors (XK02)", async render(app) {
  await meta(true);
  const o = out(); app.append(o);
  const draw = () => { o.innerHTML = ""; o.append(alv({ title: "Vendors - company code 1000", rows: FI.vendors, columns: [
    { key: "lifnr", label: "Vendor", link: r => go("FBL1N", { key: r.lifnr }) }, { key: "name", label: "Name" }, { key: "city", label: "City" }, { key: "land", label: "Ctry" },
    { key: "akont", label: "Recon. acct" }, { key: "waers", label: "Crcy" },
    { key: "zterm", label: "Terms", render: r => { const s = termsSel(r.zterm, "m"); s.addEventListener("change", async () => {
      const x = await run(() => api("/api/fi/xk02", { lifnr: r.lifnr, zterm: s.value })); if (x) { msg("S", x.message); await meta(true); } }); return s; } },
    { key: "sperr", label: "Payment block", render: r => { const c = h("input", { type: "checkbox", checked: !!r.sperr }); c.addEventListener("change", async () => {
      const x = await run(() => api("/api/fi/xk02", { lifnr: r.lifnr, sperr: c.checked ? 1 : 0 })); if (x) { msg("S", x.message); await meta(true); } }); return c; } }] })); };
  draw();
}});
register("XK02", { title: "Change Vendor", render: () => go("XK03") });

register("XD03", { title: "Display / Change Customers (XD02)", async render(app) {
  await meta(true);
  app.append(alv({ title: "Customers - company code 1000", rows: FI.customers, columns: [
    { key: "kunnr", label: "Customer", link: r => go("FBL5N", { key: r.kunnr }) }, { key: "name", label: "Name" }, { key: "city", label: "City" },
    { key: "region", label: "Region" }, { key: "kdgrp", label: "Cust.grp" }, { key: "vtweg", label: "Channel" }, { key: "akont", label: "Recon. acct" },
    { key: "zterm", label: "Terms", render: r => { const s = termsSel(r.zterm, "m"); s.addEventListener("change", async () => {
      const x = await run(() => api("/api/fi/xd02", { kunnr: r.kunnr, zterm: s.value })); if (x) msg("S", x.message); }); return s; } },
    { key: "klimk", label: "Credit limit", type: "amt" }] }));
}});
register("XD02", { title: "Change Customer", render: () => go("XD03") });

function partnerBal(code, koart, title) {
  register(code, { title, async render(app) {
    await meta();
    const o = out(); app.append(o);
    const rows = await run(() => api(`/api/fi/partners?koart=${koart}&gjahr=${FI.sample.gjahr}`));
    if (!rows) return;
    o.append(alv({ title: `${title} - fiscal year ${FI.sample.gjahr}`, rows, columns: [
      { key: "partner", label: koart === "K" ? "Vendor" : "Customer", link: r => go(koart === "K" ? "FBL1N" : "FBL5N", { key: r.partner }) },
      { key: "name", label: "Name" }, { key: "akont", label: "Recon." }, { key: "zterm", label: "Terms" },
      { key: "debit", label: "Debit", type: "amt", sum: true }, { key: "credit", label: "Credit", type: "amt", sum: true },
      { key: "balance", label: "Balance", type: "amt", sum: true, signed: true }, { key: "open", label: "Open items", type: "amt", sum: true, signed: true },
      ...(koart === "D" ? [{ key: "klimk", label: "Credit limit", type: "amt" }] : [])] }));
  }});
}
partnerBal("FK10N", "K", "Vendor Balance Display");
partnerBal("FD10N", "D", "Customer Balance Display");

// ================================================================== AP postings
function invoiceScreen(code, koart, credit) {
  const isK = koart === "K";
  register(code, { title: (isK ? "Enter Vendor " : "Enter Customer ") + (credit ? "Credit Memo" : "Invoice"), async render(app) {
    await meta();
    const p = inp({ list: isK ? "dl-lifnr" : "dl-kunnr", upper: true, w: "m" }), pinfo = h("span.hint");
    const f = { bldat: inp({ type: "date", value: today(), w: "m" }), budat: inp({ type: "date", value: today(), w: "m" }),
      xblnr: inp({ w: "m" }), gross: inp({ w: "m", ph: "optional check" }), mwskz: taxSel(isK ? "I" : "O", isK ? "V1" : "A1"), bktxt: inp({ w: "l" }) };
    p.addEventListener("change", () => { const x = isK ? FI.vendors.find(v => v.lifnr === up(p)) : FI.customers.find(v => v.kunnr === up(p));
      pinfo.textContent = x ? `${x.name} · terms ${x.zterm} · ${isK ? (x.waers || "EGP") : "EGP"}` : ""; });
    const lines = [{ hkont: isK ? "" : "800000", amount: "", kostl: "", aufnr: "", matnr: "", sgtxt: "" }];
    const sum = h("span.badge");
    const calc = () => { const net = lines.reduce((a, l) => a + (parseFloat(l.amount) || 0), 0); const t = (FI.tax.find(x => x.mwskz === f.mwskz.value) || { pct: 0 }).pct;
      const gross = net * (1 + t / 100); const g = parseFloat(val(f.gross));
      sum.textContent = `Net ${fmtAmt(net)} + tax ${fmtAmt(net * t / 100)} = ${fmtAmt(gross)}` + (isNaN(g) ? "" : ` · balance ${fmtAmt(g - gross)}`);
      sum.className = "badge " + (isNaN(g) || Math.abs(g - gross) < 0.005 ? "U" : "B"); };
    f.mwskz.addEventListener("change", calc); f.gross.addEventListener("input", calc);
    const cols = [{ key: "hkont", label: "G/L account", list: "dl-hkont" }, { key: "amount", label: "Amount (net)" },
      ...(isK ? [{ key: "kostl", label: "Cost center", list: "dl-kostl", upper: true, w: "s" }, { key: "aufnr", label: "Order", list: "dl-aufnr" }] :
        [{ key: "matnr", label: "Product (CO-PA)", list: "dl-mat", upper: true }]), { key: "sgtxt", label: "Text", w: "l" }];
    const g = itemGrid(cols, lines, calc); calc();
    app.append(panel("Basic data", grid(field(isK ? "Vendor" : "Customer", h("span.split", null, p, pinfo), { req: true }), field("Invoice date", f.bldat),
      field("Posting date", f.budat, { req: true }), field("Reference", f.xblnr), field("Amount (gross)", f.gross), field("Tax code", f.mwskz), field("Text", f.bktxt))),
    h("div.panel", null, h("div.panel-head", null, "Items", h("span.spacer"), sum, h("button.btn.ghost", { type: "button", on: { click: () => {
      lines.push({ hkont: isK ? "" : "800000", amount: "" }); g.redraw(); } } }, "+ Line")), g),
    h("div.note", null, isK ? "Expense accounts need a cost center or order (flows to CO). Tax is calculated from the net amounts. Due date from the vendor's terms of payment."
      : "Revenue accounts 800000/800100 create a CO-PA line item (record type B) for the product. Output VAT is calculated."));
    toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api(isK ? "/api/fi/fb60" : "/api/fi/fb70", { credit_memo: credit, header: { [isK ? "lifnr" : "kunnr"]: up(p), bldat: f.bldat.value,
        budat: f.budat.value, xblnr: val(f.xblnr), gross: val(f.gross), mwskz: f.mwskz.value, bktxt: val(f.bktxt) },
        lines: lines.filter(l => l.hkont).map(l => ({ ...l, kostl: (l.kostl || "").toUpperCase(), mwskz: f.mwskz.value })) }));
      if (r) { msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: r.gjahr }); lines.forEach(l => { l.amount = ""; }); g.redraw(); calc(); } } }]);
  }});
}
invoiceScreen("FB60", "K", false);
invoiceScreen("FB65", "K", true);
invoiceScreen("FB70", "D", false);
invoiceScreen("FB75", "D", true);

register("MIRO", { title: "Enter Incoming Invoice (Logistics Invoice Verification)", async render(app, params) {
  await meta();
  const e = inp({ value: params.po || "", w: "m" }), f = { bldat: inp({ type: "date", value: today(), w: "m" }), budat: inp({ type: "date", value: today(), w: "m" }),
    xblnr: inp({ w: "m" }), gross: inp({ w: "m" }), mwskz: taxSel("I", "V1"),
    trx: sel([["1", "Invoice"], ["2", "Credit memo"], ["3", "Subsequent debit"], ["4", "Subsequent credit"]], params.trx || "1", { w: "m" }) };
  const head = h("div"), box = h("div.panel"), o = out();
  let items = [];
  const bal = h("span.badge");
  const calc = () => { const net = items.filter(i => i.ok).reduce((a, i) => a + (parseFloat(i.amount) || 0), 0);
    const t = (FI.tax.find(x => x.mwskz === f.mwskz.value) || { pct: 0 }).pct, gross = net * (1 + t / 100), g = parseFloat(val(f.gross));
    bal.textContent = isNaN(g) ? `Calculated gross ${fmtAmt(gross)}` : `Balance ${fmtAmt(g - gross)}`;
    bal.className = "badge " + (!isNaN(g) && Math.abs(g - gross) < 0.005 ? "U" : isNaN(g) ? "S" : "B"); };
  f.gross.addEventListener("input", calc); f.mwskz.addEventListener("change", calc);
  const load = async () => {
    const d = await run(() => api("/api/fi/miro/po/" + enc(val(e))));
    if (!d) return;
    head.innerHTML = ""; head.append(h("div.obj-header", { style: { padding: "8px 0 0" } }, [["Vendor", `${d.header.lifnr} ${d.header.name}`], ["Terms", d.header.zterm],
      ["PO date", fmtDate(d.header.bedat)]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v)))));
    items = d.items.map(i => ({ ...i, ok: i.to_invoice > 0, qty: String(i.to_invoice), amount: String(i.value) }));
    const tb = h("tbody");
    items.forEach(i => tb.append(h("tr", null, h("td", null, h("input", { type: "checkbox", checked: i.ok, on: { change: ev => { i.ok = ev.target.checked; calc(); } } })),
      h("td", null, String(i.ebelp)), h("td", null, i.matnr), h("td", null, i.maktx), h("td.num", null, fmtQty(i.wemng)), h("td.num", null, fmtQty(i.remng)),
      h("td", null, inp({ value: i.qty, w: "s", oninput: ev => { i.qty = ev.target.value; } })), h("td.num", null, `${fmtAmt(i.netpr)} / ${i.peinh}`),
      h("td", null, inp({ value: i.amount, w: "m", oninput: ev => { i.amount = ev.target.value; calc(); } })))));
    box.innerHTML = "";
    box.append(h("div.panel-head", null, "PO reference", h("span.spacer"), bal), h("div.items-wrap", null, h("table.grid.items", null, h("thead", null, h("tr", null,
      ["OK", "Item", "Material", "Text", "GR qty", "Invoiced", "Quantity", "PO price", "Amount (net)"].map(x => h("th", null, x)))), tb)));
    calc();
  };
  e.addEventListener("keydown", ev => { if (ev.key === "Enter") load(); });
  app.append(panel("Basic data", grid(field("Transaction", f.trx), field("Purchase order", h("span.split", null, e, h("button.btn", { type: "button", on: { click: load } }, "Adopt"))),
    field("Invoice date", f.bldat), field("Posting date", f.budat), field("Reference", f.xblnr), field("Amount (gross)", f.gross, { req: true }), field("Tax code", f.mwskz)), head),
  box, o, h("div.note", null, "3-way match: quantity ≤ goods received - already invoiced. GR/IR is cleared with the value of the goods receipts; a price (or exchange-rate) difference goes to stock (moving average) as long as stock exists, otherwise to 231500. A price variance above 5 % / 100.00 blocks the invoice for payment (MRBR). Cancel with MR8M."));
  const payload = sim => ({ simulate: sim, credit: ["2", "4"].includes(f.trx.value), subsequent: ["3", "4"].includes(f.trx.value), header: { ebeln: val(e), bldat: f.bldat.value, budat: f.budat.value, xblnr: val(f.xblnr), gross: val(f.gross), mwskz: f.mwskz.value },
    items: items.filter(i => i.ok).map(i => ({ ebelp: i.ebelp, qty: i.qty, amount: i.amount })) });
  toolbar([{ label: "Simulate", onClick: async () => {
    const r = await run(() => api("/api/fi/miro", payload(true))); if (!r) return;
    o.innerHTML = ""; o.append(alv({ title: "Simulated document", rows: r.lines.map(l => ({ ...l, txt: glText(l.hkont || (l.lifnr ? "160000" : "")) })), columns: [
      { key: "hkont", label: "G/L", render: l => h("span", null, l.hkont || `vendor ${l.lifnr}`) }, { key: "txt", label: "Text" }, { key: "ktosl", label: "Key" },
      { key: "amount", label: "Amount", type: "amt", sum: true, signed: true }, { key: "sgtxt", label: "Item text" }] })); msg("S", r.message); } },
  { label: "Post", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/fi/miro", payload(false)));
    if (r) { msgLink(r.type || "S", r.message, "Display", "FB03", { id: r.belnr, year: f.budat.value.slice(0, 4) }); load(); } } },
  { label: "Cancel invoice (MR8M)", ghost: true, onClick: () => go("MR8M") }, { label: "Blocked invoices (MRBR)", ghost: true, onClick: () => go("MRBR") }]);
  if (params.po) load();
}});

function payScreen(code, koart) {
  const isK = koart === "K";
  register(code, { title: isK ? "Post Outgoing Payments" : "Post Incoming Payments", async render(app, params) {
    await meta();
    const p = inp({ value: params.key || "", list: isK ? "dl-lifnr" : "dl-kunnr", upper: true, w: "m" }), b = inp({ type: "date", value: today(), w: "m" });
    const amt = inp({ w: "m", ph: "blank = full amount" }), res = h("input", { type: "checkbox" }), bank = inp({ value: "113100", list: "dl-hkont", w: "m" });
    const box = out();
    let items = [];
    const load = async () => {
      const rows = await run(() => api(`/api/fi/openitems?koart=${koart}&partner=${enc(up(p))}`));
      if (!rows) return;
      items = rows.map(r => ({ ...r, sel: true }));
      box.innerHTML = "";
      box.append(alv({ title: `Open items of ${up(p)} ${isK ? vName(up(p)) : cName(up(p))}`, rows: items, columns: [
        { key: "sel", label: "Pay", render: r => h("input", { type: "checkbox", checked: r.sel, on: { change: e => { r.sel = e.target.checked; } } }) },
        { key: "belnr", label: "Document", link: docLink }, { key: "budat", label: "Posting", type: "date" }, { key: "xblnr", label: "Reference" },
        { key: "amount", label: "Amount LC", type: "amt", sum: true, signed: true }, { key: "waers", label: "Crcy" }, { key: "amount_fc", label: "Amount DC", type: "amt", signed: true },
        { key: "zterm", label: "Terms" }, { key: "disc_date", label: "Discount until", type: "date" }, { key: "netdt", label: "Net due", type: "date" }] }));
    };
    p.addEventListener("keydown", e => { if (e.key === "Enter") load(); });
    app.append(panel("Header data", grid(field(isK ? "Vendor" : "Customer", h("span.split", null, p, h("button.btn", { type: "button", on: { click: load } }, "Process open items")), { req: true }),
      field("Posting date", b), field("Bank G/L account", bank), field("Amount", amt), field("Partial payment", h("label.checkbox", null, res, "Leave a residual item")))),
    box, h("div.note", null, "Cash discount is taken automatically if the payment date is within the discount period. Foreign currency items create a realized exchange difference (720000 / 721000)."));
    toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/fi/pay", { koart, partner: up(p), budat: b.value, bank: val(bank), amount: val(amt), residual: res.checked,
        items: items.filter(i => i.sel).map(i => [i.belnr, i.gjahr, i.buzei]) }));
      if (r) { msgLink("S", `${r.message} - paid ${fmtAmt(r.paid)} ${r.waers}, discount ${fmtAmt(r.discount)}, FX ${fmtAmt(r.fx)}`, "Display", "FB03", { id: r.belnr, year: r.gjahr }); load(); } } }]);
    if (params.key) load();
  }});
}
payScreen("F-53", "K");
payScreen("F-28", "D");

register("F110", { title: "Automatic Payment Transactions", async render(app) {
  await meta();
  const d = new Date(today()); const nx = new Date(d); nx.setDate(nx.getDate() + 14);
  const laufd = inp({ type: "date", value: today(), w: "m" }), laufi = inp({ value: "R1", upper: true, w: "s" }), nextd = inp({ type: "date", value: nx.toISOString().slice(0, 10), w: "m" });
  const o = out(), runs = out();
  app.append(panel("Parameters - company code 1000, payment method T (bank transfer), house bank NBE", grid(field("Run date", laufd), field("Identification", laufi),
    field("Next payment date", nextd)), h("div.note", null, "Pays every vendor item due before the next payment date; uses cash discount when the discount date is not yet passed. Blocked vendors are skipped.")), o, runs);
  const listRuns = async () => { const r = await run(() => api("/api/fi/f110")); if (!r) return; runs.innerHTML = "";
    runs.append(gap(), alv({ title: "Payment runs", rows: r, columns: [{ key: "laufd", label: "Run date", type: "date" }, { key: "laufi", label: "ID" }, { key: "nextd", label: "Next date", type: "date" },
      { key: "status", label: "Status", render: x => badge(x.status, x.status === "PAID" ? "U" : "Q") }, { key: "count", label: "Vendors", type: "int" }, { key: "docs", label: "Payment documents" }, { key: "usnam", label: "User" }] })); };
  const go_ = async execute => {
    if (execute && !await confirmBox("Payment run", `Execute payment run ${val(laufi)} on ${laufd.value}?`, "Execute")) return;
    const r = await run(() => api("/api/fi/f110", { laufd: laufd.value, laufi: val(laufi), nextd: nextd.value, execute }));
    if (!r) return; o.innerHTML = "";
    const flat = []; r.payments.forEach(p => p.items.forEach(i => flat.push({ ...i, lifnr: p.lifnr, name: p.name, waers: p.waers, pdoc: p.belnr || "" })));
    o.append(alv({ title: (execute ? "Payment list" : "Payment proposal") + ` · total EGP ${fmtAmt(r.total)}`, rows: flat, columns: [
      { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "belnr", label: "Invoice doc.", link: x => go("FB03", { id: x.belnr, year: x.gjahr }) },
      { key: "xblnr", label: "Reference" }, { key: "netdt", label: "Due", type: "date" }, { key: "waers", label: "Crcy" },
      { key: "amount", label: "Amount", type: "amt", sum: true, signed: true }, { key: "discount", label: "Cash discount", type: "amt", sum: true, signed: true },
      { key: "pdoc", label: "Payment doc.", link: x => x.pdoc && go("FB03", { id: x.pdoc }) },
      { key: "ex", label: "", render: x => execute ? "" : h("button.btn.ghost", { type: "button", on: { click: async () => {
        const y = await run(() => api("/api/fi/f110/exclude", { laufd: laufd.value, laufi: val(laufi), belnr: x.belnr, gjahr: x.gjahr, buzei: x.buzei, exclude: !x.excluded }));
        if (y) { x.excluded = !x.excluded; msg("S", y.message); } } } }, x.excluded ? "Include" : "Exclude") }] }));
    if (r.exceptions && r.exceptions.length) o.append(gap(), alv({ title: "Exception list (not paid)", rows: r.exceptions, columns: [{ key: "lifnr", label: "Vendor" },
      { key: "name", label: "Name" }, { key: "reason", label: "Reason" }, { key: "amount", label: "Amount", type: "amt" }] }));
    msg("S", r.message); listRuns();
  };
  toolbar([{ label: "Proposal", key: "F8", onClick: () => go_(false) }, { label: "Payment run", primary: true, onClick: () => go_(true) },
    { label: "Delete proposal", ghost: true, onClick: async () => { const r = await run(() => api("/api/fi/f110/delete", { laufd: laufd.value, laufi: val(laufi) })); if (r) { msg("S", r.message); o.innerHTML = ""; listRuns(); } } }]);
  listRuns();
}});

function agingScreen(code, koart, title) {
  register(code, { title, async render(app) {
    await meta();
    const kd = inp({ type: "date", value: sampleEnd(), w: "m" }), o = out();
    app.append(panel("Key date", grid(field("Open items at key date", kd))), o);
    const exec = async () => {
      const r = await run(() => api(`/api/fi/aging?koart=${koart}&key_date=${kd.value}`));
      if (!r) return; o.innerHTML = "";
      const tot = k => r.rows.reduce((a, x) => a + x[k], 0);
      o.append(h("div.cards", null, card("Due date structure", `${koart === "K" ? "Payables" : "Receivables"} by days overdue`,
        bars(r.buckets.map(([k, t]) => ({ t: k === "not_due" ? "Not due" : t + " days overdue", v: tot(k) })), x => x.t, x => x.v, fmtAmt))), gap(),
      alv({ title, rows: r.rows, columns: [{ key: "partner", label: koart === "K" ? "Vendor" : "Customer", link: x => go(koart === "K" ? "FBL1N" : "FBL5N", { key: x.partner }) },
        { key: "name", label: "Name" }, ...r.buckets.map(([k, t]) => ({ key: k, label: k === "not_due" ? "Not due" : t + " days", type: "amt", sum: true })),
        { key: "total", label: "Total", type: "amt", sum: true }] }));
    };
    execBar(exec); exec();
  }});
}
agingScreen("S_ALR_87012078", "K", "Vendors: Due Date Analysis for Open Items");
agingScreen("S_ALR_87012168", "D", "Customers: Due Date Analysis for Open Items");

// ================================================================== AR special
register("FD32", { title: "Credit Management - Credit Limits & Exposure", async render(app) {
  await meta();
  const o = out(); app.append(o);
  const exec = async () => {
    const rows = await run(() => api("/api/fi/credit")); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "Credit overview (credit control area 1000)", rows, columns: [{ key: "kunnr", label: "Customer", link: r => go("FBL5N", { key: r.kunnr }) },
      { key: "name", label: "Name" }, { key: "klimk", label: "Credit limit", render: r => { const i = inp({ value: r.klimk, w: "m" }); i.addEventListener("change", async () => {
        const x = await run(() => api("/api/fi/xd02", { kunnr: r.kunnr, klimk: i.value })); if (x) { msg("S", x.message); exec(); } }); return i; } },
      { key: "exposure", label: "Credit exposure", type: "amt", sum: true }, { key: "free", label: "Free limit", type: "amt", signed: true },
      { key: "used", label: "Used", render: r => h("span.split", null, h("span.track", { style: { width: "90px", height: "10px", background: "#eef1f4", display: "inline-block", borderRadius: "2px", overflow: "hidden" } },
        h("span", { style: { display: "block", height: "100%", width: Math.min(r.used || 0, 100) + "%", background: (r.used || 0) > 90 ? "#bb0000" : "#0a6ed1" } })), (r.used ?? 0) + " %") },
      { key: "zterm", label: "Terms" }] }), h("div.note", { style: { marginTop: "8px" } }, "Billing (VF01) is blocked with message VF 035 when open items + the new invoice exceed the credit limit."));
  };
  exec();
}});

register("F150", { title: "Dunning Run", async render(app) {
  await meta();
  const d = inp({ type: "date", value: sampleEnd(), w: "m" }), o = out();
  app.append(panel(`Dunning procedure ${FI.dunning.procedure}: interval ${FI.dunning.interval} days, grace ${FI.dunning.grace} days`, grid(field("Run date / issue date", d)),
    h("div.note", null, FI.dunning.levels.map(l => `Level ${l.level}: ${l.text} (charges ${fmtAmt(l.charges)})`).join(" · "))), o);
  const letter = L => {
    const tbody = h("tbody", null, L.items.map(i => h("tr", null, h("td", null, i.belnr), h("td", null, "due " + fmtDate(i.netdt)),
      h("td.num", null, fmtAmt(i.amount)))));
    tbody.append(h("tr", null, h("td", null, h("b", null, "Total")), h("td", null, L.charges ? `+ dunning charges ${fmtAmt(L.charges)}` : ""),
      h("td.num", null, h("b", null, fmtAmt(L.total + L.charges)))));
    return h("div", { style: { border: "1px solid #ddd", padding: "14px", marginBottom: "10px", background: "#fff" } },
      h("div", { style: { display: "flex", justifyContent: "space-between" } }, h("b", null, FI.butxt), h("span", null, fmtDate(r0.ausdt))),
      h("p", null, `${L.name}, ${L.city}`), h("h3", { style: { margin: "6px 0" } }, `${L.level_text} (level ${L.level})`),
      h("p", null, "According to our records the following items are overdue. Please pay the outstanding amount immediately."),
      h("table.grid", null, tbody));
  };
  let r0 = {};
  const show = r => {
    r0 = r;
    o.innerHTML = "";
    const rows = []; r.letters.forEach(L => L.items.forEach(i => rows.push({ ...i, kunnr: L.kunnr, name: L.name, letter_level: L.level })));
    o.append(alv({ title: `${r.executed ? "Dunning run" : "Dunning proposal"} ${fmtDate(r.ausdt)}`, rows, columns: [
      { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "belnr", label: "Document", link: x => go("FB03", { id: x.belnr, year: x.gjahr }) },
      { key: "netdt", label: "Net due", type: "date" }, { key: "overdue", label: "Days overdue", type: "int", cls: () => "neg" }, { key: "amount", label: "Amount", type: "amt", sum: true },
      { key: "old_level", label: "Old level", type: "int" }, { key: "level", label: "New level", type: "int" }] }), gap(),
    h("div.panel", null, h("h2", null, "Dunning notices (print preview)"), h("div.panel-body", null, r.letters.map(letter))));
    msg("S", r.message);
  };
  toolbar([{ label: "Proposal", key: "F8", onClick: async () => { const r = await run(() => api("/api/fi/f150", { ausdt: d.value, execute: false })); if (r) show(r); } },
    { label: "Dunning run & print", primary: true, onClick: async () => { const r = await run(() => api("/api/fi/f150", { ausdt: d.value, execute: true })); if (r) show(r); } },
    { label: "Print", ghost: true, onClick: () => window.print() }]);
}});

// ================================================================== assets
register("AS01", { title: "Create Asset Master Record", async render(app) {
  await meta();
  const c = sel(FI.asset_classes.map(x => [x.anlkl, `${x.anlkl} ${x.text}`]), "2000", { w: "l" }), t = inp({ w: "l" }), k = inp({ list: "dl-kostl", upper: true, w: "s" });
  const n = inp({ w: "s", ph: "class default" }), inv = inp({ w: "m" });
  app.append(panel("Asset", grid(field("Asset class", c), field("Description", t, { req: true }), field("Cost center", k, { req: true }),
    field("Useful life (years)", n), field("Inventory number", inv))), h("div.note", null, "Depreciation key LINS: straight-line, starting the month after capitalization. Depreciation goes to the cost center (CO)."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/as01", { anlkl: c.value, txt: val(t), kostl: up(k), ndjar: val(n), invnr: val(inv) }));
    if (r) { await meta(true); msgLink("S", r.message, "Acquire (F-90)", "F-90", { id: r.anln1 }); } } }]);
}});

register("AR01", { title: "Asset Balances", async render(app) {
  await meta();
  const upto = inp({ type: "date", value: sampleEnd(), w: "m" }), o = out();
  app.append(panel("Report date", grid(field("Values up to", upto))), o);
  const exec = async () => {
    const rows = await run(() => api(`/api/fi/ar01?upto=${upto.value}`)); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "Asset balances - depreciation area 01 book", rows, rowClass: r => r.deakt ? ".canceled" : "", columns: [
      { key: "anln1", label: "Asset", link: r => go("AW01N", { id: r.anln1 }) }, { key: "txt", label: "Description" }, { key: "anlkl", label: "Class" }, { key: "cls", label: "Class text" },
      { key: "kostl", label: "Cost ctr" }, { key: "aktiv", label: "Capitalized", type: "date" }, { key: "ndjar", label: "Life (y)", type: "int" },
      { key: "apc", label: "Acquisition value", type: "amt", sum: true }, { key: "accdep", label: "Accum. depreciation", type: "amt", sum: true, signed: true },
      { key: "nbv", label: "Book value", type: "amt", sum: true }, { key: "monthly", label: "Dep. per month", type: "amt", sum: true }, { key: "deakt", label: "Retired", type: "date" }] }));
  };
  execBar(exec); exec();
}});
register("AS03", { title: "Display Asset", render: () => go("AR01") });

register("AW01N", { title: "Asset Explorer", async render(app, params) {
  await meta();
  const a = inp({ value: params.id || (FI.assets[0] || {}).anln1 || "", list: "dl-anln1", w: "m" }), y = inp({ value: FI.sample.gjahr, w: "s" }), o = out();
  app.append(panel("Asset", grid(field("Asset", a, { req: true }), field("Fiscal year", y))), o);
  const exec = async () => {
    const e = await run(() => api(`/api/fi/aw01n?anln1=${val(a)}&gjahr=${val(y)}`)); if (!e) return; o.innerHTML = "";
    o.append(h("div.panel", null, h("div.obj-header", null, [["Asset", `${e.anln1} ${e.txt}`], ["Class", `${e.anlkl} ${e.cls}`], ["Cost center", e.kostl],
      ["Capitalized", fmtDate(e.aktiv)], ["Useful life", e.ndjar + " years"], ["Dep. key", e.afasl], ["Retired", e.deakt ? fmtDate(e.deakt) : "-"]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, String(v)))))),
    h("div.two-col", null, alv({ title: "Values fiscal year " + e.gjahr, rows: [
      { t: "Acquisition value - start of year", v: e.apc_start }, { t: "Acquisitions", v: e.acquisitions }, { t: "Retirements", v: e.retirements },
      { t: "Acquisition value - end", v: e.apc_end }, { t: "Accumulated depreciation - start", v: e.dep_start }, { t: "Ordinary depreciation (posted)", v: e.dep_year },
      { t: "Depreciation on retirements", v: e.dep_retired }, { t: "Accumulated depreciation - end", v: e.dep_end }, { t: "Planned depreciation of the year", v: -e.planned_year },
      { t: "Book value - start", v: e.nbv_start }, { t: "Book value - end", v: e.nbv_end }], columns: [{ key: "t", label: "Value" }, { key: "v", label: "Amount", type: "amt", signed: true }] }),
      alv({ title: "Depreciation per period", rows: e.periods, columns: [{ key: "perio", label: "Period", type: "int" }, { key: "planned", label: "Planned", type: "amt", sum: true },
        { key: "posted", label: "Posted", type: "amt", sum: true }] })), gap(),
    alv({ title: "Transactions", rows: e.items, columns: [{ key: "budat", label: "Date", type: "date" }, { key: "bwasl", label: "Trans. type", render: r => h("span", null, `${r.bwasl} ${FI.asset_trans[r.bwasl] || ""}`) },
      { key: "belnr", label: "Document", link: r => r.belnr !== "LEGACY" && go("FB03", { id: r.belnr, year: r.gjahr }) }, { key: "apc", label: "APC", type: "amt", sum: true, signed: true },
      { key: "dep", label: "Depreciation", type: "amt", sum: true, signed: true }, { key: "txt", label: "Text" }] }));
  };
  execBar(exec); if (val(a)) exec();
}});

function assetPost(code, title, mode) {
  register(code, { title, async render(app, params) {
    await meta();
    const a = inp({ value: params.id || "", list: "dl-anln1", w: "m" }), b = inp({ type: "date", value: today(), w: "m" });
    const amount = inp({ w: "m" }), partner = inp({ list: mode === "sale" ? "dl-kunnr" : "dl-lifnr", upper: true, w: "m" }), x = inp({ w: "m" });
    const tax = taxSel(mode === "sale" ? "O" : "I", mode === "sale" ? "A1" : "V1");
    const fields = [field("Asset", a, { req: true }), field("Posting date", b)];
    if (mode === "vendor") fields.push(field("Vendor", partner, { req: true }), field("Amount (net, vendor currency)", amount, { req: true }), field("Tax code", tax), field("Reference", x));
    if (mode === "clearing") fields.push(field("Amount", amount, { req: true }));
    if (mode === "sale") fields.push(field("Customer", partner, { req: true }), field("Revenue (net)", amount, { req: true }), field("Tax code", tax));
    const notes = { vendor: "Transaction type 100: Dr asset (APC account of the class), input VAT, Cr vendor. Foreign currency vendors are converted at the posting date rate.",
      clearing: "Transaction type 100 with offset to 199900 (asset acquisition clearing).",
      scrap: "Transaction type 200: APC and accumulated depreciation are removed; the book value is posted as loss (821000).",
      sale: "Transaction type 210: customer is debited, gain (820000) or loss (821000) = revenue - book value." };
    app.append(panel(title, grid(...fields)), h("div.note", null, notes[mode]));
    toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
      const body = mode === "vendor" || mode === "clearing" ? { anln1: val(a), budat: b.value, amount: val(amount), lifnr: mode === "vendor" ? up(partner) : "", mwskz: tax.value, xblnr: val(x) }
        : { anln1: val(a), budat: b.value, revenue: mode === "sale" ? val(amount) : "", kunnr: mode === "sale" ? up(partner) : "", mwskz: tax.value };
      const r = await run(() => api(mode === "vendor" || mode === "clearing" ? "/api/fi/acquire" : "/api/fi/retire", body));
      if (r) { await meta(true); msgLink("S", r.message, "Asset explorer", "AW01N", { id: val(a) }); } } }]);
  }});
}
assetPost("F-90", "Asset Acquisition from Vendor", "vendor");
assetPost("ABZON", "Asset Acquisition with Automatic Offsetting Entry", "clearing");
assetPost("ABAVN", "Asset Retirement by Scrapping", "scrap");
assetPost("F-92", "Asset Retirement with Customer (Sale)", "sale");

register("AFAB", { title: "Execute Depreciation Run", async render(app) {
  await meta();
  const y = inp({ value: FI.sample.gjahr, w: "s" }), p = inp({ value: FI.sample.perio, w: "s" }), test = h("input", { type: "checkbox", checked: true }), o = out();
  app.append(panel("Parameters - company code 1000, depreciation area 01", grid(field("Fiscal year", y), field("Posting period", p),
    field("Processing", h("label.checkbox", null, test, "Test run")))), h("div.note", null, "Planned minus already posted depreciation is posted (repeat run safe). Expense 470000 goes to the asset's cost center in CO."), o);
  execBar(async () => {
    const r = await run(() => api("/api/fi/afab", { gjahr: val(y), perio: val(p), test: test.checked })); if (!r) return; o.innerHTML = "";
    o.append(alv({ title: "Depreciation per asset", rows: r.lines, columns: [{ key: "anln1", label: "Asset", link: x => go("AW01N", { id: x.anln1 }) }, { key: "txt", label: "Description" },
      { key: "anlkl", label: "Class" }, { key: "kostl", label: "Cost ctr" }, { key: "planned", label: "Planned", type: "amt", sum: true }, { key: "posted", label: "Already posted", type: "amt", sum: true },
      { key: "amount", label: "To post", type: "amt", sum: true }] }));
    msg(test.checked ? "I" : "S", r.message);
  });
}});

register("S_ALR_87011990", { title: "Asset History Sheet", async render(app) {
  await meta();
  const y = inp({ value: FI.sample.gjahr, w: "s" }), o = out();
  app.append(panel("Fiscal year", grid(field("Fiscal year", y))), o);
  const exec = async () => {
    const rows = await run(() => api(`/api/fi/assethistory?gjahr=${val(y)}`)); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "Asset history sheet by asset class", rows, columns: [{ key: "anlkl", label: "Class" }, { key: "txt", label: "Description" }, { key: "count", label: "Assets", type: "int" },
      { key: "apc_start", label: "APC start", type: "amt", sum: true }, { key: "acquisitions", label: "Acquisitions", type: "amt", sum: true },
      { key: "retirements", label: "Retirements", type: "amt", sum: true, signed: true }, { key: "apc_end", label: "APC end", type: "amt", sum: true },
      { key: "dep_start", label: "Acc. dep. start", type: "amt", sum: true, signed: true }, { key: "dep_year", label: "Depreciation", type: "amt", sum: true, signed: true },
      { key: "dep_retired", label: "Dep. retired", type: "amt", sum: true }, { key: "dep_end", label: "Acc. dep. end", type: "amt", sum: true, signed: true },
      { key: "nbv_start", label: "Book value start", type: "amt", sum: true }, { key: "nbv_end", label: "Book value end", type: "amt", sum: true }] }));
  };
  execBar(exec); exec();
}});

// ================================================================== bank / cash / tax
register("FF67", { title: "Manual Bank Statement", async render(app) {
  await meta(true);
  const bank = FI.banks[0];
  const az = inp({ value: "", w: "s" }), d = inp({ type: "date", value: today(), w: "m" }), op = inp({ value: bank.balance.toFixed(2), w: "m" }), cl = inp({ w: "m" });
  const lines = [{ type: "D", amount: "", kunnr: "", ref: "", text: "" }];
  const calc = () => { const s = lines.reduce((a, l) => a + (parseFloat(l.amount) || 0), 0); cl.value = (parseFloat(op.value) + s).toFixed(2); };
  const g = itemGrid([{ key: "type", label: "Transaction", options: [["D", "Incoming customer payment"], ["CHG", "Bank charges"]] }, { key: "amount", label: "Amount (+ in / - out)" },
    { key: "kunnr", label: "Customer", list: "dl-kunnr", upper: true }, { key: "ref", label: "Reference (doc. / billing no.)" }, { key: "text", label: "Text", w: "l" }], lines, calc);
  const prev = out();
  app.append(panel(`House bank ${bank.hbkid} · ${bank.text} · G/L ${bank.hkont}`, grid(field("Statement number", az, { req: true }), field("Statement date", d),
    field("Opening balance", op), field("Closing balance", cl))), h("div.panel", null, h("div.panel-head", null, "Statement items", h("span.spacer"),
    h("button.btn.ghost", { type: "button", on: { click: () => { lines.push({ type: "D", amount: "" }); g.redraw(); } } }, "+ Item")), g), prev);
  calc();
  const list = async () => { const r = await run(() => api("/api/fi/ff67")); if (!r) return; prev.innerHTML = "";
    prev.append(alv({ title: "Posted statements", rows: r, columns: [{ key: "aznum", label: "Statement" }, { key: "azdat", label: "Date", type: "date" },
      { key: "ssbtr", label: "Opening", type: "amt" }, { key: "esbtr", label: "Closing", type: "amt" }, { key: "docs", label: "Documents" }] })); };
  list();
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/ff67", { hbkid: bank.hbkid, aznum: val(az), azdat: d.value, opening: op.value, closing: cl.value, lines: lines.filter(l => l.amount) }));
    if (r) { msg("S", r.message); list(); } } }]);
}});

register("FF7A", { title: "Cash Position & Liquidity Forecast (FF7A / FF7B)", async render(app) {
  await meta();
  const kd = inp({ type: "date", value: today(), w: "m" }), wk = inp({ value: "8", w: "s" }), o = out();
  app.append(panel("Parameters", grid(field("Key date", kd), field("Weeks", wk))), o);
  const exec = async () => {
    const r = await run(() => api(`/api/fi/cash?key_date=${kd.value}&weeks=${val(wk)}`)); if (!r) return; o.innerHTML = "";
    o.append(h("div.kpis", null, kpi("Bank balance", fmtShort(r.bank)), kpi("Overdue receivables", fmtShort(r.overdue_in), "not in forecast weeks", "S_ALR_87012168", "crit"),
      kpi("Overdue payables", fmtShort(-r.overdue_out), "", "S_ALR_87012078"), kpi("Balance after forecast", fmtShort(r.weeks.length ? r.weeks[r.weeks.length - 1].balance : r.bank))),
    alv({ title: "Liquidity forecast per week (customer receipts / vendor payments by due date)", rows: r.weeks, columns: [{ key: "week", label: "Week", type: "int" },
      { key: "start", label: "From", type: "date" }, { key: "end", label: "To", type: "date" }, { key: "inflow", label: "Inflows (AR)", type: "amt", sum: true },
      { key: "outflow", label: "Outflows (AP)", type: "amt", sum: true, signed: true }, { key: "balance", label: "Projected balance", type: "amt" }] }));
  };
  execBar(exec); exec();
}});
register("FF7B", { title: "Liquidity Forecast", render: () => go("FF7A") });

register("S_ALR_87012357", { title: "Advance Return for Tax on Sales/Purchases", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: sampleStart(), w: "m" }), d2 = inp({ type: "date", value: sampleEnd(), w: "m" }), o = out();
  app.append(panel("Selection", grid(field("Posting date from", d1), field("Posting date to", d2))), o);
  const exec = async () => {
    const r = await run(() => api(`/api/fi/vat?d1=${d1.value}&d2=${d2.value}`)); if (!r) return; o.innerHTML = "";
    o.append(alv({ title: "Tax per tax code", rows: r.rows, columns: [{ key: "mwskz", label: "Tax code" }, { key: "text", label: "Description" },
      { key: "typ", label: "Type", render: x => h("span", null, x.typ === "O" ? "Output" : "Input") }, { key: "pct", label: "Rate %", type: "amt" },
      { key: "base", label: "Tax base", type: "amt", sum: true }, { key: "tax", label: "Tax amount", type: "amt", sum: true }] }),
    panel("VAT return", h("table.grid.pnl", null, h("tbody", null, h("tr", null, h("td", null, "Output VAT"), h("td.num", null, fmtAmt(r.output))),
      h("tr", null, h("td", null, "- Input VAT"), h("td.num", null, fmtAmt(r.input))), h("tr.sub", null, h("td", null, "= VAT payable to the tax authority"), h("td.num", null, fmtAmt(r.payable)))))));
  };
  execBar(exec, [{ label: "Post tax payable (FB41)", ghost: true, onClick: () => go("FB41") }]); exec();
}});

register("FB41", { title: "Post Tax Payable", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: sampleStart(), w: "m" }), d2 = inp({ type: "date", value: sampleEnd(), w: "m" }), b = inp({ type: "date", value: sampleEnd(), w: "m" });
  app.append(panel("VAT settlement", grid(field("Tax period from", d1), field("Tax period to", d2), field("Posting date", b))),
    h("div.note", null, "Moves the output VAT (175000) and input VAT (154000) of the period to the tax payable account 179000."));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/fb41", { d1: d1.value, d2: d2.value, budat: b.value })); if (r) msgLink("S", r.message, "Display", "FB03", { id: r.belnr, year: b.value.slice(0, 4) }); } }]);
}});
})();
