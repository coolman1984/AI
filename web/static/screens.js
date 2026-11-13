/* NERP - transaction screens */
"use strict";
(() => {
const { h, $, $$, api, msg, err, run, ask, confirmBox, field, inp, sel, val, up,
  alv, register, go, toolbar, fmtQty, fmtAmt, fmtDate, today, enc, S } = App;

// ------------------------------------------------------------------ helpers
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null,
  h("div.panel-body", null, ...body));
const grid = (...fields) => h("div.form-grid", null, ...fields);
const ST_TEXT = { U: "Unrestricted", Q: "Quality insp.", B: "Blocked" };
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const stBadge = st => badge(st, st);
const mt = bwart => S.meta.movement_types.find(m => m.bwart === bwart);
const daysAgo = n => { const d = new Date(today()); d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10); };
function msgLink(type, text, label, tcode, params) {
  msg(type, text);
  const a = h("a", { href: "#", style: { marginLeft: "10px" } }, label);
  a.addEventListener("click", e => { e.preventDefault(); go(tcode, params); });
  $("#status-msg").append(a);
}
function matInput(value, onchange) {
  return inp({ value, list: "dl-mat", upper: true, w: "m", ph: "Material", onchange });
}
function plantInput(value, onchange) {
  return inp({ value, list: "dl-plant", upper: true, w: "s", ph: "Plant", onchange });
}
function priceText(p, peinh, cur) {
  return `${fmtAmt(p)} ${cur || S.meta.currency}` + (peinh > 1 ? ` / ${peinh}` : "");
}
function execBar(fn) { toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }]); }
function result() { return h("div#result"); }

// ================================================================== HOME
register("ZWORKPLACE", { title: "Workplace - All Apps", async render(app) {
  const groups = [
    ["Inventory Management", [
      ["ZMM_COCKPIT", "Inventory Cockpit", "Dashboard & KPIs", "\u25D4", "kpi_value"],
      ["MIGO", "Post Goods Movement", "Receipt, issue, transfer", "\u21C4"],
      ["MMBE", "Stock Overview", "By plant, location, bin", "\u2637"],
      ["MB52", "Warehouse Stocks", "List of stock & values", "\u2630"],
      ["MB51", "Material Documents", "Document list", "\u2263", "kpi_docs"],
      ["MB03", "Display Material Document", "Items, FIFO, accounting", "\u2398"],
      ["MBST", "Cancel Material Document", "Reversal at original value", "\u21B6"],
    ]],
    ["Warehouse (Bins & FIFO)", [
      ["LX02", "Bin Stock (Quants)", "FIFO sequence & GR dates", "\u25A6"],
      ["LX03", "Bin Status / Map", "Empty, occupied, blocked", "\u25A3", "kpi_bins"],
      ["ZORG", "Enterprise Structure", "Plants, storage locs, bins", "\u2302"],
    ]],
    ["Material Master & Valuation", [
      ["MM01", "Create Material", "Basic, MRP, accounting", "\u2295"],
      ["MM02", "Change Material", "Texts, reorder point, plants", "\u270E"],
      ["MM03", "Display Material", "All views & price history", "\u24D8"],
      ["MR21", "Change Material Price", "Revalue stock", "\u00A4"],
      ["CKM3", "Price History", "Moving average over time", "\u2197"],
    ]],
    ["Sales (Order to Cash)", [
      ["ZSD_COCKPIT", "Sales Cockpit", "Revenue, margin, OTIF, credit", "\u25D4", "kpi_sdrev"],
      ["ZSD_PROCESS", "Order-to-Cash Map", "Inquiry \u2192 cash", "\u21BB"],
      ["VA21", "Create Quotation", "Probability & validity", "\u270E"],
      ["VA01", "Create Sales Order", "Pricing, ATP, credit", "\u270D"],
      ["VKM1", "Credit Blocked Orders", "Release by credit manager", "\u26A0", "kpi_sdblk"],
      ["VL10A", "Delivery Due List", "Pick & goods issue", "\u21C9"],
      ["VF04", "Billing Due List", "Invoice to FI & CO-PA", "\u2709"],
      ["ZEINV", "E-Invoices (ETA)", "UUID & status", "\u2611"],
      ["V/LD", "Price Conditions", "PR00, discounts, deals", "\u2696"],
      ["ZRET_MON", "Returns", "Credit & stock decision", "\u21A9"],
      ["IW52", "Service Notifications", "Warranty & DP90", "\u2692"],
      ["MCTA", "Customer Analysis", "Revenue & margin", "\u2261"],
    ]],
    ["Production (Plan to Produce)", [
      ["ZPP_COCKPIT", "Production Cockpit", "Orders, capacity, WIP, variances", "\u25D4", "kpi_ppord"],
      ["ZPP_PROCESS", "Production Process Map", "SOP \u2192 settlement", "\u21BB"],
      ["MC81", "Sales & Operations Plan", "Product group plan", "\u2637"],
      ["MD01", "MRP Run", "Multi-level planning", "\u21BA"],
      ["MD04", "Stock/Requirements List", "Elements & exceptions", "\u2261"],
      ["CO01", "Create Production Order", "BOM, routing, scheduling", "\u270E"],
      ["CO11N", "Confirmation", "Activities, backflush, auto GR", "\u2714"],
      ["CO24", "Missing Parts", "Availability check", "\u26A0", "kpi_ppmiss"],
      ["CM01", "Capacity Load", "Work centers per week", "\u2593"],
      ["ME2O", "Subcontracting", "Provide components", "\u21C4"],
      ["KKAX", "Work in Process", "WIP to FI", "\u29D6"],
      ["MP38", "Spare Parts Forecast", "Safety stock / ROP", "\u2197"],
    ]],
    ["Master Data", [
      ["ZMD_COCKPIT", "Master Data Cockpit", "Quality, risk, dead stock", "\u25D4", "kpi_mdq"],
      ["MM01", "Create Material", "Views per material type", "\u270E"],
      ["MM02", "Change Material", "With change documents", "\u270D"],
      ["ZMM03_LF", "Material 360\u00B0", "Logistics + financial", "\u2399"],
      ["XD01", "Create Customer", "Account group, sales area", "\u263A"],
      ["XK01", "Create Vendor", "Account group, bank, purchasing", "\u2302"],
      ["FK08", "Confirm Sensitive Changes", "Dual control (bank data)", "\u2714", "kpi_sens"],
      ["MM60", "Materials List", "Types, prices, stock", "\u2261"],
      ["J1ID", "CIN Master (India)", "GSTIN, PAN, chapter ID", "\u2691"],
    ]],
    ["Procurement (Procure-to-Pay)", [
      ["ZPUR_COCKPIT", "Procurement Cockpit", "Spend, savings, suppliers", "\u25D4", "kpi_spend"],
      ["ZPUR_PROCESS", "Procurement Process Map", "Requirement \u2192 payment", "\u21BB"],
      ["MD01", "MRP Run", "Reorder point planning", "\u21BA"],
      ["ME51N", "Create Requisition", "Stock & services", "\u270E"],
      ["ME55", "Release Requisitions", "Approval worklist", "\u2714"],
      ["ME57", "Assign & Create POs", "Source determination", "\u21C9"],
      ["ME21N", "Create Purchase Order", "Conditions, account assignment", "\u270D"],
      ["ME28", "Release Purchase Orders", "R1 / R2", "\u2714", "kpi_rel"],
      ["ME23N", "Display Purchase Order", "Items, history, release", "\u2399"],
      ["ME49", "Price Comparison", "RFQ ranking & award", "\u2696"],
      ["ME3M", "Contracts", "Target vs released", "\u2630"],
      ["ME2N", "Purchase Order List", "To deliver / to invoice", "\u2261", "kpi_po"],
      ["ME65", "Vendor Evaluation", "Scores & ranking", "\u2605"],
    ]],
    ["Financial Accounting", [
      ["ZFI_COCKPIT", "Finance Cockpit", "Cash, AR, AP, balance sheet", "\u25D4", "kpi_cash"],
      ["ZFI_PROCESS", "FI Closing Cockpit", "Process map A \u2192 Z", "\u21BB"],
      ["F.01", "Balance Sheet / P&L", "Financial statements", "\u2696"],
      ["S_ALR_87012277", "Trial Balance", "G/L account balances", "\u2261"],
      ["FB60", "Vendor Invoice", "With cost center", "\u270D"],
      ["MIRO", "Invoice Verification", "PO / GR / invoice", "\u2714"],
      ["F110", "Payment Run", "With cash discount", "\u21D2"],
      ["F-28", "Incoming Payment", "Clear customer items", "\u21D0"],
      ["FBL5N", "Customer Line Items", "Open & overdue", "\u2263", "kpi_overdue"],
      ["FBL1N", "Vendor Line Items", "Open & due", "\u2263"],
      ["AR01", "Asset Balances", "Book values", "\u2302"],
      ["AFAB", "Depreciation Run", "To cost centers", "\u2198"],
      ["FF7A", "Cash Forecast", "Next 8 weeks", "\u2197"],
      ["S_ALR_87012357", "VAT Return", "Output - input", "%"],
    ]],
    ["Controlling - Overview & Process", [
      ["ZCO_COCKPIT", "Controlling Cockpit", "Management P&L, plan vs actual", "\u25D4", "kpi_ebit"],
      ["ZCO_PROCESS", "CO Process Map", "Closing cockpit A \u2192 Z", "\u21BB"],
      ["KE30", "Profitability Report", "Contribution margin P&L", "\u2211"],
      ["ZCO_RECON", "FI \u2194 CO-PA Reconciliation", "Proof to the cent", "\u2696"],
    ]],
    ["Cost Center Accounting", [
      ["KSH1", "Hierarchy & Cost Centers", "OKEON / KS01", "\u2302"],
      ["KA03", "Cost Elements", "Primary & secondary", "\u2630"],
      ["KL01", "Activity Types", "Machine, labor, maintenance", "\u23F1"],
      ["KK01", "Statistical Key Figures", "m2, kWh, employees", "\u2116"],
      ["KP06", "Cost Center Planning", "Fixed & variable costs", "\u270E"],
      ["KP26", "Activity Planning", "Hours, capacity, prices", "\u23F2"],
      ["KP46", "Stat. Key Figures Plan/Actual", "KP46 / KB31N", "\u2116"],
      ["KSPI", "Plan Price Calculation", "Iterative", "\u00A4"],
      ["FB50", "Enter G/L Document", "Expenses to cost centers", "\u270D"],
      ["KB11N", "Repost Primary Costs", "Manual correction", "\u21C4"],
      ["KB21N", "Activity Allocation", "Direct, at plan price", "\u21C9"],
      ["KSV5", "Distribution", "Rent by m2", "\u2AA6"],
      ["KSU5", "Assessment", "Energy by kWh", "\u2AA7"],
      ["KSU3", "Allocation Cycles", "Senders, receivers, tracing", "\u2699"],
      ["S_ALR_87013611", "Actual/Plan/Variance", "Cost center report", "\u2263"],
      ["S_ALR_87013625", "Actual/Target/Variance", "Fixed vs variable", "\u2264"],
      ["KSB1", "Line Items", "KSB1 / KSBP / KOB1", "\u2261"],
      ["KSBT", "Activity Prices", "Plan & actual quantities", "\u00A4"],
    ]],
    ["Internal Orders & Product Cost Controlling", [
      ["KO01", "Create Internal Order", "With settlement rule", "\u2295"],
      ["CS03", "BOM & Routing", "Quantity structure", "\u2637"],
      ["KZS2", "Costing Sheet", "Overhead rates", "%"],
      ["CK11N", "Cost Estimate", "Standard cost of product", "\u2211"],
      ["CK13N", "Display Cost Estimate", "Cost component split", "\u24D8"],
      ["CK24", "Release Standard Price", "Mark & release", "\u2714"],
      ["CO01", "Production Order", "Create & release", "\u2692"],
      ["CO11N", "Confirmation", "Machine & labor hours", "\u23F1"],
      ["KOK5", "Order List", "Status, balances", "\u2630", "kpi_orders"],
      ["KKBC_ORD", "Order Analysis", "Plan / target / actual", "\u2696"],
      ["KGI2", "Overhead", "Costing sheet on orders", "%"],
      ["KKS2", "Variances", "Price, quantity, remaining", "\u0394"],
      ["KO88", "Settlement", "Orders \u2192 CC / CO-PA", "\u21D2"],
    ]],
    ["Profitability Analysis (CO-PA)", [
      ["VF01", "Create Billing", "Delivery 601 + revenue + CO-PA", "\u270D"],
      ["VF03", "Billing Documents", "Revenue, discount, COGS", "\u2399"],
      ["KE11", "Sales & Profit Plan", "Qty, price, discount", "\u270E"],
      ["KEU5", "Assessment to CO-PA", "Cost centers \u2192 P&L", "\u21D2"],
      ["KE24", "CO-PA Line Items", "Record types F/C/D", "\u2261"],
    ]],
    ["Accounting, Customizing & Tools", [
      ["FB03", "Display Accounting Document", "Automatic postings", "\u2696"],
      ["OMJJ", "Movement Types", "Customizing (display)", "\u2699"],
      ["MB5K", "Stock Consistency Check", "Quantity, value & G/L", "\u2714"],
      ["ZCOM", "Office Integration (COM)", "Excel, Outlook, PDF, PPT", "\u2709"],
    ]],
  ];
  const kpiEls = {};
  for (const [gname, tiles] of groups) {
    const t = h("div.tiles");
    for (const [code, title, sub, icon, kpi] of tiles) {
      const k = kpi ? h("span.tile-kpi", null, "") : null;
      if (kpi) kpiEls[kpi] = k;
      t.append(h("a.tile", { href: "#/" + code },
        h("div.tile-title", null, title), h("div.tile-sub", null, sub),
        h("div.tile-foot", null, h("span.tile-left", null, h("span.tile-icon", null, icon),
          h("span.tile-code", null, code)), k)));
    }
    app.append(h("div.lp-group", null, h("h2", null, gname), t));
  }
  run(async () => {
    const d = await api("/api/dashboard");
    kpiEls.kpi_value.append(App.fmtShort(d.kpi.total_value), h("small", null, d.currency));
    kpiEls.kpi_docs.append(String(d.kpi.docs_period), h("small", null, "30 d"));
    kpiEls.kpi_bins.append(`${d.kpi.bins_used}/${d.kpi.bins_total}`);
    kpiEls.kpi_po.append(String(d.kpi.open_po_items), h("small", null, "open"));
    api("/api/sd/cockpit").then(s => {
      kpiEls.kpi_sdrev.append(App.fmtShort(s.kpi.revenue), h("small", null, "EGP"));
      kpiEls.kpi_sdblk.append(String(s.kpi.credit_blocked_n), h("small", null, "blocked"));
    }).catch(() => {});
    api("/api/pp/cockpit").then(p => {
      kpiEls.kpi_ppord.append(String(p.kpi.open_orders), h("small", null, "open"));
      kpiEls.kpi_ppmiss.append(String(p.kpi.missing), h("small", null, "orders"));
    }).catch(() => {});
    api("/api/md/cockpit").then(m => {
      kpiEls.kpi_mdq.append(m.kpi.quality + " %", h("small", null, "quality"));
      kpiEls.kpi_sens.append(String(m.kpi.pending), h("small", null, "pending"));
    }).catch(() => {});
    api("/api/pur/cockpit").then(p => {
      kpiEls.kpi_spend.append(App.fmtShort(p.kpi.spend), h("small", null, "EGP"));
      kpiEls.kpi_rel.append(String(p.kpi.pr_waiting + p.kpi.po_blocked), h("small", null, "waiting"));
    }).catch(() => {});
    api("/api/fi/cockpit").then(f => {
      kpiEls.kpi_cash.append(App.fmtShort(f.kpi.cash), h("small", null, "cash"));
      kpiEls.kpi_overdue.append(App.fmtShort(f.kpi.overdue), h("small", null, "overdue"));
    }).catch(() => {});
    api("/api/co/cockpit").then(c => {
      kpiEls.kpi_ebit.append(App.fmtShort(c.kpi.ebit), h("small", null, "EBIT"));
      kpiEls.kpi_orders.append(String(c.kpi.open_orders), h("small", null, "open"));
    }).catch(() => {});
    if (d.kpi.below_reorder) {
      const t = $(".tile[href='#/ZMM_COCKPIT'] .tile-sub");
      t.innerHTML = ""; t.append(h("span.crit", null, `\u26A0 ${d.kpi.below_reorder} below reorder point`));
    }
  });
}});

