/* MM Core - Production planning (PP) screens */
"use strict";
(() => {
const { h, $, $$, api, msg, run, field, inp, sel, val, up, alv, register, go, toolbar,
  fmtQty, fmtAmt, fmtDate, fmtShort, today, enc, S } = App;

const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const out = () => h("div");
const gap = () => h("div", { style: { height: "12px" } });
const card = (t, sub, ...b) => h("div.card", null, h("h3", null, t), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...b));
function kpi(l, v, s, goTo, cls) {
  return h("div.kpi", { on: goTo ? { click: () => go(goTo) } : null }, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
}
function bars(items, labelFn, valFn, fmt) {
  const max = Math.max(...items.map(i => Math.abs(valFn(i))), 1);
  return h("div", null, items.map(i => h("div.hbar", null, h("span.lbl", { title: labelFn(i) }, labelFn(i)),
    h("span.track", null, h("span.fill", { style: { width: Math.min(100, Math.abs(valFn(i)) / max * 100) + "%", display: "block" } })), h("span.num", null, (fmt || fmtShort)(valFn(i))))));
}
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
function execBar(fn, extra) { toolbar([{ label: "Execute", key: "F8", primary: true, onClick: fn }, ...(extra || [])]); }

let PM = null;
async function meta(force) {
  if (!PM || force) {
    PM = await api("/api/pp/meta");
    App.datalist("dl-pp-mat", PM.materials.map(m => [m.matnr, `${m.matnr} ${m.maktx}`]));
    App.datalist("dl-pp-wc", PM.work_centers.map(w => [w.arbpl, `${w.arbpl} ${w.ktext}`]));
    App.datalist("dl-pp-kostl", PM.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
    App.datalist("dl-pp-lifnr", PM.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name}`]));
    App.datalist("dl-pp-lstar", PM.activities.map(a => [a.lstar, `${a.lstar} ${a.ktext}`]));
  }
  return PM;
}
const matIn = (v) => inp({ value: v || "", list: "dl-pp-mat", upper: true, w: "l" });
const day0 = () => (PM && PM.sample && PM.sample.d1 > today() ? PM.sample.d1 : today());
const statBadges = s => h("span", null, (s || "").split(" ").filter(Boolean).map(x =>
  badge(x, x === "MSPT" ? "B" : ["DLV", "CNF", "TECO", "MACM"].includes(x) ? "U" : ["REL", "PCNF", "PDLV"].includes(x) ? "Q" : ""), " "));
const orderLink = r => go("CO03", { id: r.aufnr });
const ORD_COLS = [
  { key: "aufnr", label: "Order", link: orderLink }, { key: "auart", label: "Type" }, { key: "matnr", label: "Material" },
  { key: "maktx", label: "Description" }, { key: "gamng", label: "Order qty", type: "qty" }, { key: "igmng", label: "Confirmed", type: "qty" },
  { key: "iasmg", label: "Scrap", type: "qty" }, { key: "wemng", label: "Delivered", type: "qty" }, { key: "progress", label: "%", type: "amt" },
  { key: "gstrp", label: "Basic start", type: "date" }, { key: "gltrp", label: "Basic finish", type: "date", cls: r => r.late ? "neg" : "" },
  { key: "status", label: "System status", render: r => statBadges(r.status) }, { key: "actual", label: "Actual costs", type: "amt", sum: true }];

// ================================================================== cockpit
register("ZPP_COCKPIT", { title: "Production Cockpit - Orders, Capacity, WIP & Variances", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: PM.sample.d1, w: "m" }), d2 = inp({ type: "date", value: PM.sample.d2, w: "m" }), body = out();
  app.append(panel("Period", grid(field("From", d1), field("To", d2))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/pp/cockpit?d1=${d1.value}&d2=${d2.value}`)); if (!d) return;
    body.innerHTML = ""; const k = d.kpi;
    body.append(h("div.kpis", null,
      kpi("Production orders", String(k.orders), `${k.open_orders} open · ${k.released} released`, "COOIS"),
      kpi("Late orders", String(k.late), "finish date passed", "COOIS", k.late ? "neg" : "pos"),
      kpi("Schedule adherence", k.on_time === null ? "-" : k.on_time + " %", `${k.delivered} delivered orders`, "COOIS", k.on_time < 80 ? "crit" : "pos"),
      kpi("Yield / scrap", `${fmtQty(k.yield_qty)} / ${fmtQty(k.scrap_qty)}`, `scrap ${k.scrap_pct} %`, "CO14", k.scrap_pct > 3 ? "crit" : "pos"),
      kpi("Labour productivity", k.productivity === null ? "-" : k.productivity + " %", `standard vs actual · ${fmtQty(k.hours)} h`, "CO14", k.productivity < 90 ? "crit" : "pos"),
      kpi("Work in process", fmtShort(k.wip), "EGP on balance sheet", "KKAX"),
      kpi("Production variances", fmtShort(k.variance), "KKS2 (target vs actual)", "KKS2", k.variance > 0 ? "crit" : "pos"),
      kpi("MRP exceptions", String(k.exceptions), "last MRP run", "MD06", k.exceptions ? "crit" : "pos"),
      kpi("Missing parts", String(k.missing), "released orders (MSPT)", "CO24", k.missing ? "neg" : "pos"),
      kpi("Planned orders", String(k.planned), `${k.plaf_late} to convert (start passed)`, "MD16"),
      kpi("Stock at subcontractors", fmtShort(k.subcon_value), "MBLB", "MBLB"),
      kpi("Spare-part forecast error", k.fc_mape === null ? "-" : k.fc_mape + " %", "MAPE (MP33)", "MP33", k.fc_mape > 50 ? "crit" : "")));
    body.append(h("div.cards", null,
      card("Capacity load next 4 weeks (CM01)", "required / available hours", alv({ compact: true, rows: d.capacity, columns: [
        { key: "arbpl", label: "Work center" }, { key: "week", label: "Week of", type: "date" }, { key: "req", label: "Required h", type: "qty" },
        { key: "avail", label: "Available h", type: "qty" }, { key: "load", label: "Load %", type: "amt", cls: r => r.load > 100 ? "neg" : r.load > 85 ? "crit" : "pos" }] })),
      card("Production variances by order", "KKS2 categories", d.variances.length ? alv({ compact: true, rows: d.variances, columns: [
        { key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" }, { key: "price", label: "Price", type: "amt" },
        { key: "qty", label: "Quantity", type: "amt" }, { key: "res", label: "Resource", type: "amt" }, { key: "rem", label: "Remaining", type: "amt" },
        { key: "total", label: "Total", type: "amt", sum: true }] }) : h("p.muted", null, "No variances calculated in the period")),
      card("SOP: planned vs actual production", "product groups (MC81)", alv({ compact: true, rows: d.sop, columns: [
        { key: "month", label: "Month" }, { key: "plan", label: "Plan", type: "qty" }, { key: "actual", label: "Actual (GR)", type: "qty" }] })),
      card("Orders with missing parts", "CO24", d.missing.length ? alv({ compact: true, rows: d.missing, columns: [
        { key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" }, { key: "gamng", label: "Qty", type: "qty" }, { key: "gstrp", label: "Start", type: "date" }] })
        : h("p.pos", null, "✔ No missing parts")),
      card("MRP exception messages", "MD06", alv({ compact: true, rows: d.exceptions, columns: [{ key: "ausk", label: "Exception" }, { key: "n", label: "Count", type: "int" }] })),
      card("Spare parts forecast quality", "MP33", alv({ compact: true, rows: d.forecast, columns: [
        { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "prmod", label: "Model" }, { key: "mape", label: "MAPE %", type: "amt" },
        { key: "ss", label: "Safety stock", type: "qty" }, { key: "rop", label: "Reorder pt", type: "qty" }] }))));
    msg("S", `Production cockpit ${fmtDate(d1.value)} - ${fmtDate(d2.value)}`);
  };
  execBar(exec, [{ label: "Process map", ghost: true, onClick: () => go("ZPP_PROCESS") }]); exec();
} });

register("ZPP_PROCESS", { title: "Production Process Map (Plan to Produce)", async render(app) {
  const step = (n, t, codes, d) => h("div.card", null, h("h3", null, `${n}. ${t}`), h("div.sub", null, d),
    h("div.body", null, codes.map(c => h("a.btn.ghost", { href: "#/" + c, style: { margin: "2px" } }, c))));
  app.append(panel(null, h("p", null, "From the sales plan to the finished product: SOP gives the volume, MRP explodes the BOM and creates planned orders and requisitions, production orders are released after the availability check, confirmations post activities and backflush components, goods receipts deliver the product, and period-end closing values WIP, variances and settles to CO-PA / cost centers / stock.")),
    h("div.cards", null,
      step(1, "Master data", ["CS01", "CR01", "CA01", "C223", "OPL8"], "BOM, work center (capacity + costing), routing with control keys, production version"),
      step(2, "Costing", ["CK11N", "CK24"], "standard cost incl. external processing and subcontracting fee"),
      step(3, "SOP & demand", ["MC84", "MC81", "MC75", "MD61", "MD63"], "product group plan -> planned independent requirements"),
      step(4, "MRP", ["MD01", "MD04", "MD06", "MD16", "MD09"], "net requirements, lot sizes, BOM explosion, exceptions"),
      step(5, "Convert & release", ["CO40", "CO41", "CO05N", "CO09", "COMAC"], "availability check, missing parts, external PRs"),
      step(6, "Component supply", ["CO27", "MF60", "ME2O", "MBLB"], "picking, staging, provide components to subcontractor"),
      step(7, "Execution", ["CO11N", "CO13", "CO14", "COOIS"], "activities, backflush, scrap, automatic GR (PP03)"),
      step(8, "Exceptional / service", ["ZPP_REWORK", "ZREF01", "CO07", "MP38", "MB21"], "rework, refurbishment, forecast-based spare parts"),
      step(9, "Period end", ["KGI2", "KKAX", "KKS2", "CO88", "KKBC_ORD"], "overhead, WIP, variances, settlement"),
      step(10, "Monitor", ["ZPP_COCKPIT", "CM01", "CO24"], "capacity, schedule adherence, scrap, variances")));
} });

// ================================================================== master data
function bomScreen(tcode, mode) {
  register(tcode, { title: { create: "Create Material BOM", change: "Change Material BOM", display: "Display Material BOM" }[mode], async render(app, params) {
    await meta();
    const m = matIn(params.id), basis = inp({ value: "1", w: "s", type: "number" }), body = out();
    app.append(panel("Material BOM - plant 1000, usage 1 (production), alternative 01", grid(field("Material", m, { req: true }), field("Base quantity", basis))), body);
    const load = async () => {
      const d = mode === "create" ? { items: [] } : await run(() => api(`/api/pp/bom/${enc(up(m))}`)); if (!d) return;
      body.innerHTML = "";
      if (mode === "display") {
        body.append(tabsUI([["Items", alv({ rows: d.items, columns: [{ key: "posnr", label: "Item", type: "int" }, { key: "idnrk", label: "Component", link: r => go("CS03", { id: r.idnrk }) },
          { key: "maktx", label: "Description" }, { key: "menge", label: "Quantity", type: "qty" }, { key: "meins", label: "Un" }, { key: "ausch", label: "Scrap %", type: "amt" },
          { key: "rgekz", label: "Backflush", render: r => r.rgekz ? "✔" : "" }, { key: "lgort", label: "Issue SLoc" }, { key: "vornr", label: "Op." }] })],
          ["Multi-level explosion (CS12)", alv({ rows: d.explosion, columns: [{ key: "level", label: "Lvl", type: "int", render: r => ".".repeat(r.level) + r.level },
            { key: "idnrk", label: "Component" }, { key: "maktx", label: "Description" }, { key: "menge", label: "Qty for 1", type: "qty" }, { key: "meins", label: "Un" },
            { key: "beskz", label: "Proc." }, { key: "sobsl", label: "Spec." }, { key: "rgekz", label: "Backfl.", render: r => r.rgekz ? "✔" : "" }] })],
          ["Where-used (CS15)", alv({ rows: d.where_used, columns: [{ key: "matnr", label: "Used in", link: r => go("CS03", { id: r.matnr }) }, { key: "maktx", label: "Description" }, { key: "menge", label: "Qty", type: "qty" }] })]]));
        toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }, { label: "Change", ghost: true, onClick: () => go("CS02", { id: up(m) }) }]);
        msg("S", `BOM ${up(m)}: ${d.items.length} items`);
        return;
      }
      const lines = (mode === "change" ? d.items : []).map(i => ({ ...i }));
      const target = mode === "change" ? lines.length + 2 : 5;
      while (lines.length < target) lines.push({ idnrk: "", menge: "", ausch: 0, rgekz: 0, lgort: "", vornr: "" });
      const els = lines.map(l => ({ idnrk: inp({ value: l.idnrk, list: "dl-pp-mat", upper: true, w: "m" }), menge: inp({ value: l.menge || "", type: "number", w: "s", step: "any" }),
        ausch: inp({ value: l.ausch || "", type: "number", w: "s" }), rgekz: h("input", { type: "checkbox", checked: !!l.rgekz }), lgort: inp({ value: l.lgort || "", w: "s", upper: true }), vornr: inp({ value: l.vornr || "", w: "s" }) }));
      body.append(panel("Item overview", h("table.grid", null, h("thead", null, h("tr", null, ["Item", "Component", "Quantity", "Scrap %", "Backflush", "Issue SLoc", "Operation"].map(x => h("th", null, x)))),
        h("tbody", null, els.map((e, i) => h("tr", null, h("td", null, String((i + 1) * 10)), h("td", null, e.idnrk), h("td", null, e.menge), h("td", null, e.ausch), h("td", null, e.rgekz), h("td", null, e.lgort), h("td", null, e.vornr))))),
        h("p.muted", null, "Checks: component in plant, no recursion, material status (BOM), component scrap 0-99 %.")));
      toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
        const items = els.filter(e => up(e.idnrk)).map(e => ({ idnrk: up(e.idnrk), menge: e.menge.value, ausch: e.ausch.value, rgekz: e.rgekz.checked ? 1 : 0, lgort: up(e.lgort), vornr: val(e.vornr) }));
        const r = await run(() => api("/api/pp/bom", { matnr: up(m), basis: basis.value, items, tcode })); if (r) msgLink("S", r.message, "Display", "CS03", { id: up(m) });
      } }]);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id || mode === "create") load();
  } });
}
bomScreen("CS01", "create"); bomScreen("CS02", "change"); bomScreen("CS03", "display");
register("CS11", { title: "Display BOM Level by Level", render: (a, p) => go("CS03", p) });
register("CS12", { title: "Multilevel BOM", render: (a, p) => go("CS03", p) });
register("CS15", { title: "Single-Level Where-Used List", render: (a, p) => go("CS03", p) });

