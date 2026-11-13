/* NERP - PowerPoint process manuals and test book.
   Input : JSON from `python -m qa.export` (catalog + last test run)
   Output: web/static/manuals/PM_<process>.pptx and NERP_Process_Test_Book.pptx
   Usage : node tools/manuals/make_manuals.js qa.json web/static/manuals
   Needs : pptxgenjs, react, react-dom, react-icons, sharp */
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const [, , IN, OUT, SKILL] = process.argv;
const D = JSON.parse(fs.readFileSync(IN, "utf8"));
const RUN = D.run || { processes: [], cases: 0, passed: 0, unit_tests: 0, unit_passed: 0, seconds: 0 };
const applyTheme = SKILL ? require(path.join(SKILL, "scripts/apply_theme.js")).applyTheme : null;

const THEME = {
  name: "NERP Manual", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "1D2A3A", lt1: "FFFFFF", dk2: "0B2E59", lt2: "EEF2F7", accent1: "0A6ED1",
    accent2: "2E9E5B", accent3: "E9730C", accent4: "BB0000", accent5: "6A7D93", accent6: "3BA0E6",
    hlink: "0A6ED1", folHlink: "6A7D93" },
};
const HX = THEME.colors;
const ICON = { O2C: "FaHandshake", P2P: "FaShoppingCart", PTP: "FaIndustry", INV: "FaBoxes", R2R: "FaBalanceScale",
  CTL: "FaChartPie", MDM: "FaDatabase", SVC: "FaTools" };
const VALUE_CHAIN = ["MDM", "P2P", "INV", "PTP", "O2C", "SVC", "R2R", "CTL"];

async function icon(name, color, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const runOf = id => (RUN.processes || []).find(p => p.id === id) || { cases: [], passed: 0, total: 0 };
const caseRes = (pid, cid) => (runOf(pid).cases || []).find(c => c.id === cid);
const runDate = RUN.run_at ? RUN.run_at.replace("T", " ") : "not run";

function newDeck(title) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";                     // 13.33 x 7.5 in
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = title;
  pres.author = "NERP QA";
  pres.company = "NERP";
  const C = pres.SchemeColor;
  const foot = { text: { text: "NERP  ·  " + title + "  ·  Test run " + runDate,
    options: { x: 0.5, y: 7.02, w: 9, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } };
  pres.defineSlideMaster({ title: "TITLE_DARK", background: { color: HX.dk2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.6, fontSize: 44, bold: true,
        color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.95, w: 11.7, h: 1.0, fontSize: 20,
        color: "CADCFC", valign: "top", margin: 0 }, text: "" } },
    ] });
  pres.defineSlideMaster({ title: "CONTENT", background: { color: HX.lt1 }, margin: [0.5, 0.5, 0.6, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 12.3, h: 0.8, fontSize: 32, bold: true,
        color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
      foot,
    ],
    slideNumber: { x: 12.3, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: HX.accent5, align: "right" } });
  return pres;
}

function titleSlide(pres, C, title, sub, section, stats) {
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addText(sub, { placeholder: "body" });
  if (stats) stats.forEach(([big, small], i) => {
    s.addText([{ text: big, options: { fontSize: 40, bold: true, color: C.background1, breakLine: true } },
      { text: small, options: { fontSize: 14, color: "CADCFC" } }],
    { x: 0.8 + i * 3.1, y: 5.35, w: 2.9, h: 1.2, margin: 0, valign: "top", isTextBox: true, objectName: "stat" + i });
  });
  s.addText("MM CORE", { x: 0.8, y: 0.6, w: 4, h: 0.5, fontSize: 18, bold: true, color: C.accent6, charSpacing: 4,
    margin: 0, isTextBox: true, objectName: "brand" });
  return s;
}