// ================================================================== MIGO
const ACTIONS = { A01: "Goods Receipt", A07: "Goods Issue", A08: "Transfer Posting",
  A03: "Cancellation", A04: "Display" };
const ACTION_KINDS = { A01: ["receipt"], A07: ["issue"], A08: ["transfer", "stocktype"] };
const DEFAULT_BWART = { A01R01: "101", A01R08: "101", A01R10: "501", A07R10: "201", A08R10: "311" };

register("MIGO", { title: "Goods Movement", async render(app, params) {
  const st = { action: params.action || "A01", ref: params.po ? "R01" : (params.ref || "R01"),
    bwart: params.bwart || "", items: [], cur: -1 };
  if (st.action !== "A01") st.ref = "R10";
  if (!st.bwart) st.bwart = DEFAULT_BWART[st.action + st.ref];
  const hdr = { bldat: inp({ type: "date", value: today(), w: "m" }),
    budat: inp({ type: "date", value: today(), w: "m" }),
    xblnr: inp({ ph: "Delivery note", w: "l" }), bktxt: inp({ ph: "Header text", w: "l" }) };
  const actionSel = sel(Object.entries(ACTIONS).map(([k, v]) => [k, `${k} ${v}`]), st.action,
    { w: "l", onchange: () => {
      st.action = actionSel.value;
      if (st.action === "A03") return go("MBST");
      if (st.action === "A04") return go("MB03");
      if (st.action !== "A01") st.ref = "R10";
      refSel.value = st.ref;
      st.bwart = DEFAULT_BWART[st.action + st.ref];
      bwartIn.value = st.bwart; st.items = []; draw();
    } });
  const refSel = sel([["R01", "R01 Purchase Order"], ["R08", "R08 Order"], ["R10", "R10 Other"]], st.ref, { w: "l",
    onchange: () => {
      if (st.action !== "A01" && refSel.value !== "R10") { refSel.value = "R10"; return msg("W", "Purchase order / order reference only for goods receipt"); }
      st.ref = refSel.value; st.bwart = DEFAULT_BWART[st.action + st.ref];
      bwartIn.value = st.bwart; st.items = []; draw(); } });
  const poIn = inp({ value: params.po || "", ph: "Purchase order", w: "m" });
  const bwartIn = inp({ value: st.bwart, list: "dl-bwart", w: "s", onchange: () => {
    const m = mt(bwartIn.value.trim());
    if (!m) { bwartIn.classList.add("err"); return msg("E", `Movement type ${bwartIn.value} does not exist`, "M7", "012"); }
    const okKinds = ACTION_KINDS[st.action];
    if (!okKinds.includes(m.kind)) { bwartIn.classList.add("err");
      return msg("E", `Movement type ${m.bwart} is not allowed for ${ACTIONS[st.action]}`, "M7", "098"); }
    if (st.ref === "R01" && m.ref !== "PO") { refSel.value = st.ref = "R10"; }
    if (m.ref === "PO" && st.action === "A01" && st.ref === "R10") { refSel.value = st.ref = "R01"; }
    bwartIn.classList.remove("err"); msg("", "");
    st.bwart = m.bwart; for (const it of st.items) it.bwart = m.bwart; draw(); } });
  const bwartText = h("span.hint");
  const poBtn = h("button.btn", { type: "button", on: { click: () => loadPO() } }, "\u2713 Adopt PO");
  poIn.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); loadPO(); } });
  const top = h("div.panel", null, h("div.panel-body.split", null, actionSel, refSel, poIn, poBtn,
    h("span.spacer"), h("span.muted", null, "Movement type"), bwartIn, bwartText));
  const header = panel("Header", grid(field("Document date", hdr.bldat), field("Posting date", hdr.budat, { req: true }),
    field("Delivery note", hdr.xblnr), field("Header text", hdr.bktxt)));
  const itemsBox = h("div.panel");
  const detail = h("div.panel");
  app.append(top, header, itemsBox, detail);

  toolbar([
    { label: "Check", onClick: () => post(true) },
    { label: "Post", key: "Ctrl+S", primary: true, onClick: () => post(false) },
    { label: "\u2191 Upload from Excel", onClick: uploadExcel, ghost: true },
    { label: "Template", onClick: template, ghost: true },
    { label: "Clear", onClick: () => { st.items = []; draw(); msg("", ""); }, ghost: true },
  ]);

  async function loadPO() {
    if (st.ref === "R08") return loadOrder();
    const e = poIn.value.trim();
    if (!e) return msg("E", "Enter a purchase order number", "M7", "037");
    const po = await run(() => api("/api/po/" + enc(e)));
    if (!po) return;
    const open = po.items.filter(i => i.open > 0 && !i.elikz);
    if (!open.length) return msg("W", `Purchase order ${e} has no open items`, "M7", "080");
    st.items = open.map(i => ({ bwart: st.bwart, ebeln: po.ebeln, ebelp: i.ebelp, matnr: i.matnr,
      werks: i.werks, lgort: i.lgort, qty: String(i.open), insmk: "U", lgpla: "", ok: false,
      fromPO: true, vendor: `${po.lifnr} ${po.vendor_name}`, netpr: i.netpr, peinh: i.peinh }));
    st.cur = 0;
    draw();
    msg("I", `Purchase order ${po.ebeln} (${po.vendor_name}) adopted - set "OK" for each item, enter bins, then Post`);
  }

  async function loadOrder() {
    const a = poIn.value.trim();
    if (!a) return msg("E", "Enter an order number", "M7", "024");
    const o = await run(() => api("/api/co/rep/order/" + enc(a)));
    if (!o) return;
    if (o.auart !== "PP01") return msg("E", `Order ${a} is not a production order`, "KO", "013");
    const open = Math.max(o.gamng - o.wemng, 0);
    st.items = [{ bwart: "101", aufnr: o.aufnr, matnr: o.matnr, werks: o.werks, lgort: o.lgort || "0003",
      qty: String(open), insmk: "U", lgpla: "", ok: false, fromPO: true }];
    st.cur = 0; draw();
    msg("I", `Order ${o.aufnr} adopted: ${o.matnr}, open quantity ${fmtQty(open)} - set "OK", enter the bin, then Post`);
  }

  function newItem() {
    const last = st.items[st.items.length - 1] || {};
    return { bwart: st.bwart, matnr: "", werks: last.werks || "1000", lgort: last.lgort || "",
      qty: "", insmk: "U", lgpla: "", ok: true, kostl: last.kostl || "", aufnr: last.aufnr || "",
      umwrk: last.umwrk || "", umlgo: last.umlgo || "", umlgp: "", amount: "", sgtxt: "" };
  }

  function cols() {
    const m = mt(st.bwart) || {};
    const c = [["ok", "OK"], ["matnr", "Material"], ["txt", "Mat. Short Text"], ["qty", "Qty in UnE"],
      ["unit", "EUn"], ["werks", m.kind === "transfer" ? "From Plnt" : "Plnt"],
      ["lgort", m.kind === "transfer" ? "From SLoc" : "SLoc"],
      ["lgpla", m.kind === "receipt" ? "Bin" : "Bin (blank = FIFO)"]];
    if (m.st_choice) c.push(["insmk", "Stock type"]);
    if (m.kind === "stocktype") c.push(["stx", "Stock type change"]);
    if (m.ref === "PO") c.push(st.ref === "R08" ? ["ord", "Order"] : ["po", "Purchase order"]);
    if (m.ref === "KOSTL") c.push(["kostl", "Cost center"]);
    if (m.ref === "AUFNR") c.push(["aufnr", "Order"]);
    if (m.value === "entered") c.push(["amount", "Amount (LC)"]);
    if (m.kind === "transfer") {
      if (m.ref === "UMWRK") c.push(["umwrk", "Recv. Plnt"]);
      c.push(["umlgo", "Recv. SLoc"], ["umlgp", "Recv. Bin"]);
    }
    c.push(["sgtxt", "Text"], ["del", ""]);
    return c;
  }

  function draw() {
    const m = mt(st.bwart);
    bwartText.textContent = m ? m.text : "";
    poIn.style.display = poBtn.style.display = st.ref !== "R10" ? "" : "none";
    poIn.placeholder = st.ref === "R08" ? "Production order" : "Purchase order";
    poBtn.textContent = st.ref === "R08" ? "\u2713 Adopt order" : "\u2713 Adopt PO";
    if (st.ref !== "R01" && !st.items.length) st.items.push(newItem());
    const c = cols();
    const table = h("table.grid.items");
    table.append(h("thead", null, h("tr", null, h("th", null, "Line"), c.map(([, l]) => h("th", null, l)))));
    const tb = h("tbody");
    st.items.forEach((it, i) => tb.append(row(it, i, c)));
    table.append(tb);
    itemsBox.innerHTML = "";
    itemsBox.append(h("div.panel-head", null, "Item Overview", h("span.spacer"),
      st.ref === "R01" ? null : h("button.btn.ghost", { type: "button", on: { click: () => {
        st.items.push(newItem()); st.cur = st.items.length - 1; draw(); } } }, "+ Add line")),
      h("div.items-wrap", null, st.items.length ? table : h("div.alv-empty", null,
        "Enter a purchase order number and choose \u201CAdopt PO\u201D")));
    drawDetail();
  }

  function row(it, i, c) {
    const tr = h("tr" + (i === st.cur ? ".cur" : ""));
    tr.addEventListener("focusin", () => { if (st.cur !== i) { st.cur = i;
      $$("tr.cur", itemsBox).forEach(x => x.classList.remove("cur")); tr.classList.add("cur"); drawDetail(); } });
    tr.append(h("td.ln", null, String(i + 1)));
    const txt = h("span", null, App.matText(it.matnr));
    const unit = h("span", null, App.matUnit(it.matnr));
    const set = (k, upper) => e => { it[k] = upper ? e.target.value.trim().toUpperCase() : e.target.value; };
    const binIn = inp({ value: it.lgpla, upper: true, w: "m", oninput: set("lgpla", true) });
    const refreshBins = async () => {
      if (it.werks && it.lgort && App.isBinManaged(it.werks, it.lgort))
        binIn.setAttribute("list", await App.binList(it.werks, it.lgort));
      else binIn.removeAttribute("list");
      binIn.placeholder = it.lgort && !App.isBinManaged(it.werks, it.lgort) ? "not bin-managed" : "";
    };
    refreshBins();
    const lgortIn = inp({ value: it.lgort, upper: true, w: "s", list: App.slocList(it.werks),
      oninput: set("lgort", true), onchange: () => { refreshBins(); drawDetail(); } });
    for (const [k] of c) {
      let el;
      switch (k) {
        case "ok": el = h("input", { type: "checkbox", checked: it.ok, title: "Item OK",
          on: { change: e => { it.ok = e.target.checked; } } }); break;
        case "matnr": el = it.fromPO ? h("span.mono", null, it.matnr) :
          matInput(it.matnr, e => { it.matnr = up(e.target); txt.textContent = App.matText(it.matnr);
            unit.textContent = App.matUnit(it.matnr); drawDetail(); });
          if (!it.fromPO) el.addEventListener("input", e => { it.matnr = up(e.target); }); break;
        case "txt": el = txt; break;
        case "qty": el = inp({ value: it.qty, w: "s", oninput: set("qty"), onchange: drawDetail }); break;
        case "unit": el = unit; break;
        case "werks": el = it.fromPO ? h("span", null, it.werks) : plantInput(it.werks, e => {
          it.werks = up(e.target); lgortIn.setAttribute("list", App.slocList(it.werks)); refreshBins(); drawDetail(); });
          if (!it.fromPO) el.addEventListener("input", e => { it.werks = up(e.target); }); break;
        case "lgort": el = lgortIn; break;
        case "lgpla": {
          const m = mt(st.bwart);
          el = h("span.split", null, binIn, m.kind === "receipt" ?
            h("button.alv-tb-btn", { type: "button", title: "Propose bin (putaway strategy)",
              on: { click: async () => {
                if (!it.matnr || !it.werks || !it.lgort) return msg("W", "Enter material, plant and storage location first");
                const p = await run(() => api(`/api/bin/propose?matnr=${enc(it.matnr)}&werks=${enc(it.werks)}&lgort=${enc(it.lgort)}&insmk=${it.insmk}`));
                if (p && p.lgpla) { binIn.value = it.lgpla = p.lgpla; msg("I", `Bin ${p.lgpla} proposed: ${p.strategy}`); }
                else if (p) msg("W", "No bin to propose (location not bin-managed or no empty bin)");
              } } }, "\u2316") : null); break;
        }
        case "insmk": el = sel(Object.entries(ST_TEXT), it.insmk, { onchange: e => { it.insmk = e.target.value; drawDetail(); } }); break;
        case "stx": { const m = mt(st.bwart); el = h("span", null, stBadge(m.from_st), " \u2192 ", stBadge(m.to_st)); break; }
        case "ord": el = h("span.mono", null, it.aufnr || ""); break;
        case "po": el = it.fromPO ? h("span.mono", null, `${it.ebeln}/${it.ebelp}`) :
          h("span.split", null, inp({ value: it.ebeln, w: "m", ph: "PO", oninput: set("ebeln") }),
            inp({ value: it.ebelp || "10", w: "s", oninput: set("ebelp") })); break;
        case "kostl": el = inp({ value: it.kostl, list: "dl-kostl", upper: true, w: "s", oninput: set("kostl", true) }); break;
        case "aufnr": el = inp({ value: it.aufnr, w: "m", oninput: set("aufnr") }); break;
        case "amount": el = inp({ value: it.amount, w: "m", ph: "blank = price", oninput: set("amount"), onchange: drawDetail }); break;
        case "umwrk": el = plantInput(it.umwrk, e => { it.umwrk = up(e.target); }); el.addEventListener("input", e => { it.umwrk = up(e.target); }); break;
        case "umlgo": el = inp({ value: it.umlgo, upper: true, w: "s", list: App.slocList(it.umwrk || it.werks), oninput: set("umlgo", true) }); break;
        case "umlgp": el = inp({ value: it.umlgp, upper: true, w: "m", oninput: set("umlgp", true) }); break;
        case "sgtxt": el = inp({ value: it.sgtxt, w: "l", oninput: set("sgtxt") }); break;
        case "del": el = h("button.alv-tb-btn", { type: "button", title: "Delete line", on: { click: () => {
          st.items.splice(i, 1); st.cur = Math.min(st.cur, st.items.length - 1); draw(); } } }, "\u2715"); break;
      }
      tr.append(h("td", null, el));
    }
    return tr;
  }

  let detailSeq = 0;
  async function drawDetail() {
    const seq = ++detailSeq;
    const it = st.items[st.cur];
    detail.innerHTML = "";
    if (!it) return;
    detail.append(h("div.panel-head", null, `Item ${st.cur + 1} - Detail`));
    const body = h("div.panel-body", null, h("span.muted", null, "Enter a material to see stock and valuation"));
    detail.append(body);
    if (!it.matnr || !App.matText(it.matnr)) return;
    let m, stock;
    try {
      [m, stock] = await Promise.all([api("/api/material/" + enc(it.matnr)), api("/api/stock/overview/" + enc(it.matnr))]);
    } catch (e) { return; }
    if (seq !== detailSeq) return;
    const plant = m.plants.find(p => p.werks === it.werks);
    const sp = stock.plants.find(p => p.werks === it.werks);
    const sl = sp && sp.slocs.find(s => s.lgort === it.lgort);
    body.innerHTML = "";
    const attrs = [["Material", `${m.matnr} ${m.maktx}`], ["Material type", `${m.mtart} ${m.mtart_text}`],
      ["Base unit", m.meins]];
    if (!plant) {
      body.append(h("div.neg", null, `Material ${m.matnr} is not maintained in plant ${it.werks || "?"}`));
      return;
    }
    const price = plant.vprsv === "S" ? plant.stprs : plant.verpr;
    attrs.push(["Price control", plant.vprsv === "V" ? "V Moving average price" : "S Standard price"],
      ["Current price", priceText(price, plant.peinh)],
      ["Plant stock / value", `${fmtQty(plant.lbkum)} ${m.meins} / ${fmtAmt(plant.salk3)} ${S.meta.currency}`]);
    if (it.lgort) attrs.push([`Stock in SLoc ${it.lgort}`, sl ?
      `U ${fmtQty(sl.U)} \u00B7 Q ${fmtQty(sl.Q)} \u00B7 B ${fmtQty(sl.B)} ${m.meins}` : `0 ${m.meins}`]);
    // valuation preview: what will the moving average price become?
    const q = parseFloat(String(it.qty).replace(/,/g, ""));
    const mm = mt(it.bwart || st.bwart);
    let preview = null;
    if (q > 0 && mm && (mm.kind === "receipt" || mm.kind === "issue")) {
      let value = null;
      if (mm.value === "po" && it.netpr !== undefined) value = q * it.netpr / (it.peinh || 1);
      else if (mm.value === "entered" && it.amount) value = parseFloat(String(it.amount).replace(/,/g, ""));
      else value = q * price / plant.peinh;
      const sign = mm.kind === "receipt" ? 1 : -1;
      const newQty = plant.lbkum + sign * q;
      if (plant.vprsv === "V") {
        let newVal = plant.salk3 + sign * value;
        if (newQty <= 0) newVal = 0;
        const newMap = newQty > 0 ? newVal / newQty * plant.peinh : price;
        preview = h("div", null, h("b", null, "Valuation preview: "),
          `value ${fmtAmt(value)} ${S.meta.currency} \u2192 new stock ${fmtQty(newQty)} ${m.meins}, ` +
          `value ${fmtAmt(newVal)}, moving average price `,
          h("b", { class: Math.abs(newMap - price) > 0.005 ? "crit" : "" }, priceText(newMap, plant.peinh)),
          newQty < 0 ? h("span.neg", null, "  \u26A0 stock would become negative") : null);
      } else {
        const diff = mm.value === "po" ? value - q * price / plant.peinh : 0;
        preview = h("div", null, h("b", null, "Valuation preview: "),
          `stock valued at standard price ${priceText(price, plant.peinh)}`,
          diff ? h("span", null, ` \u00B7 price difference ${fmtAmt(diff)} ${S.meta.currency} to account 231500`) : null);
      }
    }
    if (it.vendor) attrs.push(["Vendor", it.vendor], ["PO price", priceText(it.netpr, it.peinh)]);
    body.append(h("div.obj-header", { style: { padding: 0 } }, attrs.map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", { style: { fontSize: "13px" } }, v)))),
      preview ? h("div", { style: { marginTop: "10px", padding: "8px 10px", background: "#f5faff",
        border: "1px solid #cfe3f7", borderRadius: "4px" } }, preview) : null);
  }

  function payload() {
    const items = st.items.filter(i => i.ok).map(i => {
      const o = { bwart: i.bwart || st.bwart };
      for (const k of ["matnr", "werks", "lgort", "lgpla", "qty", "insmk", "kostl", "aufnr", "ebeln",
        "ebelp", "umwrk", "umlgo", "umlgp", "amount", "sgtxt"]) if (i[k] !== undefined && i[k] !== "") o[k] = i[k];
      return o;
    });
    return { header: { budat: hdr.budat.value, bldat: hdr.bldat.value, xblnr: val(hdr.xblnr),
      bktxt: val(hdr.bktxt) }, items };
  }
  async function post(check) {
    const p = payload();
    if (!p.items.length) return msg("E", "No items selected - set the \u201COK\u201D flag", "M7", "001");
    if (check) p.check = true;
    const r = await run(() => api("/api/goodsmovement", p));
    if (!r) return;
    if (check) return msg("S", r.message);
    msgLink("S", `Material document ${r.mblnr} posted` + (r.belnr ? ` (accounting doc. ${r.belnr})` : ""),
      "Display", "MB03", { id: r.mblnr, year: r.mjahr });
    st.items = []; poIn.value = ""; hdr.xblnr.value = ""; hdr.bktxt.value = "";
    draw();
  }

  const ALIASES = { bwart: ["bwart", "movement type", "mvt", "mvt type"], matnr: ["matnr", "material"],
    qty: ["qty", "quantity", "menge", "qty in une"], werks: ["werks", "plant", "plnt"],
    lgort: ["lgort", "sloc", "storage location"], lgpla: ["lgpla", "bin", "storage bin"],
    insmk: ["insmk", "stock type"], kostl: ["kostl", "cost center", "cost centre"],
    aufnr: ["aufnr", "order"], ebeln: ["ebeln", "po", "purchase order"], ebelp: ["ebelp", "po item"],
    umwrk: ["umwrk", "recv plant", "receiving plant"], umlgo: ["umlgo", "recv sloc", "receiving sloc"],
    umlgp: ["umlgp", "recv bin", "receiving bin"], amount: ["amount", "dmbtr", "value"],
    sgtxt: ["sgtxt", "text", "item text"] };
  const TEMPLATE_COLS = ["Movement type", "Material", "Quantity", "Plant", "SLoc", "Bin", "Stock type",
    "Cost center", "Order", "PO", "PO item", "Recv plant", "Recv SLoc", "Recv bin", "Amount", "Text"];
  async function uploadExcel() {
    if (!S.meta.com.available) return msg("E", "Excel upload uses Office COM and needs Windows: " + S.meta.com.reason, "COM", "001");
    const r = await ask("Upload goods movements from Excel", [{ name: "path", label: "File path",
      placeholder: "C:\\Users\\me\\Desktop\\movements.xlsx" }]);
    if (!r || !r.path.trim()) return;
    msg("I", "Reading the file through Excel (COM)...");
    const data = await run(() => api("/api/office/excel-read", { path: r.path }));
    if (!data) return;
    const rowsX = data.rows || [];
    if (rowsX.length < 2) return msg("E", "The sheet has no data rows");
    const head = rowsX[0].map(x => String(x || "").trim().toLowerCase());
    const idx = {};
    for (const [k, names] of Object.entries(ALIASES)) {
      const j = head.findIndex(x => names.includes(x)); if (j >= 0) idx[k] = j;
    }
    if (idx.matnr === undefined && idx.ebeln === undefined) return msg("E", "Column \u201CMaterial\u201D not found in the first row");
    const items = [];
    for (const rr of rowsX.slice(1)) {
      if (!rr.some(x => x !== null && String(x).trim() !== "")) continue;
      const it = newItem();
      for (const [k, j] of Object.entries(idx)) {
        let v = rr[j]; if (v === null || v === undefined) continue;
        v = String(v).trim();
        if (["matnr", "werks", "lgort", "lgpla", "insmk", "kostl", "umwrk", "umlgo", "umlgp"].includes(k)) v = v.toUpperCase();
        if (["werks", "lgort", "umwrk", "umlgo"].includes(k) && /^\d+$/.test(v)) v = v.padStart(4, "0");
        it[k] = v;
      }
      it.bwart = it.bwart || st.bwart; it.ok = true; items.push(it);
    }
    const types = [...new Set(items.map(i => i.bwart))];
    const m = mt(types[0]);
    if (!m) return msg("E", `Movement type ${types[0]} does not exist`);
    st.action = m.kind === "receipt" ? "A01" : m.kind === "issue" ? "A07" : "A08";
    st.ref = "R10"; st.bwart = m.bwart; actionSel.value = st.action; refSel.value = "R10"; bwartIn.value = m.bwart;
    st.items = items; st.cur = 0; draw();
    msg(types.length > 1 ? "W" : "S", `${items.length} lines read from sheet \u201C${data.sheet}\u201D` +
      (types.length > 1 ? ` - mixed movement types (${types.join(", ")}) will be posted in one document` : "") + " - check and Post");
  }
  function template() {
    App.exportRows({ columns: TEMPLATE_COLS.map(c => ({ key: c, label: c })), exportName: "MIGO_template" },
      [{ "Movement type": "201", Material: "RM-1001", Quantity: 10, Plant: "1000", SLoc: "0001",
        "Cost center": "4100", Text: "example line" }]);
  }
  draw();
  if (params.order) { refSel.value = st.ref = "R08"; poIn.value = params.order; draw(); loadOrder(); }
  else if (params.po) loadPO();
}});

