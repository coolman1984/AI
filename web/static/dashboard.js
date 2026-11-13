/* NERP - ERP Dashboard (separate window, opened by "NERP Dashboard").
   Plain JavaScript; every card comes from /api/dash/overview (live data). */
"use strict";
(() => {
const C = { blue: "#2f80ed", green: "#27ae60", orange: "#f2994a", red: "#eb5757", violet: "#9b51e0",
  teal: "#2bb3c0", yellow: "#f2c94c", grey: "#c3ccd8" };
const PAL = [C.blue, C.green, C.orange, C.violet, C.teal, C.yellow, C.red, C.grey];
const NS = "http://www.w3.org/2000/svg";
const $ = s => document.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "on") for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn);
    else if (k === "style") Object.assign(e.style, v);
    else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k instanceof Node ? k : String(k));
  return e;
}
function s(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}
const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
function money(v) {
  if (v === null || v === undefined) return "-";
  const a = Math.abs(v);
  if (a >= 1e9) return nf1.format(v / 1e9) + "B";
  if (a >= 1e6) return nf1.format(v / 1e6) + "M";
  if (a >= 1e4) return nf1.format(v / 1e3) + "K";
  return nf0.format(v);
}
// display currency (same choice as the BI reports in NERP: kept in this browser)
let CUR = "EGP";
try { CUR = localStorage.getItem("mm_dispcur") || "EGP"; } catch (e) { CUR = "EGP"; }
const egp = v => money(v) + " " + CUR;
const pct = v => v === null || v === undefined ? "-" : nf1.format(v) + "%";

function api(path) {
  return fetch(path, { credentials: "same-origin" }).then(async r => {
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw d;
    return d;
  });
}
function openTx(tcode) { window.open("/#/" + tcode, "_blank"); }

