/* MM Core - Procurement (MM-PUR) screens */
"use strict";
(() => {
const { h, $, api, msg, run, confirmBox, field, inp, sel, val, up, alv, register, go,
  toolbar, fmtQty, fmtAmt, fmtDate, fmtShort, today, enc, S } = App;

const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const out = () => h("div");
const gap = () => h("div", { style: { height: "12px" } });
let PM = null;
async function meta(force) {
  if (!PM || force) {
    PM = await api("/api/pur/meta");
    const fi = await api("/api/fi/meta");
    PM.vendors = fi.vendors;
    App.datalist("dl-lifnr", fi.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name}`]));
    App.datalist("dl-hkont", fi.gl.map(a => [a.hkont, `${a.hkont} ${a.txt}`]));
    const co = await api("/api/co/meta");
    App.datalist("dl-kostl", co.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
    App.datalist("dl-aufnr", co.orders.map(o => [o.aufnr, `${o.aufnr} ${o.ktext}`]));
    App.datalist("dl-konnr", PM.contracts.map(c => [c.konnr, `${c.konnr} ${c.bsart} vendor ${c.lifnr}`]));
  }
  return PM;
}
const vName = k => ((PM && PM.vendors || []).find(v => v.lifnr === k) || {}).name || "";
const grpSel = v => sel(Object.entries(PM.groups).map(([k, t]) => [k, `${k} ${t}`]), v || "001", { w: "l" });
function msgLink(type, text, label, tcode, params) {
  msg(type, text);
  const a = h("a", { href: "#", style: { marginLeft: "10px" } }, label);
  a.addEventListener("click", e => { e.preventDefault(); go(tcode, params); });
  $("#status-msg").append(a);
}
function execBar(fn, extra) { toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }, ...(extra || [])]); }
const relBadge = r => r === "Blocked" || r === "B" ? badge("Blocked", "B") : r === "Released" || r === "R" ? badge("Released", "U") : badge("No release", "");
const poLink = r => go("ME23N", { id: r.ebeln });
function kpi(l, v, s, goTo, cls) {
  return h("div.kpi", { dataset: goTo ? { go: goTo } : null, on: goTo ? { click: () => go(goTo) } : null },
    h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
}
const card = (t, sub, ...b) => h("div.card", null, h("h3", null, t), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...b));
function bars(items, labelFn, valFn) {
  const max = Math.max(...items.map(i => Math.abs(valFn(i))), 1);
  return h("div", null, items.map(i => h("div.hbar", null, h("span.lbl", { title: labelFn(i) }, labelFn(i)),
    h("span.track", null, h("span.fill", { style: { width: Math.abs(valFn(i)) / max * 100 + "%", display: "block" } })), h("span.num", null, fmtShort(valFn(i))))));
}
function itemGrid(cols, lines, onChange) {
  const box = h("div.items-wrap");
  const draw = () => {
    box.innerHTML = "";
    const tb = h("tbody");
    lines.forEach((l, i) => tb.append(h("tr", null, h("td.ln", null, String((i + 1) * 10)), cols.map(c => {
      const el = c.options ? sel(c.options, l[c.key], { onchange: e => { l[c.key] = e.target.value; onChange && onChange(); } })
        : inp({ value: l[c.key] ?? "", list: c.list, upper: c.upper, type: c.type, w: c.w || "m", oninput: e => { l[c.key] = e.target.value; onChange && onChange(); } });
      return h("td", null, el);
    }), h("td", null, h("button.alv-tb-btn", { type: "button", on: { click: () => { lines.splice(i, 1); draw(); } } }, "✕")))));
    box.append(h("table.grid.items", null, h("thead", null, h("tr", null, h("th", null, "Item"), cols.map(c => h("th", null, c.label)), h("th"))), tb));
  };
  draw(); box.redraw = draw; return box;
}

// ================================================================== cockpit
register("ZPUR_COCKPIT", { title: "Procurement Cockpit - Spend, Commitments & Supplier Performance", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: PM.sample.d1, w: "m" }), d2 = inp({ type: "date", value: PM.sample.d2, w: "m" }), body = out();
  app.append(panel("Period (PO date)", grid(field("From", d1), field("To", d2))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/pur/cockpit?d1=${d1.value}&d2=${d2.value}`)); if (!d) return;
    body.innerHTML = ""; const k = d.kpi;
    body.append(h("div.kpis", null,
      kpi("Purchasing volume", h("span", null, fmtShort(k.spend), " ", h("small", null, "EGP")), `${k.po_count} POs · ${k.vendors} vendors`, "ME2N"),
      kpi("Open commitment", fmtShort(k.open_commitment), "still to be delivered", "ME2M"),
      kpi("GR not invoiced", fmtShort(k.to_invoice), "GR/IR open", "ME2N"),
      kpi("Overdue deliveries", String(k.overdue_items), `value ${fmtShort(k.overdue_value)}`, "ME2N", k.overdue_items ? "neg" : "pos"),
      kpi("On-time delivery", (k.ontime ?? "-") + " %", "goods receipts in period", "ME65", k.ontime < 80 ? "crit" : "pos"),
      kpi("Contract coverage", k.contract_share + " %", "of spend via contracts", "ME3M"),
      kpi("Savings (RFQ)", fmtShort(k.savings), "vs. average quotation", "ME49", "pos"),
      kpi("Invoice price variance", fmtShort(k.ipv), "invoice above PO price", "MIRO", k.ipv > 0 ? "crit" : ""),
      kpi("Waiting for release", `${k.pr_waiting} PR · ${k.po_blocked} PO`, "approval backlog", "ME28", (k.pr_waiting + k.po_blocked) ? "crit" : ""),
      kpi("Cycle time PR → PO", k.cycle_days === null ? "-" : k.cycle_days + " days", `${k.pr_open} PR items open`, "ME5A")));
    body.append(h("div.cards", null,
      card("Spend by vendor (ABC analysis)", "A = top 80 % of volume", alv({ compact: true, rows: d.abc, columns: [
        { key: "cls", label: "ABC", render: r => badge(r.cls, r.cls === "A" ? "S" : r.cls === "B" ? "Q" : "") }, { key: "lifnr", label: "Vendor", link: r => go("ME2L", { lifnr: r.lifnr }) },
        { key: "name", label: "Name" }, { key: "spend", label: "Volume", type: "amt", sum: true }, { key: "pct", label: "%", type: "amt" }, { key: "cum", label: "Cum. %", type: "amt" }] })),
      card("Spend by material group", null, bars(d.by_group, x => x.group, x => x.spend)),
      card("Supplier evaluation (ME65)", "Score 1-100 · price 30 % · on-time 30 % · quantity 20 % · quality 20 %", alv({ compact: true, rows: d.evaluation, columns: [
        { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "total", label: "Score", type: "int", cls: r => r.total < 70 ? "neg" : r.total < 85 ? "crit" : "pos" },
        { key: "grade", label: "Grade" }, { key: "ontime_pct", label: "On-time %", type: "amt" }, { key: "return_pct", label: "Returns %", type: "amt" }] })),
      card("Overdue deliveries - expediting list", "Delivery date passed, quantity still open", d.overdue.length ? alv({ compact: true, rows: d.overdue, columns: [
        { key: "ebeln", label: "PO", link: poLink }, { key: "ebelp", label: "Item", type: "int" }, { key: "name", label: "Vendor" }, { key: "matnr", label: "Material" },
        { key: "eindt", label: "Due", type: "date" }, { key: "days", label: "Days late", type: "int", cls: () => "neg" }, { key: "open", label: "Open qty", type: "qty" }] }) : h("p.pos", null, "✔ No overdue deliveries")),
      card("Purchasing volume per month", null, bars(d.monthly, x => x.month, x => x.spend))));
    msg("S", `Procurement cockpit - volume ${fmtAmt(k.spend)} EGP`);
  };
  execBar(exec, [{ label: "Process map", ghost: true, onClick: () => go("ZPUR_PROCESS") }]); exec();
}});

