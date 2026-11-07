/* MM Core - Master data screens (material, customer, vendor, CIN, Exim, governance) */
"use strict";
(() => {
const { h, $, $$, api, msg, run, confirmBox, field, inp, sel, val, up, alv, register, go,
  toolbar, fmtQty, fmtAmt, fmtDate, fmtShort, today, enc, S } = App;

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
    h("span.track", null, h("span.fill", { style: { width: Math.abs(valFn(i)) / max * 100 + "%", display: "block" } })), h("span.num", null, (fmt || fmtShort)(valFn(i))))));
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
  const w = h("div.panel", null, bar, page);
  if (list.length) show(0);
  return w;
}
function warnBox(ws) {
  return ws && ws.length ? h("div.panel", null, h("div.panel-body", null, ws.map(w => h("p.crit", null, "⚠ " + w)))) : null;
}

let MD = null;
async function meta(force) {
  if (!MD || force) {
    MD = await api("/api/md/meta");
    App.datalist("dl-md-matnr", MD.materials.map(m => [m.matnr, `${m.matnr} ${m.maktx}`]));
    App.datalist("dl-md-kunnr", MD.customers.map(c => [c.kunnr, `${c.kunnr} ${c.name}`]));
    App.datalist("dl-md-lifnr", MD.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name}`]));
  }
  return MD;
}
const opts = (obj, empty) => [...(empty ? [["", "-"]] : []), ...Object.entries(obj || {}).map(([k, t]) => [k, `${k} ${Array.isArray(t) ? t[0] : t}`])];
const plantOpts = () => MD.plants.map(p => [p.werks, `${p.werks} ${p.name}`]);
const slocOpts = w => [["", "-"], ...MD.slocs.filter(s => s.werks === w).map(s => [s.lgort, `${s.lgort} ${s.name}`])];

// ------------------------------------------------------------------ generic form
// spec: {k, l, t: txt|num|chk|date|sel, o: options (object or fn), req, ro, w, e (empty option)}
function form(spec, data, ro, cols) {
  const els = {};
  const fields = spec.map(f => {
    const v = data && data[f.k] !== undefined && data[f.k] !== null ? data[f.k] : (f.d ?? "");
    let el;
    const r = ro || f.ro;
    if (f.t === "sel") {
      el = sel(opts(typeof f.o === "function" ? f.o() : f.o, f.e), v, { w: f.w || "l" });
      if (r) el.disabled = true;
    } else if (f.t === "chk") {
      el = h("input", { type: "checkbox", checked: !!(v && v !== "0"), disabled: r || null });
    } else {
      el = inp({ value: v, type: f.t === "num" ? "number" : f.t === "date" ? "date" : "text", step: f.t === "num" ? "any" : null,
        readonly: r || null, upper: f.up, w: f.w || "m", list: f.list });
    }
    els[f.k] = el;
    return field(f.l, el, { req: f.req && !ro, hint: f.hint });
  });
  const el = h("div.form-grid" + (cols ? ".cols-" + cols : ""), null, ...fields);
  el.get = () => { const o = {}; for (const f of spec) { if (f.ro) continue; const e = els[f.k]; o[f.k] = f.t === "chk" ? (e.checked ? 1 : 0) : e.value; } return o; };
  el.els = els;
  return el;
}

// ================================================================== material
const MV = {
  K: [{ k: "maktx", l: "Material description", req: 1, w: "xl" }, { k: "meins", l: "Base unit of measure", t: "sel", o: () => MD.units, req: 1 },
    { k: "matkl", l: "Material group", t: "sel", o: () => MD.groups, req: 1, e: 1 }, { k: "bismt", l: "Old material number" },
    { k: "spart", l: "Division", t: "sel", o: () => MD.divisions }, { k: "mtpos_mara", l: "Gen. item cat. group", t: "sel", o: () => MD.itemcat },
    { k: "mstae", l: "X-plant matl status", t: "sel", o: () => MD.status, e: 1 }, { k: "prdha", l: "Product hierarchy" },
    { k: "brgew", l: "Gross weight", t: "num" }, { k: "ntgew", l: "Net weight", t: "num" },
    { k: "gewei", l: "Weight unit", t: "sel", o: { KG: "Kilogram", G: "Gram", TO: "Ton" } }, { k: "volum", l: "Volume", t: "num" },
    { k: "voleh", l: "Volume unit", t: "sel", o: { M3: "Cubic metre", L: "Litre" }, e: 1 }, { k: "ean11", l: "EAN/UPC (13 digits)" }],
  V: [{ k: "dwerk", l: "Delivering plant", t: "sel", o: () => Object.fromEntries(MD.plants.map(p => [p.werks, p.name])) },
    { k: "ktgrm", l: "Acct assignment grp", t: "sel", o: () => MD.ktgrm }, { k: "mtpos", l: "Item category group", t: "sel", o: () => MD.itemcat },
    { k: "taxm1", l: "Tax classification", t: "sel", o: () => MD.taxcl }, { k: "aumng", l: "Min. order quantity", t: "num" },
    { k: "vmsta", l: "Distr.-chain status", t: "sel", o: () => MD.sales_status, e: 1 }, { k: "kondm", l: "Material pricing group" },
    { k: "versg", l: "Matl statistics grp" }, { k: "kbetr", l: "Sales price PR00 (EGP)", t: "num" }],
  E: [{ k: "ekgrp", l: "Purchasing group", t: "sel", o: () => MD.purch_groups }, { k: "plifz", l: "Planned deliv. time (days)", t: "num" },
    { k: "webaz", l: "GR processing time", t: "num" }, { k: "mmsta", l: "Plant-sp. matl status", t: "sel", o: () => MD.status, e: 1 },
    { k: "uebto", l: "Overdeliv. tolerance %", t: "num" }, { k: "untto", l: "Underdel. tolerance %", t: "num" },
    { k: "insmk", l: "Post to insp. stock", t: "chk" }, { k: "kordb", l: "Source list required", t: "chk" }],
  D: [{ k: "dismm", l: "MRP type", t: "sel", o: { ND: "No planning", VB: "Manual reorder point", PD: "MRP", V1: "Automatic reorder point" } },
    { k: "dispo", l: "MRP controller", t: "sel", o: () => MD.mrp_ctrl, e: 1 }, { k: "minbe", l: "Reorder point", t: "num" },
    { k: "eisbe", l: "Safety stock", t: "num" }, { k: "disls", l: "Lot size", t: "sel", o: { EX: "Lot-for-lot", FX: "Fixed lot size", HB: "Replenish to max. stock", WB: "Weekly", MB: "Monthly" } },
    { k: "bstfe", l: "Fixed lot size", t: "num" }, { k: "mabst", l: "Maximum stock level", t: "num" },
    { k: "beskz", l: "Procurement type", t: "sel", o: () => MD.proc_types }, { k: "dzeit", l: "In-house production (days)", t: "num" },
    { k: "mtvfp", l: "Availability check", t: "sel", o: () => MD.avail }, { k: "lgfsb", l: "Storage loc. for EP", w: "s", up: 1 },
    { k: "lgpro", l: "Prod. stor. location", w: "s", up: 1 }],
  L: [{ k: "raube", l: "Storage conditions", t: "sel", o: () => MD.storage }, { k: "tempb", l: "Temp. conditions", t: "sel", o: { "01": "Room temperature", "02": "2-8 °C" }, e: 1 },
    { k: "mhdhb", l: "Total shelf life (days)", t: "num" }, { k: "mhdrz", l: "Min. rem. shelf life", t: "num" }, { k: "lgpbe", l: "Storage bin (MARD)", up: 1 }],
  S: [{ k: "lgnum", l: "Warehouse number", d: "100" }, { k: "ltkze", l: "Stock placement", t: "sel", o: { F: "Fixed bin / next empty", N: "Near picking", B: "Bulk" } },
    { k: "ltkza", l: "Stock removal", t: "sel", o: { F: "FIFO", L: "LIFO", M: "Partial quantities" } }, { k: "lhmg1", l: "Loading equip. qty", t: "num" }],
  Q: [{ k: "qmatv", l: "Inspection setup active", t: "chk" }, { k: "ssqss", l: "QM control key", t: "sel", o: () => MD.qm }, { k: "insmk", l: "Post to insp. stock", t: "chk" }],
  B: [{ k: "bklas", l: "Valuation class", t: "sel", o: () => MD.valclasses }, { k: "vprsv", l: "Price control", t: "sel", o: { V: "Moving average price", S: "Standard price" } },
    { k: "price", l: "Price (MAP / standard)", t: "num" }, { k: "peinh", l: "Price unit", t: "num", d: 1 },
    { k: "bwprh", l: "Tax price 1", t: "num" }, { k: "bwph1", l: "Commercial price 1", t: "num" }],
  G: [{ k: "prctr", l: "Profit center", t: "sel", o: () => MD.prctr, e: 1 }, { k: "ncost", l: "Do not cost", t: "chk" },
    { k: "losgr", l: "Costing lot size", t: "num" }, { k: "awsls", l: "Variance key", t: "sel", o: () => MD.variance },
    { k: "zplp1", l: "Planned price 1", t: "num" }, { k: "zpld1", l: "Planned price date 1", t: "date" }],
  X: [{ k: "stawn", l: "Comm./imp. code (HS)", ph: "8302.42" }, { k: "herkl", l: "Country of origin", t: "sel", o: () => MD.countries, e: 1 },
    { k: "herkr", l: "Region of origin", up: 1 }, { k: "impctl", l: "Import legal control", t: "sel", o: () => MD.exim },
    { k: "expctl", l: "Export legal control", t: "sel", o: () => MD.exim }, { k: "lic_no", l: "Import license no." },
    { k: "lic_valid", l: "License valid to", t: "date" }, { k: "duty", l: "Customs duty %", t: "num" }, { k: "prefz", l: "Preference zone", up: 1 }],
};
const LEVEL = { K: "M", V: "S", E: "P", D: "P", L: "L", S: "W", Q: "P", B: "P", G: "P", X: "X" };

function matScreen(tcode, mode, title) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const ini = { matnr: inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }),
      mbrsh: sel(opts(MD.sectors), "M", { w: "l" }), mtart: sel(Object.entries(MD.types).map(([k, t]) => [k, `${k} ${t.text}`]), "ROH", { w: "l" }),
      werks: sel(plantOpts(), params.werks || "1000", { w: "m" }), lgort: sel(slocOpts("1000"), ""),
      vkorg: sel(opts(MD.sorgs), "1000", { w: "m" }), vtweg: sel(opts(MD.channels, true), params.vtweg || "", { w: "m" }), lgnum: inp({ value: "100", w: "s" }) };
    ini.werks.addEventListener("change", () => { const n = sel(slocOpts(ini.werks.value), ""); ini.lgort.replaceWith(n); ini.lgort = n; });
    const body = out();
    app.append(panel(mode === "create" ? "Create Material (Initial Screen)" : "Material & organizational levels",
      grid(field("Material", ini.matnr, { hint: mode === "create" ? "empty = internal number; existing number = extend" : "" }),
        mode === "create" ? field("Industry sector", ini.mbrsh, { req: true }) : null,
        mode === "create" ? field("Material type", ini.mtart, { req: true }) : null),
      h("h3", null, "Organizational levels"),
      grid(field("Plant", ini.werks), field("Storage location", ini.lgort), field("Sales organization", ini.vkorg),
        field("Distribution channel", ini.vtweg), field("Warehouse number", ini.lgnum))), body);
    let state = null;
    const org = () => ({ werks: ini.werks.value, lgort: ini.lgort.value, vkorg: ini.vkorg.value, vtweg: ini.vtweg.value, lgnum: ini.lgnum.value });

    async function selectViews() {
      const k = up(ini.matnr);
      let m = null;
      if (k && MD.materials.find(x => x.matnr === k)) m = await run(() => api(`/api/md/material/${enc(k)}`));
      const mtart = m ? m.mtart : ini.mtart.value;
      const t = MD.types[mtart];
      const o = org();
      const exists = v => { if (!m) return false; const L = LEVEL[v];
        if (L === "M") return true; if (L === "S") return !!m.sales.find(s => s.vtweg === o.vtweg);
        if (L === "W") return !!m.whse; if (L === "X") return !!m.exim; if (L === "L") return !!m.slocs.find(s => s.werks === o.werks && s.lgort === o.lgort);
        return !!m.plants.find(p => p.werks === o.werks); };
      const boxes = {};
      const list = h("div.form-grid", null, [...MD.view_order].filter(v => t.views.includes(v) && !"CPA".includes(v)).map(v => {
        const done = exists(v);
        const cb = h("input", { type: "checkbox", checked: !done && (v === "K" || (!m && "EDLB".includes(v))) || null, disabled: done || null });
        boxes[v] = cb;
        return h("label.chk", null, cb, " ", MD.views[v], done ? h("small.muted", null, " (exists)") : null);
      }));
      body.innerHTML = "";
      body.append(panel(`Select view(s) - material type ${mtart} ${t.text}${m ? " · extend " + m.matnr : ""}`, list,
        h("p.muted", null, "Views not allowed for this material type (OMS2) are not offered. Sales needs a distribution channel, plant views a plant.")));
      toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: () => {
        const views = Object.keys(boxes).filter(v => boxes[v].checked);
        if (!views.length) return msg("E", "Select at least one view");
        if (views.includes("V") && !o.vtweg) return msg("E", "Enter a distribution channel for the sales view", "M3", "341");
        if (views.includes("L") && views.length && !o.lgort && m) return msg("W", "No storage location entered - only material-level storage data");
        buildTabs(m, mtart, views, o);
      } }, { label: "Back", ghost: true, onClick: () => go(tcode) }]);
    }

    function viewData(m, v, o) {
      if (!m) return {};
      const L = LEVEL[v];
      if (L === "M") return m;
      if (L === "S") return m.sales.find(s => s.vtweg === o.vtweg) || {};
      if (L === "W") return m.whse || {};
      if (L === "X") return m.exim || {};
      const p = m.plants.find(x => x.werks === o.werks) || {};
      if (L === "L") return Object.assign({}, m, { lgpbe: (m.slocs.find(s => s.werks === o.werks && s.lgort === o.lgort) || {}).lgpbe });
      if (v === "B") return Object.assign({ bklas: m.bklas }, p);
      return p;
    }

    function buildTabs(m, mtart, views, o) {
      const t = MD.types[mtart];
      const ro = mode === "display";
      const forms = {};
      const tabList = [];
      const defaults = { K: { meins: "PC", gewei: "KG", spart: "00", mtpos_mara: "NORM" }, B: { bklas: t.bklas[0], vprsv: t.vprsv, peinh: 1 },
        E: { ekgrp: "001", plifz: 7 }, D: { dismm: "ND", disls: "EX", beskz: t.views.includes("E") ? "F" : "E", mtvfp: "02" },
        V: { dwerk: o.werks, ktgrm: "01", mtpos: "NORM", taxm1: o.vtweg === "20" ? "0" : "1", versg: "1" }, G: { awsls: t.vprsv === "S" ? "000001" : "" },
        S: { lgnum: o.lgnum, ltkze: "F", ltkza: "F" }, X: { impctl: "", expctl: "" }, L: {}, Q: { ssqss: "" } };
      for (const v of views) {
        let spec = MV[v];
        if (v === "B") spec = spec.map(f => f.k === "bklas" ? Object.assign({}, f, { o: Object.fromEntries(t.bklas.map(b => [b, MD.valclasses[b][0]])) })
          : (f.k === "price" || f.k === "peinh") && mode !== "create" && m && m.plants.find(p => p.werks === o.werks) ? Object.assign({}, f, { ro: true, hint: "MR21" }) : f);
        if (v === "K" && m && mode === "create") spec = spec.map(f => Object.assign({}, f, { ro: true }));
        if (v === "K" && mode === "change") spec = spec.map(f => f.k === "meins" ? Object.assign({}, f, { ro: true }) : f);
        const d = Object.assign({}, defaults[v] || {}, viewData(m, v, o));
        forms[v] = form(spec, d, ro);
        const orgTxt = { M: "", S: ` · ${o.vkorg}/${o.vtweg}`, P: ` · plant ${o.werks}`, L: ` · ${o.werks}/${o.lgort || "-"}`, W: ` · WH ${o.lgnum}`, X: "" }[LEVEL[v]];
        const extra = [];
        if (v === "B" && m) { const p = m.plants.find(x => x.werks === o.werks);
          if (p) extra.push(h("p.muted", null, `Total stock ${fmtQty(p.lbkum)} ${m.meins} · total value ${fmtAmt(p.salk3)} EGP · ${p.vprsv === "S" ? "standard" : "moving average"} price ${fmtAmt(p.price)} per ${p.peinh}`)); }
        if (v === "G" && m) { const p = m.plants.find(x => x.werks === o.werks);
          if (p && p.ce_total !== undefined) extra.push(h("p.muted", null, `Cost estimate ${p.ce_status} of ${fmtDate(p.ce_date)}: ${fmtAmt(p.ce_total)} for ${fmtQty(p.ce_losgr)} ${m.meins}`)); }
        tabList.push([MD.views[v], h("div", null, h("p.muted", null, MD.views[v] + orgTxt), forms[v], ...extra)]);
      }
      const uomRows = (m && m.uom ? m.uom.map(u => ({ ...u })) : []);
      while (uomRows.length < 3) uomRows.push({ meinh: "", umrez: "", umren: 1 });
      const uomEls = uomRows.map(u => ({ meinh: sel(opts(MD.units, true), u.meinh, { w: "m" }), umrez: inp({ value: u.umrez, type: "number", w: "s", readonly: ro || null }), umren: inp({ value: u.umren, type: "number", w: "s", readonly: ro || null }) }));
      tabList.push(["Units of measure", h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Alt. unit"), h("th", null, "Numerator (base)"), h("th", null, "Denominator"), h("th", null, "Meaning"))),
        h("tbody", null, uomEls.map(u => h("tr", null, h("td", null, u.meinh), h("td", null, u.umrez), h("td", null, u.umren), h("td.muted", null, "1 alt. unit = numerator / denominator base units")))))]);
      if (mode === "display" && m) {
        tabList.push(["Org. levels & stock", h("div", null,
          alv({ compact: true, title: "Plants (MARC / MBEW)", rows: m.plants, columns: [{ key: "werks", label: "Plant" }, { key: "plant_name", label: "Name" }, { key: "vpsta", label: "Views" },
            { key: "mmsta", label: "Status" }, { key: "lvorm", label: "Del.", render: r => r.lvorm ? badge("X", "B") : "" }, { key: "dismm", label: "MRP" }, { key: "vprsv", label: "PC" },
            { key: "price", label: "Price", type: "amt" }, { key: "lbkum", label: "Stock", type: "qty" }, { key: "salk3", label: "Value", type: "amt", sum: true }] }), gap(),
          alv({ compact: true, title: "Storage locations (MARD)", rows: m.slocs, columns: [{ key: "werks", label: "Plant" }, { key: "lgort", label: "SLoc" }, { key: "name", label: "Name" },
            { key: "lgpbe", label: "Bin" }, { key: "auto", label: "Created", render: r => r.auto ? "automatically (GR)" : "MM01 / MMSC" }, { key: "stock", label: "Stock", type: "qty" }] }), gap(),
          alv({ compact: true, title: "Sales areas (MVKE)", rows: m.sales, columns: [{ key: "vkorg", label: "SOrg" }, { key: "vtweg", label: "DChl" }, { key: "dwerk", label: "Plant" },
            { key: "taxm1", label: "Tax" }, { key: "vmsta", label: "Status" }, { key: "kbetr", label: "Price", type: "amt" }] }))]);
        tabList.push(["Localization (CIN / Brazil)", h("div", null,
          alv({ compact: true, title: "India: material & chapter ID (J1ID)", rows: m.cin, columns: [{ key: "werks", label: "Plant" }, { key: "chapid", label: "Chapter ID" }, { key: "hsn", label: "HSN" }, { key: "mtype", label: "Type" }, { key: "gst", label: "GST %", type: "amt" }] }), gap(),
          alv({ compact: true, title: "Brazil: NCM / usage / origin", rows: m.brazil, columns: [{ key: "werks", label: "Plant" }, { key: "steuc", label: "NCM" }, { key: "mtuse", label: "Usage", render: r => `${r.mtuse} ${MD.br_usage[r.mtuse] || ""}` }, { key: "mtorg", label: "Origin", render: r => `${r.mtorg} ${MD.br_origin[r.mtorg] || ""}` }] }))]);
      }
      body.innerHTML = "";
      const head = m ? `${m.matnr} ${m.maktx}` : `New material · ${mtart} ${t.text}`;
      body.append(panel(null, h("div.doc-head", null, h("div", null, h("div.k", null, "Material"), h("div.v", null, head)),
        h("div", null, h("div.k", null, "Type"), h("div.v", null, `${mtart} ${t.text}`)), m ? h("div", null, h("div.k", null, "Views maintained"), h("div.v", null, m.vpsta || "-")) : null,
        m && m.lvorm ? h("div", null, h("div.k", null, "Deletion flag"), h("div.v", null, badge("Flagged", "B"))) : null)), tabsUI(tabList));
      const save = async () => {
        const b = { mbrsh: ini.mbrsh.value, mtart, tcode };
        if (m) b.matnr = m.matnr; else if (up(ini.matnr)) b.matnr = up(ini.matnr);
        const plant = { werks: o.werks };
        let hasPlant = false;
        for (const v of views) {
          const d = forms[v].get();
          const L = LEVEL[v];
          if (L === "M") Object.assign(b, d);
          else if (L === "P") { Object.assign(plant, d); hasPlant = true; }
          else if (L === "L") { const { lgpbe, ...rest } = d; Object.assign(b, rest); if (o.lgort) { plant.slocs = [{ lgort: o.lgort, lgpbe }]; } }
          else if (L === "S") b.sales = [Object.assign({ vkorg: o.vkorg, vtweg: o.vtweg }, d)];
          else if (L === "W") b.whse = d;
          else if (L === "X") b.exim = d;
        }
        if (plant.bklas) { b.bklas = plant.bklas; delete plant.bklas; }
        b.uom = uomEls.filter(u => u.meinh.value && u.umrez.value).map(u => ({ meinh: u.meinh.value, umrez: u.umrez.value, umren: u.umren.value || 1 }));
        if (mode === "create") {
          const plantNew = !m || !m.plants.find(p => p.werks === o.werks);
          if (hasPlant && plantNew) b.plants = [plant];
          else if (plant.slocs) b.slocs = plant.slocs.map(s => Object.assign({ werks: o.werks }, s));
          if (m) { delete b.maktx; delete b.meins; delete b.matkl; }
          const r = await run(() => api("/api/md/material", { method: "POST", body: b }));
          if (r) { await meta(true); App.loadMaterials && App.loadMaterials(); msgLink("S", r.message, "Display", "MM03", { id: r.matnr, werks: o.werks, vtweg: o.vtweg }); body.innerHTML = ""; toolbar([{ label: "Select views", primary: true, onClick: selectViews }]); }
        } else {
          delete plant.price; delete plant.peinh;
          if (hasPlant || plant.slocs) b.plants = [plant];
          const r = await run(() => api(`/api/md/material/${enc(m.matnr)}/change`, { method: "POST", body: b }));
          if (r) msgLink("S", r.message, "Changes (MM04)", "MM04", { id: m.matnr });
        }
      };
      if (ro) toolbar([{ label: "Change", primary: true, onClick: () => go("MM02", { id: m.matnr, werks: o.werks, vtweg: o.vtweg }) },
        { label: "Changes (MM04)", ghost: true, onClick: () => go("MM04", { id: m.matnr }) }, { label: "Logistics/Financial", ghost: true, onClick: () => go("ZMM03_LF", { id: m.matnr }) }]);
      else toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: save }, { label: "Cancel", ghost: true, onClick: () => go(tcode) }]);
    }

    async function load() {
      const k = up(ini.matnr);
      if (!k) return msg("E", "Enter a material number", "M3", "301");
      const m = await run(() => api(`/api/md/material/${enc(k)}`)); if (!m) return;
      const o = org();
      const views = [...m.vpsta].filter(v => MV[v] && (LEVEL[v] !== "S" || (o.vtweg && m.sales.find(s => s.vtweg === o.vtweg))) &&
        (!"PEDQBG".includes(v) || m.plants.find(p => p.werks === o.werks)) && (LEVEL[v] !== "L" || m.plants.find(p => p.werks === o.werks)));
      if (!views.includes("K")) views.unshift("K");
      if (!m.plants.find(p => p.werks === o.werks)) msg("W", `Material ${k} is not maintained in plant ${o.werks} - plant views not shown`);
      buildTabs(m, m.mtart, views, o);
      if (mode === "display") msg("S", `Material ${k} displayed (${m.vpsta})`);
    }
    if (mode === "create") toolbar([{ label: "Select views", key: "Enter", primary: true, onClick: selectViews }]);
    else { toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]); if (params.id) { if (params.vtweg) ini.vtweg.value = params.vtweg; load(); } }
  } });
}
matScreen("MM01", "create", "Create Material");
matScreen("MM02", "change", "Change Material");
matScreen("MM03", "display", "Display Material");

// ------------------------------------------------------------------ Logistics / Financial 360
register("ZMM03_LF", { title: "Display Material (Logistics/Financial)", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }), body = out();
  app.append(panel("Material", grid(field("Material", e, { req: true }))), body);
  const exec = async () => {
    const m = await run(() => api(`/api/md/material/${enc(up(e))}?full=1`)); if (!m) return;
    body.innerHTML = "";
    const cons = m.movements.slice(-6);
    const avg = cons.length ? cons.reduce((a, r) => a + r.cons, 0) / cons.length : 0;
    const stock = m.plants.reduce((a, p) => a + p.lbkum, 0);
    const openPo = m.open_po.reduce((a, p) => a + p.open, 0);
    const sales = m.sales_docs.reduce((a, s) => a + s.value, 0);
    body.append(panel(null, h("div.doc-head", null, h("div", null, h("div.k", null, "Material"), h("div.v", null, `${m.matnr} ${m.maktx}`)),
      h("div", null, h("div.k", null, "Type / class"), h("div.v", null, `${m.mtart} · ${m.bklas} ${m.bklas_text}`)),
      h("div", null, h("div.k", null, "Status"), h("div.v", null, m.lvorm ? badge("Deletion flag", "B") : m.mstae ? badge(m.mstae + " " + m.mstae_text, "Q") : badge("Active", "U"))),
      h("div", null, h("div.k", null, "Views"), h("div.v", null, m.vpsta)))));
    body.append(h("div.kpis", null,
      kpi("Total stock", h("span", null, fmtQty(stock), " ", h("small", null, m.meins)), `${m.plants.length} plant(s)`, null),
      kpi("Stock value", fmtShort(m.plants.reduce((a, p) => a + p.salk3, 0)), "EGP (MBEW)", null),
      kpi("Open purchase orders", fmtQty(openPo), `${m.open_po.length} item(s)`, null),
      kpi("Avg. consumption / month", fmtQty(Math.round(avg)), "last 6 months", null),
      kpi("Coverage", avg ? Math.round(stock / avg * 30) + " days" : "-", "stock / consumption", null, avg && stock / avg * 30 < 15 ? "crit" : ""),
      kpi("Sales (last docs)", fmtShort(sales), `${m.sales_docs.length} billing items`, null)));
    body.append(h("div.cards", null,
      card("Logistics per plant", "Purchasing · MRP · status", alv({ compact: true, rows: m.plants, columns: [
        { key: "werks", label: "Plant" }, { key: "mmsta", label: "Status" }, { key: "dismm", label: "MRP" }, { key: "dispo", label: "Ctrl" },
        { key: "minbe", label: "Reorder pt", type: "qty" }, { key: "eisbe", label: "Safety", type: "qty" }, { key: "mabst", label: "Max", type: "qty" },
        { key: "plifz", label: "Lead time", type: "int" }, { key: "ekgrp", label: "PGr" }, { key: "insmk", label: "QI", render: r => r.insmk ? "✔" : "" },
        { key: "uebto", label: "Over %", type: "amt" }] })),
      card("Financials per plant", "Valuation · costing", alv({ compact: true, rows: m.plants, columns: [
        { key: "werks", label: "Plant" }, { key: "vprsv", label: "PC" }, { key: "verpr", label: "MAP", type: "amt" }, { key: "stprs", label: "Std price", type: "amt" },
        { key: "peinh", label: "per", type: "int" }, { key: "lbkum", label: "Stock", type: "qty" }, { key: "salk3", label: "Value", type: "amt", sum: true },
        { key: "zplp1", label: "Planned price", type: "amt" }, { key: "prctr", label: "Profit ctr" }, { key: "ce_total", label: "Cost est.", type: "amt" }] })),
      card("Account determination (OBYC)", `Valuation class ${m.bklas}`, alv({ compact: true, rows: m.accounts, columns: [
        { key: "key", label: "Key" }, { key: "text", label: "Meaning" }, { key: "hkont", label: "G/L account" }] })),
      card("Consumption & receipts per month", null, alv({ compact: true, rows: m.movements, columns: [
        { key: "month", label: "Month" }, { key: "rec", label: "Receipts", type: "qty" }, { key: "iss", label: "Issues", type: "qty" }, { key: "cons", label: "Consumption", type: "qty" }] })),
      card("Open purchase orders", null, m.open_po.length ? alv({ compact: true, rows: m.open_po, columns: [
        { key: "ebeln", label: "PO", link: r => go("ME23N", { id: r.ebeln }) }, { key: "ebelp", label: "Item", type: "int" }, { key: "name", label: "Vendor" },
        { key: "open", label: "Open qty", type: "qty" }, { key: "eindt", label: "Delivery", type: "date" }] }) : h("p.muted", null, "No open purchase orders")),
      card("Price history (CKM3)", null, alv({ compact: true, rows: m.prices, columns: [
        { key: "bwkey", label: "Plant" }, { key: "budat", label: "Date", type: "date" }, { key: "ref", label: "Ref." }, { key: "reason", label: "Reason" },
        { key: "old_price", label: "Old", type: "amt" }, { key: "new_price", label: "New", type: "amt" }] })),
      card("Sales documents", null, alv({ compact: true, rows: m.sales_docs, columns: [
        { key: "vbeln", label: "Billing doc" }, { key: "fkdat", label: "Date", type: "date" }, { key: "kunnr", label: "Customer", link: r => go("ZXD03_LF", { id: r.kunnr }) },
        { key: "qty", label: "Qty", type: "qty" }, { key: "value", label: "Net value", type: "amt", sum: true }] })),
      card("Last changes (MM04)", null, changeGrid(m.changes.slice(0, 12)))));
    msg("S", `Material ${m.matnr}: logistics and financial view`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }, { label: "Change (Log./Fin.)", ghost: true, onClick: () => go("ZMM02_LF", { id: up(e) }) }]);
  if (params.id) exec();
} });

register("ZMM02_LF", { title: "Change Material (Logistics/Financial)", async render(app, params) {
  await meta();
  const e = inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }), body = out();
  app.append(panel("Material - change logistics and financial data of all plants in one screen", grid(field("Material", e, { req: true }))), body);
  const LOG = [["mmsta", "Status", "sel", () => MD.status], ["dismm", "MRP type", "sel", () => ({ ND: "ND", VB: "VB", PD: "PD", V1: "V1" })], ["minbe", "Reorder pt", "num"], ["eisbe", "Safety", "num"],
    ["mabst", "Max stock", "num"], ["plifz", "Lead time", "num"], ["ekgrp", "PGr", "sel", () => MD.purch_groups], ["uebto", "Over %", "num"]];
  const FIN = [["prctr", "Profit ctr", "sel", () => MD.prctr], ["zplp1", "Planned price", "num"], ["zpld1", "Valid from", "date"], ["bwprh", "Tax price", "num"], ["bwph1", "Comm. price", "num"]];
  const exec = async () => {
    const m = await run(() => api(`/api/md/material/${enc(up(e))}`)); if (!m) return;
    body.innerHTML = "";
    const rowsEls = m.plants.map(p => { const o = { werks: p.werks };
      for (const [k, , t, f] of [...LOG, ...FIN]) o[k] = t === "sel" ? sel(opts(f(), true), p[k] ?? "", { w: "s" }) : inp({ value: p[k] ?? "", type: t === "num" ? "number" : t, w: "s", step: "any" });
      return o; });
    const tbl = (title, cols) => panel(title, h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Plant"), cols.map(c => h("th", null, c[1])))),
      h("tbody", null, rowsEls.map(r => h("tr", null, h("td", null, r.werks), cols.map(c => h("td", null, r[c[0]])))))));
    body.append(panel(null, h("p", null, `${m.matnr} ${m.maktx} · ${m.mtart} · price control and prices: MR21 · all changes are logged (MM04)`)),
      tbl("Logistics (purchasing / MRP)", LOG), tbl("Financial (costing / valuation)", FIN));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const plants = rowsEls.map(r => { const o = { werks: r.werks }; for (const [k] of [...LOG, ...FIN]) o[k] = r[k].value; return o; });
      const r = await run(() => api(`/api/md/material/${enc(m.matnr)}/change`, { method: "POST", body: { plants, tcode: "ZMM02_LF" } }));
      if (r) msgLink("S", r.message, "Display", "ZMM03_LF", { id: m.matnr });
    } }, { label: "Back", ghost: true, onClick: () => go("ZMM02_LF") }]);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: exec }]);
  if (params.id) exec();
} });

// ------------------------------------------------------------------ change documents
function changeGrid(rows) {
  return alv({ compact: true, rows, columns: [{ key: "udate", label: "Date", type: "date" }, { key: "utime", label: "Time" }, { key: "username", label: "User" },
    { key: "tcode", label: "T-code" }, { key: "objectid", label: "Object" }, { key: "tabname", label: "Table" }, { key: "tabkey", label: "Key" },
    { key: "ftext", label: "Field" }, { key: "chngind", label: "Ind.", render: r => r.chngind === "I" ? badge("New", "U") : r.chngind === "D" ? badge("Deleted", "B") : "Changed" },
    { key: "value_old", label: "Old value" }, { key: "value_new", label: "New value" }] });
}
function changeScreen(tcode, obj, title, list) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const k = inp({ value: params.id || "", list, upper: true, w: "l" }), user = inp({ upper: true, w: "m" }), d1 = inp({ type: "date", w: "m" }), d2 = inp({ type: "date", w: "m" }), body = out();
    app.append(panel("Selection", grid(field(obj === "MATERIAL" ? "Material" : obj === "DEBI" ? "Customer" : "Vendor", k, { hint: "empty = all" }),
      field("Changed by", user), field("From", d1), field("To", d2))), body);
    const exec = async () => {
      const r = await run(() => api(`/api/md/changes?obj=${obj}&id=${enc(up(k))}&user=${enc(up(user))}&d1=${d1.value}&d2=${d2.value}`)); if (!r) return;
      body.innerHTML = ""; body.append(changeGrid(r)); msg("S", `${r.length} change(s)`);
    };
    toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); exec();
  } });
}
changeScreen("MM04", "MATERIAL", "Display Material Change Documents", "dl-md-matnr");
changeScreen("XD04", "DEBI", "Customer Account Changes", "dl-md-kunnr");
changeScreen("XK04", "KRED", "Vendor Account Changes", "dl-md-lifnr");
register("S_ALR_87012182", { title: "Display Changes to Customers", render: (a, p) => go("XD04", p) });
register("S_ALR_87012089", { title: "Display Changes to Vendors", render: (a, p) => go("XK04", p) });

// ------------------------------------------------------------------ MM06 / MMSC / MM50 / MM60
register("MM06", { title: "Flag Material for Deletion", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }), w = sel([["", "- all plants (X-plant flag)"], ...plantOpts()], ""), f = h("input", { type: "checkbox", checked: true }), body = out();
  app.append(panel("Material", grid(field("Material", k, { req: true }), field("Plant", w), field("Deletion flag", f))), body,
    panel(null, h("p.muted", null, "The deletion flag blocks goods receipts and purchase orders. Remaining stock can still be issued. Archiving (reorganization) needs zero stock.")));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api(`/api/md/material/${enc(up(k))}/delete`, { method: "POST", body: { werks: w.value, flag: f.checked } }));
    if (r) { msg(r.warnings.length ? "W" : "S", r.message); body.innerHTML = ""; const wb = warnBox(r.warnings); if (wb) body.append(wb); }
  } }]);
} });

register("MMSC", { title: "Enter Storage Locations (Collective)", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }), w = sel(plantOpts(), "1000"), body = out();
  app.append(panel("Material / plant", grid(field("Material", k, { req: true }), field("Plant", w))), body);
  const exec = async () => {
    const m = await run(() => api(`/api/md/material/${enc(up(k))}`)); if (!m) return;
    body.innerHTML = "";
    const have = m.slocs.filter(s => s.werks === w.value);
    const lines = [{ lgort: "", lgpbe: "" }, { lgort: "", lgpbe: "" }];
    const els = lines.map(() => ({ lgort: sel(slocOpts(w.value), ""), lgpbe: inp({ upper: true, w: "m" }) }));
    body.append(alv({ compact: true, title: "Existing storage locations", rows: have, columns: [{ key: "lgort", label: "SLoc" }, { key: "name", label: "Name" }, { key: "lgpbe", label: "Bin" },
      { key: "auto", label: "Created", render: r => r.auto ? "automatically at goods receipt (OMB3)" : "manually" }, { key: "stock", label: "Stock", type: "qty" }] }), gap(),
      panel("New storage locations", h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Storage location"), h("th", null, "Storage bin"))),
        h("tbody", null, els.map(e2 => h("tr", null, h("td", null, e2.lgort), h("td", null, e2.lgpbe)))))));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const slocs = els.filter(e2 => e2.lgort.value).map(e2 => ({ werks: w.value, lgort: e2.lgort.value, lgpbe: e2.lgpbe.value }));
      if (!slocs.length) return msg("E", "Enter a storage location");
      const r = await run(() => api("/api/md/material", { method: "POST", body: { matnr: m.matnr, slocs } }));
      if (r) { msg("S", `Storage locations created for ${m.matnr}`); exec(); }
    } }]);
  };
  toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: exec }]);
  if (params.id) exec();
} });

register("MM50", { title: "List Extendable Materials", async render(app) {
  const r = await run(() => api("/api/md/mm50")); if (!r) return;
  app.append(alv({ rows: r, columns: [{ key: "matnr", label: "Material", link: x => go("MM01", { id: x.matnr }) }, { key: "maktx", label: "Description" }, { key: "mtart", label: "Type" },
    { key: "level", label: "Level" }, { key: "org", label: "Org. unit" }, { key: "missing", label: "Missing" }] }));
  toolbar([{ label: "Extend (MM01)", primary: true, onClick: () => go("MM01") }]);
  msg("S", `${r.length} extension(s) possible`);
} });

register("MM60", { title: "Materials List", async render(app) {
  await meta();
  const t = sel(opts(Object.fromEntries(Object.entries(MD.types).map(([k, v]) => [k, v.text])), true), ""), g = sel(opts(MD.groups, true), ""),
    w = sel([["", "-"], ...plantOpts()], ""), q = inp({ w: "l", ph: "number or text" }), body = out();
  app.append(panel("Selection", grid(field("Material type", t), field("Material group", g), field("Plant", w), field("Search", q))), body);
  const exec = async () => {
    const r = await run(() => api(`/api/md/mm60?mtart=${t.value}&matkl=${g.value}&werks=${w.value}&q=${enc(val(q))}`)); if (!r) return;
    body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "matnr", label: "Material", link: x => go("MM03", { id: x.matnr, werks: x.werks || "1000" }) }, { key: "maktx", label: "Description" },
      { key: "mtart", label: "Type" }, { key: "matkl", label: "Group" }, { key: "werks", label: "Plant" }, { key: "vpsta", label: "Views" },
      { key: "deleted", label: "Del.", render: x => x.deleted ? badge("X", "B") : "" }, { key: "mmsta", label: "Status", render: x => x.mmsta || x.mstae || "" },
      { key: "bklas", label: "Val. class" }, { key: "vprsv", label: "PC" }, { key: "price", label: "Price", type: "amt" }, { key: "peinh", label: "per", type: "int" },
      { key: "lbkum", label: "Stock", type: "qty" }, { key: "salk3", label: "Value", type: "amt", sum: true }, { key: "ersda", label: "Created", type: "date" },
      { key: "ernam", label: "By" }, { key: "laeda", label: "Changed", type: "date" }] }));
    msg("S", `${r.length} entries`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); exec();
} });

// ------------------------------------------------------------------ Exim
register("ZEXIM", { title: "Control for Exim (Material) - Foreign Trade & Legal Control", async render(app, params) {
  await meta();
  const body = out(), edit = out();
  app.append(body, edit);
  const exec = async () => {
    const r = await run(() => api("/api/md/exim")); if (!r) return;
    body.innerHTML = "";
    body.append(alv({ title: "Commodity codes, origin and import / export control", rows: r, columns: [
      { key: "matnr", label: "Material", link: x => openEdit(x) }, { key: "maktx", label: "Description" }, { key: "mtart", label: "Type" },
      { key: "stawn", label: "HS code" }, { key: "herkl", label: "Origin" }, { key: "impctl", label: "Import", render: x => x.impctl ? badge(MD.exim[x.impctl], x.impctl === "B" ? "B" : "Q") : "" },
      { key: "expctl", label: "Export", render: x => x.expctl ? badge(MD.exim[x.expctl], "Q") : "" }, { key: "lic_no", label: "License" },
      { key: "lic_valid", label: "Valid to", type: "date", cls: x => x.lic_valid && x.lic_valid < today() ? "neg" : "" }, { key: "duty", label: "Duty %", type: "amt" }] }));
    msg("S", "Click a material to maintain its foreign trade data");
  };
  function openEdit(x) {
    const t = MD.types[x.mtart];
    if (!t.views.includes("X")) return msg("E", `Foreign trade view not allowed for material type ${x.mtart} (OMS2)`, "M3", "803");
    const f = form(MV.X, x, false);
    edit.innerHTML = "";
    edit.append(panel(`Foreign trade data ${x.matnr} ${x.maktx}`, f, h("p.muted", null, "L = license required: purchase orders from foreign vendors need a valid license. B = embargo: blocked.")));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api(`/api/md/material/${enc(x.matnr)}/change`, { method: "POST", body: { exim: f.get(), tcode: "ZEXIM" } }));
      if (r) { msg("S", r.message); edit.innerHTML = ""; exec(); }
    } }, { label: "Refresh", ghost: true, onClick: exec }]);
  }
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: exec }]);
  await exec();
  if (params.id) { const r = await api("/api/md/exim"); const x = r.find(y => y.matnr === params.id.toUpperCase()); if (x) openEdit(x); }
} });

// ------------------------------------------------------------------ Brazil
register("ZMM02_BR", { title: "Change Material (Brazil) - NCM, Usage, Origin", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "", list: "dl-md-matnr", upper: true, w: "l" }), w = sel(plantOpts(), "1000"),
    ncm = inp({ w: "m", ph: "9403.40.00" }), use = sel(opts(MD.br_usage), "0", { w: "l" }), org = sel(opts(MD.br_origin), "0", { w: "l" }), cfop = inp({ w: "s" }), body = out();
  app.append(panel("Material - Brazilian tax data (J1BTAX / MM02 foreign trade)", grid(field("Material", k, { req: true }), field("Plant", w),
    field("NCM code", ncm, { req: true, hint: "NNNN.NN.NN" }), field("Material usage", use), field("Material origin", org), field("CFOP category", cfop))), body);
  const list = async () => { const r = await api("/api/md/cin"); body.innerHTML = ""; body.append(alv({ title: "Materials with Brazilian data", rows: r.brazil, columns: [
    { key: "matnr", label: "Material", link: x => { k.value = x.matnr; ncm.value = x.steuc; use.value = x.mtuse; org.value = x.mtorg; cfop.value = x.cfop_cat; } }, { key: "maktx", label: "Description" },
    { key: "werks", label: "Plant" }, { key: "steuc", label: "NCM" }, { key: "mtuse", label: "Usage", render: x => `${x.mtuse} ${MD.br_usage[x.mtuse]}` },
    { key: "mtorg", label: "Origin", render: x => `${x.mtorg} ${MD.br_origin[x.mtorg]}` }, { key: "cfop_cat", label: "CFOP cat." }] })); };
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api(`/api/md/material/${enc(up(k))}/brazil`, { method: "POST", body: { werks: w.value, steuc: val(ncm), mtuse: use.value, mtorg: org.value, cfop_cat: val(cfop) } }));
    if (r) { msg("S", r.message); list(); }
  } }]);
  list();
} });

// ------------------------------------------------------------------ J1ID (CIN)
function j1id(tcode, title, tab) {
  register(tcode, { title, async render(app, params) {
    await meta();
    const r = await run(() => api("/api/md/cin")); if (!r) return;
    const matF = () => { const k = inp({ list: "dl-md-matnr", upper: true, w: "l" }), w = sel(plantOpts(), "1000"),
      c = sel(opts(MD.chapters), Object.keys(MD.chapters)[0], { w: "xl" }), t = sel(opts(MD.cin_mtypes), "R", { w: "l" }), sub = h("input", { type: "checkbox" });
      return h("div", null, panel("Material and chapter ID combination", grid(field("Material", k, { req: true }), field("Plant", w), field("Chapter ID (HSN)", c), field("Material type", t), field("Subcontracting", sub)),
        h("button.btn.primary", { type: "button", on: { click: async () => { const x = await run(() => api(`/api/md/material/${enc(up(k))}/cin`, { method: "POST", body: { werks: w.value, chapid: c.value, mtype: t.value, subcon: sub.checked } })); if (x) { msg("S", x.message); go(tcode); } } } }, "Save")),
        alv({ compact: true, rows: r.materials, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "werks", label: "Plant" },
          { key: "chapid", label: "Chapter ID" }, { key: "hsn", label: "HSN" }, { key: "mtype", label: "Type", render: x => `${x.mtype} ${MD.cin_mtypes[x.mtype]}` }, { key: "gst", label: "GST %", type: "amt" }] })); };
    const partF = (kind) => { const isV = kind === "K";
      const k = inp({ list: isV ? "dl-md-lifnr" : "dl-md-kunnr", upper: true, w: "l" }), pan = inp({ upper: true, w: "m", ph: "AAAAA9999A" }), gst = inp({ upper: true, w: "l", ph: "99AAAAA9999A9Z9" }),
        exc = inp({ upper: true, w: "l" }), ecc = inp({ upper: true, w: "l" }), vt = sel(opts(MD.cin_vtypes), "MA", { w: "l" }), ssi = sel(opts(MD.ssi), ""), cst = inp({ upper: true, w: "l" });
      return h("div", null, panel(isV ? "Vendor excise / GST details" : "Customer excise / GST details", grid(field(isV ? "Vendor" : "Customer", k, { req: true }), field("PAN", pan, { req: true }),
        field("GSTIN", gst, { req: true, hint: "15 chars incl. PAN + check char" }), field("Excise reg. no.", exc), field("ECC no.", ecc), isV ? field("Vendor type", vt) : field("CST no.", cst), isV ? field("SSI status", ssi) : null),
        h("button.btn.primary", { type: "button", on: { click: async () => { const x = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(up(k))}/cin`, { method: "POST",
          body: { pan: up(pan), gstin: up(gst), excise_reg: up(exc), ecc_no: up(ecc), vtype: vt.value, ssi: ssi.value, cst_no: up(cst) } })); if (x) { msg("S", x.message); go(tcode); } } } }, "Save")),
        alv({ compact: true, rows: isV ? r.vendors : r.customers, columns: [{ key: isV ? "lifnr" : "kunnr", label: isV ? "Vendor" : "Customer" }, { key: "name", label: "Name" }, { key: "city", label: "City" },
          { key: "pan", label: "PAN" }, { key: "gstin", label: "GSTIN" }, { key: "excise_reg", label: "Excise reg." }, isV ? { key: "vtype", label: "Type", render: x => `${x.vtype} ${MD.cin_vtypes[x.vtype]}` } : { key: "cst_no", label: "CST" }] })); };
    const chap = alv({ compact: true, rows: Object.entries(MD.chapters).map(([k, v]) => ({ chapid: k, text: v[0], gst: v[1] })), columns: [{ key: "chapid", label: "Chapter ID" }, { key: "text", label: "Description" }, { key: "gst", label: "GST %", type: "int" }] });
    const all = [["Material & chapter ID", matF()], ["Customer excise details", partF("D")], ["Vendor excise details", partF("K")], ["Chapter IDs", chap]];
    const order = tab === "cust" ? [1, 0, 2, 3] : tab === "vend" ? [2, 0, 1, 3] : [0, 1, 2, 3];
    app.append(tabsUI(order.map(i => all[i])));
    msg("S", "CIN master data (India): PAN format and GSTIN check character are validated");
  } });
}
j1id("J1ID", "Excise Rate / CIN Master Data Maintenance", "mat");
j1id("ZJ1ID_MAT", "Change Material (CIN)", "mat");
j1id("ZJ1ID_CUS", "Customer India (CIN)", "cust");
j1id("ZJ1ID_VEN", "Vendor India (CIN)", "vend");

