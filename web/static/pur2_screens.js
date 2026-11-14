/* NERP - Purchasing in depth: configuration (ZPUR_CONF), month-end (ZPUR_CLOSE), import file
   with letter of credit and landed cost (ZIMP01, ZIMP02, ZIMP03, ZLC01, ZIMP_COST, ZIMP_LAND),
   service entry sheets (ML81N), delivery reminders (ME91F) and price history (ZPUR_PRICE). */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, ask, field, inp, sel, val, up, alv, register, go, toolbar, fmtAmt, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const IMP = { OPEN: ["Open", "Q"], LC: ["LC opened", "Q"], LANDED: ["Costs landed", "U"], CLOSED: ["Closed", ""] };
const COSTS = [["CUSTOMS", "Customs duty"], ["FREIGHT", "Sea / air freight"], ["INSURANCE", "Marine insurance"],
  ["CLEARING", "Clearing agent & port charges"], ["BANK", "LC bank charges & commission"], ["INLAND", "Inland transport"], ["OTHER", "Other import costs"]];
const btn = (label, fn) => h("button.btn", { type: "button", on: { click: fn } }, label);

// ------------------------------------------------------------------ 1-1 ZPUR_CONF
register("ZPUR_CONF", { title: "Purchasing - Basic Configuration (display)", async render(app) {
  const c = await run(() => api("/api/pur/config")); if (!c) return;
  app.append(h("div.kpis", null, kpi("Purchasing organization", c.ekorg, c.ekorg_text),
    kpi("Three-quotations rule", `from ${fmtAmt(c.quotation_rule.limit)}`, `${c.quotation_rule.quotations} quotations needed`),
    kpi("Invoice price tolerance", `${c.tolerance.price_pct} %`, `or ${fmtAmt(c.tolerance.price_abs)} EGP`)),
    alv({ rows: c.groups, title: "Purchasing groups (OME4)", columns: [{ key: "ekgrp", label: "Group" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.doc_types, title: "Document types", columns: [{ key: "obj", label: "Object" }, { key: "typ", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.release, title: "Release strategies (approval limits)", columns: [{ key: "obj", label: "Object" }, { key: "code", label: "Code" }, { key: "text", label: "Approver" }, { key: "limit", label: "From value (EGP)", type: "amt" }] }),
    alv({ rows: c.acct_assign, title: "Account assignment categories (OME9)", columns: [{ key: "knttp", label: "Category" }, { key: "text", label: "Meaning" }] }),
    alv({ rows: c.conditions, title: "Condition types (M/06)", columns: [{ key: "kschl", label: "Condition" }, { key: "text", label: "Description" }, { key: "calc", label: "Calculation" }] }),
    alv({ rows: c.vendor_eval, title: "Vendor evaluation criteria (ME61)", columns: [{ key: "text", label: "Criterion" }, { key: "weight", label: "Weight %", type: "int" }] }),
    alv({ rows: c.import_costs, title: "Import cost types (ZIMP_COST)", columns: [{ key: "typ", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.accounts, title: "Accounts used by purchasing", columns: [{ key: "use", label: "Use" }, { key: "hkont", label: "G/L account" }] }));
} });

// ------------------------------------------------------------------ 1-5 ZPUR_CLOSE
register("ZPUR_CLOSE", { title: "Purchasing - Closing Management", async render(app, params) {
  const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
  const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not used", ""] };
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pur/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
      alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Month-end in Purchasing - in this order",
        columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode) },
          { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }),
      note("Finish purchasing first, then Accounting (ZFI_CLOSE) and Controlling (ZCO_CLOSE)."));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "FI closing (ZFI_CLOSE)", onClick: () => go("ZFI_CLOSE") }]);
  load();
} });