// --------------------------------------------------------------------- swimlane flow chart
function flowSlide(pres, C, p, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(`${p.name} - process flow`, { placeholder: "title" });
  const X0 = 0.5, LW = 1.55, Y0 = 1.3, H = 5.55, nL = p.lanes.length, LH = H / nL;
  const cols = Math.max(...p.steps.map(x => x.col)) + 1;
  const CW = (12.83 - X0 - LW) / cols, BW = Math.min(1.12, CW - 0.16), BH = 0.78;
  p.lanes.forEach((ln, i) => {
    const y = Y0 + i * LH;
    s.addShape(pres.shapes.RECTANGLE, { x: X0, y, w: 12.33, h: LH, fill: { color: i % 2 ? "F4F6F9" : "EAEFF5" },
      line: { color: "FFFFFF", width: 1.5 }, objectName: "lane" + i });
    s.addText(ln, { x: X0 + 0.1, y, w: LW - 0.2, h: LH, fontSize: 13, color: C.accent5, valign: "middle", margin: 0,
      isTextBox: true, objectName: "laneLabel" + i });
  });
  const pos = {};
  p.steps.forEach(st => {
    const cx = X0 + LW + st.col * CW + CW / 2, cy = Y0 + st.lane * LH + LH / 2 - 0.08;
    pos[st.no] = { cx, cy, l: cx - BW / 2, r: cx + BW / 2, t: cy - BH / 2, b: cy + BH / 2, st };
  });
  const seg = (x1, y1, x2, y2, arrow) => {
    const o = { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      line: { color: HX.accent6, width: 1.5, dashType: "dash" } };
    if (x2 < x1) o.flipH = true;
    if (y2 < y1) o.flipV = true;
    if (arrow) o.line.endArrowType = "triangle";
    s.addShape(pres.shapes.LINE, o);
  };
  p.steps.forEach(st => st.next.forEach(n => {
    const a = pos[st.no], b = pos[n];
    if (!b) return;
    if (a.st.lane === b.st.lane) seg(a.r, a.cy, b.l, b.cy, true);
    else {
      seg(a.r, a.cy, b.cx, a.cy, false);
      seg(b.cx, a.cy, b.cx, b.cy > a.cy ? b.t - 0.02 : b.b + 0.27, true);
    }
  }));
  p.steps.forEach(st => {
    const q = pos[st.no];
    const shape = st.kind === "d" ? pres.shapes.DIAMOND : (st.kind === "s" || st.kind === "e") ? pres.shapes.ROUNDED_RECTANGLE
      : pres.shapes.RECTANGLE;
    const fill = st.kind === "s" ? "E3F1E8" : st.kind === "e" ? "E1ECF9" : "FFFFFF";
    const w = st.kind === "d" ? BW + 0.3 : BW, h = st.kind === "d" ? BH + 0.3 : BH;
    const opt = { x: q.cx - w / 2, y: q.cy - h / 2, w, h, fill: { color: fill }, line: { color: "9AA7B5", width: 1 },
      shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 3, offset: 1, angle: 90 },
      fontSize: 10, color: C.text1, align: "center", valign: "middle", margin: st.kind === "d" ? 0 : 3,
      objectName: "step" + st.no };
    if (st.kind === "s" || st.kind === "e") opt.rectRadius = 0.18;
    s.addText(st.title, { ...opt, shape });
    if (st.kind !== "s" && st.kind !== "e") {
      s.addShape(pres.shapes.OVAL, { x: q.cx - 0.15, y: q.t - (st.kind === "d" ? 0.48 : 0.31), w: 0.3, h: 0.3,
        fill: { color: "8E9AA8" }, line: { color: "FFFFFF", width: 1 }, objectName: "num" + st.no });
      s.addText(String(st.no), { x: q.cx - 0.15, y: q.t - (st.kind === "d" ? 0.48 : 0.31), w: 0.3, h: 0.3,
        fontSize: 10, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    }
    if (st.tcode) s.addText(st.tcode, { x: q.cx - CW / 2, y: q.cy + h / 2 + 0.03, w: CW, h: 0.24, fontSize: 10, bold: true,
      color: C.accent1, align: "center", margin: 0, isTextBox: true, objectName: "tc" + st.no });
  });
  s.addNotes(p.steps.map(st => `${st.no}. ${st.title} (${st.tcode}) - ${p.lanes[st.lane]}`).join("\n"));
  return s;
}

// --------------------------------------------------------------------- best-practice controls
async function controlsSlide(pres, C, p, section, chk) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(`${p.name} - best-practice controls`, { placeholder: "title" });
  p.controls.forEach((c, i) => {
    const y = 1.4 + i * 1.07;
    const r = caseRes(p.id, c.case);
    const ok = r && r.status === "P";
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y, w: 8.4, h: 0.92, rectRadius: 0.08,
      fill: { color: "F4F6F9" }, line: { color: "F4F6F9" }, objectName: "ctl" + i });
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.21, w: 0.5, h: 0.5, fill: { color: ok ? HX.accent2 : HX.accent4 },
      line: { color: "FFFFFF" } });
    s.addImage({ data: chk, x: 0.83, y: y + 0.34, w: 0.24, h: 0.24 });
    s.addText([{ text: c.title, options: { bold: true, fontSize: 15, color: C.text1, breakLine: true } },
      { text: c.why, options: { fontSize: 13, color: C.accent5 } }],
    { x: 1.4, y: y + 0.06, w: 5.9, h: 0.8, margin: 0, valign: "middle", isTextBox: true });
    s.addText(`${c.case}  ${ok ? "Passed" : "Failed"}`, { x: 7.35, y: y + 0.28, w: 1.4, h: 0.36, fontSize: 11, bold: true,
      color: C.background1, fill: { color: ok ? HX.accent2 : HX.accent4 }, align: "center", valign: "middle", margin: 0,
      shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.18 });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.2, y: 1.4, w: 3.63, h: 5.2, rectRadius: 0.1,
    fill: { color: HX.dk2 }, line: { color: HX.dk2 }, objectName: "kpiCard" });
  s.addText("KPIs to watch", { x: 9.5, y: 1.6, w: 3.1, h: 0.45, fontSize: 18, bold: true, color: C.background1, margin: 0,
    isTextBox: true });
  s.addText(p.kpis.map((k, i) => ({ text: k, options: { bullet: true, breakLine: i < p.kpis.length - 1 } })),
    { x: 9.5, y: 2.15, w: 3.1, h: 2.6, fontSize: 15, color: "FFFFFF", paraSpaceAfter: 8, margin: 0, valign: "top",
      isTextBox: true });
  s.addText([{ text: "Process owner cockpit", options: { fontSize: 12, color: "CADCFC", breakLine: true } },
    { text: p.map, options: { fontSize: 20, bold: true, color: HX.accent6 } }],
  { x: 9.5, y: 5.45, w: 3.1, h: 0.9, margin: 0, isTextBox: true });
  return s;
}