// ================================================================== customers & vendors
const CG = [{ k: "name", l: "Name", req: 1, w: "xl" }, { k: "name2", l: "Name 2", w: "xl" }, { k: "street", l: "Street / house no.", w: "xl" }, { k: "pstlz", l: "Postal code", w: "s" },
  { k: "city", l: "City" }, { k: "region", l: "Region", t: "sel", o: () => MD.districts, e: 1 }, { k: "land", l: "Country", t: "sel", o: () => MD.countries, d: "EG" },
  { k: "telf1", l: "Telephone" }, { k: "email", l: "E-mail", w: "l" }, { k: "stcd1", l: "Tax number 1", hint: "EG: 999-999-999" }, { k: "stceg", l: "VAT reg. no.", w: "l" },
  { k: "bankn", l: "Bank account", w: "l" }, { k: "bankl", l: "Bank key" }];
const CC = [{ k: "akont", l: "Reconciliation acct", t: "sel", o: () => Object.fromEntries(MD.recon.filter(a => a.recon === "D").map(a => [a.hkont, a.txt])), e: 1 },
  { k: "zterm", l: "Terms of payment", t: "sel", o: () => MD.terms, e: 1 }, { k: "klimk", l: "Credit limit (EGP)", t: "num" }, { k: "mahna", l: "Dunning procedure", t: "sel", o: () => MD.dunning },
  { k: "zwels", l: "Payment methods", up: 1, d: "T" }, { k: "xzver", l: "Record pmnt history", t: "chk" }, { k: "busab", l: "Accounting clerk" }];
