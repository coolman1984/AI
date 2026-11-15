/* NERP - Production status board (ZPP_BOARD): a dark shop-floor / TV screen with the lines
   of every area (plan, target, production, difference, achievement, on time, defects, loss,
   units per hour, manpower) and the panels shipping, attendance, material supply, quality
   and late purchase orders. Inputs: ZPP_LINEPLAN (daily plan per line), ZPP_LOSS (downtime). */
"use strict";
(() => {
const { h, api, msg, run, field, inp, sel, val, up, alv, register, go, toolbar, fmtQty, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);

const CSS = `
.pb{background:#1b1d22;color:#e8e8e8;font-family:Arial,Helvetica,sans-serif;padding:8px;border-radius:6px;min-height:80vh}
.pb-head{display:flex;align-items:center;gap:10px;background:linear-gradient(#0a4f8f,#06325d);border-radius:6px;padding:6px 12px;margin-bottom:8px;flex-wrap:wrap}
.pb-head input{font-size:16px;padding:3px 6px;border-radius:3px;border:0}
.pb-on{background:#2e9d3a;color:#fff;font-weight:bold;border:0;padding:5px 12px;border-radius:3px;cursor:pointer}
.pb-on.off{background:#8a8a8a}
.pb-mode{background:#eee;color:#222;padding:4px 8px;border-radius:3px;font-weight:bold;font-size:13px}
.pb-title{flex:1;text-align:center;font-size:30px;font-weight:bold;color:#fff;letter-spacing:1px}
.pb-clock{font-size:24px;font-weight:bold;color:#fff;font-variant-numeric:tabular-nums}
.pb-btn{background:#ffffff22;color:#fff;border:1px solid #ffffff55;padding:4px 10px;border-radius:3px;cursor:pointer}
.pb-areas{display:grid;grid-template-columns:repeat(auto-fit,minmax(820px,1fr));gap:8px}
.pb-area{background:#2a2c31;border-radius:4px;overflow-x:auto}
.pb td.mdl{text-align:left;max-width:230px;overflow:hidden;text-overflow:ellipsis}
.pb-area h3,.pb-box h3{margin:0;background:#cfd2d6;color:#555;text-align:center;font-size:19px;padding:5px;letter-spacing:.5px}
.pb table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
.pb th{background:#3a3c42;color:#fff;font-size:11px;padding:3px 4px;border:1px solid #555;white-space:nowrap}
.pb td{background:#000;padding:3px 6px;border:1px solid #333;text-align:right;white-space:nowrap}
.pb td.l{text-align:left}
.pb td.line{background:#b9e3ee;color:#246;font-weight:bold;text-align:left;border-left:6px solid #b9e3ee}
.pb td.line.behind{border-left-color:#ffd400}.pb td.line.ahead{border-left-color:#2ecc40}
.pb td.tg{color:#33b5ff}.pb .g{color:#2ecc40;font-weight:bold}.pb .r{color:#ff4136;font-weight:bold}.pb .y{color:#ffd400}
.pb tr.tot td{background:#3a3c42;font-size:17px;padding:6px}
.pb tr.tot td.l{font-size:18px}
.pb-boxes{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:8px;margin-top:8px}
.pb-box{background:#2a2c31;border-radius:4px;overflow-x:auto}
.pb-box td.k{background:#fff;color:#333;text-align:left;font-weight:bold}
.pb-nodata{font-size:34px;text-align:center;padding:40px 10px;color:#fff;background:#000}
.pb-ok{font-size:22px;text-align:center;padding:30px 10px;color:#2ecc40;background:#000}
.pb-empty{padding:40px;text-align:center;font-size:20px;background:#000;border-radius:4px}
.pb:fullscreen{overflow:auto;border-radius:0}
`;
const style = () => { if (!document.getElementById("pb-css")) { const s = document.createElement("style"); s.id = "pb-css"; s.textContent = CSS; document.head.append(s); } };
const n0 = v => v === null || v === undefined ? "-" : fmtQty(v);
const p1 = v => v === null || v === undefined ? "-" : Number(v).toFixed(1);
const sg = v => h("span." + (v >= 0 ? "g" : "r"), null, (v > 0 ? "+" : "") + fmtQty(v));

function areaTable(g) {
  const th = (t, attrs) => h("th", attrs || null, t);
  const head = [h("tr", null, th("LINE", { rowSpan: 2 }), th("MODEL", { rowSpan: 2 }), th("PRODUCTION", { colSpan: 4 }), th("ACH %", { rowSpan: 2 }),
    th("ON TIME", { rowSpan: 2 }), th("DEFECT %", { rowSpan: 2 }), th("LOSS min (units)", { rowSpan: 2 }), th("UPH", { colSpan: 2 }), th("MAN", { rowSpan: 2 })),
    h("tr", null, th("PLAN"), th("TARG"), th("PROD"), th("DIFF"), th("TARG"), th("RESULT"))];
  const rows = g.lines.map(r => h("tr", null,
    h("td.line." + r.status, { title: r.ktext }, r.arbpl),
    h("td.mdl", { title: (r.model_text || "") + (r.orders.length ? " - orders " + r.orders.join(", ") : "") }, `${r.model || "-"}  ${r.model_text ? "· " + r.model_text : ""}`),
    h("td", null, n0(r.plan)), h("td.tg", null, n0(r.target)), h("td", null, n0(r.prod)), h("td", null, sg(r.diff)),
    h("td", null, r.ach === null ? "-" : h("span." + (r.ach >= 100 ? "g" : r.ach >= 90 ? "y" : "r"), null, p1(r.ach))),
    h("td", null, p1(r.on_time)), h("td", null, h("span." + (r.defect <= 1 ? "g" : "r"), null, Number(r.defect).toFixed(2))),
    h("td", null, h("span." + (r.loss_min ? "r" : "g"), null, String(r.loss_min)), " ", h("span" + (r.loss_min ? ".r" : ""), null, `(${n0(r.loss_units)})`)),
    h("td", null, n0(r.uph_target)), h("td", null, h("span." + (r.uph_result >= r.uph_target ? "g" : "r"), null, n0(r.uph_result))), h("td", null, String(r.man))));
  const t = g.total;
  rows.push(h("tr.tot", null, h("td.l", { colSpan: 2 }, `Total (${t.running}/${t.lines})`), h("td", null, n0(t.plan)), h("td.tg", null, n0(t.target)),
    h("td", null, n0(t.prod)), h("td", null, sg(t.diff)), h("td", null, t.ach === null ? "-" : h("span." + (t.ach >= 100 ? "g" : "r"), null, p1(t.ach))),
    h("td", null, p1(t.on_time)), h("td", null, h("span." + (t.defect <= 1 ? "g" : "r"), null, Number(t.defect).toFixed(2))),
    h("td", null, h("span." + (t.loss_min ? "r" : "g"), null, `${t.loss_min} (${n0(t.loss_units)})`)),
    h("td", null, n0(t.uph_target)), h("td", null, h("span." + (t.uph_result >= t.uph_target ? "g" : "r"), null, n0(t.uph_result))), h("td", null, String(t.man))));
  return h("div.pb-area", null, h("h3", null, g.area), h("table", null, h("thead", null, ...head), h("tbody", null, ...rows)));
}

function boxes(b) {
  const box = (title, body) => h("div.pb-box", null, h("h3", null, title), body);
  const tbl = (head, rows) => h("table", null, h("thead", null, h("tr", null, head.map(x => h("th", null, x)))), h("tbody", null, ...rows));
  const s = b.shipping;
  const ship = tbl(["", ...s.map(w => w.week)], [["Ordered (due)", "ordered"], ["Delivery created", "delivery"], ["Shipped (goods issue)", "shipped"], ["Not shipped", "open"]]
    .map(([t, k]) => h("tr", null, h("td.k", null, t), ...s.map(w => h("td" + (k === "open" && w[k] ? ".r" : ""), null, n0(w[k]))))));
  const att = b.attendance.length ? tbl(["Team", "Total", "Absent", "Attend", "%"], b.attendance.map(a => h("tr", null, h("td.k", null, a.team),
    h("td", null, String(a.total)), h("td", null, String(a.absent)), h("td", null, String(a.attend)), h("td", null, h("span." + (a.rate >= 90 ? "g" : "r"), null, p1(a.rate))))))
    : h("div.pb-nodata", null, "No Data");
  const mat = b.shortages.length ? tbl(["Material", "Need", "Stock", "Short", "Needed"], b.shortages.map(x => h("tr", null, h("td.k", { title: x.maktx + " - orders " + x.orders.join(", ") }, x.matnr),
    h("td", null, n0(x.required)), h("td", null, n0(x.stock)), h("td.r", null, n0(x.short)), h("td", null, x.bdter || ""))))
    : h("div.pb-ok", null, "✓ No shortages for released orders");
  const q = b.quality;
  const qual = h("div", null, tbl(["Scrap", "Today", "D-1", "Week"], q.lines.map(x => h("tr", null, h("td.k", null, x.arbpl),
    h("td" + (x.today ? ".r" : ""), null, n0(x.today)), h("td", null, n0(x.d1)), h("td", null, n0(x.week))))),
    tbl(["Repair & rework", ""], [h("tr", null, h("td.k", null, "Open rework / refurbish orders"), h("td", null, String(q.rework_open))),
      h("tr", null, h("td.k", null, "Blocked (defective) stock"), h("td" + (q.blocked_stock ? ".y" : ""), null, n0(q.blocked_stock)))]));
  const po = b.po_pending.length ? tbl(["Purchasing group", "D-3+", "D-2", "D-1", "D-0"], b.po_pending.map(x => h("tr", null, h("td.k", null, x.text),
    ...["d3", "d2", "d1", "d0"].map(k => h("td" + (x[k] ? ".r" : ""), null, String(x[k]))))))
    : h("div.pb-ok", null, "✓ No late purchase orders");
  return h("div.pb-boxes", null, box("Shipping Status", ship), box("Attendance Rate", att), box("Material Supply", mat), box("Quality / Repairs", qual), box("PO Pending", po));
}

register("ZPP_BOARD", { title: "Production Status Board", async render(app, params) {
  style();
  let auto = true, timer = null, clockT = null;
  const date = h("input", { type: "date", value: params.datum || today() });
  const onBtn = h("button.pb-on", { type: "button" }, "ON");
  const clockEl = h("span.pb-clock", null, "");
  const tvBtn = h("button.pb-btn", { type: "button", title: "Full screen for the TV on the shop floor" }, "⛶ TV");
  const lastBtn = h("button.pb-btn", { type: "button" }, "Last production day");
  const body = h("div");
  const root = h("div.pb", null, h("div.pb-head", null, date, onBtn, h("span.pb-mode", null, "Plan + On time"), h("span.pb-title", null, "PRODUCTION STATUS"), lastBtn, tvBtn, clockEl), body);
  app.append(root);
  let lastDay = null;
  const tick = () => { if (!document.body.contains(root)) { clearInterval(clockT); clearInterval(timer); return; }
    const d = new Date(); clockEl.textContent = `${date.value} ${d.toTimeString().slice(0, 8)}`; };
  const load = async () => {
    const b = await run(() => api(`/api/pp/board?datum=${date.value}`)); if (!b) return;
    lastDay = b.last_day; body.innerHTML = "";
    body.append(b.groups.length ? h("div.pb-areas", null, ...b.groups.map(areaTable))
      : h("div.pb-empty", null, `No line plan and no production on ${b.datum}. `, lastDay ? `Last production day: ${lastDay}. ` : "",
        "Plan the lines in ZPP_LINEPLAN and confirm production in CO11N."), boxes(b));
  };
  const setAuto = on => { auto = on; onBtn.textContent = on ? "ON" : "OFF"; onBtn.classList.toggle("off", !on); clearInterval(timer); if (on) timer = setInterval(load, 60000); };
  onBtn.addEventListener("click", () => setAuto(!auto));
  date.addEventListener("change", load);
  lastBtn.addEventListener("click", () => { if (lastDay) { date.value = lastDay; load(); } else msg("I", "No production recorded yet"); });
  tvBtn.addEventListener("click", () => { if (document.fullscreenElement) document.exitFullscreen(); else if (root.requestFullscreen) root.requestFullscreen(); });
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Line plan", onClick: () => go("ZPP_LINEPLAN", { datum: date.value }) },
    { label: "Downtime", onClick: () => go("ZPP_LOSS", { datum: date.value }) }, { label: "Confirm production (CO11N)", onClick: () => go("CO11N") }]);
  clockT = setInterval(tick, 1000); tick();
  setAuto(true);
  await load();
} });

