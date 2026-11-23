/* NERP - GMES shop floor (ZMES_*): cockpit, station terminal (scan, OK / NG / repair / scrap, components),
   serial numbers, genealogy trace, hourly board, quality (FPY / RTY / DPU / DPMO), WIP, cycle time and
   operators, andon, SPC chart, settings; skills matrix (ZHR_SKILLS). */
"use strict";
(() => {
const { h, api, msg, run, ask, field, inp, sel, val, alv, register, go, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn, cls) => h("button.btn" + (cls ? "." + cls : ""), { type: "button", on: { click: fn } }, t);
const pct = v => v === null || v === undefined ? "-" : v + " %";
const ST = { WIP: ["In process", "Q"], REPAIR: ["In repair", "B"], DONE: ["Finished", "U"], SCRAP: ["Scrapped", "B"] };
const RES = { OK: "U", NG: "B", REPAIRED: "Q", SCRAP: "B" };
const CSS = `.mes-term{display:grid;grid-template-columns:minmax(300px,1fr) minmax(300px,1fr);gap:14px}@media(max-width:1000px){.mes-term{grid-template-columns:1fr}}
.mes-scan{font-size:26px;padding:12px 14px;width:100%;border:2px solid #1f5fae;border-radius:12px;letter-spacing:1px}
.mes-big{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.mes-big button{flex:1 1 130px;font-size:20px;font-weight:800;padding:18px 10px;border-radius:12px;border:0;color:#fff;cursor:pointer}
.mes-ok{background:#1a9a55}.mes-ng{background:#d0342c}.mes-rp{background:#e08a00}.mes-sc{background:#5d6b7c}
.mes-route{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.mes-route span{padding:6px 10px;border-radius:8px;background:#eef1f5;font-weight:700;font-size:13px}
.mes-route span.done{background:#e3f6ec;color:#11713e}.mes-route span.next{background:#1f5fae;color:#fff}.mes-route span.rep{background:#fde7e5;color:#a3221b}
.mes-hour{display:grid;grid-template-columns:58px 1fr 70px;gap:6px;align-items:center;font-size:13px;margin:3px 0}
.mes-hour .b{height:16px;background:#eef1f5;border-radius:8px;position:relative;overflow:hidden}.mes-hour .p{position:absolute;inset:0 auto 0 0;background:#c9d6e8}
.mes-hour .a{position:absolute;inset:0 auto 0 0;background:#1a9a55;opacity:.85}.mes-hour .a.low{background:#d0342c}
.mes-andon{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}.mes-call{border-radius:12px;padding:12px;color:#fff;font-weight:700}
.mes-call.OPEN{background:#d0342c;animation:mesblink 1.2s infinite}.mes-call.ACK{background:#e08a00}@keyframes mesblink{50%{opacity:.55}}
.mes-call small{display:block;font-weight:500;opacity:.9;margin-top:4px}`;
const css = () => { if (!document.getElementById("mes-css")) document.head.append(h("style#mes-css", { html: CSS })); };
const days = n => { const d = new Date(today() + "T12:00:00"); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };

// ------------------------------------------------------------------ 1-1 cockpit
register("ZMES_COCKPIT", { title: "GMES Cockpit - Shop Floor Today", async render(app, params) {
  const dt = inp({ type: "date", value: params.day || today() }), out = h("div");
  app.append(panel(null, grid(field("Day", dt))), out);
  const load = async () => {
    const d = await run(() => api("/api/mes/cockpit?day=" + dt.value)); if (!d) return;
    out.innerHTML = "";
    const andon = Object.entries(d.andon_open).map(([k, n]) => `${d.andon_kinds[k]}: ${n}`).join(" · ");
    const rtyv = Object.values(d.rty_7d), rty = rtyv.length ? Math.min(...rtyv) + " %" : "-", rtyMat = Object.entries(d.rty_7d).map(([m, v]) => `${m} ${v}%`).join(" · ");
    out.append(h("div.kpis", null, kpi("Output vs plan", `${d.actual} / ${d.plan}`, pct(d.ach), d.ach !== null && d.ach < 90 ? "neg" : "pos"),
      kpi("First pass yield today", pct(d.fpy_today), `7 days: ${pct(d.fpy_7d)}`, d.fpy_7d !== null && d.fpy_7d < 95 ? "neg" : "pos"),
      kpi("Rolled throughput yield (7 d)", rty, `${rtyMat} · DPU ${d.dpu_7d}`, rtyv.length && Math.min(...rtyv) < 90 ? "neg" : ""), kpi("WIP units", String(d.wip), `${d.in_repair} in repair · ${d.stuck} stuck > 24 h`, d.stuck ? "neg" : ""),
      kpi("Open andon calls", String(Object.values(d.andon_open).reduce((a, b) => a + b, 0)), andon || "none", andon ? "neg" : "pos"),
      kpi("Top defect (7 d)", d.top_defect ? d.top_defect.code : "-", d.top_defect ? `${d.top_defect.text} (${d.top_defect.count})` : "")),
      alv({ rows: d.lines, title: "Lines today", columns: [{ key: "arbpl", label: "Line" }, { key: "text", label: "Name" }, { key: "plan", label: "Plan" },
        { key: "actual", label: "Output", type: "int" }, { key: "ach", label: "Achievement %" }, { key: "ng", label: "Failures", type: "int" },
        { key: "takt_sec", label: "Takt (s)" }, { key: "open_andon", label: "Andon", type: "int" }, { key: "x", label: "", render: r => btn("Hourly", () => go("ZMES_HOURLY", { day: dt.value, arbpl: r.arbpl })) }] }),
      d.to_confirm.length ? alv({ rows: d.to_confirm, title: "Finished units not yet confirmed to the production order", columns: [{ key: "aufnr", label: "Order" },
        { key: "done", label: "Good", type: "int" }, { key: "scrap", label: "Scrap", type: "int" }, { key: "x", label: "", render: r => btn("Confirm (CO11N)", async () => {
          const x = await run(() => api("/api/mes/confirm", { aufnr: r.aufnr })); if (x) { msg("S", x.message); load(); } }) }] }) : null,
      note("FPY = passed at the first attempt; RTY = product of the FPY of all operations; DPU = defects per unit. The GMES screens are in the Production menu, group 8."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Station terminal", onClick: () => go("ZMES_STATION") }, { label: "Andon", onClick: () => go("ZMES_ANDON") }]);
  load();
} });

// ------------------------------------------------------------------ 2-1 station terminal
register("ZMES_STATION", { title: "GMES Station Terminal", async render(app) {
  css();
  const m = await run(() => api("/api/mes/master")); if (!m) return;
  let station = null, unitData = null;
  try { station = localStorage.getItem("mes_station"); } catch (e) { /* private */ }
  const stSel = sel(m.stations.map(s => [s.station, `${s.station} - ${s.text || ""} (${s.kind}${s.vornr ? " " + s.vornr : ""})`]), station || (m.stations[0] || {}).station);
  const opIn = inp({ w: "m", ph: "personnel no." }), scan = h("input.mes-scan", { placeholder: "Scan / type serial number and press Enter" });
  const defSel = sel([["", "- defect code -"]].concat(Object.entries(m.defects)), ""), cyc = inp({ w: "s", ph: "sec" }), noteIn = inp({ w: "l" });
  try { opIn.value = localStorage.getItem("mes_operator") || ""; } catch (e) { /* private */ }
  const info = h("div"), comps = h("div"), last = h("div");
  const remember = () => { try { localStorage.setItem("mes_station", stSel.value); localStorage.setItem("mes_operator", val(opIn)); } catch (e) { /* private */ } };
  const loadUnit = async () => {
    const sn = val(scan).toUpperCase(); if (!sn) return;
    const u = await run(() => api("/api/mes/unit?serial=" + encodeURIComponent(sn))); if (!u) { unitData = null; info.innerHTML = ""; return; }
    unitData = u; info.innerHTML = "";
    const done = new Set(u.events.filter(e => e.result === "OK").map(e => e.vornr));
    info.append(h("div", null, h("b", { style: { fontSize: "20px" } }, u.serial), " ", badge(...(ST[u.status] || [u.status, ""])), ` · order ${u.aufnr} · ${u.matnr} · repairs ${u.repairs}`),
      h("div.mes-route", null, ...u.route.map(r => h("span." + (done.has(r.vornr) ? "done" : u.next_vornr === r.vornr ? (u.status === "REPAIR" ? "rep" : "next") : ""), null, `${r.vornr} ${r.ltxa1}`))),
      alv({ rows: u.events.slice(-6).reverse(), title: "History", compact: true, columns: [{ key: "ts", label: "Time" }, { key: "station", label: "Station" }, { key: "vornr", label: "Op." },
        { key: "result", label: "Result", render: r => badge(r.result, RES[r.result]) }, { key: "defect", label: "Defect" }, { key: "operator", label: "Operator" }] }));
    comps.innerHTML = "";
    const st = m.stations.find(s => s.station === stSel.value);
    if (st && st.kind === "OP" && u.status === "WIP") {
      const rows = [0, 1, 2, 3].map(() => ({ mat: inp({ w: "s", ph: "material", upper: true }), lot: inp({ w: "m", ph: "lot / serial", upper: true }) }));
      comps.append(h("div", null, h("b", null, "Components built in (genealogy):"), ...rows.map(r => h("div", null, r.mat, " ", r.lot))));
      comps.rows = rows;
    }
  };
  const book = async result => {
    if (!unitData) { msg("E", "Scan a serial number first"); return; }
    remember();
    const body = { serial: unitData.serial, station: stSel.value, result, operator: val(opIn), defect: defSel.value, cycle_sec: val(cyc), note: val(noteIn) };
    if (comps.rows) body.components = comps.rows.map(r => ({ matnr: val(r.mat), lot: val(r.lot) })).filter(c => c.matnr && c.lot);
    const r = await run(() => api("/api/mes/book", body)); if (!r) return;
    msg("S", r.message);
    last.prepend(h("div", null, badge(result, RES[result]), " ", r.message));
    scan.value = ""; defSel.value = ""; cyc.value = ""; noteIn.value = ""; info.innerHTML = ""; comps.innerHTML = ""; comps.rows = null; unitData = null; scan.focus();
  };
  scan.addEventListener("keydown", e => { if (e.key === "Enter") loadUnit(); });
  stSel.addEventListener("change", remember);
  app.append(h("div.mes-term", null,
    panel("Station and operator", grid(field("Station", stSel), field("Operator", opIn)), h("div", { style: { marginTop: "10px" } }, scan),
      grid(field("Defect (for NG)", defSel), field("Cycle time", cyc), field("Note", noteIn)),
      h("div.mes-big", null, h("button.mes-ok", { type: "button", on: { click: () => book("OK") } }, "✔ OK"), h("button.mes-ng", { type: "button", on: { click: () => book("NG") } }, "✖ NG"),
        h("button.mes-rp", { type: "button", on: { click: () => book("REPAIRED") } }, "🔧 Repaired"), h("button.mes-sc", { type: "button", on: { click: () => book("SCRAP") } }, "🗑 Scrap")),
      comps, note("Rules: the unit must be at this station's operation (no skipping); the operator must hold a valid certification for the station's skill (ZHR_SKILLS); NG needs a defect code and sends the unit to the repair bench; after 3 repairs the unit must be scrapped.")),
    panel("Unit", info, h("h3", null, "Last bookings"), last)));
  toolbar([{ label: "Andon call", onClick: async () => { const st = m.stations.find(s => s.station === stSel.value) || {};
    const x = await ask("Andon - " + (st.arbpl || ""), [{ name: "kind", label: "Type: " + Object.keys(m.andon).join(" / "), value: "HELP" }, { name: "text", label: "What is the problem", value: "" }]); if (!x) return;
    const r = await run(() => api("/api/mes/andon/open", { arbpl: st.arbpl, station: st.station, kind: x.kind, text: x.text })); if (r) msg("S", r.message); } },
    { label: "Cockpit", onClick: () => go("ZMES_COCKPIT") }]);
  scan.focus();
} });

// ------------------------------------------------------------------ 2-2 serial numbers
register("ZMES_UNITS", { title: "GMES Serial Numbers per Order", async render(app, params) {
  const m = await run(() => api("/api/mes/master")); if (!m) return;
  const o = sel(m.orders.map(x => [x.aufnr, `${x.aufnr} ${x.matnr} (${x.gamng / 1000} pcs, ${x.units} serials)`]), params.aufnr || (m.orders[0] || {}).aufnr), out = h("div");
  app.append(panel(null, grid(field("Production order", o))), out);
  const load = async () => {
    if (!o.value) { out.append(note("No released production order.")); return; }
    const d = await run(() => api("/api/mes/units?aufnr=" + o.value)); if (!d) return;
    out.innerHTML = "";
    const by = s => d.rows.filter(r => r.status === s).length;
    out.append(h("div.kpis", null, kpi("Serials", String(d.rows.length)), kpi("In process", String(by("WIP"))), kpi("In repair", String(by("REPAIR")), "", by("REPAIR") ? "neg" : ""),
      kpi("Finished", String(by("DONE")), `${d.rows.filter(r => r.status === "DONE" && !r.confirmed).length} not confirmed`, "pos"), kpi("Scrapped", String(by("SCRAP")), "", by("SCRAP") ? "neg" : "")),
      alv({ rows: d.rows, title: "Units", columns: [{ key: "serial", label: "Serial", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); go("ZMES_TRACE", { key: r.serial }); } } }, r.serial) },
        { key: "status", label: "Status", render: r => badge(...(ST[r.status] || [r.status, ""])) }, { key: "next_vornr", label: "Next op." }, { key: "repairs", label: "Repairs", type: "int" },
        { key: "created", label: "Released" }, { key: "finished", label: "Finished" }, { key: "confirmed", label: "Confirmed", render: r => r.confirmed ? "✓" : "" }, { key: "vbeln", label: "Delivery" }] }));
  };
  o.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Release serial numbers", onClick: async () => { const x = await ask("Release serial numbers for order " + o.value, [{ name: "count", label: "Number of units", value: "1" }]); if (!x) return;
      const r = await run(() => api("/api/mes/release", { aufnr: o.value, count: x.count })); if (r) { msg("S", r.message); load(); } } },
    { label: "Confirm to order (CO11N)", onClick: async () => { const r = await run(() => api("/api/mes/confirm", { aufnr: o.value })); if (r) { msg("S", r.message); load(); } } },
    { label: "Link to delivery", onClick: async () => { const x = await ask("Ship finished units", [{ name: "vbeln", label: "Delivery", value: "" }, { name: "serials", label: "Serials (comma separated)", value: "" }]); if (!x) return;
      const r = await run(() => api("/api/mes/ship", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 3-1 trace
register("ZMES_TRACE", { title: "GMES Genealogy - Forward / Backward Trace", async render(app, params) {
  const key = inp({ w: "l", value: params.key || "", ph: "serial number or component lot", upper: true }), out = h("div");
  app.append(panel(null, grid(field("Serial / lot", key))), out);
  const load = async () => {
    if (!val(key)) return;
    const d = await run(() => api("/api/mes/trace?key=" + encodeURIComponent(val(key)))); if (!d) return;
    out.innerHTML = "";
    if (d.direction === "backward") {
      const u = d.unit;
      out.append(h("div.kpis", null, kpi("Serial", u.serial), kpi("Status", (ST[u.status] || [u.status])[0]), kpi("Order", u.aufnr, u.matnr), kpi("Repairs", String(u.repairs)),
        kpi("Customer", d.customer || "not shipped", u.vbeln ? "delivery " + u.vbeln : "")),
        alv({ rows: u.events, title: "Route history (who, where, when, result)", columns: [{ key: "ts", label: "Time" }, { key: "station", label: "Station" }, { key: "vornr", label: "Op." },
          { key: "result", label: "Result", render: r => badge(r.result, RES[r.result]) }, { key: "attempt", label: "Attempt", type: "int" }, { key: "defect", label: "Defect" },
          { key: "operator", label: "Operator" }, { key: "cycle_sec", label: "Cycle (s)", type: "int" }, { key: "note", label: "Note" }] }),
        alv({ rows: u.components, title: "Components built in (click a lot for the forward trace)", columns: [{ key: "matnr", label: "Component" },
          { key: "lot", label: "Lot / serial", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); key.value = r.lot; load(); } } }, r.lot) },
          { key: "qty", label: "Qty", type: "qty" }, { key: "station", label: "Station" }, { key: "ts", label: "Time" }] }));
    } else {
      out.append(h("div.kpis", null, kpi("Lot", d.lot), kpi("Units built", String(d.units.length)), kpi("Orders", d.orders.join(", ")),
        kpi("Shipped", String(d.shipped), d.customers.join(", ") || "", d.shipped ? "neg" : ""), kpi("Still in house", String(d.in_house), "can be blocked", "pos")),
        alv({ rows: d.units, title: "Every unit containing this lot (recall list)", columns: [{ key: "serial", label: "Serial", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); key.value = r.serial; load(); } } }, r.serial) },
          { key: "comp", label: "Component" }, { key: "aufnr", label: "Order" }, { key: "matnr", label: "Product" }, { key: "status", label: "Status", render: r => badge(...(ST[r.status] || [r.status, ""])) },
          { key: "vbeln", label: "Delivery" }, { key: "customer", label: "Customer" }] }));
    }
  };
  toolbar([{ label: "Trace", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 4-1 hourly board
register("ZMES_HOURLY", { title: "GMES Hourly Production Board", async render(app, params) {
  css();
  const dt = inp({ type: "date", value: params.day || today() }), out = h("div");
  app.append(panel(null, grid(field("Day", dt))), out);
  const load = async () => {
    const d = await run(() => api("/api/mes/report/hourly?day=" + dt.value + (params.arbpl ? "&arbpl=" + params.arbpl : ""))); if (!d) return;
    out.innerHTML = "";
    for (const l of d.lines) {
      const mx = Math.max(1, ...l.hours.map(x => Math.max(x.plan, x.actual)));
      out.append(panel(`${l.arbpl} - ${l.text}`, h("div.kpis", null, kpi("Plan", String(l.plan)), kpi("Output", String(l.actual), pct(l.ach), l.ach !== null && l.ach < 90 ? "neg" : "pos"),
        kpi("Units per hour (plan)", String(l.uph), l.takt_sec ? `takt ${l.takt_sec} s` : ""), kpi("Failures", String(l.ng), "", l.ng ? "neg" : ""), kpi("Open andon", String(l.open_andon), "", l.open_andon ? "neg" : "")),
        ...l.hours.map(x => h("div.mes-hour", null, h("b", null, x.hour), h("div.b", null, h("span.p", { style: { width: (100 * x.plan / mx) + "%" } }),
          h("span.a" + (x.plan && x.actual < x.plan * 0.85 ? ".low" : ""), { style: { width: (100 * x.actual / mx) + "%" } })),
          h("span", null, `${x.actual} / ${x.plan}${x.ng ? " · ✖" + x.ng : ""}`))),
        l.hours.length ? alv({ rows: l.hours, compact: true, title: "Cumulative", columns: [{ key: "hour", label: "Hour" }, { key: "plan", label: "Plan" }, { key: "actual", label: "Output", type: "int" },
          { key: "ng", label: "NG", type: "int" }, { key: "cum_plan", label: "Cum. plan" }, { key: "cum_actual", label: "Cum. output", type: "int" }, { key: "gap", label: "Gap" }, { key: "ach", label: "Ach. %" }] }) : note("No plan and no bookings.")));
    }
    if (!d.lines.length) out.append(note("No GMES stations yet - set them up in ZMES_CONF."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 4-2 quality
register("ZMES_QUALITY", { title: "GMES Quality - FPY, RTY, DPU, DPMO and Defects", async render(app) {
  const f = inp({ type: "date", value: days(6) }), t = inp({ type: "date", value: today() }), out = h("div");
  app.append(panel(null, grid(field("From", f), field("To", t))), out);
  const load = async () => {
    const d = await run(() => api(`/api/mes/report/quality?from=${f.value}&to=${t.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("First pass yield", pct(d.fpy), "", d.fpy !== null && d.fpy < 95 ? "neg" : "pos"), kpi("Units", String(d.units)), kpi("Defects", String(d.defects)),
      kpi("Defects per unit", String(d.dpu)), kpi("Repairs", String(d.repairs)), kpi("Scrapped", String(d.scrap), "", d.scrap ? "neg" : ""),
      ...Object.entries(d.rty).map(([mtr, v]) => kpi("RTY " + mtr, v + " %", "rolled throughput yield", v < 90 ? "neg" : "pos"))),
      alv({ rows: d.ops, title: "Per operation", columns: [{ key: "matnr", label: "Material" }, { key: "vornr", label: "Op." }, { key: "arbpl", label: "Line" },
        { key: "units", label: "Units", type: "int" }, { key: "tested_first", label: "First tests", type: "int" }, { key: "passed_first", label: "Passed first", type: "int" },
        { key: "fpy", label: "FPY %" }, { key: "defects", label: "Defects", type: "int" }, { key: "dpu", label: "DPU" }, { key: "dpmo", label: "DPMO", type: "int" }] }),
      alv({ rows: d.pareto, title: "Defect Pareto (fix the top ones first)", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Defect" }, { key: "count", label: "Count", type: "int" },
        { key: "cum_pct", label: "Cum. %" }, { key: "stations", label: "Stations" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 4-3 WIP, cycle time, operators
register("ZMES_WIP", { title: "GMES Work in Process, Cycle Time and Operators", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const [w, c, o] = await Promise.all([run(() => api("/api/mes/report/wip")), run(() => api("/api/mes/report/cycle")), run(() => api("/api/mes/report/operators"))]);
    if (!w || !c || !o) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Units in process", String(w.total)), kpi("Stuck > 24 h", String(w.stuck), "", w.stuck ? "neg" : "pos"), kpi("Bottleneck station", c.bottleneck || "-", "highest average cycle")),
      alv({ rows: w.by_step, title: "WIP by next step", columns: [{ key: "matnr", label: "Material" }, { key: "step", label: "Waiting for" }, { key: "units", label: "Units", type: "int" },
        { key: "max_age_h", label: "Oldest (h)" }, { key: "old", label: "> 24 h", type: "int" }] }),
      alv({ rows: w.units, title: "Units in process (oldest first)", columns: [{ key: "serial", label: "Serial", render: r => h("a", { href: "#", on: { click: e => { e.preventDefault(); go("ZMES_TRACE", { key: r.serial }); } } }, r.serial) },
        { key: "aufnr", label: "Order" }, { key: "status", label: "Status", render: r => badge(...(ST[r.status] || [r.status, ""])) }, { key: "step", label: "Next" }, { key: "repairs", label: "Repairs", type: "int" },
        { key: "last", label: "Last booking" }, { key: "age_h", label: "Waiting (h)" }] }),
      alv({ rows: c.stations, title: "Cycle time per station (last 7 days)", columns: [{ key: "station", label: "Station" }, { key: "text", label: "Name" }, { key: "bookings", label: "Bookings", type: "int" },
        { key: "ct_std", label: "Standard (s)", type: "int" }, { key: "avg_ct", label: "Average (s)" }, { key: "min_ct", label: "Min", type: "int" }, { key: "max_ct", label: "Max", type: "int" }, { key: "efficiency", label: "Efficiency %" }] }),
      alv({ rows: o.operators, title: "Operators (last 7 days)", columns: [{ key: "operator", label: "Pers. no." }, { key: "name", label: "Name" }, { key: "bookings", label: "Bookings", type: "int" },
        { key: "ok", label: "OK", type: "int" }, { key: "ng", label: "NG", type: "int" }, { key: "fpy", label: "FPY %" }, { key: "per_day", label: "Per day" }, { key: "uph", label: "Units / hour" }, { key: "stations", label: "Stations", type: "int" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ 5-1 andon
register("ZMES_ANDON", { title: "GMES Andon Board", async render(app) {
  css();
  const out = h("div"); app.append(out);
  let timer = null;
  const load = async () => {
    const d = await run(() => api("/api/mes/andon")); if (!d) return;
    out.innerHTML = "";
    out.append(panel(`Open calls (${d.open.length})`, d.open.length ? h("div.mes-andon", null, ...d.open.map(a => h("div.mes-call." + a.status, null,
      `${a.arbpl} · ${a.kind_text}`, h("small", null, `${a.text} · ${a.station || ""} · open ${a.open_min} min${a.ack ? " · acknowledged by " + a.ack_by : ""}`),
      h("div", { style: { marginTop: "8px" } }, a.status === "OPEN" ? btn("Acknowledge", async () => { const r = await run(() => api("/api/mes/andon/ack", { id: a.id })); if (r) load(); }) : null, " ",
        btn("Close", async () => { const x = await ask("Close andon " + a.id, [{ name: "resolution", label: "What was done", value: "" }]); if (!x) return;
          const r = await run(() => api("/api/mes/andon/close", { id: a.id, resolution: x.resolution })); if (r) { msg("S", r.message); load(); } })))))
      : note("No open calls ✓")),
      alv({ rows: d.by_kind, title: "Response (last 30 days)", columns: [{ key: "text", label: "Type" }, { key: "calls", label: "Calls", type: "int" },
        { key: "avg_respond_min", label: "Avg. response (min)" }, { key: "avg_resolve_min", label: "Avg. resolution (min)" }] }),
      alv({ rows: d.closed, title: "Closed calls", columns: [{ key: "opened", label: "Opened" }, { key: "arbpl", label: "Line" }, { key: "kind_text", label: "Type" }, { key: "text", label: "Problem" },
        { key: "respond_min", label: "Response (min)" }, { key: "resolve_min", label: "Resolution (min)" }, { key: "resolution", label: "Solution" }, { key: "closed_by", label: "By" }] }));
    clearTimeout(timer); timer = setTimeout(() => { if (document.body.contains(out)) load(); }, 30000);
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "New call", onClick: async () => {
    const x = await ask("New andon call", [{ name: "arbpl", label: "Line", value: "WC-ASSY" }, { name: "kind", label: "Type: MAT / QUAL / MAINT / HELP / SAFE", value: "HELP" }, { name: "text", label: "Problem", value: "" }]); if (!x) return;
    const r = await run(() => api("/api/mes/andon/open", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 5-2 SPC
register("ZMES_SPC", { title: "GMES SPC - X-bar / R Chart and Capability", async render(app, params) {
  const m = await run(() => api("/api/mes/master")); if (!m) return;
  const c = sel(m.chars.map(x => [x.code, `${x.code} - ${x.text}`]), params.code || (m.chars[0] || {}).code), out = h("div");
  app.append(panel(null, grid(field("Characteristic", c))), out);
  const chart = (pts, key, cl, ucl, lcl, lsl, usl) => {
    const W = 760, H = 220, pad = 30, vals = pts.map(p => p[key]).concat([ucl, lcl].concat(lsl !== undefined ? [lsl, usl] : []));
    const mx = Math.max(...vals), mn = Math.min(...vals), rg = (mx - mn) || 1, x = i => pad + i * (W - 2 * pad) / Math.max(1, pts.length - 1), y = v => H - pad - (v - mn) / rg * (H - 2 * pad);
    const line = (v, col, dash, lab) => `<line x1="${pad}" x2="${W - pad}" y1="${y(v)}" y2="${y(v)}" stroke="${col}" stroke-dasharray="${dash}"/><text x="${W - pad + 2}" y="${y(v) + 4}" font-size="10" fill="${col}">${lab}</text>`;
    let s = line(cl, "#1f5fae", "", "CL") + line(ucl, "#d0342c", "5 4", "UCL") + line(lcl, "#d0342c", "5 4", "LCL");
    if (lsl !== undefined) s += line(lsl, "#7a4b00", "2 3", "LSL") + line(usl, "#7a4b00", "2 3", "USL");
    s += `<polyline fill="none" stroke="#0b2a55" stroke-width="1.6" points="${pts.map((p, i) => x(i) + "," + y(p[key])).join(" ")}"/>`;
    s += pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p[key])}" r="3.5" fill="${p[key] > ucl || p[key] < lcl ? "#d0342c" : "#0b2a55"}"><title>${p.ts}: ${p[key]}</title></circle>`).join("");
    return h("div", { html: `<svg viewBox="0 0 ${W + 30} ${H}" width="100%" style="max-width:900px">${s}</svg>` });
  };
  const load = async () => {
    if (!c.value) { out.append(note("No characteristic yet - create one in ZMES_CONF.")); return; }
    const d = await run(() => api("/api/mes/spc?code=" + c.value)); if (!d) return;
    out.innerHTML = "";
    if (!d.enough) { out.append(note(d.note)); return; }
    const ch = d.char;
    out.append(h("div.kpis", null, kpi("Cp", String(d.cp ?? "-")), kpi("Cpk", String(d.cpk ?? "-"), d.verdict, d.cpk >= 1.33 ? "pos" : "neg"),
      kpi("Mean", String(d.xbarbar), `target ${ch.target} ${ch.unit || ""}`), kpi("Spec", `${ch.lsl} .. ${ch.usl}`, ch.unit || ""),
      kpi("In control", d.in_control ? "Yes" : "NO", `${d.rules.length} signals`, d.in_control ? "pos" : "neg"), kpi("Out of spec", String(d.out_of_spec), `of ${d.measurements}`, d.out_of_spec ? "neg" : "pos")),
      panel("X-bar chart (subgroup means)", chart(d.groups, "xbar", d.xbarbar, d.ucl, d.lcl, ch.lsl, ch.usl)),
      panel("R chart (subgroup ranges)", chart(d.groups, "r", d.rbar, d.r_ucl, d.r_lcl)),
      d.rules.length ? alv({ rows: d.rules.map(r => Object.assign({ ts: d.groups[r.i].ts }, r)), title: "Signals - investigate the process", columns: [{ key: "ts", label: "Subgroup" },
        { key: "rule", label: "Rule", type: "int" }, { key: "text", label: "Signal" }] }) : note("No signals - the process is in statistical control."),
      note("Cpk ≥ 1.33 capable, 1.00-1.33 marginal, < 1.00 not capable. Rules: 1 point outside limits, 8 in a row on one side, 6 rising / falling, range above its limit."));
  };
  c.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Enter measurement", onClick: async () => {
    const x = await ask("Measurement " + c.value, [{ name: "value", label: "Value", value: "" }, { name: "serial", label: "Serial (optional)", value: "" }]); if (!x) return;
    const r = await run(() => api("/api/mes/measure", Object.assign({ code: c.value }, x))); if (r) { msg(r.out_of_spec ? "W" : "S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ 1-2 settings
register("ZMES_CONF", { title: "GMES Settings - Stations, Skills, SPC Characteristics", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const m = await run(() => api("/api/mes/master")); if (!m) return;
    out.innerHTML = "";
    out.append(alv({ rows: m.stations, title: "Stations", columns: [{ key: "station", label: "Station" }, { key: "arbpl", label: "Line" }, { key: "vornr", label: "Op." }, { key: "kind", label: "Kind" },
      { key: "text", label: "Text" }, { key: "skill", label: "Required skill" }, { key: "ct_std", label: "Std cycle (s)", type: "int" }, { key: "opps", label: "Defect opportunities", type: "int" }] }),
      alv({ rows: m.skills, title: "Skills catalog", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Skill" }, { key: "valid_months", label: "Valid (months)", type: "int" }] }),
      alv({ rows: m.chars, title: "SPC characteristics", columns: [{ key: "code", label: "Code" }, { key: "text", label: "Characteristic" }, { key: "station", label: "Station" }, { key: "unit", label: "Unit" },
        { key: "lsl", label: "LSL" }, { key: "target", label: "Target" }, { key: "usl", label: "USL" }, { key: "n", label: "Subgroup", type: "int" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Station", onClick: async () => { const x = await ask("Station", [{ name: "station", label: "Station code" }, { name: "arbpl", label: "Line (work center)" }, { name: "vornr", label: "Operation (e.g. 0010)" },
      { name: "kind", label: "Kind OP / TEST / REPAIR", value: "OP" }, { name: "text", label: "Text" }, { name: "skill", label: "Required skill" }, { name: "ct_std", label: "Standard cycle (s)", value: "60" }, { name: "opps", label: "Defect opportunities", value: "1" }]);
      if (!x) return; const r = await run(() => api("/api/mes/station", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "Skill", onClick: async () => { const x = await ask("Skill", [{ name: "code", label: "Code" }, { name: "text", label: "Text" }, { name: "valid_months", label: "Valid (months)", value: "24" }]);
      if (!x) return; const r = await run(() => api("/api/mes/skill", x)); if (r) { msg("S", r.message); load(); } } },
    { label: "SPC characteristic", onClick: async () => { const x = await ask("SPC characteristic", [{ name: "code", label: "Code" }, { name: "text", label: "Text" }, { name: "station", label: "Station" },
      { name: "unit", label: "Unit" }, { name: "lsl", label: "Lower limit" }, { name: "usl", label: "Upper limit" }, { name: "target", label: "Target" }, { name: "n", label: "Subgroup size", value: "5" }]);
      if (!x) return; const r = await run(() => api("/api/mes/char", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });

// ------------------------------------------------------------------ HR: skills matrix
register("ZHR_SKILLS", { title: "Skills Matrix and Certifications", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/hr/skills")); if (!d) return;
    out.innerHTML = "";
    const cell = c => !c ? "" : h("span", { title: `level ${c.level} · until ${c.valid_to}` }, badge(`${"●".repeat(c.level)} ${c.valid_to.slice(2)}`, c.state === "expired" ? "B" : c.state === "expiring" ? "Q" : "U"));
    out.append(h("div.kpis", null, kpi("Skills", String(d.skills.length)), kpi("Expired", String(d.expired), "operators blocked at stations", d.expired ? "neg" : "pos"),
      kpi("Expiring in 30 days", String(d.expiring), "plan refresher training", d.expiring ? "neg" : "pos"),
      ...d.skills.map(s => kpi(s.code, String(d.coverage[s.code]), "qualified people", d.coverage[s.code] < 2 ? "neg" : ""))),
      alv({ rows: d.rows.filter(r => Object.keys(r.skills).length), title: "Who can do what (● level, valid until)", columns: [{ key: "pernr", label: "Pers. no." }, { key: "name", label: "Name" },
        { key: "job", label: "Job" }, ...d.skills.map(s => ({ key: "s_" + s.code, label: s.code, render: r => cell(r.skills[s.code]) }))] }),
      note("Levels: 1 trained (supervised), 2 independent, 3 trainer. Fewer than 2 qualified people for a skill = a single point of failure. Expired certifications block bookings at GMES stations."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Qualify employee", onClick: async () => {
    const x = await ask("Qualify employee", [{ name: "pernr", label: "Personnel no." }, { name: "skill", label: "Skill code" }, { name: "level", label: "Level 1-3", value: "1" },
      { name: "valid_from", label: "Valid from (YYYY-MM-DD)", value: today() }, { name: "trainer", label: "Trainer" }]); if (!x) return;
    const r = await run(() => api("/api/hr/qualify", x)); if (r) { msg("S", r.message); load(); } } }]);
  load();
} });
})();