// ------------------------------------------------------------------ 5-x import file / LC
register("ZIMP01", { title: "Create Import File (letter of credit)", async render(app, params) {
  const f = { ebeln: inp({ value: params.ebeln || "", w: "m" }), lcno: inp({ w: "m" }), lcbank: inp({ w: "s", upper: true, ph: "e.g. NBE" }),
    lc_amount: inp({ w: "m", ph: "empty = PO value" }), margin_pct: inp({ w: "s", value: "25" }), port: inp({ w: "m", value: "Alexandria" }),
    eta: inp({ type: "date" }), bl_no: inp({ w: "m" }), text: inp({ w: "l" }) };
  app.append(panel("Import file", grid(field("Purchase order (foreign vendor)", f.ebeln, { req: true }), field("LC number", f.lcno), field("LC bank", f.lcbank),
    field("LC amount (PO currency)", f.lc_amount), field("Cash cover (margin) %", f.margin_pct), field("Port of arrival", f.port), field("Expected arrival (ETA)", f.eta),
    field("Bill of lading", f.bl_no), field("Text", f.text))),
    note("Steps: 1 create the file - 2 open the LC (ZLC01, margin blocked at the bank) - 3 enter the costs as they come (customs, freight, clearing ... ZIMP_COST) - 4 goods receipt (MIGO) - 5 landed cost (ZIMP_LAND) - 6 settle the LC (margin back)."));
  toolbar([{ label: "Create", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/import/create", { ebeln: val(f.ebeln), lcno: val(f.lcno), lcbank: up(f.lcbank), lc_amount: val(f.lc_amount),
      margin_pct: val(f.margin_pct), port: val(f.port), eta: f.eta.value, bl_no: val(f.bl_no), text: val(f.text) }));
    if (r) { msg("S", r.message); go("ZIMP02", { id: r.impno }); } } }]);
} });