// ------------------------------------------------------------------ ZPP_LINEPLAN
register("ZPP_LINEPLAN", { title: "Daily Line Plan", async render(app, params) {
  const f = { datum: inp({ type: "date", value: params.datum || today() }), src: inp({ type: "date" }) }, out = h("div");
  app.append(panel(null, grid(field("Production day", f.datum), field("Copy from day", f.src))),
    note("One row per line (work center): the model or order, the planned quantity of the day, the target units per hour (empty = plan / shift hours), the operators and the shift. Production is counted from the confirmations (CO11N)."), out);
  const load = async () => {
    const d = await run(() => api(`/api/pp/lineplan?datum=${f.datum.value}`)); if (!d) return;
    out.innerHTML = "";
    const rows = d.rows.map(r => ({ r, aufnr: inp({ value: r.aufnr || "", w: "s" }), matnr: inp({ value: r.matnr || "", w: "s", upper: true, list: "dl-matnr" }),
      plan: inp({ value: r.plan || "", w: "s" }), uph: inp({ value: r.uph || "", w: "s" }), man: inp({ value: r.man || "", w: "s" }),
      start: inp({ value: r.start, w: "s" }), hours: inp({ value: r.hours, w: "s" }) }));
    out.append(h("table.grid", null, h("thead", null, h("tr", null, ["Area", "Line", "Order", "Material", "Plan qty", "UPH target", "Operators", "Shift start", "Hours", ""].map(t => h("th", null, t)))),
      h("tbody", null, rows.map(x => h("tr", null, h("td", null, x.r.area), h("td", null, `${x.r.arbpl} ${x.r.ktext}`), h("td", null, x.aufnr), h("td", null, x.matnr),
        h("td", null, x.plan), h("td", null, x.uph), h("td", null, x.man), h("td", null, x.start), h("td", null, x.hours),
        h("td", null, h("button.btn", { type: "button", on: { click: async () => {
          const res = await run(() => api("/api/pp/lineplan/save", { datum: f.datum.value, arbpl: x.r.arbpl, aufnr: val(x.aufnr), matnr: up(x.matnr), plan: val(x.plan),
            uph: val(x.uph), man: val(x.man), start: val(x.start), hours: val(x.hours) }));
          if (res) { msg("S", res.message); load(); } } } }, "Save")))))));
  };
  f.datum.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Copy plans", onClick: async () => {
    if (!f.src.value) return msg("E", "Enter the day to copy from");
    const r = await run(() => api("/api/pp/lineplan/copy", { src: f.src.value, dst: f.datum.value })); if (r) { msg("S", r.message); load(); } } },
    { label: "Production board", onClick: () => go("ZPP_BOARD", { datum: f.datum.value }) }]);
  load();
} });