register("ZPUR_PROCESS", { title: "Procurement Process Map (Procure-to-Pay)", async render(app) {
  await meta();
  const body = out(); app.append(h("div.note", { style: { marginBottom: "10px" } },
    `Purchasing organization ${PM.ekorg} ${PM.ekorg_text} · sample month ${fmtDate(PM.sample.d1)} - ${fmtDate(PM.sample.d2)}: requirement → approval → sourcing → order → receipt → invoice → payment, posted in MM, FI and CO.`), body);
  const s = await run(() => api("/api/pur/process")); if (!s) return;
  const st = (n, t) => n ? badge(`✔ ${t || n}`, "U") : badge("Open", "Q");
  const phases = [
    ["1. Master data & sources", [["ME11", "Info records: price, discount, freight, delivery time", "ME1M", s.info, `${s.info} records`],
      ["ME01", "Source list (allowed / fixed vendors)", "ME01", s.sl], ["MEQ1", "Quota arrangement 60 / 40", "MEQ1", s.quota],
      ["ME31K", "Contracts (outline agreements)", "ME3M", s.contracts], ["MD04", "MRP data: reorder point, max stock, lot size", "MD04", 1]]],
    ["2. Requirement & approval", [["MD01", "MRP run → requisitions", "MD01", s.mrp, `${s.mrp} run`],
      ["ME51N", "Manual requisitions (stock, service with cost center)", "ME5A", s.pr, `${s.pr} PRs`],
      ["ME54N/ME55", "Release requisitions (R1 ≥ 25,000)", "ME55", s.pr_rel, `${s.pr_rel} releases`]]],
    ["3. Sourcing", [["ME41", "Request for quotation to 3 vendors", "ME41", s.rfq], ["ME47", "Enter quotations", "ME47", s.quot, `${s.quot} quotes`],
      ["ME49", "Price comparison & award", "ME49", s.rfq], ["ME57/ME59N", "Assign source & create POs", "ME57", s.po]]],
    ["4. Order & approval", [["ME21N", "Purchase orders (conditions, account assignment, contract call-off)", "ME2N", s.po, `${s.po} POs`],
      ["ME29N/ME28", "PO release R1 ≥ 100,000 · R2 ≥ 500,000", "ME28", s.po_rel, `${s.po_rel} releases`],
      ["ME9F", "PO output", "ME9F", 1]]],
    ["5. Receipt, invoice, payment", [["MIGO 101", "Goods receipts (stock / cost center)", "ME2N", s.gr, `${s.gr} receipts`],
      ["MIGO 122", "Return to vendor", "MB51", s.ret], ["MIRO", "Invoice verification (3-way match)", "MIRO", s.miro, `${s.miro} invoices`],
      ["F110", "Payment run", "F110", s.pay, `${s.pay} payments`], ["F.13", "GR/IR clearing", "F.13", 1, `${s.grir_open} PO items open`]]],
    ["6. Analysis", [["ME2N/ME2L/ME2M", "Order lists: to deliver, to invoice", "ME2N", 1], ["ME65", "Vendor evaluation", "ME65", 1],
      ["ZPUR_COCKPIT", "Spend, savings, KPIs", "ZPUR_COCKPIT", 1]]]];
  for (const [t, steps] of phases)
    body.append(h("div.panel", null, h("div.panel-head", null, t), h("div.process", null, steps.map(([c, txt, tc, ok, lbl]) =>
      h("div.step", { on: { click: () => go(tc) } }, h("div.step-code", null, c), h("div.step-text", null, txt), st(ok, lbl))))));
}});

// ================================================================== config displays
const cfg = (code, title, rowsFn, cols, note) => register(code, { title, async render(app) {
  await meta(); app.append(alv({ title, rows: rowsFn(), columns: cols }), note ? h("div.note", { style: { marginTop: "10px" } }, note) : null); } });
cfg("OX08", "Purchasing Organization", () => [{ ekorg: PM.ekorg, text: PM.ekorg_text, bukrs: "1000", werks: "1000, 1100" }],
  [{ key: "ekorg", label: "Purch. org." }, { key: "text", label: "Description" }, { key: "bukrs", label: "Company code" }, { key: "werks", label: "Plants" }]);
cfg("OME4", "Purchasing Groups", () => Object.entries(PM.groups).map(([k, t]) => ({ k, t })), [{ key: "k", label: "Group" }, { key: "t", label: "Description" }]);
cfg("OME9", "Account Assignment Categories", () => Object.entries(PM.acct).map(([k, t]) => ({ k: k || "(blank)", t })), [{ key: "k", label: "Cat." }, { key: "t", label: "Meaning" }]);
cfg("M/06", "Condition Types (pricing procedure RM0000)", () => Object.entries(PM.conditions).map(([k, t]) => ({ k, t })), [{ key: "k", label: "Cond." }, { key: "t", label: "Description" }],
  "Net price = PB00 × (1 - RA01 %). FRB1 freight is a planned delivery cost: added to the stock value at goods receipt and posted to freight clearing 193000.");
cfg("OMGS", "Release Strategies", () => [...PM.pr_release.map(r => ({ ...r, obj: "Purchase requisition" })), ...PM.po_release.map(r => ({ ...r, obj: "Purchase order" }))],
  [{ key: "obj", label: "Object" }, { key: "code", label: "Code" }, { key: "text", label: "Approver" }, { key: "limit", label: "From value", type: "amt" }],
  "Codes must be released in sequence. Goods receipt and PO output are blocked until the PO is fully released (message ME 390). A value increase resets the release.");

// ================================================================== requisitions
register("ME51N", { title: "Create Purchase Requisition", async render(app) {
  await meta();
  const lines = [{ matnr: "", txz01: "", menge: "", meins: "", lgort: "", lfdat: "", knttp: "", kostl: "", sakto: "", preis: "", ekgrp: "", flief: "" }];
  const badat = inp({ type: "date", value: today(), w: "m" }), afnam = inp({ value: S.user, w: "m" });
  const g = itemGrid([{ key: "matnr", label: "Material", list: "dl-mat", upper: true }, { key: "txz01", label: "Short text (no material)", w: "l" },
    { key: "menge", label: "Quantity", w: "s" }, { key: "meins", label: "Unit", w: "s", upper: true }, { key: "lgort", label: "SLoc", w: "s", upper: true },
    { key: "lfdat", label: "Delivery date", type: "date" }, { key: "knttp", label: "A", options: [["", "-"], ["K", "K"], ["F", "F"]] },
    { key: "kostl", label: "Cost ctr", list: "dl-kostl", upper: true, w: "s" }, { key: "sakto", label: "G/L", list: "dl-hkont", w: "s" },
    { key: "preis", label: "Valuation price", w: "s" }, { key: "flief", label: "Fixed vendor", list: "dl-lifnr", upper: true, w: "s" }], lines);
  app.append(panel("Header", grid(field("Requisition date", badat), field("Requisitioner", afnam))),
    h("div.panel", null, h("div.panel-head", null, "Items", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: () => { lines.push({}); g.redraw(); } } }, "+ Item")), g),
    h("div.note", null, "Stock items: material + quantity. Services / direct consumption: short text, account assignment K (cost center) or F (order), G/L account and price. Total ≥ 25,000 needs release R1."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/pr", { badat: badat.value, items: lines.filter(l => l.matnr || l.txz01).map(l => ({ ...l, afnam: val(afnam), lfdat: l.lfdat || undefined })) }));
    if (r) { msgLink("S", r.message, "Display", "ME53N", { id: r.banfn }); lines.splice(0, lines.length, {}); g.redraw(); } } }]);
}});