register("ZIMP02", { title: "Import File Workbench", async render(app, params) {
  const f = { impno: inp({ value: params.id || "", w: "m" }) }, out = h("div");
  app.append(panel(null, grid(field("Import file", f.impno, { req: true }))), out);
  const call = async (path, body) => { const r = await run(() => api(path, Object.assign({ impno: val(f.impno), budat: today() }, body || {}))); if (r) { msg("S", r.message); load(); } return r; };
  const load = async () => {
    if (!val(f.impno)) return;
    const [l, c] = await Promise.all([run(() => api("/api/pur/import")), run(() => api(`/api/pur/import/costs?impno=${encodeURIComponent(val(f.impno))}`))]);
    if (!l || !c) return;
    const x = l.rows.find(r => r.impno === val(f.impno)); if (!x) return msg("E", `Import file ${val(f.impno)} does not exist`);
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Import file", x.impno, `PO ${x.ebeln} - ${x.name || x.lifnr}`), kpi("Status", IMP[x.status][0], x.lcno ? `LC ${x.lcno} ${x.lcbank || ""}` : "LC not opened"),
      kpi("LC amount", `${fmtAmt(x.lc_amount)} ${x.waers}`, `cover ${x.margin_pct} % = ${fmtAmt(x.margin)} EGP`),
      kpi("Import costs", fmtAmt(x.costs), `landed ${fmtAmt(x.landed)}`), kpi("Landed cost %", x.landed_pct == null ? "-" : x.landed_pct + " %", `goods received ${fmtAmt(x.goods_received)} EGP`)),
      h("div.toolbar-inline", null, x.status === "OPEN" ? btn("Open LC (ZLC01)", () => go("ZLC01", { id: x.impno })) : null, " ",
        x.status !== "CLOSED" ? btn("Add cost (ZIMP_COST)", () => go("ZIMP_COST", { id: x.impno })) : null, " ",
        x.status !== "CLOSED" ? btn("Landed cost (ZIMP_LAND)", () => go("ZIMP_LAND", { id: x.impno })) : null, " ",
        x.status === "LC" || x.status === "LANDED" ? btn("Settle LC - release margin", async () => {
          if (await confirmBox("Settle LC", `LC ${x.lcno} paid by the bank - release the margin ${fmtAmt(x.margin)} EGP and close the file?`)) call("/api/pur/import/release"); }) : null),
      alv({ rows: c.rows, title: "Costs of the shipment", emptyText: "No costs yet", columns: [{ key: "id", label: "No.", type: "int" }, { key: "typ_text", label: "Cost" },
        { key: "budat", label: "Date", type: "date" }, { key: "amount", label: "Amount (EGP)", type: "amt", sum: true }, { key: "name", label: "Paid to", render: r => r.name || "Bank" },
        { key: "belnr", label: "FI document" }, { key: "land_belnr", label: "Landed in", render: r => r.land_belnr ? badge(r.land_belnr, "U") : badge("not yet", "Q") }, { key: "text", label: "Text" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "All import files", onClick: () => go("ZIMP03") }]);
  load();
} });

register("ZIMP03", { title: "Import Files - Overview", async render(app) {
  const st = sel([["", "All"], ["OPEN", "Open"], ["LC", "LC opened"], ["LANDED", "Costs landed"], ["CLOSED", "Closed"]], ""), out = h("div");
  app.append(panel(null, grid(field("Status", st))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pur/import?status=${st.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: "Import files", emptyText: "No import files - create one with ZIMP01", columns: [
      { key: "impno", label: "File", link: r => go("ZIMP02", { id: r.impno }) }, { key: "ebeln", label: "PO" }, { key: "name", label: "Vendor" },
      { key: "lcno", label: "LC" }, { key: "lcbank", label: "Bank" }, { key: "lc_amount", label: "LC amount", type: "amt" }, { key: "waers", label: "Cur." },
      { key: "margin", label: "Margin EGP", type: "amt", sum: true }, { key: "eta", label: "ETA", type: "date" }, { key: "costs", label: "Costs", type: "amt", sum: true },
      { key: "landed", label: "Landed", type: "amt", sum: true }, { key: "landed_pct", label: "Landed %" },
      { key: "status", label: "Status", render: r => badge(IMP[r.status][0], IMP[r.status][1]) }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Create import file", onClick: () => go("ZIMP01") }]);
  load();
} });

register("ZLC01", { title: "Open Letter of Credit (LC margin)", async render(app, params) {
  const f = { impno: inp({ value: params.id || "", w: "m" }), lcno: inp({ w: "m" }), budat: inp({ type: "date", value: today() }) };
  app.append(panel(null, grid(field("Import file", f.impno, { req: true }), field("LC number from the bank", f.lcno, { req: true }), field("Posting date", f.budat))),
    note("The cash cover (margin %) of the LC amount is moved from the bank account 113100 to LC margin deposits 116000, translated to EGP at the day's rate."));
  toolbar([{ label: "Open LC", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/import/lc", { impno: val(f.impno), lcno: val(f.lcno), budat: f.budat.value }));
    if (r) { msg("S", r.message); go("ZIMP02", { id: val(f.impno) }); } } }]);
} });

register("ZIMP_COST", { title: "Enter Import Cost", async render(app, params) {
  const f = { impno: inp({ value: params.id || "", w: "m" }), typ: sel(COSTS, "CUSTOMS"), amount: inp({ w: "m" }), budat: inp({ type: "date", value: today() }),
    lifnr: inp({ w: "m", upper: true, list: "dl-lifnr", ph: "empty = paid from the bank" }), xblnr: inp({ w: "m" }), text: inp({ w: "l" }) };
  app.append(panel(null, grid(field("Import file", f.impno, { req: true }), field("Cost type", f.typ), field("Amount (EGP)", f.amount, { req: true }),
    field("Date", f.budat), field("Service provider (vendor)", f.lifnr), field("Reference (receipt no.)", f.xblnr), field("Text", f.text))),
    note("The cost is collected on 193500 (import costs clearing) and added to the stock value with ZIMP_LAND after the goods receipt."));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pur/import/cost", { impno: val(f.impno), typ: f.typ.value, amount: val(f.amount), budat: f.budat.value, lifnr: up(f.lifnr), xblnr: val(f.xblnr), text: val(f.text) }));
    if (r) { msg("S", r.message); f.amount.value = ""; f.text.value = ""; f.xblnr.value = ""; } } }, { label: "Workbench", onClick: () => go("ZIMP02", { id: val(f.impno) }) }]);
} });

register("ZIMP_LAND", { title: "Landed Cost - Add Import Costs to Stock", async render(app, params) {
  const f = { impno: inp({ value: params.id || "", w: "m" }), budat: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("Import file", f.impno, { req: true }), field("Posting date", f.budat))), out);
  const exec = async act => {
    const r = await run(() => api("/api/pur/import/" + act, { impno: val(f.impno), budat: f.budat.value })); if (!r) return;
    msg("S", r.message); out.innerHTML = "";
    out.append(alv({ rows: r.items, title: r.test ? "Test run - nothing posted" : `Posted - document ${r.belnr}`, columns: [{ key: "ebelp", label: "Item", type: "int" },
      { key: "matnr", label: "Material" }, { key: "qty", label: "Received", type: "qty" }, { key: "goods", label: "Goods value EGP", type: "amt", sum: true },
      { key: "share", label: "Import costs", type: "amt", sum: true }, { key: "pct", label: "% on goods" },
      { key: "to_stock", label: "To stock value", type: "amt", sum: true }, { key: "to_prd", label: "To price differences", type: "amt", sum: true }] }),
      note("Costs are shared by the value of the goods received. Moving average materials: to the stock value as far as the quantity is still in stock, the rest to price differences."));
  };
  toolbar([{ label: "Test run", key: "F8", onClick: () => exec("test") }, { label: "Post", primary: true, onClick: () => exec("land") }]);
} });