const CS = [{ k: "bzirk", l: "Sales district", t: "sel", o: () => MD.districts, e: 1 }, { k: "kdgrp", l: "Customer group", t: "sel", o: () => MD.custgroups, e: 1 },
  { k: "konda", l: "Price group", t: "sel", o: () => MD.pricegroups, e: 1 }, { k: "kalks", l: "Cust. pric. procedure", t: "sel", o: () => MD.pricing, req: 1 },
  { k: "vsbed", l: "Shipping conditions", t: "sel", o: () => MD.shipping, req: 1 }, { k: "vwerk", l: "Delivering plant", t: "sel", o: () => Object.fromEntries(MD.plants.map(p => [p.werks, p.name])) },
  { k: "inco1", l: "Incoterms", t: "sel", o: () => MD.incoterms, e: 1 }, { k: "inco2", l: "Incoterms (part 2)" }, { k: "zterm", l: "Terms of payment", t: "sel", o: () => MD.terms, req: 1 },
  { k: "ktgrd", l: "Acct assgmt group", t: "sel", o: () => MD.ktgrd, req: 1 }, { k: "taxkd", l: "Tax classification", t: "sel", o: () => MD.taxcl }, { k: "waers", l: "Currency", t: "sel", o: () => MD.currencies, d: "EGP" }];