// ================================================================== MMBE
register("MMBE", { title: "Stock Overview: Company Code/Plant/Storage Location/Bin", async render(app, params) {
  const m = matInput(params.id || "");
  const w = plantInput(params.werks || "");
  const out = result();
  app.append(panel("Database Selections", grid(field("Material", m, { req: true }), field("Plant", w))), out);
  const exec = async () => {
    if (!up(m)) return msg("E", "Enter a material", "M7", "002");
    const d = await run(() => api("/api/stock/overview/" + enc(up(m))));
    if (!d) return;
    msg("", "");
    out.innerHTML = "";
    const plants = d.plants.filter(p => !up(w) || p.werks === up(w));
    const head = h("div.panel", null, h("div.obj-header", null,
      [["Material", d.matnr], ["Description", d.maktx], ["Material type", d.mtart], ["Base unit", d.meins],
        ["Total unrestricted", fmtQty(d.U) + " " + d.meins]].map(([k, v], i) =>
        h("div.attr", null, h("span.k", null, k), h("span.v" + (i === 4 ? ".big" : ""), null, v)))));
    const t = h("table.grid.tree");
    t.append(h("thead", null, h("tr", null, ["Client / Company Code / Plant / Storage Location / Bin", "Unrestricted use",
      "Qual. inspection", "Blocked", "Oldest GR", "Valuation"].map((x, i) => h("th" + (i && i < 4 ? ".num" : ""), null, x)))));
    const tb = h("tbody");
    const r = (lvl, label, u, q, b, extra, oldest) => h("tr", null, h("td.lvl" + lvl, null, label),
      h("td.num", null, fmtQty(u)), h("td.num", null, fmtQty(q)), h("td.num", null, fmtQty(b)),
      h("td", null, oldest ? fmtDate(oldest) : ""), h("td", null, extra || ""));
    const sum = k => plants.reduce((a, p) => a + p[k], 0);
    tb.append(r(0, "Full", sum("U"), sum("Q"), sum("B")));
    for (const p of plants) {
      tb.append(r(1, `${p.werks} ${p.name}`, p.U, p.Q, p.B, h("span", null, badge(p.vprsv, p.vprsv), " ",
        `${priceText(p.price, p.peinh)} \u00B7 value ${fmtAmt(p.salk3)}`)));
      for (const s of p.slocs) {
        const oldest = s.bins.reduce((a, b) => !a || b.oldest < a ? b.oldest : a, "");
        tb.append(r(2, `${s.lgort} ${s.name}`, s.U, s.Q, s.B, "", oldest));
        for (const b of s.bins) if (b.lgpla) tb.append(r(3, `Bin ${b.lgpla}`, b.insmk === "U" ? b.qty : 0,
          b.insmk === "Q" ? b.qty : 0, b.insmk === "B" ? b.qty : 0, stBadge(b.insmk), b.oldest));
      }
    }
    t.append(tb);
    out.append(head, h("div.alv", null, h("div.alv-toolbar", null, h("span.title", null, "Stock overview"),
      h("button.alv-tb-btn", { type: "button", on: { click: () => go("MB51", { matnr: d.matnr }) } }, "Material documents"),
      h("button.alv-tb-btn", { type: "button", on: { click: () => go("LX02", { matnr: d.matnr }) } }, "Bin stock (FIFO)"),
      h("button.alv-tb-btn", { type: "button", on: { click: () => go("MM03", { id: d.matnr }) } }, "Material master")),
      h("div.alv-scroll", null, t)));
  };
  execBar(exec);
  m.addEventListener("keydown", e => { if (e.key === "Enter") exec(); });
  if (params.id) exec(); else m.focus();
}});

