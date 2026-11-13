/* NERP - BI (Business Intelligence): report portal with category bar and mega
   menu, analysis workspace (Data / Layout / grid) with tabs, P/L structure,
   drill-down, filters, period variables, calculations, exceptions, saved views,
   and the executive KPI cockpit. */
"use strict";
(() => {
const { h, $, api, msg, run, register, go, toolbar, dialog, S } = App;

const B = { cat: null, tabs: [], active: -1, catalog: null, collapsed: {} };
const NF0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const NF1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const NF3 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });
function fmt(v, type) {
  if (v === null || v === undefined) return "";
  if (type === "pct") return NF1.format(v) + " %";
  if (type === "qty") return NF3.format(v);
  return NF0.format(v);
}
const ico = (feat) => h("span.bi-ico" + (feat ? ".feat" : ""), null, feat ? "▦" : "⚲");

async function catalog(force) {
  if (!B.catalog || force) B.catalog = await api("/api/bi/catalog");
  return B.catalog;
}

// ------------------------------------------------------------------ portal shell
function shell(app, body) {
  app.classList.add("bi-app");
  const cats = B.catalog.tree.map(c => c.category);
  const top = h("div.bi-top", null, cats.map(c => h("a.bi-top-i" + (c === B.cat && B.active < 0 ? ".on" : ""), {
    href: "#", on: { click: e => { e.preventDefault(); B.cat = c; B.active = -1; draw(app); } } }, c)),
    h("span.bi-top-user", null, `${(S.me && S.me.name) || S.user} (${S.user})`));
  const left = h("div.bi-left", null,
    h("div.bi-left-h", null, "Standard Report"),
    cats.map(c => h("a.bi-left-i" + (c === B.cat ? ".on" : ""), { href: "#", on: { click: e => { e.preventDefault(); B.cat = c; B.active = -1; draw(app); } } }, c)),
    h("div.bi-left-h", null, "My views"),
    (B.catalog.views || []).length ? B.catalog.views.map(v => h("div.bi-left-v", null,
      h("a", { href: "#", on: { click: e => { e.preventDefault(); openTab(app, v.report, v.title, v.query); } } }, v.title),
      h("button.bi-x", { type: "button", title: "Delete view", on: { click: async () => {
        const r = await run(() => api("/api/bi/view", { delete: true, id: v.id })); if (r) { await catalog(true); draw(app); } } } }, "×")))
      : h("div.bi-left-empty", null, "Save a layout with 'Save view'"));
  const tabs = h("div.bi-tabs", null,
    h("a.bi-tab" + (B.active < 0 ? ".on" : ""), { href: "#", on: { click: e => { e.preventDefault(); B.active = -1; draw(app); } } }, "☰ Reports"),
    B.tabs.map((t, i) => h("span.bi-tab" + (i === B.active ? ".on" : ""), null,
      h("a", { href: "#", on: { click: e => { e.preventDefault(); B.active = i; draw(app); } } }, t.title),
      h("button.bi-x", { type: "button", title: "Close", on: { click: () => { B.tabs.splice(i, 1); B.active = Math.min(B.active, B.tabs.length - 1); if (B.active === i) B.active = -1; draw(app); } } }, "×"))));
  app.append(top, h("div.bi-body", null, left, h("div.bi-main", null, tabs, body)));
}

function draw(app) {
  app.innerHTML = "";
  if (B.active >= 0 && B.tabs[B.active]) return analysis(app, B.tabs[B.active]);
  const cat = B.catalog.tree.find(c => c.category === B.cat) || B.catalog.tree[0];
  B.cat = cat.category;
  const mega = h("div.bi-mega", null, cat.groups.map(g => h("div.bi-mega-col", null, h("h3", null, g.group),
    g.reports.map(r => h("a.bi-rep" + (r.featured ? ".feat" : ""), { href: "#", title: r.id,
      on: { click: e => { e.preventDefault(); openReport(app, r.id); } } }, ico(r.featured), r.title)))));
  toolbar([{ label: "KPI cockpit", primary: true, onClick: () => openReport(app, "EXE_KPI") }, { label: "PL Detail", onClick: () => openReport(app, "CO_PL_DETAIL") }]);
  shell(app, h("div.bi-content", null, h("h2.bi-cat", null, cat.category), mega,
    h("div.note", null, "Every report reads the live data of NERP (no copy). Open a report, then change rows, columns, filters and period; 'Save view' keeps your layout under 'My views'.")));
}