const VG = [...CG.filter(f => f.k !== "region"), { k: "iban", l: "IBAN", w: "xl" }, { k: "swift", l: "SWIFT / BIC", up: 1 }];
const VC = [{ k: "akont", l: "Reconciliation acct", t: "sel", o: () => Object.fromEntries(MD.recon.filter(a => a.recon === "K").map(a => [a.hkont, a.txt])), e: 1 },
  { k: "zterm", l: "Terms of payment", t: "sel", o: () => MD.terms, e: 1 }, { k: "zwels", l: "Payment methods", up: 1, d: "T" }, { k: "reprf", l: "Check double invoice", t: "chk", d: 1 },
  { k: "witht", l: "Withholding tax type", up: 1 }, { k: "busab", l: "Accounting clerk" }];
const VP = [{ k: "waers", l: "Order currency", t: "sel", o: () => MD.currencies, d: "EGP" }, { k: "minbw", l: "Minimum order value", t: "num" },
  { k: "ekgrp", l: "Purchasing group", t: "sel", o: () => MD.purch_groups, e: 1 }, { k: "plifz", l: "Planned deliv. time", t: "num" }, { k: "webre", l: "GR-based inv. verif.", t: "chk", d: 1 },
  { k: "verkf", l: "Salesperson" }, { k: "lfabc", l: "ABC indicator", up: 1, w: "s" }, { k: "inco1", l: "Incoterms", t: "sel", o: () => MD.incoterms, e: 1 }, { k: "inco2", l: "Incoterms (part 2)" }];