function prTable(rows, extraCols) {
  return alv({ title: "Purchase requisition items", rows, columns: [
    { key: "banfn", label: "Purch.req.", link: r => go("ME53N", { id: r.banfn }) }, { key: "bnfpo", label: "Item", type: "int" },
    { key: "estkz", label: "Created by", render: r => h("span", null, r.estkz === "B" ? "MRP" : "Manual") }, { key: "badat", label: "Req. date", type: "date" },
    { key: "matnr", label: "Material" }, { key: "txz01", label: "Short text" }, { key: "menge", label: "Qty", type: "qty" }, { key: "meins", label: "Un" },
    { key: "lfdat", label: "Deliv. date", type: "date" }, { key: "ekgrp", label: "PGr" }, { key: "knttp", label: "A" }, { key: "kostl", label: "Cost ctr" },
    { key: "value", label: "Value", type: "amt", sum: true }, { key: "afnam", label: "Requisitioner" },
    { key: "statu", label: "Status", render: r => badge(r.statu_text.split(" - ")[0], r.statu === "B" ? "B" : r.statu === "A" ? "U" : r.statu === "N" ? "S" : "") },
    { key: "frgst", label: "Strategy" }, { key: "frgzu", label: "Released" }, { key: "ebeln", label: "PO", link: r => r.ebeln && poLink(r) }, ...(extraCols || [])] });
}
register("ME5A", { title: "List Display of Purchase Requisitions", async render(app) {
  await meta();
  const st = sel([["", "(all)"], ...Object.entries(PM.pr_status)], "", { w: "l" }), o = out();
  app.append(panel("Selection", grid(field("Processing status", st))), o);
  const exec = async () => { const r = await run(() => api(`/api/pur/pr?statu=${st.value}`)); if (r) { o.innerHTML = ""; o.append(prTable(r)); } };
  execBar(exec); exec();
}});
register("ME53N", { title: "Display Purchase Requisition", async render(app, params) {
  await meta();
  const b = inp({ value: params.id || "", w: "m" }), o = out();
  app.append(panel("Purchase requisition", grid(field("Requisition", b))), o);
  const exec = async () => {
    const r = await run(() => api(`/api/pur/pr?banfn=${val(b)}`)); if (!r) return; o.innerHTML = "";
    o.append(prTable(r));
    const blocked = r.length && r[0].statu === "B";
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, blocked ? { label: "Release (ME54N)", primary: true, onClick: () => go("ME54N", { id: val(b) }) } : null]);
  };
  execBar(exec); if (params.id) exec();
}});
register("ME52N", { title: "Change Purchase Requisition", render: (a, p) => go("ME53N", p) });
register("ME54N", { title: "Release Purchase Requisition", async render(app, params) {
  await meta();
  const b = inp({ value: params.id || "", w: "m" }), code = sel(PM.pr_release.map(r => [r.code, `${r.code} ${r.text}`]), "R1", { w: "l" }), o = out();
  app.append(panel("Release", grid(field("Requisition", b), field("Release code", code))), o);
  const show = async () => { const r = await run(() => api(`/api/pur/pr?banfn=${val(b)}`)); if (r) { o.innerHTML = ""; o.append(prTable(r)); } };
  toolbar([{ label: "Show", key: "F8", onClick: show }, { label: "Release", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/pr/release", { banfn: val(b), code: code.value })); if (r) { msg("S", r.message); show(); } } },
  { label: "Reject", danger: true, onClick: async () => { const r = await run(() => api("/api/pur/pr/release", { banfn: val(b), code: code.value, reject: true })); if (r) { msg("S", r.message); show(); } } }]);
  if (params.id) show();
}});

function releaseList(code, title, typeFilter) {
  register(code, { title, async render(app) {
    await meta();
    const o = out(); app.append(o);
    const exec = async () => {
      const rows = (await run(() => api("/api/pur/release")) || []).filter(r => !typeFilter || r.objtyp === typeFilter);
      o.innerHTML = "";
      o.append(alv({ title: "Documents waiting for release", rows, emptyText: "Nothing to release ✔", columns: [
        { key: "objtyp", label: "Object" }, { key: "key", label: "Document", link: r => r.objtyp === "PO" ? go("ME23N", { id: r.key }) : go("ME53N", { id: r.key }) },
        { key: "partner", label: "Vendor / requisitioner" }, { key: "date", label: "Date", type: "date" }, { key: "value", label: "Value", type: "amt", sum: true },
        { key: "strategy", label: "Strategy" }, { key: "released", label: "Released" }, { key: "next", label: "Next code" },
        { key: "x", label: "", render: r => h("a", { href: "#", on: { click: async e => { e.preventDefault();
          const x = await run(() => api(r.objtyp === "PO" ? "/api/pur/po/release" : "/api/pur/pr/release", r.objtyp === "PO" ? { ebeln: r.key, code: r.next } : { banfn: r.key, code: r.next }));
          if (x) { msg("S", x.message); exec(); } } } }, `Release with ${r.next}`) }] }));
    };
    execBar(exec); exec();
  }});
}
releaseList("ME55", "Collective Release of Purchase Requisitions", "PR");
releaseList("ME28", "Release Purchase Orders (Collective)", "PO");

register("ME57", { title: "Assign and Process Purchase Requisitions", async render(app) {
  await meta();
  const o = out(), bedat = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Parameters", grid(field("PO date", bedat)), h("div.note", null,
    "Source determination: 1 contract → 2 fixed vendor (source list) → 3 quota arrangement → 4 cheapest info record. Requisitions waiting for release are not shown.")), o);
  const exec = async () => {
    const rows = await run(() => api("/api/pur/assign")); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "Released requisitions with proposed source", rows, emptyText: "No open released requisitions", columns: [
      { key: "banfn", label: "Purch.req." }, { key: "bnfpo", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "txz01", label: "Text" },
      { key: "menge", label: "Qty", type: "qty" }, { key: "lfdat", label: "Deliv.", type: "date" },
      { key: "v", label: "Proposed vendor", render: r => h("span", null, r.source ? `${r.source.lifnr} ${vName(r.source.lifnr)}` : "✖ no source") },
      { key: "how", label: "How determined", render: r => h("span", null, r.source ? r.source.how : "") },
      { key: "p", label: "Price", render: r => h("span", null, r.source && r.source.brutto !== null ? fmtAmt(r.source.brutto) : fmtAmt(r.preis)) }] }));
  };
  toolbar([{ label: "Assign", key: "F8", onClick: exec }, { label: "Create purchase orders (ME59N)", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/convert", { bedat: bedat.value })); if (!r) return;
    msg("S", r.message); o.innerHTML = "";
    o.append(alv({ title: "Created purchase orders", rows: r.pos, columns: [{ key: "ebeln", label: "PO", link: poLink }, { key: "lifnr", label: "Vendor" },
      { key: "items", label: "Items", type: "int" }, { key: "how", label: "Source" }] }));
    if (r.skipped.length) o.append(gap(), alv({ title: "Not converted", rows: r.skipped, columns: [{ key: "banfn", label: "PR" }, { key: "bnfpo", label: "Item" }, { key: "reason", label: "Reason" }] }));
  } }]);
  exec();
}});
register("ME59N", { title: "Automatic Creation of Purchase Orders", render: () => go("ME57") });

