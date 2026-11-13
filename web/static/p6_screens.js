/* NERP - go-live functions: physical inventory (MI01..MI07, MICN), MM periods
   (MMPV, MMRV), MB5B, print forms (ZPRINT), data import (ZIMPORT), withholding
   tax (ZWHT, ZWHT_RPT), manual clearing (F-44, F-32, F-03), down payments
   (F-47, F-37, F-48, F-29, F-54, F-39) */
"use strict";
(() => {
const { h, api, msg, run, register, go, toolbar, field, inp, sel, val, up, alv, today, dialog, confirmBox } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);

// ------------------------------------------------------------------ print helper (also used by other screens)
async function printForm(form, key) {
  const r = await run(() => api(`/api/forms/${form}/${encodeURIComponent(key)}`)); if (!r) return;
  const w = window.open("", "_blank");
  if (!w) return msg("E", "The browser blocked the print window - allow pop-ups for this page");
  w.document.open(); w.document.write(r.html); w.document.close();
  setTimeout(() => { try { w.focus(); w.print(); } catch (e) {} }, 400);
  await run(() => api("/api/forms/log", { form, key, medium: "PRINT" }));
}
App.printForm = printForm;

// ------------------------------------------------------------------ MI01 create
register("MI01", { title: "Create Physical Inventory Document", async render(app) {
  const f = { werks: inp({ value: "1000", list: "dl-plant", w: "s", upper: true }), lgort: inp({ value: "0001", w: "s", upper: true }),
    date: inp({ type: "date", value: today(), w: "m" }), mats: inp({ w: "l", ph: "empty = all materials with stock" }),
    freeze: h("input", { type: "checkbox", checked: true }) };
  app.append(panel("Header", grid(field("Plant", f.werks, { req: true }), field("Storage location", f.lgort, { req: true }),
    field("Planned count date", f.date), field("Materials", f.mats), field("Posting block (freeze book qty)", f.freeze))),
    note("With the posting block every goods movement of these materials in the storage location is refused (M7 140) until the count is posted (MI07) or the document is deleted."));
  toolbar([{ label: "Create", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/mi/create", { werks: up(f.werks), lgort: up(f.lgort), date: f.date.value, matnrs: up(f.mats), freeze: f.freeze.checked }));
    if (r) { msg("S", r.message, "M7", "710", true); go("MI04", { id: r.iblnr }); } } }]);
} });

function docKey(params, then) {
  const k = inp({ value: params.id || "", w: "m" });
  return [k, () => { const v = val(k); if (!v) { msg("E", "Enter the physical inventory document", "M7", "141"); return; } then(v); }];
}
const invCols = [{ key: "zeili", label: "Item", type: "int" }, { key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
  { key: "lgpla", label: "Bin" }, { key: "insmk", label: "Stock type" }];

// ------------------------------------------------------------------ MI03 display / MI11 recount
register("MI03", { title: "Display Physical Inventory Document", async render(app, params) {
  const out = h("div");
  let cur = null, selected = new Set();
  const load = async id => {
    const d = await run(() => api("/api/mi/doc/" + encodeURIComponent(id))); if (!d) return;
    cur = d; selected = new Set(); out.innerHTML = "";
    out.append(panel(`Document ${d.iblnr} - ${d.status_text}`, grid(field("Plant / sloc", h("span", null, `${d.werks} / ${d.lgort}`)),
      field("Planned", h("span", null, App.fmtDate(d.plan_date))), field("Counted", h("span", null, App.fmtDate(d.count_date || ""))),
      field("Posting block", h("span", null, d.freeze ? "yes" : "no")), field("Material doc.", h("span", null, d.mblnr || "-")))),
      alv({ rows: d.items, title: "Items (select a line for recount)", onRow: r => { selected.has(r.zeili) ? selected.delete(r.zeili) : selected.add(r.zeili); msg("I", `Selected for recount: ${[...selected].join(", ") || "-"}`); },
        columns: invCols.concat([{ key: "buchm_o", label: "Book qty", type: "qty" }, { key: "menge_o", label: "Counted", type: "qty" },
          { key: "diff_o", label: "Difference", type: "qty", signed: true }, { key: "counted_by", label: "Counted by" },
          { key: "recount", label: "Recounted", render: r => h("span", null, r.recount ? "yes" : "") }]) }));
  };
  const [k, exec] = docKey(params, load);
  app.append(panel(null, grid(field("Phys. inventory doc.", k, { req: true }))), out);
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: exec },
    { label: "Recount selected (MI11)", onClick: async () => {
      if (!cur || !selected.size) return msg("E", "Select the items to recount", "M7", "147");
      const r = await run(() => api("/api/mi/recount", { iblnr: cur.iblnr, zeilis: [...selected] }));
      if (r) { msg("S", r.message); go("MI04", { id: r.iblnr }); } } },
    { label: "Count sheet", onClick: () => cur ? printForm("COUNT", cur.iblnr) : exec() },
    { label: "Delete", danger: true, onClick: async () => {
      if (!cur || !await confirmBox("Delete document", `Delete ${cur.iblnr} and remove the posting block?`)) return;
      const r = await run(() => api("/api/mi/delete", { iblnr: cur.iblnr })); if (r) { msg("S", r.message); load(cur.iblnr); } } }]);
  if (params.id) exec();
} });
register("MI11", { title: "Recount Physical Inventory Document", async render() { msg("I", "Select the items in MI03 and press 'Recount selected'"); go("MI03"); } });

