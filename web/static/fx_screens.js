/* NERP - ZFX: exchange rates of all currencies - latest rate, change and age, search, bulk entry,
   history chart, currency converter (cross rates through EGP), currencies used without a rate. */
"use strict";
(() => {
const { h, api, msg, run, ask, field, inp, sel, val, alv, register, toolbar, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const num = (v, d) => v === null || v === undefined ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d ?? 2, maximumFractionDigits: d ?? 5 });

function chart(rows) {
  if (rows.length < 2) return note("Not enough history for a chart.");
  const W = 720, H = 200, p = 34, v = rows.map(r => r.rate), mx = Math.max(...v), mn = Math.min(...v), rg = (mx - mn) || 1;
  const x = i => p + i * (W - 2 * p) / (rows.length - 1), y = r => H - p - (r - mn) / rg * (H - 2 * p);
  const pts = rows.map((r, i) => `${x(i)},${y(r.rate)}`).join(" ");
  const lab = rows.map((r, i) => (i === 0 || i === rows.length - 1 || i % Math.ceil(rows.length / 6) === 0) ?
    `<text x="${x(i)}" y="${H - 8}" font-size="10" text-anchor="middle" fill="#5d6b7c">${r.gdatu.slice(5)}</text>` : "").join("");
  return h("div", { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:820px"><polyline fill="none" stroke="#1f5fae" stroke-width="2" points="${pts}"/>` +
    rows.map((r, i) => `<circle cx="${x(i)}" cy="${y(r.rate)}" r="3" fill="#1f5fae"><title>${r.gdatu}: ${r.rate}</title></circle>`).join("") +
    `<text x="4" y="${y(mx) + 4}" font-size="10" fill="#5d6b7c">${mx}</text><text x="4" y="${y(mn) + 4}" font-size="10" fill="#5d6b7c">${mn}</text>${lab}</svg>` });
}

register("ZFX", { title: "Exchange Rates - All Currencies", async render(app, params) {
  const dt = inp({ type: "date", value: params.day || today() }), q = inp({ w: "m", ph: "search: code or name (e.g. riyal, ريال)" });
  const all = sel([["0", "Shown currencies"], ["1", "All incl. hidden"]], "0");
  const out = h("div"), conv = h("div"), hist = h("div");
  app.append(panel(null, grid(field("Rates valid on", dt), field("Search", q), field("List", all))), out);
  let data = null;
  const draw = () => {
    if (!data) return;
    const s = val(q).toLowerCase();
    const rows = data.rows.filter(r => !s || r.waers.toLowerCase().includes(s) || r.ltext.toLowerCase().includes(s) || (r.ltext_ar || "").includes(val(q)));
    out.querySelector(".fx-list").replaceChildren(alv({ rows, title: `Currencies (${rows.length})`, rowClass: r => r.stale ? ".neg" : "", columns: [
      { key: "waers", label: "Code" }, { key: "ltext", label: "Currency" }, { key: "ltext_ar", label: "العملة" },
      { key: "factor", label: "Per", render: r => r.factor === 1 ? "1" : String(r.factor) },
      { key: "rate", label: "EGP", render: r => r.rate === null ? h("span", { style: { color: "#9aa8b8" } }, "no rate") : h("b", null, num(r.rate, 2)) },
      { key: "change_pct", label: "Change %", render: r => r.change_pct === null ? "" : h("span", { style: { color: r.change_pct > 0 ? "#b3261e" : r.change_pct < 0 ? "#11713e" : "" } },
        (r.change_pct > 0 ? "▲ +" : r.change_pct < 0 ? "▼ " : "") + r.change_pct) },
      { key: "previous", label: "Previous", render: r => num(r.previous, 2) }, { key: "per_egp", label: "Per 1 EGP", render: r => num(r.per_egp, 4) },
      { key: "gdatu", label: "Valid from", type: "date" }, { key: "age_days", label: "Age (days)", render: r => r.age_days === null ? "" : (r.stale ? badge(r.age_days + " old", "B") : String(r.age_days)) },
      { key: "x", label: "", render: r => h("span", null, btn("Rate", () => enter(r)), " ", btn("History", () => showHistory(r.waers)), " ",
        btn(r.active ? "Hide" : "Show", async () => { const x = await run(() => api("/api/fi/fx/active", { waers: r.waers, active: !r.active })); if (x) { msg("S", x.message); load(); } })) }] }));
  };
  const enter = async r => {
    const x = await ask(`${r.waers} - ${r.ltext}: EGP per ${r.factor} ${r.waers}`, [{ name: "rate", label: `Rate (EGP per ${r.factor})`, value: r.rate ?? "" }, { name: "gdatu", label: "Valid from", value: dt.value }]); if (!x) return;
    const res = await run(() => api("/api/fi/fx/rate", { waers: r.waers, gdatu: x.gdatu, rate: x.rate })); if (res) { msg("S", res.message); load(); }
  };
  const showHistory = async w => {
    const d = await run(() => api("/api/fi/fx/history?waers=" + w)); if (!d) return;
    hist.replaceChildren(panel(`${d.waers} - ${d.ltext}: EGP per ${d.factor} (last ${d.rows.length} rates)`,
      h("div.kpis", null, kpi("Lowest", num(d.min, 2)), kpi("Highest", num(d.max, 2)), kpi("Change", d.change_pct === null ? "-" : d.change_pct + " %", "", d.change_pct > 0 ? "neg" : "pos")),
      chart(d.rows), alv({ rows: d.rows.slice().reverse(), compact: true, title: "Rates", columns: [{ key: "gdatu", label: "Valid from", type: "date" }, { key: "rate", label: "EGP" }] })));
    hist.scrollIntoView({ behavior: "smooth" });
  };
  const amt = inp({ w: "s", value: "1000" }), from = inp({ w: "s", value: "USD", upper: true }), to = inp({ w: "s", value: "EGP", upper: true }), res = h("div.kpi");
  const doConv = async () => { const r = await run(() => api(`/api/fi/fx/convert?amount=${encodeURIComponent(val(amt))}&from=${val(from)}&to=${val(to)}&day=${dt.value}`)); if (!r) return;
    res.replaceChildren(h("div.k", null, "Result"), h("div.v", null, `${num(r.result, 2)} ${r.to}`), h("div.s", null, r.text)); };
  conv.append(panel("Currency converter (cross rate through EGP)", grid(field("Amount", amt), field("From", from), field("To", to)), btn("Convert", doConv), " ",
    btn("⇄ Swap", () => { const t = from.value; from.value = to.value; to.value = t; doConv(); }), h("div.kpis", null, res)));
  async function load() {
    data = await run(() => api(`/api/fi/fx?day=${dt.value}&all=${all.value}`)); if (!data) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Currencies", String(data.total), "ISO 4217 + gold / silver"), kpi("With a rate", String(data.with_rate)),
      kpi("Older than " + data.stale_days + " days", String(data.stale), "update them", data.stale ? "neg" : "pos"),
      kpi("Used without a rate", String(data.missing.length), data.missing.map(m => m.waers).join(", ") || "none", data.missing.length ? "neg" : "pos")),
      conv, h("div.fx-list"), hist,
      note("Rates are EGP per 1 unit (type M, average). Weak currencies are quoted per 100 or 1,000 units, like the banks (e.g. 100 JPY). Postings use the rate valid on the posting date; OB08 maintains the same rates."));
    draw();
  }
  q.addEventListener("input", draw);
  dt.addEventListener("change", load); all.addEventListener("change", load);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load },
    { label: "Enter many rates", onClick: async () => {
      const x = await ask("Paste rates: CODE rate, CODE rate ... (e.g. USD 49.85, SAR 13.27, JPY 33.1 per 100)", [{ name: "text", label: "Rates", value: "" }, { name: "gdatu", label: "Valid from", value: dt.value }]); if (!x) return;
      const r = await run(() => api("/api/fi/fx/rates", { text: x.text, gdatu: x.gdatu })); if (!r) return;
      msg(r.errors.length ? "W" : "S", r.message + (r.errors.length ? ": " + r.errors.map(e => `${e.text} (${e.error})`).join("; ") : "")); load(); } }]);
  load();
} });
})();
