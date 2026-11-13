/* NERP Mobile - the ERP dashboard on the phone, updated live (Server-Sent Events).
   Plain JavaScript; reads /m/api/stream of the NERP Mobile gateway on the PC. */
"use strict";
(() => {
  const $ = s => document.querySelector(s);
  const app = $("#app");
  const IN_APP = / NERPApp\//.test(navigator.userAgent);     // the Android app "NERP"
  let CUR = "EGP", es = null, last = null, prev = {}, pollTimer = null;
  try { CUR = localStorage.getItem("mm_m_cur") || "EGP"; } catch (e) { /* private mode */ }
  $("#cur").value = CUR;

  // ---------------------------------------------------------------- helpers
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v; else if (k === "on") Object.entries(v).forEach(([e, f]) => el.addEventListener(e, f));
      else el.setAttribute(k, v);
    }
    for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k instanceof Node ? k : String(k));
    return el;
  }
  const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
  function short(v) {
    if (v === null || v === undefined) return "-";
    const a = Math.abs(v);
    if (a >= 1e9) return nf1.format(v / 1e9) + "B";
    if (a >= 1e6) return nf1.format(v / 1e6) + "M";
    if (a >= 1e4) return nf1.format(v / 1e3) + "K";
    return nf0.format(v);
  }
  const money = v => short(v) + " " + CUR;
  const pct = v => v === null || v === undefined ? "-" : nf1.format(v) + "%";
  const cls = v => (v || 0) < 0 ? "neg" : "pos";
  function kpi(id, label, value, sub, c) {
    return h("div", { class: "kpi", "data-id": id }, h("div", { class: "l" }, label), h("div", { class: "v " + (c || "") }, value), sub ? h("div", { class: "s" }, sub) : null);
  }
  const row = (id, label, value, c) => h("div", { class: "row", "data-id": id }, h("span", null, label), h("b", { class: c || "" }, value));
  const card = (icon, color, title, ...body) => h("section", { class: "card" }, h("h3", null, h("i", { "data-c": color }, icon), title), ...body);
  function bar(p, color) {
    const s = h("span"); s.style.width = Math.max(0, Math.min(100, p || 0)) + "%"; if (color) s.style.background = color;
    return h("div", { class: "bar" }, s);
  }
  function hbars(items) {
    const max = Math.max(1, ...items.map(x => Math.abs(x.value || 0)));
    return items.map(x => { const s = h("span"); s.style.width = (Math.abs(x.value || 0) * 100 / max) + "%";
      return h("div", { class: "hb" }, h("span", { class: "n" }, x.name), h("span", { class: "b" }, s), h("b", null, short(x.value))); });
  }
  function spark(values, color) {
    const NS = "http://www.w3.org/2000/svg", W = 300, H = 64, v = values.length ? values : [0];
    const mx = Math.max(...v, 0), mn = Math.min(...v, 0), rng = (mx - mn) || 1;
    const pts = v.map((x, i) => [v.length > 1 ? i * W / (v.length - 1) : W / 2, H - 4 - (x - mn) * (H - 10) / rng]);
    const svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("class", "spark");
    const area = document.createElementNS(NS, "path");
    area.setAttribute("d", `M0,${H} ` + pts.map(p => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ") + ` L${W},${H} Z`);
    area.setAttribute("fill", color); area.setAttribute("opacity", "0.15");
    const line = document.createElementNS(NS, "polyline");
    line.setAttribute("points", pts.map(p => p.map(n => n.toFixed(1)).join(",")).join(" "));
    line.setAttribute("fill", "none"); line.setAttribute("stroke", color); line.setAttribute("stroke-width", "2.5"); line.setAttribute("vector-effect", "non-scaling-stroke");
    svg.append(area, line);
    return svg;
  }
  const COLORS = { blue: "#0a6ed1", green: "#19875a", orange: "#e9730c", violet: "#7655d6", red: "#c8343b", teal: "#0f8c8c", grey: "#5b6b7f" };

  // ---------------------------------------------------------------- render
  function render(d) {
    const F = d.finance, P = d.profit, Pr = d.production, Q = d.quality, W = d.warehouse, Pu = d.procurement,
      S = d.sales, Co = d.controlling, Hr = d.hr, A = d.analytics;
    const view = h("div", null,
      h("div", { class: "kpis" },
        kpi("s_month", "Sales this month", money(S.month), `${S.open_orders} open order${S.open_orders === 1 ? "" : "s"}`),
        kpi("ns_ytd", "Net sales YTD", money(F.income_ytd), `plan ${pct(F.income_ach)}`),
        kpi("op_ytd", "Operating profit YTD", money(A.op_ytd), `margin ${pct(P.margin_pct)}`, cls(A.op_ytd)),
        kpi("bank", "Bank", money(F.bank), `AR ${short(F.receivables)} · AP ${short(F.payables)}`)),
      card("↗", "blue", "Sales trend",
        spark(S.trend || [], COLORS.blue),
        h("div", { class: "chips" }, (d.months || []).map((m, i) => i === 0 || i === d.months.length - 1 ? h("span", { class: "chip" }, m) : null)),
        row("backlog", "Order backlog", money(S.backlog)), row("blocked", "Credit blocked orders", S.blocked, S.blocked ? "neg" : ""),
        row("margin", "Sales margin YTD", pct(S.margin_pct)), row("cust", "Customers YTD", S.customers)),
      card("$", "green", "Finance",
        row("ar", "Receivables", money(F.receivables)), row("od", "Overdue", money(F.overdue), F.overdue ? "neg" : ""),
        row("ap", "Payables", money(F.payables)), row("ni", "Net income YTD", money(P.net), cls(P.net)),
        row("gm", "Gross margin", pct(A.gm_pct)), row("ms", "Net sales this month / last year", `${short(A.month_sales)} / ${short(A.prev_year)}`)),
      card("⚙", "orange", "Production",
        bar(Pr.on_track, COLORS.green), row("ontrack", "On track", pct(Pr.on_track)),
        row("ord", "Orders done / running / late", `${Pr.done} / ${Pr.running} / ${Pr.late}`, Pr.late ? "neg" : ""),
        row("yield", "Yield (quality)", pct(Q.yield_pct)), row("scrap", "Scrap quantity", nf1.format(Q.scrap))),
      card("▦", "violet", "Warehouse",
        row("stock", "Stock value", money(W.value)), row("reorder", "Below reorder point", W.below_reorder, W.below_reorder ? "neg" : ""),
        row("old", "Older than 180 days", money(W.old_stock)), row("qb", "Quality / blocked", money(W.q_blocked)),
        hbars((W.groups || []).slice(0, 5))),
      card("🛒", "teal", "Procurement",
        row("spend", "Spend YTD", money(Pu.spend_ytd)), row("open", "Open purchase orders", money(Pu.open_value)),
        row("rel", "Waiting for release", Pu.waiting_release, Pu.waiting_release ? "neg" : ""),
        row("chg", "This month vs last month", pct(Pu.change))),
      card("◎", "blue", "Cost centers (plan vs actual YTD)",
        bar(Co.ach, (Co.ach || 0) > 100 ? COLORS.red : COLORS.orange), row("coach", "Used", pct(Co.ach), (Co.ach || 0) > 100 ? "neg" : ""),
        (Co.centers || []).map(c => row("cc" + c.name, c.name, `${short(c.actual)} / ${short(c.plan)}`))),
      card("👥", "grey", "Human resources",
        row("hc", "Headcount", Hr.headcount), row("leave", "On leave today", Hr.on_leave),
        row("req", "Open leave requests", Hr.open_requests, Hr.open_requests ? "neg" : ""),
        row("hrcost", `Payroll cost ${Hr.last_period}`, money(Hr.cost_last))),
      card("✓", "red", `Open tasks (${(d.tasks || []).length})`,
        (d.tasks || []).length ? d.tasks.map(t => h("div", { class: "task" }, h("div", { class: "t" }, t.typ), t.text)) : h("div", { class: "mut" }, "Nothing waiting")),
      card("🧾", "green", "Latest invoices",
        (P.invoices || []).map(i => row("inv" + i.no, `${i.no} · ${i.customer}`, `${short(i.amount)} · ${i.date}`))));
    // highlight what changed since the last update
    const now = {};
    view.querySelectorAll("[data-id]").forEach(el => { now[el.dataset.id] = el.textContent; if (last && prev[el.dataset.id] !== undefined && prev[el.dataset.id] !== el.textContent) el.classList.add("flash"); });
    view.querySelectorAll("[data-c]").forEach(el => { el.style.background = COLORS[el.dataset.c] || COLORS.blue; });
    prev = now;
    app.replaceChildren(view);
    last = d;
    $("#foot").replaceChildren(`Period ${d.period} · business date ${d.date} · ${d.currency_note || "amounts in EGP"} · update ${d.server_time}`,
      IN_APP ? h("div", null, h("a", { href: "nerp://rescan", class: "rescan" }, "Connect to another PC (scan a new QR code)")) : null);
  }

  function status(state, text) {
    $("#live").className = "live " + state;
    $("#liveText").textContent = text;
  }
  function notPaired(text) {
    if (es) { es.close(); es = null; }
    status("off", "Not paired");
    app.replaceChildren(h("div", { class: "msg" }, h("h2", null, "Pair this phone"),
      text || "On the PC: start 'NERP Mobile' and scan the QR code with this phone's camera.",
      IN_APP ? h("div", null, h("a", { href: "nerp://rescan", class: "btn" }, "Scan the QR code")) : null));
  }

  // ---------------------------------------------------------------- connection
  async function pairFromLink() {
    const m = location.hash.match(/k=([A-Za-z0-9_-]{20,})/);
    if (!m) return;
    history.replaceState(null, "", location.pathname);           // the key does not stay in the address bar
    try {
      const r = await fetch("/m/api/pair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: m[1] }) });
      if (!r.ok) notPaired((await r.json()).text);
    } catch (e) { status("off", "No connection"); }
  }
  async function loadOnce() {
    const r = await fetch("/m/api/overview?currency=" + CUR, { cache: "no-store" });
    if (r.status === 401 || r.status === 429) { notPaired((await r.json()).text); return false; }
    if (!r.ok) throw new Error((await r.json()).text);
    render(await r.json());
    return true;
  }
  function connect() {
    if (es) es.close();
    if (!window.EventSource) { poll(); return; }
    es = new EventSource("/m/api/stream?currency=" + CUR);
    es.addEventListener("dashboard", ev => { try { render(JSON.parse(ev.data)); status("on", "Live · " + new Date().toLocaleTimeString()); } catch (e) { status("off", "Data error"); } });
    es.onopen = () => status("on", "Live");
    es.onerror = () => { status("off", "Reconnecting…"); };                // EventSource retries by itself
  }
  function poll() {
    clearTimeout(pollTimer);
    loadOnce().then(ok => { if (ok) status("on", "Updated " + new Date().toLocaleTimeString()); pollTimer = setTimeout(poll, 10000); })
      .catch(() => { status("off", "No connection"); pollTimer = setTimeout(poll, 5000); });
  }
  async function start() {
    await pairFromLink();
    try { if (!await loadOnce()) return; } catch (e) { status("off", "No connection to the PC"); app.replaceChildren(h("div", { class: "msg" }, h("h2", null, "No connection"),
      "Is the PC on, NERP Mobile running and this phone in the same Wi-Fi?", h("br"), h("button", { class: "btn", on: { click: start } }, "Try again"))); return; }
    connect();
  }
  $("#cur").addEventListener("change", () => {
    CUR = $("#cur").value;
    try { localStorage.setItem("mm_m_cur", CUR); } catch (e) { /* private mode */ }
    prev = {}; last = null; connect();
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && (!es || es.readyState === 2)) start(); });
  start();
})();
