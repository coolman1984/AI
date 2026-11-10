/* MM Core - SAP Easy Access style menu tree (left side) */
"use strict";
(() => {
const { h, $, $$, go, S } = App;

// [folder text, children] or tcode string. "!" prefix = not in scope yet.
const MENU = [
  ["Master Data", [
    ["Material", ["MM01", "MM02", "ZJ1ID_MAT", "ZMM02_BR", "ZMM02_LF", "MM03", "ZMM03_LF", "ZEXIM"]],
    ["Material - Lists & Tools", ["MM60", "MM50", "MMSC", "MM06", "MM04"]],
    ["Customer", ["XD01", "XD02", "XD03", "ZXD03_LF", "ZJ1ID_CUS"]],
    ["Customer - Sales / Accounting", ["VD01", "VD02", "VD03", "FD01", "FD02", "FD03", "XD04", "XD05", "XD06", "XD07", "FD08", "FD09", "S_ALR_87012179"]],
    ["Vendor", ["XK01", "XK02", "ZJ1ID_VEN", "XK03", "ZXK03_LF"]],
    ["Vendor - Purchasing / Accounting", ["MK01", "MK02", "MK03", "FK01", "FK02", "FK03", "XK04", "XK05", "XK06", "XK07", "FK08", "FK09", "S_ALR_87012086"]],
    ["Overview & Governance", ["ZMD_COCKPIT", "ZMD_PROCESS"]],
    ["Customizing", ["OMS2", "OMS3", "OMS4", "OMSF", "OMSK", "CUNI", "OBD2", "OBD3", "XDN1", "XKN1", "J1ID"]],
  ]],
  ["Sales", [
    ["Master", ["XD01", "XD02", "XD03", "VD51", "VB01", "FD32"]],
    ["Sample", ["ZSD_SAMPLE", "ZSD_SAMPLES"]],
    ["Condition", ["VK11", "VK12", "VK13", "V/LD", "ZPRICE", "V/06", "V/08", "VKOA"]],
    ["SCM MGMT", ["VL10A", "VL01N", "VL02N", "VL03N", "VL06O", "VL09", "V_V2", "V.15"]],
    ["Sales Order", ["VA11", "VA13", "VA21", "VA23", "VA25", "VA01", "VA02", "VA03", "VA05"]],
    ["Billing", ["VF04", "VF01", "VF02", "VF03", "VF11", "VF05"]],
    ["Return", ["ZRETURN", "ZRET_MON"]],
    ["Invoice", ["VF31", "ZEINV", "VF05"]],
    ["SD MGMT", ["VA05", "V.02", "VKM1", "V.15", "VL06O", "VOV8"]],
    ["Next Biz", ["VC01N", "VC05", "VB21", "VB23", "ZSD_PIPE"]],
    ["SLM", ["ZSLM", "V_V2", "V.15"]],
    ["SVC Master", ["IE01", "IE03", "BGM1"]],
    ["SVC SCM", ["ZSP01", "ZWR01", "MP33"]],
    ["SVC Order", ["IW51", "IW52", "IW31", "IW41", "DP90"]],
    ["GCIS", ["F.31", "FD33", "VKM1", "ZXD03_LF"]],
    ["Performance", ["ZSD_COCKPIT", "MCTA", "MCTC", "KE30", "ZSD_PROCESS"]],
  ]],
  ["Production", [
    ["Production Master Data", ["CS01", "CS02", "CS03", "CS11", "CS15", "CR01", "CR02", "CR03", "CR05", "CA01", "CA02", "CA03", "C223", "OPL8", "SCAL"]],
    ["SOP & Demand Management", ["MC84", "MC81", "MC75", "MD61", "MD62", "MD63"]],
    ["Production Planning", ["MD01", "MD02", "MD03", "MD11", "MD12", "MD13", "MD16", "CO40", "CO41", "CM01"]],
    ["Exceptional Production", ["ZPP_REWORK", "CO07", "CO13"]],
    ["Material Availability Check", ["CO09", "COMAC", "CO24"]],
    ["Material Requirement Management", ["MD04", "MD05", "MD06", "MD07", "MD09"]],
    ["Production Execution", ["CO01", "CO02", "CO03", "CO05N", "CO11N", "CO13", "CO14", "COHV", "COOIS"]],
    ["Period-End Closing", ["KGI2", "KKAX", "KKS2", "CO88", "KKBC_ORD"]],
    ["External processing", ["ZPP_EXTOP", "ME5A", "ME59N", "ME2N"]],
    ["External Production Planning", ["ZME21_SC", "ME2O", "MBLB"]],
    ["Component Supply", ["CO27", "MF60"]],
    ["SVC Parts Forecasting", ["MP30", "MP38", "MP33"]],
    ["SVC Parts Operation", ["MB21", "MB25", "MB24"]],
    ["SVC Refurbish", ["ZREF01", "ZREF03"]],
    ["Overview", ["ZPP_COCKPIT", "ZPP_PROCESS"]],
  ]],
  ["Procurement", [
    ["[0] Overview", ["ZPUR_COCKPIT", "ZPUR_PROCESS"]],
    ["[1] Master Data & Sources", ["ME11", "ME1M", "ME01", "MEQ1", "XK01", "XK03"]],
    ["[2] Contract Management", ["ME31K", "ME3M", "ME33K"]],
    ["[3] Material Requirements Planning", ["MD01", "MD04"]],
    ["[4] Purchase Requisition", ["ME51N", "ME53N", "ME54N", "ME55", "ME5A"]],
    ["[5] RFQ / Quotation", ["ME41", "ME47", "ME49"]],
    ["[6] Purchase Order", ["ME57", "ME59N", "ME21N", "ME22N", "ME23N", "ME29N", "ME28", "ME9F"]],
    ["[7] Material Movement & Invoice", ["MIGO", "MB51", "MIRO", "F110"]],
    ["[8] Reporting", ["ME2N", "ME2L", "ME2M", "ME2K", "ME80FN", "ME65"]],
    ["[9] Customizing", ["OX08", "OME4", "OME9", "M/06", "OMGS"]],
  ]],
  ["Logistics Execution", [
    ["Materials Management", [
      ["Inventory Management", ["MIGO", "MB03", "MBST", "MB51", "MB52", "MMBE", "MB5B", "MB5K", "ZMM_COCKPIT"]],
      ["Physical Inventory", ["MI01", "MI03", "MI04", "MI11", "MI20", "MI07", "MICN"]],
      ["Period", ["MMPV", "MMRV"]],
      ["Purchasing", ["ME21N", "ME23N", "ME2M"]],
      ["Logistics Invoice Verification", ["MIRO", "MR8M", "MRBR"]],
      ["Purchasing Info & Reports", ["ME12", "ME13", "ME03", "ME1L", "ME52N", "ME61", "ME6H"]],
      ["Warehouse Management (bins)", ["LX02", "LX03", "LS01"]],
      ["Material Master", ["MM01", "MM02", "MM03"]],
      ["Valuation", ["MR21", "CKM3"]],
      ["Customizing", ["OMJJ", "ZORG", "OX10", "OX09"]],
    ]],
    ["Shipping", ["VL10A", "VL01N", "VL02N", "VL06O", "VL09"]],
    ["Stock with Subcontractor", ["ME2O", "MBLB"]],
  ]],
  ["Financial Accounting", [
    ["My Request", ["ZFI_COCKPIT", "ZFI_PROCESS"]],
    ["Accounts Receivable", [
      ["Master Records", ["XD01", "XD03", "FD32"]],
      ["Document Entry", ["FB70", "FB75", "F-28"]],
      ["Account", ["FD10N", "FBL5N", "F-32"]],
      ["Down Payment", ["F-37", "F-29", "F-39"]],
      ["Periodic Processing", ["F150"]],
      ["Information System", ["S_ALR_87012168", "FD32"]],
    ]],
    ["Accounts Payable", [
      ["Master Records", ["XK01", "XK03"]],
      ["Document Entry", ["FB60", "FB65", "MIRO", "F-53"]],
      ["Invoice Verification", ["MIRO", "MR8M", "MRBR"]],
      ["Account", ["FK10N", "FBL1N", "F-44"]],
      ["Down Payment", ["F-47", "F-48", "F-54"]],
      ["Withholding Tax", ["ZWHT", "ZWHT_RPT"]],
      ["Periodic Processing", ["F110"]],
      ["Information System", ["S_ALR_87012078"]],
    ]],
    ["!Enterprise Consolidation", []],
    ["Treasury", [
      ["Bank Accounting", ["FI12", "FF67"]],
      ["Cash Management", ["FF7A", "FF7B"]],
    ]],
    ["General Accounting", [
      ["Master Records", ["FS00", "OB08"]],
      ["Document Entry", ["F-02", "FB50", "FBS1"]],
      ["Document", ["FB03", "FB08", "FBRA", "F.81"]],
      ["Account", ["FS10N", "FBL3N", "F.13", "F-03"]],
      ["Information System", ["S_ALR_87012277", "F.01", "FAGLB03", "S_ALR_87012284", "S_ALR_87012182", "S_ALR_87012089"]],
    ]],
    ["!Investment Management", []],
    ["General Components", [
      ["Organization", ["OX02"]],
      ["Document control", ["OBA7", "OB41", "FBN1"]],
      ["Terms & tax", ["OBB8", "FTXP"]],
    ]],
    ["Closing", [
      ["Closing Cockpit", ["ZFI_PROCESS"]],
      ["Open and Close Periods", ["OB52"]],
      ["Valuate", ["FAGL_FCV", "AFAB"]],
      ["Reclassify / Clear", ["F.13", "F.81", "FBRA"]],
      ["Year End", ["F.16"]],
      ["Report", ["FB41", "F.01", "S_ALR_87012277"]],
    ]],
    ["Fixed Asset Management", [
      ["Asset", ["AS01", "AS03", "AW01N"]],
      ["Posting", ["F-90", "ABZON", "ABAVN", "F-92"]],
      ["Periodic Processing", ["AFAB", "ZAFAB_REV"]],
      ["Information System", ["AR01", "S_ALR_87011990"]],
      ["Customizing", ["OAOA"]],
    ]],
    ["!Risk Management", []],
    ["Tax Accounting", [["Tax", ["FTXP", "S_ALR_87012357", "FB41"]]]],
  ]],
  ["Controlling", [
    ["Overview", ["ZCO_COCKPIT", "ZCO_PROCESS", "ZCO_RECON"]],
    ["Cost Element Accounting", ["KA03", "KA01", "KA06"]],
    ["Cost Center Accounting", [
      ["Master Data", ["KSH1", "KS01", "KS03", "KL01", "KK01"]],
      ["Planning", ["KP06", "KP26", "KP46", "KSPI"]],
      ["Actual Postings", ["KB11N", "KB21N", "KB31N", "KSB5"]],
      ["Period-End Closing", ["KSV5", "KSU5", "KSU3"]],
      ["Information System", ["S_ALR_87013611", "S_ALR_87013625", "KSB1", "KSB2", "KSBP", "KSBT"]],
    ]],
    ["Internal Orders", ["KO01", "KO03", "KOB2", "KOK5", "KOB1", "KO88"]],
    ["Product Cost Controlling", [
      ["Product Cost Planning", ["CS03", "KZS2", "CK11N", "CK13N", "CK24"]],
      ["Cost Object Controlling", ["CO01", "CO11N", "KGI2", "KKS2", "KO88", "KKBC_ORD"]],
    ]],
    ["Profitability Analysis", ["KE11", "VF01", "KEU5", "KE30", "KE24"]],
  ]],
];

MENU.push(
  ["Marketing", [
    ["Sales Analysis", ["ZSD_COCKPIT", "MCTA", "MCTC", "ZSLM"]],
    ["Profitability (CO-PA)", ["KE30", "KE24", "KE11", "KEU5"]],
    ["Promotions & Pricing", ["VB21", "VB23", "V/LD", "ZPRICE"]],
    ["Customer Activities", ["VC01N", "VC05", "ZSD_PIPE"]],
  ]],
  ["Common", [
    ["BI (Business Intelligence)", ["ZBI", "ZBI_DASH"]],
    ["Cockpits", ["ZMM_COCKPIT", "ZSD_COCKPIT", "ZPUR_COCKPIT", "ZPP_COCKPIT", "ZFI_COCKPIT", "ZCO_COCKPIT", "ZMD_COCKPIT"]],
    ["Process Maps", ["ZPROCESS_ALL", "ZSD_PROCESS", "ZPUR_PROCESS", "ZPP_PROCESS", "ZFI_PROCESS", "ZCO_PROCESS", "ZMD_PROCESS"]],
    ["Change Documents", ["MM04", "XD04", "XK04"]],
    ["Tools", ["ZWORKPLACE", "ZCOM", "ZORG", "MB5K", "ZEINV", "ZPRINT"]],
    ["e-Learning & Quality", ["ZLMS", "ZQA_TEST", "ZQA_CHECK"]],
    ["More transactions", ["OKEON", "CS12", "MC82", "KKAO", "VKM3", "IW53"]],
  ]],
  ["Administration", [
    ["AMS - ID & Authorization", ["ZAMS", "ZINBOX", "SU53"]],
    ["User Maintenance", ["SU01", "PFCG", "SUIM"]],
    ["Monitoring", ["SM04", "SM20"]],
    ["Data Transfer (go-live)", ["ZIMPORT"]],
  ]]);
// N-ERP order of the top-level areas
const TOP = ["Sales", "Logistics Execution", "Procurement", "Production", "Financial Accounting", "Controlling",
  "Marketing", "Master Data", "Common", "Administration"];
MENU.sort((a, b) => TOP.indexOf(a[0]) - TOP.indexOf(b[0]));

// Process view: end-to-end flows across modules
const PROCESS = [
  ["Master Data Lifecycle", ["ZMD_PROCESS", "ZMD_COCKPIT", "MM01", "XK01", "XD01", "FK08", "MM06"]],
  ["Procure-to-Pay", ["ZPUR_PROCESS", "MD01", "ME51N", "ME55", "ME57", "ME21N", "ME29N", "MIGO", "MIRO", "F110"]],
  ["Order-to-Cash", ["ZSD_PROCESS", "VA21", "VA01", "VKM1", "VL01N", "VL02N", "VF01", "ZEINV", "F-28", "FBL5N"]],
  ["Returns & service", ["ZRETURN", "ZRET_MON", "IW51", "IW31", "DP90"]],
  ["Plan-to-Produce", ["ZPP_PROCESS", "MC81", "MD01", "MD04", "CO40", "CO05N", "CO27", "CO11N", "KKAX", "KKS2", "CO88"]],
  ["Subcontracting", ["MD04", "ZME21_SC", "ME2O", "MBLB", "MIGO"]],
  ["Service parts", ["MP38", "MP33", "MB21", "MB25", "ZREF01"]],
  ["Test & e-Learning", ["ZQA_TEST", "ZLMS", "ZPROCESS_ALL"]],
  ["Record-to-Report", ["ZFI_PROCESS", "OB52", "FAGL_FCV", "AFAB", "F.01", "ZCO_RECON"]],
];
const open = new Set();
let favs = [];
let showCodes = true;
let pinned = true;
try { favs = JSON.parse(localStorage.getItem("mm_favs") || "[]"); showCodes = localStorage.getItem("mm_codes") !== "0"; } catch (e) {}
let tab = "menu";

function title(code) { return (S.screens[code] || {}).title || ""; }

function leaf(code, path) {
  const known = !!S.screens[code];
  const star = h("span.star" + (favs.includes(code) ? ".on" : ""), { title: "Favorite" }, "★");
  star.addEventListener("click", e => {
    e.stopPropagation();
    favs = favs.includes(code) ? favs.filter(f => f !== code) : [...favs, code];
    try { localStorage.setItem("mm_favs", JSON.stringify(favs)); } catch (er) {}
    draw();
  });
  const n = h("div.sm-node.leaf" + (known ? "" : ".na"), { style: { paddingLeft: (8 + path * 16) + "px" },
    title: known ? `${code} - ${title(code)}` : "Not available yet", dataset: { code } },
    h("span.sm-ico", null, "•"), h("span", null, showCodes ? h("span.code", null, code) : null, showCodes ? " " : "",
      title(code) || code), star);
  if (known) n.addEventListener("click", () => {
    go(code);
    if (!pinned && window.innerWidth < 1400) $("#sidemenu").classList.add("closed");
  });
  return n;
}

function node(item, depth, filter, out) {
  if (typeof item === "string") {
    if (App.allowed && !App.allowed(item)) return;      // no authorization: hidden
    if (!filter || item.toLowerCase().includes(filter) || title(item).toLowerCase().includes(filter))
      out.push(leaf(item, depth));
    return;
  }
  let [text, kids] = item;
  const na = text.startsWith("!");
  if (na) text = text.slice(1);
  const key = text + "@" + depth;
  const sub = [];
  kids.forEach(k => node(k, depth + 1, filter, sub));
  if (filter && !sub.length && !text.toLowerCase().includes(filter)) return;
  if (!filter && !sub.length && !na) return;           // nothing authorised inside
  const isOpen = filter ? true : open.has(text) || open.has(key);
  const n = h("div.sm-node" + (depth === 0 ? ".root" : "") + (isOpen ? ".open" : "") + (na ? ".na" : ""), { style: { paddingLeft: (8 + depth * 16) + "px" },
    title: na ? "Not in scope of this version" : text },
    h("span.sm-ico", null, na ? "·" : isOpen ? "−" : "+"), h("span", null, text + (na ? " (not in scope)" : "")));
  if (!na) n.addEventListener("click", () => { open.has(key) || open.has(text) ? (open.delete(key), open.delete(text)) : open.add(key); draw(); });
  out.push(n);
  if (isOpen) out.push(...sub);
}

function draw() {
  const tree = $("#sm-tree");
  tree.innerHTML = "";
  const f = ($("#sm-filter").value || "").trim().toLowerCase();
  const out = [];
  if (tab === "fav") {
    if (!favs.length) out.push(h("div.sm-node.na", null, "Click ★ on a transaction to add it here"));
    favs.filter(c => !App.allowed || App.allowed(c)).forEach(c => out.push(leaf(c, 0)));
  } else if (tab === "process") {
    PROCESS.forEach(m => node(m, 0, f, out));
  } else MENU.forEach(m => node(m, 0, f, out));
  tree.append(...out);
  markActive();
}
function markActive() {
  const code = (location.hash.replace(/^#\/?/, "").split("?")[0] || "").toUpperCase();
  $$(".sm-node.leaf", $("#sm-tree")).forEach(n => n.classList.toggle("active", n.dataset.code === code));
}
function allFolders(items, depth, acc) {
  for (const it of items) if (typeof it !== "string") { acc.push(it[0].replace(/^!/, "") + "@" + depth); allFolders(it[1], depth + 1, acc); }
  return acc;
}

function init() {
  const side = $("#sidemenu");
  let shown = window.innerWidth > 1100;
  try { const v = localStorage.getItem("mm_menu"); if (v !== null) shown = v === "1"; } catch (e) {}
  side.classList.toggle("closed", !shown);
  $("#menu-btn").addEventListener("click", () => {
    const now = side.classList.toggle("closed");
    try { localStorage.setItem("mm_menu", now ? "0" : "1"); } catch (e) {}
  });
  $$(".sm-tab").forEach(t => t.addEventListener("click", () => {
    tab = t.dataset.tab; $$(".sm-tab").forEach(x => x.classList.toggle("active", x === t)); draw(); }));
  $("#sm-filter").addEventListener("input", draw);
  $("#sm-expand").addEventListener("click", () => { allFolders(MENU, 0, []).forEach(k => open.add(k)); draw(); });
  $("#sm-collapse").addEventListener("click", () => { open.clear(); draw(); });
  try { pinned = localStorage.getItem("mm_pin") !== "0"; } catch (e) {}
  $("#sm-pin").classList.toggle("on", pinned);
  $("#sm-pin").addEventListener("click", () => {
    pinned = !pinned; $("#sm-pin").classList.toggle("on", pinned);
    try { localStorage.setItem("mm_pin", pinned ? "1" : "0"); } catch (e) {}
    App.msg("S", pinned ? "Menu pinned - stays open" : "Menu unpinned - closes after choosing a transaction");
  });
  $("#sm-codes").addEventListener("click", () => {
    showCodes = !showCodes;
    try { localStorage.setItem("mm_codes", showCodes ? "1" : "0"); } catch (e) {}
    draw();
  });
  $("#sm-search").addEventListener("submit", e => {
    e.preventDefault();
    const v = $("#sm-search-in").value.trim().toUpperCase();
    if (!v) return;
    if (S.screens[v]) { go(v); $("#sm-search-in").value = ""; }
    else App.msg("E", `Transaction ${v} does not exist`, "00", "343");
  });
  window.addEventListener("hashchange", markActive);
  PROCESS.forEach(p => open.add(p[0] + "@0"));
  draw();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
App.MENU = MENU;
App.menuRedraw = () => { if ($("#sm-tree")) draw(); };
})();