// parts: g general, c company code, s sales area / purchasing
function partnerScreen(kind, tcode, mode, parts, title) {
  const isV = kind === "K";
  register(tcode, { title, async render(app, params) {
    await meta();
    const groups = isV ? MD.vend_groups : MD.cust_groups;
    const key = inp({ value: params.id || "", list: isV ? "dl-md-lifnr" : "dl-md-kunnr", upper: true, w: "l" });
    const grp = sel(Object.entries(groups).map(([k, g]) => [k, `${k} ${g.text}`]), isV ? "0001" : "0001", { w: "l" });
    const vtweg = sel(opts(MD.channels), params.vtweg || "10", { w: "m" });
    const body = out();
    app.append(panel(isV ? "Vendor" : "Customer", grid(field(isV ? "Vendor" : "Customer", key, { hint: mode === "create" ? "internal number range: leave empty" : "" }),
      mode === "create" ? field("Account group", grp, { req: true }) : null, field("Company code", inp({ value: "1000 MM Core Egypt", readonly: true, w: "l" })),
      parts.includes("s") ? (isV ? field("Purchasing organization", inp({ value: "1000", readonly: true, w: "s" })) : field("Sales area", h("span", null, "1000 / ", vtweg, " / 00"))) : null)), body);
    const info = () => { const g = groups[grp.value]; return h("p.muted", null, `Account group ${grp.value}: required ${g.req.join(", ")}${g.sup.length ? " · suppressed " + g.sup.join(", ") : ""}${g.partners ? " · partner functions " + g.partners : ""}`); };

    function build(d, ro) {
      const tabs = [], forms = {};
      if (parts.includes("g")) { forms.g = form(isV ? VG : CG, d, ro); tabs.push(["General data", forms.g]); }
      if (parts.includes("c")) { forms.c = form(isV ? VC : CC, d, ro); tabs.push(["Company code data", forms.c]); }
      if (parts.includes("s")) {
        if (isV) { forms.s = form(VP, d, ro); tabs.push(["Purchasing data", forms.s]); }
        else { const a = (d.sales || []).find(s => s.vtweg === vtweg.value) || { vwerk: "1000", waers: "EGP", taxkd: vtweg.value === "20" ? "0" : "1", kalks: vtweg.value === "20" ? "2" : "1", vsbed: "01", ktgrd: vtweg.value === "20" ? "02" : "01", zterm: d.zterm || "NT30" };
          forms.s = form(CS, a, ro); tabs.push([`Sales area 1000/${vtweg.value}/00`, forms.s]);
          const pf = (d.partners || []).filter(p => p.vtweg === vtweg.value);
          forms.p = h("div", null, alv({ compact: true, rows: pf, columns: [{ key: "parvw", label: "Function" }, { key: "text", label: "Name" }, { key: "kunn2", label: "Partner" }, { key: "name", label: "Partner name" }] }));
          if (!ro) { const e1 = sel(opts(MD.partners), "WE", { w: "l" }), e2 = inp({ list: "dl-md-kunnr", upper: true, w: "m" }); forms.p.extra = [e1, e2];
            forms.p.append(h("p.muted", null, "Add a partner (e.g. ship-to party of account group 0002):"), grid(field("Function", e1), field("Partner", e2))); }
          tabs.push(["Partner functions", forms.p]); }
      }
      return { tabs, forms };
    }
    function collect(forms) {
      const b = {};
      if (forms.g) Object.assign(b, forms.g.get());
      if (forms.c) Object.assign(b, forms.c.get());
      if (forms.s) { if (isV) Object.assign(b, forms.s.get()); else b.sales = [Object.assign({ vkorg: "1000", vtweg: vtweg.value, spart: "00" }, forms.s.get())]; }
      if (forms.p && forms.p.extra && forms.p.extra[1].value) b.partners = [{ parvw: forms.p.extra[0].value, kunn2: up(forms.p.extra[1]) }];
      return b;
    }
    async function start() {
      body.innerHTML = "";
      if (mode === "create") {
        const k = up(key);
        if (!isV && tcode === "VD01" && k && MD.customers.find(c => c.kunnr === k)) return load();
        const g = groups[grp.value];
        const d = { land: isV && grp.value === "0003" ? "CN" : "EG", akont: g.sup.includes("akont") ? "" : (isV ? (grp.value === "0003" ? "161000" : "160000") : "140000"), zterm: g.sup.includes("zterm") ? "" : "NT30", zwels: "T", waers: "EGP", reprf: 1, webre: 1 };
        const { tabs, forms } = build(d, false);
        body.append(info(), tabsUI(tabs));
        toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
          const b = collect(forms); b.tcode = tcode; if (isV) b.ktokk = grp.value; else b.ktokd = grp.value;
          if (k) b[isV ? "lifnr" : "kunnr"] = k;
          const r = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}`, { method: "POST", body: b }));
          if (r) { await meta(true); const id = r.lifnr || r.kunnr; body.innerHTML = ""; const wb = warnBox(r.warnings); if (wb) body.append(wb);
            msgLink(r.warnings && r.warnings.length ? "W" : "S", r.message, "Display", isV ? "XK03" : "XD03", { id }); }
        } }, { label: "Back", ghost: true, onClick: () => go(tcode) }]);
      } else load();
    }
    async function load() {
      const k = up(key); if (!k) return msg("E", `Enter a ${isV ? "vendor" : "customer"}`);
      const d = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(k)}`)); if (!d) return;
      body.innerHTML = "";
      const ro = mode === "display";
      const { tabs, forms } = build(d, ro);
      const stat = [d.sperr ? badge("Posting block", "B") : null, d.sperm ? badge("Purchasing block", "B") : null, d.zahls ? badge("Payment block " + d.zahls, "B") : null,
        d.aufsd ? badge("Order block " + d.aufsd, "B") : null, d.faksd ? badge("Billing block " + d.faksd, "B") : null, d.lifsd ? badge("Delivery block " + d.lifsd, "B") : null,
        d.loevm ? badge("Deletion flag", "B") : null, d.payment_exception ? badge(d.payment_exception, "Q") : null].filter(Boolean);
      body.append(panel(null, h("div.doc-head", null, h("div", null, h("div.k", null, isV ? "Vendor" : "Customer"), h("div.v", null, `${k} ${d.name}`)),
        h("div", null, h("div.k", null, "Account group"), h("div.v", null, `${d.ktokk || d.ktokd} ${d.ktokk_text || d.ktokd_text}`)),
        h("div", null, h("div.k", null, "Balance (open items)"), h("div.v", null, `${fmtAmt(d.open_balance)} EGP · ${d.open_items} item(s)`)),
        h("div", null, h("div.k", null, "Status"), h("div.v", null, stat.length ? stat : badge("Active", "U"))))));
      if (ro) {
        tabs.push(["Changes", changeGrid(d.changes)]);
        if (d.cin) tabs.push(["CIN (India)", form([{ k: "pan", l: "PAN" }, { k: "gstin", l: "GSTIN", w: "l" }, { k: "excise_reg", l: "Excise reg." }, { k: "ecc_no", l: "ECC no." }], d.cin, true)]);
        if (d.sensitive && d.sensitive.length) tabs.push(["Sensitive changes", alv({ compact: true, rows: d.sensitive, columns: [{ key: "fields", label: "Fields" }, { key: "changed_by", label: "Changed by" },
          { key: "changed_at", label: "At" }, { key: "status", label: "Status", render: r => r.status === "P" ? badge("Not confirmed", "B") : r.status === "C" ? badge("Confirmed", "U") : badge("Rejected", "Q") }, { key: "confirmed_by", label: "Confirmed by" }] })]);
      }
      body.append(tabsUI(tabs));
      if (ro) toolbar([{ label: "Change", primary: true, onClick: () => go(isV ? "XK02" : "XD02", { id: k }) }, { label: "Logistics/Financial", ghost: true, onClick: () => go(isV ? "ZXK03_LF" : "ZXD03_LF", { id: k }) },
        { label: "Block (" + (isV ? "XK05" : "XD05") + ")", ghost: true, onClick: () => go(isV ? "XK05" : "XD05", { id: k }) }]);
      else toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
        const b = collect(forms); b.tcode = tcode;
        const r = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(k)}/change`, { method: "POST", body: b }));
        if (r) { const wb = warnBox(r.warnings); if (wb) body.prepend(wb); msgLink(r.sensitive && r.sensitive.length ? "W" : "S", r.message, r.sensitive && r.sensitive.length ? "Confirm (" + (isV ? "FK08" : "FD08") + ")" : "Changes", r.sensitive && r.sensitive.length ? (isV ? "FK08" : "FD08") : (isV ? "XK04" : "XD04"), { id: k }); }
      } }, { label: "Back", ghost: true, onClick: () => go(tcode) }]);
      if (ro) msg("S", `${isV ? "Vendor" : "Customer"} ${k} displayed`);
    }
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: start }]);
    if (params.id && mode !== "create") load();
  } });
}
partnerScreen("D", "XD01", "create", "gcs", "Create Customer (Centrally)");
partnerScreen("D", "XD02", "change", "gcs", "Change Customer (Centrally)");
partnerScreen("D", "XD03", "display", "gcs", "Display Customer (Centrally)");
partnerScreen("D", "FD01", "create", "gc", "Create Customer (Accounting)");
partnerScreen("D", "FD02", "change", "gc", "Change Customer (Accounting)");
partnerScreen("D", "FD03", "display", "gc", "Display Customer (Accounting)");
partnerScreen("D", "VD01", "create", "gcs", "Create Customer (Sales) / Extend Sales Area");
partnerScreen("D", "VD02", "change", "gs", "Change Customer (Sales)");
partnerScreen("D", "VD03", "display", "gs", "Display Customer (Sales)");
partnerScreen("K", "XK01", "create", "gcs", "Create Vendor (Centrally)");
partnerScreen("K", "XK02", "change", "gcs", "Change Vendor (Centrally)");
partnerScreen("K", "XK03", "display", "gcs", "Display Vendor (Centrally)");
partnerScreen("K", "FK01", "create", "gc", "Create Vendor (Accounting)");
partnerScreen("K", "FK02", "change", "gc", "Change Vendor (Accounting)");
partnerScreen("K", "FK03", "display", "gc", "Display Vendor (Accounting)");
partnerScreen("K", "MK01", "create", "gs", "Create Vendor (Purchasing)");
partnerScreen("K", "MK02", "change", "gs", "Change Vendor (Purchasing)");
partnerScreen("K", "MK03", "display", "gs", "Display Vendor (Purchasing)");

// ------------------------------------------------------------------ blocks / deletion / account group
function blockScreen(kind, tcode) {
  const isV = kind === "K";
  register(tcode, { title: isV ? "Block / Unblock Vendor" : "Block / Unblock Customer", async render(app, params) {
    await meta();
    const k = inp({ value: params.id || "", list: isV ? "dl-md-lifnr" : "dl-md-kunnr", upper: true, w: "l" }), body = out();
    app.append(panel(isV ? "Vendor" : "Customer", grid(field(isV ? "Vendor" : "Customer", k, { req: true }))), body);
    const reasons = { "": "-", "01": "Credit limit", "02": "Legal / dispute", "08": "Overdue items", "10": "Other" };
    const load = async () => {
      const d = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(up(k))}`)); if (!d) return;
      body.innerHTML = "";
      const sperr = h("input", { type: "checkbox", checked: !!d.sperr });
      let els;
      if (isV) { const sperm = h("input", { type: "checkbox", checked: !!d.sperm }), zahls = sel([["", "- no block"], ["A", "A Blocked for payment"], ["R", "R Invoice verification"], ["*", "* Skip account"]], d.zahls || "");
        els = { sperr, sperm, zahls };
        body.append(panel(`${d.lifnr} ${d.name}`, grid(field("Posting block (company code)", sperr), field("Purchasing block", sperm), field("Payment block", zahls)),
          h("p.muted", null, `Open items ${fmtAmt(d.open_balance)} EGP · purchasing block stops new POs (ME21N), posting block stops invoices and payments, payment block only F110.`)));
      } else { const aufsd = sel(opts(reasons), d.aufsd || ""), lifsd = sel(opts(reasons), d.lifsd || ""), faksd = sel(opts(reasons), d.faksd || "");
        els = { sperr, aufsd, lifsd, faksd };
        body.append(panel(`${d.kunnr} ${d.name}`, grid(field("Posting block (company code)", sperr), field("Order block", aufsd), field("Delivery block", lifsd), field("Billing block", faksd)),
          h("p.muted", null, `Open items ${fmtAmt(d.open_balance)} EGP · credit exposure ${fmtAmt(d.exposure)} / limit ${fmtAmt(d.klimk)}`)));
      }
      toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
        const b = {}; for (const [f, e] of Object.entries(els)) b[f] = e.type === "checkbox" ? (e.checked ? 1 : 0) : e.value;
        const r = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(up(k))}/block`, { method: "POST", body: b }));
        if (r) msgLink("S", r.message + (r.open_po_items ? ` · ${r.open_po_items} open PO item(s) remain` : ""), "Changes", isV ? "XK04" : "XD04", { id: up(k) });
      } }]);
    };
    toolbar([{ label: "Continue", key: "Enter", primary: true, onClick: load }]);
    if (params.id) load();
  } });
}
blockScreen("K", "XK05"); blockScreen("D", "XD05");

function deleteScreen(kind, tcode) {
  const isV = kind === "K";
  register(tcode, { title: isV ? "Mark Vendor for Deletion" : "Mark Customer for Deletion", async render(app, params) {
    await meta();
    const k = inp({ value: params.id || "", list: isV ? "dl-md-lifnr" : "dl-md-kunnr", upper: true, w: "l" }), f = h("input", { type: "checkbox", checked: true });
    app.append(panel(isV ? "Vendor" : "Customer", grid(field(isV ? "Vendor" : "Customer", k, { req: true }), field("Deletion flag (all areas)", f)),
      h("p.muted", null, "A deletion flag stops purchasing / billing. The account can only be archived when no open items remain.")));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(up(k))}/delete`, { method: "POST", body: { flag: f.checked } }));
      if (r) msg(r.open_items ? "W" : "S", r.message + (r.open_items ? ` - ${r.open_items} open item(s), balance ${fmtAmt(r.open_balance)}: cannot be archived yet` : ""));
    } }]);
  } });
}
deleteScreen("K", "XK06"); deleteScreen("D", "XD06");