// ------------------------------------------------------------------ MI04 enter count
register("MI04", { title: "Enter Inventory Count", async render(app, params) {
  const out = h("div");
  let cur = null;
  const ins = {};
  const load = async id => {
    const d = await run(() => api("/api/mi/doc/" + encodeURIComponent(id))); if (!d) return;
    cur = d; out.innerHTML = "";
    const tb = h("tbody");
    d.items.filter(i => !i.recount).forEach(i => {
      const q = inp({ value: i.menge_o === null ? "" : i.menge_o, w: "s" }), z = h("input", { type: "checkbox", checked: !!i.xnull });
      ins[i.zeili] = { q, z };
      tb.append(h("tr", null, h("td", null, String(i.zeili)), h("td", null, i.matnr), h("td", null, i.maktx), h("td", null, i.lgpla),
        h("td", null, i.insmk), h("td", null, i.meins), h("td", null, q), h("td", null, z)));
    });
    out.append(panel(`Document ${d.iblnr} - ${d.status_text} (${d.werks}/${d.lgort})`,
      h("table.grid", null, h("thead", null, h("tr", null, ["Item", "Material", "Description", "Bin", "Stock type", "Unit", "Counted quantity", "Zero"].map(t => h("th", null, t)))), tb),
      note("Blind count: the book quantity is not shown. Tick 'Zero' when the bin is empty.")));
  };
  const [k, exec] = docKey(params, load);
  app.append(panel(null, grid(field("Phys. inventory doc.", k, { req: true }))), out);
  toolbar([{ label: "Display", key: "F8", onClick: exec }, { label: "Save count", key: "Ctrl+S", primary: true, onClick: async () => {
    if (!cur) return exec();
    const items = Object.entries(ins).map(([z, x]) => ({ zeili: +z, qty: val(x.q), zero: x.z.checked }));
    const r = await run(() => api("/api/mi/count", { iblnr: cur.iblnr, items })); if (r) { msg("S", r.message); load(cur.iblnr); } } },
    { label: "Difference list (MI20)", onClick: () => cur && go("MI20", { id: cur.iblnr }) }]);
  if (params.id) exec();
} });

// ------------------------------------------------------------------ MI20 differences / MI07 post
function diffScreen(post) {
  return async (app, params) => {
    const out = h("div"), th = inp({ value: "1000", w: "s" });
    let cur = null;
    const load = async id => {
      const d = await run(() => api(`/api/mi/doc/${encodeURIComponent(id)}?diff=1&threshold=${val(th) || 0}`)); if (!d) return;
      cur = d; out.innerHTML = "";
      out.append(h("div.kpis", null, h("div.kpi", null, h("div.k", null, "Status"), h("div.v", null, d.status_text)),
        h("div.kpi", null, h("div.k", null, "Difference value"), h("div.v" + (d.total < 0 ? ".neg" : ""), null, App.fmtAmt(d.total_o)))),
        alv({ rows: d.items.filter(i => !i.recount), title: "Book vs count", rowClass: r => r.big ? ".neg" : "",
          columns: invCols.concat([{ key: "buchm_o", label: "Book", type: "qty" }, { key: "menge_o", label: "Counted", type: "qty" },
            { key: "diff_o", label: "Difference", type: "qty", signed: true }, { key: "diff_value_o", label: "Value", type: "amt", sum: true, signed: true }]) }));
    };
    const [k, exec] = docKey(params, load);
    const reason = inp({ w: "l" }), budat = inp({ type: "date", value: today(), w: "m" });
    app.append(panel(null, grid(field("Phys. inventory doc.", k, { req: true }), field("Highlight from (EGP)", th),
      post ? field("Posting date", budat) : null, post ? field("Reason", reason) : null)), out);
    const btns = [{ label: "Display", key: "F8", primary: !post, onClick: exec }];
    if (post) btns.push({ label: "Post differences", key: "Ctrl+S", primary: true, onClick: async () => {
      if (!cur) return exec();
      if (!await confirmBox("Post differences", `Post the differences of ${cur.iblnr} (value ${App.fmtAmt(cur.total_o)}) with 701 / 702?`)) return;
      const r = await run(() => api("/api/mi/post", { iblnr: cur.iblnr, budat: budat.value, reason: val(reason) }));
      if (r) { msg("S", r.message); load(cur.iblnr); } } });
    else btns.push({ label: "Post (MI07)", onClick: () => cur && go("MI07", { id: cur.iblnr }) });
    toolbar(btns);
    if (params.id) exec();
  };
}
register("MI20", { title: "List of Inventory Differences", render: diffScreen(false) });
register("MI07", { title: "Post Inventory Differences", render: diffScreen(true) });

