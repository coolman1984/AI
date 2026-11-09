/* MM Core - Arabic process guide (right-to-left).
   Usage: node tools/manuals/make_manual_ar.js qa.json web/static/manuals [pptx-skill-dir]
   Output: MM_Core_Process_Guide_AR.pptx */
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const AR = require("./ar_content.js");

const [, , IN, OUT, SKILL] = process.argv;
const D = JSON.parse(fs.readFileSync(IN, "utf8"));
const RUN = D.run || { processes: [] };
const applyTheme = SKILL ? require(path.join(SKILL, "scripts/apply_theme.js")).applyTheme : null;
const THEME = {
  name: "MM Core Arabic Guide", headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: "1D2A3A", lt1: "FFFFFF", dk2: "0B2E59", lt2: "EEF2F7", accent1: "0A6ED1",
    accent2: "2E9E5B", accent3: "E9730C", accent4: "BB0000", accent5: "5B6B7D", accent6: "3BA0E6",
    hlink: "0A6ED1", folHlink: "5B6B7D" },
};
const HX = THEME.colors;
const ORDER = ["MDM", "P2P", "INV", "PTP", "O2C", "SVC", "R2R", "CTL"];
const ICON = { O2C: "FaHandshake", P2P: "FaShoppingCart", PTP: "FaIndustry", INV: "FaBoxes", R2R: "FaBalanceScale",
  CTL: "FaChartPie", MDM: "FaDatabase", SVC: "FaTools" };
const MOD_ICON = { MD: "FaDatabase", PUR: "FaShoppingCart", MM: "FaBoxes", PP: "FaIndustry", SD: "FaHandshake",
  CS: "FaTools", FI: "FaBalanceScale", CO: "FaChartPie" };
const R = { rtlMode: true, align: "right" };             // right-to-left text
const W = 13.333, M = 0.5;

async function icon(name, color) {
  const svg = RDS.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size: "256" }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
const runOf = id => (RUN.processes || []).find(p => p.id === id) || { passed: 0, total: 0 };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.rtlMode = true;
pres.theme = { headFontFace: "Arial", bodyFontFace: "Arial" };
pres.title = "دليل العمليات بالعربي - MM Core";
pres.author = "MM Core";
pres.company = "MM Core";
const C = pres.SchemeColor;

pres.defineSlideMaster({ title: "AR_DARK", background: { color: HX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: W - 2 * M, h: 1.5, fontSize: 44, bold: true,
      color: C.background1, valign: "bottom", align: "right", rtlMode: true, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.65, w: W - 2 * M, h: 1.2, fontSize: 20,
      color: "CADCFC", valign: "top", align: "right", rtlMode: true, margin: 0 }, text: "" } },
  ] });
pres.defineSlideMaster({ title: "AR_CONTENT", background: { color: HX.lt1 }, margin: [0.5, 0.5, 0.6, 0.5],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.3, w: W - 2 * M, h: 0.8, fontSize: 30, bold: true,
      color: C.text2, valign: "middle", align: "right", rtlMode: true, margin: 0 }, text: "" } },
    { text: { text: "MM Core  ·  دليل العمليات بالعربي", options: { x: 3.3, y: 7.02, w: 9.53, h: 0.3, fontSize: 10,
      color: C.accent5, align: "right", rtlMode: true, margin: 0 } } },
  ],
  slideNumber: { x: 0.5, y: 7.02, w: 0.6, h: 0.3, fontSize: 10, color: HX.accent5, align: "left" } });

function content(title, section) {
  const s = pres.addSlide({ masterName: "AR_CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}
const T = (s, text, o) => s.addText(text, { ...R, margin: 0, isTextBox: true, ...o });
function list(s, items, x, y, w, lh, fs, color, dot) {
  items.forEach((t, i) => {
    s.addShape(pres.shapes.OVAL, { x: x + w - 0.13, y: y + i * lh + 0.13, w: 0.11, h: 0.11, fill: { color: dot || color }, line: { color: dot || color } });
    s.addText(t, { ...R, margin: 0, isTextBox: true, x, y: y + i * lh, w: w - 0.25, h: lh, fontSize: fs, color, valign: "top" });
  });
}
const card = (s, x, y, w, h, color, name) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
  fill: { color: color || "F4F6F9" }, line: { color: color || "F4F6F9" }, objectName: name });
const circleIcon = async (s, x, y, d, ic, bg) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg } });
  s.addImage({ data: await icon(ic, "FFFFFF"), x: x + d * 0.25, y: y + d * 0.25, w: d * 0.5, h: d * 0.5 });
};