function groupScreen(kind, tcode) {
  const isV = kind === "K";
  register(tcode, { title: isV ? "Change Vendor Account Group" : "Change Customer Account Group", async render(app, params) {
    await meta();
    const groups = isV ? MD.vend_groups : MD.cust_groups;
    const k = inp({ value: params.id || "", list: isV ? "dl-md-lifnr" : "dl-md-kunnr", upper: true, w: "l" }), g = sel(Object.entries(groups).map(([x, y]) => [x, `${x} ${y.text}`]), "0001", { w: "l" });
    app.append(panel("New account group", grid(field(isV ? "Vendor" : "Customer", k, { req: true }), field("New account group", g)),
      h("p.muted", null, "Allowed only when the number lies in the interval of the new group and the required data exists.")));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api(`/api/md/${isV ? "vendor" : "customer"}/${enc(up(k))}/group`, { method: "POST", body: isV ? { ktokk: g.value } : { ktokd: g.value } }));
      if (r) { msg("S", r.message); meta(true); }
    } }]);
  } });
}
groupScreen("K", "XK07"); groupScreen("D", "XD07");

// ------------------------------------------------------------------ FK08/FK09 FD08/FD09
function sensScreen(kind, tcode, all) {
  const isV = kind === "K";
  register(tcode, { title: (all ? "Display Changes to Sensitive Fields: " : "Confirm Change: ") + (isV ? "Vendor" : "Customer") + (all ? "s (List)" : " (Dual Control)"), async render(app, params) {
    await meta();
    const body = out();
    app.append(panel(null, h("p", null, "Sensitive fields (bank details, payment terms, reconciliation account" + (isV ? ", payment methods" : ", credit limit") +
      ") need a second person to confirm. Until then " + (isV ? "the vendor is excluded from the payment run (F110)." : "the change is flagged.")),
      h("p.muted", null, `You are logged on as ${S.user || "the current user"} - you cannot confirm your own changes.`)), body);
    const exec = async () => {
      const r = await run(() => api(`/api/md/sensitive?koart=${kind}${all ? "&status=all" : ""}`)); if (!r) return;
      body.innerHTML = "";
      body.append(alv({ rows: r, columns: [{ key: "objectid", label: isV ? "Vendor" : "Customer", link: x => go(isV ? "XK03" : "XD03", { id: x.objectid }) }, { key: "name", label: "Name" },
        { key: "fields", label: "Fields" }, { key: "details", label: "Old → new", render: x => x.details.map(d => `${d.fname}: ${d.value_old || "∅"} → ${d.value_new}`).join(" · ") },
        { key: "changed_by", label: "Changed by" }, { key: "changed_at", label: "At" }, isV ? { key: "open_balance", label: "Open items", type: "amt" } : null,
        { key: "status", label: "Status", render: x => x.status === "P" ? badge("Not confirmed", "B") : x.status === "C" ? badge("Confirmed", "U") : badge("Rejected", "Q") },
        { key: "confirmed_by", label: "Confirmed by" },
        all ? null : { key: "act", label: "Action", render: x => h("span", null,
          h("button.btn.primary", { type: "button", on: { click: () => act(x, false) } }, "Confirm"), " ",
          h("button.btn.ghost", { type: "button", on: { click: () => act(x, true) } }, "Reject")) }].filter(Boolean) }));
      msg("S", `${r.length} ${all ? "change(s)" : "unconfirmed change(s)"}`);
    };
    const act = async (x, reject) => {
      const r = await run(() => api("/api/md/sensitive/confirm", { method: "POST", body: { koart: kind, id: x.objectid, reject } }));
      if (r) { await exec(); msg("S", `${x.objectid}: ${r.message}`); }
    };
    toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: exec }, { label: all ? "Confirm (" + (isV ? "FK08" : "FD08") + ")" : "List (" + (isV ? "FK09" : "FD09") + ")", ghost: true, onClick: () => go(all ? (isV ? "FK08" : "FD08") : (isV ? "FK09" : "FD09")) }]);
    exec();
  } });
}
sensScreen("K", "FK08"); sensScreen("K", "FK09", true); sensScreen("D", "FD08"); sensScreen("D", "FD09", true);

