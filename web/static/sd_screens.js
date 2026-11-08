/* MM Core - Sales & distribution (SD) screens */
"use strict";
(() => {
const { h, $, $$, api, msg, run, field, inp, sel, val, up, alv, register, go, toolbar,
  fmtQty, fmtAmt, fmtDate, fmtShort, today, enc } = App;

const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const out = () => h("div");
const gap = () => h("div", { style: { height: "12px" } });
const card = (t, sub, ...b) => h("div.card", null, h("h3", null, t), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...b));
const kpi = (l, v, s, goTo, cls) => h("div.kpi", { on: goTo ? { click: () => go(goTo) } : null }, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const attrs = list => h("div.obj-header", null, list.map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v))));
function msgLink(type, text, label, tcode, params) {
  msg(type, text);
  if (!label) return;
  const a = h("a", { href: "#", style: { marginLeft: "10px" } }, label);
  a.addEventListener("click", e => { e.preventDefault(); go(tcode, params); });
  $("#status-msg").append(a);
}
function tabsUI(list) {
  const bar = h("div.tabs"), page = h("div.panel-body");
  const show = i => { $$(".tab", bar).forEach((x, j) => x.classList.toggle("active", i === j)); page.innerHTML = ""; page.append(list[i][1]); };
  list.forEach(([t], i) => bar.append(h("button.tab", { type: "button", on: { click: () => show(i) } }, t)));
  if (list.length) show(0);
  return h("div.panel", null, bar, page);
}
function bars(items, labelFn, valFn) {
  const max = Math.max(...items.map(i => Math.abs(valFn(i))), 1);
  return h("div", null, items.map(i => h("div.hbar", null, h("span.lbl", { title: labelFn(i) }, labelFn(i)),
    h("span.track", null, h("span.fill", { style: { width: Math.abs(valFn(i)) / max * 100 + "%", display: "block" } })), h("span.num", null, fmtShort(valFn(i))))));
}
const execBar = (fn, extra) => toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }, ...(extra || [])]);

let SM = null;
async function meta(force) {
  if (!SM || force) {
    SM = await api("/api/sd/meta");
    App.datalist("dl-sd-kunnr", SM.customers.map(c => [c.kunnr, `${c.kunnr} ${c.name}`]));
    App.datalist("dl-sd-matnr", SM.materials.map(m => [m.matnr, `${m.matnr} ${m.maktx}`]));
  }
  return SM;
}
const opts = (o, empty) => [...(empty ? [["", "-"]] : []), ...Object.entries(o).map(([k, v]) => [k, `${k} ${typeof v === "string" ? v : v.text}`])];
const docLink = v => {
  const n = String(v || "");
  if (n.startsWith("8")) return go("VL03N", { id: n });
  if (n.startsWith("9")) return go("VF03", { id: n });
  return go("VA03", { id: n });
};
const gb = s => s === "C" ? badge("Completed", "U") : s === "B" ? badge("In process", "Q") : badge("Open", "");
const cm = s => s === "B" ? badge("Credit block", "B") : s === "D" ? badge("Released", "U") : s === "A" ? badge("OK", "U") : "";

