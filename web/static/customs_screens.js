/* NERP - customs clearance for imports and exports: cockpit with alerts and declarations (ZCUS),
   tariff, HS codes of materials and settings (ZCUS_TARIFF). */
"use strict";
(() => {
const { h, api, msg, run, ask, field, inp, sel, val, alv, register, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const egp = c => ((c || 0) / 100).toLocaleString("en-US", { maximumFractionDigits: 0 });
const pct = p => ((p || 0) / 100).toLocaleString("en-US", { maximumFractionDigits: 2 }) + " %";
const qty = m => ((m || 0) / 1000).toLocaleString("en-US", { maximumFractionDigits: 3 });
const ST = { DRAFT: "", ACID: "Q", ARRIVED: "Q", SUBMITTED: "Q", INSPECTION: "Q", ASSESSED: "B", PAID: "Q", RELEASED: "U", SHIPPED: "U" };

function timeline(steps) {
  return h("div", { style: { display: "flex", flexWrap: "wrap", gap: "6px", margin: "6px 0 10px" } }, ...steps.map(s =>
    h("div", { style: { padding: "6px 10px", borderRadius: "6px", fontSize: "13px", border: "1px solid " + (s.done ? "#1d7a45" : "#c9d3dd"),
      background: s.done ? "#e6f4ec" : "transparent", minWidth: "120px" } },
      h("div", { style: { fontWeight: "600" } }, (s.done ? "✓ " : "") + s.text), h("div", { style: { color: "#5d6b7c" } }, s.date || "—"))));
}

register("ZCUS", { title: "Customs Clearance - Imports and Exports", async render(app, params) {
  const dir = sel([["", "Imports and exports"], ["IMP", "Imports"], ["EXP", "Exports"]], params.dir || "");
  const open = sel([["1", "Open declarations"], ["0", "All declarations"]], "0");
  const out = h("div"), det = h("div");
  app.append(panel(null, grid(field("Direction", dir), field("Show", open))), det, out);
  async function load() {
    const d = await run(() => api(`/api/customs?dir=${dir.value}&open=${open.value}`)); if (!d) return;
    out.replaceChildren(
      h("div.kpis", null, kpi("Open imports", String(d.open_imports), "not released yet"), kpi("Open exports", String(d.open_exports), "not shipped yet"),
        kpi("Duty paid this month", egp(d.duty_month) + " EGP", "goes into the landed cost"), kpi("Import VAT this month", egp(d.vat_month) + " EGP", "deductible input tax (VAT return line 4a)"),
        kpi("Expected export support", egp(d.export_support) + " EGP", "released / shipped exports"),
        kpi("Alerts", String(d.alerts.length), d.alerts.length ? "see below" : "none", d.alerts.length ? "neg" : "pos")),
      d.alerts.length ? panel("⚠ Needs attention", ...d.alerts.map(a => h("div", { style: { padding: "4px 0" } }, badge(a.kind, "B"), " ", a.text, " ", btn("Open", () => show(a.declno))))) : "",
      alv({ rows: d.rows, title: "Customs declarations", columns: [
        { key: "declno", label: "Declaration" }, { key: "direction", label: "Dir.", render: r => r.direction === "IMP" ? "Import" : "Export" },
        { key: "impno", label: "Import file / delivery", render: r => r.impno || r.vbeln || "" }, { key: "partner", label: "Partner" },
        { key: "country", label: "Country" }, { key: "status", label: "Status", render: r => badge(r.status_text, ST[r.status]) },
        { key: "acid", label: "ACID" }, { key: "decl_ref", label: "Customs ref." },
        { key: "cif", label: "Customs value EGP", render: r => egp(r.cif) }, { key: "duty", label: "Duty", render: r => egp(r.duty) }, { key: "vat", label: "Import VAT", render: r => egp(r.vat) },
        { key: "days_in_port", label: "Days in port", render: r => r.days_in_port === null ? "" : (r.over_days ? badge(r.days_in_port + " (+" + r.over_days + ")", "B") : String(r.days_in_port)) },
        { key: "x", label: "", render: r => btn("Open", () => show(r.declno)) }] }),
      note("Import: ACID pre-registration → arrival → declaration → inspection → duties assessed → paid → release. Export: declaration → inspection → release → shipped. Tariff rates in ZCUS_TARIFF are maintained by you - check them with the customs broker."));
  }
  async function show(declno) {
    const d = await run(() => api("/api/customs/decl?declno=" + encodeURIComponent(declno))); if (!d) return;
    const isImp = d.direction === "IMP";
    det.replaceChildren(panel(`${isImp ? "Import" : "Export"} declaration ${d.declno} - ${d.partner} ${d.partner_name}`,
      timeline(d.steps),
      h("div.kpis", null,
        kpi("Goods value", egp(d.goods) + " " + d.waers, isImp ? `freight ${egp(d.freight)}, insurance ${egp(d.insurance)} (${d.incoterm || "-"})` : (d.incoterm || "")),
        kpi("Customs rate", d.kurs ? (d.kurs / 100000).toFixed(4) : "-", "EGP per " + d.waers),
        kpi(isImp ? "Customs value (CIF)" : "FOB value", egp(d.cif) + " EGP"),
        isImp ? kpi("Duty + import VAT", egp(d.duty + d.vat + d.fees) + " EGP", `duty ${egp(d.duty)}, VAT ${egp(d.vat)}, fees ${egp(d.fees)}`) : kpi("Expected export support", egp(d.export_support) + " EGP"),
        isImp ? kpi("Days in port", d.days_in_port === null ? "-" : String(d.days_in_port), d.over_days ? `${d.over_days} days over the ${d.free_days} free days - about ${egp(d.storage)} EGP storage` : `${d.free_days} free days`, d.over_days ? "neg" : "pos")
          : kpi("Certificate of origin", d.coo_no || "-", d.bl_no ? "B/L " + d.bl_no : "")),
      h("div", null, `ACID: ${d.acid || "-"} · customs ref.: ${d.decl_ref || "-"} · broker: ${d.broker || "-"} ${d.broker_name || ""} · port: ${d.port || "-"}` + (d.pay_belnr ? ` · VAT document ${d.pay_belnr}` : "")),
      d.missing_hs.length ? note("⚠ Lines without a HS code in the tariff: " + d.missing_hs.map(x => x.matnr).join(", ") + " - maintain them in ZCUS_TARIFF before the assessment.") : "",
      alv({ rows: d.items, compact: true, columns: [{ key: "pos", label: "Item" }, { key: "matnr", label: "Material" }, { key: "text", label: "Text" },
        { key: "hs", label: "HS code" }, { key: "qty", label: "Quantity", render: r => qty(r.qty) + " " + (r.meins || "") },
        { key: "value_fc", label: "Value " + d.waers, render: r => egp(r.value_fc) }, { key: "cif", label: isImp ? "CIF EGP" : "FOB EGP", render: r => egp(r.cif) },
        { key: "duty_pct", label: "Duty %", render: r => pct(r.duty_pct) }, { key: "duty", label: "Duty", render: r => egp(r.duty) }, { key: "vat", label: "VAT", render: r => egp(r.vat) }] }),
      h("div", null, ...d.next.slice(0, 1).map(s => btn("▶ Next: " + d.steps.find(x => x.step === s).text, () => next(d, s))), " ",
        d.next.length > 1 ? btn("Other step…", async () => {
          const x = await ask("Step", [{ name: "step", label: "Step (" + d.next.join(", ") + ")", value: d.next[0] }]); if (x) next(d, x.step.toUpperCase()); }) : "", " ",
        btn("Edit values", () => edit(d)),
        !isImp && d.vbeln ? btn("🖨 Packing list", () => App.printForm("PACKLIST", d.vbeln)) : "",
        !isImp && d.vbeln ? btn("🖨 Certificate of origin data", () => App.printForm("ORIGIN", d.vbeln)) : "")));
    det.scrollIntoView({ behavior: "smooth" });
  }
  async function next(d, s) {
    const f = [{ name: "day", label: "Date", value: today() }];
    if (s === "ACID" && !d.acid) f.push({ name: "acid", label: "ACID number (19 digits)", value: "" });
    if (s === "SUBMITTED") f.push({ name: "decl_ref", label: "Customs declaration number", value: d.decl_ref || "" });
    if (s === "PAID") f.push({ name: "paid_by", label: "Paid by: BANK or BROKER", value: "BANK" });
    if (s === "RELEASED" && d.direction === "EXP") f.push({ name: "coo_no", label: "Certificate of origin number", value: d.coo_no || "" });
    if (s === "SHIPPED") f.push({ name: "bl_no", label: "Bill of lading", value: d.bl_no || "" });
    const x = await ask(`${d.declno}: ${s}`, f); if (!x) return;
    const r = await run(() => api("/api/customs/decl/step", Object.assign({ declno: d.declno, step: s }, x))); if (r) { msg("S", r.message); show(d.declno); load(); }
  }
  async function edit(d) {
    const f = [{ name: "acid", label: "ACID (19 digits)", value: d.acid || "" }, { name: "decl_ref", label: "Customs declaration number", value: d.decl_ref || "" },
      { name: "broker", label: "Broker (vendor)", value: d.broker || "" }, { name: "port", label: "Port", value: d.port || "" }, { name: "incoterm", label: "Incoterm", value: d.incoterm || "" },
      { name: "freight", label: "Freight (" + d.waers + ")", value: (d.freight / 100).toFixed(2) }, { name: "insurance", label: "Insurance (" + d.waers + ")", value: (d.insurance / 100).toFixed(2) },
      { name: "kurs", label: "Customs exchange rate (EGP per " + d.waers + ", empty = system rate)", value: d.kurs ? (d.kurs / 100000).toFixed(5) : "" },
      { name: "fees", label: "Other customs fees (EGP)", value: (d.fees / 100).toFixed(2) }, { name: "free_days", label: "Free days in port", value: d.free_days },
      { name: "coo_no", label: "Certificate of origin number", value: d.coo_no || "" }, { name: "bl_no", label: "Bill of lading", value: d.bl_no || "" }];
    const x = await ask("Declaration " + d.declno, f); if (!x) return;
    if (!x.kurs) delete x.kurs;
    const r = await run(() => api("/api/customs/decl/update", Object.assign({ declno: d.declno }, x))); if (r) { msg("S", r.message); show(d.declno); load(); }
  }
  dir.addEventListener("change", load); open.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "New import declaration", onClick: async () => {
      const x = await ask("Import declaration from an import file (ZIMP01)", [{ name: "impno", label: "Import file" }, { name: "acid", label: "ACID number (19 digits, if known)" },
        { name: "incoterm", label: "Incoterm", value: "FOB" }, { name: "freight", label: "Freight (PO currency)", value: "0" }, { name: "insurance", label: "Insurance (PO currency)", value: "0" },
        { name: "broker", label: "Broker (vendor, empty = default)" }]); if (!x) return;
      if (!x.acid) delete x.acid;
      const r = await run(() => api("/api/customs/decl/import", x)); if (r) { msg("S", r.message); load(); show(r.declno); } } },
    { label: "New export declaration", onClick: async () => {
      const x = await ask("Export declaration for a delivery", [{ name: "vbeln", label: "Delivery" }, { name: "port", label: "Port", value: "Alexandria" },
        { name: "incoterm", label: "Incoterm", value: "FOB" }, { name: "broker", label: "Broker (vendor, empty = default)" }]); if (!x) return;
      const r = await run(() => api("/api/customs/decl/export", x)); if (r) { msg("S", r.message); load(); show(r.declno); } } }]);
  await load();
  if (params.declno) show(params.declno);
} });