// ------------------------------------------------------------------ lists
register("S_ALR_87012179", { title: "Customer List", async render(app) {
  await meta();
  const g = sel(opts(Object.fromEntries(Object.entries(MD.cust_groups).map(([k, v]) => [k, v.text])), true), ""), b = h("input", { type: "checkbox" }), body = out();
  app.append(panel("Selection", grid(field("Account group", g), field("Only blocked / flagged", b))), body);
  const exec = async () => {
    const r = await run(() => api(`/api/md/customers?ktokd=${g.value}&blocked=${b.checked ? 1 : ""}`)); if (!r) return;
    body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "kunnr", label: "Customer", link: x => go("XD03", { id: x.kunnr }) }, { key: "name", label: "Name" }, { key: "ktokd", label: "Group" },
      { key: "city", label: "City" }, { key: "land", label: "Ctry" }, { key: "stcd1", label: "Tax no." }, { key: "areas", label: "Sales areas" }, { key: "akont", label: "Recon" },
      { key: "zterm", label: "Terms" }, { key: "klimk", label: "Credit limit", type: "amt" }, { key: "open_balance", label: "Open items", type: "amt", sum: true },
      { key: "blocked", label: "Status", render: x => x.loevm ? badge("Deletion flag", "B") : x.blocked ? badge("Blocked", "B") : badge("Active", "U") },
      { key: "erdat", label: "Created", type: "date" }, { key: "ernam", label: "By" }] }));
    msg("S", `${r.length} customers`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); exec();
} });
register("S_ALR_87012086", { title: "Vendor List", async render(app) {
  await meta();
  const g = sel(opts(Object.fromEntries(Object.entries(MD.vend_groups).map(([k, v]) => [k, v.text])), true), ""), b = h("input", { type: "checkbox" }), body = out();
  app.append(panel("Selection", grid(field("Account group", g), field("Only blocked / flagged", b))), body);
  const exec = async () => {
    const r = await run(() => api(`/api/md/vendors?ktokk=${g.value}&blocked=${b.checked ? 1 : ""}`)); if (!r) return;
    body.innerHTML = "";
    body.append(alv({ rows: r, columns: [{ key: "lifnr", label: "Vendor", link: x => go("XK03", { id: x.lifnr }) }, { key: "name", label: "Name" }, { key: "ktokk", label: "Group" },
      { key: "city", label: "City" }, { key: "land", label: "Ctry" }, { key: "stcd1", label: "Tax no." }, { key: "iban", label: "IBAN" }, { key: "swift", label: "SWIFT" },
      { key: "zterm", label: "Terms" }, { key: "waers", label: "Curr." }, { key: "open_balance", label: "Open items", type: "amt", sum: true },
      { key: "blocked", label: "Status", render: x => x.loevm ? badge("Deletion flag", "B") : x.blocked ? badge("Blocked", "B") : x.payment_exception ? badge("Payment held", "Q") : badge("Active", "U") },
      { key: "payment_exception", label: "Payment exception" }] }));
    msg("S", `${r.length} vendors`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); exec();
} });

// ------------------------------------------------------------------ 360 views of partners
register("ZXD03_LF", { title: "Display Customer (Logistics/Financial)", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "", list: "dl-md-kunnr", upper: true, w: "l" }), body = out();
  app.append(panel("Customer", grid(field("Customer", k, { req: true }))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/md/customer/${enc(up(k))}`)); if (!d) return;
    body.innerHTML = "";
    const util = d.klimk ? Math.round(d.exposure / d.klimk * 100) : null;
    body.append(h("div.kpis", null, kpi("Sales volume", fmtShort(d.sales_volume), "billing (net)", null), kpi("Open receivables", fmtShort(d.open_balance), `${d.open_items} open item(s)`, null),
      kpi("Credit limit", d.klimk ? fmtShort(d.klimk) : "none", "FD32", null, d.klimk ? "" : "crit"), kpi("Limit used", util === null ? "-" : util + " %", "exposure / limit", null, util > 90 ? "neg" : util > 70 ? "crit" : "pos"),
      kpi("Status", d.loevm ? "Deletion flag" : d.blocked ? "Blocked" : "Active", d.ktokd + " " + d.ktokd_text, null, d.blocked || d.loevm ? "neg" : "pos")));
    body.append(h("div.cards", null,
      card("Logistics - sales areas", null, alv({ compact: true, rows: d.sales, columns: [{ key: "vtweg", label: "DChl" }, { key: "bzirk", label: "District" }, { key: "kdgrp", label: "Cust. grp" },
        { key: "kalks", label: "Pric. proc." }, { key: "vsbed", label: "Shipping" }, { key: "inco1", label: "Incoterms" }, { key: "inco2", label: "Place" }, { key: "taxkd", label: "Tax" }, { key: "ktgrd", label: "AAG" }] })),
      card("Partner functions", null, alv({ compact: true, rows: d.partners, columns: [{ key: "vtweg", label: "DChl" }, { key: "parvw", label: "Fn" }, { key: "text", label: "Function" }, { key: "kunn2", label: "Partner" }, { key: "name", label: "Name" }] })),
      card("Financial - company code", null, form(CC, d, true)),
      card("Last billing documents", null, alv({ compact: true, rows: d.bills, columns: [{ key: "vbeln", label: "Billing doc" }, { key: "fkdat", label: "Date", type: "date" }, { key: "netwr", label: "Net value", type: "amt", sum: true }] })),
      card("Change history", null, changeGrid(d.changes.slice(0, 10)))));
    msg("S", `Customer ${d.kunnr} ${d.name}`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); if (params.id) exec();
} });

register("ZXK03_LF", { title: "Display Vendor (Logistics/Financial)", async render(app, params) {
  await meta();
  const k = inp({ value: params.id || "", list: "dl-md-lifnr", upper: true, w: "l" }), body = out();
  app.append(panel("Vendor", grid(field("Vendor", k, { req: true }))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/md/vendor/${enc(up(k))}`)); if (!d) return;
    body.innerHTML = "";
    const ev = d.evaluation;
    body.append(h("div.kpis", null, kpi("PO volume", fmtShort(d.po_volume), `${d.pos.length} purchase order(s)`, null), kpi("Open payables", fmtShort(-d.open_balance), `${d.open_items} open item(s)`, null),
      kpi("Evaluation score", ev ? String(ev.total) : "-", ev ? `grade ${ev.grade}` : "ME65", null, ev && ev.total < 70 ? "neg" : "pos"),
      kpi("Payment", d.payment_exception ? "Held" : "Free", d.payment_exception || "F110 will pay", null, d.payment_exception ? "neg" : "pos"),
      kpi("Status", d.loevm ? "Deletion flag" : d.blocked ? "Blocked" : "Active", `${d.ktokk} ${d.ktokk_text}`, null, d.blocked || d.loevm ? "neg" : "pos")));
    body.append(h("div.cards", null,
      card("Logistics - purchasing data", null, form(VP, d, true)),
      card("Financial - company code & bank", null, form([...VC, { k: "iban", l: "IBAN", w: "xl" }, { k: "swift", l: "SWIFT" }, { k: "bankn", l: "Bank account" }], d, true)),
      card("Purchase orders", null, alv({ compact: true, rows: d.pos, columns: [{ key: "ebeln", label: "PO", link: r => go("ME23N", { id: r.ebeln }) }, { key: "bedat", label: "Date", type: "date" }, { key: "items", label: "Items", type: "int" }, { key: "frgke", label: "Release" }] })),
      card("Info records", null, alv({ compact: true, rows: d.info_records, columns: [{ key: "infnr", label: "Info rec." }, { key: "matnr", label: "Material" }, { key: "netpr", label: "Gross price", type: "amt" }, { key: "peinh", label: "per", type: "int" }, { key: "aplfz", label: "Lead time", type: "int" }] })),
      card("Change history", null, changeGrid(d.changes.slice(0, 10)))));
    msg("S", `Vendor ${d.lifnr} ${d.name}`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); if (params.id) exec();
} });