// ------------------------------------------------------------------ MICN cycle counting
register("MICN", { title: "Cycle Counting - Proposal", async render(app) {
  const werks = inp({ value: "1000", w: "s", list: "dl-plant" }), out = h("div");
  app.append(panel(null, grid(field("Plant", werks)), note("ABC indicator in the material (MRP view, default C): A every 30 days, B 90, C 180.")), out);
  let rows = [];
  const exec = async () => {
    rows = (await run(() => api("/api/mi/cycle?werks=" + encodeURIComponent(up(werks))))) || []; out.innerHTML = "";
    out.append(alv({ rows, title: "Materials due for counting", columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
      { key: "lgort", label: "Sloc" }, { key: "abc", label: "ABC" }, { key: "qty", label: "Stock", type: "qty" }, { key: "last", label: "Last count", type: "date" },
      { key: "due", label: "Due", type: "date" }] }));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }, { label: "Create documents", onClick: async () => {
    const by = {}; rows.forEach(r => { (by[r.lgort] = by[r.lgort] || []).push(r.matnr); });
    for (const [lg, mats] of Object.entries(by)) {
      const r = await run(() => api("/api/mi/create", { werks: up(werks), lgort: lg, matnrs: mats }));
      if (r) msg("S", r.message);
    }
    exec(); } }]);
  exec();
} });

// ------------------------------------------------------------------ MMPV / MMRV / MB5B
register("MMPV", { title: "Close Period - MM (open next period)", async render(app) {
  const out = h("div"); app.append(out);
  const load = async () => {
    const r = await run(() => api("/api/mmpv")); if (!r) return; out.innerHTML = "";
    const c = r.current, t = today();
    const ny = c ? (c.perio === 12 ? c.gjahr + 1 : c.gjahr) : +t.slice(0, 4), np = c ? (c.perio % 12) + 1 : +t.slice(5, 7);
    const y = inp({ value: ny, w: "s" }), p = inp({ value: np, w: "s" }), prev = h("input", { type: "checkbox", checked: true });
    out.append(panel("MM periods (company code 1000)", grid(field("Current period", h("b", null, c ? `${c.perio} / ${c.gjahr}` : "not active - every date can be posted")),
      field("Previous period open", h("span", null, c ? (c.prev_open ? "yes" : "no") : "-")),
      field("Open period", h("span.split", null, p, "/", y)), field("Allow postings in previous period", prev)),
      note("Goods movements are possible in the current and (optionally) the previous period only (M7 053). The stock at the end of a closed period is kept (MBEWH).")),
      alv({ rows: r.history, title: "Stock history (MBEWH)", columns: [{ key: "gjahr", label: "Year", type: "int" }, { key: "perio", label: "Period", type: "int" },
        { key: "matnr", label: "Material" }, { key: "bwkey", label: "Plant" }, { key: "lbkum", label: "Quantity", render: x => h("span", null, App.fmtQty(x.lbkum / 1000)) },
        { key: "salk3", label: "Value", render: x => h("span", null, App.fmtAmt(x.salk3 / 100)) }] }));
    toolbar([{ label: "Open period", key: "Ctrl+S", primary: true, onClick: async () => {
      const x = await run(() => api("/api/mmpv", { gjahr: val(y), perio: val(p), prev_open: prev.checked })); if (x) { msg("S", x.message); load(); } } },
      { label: "Close previous period (MMRV)", onClick: async () => { const x = await run(() => api("/api/mmrv", {})); if (x) { msg("S", x.message); load(); } } }]);
  };
  load();
} });
register("MMRV", { title: "Allow Posting to Previous Period", async render() { go("MMPV"); } });

