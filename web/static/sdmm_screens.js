/* NERP - Sales and Warehouse in depth: rebate agreements (ZREB01, ZREB02, ZREB_ACR, ZREB03),
   quotation follow-up (ZSD_QFU), sales configuration and month-end (ZSD_CONF, ZSD_CLOSE), stock
   aging (ZMM_AGING), ABC analysis (ZMM_ABC), range of coverage (ZMM_COVER), warehouse
   configuration and month-end (ZMM_CONF, ZMM_CLOSE). */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, field, inp, val, up, alv, register, go, toolbar, fmtAmt, fmtQty, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not used", ""] };

function closeScreen(code, title, url, noteText, other) {
  register(code, { title, async render(app, params) {
    const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
    app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
    const load = async () => {
      const d = await run(() => api(`${url}?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
      out.innerHTML = "";
      out.append(h("div.kpis", null, kpi("Steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
        alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Month-end - in this order",
          columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode) },
            { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }), note(noteText));
    };
    toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, ...other]);
    load();
  } });
}
closeScreen("ZSD_CLOSE", "Sales - Closing Management", "/api/sd/close_mgmt", "Finish sales first (everything shipped is billed and posted, e-invoices submitted, rebates accrued), then the warehouse (ZMM_CLOSE) and Accounting (ZFI_CLOSE).",
  [{ label: "Warehouse closing (ZMM_CLOSE)", onClick: () => go("ZMM_CLOSE") }]);
closeScreen("ZMM_CLOSE", "Warehouse - Closing Management", "/api/wm/close_mgmt", "Close the materials period (MMPV) last, after all receipts, issues and counts of the month are posted.",
  [{ label: "FI closing (ZFI_CLOSE)", onClick: () => go("ZFI_CLOSE") }]);

// ------------------------------------------------------------------ ZSD_CONF
register("ZSD_CONF", { title: "Sales - Basic Configuration (display)", async render(app) {
  const c = await run(() => api("/api/sd/config")); if (!c) return;
  const cr = c.credit;
  app.append(h("div.kpis", null, kpi("Credit control area", cr.area, cr.text), kpi("Overdue limit", `${cr.oldest_days} days`, "older open items block new orders"),
    kpi("Warranty", `${c.warranty_months} months`, "from the goods issue")),
    alv({ rows: c.doc_types, title: "Sales document types (VOV8)", columns: [{ key: "auart", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.item_cats, title: "Item categories", columns: [{ key: "pstyv", label: "Category" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.billing_types, title: "Billing types", columns: [{ key: "fkart", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.conditions, title: "Condition types (V/06)", columns: [{ key: "kschl", label: "Condition" }, { key: "text", label: "Description" }, { key: "kind", label: "Class" },
      { key: "calc", label: "Calc." }, { key: "access", label: "Access sequence" }] }),
    alv({ rows: c.procedures, title: "Pricing procedures (V/08)", columns: [{ key: "kalsm", label: "Procedure" }, { key: "text", label: "Steps" }] }),
    alv({ rows: c.risk, title: "Risk categories", columns: [{ key: "ctlpc", label: "Category" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.blocks, title: "Blocks", columns: [{ key: "code", label: "Block" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.reasons, title: "Order reasons", columns: [{ key: "augru", label: "Reason" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.shipping_points, title: "Shipping points", columns: [{ key: "vstel", label: "Shipping point" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.accounts, title: "Accounts used by sales", columns: [{ key: "use", label: "Use" }, { key: "hkont", label: "G/L account" }] }));
} });

// ------------------------------------------------------------------ rebates
register("ZREB01", { title: "Create Rebate Agreement", async render(app, params) {
  const y = now().y;
  const f = { kunnr: inp({ value: params.id || "", w: "m", upper: true, list: "dl-kunnr" }), datab: inp({ type: "date", value: `${y}-01-01` }),
    datbi: inp({ type: "date", value: `${y}-12-31` }), text: inp({ w: "l", ph: "e.g. Distributor agreement 2026" }) };
  const tiers = [0, 1, 2, 3].map(() => ({ t: inp({ w: "m", ph: "sales from (EGP)" }), p: inp({ w: "s", ph: "%" }) }));
  app.append(panel("Agreement", grid(field("Customer", f.kunnr, { req: true }), field("Valid from", f.datab), field("Valid to", f.datbi), field("Description", f.text))),
    panel("Targets (scale)", h("table.grid", null, h("thead", null, h("tr", null, h("th", null, "Tier"), h("th", null, "Net sales from (EGP)"), h("th", null, "Rebate %"))),
      h("tbody", null, tiers.map((x, i) => h("tr", null, h("td", null, String(i + 1)), h("td", null, x.t), h("td", null, x.p)))))),
    note("The reached tier applies to all sales of the period. Example: from 1,000,000 → 2 %, from 2,000,000 → 3.5 %. Credit memos reduce the sales. The rebate is accrued every month (ZREB_ACR) and credited to the customer at the end (ZREB03)."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/sd/rebate/create", { kunnr: up(f.kunnr), datab: f.datab.value, datbi: f.datbi.value, text: val(f.text),
      scale: tiers.map(x => [val(x.t), val(x.p)]).filter(x => x[0] && x[1]) }));
    if (r) { msg("S", r.message); go("ZREB02"); } } }]);
} });

register("ZREB02", { title: "Rebate Agreements - Status", async render(app) {
  const f = { kunnr: inp({ w: "m", upper: true, list: "dl-kunnr" }), upto: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("Customer", f.kunnr), field("Sales up to", f.upto))), out);
  const load = async () => {
    const d = await run(() => api(`/api/sd/rebate?kunnr=${up(f.kunnr)}&upto=${f.upto.value}`)); if (!d) return;
    out.innerHTML = "";
    const act = d.rows.filter(r => r.status === "A");
    out.append(h("div.kpis", null, kpi("Active agreements", act.length), kpi("Rebate earned", fmtAmt(act.reduce((a, r) => a + r.earned, 0)), "EGP"),
      kpi("Not yet accrued", fmtAmt(act.reduce((a, r) => a + r.to_accrue, 0)), "run ZREB_ACR", act.some(r => r.to_accrue) ? "neg" : "pos")),
      alv({ rows: d.rows, title: "Agreements", emptyText: "No rebate agreements - create one with ZREB01", columns: [{ key: "knuma", label: "Agreement" },
        { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "datab", label: "From", type: "date" }, { key: "datbi", label: "To", type: "date" },
        { key: "basis", label: "Sales so far", type: "amt", sum: true }, { key: "rate", label: "Tier %" }, { key: "earned", label: "Earned", type: "amt", sum: true },
        { key: "next", label: "Next tier", render: r => r.next ? `${fmtAmt(r.next.missing)} more → ${r.next.rate} %` : "top tier" },
        { key: "accrued", label: "Accrued", type: "amt", sum: true }, { key: "settled", label: "Settled", type: "amt", sum: true },
        { key: "status_text", label: "Status", render: r => badge(r.status_text, r.status === "A" ? "Q" : "U") },
        { key: "x", label: "", render: r => r.status === "A" ? h("button.btn", { type: "button", on: { click: () => go("ZREB03", { id: r.knuma }) } }, "Settle") : (r.set_belnr || "") }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Create", onClick: () => go("ZREB01") }, { label: "Monthly accrual", onClick: () => go("ZREB_ACR") }]);
  load();
} });

register("ZREB_ACR", { title: "Rebate Accrual (monthly)", async render(app) {
  const f = { budat: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("Posting date (month end)", f.budat))), note("Posts the rebate earned so far minus what is already accrued: Dr 881000 customer rebates / Cr 291000 accrued customer rebates. Run it at every month end."), out);
  const exec = async act => {
    const r = await run(() => api("/api/sd/rebate/" + act, { budat: f.budat.value })); if (!r) return;
    msg("S", r.message); out.innerHTML = "";
    out.append(alv({ rows: r.rows, title: r.test ? "Test run - nothing posted" : "Posted", emptyText: "Nothing to accrue", columns: [{ key: "knuma", label: "Agreement" },
      { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "basis", label: "Sales", type: "amt" }, { key: "earned", label: "Earned", type: "amt" },
      { key: "amount", label: "Accrued now", type: "amt", sum: true }, { key: "belnr", label: "FI document" }] }));
  };
  toolbar([{ label: "Test run", key: "F8", onClick: () => exec("test") }, { label: "Post", primary: true, onClick: () => exec("accrue") }]);
} });

register("ZREB03", { title: "Settle Rebate Agreement", async render(app, params) {
  const f = { knuma: inp({ value: params.id || "", w: "m" }), budat: inp({ type: "date", value: today() }) };
  app.append(panel(null, grid(field("Agreement", f.knuma, { req: true }), field("Posting date", f.budat))),
    note("After the end of the agreement: the earned rebate is credited to the customer (open item, can be paid out or cleared against invoices) and the accrual is cleared."));
  toolbar([{ label: "Settle", primary: true, onClick: async () => {
    if (!await confirmBox("Settle", `Settle rebate agreement ${val(f.knuma)} and credit the customer?`)) return;
    const r = await run(() => api("/api/sd/rebate/settle", { knuma: val(f.knuma), budat: f.budat.value })); if (r) { msg("S", r.message); go("ZREB02"); } } }]);
} });

// ------------------------------------------------------------------ ZSD_QFU
register("ZSD_QFU", { title: "Quotation Follow-up", async render(app) {
  const f = { kd: inp({ type: "date", value: today() }) }, out = h("div");
  const SB = { Open: "Q", Won: "U", "Partly won": "U", Expired: "B", Rejected: "" };
  app.append(panel(null, grid(field("Key date", f.kd))), out);
  const load = async () => {
    const d = await run(() => api(`/api/sd/quotations?key_date=${f.kd.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Quoted", fmtAmt(d.total), `${d.rows.length} quotation(s)`), kpi("Won (ordered)", fmtAmt(d.won), d.hit_rate == null ? "" : `hit rate ${d.hit_rate} %`, "pos"),
      kpi("Open", d.open), kpi("Call the customer", d.follow_up, "open, valid 7 days or less", d.follow_up ? "neg" : "pos")),
      alv({ rows: d.rows, title: "Quotations", rowClass: r => r.follow_up ? ".neg" : "", columns: [{ key: "vbeln", label: "Quotation", link: r => go("VA23", { id: r.vbeln }) },
        { key: "kunnr", label: "Customer" }, { key: "name", label: "Name" }, { key: "audat", label: "Date", type: "date" }, { key: "bnddt", label: "Valid to", type: "date" },
        { key: "days_left", label: "Days left", type: "int" }, { key: "netwr", label: "Value", type: "amt", sum: true }, { key: "ordered", label: "Ordered", type: "amt", sum: true },
        { key: "conversion", label: "Converted %" }, { key: "status", label: "Status", render: r => badge(r.status, SB[r.status]) },
        { key: "x", label: "", render: r => r.status === "Open" ? h("button.btn", { type: "button", on: { click: () => go("VA01", { ref: r.vbeln }) } }, "Create order") : "" }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }, { label: "Create quotation", onClick: () => go("VA21") }]);
  load();
} });

// ------------------------------------------------------------------ warehouse
register("ZMM_CONF", { title: "Warehouse - Basic Configuration (display)", async render(app) {
  const c = await run(() => api("/api/wm/config")); if (!c) return;
  app.append(h("div.kpis", null, kpi("Plants", c.plants.length), kpi("Storage locations", c.slocs.length), kpi("MM period", c.period ? `${String(c.period.perio).padStart(2, "0")}/${c.period.gjahr}` : "not used"),
    kpi("ABC split", `A ${c.abc_limits.A} % · B ${c.abc_limits.B} % · C ${c.abc_limits.C} %`, "of the consumption value")),
    alv({ rows: c.plants, title: "Plants (OX10)", columns: [{ key: "werks", label: "Plant" }, { key: "name", label: "Name" }, { key: "city", label: "City" }] }),
    alv({ rows: c.slocs, title: "Storage locations (OX09)", columns: [{ key: "werks", label: "Plant" }, { key: "lgort", label: "SLoc" }, { key: "name", label: "Name" },
      { key: "bin_managed", label: "Bins managed", render: r => r.bin_managed ? "yes" : "no" }, { key: "bins", label: "Bins", type: "int" }] }),
    alv({ rows: c.cycle_days, title: "Cycle counting interval by ABC class (MICN)", columns: [{ key: "abc", label: "Class" }, { key: "days", label: "Count every ... days", type: "int" }] }),
    alv({ rows: c.stock_types, title: "Stock types", columns: [{ key: "insmk", label: "Type" }, { key: "text", label: "Description" }] }),
    alv({ rows: c.movement_types, title: "Movement types (OMJJ)", columns: [{ key: "bwart", label: "Mvt" }, { key: "text", label: "Description" }, { key: "kind", label: "Kind" }, { key: "value", label: "Value from" }] }));
} });

register("ZMM_AGING", { title: "Stock Aging (by goods receipt date)", async render(app) {
  const f = { kd: inp({ type: "date", value: today() }), werks: inp({ w: "s", value: "" , ph: "all" }) }, out = h("div");
  app.append(panel(null, grid(field("Key date", f.kd), field("Plant", f.werks))), out);
  const load = async () => {
    const d = await run(() => api(`/api/wm/aging?key_date=${f.kd.value}&werks=${val(f.werks)}`)); if (!d) return;
    out.innerHTML = "";
    const t = d.total;
    out.append(h("div.kpis", null, kpi("Stock value", fmtAmt(t.value), "EGP"), ...d.buckets.map(b => kpi(`${b.text} days`, fmtAmt(t[b.key]),
      t.value ? (t[b.key] * 100 / t.value).toFixed(1) + " %" : "", ["d365", "old"].includes(b.key) && t[b.key] ? "neg" : ""))),
      alv({ rows: d.rows, title: "Stock by age (value EGP)", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "werks", label: "Plant" },
        { key: "qty", label: "Qty", type: "qty" }, { key: "meins", label: "Unit" }, { key: "value", label: "Value", type: "amt", sum: true },
        ...d.buckets.map(b => ({ key: b.key, label: b.text, type: "amt", sum: true })), { key: "oldest", label: "Oldest receipt", type: "date" }, { key: "age_days", label: "Age (days)", type: "int" }] }),
      note("Old stock ties up cash and may become obsolete - sell, use or scrap it (MIGO 551)."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

register("ZMM_ABC", { title: "ABC Analysis (consumption value)", async render(app) {
  const f = { werks: inp({ w: "s", value: "1000" }), kd: inp({ type: "date", value: today() }) }, out = h("div");
  app.append(panel(null, grid(field("Plant", f.werks), field("Up to", f.kd))), out);
  const load = async () => {
    const d = await run(() => api(`/api/wm/abc?werks=${val(f.werks)}&key_date=${f.kd.value}`)); if (!d) return;
    out.innerHTML = "";
    const s = d.summary;
    out.append(h("div.kpis", null, ...["A", "B", "C"].map(k => kpi(`Class ${k}`, `${s[k].count} material(s)`, `${fmtAmt(s[k].value)} EGP`))),
      alv({ rows: d.rows, title: `Consumption ${d.d1} to ${d.d2}`, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
        { key: "qty", label: "Consumed qty", type: "qty" }, { key: "value", label: "Consumption value", type: "amt", sum: true }, { key: "share", label: "Share %" },
        { key: "cum", label: "Cumulative %" }, { key: "abc", label: "ABC", render: r => badge(r.abc, r.abc === "A" ? "B" : r.abc === "B" ? "Q" : "") },
        { key: "current", label: "Saved", render: r => r.current || "-" }, { key: "changed", label: "", render: r => r.changed ? badge("changed", "Q") : "" }] }),
      d.idle.length ? alv({ rows: d.idle, title: "In stock but not consumed (class C)", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" }, { key: "current", label: "Saved" }] }) : h("div"),
      note("A = the few materials that make 80 % of the value: count them every 30 days and watch them closely. Save the result to use it in cycle counting (MICN)."));
  };
  toolbar([{ label: "Analyse", key: "F8", primary: true, onClick: load }, { label: "Save ABC indicators", onClick: async () => {
    if (!await confirmBox("ABC", "Save the ABC class as indicator of the materials (changes the cycle counting interval)?")) return;
    const r = await run(() => api("/api/wm/abc/save", { werks: val(f.werks), key_date: f.kd.value })); if (r) { msg("S", r.message); load(); } } },
    { label: "Cycle counting (MICN)", onClick: () => go("MICN") }]);
  load();
} });

register("ZMM_COVER", { title: "Range of Coverage (days of stock)", async render(app) {
  const f = { werks: inp({ w: "s", value: "1000" }), kd: inp({ type: "date", value: today() }), days: inp({ w: "s", value: "90" }) }, out = h("div");
  const FL = { short: ["< 14 days", "B"], high: ["> 180 days", "Q"], "no use": ["not used", ""], ok: ["OK", "U"] };
  app.append(panel(null, grid(field("Plant", f.werks), field("Key date", f.kd), field("Average over days", f.days))), out);
  const load = async () => {
    const d = await run(() => api(`/api/wm/coverage?werks=${val(f.werks)}&key_date=${f.kd.value}&days=${val(f.days)}`)); if (!d) return;
    out.innerHTML = "";
    const cnt = k => d.rows.filter(r => r.flag === k).length;
    out.append(h("div.kpis", null, kpi("Short (< 14 days)", cnt("short"), "order now", cnt("short") ? "neg" : "pos"), kpi("Too much (> 180 days)", cnt("high"), "stop ordering"),
      kpi("Not used", cnt("no use"), `no consumption in ${d.days} days`), kpi("OK", cnt("ok"))),
      alv({ rows: d.rows, title: `Unrestricted stock / average daily use ${d.d1} to ${d.d2}`, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
        { key: "stock", label: "Stock", type: "qty" }, { key: "meins", label: "Unit" }, { key: "used", label: `Used in ${d.days} d`, type: "qty" }, { key: "per_day", label: "Per day" },
        { key: "cover_days", label: "Days of stock", render: r => r.cover_days == null ? "∞" : fmtQty(r.cover_days) }, { key: "value", label: "Value", type: "amt", sum: true },
        { key: "flag", label: "Status", render: r => badge(FL[r.flag][0], FL[r.flag][1]) }] }));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });
})();