// ================================================================== cockpit & process
register("ZSD_COCKPIT", { title: "Sales Cockpit - Orders, Revenue, Margin, Service Level & Credit", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: SM.period.d1, w: "m" }), d2 = inp({ type: "date", value: SM.period.d2, w: "m" }), body = out();
  app.append(panel("Period", grid(field("From", d1), field("To", d2))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/sd/cockpit?d1=${d1.value}&d2=${d2.value}`)); if (!d) return;
    body.innerHTML = ""; const k = d.kpi;
    body.append(h("div.kpis", null,
      kpi("Incoming orders", fmtShort(k.incoming), `${k.orders} orders`, "VA05"),
      kpi("Order backlog", fmtShort(k.backlog), "not yet delivered", "V.15"),
      kpi("Delivered, not billed", fmtShort(k.delivered_not_billed), "billing due list", "VF04", k.delivered_not_billed ? "crit" : "pos"),
      kpi("Net revenue", fmtShort(k.revenue), "invoices - credits - returns", "MCTA"),
      kpi("Gross margin", k.margin_pct + " %", fmtShort(k.margin) + " EGP", "MCTC", k.margin_pct < 25 ? "crit" : "pos"),
      kpi("Discount rate", k.discount_pct + " %", "deductions / gross", "V/LD", k.discount_pct > 5 ? "crit" : ""),
      kpi("OTIF", k.otif === null ? "-" : k.otif + " %", `fill rate ${k.fill_rate ?? "-"} % · lead time ${k.lead_time ?? "-"} d`, "ZSLM", k.otif < 90 ? "crit" : "pos"),
      kpi("Quotation hit rate", k.hit_rate === null ? "-" : k.hit_rate + " %", `pipeline ${fmtShort(k.pipeline)}`, "ZSD_PIPE"),
      kpi("Returns", k.returns_pct + " %", "of net revenue", "ZRET_MON", k.returns_pct > 2 ? "crit" : "pos"),
      kpi("Samples (free goods)", fmtShort(k.samples), "cost at goods issue", "ZSD_SAMPLES"),
      kpi("Credit blocked", fmtShort(k.credit_blocked), `${k.credit_blocked_n} document(s)`, "VKM1", k.credit_blocked_n ? "neg" : "pos"),
      kpi("DSO", k.dso + " days", "open receivables / sales", "F.31", k.dso > 60 ? "crit" : "pos")));
    body.append(h("div.cards", null,
      card("Top customers", "net revenue and margin", alv({ compact: true, rows: d.top_customers, columns: [
        { key: "key", label: "Customer", link: r => go("ZXD03_LF", { id: r.key }) }, { key: "name", label: "Name" }, { key: "net", label: "Net revenue", type: "amt", sum: true },
        { key: "margin", label: "Margin", type: "amt", sum: true }, { key: "margin_pct", label: "Margin %", type: "amt" }, { key: "returns", label: "Returns", type: "amt" }] })),
      card("Top materials", null, alv({ compact: true, rows: d.top_materials, columns: [
        { key: "key", label: "Material" }, { key: "name", label: "Description" }, { key: "qty", label: "Qty", type: "qty" }, { key: "net", label: "Net revenue", type: "amt", sum: true },
        { key: "margin_pct", label: "Margin %", type: "amt", cls: r => r.margin_pct < 25 ? "crit" : "pos" }] })),
      card("Credit exposure (GCIS)", "limit utilisation", alv({ compact: true, rows: d.credit, columns: [
        { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "klimk", label: "Limit", type: "amt" }, { key: "exposure", label: "Exposure", type: "amt" },
        { key: "utilization", label: "Used %", type: "amt", cls: r => r.utilization > 90 ? "neg" : r.utilization > 70 ? "crit" : "pos" }, { key: "overdue_days", label: "Overdue d", type: "int", cls: r => r.overdue_days > 30 ? "neg" : "" }] })),
      card("Service level (SLM)", "OTIF per delivery item", alv({ compact: true, rows: d.service.lines, columns: [
        { key: "delivery", label: "Delivery", link: r => go("VL03N", { id: r.delivery }) }, { key: "name", label: "Customer" }, { key: "matnr", label: "Material" },
        { key: "requested", label: "Requested", type: "date" }, { key: "shipped", label: "Shipped", type: "date" },
        { key: "otif", label: "OTIF", render: r => r.otif ? badge("OTIF", "U") : badge(r.on_time ? "Not in full" : "Late", "B") }] })),
      card("Sales plan vs actual (KE11)", "current month", d.plan_vs_actual.length ? alv({ compact: true, rows: d.plan_vs_actual, columns: [
        { key: "matnr", label: "Material" }, { key: "plan", label: "Plan", type: "amt", sum: true }, { key: "actual", label: "Actual", type: "amt", sum: true }] }) : h("p.muted", null, "No plan for this month"))));
    msg("S", `Sales cockpit ${fmtDate(d1.value)} - ${fmtDate(d2.value)}`);
  };
  execBar(exec, [{ label: "Process map", ghost: true, onClick: () => go("ZSD_PROCESS") }]); exec();
} });

register("ZSD_PROCESS", { title: "Order-to-Cash Process Map", async render(app) {
  const step = (n, t, codes, d) => h("div.card", null, h("h3", null, `${n}. ${t}`), h("div.sub", null, d), h("div.body", null, codes.map(c => h("a.btn.ghost", { href: "#/" + c, style: { margin: "2px" } }, c))));
  app.append(panel(null, h("p", null, "From the first customer contact to the cash: pricing by condition records, availability and credit check in the order, delivery with goods issue (cost of sales), billing to FI and CO-PA, payment. Returns, credit / debit memos, samples and after-sales service are part of the same flow.")),
    h("div.cards", null,
      step(1, "Master data & prices", ["XD01", "VD51", "VB01", "VK11", "V/LD", "VB21"], "customer, customer material, exclusion, condition records, promotions"),
      step(2, "Pre-sales", ["VC01N", "VA11", "VA21", "VA25", "ZSD_PIPE"], "activities, inquiries, quotations with probability"),
      step(3, "Sales order", ["VA01", "VA02", "VA03", "V.02"], "pricing, ATP + schedule lines, credit check, incompletion"),
      step(4, "Credit", ["VKM1", "F.31", "FD33"], "dynamic credit check, release by the credit manager"),
      step(5, "Shipping", ["VL10A", "VL01N", "VL02N", "VL06O"], "picking, goods issue 601, equipment for serial numbers"),
      step(6, "Billing", ["VF04", "VF01", "VF03", "VF11", "ZEINV"], "FI revenue + VAT + receivable, CO-PA, e-invoice"),
      step(7, "Cash", ["F-28", "FBL5N", "F150"], "incoming payment, open items, dunning"),
      step(8, "Exceptions", ["ZRETURN", "ZRET_MON", "VA01", "ZSD_SAMPLE"], "returns, credit / debit memos, free samples"),
      step(9, "Service", ["IE03", "IW51", "IW31", "DP90", "ZWR01"], "warranty check, service order, resource-related billing"),
      step(10, "Monitor", ["ZSD_COCKPIT", "MCTA", "MCTC", "ZSLM", "KE30"], "revenue, margin, OTIF, credit, profitability")));
} });

// ================================================================== sales documents
function vaCreate(tcode, title, auart, kind) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const types = kind === "pre" ? ["IN", "QT"] : kind === "ret" ? ["RE", "CR", "DR"] : ["OR", "RO", "ZSP", "FD", "ZWR", "CR", "DR", "RE"];
    const f = { auart: sel(types.map(t => [t, `${t} ${SM.doc_types[t].text}`]), auart, { w: "xl" }), kunnr: inp({ value: params.kunnr || "", list: "dl-sd-kunnr", upper: true, w: "m" }),
      kunwe: inp({ upper: true, w: "m", ph: "= sold-to" }), bstnk: inp({ w: "l" }), audat: inp({ type: "date", value: today(), w: "m" }), vdatu: inp({ type: "date", w: "m" }),
      vgbel: inp({ value: params.ref || "", w: "m", ph: "inquiry / quotation / billing doc." }), augru: sel(opts(SM.reasons), auart === "FD" ? "001" : auart === "ZWR" ? "301" : "", { w: "xl" }),
      prob: inp({ type: "number", value: 50, w: "s" }) };
    const lines = Array.from({ length: 4 }, () => ({ matnr: inp({ list: "dl-sd-matnr", upper: true, w: "m" }), qty: inp({ type: "number", w: "s" }), price: inp({ type: "number", w: "s", ph: "auto" }), disc: inp({ type: "number", w: "s", ph: "%" }) }));
    const sim = out();
    app.append(panel("Header", grid(field("Order type", f.auart), field("Sold-to party", f.kunnr), field("Ship-to party", f.kunwe), field("Customer reference (PO)", f.bstnk),
      field("Document date", f.audat), field("Req. delivery date", f.vdatu), field("With reference to", f.vgbel), field("Order reason", f.augru),
      kind === "pre" ? field("Probability %", f.prob) : null)),
      panel("Items (leave empty to copy all items of the reference)", h("table.grid", null, h("thead", null, h("tr", null, ["Item", "Material", "Order qty", "Price (manual)", "Discount % (RA01)"].map(x => h("th", null, x)))),
        h("tbody", null, lines.map((l, i) => h("tr", null, h("td", null, String((i + 1) * 10)), h("td", null, l.matnr), h("td", null, l.qty), h("td", null, l.price), h("td", null, l.disc))))),
        h("p.muted", null, "Pricing uses condition records (VK11): customer price A305 before list price A304, scales, discounts, freight by Incoterms, 14 % VAT.")), sim);
    const items = () => lines.filter(l => up(l.matnr) && l.qty.value).map(l => ({ matnr: up(l.matnr), qty: l.qty.value, price: l.price.value || null, disc: l.disc.value || null,
      vgbel: f.vgbel.value || null }));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const b = { auart: f.auart.value, kunnr: up(f.kunnr), kunwe: up(f.kunwe), bstnk: val(f.bstnk), audat: f.audat.value, vdatu: f.vdatu.value || null, vgbel: val(f.vgbel) || null,
        augru: f.augru.value, prob: f.prob.value, items: items() };
      if (!b.items.length) delete b.items;
      const r = await run(() => api("/api/sd/order", b)); if (r) msgLink(r.type || "S", r.message, "Display", "VA03", { id: r.vbeln }); } },
      { label: "Pricing simulation", ghost: true, onClick: async () => {
        sim.innerHTML = "";
        for (const it of items()) {
          const r = await run(() => api(`/api/sd/price?kunnr=${enc(up(f.kunnr))}&matnr=${enc(it.matnr)}&qty=${it.qty}&date=${f.audat.value}${it.disc ? "&disc=" + it.disc : ""}`)); if (!r) return;
          sim.append(panel(`Pricing ${it.matnr} - procedure ${r.proc}`, alv({ compact: true, rows: r.conds, columns: [{ key: "kschl", label: "CnTy" }, { key: "text", label: "Name" },
            { key: "kbetr_txt", label: "Amount / rate" }, { key: "kwert", label: "Condition value", type: "amt" }] }),
            h("p", null, `Net ${fmtAmt(r.net)} · freight ${fmtAmt(r.freight)} · tax ${fmtAmt(r.tax)} · cost ${fmtAmt(r.cost)} · margin ${fmtAmt(r.net - r.cost)}`)));
        } } }]);
  } });
}
vaCreate("VA01", "Create Sales Order", "OR", "order");
vaCreate("VA11", "Create Inquiry", "IN", "pre");
vaCreate("VA21", "Create Quotation", "QT", "pre");
vaCreate("ZSD_SAMPLE", "Create Free-of-Charge Sample Delivery (FD)", "FD", "order");
vaCreate("ZSP01", "Create Spare Parts Order (ZSP)", "ZSP", "order");
vaCreate("ZWR01", "Create Warranty Replacement (ZWR)", "ZWR", "order");
vaCreate("ZRETURN", "Create Returns / Credit & Debit Memo Request", "RE", "ret");

function vaDisplay(tcode, title, change) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const v = inp({ value: params.id || "", w: "m" }), body = out();
    app.append(panel("Sales document", grid(field("Document", v, { req: true }))), body);
    const load = async () => {
      const d = await run(() => api(`/api/sd/order/${enc(val(v))}`)); if (!d) return;
      body.innerHTML = "";
      body.append(panel(null, attrs([["Document", `${d.vbeln} ${d.auart} ${d.type_text}`], ["Sold-to", `${d.kunnr} ${d.name}`], ["Ship-to", d.kunwe], ["PO", d.bstnk || "-"],
        ["Doc. date", fmtDate(d.audat)], ["Req. delivery", fmtDate(d.vdatu)], ["Net value", fmtAmt(d.netwr) + " EGP"], ["Tax", fmtAmt(d.mwsbk)],
        ["Pricing", d.kalsm], ["Incoterms", `${d.inco1 || "-"} ${d.inco2 || ""}`], ["Status", gb(d.gbstk)], ["Credit", cm(d.cmgst) || "-"],
        ["Blocks", `${d.faksk ? "billing " + d.faksk : ""} ${d.lifsk ? "delivery " + d.lifsk : ""}` || "-"], ["Reason", d.reason_text || "-"]]),
        d.credit_note ? h("p.crit", null, d.credit_note) : null, d.incomplete.length ? h("p.neg", null, "Incomplete: " + d.incomplete.join(", ")) : null));
      const condRows = d.items.flatMap(p => p.conditions.map(c => ({ ...c, posnr: p.posnr })));
      const schedRows = d.items.flatMap(p => p.schedule.map(s => ({ ...s })));
      body.append(tabsUI([
        ["Items", alv({ rows: d.items, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "kdmat", label: "Cust. material" }, { key: "arktx", label: "Description" },
          { key: "pstyv", label: "ItCa" }, { key: "kwmeng", label: "Order qty", type: "qty" }, { key: "confirmed", label: "Confirmed", type: "qty" }, { key: "delivered", label: "Delivered", type: "qty" },
          { key: "billed", label: "Billed", type: "qty" }, { key: "netpr", label: "Net price", type: "amt" }, { key: "netwr", label: "Net value", type: "amt", sum: true },
          { key: "freight", label: "Freight", type: "amt", sum: true }, { key: "mwsbp", label: "Tax", type: "amt", sum: true }, { key: "wavwr", label: "Cost", type: "amt", sum: true },
          { key: "margin", label: "Margin", type: "amt", sum: true }, { key: "abgru", label: "Rejected", render: r => r.abgru ? badge(SM.rejections[r.abgru] || r.abgru, "B") : "" }] })],
        ["Conditions", alv({ rows: condRows, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "stunr", label: "Step", type: "int" }, { key: "kschl", label: "CnTy" }, { key: "text", label: "Name" },
          { key: "kbetr_txt", label: "Amount" }, { key: "kwert", label: "Condition value", type: "amt" }, { key: "manual", label: "Manual", render: r => r.manual ? "✔" : "" }] })],
        ["Schedule lines (ATP)", alv({ rows: schedRows, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "etenr", label: "Line", type: "int" }, { key: "ettyp", label: "Cat." },
          { key: "edatu", label: "Delivery date", type: "date" }, { key: "mbdat", label: "Mat. avail. date", type: "date" }, { key: "wmeng", label: "Order qty", type: "qty" }, { key: "bmeng", label: "Confirmed", type: "qty" }] })],
        ["Document flow", alv({ rows: d.flow, columns: [{ key: "doc", label: "Document", link: r => docLink(r.doc) }, { key: "text", label: "Type" }, { key: "info", label: "Status / value" }] })],
        ["Credit", h("div.kpis", null, kpi("Credit limit", fmtAmt(d.klimk)), kpi("Open items", fmtAmt(d.exposure.open_items)), kpi("Open orders", fmtAmt(d.exposure.open_orders)),
          kpi("Total exposure", fmtAmt(d.exposure.total), d.klimk ? Math.round(d.exposure.total / d.klimk * 100) + " % used" : "no limit", null, d.klimk && d.exposure.total > d.klimk ? "neg" : "pos"))]]));
      const bt = [];
      if (d.cmgst === "B") bt.push({ label: "Release credit (VKM1)", primary: true, onClick: async () => { const r = await run(() => api(`/api/sd/order/${d.vbeln}/release`, {})); if (r) { msg("S", r.message); load(); } } });
      if (["C", "H"].includes(d.vbtyp) && d.gbstk !== "C" && SM.doc_types[d.auart].lfart) bt.push({ label: "Create delivery (VL01N)", primary: !bt.length, onClick: () => go("VL01N", { id: d.vbeln }) });
      if (["K", "L"].includes(d.vbtyp) && d.gbstk !== "C") bt.push({ label: "Bill (VF01)", primary: !bt.length, onClick: () => go("VF01", { id: d.vbeln }) });
      if (d.vbtyp === "B" && d.gbstk !== "C") bt.push({ label: "Create order from quotation", primary: true, onClick: () => go("VA01", { ref: d.vbeln, kunnr: d.kunnr }) });
      if (d.vbtyp === "A") bt.push({ label: "Create quotation", primary: true, onClick: () => go("VA21", { ref: d.vbeln, kunnr: d.kunnr }) });
      if (!change) bt.push({ label: "Change (VA02)", ghost: true, onClick: () => go("VA02", { id: d.vbeln }) });
      if (change) {
        const bst = inp({ value: d.bstnk || "", w: "l" }), lif = sel([["", "-"], ...Object.entries(SM.blocks).map(([k, t]) => [k, `${k} ${t}`])], d.lifsk || ""),
          fak = sel([["", "-"], ...Object.entries(SM.blocks).map(([k, t]) => [k, `${k} ${t}`])], d.faksk || ""),
          rej = d.items.map(p => ({ posnr: p.posnr, s: sel([["", "-"], ...Object.entries(SM.rejections).map(([k, t]) => [k, `${k} ${t}`])], p.abgru || "") }));
        body.prepend(panel("Change", grid(field("Customer reference", bst), field("Delivery block", lif), field("Billing block", fak), ...rej.map(r => field(`Reject item ${r.posnr}`, r.s))),
          h("p.muted", null, "A billing block 08 (credit memo request) must be removed by another person than the creator.")));
        bt.unshift({ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
          const r = await run(() => api(`/api/sd/order/${d.vbeln}/change`, { bstnk: val(bst), lifsk: lif.value, faksk: fak.value, items: rej.filter(x => x.s.value).map(x => ({ posnr: x.posnr, abgru: x.s.value })) }));
          if (r) { msg("S", r.message); load(); } } },
          { label: "Reschedule (V_V2)", ghost: true, onClick: async () => { const r = await run(() => api(`/api/sd/order/${d.vbeln}/reschedule`, { today: today() })); if (r) { msg("S", r.message); load(); } } });
      }
      toolbar(bt);
      if (!change) msg(d.cmgst === "B" ? "W" : "S", `${d.type_text} ${d.vbeln}${d.cmgst === "B" ? " is blocked for credit" : ""}`);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id) load();
  } });
}
vaDisplay("VA03", "Display Sales Document", false);
vaDisplay("VA02", "Change Sales Document", true);
register("VA13", { title: "Display Inquiry", render: (a, p) => go("VA03", p) });
register("VA23", { title: "Display Quotation", render: (a, p) => go("VA03", p) });

function listScreen(tcode, title, url, cols, filters) {
  register(tcode, { title, async render(app) {
    await meta();
    const body = out(); const fs = filters ? filters() : null;
    if (fs) app.append(panel("Selection", grid(...fs.fields)));
    app.append(body);
    const exec = async () => { const r = await run(() => api(url + (fs ? fs.query() : ""))); if (!r) return; body.innerHTML = ""; body.append(alv({ rows: r, columns: cols })); msg("S", `${r.length} entries`); };
    execBar(exec); exec();
  } });
}
const VA05_COLS = [{ key: "vbeln", label: "Document", link: r => go("VA03", { id: r.vbeln }) }, { key: "auart", label: "Type" }, { key: "type_text", label: "Description" },
  { key: "kunnr", label: "Sold-to" }, { key: "name", label: "Name" }, { key: "bstnk", label: "PO" }, { key: "audat", label: "Date", type: "date" }, { key: "vdatu", label: "Req. delivery", type: "date" },
  { key: "netwr", label: "Net value", type: "amt", sum: true }, { key: "gbstk", label: "Status", render: r => gb(r.gbstk) }, { key: "blocked", label: "Blocks", render: r => r.blocked ? badge(r.blocked, "B") : "" }];
listScreen("VA05", "List of Sales Documents", "/api/sd/orders", VA05_COLS, () => {
  const t = sel([["", "- all"], ...Object.keys(SM.doc_types).map(k => [k, `${k} ${SM.doc_types[k].text}`])], ""), k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), o = h("input", { type: "checkbox" });
  return { fields: [field("Document type", t), field("Customer", k), field("Open only", o)], query: () => `?auart=${t.value}&kunnr=${enc(up(k))}&open=${o.checked ? 1 : ""}` };
});
listScreen("VA25", "List of Quotations", "/api/sd/pipeline", [{ key: "vbeln", label: "Document", link: r => go("VA03", { id: r.vbeln }) }, { key: "auart", label: "Type" },
  { key: "name", label: "Customer" }, { key: "audat", label: "Date", type: "date" }, { key: "bnddt", label: "Valid to", type: "date" }, { key: "netwr", label: "Value", type: "amt", sum: true },
  { key: "prob", label: "Prob. %", type: "int" }, { key: "weighted", label: "Weighted", type: "amt", sum: true }, { key: "state", label: "Status", render: r => badge(r.state, r.state === "Won" ? "U" : r.state === "Expired" ? "B" : "Q") },
  { key: "followed", label: "Follow-on" }]);
register("ZSD_PIPE", { title: "Sales Pipeline (Inquiries & Quotations)", render: () => go("VA25") });
listScreen("V.15", "Backorders", "/api/sd/backorders", [{ key: "vbeln", label: "Order", link: r => go("VA03", { id: r.vbeln }) }, { key: "posnr", label: "Item", type: "int" },
  { key: "name", label: "Customer" }, { key: "matnr", label: "Material" }, { key: "kwmeng", label: "Order qty", type: "qty" }, { key: "on_time", label: "Confirmed on req. date", type: "qty" },
  { key: "confirmed", label: "Confirmed total", type: "qty" }, { key: "missing", label: "Not confirmed", type: "qty" }, { key: "vdatu", label: "Requested", type: "date" }, { key: "last_date", label: "Last confirmed date", type: "date" }]);
listScreen("VKM1", "Blocked SD Documents (Credit Management)", "/api/sd/blocked", [{ key: "vbeln", label: "Document", link: r => go("VA03", { id: r.vbeln }) }, { key: "auart", label: "Type" },
  { key: "name", label: "Customer" }, { key: "netwr", label: "Value", type: "amt", sum: true }, { key: "klimk", label: "Credit limit", type: "amt" }, { key: "exposure", label: "Exposure", type: "amt" },
  { key: "cmgst", label: "Credit", render: r => cm(r.cmgst) }, { key: "credit_note", label: "Reason" }, { key: "faksk", label: "Billing block" }, { key: "lifsk", label: "Delivery block" }]);
register("VKM3", { title: "Sales Documents Blocked for Credit", render: () => go("VKM1") });
listScreen("V.02", "Incomplete SD Documents", "/api/sd/incomplete", [{ key: "vbeln", label: "Document", link: r => go("VA02", { id: r.vbeln }) }, { key: "auart", label: "Type" },
  { key: "name", label: "Customer" }, { key: "audat", label: "Date", type: "date" }, { key: "missing", label: "Missing data" }]);
register("V_V2", { title: "Rescheduling of Sales Documents", async render(app) {
  const r = await run(() => api("/api/sd/backorders")); if (!r) return;
  app.append(alv({ rows: r, columns: [{ key: "vbeln", label: "Order", link: x => go("VA02", { id: x.vbeln }) }, { key: "matnr", label: "Material" }, { key: "kwmeng", label: "Qty", type: "qty" },
    { key: "on_time", label: "On time", type: "qty" }, { key: "last_date", label: "Last date", type: "date" },
    { key: "act", label: "", render: x => h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api(`/api/sd/order/${x.vbeln}/reschedule`, { today: today() })); if (y) msg("S", y.message); } } }, "Reschedule") }] }));
} });

// ================================================================== conditions
register("VK11", { title: "Create Condition Record", async render(app, params) {
  await meta();
  const k = sel(Object.entries(SM.cond_types).map(([x, t]) => [x, `${x} ${t.text}`]), params.kschl || "PR00", { w: "xl" }), tab = sel([], ""), body = out();
  const f = { kunnr: inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), matnr: inp({ list: "dl-sd-matnr", upper: true, w: "m" }), kbetr: inp({ type: "number", w: "s", step: "any" }),
    datab: inp({ type: "date", value: today(), w: "m" }), datbi: inp({ type: "date", value: "9999-12-31", w: "m" }) };
  const sc = Array.from({ length: 3 }, () => ({ from: inp({ type: "number", w: "s" }), kbetr: inp({ type: "number", w: "s", step: "any" }) }));
  const fill = () => { tab.innerHTML = ""; SM.cond_types[k.value].access.forEach(a => tab.append(h("option", { value: a }, `${a} ${SM.access[a]}`))); if (k.value === "ZLAB") tab.append(h("option", { value: "A304" }, "A304 Material")); };
  k.addEventListener("change", fill); fill();
  app.append(panel("Condition type and key combination", grid(field("Condition type", k), field("Key combination (table)", tab))),
    panel("Condition record", grid(field("Customer", f.kunnr), field("Material", f.matnr), field("Amount / % ", f.kbetr, { req: true }), field("Valid from", f.datab), field("Valid to", f.datbi))),
    panel("Scales (quantity from - amount)", h("table.grid", null, h("tbody", null, sc.map(s => h("tr", null, h("td", null, s.from), h("td", null, s.kbetr)))))), body);
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/sd/condition", { kschl: k.value, kotab: tab.value, kunnr: up(f.kunnr), matnr: up(f.matnr), kbetr: f.kbetr.value, datab: f.datab.value, datbi: f.datbi.value,
      scales: sc.map(s => ({ from: s.from.value, kbetr: s.kbetr.value })) })); if (r) msgLink("S", r.message, "Pricing report", "V/LD"); } }]);
} });
register("VK12", { title: "Change Condition Records", render: () => go("V/LD") });
register("V/LD", { title: "Pricing Report (Condition Records)", async render(app) {
  await meta();
  const k = sel([["", "- all"], ...Object.entries(SM.cond_types).map(([x, t]) => [x, `${x} ${t.text}`])], ""), d = inp({ type: "date", value: today(), w: "m" }), body = out();
  app.append(panel("Selection", grid(field("Condition type", k), field("Valid on", d))), body);
  const exec = async () => { const r = await run(() => api(`/api/sd/conditions?kschl=${k.value}&date=${d.value}`)); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "knumh", label: "Record", type: "int" }, { key: "kschl", label: "CnTy" }, { key: "text", label: "Name" }, { key: "kotab", label: "Table" },
      { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "rate", label: "Amount" },
      { key: "scales_txt", label: "Scales" }, { key: "datab", label: "From", type: "date" }, { key: "datbi", label: "To", type: "date" }, { key: "knuma", label: "Deal" },
      { key: "del", label: "", render: x => h("button.alv-tb-btn", { type: "button", on: { click: async () => { const y = await run(() => api("/api/sd/condition/delete", { knumh: x.knumh })); if (y) { msg("S", y.message); exec(); } } } }, "✕") }] }));
    msg("S", `${r.length} condition records`); };
  execBar(exec, [{ label: "Create (VK11)", ghost: true, onClick: () => go("VK11") }]); exec();
} });
register("VK13", { title: "Display Condition Records", render: () => go("V/LD") });
register("ZPRICE", { title: "Pricing Simulation", async render(app) {
  await meta();
  const k = inp({ value: "C1002", list: "dl-sd-kunnr", upper: true, w: "m" }), m = inp({ value: "FG-3001", list: "dl-sd-matnr", upper: true, w: "m" }), q = inp({ type: "number", value: 30, w: "s" }), body = out();
  app.append(panel("Customer / material / quantity", grid(field("Customer", k), field("Material", m), field("Quantity", q))), body);
  const exec = async () => { const r = await run(() => api(`/api/sd/price?kunnr=${enc(up(k))}&matnr=${enc(up(m))}&qty=${q.value}`)); if (!r) return; body.innerHTML = "";
    body.append(panel(`Pricing procedure ${r.proc}`, alv({ compact: true, rows: r.conds, columns: [{ key: "stunr", label: "Step", type: "int" }, { key: "kschl", label: "CnTy" }, { key: "text", label: "Name" },
      { key: "kbetr_txt", label: "Amount" }, { key: "kwert", label: "Value", type: "amt" }] })),
      h("div.kpis", null, kpi("Gross", fmtAmt(r.gross)), kpi("Discounts", fmtAmt(r.disc)), kpi("Net", fmtAmt(r.net)), kpi("Freight", fmtAmt(r.freight)), kpi("Tax", fmtAmt(r.tax)), kpi("Cost (VPRS)", fmtAmt(r.cost)),
        kpi("Margin", fmtAmt(r.net - r.cost), r.net ? Math.round((r.net - r.cost) / r.net * 100) + " %" : "", null, r.net - r.cost > 0 ? "pos" : "neg"))); };
  execBar(exec); exec();
} });
function custTable(tcode, title, rowsFn, cols, note) {
  register(tcode, { title, async render(app) { await meta(); app.append(note ? panel(null, h("p.muted", null, note)) : "", alv({ rows: rowsFn(), columns: cols })); } });
}
custTable("V/06", "Condition Types", () => Object.entries(SM.cond_types).map(([k, v]) => ({ k, ...v, access: v.access.join(" → ") })),
  [{ key: "k", label: "CnTy" }, { key: "text", label: "Name" }, { key: "kind", label: "Class" }, { key: "calc", label: "Calc." }, { key: "access", label: "Access sequence" }, { key: "scales", label: "Scales", render: r => r.scales ? "✔" : "" }],
  "Class B price, A discount, F freight, D tax, S statistical. Calculation C quantity, A percentage.");
custTable("V/08", "Pricing Procedures", () => Object.entries(SM.procs).map(([k, v]) => ({ k, steps: v.join(" → "), det: Object.entries(SM.proc_det).filter(([, p]) => p === k).map(([c]) => "customer proc. " + c).join(", ") })),
  [{ key: "k", label: "Procedure" }, { key: "steps", label: "Steps" }, { key: "det", label: "Determination (OVKK)" }]);
custTable("VKOA", "Revenue Account Determination", () => SM.revenue, [{ key: "ktgrd", label: "Customer AAG" }, { key: "ktgrm", label: "Material AAG" }, { key: "hkont", label: "Revenue account (ERL)" }],
  "Deductions ERS → 880000 · freight ERF → 805000 · service revenue → 810000 · output tax MWS → 175000.");
custTable("VOV8", "Sales Document Types, Item Categories, Billing Types", () => Object.entries(SM.doc_types).map(([k, v]) => ({ k, ...v, credit: v.credit ? "✔" : "", reason: v.reason ? "✔" : "" })),
  [{ key: "k", label: "Type" }, { key: "text", label: "Description" }, { key: "vbtyp", label: "Category" }, { key: "nr", label: "No. range" }, { key: "pstyv", label: "Item cat." }, { key: "lfart", label: "Delivery" },
    { key: "fkart", label: "Billing" }, { key: "faksk", label: "Billing block" }, { key: "credit", label: "Credit check" }, { key: "ref", label: "Ref. mandatory" }, { key: "reason", label: "Order reason" }]);

// ================================================================== shipping
listScreen("VL10A", "Sales Orders Due for Delivery", "/api/sd/duelist?until=" + new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10), [{ key: "vbeln", label: "Order", link: r => go("VA03", { id: r.vbeln }) },
  { key: "posnr", label: "Item", type: "int" }, { key: "name", label: "Customer" }, { key: "matnr", label: "Material" }, { key: "due", label: "Due qty", type: "qty", sum: true },
  { key: "blocked", label: "Block", render: r => r.blocked ? badge(r.blocked, "B") : "" }, { key: "act", label: "", render: r => r.blocked ? "" : h("button.btn.primary", { type: "button", on: { click: () => go("VL01N", { id: r.vbeln }) } }, "Deliver") }]);
register("VL01N", { title: "Create Outbound Delivery with Order Reference", async render(app, params) {
  const v = inp({ value: params.id || "", w: "m" }), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Shipping point 1000 · order reference", grid(field("Order", v, { req: true }), field("Selection date", d)), h("p.muted", null, "All confirmed schedule lines due until the selection date are copied. Credit / delivery blocks and incompletion are checked.")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/delivery", { vbeln: val(v), lfdat: d.value })); if (r) msgLink("S", r.message, "Pick & post GI", "VL02N", { id: r.vbeln }); } }]);
} });
function vlDisplay(tcode, title, change) {
  register(tcode, { title, async render(app, params) {
    const v = inp({ value: params.id || "", w: "m" }), body = out();
    app.append(panel("Delivery", grid(field("Delivery", v, { req: true }))), body);
    const load = async () => {
      const d = await run(() => api(`/api/sd/delivery/${enc(val(v))}`)); if (!d) return; body.innerHTML = "";
      body.append(panel(null, attrs([["Delivery", `${d.vbeln} (${d.lfart})`], ["Ship-to", `${d.kunnr} ${d.name}, ${d.city}`], ["Order", d.vgbel], ["Delivery date", fmtDate(d.lfdat)],
        ["Planned GI", fmtDate(d.wadat)], ["Actual GI", fmtDate(d.wadat_ist)], ["Picking", d.kostk === "C" ? badge("Picked", "U") : badge("Open", "")],
        ["Goods movement", d.wbstk === "C" ? badge("Posted " + (d.mblnr || ""), "U") : badge("Open", "Q")], ["Billing", d.fkstk === "C" ? badge("Billed", "U") : badge("Open", "")]])),
        alv({ rows: d.items, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "arktx", label: "Description" }, { key: "pstyv", label: "ItCa" },
          { key: "lfimg", label: "Delivery qty", type: "qty" }, { key: "pikmg", label: "Picked", type: "qty" }, { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Bin (FIFO)" }, { key: "cogs", label: "Cost (GI)", type: "amt", sum: true }] }));
      const bt = [];
      if (d.wbstk !== "C") {
        if (d.kostk !== "C") bt.push({ label: "Pick", ghost: true, onClick: async () => { const r = await run(() => api(`/api/sd/delivery/${d.vbeln}/pick`, {})); if (r) { msg("S", r.message); load(); } } });
        bt.unshift({ label: d.lfart === "LR" ? "Post goods receipt" : "Post goods issue", key: "F8", primary: true, onClick: async () => { const r = await run(() => api(`/api/sd/delivery/${d.vbeln}/gi`, { budat: today() })); if (r) { msg("S", r.message); load(); } } });
      } else {
        if (d.fkstk !== "C") bt.push({ label: "Billing (VF01)", primary: true, onClick: () => go("VF01", { id: d.vbeln }) });
        bt.push({ label: "Reverse GI (VL09)", ghost: true, onClick: async () => { const r = await run(() => api(`/api/sd/delivery/${d.vbeln}/reverse`, { budat: today() })); if (r) { msg("S", r.message); load(); } } });
      }
      toolbar(bt);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id) load();
  } });
}
vlDisplay("VL02N", "Change Outbound Delivery (Picking / Goods Issue)", true);
vlDisplay("VL03N", "Display Outbound Delivery", false);
register("VL09", { title: "Cancel Goods Issue for Delivery", render: (a, p) => go("VL02N", p) });
listScreen("VL06O", "Outbound Delivery Monitor", "/api/sd/deliveries", [{ key: "vbeln", label: "Delivery", link: r => go("VL03N", { id: r.vbeln }) }, { key: "lfart", label: "Type" },
  { key: "auart", label: "Order type" }, { key: "vgbel", label: "Order", link: r => go("VA03", { id: r.vgbel }) }, { key: "name", label: "Ship-to" }, { key: "vdatu", label: "Requested", type: "date" },
  { key: "wadat_ist", label: "GI date", type: "date" }, { key: "n", label: "Items", type: "int" }, { key: "wbstk", label: "GI", render: r => r.wbstk === "C" ? badge("Posted", "U") : badge("Open", "Q") },
  { key: "fkstk", label: "Billing", render: r => r.fkstk === "C" ? badge("Billed", "U") : ["FD", "ZWR"].includes(r.auart) ? badge("Free", "") : badge("Open", "Q") },
  { key: "on_time", label: "On time", render: r => r.wadat_ist ? (r.on_time ? badge("Yes", "U") : badge("Late", "B")) : "" }]);

// ================================================================== billing
listScreen("VF04", "Billing Due List", "/api/sd/billdue", [{ key: "ref", label: "Reference", link: r => docLink(r.ref) }, { key: "kind", label: "Kind" }, { key: "fkart", label: "Billing type" },
  { key: "name", label: "Customer" }, { key: "date", label: "Date", type: "date" }, { key: "value", label: "Net value", type: "amt", sum: true }, { key: "blocked", label: "Block", render: r => r.blocked ? badge(r.blocked, "B") : "" },
  { key: "act", label: "", render: r => r.blocked ? "" : h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api("/api/sd/billing", { ref: r.ref, fkdat: today() })); if (y) msgLink("S", y.message, "Display", "VF03", { id: y.vbeln }); } } }, "Bill") }]);
register("VF01", { title: "Create Billing Document", async render(app, params) {
  const v = inp({ value: params.id || "", w: "m" }), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Document to be billed", grid(field("Delivery / memo request", v, { req: true }), field("Billing date", d)),
    h("p.muted", null, "F2 from a delivery, RE from a returns delivery, G2/L2 from a credit / debit memo request. FI: receivable, revenue (VKOA), deductions, freight, VAT. CO-PA: revenue + cost of sales from the goods issue.")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/billing", { ref: val(v), fkdat: d.value })); if (r) msgLink("S", r.message, "Display", "VF03", { id: r.vbeln }); } }]);
} });
register("VF03", { title: "Display Billing Document", async render(app, params) {
  const v = inp({ value: params.id || "", w: "m" }), body = out();
  app.append(panel("Billing document", grid(field("Billing document", v, { req: true }))), body);
  const load = async () => {
    const d = await run(() => api(`/api/sd/billing/${enc(val(v))}`)); if (!d) return; body.innerHTML = "";
    body.append(panel(null, attrs([["Billing document", `${d.vbeln} ${d.fkart} ${d.type_text}`], ["Payer", `${d.kunnr} ${d.name}`], ["Date", fmtDate(d.fkdat)], ["Net value", fmtAmt(d.netwr)],
      ["Tax", fmtAmt(d.mwsbk)], ["Accounting doc.", d.belnr], ["Due date", fmtDate(d.netdt)], ["Paid", d.paid ? badge("Cleared", "U") : badge("Open", "Q")],
      ["Status", d.cancelled ? badge("Cancelled", "B") : badge("Posted", "U")], ["E-invoice", d.einv ? badge(d.einv.status, d.einv.status.startsWith("Valid") ? "U" : "B") : "-"]])),
      alv({ rows: d.items, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "arktx", label: "Description" }, { key: "fkimg", label: "Qty", type: "qty" },
        { key: "gross", label: "Gross", type: "amt", sum: true }, { key: "disc", label: "Discount", type: "amt", sum: true }, { key: "freight", label: "Freight", type: "amt", sum: true },
        { key: "net", label: "Net", type: "amt", sum: true }, { key: "mwsbp", label: "Tax", type: "amt", sum: true }, { key: "cogs", label: "Cost", type: "amt", sum: true }, { key: "aubel", label: "Order" }, { key: "vgbel", label: "Reference" }] }));
    const bt = [{ label: "Print (VF31)", primary: true, onClick: () => go("VF31", { id: d.vbeln }) }, { label: "Accounting (FB03)", ghost: true, onClick: () => go("FB03", { id: d.belnr }) }];
    if (!d.cancelled) bt.push({ label: "Cancel (VF11)", ghost: true, onClick: async () => { const r = await run(() => api(`/api/sd/billing/${d.vbeln}/cancel`, { budat: today() })); if (r) msgLink("S", r.message, "Display", "VF03", { id: r.vbeln }); } },
      { label: "E-invoice (ETA)", ghost: true, onClick: async () => { const r = await run(() => api(`/api/sd/billing/${d.vbeln}/einv`, {})); if (r) { msg(r.errors.length ? "E" : "S", r.message); load(); } } });
    toolbar(bt);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
  if (params.id) load();
} });
register("VF02", { title: "Change Billing Document", render: (a, p) => go("VF03", p) });
register("VF11", { title: "Cancel Billing Document", render: (a, p) => go("VF03", p) });
listScreen("VF05", "List of Billing Documents", "/api/sd/billings", [{ key: "vbeln", label: "Billing doc.", link: r => go("VF03", { id: r.vbeln }) }, { key: "fkart", label: "Type" }, { key: "type_text", label: "Description" },
  { key: "fkdat", label: "Date", type: "date" }, { key: "kunnr", label: "Payer" }, { key: "name", label: "Name" }, { key: "netwr", label: "Net value", type: "amt", sum: true }, { key: "mwsbk", label: "Tax", type: "amt" },
  { key: "belnr", label: "FI doc." }, { key: "cancelled", label: "Status", render: r => r.cancelled ? badge("Cancelled", "B") : badge("Posted", "U") }, { key: "eta_status", label: "E-invoice" }]);
register("VF31", { title: "Output from Billing Documents (Invoice)", async render(app, params) {
  const v = inp({ value: params.id || "", w: "m" }), body = out();
  app.append(panel("Billing document", grid(field("Billing document", v))), body);
  const load = async () => {
    const d = await run(() => api(`/api/sd/billing/${enc(val(v))}`)); if (!d) return; body.innerHTML = "";
    const totalNet = d.items.reduce((a, i) => a + i.net, 0);
    body.append(h("div.panel", { style: { maxWidth: "900px", margin: "auto", padding: "28px", background: "#fff" } },
      h("div", { style: { display: "flex", justifyContent: "space-between" } }, h("div", null, h("h2", null, d.company.name), h("div.muted", null, `Tax registration ${d.company.tax} · ${d.company.city}`)),
        h("div", { style: { textAlign: "right" } }, h("h2", null, d.type_text.toUpperCase()), h("div", null, `No. ${d.vbeln}`), h("div", null, `Date ${fmtDate(d.fkdat)}`), h("div", null, `Due ${fmtDate(d.netdt)}`))),
      gap(), h("div", null, h("b", null, "Bill to: "), `${d.kunnr} ${d.name}, ${d.street || ""} ${d.city || ""} (${d.land}) · Tax no. ${d.stcd1 || d.stceg || "-"}`), gap(),
      h("table.grid", null, h("thead", null, h("tr", null, ["Item", "Description", "Qty", "Unit price", "Discount", "Freight", "Net", "VAT"].map(x => h("th", null, x)))),
        h("tbody", null, d.items.map(i => h("tr", null, h("td", null, String(i.posnr)), h("td", null, i.arktx || i.maktx), h("td.num", null, fmtQty(i.fkimg)), h("td.num", null, fmtAmt(i.price)),
          h("td.num", null, fmtAmt(i.disc)), h("td.num", null, fmtAmt(i.freight)), h("td.num", null, fmtAmt(i.net)), h("td.num", null, fmtAmt(i.mwsbp)))))),
      h("div", { style: { textAlign: "right", marginTop: "12px" } }, h("div", null, `Net ${fmtAmt(totalNet)} EGP`), h("div", null, `VAT 14 % ${fmtAmt(d.mwsbk)} EGP`), h("h3", null, `Total ${fmtAmt(totalNet + d.mwsbk)} EGP`)),
      d.einv ? h("p.muted", null, `ETA e-invoice UUID ${d.einv.uuid} · ${d.einv.status}`) : h("p.muted", null, "E-invoice not yet generated (ZEINV)")));
    toolbar([{ label: "Print", primary: true, onClick: () => window.print() }]);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]); if (params.id) load();
} });
register("ZEINV", { title: "E-Invoice Monitor (Egyptian Tax Authority)", async render(app) {
  const body = out(), view = out(); app.append(panel(null, h("p.muted", null, "Documents are built in the ETA v1.0 structure; the UUID is the SHA-256 of the ETA serialization. Offline mode: validated and ready to submit, not transmitted.")), body, view);
  const exec = async () => { const r = await run(() => api("/api/sd/einv")); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "vbeln", label: "Billing doc.", link: x => go("VF03", { id: x.vbeln }) }, { key: "fkart", label: "Type" }, { key: "fkdat", label: "Date", type: "date" },
      { key: "name", label: "Receiver" }, { key: "netwr", label: "Net", type: "amt", sum: true }, { key: "mwsbk", label: "VAT", type: "amt", sum: true },
      { key: "status", label: "Status", render: x => x.status ? badge(x.status, x.status.startsWith("Valid") ? "U" : "B") : badge("Not generated", "") }, { key: "uuid", label: "UUID", render: x => (x.uuid || "").slice(0, 16) + (x.uuid ? "…" : "") },
      { key: "act", label: "", render: x => h("span", null, h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api(`/api/sd/billing/${x.vbeln}/einv`, {})); if (y) { msg(y.errors.length ? "E" : "S", y.message); exec(); } } } }, "Generate"), " ",
        x.uuid ? h("button.btn.ghost", { type: "button", on: { click: async () => { const d = await api(`/api/sd/billing/${x.vbeln}`); view.innerHTML = ""; view.append(panel(`ETA document ${x.vbeln}`, h("pre", { style: { maxHeight: "420px", overflow: "auto", fontSize: "12px" } }, JSON.stringify(d.einv.payload, null, 1)))); } } }, "View JSON") : "") }] })); };
  execBar(exec); exec();
} });

// ================================================================== returns & samples
register("ZRET_MON", { title: "Returns Monitor (Returns, Credits, Blocked Stock Decision)", async render(app) {
  const body = out(); app.append(body);
  const exec = async () => { const r = await run(() => api("/api/sd/returns")); if (!r) return; body.innerHTML = "";
    body.append(alv({ title: "Returns orders", rows: r.orders, columns: [{ key: "vbeln", label: "Returns order", link: x => go("VA03", { id: x.vbeln }) }, { key: "name", label: "Customer" },
      { key: "vgbel", label: "Ref. invoice", link: x => go("VF03", { id: x.vgbel }) }, { key: "reason", label: "Reason" }, { key: "netwr", label: "Value", type: "amt", sum: true },
      { key: "delivery", label: "Returns delivery", link: x => x.delivery && go("VL03N", { id: x.delivery }) }, { key: "credit", label: "Credit memo", link: x => x.credit && go("VF03", { id: x.credit }) },
      { key: "gbstk", label: "Status", render: x => gb(x.gbstk) }] }), gap(),
      alv({ title: "Blocked stock from returns - usage decision", rows: r.blocked, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "lgort", label: "SLoc" }, { key: "lgpla", label: "Bin" },
        { key: "qty", label: "Blocked qty", type: "qty" }, { key: "act", label: "Decision", render: x => h("span", null,
          h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api("/api/sd/retdecision", { decision: "343", matnr: x.matnr, lgort: x.lgort, lgpla: x.lgpla, qty: String(x.qty), budat: today() })); if (y) { msg("S", y.message); exec(); } } } }, "Back to stock (343)"), " ",
          h("button.btn.ghost", { type: "button", on: { click: async () => { const y = await run(() => api("/api/sd/retdecision", { decision: "551", matnr: x.matnr, lgort: x.lgort, lgpla: x.lgpla, qty: String(x.qty), budat: today() })); if (y) { msg("S", y.message); exec(); } } } }, "Scrap (551)")) }] })); };
  execBar(exec, [{ label: "New return (ZRETURN)", ghost: true, onClick: () => go("ZRETURN") }]); exec();
} });
listScreen("ZSD_SAMPLES", "Samples & Free-of-Charge Deliveries", "/api/sd/samples", [{ key: "vbeln", label: "Order", link: r => go("VA03", { id: r.vbeln }) }, { key: "name", label: "Customer" },
  { key: "audat", label: "Date", type: "date" }, { key: "augru", label: "Reason" }, { key: "dl", label: "Delivery", link: r => r.dl && go("VL03N", { id: r.dl }) }, { key: "wadat_ist", label: "GI", type: "date" },
  { key: "matnr", label: "Material" }, { key: "lfimg", label: "Qty", type: "qty" }, { key: "cogs", label: "Cost (CO-PA)", type: "amt", sum: true }]);

// ================================================================== master
register("VD51", { title: "Customer-Material Info Records", async render(app) {
  await meta();
  const k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), x = inp({ w: "l" }), t = inp({ w: "l" }), body = out();
  app.append(panel("New record", grid(field("Customer", k), field("Material", m), field("Customer material no.", x), field("Text", t))), body);
  const list = async () => { const r = await api("/api/sd/listing"); body.innerHTML = ""; body.append(alv({ rows: r.custmat, columns: [{ key: "kunnr", label: "Customer" }, { key: "name", label: "Name" },
    { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "kdmat", label: "Customer material" }, { key: "postx", label: "Text" }] })); };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/custmat", { kunnr: up(k), matnr: up(m), kdmat: val(x), postx: val(t) })); if (r) { msg("S", "Saved - orders accept the customer's material number"); list(); } } }]);
  list();
} });
register("VB01", { title: "Material Listing / Exclusion", async render(app) {
  await meta();
  const k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), kind = sel([["B", "B001 Exclusion"], ["A", "A001 Listing"]], "B"), d = inp({ type: "date", value: today(), w: "m" }), body = out();
  app.append(panel("New record", grid(field("Customer", k), field("Material", m), field("Type", kind), field("Valid from", d))), body);
  const list = async () => { const r = await api("/api/sd/listing"); body.innerHTML = ""; body.append(alv({ rows: r.listing, columns: [{ key: "kunnr", label: "Customer" }, { key: "name", label: "Name" },
    { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "kind", label: "Type", render: x => x.kind === "B" ? badge("Excluded", "B") : badge("Listed", "U") }, { key: "datab", label: "From", type: "date" }, { key: "datbi", label: "To", type: "date" }] })); };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/listing", { kunnr: up(k), matnr: up(m), kind: kind.value, datab: d.value })); if (r) { msg("S", "Saved"); list(); } } }]);
  list();
} });

// ================================================================== next biz (CRM)
register("VC01N", { title: "Create Sales Activity", async render(app) {
  await meta();
  const k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), t = sel([["0001", "0001 Phone call"], ["0002", "0002 Customer visit"], ["0003", "0003 Meeting"], ["0004", "0004 E-mail"]], "0002", { w: "l" }),
    d = inp({ type: "date", value: today(), w: "m" }), s = inp({ w: "xl" }), r = inp({ w: "xl" }), f = inp({ type: "date", w: "m" });
  app.append(panel("Sales activity", grid(field("Customer", k, { req: true }), field("Activity type", t), field("Date", d), field("Subject", s), field("Result", r), field("Follow-up on", f))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const x = await run(() => api("/api/sd/activity", { kunnr: up(k), ktaar: t.value, datum: d.value, subject: val(s), result: val(r), followup: f.value || null })); if (x) msgLink("S", x.message, "List", "VC05"); } }]);
} });
listScreen("VC05", "Sales Activities", "/api/sd/activity", [{ key: "id", label: "No.", type: "int" }, { key: "datum", label: "Date", type: "date" }, { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" },
  { key: "ktaar", label: "Type" }, { key: "subject", label: "Subject" }, { key: "result", label: "Result" }, { key: "followup", label: "Follow-up", type: "date" }, { key: "usnam", label: "Sales rep" }]);
register("VB21", { title: "Create Sales Deal / Promotion", async render(app) {
  await meta();
  const t = inp({ w: "xl" }), a = inp({ type: "date", value: SM.period.d1, w: "m" }), b = inp({ type: "date", w: "m" }), bud = inp({ type: "number", w: "s" }), m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), p = inp({ type: "number", w: "s" });
  app.append(panel("Promotion", grid(field("Description", t), field("Valid from", a), field("Valid to", b), field("Budget (EGP)", bud), field("Material", m), field("Discount %", p))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/deal", { botext: val(t), datab: a.value, datbi: b.value, budget: bud.value, materials: [{ matnr: up(m), pct: p.value }] })); if (r) msgLink("S", r.message, "List", "VB23"); } }]);
} });
listScreen("VB23", "Sales Deals / Promotions", "/api/sd/deal", [{ key: "knuma", label: "Deal" }, { key: "botext", label: "Description" }, { key: "datab", label: "From", type: "date" }, { key: "datbi", label: "To", type: "date" },
  { key: "budget", label: "Budget", type: "amt" }, { key: "used", label: "Granted so far", type: "amt" }, { key: "materials", label: "Materials", render: r => r.materials.map(x => `${x.matnr} ${x.kbetr / 100} %`).join(", ") },
  { key: "status", label: "Budget used", render: r => r.budget ? badge(Math.round(r.used / r.budget * 100) + " %", r.used > r.budget ? "B" : "U") : "" }]);

// ================================================================== SLM / GCIS / performance
register("ZSLM", { title: "Service Level Monitor (OTIF, Fill Rate, Lead Time)", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: SM.period.d1, w: "m" }), d2 = inp({ type: "date", value: SM.period.d2, w: "m" }), body = out();
  app.append(panel("Period (goods issue date)", grid(field("From", d1), field("To", d2))), body);
  const exec = async () => { const r = await run(() => api(`/api/sd/slm?d1=${d1.value}&d2=${d2.value}`)); if (!r) return; body.innerHTML = "";
    body.append(h("div.kpis", null, kpi("OTIF", (r.otif ?? "-") + " %", "on time AND in full", null, r.otif < 90 ? "crit" : "pos"), kpi("On time", (r.on_time ?? "-") + " %"), kpi("In full", (r.in_full ?? "-") + " %"),
      kpi("Fill rate", (r.fill_rate ?? "-") + " %", "confirmed on requested date at order entry"), kpi("Order-to-ship lead time", (r.lead_time ?? "-") + " days")),
      alv({ rows: r.lines, columns: [{ key: "delivery", label: "Delivery", link: x => go("VL03N", { id: x.delivery }) }, { key: "order", label: "Order", link: x => go("VA03", { id: x.order }) }, { key: "name", label: "Customer" },
        { key: "matnr", label: "Material" }, { key: "qty", label: "Qty", type: "qty" }, { key: "requested", label: "Requested", type: "date" }, { key: "shipped", label: "Shipped", type: "date" },
        { key: "lead_days", label: "Lead days", type: "int" }, { key: "on_time", label: "On time", render: x => x.on_time ? "✔" : badge("Late", "B") }, { key: "in_full", label: "In full", render: x => x.in_full ? "✔" : badge("Partial", "Q") }] })); };
  execBar(exec); exec();
} });
listScreen("F.31", "Credit Management - Overview", "/api/sd/credit", [{ key: "kunnr", label: "Customer", link: r => go("FD33", { id: r.kunnr }) }, { key: "name", label: "Name" }, { key: "klimk", label: "Credit limit", type: "amt" },
  { key: "open_items", label: "Open items", type: "amt", sum: true }, { key: "open_orders", label: "Open orders", type: "amt", sum: true }, { key: "exposure", label: "Exposure", type: "amt", sum: true },
  { key: "utilization", label: "Used %", type: "amt", cls: r => r.utilization > 90 ? "neg" : r.utilization > 70 ? "crit" : "pos" }, { key: "overdue", label: "Overdue", type: "amt" },
  { key: "overdue_days", label: "Oldest overdue (days)", type: "int", cls: r => r.overdue_days > 30 ? "neg" : "" }, { key: "dso", label: "DSO", type: "amt" }, { key: "blocked", label: "Blocked docs", type: "int" },
  { key: "risk", label: "Risk", render: r => badge(SM.risk[r.risk], r.risk === "003" ? "B" : r.risk === "002" ? "Q" : "U") }]);
register("FD33", { title: "Display Credit Management (Customer)", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "C1004", list: "dl-sd-kunnr", upper: true, w: "m" }), body = out();
  app.append(panel("Customer / credit control area 1000", grid(field("Customer", k))), body);
  const exec = async () => { const all = await run(() => api("/api/sd/credit")); if (!all) return; const c = all.find(x => x.kunnr === up(k)); body.innerHTML = "";
    if (!c) return msg("E", "Customer has no credit data");
    body.append(h("div.kpis", null, kpi("Credit limit", fmtAmt(c.klimk)), kpi("Open receivables", fmtAmt(c.open_items)), kpi("Open orders (not billed)", fmtAmt(c.open_orders)),
      kpi("Total exposure", fmtAmt(c.exposure), c.utilization === null ? "no limit" : c.utilization + " % of limit", null, c.utilization > 100 ? "neg" : "pos"),
      kpi("Oldest overdue item", c.overdue_days + " days", fmtAmt(c.overdue) + " overdue", null, c.overdue_days > 30 ? "neg" : "pos"), kpi("DSO", (c.dso ?? "-") + " days"), kpi("Risk category", SM.risk[c.risk])),
      panel(null, h("p.muted", null, SM.credit.text))); };
  execBar(exec, [{ label: "Change limit (FD32)", ghost: true, onClick: () => go("FD32") }, { label: "Customer 360°", ghost: true, onClick: () => go("ZXD03_LF", { id: up(k) }) }]); exec();
} });
function sisScreen(tcode, title, by) {
  register(tcode, { title, async render(app) {
    await meta();
    const d1 = inp({ type: "date", value: SM.period.d1, w: "m" }), d2 = inp({ type: "date", value: SM.period.d2, w: "m" }), body = out();
    app.append(panel("Period", grid(field("From", d1), field("To", d2))), body);
    const exec = async () => { const r = await run(() => api(`/api/sd/sis?by=${by}&d1=${d1.value}&d2=${d2.value}`)); if (!r) return; body.innerHTML = "";
      body.append(alv({ rows: r, columns: [{ key: "key", label: by === "kunnr" ? "Customer" : "Material" }, { key: "name", label: "Name" }, { key: "order_value", label: "Incoming orders", type: "amt", sum: true },
        { key: "qty", label: "Invoiced qty", type: "qty" }, { key: "revenue", label: "Gross revenue", type: "amt", sum: true }, { key: "deductions", label: "Deductions", type: "amt", sum: true },
        { key: "returns", label: "Returns", type: "amt", sum: true }, { key: "credits", label: "Credit memos", type: "amt", sum: true }, { key: "net", label: "Net revenue", type: "amt", sum: true },
        { key: "cost", label: "Cost of sales", type: "amt", sum: true }, { key: "margin", label: "Margin", type: "amt", sum: true }, { key: "margin_pct", label: "Margin %", type: "amt", cls: x => x.margin_pct < 25 ? "crit" : "pos" }] }),
        h("div.cards", null, card("Net revenue", null, bars(r.slice(0, 10), x => `${x.key} ${x.name}`, x => x.net)))); };
    execBar(exec); exec();
  } });
}
sisScreen("MCTA", "SIS: Customer Analysis", "kunnr");
sisScreen("MCTC", "SIS: Material Analysis", "matnr");

// ================================================================== service
listScreen("IE03", "Equipment (Installed Base) & Warranty", "/api/sd/equi", [{ key: "equnr", label: "Equipment" }, { key: "sernr", label: "Serial no." }, { key: "matnr", label: "Material" },
  { key: "maktx", label: "Description" }, { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "inbdt", label: "Start-up / GI", type: "date" }, { key: "gwlen", label: "Warranty end", type: "date" },
  { key: "warranty", label: "Warranty", render: r => r.warranty ? badge("Active", "U") : badge("Expired", "B") }, { key: "notifications", label: "Notifications", type: "int" }, { key: "lieferung", label: "Delivery" },
  { key: "act", label: "", render: r => h("button.btn.ghost", { type: "button", on: { click: () => go("IW51", { equnr: r.equnr }) } }, "Notification") }]);
register("IE01", { title: "Create Equipment", async render(app) {
  await meta();
  const m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), s = inp({ w: "m" }), d = inp({ type: "date", value: today(), w: "m" }), mo = inp({ type: "number", value: SM.warranty, w: "s" });
  app.append(panel("Equipment", grid(field("Material", m), field("Customer", k), field("Serial number", s), field("Start-up date", d), field("Warranty months (BGM1)", mo))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/equi", { matnr: up(m), kunnr: up(k), sernr: val(s), inbdt: d.value, months: mo.value })); if (r) msgLink("S", r.message, "List", "IE03"); } }]);
} });
register("BGM1", { title: "Warranty Master", async render(app) {
  await meta();
  app.append(panel("Warranty W001 - customer warranty", attrs([["Duration", SM.warranty + " months"], ["Starts", "goods issue of the delivery (installation date)"], ["Serialised materials", SM.serialized.join(", ")],
    ["Coverage", "labour + spare parts free of charge"], ["Cost", "service order settled to CO-PA (after-sales costs)"]])));
} });
register("IW51", { title: "Create Service Notification", async render(app, params) {
  await meta();
  const e = inp({ value: params.equnr || "", w: "m" }), k = inp({ list: "dl-sd-kunnr", upper: true, w: "m" }), m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), t = inp({ w: "xl" }),
    p = sel([["1", "1 Very high"], ["2", "2 High"], ["3", "3 Medium"], ["4", "4 Low"]], "3"), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Notification S1 (customer service)", grid(field("Equipment", e, { hint: "warranty is checked" }), field("or customer", k), field("Material", m), field("Description", t, { req: true }), field("Priority", p), field("Date", d))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/sd/qmel", { equnr: val(e) || null, kunnr: up(k), matnr: up(m), qmtxt: val(t), priok: p.value, erdat: d.value })); if (r) msgLink(r.warranty ? "W" : "S", r.message, "Notifications", "IW52"); } }]);
} });
register("IW52", { title: "Service Notifications & Orders", async render(app) {
  const body = out(); app.append(body);
  const exec = async () => { const r = await run(() => api("/api/sd/qmel")); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "qmnum", label: "Notification" }, { key: "erdat", label: "Date", type: "date" }, { key: "name", label: "Customer" }, { key: "equnr", label: "Equipment" },
      { key: "qmtxt", label: "Description" }, { key: "warranty", label: "Warranty", render: x => x.warranty ? badge("Under warranty", "U") : badge("Billable", "Q") },
      { key: "aufnr", label: "Service order", link: x => x.aufnr && go("CO03", { id: x.aufnr }) }, { key: "stat", label: "Order status" }, { key: "cost", label: "Actual cost", type: "amt" },
      { key: "status", label: "Status", render: x => badge(x.status, x.status === "NOCO" ? "U" : "Q") }, { key: "billed", label: "Invoice", link: x => x.billed && go("VF03", { id: x.billed }) },
      { key: "act", label: "", render: x => h("span", null,
        !x.aufnr ? h("button.btn.primary", { type: "button", on: { click: () => go("IW31", { id: x.qmnum }) } }, "Order") : "",
        x.aufnr && x.status !== "NOCO" ? h("button.btn.ghost", { type: "button", on: { click: () => go("CO11N", { id: x.aufnr }) } }, "Confirm") : "",
        x.aufnr && x.status !== "NOCO" ? h("button.btn.ghost", { type: "button", on: { click: async () => { const y = await run(() => api(`/api/sd/qmel/${x.qmnum}/complete`, {})); if (y) { msg("S", y.message); exec(); } } } }, "Complete") : "",
        x.status === "NOCO" && !x.warranty && !x.billed ? h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api(`/api/sd/qmel/${x.qmnum}/dp90`, { fkdat: today() })); if (y) msgLink("S", y.message, "Display", "VF03", { id: y.vbeln }); } } }, "Bill (DP90)") : "") }] })); };
  execBar(exec, [{ label: "New notification (IW51)", ghost: true, onClick: () => go("IW51") }]); exec();
} });
register("IW53", { title: "Display Service Notification", render: () => go("IW52") });
register("IW31", { title: "Create Service Order from Notification", async render(app, params) {
  await meta();
  const n = inp({ value: params.id || "", w: "m" }), op = inp({ value: "Repair at customer", w: "xl" }), hrs = inp({ type: "number", value: 2, w: "s", step: "any" }), m = inp({ list: "dl-sd-matnr", upper: true, w: "m" }), q = inp({ type: "number", w: "s" }),
    d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Service order SM01 - repair shop WC-REPR (cost center 4200)", grid(field("Notification", n, { req: true }), field("Operation", op), field("Planned hours", hrs), field("Spare part", m), field("Quantity", q), field("Start", d))));
  toolbar([{ label: "Save & release", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api(`/api/sd/qmel/${enc(val(n))}/order`, { gstrp: d.value, ops: [{ arbpl: "WC-REPR", ltxa1: val(op), vgw: hrs.value }], comps: up(m) ? [{ matnr: up(m), menge: q.value || "1", lgort: "0004" }] : [] }));
    if (r) msgLink("S", r.message, "Pick parts (CO27)", "CO27"); } }]);
} });
register("IW41", { title: "Confirmation of Service Order", render: (a, p) => go("CO11N", p) });
register("DP90", { title: "Resource-Related Billing (Service)", render: () => go("IW52") });
})();
