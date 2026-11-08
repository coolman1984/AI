/* MM Core - home page in the N-ERP portal layout:
   navy banner with round app icons (favorites first), portal carousel,
   notice line and footer. The classic tile launchpad is "Workplace" (ZWORKPLACE). */
"use strict";
(() => {
const { h, $, register, go, S } = App;

// ------------------------------------------------------------------ icons (inline SVG)
const NS = "http://www.w3.org/2000/svg";
function svg(paths, size, stroke) {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", "0 0 48 48");
  s.setAttribute("width", size || 40);
  s.setAttribute("height", size || 40);
  s.setAttribute("fill", "none");
  s.setAttribute("stroke", stroke || "currentColor");
  s.setAttribute("stroke-width", "2.6");
  s.setAttribute("stroke-linecap", "round");
  s.setAttribute("stroke-linejoin", "round");
  s.innerHTML = paths;
  return s;
}
const GLYPH = {
  report: '<path d="M14 26a10 10 0 1 0 10-10"/><path d="M24 20v7h6"/><path d="M28 13h8M28 18h8M30 23h6"/>',
  person: '<circle cx="24" cy="24" r="10"/><circle cx="27" cy="22" r="3.5"/><path d="M21 31c1-4 4-5 6-5s5 1 6 5"/><path d="M15 20h5M15 25h4"/>',
  clock: '<circle cx="24" cy="24" r="11"/><path d="M24 17v8h6"/>',
  money: '<rect x="12" y="15" width="11" height="18" rx="1"/><path d="M15 20h5M15 24h5M15 28h5"/><path d="M33 15v18M37 19c0-2-2-3-4-3s-4 1-4 3 2 3 4 3 4 1 4 3-2 3-4 3-4-1-4-3"/>',
  building: '<path d="M16 34V16l9-4v22M25 34V20l8 3v11M13 34h23"/><path d="M19 20h2M19 24h2M19 28h2M28 26h2M28 30h2"/>',
  box: '<path d="M14 18l10-5 10 5v12l-10 5-10-5z"/><path d="M14 18l10 5 10-5M24 23v12"/>',
  truck: '<path d="M10 17h18v13H10zM28 22h6l4 4v4H28z"/><circle cx="16" cy="32" r="2.5"/><circle cx="33" cy="32" r="2.5"/>',
  gear: '<circle cx="24" cy="24" r="5"/><path d="M24 11v4M24 33v4M11 24h4M33 24h4M15 15l3 3M30 30l3 3M15 33l3-3M30 18l3-3"/>',
  cart: '<path d="M11 13h4l4 15h14l3-10H17"/><circle cx="20" cy="33" r="2"/><circle cx="31" cy="33" r="2"/>',
  chart: '<path d="M12 34V14M12 34h24"/><path d="M17 29l6-7 5 4 7-9"/>',
  factory: '<path d="M10 35V22l8 5v-5l8 5v-5l8 5V14h4v21z"/>',
  tag: '<path d="M12 24V13h11l13 13-11 11z"/><circle cx="18" cy="19" r="2"/>',
};
const PORTAL_ICON = {
  learn: '<rect x="9" y="12" width="26" height="18" rx="1"/><path d="M15 36h14M22 30v6"/><path d="M30 17l9-3v14l-9 3z"/>',
  cockpit: '<path d="M10 30a14 14 0 1 1 28 0"/><path d="M24 30l7-8"/><circle cx="24" cy="30" r="2"/>',
  globe: '<circle cx="24" cy="24" r="13"/><path d="M11 24h26M24 11c4 4 4 22 0 26M24 11c-4 4-4 22 0 26"/>',
  board: '<rect x="10" y="10" width="28" height="20"/><path d="M24 30v8M18 38h12M15 24l5-5 4 3 6-6"/>',
  people: '<circle cx="18" cy="17" r="4"/><circle cx="31" cy="17" r="4"/><path d="M11 29c1-4 4-6 7-6s6 2 7 6M24 29c1-4 4-6 7-6s6 2 7 6"/><path d="M15 35h18M18 32l-3 3 3 3M30 32l3 3-3 3"/>',
  doc: '<path d="M14 10h14l7 7v21H14z"/><path d="M28 10v7h7M18 24h12M18 29h12"/>',
};

// default banner apps (favorites of the menu come first)
const HERO = [
  ["ZCO_PROCESS", "Execute CO Process Map", "report"],
  ["F.01", "Financial Statement", "person"],
  ["FBL3N", "G/L Account Line Items", "clock"],
  ["KE30", "PA Allocation Result (P/L) - By Segment", "report"],
  ["MB52", "List of Warehouse Stocks on Hand", "person"],
  ["MMBE", "Display Stock Overview", "box"],
  ["KSB1", "Display Expense by Cost Center", "report"],
  ["KP06", "Maintain Expense Plan", "person"],
  ["S_ALR_87013611", "Confirm Expense Plan (Plan/Actual)", "clock"],
  ["ZFI_COCKPIT", "Investment HUB (Finance Cockpit)", "money", "green"],
  ["AW01N", "Fixed Asset HUB", "building", "green"],
  ["ZSD_COCKPIT", "Sales HUB", "chart", "green"],
  ["ZPP_COCKPIT", "Production HUB", "factory", "green"],
  ["ZPUR_COCKPIT", "Procurement HUB", "cart", "green"],
];
const PORTAL = [
  ["ZPROCESS_ALL", "Process Maps", "All end-to-end processes", "board"],
  ["ZMM_COCKPIT", "Inventory Cockpit", "Stock, bins and FIFO", "cockpit"],
  ["ZSD_COCKPIT", "Sales Cockpit", "Revenue, margin, OTIF, credit", "people"],
  ["ZPP_COCKPIT", "Production Cockpit", "Orders, capacity, WIP", "cockpit"],
  ["ZPUR_COCKPIT", "Procurement Cockpit", "Spend, savings, suppliers", "globe"],
  ["ZFI_COCKPIT", "Finance Cockpit", "Balance sheet, P&L, cash", "board"],
  ["ZCO_COCKPIT", "Controlling Cockpit", "Cost centers, orders, CO-PA", "cockpit"],
  ["ZMD_COCKPIT", "Master Data Cockpit", "Quality, risk, dead stock", "people"],
  ["ZEINV", "E-Invoice Center", "Egyptian Tax Authority (ETA)", "doc"],
  ["ZCOM", "Office Integration", "Excel, Outlook, PDF via COM", "learn"],
];
const NOTICES = [
  ["The month-end sequence: KGI2 overhead → KKAX WIP → KKS2 variances → CO88 settlement", "ZPP_PROCESS"],
  ["Credit-blocked sales orders are released only by the credit manager (VKM1)", "VKM1"],
  ["Changes of vendor bank details need a second confirmation (FK08) before payment", "FK08"],
  ["E-invoices must be generated for every invoice and credit memo (ZEINV)", "ZEINV"],
];

function heroApps() {
  let favs = [];
  try { favs = JSON.parse(localStorage.getItem("mm_favs") || "[]"); } catch (e) { favs = []; }
  const list = favs.filter(c => S.screens[c]).map(c => [c, S.screens[c].title, "report"]);
  for (const x of HERO) if (!list.find(y => y[0] === x[0]) && S.screens[x[0]]) list.push(x);
  return list;
}

function ring(glyph, green) {
  return h("span.ring" + (green ? ".green" : ""), null, svg(GLYPH[glyph] || GLYPH.report, 50, "#fff"));
}

register("HOME", { title: "Home", async render(app) {
  app.classList.add("home-main");
  // ---------------------------------------------------------------- banner
  const apps = heroApps();
  const strip = h("div.hero-strip");
  const PER_PAGE = 12;                     // 2 rows x 6 like the N-ERP workplace
  for (let i = 0; i < apps.length; i += PER_PAGE) {
    const pg = h("div.hero-page");
    for (const [code, text, glyph, color] of apps.slice(i, i + PER_PAGE)) {
      pg.append(h("a.hero-app", { href: "#/" + code, title: `${code} - ${(S.screens[code] || {}).title || text}` },
        ring(glyph, color === "green"), h("span.hero-label", null, text)));
    }
    strip.append(pg);
  }
  const left = h("button.hero-nav.left", { type: "button", title: "Back" }, "‹");
  const right = h("button.hero-nav.right", { type: "button", title: "More" }, "›");
  left.addEventListener("click", () => strip.scrollBy({ left: -strip.clientWidth, behavior: "smooth" }));
  right.addEventListener("click", () => strip.scrollBy({ left: strip.clientWidth, behavior: "smooth" }));
  const waves = svg('<path d="M0 30 C 10 20, 20 40, 48 18" stroke="rgba(120,170,255,.18)" stroke-width="0.6"/>' +
    '<path d="M0 36 C 14 26, 26 44, 48 24" stroke="rgba(120,170,255,.12)" stroke-width="0.5"/>' +
    '<path d="M0 22 C 12 30, 30 10, 48 30" stroke="rgba(120,170,255,.10)" stroke-width="0.5"/>', "100%");
  waves.setAttribute("preserveAspectRatio", "none");
  waves.classList.add("hero-waves");
  app.append(h("section.hero", null, waves, left, strip, right));

  // ---------------------------------------------------------------- portal carousel
  const per = 5;
  const pages = Math.ceil(PORTAL.length / per);
  let page = 0;
  const row = h("div.portal-row"), dots = h("div.portal-dots");
  const draw = () => {
    row.innerHTML = "";
    PORTAL.slice(page * per, page * per + per).forEach(([code, title, sub, icon]) => row.append(
      h("a.portal-item", { href: "#/" + code }, h("span.portal-icon", null, svg(PORTAL_ICON[icon], 44, "#1d2a3a")),
        h("span.portal-title", null, title), h("span.portal-sub", null, sub))));
    dots.innerHTML = "";
    for (let i = 0; i < pages; i++) {
      const d = h("span.dot" + (i === page ? ".on" : ""));
      d.addEventListener("click", () => { page = i; draw(); });
      dots.append(d);
    }
  };
  const pl = h("button.portal-nav", { type: "button" }, "‹"), pr = h("button.portal-nav", { type: "button" }, "›");
  pl.addEventListener("click", () => { page = (page - 1 + pages) % pages; draw(); });
  pr.addEventListener("click", () => { page = (page + 1) % pages; draw(); });
  draw();
  app.append(h("section.portal", null, h("div.portal-wrap", null, pl, row, pr), dots));

  // ---------------------------------------------------------------- notice + footer
  const n = NOTICES[new Date().getDate() % NOTICES.length];
  const a = h("a.notice-link", { href: "#/" + n[1] }, n[0]);
  const when = h("span.notice-date", null, new Date().toString().replace(/ \(.*\)$/, ""));
  app.append(h("section.notice", null, h("span.notice-icon", null, "🔈"), h("b", null, "Notice"), a, when),
    h("footer.home-foot", null, "© MM Core ", h("a", { href: "#/ZWORKPLACE" }, "Workplace"), " · Privacy Policy & Legal"));
} });

// "All process maps" entry of the portal
register("ZPROCESS_ALL", { title: "Process Maps (All Modules)", async render(app) {
  const maps = [["ZSD_PROCESS", "Order to Cash"], ["ZPUR_PROCESS", "Procure to Pay"], ["ZPP_PROCESS", "Plan to Produce"],
    ["ZFI_PROCESS", "Record to Report"], ["ZCO_PROCESS", "Controlling"], ["ZMD_PROCESS", "Master Data Lifecycle"]];
  app.append(h("div.portal-row.wrap", null, maps.map(([c, t]) => h("a.portal-item", { href: "#/" + c },
    h("span.portal-icon", null, svg(PORTAL_ICON.board, 44, "#1d2a3a")), h("span.portal-title", null, t), h("span.portal-sub", null, c)))));
} });
})();