// ================================================================== MB52
register("MB52", { title: "Display Warehouse Stocks of Material", async render(app, params) {
  const m = inp({ value: params.matnr || "", upper: true, w: "m", list: "dl-mat", ph: "e.g. RM-*" });
  const w = plantInput(params.werks || "");
  const l = inp({ value: params.lgort || "", upper: true, w: "s", list: App.slocList("") });
  const t = sel([["", "(all)"], ...Object.entries(S.meta.material_types).map(([k, v]) => [k, `${k} ${v}`])], "", { w: "l" });
  const out = result();
  app.append(panel("Database Selections", grid(field("Material", m, { hint: "* = wildcard" }), field("Plant", w),
    field("Storage location", l), field("Material type", t))), out);
  const exec = async () => {
    const rows = await run(() => api(`/api/stock/warehouse?matnr=${enc(up(m))}&werks=${enc(up(w))}&lgort=${enc(up(l))}&mtart=${enc(t.value)}`));
    if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ title: "Warehouse stocks", exportName: "MB52", rows, sumUnitKey: "meins", columns: [
      { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) },
      { key: "maktx", label: "Material Description" }, { key: "mtart", label: "MTyp" },
      { key: "werks", label: "Plnt" }, { key: "lgort", label: "SLoc" }, { key: "lgobe", label: "Descr. of Storage Loc." },
      { key: "meins", label: "BUn" },
      { key: "unrestricted", label: "Unrestricted", type: "qty", sum: true },
      { key: "val_unrestricted", label: "Value Unrestricted", type: "amt", sum: true },
      { key: "quality", label: "In Qual. Insp.", type: "qty", sum: true },
      { key: "val_quality", label: "Value in QualInsp.", type: "amt", sum: true },
      { key: "blocked", label: "Blocked", type: "qty", sum: true },
      { key: "val_blocked", label: "Value Blocked", type: "amt", sum: true },
      { key: "price", label: "Price", type: "amt" }, { key: "peinh", label: "per", type: "int" },
      { key: "vprsv", label: "Pr.", render: r => badge(r.vprsv, r.vprsv) }, { key: "currency", label: "Crcy" }] }));
    msg("S", `${rows.length} entries selected`);
  };
  execBar(exec);
  exec();
}});

// ================================================================== MB51
register("MB51", { title: "Material Document List", async render(app, params) {
  const f = { matnr: inp({ value: params.matnr || "", upper: true, w: "m", list: "dl-mat" }),
    werks: plantInput(params.werks || ""), lgort: inp({ value: "", upper: true, w: "s", list: App.slocList("") }),
    bwart: inp({ value: params.bwart || "", w: "m", list: "dl-bwart", ph: "e.g. 101,261" }),
    from: inp({ type: "date", value: params.from || daysAgo(30), w: "m" }),
    to: inp({ type: "date", value: params.to || today(), w: "m" }),
    usnam: inp({ value: "", upper: true, w: "s" }) };
  const out = result();
  app.append(panel("Item Data / Header Data", grid(field("Material", f.matnr, { hint: "* = wildcard" }),
    field("Plant", f.werks), field("Storage location", f.lgort),
    field("Movement type", f.bwart, { hint: "list with commas" }), field("Posting date from", f.from),
    field("Posting date to", f.to), field("User name", f.usnam))), out);
  const exec = async () => {
    const q = Object.entries(f).map(([k, el]) => `${k}=${enc(k === "bwart" ? val(el) : up(el) || val(el))}`).join("&");
    const rows = await run(() => api("/api/docs?" + q));
    if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ title: "Material documents", exportName: "MB51", rows,
      rowClass: r => r.canceled ? ".canceled" : "", columns: [
        { key: "mblnr", label: "Mat. Doc.", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) },
        { key: "zeile", label: "Item", type: "int" }, { key: "budat", label: "Pstng Date", type: "date" },
        { key: "bwart", label: "MvT" }, { key: "bwart_text", label: "Movement Type Text" },
        { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) },
        { key: "maktx", label: "Material Description" }, { key: "werks", label: "Plnt" },
        { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Bin" },
        { key: "insmk", label: "S", render: r => stBadge(r.insmk) },
        { key: "qty", label: "Quantity", type: "qty", signed: true },
        { key: "meins", label: "EUn" }, { key: "amount", label: "Amount in LC", type: "amt", signed: true, sum: true },
        { key: "ebeln", label: "Purch. Doc.", link: r => r.ebeln && go("ME23N", { id: r.ebeln }) },
        { key: "kostl", label: "Cost Ctr" }, { key: "aufnr", label: "Order" },
        { key: "usnam", label: "User" }, { key: "smbln", label: "Ref. (reversal of)" },
        { key: "sgtxt", label: "Text" }] }));
    msg("S", `${rows.length} items selected`);
  };
  execBar(exec);
  exec();
}});