// ================================================================== PO
register("ME21N", { title: "Create Purchase Order", async render(app, params) {
  await meta();
  const f = { lifnr: inp({ value: params.lifnr || "", list: "dl-lifnr", upper: true, w: "m" }), bedat: inp({ type: "date", value: today(), w: "m" }), ekgrp: grpSel("001") };
  const info = h("span.hint");
  f.lifnr.addEventListener("change", () => { info.textContent = vName(up(f.lifnr)); });
  const lines = [{ matnr: "", menge: "", netpr: "", rabatt: "", frb: "", lgort: "", eindt: "", knttp: "", kostl: "", sakto: "", txz01: "", konnr: "" }];
  const sum = h("span.badge.S");
  const calc = () => { const v = lines.reduce((a, l) => a + (parseFloat(l.menge) || 0) * (parseFloat(l.netpr) || 0) * (1 - (parseFloat(l.rabatt) || 0) / 100) + (parseFloat(l.frb) || 0), 0);
    const need = PM.po_release.filter(r => v >= r.limit).map(r => r.code);
    sum.textContent = `Net value ${fmtAmt(v)}` + (need.length ? ` · release ${need.join("+")}` : " · no release"); };
  const g = itemGrid([{ key: "matnr", label: "Material", list: "dl-mat", upper: true }, { key: "txz01", label: "Short text (text item)", w: "l" },
    { key: "menge", label: "PO qty", w: "s" }, { key: "netpr", label: "PB00 price (blank = info rec.)", w: "s" }, { key: "rabatt", label: "RA01 %", w: "s" },
    { key: "frb", label: "FRB1 freight", w: "s" }, { key: "lgort", label: "SLoc", upper: true, w: "s" }, { key: "eindt", label: "Deliv. date", type: "date" },
    { key: "knttp", label: "A", options: [["", "-"], ["K", "K"], ["F", "F"]] }, { key: "kostl", label: "Cost ctr", list: "dl-kostl", upper: true, w: "s" },
    { key: "sakto", label: "G/L", list: "dl-hkont", w: "s" }, { key: "konnr", label: "Contract", list: "dl-konnr", w: "s" }], lines, calc);
  calc();
  app.append(panel("Header - document type NB standard PO, purchasing org. 1000", grid(field("Vendor", h("span.split", null, f.lifnr, info), { req: true }),
    field("Doc. date", f.bedat), field("Purch. group", f.ekgrp))),
    h("div.panel", null, h("div.panel-head", null, "Item overview", h("span.spacer"), sum, h("button.btn.ghost", { type: "button", on: { click: () => { lines.push({}); g.redraw(); } } }, "+ Item")), g),
    h("div.note", null, "Price defaults from contract or info record (ME11). Net price = PB00 - RA01 %. Freight FRB1 is a planned delivery cost. The info record is updated with the new price."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/po", { lifnr: up(f.lifnr), bedat: f.bedat.value, ekgrp: f.ekgrp.value,
      items: lines.filter(l => l.matnr || l.txz01).map(l => ({ ...l, matnr: (l.matnr || "").toUpperCase(), kostl: (l.kostl || "").toUpperCase(), ktpnr: l.konnr ? 10 : undefined })) }));
    if (r) { msgLink("S", r.message, "Display", "ME23N", { id: r.ebeln }); lines.splice(0, lines.length, {}); g.redraw(); calc(); } } }]);
}});

register("ME23N", { title: "Display Purchase Order", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", w: "m" }), o = out();
  app.append(panel("Purchase order", grid(field("Purchase order", e, { req: true }))), o);
  const exec = async () => {
    const d = await run(() => api("/api/pur/po/" + enc(val(e)))); if (!d) return; o.innerHTML = "";
    o.append(h("div.panel", null, h("div.obj-header", null, [["Standard PO", `${d.ebeln} (${d.bsart})`], ["Vendor", `${d.lifnr} ${d.name}`], ["Doc. date", fmtDate(d.bedat)],
      ["Purch. org / group", `${d.ekorg} / ${d.ekgrp} ${PM.groups[d.ekgrp] || ""}`], ["Terms", d.zterm || "-"], ["Net value", h("b", null, `${fmtAmt(d.total)} EGP`)],
      ["Release", h("span", null, relBadge(d.frgke || ""), d.frgst ? ` ${d.frgst} · done: ${d.frgzu || "-"}` : "")], ["RFQ", d.angnr || "-"], ["Output", d.printed ? "printed" : "not yet"]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
    o.append(alv({ title: "Items & conditions", rows: d.items, rowClass: r => r.loekz ? ".canceled" : "", columns: [
      { key: "ebelp", label: "Itm", type: "int" }, { key: "knttp", label: "A" }, { key: "matnr", label: "Material" }, { key: "txz01", label: "Short text" },
      { key: "menge", label: "PO qty", type: "qty" }, { key: "meins", label: "OUn" }, { key: "brtwr", label: "PB00 gross", type: "amt" }, { key: "rabatt", label: "RA01 %", type: "amt" },
      { key: "netpr", label: "Net price", type: "amt" }, { key: "peinh", label: "Per", type: "int" }, { key: "frb", label: "FRB1 freight", type: "amt" },
      { key: "total", label: "Net value", type: "amt", sum: true }, { key: "eindt", label: "Deliv. date", type: "date" }, { key: "wemng", label: "Delivered", type: "qty" },
      { key: "remng", label: "Invoiced", type: "qty" }, { key: "kostl", label: "Cost ctr" }, { key: "sakto", label: "G/L" },
      { key: "banfn", label: "PR", link: r => r.banfn && go("ME53N", { id: r.banfn }) }, { key: "konnr", label: "Contract" }, { key: "infnr", label: "Info rec." },
      { key: "elikz", label: "DCI", render: r => r.elikz ? badge("done", "U") : "" }] }));
    if (d.history.length) o.append(gap(), alv({ title: "PO history - goods receipts", rows: d.history, rowClass: r => r.canceled ? ".canceled" : "", columns: [
      { key: "bwart", label: "MvT" }, { key: "mblnr", label: "Mat. doc.", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) }, { key: "zeile", label: "Item" },
      { key: "budat", label: "Posting", type: "date" }, { key: "qty", label: "Quantity", type: "qty", signed: true }, { key: "dmbtr", label: "Amount", type: "amt" }] }));
    if (d.invoices.length) o.append(gap(), alv({ title: "PO history - invoices (MIRO)", rows: d.invoices, columns: [
      { key: "belnr", label: "Document", link: r => go("FB03", { id: r.belnr, year: r.gjahr }) }, { key: "budat", label: "Posting", type: "date" }, { key: "xblnr", label: "Reference" },
      { key: "ebelp", label: "Item" }, { key: "menge", label: "Quantity", type: "qty" }, { key: "dmbtr", label: "GR/IR amount", type: "amt" }] }));
    if (d.release_log.length) o.append(gap(), alv({ title: "Release history", rows: d.release_log, columns: [{ key: "frgco", label: "Code" }, { key: "action", label: "Action" }, { key: "usnam", label: "User" }, { key: "ts", label: "Time" }] }));
    const open = d.items.some(i => i.wemng < i.menge && !i.elikz && !i.loekz);
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, d.frgke === "B" ? { label: "Release (ME29N)", primary: true, onClick: () => go("ME29N", { id: d.ebeln }) } : null,
      d.frgke !== "B" && open ? { label: "Goods receipt (MIGO)", primary: true, onClick: () => go("MIGO", { po: d.ebeln }) } : null,
      { label: "Invoice (MIRO)", ghost: true, onClick: () => go("MIRO", { po: d.ebeln }) }, { label: "Change (ME22N)", ghost: true, onClick: () => go("ME22N", { id: d.ebeln }) },
      { label: "Print (ME9F)", ghost: true, onClick: () => go("ME9F", { id: d.ebeln }) }]);
  };
  execBar(exec); if (params.id) exec();
}});