register("MB5B", { title: "Stock on Posting Date", async render(app) {
  const f = { werks: inp({ value: "1000", w: "s", list: "dl-plant" }), date: inp({ type: "date", value: today(), w: "m" }), matnr: inp({ w: "m", upper: true }) };
  const out = h("div");
  app.append(panel(null, grid(field("Plant", f.werks), field("Key date", f.date), field("Material", f.matnr)),
    note("Quantity from all material documents up to the key date; value from the stock accounts (incl. price changes and invoice differences).")), out);
  const exec = async () => {
    const q = new URLSearchParams({ werks: up(f.werks), date: f.date.value, matnr: up(f.matnr) });
    const rows = await run(() => api("/api/mb5b?" + q)); if (!rows) return; out.innerHTML = "";
    out.append(alv({ rows, title: `Stock on ${App.fmtDate(f.date.value)}`, columns: [{ key: "matnr", label: "Material" }, { key: "maktx", label: "Description" },
      { key: "qty", label: "Quantity", type: "qty" }, { key: "meins", label: "Unit" }, { key: "value", label: "Value", type: "amt", sum: true }] }));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]);
  exec();
} });

// ------------------------------------------------------------------ ZPRINT
register("ZPRINT", { title: "Print Forms and Output Log", async render(app, params) {
  const meta = await run(() => api("/api/forms")); if (!meta) return;
  const form = sel(Object.entries(meta.forms), params.form || "PO", { w: "l" }), key = inp({ value: params.id || "", w: "m" });
  const prev = h("iframe.form-preview", { title: "Preview" }), log = h("div");
  app.append(panel(null, grid(field("Form", form), field("Document", key, { req: true })),
    note("PO: order no. · RFQ: RFQ no. · DELIVERY: delivery · INVOICE: billing doc. · DUNNING: run-customer (1-C1002) · PAYADVICE: document-year · COUNT: phys. inv. doc. · PRODORDER: order")),
    prev, log);
  const show = async () => {
    if (!val(key)) return msg("E", "Enter the document number", "VN", "003");
    const r = await run(() => api(`/api/forms/${form.value}/${encodeURIComponent(val(key))}`)); if (!r) return;
    prev.srcdoc = r.html;
    log.innerHTML = "";
    log.append(alv({ rows: r.outputs, title: "Output log (message status)", columns: [{ key: "ts", label: "Time" }, { key: "medium", label: "Medium" }, { key: "usnam", label: "User" }],
      emptyText: "Not output yet" }));
  };
  toolbar([{ label: "Preview", key: "F8", primary: true, onClick: show },
    { label: "Print", onClick: async () => { if (val(key)) { await printForm(form.value, val(key)); show(); } } },
    { label: "Mark as e-mailed", onClick: async () => { const r = await run(() => api("/api/forms/log", { form: form.value, key: val(key), medium: "EMAIL" })); if (r) { msg("S", r.message); show(); } } }]);
  if (params.id) show();
} });