// ================================================================== MB03
register("MB03", { title: "Display Material Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m", ph: "49........" });
  const y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const out = result();
  app.append(panel("Material Document", grid(field("Material document", d, { req: true }), field("Mat. doc. year", y))), out);
  const exec = async () => {
    if (!val(d)) return msg("E", "Enter a material document", "M7", "060");
    const doc = await run(() => api(`/api/doc/${enc(val(y))}/${enc(val(d))}`).catch(() => api(`/api/doc/${enc(val(d))}`)));
    if (!doc) return;
    y.value = doc.mjahr;
    msg("", "");
    toolbar([{ label: "Execute", key: "F8", onClick: exec },
      doc.acc_doc ? { label: "Accounting Documents", onClick: () => go("FB03", { id: doc.acc_doc.belnr, year: doc.acc_doc.gjahr }) } : null,
      !doc.reversed_by && !doc.items.some(i => i.smbln) ? { label: "\u21B6 Cancel (MBST)", danger: true,
        onClick: () => go("MBST", { id: doc.mblnr, year: doc.mjahr }) } : null,
      { label: "Print", ghost: true, onClick: () => window.print() }]);
    out.innerHTML = "";
    const attrs = [["Material document", `${doc.mblnr} / ${doc.mjahr}`], ["Posting date", fmtDate(doc.budat)],
      ["Document date", fmtDate(doc.bldat)], ["Entered by", doc.usnam], ["Entered at", doc.cpudt],
      ["Transaction", doc.tcode], ["Delivery note / ref.", doc.xblnr || "\u2013"], ["Header text", doc.bktxt || "\u2013"]];
    out.append(h("div.panel", null, h("div.obj-header", null, attrs.map(([k, v]) => h("div.attr", null,
      h("span.k", null, k), h("span.v", null, v)))),
      doc.reversed_by ? h("div.panel-body.neg", null, "\u26A0 This document was reversed by ",
        h("a", { href: `#/MB03?id=${doc.reversed_by.mblnr}&year=${doc.reversed_by.mjahr}` }, doc.reversed_by.mblnr)) : null));
    out.append(alv({ title: "Items", exportName: "MB03_" + doc.mblnr, rows: doc.items, columns: [
      { key: "zeile", label: "Item", type: "int" }, { key: "bwart", label: "MvT" },
      { key: "bwart_text", label: "Movement" }, { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) },
      { key: "maktx", label: "Description" }, { key: "menge", label: "Quantity", type: "qty" },
      { key: "meins", label: "EUn" }, { key: "werks", label: "Plnt" }, { key: "lgort", label: "SLoc" },
      { key: "lgpla", label: "Bin(s)" }, { key: "insmk", label: "Stock type", render: r => stBadge(r.insmk) },
      { key: "shkzg", label: "D/C", render: r => h("span", { class: r.shkzg === "S" ? "pos" : "neg" }, r.shkzg === "S" ? "S + (in)" : "H \u2212 (out)") },
      { key: "dmbtr", label: "Movement value", type: "amt" }, { key: "salk", label: "Stock value change", type: "amt" },
      { key: "ebeln", label: "PO", render: r => r.ebeln ? h("span", null, `${r.ebeln}/${r.ebelp}`) : "" },
      { key: "kostl", label: "Cost Ctr" }, { key: "aufnr", label: "Order" },
      { key: "smbln", label: "Reversal of", render: r => r.smbln ? h("span", null, `${r.smbln}/${r.smblp}`) : "" },
      { key: "sgtxt", label: "Text" }] }));
    const pieces = doc.items.filter(i => i.pieces.length);
    if (pieces.length) {
      const rows = [];
      for (const i of pieces) for (const p of i.pieces) rows.push({ zeile: i.zeile, matnr: i.matnr, shkzg: i.shkzg,
        lgort: i.lgort, lgpla: p.lgpla, wdatu: p.wdatu, qty: p.qty, meins: i.meins });
      out.append(h("div", { style: { height: "14px" } }), alv({ title: "Quants touched (FIFO by goods receipt date)",
        rows, columns: [{ key: "zeile", label: "Item", type: "int" }, { key: "matnr", label: "Material" },
          { key: "shkzg", label: "Direction", render: r => r.shkzg === "S" ? "placed" : "taken" },
          { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Bin" },
          { key: "wdatu", label: "GR date", type: "date" }, { key: "qty", label: "Quantity", type: "qty" },
          { key: "meins", label: "EUn" }] }));
    }
  };
  execBar(exec);
  d.addEventListener("keydown", e => { if (e.key === "Enter") exec(); });
  if (params.id) exec(); else d.focus();
}});

// ================================================================== MBST
register("MBST", { title: "Cancel Material Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" });
  const y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const b = inp({ type: "date", value: today(), w: "m" });
  const r = inp({ value: "", w: "l", ph: "Reason for reversal" });
  const out = result();
  app.append(panel("Default values", grid(field("Material document", d, { req: true }), field("Mat. doc. year", y),
    field("Posting date", b), field("Reason", r))),
  h("div.note", { style: { marginBottom: "10px" } }, "The reversal posts the opposite movement type (e.g. 101 \u2192 102, 201 \u2192 202) " +
    "at the ORIGINAL values. Stock goes back to the same bins with the same goods receipt dates."), out);
  const show = async (quiet) => {
    out.innerHTML = "";
    if (!val(d)) return;
    const doc = await run(() => api(`/api/doc/${enc(val(y))}/${enc(val(d))}`));
    if (!doc) return;
    out.append(alv({ title: `Items of ${doc.mblnr} (posted ${fmtDate(doc.budat)} by ${doc.usnam})`, rows: doc.items, columns: [
      { key: "zeile", label: "Item", type: "int" }, { key: "bwart", label: "MvT" },
      { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
      { key: "menge", label: "Quantity", type: "qty" }, { key: "meins", label: "EUn" },
      { key: "werks", label: "Plnt" }, { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Bin" },
      { key: "salk", label: "Value", type: "amt" },
      { key: "rev", label: "Reversal MvT", render: x => h("b", null, (mt(x.bwart) || {}).reverse || "") }] }));
    if (doc.reversed_by && quiet !== true) msg("W", `Document ${doc.mblnr} was already reversed by ${doc.reversed_by.mblnr}`, "M7", "065");
  };
  const exec = async () => {
    if (!val(d)) return msg("E", "Enter a material document", "M7", "060");
    if (!await confirmBox("Cancel material document", `Reverse material document ${val(d)} completely?`, "Reverse")) return;
    const res = await run(() => api("/api/doc/cancel", { mblnr: val(d), mjahr: val(y), budat: b.value, reason: val(r) }));
    if (res) { msgLink("S", `Document ${res.mblnr} posted (reversal of ${val(d)})`, "Display", "MB03", { id: res.mblnr, year: res.mjahr }); show(true); }
  };
  toolbar([{ label: "Show items", key: "F8", onClick: () => show() }, { label: "Post reversal", key: "Ctrl+S", primary: true, onClick: exec }]);
  d.addEventListener("change", () => show());
  if (params.id) show();
}});

// ================================================================== MM01 / MM02 / MM03
register("MM01", { title: "Create Material", async render(app) {
  const f = { matnr: inp({ upper: true, w: "m", ph: "blank = internal number" }),
    mtart: sel(Object.entries(S.meta.material_types).map(([k, v]) => [k, `${k} ${v}`]), "ROH", { w: "l",
      onchange: () => { vclass.value = VC[f.mtart.value]; } }),
    maktx: inp({ w: "l" }), meins: sel(Object.entries(S.meta.units).map(([k, v]) => [k, `${k} ${v}`]), "PC", { w: "m" }),
    matkl: inp({ upper: true, w: "m" }), minbe: inp({ value: "0", w: "m" }), eisbe: inp({ value: "0", w: "m" }),
    vprsv: sel([["V", "V Moving average price"], ["S", "S Standard price"]], "V", { w: "l" }),
    price: inp({ value: "0.00", w: "m" }), peinh: inp({ value: "1", w: "s" }) };
  const VC = { ROH: "3000", HALB: "7900", FERT: "7920", HIBE: "3030", VERP: "3050" };
  const vclass = inp({ value: "3000", readonly: true, w: "s" });
  const plantChecks = S.meta.plants.map(p => {
    const c = h("input", { type: "checkbox", value: p.werks, checked: p.werks === "1000" });
    return h("label.checkbox", { style: { marginRight: "18px" } }, c, `${p.werks} ${p.name}`);
  });
  const tabs = ["Basic data 1", "MRP 1", "Accounting 1"];
  const pages = [grid(field("Material description", f.maktx, { req: true }), field("Base unit of measure", f.meins, { req: true }),
      field("Material group", f.matkl)),
    grid(field("Reorder point", f.minbe), field("Safety stock", f.eisbe)),
    grid(field("Price control", f.vprsv, { req: true }), field(f.vprsv.value === "S" ? "Standard price" : "Price (initial MAP)", f.price),
      field("Price unit", f.peinh), field("Valuation class", vclass))];
  const tabBar = h("div.tabs"), page = h("div.panel-body");
  tabs.forEach((t, i) => tabBar.append(h("button.tab" + (i === 0 ? ".active" : ""), { type: "button", on: { click: e => {
    $$(".tab", tabBar).forEach(x => x.classList.remove("active")); e.currentTarget.classList.add("active");
    page.innerHTML = ""; page.append(pages[i]); } } }, t)));
  page.append(pages[0]);
  app.append(panel("Initial screen", grid(field("Material", f.matnr), field("Material type", f.mtart, { req: true }))),
    panel("Organizational levels - Plants", ...plantChecks),
    h("div.panel", null, tabBar, page),
    h("div.note", null, "Moving average price (V): the price changes with every goods receipt. Standard price (S): " +
      "the price is fixed; differences go to the price difference account."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const plants = plantChecks.map(l => $("input", l)).filter(c => c.checked).map(c => ({ werks: c.value,
      vprsv: f.vprsv.value, price: val(f.price), peinh: val(f.peinh), minbe: val(f.minbe), eisbe: val(f.eisbe) }));
    const r = await run(() => api("/api/material", { matnr: up(f.matnr), mtart: f.mtart.value, maktx: val(f.maktx),
      meins: f.meins.value, matkl: up(f.matkl), plants }));
    if (r) { await App.loadMaterials(); msgLink("S", r.message, "Display", "MM03", { id: r.matnr });
      for (const k of ["matnr", "maktx", "matkl"]) f[k].value = ""; }
  } }]);
  f.maktx.focus();
}});

async function loadMat(input) {
  if (!up(input)) { msg("E", "Enter a material", "M3", "305"); return null; }
  return run(() => api("/api/material/" + enc(up(input))));
}

register("MM02", { title: "Change Material", async render(app, params) {
  const m = matInput(params.id || "");
  const out = result();
  app.append(panel("Initial screen", grid(field("Material", m, { req: true }))), out);
  const exec = async () => {
    const d = await loadMat(m);
    if (!d) return;
    msg("", "");
    out.innerHTML = "";
    const maktx = inp({ value: d.maktx, w: "l" }), matkl = inp({ value: d.matkl, upper: true, w: "m" });
    const plantRows = d.plants.map(p => ({ werks: p.werks, minbe: inp({ value: p.minbe, w: "m" }), eisbe: inp({ value: p.eisbe, w: "m" }) }));
    const t = h("table.grid.items", null, h("thead", null, h("tr", null, ["Plant", "Reorder point", "Safety stock", "Price control", "Price"].map(x => h("th", null, x)))),
      h("tbody", null, d.plants.map((p, i) => h("tr", null, h("td", null, `${p.werks} ${p.plant_name}`),
        h("td", null, plantRows[i].minbe), h("td", null, plantRows[i].eisbe), h("td", null, badge(p.vprsv, p.vprsv)),
        h("td", null, priceText(p.vprsv === "S" ? p.stprs : p.verpr, p.peinh), " ",
          h("a", { href: `#/MR21?id=${enc(d.matnr)}&werks=${p.werks}` }, "change (MR21)"))))));
    const missing = S.meta.plants.filter(p => !d.plants.find(x => x.werks === p.werks));
    const ext = missing.length ? (() => {
      const w = sel(missing.map(p => [p.werks, `${p.werks} ${p.name}`]), missing[0].werks, { w: "l" });
      const v = sel([["V", "V Moving average"], ["S", "S Standard"]], d.plants[0] ? d.plants[0].vprsv : "V", { w: "m" });
      const pr = inp({ value: "0.00", w: "m" });
      return panel("Extend to another plant", grid(field("Plant", w), field("Price control", v), field("Price", pr)),
        h("div.row-actions", null, h("button.btn", { type: "button", on: { click: async () => {
          const r = await run(() => api(`/api/material/${enc(d.matnr)}/extend`, { werks: w.value, vprsv: v.value, price: val(pr) }));
          if (r) { msg("S", r.message); await App.loadMaterials(); exec(); } } } }, "Extend")));
    })() : null;
    out.append(panel("Basic data", grid(field("Material", inp({ value: d.matnr, readonly: true, w: "m" })),
      field("Description", maktx, { req: true }), field("Material group", matkl), field("Base unit", inp({ value: d.meins, readonly: true, w: "s" })))),
      panel("MRP 1 (per plant)", h("div.items-wrap", null, t)), ext);
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, { label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api(`/api/material/${enc(d.matnr)}/change`, { maktx: val(maktx), matkl: up(matkl),
        plants: plantRows.map(p => ({ werks: p.werks, minbe: val(p.minbe), eisbe: val(p.eisbe) })) }));
      if (r) { msg("S", r.message); App.loadMaterials(); } } }]);
  };
  execBar(exec);
  m.addEventListener("keydown", e => { if (e.key === "Enter") exec(); });
  if (params.id) exec();
}});

