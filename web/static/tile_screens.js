/* NERP - ceramic tiles: sorting with shade / caliber lots (ZTILE_SORT), lot stock and lots of a delivery
   (ZTILE_LOTS), lab tests (ZTILE_LAB), first-choice rate (ZTILE_KPI), gas and power per m2 (ZENERGY),
   settings (ZTILE_CONF). */
"use strict";
(() => {
const { h, api, msg, run, ask, field, inp, sel, val, alv, register, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const m2 = v => v === null || v === undefined ? "" : (v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 });
const pct = v => v === null || v === undefined ? "-" : v.toFixed(1) + " %";
const back = (days) => { const d = new Date(today()); d.setDate(d.getDate() - days); return d.toISOString().slice(0, 10); };
const ST = { OK: "U", HOLD: "Q", BLOCK: "B" };

function bars(rows, key, label, target) {
  if (!rows.length) return note("No data in this period.");
  const W = 720, H = 180, p = 30, bw = Math.max(6, (W - 2 * p) / rows.length - 4);
  const v = rows.map(r => r[key] ?? 0), mx = Math.max(...v, target || 0) || 1, mn = Math.min(...v.filter(x => x), target || 100) * 0.95;
  const y = x => H - p - (x - mn) / ((mx - mn) || 1) * (H - 2 * p);
  let s = rows.map((r, i) => { const x = p + i * (W - 2 * p) / rows.length, val = r[key] ?? 0, col = target && val < target ? "#c0392b" : "#1f5fae";
    return `<rect x="${x}" y="${y(val)}" width="${bw}" height="${Math.max(1, H - p - y(val))}" fill="${col}"><title>${r.day}: ${val}</title></rect>` +
      (i % Math.ceil(rows.length / 8) === 0 ? `<text x="${x}" y="${H - 10}" font-size="10" fill="#5d6b7c">${r.day.slice(5)}</text>` : ""); }).join("");
  if (target) s += `<line x1="${p}" x2="${W - p}" y1="${y(target)}" y2="${y(target)}" stroke="#11713e" stroke-dasharray="4"/><text x="${W - p - 60}" y="${y(target) - 4}" font-size="10" fill="#11713e">${label} ${target}</text>`;
  return h("div", { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:820px">${s}</svg>` });
}

register("ZTILE_SORT", { title: "Tile Sorting - Grades, Shades and Calibers", async render(app) {
  const out = h("div");
  app.append(note("After the kiln every tile is graded: grade 1 and grade 2 go into stock as lots (one shade + one caliber each), grade 3 and broken tiles are scrap. Grade 1 is received on the order (101), grade 2 into the grade 2 material (501)."), out);
  async function load() {
    const d = await run(() => api("/api/tile/orders")); if (!d) return;
    out.replaceChildren(alv({ rows: d.rows, title: "Tile production orders", columns: [
      { key: "aufnr", label: "Order" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Text" },
      { key: "gamng", label: "Order m2", render: r => m2(r.gamng) }, { key: "grade1", label: "Grade 1", render: r => m2(r.grade1) },
      { key: "grade2", label: "Grade 2", render: r => m2(r.grade2) }, { key: "rest", label: "Grade 3 + broken", render: r => m2(r.rest) },
      { key: "fc", label: "First choice", render: r => { const t = r.grade1 + r.grade2 + r.rest; return t ? pct(100 * r.grade1 / t) : ""; } },
      { key: "sortings", label: "Sortings", type: "int" }, { key: "x", label: "", render: r => btn("Enter sorting", () => enter(r)) }] }));
  }
  async function enter(o) {
    const x = await ask(`Sorting of order ${o.aufnr} (${o.matnr}) - m2`, [
      { name: "day", label: "Day", value: today() },
      { name: "lots", label: "Grade 1 lots: shade/caliber/m2, ... (e.g. A1/9.8/1200, A2/9.8/300)", value: "" },
      { name: "grade2", label: "Grade 2 lots: shade/caliber/m2, ...", value: "" },
      { name: "grade3", label: "Grade 3 (m2)", value: "0" }, { name: "broken", label: "Broken (m2)", value: "0" },
      { name: "defects", label: "Defects: code m2, ... (CRK PIN GLZ PRN SHD SIZ PLN CHP DOT)", value: "" }]); if (!x) return;
    const parse = t => (t || "").split(",").map(s => s.trim()).filter(Boolean).map(s => { const [shade, caliber, qty] = s.split("/").map(v => (v || "").trim()); return { shade, caliber, qty }; });
    const defects = {}; (x.defects || "").split(",").map(s => s.trim()).filter(Boolean).forEach(s => { const [c, q] = s.split(/\s+/); defects[c] = q; });
    const r = await run(() => api("/api/tile/sort", { aufnr: o.aufnr, day: x.day, lots: parse(x.lots), grade2: parse(x.grade2), grade3: x.grade3, broken: x.broken, defects, arbpl: "WC-SORT" }));
    if (r) { msg("S", r.message + " - lots " + r.lots.join(", ")); load(); }
  }
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

register("ZTILE_LOTS", { title: "Tile Lots - Shade / Caliber Stock and Deliveries", async render(app, params) {
  const mat = inp({ w: "s", upper: true, value: params.matnr || "" }), all = sel([["0", "Open lots"], ["1", "All lots"]], "0");
  const dn = inp({ w: "s", value: params.vbeln || "", ph: "delivery" });
  const out = h("div"), dlv = h("div");
  app.append(panel(null, grid(field("Material", mat), field("Lots", all), field("Delivery", dn))), dlv, out);
  async function load() {
    const d = await run(() => api(`/api/tile/lots?matnr=${encodeURIComponent(val(mat))}&all=${all.value}`)); if (!d) return;
    const bad = d.reconcile.filter(r => r.difference);
    out.replaceChildren(
      h("div.kpis", null, kpi("Lots", String(d.rows.length)), kpi("Blocked", String(d.rows.filter(r => r.status === "BLOCK").length), "failed in the lab", d.rows.some(r => r.status === "BLOCK") ? "neg" : "pos"),
        kpi("Lots = stock", bad.length ? "NO" : "YES", bad.length ? bad.map(r => `${r.matnr} ${m2(r.difference)} m2 without lot`).join(", ") : "every m2 has a lot", bad.length ? "neg" : "pos")),
      alv({ rows: d.groups, compact: true, title: "Free per shade + caliber (what one delivery item can get)", columns: [
        { key: "matnr", label: "Material" }, { key: "shade", label: "Shade" }, { key: "caliber", label: "Caliber" }, { key: "qty", label: "Free m2", render: r => m2(r.qty) }] }),
      alv({ rows: d.rows, title: "Lots", rowClass: r => r.status === "BLOCK" ? ".neg" : "", columns: [
        { key: "lot", label: "Lot" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Text" }, { key: "grade", label: "Grade" },
        { key: "shade", label: "Shade" }, { key: "caliber", label: "Caliber" }, { key: "prod_date", label: "Produced", type: "date" },
        { key: "qty", label: "m2", render: r => m2(r.qty) }, { key: "rest", label: "Free m2", render: r => m2(r.rest) },
        { key: "status", label: "Status", render: r => badge(d.status[r.status], ST[r.status]) }, { key: "note", label: "Note" },
        { key: "x", label: "", render: r => btn(r.status === "BLOCK" ? "Release" : "Block", async () => {
          const x = await ask(`Lot ${r.lot}`, [{ name: "note", label: "Reason", value: "" }]); if (!x) return;
          const res = await run(() => api("/api/tile/lots/status", { lot: r.lot, status: r.status === "BLOCK" ? "OK" : "BLOCK", note: x.note })); if (res) { msg("S", res.message); load(); } }) }] }));
  }
  async function delivery() {
    if (!val(dn)) { dlv.replaceChildren(); return; }
    const d = await run(() => api("/api/tile/delivery?vbeln=" + encodeURIComponent(val(dn)))); if (!d) return;
    const pk = await api("/api/tile/delivery/packing?vbeln=" + encodeURIComponent(val(dn))).catch(() => null);
    dlv.replaceChildren(pk ? panel(`Packing of delivery ${d.vbeln}`, h("div.kpis", null, kpi("m2", m2(pk.total.m2)), kpi("Boxes", String(pk.total.boxes)),
        kpi("Pallets", String(pk.total.pallets)), kpi("Gross weight", pk.total.gross_kg.toLocaleString("en-US") + " kg")),
      alv({ rows: pk.items.filter(i => i.boxes), compact: true, columns: [{ key: "posnr", label: "Item" }, { key: "matnr", label: "Material" },
        { key: "qty", label: "m2", render: r => m2(r.qty) }, { key: "boxes", label: "Boxes", type: "int" }, { key: "full_pallets", label: "Full pallets", type: "int" },
        { key: "loose_boxes", label: "+ loose boxes", type: "int" }, { key: "gross_kg", label: "Gross kg", type: "int" }] }),
      h("div", null, btn("🖨 Packing list", () => App.printForm("PACKLIST", d.vbeln)), " ", btn("🖨 Certificate of origin data", () => App.printForm("ORIGIN", d.vbeln)))) : "", panel(`Lots of delivery ${d.vbeln} (one shade + one caliber per item)`, d.items.length ? alv({ rows: d.items, compact: true, columns: [
      { key: "posnr", label: "Item" }, { key: "matnr", label: "Material" }, { key: "qty", label: "m2", render: r => m2(r.qty) },
      { key: "lots", label: "Lots", render: r => r.error ? h("span", { style: { color: "#b3261e" } }, r.error) : r.lots.map(l => `${l.lot} ${l.shade}/${l.caliber} ${m2(l.qty)}`).join(", ") },
      { key: "chosen", label: "", render: r => r.chosen ? badge("chosen", "U") : badge("proposal", "Q") },
      { key: "x", label: "", render: r => btn("Choose lots", async () => {
        const x = await ask(`Item ${r.posnr} - ${m2(r.qty)} m2: lot m2, lot m2 ...`, [{ name: "t", label: "Lots", value: r.lots.map(l => `${l.lot} ${l.qty / 1000}`).join(", ") }]); if (!x) return;
        const lots = x.t.split(",").map(s => s.trim()).filter(Boolean).map(s => { const [lot, qty] = s.split(/\s+/); return { lot, qty }; });
        const res = await run(() => api("/api/tile/delivery/assign", { vbeln: d.vbeln, posnr: r.posnr, lots })); if (res) { msg("S", res.message); delivery(); } }) }] })
      : note("No tile items in this delivery."), note("The goods issue (VL02N) takes these lots; without a choice it takes the proposal. A mix of shades or calibers is refused.")));
  }
  dn.addEventListener("change", delivery);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: () => { load(); delivery(); } }]);
  load(); delivery();
} });

register("ZTILE_LAB", { title: "Tile Lab Tests (ISO 13006 groups)", async render(app) {
  const out = h("div");
  app.append(out);
  async function load() {
    const d = await run(() => api("/api/tile/lab")); if (!d) return;
    out.replaceChildren(
      alv({ rows: Object.entries(d.groups).map(([k, g]) => ({ k, t: g[0], lo: g[1] / 1000, hi: g[2] === null ? "-" : g[2] / 1000, st: g[3] })), compact: true, title: "Limits per group",
        columns: [{ key: "k", label: "Group" }, { key: "t", label: "Text" }, { key: "lo", label: "Water abs. from %" }, { key: "hi", label: "to %" }, { key: "st", label: "Min. strength N" }] }),
      note("Planarity max. 0.5 %, size max. 0.6 % deviation. Defaults - check them against the standard you certify to. A failed test blocks the lot."),
      alv({ rows: d.rows, title: "Tests", rowClass: r => r.result === "FAIL" ? ".neg" : "", columns: [
        { key: "day", label: "Day", type: "date" }, { key: "lot", label: "Lot" }, { key: "matnr", label: "Material" }, { key: "shade", label: "Shade" },
        { key: "water_abs", label: "Water abs. %", render: r => (r.water_abs / 1000).toFixed(2) }, { key: "strength", label: "Strength N", type: "int" },
        { key: "planarity", label: "Planarity %", render: r => (r.planarity / 1000).toFixed(2) }, { key: "size_dev", label: "Size %", render: r => (r.size_dev / 1000).toFixed(2) },
        { key: "result", label: "Result", render: r => badge(r.result, r.result === "PASS" ? "U" : "B") }, { key: "failed", label: "Why" }] }));
  }
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load },
    { label: "Enter test", onClick: async () => {
      const x = await ask("Lab test of a lot", [{ name: "lot", label: "Lot", value: "" }, { name: "day", label: "Day", value: today() },
        { name: "water_abs", label: "Water absorption %", value: "" }, { name: "strength", label: "Breaking strength N", value: "" },
        { name: "planarity", label: "Planarity deviation %", value: "0" }, { name: "size_dev", label: "Size deviation %", value: "0" }]); if (!x) return;
      const r = await run(() => api("/api/tile/lab", x)); if (r) { msg(r.result === "PASS" ? "S" : "W", r.message); load(); } } }]);
  load();
} });

register("ZTILE_KPI", { title: "First-Choice Rate and Defects", async render(app) {
  const f = inp({ type: "date", value: back(29) }), t = inp({ type: "date", value: today() }), out = h("div");
  app.append(panel(null, grid(field("From", f), field("To", t))), out);
  async function load() {
    const d = await run(() => api(`/api/tile/kpi?from=${f.value}&to=${t.value}`)); if (!d) return;
    const k = d.total, rest = k.total - k.grade1;
    out.replaceChildren(
      h("div.kpis", null, kpi("First choice", pct(k.first_choice), "target " + d.target + " %", k.first_choice !== null && k.first_choice < d.target ? "neg" : "pos"),
        kpi("Sorted", m2(k.total) + " m2"), kpi("Grade 2", m2(k.grade2) + " m2"), kpi("Grade 3 + broken", m2(k.grade3 + k.broken) + " m2"),
        kpi("Not first choice", m2(rest) + " m2", "each 1 % = " + m2(k.total / 100) + " m2")),
      panel("First choice per day", bars(d.days, "first_choice", "target", d.target)),
      alv({ rows: d.products, compact: true, title: "Per product", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Text" },
        { key: "total", label: "Sorted m2", render: r => m2(r.total) }, { key: "first_choice", label: "First choice", render: r => pct(r.first_choice) },
        { key: "grade2", label: "Grade 2", render: r => m2(r.grade2) }, { key: "grade3", label: "Grade 3", render: r => m2(r.grade3) }, { key: "broken", label: "Broken", render: r => m2(r.broken) }] }),
      alv({ rows: d.defects, compact: true, title: "Defects (Pareto)", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Defect" }, { key: "text_ar", label: "العيب" },
        { key: "qty", label: "m2", render: r => m2(r.qty) }, { key: "share", label: "Share", render: r => { const s = d.defects.reduce((a, x) => a + x.qty, 0); return pct(100 * r.qty / s); } }] }),
      alv({ rows: d.days, compact: true, title: "Per day", columns: [{ key: "day", label: "Day", type: "date" }, { key: "total", label: "Sorted m2", render: r => m2(r.total) },
        { key: "first_choice", label: "First choice", render: r => pct(r.first_choice) }] }));
  }
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

register("ZENERGY", { title: "Energy - Gas and Power per m2", async render(app) {
  const f = inp({ type: "date", value: back(29) }), t = inp({ type: "date", value: today() }), out = h("div");
  app.append(panel(null, grid(field("From", f), field("To", t))), out);
  const n3 = v => v === null || v === undefined ? "-" : Number(v).toFixed(2);
  async function load() {
    const d = await run(() => api(`/api/energy?from=${f.value}&to=${t.value}`)); if (!d) return;
    const k = d.total, high = d.rows.filter(r => r.high);
    out.replaceChildren(
      h("div.kpis", null, kpi("Gas per m2", n3(k.gas_m2) + " m3"), kpi("Power per m2", n3(k.kwh_m2) + " kWh"),
        kpi("Energy cost per m2", n3(k.cost_m2) + " EGP", "total " + (k.cost / 100).toLocaleString("en-US", { maximumFractionDigits: 0 }) + " EGP"),
        kpi("Days above normal", String(high.length), "more than " + d.limit_pct + " % above the 28-day average", high.length ? "neg" : "pos"),
        kpi("Readings missing today", String(d.missing.length), d.missing.join(", ") || "none", d.missing.length ? "neg" : "pos")),
      panel("Gas m3 per m2 per day", bars(d.rows.filter(r => r.gas_m2), "gas_m2", "", 0)),
      alv({ rows: d.meters, compact: true, title: "Per meter", columns: [{ key: "meter", label: "Meter" }, { key: "text", label: "Text" }, { key: "qty", label: "Consumption", render: r => m2(r.qty) + " " + r.unit },
        { key: "per_m2", label: "Per m2", render: r => n3(r.per_m2) }, { key: "cost", label: "Cost EGP", render: r => (r.cost / 100).toLocaleString("en-US", { maximumFractionDigits: 0 }) }] }),
      alv({ rows: d.rows.slice().reverse(), title: "Per day", rowClass: r => r.high ? ".neg" : "", columns: [{ key: "day", label: "Day", type: "date" },
        { key: "m2", label: "Sorted m2", render: r => m2(r.m2) }, { key: "gas", label: "Gas m3", render: r => m2(r.gas) }, { key: "power", label: "kWh", render: r => m2(r.power) },
        { key: "gas_m2", label: "m3 / m2", render: r => n3(r.gas_m2) }, { key: "base_gas_m2", label: "Normal", render: r => n3(r.base_gas_m2) },
        { key: "kwh_m2", label: "kWh / m2", render: r => n3(r.kwh_m2) }, { key: "cost_m2", label: "EGP / m2", render: r => n3(r.cost_m2) },
        { key: "high", label: "", render: r => r.high ? badge("high", "B") : "" }] }),
      note("Consumption of a day = meter reading of the day - previous reading. Days without sorting (kiln kept hot) count in the cost but not per m2."));
  }
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Enter readings", onClick: async () => {
      const c = await run(() => api("/api/tile/conf")); if (!c) return;
      const x = await ask("Meter readings of " + today(), [{ name: "day", label: "Day", value: today() }].concat(c.meters.filter(m => m.active).map(m => ({ name: m.meter, label: `${m.text} (${m.meter}, ${m.unit})`, value: "" })))); if (!x) return;
      for (const m of c.meters) { if (x[m.meter]) { const r = await run(() => api("/api/energy/reading", { meter: m.meter, day: x.day, reading: x[m.meter] })); if (!r) return; } }
      msg("S", "Readings saved"); load(); } }]);
  load();
} });