register("ME22N", { title: "Change Purchase Order", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", w: "m" }), p = inp({ value: "10", w: "s" }), q = inp({ w: "s" }), dd = inp({ type: "date", w: "m" });
  const dci = sel([["", "(unchanged)"], ["1", "Set delivery completed"], ["0", "Remove delivery completed"]], "", { w: "l" }), del = h("input", { type: "checkbox" });
  app.append(panel("Change item", grid(field("Purchase order", e, { req: true }), field("Item", p), field("New quantity", q), field("New delivery date", dd),
    field("Delivery completed", dci), field("Delete item", h("label.checkbox", null, del, "Deletion indicator (only without GR)")))),
    h("div.note", null, "A value increase resets the release - the PO must be released again before goods receipt."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/po/change", { ebeln: val(e), ebelp: val(p), menge: val(q), eindt: dd.value, elikz: dci.value === "" ? null : dci.value === "1", loekz: del.checked }));
    if (r) msgLink("S", r.message, "Display", "ME23N", { id: val(e) }); } }]);
}});

register("ME29N", { title: "Release Purchase Order", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", w: "m" }), c = sel(PM.po_release.map(r => [r.code, `${r.code} ${r.text} (from ${fmtAmt(r.limit)})`]), "R1", { w: "l" });
  app.append(panel("Release", grid(field("Purchase order", e, { req: true }), field("Release code", c))));
  toolbar([{ label: "Display", onClick: () => go("ME23N", { id: val(e) }) }, { label: "Release", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/po/release", { ebeln: val(e), code: c.value })); if (r) msgLink("S", r.message, "Display", "ME23N", { id: val(e) }); } }]);
}});

register("ME9F", { title: "Message Output: Purchase Order", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", w: "m" }), o = out();
  app.append(panel("Purchase order", grid(field("Purchase order", e))), o);
  const exec = async () => {
    const d = await run(() => api("/api/pur/po/" + enc(val(e)))); if (!d) return; o.innerHTML = "";
    const tb = h("tbody", null, d.items.filter(i => !i.loekz).map(i => h("tr", null, h("td", null, String(i.ebelp)), h("td", null, i.matnr || ""), h("td", null, i.txz01),
      h("td.num", null, `${fmtQty(i.menge)} ${i.meins}`), h("td.num", null, fmtAmt(i.netpr)), h("td", null, fmtDate(i.eindt)), h("td.num", null, fmtAmt(i.total)))));
    tb.append(h("tr", null, h("td", { colspan: 6 }, h("b", null, "Total net")), h("td.num", null, h("b", null, fmtAmt(d.total)))),
      h("tr", null, h("td", { colspan: 6 }, "VAT 14 %"), h("td.num", null, fmtAmt(d.vat))), h("tr", null, h("td", { colspan: 6 }, h("b", null, "Total incl. VAT")), h("td.num", null, h("b", null, fmtAmt(d.total + d.vat)))));
    o.append(h("div.panel", null, h("div.panel-body", { style: { maxWidth: "800px", background: "#fff" } },
      h("div", { style: { display: "flex", justifyContent: "space-between" } }, h("div", null, h("b", null, "Factory Egypt S.A.E."), h("div.muted", null, "Purchasing organization 1000")),
        h("div", null, h("h2", { style: { margin: 0 } }, "PURCHASE ORDER"), h("div", null, `No. ${d.ebeln} · ${fmtDate(d.bedat)}`))),
      h("p", null, h("b", null, d.name), h("br"), `${d.city} · ${d.land} · vendor ${d.lifnr}`),
      h("table.grid", null, h("thead", null, h("tr", null, ["Item", "Material", "Description", "Quantity", "Price", "Delivery", "Value"].map(x => h("th", null, x)))), tb),
      h("p.muted", null, `Terms of payment ${d.zterm || ""} · delivery to plant 1000 Cairo · please quote PO number on delivery note and invoice.`),
      d.frgke === "B" ? h("p.neg", null, "✖ Not released - output is blocked") : null)));
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, { label: "Print / issue output", primary: true, onClick: async () => {
      const r = await run(() => api("/api/pur/po/print", { ebeln: val(e) })); if (r) { msg("S", r.message); window.print(); } } }]);
  };
  execBar(exec); if (params.id) exec();
}});

function poList(code, title, key) {
  register(code, { title, async render(app, params) {
    await meta();
    const f = { lifnr: inp({ value: params.lifnr || "", list: "dl-lifnr", upper: true, w: "m" }), matnr: inp({ value: params.matnr || "", list: "dl-mat", upper: true, w: "m" }),
      ekgrp: sel([["", "(all)"], ...Object.entries(PM.groups)], "", { w: "l" }), knttp: sel([["*", "(all)"], ["", "Stock"], ["K", "K Cost center"], ["F", "F Order"]], code === "ME2K" ? "K" : "*", { w: "l" }),
      open: h("input", { type: "checkbox", checked: code !== "ME2N" }), d1: inp({ type: "date", w: "m" }), d2: inp({ type: "date", w: "m" }) };
    const o = out();
    app.append(panel("Selection - scope of list ALLES / WE101 / RE101", grid(field("Vendor", f.lifnr), field("Material", f.matnr), field("Purch. group", f.ekgrp),
      field("Account assignment", f.knttp), field("Doc. date from", f.d1), field("to", f.d2), field("Selection", h("label.checkbox", null, f.open, "Only open (to deliver or to invoice)")))), o);
    const exec = async () => {
      const qs = `lifnr=${up(f.lifnr)}&matnr=${up(f.matnr)}&ekgrp=${f.ekgrp.value}&knttp=${f.knttp.value}&open=${f.open.checked ? 1 : 0}&d1=${f.d1.value}&d2=${f.d2.value}`;
      const rows = await run(() => api("/api/pur/polines?" + qs)); if (!rows) return;
      rows.sort((a, b) => String(a[key]).localeCompare(String(b[key])));
      o.innerHTML = "";
      o.append(alv({ title: `${title} - ${rows.length} items`, exportName: code, rows, rowClass: r => r.overdue ? "" : "", columns: [
        { key: "ebeln", label: "Purch.Doc.", link: poLink }, { key: "ebelp", label: "Item", type: "int" }, { key: "bedat", label: "Doc. date", type: "date" },
        { key: "lifnr", label: "Vendor" }, { key: "vname", label: "Name" }, { key: "ekgrp", label: "PGr" }, { key: "knttp", label: "A" },
        { key: "matnr", label: "Material" }, { key: "text", label: "Short text" }, { key: "menge", label: "PO qty", type: "qty" }, { key: "meins", label: "OUn" },
        { key: "netpr", label: "Net price", type: "amt" }, { key: "net_value", label: "Net value", type: "amt", sum: true }, { key: "eindt", label: "Deliv. date", type: "date", cls: r => r.overdue ? "neg" : "" },
        { key: "to_deliver_qty", label: "Still to deliver", type: "qty" }, { key: "to_deliver_val", label: "To deliver (val.)", type: "amt", sum: true },
        { key: "to_invoice_qty", label: "Still to invoice", type: "qty" }, { key: "to_invoice_val", label: "To invoice (val.)", type: "amt", sum: true },
        { key: "release", label: "Release", render: r => relBadge(r.release) }, { key: "kostl", label: "Cost ctr" }, { key: "konnr", label: "Contract" }] }));
      msg("S", `${rows.length} items`);
    };
    execBar(exec); exec();
  }});
}
poList("ME2N", "Purchasing Documents per Document Number", "ebeln");
poList("ME2L", "Purchasing Documents per Vendor", "lifnr");
poList("ME2M", "Purchasing Documents per Material", "matnr");
poList("ME2K", "Purchasing Documents per Account Assignment", "kostl");
register("ME80FN", { title: "General Analyses for Purchasing Documents", render: () => go("ME2N") });