// ------------------------------------------------------------------ ZIMPORT
register("ZIMPORT", { title: "Data Import for Go-Live", async render(app) {
  const m = await run(() => api("/api/import/objects")); if (!m) return;
  const obj = sel([["ALL", "Excel workbook - all sheets (in the right order)"]].concat(m.objects.map(o => [o.obj, `${o.order}. ${o.text}`])), "ALL", { w: "l" });
  const file = h("input", { type: "file", accept: ".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const text = h("textarea.f", { rows: 6, spellcheck: "false", style: { width: "100%", fontFamily: "monospace" } });
  const cols = h("code"), out = h("div"), fname = h("b");
  let xlsx = null;                                   // base64 of the chosen Excel file
  const showCols = () => {
    const o = m.objects.find(x => x.obj === obj.value);
    cols.textContent = o ? `${o.columns}  (Excel sheet "${o.sheet}")` : "every NERP sheet of the workbook, e.g. 01 Plants ... 08 Open purchase orders";
  };
  obj.addEventListener("change", showCols); showCols();
  file.addEventListener("change", () => {
    const f = file.files[0]; if (!f) return;
    const rd = new FileReader();
    fname.textContent = f.name;
    if (/\.xlsx$/i.test(f.name)) {
      rd.onload = () => { const b = new Uint8Array(rd.result); let s = ""; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
        xlsx = btoa(s); text.value = ""; text.placeholder = `Excel file ${f.name} (${Math.round(f.size / 1024)} KB) - ready`; };
      rd.readAsArrayBuffer(f);
    } else { xlsx = null; rd.onload = () => { text.value = rd.result; }; rd.readAsText(f, "utf-8"); }
  });
  const download = async example => {
    const r = await run(() => api("/api/import/workbook/PUR" + (example ? "?example=1" : ""))); if (!r) return;
    const bin = atob(r.xlsx), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const a = h("a", { href: URL.createObjectURL(new Blob([u8], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })), download: r.name });
    document.body.append(a); a.click(); a.remove(); msg("S", `${r.name} downloaded - fill it in Excel and choose it here`);
  };
  app.append(panel("1. Excel template", h("div", null,
      h("button.btn", { type: "button", on: { click: () => download(false) } }, "⇩ Purchasing template (empty, for your data)"), " ",
      h("button.btn", { type: "button", on: { click: () => download(true) } }, "⇩ Purchasing example (sample data, for the sandbox)")),
    note("The workbook has a guide in Arabic (sheet '00 Start here'), one sheet per data type with dropdown lists, and a 'Control' sheet with the counts and the open order value to compare.")),
    panel("2. File", grid(field("Object (load in this order)", obj), field("Excel workbook (.xlsx) or CSV file", file)), h("div", null, "File: ", fname),
      h("div", null, "Columns: ", cols), text,
      note(`Simulate = test every line with all checks, nothing is saved. Post = save every correct line (wrong lines are listed and skipped). Compare = after the upload, every value of the file is compared with NERP. Open items, balances and stock are posted against the takeover account 399999 - current balance ${App.fmtAmt(m.takeover)} (must be 0 when the load is complete).`)), out);
  const body = extra => {
    if (xlsx) return Object.assign({ obj: obj.value, xlsx }, extra);
    if (obj.value === "ALL") { msg("E", "Choose an Excel workbook (.xlsx) for 'all sheets', or choose one object for a CSV file", "ZI", "002"); return null; }
    if (!val(text)) { msg("E", "Choose a file or paste the CSV text", "ZI", "002"); return null; }
    return Object.assign({ obj: obj.value, text: text.value }, extra);
  };
  const exec = async simulate => {
    const b = body({ simulate }); if (!b) return;
    if (!simulate && !await confirmBox("Post import", "Post every correct line now? (run Simulate first)")) return;
    const r = await run(() => api(xlsx ? "/api/import/xlsx" : "/api/import/run", b)); if (!r) return;
    msg(r.errors ? "W" : "S", r.message); out.innerHTML = "";
    if (r.sheets) out.append(alv({ rows: r.sheets, title: "Per sheet", columns: [{ key: "sheet", label: "Sheet" }, { key: "ok", label: "OK", type: "int", sum: true }, { key: "errors", label: "Errors", type: "int", sum: true }] }));
    out.append(alv({ rows: r.log, title: (simulate ? "Simulation log" : "Import log") + " - S = OK, E = error (fix it in the file)", rowClass: x => x.status === "E" ? ".neg" : "",
      columns: [{ key: "sheet", label: "Sheet" }, { key: "line", label: "Line (Excel row)" }, { key: "status", label: "Status" }, { key: "key", label: "Number in NERP" }, { key: "message", label: "Message" }] }));
  };
  const compare = async () => {
    const b = body({}); if (!b) return;
    const r = await run(() => api("/api/import/verify", b)); if (!r) return;
    msg(r.all_ok ? "S" : "W", r.message); out.innerHTML = "";
    out.append(h("div.kpis", null, h("div.kpi", null, h("div.k", null, "Result"), h("div.v" + (r.all_ok ? ".pos" : ".neg"), null, r.all_ok ? "✔ Match" : "✖ Differences")),
      h("div.kpi", null, h("div.k", null, "Values compared"), h("div.v", null, String(r.checked))),
      h("div.kpi", null, h("div.k", null, "Missing / different"), h("div.v" + (r.differences.length ? ".neg" : ""), null, String(r.differences.length)))));
    out.append(alv({ rows: r.summary.map(s => Object.assign({}, s, { st: s.control_ok === false ? "✖" : (s.control_ok ? "✔" : "-") })), title: "Control totals per sheet (compare with the 'Control' sheet of the workbook)",
      columns: [{ key: "sheet", label: "Sheet" }, { key: "lines", label: "Lines in file", type: "int" }, { key: "found", label: "Found in NERP", type: "int" }, { key: "control", label: "Control" }, { key: "st", label: "OK" }] }));
    out.append(alv({ rows: r.differences, title: "Missing or different values (empty = everything matches)", rowClass: () => ".neg", emptyText: "No differences - every value of the file is in NERP",
      columns: [{ key: "sheet", label: "Sheet" }, { key: "line", label: "Line" }, { key: "key", label: "Record" }, { key: "field", label: "Field" }, { key: "file", label: "Value in file" }, { key: "system", label: "Value in NERP" }, { key: "status", label: "Status" }] }));
  };
  toolbar([{ label: "CSV template", onClick: async () => { if (obj.value === "ALL") return download(false); const r = await run(() => api("/api/import/template/" + obj.value)); if (r) { xlsx = null; text.value = r.csv; } } },
    { label: "Simulate", key: "F8", primary: true, onClick: () => exec(true) }, { label: "Post", onClick: () => exec(false) },
    { label: "Compare file with system", onClick: compare }]);
} });

// ------------------------------------------------------------------ withholding tax
register("ZWHT", { title: "Withholding Tax - Codes and Vendors", async render(app, params) {
  const lifnr = inp({ value: params.id || "", list: "dl-lifnr", w: "m", upper: true }), out = h("div");
  app.append(panel(null, grid(field("Vendor", lifnr))), out);
  const load = async () => {
    const r = await run(() => api("/api/fi/wht" + (val(lifnr) ? "?lifnr=" + encodeURIComponent(up(lifnr)) : ""))); if (!r) return;
    out.innerHTML = "";
    out.append(alv({ rows: r.codes.map(c => Object.assign({}, c, { pct_t: (c.pct / 100).toFixed(2) + " %" })), title: "Withholding tax codes",
      columns: [{ key: "code", label: "Code" }, { key: "text", label: "Purchase type" }, { key: "pct_t", label: "Rate" }, { key: "base", label: "Base" },
        { key: "at", label: "Deducted at" }, { key: "hkont", label: "Account" }] }),
      note("Confirm the rates with the company's tax adviser before go-live."));
    if (r.vendor) {
      const code = sel(r.codes.map(c => [c.code, `${c.code} ${c.text}`]), "W3"), ef = inp({ type: "date" }), et = inp({ type: "date" }), cert = inp({ w: "m" });
      out.append(panel(`Vendor ${up(lifnr)}`, alv({ rows: r.vendor, columns: [{ key: "code", label: "Code" }, { key: "text", label: "Text" },
        { key: "exempt_from", label: "Exempt from", type: "date" }, { key: "exempt_to", label: "Exempt to", type: "date" }, { key: "certificate_no", label: "Certificate" },
        { key: "x", label: "", render: x => h("button.btn", { type: "button", on: { click: async () => {
          const y = await run(() => api("/api/fi/wht/assign", { lifnr: up(lifnr), code: x.code, delete: true })); if (y) { msg("S", y.message); load(); } } } }, "Remove") }],
        emptyText: "No withholding tax for this vendor" }),
      grid(field("Code", code), field("Exempt from", ef), field("Exempt to", et), field("Exemption certificate", cert)),
      h("button.btn.primary", { type: "button", on: { click: async () => {
        const y = await run(() => api("/api/fi/wht/assign", { lifnr: up(lifnr), code: code.value, exempt_from: ef.value, exempt_to: et.value, certificate_no: val(cert) }));
        if (y) { msg("S", y.message); load(); } } } }, "Assign")));
    }
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  load();
} });

register("ZWHT_RPT", { title: "Withholding Tax Report (Form 41)", async render(app) {
  const t = today(), q0 = t.slice(0, 5) + String(Math.floor((+t.slice(5, 7) - 1) / 3) * 3 + 1).padStart(2, "0") + "-01";
  const f = { d1: inp({ type: "date", value: q0 }), d2: inp({ type: "date", value: t }), lifnr: inp({ list: "dl-lifnr", w: "m", upper: true }) };
  const out = h("div");
  app.append(panel(null, grid(field("From", f.d1), field("To", f.d2), field("Vendor", f.lifnr))), out);
  const exec = async () => {
    const rows = await run(() => api("/api/fi/wht/report?" + new URLSearchParams({ d1: f.d1.value, d2: f.d2.value, lifnr: up(f.lifnr) }))); if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ rows, title: "Withholding tax by vendor and code", columns: [{ key: "lifnr", label: "Vendor" }, { key: "name", label: "Name" },
      { key: "taxid", label: "Tax ID" }, { key: "code", label: "Code" }, { key: "pct", label: "Rate %" }, { key: "base", label: "Base", type: "amt", sum: true },
      { key: "amount", label: "Withheld", type: "amt", sum: true }, { key: "docs", label: "Documents", type: "int" }] }));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]);
  exec();
} });