function wcScreen(tcode, mode) {
  register(tcode, { title: { create: "Create Work Center", change: "Change Work Center", display: "Display Work Center" }[mode], async render(app, params) {
    await meta();
    const w = PM.work_centers.find(x => x.arbpl === (params.id || "").toUpperCase()) || {};
    const f = { arbpl: inp({ value: w.arbpl || params.id || "", list: "dl-pp-wc", upper: true, w: "m", readonly: mode !== "create" && w.arbpl ? true : null }), ktext: inp({ value: w.ktext || "", w: "l" }),
      kostl: inp({ value: w.kostl || "", list: "dl-pp-kostl", upper: true, w: "m" }), lstar: inp({ value: w.lstar || "", list: "dl-pp-lstar", upper: true, w: "m" }),
      kapaz: inp({ value: w.kapaz || 8, type: "number", w: "s" }), shifts: inp({ value: w.shifts || 1, type: "number", w: "s" }), ngrad: inp({ value: w.ngrad || 85, type: "number", w: "s" }),
      steus: sel(Object.entries(PM.control_keys).map(([k, v]) => [k, `${k} ${v.text}`]), w.steus || "PP01", { w: "l" }), veran: inp({ value: w.veran || "", w: "m" }) };
    if (mode === "display") Object.values(f).forEach(e => e.disabled = true);
    app.append(tabsUI([["Basic data", grid(field("Work center", f.arbpl, { req: true }), field("Description", f.ktext), field("Person responsible", f.veran), field("Default control key", f.steus))],
      ["Capacities", grid(field("Hours per shift", f.kapaz), field("Shifts per day", f.shifts), field("Utilization %", f.ngrad),
        h("p.muted", null, "Available capacity per working day = hours x shifts x utilization (factory calendar: Friday off)."))],
      ["Costing", grid(field("Cost center", f.kostl, { req: true }), field("Activity type", f.lstar, { req: true }),
        h("p.muted", null, "Confirmations allocate this activity from the cost center to the order at the planned price (KP26)."))]]));
    if (mode !== "display") toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const b = {}; for (const [k, e] of Object.entries(f)) b[k] = e.value; b.tcode = tcode;
      const r = await run(() => api("/api/pp/wc", b)); if (r) { await meta(true); msgLink("S", r.message, "List", "CR05"); }
    } }]);
    else toolbar([{ label: "Change", primary: true, onClick: () => go("CR02", { id: w.arbpl }) }]);
  } });
}
wcScreen("CR01", "create"); wcScreen("CR02", "change"); wcScreen("CR03", "display");
register("CR05", { title: "Work Center List", async render(app) {
  await meta(true);
  app.append(alv({ rows: PM.work_centers, columns: [{ key: "arbpl", label: "Work center", link: r => go("CR03", { id: r.arbpl }) }, { key: "ktext", label: "Description" },
    { key: "kostl", label: "Cost center" }, { key: "cc_name", label: "Name" }, { key: "lstar", label: "Activity" }, { key: "steus", label: "Ctrl key" },
    { key: "kapaz", label: "h/shift", type: "qty" }, { key: "shifts", label: "Shifts", type: "int" }, { key: "ngrad", label: "Util. %", type: "int" }, { key: "avail_day", label: "Avail. h/day", type: "qty" }] }));
  toolbar([{ label: "Create (CR01)", primary: true, onClick: () => go("CR01") }]);
} });

function rtgScreen(tcode, mode) {
  register(tcode, { title: { create: "Create Routing", change: "Change Routing", display: "Display Routing" }[mode], async render(app, params) {
    await meta();
    const m = matIn(params.id), body = out();
    app.append(panel("Routing - plant 1000, usage 1, base quantity 1", grid(field("Material", m, { req: true }))), body);
    const load = async () => {
      const d = mode === "create" ? { ops: [] } : await run(() => api(`/api/pp/routing/${enc(up(m))}`)); if (!d) return;
      body.innerHTML = "";
      if (mode === "display") {
        body.append(alv({ title: "Operations", rows: d.ops, columns: [{ key: "vornr", label: "Op." }, { key: "steus", label: "Ctrl" }, { key: "arbpl", label: "Work center" },
          { key: "ltxa1", label: "Description" }, { key: "vgw_setup", label: "Setup h", type: "qty" }, { key: "vgw", label: "Std value h", type: "qty" },
          { key: "lifnr", label: "Vendor" }, { key: "vname", label: "Name" }, { key: "preis", label: "Price", type: "amt" }, { key: "plifz", label: "Deliv. days", type: "int" }] }), gap(),
          alv({ title: "Production versions (C223)", compact: true, rows: d.versions, columns: [{ key: "verid", label: "Version" }, { key: "text", label: "Text" }, { key: "adatu", label: "Valid from", type: "date" },
            { key: "bdatu", label: "Valid to", type: "date" }, { key: "bstmi", label: "Min lot", type: "qty" }, { key: "bstma", label: "Max lot", type: "qty" }] }),
          h("p", null, d.check.length ? badge("Inconsistent: " + d.check.join(", "), "B") : badge("Consistency check OK", "U")));
        toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }, { label: "Change", ghost: true, onClick: () => go("CA02", { id: up(m) }) }]);
        return;
      }
      const lines = (mode === "change" ? d.ops : []).map(o => ({ ...o }));
      const target = mode === "change" ? lines.length + 1 : 3;
      while (lines.length < target) lines.push({ vornr: "", steus: "PP01", arbpl: "", ltxa1: "", vgw: "", vgw_setup: "" });
      const els = lines.map(l => ({ vornr: inp({ value: l.vornr || "", w: "s" }), steus: sel(Object.keys(PM.control_keys).map(k => [k, k]), l.steus || "PP01", { w: "s" }),
        arbpl: inp({ value: l.arbpl || "", list: "dl-pp-wc", upper: true, w: "m" }), ltxa1: inp({ value: l.ltxa1 || "", w: "l" }), vgw_setup: inp({ value: l.vgw_setup || "", type: "number", w: "s", step: "any" }),
        vgw: inp({ value: l.vgw || "", type: "number", w: "s", step: "any" }), lifnr: inp({ value: l.lifnr || "", list: "dl-pp-lifnr", w: "s" }), preis: inp({ value: l.preis || "", type: "number", w: "s" }), plifz: inp({ value: l.plifz || "", type: "number", w: "s" }) }));
      body.append(panel("Operation overview", h("table.grid", null, h("thead", null, h("tr", null, ["Op.", "Ctrl key", "Work center", "Description", "Setup h", "Std value h", "Vendor (PP02)", "Price", "Days"].map(x => h("th", null, x)))),
        h("tbody", null, els.map(e => h("tr", null, Object.values(e).map(x => h("td", null, x)))))),
        h("p.muted", null, "PP01 internal · PP02 external processing (vendor, price, delivery days → purchase requisition at release) · PP03 internal + automatic goods receipt (last operation only).")));
      toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
        const ops = els.filter(e => val(e.vornr) || up(e.arbpl) || e.steus.value === "PP02" && up(e.lifnr)).map(e => ({ vornr: val(e.vornr), steus: e.steus.value, arbpl: up(e.arbpl), ltxa1: val(e.ltxa1),
          vgw_setup: e.vgw_setup.value, vgw: e.vgw.value, lifnr: up(e.lifnr), preis: e.preis.value, plifz: e.plifz.value }));
        const r = await run(() => api("/api/pp/routing", { matnr: up(m), ops, tcode })); if (r) msgLink("S", r.message, "Display", "CA03", { id: up(m) });
      } }]);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id || mode === "create") load();
  } });
}
rtgScreen("CA01", "create"); rtgScreen("CA02", "change"); rtgScreen("CA03", "display");