register("ZSD_EXPORT", { title: "Export Sales and Export Documents", async render(app) {
  const f = inp({ type: "date", value: today().slice(0, 4) + "-01-01" }), t = inp({ type: "date", value: today() });
  const dn = inp({ w: "s", ph: "delivery" }), out = h("div"), docs = h("div");
  app.append(panel(null, grid(field("From", f), field("To", t), field("Export delivery", dn))), docs, out);
  const egp = c => (c / 100).toLocaleString("en-US", { maximumFractionDigits: 0 });
  async function load() {
    const d = await run(() => api(`/api/sd/export?from=${f.value}&to=${t.value}`)); if (!d) return;
    out.replaceChildren(
      h("div.kpis", null, kpi("Export sales", egp(d.total_egp) + " EGP", `${d.invoices.length} invoices`), kpi("Share of sales", pct(d.share)),
        kpi("Countries", String(d.countries.length), d.countries.map(c => c.land).join(", ")), kpi("Open export orders", String(d.open_orders.length))),
      alv({ rows: d.countries, compact: true, title: "Per country", columns: [{ key: "land", label: "Country" }, { key: "qty", label: "m2", render: r => m2(r.qty) },
        { key: "egp", label: "EGP", render: r => egp(r.egp) }, { key: "invoices", label: "Invoices", type: "int" }] }),
      alv({ rows: d.customers, compact: true, title: "Per customer", columns: [{ key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "land", label: "Country" },
        { key: "qty", label: "m2", render: r => m2(r.qty) }, { key: "fc", label: "Document currency", render: r => egp(r.fc) + " " + r.waerk }, { key: "egp", label: "EGP", render: r => egp(r.egp) }] }),
      alv({ rows: d.invoices, title: "Export invoices (VAT 0 %)", columns: [{ key: "vbeln", label: "Invoice" }, { key: "fkdat", label: "Date", type: "date" },
        { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "land", label: "Country" }, { key: "vtweg", label: "Channel" },
        { key: "netwr_fc", label: "Amount", render: r => egp(r.netwr_fc ?? r.netwr) + " " + r.waerk }, { key: "netwr", label: "EGP", render: r => egp(r.netwr) },
        { key: "x", label: "", render: r => btn("🖨 Invoice", () => App.printForm("INVOICE", r.vbeln)) }] }),
      alv({ rows: d.open_orders, compact: true, title: "Open export orders", columns: [{ key: "vbeln", label: "Order" }, { key: "audat", label: "Date", type: "date" },
        { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "land", label: "Country" }, { key: "waerk", label: "Currency" }] }),
      note("Export = distribution channel 20 or a customer outside Egypt. Exports are zero-rated for VAT."));
  }
  async function showDocs() {
    if (!val(dn)) { docs.replaceChildren(); return; }
    const pk = await run(() => api("/api/tile/delivery/packing?vbeln=" + encodeURIComponent(val(dn)))); if (!pk) return;
    docs.replaceChildren(panel(`Export documents of delivery ${pk.vbeln}`, h("div.kpis", null, kpi("m2", m2(pk.total.m2)), kpi("Boxes", String(pk.total.boxes)),
        kpi("Pallets", String(pk.total.pallets)), kpi("Gross weight", pk.total.gross_kg.toLocaleString("en-US") + " kg")),
      h("div", null, btn("🖨 Packing list", () => App.printForm("PACKLIST", pk.vbeln)), " ", btn("🖨 Certificate of origin data", () => App.printForm("ORIGIN", pk.vbeln)), " ",
        btn("🖨 Delivery note", () => App.printForm("DELIVERY", pk.vbeln)))));
  }
  dn.addEventListener("change", showDocs);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: () => { load(); showDocs(); } }]);
  load();
} });