// ------------------------------------------------------------------ ZPP_LOSS
register("ZPP_LOSS", { title: "Line Downtime (loss)", async render(app, params) {
  const REASONS = [["MAT", "Material shortage"], ["MACH", "Machine breakdown"], ["CHG", "Model changeover"], ["QUAL", "Quality problem"],
    ["MAN", "Manpower shortage"], ["UTIL", "Power / utilities"], ["OTH", "Other"]];
  const f = { datum: inp({ type: "date", value: params.datum || today() }), arbpl: inp({ w: "s", upper: true, ph: "e.g. WC-ASSY" }), minutes: inp({ w: "s" }),
    reason: sel(REASONS, "MAT"), text: inp({ w: "l" }) }, out = h("div");
  app.append(panel("Record a stop of the line", grid(field("Day", f.datum), field("Line (work center)", f.arbpl, { req: true }), field("Minutes stopped", f.minutes, { req: true }),
    field("Reason", f.reason), field("Text", f.text))), out);
  const load = async () => {
    const d = await run(() => api(`/api/pp/loss?datum=${f.datum.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(alv({ rows: d.rows, title: `Downtime on ${f.datum.value}`, emptyText: "No downtime recorded", columns: [{ key: "arbpl", label: "Line" },
      { key: "minutes", label: "Minutes", type: "int", sum: true }, { key: "reason_text", label: "Reason" }, { key: "text", label: "Text" }, { key: "usnam", label: "By" }, { key: "ts", label: "Entered" }] }));
  };
  f.datum.addEventListener("change", load);
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/pp/loss", { datum: f.datum.value, arbpl: up(f.arbpl), minutes: val(f.minutes), reason: f.reason.value, text: val(f.text) }));
    if (r) { msg("S", r.message); f.minutes.value = ""; f.text.value = ""; load(); } } }, { label: "Production board", onClick: () => go("ZPP_BOARD", { datum: f.datum.value }) }]);
  load();
} });
})();