// ------------------------------------------------------------------ manual clearing
function clearScreen(koart) {
  const lbl = { K: "Vendor", D: "Customer", S: "G/L account" }[koart];
  return async (app, params) => {
    const p = inp({ value: params.id || "", w: "m", upper: true, list: koart === "K" ? "dl-lifnr" : null }), budat = inp({ type: "date", value: today(), w: "m" });
    const resid = h("input", { type: "checkbox" }), out = h("div"), sum = h("span.badge");
    let rows = [], pick = new Set();
    const calc = () => { const s = rows.filter(r => pick.has(r.k)).reduce((a, r) => a + r.amount, 0); sum.textContent = `Selected balance ${App.fmtAmt(s)}`; sum.className = "badge " + (Math.abs(s) < 0.005 ? "U" : "B"); };
    app.append(panel(null, grid(field(lbl, p, { req: true }), field("Posting date", budat), field("Rest as residual item", resid))),
      h("div.panel", null, h("div.panel-head", null, "Open items", h("span.spacer"), sum), out),
      note("Select items that clear each other. A difference up to 5.00 goes to 'payment differences' (288000); a larger one needs 'residual item'."));
    const load = async () => {
      if (!val(p)) return msg("E", `Enter the ${lbl.toLowerCase()}`, "F5", "260");
      const r = await run(() => api(`/api/fi/openitems?koart=${koart}&partner=${encodeURIComponent(up(p))}`)); if (!r) return;
      rows = r.map(x => Object.assign(x, { k: `${x.belnr}/${x.gjahr}/${x.buzei}` })); pick = new Set(); out.innerHTML = "";
      out.append(alv({ rows, columns: [{ key: "sel", label: "✓", render: x => { const c = h("input", { type: "checkbox" }); c.addEventListener("change", () => { c.checked ? pick.add(x.k) : pick.delete(x.k); calc(); }); return c; } },
        { key: "belnr", label: "Document" }, { key: "buzei", label: "Line", type: "int" }, { key: "budat", label: "Posting date", type: "date" }, { key: "xblnr", label: "Reference" },
        { key: "sgtxt", label: "Text" }, { key: "zlspr", label: "Block" }, { key: "amount", label: "Amount", type: "amt", signed: true, sum: true }] }));
      calc();
    };
    toolbar([{ label: "Open items", key: "F8", onClick: load }, { label: "Post clearing", key: "Ctrl+S", primary: true, onClick: async () => {
      const items = rows.filter(r => pick.has(r.k)).map(r => [r.belnr, r.gjahr, r.buzei]);
      const r = await run(() => api("/api/fi/clear", { koart, partner: up(p), items, budat: budat.value, residual: resid.checked }));
      if (r) { msg("S", r.message); load(); } } }]);
    if (params.id) load();
  };
}
register("F-44", { title: "Clear Vendor", render: clearScreen("K") });
register("F-32", { title: "Clear Customer", render: clearScreen("D") });
register("F-03", { title: "Clear G/L Account", render: clearScreen("S") });