register("MM03", { title: "Display Material", async render(app, params) {
  const m = matInput(params.id || "");
  const out = result();
  app.append(panel("Initial screen", grid(field("Material", m, { req: true }))), out);
  const exec = async () => {
    const d = await loadMat(m);
    if (!d) return;
    msg("", "");
    out.innerHTML = "";
    out.append(h("div.panel", null, h("div.obj-header", null, [["Material", d.matnr], ["Description", d.maktx],
      ["Material type", `${d.mtart} ${d.mtart_text}`], ["Base unit", d.meins], ["Material group", d.matkl || "\u2013"],
      ["Valuation class", d.bklas], ["Created", `${fmtDate(d.ersda)} by ${d.ernam}`]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
    out.append(alv({ title: "Plant data / Accounting 1", rows: d.plants, columns: [
      { key: "werks", label: "Plant" }, { key: "plant_name", label: "Name" },
      { key: "vprsv", label: "Price ctrl", render: r => badge(r.vprsv === "V" ? "V Moving avg" : "S Standard", r.vprsv) },
      { key: "verpr", label: "Moving avg. price", type: "amt" }, { key: "stprs", label: "Standard price", type: "amt" },
      { key: "peinh", label: "Price unit", type: "int" }, { key: "lbkum", label: "Total stock", type: "qty" },
      { key: "salk3", label: "Total value", type: "amt", sum: true }, { key: "minbe", label: "Reorder point", type: "qty" },
      { key: "eisbe", label: "Safety stock", type: "qty" },
      { key: "x", label: "", render: r => h("span", null, h("a", { href: `#/CKM3?id=${enc(d.matnr)}&werks=${r.werks}` }, "price history"), " \u00B7 ",
        h("a", { href: `#/MMBE?id=${enc(d.matnr)}` }, "stock")) }] }));
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, { label: "Change (MM02)", onClick: () => go("MM02", { id: d.matnr }) },
      { label: "Stock overview", onClick: () => go("MMBE", { id: d.matnr }) }]);
  };
  execBar(exec);
  m.addEventListener("keydown", e => { if (e.key === "Enter") exec(); });
  if (params.id) exec();
}});

// ================================================================== MR21 / CKM3
register("MR21", { title: "Price Change: Overview Screen", async render(app, params) {
  const m = matInput(params.id || ""), w = plantInput(params.werks || "1000");
  const np = inp({ w: "m" }), pu = inp({ w: "s" }), b = inp({ type: "date", value: today(), w: "m" });
  const info = h("div");
  app.append(panel("Selection", grid(field("Material", m, { req: true }), field("Plant", w, { req: true }), field("Posting date", b))),
    panel("New price", grid(field("New price", np, { req: true }), field("Price unit", pu)), info));
  let cur = null;
  const load = async () => {
    const d = await loadMat(m);
    if (!d) return;
    cur = d.plants.find(p => p.werks === up(w));
    info.innerHTML = "";
    if (!cur) return msg("E", `Material ${d.matnr} not maintained in plant ${up(w)}`, "M7", "001");
    const price = cur.vprsv === "S" ? cur.stprs : cur.verpr;
    pu.value = cur.peinh;
    info.append(h("div.obj-header", { style: { padding: "10px 0 0" } }, [["Price control", cur.vprsv === "S" ? "S Standard" : "V Moving average"],
      ["Current price", priceText(price, cur.peinh)], ["Total stock", `${fmtQty(cur.lbkum)} ${d.meins}`],
      ["Total value", `${fmtAmt(cur.salk3)} ${S.meta.currency}`]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v)))));
    const prev = h("div.note", { style: { marginTop: "8px" } });
    const upd = () => { const p = parseFloat(np.value), u = parseInt(pu.value) || 1;
      prev.textContent = isNaN(p) ? "" : `Revaluation: ${fmtAmt(cur.lbkum * p / u - cur.salk3)} ${S.meta.currency} ` +
        `(stock account vs. 281500 Revaluation)`; };
    np.oninput = pu.oninput = upd;
    info.append(prev);
    msg("", "");
  };
  toolbar([{ label: "Read", key: "F8", onClick: load }, { label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!cur) await load();
    if (!cur) return;
    const r = await run(() => api("/api/pricechange", { matnr: up(m), werks: up(w), price: val(np), peinh: val(pu), budat: b.value }));
    if (r) { r.belnr ? msgLink("S", r.message + ` (revaluation ${fmtAmt(r.revaluation)})`, "Display", "FB03", { id: r.belnr, year: r.gjahr }) : msg("S", r.message); load(); }
  } }]);
  if (params.id) load();
}});

register("CKM3", { title: "Material Price Analysis (Price History)", async render(app, params) {
  const m = matInput(params.id || ""), w = plantInput(params.werks || "1000");
  const out = result();
  app.append(panel("Selection", grid(field("Material", m, { req: true }), field("Plant", w, { req: true }))), out);
  const exec = async () => {
    if (!up(m)) return msg("E", "Enter a material");
    const rows = await run(() => api(`/api/pricehistory?matnr=${enc(up(m))}&werks=${enc(up(w))}`));
    if (!rows) return;
    out.innerHTML = "";
    if (rows.length > 1) out.append(h("div.panel", null, h("h2", null, "Price over time"), h("div.panel-body", null, priceChart(rows))));
    out.append(alv({ title: "Price changes", rows: rows.slice().reverse(), columns: [
      { key: "budat", label: "Date", type: "date" }, { key: "ref", label: "Document / MvT" }, { key: "reason", label: "Reason" },
      { key: "old_price", label: "Old price", type: "amt" }, { key: "new_price", label: "New price", type: "amt" },
      { key: "peinh", label: "per", type: "int" }, { key: "lbkum", label: "Stock after", type: "qty" },
      { key: "salk3", label: "Value after", type: "amt" }] }));
    msg("S", `${rows.length} price changes`);
  };
  execBar(exec);
  if (params.id) exec();
}});

function priceChart(rows) {
  const W = 900, H = 220, P = { l: 60, r: 16, t: 12, b: 28 };
  const pts = rows.map(r => ({ d: new Date(r.budat).getTime(), p: r.new_price }));
  const x0 = Math.min(...pts.map(p => p.d)), x1 = Math.max(...pts.map(p => p.d)) || x0 + 1;
  let y0 = Math.min(...pts.map(p => p.p)), y1 = Math.max(...pts.map(p => p.p));
  const pad = (y1 - y0) * 0.15 || y1 * 0.05 || 1; y0 -= pad; y1 += pad;
  const X = d => P.l + (d - x0) / ((x1 - x0) || 1) * (W - P.l - P.r);
  const Y = v => P.t + (1 - (v - y0) / (y1 - y0)) * (H - P.t - P.b);
  let path = "";
  pts.forEach((p, i) => { path += (i ? `L${X(p.d)},${Y(i ? pts[i - 1].p : p.p)}L` : "M") + `${X(p.d)},${Y(p.p)}`; });
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.style.width = "100%"; svg.style.maxHeight = "240px";
  let inner = "";
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4;
    inner += `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e5e5e5"/>` +
      `<text x="${P.l - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="#6a6d70">${fmtAmt(v)}</text>`; }
  [x0, (x0 + x1) / 2, x1].forEach(d => { inner += `<text x="${X(d)}" y="${H - 8}" font-size="11" text-anchor="middle" fill="#6a6d70">${fmtDate(new Date(d).toISOString())}</text>`; });
  inner += `<path d="${path}" fill="none" stroke="#0a6ed1" stroke-width="2"/>`;
  pts.forEach(p => { inner += `<circle cx="${X(p.d)}" cy="${Y(p.p)}" r="3" fill="#0a6ed1"><title>${fmtDate(new Date(p.d).toISOString())}: ${fmtAmt(p.p)}</title></circle>`; });
  svg.innerHTML = inner;
  return svg;
}

// ================================================================== ME21N / ME23N / ME2M
register("ME21N", { title: "Create Purchase Order", async render(app) {
  const lifnr = inp({ list: "dl-lifnr", upper: true, w: "m" });
  const vname = h("span.hint");
  lifnr.addEventListener("change", () => { const v = S.meta.vendors.find(x => x.lifnr === up(lifnr)); vname.textContent = v ? v.name : ""; });
  const bedat = inp({ type: "date", value: today(), w: "m" });
  const items = [];
  const box = h("div.panel");
  app.append(panel("Header", grid(field("Vendor", h("span.split", null, lifnr, vname), { req: true }), field("Doc. date", bedat))), box);
  const add = () => { const l = items[items.length - 1] || {}; items.push({ matnr: "", menge: "", netpr: "", peinh: "1", werks: l.werks || "1000", lgort: l.lgort || "" }); draw(); };
  function draw() {
    box.innerHTML = "";
    const tb = h("tbody");
    items.forEach((it, i) => {
      const txt = h("span", null, App.matText(it.matnr)), un = h("span", null, App.matUnit(it.matnr));
      const valEl = h("span");
      const calc = () => { const v = parseFloat(it.menge) * parseFloat(it.netpr) / (parseInt(it.peinh) || 1); valEl.textContent = isNaN(v) ? "" : fmtAmt(v); };
      const s = (k, u) => e => { it[k] = u ? e.target.value.trim().toUpperCase() : e.target.value; calc(); };
      const mi = matInput(it.matnr, e => { it.matnr = up(e.target); txt.textContent = App.matText(it.matnr); un.textContent = App.matUnit(it.matnr); });
      mi.addEventListener("input", s("matnr", true));
      tb.append(h("tr", null, h("td.ln", null, String((i + 1) * 10)), h("td", null, mi), h("td", null, txt),
        h("td", null, inp({ value: it.menge, w: "s", oninput: s("menge") })), h("td", null, un),
        h("td", null, inp({ value: it.netpr, w: "m", oninput: s("netpr") })), h("td", null, inp({ value: it.peinh, w: "s", oninput: s("peinh") })),
        h("td", null, inp({ value: it.werks, w: "s", list: "dl-plant", upper: true, oninput: s("werks", true) })),
        h("td", null, inp({ value: it.lgort, w: "s", list: App.slocList(it.werks), upper: true, oninput: s("lgort", true) })),
        h("td.num", null, valEl),
        h("td", null, h("button.alv-tb-btn", { type: "button", on: { click: () => { items.splice(i, 1); draw(); } } }, "\u2715"))));
      calc();
    });
    box.append(h("div.panel-head", null, "Item Overview", h("span.spacer"), h("button.btn.ghost", { type: "button", on: { click: add } }, "+ Add item")),
      h("div.items-wrap", null, h("table.grid.items", null, h("thead", null, h("tr", null,
        ["Itm", "Material", "Short Text", "PO Quantity", "OUn", "Net Price", "Per", "Plant", "SLoc", "Net value", ""].map(x => h("th", null, x)))), tb)));
  }
  add();
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/po", { lifnr: up(lifnr), bedat: bedat.value, items: items.filter(i => i.matnr) }));
    if (r) { msgLink("S", r.message, "Goods receipt", "MIGO", { po: r.ebeln }); items.length = 0; add(); }
  } }]);
}});