// ================================================================== info records, source list, quota
register("ME11", { title: "Create / Change Purchasing Info Record (ME11 / ME12)", async render(app, params) {
  await meta();
  const f = { lifnr: inp({ value: params.lifnr || "", list: "dl-lifnr", upper: true, w: "m" }), matnr: inp({ value: params.matnr || "", list: "dl-mat", upper: true, w: "m" }),
    brutto: inp({ w: "m" }), peinh: inp({ value: "1", w: "s" }), rabatt: inp({ value: "0", w: "s" }), frb: inp({ value: "0", w: "m" }),
    aplfz: inp({ value: "7", w: "s" }), norbm: inp({ value: "0", w: "s" }), idnlf: inp({ w: "m" }) };
  app.append(panel("General data + purchasing org. 1000 data + conditions", grid(field("Vendor", f.lifnr, { req: true }), field("Material", f.matnr, { req: true }),
    field("Vendor material no.", f.idnlf), field("PB00 gross price", f.brutto, { req: true }), field("Price unit", f.peinh), field("RA01 discount %", f.rabatt),
    field("FRB1 freight per item", f.frb), field("Planned deliv. time (days)", f.aplfz), field("Standard quantity", f.norbm))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/info", { lifnr: up(f.lifnr), matnr: up(f.matnr), brutto: val(f.brutto), peinh: val(f.peinh), rabatt: val(f.rabatt),
      frb: val(f.frb), aplfz: val(f.aplfz), norbm: val(f.norbm), idnlf: val(f.idnlf) })); if (r) msgLink("S", r.message, "List", "ME1M", { matnr: up(f.matnr) }); } }]);
}});
register("ME12", { title: "Change Info Record", render: (a, p) => go("ME11", p) });
register("ME1M", { title: "Info Records per Material (ME1M / ME1L / ME13)", async render(app, params) {
  await meta();
  const m = inp({ value: params.matnr || "", list: "dl-mat", upper: true, w: "m" }), l = inp({ value: params.lifnr || "", list: "dl-lifnr", upper: true, w: "m" }), o = out();
  app.append(panel("Selection", grid(field("Material", m), field("Vendor", l))), o);
  const exec = async () => { const rows = await run(() => api(`/api/pur/info?matnr=${up(m)}&lifnr=${up(l)}`)); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "Purchasing info records", rows, onDbl: r => go("ME11", { lifnr: r.lifnr, matnr: r.matnr }), columns: [
      { key: "infnr", label: "Info rec." }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
      { key: "brutto", label: "PB00 gross", type: "amt" }, { key: "rabatt", label: "RA01 %", type: "amt" }, { key: "netpr", label: "Net price", type: "amt" },
      { key: "peinh", label: "Per", type: "int" }, { key: "meins", label: "Un" }, { key: "frb", label: "Freight", type: "amt" }, { key: "aplfz", label: "Pl. deliv. days", type: "int" },
      { key: "ebeln", label: "Last PO", link: r => r.ebeln && poLink(r) }, { key: "datab", label: "Valid from", type: "date" }] })); };
  execBar(exec); exec();
}});
register("ME1L", { title: "Info Records per Vendor", render: (a, p) => go("ME1M", p) });
register("ME13", { title: "Display Info Record", render: (a, p) => go("ME1M", p) });