// ------------------------------------------------------------------ 6-x ML81N service entry sheet
register("ML81N", { title: "Service Entry Sheet", async render(app, params) {
  const out = h("div");
  app.append(note("Services (cleaning, maintenance, security ...) are ordered with a PO item on a cost center or order. Enter what was done; a second person accepts it - only then the cost is posted and the invoice can be checked."), out);
  const load = async () => {
    const d = await run(() => api("/api/pur/ses" + (params.ebeln ? `?ebeln=${params.ebeln}` : ""))); if (!d) return;
    out.innerHTML = "";
    const pending = d.sheets.filter(s => s.status === "P");
    out.append(h("div.kpis", null, kpi("Waiting for acceptance", pending.length, fmtAmt(pending.reduce((a, s) => a + s.amount, 0)) + " EGP", pending.length ? "neg" : "pos")),
      alv({ rows: d.items, title: "Service items of purchase orders", emptyText: "No service PO items (account assignment K / F)", columns: [
        { key: "ebeln", label: "PO" }, { key: "ebelp", label: "Item", type: "int" }, { key: "name", label: "Vendor" }, { key: "txz01", label: "Service" },
        { key: "kostl", label: "Cost center", render: r => r.kostl || r.aufnr || "" }, { key: "menge", label: "Ordered", type: "qty" }, { key: "wemng", label: "Accepted", type: "qty" },
        { key: "open", label: "Open", type: "qty" }, { key: "value", label: "PO value", type: "amt" },
        { key: "x", label: "", render: r => r.open > 0 ? btn("Enter work done", async () => {
          const x = await ask(`Service entry - PO ${r.ebeln}/${r.ebelp}`, [{ name: "menge", label: "Quantity done", value: String(r.open) }, { name: "text", label: "Work done (description)", value: "" }]);
          if (!x) return;
          const res = await run(() => api("/api/pur/ses/create", { ebeln: r.ebeln, ebelp: r.ebelp, menge: x.menge, text: x.text, budat: today() }));
          if (res) { msg("S", res.message); load(); } }) : "" }] }),
      alv({ rows: d.sheets, title: "Service entry sheets", columns: [{ key: "lblni", label: "Sheet" }, { key: "ebeln", label: "PO" }, { key: "name", label: "Vendor" },
        { key: "text", label: "Work done" }, { key: "menge", label: "Qty", type: "qty" }, { key: "amount", label: "Value", type: "amt", sum: true },
        { key: "created_by", label: "Entered by" }, { key: "status_text", label: "Status" }, { key: "accepted_by", label: "Decided by" }, { key: "mblnr", label: "Document" },
        { key: "x", label: "", render: r => r.status === "P" ? h("span", null,
          btn("Accept", async () => { const x = await run(() => api("/api/pur/ses/accept", { lblni: r.lblni, budat: today() })); if (x) { msg("S", x.message); load(); } }), " ",
          btn("Reject", async () => { const x = await ask("Reject service entry", [{ name: "reason", label: "Reason", value: "" }]); if (!x) return;
            const y = await run(() => api("/api/pur/ses/reject", { lblni: r.lblni, reason: x.reason })); if (y) { msg("S", y.message); load(); } })) : "" }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Approval inbox", onClick: () => go("ZINBOX") }]);
  load();
} });

// ------------------------------------------------------------------ 7-x ME91F delivery reminders
register("ME91F", { title: "Delivery Reminders (late purchase orders)", async render(app) {
  const f = { kd: inp({ type: "date", value: today() }), lifnr: inp({ w: "m", upper: true, list: "dl-lifnr" }) }, out = h("div");
  let rows = [], picks = new Set();
  app.append(panel(null, grid(field("Key date", f.kd), field("Vendor", f.lifnr))), out);
  const LV = { 1: ["1st", "Q"], 2: ["2nd", "Q"], 3: ["Final", "B"] };
  const load = async () => {
    const d = await run(() => api(`/api/pur/reminders?key_date=${f.kd.value}&lifnr=${up(f.lifnr)}`)); if (!d) return;
    rows = d.rows; picks = new Set(rows.map((r, i) => r.due ? i : -1).filter(i => i >= 0));
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Late items", rows.length, fmtAmt(rows.reduce((a, r) => a + r.open_value, 0)) + " open value", rows.length ? "neg" : "pos"),
      kpi("Reminders due", picks.size, "new or higher level")),
      alv({ rows: rows.map((r, i) => Object.assign({ i }, r)), title: "Purchase order items past their delivery date", emptyText: "Nothing late", rowClass: r => r.level === 3 ? ".neg" : "",
        columns: [{ key: "pick", label: "Send", render: r => { const cb = h("input", { type: "checkbox" }); cb.checked = picks.has(r.i); cb.addEventListener("change", () => cb.checked ? picks.add(r.i) : picks.delete(r.i)); return cb; } },
          { key: "ebeln", label: "PO" }, { key: "ebelp", label: "Item", type: "int" }, { key: "name", label: "Vendor" }, { key: "matnr", label: "Material", render: r => r.matnr || r.txz01 || "" },
          { key: "eindt", label: "Delivery date", type: "date" }, { key: "days", label: "Days late", type: "int" }, { key: "open", label: "Open qty", type: "qty" },
          { key: "open_value", label: "Open value", type: "amt", sum: true }, { key: "level", label: "Level", render: r => badge(LV[r.level][0], LV[r.level][1]) },
          { key: "reminders", label: "Sent", type: "int" }, { key: "last_sent", label: "Last sent", type: "date" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Send reminders", onClick: async () => {
    if (!picks.size) return msg("E", "Select the items");
    const r = await run(() => api("/api/pur/reminders/send", { key_date: f.kd.value, items: [...picks].map(i => [rows[i].ebeln, rows[i].ebelp]) })); if (!r) return;
    msg("S", r.message); await load();
    out.append(panel("Reminder letters (print with the browser)", ...r.letters.map(v => h("div.letter", null,
      h("h3", null, `${v.name} (${v.lifnr})`), h("p", null, v.text),
      h("ul", null, v.items.map(i => h("li", null, `PO ${i.ebeln}/${i.ebelp} ${i.matnr || i.txz01 || ""} - open ${i.open}, due ${i.eindt} (${i.days} days late)`)))))));
  } }]);
  load();
} });

// ------------------------------------------------------------------ 8-x ZPUR_PRICE price history
register("ZPUR_PRICE", { title: "Purchase Price History", async render(app, params) {
  const f = { matnr: inp({ value: params.id || "", w: "m", upper: true, list: "dl-matnr" }), lifnr: inp({ w: "m", upper: true, list: "dl-lifnr" }) }, out = h("div");
  app.append(panel(null, grid(field("Material", f.matnr, { req: true }), field("Vendor (optional)", f.lifnr))), out);
  const load = async () => {
    if (!up(f.matnr)) return msg("E", "Enter the material");
    const d = await run(() => api(`/api/pur/price_history?matnr=${encodeURIComponent(up(f.matnr))}&lifnr=${up(f.lifnr)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Material", d.matnr, d.maktx), ...Object.entries(d.stats).map(([w, s]) =>
      kpi(`Last price (${w})`, s.last.toFixed(2), `min ${s.min.toFixed(2)} · avg ${s.avg.toFixed(2)} · max ${s.max.toFixed(2)} · ${s.change_pct == null ? "" : (s.change_pct > 0 ? "+" : "") + s.change_pct + " % since first order"}`, s.change_pct > 0 ? "neg" : "pos"))),
      alv({ rows: d.rows, title: "Every purchase order price", emptyText: "Never ordered", columns: [{ key: "bedat", label: "Date", type: "date" }, { key: "ebeln", label: "PO" },
        { key: "name", label: "Vendor" }, { key: "menge", label: "Quantity", type: "qty" }, { key: "price", label: "Price / unit" }, { key: "waers", label: "Cur." },
        { key: "change_pct", label: "Change %", render: r => r.change_pct == null ? "" : h("span" + (r.change_pct > 0 ? ".neg" : ".pos"), null, (r.change_pct > 0 ? "+" : "") + r.change_pct + " %") }] }),
      alv({ rows: d.info_records, title: "Current agreed prices (info records)", columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
        { key: "brutto", label: "Gross", type: "amt" }, { key: "rabatt", label: "Discount %" }, { key: "net", label: "Net / unit" }, { key: "frb", label: "Freight", type: "amt" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  if (params.id) load();
} });
})();