register("C223", { title: "Production Version: Mass Processing", async render(app) {
  await meta();
  const body = out(), m = matIn(""), verid = inp({ value: "0001", w: "s" }), text = inp({ w: "l" }), a = inp({ type: "date", value: PM.sample.d1, w: "m" }),
    b = inp({ type: "date", value: `${PM.sample.y + 1}-12-31`, w: "m" }), mi = inp({ type: "number", w: "s" }), ma = inp({ type: "number", w: "s" }), lock = h("input", { type: "checkbox" });
  app.append(panel("New / change production version", grid(field("Material", m, { req: true }), field("Version", verid), field("Text", text), field("Valid from", a), field("Valid to", b),
    field("Lot size from", mi), field("Lot size to", ma), field("Locked", lock))), body);
  const list = async () => { const r = await api("/api/pp/versions"); body.innerHTML = ""; body.append(alv({ rows: r, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
    { key: "verid", label: "Version" }, { key: "text", label: "Text" }, { key: "adatu", label: "From", type: "date" }, { key: "bdatu", label: "To", type: "date" },
    { key: "bstmi", label: "Lot from", type: "qty" }, { key: "bstma", label: "Lot to", type: "qty" }, { key: "lock", label: "Lock", render: x => x.lock ? badge("Locked", "B") : "" },
    { key: "check", label: "Consistency", render: x => x.check === "OK" ? badge("OK", "U") : badge(x.check, "B") }] })); };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pp/version", { matnr: up(m), verid: val(verid), text: val(text), adatu: a.value, bdatu: b.value, bstmi: mi.value, bstma: ma.value, lock: lock.checked }));
    if (r) { msg("S", r.message); list(); } } }]);
  list();
} });

register("OPL8", { title: "Order Types, Control Keys & Settings (Customizing)", async render(app) {
  await meta();
  app.append(tabsUI([
    ["Order types", alv({ rows: Object.entries(PM.order_types).map(([k, v]) => ({ k, ...v })), columns: [{ key: "k", label: "Type" }, { key: "text", label: "Description" },
      { key: "settle", label: "Default settlement", render: r => ({ PA: "CO-PA (variances)", KS: "Cost center", MA: "Material (stock)" })[r.settle] }, { key: "variance", label: "KKS2", render: r => r.variance ? "✔" : "" },
      { key: "release_missing", label: "Release with missing parts", render: r => r.release_missing === "E" ? badge("Not allowed", "B") : badge("Allowed (warning)", "Q") }] })],
    ["Control keys", alv({ rows: Object.entries(PM.control_keys).map(([k, v]) => ({ k, ...v })), columns: [{ key: "k", label: "Key" }, { key: "text", label: "Description" },
      { key: "conf", label: "Confirm", render: r => r.conf ? "✔" : "" }, { key: "cost", label: "Costing", render: r => r.cost ? "✔" : "" },
      { key: "external", label: "External", render: r => r.external ? "✔" : "" }, { key: "auto_gr", label: "Auto GR", render: r => r.auto_gr ? "✔" : "" }] })],
    ["System status", alv({ rows: Object.entries(PM.status).map(([k, t]) => ({ k, t })), columns: [{ key: "k", label: "Status" }, { key: "t", label: "Text" }] })],
    ["MRP types / strategies", h("div", null, alv({ compact: true, rows: Object.entries(PM.mrp_types).map(([k, t]) => ({ k, t })), columns: [{ key: "k", label: "MRP type" }, { key: "t", label: "Text" }] }), gap(),
      alv({ compact: true, rows: Object.entries(PM.strategies).map(([k, t]) => ({ k, t })), columns: [{ key: "k", label: "Strategy" }, { key: "t", label: "Text" }] }), gap(),
      alv({ compact: true, rows: Object.entries(PM.lot_sizes).map(([k, t]) => ({ k, t })), columns: [{ key: "k", label: "Lot size" }, { key: "t", label: "Text" }] }))],
    ["MRP exceptions", alv({ rows: Object.entries(PM.exceptions).map(([k, t]) => ({ k, t })), columns: [{ key: "k", label: "Key" }, { key: "t", label: "Exception message" }] })]]));
} });
register("SCAL", { title: "Factory Calendar EG (Plant 1000)", async render(app) {
  await meta();
  const y = PM.sample.y, m = PM.sample.m, days = new Date(y, m, 0).getDate(), names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const cells = [];
  for (let d = 1; d <= days; d++) { const dt = new Date(y, m - 1, d); const wd = dt.getDay(); cells.push({ d, wd: names[wd], work: wd !== 5 }); }
  app.append(panel(`Working days ${y}-${String(m).padStart(2, "0")}: ${cells.filter(c => c.work).length} of ${days}`, h("div", { style: { display: "flex", flexWrap: "wrap", gap: "6px" } },
    cells.map(c => h("div", { style: { width: "64px", padding: "6px", borderRadius: "6px", textAlign: "center", background: c.work ? "var(--surface-2, #eef4fb)" : "#fde2e2" } }, h("b", null, String(c.d)), h("div.muted", null, c.wd))))),
    panel(null, h("p.muted", null, "Friday is not a working day. Scheduling of orders and MRP lead-time offsetting skip non-working days.")));
} });

// ================================================================== SOP & demand
register("MC84", { title: "Create / Change Product Group", async render(app, params) {
  await meta();
  const g = inp({ value: params.id || (PM.groups[0] || {}).prgrp || "PG-CAB", upper: true, w: "m" }), t = inp({ w: "l" }), body = out();
  app.append(panel("Product group", grid(field("Product group", g), field("Description", t))), body);
  const load = async () => {
    const d = await run(() => api(`/api/pp/sop/${enc(up(g))}`)); if (!d) return;
    if (d.group[0]) t.value = d.group[0].ktext;
    const lines = d.group.map(x => ({ matnr: x.matnr, factor: x.factor })); while (lines.length < 5) lines.push({ matnr: "", factor: "" });
    const els = lines.map(l => ({ matnr: inp({ value: l.matnr, list: "dl-pp-mat", upper: true, w: "m" }), factor: inp({ value: l.factor, type: "number", w: "s" }) }));
    body.innerHTML = "";
    body.append(panel("Members and proportional factors (must add up to 100 %)", h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Material"), h("th", null, "Factor %"))),
      h("tbody", null, els.map(e => h("tr", null, h("td", null, e.matnr), h("td", null, e.factor)))))));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/pp/sop/group", { prgrp: up(g), ktext: val(t), members: els.filter(e => up(e.matnr)).map(e => ({ matnr: up(e.matnr), factor: e.factor.value })) }));
      if (r) msgLink("S", r.message, "Plan (MC81)", "MC81", { id: up(g) }); } }]);
  };
  load();
} });

register("MC81", { title: "Create / Change Rough-Cut Plan (SOP)", async render(app, params) {
  await meta();
  const g = inp({ value: params.id || "PG-CAB", upper: true, w: "m" }), days = inp({ type: "number", value: 10, w: "s" }), body = out();
  app.append(panel("Product group plan - version A00 (active)", grid(field("Product group", g), field("Target days' supply", days))), body);
  const months = []; { let y = PM.sample.y, m = PM.sample.m; for (let i = 0; i < 3; i++) { months.push(`${y}-${String(m).padStart(2, "0")}`); m++; if (m > 12) { m = 1; y++; } } }
  const load = async () => {
    const d = await run(() => api(`/api/pp/sop/${enc(up(g))}`)); if (!d) return;
    const byM = Object.fromEntries(d.plan.map(p => [p.month, p]));
    const sales = months.map(mo => inp({ value: byM[mo] ? byM[mo].sales : "", type: "number", w: "s" }));
    body.innerHTML = "";
    body.append(panel("Planning table", h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Key figure"), months.map(mo => h("th", null, mo)))),
      h("tbody", null, h("tr", null, h("td", null, "Sales"), sales.map(s => h("td", null, s))),
        h("tr", null, h("td", null, "Production"), months.map(mo => h("td.num", null, byM[mo] ? fmtQty(byM[mo].production) : ""))),
        h("tr", null, h("td", null, "Stock level"), months.map(mo => h("td.num", null, byM[mo] ? fmtQty(byM[mo].stock) : ""))),
        h("tr", null, h("td", null, "Target days' supply"), months.map(mo => h("td.num", null, byM[mo] ? String(byM[mo].target_days) : ""))))),
      h("p.muted", null, "Production = sales + target stock (days' supply of next month's sales) - opening stock of all group members.")),
      panel("Members", alv({ compact: true, rows: d.group, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "factor", label: "Factor %", type: "int" }] })));
    toolbar([{ label: "Create production plan", key: "F8", primary: true, onClick: async () => {
      const r = await run(() => api("/api/pp/sop/plan", { prgrp: up(g), days: days.value, months: months.map((mo, i) => ({ month: mo, sales: sales[i].value || "0" })) }));
      if (r) { await load(); msg("S", r.message); } } },
      { label: "Transfer to demand mgmt (MC75)", ghost: true, onClick: async () => { const r = await run(() => api("/api/pp/sop/transfer", { prgrp: up(g) })); if (r) msgLink("S", r.message, "Display PIRs", "MD63"); } }]);
  };
  load();
} });
register("MC82", { title: "Change Rough-Cut Plan", render: (a, p) => go("MC81", p) });
register("MC75", { title: "Transfer Product Group Plan to Demand Management", render: (a, p) => go("MC81", p) });