register("ZCUS_TARIFF", { title: "Customs Tariff, HS Codes and Settings", async render(app) {
  const out = h("div");
  app.append(out);
  async function load() {
    const d = await run(() => api("/api/customs/tariff")); if (!d) return;
    out.replaceChildren(
      h("div.kpis", null, kpi("HS codes", String(d.tariff.length)), kpi("Materials with HS code", String(d.materials.length)),
        kpi("Free days in port", d.settings.free_days || "-"), kpi("Storage per day over", (d.settings.storage_egp_day || "0") + " EGP"), kpi("Default broker", d.settings.default_broker || "-")),
      alv({ rows: d.tariff, title: "Customs tariff", columns: [{ key: "hs", label: "HS code" }, { key: "text", label: "Description" },
        { key: "duty_pct", label: "Duty", render: r => pct(r.duty_pct) }, { key: "vat_pct", label: "Import VAT", render: r => pct(r.vat_pct) },
        { key: "export_support_pct", label: "Export support", render: r => pct(r.export_support_pct) }, { key: "note", label: "Note" }] }),
      alv({ rows: d.materials, compact: true, title: "HS code of the materials", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Text" },
        { key: "hs", label: "HS code" }, { key: "text", label: "Tariff text" }, { key: "duty_pct", label: "Duty", render: r => r.duty_pct === null ? "not in tariff" : pct(r.duty_pct) }] }),
      note("The rates are maintained by you and are examples in the demo. Check every HS code and rate with the customs broker or the published tariff before you use them."));
  }
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load },
    { label: "HS code", onClick: async () => {
      const x = await ask("Tariff line", [{ name: "hs", label: "HS code (e.g. 3207.40)" }, { name: "text", label: "Description" }, { name: "duty_pct", label: "Duty %", value: "0" },
        { name: "vat_pct", label: "Import VAT %", value: "14" }, { name: "export_support_pct", label: "Export support %", value: "0" }, { name: "note", label: "Note" }]); if (!x) return;
      const r = await run(() => api("/api/customs/tariff/hs", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Material HS code", onClick: async () => {
      const x = await ask("HS code of a material", [{ name: "matnr", label: "Material" }, { name: "hs", label: "HS code" }]); if (!x) return;
      const r = await run(() => api("/api/customs/tariff/material", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Settings", onClick: async () => {
      const d = await run(() => api("/api/customs/tariff")); if (!d) return;
      const x = await ask("Customs settings", [{ name: "free_days", label: "Free days in port", value: d.settings.free_days }, { name: "storage_egp_day", label: "Storage per day over the free days (EGP)", value: d.settings.storage_egp_day },
        { name: "default_broker", label: "Default broker (vendor)", value: d.settings.default_broker || "" }]); if (!x) return;
      const r = await run(() => api("/api/customs/tariff/settings", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });
})();