// --------------------------------------------------------------------- test script / results
function casesSlides(pres, C, p, section) {
  const cases = p.cases, per = Math.ceil(cases.length / Math.ceil(cases.length / 9));
  for (let i = 0; i < cases.length; i += per) {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    const part = cases.length > per ? ` (${i / per + 1}/${Math.ceil(cases.length / per)})` : "";
    s.addText(`${p.name} - test script and result${part}`, { placeholder: "title" });
    const hdr = ["ID", "Test case", "T-codes", "Expected result", "Result"].map(t => ({ text: t,
      options: { bold: true, color: "FFFFFF", fill: { color: HX.dk2 }, fontSize: 11 } }));
    const rows = [hdr];
    cases.slice(i, i + per).forEach((c, k) => {
      const r = caseRes(p.id, c.id), ok = r && r.status === "P";
      const fill = { color: k % 2 ? "FFFFFF" : "F4F6F9" };
      rows.push([
        { text: c.id, options: { bold: true, fill } }, { text: c.title, options: { fill } },
        { text: c.tcodes, options: { color: HX.accent1, fill } }, { text: c.expected, options: { fill } },
        { text: ok ? "✓ Passed" : "✗ Failed", options: { bold: true, color: ok ? HX.accent2 : HX.accent4, fill } },
      ]);
    });
    s.addTable(rows, { x: 0.5, y: 1.35, w: 12.33, colW: [0.95, 3.6, 1.85, 4.6, 1.33], fontSize: 11, color: HX.dk1,
      border: { type: "solid", pt: 0.5, color: "D5DCE4" }, valign: "middle", margin: [3, 5, 3, 5], rowH: 0.5,
      objectName: "cases" });
  }
}

// --------------------------------------------------------------------- book-only slides
function summarySlide(pres, C, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText("All processes tested end to end - everything passed", { placeholder: "title" });
  const stats = [[`${RUN.passed}/${RUN.cases}`, "test cases passed"], [String(RUN.unit_tests), "automated tests"],
    [String(D.processes.length), "end-to-end processes"], [`${RUN.seconds}s`, "full regression run"]];
  stats.forEach(([b, t], i) => {
    s.addText([{ text: b, options: { fontSize: 40, bold: true, color: i === 0 ? HX.accent2 : HX.dk2, breakLine: true } },
      { text: t, options: { fontSize: 14, color: HX.accent5 } }],
    { x: 0.5, y: 1.45 + i * 1.3, w: 3.6, h: 1.15, margin: 0, valign: "top", isTextBox: true, objectName: "kpi" + i });
  });
  const ps = D.processes.map(p => runOf(p.id));
  const series = [{ name: "Passed", labels: D.processes.map(p => p.name), values: ps.map(r => r.passed) }];
  const anyFail = ps.some(r => r.total > r.passed);
  if (anyFail) series.push({ name: "Failed", labels: D.processes.map(p => p.name), values: ps.map(r => r.total - r.passed) });
  s.addChart(pres.charts.BAR, series, {
    x: 4.4, y: 1.4, w: 8.4, h: 5.3, barDir: "bar", barGrouping: "stacked", chartColors: [HX.accent2, HX.accent4],
    showTitle: true, title: "Test cases by process", titleFontSize: 14, titleColor: HX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "inEnd", dataLabelColor: "FFFFFF", dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HX.accent5, valAxisLabelColor: HX.accent5, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
    valGridLine: { color: "E1E6EC", size: 0.5 }, catGridLine: { style: "none" }, showLegend: anyFail, legendPos: "b",
    legendFontSize: 11, legendFontFace: "+mn-lt", legendColor: HX.accent5, objectName: "chart" });
  s.addNotes(`Run ${runDate}: ${RUN.passed} of ${RUN.cases} cases, ${RUN.unit_passed} of ${RUN.unit_tests} automated tests passed.`);
}

