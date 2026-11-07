/* MM Core - Inventory Cockpit (dashboard) */
"use strict";
(() => {
const { h, api, msg, run, alv, register, go, toolbar, fmtQty, fmtAmt, fmtShort, fmtDate, S } = App;
const NS = "http://www.w3.org/2000/svg";
const svgEl = (w, hgt, inner) => { const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", `0 0 ${w} ${hgt}`); s.style.width = "100%"; s.innerHTML = inner; return s; };
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

register("ZMM_COCKPIT", { title: "Inventory Cockpit", async render(app) {
  const d = await api("/api/dashboard");
  const cur = d.currency, k = d.kpi;
  toolbar([{ label: "Refresh", key: "F8", onClick: () => App.render() },
    { label: "⇩ Excel", ghost: true, onClick: () => exportAll(d) },
    { label: "✉ Send by Outlook", ghost: true, onClick: () => outlook(d) },
    { label: "Print", ghost: true, onClick: () => window.print() }]);

  const kpi = (label, value, sub, goTo, cls) => h("div.kpi", { dataset: goTo ? { go: goTo } : null,
    on: goTo ? { click: () => location.hash = "#/" + goTo } : null },
    h("div.k", null, label), h("div.v" + (cls ? "." + cls : ""), null, value), sub ? h("div.s", null, sub) : null);
  app.append(h("div.kpis", null,
    kpi("Total stock value", h("span", null, fmtShort(k.total_value), " ", h("small", null, cur)), `${fmtAmt(k.total_value)} ${cur}`, "MB52"),
    kpi("Unrestricted", h("span", null, fmtShort(k.unrestricted_value), " ", h("small", null, cur)),
      `${(k.unrestricted_value / (k.total_value || 1) * 100).toFixed(1)} % of value`, "MB52"),
    kpi("In quality inspection", h("span", null, fmtShort(k.quality_value), " ", h("small", null, cur)), "Waiting for QC release (321)", "MB52", k.quality_value ? "crit" : ""),
    kpi("Blocked stock", h("span", null, fmtShort(k.blocked_value), " ", h("small", null, cur)), "Damaged / on hold", "MB52", k.blocked_value ? "neg" : ""),
    kpi("Below reorder point", String(k.below_reorder), "Material / plant combinations", null, k.below_reorder ? "neg" : ""),
    kpi("Material documents", String(k.docs_period), `last 30 days · ${k.docs_today} today`, "MB51"),
    kpi("Open PO items", String(k.open_po_items), "Still to be delivered", "ME2M"),
    kpi("Bin occupancy", `${k.bins_used} / ${k.bins_total}`, `${Math.round(k.bins_used / (k.bins_total || 1) * 100)} % of bins in use`, "LX03")));

  const card = (title, sub, ...body) => h("div.card", null, h("h3", null, title), sub ? h("div.sub", null, sub) : null, h("div.body", null, ...body));
  const hbars = (items, labelFn, valueFn, onClick, fmt) => {
    fmt = fmt || fmtShort;
    const max = Math.max(...items.map(valueFn), 1);
    return h("div", null, items.map(it => h("div.hbar", { style: onClick ? { cursor: "pointer" } : null, on: onClick ? { click: () => onClick(it) } : null },
      h("span.lbl", { title: labelFn(it) }, labelFn(it)), h("span.track", null, h("span.fill", { style: { width: (valueFn(it) / max * 100) + "%", display: "block" } })),
      h("span.num", null, fmt(valueFn(it))))));
  };

  // stock value by storage location
  const c1 = card("Stock value by storage location", cur, hbars(d.by_sloc, s => `${s.werks}/${s.lgort} ${s.name}`, s => s.value,
    s => go("MB52", { werks: s.werks, lgort: s.lgort })));

  // goods flow chart (receipts up, issues down)
  const flow = d.flow, W = 560, H = 200, P = { l: 46, r: 6, t: 10, b: 24 };
  const mx = Math.max(...flow.map(f => Math.max(f.in, f.out)), 1);
  const bw = (W - P.l - P.r) / flow.length, mid = P.t + (H - P.t - P.b) / 2, sc = (H - P.t - P.b) / 2 / mx;
  let inner = `<line x1="${P.l}" x2="${W - P.r}" y1="${mid}" y2="${mid}" stroke="#89919a"/>` +
    `<text x="${P.l - 6}" y="${P.t + 8}" font-size="10" text-anchor="end" fill="#6a6d70">+${esc(fmtShort(mx))}</text>` +
    `<text x="${P.l - 6}" y="${H - P.b}" font-size="10" text-anchor="end" fill="#6a6d70">−${esc(fmtShort(mx))}</text>`;
  flow.forEach((f, i) => {
    const x = P.l + i * bw + 1, w = Math.max(bw - 2, 1);
    if (f.in) inner += `<rect x="${x}" y="${mid - f.in * sc}" width="${w}" height="${f.in * sc}" fill="#107e3e"><title>${esc(fmtDate(f.date))} receipts ${esc(fmtAmt(f.in))}</title></rect>`;
    if (f.out) inner += `<rect x="${x}" y="${mid}" width="${w}" height="${f.out * sc}" fill="#e9730c"><title>${esc(fmtDate(f.date))} issues ${esc(fmtAmt(f.out))}</title></rect>`;
    if (i % 7 === 0) inner += `<text x="${x + w / 2}" y="${H - 6}" font-size="10" text-anchor="middle" fill="#6a6d70">${esc(fmtDate(f.date).slice(0, 5))}</text>`;
  });
  const totIn = flow.reduce((a, f) => a + f.in, 0), totOut = flow.reduce((a, f) => a + f.out, 0);
  const c2 = card("Goods flow - last 30 days (value)", `Receipts ${fmtAmt(totIn)} · Issues ${fmtAmt(totOut)} ${cur}`,
    h("div.legend", null, h("span", null, h("i", { style: { background: "#107e3e" } }), "Receipts"), h("span", null, h("i", { style: { background: "#e9730c" } }), "Issues")),
    svgEl(W, H, inner));

  // stock aging (by goods receipt date of the quants)
  const ag = d.aging, maxA = Math.max(...ag.map(a => a.value), 1), AW = 420, AH = 190;
  let ai = "";
  const colors = ["#0a6ed1", "#5899da", "#e9730c", "#bb0000"];
  ag.forEach((a, i) => {
    const bwA = (AW - 40) / ag.length, x = 20 + i * bwA + 14, hh = a.value / maxA * (AH - 50);
    ai += `<rect x="${x}" y="${AH - 30 - hh}" width="${bwA - 28}" height="${hh}" fill="${colors[i]}" rx="2"><title>${esc(fmtAmt(a.value))}</title></rect>` +
      `<text x="${x + (bwA - 28) / 2}" y="${AH - 34 - hh}" font-size="11" text-anchor="middle" fill="#32363a">${esc(fmtShort(a.value))}</text>` +
      `<text x="${x + (bwA - 28) / 2}" y="${AH - 12}" font-size="11" text-anchor="middle" fill="#6a6d70">${esc(a.bucket)} days</text>`;
  });
  const old = ag.slice(2).reduce((a, b) => a + b.value, 0);
  const c3 = card("Stock aging (FIFO goods receipt date)", `${(old / (k.total_value || 1) * 100).toFixed(1)} % of value older than 90 days`,
    svgEl(AW, AH, ai), h("a", { href: "#/LX02" }, "Show quants with GR dates (LX02) →"));

  // top materials
  const c4 = card("Top materials by stock value", null, alv({ compact: true, rows: d.top_materials, columns: [
    { key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) }, { key: "maktx", label: "Description" },
    { key: "werks", label: "Plnt" }, { key: "qty", label: "Stock", type: "qty" }, { key: "meins", label: "BUn" },
    { key: "price", label: "Price", type: "amt" }, { key: "vprsv", label: "Pr." },
    { key: "value", label: "Value", type: "amt" }] }));

  // reorder alerts
  const c5 = card("Below reorder point", "Unrestricted stock ≤ reorder point", d.below_reorder.length ? alv({ compact: true, rows: d.below_reorder,
    columns: [{ key: "matnr", label: "Material", link: r => go("MMBE", { id: r.matnr }) }, { key: "maktx", label: "Description" },
      { key: "werks", label: "Plnt" }, { key: "stock", label: "Stock", type: "qty", cls: r => r.critical ? "neg" : "crit" },
      { key: "minbe", label: "Reorder pt", type: "qty" }, { key: "eisbe", label: "Safety", type: "qty" }, { key: "meins", label: "BUn" },
      { key: "st", label: "Status", render: r => r.critical ? h("span.badge.B", null, "Below safety") : h("span.badge.Q", null, "Reorder") },
      { key: "po", label: "", render: () => h("a", { href: "#/ME21N" }, "Create PO") }] }) : h("p.pos", null, "✔ All materials above reorder point"));

  // movement types
  const c6 = card("Movements by type - last 30 days", "Number of document items", hbars(d.by_bwart.slice(0, 10),
    b => `${b.bwart} ${b.text}`, b => b.count, b => go("MB51", { bwart: b.bwart }), String));

  // recent docs
  const c7 = card("Latest material documents", null, alv({ compact: true, rows: d.recent, columns: [
    { key: "mblnr", label: "Mat. Doc.", link: r => go("MB03", { id: r.mblnr, year: r.mjahr }) },
    { key: "budat", label: "Date", type: "date" }, { key: "bwart", label: "MvT" }, { key: "bwart_text", label: "Movement" },
    { key: "matnr", label: "Material" }, { key: "menge", label: "Qty", type: "qty" }, { key: "meins", label: "EUn" },
    { key: "usnam", label: "User" }] }));
  app.append(h("div.cards", null, c2, c1, c3, c5, c4, c6, c7));
  msg("S", `Cockpit refreshed · stock value ${fmtAmt(k.total_value)} ${cur}`);
}});

function exportAll(d) {
  App.exportRows({ exportName: "Inventory_cockpit", columns: [
    { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "werks", label: "Plant" },
    { key: "stock", label: "Unrestricted stock" }, { key: "minbe", label: "Reorder point" },
    { key: "eisbe", label: "Safety stock" }, { key: "meins", label: "Unit" }] }, d.below_reorder);
}

async function outlook(d) {
  if (!S.meta.com.available) return msg("E", "Outlook uses Office COM and needs Windows: " + S.meta.com.reason, "COM", "001");
  const r = await App.ask("Send cockpit summary by Outlook", [{ name: "to", label: "To", placeholder: "name@company.com" }]);
  if (!r) return;
  const k = d.kpi, cur = d.currency;
  const rows = d.below_reorder.map(b => `<tr><td>${esc(b.matnr)}</td><td>${esc(b.maktx)}</td><td>${esc(b.werks)}</td>` +
    `<td align="right">${esc(fmtQty(b.stock))} ${esc(b.meins)}</td><td align="right">${esc(fmtQty(b.minbe))}</td></tr>`).join("");
  const html = `<div style="font-family:Arial;font-size:13px"><h3>Inventory cockpit - ${esc(fmtDate(S.meta.today))}</h3>` +
    `<p>Total stock value: <b>${esc(fmtAmt(k.total_value))} ${cur}</b><br>Quality inspection: ${esc(fmtAmt(k.quality_value))} ${cur}` +
    `<br>Blocked: ${esc(fmtAmt(k.blocked_value))} ${cur}<br>Open PO items: ${k.open_po_items}</p>` +
    (rows ? `<p><b>Below reorder point (${d.below_reorder.length})</b></p><table border="1" cellpadding="4" cellspacing="0" ` +
      `style="border-collapse:collapse;font-size:12px"><tr><th>Material</th><th>Description</th><th>Plant</th><th>Stock</th>` +
      `<th>Reorder pt</th></tr>${rows}</table>` : "") + `<p style="color:#888">Created by MM Core</p></div>`;
  const res = await run(() => api("/api/office/outlook-draft", { to: r.to, subject: `Inventory cockpit ${fmtDate(S.meta.today)}`, html }));
  if (res) msg("S", res.message);
}
})();