register("ME23N", { title: "Display Purchase Order", async render(app, params) {
  const e = inp({ value: params.id || "", w: "m" });
  const out = result();
  app.append(panel("Purchase order", grid(field("Purchase order", e, { req: true }))), out);
  const exec = async () => {
    if (!val(e)) return msg("E", "Enter a purchase order number");
    const po = await run(() => api("/api/po/" + enc(val(e))));
    if (!po) return;
    msg("", "");
    out.innerHTML = "";
    const total = po.items.reduce((a, i) => a + i.value, 0);
    out.append(h("div.panel", null, h("div.obj-header", null, [["Standard PO", po.ebeln], ["Vendor", `${po.lifnr} ${po.vendor_name}`],
      ["Doc. date", fmtDate(po.bedat)], ["Created by", po.ernam], ["Net value", `${fmtAmt(total)} ${S.meta.currency}`]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
    out.append(alv({ title: "Items", rows: po.items, columns: [
      { key: "ebelp", label: "Itm", type: "int" }, { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) },
      { key: "maktx", label: "Short Text" }, { key: "menge", label: "PO Qty", type: "qty" }, { key: "meins", label: "OUn" },
      { key: "netpr", label: "Net Price", type: "amt" }, { key: "peinh", label: "Per", type: "int" },
      { key: "werks", label: "Plnt" }, { key: "lgort", label: "SLoc" }, { key: "wemng", label: "Delivered", type: "qty" },
      { key: "open", label: "Still to deliv.", type: "qty" }, { key: "value", label: "Net value", type: "amt", sum: true },
      { key: "st", label: "Status", render: r => r.open > 0 ? badge("Open", "Q") : badge("Delivered", "U") }] }));
    if (po.history.length) out.append(h("div", { style: { height: "14px" } }), alv({ title: "Purchase Order History", rows: po.history,
      rowClass: r => r.canceled ? ".canceled" : "", columns: [
        { key: "bwart", label: "MvT" }, { key: "mblnr", label: "Material Doc.", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) },
        { key: "zeile", label: "Item", type: "int" }, { key: "budat", label: "Posting Date", type: "date" },
        { key: "qty", label: "Quantity", type: "qty", signed: true }, { key: "meins", label: "OUn" },
        { key: "dmbtr", label: "Amount in LC", type: "amt" }, { key: "lgpla", label: "Bin" }, { key: "usnam", label: "User" }] }));
    toolbar([{ label: "Execute", key: "F8", onClick: exec },
      po.items.some(i => i.open > 0) ? { label: "Goods receipt (MIGO)", primary: true, onClick: () => go("MIGO", { po: po.ebeln }) } : null]);
  };
  execBar(exec);
  e.addEventListener("keydown", x => { if (x.key === "Enter") exec(); });
  if (params.id) exec();
}});

register("ME2M", { title: "Purchasing Documents per Material", async render(app) {
  const open = h("input", { type: "checkbox", checked: true });
  const out = result();
  app.append(panel("Selection", h("label.checkbox", null, open, "Only open items (still to be delivered)")), out);
  const exec = async () => {
    const rows = await run(() => api("/api/pos?open=" + (open.checked ? 1 : 0)));
    if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ title: "Purchase order items", exportName: "ME2M", rows, columns: [
      { key: "ebeln", label: "Purch.Doc.", link: r => go("ME23N", { id: r.ebeln }) }, { key: "ebelp", label: "Item", type: "int" },
      { key: "bedat", label: "Doc. Date", type: "date" }, { key: "lifnr", label: "Vendor" }, { key: "vendor_name", label: "Name" },
      { key: "matnr", label: "Material" }, { key: "maktx", label: "Short Text" }, { key: "werks", label: "Plnt" },
      { key: "lgort", label: "SLoc" }, { key: "menge", label: "PO Qty", type: "qty" }, { key: "meins", label: "OUn" },
      { key: "wemng", label: "Delivered", type: "qty" }, { key: "open", label: "Still to deliv.", type: "qty" },
      { key: "netpr", label: "Net Price", type: "amt" },
      { key: "gr", label: "", render: r => r.open > 0 ? h("a", { href: `#/MIGO?po=${r.ebeln}` }, "GR \u2192") : "" }] }));
    msg("S", `${rows.length} items selected`);
  };
  execBar(exec); exec();
}});

// ================================================================== LX02 / LX03
register("LX02", { title: "Bin Stock (Quants) - FIFO View", async render(app, params) {
  const w = plantInput(params.werks || "1000"), l = inp({ value: params.lgort || "", upper: true, w: "s", list: App.slocList("1000") });
  const m = inp({ value: params.matnr || "", upper: true, w: "m", list: "dl-mat" }), b = inp({ value: params.lgpla || "", upper: true, w: "m" });
  const out = result();
  app.append(panel("Selection", grid(field("Plant", w), field("Storage location", l), field("Material", m), field("Storage bin", b))),
    h("div.note", { style: { marginBottom: "10px" } }, "Every goods receipt creates a quant with its goods receipt (GR) date. " +
      "Issues always take the quant with FIFO sequence 1 first (oldest GR date)."), out);
  const exec = async () => {
    const rows = await run(() => api(`/api/quants?werks=${enc(up(w))}&lgort=${enc(up(l))}&matnr=${enc(up(m))}&lgpla=${enc(up(b))}`));
    if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ title: "Quants", exportName: "LX02", rows, sumUnitKey: "meins", columns: [
      { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) }, { key: "maktx", label: "Description" },
      { key: "werks", label: "Plnt" }, { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Storage Bin" },
      { key: "insmk", label: "Stock type", render: r => stBadge(r.insmk) }, { key: "qty", label: "Quantity", type: "qty", sum: true },
      { key: "meins", label: "BUn" }, { key: "wdatu", label: "GR Date", type: "date" },
      { key: "age_days", label: "Age (days)", type: "int", cls: r => r.age_days > 90 ? "crit" : "" },
      { key: "fifo_seq", label: "FIFO seq.", type: "int", cls: r => r.fifo_seq === 1 ? "pos" : "" },
      { key: "mblnr", label: "GR Mat. Doc.", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) }] }));
    msg("S", `${rows.length} quants`);
  };
  execBar(exec); exec();
}});

register("LX03", { title: "Bin Status Report / Warehouse Map", async render(app, params) {
  const bm = S.meta.slocs.filter(s => s.bin_managed);
  const s = sel(bm.map(x => [`${x.werks}/${x.lgort}`, `${x.werks} / ${x.lgort} ${x.name}`]), params.sl || (bm[0] && `${bm[0].werks}/${bm[0].lgort}`), { w: "l" });
  const out = result();
  app.append(panel("Selection (bin-managed storage locations)", grid(field("Plant / SLoc", s))), out);
  const exec = async () => {
    const [werks, lgort] = s.value.split("/");
    const bins = await run(() => api(`/api/bins?werks=${werks}&lgort=${lgort}`));
    if (!bins) return;
    out.innerHTML = "";
    const cnt = st => bins.filter(b => b.status === st).length;
    const map = h("div.binmap", null, bins.map(b => h("div.bin." + b.status, { title: b.status, on: { click: async () => {
      const body = h("div", null, h("p", null, `Status: ${b.status}`), b.content.length ? h("table.grid", null,
        h("tbody", null, b.content.map(c => h("tr", null, h("td", null, c.matnr), h("td", null, c.maktx), h("td", null, stBadge(c.insmk)),
          h("td.num", null, `${fmtQty(c.qty)} ${c.meins}`))))) : h("p.muted", null, "Bin is empty"));
      const r = await App.dialog(`Storage bin ${b.lgpla}`, body, [{ label: "Close", value: () => null },
        { label: b.blocked ? "Unblock bin" : "Block bin", value: () => "toggle" }, { label: "Quants", primary: true, value: () => "q" }]);
      if (r === "q") go("LX02", { werks, lgort, lgpla: b.lgpla });
      if (r === "toggle") { const x = await run(() => api("/api/bin/block", { werks, lgort, lgpla: b.lgpla, blocked: !b.blocked }));
        if (x) { msg("S", x.message); App.S.binLists = {}; exec(); } }
    } } }, h("div.n", null, b.lgpla), b.content.map(c => h("div", null, `${c.matnr} \u00B7 ${fmtQty(c.qty)} ${c.meins} `, c.insmk !== "U" ? stBadge(c.insmk) : null)),
      !b.content.length ? h("div.muted", null, b.blocked ? "blocked" : "empty") : null)));
    out.append(h("div.panel", null, h("div.panel-head", null, `Warehouse map ${werks}/${lgort}`, h("span.spacer"),
      h("span.legend", null, h("span", null, h("i", { style: { background: "#107e3e" } }), `Occupied ${cnt("Occupied")}`),
        h("span", null, h("i", { style: { background: "#9fb3c8" } }), `Empty ${cnt("Empty")}`),
        h("span", null, h("i", { style: { background: "#bb0000" } }), `Blocked ${cnt("Blocked")}`))),
      h("div.panel-body", null, map)));
  };
  s.addEventListener("change", exec);
  execBar(exec); exec();
}});

// ================================================================== FB03
register("FB03", { title: "Display Accounting Document", async render(app, params) {
  const d = inp({ value: params.id || "", w: "m" }), y = inp({ value: params.year || today().slice(0, 4), w: "s" });
  const out = result();
  app.append(panel("Document", grid(field("Document number", d, { req: true }), field("Fiscal year", y))), out);
  const exec = async () => {
    if (!val(d)) return msg("E", "Enter a document number");
    const doc = await run(() => api(`/api/accdoc/${enc(val(y))}/${enc(val(d))}`));
    if (!doc) return;
    msg("", "");
    out.innerHTML = "";
    const deb = doc.items.filter(i => i.shkzg === "S").reduce((a, i) => a + i.dmbtr, 0);
    const cre = doc.items.filter(i => i.shkzg === "H").reduce((a, i) => a + i.dmbtr, 0);
    const mat = doc.awkey && /^49/.test(doc.awkey) ? doc.awkey.slice(0, 10) : null;
    out.append(h("div.panel", null, h("div.obj-header", null, [["Document number", doc.belnr], ["Company code", "1000"], ["Fiscal year", doc.gjahr],
      ["Document type", doc.blart], ["Doc. date", fmtDate(doc.bldat || doc.budat)], ["Posting date", fmtDate(doc.budat)], ["Period", doc.monat || ""],
      ["Currency", `${doc.waers || "EGP"}${doc.kursf && doc.kursf !== 100000 ? " @ " + (doc.kursf / 100000).toFixed(4) : ""}`],
      ["Reference", doc.xblnr || "-"], ["Transaction", doc.tcode || "-"], ["User", doc.usnam],
      ["Origin", mat ? h("a", { href: `#/MB03?id=${mat}&year=${doc.awkey.slice(10)}` }, "Mat. doc. " + mat) : doc.awkey],
      ["Reversed by", doc.stblg ? h("a", { href: `#/FB03?id=${doc.stblg}&year=${doc.gjahr}` }, doc.stblg) : "-"],
      ["Planned reversal", doc.stodt ? fmtDate(doc.stodt) : "-"],
      ["Debit = Credit", h("span", { class: Math.abs(deb - cre) < 0.005 ? "pos" : "neg" }, `${fmtAmt(deb)} = ${fmtAmt(cre)}`)]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))));
    toolbar([{ label: "Execute", key: "F8", onClick: exec }, !doc.stblg ? { label: "Reverse (FB08)", ghost: true, onClick: () => go("FB08", { id: doc.belnr, year: doc.gjahr }) } : null]);
    out.append(alv({ title: "Line items", rows: doc.items.map(i => ({ ...i, debit: i.shkzg === "S" ? i.dmbtr : null, credit: i.shkzg === "H" ? i.dmbtr : null,
      partner: i.lifnr || i.kunnr || i.anln1 || "", wrbtr_v: i.wrbtr !== null && i.wrbtr !== undefined ? i.wrbtr / 100 : null })),
      columns: [{ key: "buzei", label: "Itm", type: "int" }, { key: "bschl", label: "PK" }, { key: "koart", label: "AccTy" }, { key: "hkont", label: "G/L Acct" },
        { key: "txt", label: "Account Name" }, { key: "partner", label: "Vendor/Cust./Asset" },
        { key: "debit", label: "Debit", type: "amt", sum: true }, { key: "credit", label: "Credit", type: "amt", sum: true },
        { key: "wrbtr_v", label: "Amount in DC", type: "amt" }, { key: "mwskz", label: "Tx" }, { key: "kostl", label: "Cost ctr" }, { key: "aufnr", label: "Order" },
        { key: "zterm", label: "Terms" }, { key: "netdt", label: "Due", type: "date" }, { key: "augbl", label: "Clearing doc." },
        { key: "zuonr", label: "Assignment" }, { key: "ktosl", label: "Trans. key" },
        { key: "matnr", label: "Material" }, { key: "menge", label: "Quantity", type: "qty" }, { key: "sgtxt", label: "Text" }] }));
  };
  execBar(exec);
  if (params.id) exec();
}});