register("ME01", { title: "Maintain Source List / Quota Arrangement (ME01 / MEQ1)", async render(app, params) {
  await meta();
  const m = inp({ value: params.matnr || "RM-1001", list: "dl-mat", upper: true, w: "m" }), o = out();
  app.append(panel("Material - plant 1000", grid(field("Material", m))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/pur/sourcelist?matnr=${up(m)}`)); if (!d) return; o.innerHTML = "";
    const src = d.sources.map(s => ({ lifnr: s.lifnr, vdatu: s.vdatu, bdatu: s.bdatu, flifn: s.flifn ? "X" : "", notkz: s.notkz ? "X" : "", konnr: s.konnr || "" }));
    const quota = d.quota.map(q => ({ lifnr: q.lifnr, quote: String(q.quote) }));
    const g1 = itemGrid([{ key: "lifnr", label: "Vendor", list: "dl-lifnr", upper: true }, { key: "vdatu", label: "Valid from", type: "date" }, { key: "bdatu", label: "Valid to", type: "date" },
      { key: "flifn", label: "Fixed", options: [["", "-"], ["X", "X"]] }, { key: "notkz", label: "Blocked", options: [["", "-"], ["X", "X"]] }, { key: "konnr", label: "Contract", list: "dl-konnr" }], src);
    const g2 = itemGrid([{ key: "lifnr", label: "Vendor", list: "dl-lifnr", upper: true }, { key: "quote", label: "Quota", w: "s" }], quota);
    o.append(h("div.panel", null, h("div.panel-head", null, "Source list (ME01)", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: () => { src.push({}); g1.redraw(); } } }, "+"),
      h("button.btn", { type: "button", on: { click: async () => { const r = await run(() => api("/api/pur/sourcelist", { matnr: up(m), entries: src.filter(s => s.lifnr).map(s => ({ ...s, flifn: s.flifn === "X", notkz: s.notkz === "X" })) })); if (r) msg("S", r.message); } } }, "Save")), g1),
    h("div.panel", null, h("div.panel-head", null, "Quota arrangement (MEQ1)", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: () => { quota.push({}); g2.redraw(); } } }, "+"),
      h("button.btn", { type: "button", on: { click: async () => { const r = await run(() => api("/api/pur/quota", { matnr: up(m), entries: quota.filter(q => q.lifnr) })); if (r) msg("S", r.message); } } }, "Save")), g2,
      alv({ compact: true, rows: d.quota, columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "quote", label: "Quota", type: "int" }, { key: "qubmg", label: "Allocated qty", type: "qty" }] })),
    h("div.note", null, "Quota rating = (allocated quantity + requirement) / quota - the vendor with the lowest rating gets the next requisition."));
    const qty = inp({ value: "1000", w: "s" }), res = h("span.hint");
    o.append(panel("Test source determination", h("span.split", null, "Quantity", qty, h("button.btn", { type: "button", on: { click: async () => {
      const s = await run(() => api(`/api/pur/source?matnr=${up(m)}&qty=${val(qty)}`)); res.textContent = s && s.lifnr ? `→ ${s.lifnr} ${vName(s.lifnr)} · ${s.how} · price ${fmtAmt(s.brutto)}` : "no source"; } } }, "Determine"), res)));
  };
  execBar(exec); exec();
}});
register("MEQ1", { title: "Maintain Quota Arrangement", render: (a, p) => go("ME01", p) });
register("ME03", { title: "Display Source List", render: (a, p) => go("ME01", p) });

// ================================================================== contracts
register("ME31K", { title: "Create Contract", async render(app) {
  await meta();
  const f = { lifnr: inp({ list: "dl-lifnr", upper: true, w: "m" }), bsart: sel(Object.entries(PM.contract_types).map(([k, t]) => [k, `${k} ${t}`]), "MK", { w: "l" }),
    kdatb: inp({ type: "date", value: today(), w: "m" }), kdate: inp({ type: "date", w: "m" }), ktwrt: inp({ w: "m" }) };
  const lines = [{ matnr: "", ktmng: "", netpr: "" }];
  const g = itemGrid([{ key: "matnr", label: "Material", list: "dl-mat", upper: true }, { key: "ktmng", label: "Target quantity", w: "s" }, { key: "netpr", label: "Net price", w: "s" }], lines);
  app.append(panel("Header", grid(field("Vendor", f.lifnr, { req: true }), field("Agreement type", f.bsart), field("Validity start", f.kdatb), field("Validity end", f.kdate, { req: true }),
    field("Target value (WK)", f.ktwrt))), h("div.panel", null, h("div.panel-head", null, "Items", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: () => { lines.push({}); g.redraw(); } } }, "+ Item")), g));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/contract", { lifnr: up(f.lifnr), bsart: f.bsart.value, kdatb: f.kdatb.value, kdate: f.kdate.value, ktwrt: val(f.ktwrt), items: lines.filter(l => l.matnr) }));
    if (r) { await meta(true); msgLink("S", r.message, "Contract list", "ME3M"); } } }]);
}});
register("ME3M", { title: "Outline Agreements per Material / Contract Status (ME3M / ME33K)", async render(app) {
  await meta();
  const rows = await run(() => api("/api/pur/contracts")); if (!rows) return;
  app.append(alv({ title: "Contracts - target vs. released (call-offs)", rows, columns: [
    { key: "konnr", label: "Contract" }, { key: "bsart", label: "Type" }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "kdatb", label: "Valid from", type: "date" },
    { key: "kdate", label: "Valid to", type: "date" }, { key: "ktpnr", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
    { key: "netpr", label: "Net price", type: "amt" }, { key: "ktmng", label: "Target qty", type: "qty" }, { key: "released_qty", label: "Released", type: "qty" },
    { key: "open_qty", label: "Open", type: "qty" }, { key: "released_val", label: "Released value", type: "amt", sum: true },
    { key: "pct", label: "Consumed", render: r => h("span", null, (r.pct ?? 0) + " %") },
    { key: "x", label: "", render: r => h("a", { href: `#/ME21N?lifnr=${r.lifnr}` }, "Call-off →") }] }));
}});
register("ME33K", { title: "Display Contract", render: () => go("ME3M") });

// ================================================================== RFQ
register("ME41", { title: "Create RFQ (Request for Quotation)", async render(app) {
  await meta();
  const f = { matnr: inp({ list: "dl-mat", upper: true, w: "m" }), menge: inp({ w: "s" }), lfdat: inp({ type: "date", w: "m" }), angdt: inp({ type: "date", w: "m" }), v: inp({ w: "l", ph: "100006,100008,100009" }) };
  const o = out();
  app.append(panel("RFQ - one per vendor under one collective number", grid(field("Material", f.matnr, { req: true }), field("Quantity", f.menge, { req: true }),
    field("Delivery date", f.lfdat), field("Quotation deadline", f.angdt), field("Vendors (comma list)", f.v, { req: true }))), o);
  const list = async () => { const rows = await run(() => api("/api/pur/rfqs")); if (!rows) return; o.innerHTML = "";
    o.append(alv({ title: "RFQs", rows, columns: [{ key: "submi", label: "Coll. no.", link: r => go("ME49", { id: r.submi }) }, { key: "anfnr", label: "RFQ" }, { key: "lifnr", label: "Vendor" },
      { key: "name", label: "Name" }, { key: "matnr", label: "Material" }, { key: "menge", label: "Qty", type: "qty" }, { key: "angdt", label: "Deadline", type: "date" },
      { key: "netpr", label: "Quoted price", type: "amt" }, { key: "statu", label: "Status", render: r => badge({ O: "Open", Q: "Quoted", A: "Accepted", R: "Rejected" }[r.statu], r.statu === "A" ? "U" : r.statu === "R" ? "B" : "Q") }] })); };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/rfq", { matnr: up(f.matnr), menge: val(f.menge), lfdat: f.lfdat.value, angdt: f.angdt.value, vendors: val(f.v).split(",").map(x => x.trim()).filter(Boolean) }));
    if (r) { msgLink("S", r.message, "Enter quotations", "ME47"); list(); } } }]);
  list();
}});
register("ME47", { title: "Maintain Quotation", async render(app) {
  await meta();
  const rows = await run(() => api("/api/pur/rfqs")); if (!rows) return;
  app.append(alv({ title: "Enter vendor quotations", rows, columns: [{ key: "submi", label: "Coll. no." }, { key: "anfnr", label: "RFQ" }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
    { key: "matnr", label: "Material" }, { key: "menge", label: "Qty", type: "qty" },
    { key: "q", label: "Price / delivery days", render: r => { if (r.statu === "A" || r.statu === "R") return h("span", null, `${fmtAmt(r.netpr)} · ${r.aplfz || "-"} d`);
      const p = inp({ value: r.netpr ?? "", w: "s" }), d = inp({ value: r.aplfz ?? "7", w: "s" });
      return h("span.split", null, p, d, h("button.btn", { type: "button", on: { click: async () => { const x = await run(() => api("/api/pur/quotation", { anfnr: r.anfnr, netpr: p.value, aplfz: d.value, quodt: today() })); if (x) msg("S", x.message); } } }, "Save")); } }] }));
}});
register("ME49", { title: "Price Comparison List", async render(app, params) {
  await meta();
  const s = inp({ value: params.id || "COLL-0001", w: "m" }), o = out();
  app.append(panel("Collective number", grid(field("Collective RFQ", s))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/pur/compare?submi=${val(s)}`)); if (!d) return; o.innerHTML = "";
    o.append(h("div.kpis", null, kpi("Best price", fmtAmt(d.best)), kpi("Average quotation", fmtAmt(d.average)), kpi("Saving vs. average", fmtAmt(d.saving_vs_avg), "on total quantity", null, "pos")),
      alv({ title: "Ranking", rows: d.items, columns: [{ key: "rank", label: "Rank", type: "int" }, { key: "anfnr", label: "RFQ" }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
        { key: "netpr", label: "Price", type: "amt" }, { key: "value", label: "Value", type: "amt" }, { key: "pct_of_best", label: "% of best", type: "amt" }, { key: "pct_of_avg", label: "% of avg.", type: "amt" },
        { key: "aplfz", label: "Deliv. days", type: "int" }, { key: "statu", label: "Status", render: r => badge({ O: "Open", Q: "Quoted", A: "Accepted", R: "Rejected" }[r.statu], r.statu === "A" ? "U" : "Q") },
        { key: "x", label: "", render: r => r.statu === "Q" ? h("a", { href: "#", on: { click: async e => { e.preventDefault();
          if (!await confirmBox("Award", `Accept quotation of ${r.lifnr} ${r.name} and create a PO?`, "Accept")) return;
          const x = await run(() => api("/api/pur/award", { anfnr: r.anfnr })); if (x) { msgLink("S", x.message, "Display PO", "ME23N", { id: x.ebeln }); exec(); } } } }, "Accept & order") : "" }] }));
  };
  execBar(exec); exec();
}});

// ================================================================== MRP
register("MD01", { title: "MRP Run (Reorder Point Planning)", async render(app) {
  await meta();
  const d = inp({ type: "date", value: today(), w: "m" }), o = out();
  app.append(panel("Plant 1000 - regenerative planning, create purchase requisitions", grid(field("Planning date", d)),
    h("div.note", null, "Available = unrestricted + quality stock + open POs + open requisitions. If available ≤ reorder point: requisition for maximum stock - available (lot size HB).")), o);
  const show = r => { o.innerHTML = ""; o.append(alv({ title: `Planning result ${r.rundt ? fmtDate(r.rundt) : ""}`, rows: r.lines, columns: [
    { key: "matnr", label: "Material", link: x => go("MD04", { id: x.matnr }) }, { key: "maktx", label: "Description" }, { key: "stock", label: "Stock", type: "qty" },
    { key: "open_po", label: "Open PO", type: "qty" }, { key: "open_pr", label: "Open PR", type: "qty" }, { key: "available", label: "Available", type: "qty" },
    { key: "minbe", label: "Reorder pt", type: "qty" }, { key: "mabst", label: "Max stock", type: "qty" }, { key: "qty", label: "Order qty", type: "qty" }, { key: "meins", label: "Un" },
    { key: "vendor", label: "Source" }, { key: "banfn", label: "Requisition", link: x => x.banfn && go("ME53N", { id: x.banfn }) }, { key: "status", label: "Result" }] })); };
  toolbar([{ label: "Last run", key: "F8", onClick: async () => { const r = await run(() => api("/api/pur/mrp/last")); if (r) show(r); } },
    { label: "Execute MRP run", primary: true, onClick: async () => { const r = await run(() => api("/api/pur/mrp", { rundt: d.value })); if (r) { msg("S", r.message); show({ ...r, rundt: d.value }); } } }]);
  const r = await run(() => api("/api/pur/mrp/last")); if (r) show(r);
}});
register("MD04", { title: "Stock/Requirements List", async render(app, params) {
  await meta();
  const m = inp({ value: params.id || "RM-1003", list: "dl-mat", upper: true, w: "m" }), o = out();
  app.append(panel("Material - plant 1000", grid(field("Material", m))), o);
  const exec = async () => {
    const d = await run(() => api(`/api/pur/md04?matnr=${up(m)}`)); if (!d) return; o.innerHTML = "";
    const mp = PM.mrp.find(x => x.matnr === d.matnr) || {};
    const f = { dismm: sel(Object.entries(PM.mrp_types).map(([k, t]) => [k, `${k} ${t}`]), d.dismm, { w: "l" }), minbe: inp({ value: d.minbe, w: "s" }), eisbe: inp({ value: d.eisbe, w: "s" }),
      mabst: inp({ value: d.mabst, w: "s" }), disls: sel(Object.entries(PM.lot_sizes).map(([k, t]) => [k, `${k} ${t}`]), d.disls, { w: "l" }), bstfe: inp({ value: (mp.bstfe || 0) / 1000, w: "s" }),
      plifz: inp({ value: d.plifz, w: "s" }), ekgrp: grpSel(mp.ekgrp) };
    o.append(h("div.panel", null, h("div.obj-header", null, [["Material", `${d.matnr} ${d.maktx}`], ["MRP type", d.dismm], ["Reorder point", `${fmtQty(d.minbe)} ${d.meins}`],
      ["Safety stock", fmtQty(d.eisbe)], ["Max stock", fmtQty(d.mabst)], ["Lot size", d.disls], ["Planned deliv. time", d.plifz + " days"]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, String(v)))))),
    alv({ title: "Stock / requirements", rows: d.lines, columns: [{ key: "date", label: "Date", type: "date" }, { key: "element", label: "MRP element" }, { key: "text", label: "Data" },
      { key: "receipt", label: "Receipt", type: "qty" }, { key: "req", label: "Requirement", type: "qty" }, { key: "available", label: "Available qty", type: "qty" }] }), gap(),
    panel("MRP 1 / MRP 2 view (MM02)", grid(field("MRP type", f.dismm), field("Reorder point", f.minbe), field("Safety stock", f.eisbe), field("Max stock level", f.mabst),
      field("Lot size", f.disls), field("Fixed lot size", f.bstfe), field("Planned deliv. time", f.plifz), field("Purchasing group", f.ekgrp)),
      h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
        const r = await run(() => api("/api/pur/mrpdata", { matnr: d.matnr, dismm: f.dismm.value, minbe: val(f.minbe), eisbe: val(f.eisbe), mabst: val(f.mabst), disls: f.disls.value,
          bstfe: val(f.bstfe), plifz: val(f.plifz), ekgrp: f.ekgrp.value })); if (r) { msg("S", r.message); await meta(true); } } } }, "Save MRP data"))));
  };
  execBar(exec); exec();
}});

// ================================================================== vendor evaluation
register("ME65", { title: "Evaluation Lists - Vendor Evaluation", async render(app) {
  await meta();
  const d1 = inp({ type: "date", w: "m" }), d2 = inp({ type: "date", w: "m" }), o = out();
  app.append(panel("Period (blank = all)", grid(field("PO date from", d1), field("to", d2)), h("div.note", null,
    "Main criteria (ME61): " + PM.eval.map(e => `${e.text} ${e.weight} %`).join(" · ") + ". Price vs. average price paid; on-time: -12 points per day late; quantity: deviation from PO quantity; quality: returns (122).")), o);
  const exec = async () => {
    const rows = await run(() => api(`/api/pur/eval?d1=${d1.value}&d2=${d2.value}`)); if (!rows) return; o.innerHTML = "";
    const cls = v => v === null ? "" : v < 70 ? "neg" : v < 85 ? "crit" : "pos";
    o.append(alv({ title: "Vendor ranking", rows, columns: [{ key: "lifnr", label: "Vendor", link: r => go("ME2L", { lifnr: r.lifnr }) }, { key: "name", label: "Name" },
      { key: "total", label: "Overall score", type: "int", cls: r => cls(r.total) }, { key: "grade", label: "Grade", render: r => badge(r.grade, r.grade === "A" ? "U" : r.grade === "B" ? "Q" : "B") },
      { key: "price", label: "Price", type: "int", cls: r => cls(r.price) }, { key: "ontime", label: "On-time", type: "int", cls: r => cls(r.ontime) },
      { key: "quantity", label: "Quantity", type: "int", cls: r => cls(r.quantity) }, { key: "quality", label: "Quality", type: "int", cls: r => cls(r.quality) },
      { key: "ontime_pct", label: "On-time %", type: "amt" }, { key: "avg_late", label: "Avg. days late", type: "amt" }, { key: "return_pct", label: "Returns %", type: "amt" },
      { key: "items", label: "PO items", type: "int" }, { key: "spend", label: "Volume", type: "amt", sum: true }] }));
  };
  execBar(exec); exec();
}});
register("ME61", { title: "Maintain Vendor Evaluation", render: () => go("ME65") });
register("ME6H", { title: "Vendor Evaluation Analysis", render: () => go("ME65") });
})();