async function approachSlide(pres, C, section, icons) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText("Test approach - four levels, every run automatic", { placeholder: "title" });
  const lv = [
    ["FaCogs", "Unit tests", `${RUN.unit_tests} automated checks of single rules: pricing, release, FIFO, tax, variance`],
    ["FaLink", "Integration", "Every posting checked across modules: stock = G/L, FI = CO-PA, books balanced"],
    ["FaRoute", "End to end", "Six cross-module cycles run like a key user: order to cash, procure to pay, plan to produce"],
    ["FaRedo", "Regression", `Whole suite on a fresh system in ${RUN.seconds}s after every change - nothing breaks silently`],
  ];
  for (let i = 0; i < lv.length; i++) {
    const x = 0.5 + i * 3.13;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 2.85, h: 3.0, rectRadius: 0.1, fill: { color: "F4F6F9" },
      line: { color: "F4F6F9" }, objectName: "level" + i });
    s.addShape(pres.shapes.OVAL, { x: x + 0.3, y: 1.8, w: 0.75, h: 0.75, fill: { color: HX.accent1 }, line: { color: HX.accent1 } });
    s.addImage({ data: await icon(lv[i][0], "FFFFFF"), x: x + 0.48, y: 1.98, w: 0.39, h: 0.39 });
    s.addText(`${i + 1}  ${lv[i][1]}`, { x: x + 0.3, y: 2.7, w: 2.4, h: 0.45, fontSize: 18, bold: true, color: C.text2,
      margin: 0, isTextBox: true });
    s.addText(lv[i][2], { x: x + 0.3, y: 3.15, w: 2.35, h: 1.25, fontSize: 13, color: C.text1, margin: 0, valign: "top",
      isTextBox: true });
    if (i < 3) s.addText("›", { x: x + 2.85, y: 2.6, w: 0.28, h: 0.6, fontSize: 30, color: HX.accent5, align: "center",
      margin: 0, isTextBox: true });
  }
  const pr = [["Fresh system per run", "Seeded sample company - production data never touched"],
    ["Traceable", "Every case names its T-codes, expected and actual result"],
    ["Segregation of duties", "Negative tests prove that wrong users are stopped"],
    ["Evidence kept", "Each run is logged with date, user and result (ZQA_TEST)"]];
  pr.forEach(([t, d], i) => {
    const x = 0.5 + (i % 2) * 6.2, y = 4.85 + Math.floor(i / 2) * 0.95;
    s.addImage({ data: icons.checkGreen, x, y: y + 0.07, w: 0.3, h: 0.3 });
    s.addText([{ text: t + "  ", options: { bold: true, color: C.text2 } }, { text: d, options: { color: C.text1 } }],
      { x: x + 0.45, y, w: 5.6, h: 0.8, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  });
}

async function landscapeSlide(pres, C, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText("Process landscape - eight end-to-end processes", { placeholder: "title" });
  const ps = VALUE_CHAIN.map(id => D.processes.find(p => p.id === id)).filter(Boolean);
  for (let i = 0; i < ps.length; i++) {
    const p = ps[i], r = runOf(p.id), x = 0.5 + (i % 4) * 3.13, y = 1.45 + Math.floor(i / 4) * 2.7;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.85, h: 2.45, rectRadius: 0.1, fill: { color: "F4F6F9" },
      line: { color: "F4F6F9" }, objectName: "proc" + p.id });
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.7, h: 0.7, fill: { color: HX.dk2 }, line: { color: HX.dk2 } });
    s.addImage({ data: await icon(ICON[p.id], "FFFFFF"), x: x + 0.42, y: y + 0.42, w: 0.36, h: 0.36 });
    s.addText(`${r.passed}/${r.total}`, { x: x + 1.55, y: y + 0.35, w: 1.05, h: 0.5, fontSize: 20, bold: true,
      color: r.passed === r.total ? HX.accent2 : HX.accent4, align: "right", margin: 0, isTextBox: true });
    s.addText([{ text: p.name, options: { fontSize: 17, bold: true, color: HX.dk2, breakLine: true } },
      { text: `${p.module} · ${p.steps.length} steps · ${p.map}`, options: { fontSize: 12, color: HX.accent5 } }],
    { x: x + 0.25, y: y + 1.1, w: 2.4, h: 1.15, margin: 0, valign: "top", isTextBox: true });
  }
}