// ================================================================== OMJJ
register("OMJJ", { title: "Movement Types (Customizing - Display)", async render(app) {
  const KIND = { receipt: "Goods receipt (+)", issue: "Goods issue (\u2212)", transfer: "Transfer posting", stocktype: "Stock type change" };
  const VAL = { po: "PO price", price: "Material price", entered: "Entered amount / price", "": "not valuated" };
  app.append(alv({ title: "Movement types", rows: S.meta.movement_types.map(m => ({ ...m, kindt: KIND[m.kind], valt: VAL[m.value],
    stc: m.from_st ? `${m.from_st} \u2192 ${m.to_st}` : m.st_choice ? "selectable" : "U" })), columns: [
    { key: "bwart", label: "MvT" }, { key: "text", label: "Movement type text" }, { key: "kindt", label: "Type" },
    { key: "valt", label: "Valuation" }, { key: "offset", label: "Offset trans. key" }, { key: "ref", label: "Reference" },
    { key: "stc", label: "Stock type" }, { key: "reverse", label: "Reversal MvT" }] }),
  h("div.note", { style: { marginTop: "10px" } }, "Transaction keys (OBYC): BSX stock \u00B7 WRX GR/IR clearing \u00B7 VBR consumption \u00B7 " +
    "VNG scrapping \u00B7 INV inventory differences \u00B7 BSA initial entry \u00B7 ZOB receipt without PO \u00B7 PRD price differences \u00B7 " +
    "AUM transfer price differences \u00B7 UMB revaluation."));
}});

// ================================================================== MB5K
register("MB5K", { title: "Stock Consistency Check", async render(app) {
  const out = result(); app.append(out);
  const exec = async () => {
    const r = await run(() => api("/api/check"));
    if (!r) return;
    out.innerHTML = "";
    out.append(panel("Result",
      h("div", { style: { fontSize: "16px", marginBottom: "8px" }, class: r.ok ? "pos" : "neg" },
        r.ok ? "\u2714 Everything is consistent" : `\u2716 ${r.issues.length} inconsistencies found`),
      h("ul", null, h("li", null, `Material stock value (all plants): ${fmtAmt(r.stock_value)} ${S.meta.currency}`),
        h("li", null, `Balance of stock G/L accounts (BSX): ${fmtAmt(r.gl_balance)} ${S.meta.currency}`),
        h("li", null, "Quantity in bins (quants) = valuated stock for every material and plant"),
        h("li", null, "Every accounting document: debit = credit")),
      r.issues.length ? h("ul.neg", null, r.issues.map(i => h("li", null, i))) : null));
    msg(r.ok ? "S" : "E", r.ok ? "Stock, values and G/L accounts are consistent" : "Inconsistencies found");
  };
  execBar(exec); exec();
}});

// ================================================================== ZORG + aliases
register("ZORG", { title: "Enterprise Structure & Basic Master Data", async render(app, params) {
  const tabsDef = [["plants", "Plants (OX10)"], ["slocs", "Storage Locations (OX09)"], ["bins", "Storage Bins (LS01)"],
    ["vendors", "Vendors (XK01)"], ["kostl", "Cost Centers (KS01)"]];
  let tab = params.tab || "plants";
  const bar = h("div.tabs"), body = h("div.panel-body");
  app.append(h("div.panel", null, bar, body));
  const drawTabs = () => { bar.innerHTML = ""; tabsDef.forEach(([k, t]) => bar.append(h("button.tab" + (k === tab ? ".active" : ""),
    { type: "button", on: { click: () => { tab = k; drawTabs(); draw(); } } }, t))); };
  const createBtn = (label, fn) => h("div.row-actions", null, h("button.btn.primary", { type: "button", on: { click: async () => {
    const r = await run(fn); if (r) { msg("S", r.message); await App.refreshMeta(); draw(); } } } }, label));
  async function draw() {
    body.innerHTML = "";
    if (tab === "plants") {
      const w = inp({ upper: true, w: "s" }), n = inp({ w: "l" }), c = inp({ w: "m" });
      body.append(grid(field("Plant", w, { req: true }), field("Name", n, { req: true }), field("City", c)),
        createBtn("Create plant", () => api("/api/plant", { werks: up(w), name: val(n), city: val(c) })),
        h("div", { style: { height: "12px" } }), alv({ title: "Plants", rows: S.meta.plants, columns: [
          { key: "werks", label: "Plant" }, { key: "name", label: "Name" }, { key: "city", label: "City" }] }));
    } else if (tab === "slocs") {
      const w = plantInput("1000"), l = inp({ upper: true, w: "s" }), n = inp({ w: "l" }), b = h("input", { type: "checkbox" });
      body.append(grid(field("Plant", w, { req: true }), field("Storage location", l, { req: true }), field("Description", n, { req: true }),
        field("Bin-managed", h("label.checkbox", null, b, "Stock is managed in storage bins"))),
        createBtn("Create storage location", () => api("/api/sloc", { werks: up(w), lgort: up(l), name: val(n), bin_managed: b.checked })),
        h("div", { style: { height: "12px" } }), alv({ title: "Storage locations", rows: S.meta.slocs, columns: [
          { key: "werks", label: "Plant" }, { key: "lgort", label: "SLoc" }, { key: "name", label: "Description" },
          { key: "bin_managed", label: "Bin-managed", render: r => r.bin_managed ? badge("Yes", "U") : badge("No") }] }));
    } else if (tab === "bins") {
      const bm = S.meta.slocs.filter(s => s.bin_managed);
      const sl = sel(bm.map(x => [`${x.werks}/${x.lgort}`, `${x.werks} / ${x.lgort} ${x.name}`]), bm[0] && `${bm[0].werks}/${bm[0].lgort}`, { w: "l" });
      const pre = inp({ upper: true, w: "m", ph: "e.g. D-01-" }), from = inp({ value: "1", w: "s" }), to = inp({ value: "1", w: "s" });
      const bt = inp({ w: "m", value: "Rack" });
      const prev = h("span.hint");
      const names = () => { const a = parseInt(val(from)), z = parseInt(val(to)); const out = [];
        if (!isNaN(a) && !isNaN(z) && z >= a && z - a < 500) for (let i = a; i <= z; i++) out.push(up(pre) + String(i).padStart(2, "0"));
        return out; };
      [pre, from, to].forEach(x => x.addEventListener("input", () => { const n = names(); prev.textContent = n.length ? `${n.length} bins: ${n[0]} \u2026 ${n[n.length - 1]}` : ""; }));
      body.append(grid(field("Plant / SLoc", sl, { req: true }), field("Bin name prefix", pre, { req: true }),
        field("Number from", from), field("Number to", h("span.split", null, to, prev)), field("Bin type", bt)),
        createBtn("Create storage bins", () => { const [werks, lgort] = sl.value.split("/");
          return api("/api/bin", { werks, lgort, lgpla_list: names(), bin_type: val(bt) }); }),
        h("div.note", null, "Show the bins as a warehouse map with LX03."));
    } else if (tab === "vendors") {
      const v = inp({ upper: true, w: "m" }), n = inp({ w: "l" }), c = inp({ w: "m" });
      body.append(grid(field("Vendor", v, { req: true }), field("Name", n, { req: true }), field("City", c)),
        createBtn("Create vendor", () => api("/api/vendor", { lifnr: up(v), name: val(n), city: val(c) })),
        h("div", { style: { height: "12px" } }), alv({ title: "Vendors", rows: S.meta.vendors, columns: [
          { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "city", label: "City" }] }));
    } else {
      const k = inp({ upper: true, w: "m" }), n = inp({ w: "l" });
      body.append(grid(field("Cost center", k, { req: true }), field("Name", n, { req: true })),
        createBtn("Create cost center", () => api("/api/costcenter", { kostl: up(k), name: val(n) })),
        h("div", { style: { height: "12px" } }), alv({ title: "Cost centers", rows: S.meta.cost_centers, columns: [
          { key: "kostl", label: "Cost center" }, { key: "name", label: "Name" }] }));
    }
  }
  drawTabs(); draw();
}});
[["OX10", "plants", "Plants"], ["OX09", "slocs", "Storage Locations"], ["LS01", "bins", "Create Storage Bins"],
 ["XK01", "vendors", "Create Vendor"], ["KS01", "kostl", "Create Cost Center"]].forEach(([code, tab, title]) =>
  register(code, { title, render: () => go("ZORG", { tab }) }));

// ================================================================== ZCOM
register("ZCOM", { title: "Office Integration (COM) - Test Cockpit", async render(app) {
  const c = S.meta.com;
  const out = h("div");
  const pathIn = (ph) => inp({ w: "l", ph });
  const xl = pathIn("C:\\path\\file.xlsx"), pdf = pathIn("C:\\path\\file.pdf"), ppt = pathIn("C:\\path\\file.pptx");
  const to = inp({ w: "l", ph: "name@company.com" });
  const show = (title, content) => { out.innerHTML = ""; out.append(panel(title, content)); };
  const pre = t => h("pre", { style: { whiteSpace: "pre-wrap", maxHeight: "50vh", overflow: "auto", margin: 0 } }, t);
  app.append(panel("Status", h("div", { class: c.available ? "pos" : "neg" }, c.available ? "\u2714 " + c.reason : "\u2716 " + c.reason),
    h("p.note", null, "With NASCA (DRM), protected files are opened by the Office programs themselves through COM, so Python never " +
      "needs to read the encrypted bytes. Each test below starts the Office program in the background.")),
  panel("Excel", grid(field("Read Excel file", h("span.split", null, xl, h("button.btn", { type: "button", on: { click: async () => {
    msg("I", "Excel is reading the file...");
    const r = await run(() => api("/api/office/excel-read", { path: val(xl) }));
    if (r) { msg("S", `Sheet \u201C${r.sheet}\u201D: ${r.rows.length} rows (sheets: ${r.sheets.join(", ")})`);
      const rows = r.rows.slice(1, 500).map(x => Object.fromEntries(x.map((v, i) => ["c" + i, v])));
      show("Excel content (first 500 rows)", alv({ rows, columns: (r.rows[0] || []).map((hd, i) => ({ key: "c" + i, label: String(hd ?? `Col ${i + 1}`) })) })); }
  } } }, "Read"))),
    field("Write test workbook", h("button.btn", { type: "button", on: { click: async () => {
      const r = await run(() => api("/api/office/excel-export", { title: "COM_test", header: ["Material", "Description", "Qty"],
        rows: [["RM-1001", "Steel sheet", 125.5], ["SP-4001", "Ball bearing", 12]] }));
      if (r) msg("S", r.message); } } }, "Create & open in Excel")))),
  panel("PDF (read via Word)", grid(field("PDF file", h("span.split", null, pdf, h("button.btn", { type: "button", on: { click: async () => {
    msg("I", "Word is opening the PDF...");
    const r = await run(() => api("/api/office/pdf-read", { path: val(pdf) }));
    if (r) { msg("S", `${r.pages} pages read`); show("PDF text", pre(r.text)); } } } }, "Read text"))))),
  panel("PowerPoint", grid(field("Presentation", h("span.split", null, ppt, h("button.btn", { type: "button", on: { click: async () => {
    const r = await run(() => api("/api/office/ppt-read", { path: val(ppt) }));
    if (r) { msg("S", `${r.slides.length} slides read`); show("Slide texts", pre(r.slides.map(s => `--- Slide ${s.slide} ---\n${s.text}`).join("\n\n"))); } } } }, "Read text"))))),
  panel("Outlook", grid(field("Inbox", h("button.btn", { type: "button", on: { click: async () => {
    const r = await run(() => api("/api/office/inbox?count=15"));
    if (r) { msg("S", `${r.mails.length} mails read`); show("Newest mails", alv({ rows: r.mails, columns: [
      { key: "received", label: "Received" }, { key: "from", label: "From" }, { key: "subject", label: "Subject" },
      { key: "attachments", label: "Attachments", type: "int" }] })); } } } }, "Read newest 15 mails")),
    field("Draft a mail", h("span.split", null, to, h("button.btn", { type: "button", on: { click: async () => {
      const r = await run(() => api("/api/office/outlook-draft", { to: val(to), subject: "NERP test mail",
        html: "<p>This mail was created by NERP through Outlook COM.</p>" }));
      if (r) msg("S", r.message); } } }, "Open draft"))))),
  out);
}});
})();