async function openReport(app, rid) {
  const r = await run(() => api("/api/bi/report/" + rid)); if (!r) return;
  openTab(app, rid, r.title, r.query);
}
function openTab(app, rid, title, query) {
  const i = B.tabs.findIndex(t => t.title === title);
  if (i >= 0) { B.active = i; return draw(app); }
  B.tabs.push({ id: rid, title, query: JSON.parse(JSON.stringify(query)), opt: { pct: true, exc: true } });
  if (B.tabs.length > 8) B.tabs.shift();
  B.active = B.tabs.length - 1;
  draw(app);
}

// ------------------------------------------------------------------ analysis workspace
async function analysis(app, tab) {
  const q = tab.query;
  if (q.dashboard) return dashboard(app, tab);
  let res;
  q.currency = q.currency || App.dispCur();
  try { res = await api("/api/bi/query?q=" + encodeURIComponent(JSON.stringify(q))); }
  catch (e) { App.err(e); res = null; }
  app.innerHTML = "";
  const year = h("input.f.w-s", { value: q.year || (res && res.year) || "" }), per = h("input.f.w-s", { value: q.period || (res && res.period) || "" });
  const refresh = () => { q.year = year.value; q.period = per.value; draw(app); };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: refresh },
    { label: (tab.opt.pct ? "Hide" : "Show") + " (%) columns", onClick: () => { tab.opt.pct = !tab.opt.pct; draw(app); } },
    { label: (tab.opt.exc ? "No" : "Show") + " exceptions", onClick: () => { tab.opt.exc = !tab.opt.exc; draw(app); } },
    !q.structure ? { label: "Add share %", onClick: () => { addShare(q); draw(app); } } : null,
    { label: "Swap rows / columns", onClick: () => { swap(q); draw(app); } },
    { label: "Excel", onClick: () => res && excel(tab, res) },
    { label: "Save view", onClick: async () => {
      const r = await App.ask("Save view", [{ name: "t", label: "Name", value: tab.title + " (my view)" }]);
      if (!r) return; const x = await run(() => api("/api/bi/view", { report: tab.id, title: r.t, query: q }));
      if (x) { msg("S", x.message); await catalog(true); } } },
    { label: "Reset", onClick: async () => { const r = await run(() => api("/api/bi/report/" + tab.id)); if (r) { tab.query = r.query; draw(app); } } }]);
  if (!res) { shell(app, h("div.bi-content", null, "No data")); return; }
  // ---------------- data panel
  const chars = Object.entries(res.chars), kfs = Object.entries(res.kfs);
  const used = new Set([...(q.rows || []), q.colchar].filter(Boolean));
  const data = h("div.bi-pane.bi-data", null, h("div.bi-pane-h", null, "Data"),
    h("div.bi-prov", null, `${res.provider_text} [${res.provider}]`),
    h("div.bi-tree", null,
      q.provider === "COPA" ? h("div.bi-node" + (q.structure ? ".used" : ""), { on: { click: () => structMenu(app, q) } }, "▤ P/L Str.") : null,
      chars.map(([k, t]) => h("div.bi-node" + (used.has(k) ? ".used" : "") + ((q.filters || {})[k] ? ".filt" : ""),
        { on: { click: () => charMenu(app, tab, k, t) } }, "◈ " + t)),
      h("div.bi-sub", null, "Key figures"),
      kfs.map(([k, t]) => {
        const on = (q.columns || []).some(c => c.kf === k);
        const cb = h("input", { type: "checkbox", checked: on, disabled: !!q.structure });
        cb.addEventListener("change", () => { toggleKf(q, k, cb.checked); draw(app); });
        return h("label.bi-kf", null, cb, " ", t);
      })));
  // ---------------- layout panel
  const chip = (t, onX) => h("div.bi-chip", null, t, onX ? h("button.bi-x", { type: "button", on: { click: onX } }, "×") : null);
  const colsLbl = q.structure ? (q.columns || []).filter(c => !c.pct).map(c => c.label || c.kf) : (q.columns || []).filter(c => !c.pct).map(c => c.label || res.kfs[c.kf]);
  const layout = h("div.bi-pane.bi-layout", null, h("div.bi-pane-h", null, "Layout"),
    h("div.bi-sec", null, "Columns"), q.colchar ? chip(res.chars[q.colchar], () => { delete q.colchar; draw(app); }) : null,
    colsLbl.map(t => chip(t)),
    h("div.bi-sec", null, "Rows"), q.structure ? chip("P/L Str.") : (q.rows || []).map(r => chip(res.chars[r], () => { q.rows = q.rows.filter(x => x !== r); draw(app); })),
    h("div.bi-sec", null, "Background (filters)"),
    Object.entries(q.filters || {}).filter(([, v]) => v && v.length).map(([k, v]) => chip(`${res.chars[k]} = ${[].concat(v).join(", ")}`, () => { delete q.filters[k]; draw(app); })),
    h("div.bi-sec", null, "Variables"),
    h("div.bi-var", null, "Year ", year), h("div.bi-var", null, "Period ", per),
    h("div.bi-var", null, "Currency ", App.curSel(v => { q.currency = v; draw(app); })),
    h("button.btn.primary", { type: "button", on: { click: refresh } }, "Apply"));
  // ---------------- grid
  const cols = res.columns.map((c, i) => Object.assign({ i }, c)).filter(c => tab.opt.pct || !c.pct);
  const grid = h("table.bi-grid");
  const hd = h("tr", null, res.row_headers.map(x => h("th.bi-rh", null, x.label)),
    cols.map(c => h("th" + (c.pct ? ".pct" : "") + (c.total ? ".tot" : ""), { title: "Sort", on: { click: () => {
      if (q.structure) return; q.sort = { col: c.i, dir: q.sort && q.sort.col === c.i ? -q.sort.dir : -1 }; draw(app); } } }, c.label)));
  const tb = h("tbody");
  let parent = null;
  res.rows.forEach(r => {
    if (q.structure && r.level === 0) parent = r.node;
    const hidden = q.structure && r.level > 0 && B.collapsed[tab.title + parent];
    if (hidden) return;
    const hasKids = q.structure && r.level === 0 && res.rows.some((x, j) => x.level > 0 && res.rows.slice(0, j).reverse().find(y => y.level === 0).node === r.node);
    const lab = r.labels.map((l, j) => h("td.bi-rh" + (j === 0 && r.level ? ".lv1" : ""), null,
      j === 0 && hasKids ? h("span.bi-tg", { on: { click: () => { const k = tab.title + r.node; B.collapsed[k] = !B.collapsed[k]; draw(app); } } }, B.collapsed[tab.title + r.node] ? "⊞ " : "⊟ ") : null, l));
    const big = q.structure && ["NS", "GM", "OP", "NI"].includes(r.node);
    tb.append(h("tr" + (r.total ? ".total" : "") + (big ? ".key" : ""), null, lab, cols.map(c => {
      const v = r.values[c.i];
      const neg = tab.opt.exc && typeof v === "number" && v < 0;
      return h("td" + (c.pct ? ".pct" : "") + (neg ? ".neg" : ""), null, fmt(v, c.type));
    })));
  });
  grid.append(h("thead", null, hd), tb);
  const head = h("div.bi-head", null, h("b", null, tab.title), h("span", null, ` · ${res.provider_text} · year ${res.year}, period ${res.period} · ${res.currency}` +
    (Object.keys(q.filters || {}).length ? " · filtered" : "")), res.currency_note ? h("small", null, " · " + res.currency_note) : null);
  shell(app, h("div.bi-work", null, data, layout, h("div.bi-gridwrap", null, head, h("div.bi-scroll", null, grid))));
}