// ------------------------------------------------------------------ customizing
function custTable(tcode, title, rowsFn, columns, note) {
  register(tcode, { title, async render(app) {
    await meta();
    const r = await rowsFn();
    app.append(note ? panel(null, h("p.muted", null, note)) : "", alv({ rows: r, columns }));
    msg("S", `${r.length} entries (display)`);
  } });
}
custTable("OMS2", "Material Types (Views, Price Control, Valuation)", () => Object.entries(MD.types).map(([k, t]) => ({ mtart: k, text: t.text, views: [...t.views].map(v => MD.views[v]).join(", "), vprsv: t.vprsv, fixed: t.fixed ? "mandatory" : "default", bklas: t.bklas.join(", "), ref: t.ref, ext: t.ext ? "internal + external" : "internal" })),
  [{ key: "mtart", label: "Type" }, { key: "text", label: "Description" }, { key: "views", label: "Allowed views" }, { key: "vprsv", label: "Price ctrl" }, { key: "fixed", label: "PC" }, { key: "ref", label: "Acct cat. ref." }, { key: "bklas", label: "Valuation classes" }, { key: "ext", label: "Numbering" }],
  "The material type controls which views can be maintained (MM01), the price control and the allowed valuation classes (account determination).");
custTable("OMS3", "Industry Sectors", () => Object.entries(MD.sectors).map(([k, t]) => ({ k, t })), [{ key: "k", label: "Sector" }, { key: "t", label: "Description" }]);
custTable("OMS4", "Material Statuses", () => Object.entries(MD.status).map(([k, s]) => ({ k, t: s[0], purch: s[1], inv: s[2], sales: s[3], cost: s[4], bom: s[5] })),
  [{ key: "k", label: "Status" }, { key: "t", label: "Description" }, { key: "purch", label: "Purchasing" }, { key: "inv", label: "Inventory mgmt" }, { key: "sales", label: "Sales" }, { key: "cost", label: "Costing" }, { key: "bom", label: "BOM" }],
  "A = warning, B = error (transaction blocked). X-plant status (basic data) and plant-specific status (purchasing / MRP view).");
custTable("OMSF", "Material Groups", () => Object.entries(MD.groups).map(([k, t]) => ({ k, t })), [{ key: "k", label: "Material group" }, { key: "t", label: "Description" }]);
custTable("OMSK", "Valuation Classes & Account Category Reference", () => Object.entries(MD.valclasses).map(([k, v]) => ({ k, t: v[0], ref: v[1], types: Object.entries(MD.types).filter(([, t]) => t.bklas.includes(k)).map(([m]) => m).join(", ") })),
  [{ key: "k", label: "Val. class" }, { key: "t", label: "Description" }, { key: "ref", label: "Acct cat. ref." }, { key: "types", label: "Material types" }]);
custTable("CUNI", "Units of Measure", () => Object.entries(MD.units).map(([k, t]) => ({ k, t })), [{ key: "k", label: "Unit" }, { key: "t", label: "Text" }]);
const grpRows = g => Object.entries(g).map(([k, v]) => ({ k, t: v.text, nr: v.nr, req: v.req.join(", "), sup: v.sup.join(", "), partners: v.partners || "" }));
const grpCols = [{ key: "k", label: "Group" }, { key: "t", label: "Name" }, { key: "nr", label: "Number range" }, { key: "req", label: "Required fields" }, { key: "sup", label: "Suppressed fields" }];
custTable("OBD2", "Customer Account Groups (Field Status, Number Range, Partners)", () => grpRows(MD.cust_groups), [...grpCols, { key: "partners", label: "Partner functions" }]);
custTable("OBD3", "Vendor Account Groups (Field Status, Number Range)", () => grpRows(MD.vend_groups), grpCols);
const rangeCols = [{ key: "nr", label: "No." }, { key: "frm", label: "From" }, { key: "to", label: "To" }, { key: "ext", label: "Ext." }, { key: "current", label: "Highest used" }, { key: "used", label: "Used", type: "int" }, { key: "groups", label: "Account groups" }];
custTable("XDN1", "Number Ranges for Customer Accounts", async () => (await api("/api/md/ranges")).filter(r => r.kind === "Customer"), rangeCols);
custTable("XKN1", "Number Ranges for Vendor Accounts", async () => (await api("/api/md/ranges")).filter(r => r.kind === "Vendor"), rangeCols);

// ================================================================== cockpit & process
register("ZMD_COCKPIT", { title: "Master Data Cockpit - Quality, Risk & Governance", async render(app) {
  await meta();
  const days = inp({ type: "number", value: 60, w: "s" }), body = out();
  app.append(panel("Parameters", grid(field("Dead stock: no issue for (days)", days))), body);
  const exec = async () => {
    const d = await run(() => api(`/api/md/cockpit?days=${days.value}`)); if (!d) return;
    body.innerHTML = ""; const k = d.kpi;
    body.append(h("div.kpis", null,
      kpi("Data quality", k.quality + " %", "records without errors", null, k.quality < 90 ? "crit" : "pos"),
      kpi("Materials", String(k.materials), `${k.flagged} flagged for deletion`, "MM60"),
      kpi("Customers", String(k.customers), `${k.blocked_customers} blocked`, "S_ALR_87012179"),
      kpi("Vendors", String(k.vendors), `${k.blocked_vendors} blocked`, "S_ALR_87012086"),
      kpi("Errors / warnings", `${k.errors} / ${k.warnings}`, "records that block the business", null, k.errors ? "neg" : "pos"),
      kpi("Unconfirmed changes", String(k.pending), `payments held ${fmtShort(k.held)}`, "FK08", k.pending ? "neg" : "pos"),
      kpi("Dead stock", fmtShort(k.dead_value), `${k.dead_items} item(s), no issue for ${d.days} days`, "MM60", k.dead_value ? "crit" : "pos"),
      kpi("Duplicate suspects", String(k.duplicates), "same tax no. / bank / name", null, k.duplicates ? "crit" : "pos"),
      kpi("Changes (30 days)", String(k.changes_30), "change documents", "MM04")));
    body.append(alv({ title: "Issues to fix - sorted by severity and value", rows: d.issues, columns: [
      { key: "sev", label: "", render: r => r.sev === "E" ? badge("Error", "B") : badge("Warning", "Q") }, { key: "obj", label: "Object" },
      { key: "key", label: "Key", link: r => go(r.obj === "Material" ? "MM03" : r.obj === "Vendor" ? "XK03" : "XD03", { id: r.key }) }, { key: "name", label: "Name" },
      { key: "issue", label: "Issue" }, { key: "value", label: "Value at risk", type: "amt" }, { key: "tcode", label: "Fix with", link: r => go(r.tcode, { id: r.key }) }] }));
    body.append(h("div.cards", null,
      card("Dead stock - candidates for scrapping / sale", `no goods issue for ${d.days} days (key date ${fmtDate(d.key_date)})`, d.dead.length ? alv({ compact: true, rows: d.dead, columns: [
        { key: "matnr", label: "Material", link: r => go("ZMM03_LF", { id: r.matnr }) }, { key: "maktx", label: "Description" }, { key: "bwkey", label: "Plant" },
        { key: "lbkum", label: "Stock", type: "qty" }, { key: "salk3", label: "Value", type: "amt", sum: true }, { key: "last_mv", label: "Last movement", type: "date" }] }) : h("p.pos", null, "✔ No dead stock")),
      card("Stock value by material type", null, bars(d.by_type, x => `${x.mtart} ${x.text} (${x.n})`, x => x.value)),
      card("Who changes master data", "change documents by user and object", alv({ compact: true, rows: d.activity, columns: [{ key: "user", label: "User" }, { key: "obj", label: "Object" }, { key: "n", label: "Fields changed", type: "int" }] })),
      card("Duplicate suspects", null, d.duplicates.length ? alv({ compact: true, rows: d.duplicates, columns: [{ key: "obj", label: "Object" }, { key: "field", label: "Same" }, { key: "value", label: "Value" }, { key: "keys", label: "Records" }] }) : h("p.pos", null, "✔ No duplicates found")),
      card("Latest changes", null, changeGrid(d.recent))));
    msg("S", `Master data cockpit - quality ${k.quality} %`);
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }, { label: "Process map", ghost: true, onClick: () => go("ZMD_PROCESS") }]); exec();
} });

register("ZMD_PROCESS", { title: "Master Data Process Map (Create → Use → Block → Delete)", async render(app) {
  const step = (n, t, codes, d) => h("div.card", null, h("h3", null, `${n}. ${t}`), h("div.sub", null, d),
    h("div.body", null, codes.map(c => h("a.btn.ghost", { href: "#/" + c, style: { margin: "2px" } }, c))));
  app.append(panel(null, h("p", null, "Master data is the base of every transaction: the material type decides which views exist, the views decide what the business can do (buy, store, sell, cost), the account group decides number range and required fields of customers and vendors. Every change is logged; sensitive changes need a second person.")),
    h("div.cards", null,
      step(1, "Customizing", ["OMS2", "OMSK", "OMS4", "OBD2", "OBD3", "XDN1", "XKN1"], "types, views, valuation classes, statuses, account groups, number ranges"),
      step(2, "Create", ["MM01", "XK01", "XD01", "MK01", "FK01", "VD01", "FD01"], "material views per org level; vendor / customer central or per area"),
      step(3, "Extend", ["MM50", "MM01", "MMSC", "VD01"], "new plants, storage locations, sales areas"),
      step(4, "Localize", ["ZJ1ID_MAT", "ZJ1ID_CUS", "ZJ1ID_VEN", "ZMM02_BR", "ZEXIM"], "India CIN (GST), Brazil (NCM), foreign trade & licenses"),
      step(5, "Use in transactions", ["ME21N", "MIGO", "VF01", "FB60", "F110"], "status, blocks, QM flag, tolerances, license and sales view are checked"),
      step(6, "Change & control", ["MM02", "XK02", "XD02", "FK08", "FD08", "MM04", "XK04", "XD04"], "change documents, dual control for bank / terms"),
      step(7, "Block", ["XK05", "XD05", "MM02"], "purchasing / posting / payment / order / billing blocks, material status"),
      step(8, "Delete", ["MM06", "XK06", "XD06"], "deletion flag, then archive when stock and open items are zero"),
      step(9, "Monitor", ["ZMD_COCKPIT", "MM60", "S_ALR_87012086", "S_ALR_87012179", "ZMM03_LF", "ZXK03_LF", "ZXD03_LF"], "quality, risk, dead stock, 360° views")));
} });
})();