// ------------------------------------------------------------------ down payments
function dpRequest(koart) {
  return async app => {
    const f = { partner: inp({ w: "m", upper: true, list: koart === "K" ? "dl-lifnr" : null }), amount: inp({ w: "m" }), due: inp({ type: "date", value: today() }),
      ebeln: inp({ w: "m" }), text: inp({ w: "l" }) };
    const out = h("div");
    app.append(panel("Down-payment request (noted item - no balance)", grid(field(koart === "K" ? "Vendor" : "Customer", f.partner, { req: true }),
      field("Amount", f.amount, { req: true }), field("Due on", f.due), field("Purchase / sales order", f.ebeln), field("Text", f.text))), out);
    const list = async () => { const r = await run(() => api(`/api/fi/dp/requests?koart=${koart}`)); if (!r) return; out.innerHTML = "";
      out.append(alv({ rows: r, title: "Open requests", columns: [{ key: "id", label: "Request", type: "int" }, { key: "partner", label: "Partner" },
        { key: "amount", label: "Amount", type: "amt" }, { key: "due", label: "Due", type: "date" }, { key: "ebeln", label: "Order" }, { key: "text", label: "Text" }] })); };
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/fi/dp/request", { koart, partner: up(f.partner), amount: val(f.amount), due: f.due.value, ebeln: val(f.ebeln), text: val(f.text) }));
      if (r) { msg("S", r.message); list(); } } }]);
    list();
  };
}
function dpPost(koart) {
  return async app => {
    const f = { partner: inp({ w: "m", upper: true, list: koart === "K" ? "dl-lifnr" : null }), amount: inp({ w: "m" }), budat: inp({ type: "date", value: today() }),
      req: inp({ w: "s" }), bank: inp({ value: "113100", w: "m" }), text: inp({ w: "l" }) };
    app.append(panel(koart === "K" ? "Down payment to the vendor (special G/L A, account 164000)" : "Down payment received from the customer (special G/L A, account 170000)",
      grid(field(koart === "K" ? "Vendor" : "Customer", f.partner, { req: true }), field("Amount (empty = from request)", f.amount),
        field("Request no.", f.req), field("Posting date", f.budat), field("Bank account", f.bank), field("Text", f.text))));
    toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/fi/dp/post", { koart, partner: up(f.partner), amount: val(f.amount), request_id: val(f.req), budat: f.budat.value, bank: val(f.bank), text: val(f.text) }));
      if (r) msg("S", r.message); } }]);
  };
}
function dpClear(koart) {
  return async app => {
    const p = inp({ w: "m", upper: true, list: koart === "K" ? "dl-lifnr" : null }), budat = inp({ type: "date", value: today() }), out = h("div");
    let dp = null, inv = null;
    app.append(panel(null, grid(field(koart === "K" ? "Vendor" : "Customer", p, { req: true }), field("Posting date", budat))), out,
      note("Choose one down payment and one invoice. The down payment is transferred to the normal account and clears the invoice; the rest of the invoice stays open."));
    const load = async () => {
      if (!val(p)) return msg("E", "Enter the partner", "F5", "260");
      const r = await run(() => api(`/api/fi/openitems?koart=${koart}&special=all&partner=${encodeURIComponent(up(p))}`)); if (!r) return;
      out.innerHTML = ""; dp = inv = null;
      const radio = (name, x, set) => { const c = h("input", { type: "radio", name }); c.addEventListener("change", () => set(x)); return c; };
      out.append(alv({ rows: r.filter(x => x.umskz === "A"), title: "Down payments", columns: [{ key: "s", label: "", render: x => radio("dp", x, v => { dp = v; }) },
        { key: "belnr", label: "Document" }, { key: "budat", label: "Date", type: "date" }, { key: "amount", label: "Amount", type: "amt" }], emptyText: "No down payment" }),
      alv({ rows: r.filter(x => !x.umskz), title: "Open invoices", columns: [{ key: "s", label: "", render: x => radio("inv", x, v => { inv = v; }) },
        { key: "belnr", label: "Document" }, { key: "xblnr", label: "Reference" }, { key: "budat", label: "Date", type: "date" }, { key: "amount", label: "Amount", type: "amt" }] }));
    };
    toolbar([{ label: "Open items", key: "F8", onClick: load }, { label: "Post clearing", key: "Ctrl+S", primary: true, onClick: async () => {
      if (!dp || !inv) return msg("E", "Choose a down payment and an invoice", "F5", "271");
      const r = await run(() => api("/api/fi/dp/clear", { koart, partner: up(p), budat: budat.value, dp: [dp.belnr, dp.gjahr, dp.buzei], invoice: [inv.belnr, inv.gjahr, inv.buzei] }));
      if (r) { msg("S", r.message); load(); } } }]);
  };
}
register("F-47", { title: "Down Payment Request (Vendor)", render: dpRequest("K") });
register("F-37", { title: "Down Payment Request (Customer)", render: dpRequest("D") });
register("F-48", { title: "Post Vendor Down Payment", render: dpPost("K") });
register("F-29", { title: "Post Customer Down Payment", render: dpPost("D") });
register("F-54", { title: "Clear Vendor Down Payment", render: dpClear("K") });
register("F-39", { title: "Clear Customer Down Payment", render: dpClear("D") });
})();