function toggleKf(q, k, on) {
  q.columns = q.columns || [];
  if (on) q.columns.push({ kf: k }); else q.columns = q.columns.filter(c => c.kf !== k);
  q.columns = q.columns.filter((c, i, a) => !c.pct || (i && !a[i - 1].pct));
}
function addShare(q) {
  const out = [];
  (q.columns || []).filter(c => !c.pct).forEach(c => { out.push(c); out.push({ kf: c.kf, pct: true, label: "Share %" }); });
  q.columns = out;
}
function swap(q) {
  if (q.structure) return msg("I", "The P/L structure always stays in the rows");
  const r = (q.rows || [])[0];
  if (q.colchar) { q.rows = [q.colchar].concat((q.rows || []).slice(1)); q.colchar = r; }
  else if (r && (q.rows || []).length > 1) { q.colchar = r; q.rows = q.rows.slice(1); }
  else msg("I", "Drill down a second characteristic first");
}
async function structMenu(app, q) {
  if (q.structure) {
    if (!await App.confirmBox("P/L structure", "Replace the P/L structure by a drill-down (customer rows, gross sales / deduction / qty)?")) return;
    const cols = (q.columns || []).filter(c => !c.pct);
    q.columns = cols.length ? cols.map(c => Object.assign({}, c, { kf: "vv010", label: (c.label || "") + " Gross sales" })) : [{ kf: "vv010" }];
    delete q.structure; delete q.colchar; q.rows = ["customer"];
  } else { q.structure = "PL"; q.rows = []; q.columns = (q.columns || []).filter(c => !c.pct).map(c => ({ version: c.version, time: c.time, label: c.label })); if (!q.columns.length) q.columns = [{ version: "ACT", label: "Actual" }]; }
  draw(app);
}
async function charMenu(app, tab, k, t) {
  const q = tab.query;
  const a = await dialog(t, h("p", null, "What do you want to do with this characteristic?"), [
    { label: "Filter values…", value: () => "f" }, !q.structure ? { label: "Drill down in rows", value: () => "r" } : null,
    { label: "Spread over columns", value: () => "c" }, { label: "Cancel", value: () => null }].filter(Boolean));
  if (a === "r") { q.rows = (q.rows || []).filter(x => x !== k); q.rows.push(k); if (q.rows.length > 3) q.rows.shift(); if (q.colchar === k) delete q.colchar; }
  if (a === "c") { if (q.structure && (q.columns || []).filter(c => !c.pct).length > 3) q.columns = q.columns.filter(c => !c.pct).slice(0, 2); q.colchar = k; q.rows = (q.rows || []).filter(x => x !== k); }
  if (a === "f") {
    const vals = await run(() => api(`/api/bi/values?provider=${q.provider}&char=${k}`)); if (!vals) return;
    const cur = new Set([].concat((q.filters || {})[k] || []));
    const boxes = vals.map(v => { const c = h("input", { type: "checkbox", checked: cur.has(v) }); return [v, c]; });
    const r = await dialog(`Filter: ${t}`, h("div.bi-fil", null, boxes.map(([v, c]) => h("label", null, c, " ", v))), [
      { label: "Remove filter", value: () => [] }, { label: "Cancel", value: () => null }, { label: "OK", primary: true, value: () => boxes.filter(x => x[1].checked).map(x => x[0]) }]);
    if (r === null) return;
    q.filters = q.filters || {};
    if (r.length) q.filters[k] = r; else delete q.filters[k];
  }
  if (a) draw(app);
}
function excel(tab, res) {
  const cols = res.columns.filter(c => tab.opt.pct || !c.pct);
  const idx = res.columns.map((c, i) => i).filter(i => tab.opt.pct || !res.columns[i].pct);
  const rows = res.rows.map(r => { const o = {}; res.row_headers.forEach((x, j) => { o["h" + j] = (r.level ? "   " : "") + r.labels[j]; }); idx.forEach((i, j) => { o["c" + j] = r.values[i]; }); return o; });
  App.exportRows({ title: tab.title, columns: res.row_headers.map((x, j) => ({ key: "h" + j, label: x.label })).concat(cols.map((c, j) => ({ key: "c" + j, label: c.label, type: c.type === "pct" ? null : c.type === "qty" ? "qty" : "amt" }))) }, rows);
}