// ------------------------------------------------------------------ intro
async function intro() {
  const sec = "مقدمة";
  pres.addSection({ title: sec });
  const s = pres.addSlide({ masterName: "AR_DARK", sectionTitle: sec });
  s.addText("دليل العمليات بالعربي", { placeholder: "title" });
  s.addText("شرح مبسّط لكل Process في كل موديول - خطوة بخطوة، بالأرقام والقيود", { placeholder: "body" });
  const steps = D.processes.reduce((n, p) => n + p.steps.length, 0);
  [["8", "عمليات كاملة"], ["8", "موديولات"], [String(steps), "خطوة مشروحة"], [`${RUN.passed || 0}/${RUN.cases || 0}`, "اختبار ناجح"]]
    .forEach(([b, t], i) => T(s, [{ text: b, options: { fontSize: 40, bold: true, color: "FFFFFF", breakLine: true } },
      { text: t, options: { fontSize: 15, color: "CADCFC" } }], { x: W - M - 2.8 - i * 3.1, y: 5.2, w: 2.8, h: 1.2, valign: "top" }));
  T(s, "MM CORE", { x: W - M - 4, y: 0.6, w: 4, h: 0.5, fontSize: 18, bold: true, color: HX.accent6, rtlMode: false });

  // big idea
  const b = content("الفكرة الكبيرة: سيستم واحد ودفتر واحد للشركة كلها", sec);
  const cx = 3.6, cy = 4.1, rad = 2.05;
  AR.modules.forEach(([code], i) => {
    const a = (i / AR.modules.length) * 2 * Math.PI - Math.PI / 2, x = cx + rad * Math.cos(a), y = cy + rad * Math.sin(a);
    b.addShape(pres.shapes.LINE, { x: Math.min(cx, x), y: Math.min(cy, y), w: Math.abs(x - cx), h: Math.abs(y - cy),
      flipH: (x < cx) !== (y < cy), line: { color: "C9D2DC", width: 1.2 } });
  });
  b.addShape(pres.shapes.OVAL, { x: cx - 1.1, y: cy - 1.1, w: 2.2, h: 2.2, fill: { color: HX.dk2 }, line: { color: HX.dk2 } });
  T(b, "قاعدة بيانات واحدة", { x: cx - 1.0, y: cy - 0.5, w: 2.0, h: 1.0, fontSize: 16, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
  AR.modules.forEach(([code, name], i) => {
    const a = (i / AR.modules.length) * 2 * Math.PI - Math.PI / 2, x = cx + rad * Math.cos(a), y = cy + rad * Math.sin(a);
    b.addShape(pres.shapes.OVAL, { x: x - 0.5, y: y - 0.5, w: 1.0, h: 1.0, fill: { color: HX.accent1 }, line: { color: "FFFFFF", width: 2 } });
    T(b, [{ text: code, options: { bold: true, fontSize: 14, breakLine: true } }, { text: name, options: { fontSize: 10 } }],
      { x: x - 0.55, y: y - 0.4, w: 1.1, h: 0.8, color: "FFFFFF", align: "center", valign: "middle" });
  });
  const pts = [["كل حركة بتتسجل مرة واحدة", "أمين المخزن لما يستلم، الحسابات والتكاليف بيتحدثوا في نفس اللحظة - مفيش إعادة إدخال."],
    ["كل الأقسام بتشوف نفس الرقم", "المبيعات والمخازن والحسابات بيشتغلوا على نفس الأصناف والعملاء والأسعار."],
    ["كل رقم له مستند وراه", "تقدر تنزل من القوائم المالية لحد الفاتورة أو حركة المخزن اللي عملت الرقم."]];
  pts.forEach(([h1, d], i) => {
    card(b, 7.0, 1.5 + i * 1.75, 5.83, 1.5, null, "idea" + i);
    T(b, [{ text: h1, options: { bold: true, fontSize: 18, color: HX.dk2, breakLine: true } }, { text: d, options: { fontSize: 14, color: HX.dk1 } }],
      { x: 7.25, y: 1.62 + i * 1.75, w: 5.35, h: 1.3, valign: "top" });
  });

  // modules
  const m = content("الموديولات الثمانية ودور كل واحد", sec);
  for (let i = 0; i < AR.modules.length; i++) {
    const [code, name, desc] = AR.modules[i];
    const col = i % 4, row = Math.floor(i / 4), w = 2.9, x = W - M - w - col * (w + 0.243), y = 1.45 + row * 2.75;
    card(m, x, y, w, 2.5, null, "mod" + code);
    await circleIcon(m, x + w - 0.95, y + 0.25, 0.7, MOD_ICON[code], HX.dk2);
    T(m, code, { x: x + 0.2, y: y + 0.35, w: 1.4, h: 0.5, fontSize: 20, bold: true, color: HX.accent1, align: "left", rtlMode: false });
    T(m, [{ text: name, options: { bold: true, fontSize: 18, color: HX.dk2, breakLine: true } }, { text: desc, options: { fontSize: 13, color: HX.dk1 } }],
      { x: x + 0.2, y: y + 1.1, w: w - 0.4, h: 1.3, valign: "top" });
  }

  // journey
  const j = content("رحلة البضاعة والفلوس: كل خطوة وأثرها في الحسابات", sec);
  const n = AR.journey.length, gw = (W - 2 * M) / n;
  AR.journey.forEach((_, i) => {
    const x = W - M - (i + 1) * gw;
    j.addShape(pres.shapes.CHEVRON, { x: x + 0.02, y: 1.7, w: gw - 0.04, h: 1.0, flipH: true,
      fill: { color: i === n - 1 ? HX.accent2 : HX.accent1 }, line: { color: "FFFFFF" }, objectName: "chev" + i });
  });
  AR.journey.forEach(([t, d], i) => {
    const x = W - M - (i + 1) * gw;
    T(j, t, { x: x + 0.3, y: 1.7, w: gw - 0.6, h: 1.0, fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(j, d, { x: x + 0.08, y: 2.95, w: gw - 0.16, h: 1.8, fontSize: 13, color: HX.dk1, align: "center", valign: "top" });
  });
  card(j, M, 5.0, W - 2 * M, 1.5, "E9F5EE", "journeyNote");
  T(j, [{ text: "الخلاصة: ", options: { bold: true, color: HX.accent2 } },
    { text: "كل عملية في المصنع ليها أثر مالي أوتوماتيك. لو فهمت الرحلة دي، هتفهم ليه السيستم بيمنع أي خطوة تتعمل من غير اللي قبلها، وليه الحسابات والتكاليف بيطلعوا متطابقين آخر الشهر.",
      options: { color: HX.dk1 } }], { x: M + 0.3, y: 5.15, w: W - 2 * M - 0.6, h: 1.2, fontSize: 16, valign: "middle" });

  // legend
  const l = content("إزاي تقرأ رسمة العملية", sec);
  const items = [["start", "بداية العملية", "مستطيل أخضر بحواف مدورة"], ["task", "خطوة شغل", "مستطيل أبيض عليه رقم الخطوة"],
    ["dec", "قرار / فحص", "شكل معيّن - لو الإجابة نعم بنكمل"], ["end", "نهاية العملية", "مستطيل أزرق بحواف مدورة"],
    ["tc", "كود الشاشة", "بالأزرق تحت كل خطوة - تكتبه وتفتح الشاشة"], ["lane", "المسار", "كل صف = قسم أو دور مسؤول عن الخطوات اللي فيه"]];
  items.forEach(([k, t, d], i) => {
    const col = i % 2, row = Math.floor(i / 2), x = W - M - 6.0 - col * 6.33, y = 1.5 + row * 1.7;
    card(l, x, y, 6.0, 1.45, null, "lg" + k);
    const sx = x + 4.4, sy = y + 0.35;
    if (k === "start" || k === "end") l.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: sx, y: sy, w: 1.3, h: 0.75, rectRadius: 0.15,
      fill: { color: k === "start" ? "E3F1E8" : "E1ECF9" }, line: { color: "9AA7B5" } });
    if (k === "task") { l.addShape(pres.shapes.RECTANGLE, { x: sx, y: sy + 0.05, w: 1.3, h: 0.7, fill: { color: "FFFFFF" }, line: { color: "9AA7B5" } });
      l.addShape(pres.shapes.OVAL, { x: sx + 0.5, y: sy - 0.13, w: 0.3, h: 0.3, fill: { color: "8E9AA8" }, line: { color: "FFFFFF" } });
      T(l, "3", { x: sx + 0.5, y: sy - 0.13, w: 0.3, h: 0.3, fontSize: 10, bold: true, color: "FFFFFF", align: "center", valign: "middle" }); }
    if (k === "dec") l.addShape(pres.shapes.DIAMOND, { x: sx + 0.2, y: sy - 0.05, w: 0.9, h: 0.85, fill: { color: "FFFFFF" }, line: { color: "9AA7B5" } });
    if (k === "tc") T(l, "VA01", { x: sx, y: sy + 0.15, w: 1.3, h: 0.45, fontSize: 18, bold: true, color: HX.accent1, align: "center", rtlMode: false });
    if (k === "lane") { l.addShape(pres.shapes.RECTANGLE, { x: sx - 0.2, y: sy, w: 1.7, h: 0.36, fill: { color: "EAEFF5" }, line: { color: "FFFFFF" } });
      l.addShape(pres.shapes.RECTANGLE, { x: sx - 0.2, y: sy + 0.38, w: 1.7, h: 0.36, fill: { color: "F4F6F9" }, line: { color: "FFFFFF" } }); }
    T(l, [{ text: t, options: { bold: true, fontSize: 17, color: HX.dk2, breakLine: true } }, { text: d, options: { fontSize: 13, color: HX.dk1 } }],
      { x: x + 0.25, y: y + 0.2, w: 3.9, h: 1.05, valign: "middle" });
  });
}

// ------------------------------------------------------------------ process slides
function flow(p, a, sec) {
  const s = content(`${a.name} - رسمة الخطوات`, sec);
  const Y0 = 1.3, H = 5.55, nL = a.lanes.length, LH = H / nL, LW = 1.75;
  const cols = Math.max(...p.steps.map(x => x.col)) + 1, CW = (W - 2 * M - LW) / cols, BW = Math.min(1.15, CW - 0.14), BH = 0.8;
  a.lanes.forEach((ln, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: M, y: Y0 + i * LH, w: W - 2 * M, h: LH, fill: { color: i % 2 ? "F4F6F9" : "EAEFF5" },
      line: { color: "FFFFFF", width: 1.5 }, objectName: "lane" + i });
    T(s, ln, { x: W - M - LW + 0.1, y: Y0 + i * LH, w: LW - 0.25, h: LH, fontSize: 14, bold: true, color: HX.accent5, valign: "middle" });
  });
  const pos = {};
  p.steps.forEach(st => {
    const cx = W - M - LW - st.col * CW - CW / 2, cy = Y0 + st.lane * LH + LH / 2 - 0.08;
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
  p.steps.forEach(st => st.next.forEach(nx => {
    const q = pos[st.no], b = pos[nx];
    if (!b) return;
    const dia = b.st.kind === "d" ? 0.15 : 0;
    if (q.st.lane === b.st.lane) seg(q.l - (q.st.kind === "d" ? 0.15 : 0), q.cy, b.r + dia, b.cy, true);
    else { seg(q.l - (q.st.kind === "d" ? 0.15 : 0), q.cy, b.cx, q.cy, false);
      seg(b.cx, q.cy, b.cx, b.cy > q.cy ? b.t - 0.02 - dia : b.b + 0.29 + dia, true); }
  }));
  p.steps.forEach((st, i) => {
    const q = pos[st.no], d = st.kind === "d", se = st.kind === "s" || st.kind === "e";
    const w = d ? BW + 0.3 : BW, h = d ? BH + 0.3 : BH;
    s.addText(a.steps[i][0], { shape: d ? pres.shapes.DIAMOND : se ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE,
      x: q.cx - w / 2, y: q.cy - h / 2, w, h, rectRadius: se ? 0.18 : undefined,
      fill: { color: st.kind === "s" ? "E3F1E8" : st.kind === "e" ? "E1ECF9" : "FFFFFF" }, line: { color: "9AA7B5", width: 1 },
      shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 3, offset: 1, angle: 90 },
      fontSize: d ? 10 : 11, color: HX.dk1, align: "center", valign: "middle", rtlMode: true, margin: d ? 0 : 3, objectName: "step" + st.no });
    if (!se) {
      const ny = q.t - (d ? 0.48 : 0.31);
      s.addShape(pres.shapes.OVAL, { x: q.cx - 0.15, y: ny, w: 0.3, h: 0.3, fill: { color: "8E9AA8" }, line: { color: "FFFFFF" } });
      T(s, String(st.no), { x: q.cx - 0.15, y: ny, w: 0.3, h: 0.3, fontSize: 10, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    }
    T(s, st.tcode, { x: q.cx - CW / 2, y: q.cy + h / 2 + 0.03, w: CW, h: 0.24, fontSize: 10, bold: true, color: HX.accent1,
      align: "center", rtlMode: false });
  });
  s.addNotes(a.steps.map((x, i) => `${i + 1}. ${x[0]} (${p.steps[i].tcode}): ${x[1]} - ${x[2]}`).join("\n"));
}

function stepsSlides(p, a, sec) {
  const n = a.steps.length, pages = Math.ceil(n / 5), per = Math.ceil(n / pages);
  for (let k = 0; k < n; k += per) {
    const s = content(`${a.name} - شرح الخطوات${pages > 1 ? ` (${k / per + 1}/${pages})` : ""}`, sec);
    const cols = [[W - M - 3.55, 3.05, "الخطوة"], [W - M - 7.7, 4.0, "بتعمل إيه؟"], [M, 4.55, "السيستم بيعمل إيه؟"]];
    cols.forEach(([x, w, t]) => T(s, t, { x, y: 1.2, w, h: 0.35, fontSize: 13, bold: true, color: HX.accent5 }));
    a.steps.slice(k, k + per).forEach((st, i) => {
      const no = k + i + 1, y = 1.6 + i * 1.07, ps = p.steps[no - 1];
      card(s, M, y, W - 2 * M, 0.95, i % 2 ? "FFFFFF" : "F4F6F9", "row" + no);
      s.addShape(pres.shapes.OVAL, { x: W - M - 0.5, y: y + 0.25, w: 0.42, h: 0.42, fill: { color: ps.kind === "d" ? HX.accent3 : HX.dk2 },
        line: { color: "FFFFFF" } });
      T(s, String(no), { x: W - M - 0.5, y: y + 0.25, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
      T(s, [{ text: st[0], options: { bold: true, fontSize: 16, color: HX.dk2, breakLine: true } },
        { text: ps.tcode, options: { bold: true, fontSize: 12, color: HX.accent1 } }],
      { x: cols[0][0], y: y + 0.08, w: cols[0][1] - 0.6, h: 0.8, valign: "middle" });
      T(s, st[1], { x: cols[1][0], y: y + 0.08, w: cols[1][1], h: 0.8, fontSize: 14, color: HX.dk1, valign: "middle" });
      T(s, st[2], { x: cols[2][0] + 0.1, y: y + 0.08, w: cols[2][1] - 0.1, h: 0.8, fontSize: 13, color: HX.dk1, valign: "middle" });
    });
  }
}

function exampleSlide(p, a, sec) {
  const e = a.example;
  const s = content(`${a.name} - مثال بالأرقام: ${e.title}`, sec);
  const wide = !e.entries.length;
  const fw = wide ? W - 2 * M : 5.4, fx = W - M - fw, fh = wide ? 0.95 + e.facts.length * 0.55 : 4.15;
  card(s, fx, 1.35, fw, fh, null, "facts");
  T(s, "الحكاية بالأرقام (مثال توضيحي)", { x: fx + 0.3, y: 1.5, w: fw - 0.6, h: 0.45, fontSize: 17, bold: true, color: HX.dk2 });
  list(s, e.facts, fx + 0.3, 2.05, fw - 0.6, 0.55, 15, HX.dk1, HX.accent1);
  const ry = wide ? 1.35 + fh + 0.3 : 5.7;
  if (!wide) {
    const hdr = ["المبلغ", "إلى حـ (دائن)", "من حـ (مدين)"].map(t => ({ text: t, options: { bold: true, color: "FFFFFF",
      fill: { color: HX.dk2 }, align: "right", rtlMode: true } }));
    const rows = [hdr, ...e.entries.map((x, i) => {
      const fill = { color: i % 2 ? "FFFFFF" : "F4F6F9" };
      return [{ text: x[2], options: { fill, align: "left", bold: true } }, { text: x[1], options: { fill, align: "right", rtlMode: true } },
        { text: x[0], options: { fill, align: "right", rtlMode: true } }];
    })];
    T(s, "القيود اللي السيستم بيعملها لوحده", { x: M, y: 1.35, w: 6.9, h: 0.4, fontSize: 16, bold: true, color: HX.dk2 });
    s.addTable(rows, { x: M, y: 1.85, w: 6.9, colW: [1.5, 2.7, 2.7], fontSize: 13, color: HX.dk1, rowH: 0.48, valign: "middle",
      border: { type: "solid", pt: 0.5, color: "D5DCE4" }, margin: [3, 6, 3, 6], objectName: "entries" });
  }
  card(s, M, ry, W - 2 * M, 1.1, "E9F5EE", "result");
  T(s, [{ text: "النتيجة: ", options: { bold: true, color: HX.accent2 } }, { text: e.result, options: { color: HX.dk1 } }],
    { x: M + 0.3, y: ry + 0.05, w: W - 2 * M - 0.6, h: 1.0, fontSize: 15, valign: "middle" });
}

async function rulesSlide(p, a, sec) {
  const s = content(`${a.name} - الضوابط والأخطاء الشائعة والمؤشرات`, sec);
  const r = runOf(p.id);
  const cols = [["الضوابط (أفضل الممارسات)", a.controls, HX.accent2, "FaShieldAlt"], ["أخطاء شائعة لازم تتجنبها", a.mistakes, HX.accent4, "FaExclamationTriangle"],
    ["مؤشرات تتابعها", a.kpis, HX.accent1, "FaChartLine"]];
  for (let i = 0; i < 3; i++) {
    const [t, items, col, ic] = cols[i], w = 3.95, x = W - M - w - i * (w + 0.24);
    card(s, x, 1.4, w, 4.3, null, "rules" + i);
    await circleIcon(s, x + w - 0.85, 1.6, 0.6, ic, col);
    T(s, t, { x: x + 0.2, y: 1.65, w: w - 1.15, h: 0.55, fontSize: 16, bold: true, color: col, valign: "middle" });
    list(s, items, x + 0.25, 2.5, w - 0.5, 0.72, 17, HX.dk1, col);
  }
  card(s, M, 5.9, W - 2 * M, 0.85, HX.dk2, "testbar");
  T(s, [{ text: "اختبار العملية: ", options: { bold: true, color: "FFFFFF" } },
    { text: `${r.passed} من ${r.total} حالة اختبار ناجحة - وتقدر تعيد الاختبار في أي وقت من مركز الاختبارات`, options: { color: "CADCFC" } }],
  { x: 4.0, y: 5.95, w: W - M - 4.3, h: 0.75, fontSize: 15, valign: "middle" });
  T(s, "ZQA_TEST  ·  ZLMS", { x: M + 0.3, y: 5.95, w: 3.3, h: 0.75, fontSize: 18, bold: true, color: HX.accent6, align: "left",
    rtlMode: false, valign: "middle" });
}

async function processSection(p) {
  const a = AR.processes[p.id];
  const sec = a.name;
  pres.addSection({ title: sec });
  const d = pres.addSlide({ masterName: "AR_DARK", sectionTitle: sec });
  d.addText(a.name, { placeholder: "title" });
  d.addText(a.goal, { placeholder: "body" });
  await circleIcon(d, W - M - 1.1, 0.7, 1.1, ICON[p.id], HX.accent1);
  const r = runOf(p.id);
  [[a.module, "الموديول"], [String(p.steps.length), "خطوات"], [`${r.passed}/${r.total}`, "اختبارات ناجحة"]].forEach(([b, t], i) =>
    T(d, [{ text: b, options: { fontSize: 22, bold: true, color: "FFFFFF", breakLine: true } }, { text: t, options: { fontSize: 14, color: "CADCFC" } }],
      { x: W - M - 3.6 - i * 3.8, y: 5.25, w: 3.6, h: 1.0, valign: "top" }));
  T(d, "مين بيشتغل فيها: " + a.who, { x: M, y: 6.45, w: W - 2 * M, h: 0.4, fontSize: 14, color: "CADCFC" });
  flow(p, a, sec);
  stepsSlides(p, a, sec);
  exampleSlide(p, a, sec);
  await rulesSlide(p, a, sec);
}

// ------------------------------------------------------------------ closing
function closing() {
  const sec = "مراجع";
  pres.addSection({ title: sec });
  const g = content("قاموس المصطلحات", sec);
  AR.glossary.forEach(([k, v], i) => {
    const col = i < 8 ? 0 : 1, row = i % 8, x = col ? M : W / 2 + 0.12, y = 1.35 + row * 0.68, w = W / 2 - M - 0.12;
    card(g, x, y, w, 0.58, row % 2 ? "FFFFFF" : "F4F6F9", "g" + i);
    T(g, k, { x: x + 0.15, y, w: 1.9, h: 0.58, fontSize: 14, bold: true, color: HX.accent1, align: "left", rtlMode: false, valign: "middle" });
    T(g, v, { x: x + 2.1, y, w: w - 2.3, h: 0.58, fontSize: 13, color: HX.dk1, valign: "middle" });
  });
  const l = content("تتعلم بالترتيب ده", sec);
  ORDER.forEach((id, i) => {
    const a = AR.processes[id], col = i % 4, row = Math.floor(i / 4), w = 2.9, x = W - M - w - col * (w + 0.243), y = 1.45 + row * 2.05;
    card(l, x, y, w, 1.8, null, "learn" + id);
    T(l, String(i + 1), { x: x + w - 0.75, y: y + 0.2, w: 0.55, h: 0.55, fontSize: 22, bold: true, color: "FFFFFF", align: "center",
      valign: "middle", fill: { color: HX.accent1 }, shape: pres.shapes.OVAL });
    T(l, [{ text: a.name, options: { bold: true, fontSize: 15, color: HX.dk2, breakLine: true } }, { text: a.module, options: { fontSize: 12, color: HX.accent5 } }],
      { x: x + 0.2, y: y + 0.85, w: w - 0.4, h: 0.85, valign: "top" });
  });
  card(l, M, 5.75, W - 2 * M, 1.0, "E9F5EE", "learnTip");
  T(l, [{ text: "نصيحة: ", options: { bold: true, color: HX.accent2 } },
    { text: "ابدأ بالبيانات الأساسية لأنها بتغذي كل حاجة، وبعدين امشي ورا البضاعة: شراء ← مخزن ← إنتاج ← بيع، وفي الآخر الحسابات والتكاليف اللي بيجمعوا الصورة كلها.",
      options: { color: HX.dk1 } }], { x: M + 0.3, y: 5.8, w: W - 2 * M - 0.6, h: 0.9, fontSize: 15, valign: "middle" });
}

(async () => {
  await intro();
  for (const id of ORDER) await processSection(D.processes.find(p => p.id === id));
  closing();
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, "MM_Core_Process_Guide_AR.pptx");
  await pres.writeFile({ fileName: file });
  if (applyTheme) await applyTheme(file, THEME);
  console.log("wrote", file);
})().catch(e => { console.error(e); process.exit(1); });