register("MD61", { title: "Create / Change Planned Independent Requirements", async render(app, params) {
  await meta();
  const m = matIn(params.id || "FG-3003"), body = out();
  app.append(panel("Planned independent requirements - version 00 (active), plant 1000", grid(field("Material", m, { req: true }))), body);
  const months = []; { let y = PM.sample.y, mo = PM.sample.m; for (let i = 0; i < 6; i++) { months.push(`${y}-${String(mo).padStart(2, "0")}`); mo++; if (mo > 12) { mo = 1; y++; } } }
  const load = async () => {
    const r = await run(() => api(`/api/pp/pir?matnr=${enc(up(m))}`)); if (!r) return;
    const by = Object.fromEntries(r.map(p => [p.month, p]));
    const els = months.map(mo => inp({ value: by[mo] ? by[mo].plnmg : "", type: "number", w: "s" }));
    const mat = PM.materials.find(x => x.matnr === up(m)) || {};
    body.innerHTML = "";
    body.append(panel(`Strategy ${mat.strgr || "-"} ${PM.strategies[mat.strgr] || ""}`, h("table.grid", null, h("thead", null, h("tr", null, h("th", null, ""), months.map(mo => h("th", null, mo)))),
      h("tbody", null, h("tr", null, h("td", null, "Planned qty"), els.map(e => h("td", null, e))),
        h("tr", null, h("td", null, "Consumed"), months.map(mo => h("td.num", null, by[mo] ? fmtQty(by[mo].consumed) : ""))),
        h("tr", null, h("td", null, "Open"), months.map(mo => h("td.num", null, by[mo] ? fmtQty(by[mo].open) : "")))))));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const x = await run(() => api("/api/pp/pir", { matnr: up(m), items: months.map((mo, i) => ({ month: mo, qty: els[i].value || "0" })) })); if (x) { msg("S", x.message); load(); } } },
      { label: "MD04", ghost: true, onClick: () => go("MD04", { id: up(m) }) }]);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]); load();
} });
register("MD62", { title: "Change Planned Independent Requirements", render: (a, p) => go("MD61", p) });
register("MD63", { title: "Display Planned Independent Requirements", async render(app) {
  const r = await run(() => api("/api/pp/pir")); if (!r) return;
  app.append(alv({ rows: r, columns: [{ key: "matnr", label: "Material", link: x => go("MD61", { id: x.matnr }) }, { key: "maktx", label: "Description" }, { key: "versb", label: "Version" },
    { key: "bedae", label: "Req. type" }, { key: "month", label: "Month" }, { key: "plnmg", label: "Planned", type: "qty", sum: true }, { key: "consumed", label: "Consumed", type: "qty", sum: true },
    { key: "open", label: "Open", type: "qty", sum: true }, { key: "meins", label: "Un" }] }));
  msg("S", `${r.length} requirements`);
} });

// ================================================================== MRP
function mrpScreen(tcode, title, scope) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const m = matIn(params.id || ""), d = inp({ type: "date", value: today(), w: "m" }), body = out();
    const pl = sel([["1000", "1000 Cairo Plant"], ["1100", "1100 Alexandria Plant"], ["ALL", "All plants"]], "1000", { w: "l" });
    app.append(panel("Control parameters", grid(scope !== "total" ? field("Material", m, { req: true }) : field("Plant", pl),
      field("Planning date", d), field("Processing key", inp({ value: "NEUPL (regenerative)", readonly: true, w: "l" })),
      field("Create purchase req.", inp({ value: "1 Purchase requisitions", readonly: true, w: "l" })))),
      panel(null, h("p.muted", null, scope === "total" ? "All materials of the plant: reorder point (VB) first, then MRP (PD) and forecast-based (VV) by low-level code - finished products before components. Customer orders and deliveries are requirements (strategy 40: they consume the planned independent requirements)." :
        scope === "multi" ? "Material plus all BOM levels below it." : "Only this material - dependent requirements are created but components are not planned.")), body);
    execBar(async () => {
      const r = await run(() => api("/api/pp/mrp", { matnr: scope === "total" ? "" : up(m), werks: scope === "total" ? pl.value : "1000", single: scope === "single", today: d.value })); if (!r) return;
      body.innerHTML = "";
      body.append(h("div.kpis", null, kpi("Materials planned", String(r.materials)), kpi("Planned orders", String(r.planned_orders), "", "MD16"),
        kpi("Purchase requisitions", String(r.requisitions), "", "ME5A"), kpi("Exception messages", String(r.exceptions), "", "MD06", r.exceptions ? "crit" : "pos"),
        scope === "total" ? kpi("Reorder point materials", String(r.reorder_point), "VB") : ""));
      msgLink("S", r.message, "MRP list (MD06)", "MD06");
    });
  } });
}
mrpScreen("MD01", "MRP Run - Total Planning (Plant)", "total");
mrpScreen("MD02", "MRP - Single-Item, Multi-Level", "multi");
mrpScreen("MD03", "MRP - Single-Item, Single-Level", "single");

