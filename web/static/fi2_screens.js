/* NERP - Accounting in depth: cheques received / issued (ZCHQ_IN, ZCHQ_OUT, ZCHQ), petty
   cash journal (FBCJ), recurring entries (FBD1, FBD3, F.14), parked documents (FV50, FBV0,
   FBV3), statement of account (F.27) and FI closing management (ZFI_CLOSE). */
"use strict";
(() => {
const { h, api, msg, run, confirmBox, field, inp, sel, val, up, alv, register, go, toolbar, fmtAmt, today } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const now = () => { const d = today(); return { y: +d.slice(0, 4), p: +d.slice(5, 7) }; };
const CHQ = { REC: ["In portfolio", "Q"], ISS: ["Issued", "Q"], COL: ["Collected", "U"], BNC: ["Bounced", "B"] };

// ------------------------------------------------------------------ cheques
function chequeEntry(dir) {
  const D = dir === "in";
  return { title: D ? "Receive Customer Cheque (notes receivable)" : "Issue Vendor Cheque (notes payable)", async render(app, params) {
    const f = { partner: inp({ value: params.id || "", w: "m", upper: true, list: D ? "dl-kunnr" : "dl-lifnr" }), chqno: inp({ w: "m" }), bank: inp({ w: "s", upper: true, ph: "e.g. CIB" }),
      due: inp({ type: "date", value: today() }), budat: inp({ type: "date", value: today() }), amount: inp({ w: "m", ph: "only for on-account" }), text: inp({ w: "l" }) };
    const items = h("div");
    let open = [], picks = new Set();
    app.append(panel(D ? "Cheque from the customer" : "Cheque to the vendor", grid(field(D ? "Customer" : "Vendor", f.partner, { req: true }), field("Cheque number", f.chqno, { req: true }),
      field("Bank of the cheque", f.bank, { req: true }), field("Due date (on the cheque)", f.due, { req: true }), field("Posting date", f.budat), field("Amount (on account)", f.amount), field("Text", f.text))),
      note(D ? "Select the invoices the cheque pays: they are cleared at once and the amount goes to notes receivable (115000) until the bank collects the cheque at its due date (ZCHQ). Without invoices the amount is posted on account."
        : "Select the invoices the cheque pays: they are cleared and the amount goes to notes payable (165000) until the vendor cashes the cheque (ZCHQ)."), items);
    const loadItems = async () => {
      if (!up(f.partner)) return;
      open = await run(() => api(`/api/fi/openitems?koart=${D ? "D" : "K"}&partner=${encodeURIComponent(up(f.partner))}`)) || [];
      picks = new Set(); items.innerHTML = "";
      items.append(alv({ rows: open.map((o, i) => Object.assign({ i }, o)), title: `Open items of ${up(f.partner)} - tick the items the cheque pays`, emptyText: "No open items",
        columns: [{ key: "pick", label: "Pay", render: r => { const cb = h("input", { type: "checkbox" }); cb.addEventListener("change", () => { if (cb.checked) picks.add(r.i); else picks.delete(r.i); }); return cb; } },
          { key: "belnr", label: "Document" }, { key: "xblnr", label: "Reference" }, { key: "zfbdt", label: "Base date", type: "date" }, { key: "amount", label: "Amount", type: "amt", sum: true }] }));
    };
    f.partner.addEventListener("change", loadItems);
    toolbar([{ label: "Open items", key: "F8", onClick: loadItems }, { label: D ? "Receive cheque" : "Issue cheque", primary: true, onClick: async () => {
      const b = { [D ? "kunnr" : "lifnr"]: up(f.partner), chqno: val(f.chqno), bank: up(f.bank), due: f.due.value, budat: f.budat.value, amount: val(f.amount), text: val(f.text),
        items: [...picks].map(i => [open[i].belnr, open[i].gjahr, open[i].buzei]) };
      const r = await run(() => api("/api/fi/cheque/" + dir, b)); if (r) { msg("S", r.message); loadItems(); } } },
      { label: "Cheque register", onClick: () => go("ZCHQ") }]);
    if (params.id) loadItems();
  } };
}
register("ZCHQ_IN", chequeEntry("in"));
register("ZCHQ_OUT", chequeEntry("out"));
register("ZCHQ", { title: "Cheque Register (received / issued)", async render(app) {
  const dir = sel([["", "All"], ["IN", "Received from customers"], ["OUT", "Issued to vendors"]], ""), st = sel([["", "All"], ["REC", "In portfolio"], ["ISS", "Issued"], ["COL", "Collected"], ["BNC", "Bounced"]], "");
  const out = h("div");
  app.append(panel(null, grid(field("Direction", dir), field("Status", st))), out);
  const act = async (r, a) => {
    if (a === "bounce") {
      const x = await App.ask("Bounced cheque", [{ name: "reason", label: "Reason", value: "insufficient funds" }]); if (!x) return;
      const res = await run(() => api("/api/fi/cheque/bounce", { id: r.id, budat: today(), reason: x.reason })); if (res) { msg("S", res.message); load(); } return;
    }
    if (!await confirmBox("Cheque", `${r.dir === "IN" ? "Collected by the bank" : "Cashed by the vendor"}: cheque ${r.chqno}?`)) return;
    const res = await run(() => api("/api/fi/cheque/collect", { id: r.id, budat: today() })); if (res) { msg("S", res.message); load(); }
  };
  const load = async () => {
    const d = await run(() => api(`/api/fi/cheques?dir=${dir.value}&status=${st.value}`)); if (!d) return;
    out.innerHTML = "";
    const overdue = d.rows.filter(r => r.overdue);
    out.append(h("div.kpis", null, kpi("Cheques in portfolio", fmtAmt(d.summary.IN.amount), `${d.summary.IN.count} received, not yet collected`),
      kpi("Cheques issued, not cashed", fmtAmt(d.summary.OUT.amount), `${d.summary.OUT.count} cheque(s)`),
      kpi("Overdue", overdue.length, "due date passed, still open", overdue.length ? "neg" : "pos")));
    out.append(alv({ rows: d.rows, title: "Cheques", rowClass: r => r.overdue ? ".neg" : "", columns: [{ key: "dir", label: "Dir.", render: r => r.dir === "IN" ? "⬇ In" : "⬆ Out" },
      { key: "chqno", label: "Cheque no." }, { key: "bank", label: "Bank" }, { key: "partner", label: "Partner" }, { key: "name", label: "Name" }, { key: "amount", label: "Amount", type: "amt", sum: true },
      { key: "due", label: "Due", type: "date" }, { key: "days", label: "Days", type: "int" }, { key: "status", label: "Status", render: r => badge(CHQ[r.status][0], CHQ[r.status][1]) },
      { key: "belnr", label: "Document" }, { key: "x", label: "", render: r => r.status === "REC" || r.status === "ISS" ? h("span", null,
        h("button.btn", { type: "button", on: { click: () => act(r, "collect") } }, r.dir === "IN" ? "Collected" : "Cashed"), " ",
        r.dir === "IN" ? h("button.btn", { type: "button", on: { click: () => act(r, "bounce") } }, "Bounced") : null) : "" }] }));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Receive cheque", onClick: () => go("ZCHQ_IN") }, { label: "Issue cheque", onClick: () => go("ZCHQ_OUT") }]);
  load();
} });

// ------------------------------------------------------------------ FBCJ petty cash
register("FBCJ", { title: "Cash Journal (petty cash)", async render(app) {
  const n = now();
  const f = { typ: sel([["EXPENSE", "Expense paid in cash"], ["BANK_IN", "Cash from the bank"], ["BANK_OUT", "Cash to the bank"], ["RECEIPT", "Cash receipt"]], "EXPENSE"),
    budat: inp({ type: "date", value: today() }), amount: inp({ w: "m" }), hkont: inp({ w: "s", ph: "e.g. 477000" }), kostl: inp({ w: "s", upper: true, list: "dl-kostl" }), text: inp({ w: "l" }),
    d1: inp({ type: "date", value: `${n.y}-${String(n.p).padStart(2, "0")}-01` }), d2: inp({ type: "date", value: today() }) };
  const out = h("div");
  app.append(panel("New entry", grid(field("Entry", f.typ), field("Date", f.budat), field("Amount", f.amount, { req: true }), field("Expense / income account", f.hkont), field("Cost center", f.kostl), field("Text", f.text, { req: true }))),
    note("Cash account 100000. The cash box can never go below zero. Count the cash at the end of the day and compare it with the closing balance."),
    panel("Cash book", grid(field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    const d = await run(() => api(`/api/fi/cashbook?d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Opening balance", fmtAmt(d.opening), d.d1), kpi("Receipts", fmtAmt(d.receipts)), kpi("Payments", fmtAmt(d.payments)), kpi("Closing balance", fmtAmt(d.closing), d.d2, "pos")),
      alv({ rows: d.lines, title: "Cash book", columns: [{ key: "budat", label: "Date", type: "date" }, { key: "belnr", label: "Document" }, { key: "text", label: "Text" },
        { key: "receipt", label: "Receipt", type: "amt", sum: true }, { key: "payment", label: "Payment", type: "amt", sum: true }, { key: "balance", label: "Balance", type: "amt" }, { key: "usnam", label: "User" }] }));
  };
  toolbar([{ label: "Post", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/cashbook/post", { typ: f.typ.value, budat: f.budat.value, amount: val(f.amount), hkont: val(f.hkont), kostl: up(f.kostl), text: val(f.text) }));
    if (r) { msg("S", r.message); f.amount.value = ""; f.text.value = ""; load(); } } }, { label: "Display book", key: "F8", onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ recurring entries
const lineEditor = (n) => {
  const rows = Array.from({ length: n }, (_, i) => ({ bschl: sel([["40", "40 Debit G/L"], ["50", "50 Credit G/L"], ["01", "01 Customer debit"], ["15", "15 Customer credit"], ["31", "31 Vendor credit"], ["25", "25 Vendor debit"]], i === 0 ? "40" : "50"),
    account: inp({ w: "s" }), amount: inp({ w: "s" }), kostl: inp({ w: "s", upper: true }), sgtxt: inp({ w: "m" }) }));
  const table = h("table.grid", null, h("thead", null, h("tr", null, ["PK", "Account", "Amount", "Cost center", "Text"].map(t => h("th", null, t)))),
    h("tbody", null, rows.map(r => h("tr", null, h("td", null, r.bschl), h("td", null, r.account), h("td", null, r.amount), h("td", null, r.kostl), h("td", null, r.sgtxt)))));
  const data = () => rows.filter(r => val(r.account) && val(r.amount)).map(r => ({ bschl: r.bschl.value, account: up(r.account), amount: val(r.amount), kostl: up(r.kostl), sgtxt: val(r.sgtxt) }));
  return { table, data };
};
register("FBD1", { title: "Create Recurring Entry", async render(app) {
  const n = now();
  const f = { text: inp({ w: "l", ph: "e.g. warehouse rent" }), first: inp({ type: "date", value: `${n.y}-${String(n.p).padStart(2, "0")}-01` }), last: inp({ type: "date" }) };
  const ed = lineEditor(4);
  app.append(panel("Recurring document", grid(field("Description", f.text, { req: true }), field("First posting", f.first, { req: true }), field("Last posting (empty = no end)", f.last))),
    panel("Lines (posted every month)", ed.table), note("Example rent: 40 / 475000 / 20000 / cost center 4400 - and 50 / 113100 / 20000. The run F.14 posts it once per month."));
  toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/recurring/save", { text: val(f.text), first: f.first.value, last: f.last.value, lines: ed.data() })); if (r) { msg("S", r.message); go("FBD3"); } } }]);
} });
register("FBD3", { title: "Display Recurring Entries", async render(app) {
  const d = await run(() => api("/api/fi/recurring")); if (!d) return;
  app.append(alv({ rows: d.docs, title: "Recurring documents", columns: [{ key: "id", label: "No.", type: "int" }, { key: "text", label: "Description" }, { key: "first", label: "First", type: "date" },
    { key: "last", label: "Last", type: "date" }, { key: "amount", label: "Amount", type: "amt" }, { key: "runs", label: "Posted", type: "int" }, { key: "usnam", label: "By" }] }),
    alv({ rows: d.runs, title: "Postings", columns: [{ key: "gjahr", label: "Year", type: "int" }, { key: "perio", label: "Period", type: "int" }, { key: "text", label: "Document" }, { key: "belnr", label: "FI document" }, { key: "usnam", label: "User" }] }));
  toolbar([{ label: "Create", onClick: () => go("FBD1") }, { label: "Run (F.14)", primary: true, onClick: () => go("F.14") }]);
} });
register("F.14", { title: "Post Recurring Entries", async render(app, params) {
  const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const exec = async act => {
    const r = await run(() => api("/api/fi/recurring/" + act, { gjahr: val(f.y), perio: val(f.p) })); if (!r) return;
    msg("S", r.message); out.innerHTML = "";
    out.append(alv({ rows: r.docs, title: r.test ? "Test run - nothing posted" : "Posted", columns: [{ key: "id", label: "No.", type: "int" }, { key: "text", label: "Description" }, { key: "budat", label: "Posting date", type: "date" }, { key: "belnr", label: "FI document" }] }));
  };
  toolbar([{ label: "Test run", key: "F8", onClick: () => exec("test") }, { label: "Post", primary: true, onClick: () => exec("run") }]);
} });

// ------------------------------------------------------------------ parked documents
register("FV50", { title: "Park G/L Account Document", async render(app) {
  const f = { budat: inp({ type: "date", value: today() }), bktxt: inp({ w: "l" }), xblnr: inp({ w: "m" }) };
  const ed = lineEditor(4);
  app.append(panel("Header", grid(field("Posting date", f.budat), field("Header text", f.bktxt, { req: true }), field("Reference", f.xblnr))), panel("Lines", ed.table),
    note("The document is checked like a real posting but not posted. A second person checks and posts it (FBV0) - it waits in the approval inbox (ZINBOX)."));
  toolbar([{ label: "Park", key: "Ctrl+S", primary: true, onClick: async () => {
    const r = await run(() => api("/api/fi/parked/park", { budat: f.budat.value, bktxt: val(f.bktxt), xblnr: val(f.xblnr), lines: ed.data() })); if (r) { msg("S", r.message); go("FBV0"); } } }]);
} });
function parkedList(title, onlyOpen) {
  return { title, async render(app) {
    const out = h("div");
    app.append(out);
    const load = async () => {
      const d = await run(() => api("/api/fi/parked" + (onlyOpen ? "?status=P" : ""))); if (!d) return;
      out.innerHTML = "";
      out.append(alv({ rows: d.rows, title: onlyOpen ? "Parked documents waiting for posting" : "All parked documents", emptyText: "No parked documents",
        columns: [{ key: "id", label: "No.", type: "int" }, { key: "budat", label: "Date", type: "date" }, { key: "bktxt", label: "Text" }, { key: "xblnr", label: "Reference" }, { key: "amount", label: "Amount", type: "amt", sum: true },
          { key: "parked_by", label: "Parked by" }, { key: "status_text", label: "Status" }, { key: "belnr", label: "FI document" },
          { key: "lines", label: "Lines", render: r => r.lines.map(l => `${l.bschl} ${l.account} ${l.amount}`).join(" · ") },
          { key: "x", label: "", render: r => r.status === "P" && onlyOpen ? h("span", null,
            h("button.btn", { type: "button", on: { click: async () => { const x = await run(() => api("/api/fi/parked/post", { id: r.id })); if (x) { msg("S", x.message); load(); } } } }, "Post"), " ",
            h("button.btn", { type: "button", on: { click: async () => { if (!await confirmBox("Delete", `Delete parked document ${r.id}?`)) return; const x = await run(() => api("/api/fi/parked/delete", { id: r.id })); if (x) { msg("S", x.message); load(); } } } }, "Delete")) : "" }] }));
    };
    toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Park document", onClick: () => go("FV50") }]);
    load();
  } };
}
register("FBV0", parkedList("Post Parked Documents", true));
register("FBV3", parkedList("Display Parked Documents", false));

// ------------------------------------------------------------------ F.27 statement of account
register("F.27", { title: "Statement of Account (customer / vendor)", async render(app, params) {
  const n = now();
  const f = { koart: sel([["D", "Customer"], ["K", "Vendor"]], params.koart || "D"), partner: inp({ value: params.id || "", w: "m", upper: true }),
    d1: inp({ type: "date", value: `${n.y}-01-01` }), d2: inp({ type: "date", value: today() }) };
  const out = h("div");
  app.append(panel(null, grid(field("Account type", f.koart), field("Customer / vendor", f.partner, { req: true }), field("From", f.d1), field("To", f.d2))), out);
  const load = async () => {
    if (!up(f.partner)) return msg("E", "Enter the customer or vendor");
    const d = await run(() => api(`/api/fi/statement?koart=${f.koart.value}&partner=${encodeURIComponent(up(f.partner))}&d1=${f.d1.value}&d2=${f.d2.value}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi(d.koart === "D" ? "Customer" : "Vendor", `${d.partner}`, d.name), kpi("Opening balance", fmtAmt(d.opening), d.d1),
      kpi("Debit", fmtAmt(d.debit)), kpi("Credit", fmtAmt(d.credit)), kpi("Closing balance", fmtAmt(d.closing), d.d2, d.closing ? "" : "pos")),
      alv({ rows: d.lines, title: `Statement of account ${d.partner} ${d.name} - ${d.d1} to ${d.d2}`, columns: [{ key: "budat", label: "Date", type: "date" }, { key: "belnr", label: "Document" },
        { key: "blart", label: "Type" }, { key: "xblnr", label: "Reference" }, { key: "text", label: "Text" }, { key: "debit", label: "Debit", type: "amt", sum: true },
        { key: "credit", label: "Credit", type: "amt", sum: true }, { key: "balance", label: "Balance", type: "amt" }, { key: "due", label: "Due", type: "date" }, { key: "cleared", label: "Cleared by" }] }),
      note("Send it to the customer / vendor (Print or Excel above) and ask for a balance confirmation."));
  };
  toolbar([{ label: "Display", key: "F8", primary: true, onClick: load }]);
  if (params.id) load();
} });

// ------------------------------------------------------------------ ZFI_CLOSE
register("ZFI_CLOSE", { title: "Accounting - Closing Management", async render(app, params) {
  const n = now(), f = { y: inp({ value: params.gjahr || n.y, w: "s" }), p: inp({ value: params.perio || n.p, w: "s" }) }, out = h("div");
  const ST = { done: ["Done", "U"], open: ["Open", "Q"], "n/a": ["Not needed", ""] };
  app.append(panel(null, grid(field("Fiscal year", f.y), field("Period", f.p))), out);
  const load = async () => {
    const d = await run(() => api(`/api/fi/close_mgmt?gjahr=${val(f.y)}&perio=${val(f.p)}`)); if (!d) return;
    out.innerHTML = "";
    out.append(h("div.kpis", null, kpi("Closing steps done", `${d.done} / ${d.needed}`, `${String(d.perio).padStart(2, "0")}/${d.gjahr}`, d.done === d.needed ? "pos" : "")),
      alv({ rows: d.steps.map(s => Object.assign({}, s, { st: ST[s.status][0] })), title: "Month-end closing in Accounting - in this order",
        columns: [{ key: "no", label: "Step", type: "int" }, { key: "step", label: "Task" }, { key: "tcode", label: "Transaction", link: r => go(r.tcode, { gjahr: val(f.y), perio: val(f.p) }) },
          { key: "st", label: "Status", render: r => badge(ST[r.status][0], ST[r.status][1]) }, { key: "info", label: "Result" }] }),
      note("Controlling has its own closing cockpit (ZCO_CLOSE). Close the posting period (OB52) last."));
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "CO closing (ZCO_CLOSE)", onClick: () => go("ZCO_CLOSE") }]);
  load();
} });
})();