// ------------------------------------------------------------------ charts (inline SVG)
function areaChart(values, labels, color, opts) {
  opts = opts || {};
  const W = 420, H = opts.h || 140, P = 24, n = Math.max(values.length, 2);
  const max = Math.max(1, ...values.map(v => v || 0)), min = Math.min(0, ...values.map(v => v || 0));
  const x = i => P + i * (W - 2 * P) / (n - 1), y = v => H - 22 - ((v || 0) - min) / (max - min) * (H - 40);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
  const id = "g" + Math.random().toString(36).slice(2);
  const g = s("linearGradient", { id, x1: 0, x2: 0, y1: 0, y2: 1 });
  g.append(s("stop", { offset: "0", "stop-color": color, "stop-opacity": ".35" }), s("stop", { offset: "1", "stop-color": color, "stop-opacity": "0" }));
  const defs = s("defs"); defs.append(g); svg.append(defs);
  for (let k = 0; k <= 3; k++) svg.append(s("line", { x1: P, x2: W - P, y1: 18 + k * (H - 40) / 3, y2: 18 + k * (H - 40) / 3, stroke: "#eef1f5" }));
  const pts = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  svg.append(s("polygon", { points: `${x(0)},${y(min)} ${pts} ${x(values.length - 1)},${y(min)}`, fill: `url(#${id})` }));
  svg.append(s("polyline", { points: pts, fill: "none", stroke: color, "stroke-width": 2.5, "stroke-linejoin": "round" }));
  values.forEach((v, i) => svg.append(s("circle", { cx: x(i), cy: y(v), r: 3, fill: "#fff", stroke: color, "stroke-width": 2 })));
  (labels || []).forEach((l, i) => svg.append(s("text", { x: x(i), y: H - 4, "text-anchor": "middle" }, l)));
  if (opts.second) {
    const m2 = Math.max(1, ...opts.second.map(v => Math.abs(v || 0)));
    const y2 = v => H - 22 - ((v || 0) + m2) / (2 * m2) * (H - 40);
    svg.append(s("polyline", { points: opts.second.map((v, i) => `${x(i)},${y2(v)}`).join(" "), fill: "none", stroke: opts.secondColor || C.orange, "stroke-width": 2, "stroke-dasharray": "5 4" }));
  }
  return svg;
}
function donut(parts, center, sub) {
  const W = 180, R = 70, r = 46, cx = 90, cy = 90;
  const svg = s("svg", { viewBox: `0 0 ${W} ${W}`, style: "max-width:190px;margin:auto" });
  const tot = parts.reduce((a, p) => a + Math.max(p.value, 0), 0) || 1;
  let a0 = -Math.PI / 2;
  parts.forEach((p, i) => {
    const frac = Math.max(p.value, 0) / tot;
    if (frac <= 0) return;
    const a1 = a0 + frac * Math.PI * 2 - (frac >= 1 ? 0.0001 : 0);
    const L = a1 - a0 > Math.PI ? 1 : 0;
    const P1 = [cx + R * Math.cos(a0), cy + R * Math.sin(a0)], P2 = [cx + R * Math.cos(a1), cy + R * Math.sin(a1)];
    const p3 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)], p4 = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
    svg.append(s("path", { d: `M${P1} A${R},${R} 0 ${L} 1 ${P2} L${p3} A${r},${r} 0 ${L} 0 ${p4} Z`, fill: p.color || PAL[i % PAL.length] }));
    a0 = a1;
  });
  svg.append(s("text", { x: cx, y: cy + 4, "text-anchor": "middle", style: "font-size:22px;font-weight:700;fill:#1d2a3a" }, center));
  if (sub) svg.append(s("text", { x: cx, y: cy + 22, "text-anchor": "middle" }, sub));
  return svg;
}
function bars(items, color) {
  const W = 420, H = 130, P = 6, n = Math.max(items.length, 1), bw = (W - 2 * P) / n * 0.62;
  const max = Math.max(1, ...items.map(i => i.value));
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}` });
  items.forEach((it, i) => {
    const x = P + i * (W - 2 * P) / n + ((W - 2 * P) / n - bw) / 2, hgt = it.value / max * (H - 34);
    svg.append(s("rect", { x, y: H - 18 - hgt, width: bw, height: Math.max(hgt, 1), rx: 3, fill: it.color || color }));
    svg.append(s("text", { x: x + bw / 2, y: H - 4, "text-anchor": "middle" }, String(it.name).slice(0, 7)));
    svg.append(s("text", { x: x + bw / 2, y: H - 22 - hgt, "text-anchor": "middle", style: "font-weight:600;fill:#1d2a3a" }, money(it.value)));
  });
  return svg;
}
function hbars(items) {
  const wrap = h("div");
  const max = Math.max(1, ...items.map(i => Math.max(i.a || 0, i.b || 0)));
  items.forEach(i => wrap.append(h("div", { style: { margin: "6px 0" } },
    h("div", { style: { display: "flex", fontSize: "12px" } }, h("span", null, i.name), h("span", { style: { marginLeft: "auto", fontWeight: 600 } }, i.right || "")),
    h("div", { style: { background: "#eef1f5", height: "7px", borderRadius: "4px", position: "relative", marginTop: "3px" } },
      h("div", { style: { position: "absolute", left: 0, top: 0, bottom: 0, width: (Math.max(0, i.b || 0) / max * 100) + "%", background: "#c9d8f3", borderRadius: "4px" } }),
      h("div", { style: { position: "absolute", left: 0, top: 0, bottom: 0, width: (Math.max(0, i.a || 0) / max * 100) + "%", background: i.color || C.blue, borderRadius: "4px", opacity: .9 } })))));
  return wrap;
}

// ------------------------------------------------------------------ cards
function card(id, title, icon, color, go, ...body) {
  return h("section", { class: "card " + (id.cls || ""), id: id.id || null },
    h("h2", null, h("span", { class: "ic", style: { background: color } }, icon), title,
      go ? h("a", { class: "go", on: { click: () => openTx(go) }, title: "Open " + go }, go + " ›") : null), ...body);
}
const legend = items => h("ul", { class: "legend" }, items.map((it, i) =>
  h("li", null, h("i", { style: { background: it.color || PAL[i % PAL.length] } }), it.name, h("em", null, it.text))));
const kpi = (label, value, cls) => h("div", { class: "kpi" }, h("div", { class: "lbl" }, label), h("div", { class: "v " + (cls || "") }, value));
const tile = (value, label) => h("div", { class: "tile" }, h("b", null, value), h("span", null, label));
const shortM = m => m ? ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m.slice(5, 7) - 1] : "";

function render(d) {
  const g = $("#grid");
  g.innerHTML = "";
  const F = d.finance, Pf = d.profit, Pr = d.production, Q = d.quality, W = d.warehouse, Pu = d.procurement, S = d.sales, Co = d.controlling, A = d.analytics;
  const months = d.months.map(shortM);
  // Finance - income
  g.append(card({ id: "finance", cls: "span2" }, "Finance", "€", C.blue, "F.01",
    h("div", { style: { display: "flex", alignItems: "baseline", gap: "12px" } }, h("div", null, h("div", { class: "lbl" }, "Total income (net sales, year to date)"),
      h("div", { class: "big" }, egp(F.income_ytd))), h("span", { class: "badge", style: { marginLeft: "auto" } }, `Plan ${egp(F.income_plan)} · ${pct(F.income_ach)}`)),
    areaChart(F.income_trend, months, C.blue)));
  // Finance - cash
  g.append(card({}, "Cash & Open Items", "₤", C.teal, "FBL5N",
    h("div", { class: "kpis" }, kpi("Bank balance", egp(F.bank)), kpi("Receivables", egp(F.receivables)),
      kpi("Payables", egp(F.payables)), kpi("Overdue receivables", egp(F.overdue), F.overdue > 0 ? "neg" : "pos"))));
  // Tasks
  g.append(card({ id: "tasks", cls: "row2" }, "Tasks", "☑", C.violet, "ZINBOX",
    d.tasks.length ? d.tasks.map((t, i) => h("div", { class: "task", on: { click: () => openTx(t.tcode) } },
      h("span", { class: "dot", style: { background: PAL[i % PAL.length] } }, "!"),
      h("div", null, h("b", null, t.typ), h("small", null, t.text.slice(0, 70)), h("small", null, `${t.date || ""} · ${t.tcode}`))))
      : h("p", { class: "muted" }, "Nothing is waiting for approval.")));
  // Profitability
  g.append(card({}, "Profitability", "◔", C.green, "KE30",
    h("div", { class: "split" }, donut([{ value: Pf.income, color: C.green }, { value: Pf.expenses, color: C.blue }, { value: Math.max(Pf.profit, 0), color: C.orange }],
      money(Pf.profit), "operating profit"),
    legend([{ name: "Income", text: money(Pf.income), color: C.green }, { name: "Expenses", text: money(Pf.expenses), color: C.blue },
      { name: "Profit", text: money(Pf.profit), color: C.orange }, { name: "Margin", text: pct(Pf.margin_pct), color: C.grey }])),
    h("div", { class: "lbl", style: { marginTop: "6px" } }, "Recent invoices"),
    h("table", null, h("tbody", null, Pf.invoices.map(i => h("tr", null, h("td", null, i.no), h("td", null, (i.customer || "").slice(0, 18)),
      h("td", { class: "n" + (i.amount < 0 ? " neg" : "") }, money(i.amount))))))));
  // Manufacturing
  g.append(card({ id: "manufacturing" }, "Manufacturing", "⚙", C.orange, "COOIS",
    h("div", { class: "split" }, donut([{ value: Pr.done, color: C.green }, { value: Pr.running, color: C.blue }, { value: Pr.late, color: C.red }, { value: Pr.created, color: C.yellow }],
      pct(Pr.on_track).replace(".0", ""), "on track"),
    legend([{ name: "Completed", text: Pr.done, color: C.green }, { name: "In progress", text: Pr.running, color: C.blue },
      { name: "Delayed", text: Pr.late, color: C.red }, { name: "Not released", text: Pr.created, color: C.yellow }])),
    h("div", { class: "lbl" }, `${Pr.total} production orders`)));
  // Quality
  g.append(card({ id: "quality" }, "Quality Control", "✓", C.teal, "MB52",
    h("div", { class: "kpis" }, kpi("Good yield", pct(Q.yield_pct), "pos"), kpi("Scrap qty", nf0.format(Q.scrap), Q.scrap ? "neg" : ""),
      kpi("Materials in QI", Q.q_materials)),
    h("div", { class: "lbl", style: { marginTop: "8px" } }, "Latest activity"),
    h("table", null, h("tbody", null, Q.activity.map(a => h("tr", null, h("td", null, a.text.slice(0, 26)), h("td", { class: "n" }, a.date || "")))))));
  // Warehouse
  g.append(card({ id: "warehouse", cls: "span2" }, "Warehouse", "▦", C.blue, "MB52",
    h("div", { style: { display: "flex", alignItems: "baseline", gap: "10px" } }, h("div", { class: "lbl" }, "Inventory value"), h("div", { class: "big" }, egp(W.value))),
    bars(W.groups.slice(0, 8).map((x, i) => ({ name: x.name, value: x.value, color: i % 2 ? "#5b9bf0" : C.blue })), C.blue),
    h("div", { class: "tiles" }, tile(W.materials, "materials in stock"), tile(W.bins, "bins used"), tile(W.below_reorder, "below reorder point"),
      tile(money(W.q_blocked), "quality / blocked"), tile(money(W.old_stock), "older than 180 days"), tile(W.counts_open, "open stock counts"))));
  // Procurement
  g.append(card({ id: "procurement" }, "Procurement", "⛟", C.violet, "ME2N",
    h("div", { class: "split" }, donut(Pu.groups.map((x, i) => ({ value: x.value, color: PAL[i % PAL.length] })), money(Pu.spend_ytd), "spend YTD"),
      legend(Pu.groups.slice(0, 6).map((x, i) => ({ name: x.name, text: money(x.value), color: PAL[i % PAL.length] })))),
    h("div", { class: "kpis", style: { marginTop: "6px" } }, kpi("Open PO value", money(Pu.open_value)),
      kpi("vs last month", pct(Pu.change), Pu.change > 0 ? "neg" : "pos"), kpi("Vendors", Pu.vendors))));
  // Sales
  g.append(card({ id: "sales" }, "Sales & CRM", "☎", C.green, "VA05",
    h("div", { class: "kpis" }, kpi("This month", egp(S.month)), kpi("Order backlog", money(S.backlog)), kpi("Margin", pct(S.margin_pct), "pos")),
    areaChart(S.trend, months, C.green, { h: 120 }),
    h("div", { class: "lbl" }, `${S.customers} customers this year · ${S.open_orders} open orders · ${S.blocked} credit-blocked`)));
  // HR
  const H = d.hr;
  g.append(card({ id: "hr" }, "HR", "☺", C.teal, "ZHR_COCKPIT",
    h("div", { class: "kpis" }, kpi("Headcount", H.headcount), kpi("Payroll cost " + H.last_period, money(H.cost_last)),
      kpi("On leave today", H.on_leave), kpi("Open leave requests", H.open_requests, H.open_requests ? "neg" : "")),
    H.cost_trend.length ? areaChart(H.cost_trend, H.months.map(shortM), C.teal, { h: 110 }) : null,
    h("div", { class: "lbl" }, H.by_group.map(x => `${x.name} ${x.value}`).join(" · ") + ` · hires ${H.hires} / leavers ${H.leavers} this year`)));
  // Controlling
  g.append(card({ id: "controlling" }, "Controlling", "◔", C.orange, "S_ALR_87013611",
    h("div", { class: "kpis" }, kpi("Cost YTD", money(Co.actual)), kpi("Plan YTD", money(Co.plan)), kpi("Used", pct(Co.ach), Co.ach > 100 ? "neg" : "pos")),
    hbars(Co.centers.map(c => ({ name: c.name, a: c.actual, b: c.plan, right: pct(c.ach), color: c.ach > 100 ? C.red : C.orange })))));
  // Analytics
  g.append(card({ id: "analytics" }, "Analytics", "↗", C.blue, "ZBI_DASH",
    h("div", { class: "kpis" }, kpi("Operating profit YTD", egp(A.op_ytd), A.op_ytd < 0 ? "neg" : "pos"), kpi("Gross margin", pct(A.gm_pct))),
    areaChart(A.op_trend, months, C.violet, { h: 120 }),
    h("div", { class: "lbl" }, `Net sales this month ${egp(A.month_sales)} · same month last year ${egp(A.prev_year)}`)));
  $("#sub").textContent = `Live data · period ${d.period} · business date ${d.date} · ${d.currency_note || "amounts in EGP"} · refreshed ${new Date().toLocaleTimeString()}`;
  $("#avatar").textContent = (d.user || "?").slice(0, 2);
  $("#avatar").title = d.user;
  $("#foot").textContent = d.auth ? "User logon ON" : "User logon OFF";
}

async function load() {
  $("#err").innerHTML = "";
  try {
    const d = await api("/api/dash/overview?currency=" + encodeURIComponent(CUR));
    CUR = d.currency || CUR;
    render(d);
  } catch (e) {
    const box = h("div", { class: "err" }, (e && e.text) || "No connection to NERP. Is it running?");
    if (e && e.logon) box.append(" ", h("button", { class: "btn", on: { click: () => { window.open("/", "_blank"); } } }, "Log on in NERP"),
      " then ", h("button", { class: "btn", on: { click: load } }, "Retry"));
    $("#err").append(box);
  }
}
$("#refresh").addEventListener("click", load);
$("#cur").value = CUR;
$("#cur").addEventListener("change", () => {
  CUR = $("#cur").value;
  try { localStorage.setItem("mm_dispcur", CUR); } catch (e) { /* private window */ }
  load();
});
$("#bi").addEventListener("click", () => openTx("ZBI"));
document.querySelectorAll("nav a").forEach(a => a.addEventListener("click", e => {
  if (a.dataset.ext) return;
  document.querySelectorAll("nav a").forEach(x => x.classList.toggle("on", x === a));
}));
// the server stops when no window is left: this window counts as one
const tab = "dash-" + Math.random().toString(36).slice(2);
const ping = () => fetch("/api/ping", { method: "POST", body: JSON.stringify({ tab }), headers: { "Content-Type": "application/json" } }).catch(() => {});
ping(); setInterval(ping, 10000);
window.addEventListener("pagehide", () => navigator.sendBeacon("/api/bye", new Blob([JSON.stringify({ tab })], { type: "text/plain" })));
load();
setInterval(load, 120000);
})();
