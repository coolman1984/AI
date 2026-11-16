/* NERP - Production in depth: configuration (ZPP_CONF), month-end (ZPP_CLOSE), OEE per line
   (ZPP_OEE), scrap analysis (ZPP_SCRAP) and order progress (ZPP_PROGRESS). */
"use strict";
(() => {
const { h, api, run, field, inp, val, alv, register, go, toolbar, fmtAmt, fmtQty, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const first = () => today().slice(0, 8) + "01";
const pct = v => v === null || v === undefined ? "-" : v.toFixed(1) + " %";
const pcls = (v, good, ok) => v === null || v === undefined ? "" : v >= good ? "U" : v >= ok ? "Q" : "B";

// ------------------------------------------------------------------ ZPP_CONF
register("ZPP_CONF", { title: "Production - Basic Configuration (display)", async render(app) {
  const c = await run(() => api("/api/pp/config")); if (!c) return;
  app.append(h("div.kpis", null, kpi("Work centers (lines)", c.work_centers.length), kpi("Order types", c.order_types.length), kpi("Working days", c.workdays, "factory calendar")),
    alv({ rows: c.order_types, title: "Order types (OPL8)", columns: [{ key: "auart", label: "Type" }, { key: "text", label: "Description" }, { key: "settle", label: "Settles to" },
      { key: "material", label: "Material" }, { key: "variance", label: "Variances" }, { key: "over_conf", label: "Over-confirmation %" }] }),
    alv({ rows: c.work_centers, title: "Work centers / lines (CR01)", columns: [{ key: "arbpl", label: "Work center" }, { key: "ktext", label: "Description" }, { key: "area", label: "Board area" },
      { key: "kostl", label: "Cost center" }, { key: "lstar", label: "Activity" }, { key: "kapaz", label: "Hours / shift", render: r => fmtQty(r.kapaz / 1000) },
      { key: "shifts", label: "Shifts", type: "int" }, { key: "ngrad", label: "Utilization %", type: "int" }] }),
    alv({ rows: c.control_keys, title: "Control keys", columns: [{ key: "steus", label: "Key" }, { key: "text", label: "Description" }, { key: "conf", label: "Confirm" },
      { key: "external", label: "External" }, { key: "auto_gr", label: "Auto GR" }] }),
    alv({ rows: c.mrp_types, title: "MRP types", columns: [{ key: "dismm", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.lot_sizes, title: "Lot sizes", columns: [{ key: "disls", label: "Lot size" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.strategies, title: "Planning strategies", columns: [{ key: "strgr", label: "Strategy" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.scrap_reasons, title: "Scrap reasons", columns: [{ key: "grund", label: "Reason" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.accounts, title: "Accounts used by production", columns: [{ key: "use", label: "Use" }, { key: "hkont", label: "G/L account" }] }));
} });

// ------------------------------------------------------------------ ZPP_CLOSE
register("ZPP_CLOSE", { title: "Production - Closing Management", async render(app, params) {
  const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
  const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not needed", ""] };
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pp/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
      alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Month-end in Production - in this order",
        columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode) },
          { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }),
      note("Finish production first (orders confirmed, received, completed), then Controlling (ZCO_CLOSE) values WIP and variances and settles the orders."));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "CO closing (ZCO_CLOSE)", onClick: () => go("ZCO_CLOSE") }]);
  load();
} });

// ------------------------------------------------------------------ ZPP_OEE
register("ZPP_OEE", { title: "OEE - Overall Equipment Effectiveness", async render(app) {
  const f = { d1: inp({ type: "date", value: first() }), d2: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pp/oee?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Average OEE", pct(d.average), "world class: 85 %", d.average >= 85 ? "pos" : d.average ? "neg" : ""),
      ...d.rows.map(r => kpi(r.arbpl, pct(r.oee), `A ${pct(r.availability)} · P ${pct(r.performance)} · Q ${pct(r.quality)}`, r.oee >= 85 ? "pos" : r.oee === null ? "" : "neg"))),
      alv({ rows: d.rows, title: `OEE per line ${d.d1} to ${d.d2}`, emptyText: "No line plans or confirmations in the period", columns: [{ key: "arbpl", label: "Line" }, { key: "ktext", label: "Description" },
        { key: "days", label: "Days", type: "int" }, { key: "planned_min", label: "Planned min", type: "int" }, { key: "downtime", label: "Downtime min", type: "int" },
        { key: "run_min", label: "Run min", type: "int" }, { key: "good", label: "Good", type: "qty" }, { key: "scrap", label: "Scrap", type: "qty" }, { key: "ideal", label: "Ideal output", type: "qty" },
        { key: "availability", label: "Availability", render: r => badge(pct(r.availability), pcls(r.availability, 90, 80)) },
        { key: "performance", label: "Performance", render: r => badge(pct(r.performance), pcls(r.performance, 95, 80)) },
        { key: "quality", label: "Quality", render: r => badge(pct(r.quality), pcls(r.quality, 99, 95)) },
        { key: "oee", label: "OEE", render: r => badge(pct(r.oee), pcls(r.oee, 85, 60)) },
        { key: "losses", label: "Where the time is lost", render: r => r.losses.map(l => `${l.text} ${l.minutes} min`).join(" · ") || "-" }] }),
      note("Availability = time the line really ran / planned time (downtime from ZPP_LOSS). Performance = output / what the line could make at its target speed (UPH of ZPP_LINEPLAN). Quality = good / (good + scrap). OEE = the three multiplied."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Downtime (ZPP_LOSS)", onClick: () => go("ZPP_LOSS") }, { label: "Board", onClick: () => go("ZPP_BOARD") }]);
  load();
} });

// ------------------------------------------------------------------ ZPP_SCRAP
register("ZPP_SCRAP", { title: "Scrap Analysis (Pareto)", async render(app) {
  const f = { d1: inp({ type: "date", value: first() }), d2: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2))), out);
  const cols = (label) => [{ key: "key", label }, { key: "text", label: "Description" }, { key: "good", label: "Good", type: "qty", sum: true },
    { key: "scrap", label: "Scrap", type: "qty", sum: true }, { key: "rate", label: "Scrap %" }, { key: "value", label: "Scrap value", type: "amt", sum: true }, { key: "cum", label: "Cumulative %" }];
  const load = async () => {
    const d = await run(() => api(`/api/pp/scrap?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Scrap rate", d.rate.toFixed(2) + " %", `${fmtQty(d.scrap)} of ${fmtQty(d.good + d.scrap)}`, d.rate > 1 ? "neg" : "pos"),
      kpi("Scrap value", fmtAmt(d.value), "EGP at the material price")),
      alv({ rows: d.by_reason, title: "By reason - fix the top ones first", emptyText: "No scrap in the period", columns: cols("Reason") }),
      alv({ rows: d.by_material, title: "By material", emptyText: "No scrap", columns: cols("Material") }),
      alv({ rows: d.by_line, title: "By line", emptyText: "No scrap", columns: cols("Line") }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ ZPP_PROGRESS
register("ZPP_PROGRESS", { title: "Production Order Progress", async render(app) {
  const f = { kd: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("Key date", f.kd))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pp/progress?key_date=${f.kd.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Open orders", d.rows.length), kpi("Late", d.late, "past the finish date", d.late ? "neg" : "pos"),
      kpi("Missing parts", d.missing, "components short", d.missing ? "neg" : "pos"), kpi("Not started", d.not_started, "start date passed, not released", d.not_started ? "neg" : "pos")),
      alv({ rows: d.rows, title: "Open production orders", rowClass: r => r.late_days ? ".neg" : "", emptyText: "No open production orders", columns: [
        { key: "aufnr", label: "Order", link: r => go("CO03", { id: r.aufnr }) }, { key: "auart", label: "Type" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
        { key: "stat_text", label: "Status" }, { key: "gamng", label: "Planned", type: "qty" }, { key: "confirmed", label: "Confirmed", type: "qty" }, { key: "delivered", label: "Received", type: "qty" },
        { key: "conf_pct", label: "Done %", render: r => badge(r.conf_pct.toFixed(0) + " %", r.conf_pct >= 100 ? "U" : r.conf_pct > 0 ? "Q" : "") },
        { key: "gstrp", label: "Start", type: "date" }, { key: "gltrp", label: "Finish", type: "date" }, { key: "late_days", label: "Days late", type: "int" },
        { key: "missing", label: "Parts", render: r => r.missing ? badge("missing", "B") : badge("ok", "U") }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Order info system (COOIS)", onClick: () => go("COOIS") }]);
  load();
} });
})();