register("ZTILE_CONF", { title: "Ceramics Settings - Tile Products and Energy Meters", async render(app) {
  const out = h("div");
  app.append(out);
  async function load() {
    const d = await run(() => api("/api/tile/conf")); if (!d) return;
    out.replaceChildren(
      alv({ rows: d.products, title: "Tile products (kept in shade / caliber lots)", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Text" },
        { key: "fmt", label: "Format" }, { key: "bgroup", label: "ISO group" }, { key: "grade2", label: "Grade 2 material" },
        { key: "m2_box", label: "m2 / box", render: r => (r.m2_box / 1000).toFixed(3) }, { key: "boxes_pal", label: "Boxes / pallet", type: "int" },
        { key: "kg_m2", label: "kg / m2", render: r => (r.kg_m2 / 1000).toFixed(1) }, { key: "pal", label: "m2 / pallet", render: r => (r.m2_box * r.boxes_pal / 1e6).toFixed(2) }] }),
      alv({ rows: d.meters, title: "Energy meters", columns: [{ key: "meter", label: "Meter" }, { key: "text", label: "Text" }, { key: "kind", label: "Kind" },
        { key: "unit", label: "Unit" }, { key: "area", label: "Area" }, { key: "price", label: "Price EGP / unit", render: r => (r.price / 100).toFixed(2) }, { key: "active", label: "Active", type: "int" }] }));
  }
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load },
    { label: "Tile product", onClick: async () => {
      const x = await ask("Tile product", [{ name: "matnr", label: "Material" }, { name: "fmt", label: "Format (e.g. 60x60)" }, { name: "bgroup", label: "ISO group (BIa BIb BIIa BIIb BIII)", value: "BIIa" },
        { name: "grade2", label: "Grade 2 material (optional)" }, { name: "m2_box", label: "m2 per box", value: "1.44" }, { name: "boxes_pal", label: "Boxes per pallet", value: "40" },
        { name: "kg_m2", label: "kg per m2", value: "20" }]); if (!x) return;
      const r = await run(() => api("/api/tile/conf/product", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Energy meter", onClick: async () => {
      const x = await ask("Energy meter", [{ name: "meter", label: "Meter" }, { name: "text", label: "Text" }, { name: "kind", label: "Kind (GAS / POWER)", value: "GAS" },
        { name: "area", label: "Area" }, { name: "price", label: "Price EGP per unit" }]); if (!x) return;
      const r = await run(() => api("/api/tile/conf/meter", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });
})();
