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
  ["Logistics", [
    ["Materials Management", [
      ["Inventory Management", ["MIGO", "MB03", "MBST", "MB51", "MB52", "MMBE", "MB5K", "ZMM_COCKPIT"]],
      ["Purchasing", ["ME21N", "ME23N", "ME2M"]],
      ["Logistics Invoice Verification", ["MIRO"]],
      ["Warehouse Management (bins)", ["LX02", "LX03", "LS01"]],
      ["Material Master", ["MM01", "MM02", "MM03"]],
      ["Valuation", ["MR21", "CKM3"]],
      ["Customizing", ["OMJJ", "ZORG", "OX10", "OX09"]],
    ]],
    ["Sales and Distribution", [
      ["Billing", ["VF01", "VF03"]],
      ["Customer master", ["XD01", "XD03"]],
    ]],
    ["Production", [["Production orders", ["CO01", "CO11N", "KOK5", "CS03"]]]],
  ]],
  ["Financial Accounting", [
    ["My Request", ["ZFI_COCKPIT", "ZFI_PROCESS"]],
    ["Accounts Receivable", [
      ["Master Records", ["XD01", "XD03", "FD32"]],
      ["Document Entry", ["FB70", "FB75", "F-28"]],
      ["Account", ["FD10N", "FBL5N"]],
      ["Periodic Processing", ["F150"]],
      ["Information System", ["S_ALR_87012168", "FD32"]],
    ]],
    ["Accounts Payable", [
      ["Master Records", ["XK01", "XK03"]],
      ["Document Entry", ["FB60", "FB65", "MIRO", "F-53"]],
      ["Account", ["FK10N", "FBL1N"]],
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
      ["Document", ["FB03", "FB08", "F.81"]],
      ["Account", ["FS10N", "FBL3N", "F.13"]],
      ["Information System", ["S_ALR_87012277", "F.01"]],
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
      ["Reclassify / Clear", ["F.13", "F.81"]],
      ["Report", ["FB41", "F.01", "S_ALR_87012277"]],
    ]],
    ["Fixed Asset Management", [
      ["Asset", ["AS01", "AS03", "AW01N"]],
      ["Posting", ["F-90", "ABZON", "ABAVN", "F-92"]],
      ["Periodic Processing", ["AFAB"]],
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
      ["Information System", ["S_ALR_87013611", "S_ALR_87013625", "KSB1", "KSBP", "KSBT"]],
    ]],
    ["Internal Orders", ["KO01", "KO03", "KOK5", "KOB1", "KO88"]],
    ["Product Cost Controlling", [
      ["Product Cost Planning", ["CS03", "KZS2", "CK11N", "CK13N", "CK24"]],
      ["Cost Object Controlling", ["CO01", "CO11N", "KGI2", "KKS2", "KO88", "KKBC_ORD"]],
    ]],
    ["Profitability Analysis", ["KE11", "VF01", "KEU5", "KE30", "KE24"]],
  ]],
];

// Process view: end-to-end flows across modules
const PROCESS = [
  ["Master Data Lifecycle", ["ZMD_PROCESS", "ZMD_COCKPIT", "MM01", "XK01", "XD01", "FK08", "MM06"]],
  ["Procure-to-Pay", ["ZPUR_PROCESS", "MD01", "ME51N", "ME55", "ME57", "ME21N", "ME29N", "MIGO", "MIRO", "F110"]],
  ["Order-to-Cash", ["XD01", "FD32", "VF01", "FBL5N", "F-28", "F150"]],
  ["Plan-to-Produce", ["ZPP_PROCESS", "MC81", "MD01", "MD04", "CO40", "CO05N", "CO27", "CO11N", "KKAX", "KKS2", "CO88"]],
  ["Subcontracting", ["MD04", "ZME21_SC", "ME2O", "MBLB", "MIGO"]],
  ["Service parts", ["MP38", "MP33", "MB21", "MB25", "ZREF01"]],
  ["Record-to-Report", ["ZFI_PROCESS", "OB52", "FAGL_FCV", "AFAB", "F.01", "ZCO_RECON"]],
];
const open = new Set();
let favs = [];
try { favs = JSON.parse(localStorage.getItem("mm_favs") || "[]"); open.add("Financial Accounting"); } catch (e) {}
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
    h("span.sm-ico", null, "•"), h("span", null, h("span.code", null, code), " ", title(code)), star);
  if (known) n.addEventListener("click", () => go(code));
  return n;
}

function node(item, depth, filter, out) {
  if (typeof item === "string") {
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
  const isOpen = filter ? true : open.has(text) || open.has(key);
  const n = h("div.sm-node" + (isOpen ? ".open" : "") + (na ? ".na" : ""), { style: { paddingLeft: (8 + depth * 16) + "px" },
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
    favs.forEach(c => out.push(leaf(c, 0)));
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
  $("#sm-search").addEventListener("submit", e => {
    e.preventDefault();
    const v = $("#sm-search-in").value.trim().toUpperCase();
    if (!v) return;
    if (S.screens[v]) { go(v); $("#sm-search-in").value = ""; }
    else App.msg("E", `Transaction ${v} does not exist`, "00", "343");
  });
  window.addEventListener("hashchange", markActive);
  open.add("Production@0");
  PROCESS.forEach(p => open.add(p[0] + "@0"));
  draw();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
App.MENU = MENU;
})();