register("MD04", { title: "Stock/Requirements List", async render(app, params) {
  await meta();
  const m = matIn(params.id || "FG-3003"), body = out();
  app.append(panel("Material / plant 1000", grid(field("Material", m, { req: true }))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/pp/md04/${enc(up(m))}`)); if (!d) return;
    const x = d.material;
    body.innerHTML = "";
    body.append(panel(null, h("div.obj-header", null, [["Material", `${x.matnr} ${x.maktx}`], ["MRP type", `${x.dismm} ${PM.mrp_types[x.dismm] || ""}`], ["Procurement", `${x.beskz}${x.sobsl ? " / " + x.sobsl + " " + (PM.special[x.sobsl] || "") : ""}`],
      ["Strategy", x.strgr || "-"], ["Lot size", x.disls], ["Safety stock", fmtQty(x.eisbe)], ["MRP controller", x.dispo || "-"]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v))))),
      alv({ title: "Stock / requirements", rows: d.lines, columns: [{ key: "dat", label: "Date", type: "date" }, { key: "typ", label: "MRP element" }, { key: "txt", label: "MRP element data" },
        { key: "qty", label: "Rec./reqd qty", type: "qty", cls: r => r.qty < 0 ? "neg" : "" }, { key: "avail", label: "Available qty", type: "qty", cls: r => r.avail < 0 ? "neg" : "" }] }),
      d.messages.length ? alv({ title: "Exception messages (last MRP run)", compact: true, rows: d.messages, columns: [{ key: "dat", label: "Date", type: "date" }, { key: "ausk", label: "Exc." }, { key: "text", label: "Message" }] }) : "");
    toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: exec }, { label: "MRP for material (MD02)", ghost: true, onClick: () => go("MD02", { id: up(m) }) },
      { label: "Pegging (MD09)", ghost: true, onClick: () => go("MD09", { id: up(m) }) }]);
    msg("S", `Available quantity at the end: ${fmtQty(x.final_avail)} ${x.meins}`);
  };
  execBar(exec); exec();
} });
register("MD05", { title: "Individual Display of MRP List", render: (a, p) => go("MD04", p) });

register("MD06", { title: "Collective Display of MRP Lists", async render(app) {
  await meta();
  const dispo = sel([["", "- all MRP controllers"], ["001", "001 Raw materials"], ["002", "002 Finished goods"], ["003", "003 Spare parts"]], ""), body = out();
  app.append(panel("Selection", grid(field("MRP controller", dispo))), body);
  const exec = async () => {
    const [r, mm] = await Promise.all([api(`/api/pp/mrplist?dispo=${dispo.value}`), api("/api/pp/mrpmsg")]);
    body.innerHTML = "";
    body.append(alv({ title: "Materials", rows: r, columns: [{ key: "light", label: "", render: x => badge(x.light === "R" ? "●" : x.light === "Y" ? "●" : "●", x.light === "R" ? "B" : x.light === "Y" ? "Q" : "U") },
      { key: "matnr", label: "Material", link: x => go("MD04", { id: x.matnr }) }, { key: "maktx", label: "Description" }, { key: "dismm", label: "MRP" }, { key: "dispo", label: "Ctrl" },
      { key: "stock", label: "Stock", type: "qty" }, { key: "eisbe", label: "Safety", type: "qty" }, { key: "requirements", label: "Requirements", type: "qty" }, { key: "receipts", label: "Receipts", type: "qty" },
      { key: "final", label: "Final avail.", type: "qty", cls: x => x.final < 0 ? "neg" : "" }, { key: "coverage", label: "Days' supply", type: "amt" }, { key: "exceptions", label: "Exceptions" }] }), gap(),
      alv({ title: mm.run ? `Exception messages of MRP run ${mm.run.id} (${mm.run.ts})` : "No MRP run yet", rows: mm.messages, columns: [{ key: "ausk", label: "Exc." }, { key: "matnr", label: "Material", link: x => go("MD04", { id: x.matnr }) },
        { key: "maktx", label: "Description" }, { key: "dat", label: "Date", type: "date" }, { key: "text", label: "Message" }] }));
    msg("S", `${r.length} materials`);
  };
  execBar(exec); exec();
} });
register("MD07", { title: "Current Stock/Requirements List (Collective)", render: () => go("MD06") });

register("MD09", { title: "Pegged Requirements", async render(app, params) {
  await meta();
  const m = matIn(params.id || "SF-3102"), body = out();
  app.append(panel("Material", grid(field("Material", m))), body);
  const exec = async () => { const r = await run(() => api(`/api/pp/pegging/${enc(up(m))}`)); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "dat", label: "Req. date", type: "date" }, { key: "qty", label: "Quantity", type: "qty", sum: true }, { key: "source", label: "Requirement from" },
      { key: "head", label: "Higher-level material", link: x => go("MD04", { id: x.head }) }, { key: "origin", label: "Original demand" }] })); };
  execBar(exec); exec();
} });

register("MD16", { title: "Collective Display of Planned Orders", async render(app) {
  await meta();
  const m = matIn(""), body = out();
  app.append(panel("Selection", grid(field("Material", m, { hint: "empty = all" }))), body);
  let rowsSel = new Set();
  const exec = async () => {
    const r = await run(() => api(`/api/pp/plaf?matnr=${enc(up(m))}`)); if (!r) return;
    body.innerHTML = ""; rowsSel = new Set();
    body.append(alv({ rows: r, columns: [{ key: "sel", label: "", render: x => { const c = h("input", { type: "checkbox" }); c.addEventListener("change", () => c.checked ? rowsSel.add(x.plnum) : rowsSel.delete(x.plnum)); return c; } },
      { key: "plnum", label: "Planned order", link: x => go("MD13", { id: x.plnum }) }, { key: "matnr", label: "Material", link: x => go("MD04", { id: x.matnr }) }, { key: "maktx", label: "Description" },
      { key: "paart", label: "Type", render: x => x.paart === "NB" ? "NB subcontracting" : "LA in-house" }, { key: "gsmng", label: "Quantity", type: "qty", sum: true },
      { key: "psttr", label: "Start", type: "date", cls: x => x.psttr < today() ? "neg" : "" }, { key: "pedtr", label: "Finish", type: "date" }, { key: "auffx", label: "Firm", render: x => x.auffx ? "✔" : "" }] }));
    msg("S", `${r.length} open planned orders`);
  };
  execBar(exec, [{ label: "Convert selected (CO41)", ghost: true, onClick: async () => {
    if (!rowsSel.size) return msg("E", "Select planned orders");
    const r = await run(() => api("/api/pp/convert", { plnums: [...rowsSel] })); if (r) { msg("S", r.message); exec(); } } }]);
  exec();
} });
register("CO41", { title: "Collective Conversion of Planned Orders", render: () => go("MD16") });
function plafScreen(tcode, mode) {
  register(tcode, { title: { create: "Create Planned Order", change: "Change Planned Order", display: "Display Planned Order" }[mode], async render(app, params) {
    await meta();
    const all = await api("/api/pp/plaf?all=1");
    const p = all.find(x => x.plnum === params.id) || {};
    const f = { plnum: inp({ value: p.plnum || params.id || "", w: "m", readonly: mode !== "create" ? true : null }), matnr: matIn(p.matnr || ""), gsmng: inp({ value: p.gsmng || "", type: "number", w: "s" }),
      psttr: inp({ type: "date", value: p.psttr || "", w: "m" }), pedtr: inp({ type: "date", value: p.pedtr || today(), w: "m" }) };
    if (mode !== "create") f.matnr.readOnly = true;
    app.append(panel("Planned order", grid(field("Planned order", f.plnum), field("Material", f.matnr, { req: true }), field("Order quantity", f.gsmng, { req: true }),
      field("Basic start", f.psttr), field("Basic finish", f.pedtr, { req: true }), p.conv ? field("Converted to", inp({ value: p.conv, readonly: true })) : null)));
    if (mode === "display") { toolbar([{ label: "Change", primary: true, onClick: () => go("MD12", { id: p.plnum }) }, { label: "Convert (CO40)", ghost: true, onClick: () => go("CO40", { id: p.plnum }) }]); return; }
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/pp/plaf", { plnum: mode === "change" ? p.plnum : "", matnr: up(f.matnr), gsmng: f.gsmng.value, psttr: f.psttr.value, pedtr: f.pedtr.value }));
      if (r) msgLink("S", r.message, "Display", "MD13", { id: r.plnum }); } },
      mode === "change" ? { label: "Delete", ghost: true, onClick: async () => { const r = await run(() => api("/api/pp/plaf/delete", { plnum: p.plnum })); if (r) { msg("S", r.message); go("MD16"); } } } : null]);
  } });
}
plafScreen("MD11", "create"); plafScreen("MD12", "change"); plafScreen("MD13", "display");
register("CO40", { title: "Convert Planned Order to Production Order", async render(app, params) {
  await meta();
  const p = inp({ value: params.id || "", w: "m" }), rel = h("input", { type: "checkbox" }), body = out();
  app.append(panel("Planned order", grid(field("Planned order", p, { req: true }), field("Release immediately", rel))), body);
  toolbar([{ label: "Convert", key: "Enter", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pp/convert", { plnum: val(p), release: rel.checked })); if (!r) return;
    const x = r.results[0]; msgLink("S", r.message, "Display", x.type === "ORDER" ? "CO03" : "ME23N", { id: x.number }); } }]);
} });

register("CM01", { title: "Capacity Planning: Work Center Load", async render(app) {
  await meta();
  const d1 = inp({ type: "date", value: PM.sample.d1, w: "m" }), w = sel([["", "- all"], ...PM.work_centers.map(x => [x.arbpl, `${x.arbpl} ${x.ktext}`])], ""), body = out();
  app.append(panel("Selection", grid(field("From", d1), field("Work center", w))), body);
  const exec = async () => {
    const r = await run(() => api(`/api/pp/capacity?d1=${d1.value}&arbpl=${w.value}`)); if (!r) return;
    body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "arbpl", label: "Work center" }, { key: "ktext", label: "Description" }, { key: "week", label: "Week of", type: "date" },
      { key: "req", label: "Requirement h", type: "qty", sum: true }, { key: "avail", label: "Available h", type: "qty", sum: true },
      { key: "load", label: "Load %", type: "amt", cls: x => x.load > 100 ? "neg" : x.load > 85 ? "crit" : "pos" }, { key: "bar", label: "", render: x => h("span.track", { style: { display: "inline-block", width: "120px" } }, h("span.fill", { style: { display: "block", width: Math.min(100, x.load) + "%" } })) }] }));
    msg("S", "Load above 100 % = overload: move orders (CO02) or add a shift (CR02)");
  };
  execBar(exec); exec();
} });

// ================================================================== orders
function orderCreate(tcode, title, auart) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const f = { auart: sel(Object.entries(PM.order_types).map(([k, v]) => [k, `${k} ${v.text}`]), auart || "PP01", { w: "xl" }), matnr: matIn(params.id || ""),
      gamng: inp({ type: "number", value: "", w: "s" }), gstrp: inp({ type: "date", value: today(), w: "m" }), lgort: inp({ value: "", upper: true, w: "s" }),
      kostl: inp({ value: auart === "ZP03" ? "4300" : "", list: "dl-pp-kostl", upper: true, w: "m" }), ktext: inp({ w: "l" }), comp_lgort: inp({ value: "", upper: true, w: "s" }),
      op_wc: inp({ value: auart === "ZREF" ? "WC-REPR" : "WC-ASSY", list: "dl-pp-wc", upper: true, w: "m" }), op_txt: inp({ value: auart === "ZREF" ? "Refurbish" : "Rework", w: "l" }), op_h: inp({ type: "number", value: "1", w: "s", step: "any" }),
      c_mat: matIn(""), c_qty: inp({ type: "number", w: "s" }), rel: h("input", { type: "checkbox" }) };
    const exc = () => f.auart.value !== "PP01";
    const opsPanel = panel("Operation (no standard routing for this order type)", grid(field("Work center", f.op_wc), field("Description", f.op_txt), field("Total hours", f.op_h),
      field("Extra component", f.c_mat), field("Component qty", f.c_qty), field("Defective units from SLoc", f.comp_lgort, { hint: "blocked stock" })));
    app.append(panel("Order header", grid(field("Order type", f.auart), field(auart === "ZP07" ? "Description" : "Material", auart === "ZP07" ? f.ktext : f.matnr, { req: true }),
      field("Total quantity", f.gamng, { req: true }), field("Basic start date", f.gstrp), field("Receiving SLoc", f.lgort), field("Cost center (settlement)", f.kostl),
      field("Release immediately", f.rel))), opsPanel);
    const sync = () => { opsPanel.style.display = exc() ? "" : "none"; };
    f.auart.addEventListener("change", sync); sync();
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const b = { auart: f.auart.value, matnr: up(f.matnr), gamng: f.gamng.value, gstrp: f.gstrp.value, lgort: up(f.lgort), kostl: up(f.kostl), ktext: val(f.ktext),
        comp_lgort: up(f.comp_lgort), release: f.rel.checked };
      if (exc()) { b.ops = [{ arbpl: up(f.op_wc), ltxa1: val(f.op_txt), vgw: f.op_h.value }]; if (up(f.c_mat)) b.comps = [{ matnr: up(f.c_mat), menge: f.c_qty.value }]; }
      const r = await run(() => api("/api/pp/order", b)); if (r) msgLink("S", r.message, "Display", "CO03", { id: r.aufnr }); } }]);
  } });
}
orderCreate("CO01", "Create Production Order", "PP01");
orderCreate("CO07", "Create Production Order without Material", "ZP07");
orderCreate("ZPP_REWORK", "Create Rework Order", "ZP03");
orderCreate("ZREF01", "Create Refurbishment Order", "ZREF");

function orderDisplay(tcode, title, change) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const a = inp({ value: params.id || "", w: "m" }), body = out();
    app.append(panel("Order", grid(field("Order", a, { req: true }))), body);
    const load = async () => {
      const o = await run(() => api(`/api/pp/order/${enc(val(a))}`)); if (!o) return;
      body.innerHTML = "";
      body.append(panel(null, h("div.obj-header", null, [["Order", `${o.aufnr} (${o.auart} ${o.type_text})`], ["Material", `${o.matnr || "-"} ${o.maktx || ""}`],
        ["Quantity", `${fmtQty(o.gamng)} ${o.meins || ""}`], ["Delivered", fmtQty(o.wemng)], ["Scrap", fmtQty(o.iasmg)], ["Basic dates", `${fmtDate(o.gstrp)} - ${fmtDate(o.gltrp)}`],
        ["Version", o.verid || "-"], ["Planned order", o.plnum || "-"]].map(([k, v]) => h("div.attr", null, h("span.k", null, k), h("span.v", null, v))),
        h("div.attr", null, h("span.k", null, "Status"), h("span.v", null, statBadges(o.status))))));
      const tabs = [
        ["Operations", alv({ rows: o.ops, columns: [{ key: "vornr", label: "Op." }, { key: "steus", label: "Ctrl" }, { key: "arbpl", label: "Work center" }, { key: "ltxa1", label: "Description" },
          { key: "ssavd", label: "Start", type: "date" }, { key: "ssedd", label: "Finish", type: "date" }, { key: "vgw", label: "Planned h", type: "qty" }, { key: "ism", label: "Actual h", type: "qty" },
          { key: "lmnga", label: "Yield", type: "qty" }, { key: "xmnga", label: "Scrap", type: "qty" }, { key: "status", label: "Status", render: r => statBadges(r.status) },
          { key: "banfn", label: "PR / PO", render: r => r.banfn ? `${r.banfn}${r.ebeln ? " / " + r.ebeln : ""}` : "" }] })],
        ["Components", alv({ rows: o.comps, columns: [{ key: "rspos", label: "Item", type: "int" }, { key: "matnr", label: "Component", link: r => go("MD04", { id: r.matnr }) }, { key: "maktx", label: "Description" },
          { key: "bdmng", label: "Requirement", type: "qty" }, { key: "enmng", label: "Withdrawn", type: "qty" }, { key: "meins", label: "Un" }, { key: "lgort", label: "SLoc" },
          { key: "bdter", label: "Req. date", type: "date" }, { key: "vornr", label: "Op." }, { key: "rgekz", label: "Backflush", render: r => r.rgekz ? "✔" : "" }] })],
        ["Availability", o.availability.length ? alv({ rows: o.availability, columns: [{ key: "matnr", label: "Component" }, { key: "required", label: "Required", type: "qty" },
          { key: "stock", label: "Stock", type: "qty" }, { key: "committed", label: "Committed", type: "qty" }, { key: "receipts", label: "Receipts", type: "qty" }, { key: "atp", label: "ATP", type: "qty" },
          { key: "ok", label: "", render: r => r.ok ? badge("Available", "U") : badge("Missing " + fmtQty(r.short), "B") }, { key: "commit_date", label: "Commit date", type: "date" }] }) : h("p.muted", null, "No open components")],
        ["Confirmations", alv({ rows: o.confirmations, columns: [{ key: "rueck", label: "Conf." }, { key: "vornr", label: "Op." }, { key: "budat", label: "Posted", type: "date" },
          { key: "lmnga", label: "Yield", type: "qty" }, { key: "xmnga", label: "Scrap", type: "qty" }, { key: "ism", label: "Activity h", type: "qty" }, { key: "aueru", label: "Final", render: r => r.aueru ? "✔" : "" },
          { key: "stokz", label: "Cancelled", render: r => r.stokz ? badge("Cancelled", "B") : "" }, { key: "mblnr", label: "Mat. doc" }] })],
        ["Goods movements", alv({ rows: o.movements, columns: [{ key: "mblnr", label: "Mat. doc", link: r => go("MB03", { id: r.mblnr }) }, { key: "budat", label: "Date", type: "date" }, { key: "bwart", label: "MvT" },
          { key: "matnr", label: "Material" }, { key: "menge", label: "Qty", type: "qty" }, { key: "meins", label: "Un" }, { key: "insmk", label: "ST" }, { key: "dmbtr", label: "Amount", type: "amt" }] })],
        ["Costs (plan/target/actual)", alv({ rows: o.costs, columns: [{ key: "kstar", label: "Cost elem." }, { key: "ktext", label: "Text" }, { key: "plan", label: "Plan", type: "amt", sum: true },
          { key: "target", label: "Target", type: "amt", sum: true }, { key: "actual", label: "Actual", type: "amt", sum: true }, { key: "variance", label: "Act - target", type: "amt", sum: true }] })],
        ["Settlement / WIP", h("div", null, alv({ compact: true, rows: o.rules, columns: [{ key: "konty", label: "Cat." }, { key: "receiver", label: "Receiver" }, { key: "prozs", label: "%", type: "int" }] }), gap(),
          alv({ compact: true, rows: o.wip, columns: [{ key: "gjahr", label: "Year" }, { key: "perio", label: "Period" }, { key: "wip", label: "WIP", type: "amt" }, { key: "belnr", label: "FI doc" }] }))]];
      body.append(tabsUI(tabs));
      const bt = [];
      if (o.stat === "CRTD") bt.push({ label: "Release", primary: true, onClick: async () => { const r = await run(() => api(`/api/pp/order/${o.aufnr}/release`, { budat: today() })); if (r) { await load(); msg(r.type || "S", r.message); } } });
      if (o.stat === "REL") bt.push({ label: "Confirm (CO11N)", primary: true, onClick: () => go("CO11N", { id: o.aufnr }) }, { label: "TECO", ghost: true, onClick: async () => { const r = await run(() => api(`/api/pp/order/${o.aufnr}/teco`, {})); if (r) { msg("S", r.message); load(); } } });
      if (change && ["CRTD", "REL"].includes(o.stat)) {
        const q = inp({ type: "number", value: o.gamng, w: "s" }), s = inp({ type: "date", value: o.gstrp, w: "m" });
        body.prepend(panel("Change quantity / dates (rescheduling)", grid(field("Total quantity", q), field("Basic start", s)),
          h("button.btn.primary", { type: "button", on: { click: async () => { const r = await run(() => api(`/api/pp/order/${o.aufnr}/change`, { gamng: q.value, gstrp: s.value })); if (r) { msg("S", r.message); load(); } } } }, "Save changes")));
      }
      bt.push({ label: "Order analysis (KKBC_ORD)", ghost: true, onClick: () => go("KKBC_ORD", { id: o.aufnr }) });
      toolbar(bt);
      msg("S", `Order ${o.aufnr}: ${o.status}`);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id) load();
  } });
}
orderDisplay("CO03", "Display Production Order", false);
orderDisplay("CO02", "Change Production Order", true);

register("COOIS", { title: "Production Order Information System", async render(app) {
  await meta();
  const t = sel([["", "- all"], ...Object.entries(PM.order_types).map(([k, v]) => [k, `${k} ${v.text}`])], ""), s = sel([["", "- all"], ["CRTD", "CRTD"], ["REL", "REL"], ["DLV", "DLV"], ["TECO", "TECO"], ["CLSD", "CLSD"]], ""),
    m = matIn(""), body = out();
  app.append(panel("Selection", grid(field("Order type", t), field("Status", s), field("Material", m))), body);
  const exec = async () => { const r = await run(() => api(`/api/pp/coois?auart=${t.value}&stat=${s.value}&matnr=${enc(up(m))}`)); if (!r) return;
    body.innerHTML = ""; body.append(alv({ rows: r, columns: ORD_COLS })); msg("S", `${r.length} orders`); };
  execBar(exec); exec();
} });
register("ZREF03", { title: "Refurbishment Orders", async render(app) {
  const r = await run(() => api("/api/pp/coois?auart=ZREF")); if (!r) return;
  app.append(alv({ rows: r, columns: ORD_COLS })); toolbar([{ label: "Create (ZREF01)", primary: true, onClick: () => go("ZREF01") }]);
} });

register("CO05N", { title: "Collective Release of Production Orders", async render(app) {
  const body = out(); app.append(body); let selset = new Set();
  const exec = async () => { const r = await run(() => api("/api/pp/coois?stat=CRTD")); if (!r) return; body.innerHTML = ""; selset = new Set();
    body.append(alv({ rows: r, columns: [{ key: "sel", label: "", render: x => { const c = h("input", { type: "checkbox" }); c.addEventListener("change", () => c.checked ? selset.add(x.aufnr) : selset.delete(x.aufnr)); return c; } }, ...ORD_COLS] }));
    msg("S", `${r.length} orders with status CRTD`); };
  execBar(exec, [{ label: "Release selected", ghost: true, onClick: async () => { const r = await run(() => api("/api/pp/release", { aufnrs: [...selset], budat: today() })); if (r) { msg("S", r.message); exec(); } } }]); exec();
} });
register("COHV", { title: "Mass Processing Production Orders (TECO)", async render(app) {
  const body = out(); app.append(body); let selset = new Set();
  const exec = async () => { const r = await run(() => api("/api/pp/coois?stat=REL")); if (!r) return; body.innerHTML = ""; selset = new Set();
    body.append(alv({ rows: r, columns: [{ key: "sel", label: "", render: x => { const c = h("input", { type: "checkbox" }); c.addEventListener("change", () => c.checked ? selset.add(x.aufnr) : selset.delete(x.aufnr)); return c; } }, ...ORD_COLS] })); };
  execBar(exec, [{ label: "Technically complete selected", ghost: true, onClick: async () => { for (const a of selset) { const r = await run(() => api(`/api/pp/order/${a}/teco`, {})); if (!r) return; } msg("S", `${selset.size} orders TECO`); exec(); } }]); exec();
} });

register("CO11N", { title: "Enter Time Ticket for Production Order", async render(app, params) {
  await meta();
  const a = inp({ value: params.id || "", w: "m" }), body = out();
  app.append(panel("Order", grid(field("Order", a, { req: true }))), body);
  const load = async () => {
    const o = await run(() => api(`/api/pp/order/${enc(val(a))}`)); if (!o) return;
    const ops = o.ops.filter(x => x.steus !== "PP02" && x.status !== "CNF");
    body.innerHTML = "";
    if (!ops.length) return body.append(panel(null, h("p", null, "All operations are finally confirmed.")));
    const op = sel(ops.map(x => [x.vornr, `${x.vornr} ${x.arbpl} ${x.ltxa1} (${x.steus})`]), ops[0].vornr, { w: "xl" });
    const y = inp({ type: "number", w: "s", value: Math.max(0, ops[0].mgvrg - ops[0].lmnga - ops[0].xmnga) }), x = inp({ type: "number", w: "s", value: 0 }), act = inp({ type: "number", w: "s", ph: "proposed" }),
      d = inp({ type: "date", value: today(), w: "m" }), fin = sel([["", "Automatic"], ["1", "Final confirmation"], ["0", "Partial confirmation"]], "");
    const gr = sel([["", "-"], ["01", "01 Material defect"], ["02", "02 Machine fault"], ["03", "03 Operator error"], ["04", "04 Setup / first piece"], ["05", "05 Handling damage"]], "", { w: "l" });
    const info = h("p.muted");
    const upd = () => { const p = ops.find(z => z.vornr === op.value); info.textContent = `Operation qty ${fmtQty(p.mgvrg)} · confirmed ${fmtQty(p.lmnga)} · planned ${fmtQty(p.vgw)} h + setup ${fmtQty(p.vgw_setup)} h · ${p.steus === "PP03" ? "automatic goods receipt" : "no goods receipt"}`; };
    op.addEventListener("change", upd); upd();
    body.append(panel(`${o.aufnr} ${o.matnr} ${o.maktx}`, grid(field("Operation", op), field("Yield", y), field("Scrap", x), field("Scrap reason", gr), field("Activity (h)", act, { hint: "empty = standard" }),
      field("Posting date", d), field("Confirmation type", fin)), info, h("p.muted", null, "Components with the backflush indicator assigned to this operation are issued automatically (261); the final confirmation issues the rest. An operation cannot confirm more than the previous operation produced.")));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/pp/confirm", { aufnr: o.aufnr, vornr: op.value, yield: y.value, scrap: x.value, grund: gr.value, act: act.value, budat: d.value, final: fin.value === "" ? null : fin.value === "1" }));
      if (r) { msgLink("S", r.message, "Order", "CO03", { id: o.aufnr }); load(); } } }]);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
  if (params.id) load();
} });
register("CO14", { title: "Display Confirmations", async render(app) {
  const body = out(); app.append(body);
  const exec = async () => { const r = await run(() => api("/api/pp/confirmations")); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "rueck", label: "Conf." }, { key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" }, { key: "vornr", label: "Op." }, { key: "arbpl", label: "Work center" },
      { key: "budat", label: "Date", type: "date" }, { key: "yield", label: "Yield", type: "qty", sum: true }, { key: "scrap", label: "Scrap", type: "qty", sum: true }, { key: "act", label: "Activity h", type: "qty", sum: true },
      { key: "aueru", label: "Final", render: x => x.aueru ? "✔" : "" }, { key: "stokz", label: "Status", render: x => x.stokz ? badge("Cancelled", "B") : "" }, { key: "usnam", label: "User" }] })); };
  execBar(exec, [{ label: "Cancel (CO13)", ghost: true, onClick: () => go("CO13") }]); exec();
} });
register("CO13", { title: "Cancel Confirmation of Production Order", async render(app) {
  const r = inp({ w: "m" }), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Confirmation", grid(field("Confirmation no.", r, { req: true }), field("Posting date", d)),
    h("p.muted", null, "The activity allocation is reversed and goods movements (backflush, automatic GR) are cancelled.")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const x = await run(() => api("/api/pp/confirm/cancel", { rueck: val(r), budat: d.value })); if (x) msg("S", x.message); } }]);
} });

// ================================================================== availability
register("CO09", { title: "Availability Overview (ATP)", async render(app, params) {
  await meta();
  const m = matIn(params.id || "TR-5001"), q = inp({ type: "number", value: "10", w: "s" }), d = inp({ type: "date", value: today(), w: "m" }), body = out();
  app.append(panel("Material / plant 1000 - checking rule PP", grid(field("Material", m), field("Required qty", q), field("Required date", d))), body);
  const exec = async () => { const r = await run(() => api(`/api/pp/atp?matnr=${enc(up(m))}&qty=${q.value}&date=${d.value}`)); if (!r) return; body.innerHTML = "";
    body.append(h("div.kpis", null, kpi("Unrestricted stock", fmtQty(r.stock)), kpi("Committed (reservations)", fmtQty(r.committed)), kpi("Receipts until date", fmtQty(r.receipts)),
      kpi("ATP quantity", fmtQty(r.atp), "", null, r.ok ? "pos" : "neg"), kpi("Result", r.ok ? "Available" : "Short " + fmtQty(r.short), r.commit_date ? "commit date " + fmtDate(r.commit_date) : "no receipt covers it", null, r.ok ? "pos" : "neg"))); };
  execBar(exec); exec();
} });
register("COMAC", { title: "Collective Availability Check", render: () => go("CO24") });
register("CO24", { title: "Missing Parts Information System", async render(app) {
  const body = out(); app.append(body);
  const exec = async () => { const r = await run(() => api("/api/pp/missing")); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "aufnr", label: "Order", link: orderLink }, { key: "header", label: "Header material" }, { key: "matnr", label: "Component", link: x => go("MD04", { id: x.matnr }) },
      { key: "maktx", label: "Description" }, { key: "bdter", label: "Req. date", type: "date" }, { key: "required", label: "Required", type: "qty" }, { key: "atp", label: "ATP", type: "qty" },
      { key: "ok", label: "", render: x => x.ok ? badge("OK", "U") : badge("Missing " + fmtQty(x.short), "B") }, { key: "commit_date", label: "Commit date", type: "date" }] }));
    msg("S", `${r.filter(x => !x.ok).length} missing part(s) in ${new Set(r.map(x => x.aufnr)).size} orders`); };
  execBar(exec); exec();
} });

// ================================================================== component supply
register("CO27", { title: "Picking List for Production Orders", async render(app) {
  const body = out(), d = inp({ type: "date", value: today(), w: "m" }); app.append(panel("Posting", grid(field("Posting date", d))), body); let sel_ = new Set();
  const exec = async () => { const r = await run(() => api("/api/pp/picking")); if (!r) return; body.innerHTML = ""; sel_ = new Set();
    body.append(alv({ rows: r, columns: [{ key: "sel", label: "", render: x => { const c = h("input", { type: "checkbox" }); c.addEventListener("change", () => c.checked ? sel_.add(x) : sel_.delete(x)); return c; } },
      { key: "aufnr", label: "Order", link: orderLink }, { key: "header", label: "Header" }, { key: "matnr", label: "Component" }, { key: "maktx", label: "Description" },
      { key: "open", label: "Open qty", type: "qty" }, { key: "meins", label: "Un" }, { key: "lgort", label: "SLoc" }, { key: "bin", label: "Bin (FIFO)" },
      { key: "stock", label: "Stock in SLoc", type: "qty", cls: x => x.stock < x.open ? "neg" : "" }, { key: "bdter", label: "Req. date", type: "date" }] }));
    msg("S", `${r.length} open reservation items (not backflushed)`); };
  execBar(exec, [{ label: "Post goods issue (261)", ghost: true, onClick: async () => {
    if (!sel_.size) return msg("E", "Select items");
    const r = await run(() => api("/api/pp/picking", { budat: d.value, items: [...sel_].map(x => ({ rsnum: x.rsnum, rspos: x.rspos, lgpla: x.bin })) })); if (r) { msg("S", r.message); exec(); } } }]); exec();
} });
register("MF60", { title: "Material Staging (Transfer to Production Storage Location)", async render(app) {
  await meta();
  const m = matIn(""), q = inp({ type: "number", w: "s" }), from = inp({ value: "0001", upper: true, w: "s" }), to = inp({ value: "0002", upper: true, w: "s" }), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Stage components for production (311)", grid(field("Material", m), field("Quantity", q), field("From SLoc", from), field("To production SLoc", to), field("Posting date", d)),
    h("p.muted", null, "Components move to the production storage location (MRP 2 view) from which backflushing takes them.")));
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/goodsmovement", { tcode: "MF60", header: { budat: d.value, bktxt: "Staging MF60" }, items: [{ bwart: "311", matnr: up(m), werks: "1000", lgort: up(from), umlgo: up(to), qty: q.value }] }));
    if (r) msg("S", `Material document ${r.mblnr} posted (311)`); } }]);
} });

// ================================================================== external processing & subcontracting
register("ZPP_EXTOP", { title: "External Operations of Production Orders", async render(app) {
  const r = await run(() => api("/api/pp/coois")); if (!r) return;
  const rows = [];
  for (const o of r.filter(x => x.auart === "PP01").slice(0, 30)) { const d = await api(`/api/pp/order/${o.aufnr}`); d.ops.filter(p => p.steus === "PP02").forEach(p => rows.push({ ...p, matnr: o.matnr })); }
  app.append(alv({ rows, columns: [{ key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" }, { key: "vornr", label: "Op." }, { key: "ltxa1", label: "Description" },
    { key: "lifnr", label: "Vendor" }, { key: "vname", label: "Name" }, { key: "preis", label: "Price", type: "amt" }, { key: "mgvrg", label: "Qty", type: "qty" },
    { key: "banfn", label: "Requisition" }, { key: "ebeln", label: "PO", link: x => x.ebeln && go("ME23N", { id: x.ebeln }) }, { key: "ext_received", label: "Received", type: "qty" },
    { key: "status", label: "Status", render: x => statBadges(x.status) }] }));
  toolbar([{ label: "Convert PRs (ME59N)", primary: true, onClick: () => go("ME59N") }]);
} });
register("ME2O", { title: "Subcontracting Cockpit - Components to Provide", async render(app) {
  const body = out(), d = inp({ type: "date", value: today(), w: "m" }); app.append(panel("Posting", grid(field("Posting date", d))), body);
  const exec = async () => { const r = await run(() => api("/api/pp/subcon")); if (!r) return; body.innerHTML = "";
    body.append(alv({ title: "Components per subcontracting PO item", rows: r.items, columns: [{ key: "ebeln", label: "PO", link: x => go("ME23N", { id: x.ebeln }) }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
      { key: "product", label: "Product" }, { key: "po_qty", label: "PO qty", type: "qty" }, { key: "wemng", label: "Received", type: "qty" }, { key: "matnr", label: "Component" },
      { key: "required", label: "Required", type: "qty" }, { key: "consumed", label: "Consumed (543)", type: "qty" }, { key: "at_vendor", label: "At vendor", type: "qty" },
      { key: "to_provide", label: "To provide", type: "qty", cls: x => x.to_provide > 0 ? "crit" : "" },
      { key: "act", label: "", render: x => x.to_provide > 0 ? h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api("/api/pp/subcon/provide", { ebeln: x.ebeln, budat: d.value })); if (y) { msg("S", y.message); exec(); } } } }, "Provide (541)") : "" }] }));
    msg("S", "Goods receipt of the product (MIGO 101) consumes the components automatically (543)"); };
  execBar(exec, [{ label: "Stock at vendor (MBLB)", ghost: true, onClick: () => go("MBLB") }, { label: "New subcontracting PO", ghost: true, onClick: () => go("ZME21_SC") }]); exec();
} });
register("MBLB", { title: "Stocks Provided to Vendor", async render(app) {
  const r = await run(() => api("/api/pp/subcon")); if (!r) return;
  app.append(alv({ rows: r.stock, columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
    { key: "qty", label: "Quantity", type: "qty" }, { key: "meins", label: "Un" }, { key: "value", label: "Value", type: "amt", sum: true }] }), gap(),
    alv({ title: "Subcontracting PO items (item category L)", rows: r.pos, columns: [{ key: "ebeln", label: "PO", link: x => go("ME23N", { id: x.ebeln }) }, { key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
      { key: "matnr", label: "Product" }, { key: "menge", label: "Qty", type: "qty" }, { key: "wemng", label: "Received", type: "qty" }, { key: "netpr", label: "Fee", type: "amt" }] }));
} });
register("ZME21_SC", { title: "Create Subcontracting Purchase Order (Item Category L)", async render(app) {
  await meta();
  const v = inp({ list: "dl-pp-lifnr", upper: true, w: "m" }), m = matIn("SF-3102"), q = inp({ type: "number", w: "s" }), d = inp({ type: "date", value: today(), w: "m" });
  app.append(panel("Subcontracting item", grid(field("Vendor", v, { req: true }), field("Material (product)", m, { req: true }), field("Quantity", q, { req: true }), field("Delivery date", d)),
    h("p.muted", null, "The price is the processing fee from the info record; the components come from the BOM and are provided with ME2O (541).")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/pp/subcon/po", { lifnr: up(v), matnr: up(m), qty: q.value, eindt: d.value })); if (r) msgLink("S", r.message, "ME2O", "ME2O"); } }]);
} });

// ================================================================== service parts
register("MP30", { title: "Execute Forecast (Single Material)", async render(app, params) {
  await meta();
  const m = matIn(params.id || "SP-4001"), model = sel(Object.entries(PM.models).map(([k, t]) => [k, `${k} ${t}`]), "G", { w: "xl" }), alpha = inp({ type: "number", value: 0.3, w: "s", step: "0.05" }),
    hist = inp({ type: "number", value: 6, w: "s" }), sl = sel(PM.service.map(x => [x, x + " %"]), 95, { w: "s" }), apply = h("input", { type: "checkbox" }), body = out();
  app.append(panel("Forecast parameters", grid(field("Material", m), field("Forecast model", model), field("Alpha factor", alpha), field("Historical periods", hist), field("Service level", sl), field("Update safety stock / reorder point", apply))), body);
  execBar(async () => {
    const r = await run(() => api("/api/pp/forecast", { matnr: up(m), model: model.value, alpha: alpha.value, hist: hist.value, service: sl.value, apply: apply.checked })); if (!r) return;
    body.innerHTML = "";
    body.append(h("div.kpis", null, kpi("MAD", fmtQty(r.mad), "mean absolute deviation"), kpi("MAPE", r.mape + " %", "forecast error"), kpi("Tracking signal", String(r.tsig), r.warning || "within ±4", null, r.warning ? "neg" : "pos"),
      kpi("Safety stock", fmtQty(r.safety_stock), `z(${r.service} %) × 1.25 × MAD × √LT`), kpi("Reorder point", fmtQty(r.reorder_point), `lead time ${r.lead_days} days`)),
      h("div.cards", null, card("History vs ex-post forecast", null, alv({ compact: true, rows: r.history.map((x, i) => ({ ...x, expost: r.expost[i] })), columns: [{ key: "month", label: "Month" }, { key: "value", label: "Consumption", type: "qty" }, { key: "expost", label: "Ex-post", type: "qty" }] })),
        card("Forecast", null, bars(r.forecast, x => x.month, x => x.value, fmtQty))));
    msg(r.warning ? "W" : "S", r.message);
  });
} });
register("MP38", { title: "Mass Forecast (Forecast-Based Planning, MRP Type VV)", async render(app) {
  const apply = h("input", { type: "checkbox" }), body = out();
  app.append(panel("Selection: all materials with MRP type VV in plant 1000", grid(field("Update safety stock / reorder point", apply))), body);
  execBar(async () => { const r = await run(() => api("/api/pp/forecast", { mass: true, apply: apply.checked })); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r.results, columns: [{ key: "matnr", label: "Material", link: x => go("MP30", { id: x.matnr }) }, { key: "ok", label: "", render: x => x.ok ? badge("OK", "U") : badge("Error", "B") },
      { key: "mad", label: "MAD", type: "qty" }, { key: "mape", label: "MAPE %", type: "amt" }, { key: "ss", label: "Safety stock", type: "qty" }, { key: "rop", label: "Reorder pt", type: "qty" }, { key: "warning", label: "Message" }] }));
    msg("S", r.message); });
} });
register("MP33", { title: "Forecast Results & Service Parts Overview", async render(app) {
  const r = await run(() => api("/api/pp/forecast")); if (!r) return;
  app.append(alv({ rows: r, columns: [{ key: "matnr", label: "Material", link: x => go("MP30", { id: x.matnr }) }, { key: "maktx", label: "Description" }, { key: "prmod", label: "Model" },
    { key: "alpha", label: "Alpha", type: "amt" }, { key: "mad", label: "MAD", type: "qty" }, { key: "mape", label: "MAPE %", type: "amt", cls: x => x.mape > 50 ? "crit" : "" },
    { key: "tsig", label: "Track. signal", type: "amt", cls: x => Math.abs(x.tsig) > 4 ? "neg" : "" }, { key: "stock", label: "Stock", type: "qty" }, { key: "eisbe", label: "Safety stock", type: "qty" },
    { key: "minbe", label: "Reorder pt", type: "qty" }, { key: "rop", label: "Proposed ROP", type: "qty" },
    { key: "status", label: "Status", render: x => x.stock < x.eisbe ? badge("Below safety stock", "B") : x.stock < x.minbe ? badge("Below reorder point", "Q") : badge("OK", "U") }] }));
} });
register("MB21", { title: "Create Reservation (Cost Center)", async render(app) {
  await meta();
  const k = inp({ value: "4200", list: "dl-pp-kostl", upper: true, w: "m" }), d = inp({ type: "date", value: today(), w: "m" }), m = matIn("SP-4003"), q = inp({ type: "number", w: "s" }), l = inp({ value: "0004", upper: true, w: "s" });
  app.append(panel("Reservation - movement type 201 (goods issue for cost center)", grid(field("Cost center", k, { req: true }), field("Requirement date", d), field("Material", m, { req: true }), field("Quantity", q, { req: true }), field("Storage location", l))));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => { const r = await run(() => api("/api/pp/reservation", { kostl: up(k), bdter: d.value, items: [{ matnr: up(m), menge: q.value, lgort: up(l) }] })); if (r) msgLink("S", r.message, "List (MB25)", "MB25"); } }]);
} });
register("MB25", { title: "Reservation List", async render(app) {
  const d = inp({ type: "date", value: today(), w: "m" }), body = out(); app.append(panel("Goods issue", grid(field("Posting date", d))), body);
  const exec = async () => { const r = await run(() => api("/api/pp/reservations")); if (!r) return; body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "rsnum", label: "Reservation" }, { key: "rspos", label: "Item", type: "int" }, { key: "kostl", label: "Cost center" }, { key: "kname", label: "Name" },
      { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "bdmng", label: "Requirement", type: "qty" }, { key: "enmng", label: "Withdrawn", type: "qty" },
      { key: "bdter", label: "Req. date", type: "date" }, { key: "act", label: "", render: x => h("button.btn.primary", { type: "button", on: { click: async () => { const y = await run(() => api("/api/pp/reservation/issue", { rsnum: x.rsnum, budat: d.value })); if (y) { msg("S", y.message); exec(); } } } }, "Issue (201)") }] })); };
  execBar(exec, [{ label: "Create (MB21)", ghost: true, onClick: () => go("MB21") }]); exec();
} });
register("MB24", { title: "Reservation List (Cost Center)", render: () => go("MB25") });

// ================================================================== period end
register("KKAX", { title: "Work in Process: Calculation and Settlement to FI (KKAX / KKAO)", async render(app) {
  await meta();
  const y = inp({ type: "number", value: PM.sample.y, w: "s" }), p = inp({ type: "number", value: PM.sample.m, w: "s" }), test = h("input", { type: "checkbox", checked: true }), body = out();
  app.append(panel("Parameters", grid(field("Fiscal year", y), field("Period", p), field("Test run", test)),
    h("p.muted", null, "WIP = actual costs of released orders not yet delivered. The change vs. the previous period is posted to FI: Dr 793000 WIP / Cr 893000 change in WIP. Delivered / TECO orders cancel their WIP.")), body);
  const list = async () => { const r = await api("/api/pp/wip"); body.innerHTML = ""; body.append(alv({ title: "WIP history", rows: r, columns: [{ key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" },
    { key: "stat", label: "Status" }, { key: "gjahr", label: "Year" }, { key: "perio", label: "Period" }, { key: "wip", label: "WIP", type: "amt", sum: true }, { key: "belnr", label: "FI doc", link: x => x.belnr && go("FB03", { id: x.belnr }) }] })); };
  execBar(async () => { const r = await run(() => api("/api/pp/wip", { gjahr: y.value, perio: p.value, test: test.checked })); if (!r) return; await list();
    body.prepend(alv({ title: test.checked ? "Test run" : "Posted", rows: r.orders, columns: [{ key: "aufnr", label: "Order", link: orderLink }, { key: "matnr", label: "Material" }, { key: "stat", label: "Status" },
      { key: "previous", label: "Previous WIP", type: "amt" }, { key: "wip", label: "WIP", type: "amt", sum: true }, { key: "delta", label: "Posting", type: "amt", sum: true }, { key: "note", label: "Note" }] }), gap());
    msg("S", r.message); });
  list();
} });
register("KKAO", { title: "Calculate Work in Process: Collective", render: () => go("KKAX") });
})();
