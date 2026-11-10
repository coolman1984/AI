/* MM Core - e-Learning (ZLMS: manuals repository + LMS ID) and Process Test Center (ZQA_TEST) */
"use strict";
(() => {
const { h, $, $$, api, msg, run, register, go, toolbar, fmtDate } = App;

const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const kpi = (l, v, s, cls) => h("div.kpi", null, h("div.k", null, l), h("div.v" + (cls ? "." + cls : ""), null, v), s ? h("div.s", null, s) : null);
const ok = st => st === "P";
const tick = st => h("span.qa-st." + (ok(st) ? "ok" : st ? "bad" : "na"), { title: ok(st) ? "Passed" : st ? "Failed" : "Not tested" },
  ok(st) ? "✔" : st ? "✖" : "•");
const tcLinks = s => h("span", null, String(s || "").split(/\s+/).filter(Boolean).map(t =>
  h("a.qa-tc", { href: "#/" + t }, t)));

let CAT = null;
async function catalog(force) {
  if (!CAT || force) CAT = await api("/api/qa/catalog");
  return CAT;
}
const runOf = id => ((CAT.run || {}).processes || []).find(p => p.id === id);
const caseRun = (pid, cid) => ((runOf(pid) || {}).cases || []).find(c => c.id === cid);

// ------------------------------------------------------------------ repository model
const AREA = { "1": [[["Marketing"]], "MKT"], "2": [[["Sales"]], "SD"], "3": [[], "CS"], "4": [[["Procurement"]], "MM"],
  "5": [[["Production"]], "PP"], "6": [[["Logistics Execution"]], "LE"], "7": [[["Financial Accounting"], ["Controlling"]], "FI"],
  "8": [[["Master Data"]], "MD"], "9": [[["Common", "Cockpits"]], "BI"], "A": [[["Common"], ["Administration"]], "CA"], "B": [[], "TV"] };
const SERVICE = ["IW51", "IW52", "IW53", "IW31", "IW41", "IE01", "IE03", "DP90", "MP30", "MP33", "MP38"];

function codesOf(item, out) {
  if (typeof item === "string") { if (!item.startsWith("!") && App.S.screens[item]) out.push(item); }
  else for (const c of item[1]) codesOf(c, out);
  return out;
}
function menuCodes(path) {
  const top = (App.MENU || []).find(m => m[0] === path[0]);
  if (!top) return [];
  if (path.length === 1) return codesOf(top, []);
  const sub = top[1].find(x => Array.isArray(x) && x[0] === path[1]);
  return sub ? codesOf(sub, []) : [];
}

function buildDocs(opt) {
  const docs = [];
  const seen = new Set();
  const book = "MM_Core_Process_Test_Book.pptx";
  const run = CAT.run || {};
  docs.push({ folder: "", key: "MM CORE", status: run.cases ? (run.failed ? "F" : "P") : "", module: "QA", course: "S_QA00001_1.0",
    doc: "Material", type: "PR", title: "Process Manual & Test Book - all processes(EN)", href: "/manuals/" + book, dl: true });
  docs.push({ folder: "", key: "MM CORE", lang: "AR", status: run.cases ? (run.failed ? "F" : "P") : "", module: "QA",
    course: "S_QA00002_AR", doc: "Material", type: "PR", title: "دليل العمليات بالعربي - شرح كل Process في كل موديول(AR)",
    href: "/manuals/MM_Core_Process_Guide_AR.pptx", dl: true });
  for (const p of CAT.processes) {
    const r = runOf(p.id);
    const st = r ? (r.passed === r.total ? "P" : "F") : "";
    const base = { folder: p.folder, key: p.name, module: p.module, doc: "Material", type: "PR", dl: true,
      href: "/manuals/PM_" + p.id + ".pptx" };
    docs.push({ ...base, status: st, course: `S_${p.module}${p.id}_${p.version}`,
      title: `Process Manual ${p.module} ${p.version} ${p.name}(EN)` });
    for (const s of p.steps) docs.push({ ...base, status: st, course: `S_${p.module}${p.id}${String(s.no).padStart(2, "0")}_${p.version}`,
      title: `Process Manual ${p.module} ${p.version}.${s.no} ${s.title} [${s.tcode}](EN)` });
    docs.push({ ...base, lang: "AR", status: st, course: `S_${p.module}${p.id}_AR`, href: "/manuals/MM_Core_Process_Guide_AR.pptx",
      title: `شرح العملية بالعربي - ${p.name} (${p.module})(AR)` });
    if (opt.all) for (const c of p.cases) {
      const cr = caseRun(p.id, c.id);
      docs.push({ ...base, doc: "Test script", type: "TS", status: cr ? cr.status : "", course: c.id, dl: false,
        href: "#/ZQA_TEST", title: `Test Script ${c.id} ${c.title}(EN)` });
    }
  }
  const order = Object.keys(AREA).sort((a, b) => (a === "9" ? -1 : b === "9" ? 1 : 0));
  for (const f of order) {
    const [paths, mod] = AREA[f];
    let codes = f === "3" ? SERVICE.filter(c => App.S.screens[c]) : paths.flatMap(menuCodes);
    if (f === "A") codes = codes.filter(c => !menuCodes(["Common", "Cockpits"]).includes(c));
    for (const c of codes) {
      if (!opt.dup && seen.has(c)) continue;
      seen.add(c);
      let m = mod;
      if (f === "7") m = menuCodes(["Controlling"]).includes(c) ? "CO" : "FI";
      const key = f === "3" ? "Service" : (paths.find(x => menuCodes(x).includes(c)) || paths[0]).join(" / ");
      docs.push({ folder: f, key, status: "P", module: m, course: `S_${m}_${c}_1.0`, doc: "Material",
        type: "PG", title: `Program Manual ${m} ${c} ${App.S.screens[c].title}(EN)`, href: "#/" + c });
    }
  }
  return docs;
}

// ------------------------------------------------------------------ ZLMS
register("ZLMS", { title: "e-Learning - On-line Academy (Manuals)", async render(app) {
  await catalog(true);
  const lms = await api("/api/qa/lms");
  const f = { lang: h("select.inp", null, h("option", null, "EN"), h("option", { value: "AR" }, "AR - عربي")), all: h("input", { type: "checkbox" }),
    show: h("input", { type: "checkbox" }), dup: h("input", { type: "checkbox" }) };
  const search = h("input.inp", { placeholder: "Search title, T-code or course code", style: { width: "260px" } });
  const tree = h("div"), list = h("div.qa-list");
  let mode = "Set";
  const open = new Set();
  const draw = () => {
    const docs = buildDocs({ all: f.all.checked, dup: f.dup.checked })
      .filter(d => d.type === "PG" || (d.lang || "EN") === f.lang.value);
    tree.innerHTML = "";
    const tb = h("tbody");
    const count = (arr, t) => arr.filter(d => d.type === t || (t === "PR" && d.type === "TS")).length;
    const cell = (arr, t, label) => {
      const n = count(arr, t);
      return h("td.num", null, n ? h("a", { href: "#", on: { click: e => { e.preventDefault();
        showList(arr.filter(d => d.type === t || (t === "PR" && d.type === "TS")), label); } } }, n.toLocaleString()) : "0");
    };
    const row = (txt, arr, lvl, toggle, isOpen) => h("tr" + (lvl ? ".sub" : ""), null,
      h("td", { style: { paddingLeft: 14 + lvl * 22 + "px" } }, toggle ? h("a.qa-tog", { href: "#", on: { click: e => { e.preventDefault(); toggle(); } } },
        isOpen ? "⌄ " : "› ") : h("span.qa-tog", null, "  "), txt),
      cell(arr, "PR", txt), cell(arr, "PG", txt));
    let groups;
    if (mode === "Set") {
      tb.append(row("MM CORE", docs.filter(d => d.folder === ""), 0));
      groups = CAT.folders.map(([k, t]) => [k, `${k} ${t}`, docs.filter(d => d.folder === k)]);
    } else {
      const mods = [...new Set(docs.map(d => d.module))].sort();
      groups = mods.map(m => [m, m, docs.filter(d => d.module === m)]);
    }
    for (const [k, label, arr] of groups) {
      if (!f.show.checked && !arr.length && mode === "DS") continue;
      const isOpen = open.has(mode + k);
      tb.append(row(label, arr, 0, arr.length ? () => { isOpen ? open.delete(mode + k) : open.add(mode + k); draw(); } : null, isOpen));
      if (isOpen) {
        const subs = [...new Set(arr.map(d => d.key))];
        for (const s of subs) tb.append(row(s, arr.filter(d => d.key === s), 1));
      }
    }
    tb.append(h("tr.total", null, h("td", null, "Total"), cell(docs, "PR", "All process manuals"), cell(docs, "PG", "All program manuals")));
    tree.append(h("table.grid.qa-repo", null, h("thead", null,
      h("tr", null, h("th", { rowspan: 2 }, "Contents Repository Path"), h("th.num", null, "Process Manual"), h("th.num", null, "Program Manual")),
      h("tr", null, h("th.num.curr", null, "Curr"), h("th.num.curr", null, "Curr"))), tb));
  };
  const showList = (arr, label) => {
    list.innerHTML = "";
    list.append(h("div.qa-total", null, `${label} - Total : ${arr.length}`), h("table.grid.qa-docs", null,
      h("thead", null, h("tr", null, ["Status", "Module", "Course Code", "Doc. Type", "Manual Type", "Title", "Language"].map(t => h("th", null, t)))),
      h("tbody", null, arr.map(d => h("tr", null, h("td.c", null, tick(d.status)), h("td", null, d.module), h("td", null, d.course),
        h("td", null, d.doc), h("td", null, d.type), h("td", null, h("a", d.dl ? { href: d.href, download: "" } : { href: d.href }, d.title)),
        h("td", null, d.lang || "EN"))))));
    list.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  [f.all, f.show, f.dup, f.lang].forEach(x => x.addEventListener("change", draw));
  const tabs = h("div.tabs.qa-settabs", null, ["Set", "DS"].map(t => h("button.tab" + (t === mode ? ".active" : ""), { type: "button",
    on: { click: e => { mode = t; $$(".tab", tabs).forEach(b => b.classList.toggle("active", b === e.currentTarget)); draw(); } } }, t)));
  const doSearch = () => {
    const q = search.value.trim().toLowerCase();
    if (!q) return msg("W", "Enter a search term");
    showList(buildDocs({ all: true, dup: false }).filter(d => (d.title + " " + d.course).toLowerCase().includes(q)), `Search "${search.value}"`);
  };
  search.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
  const launch = () => {
    if (lms.status !== "CONNECTED") { msg("W", "Connect your LMS ID first (tab LMS ID)"); return showTab(1); }
    const a = h("a", { href: "/manuals/MM_Core_Process_Test_Book.pptx", download: "" }); document.body.append(a); a.click(); a.remove();
    msg("S", "LMS launched - Process Manual & Test Book downloaded");
  };
  const manuals = h("div", null,
    h("div.qa-filter", null,
      h("label", null, "Language:", f.lang), h("label", null, "All Types of Manuals:", f.all),
      h("label", null, "Show All Documents:", f.show), h("label", null, "Duplication:", f.dup)),
    h("div.qa-body", null, tabs,
      h("div.qa-actions", null, search, h("button.btn.primary", { type: "button", on: { click: doSearch } }, "Manual Search"),
        h("button.btn.primary", { type: "button", on: { click: launch } }, "Exit & LMS Launch")),
      tree, list));
  // ---------------------------------------------------------------- LMS ID flow
  const flow = h("div");
  const drawFlow = d => {
    Object.assign(lms, d);
    const st = lms.status;
    const done = { req: st !== "NONE", requested: st !== "NONE", check: st !== "NONE", register: ["REGISTERED", "CONNECTED"].includes(st),
      connect: st === "CONNECTED", end: st === "CONNECTED" };
    const cur = { NONE: "req", REQUESTED: "register", REGISTERED: "connect", CONNECTED: "end" }[st];
    const W = 150, X0 = 170, LH = 130;
    const node = (id, lane, col, txt, num, kind) => h("div.lms-node." + (kind || "box") + (done[id] ? ".done" : "") + (cur === id ? ".cur" : ""),
      { style: { left: X0 + col * (W + 40) + "px", top: lane * LH + 36 + "px", width: W - 20 + "px" } },
      num ? h("span.lms-num", null, String(num)) : null, h("span.lms-txt", null, txt));
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "lms-arrows");
    svg.setAttribute("width", "960"); svg.setAttribute("height", "260");
    const cx = c => X0 + c * (W + 40) + (W - 20) / 2, l = c => X0 + c * (W + 40), r = c => X0 + c * (W + 40) + W - 20;
    const y = lane => lane * LH + 36 + 29;
    const path = d2 => `<path d="${d2}" fill="none" stroke="#3ba0e6" stroke-width="1.6" stroke-dasharray="4 3" marker-end="url(#ah)"/>`;
    svg.innerHTML = '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">' +
      '<path d="M0,0 L10,5 L0,10 z" fill="#3ba0e6"/></marker></defs>' +
      path(`M${cx(0)},${y(0) + 30} V${y(1) - 30}`) + path(`M${r(0)},${y(1)} H${l(1)}`) + path(`M${cx(1)},${y(1) - 29} V${y(0) + 29}`) +
      path(`M${r(1)},${y(0)} H${cx(2)} V${y(1) - 31}`) + path(`M${r(2)},${y(1)} H${l(3)}`);
    flow.innerHTML = "";
    flow.append(h("div.lms-lanes", null,
      h("div.lms-lane", null, h("span", null, "MM Core (HQ)")), h("div.lms-lane", null, h("span", null, "User")), svg,
      node("check", 0, 0, "Check LMS ID?", 0, "dia"), node("req", 1, 0, "Request LMS ID", 1), node("requested", 1, 1, "Requested"),
      node("register", 0, 1, "Register ID", 2), node("connect", 1, 2, "Connect LMS", 3), node("end", 1, 3, "Manuals & tests open", 0, "end")),
    h("div.obj-header", null, [["User", lms.user], ["Status", st], ["LMS ID", lms.lms_id || "-"], ["Requested", lms.request_at || "-"],
      ["Registered", lms.register_at || "-"], ["Connected", lms.connect_at || "-"]].map(([k, v]) =>
      h("div.attr", null, h("span.k", null, k), h("span.v", null, v)))),
    h("div.qa-actions", null,
      [["request", "1  Request LMS ID", "NONE"], ["register", "2  Register ID (HQ)", "REQUESTED"], ["connect", "3  Connect LMS", "REGISTERED"]]
        .map(([s, t, need]) => h("button.btn" + (st === need ? ".primary" : ""), { type: "button", disabled: st !== need,
          on: { click: async () => { const r = await run(() => api("/api/qa/lms/" + s, {})); if (r) { msg(r.type, r.text); drawFlow(r); } } } }, t)),
      h("button.btn.ghost", { type: "button", on: { click: async () => { const r = await run(() => api("/api/qa/lms/reset", {}));
        if (r) { msg("S", r.text); drawFlow(r); } } } }, "Reset")));
  };
  drawFlow(lms);
  const bar = h("div.tabs"), page = h("div.panel-body");
  const pages = [["Manuals", manuals], ["LMS ID", h("div", null, h("p.muted", null,
    "How to start: request your LMS ID, HQ registers it, then connect - the manuals repository and the test book are opened for you."), flow)]];
  const showTab = i => { $$(".tab", bar).forEach((x, j) => x.classList.toggle("active", i === j)); page.innerHTML = ""; page.append(pages[i][1]); };
  pages.forEach(([t], i) => bar.append(h("button.tab", { type: "button", on: { click: () => showTab(i) } }, t)));
  app.append(h("div.panel", null, bar, page));
  showTab(0);
  draw();
  toolbar([{ label: "Test Center", onClick: () => go("ZQA_TEST") },
    { label: "Process Maps", ghost: true, onClick: () => go("ZPROCESS_ALL") }]);
} });

// ------------------------------------------------------------------ ZQA_CHECK
register("ZQA_CHECK", { title: "Data Consistency Check", async render(app) {
  const body = h("div"); app.append(panel(null, h("p", null, "Checks rules that must always hold: every FI document balances, stock in bins = valuated stock, stock accounts = material values, sub-ledgers = reconciliation accounts, invoiced ≤ received, reservations = goods issues, returned ≤ billed, FI = CO-PA, clearing data, number ranges.")), body);
  const exec = async () => {
    const r = await run(() => api("/api/qa/check")); if (!r) return; body.innerHTML = "";
    msg(r.count ? "E" : "S", r.message);
    body.append(r.count ? App.alv({ rows: r.violations, columns: [{ key: "rule", label: "Rule" }, { key: "object", label: "Object" },
      { key: "expected", label: "Expected" }, { key: "actual", label: "Actual" }, { key: "hint", label: "Hint" }] })
      : panel(null, h("p", null, tick("P"), " No violations - the data is consistent.")));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]); exec();
} });

// ------------------------------------------------------------------ ZQA_TEST
register("ZQA_TEST", { title: "Process Test Center - End-to-End Tests", async render(app) {
  await catalog(true);
  const body = h("div");
  const draw = () => {
    body.innerHTML = "";
    const r = CAT.run;
    if (!r) {
      body.append(panel(null, h("p", null, "No test run yet. Press Execute (F8) - all processes are tested on a fresh sample system; your data is not touched.")));
      return;
    }
    body.append(h("div.kpis", null,
      kpi("Test cases passed", `${r.passed} / ${r.cases}`, r.failed ? `${r.failed} failed` : "all passed", r.failed ? "neg" : "pos"),
      kpi("Automated tests", `${r.unit_passed} / ${r.unit_tests}`, "unit + end-to-end"),
      kpi("Processes", String(r.processes.length), "end to end"),
      kpi("Duration", `${r.seconds} s`, "fresh system per run"),
      kpi("Last run", fmtDate(r.run_at.slice(0, 10)), `${r.run_at.slice(11)} by ${r.user}`)));
    body.append(h("div.qa-cards", null, CAT.processes.map(p => {
      const pr = runOf(p.id) || { passed: 0, total: p.cases.length };
      return h("div.qa-card", null, h("div.qa-card-h", null, h("b", null, p.name), h("span.qa-ratio." + (pr.passed === pr.total ? "ok" : "bad"),
        null, `${pr.passed}/${pr.total}`)), h("div.qa-bar", null, h("span", { style: { width: (pr.passed / Math.max(pr.total, 1) * 100) + "%" } })),
      h("div.qa-card-l", null, h("a", { href: "#/" + p.map }, "Process map"), " · ",
        h("a", { href: "/manuals/PM_" + p.id + ".pptx", download: "" }, "Manual (PowerPoint)")));
    })));
    for (const p of CAT.processes) {
      const tb = h("tbody");
      for (const c of p.cases) {
        const cr = caseRun(p.id, c.id) || {};
        const det = h("tr.qa-det", { style: { display: "none" } }, h("td", { colspan: 7 }, (cr.tests || []).map(t =>
          h("div", null, tick(t.status), " ", h("code", null, t.id), ` - ${t.ms} ms`, t.status !== "P" ? h("pre.qa-err", null, t.msg) : null))));
        tb.append(h("tr", { style: { cursor: "pointer" }, on: { click: () => { det.style.display = det.style.display ? "" : "none"; } } },
          h("td.c", null, tick(cr.status)), h("td", null, h("b", null, c.id)), h("td", null, c.title), h("td", null, tcLinks(c.tcodes)),
          h("td", null, c.expected), h("td", null, cr.actual || "-"), h("td.num", null, cr.ms != null ? cr.ms + " ms" : "")), det);
      }
      const pr = runOf(p.id) || { passed: 0, total: p.cases.length };
      body.append(panel(`${p.name} (${p.module}) - ${pr.passed} of ${pr.total} passed`,
        h("p.muted", null, p.purpose),
        h("table.grid", null, h("thead", null, h("tr", null, ["", "ID", "Test case", "T-codes", "Expected result", "Actual result", "Time"]
          .map(t => h("th", null, t)))), tb)));
    }
  };
  const exec = async () => {
    msg("I", "Test run in progress - all processes on a fresh sample system ...");
    const r = await run(() => api("/api/qa/run", {}));
    if (!r) return;
    msg(r.type, r.text);
    await catalog(true);
    draw();
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec },
    { label: "Test book (PowerPoint)", onClick: () => { const a = h("a", { href: "/manuals/MM_Core_Process_Test_Book.pptx", download: "" });
      document.body.append(a); a.click(); a.remove(); } },
    { label: "e-Learning manuals", ghost: true, onClick: () => go("ZLMS") }]);
  app.append(panel(null, h("p", null, "Every process is tested end to end like a key-user acceptance test: each test case has its T-codes, " +
    "the expected result and the automatic actual result. Click a line to see the underlying automated checks.")), body);
  draw();
} });
})();