// ------------------------------------------------------------------ executive cockpit
async function dashboard(app, tab) {
  if (tab.query.dashboard !== "EXEC") return statusBoard(app, tab);
  const d = await run(() => api("/api/bi/dashboard/" + tab.query.dashboard));
  app.innerHTML = "";
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: () => draw(app) }]);
  if (!d) return shell(app, h("div"));
  const tiles = h("div.bi-kpis", null, d.kpis.map(k => {
    const val = k.unit === "%" ? fmt(k.v, "pct") : k.unit === "pcs" ? fmt(k.v, "qty") : fmt(k.v, "amt");
    const ach = k.ach !== undefined && k.ach !== null ? h("div.bi-bar", null, h("span" + (k.ach < 90 ? ".low" : ""), { style: { width: Math.max(0, Math.min(k.ach, 130)) / 1.3 + "%" } })) : null;
    return h("a.bi-kpi" + (k.bad && k.v ? ".bad" : ""), { href: "#", on: { click: e => { e.preventDefault(); openReport(app, k.go); } } },
      h("div.k", null, k.k), h("div.v", null, val, " ", h("small", null, k.unit === "%" || k.unit === "pcs" ? "" : k.unit)),
      k.plan !== undefined && k.plan !== null ? h("div.s", null, `Plan ${k.unit === "%" ? fmt(k.plan, "pct") : fmt(k.plan, "amt")}` + (k.ach !== undefined && k.ach !== null ? ` · ${fmt(k.ach, "pct")}` : "")) : null, ach);
  }));
  shell(app, h("div.bi-content", null, h("h2.bi-cat", null, `Executive Summary - ${d.year} / ${String(d.period).padStart(2, "0")}`), tiles,
    h("div.panel", null, h("h2", null, "Net sales: actual vs plan, operating profit (by month)"), h("div.panel-body", null, chart(d)))));
}
function chart(d) {
  const W = 760, H = 240, P = 40, n = d.months.length || 1;
  const all = [].concat(d.trend.net_actual, d.trend.net_plan, d.trend.op_actual).filter(v => typeof v === "number");
  const max = Math.max(1, ...all), min = Math.min(0, ...all);
  const y = v => H - P - (v - min) / (max - min) * (H - 2 * P), x = i => P + 30 + i * ((W - 2 * P - 30) / Math.max(n - 1, 1));
  const NS = "http://www.w3.org/2000/svg";
  const el = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const s = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "bi-chart" });
  s.append(el("line", { x1: P + 20, x2: W - P, y1: y(0), y2: y(0), class: "ax" }));
  const bw = (W - 2 * P) / n / 3;
  (d.trend.op_actual || []).forEach((v, i) => s.append(el("rect", { x: x(i) - bw / 2, y: Math.min(y(v), y(0)), width: bw, height: Math.abs(y(v) - y(0)), class: v < 0 ? "bar neg" : "bar" })));
  const line = (vals, cls) => { const pts = vals.map((v, i) => `${x(i)},${y(v || 0)}`).join(" "); s.append(el("polyline", { points: pts, class: cls })); vals.forEach((v, i) => s.append(el("circle", { cx: x(i), cy: y(v || 0), r: 3.5, class: cls }))); };
  if (d.trend.net_plan.length) line(d.trend.net_plan, "plan");
  line(d.trend.net_actual, "act");
  d.months.forEach((m, i) => { const t = el("text", { x: x(i), y: H - 12, "text-anchor": "middle", class: "lbl" }); t.textContent = m; s.append(t); });
  [["act", "Net sales actual"], ["plan", "Net sales plan"], ["bar", "Operating profit"]].forEach(([c, t], i) => {
    s.append(el("rect", { x: W - 190, y: 10 + i * 18, width: 12, height: 10, class: c + " lg" }));
    const tx = el("text", { x: W - 172, y: 19 + i * 18, class: "lbl" }); tx.textContent = t; s.append(tx);
  });
  return s;
}