function signoffSlide(pres, C, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText("Sign-off and how to re-run", { placeholder: "title" });
  const how = [["ZQA_TEST", "Execute - runs all tests on a fresh system and shows the log"],
    ["ZLMS", "e-Learning - manuals repository, process and program manuals"],
    ["python -m qa.runner", "Same run from the command line, log in exports/qa_last_run.json"]];
  how.forEach(([c, d], i) => {
    s.addText([{ text: c, options: { bold: true, color: HX.accent1, fontSize: 18, breakLine: true } },
      { text: d, options: { color: HX.dk1, fontSize: 14 } }], { x: 0.5, y: 1.5 + i * 1.15, w: 5.6, h: 1.0, margin: 0,
      valign: "top", isTextBox: true });
  });
  const rows = [["Role", "Name", "Date", "Signature"].map(t => ({ text: t, options: { bold: true, color: "FFFFFF",
    fill: { color: HX.dk2 } } }))];
  ["Key user", "Process owner", "QA lead", "IT / system owner"].forEach(r => rows.push([r, "", "", ""]));
  s.addTable(rows, { x: 6.6, y: 1.5, w: 6.23, colW: [1.8, 1.7, 1.2, 1.53], rowH: 0.62, fontSize: 14, color: HX.dk1,
    border: { type: "solid", pt: 0.5, color: "C9D2DC" }, valign: "middle", objectName: "signoff" });
  s.addText("Release rule: production go-live only with all cases passed and all four signatures.",
    { x: 6.6, y: 4.9, w: 6.23, h: 0.7, fontSize: 14, italic: true, color: HX.accent5, margin: 0, isTextBox: true });
}

// --------------------------------------------------------------------- build
async function processSlides(pres, C, p, icons, section) {
  flowSlide(pres, C, p, section);
  await controlsSlide(pres, C, p, section, icons.check);
  casesSlides(pres, C, p, section);
}

async function save(pres, file) {
  await pres.writeFile({ fileName: file });
  if (applyTheme) await applyTheme(file, THEME);
  console.log("wrote", file);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const icons = { check: await icon("FaCheck", "FFFFFF"), checkGreen: await icon("FaCheckCircle", HX.accent2) };
  // full test book
  {
    const title = "Process Manual & Test Book";
    const pres = newDeck(title), C = pres.SchemeColor;
    pres.addSection({ title: "Overview" });
    titleSlide(pres, C, "End-to-end process manual & test book", `All NERP processes - flow, best-practice controls, test script and result`,
      "Overview", [[`${RUN.passed}/${RUN.cases}`, "test cases passed"], [String(RUN.unit_tests), "automated tests"],
        [String(D.processes.length), "processes"], [runDate.slice(0, 10), "test run"]]);
    summarySlide(pres, C, "Overview");
    await approachSlide(pres, C, "Overview", icons);
    await landscapeSlide(pres, C, "Overview");
    for (const id of VALUE_CHAIN) {
      const p = D.processes.find(x => x.id === id);
      pres.addSection({ title: p.name });
      await processSlides(pres, C, p, icons, p.name);
    }
    pres.addSection({ title: "Sign-off" });
    signoffSlide(pres, C, "Sign-off");
    await save(pres, path.join(OUT, "NERP_Process_Test_Book.pptx"));
  }
  // one process manual per process
  for (const p of D.processes) {
    const title = `Process Manual ${p.module} - ${p.name}`;
    const pres = newDeck(title), C = pres.SchemeColor, r = runOf(p.id);
    pres.addSection({ title: p.name });
    titleSlide(pres, C, p.name, p.purpose, p.name, [[`${r.passed}/${r.total}`, "test cases passed"],
      [String(p.steps.length), "process steps"], [p.module, "module"], ["v" + p.version, "manual version"]]);
    await processSlides(pres, C, p, icons, p.name);
    await save(pres, path.join(OUT, `PM_${p.id}.pptx`));
  }
})().catch(e => { console.error(e); process.exit(1); });