// ------------------------------------------------------------------ status dashboards (charts + table)
async function statusBoard(app, tab) {
  const q = tab.query;
  const qs = new URLSearchParams({ year: q.year || "", period: q.period || "", currency: q.currency || App.dispCur(), scale: q.scale || "1" });
  let d = null;
  try { d = await api(`/api/bi/dashboard/${q.dashboard}?${qs}`); } catch (e) { App.err(e); }
  app.innerHTML = "";
  const year = h("input.f.w-s", { value: q.year || (d && d.year) || "" }), per = h("input.f.w-s", { value: q.period || (d && d.period) || "" });
  const cur = h("select.f", null, [["EGP", "Egyptian pound"], ["USD", "US Dollar"], ["EUR", "Euro"]].map(([k, t]) => h("option", { value: k, selected: (q.currency || App.dispCur()) === k }, t)));
  const sc = h("select.f", null, [["1", "1"], ["1000", "1,000"], ["1000000", "1,000,000"]].map(([k, t]) => h("option", { value: k, selected: (q.scale || "1") === k }, t)));
  const apply = () => { q.year = year.value; q.period = per.value; q.currency = App.dispCur(cur.value); q.scale = sc.value; draw(app); };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: apply },
    d && d.drill ? { label: "Detail report", onClick: () => openReport(app, d.drill) } : null,
    { label: "Excel", onClick: () => d && boardExcel(tab, d) }, { label: "Print", onClick: () => window.print() }]);
  const vars = h("div.bd-vars", null,
    h("div.bd-var", null, h("span", null, "{ }"), h("div", null, h("small", null, "Fiscal year / period"), h("span", null, year, " / ", per))),
    h("div.bd-var", null, h("span", null, "{ }"), h("div", null, h("small", null, "Display currency"), cur)),
    h("div.bd-var", null, h("span", null, "{ }"), h("div", null, h("small", null, "Amount scaling"), sc)),
    h("button.btn.primary", { type: "button", on: { click: apply } }, "Apply"));
  if (!d) return shell(app, h("div.bi-content", null, vars));
  const charts = h("div.bd-charts", null, d.widgets.map(w => h("div.bd-card", null, h("h3", null, w.title), combo(w))));
  const t = d.table, groups = [];
  t.columns.forEach(c => { const g = c.group || ""; const last = groups[groups.length - 1]; if (last && last.g === g) last.n++; else groups.push({ g, n: 1 }); });
  const fmtv = (v, type, kind) => v === null || v === undefined ? "" : (type === "pct" || kind === "pct") ? NF1.format(v) + "%" : (Math.abs(v) < 1 && v !== 0 ? (v > 0 ? "+0" : "-0") : NF0.format(v));
  const table = h("table.bd-table", null,
    h("thead", null, h("tr", null, h("th", null, ""), t.columns.map((c, i) => h("th" + ((groups.findIndex((g, gi) => groups.slice(0, gi).reduce((a, x) => a + x.n, 0) === i) % 2) ? ".alt" : ""), null, c.label)))),
    h("tbody", null, t.rows.map(r => h("tr" + (r.bold ? ".b" : ""), null, h("td.lbl", null, r.label),
      r.values.map((v, i) => h("td" + (typeof v === "number" && v < 0 ? ".neg" : "") + (t.columns[i].type === "pct" ? ".ach" : ""), null, fmtv(v, t.columns[i].type, r.kind)))))));
  shell(app, h("div.bi-content.bd", null, vars, h("div.bd-note", null, d.note), charts,
    h("div.bd-tw", null, h("div.bd-tt", null, t.title), h("div.bi-scroll", null, table))));
}
function boardExcel(tab, d) {
  const t = d.table;
  App.exportRows({ title: tab.title, columns: [{ key: "l", label: "" }].concat(t.columns.map((c, i) => ({ key: "c" + i, label: c.label }))) },
    t.rows.map(r => { const o = { l: r.label }; r.values.forEach((v, i) => { o["c" + i] = v; }); return o; }));
}
function combo(w) {
  const W = 420, H = 230, L = 34, R = 44, T = 34, Bm = 34;
  const NS = "http://www.w3.org/2000/svg";
  const el = (t, a, txt) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (txt !== undefined) e.textContent = txt; return e; };
  const s = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "bd-svg" });
  const bars = w.bars[0].values.map(v => v || 0), line = w.line.values;
  const bmax = Math.max(1, ...bars), bmin = Math.min(0, ...bars);
  const lv = line.filter(v => typeof v === "number"), lmax = Math.max(1, ...lv), lmin = Math.min(0, ...lv);
  const n = w.categories.length || 1, step = (W - L - R) / n, bw = Math.min(60, step * 0.62);
  const band = (H - T - Bm) * 0.55;          // the % line floats in the upper part, above the bars
  const yb = v => T + 14 + (bmax - v) / (bmax - bmin) * (H - T - Bm - 14), yl = v => T + 10 + (lmax - v) / ((lmax - lmin) || 1) * band;
  const cx = i => L + step * i + step / 2;
  // legend
  s.append(el("rect", { x: W / 2 - 110, y: 6, width: 12, height: 10, class: "b" }), el("text", { x: W / 2 - 94, y: 15, class: "lg" }, w.bars[0].name),
    el("line", { x1: W / 2 + 6, x2: W / 2 + 24, y1: 11, y2: 11, class: "l" }), el("circle", { cx: W / 2 + 15, cy: 11, r: 3, class: "l" }),
    el("text", { x: W / 2 + 28, y: 15, class: "lg" }, w.line.name));
  s.append(el("line", { x1: L, x2: W - R, y1: yb(0), y2: yb(0), class: "ax" }));
  [bmin, (bmax + bmin) / 2, bmax].forEach(v => s.append(el("text", { x: L - 4, y: yb(v) + 4, class: "tk", "text-anchor": "end" }, short(v))));
  [lmin, lmax].forEach(v => s.append(el("text", { x: W - R + 6, y: yl(v) + 4, class: "tk" }, NF1.format(v) + "%")));
  const cut = n > 6 ? 8 : n > 4 ? 11 : 18;
  bars.forEach((v, i) => {
    s.append(el("rect", { x: cx(i) - bw / 2, y: Math.min(yb(v), yb(0)), width: bw, height: Math.max(1, Math.abs(yb(v) - yb(0))), class: "b" + (v < 0 ? " neg" : "") }));
    s.append(el("text", { x: cx(i), y: Math.min(yb(v), yb(0)) - 4, class: "dl", "text-anchor": "middle" }, short(v)));
    s.append(el("text", { x: cx(i), y: H - 12, class: "ct", "text-anchor": "middle" }, String(w.categories[i]).slice(0, cut)));
  });
  const pts = line.map((v, i) => typeof v === "number" ? [cx(i), yl(v), v] : null).filter(Boolean);
  if (pts.length > 1) s.append(el("polyline", { points: pts.map(p => p[0] + "," + p[1]).join(" "), class: "l" }));
  pts.forEach(p => { s.append(el("circle", { cx: p[0], cy: p[1], r: 4, class: "l" })); s.append(el("text", { x: p[0] + 6, y: p[1] - 7, class: "pl", "text-anchor": "start" }, NF1.format(p[2]) + "%")); });
  return s;
}
function short(v) {
  const a = Math.abs(v);
  return a >= 1e9 ? NF1.format(v / 1e9) + "B" : a >= 1e6 ? NF1.format(v / 1e6) + "M" : a >= 1e4 ? NF0.format(v / 1e3) + "K" : NF0.format(v);
}

register("ZDASH", { title: "ERP Dashboard", async render(app) {
  const open = () => window.open("/dashboard.html", "mmcore_dashboard", "width=1560,height=960");
  toolbar([{ label: "Open in its own window", primary: true, onClick: open }, { label: "Refresh", key: "F8", onClick: () => { fr.src = "/dashboard.html"; } }]);
  const fr = h("iframe", { src: "/dashboard.html", title: "ERP Dashboard", style: { width: "100%", height: "calc(100vh - 150px)", border: "0", borderRadius: "8px", background: "#eef2f7" } });
  app.append(fr);
} });

register("ZBI_DASH", { title: "BI Dashboard - PL Status", async render(app, params) {
  go("ZBI", { id: params.id || "DB_PL_STATUS" });
} });

register("ZBI", { title: "BI (Business Intelligence)", async render(app, params) {
  await run(() => catalog(true));
  if (!B.catalog) return;
  if (!B.cat) B.cat = "Controlling";
  if (params.id) { B.active = -1; return openReport(app, params.id); }
  draw(app);
} });
})();
