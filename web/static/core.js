/* MM Core - shell, router, API, formatting, status bar, dialogs, ALV grid.
   Plain JavaScript, no libraries. */
"use strict";

const App = (() => {
  const S = { meta: null, screens: {}, current: null, materials: [],
              binLists: {}, user: "OWNER", auth: false, me: null, demo: false };
  try { S.user = localStorage.getItem("mm_user") || "OWNER"; } catch (e) {}

  // ------------------------------------------------------------------ DOM
  function h(tag, props, ...kids) {
    const parts = tag.split(/(?=[.#])/);
    const el = document.createElement(parts[0] || "div");
    for (const p of parts.slice(1)) {
      if (p[0] === ".") el.classList.add(p.slice(1)); else el.id = p.slice(1);
    }
    if (props) for (const [k, v] of Object.entries(props)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "on") for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k === "html") el.innerHTML = v;
      else if (k === "value") el.value = v;
      else if (k === "checked") el.checked = !!v;
      else if (k === "dataset") Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ------------------------------------------------------------------ format
  const nf = (min, max) => new Intl.NumberFormat("en-US",
    { minimumFractionDigits: min, maximumFractionDigits: max });
  const NF_Q = nf(0, 3), NF_A = nf(2, 2), NF_0 = nf(0, 0);
  const fmtQty = v => (v === null || v === undefined || v === "") ? "" : NF_Q.format(v);
  const fmtAmt = v => (v === null || v === undefined || v === "") ? "" : NF_A.format(v);
  const fmtInt = v => NF_0.format(v || 0);
  function fmtDate(iso) {
    if (!iso) return "";
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
  }
  function fmtShort(v) {
    const a = Math.abs(v);
    if (a >= 1e6) return (v / 1e6).toFixed(2) + " M";
    if (a >= 1e3) return (v / 1e3).toFixed(1) + " K";
    return NF_A.format(v);
  }
  const today = () => (S.meta && S.meta.today) || new Date().toISOString().slice(0, 10);

  // ------------------------------------------------------------------ API
  async function api(path, body, retried) {
    // a display screen opened without its key: ask for the key instead of calling the server
    if (/\/(\?|$)|\/\//.test(path.replace(/^\/api/, ""))) throw { type: "E", text: "Enter the key fields first", class: "00", number: "055" };
    const opt = { headers: S.auth ? {} : { "X-User": S.user }, credentials: "same-origin" };
    const tc = S.current && S.current.tcode;
    if (tc && tc !== "HOME") opt.headers["X-Tcode"] = tc;
    if (body !== undefined) {
      opt.method = "POST";
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    let res, data;
    try {
      res = await fetch(path, opt);
      data = await res.json();
    } catch (e) {
      const err = { type: "E", text: "No connection to the MM Core server. Is run.py still running?" };
      throw err;
    }
    if (res.status === 401 && data && data.logon && !retried && !path.startsWith("/api/sec/login")) {
      await logon();                       // session expired: log on again, then repeat the call
      return api(path, body, true);
    }
    if (res.status === 403 && data && data.must_change && !retried) {
      await changePassword(true);
      return api(path, body, true);
    }
    if (!res.ok) throw data;
    return data;
  }

  // ------------------------------------------------------------------ logon / authorization
  const ALWAYS_DEV = ["HOME"];
  function allowed(code) {
    if (!S.auth || !S.me) return true;
    code = String(code || "").toUpperCase();
    if (code === "HOME" || (S.me.always || ALWAYS_DEV).includes(code)) return true;
    if ((S.me.allowed || []).includes(code)) return true;
    return (S.me.patterns || []).some(p => p === "*" || p === code ||
      (p.includes("*") && new RegExp("^" + p.replace(/[.+?^${}()|[\]\\/]/g, "\\$&").replace(/\*/g, ".*") + "$").test(code)));
  }
  let logonBusy = null;
  function logon() {
    if (!logonBusy) logonBusy = logonLoop().finally(() => { logonBusy = null; });
    return logonBusy;
  }
  async function logonLoop() {
    let note = "";
    for (;;) {
      const u = h("input.f", { autocomplete: "username", value: S.lastUser || "", spellcheck: "false" });
      const p = h("input.f", { type: "password", autocomplete: "current-password" });
      const body = h("div.logon", null,
        h("div.logon-brand", null, h("span.shell-logo", null, "MM", h("i", null, "·"), "CORE"), h("span", null, "AMS - ID & Authorization")),
        h("div.form-grid", { style: { gridTemplateColumns: "1fr" } },
          h("div.field", null, h("label.req", null, "User"), h("div.val", null, u)),
          h("div.field", null, h("label.req", null, "Password"), h("div.val", null, p))),
        note ? h("div.logon-err", null, note) : null,
        S.demo ? h("div.note", null, "Demo system: ADMIN / admin, SALES1 / sales1, BUYER1 / buyer1, AP1 / ap1 ... (password = user name in small letters)") : null);
      const r = await dialog("Log on to MM Core", body, [
        { label: "Unlock / Change password", value: () => ({ unlock: u.value }) },
        { label: "Log on", primary: true, value: () => ({ bname: u.value, password: p.value }) }]);
      if (!r) continue;
      if (r.unlock !== undefined) { await unlockRequest(r.unlock); continue; }
      S.lastUser = (r.bname || "").trim().toUpperCase();
      try {
        const res = await api("/api/sec/login", { bname: r.bname, password: r.password }, true);
        await loadMe();
        if (res.must_change) await changePassword(true);
        msg("S", `Welcome ${S.me.name || S.user}`);
        return;
      } catch (e) { note = (e && e.text) || String(e); }
    }
  }
  async function unlockRequest(user) {
    const r = await ask("Self-service: unlock / password reset", Object.assign([
      { name: "bname", label: "User", value: user || "" },
      { name: "reason", label: "Reason" }], { note: "The request goes to the administrator's approval inbox (ZINBOX). A locked user is unlocked; otherwise the password is reset and the administrator gives you the new initial password." }));
    if (!r || !r.bname.trim()) return;
    try { const x = await api("/api/sec/unlock-request", r, true); await dialog("Request sent", h("p", null, x.message), [{ label: "OK", primary: true }]); }
    catch (e) { err(e); }
  }
  async function changePassword(forced) {
    for (;;) {
      const o = h("input.f", { type: "password", autocomplete: "current-password" });
      const n = h("input.f", { type: "password", autocomplete: "new-password" });
      const n2 = h("input.f", { type: "password", autocomplete: "new-password" });
      const body = h("div.form-grid", { style: { gridTemplateColumns: "1fr" } },
        forced ? h("div.note", null, "Your password is an initial password. Choose your own password now (at least 8 characters, letters and digits).") : null,
        h("div.field", null, h("label.req", null, "Current password"), h("div.val", null, o)),
        h("div.field", null, h("label.req", null, "New password"), h("div.val", null, n)),
        h("div.field", null, h("label.req", null, "Repeat new password"), h("div.val", null, n2)));
      const btns = [{ label: "Change", primary: true, value: () => ({ old: o.value, new: n.value, repeat: n2.value }) }];
      if (!forced) btns.unshift({ label: "Cancel", value: () => null });
      const r = await dialog("Change password", body, btns);
      if (!r) { if (forced) continue; return false; }
      try { const x = await api("/api/sec/password", r, true); msg("S", x.message); await loadMe(); return true; }
      catch (e) { err(e); if (!forced) await dialog("Password not changed", h("p", null, e.text || String(e)), [{ label: "OK", primary: true }]); }
    }
  }
  async function loadMe() {
    S.me = await api("/api/sec/me", undefined, true);
    S.user = S.me.bname;
    $("#status-user").textContent = S.user;
    $("#user-btn").textContent = S.user.slice(0, 2);
    $("#user-btn").title = `${S.user} - ${S.me.name || ""}`;
    if (App.menuRedraw) App.menuRedraw();
    if (S.meta) datalist("tcode-list", Object.values(S.screens).filter(s => s.tcode !== "HOME" && allowed(s.tcode))
      .map(s => [s.tcode, `${s.tcode} - ${s.title}`]));
  }
  async function logoff() {
    try { await api("/api/sec/logout", {}, true); } catch (e) {}
    S.me = null;
    $("#app").innerHTML = "";
    await logon();
    go("HOME"); render();
  }

  // ------------------------------------------------------------------ status bar
  function msg(type, text, cls, no, keep) {
    if (keep) S.keepMsg = true;
    const el = $("#status-msg");
    el.className = "status-msg " + (type || "I");
    el.innerHTML = "";
    if (!text) return;
    const ico = { S: "✓", E: "✕", W: "!", I: "i" }[type] || "i";
    el.append(h("span.ico", null, ico), h("span", null, text));
    if (cls) el.append(h("span.msgno", null, `Message no. ${cls}${no || ""}`));
  }
  function err(e) {
    if (e && e.text) msg("E", e.text, e.class, e.number);
    else msg("E", String(e && e.message || e));
  }
  async function run(fn) {
    try { return await fn(); } catch (e) { err(e); return undefined; }
  }

  // ------------------------------------------------------------------ dialogs
  function dialog(title, body, buttons) {
    return new Promise(resolve => {
      const back = $("#dialog"), box = $("#dialog-box");
      box.innerHTML = "";
      const close = v => { back.hidden = true; document.removeEventListener("keydown", onKey); resolve(v); };
      const foot = h("div.dlg-foot");
      for (const b of buttons) {
        foot.append(h("button.btn" + (b.primary ? ".primary" : ""),
          { on: { click: () => close(b.value === undefined ? b.label : b.value()) } }, b.label));
      }
      const onKey = e => {
        if (e.key === "Escape") close(null);
        if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") {
          const p = buttons.find(b => b.primary);
          if (p) { e.preventDefault(); close(p.value === undefined ? p.label : p.value()); }
        }
      };
      document.addEventListener("keydown", onKey);
      box.append(h("h3", null, title), h("div.dlg-body", null, body), foot);
      back.hidden = false;
      const first = $("input,select,textarea", box);
      if (first) first.focus();
    });
  }
  async function ask(title, fields) {
    const inputs = {};
    const body = h("div.form-grid", { style: { gridTemplateColumns: "1fr" } },
      fields.map(f => {
        inputs[f.name] = h("input.f", { value: f.value || "", placeholder: f.placeholder || "" });
        return h("div.field", null, h("label", null, f.label), h("div.val", null, inputs[f.name]));
      }), fields.note ? h("div.note", null, fields.note) : null);
    return dialog(title, body, [
      { label: "Cancel", value: () => null },
      { label: "OK", primary: true, value: () => {
        const o = {}; for (const k in inputs) o[k] = inputs[k].value; return o; } }]);
  }
  const confirmBox = (title, text, yes) => dialog(title, h("p", null, text), [
    { label: "No", value: () => false }, { label: yes || "Yes", primary: true, value: () => true }]);

  // ------------------------------------------------------------------ fields
  function field(label, input, opt) {
    opt = opt || {};
    return h("div.field", null, h("label" + (opt.req ? ".req" : ""), { title: label }, label),
      h("div.val", null, input, opt.hint ? h("span.hint", null, opt.hint) : null));
  }
  function inp(opt) {
    opt = opt || {};
    const cls = "input.f" + (opt.upper ? ".upper" : "") + (opt.w ? ".w-" + opt.w : "");
    const el = h(cls, { value: opt.value, list: opt.list, placeholder: opt.ph,
      type: opt.type, readonly: opt.readonly, name: opt.name, autocomplete: "off",
      step: opt.step, title: opt.title });
    if (opt.onchange) el.addEventListener("change", opt.onchange);
    if (opt.oninput) el.addEventListener("input", opt.oninput);
    return el;
  }
  function sel(options, value, opt) {
    opt = opt || {};
    const el = h("select.f" + (opt.w ? ".w-" + opt.w : ""));
    for (const o of options) {
      const [v, t] = Array.isArray(o) ? o : [o, o];
      el.append(h("option", { value: v, selected: String(v) === String(value) }, t));
    }
    if (opt.onchange) el.addEventListener("change", opt.onchange);
    return el;
  }
  const val = el => (el.value || "").trim();
  const up = el => val(el).toUpperCase();

  // value help lists (F4) as <datalist>
  function datalist(id, items) {
    let dl = document.getElementById(id);
    if (!dl) { dl = h("datalist", { id }); document.body.append(dl); }
    dl.innerHTML = "";
    for (const [v, t] of items) dl.append(h("option", { value: v, label: t }, t));
    return id;
  }
  function slocList(werks) {
    const id = "dl-sloc-" + (werks || "all");
    if (!document.getElementById(id))
      datalist(id, S.meta.slocs.filter(s => !werks || s.werks === werks)
        .map(s => [s.lgort, `${s.lgort} ${s.name}${werks ? "" : " (" + s.werks + ")"}`]));
    return id;
  }
  async function binList(werks, lgort) {
    const id = `dl-bin-${werks}-${lgort}`;
    if (!S.binLists[id]) {
      const bins = await api(`/api/bins?werks=${enc(werks)}&lgort=${enc(lgort)}`);
      datalist(id, bins.map(b => [b.lgpla, `${b.lgpla} - ${b.status}`]));
      S.binLists[id] = true;
    }
    return id;
  }
  async function loadMaterials() {
    S.materials = await api("/api/materials");
    datalist("dl-mat", S.materials.map(m => [m.matnr, `${m.matnr} ${m.maktx}`]));
  }
  const matText = matnr => (S.materials.find(m => m.matnr === matnr) || {}).maktx || "";
  const matUnit = matnr => (S.materials.find(m => m.matnr === matnr) || {}).meins || "";
  const enc = encodeURIComponent;
  const slocName = (w, l) => (S.meta.slocs.find(s => s.werks === w && s.lgort === l) || {}).name || "";
  const isBinManaged = (w, l) => !!(S.meta.slocs.find(s => s.werks === w && s.lgort === l) || {}).bin_managed;

  // ------------------------------------------------------------------ ALV grid
  /* alv(cfg) -> element.  cfg: {title, columns:[{key,label,type:'qty'|'amt'|
     'date'|'int'|'text', sum, width, render(row), link(row), cls(row)}], rows,
     onRow(row), rowClass(row), exportName, emptyText} */
  function alv(cfg) {
    const st = { sortKey: null, sortDir: 1, filters: {}, showFilter: false, sel: -1 };
    const wrap = h("div.alv" + (cfg.compact ? ".compact" : ""));
    const countEl = h("span.count");
    const hasSum = cfg.columns.some(c => c.sum);
    const sumBtn = tbBtn("\u2211 Totals", e => { st.noSum = !st.noSum;
      e.currentTarget.classList.toggle("on", !st.noSum); draw(); }, hasSum ? "" : "hidden");
    if (hasSum) sumBtn.classList.add("on");
    const tb = h("div.alv-toolbar", null,
      cfg.title ? h("span.title", null, cfg.title) : null,
      tbBtn("▲ Sort asc", () => { if (st.lastKey) { st.sortKey = st.lastKey; st.sortDir = 1; draw(); } }),
      tbBtn("▼ Sort desc", () => { if (st.lastKey) { st.sortKey = st.lastKey; st.sortDir = -1; draw(); } }),
      tbBtn("⨸ Filter", e => { st.showFilter = !st.showFilter;
        e.currentTarget.classList.toggle("on", st.showFilter); draw(); }),
      sumBtn,
      tbBtn("⇩ Excel", () => exportRows(cfg, visibleRows())),
      tbBtn("⎙ Print", () => window.print()),
      cfg.extraButtons || null, countEl);
    const scroll = h("div.alv-scroll");
    wrap.append(tb, scroll);
    function tbBtn(label, fn, hidden) {
      return h("button.alv-tb-btn", { on: { click: fn }, hidden: hidden || null, type: "button" }, label);
    }
    function cellText(c, r) {
      const v = r[c.key];
      if (c.type === "qty") return fmtQty(v);
      if (c.type === "amt") return fmtAmt(v);
      if (c.type === "int") return v === null || v === undefined ? "" : String(v);
      if (c.type === "date") return fmtDate(v);
      return v === null || v === undefined ? "" : String(v);
    }
    function visibleRows() {
      let rs = cfg.rows.slice();
      for (const [k, f] of Object.entries(st.filters)) {
        if (!f) continue;
        const c = cfg.columns.find(x => x.key === k);
        const needle = f.toLowerCase();
        rs = rs.filter(r => cellText(c, r).toLowerCase().includes(needle) ||
          String(r[k] ?? "").toLowerCase().includes(needle));
      }
      if (st.sortKey) {
        const k = st.sortKey, d = st.sortDir;
        rs.sort((a, b) => {
          const x = a[k], y = b[k];
          if (typeof x === "number" && typeof y === "number") return (x - y) * d;
          return String(x ?? "").localeCompare(String(y ?? ""), undefined, { numeric: true }) * d;
        });
      }
      return rs;
    }
    function draw() {
      const rs = visibleRows();
      countEl.textContent = `${rs.length} ${rs.length === 1 ? "entry" : "entries"}`;
      scroll.innerHTML = "";
      if (!cfg.rows.length) {
        scroll.append(h("div.alv-empty", null, cfg.emptyText || "No data was selected"));
        return;
      }
      const num = c => ["qty", "amt", "int"].includes(c.type);
      const head = h("tr", null, cfg.columns.map(c => h("th" + (num(c) ? ".num" : ""),
        { style: c.width ? { minWidth: c.width + "px" } : null, title: c.tip || c.label,
          on: { click: () => {
            st.lastKey = c.key;
            if (st.sortKey === c.key) st.sortDir = -st.sortDir; else { st.sortKey = c.key; st.sortDir = 1; }
            draw(); } } },
        c.label, st.sortKey === c.key ? h("span.sort", null, st.sortDir > 0 ? "▲" : "▼") : null)));
      const thead = h("thead", null, head);
      if (st.showFilter) {
        thead.append(h("tr.filter", null, cfg.columns.map(c => {
          const i = h("input", { value: st.filters[c.key] || "", placeholder: "⌕" });
          i.addEventListener("input", () => { st.filters[c.key] = i.value; drawBody(); });
          return h("th", null, i);
        })));
      }
      const tbody = h("tbody"), tfoot = h("tfoot");
      const table = h("table.grid", null, thead, tbody, tfoot);
      scroll.append(table);
      function drawBody() {
        const rows = visibleRows();
        countEl.textContent = `${rows.length} ${rows.length === 1 ? "entry" : "entries"}`;
        tbody.innerHTML = ""; tfoot.innerHTML = "";
        rows.forEach((r, i) => {
          const tr = h("tr" + (cfg.rowClass ? cfg.rowClass(r) : ""));
          for (const c of cfg.columns) {
            let cls = num(c) ? "num" : "";
            if (c.cls) cls += " " + (c.cls(r) || "");
            if (c.signed && typeof r[c.key] === "number") cls += r[c.key] < 0 ? " neg" : "";
            const td = h("td", { class: cls.trim() || null });
            if (c.render) td.append(c.render(r));
            else if (c.link) {
              const a = h("a", { href: "#" }, cellText(c, r));
              a.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); c.link(r); });
              td.append(a);
            } else td.textContent = cellText(c, r);
            tr.append(td);
          }
          tr.addEventListener("click", () => {
            $$("tr.sel", tbody).forEach(x => x.classList.remove("sel"));
            tr.classList.add("sel");
            if (cfg.onRow) cfg.onRow(r);
          });
          if (cfg.onDbl) tr.addEventListener("dblclick", () => cfg.onDbl(r));
          tbody.append(tr);
        });
        if (cfg.columns.some(c => c.sum) && !st.noSum && rows.length) {
          const unitKey = cfg.sumUnitKey;
          const units = unitKey ? new Set(rows.map(r => r[unitKey])) : null;
          tfoot.append(h("tr", null, cfg.columns.map((c, i) => {
            if (c.sum) {
              if (c.type === "qty" && units && units.size > 1) return h("td.num", { title: "Mixed units" }, "*");
              const s = rows.reduce((a, r) => a + (Number(r[c.key]) || 0), 0);
              return h("td.num", null, c.type === "qty" ? fmtQty(s) : c.type === "int" ? String(s) : fmtAmt(s));
            }
            return h("td", null, i === 0 ? "∑" : "");
          })));
        }
      }
      drawBody();
    }
    draw();
    wrap.update = rows => { cfg.rows = rows; draw(); };
    return wrap;
  }

  async function exportRows(cfg, rows) {
    const cols = cfg.columns.filter(c => !c.noExport);
    const header = cols.map(c => c.label);
    const data = rows.map(r => cols.map(c => {
      const v = c.exportValue ? c.exportValue(r) : r[c.key];
      return v === undefined ? null : v;
    }));
    const name = cfg.exportName || cfg.title || "export";
    if (S.meta && S.meta.com && S.meta.com.available) {
      const res = await run(() => api("/api/office/excel-export",
        { title: name, header, rows: data }));
      if (res) { msg("S", res.message); return; }
      msg("W", "Excel (COM) failed - downloading a CSV file instead");
    }
    const q = v => {
      if (v === null || v === undefined) return "";
      const s = String(v);
      return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const csv = "﻿" + [header, ...data].map(r => r.map(q).join(",")).join("\r\n");
    const a = h("a", { href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
      download: name.replace(/\W+/g, "_") + ".csv" });
    document.body.append(a); a.click(); a.remove();
    msg("S", `${rows.length} rows downloaded as CSV (open with Excel)`);
  }

  // ------------------------------------------------------------------ router
  function register(tcode, def) { def.tcode = tcode; S.screens[tcode] = def; }
  function parseHash() {
    const raw = location.hash.replace(/^#\/?/, "");
    const [code, qs] = raw.split("?");
    const params = {};
    new URLSearchParams(qs || "").forEach((v, k) => { params[k] = v; });
    return { code: (code || "").toUpperCase(), params };
  }
  function go(tcode, params) {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    const target = "#/" + tcode + qs;
    if (location.hash === target) render(); else location.hash = target;
  }
  function toolbar(buttons) {
    const tb = $("#app-toolbar");
    tb.innerHTML = "";
    for (const b of buttons || []) {
      if (!b) continue;
      tb.append(h("button.btn" + (b.primary ? ".primary" : "") + (b.ghost ? ".ghost" : "") +
        (b.danger ? ".danger" : ""), { on: { click: b.onClick }, title: b.title || null,
          disabled: b.disabled || null, type: "button" },
        b.label, b.key ? h("span.key", null, b.key) : null));
    }
    S.keys = {};
    for (const b of buttons || []) if (b && b.key) S.keys[b.key] = b.onClick;
  }
  async function render() {
    const { code, params } = parseHash();
    const app = $("#app");
    app.className = "";
    app.innerHTML = "";
    const def = S.screens[code || "HOME"];
    if (!def) {
      msg("E", `Transaction ${code} does not exist`, "00", "343");
      S.keepMsg = true;
      return go("HOME");
    }
    if (!allowed(code || "HOME")) {
      msg("E", `No authorization for transaction ${code}`, "00", "077");
      S.keepMsg = true;
      return go("HOME");
    }
    S.current = def;
    if (S.keepMsg) S.keepMsg = false; else msg("", "");
    const home = !code || code === "HOME";
    $("#titlebar").hidden = home;
    $("#screen-title").textContent = def.title + (home ? "" : "");
    $("#status-tcode").textContent = home ? "" : def.tcode;
    document.title = home ? "MM Core" : `${def.tcode} - ${def.title}`;
    toolbar([]);
    try { await def.render(app, params); } catch (e) { err(e); }
  }
  function okcode(text) {
    let t = text.trim().toUpperCase();
    if (!t) return;
    t = t.replace(/^\/[NO]/, "");
    if (t === "" || t === "HOME" || t === "/N") return go("HOME");
    const [code, arg] = t.split(/\s+/);
    if (!S.screens[code]) return msg("E", `Transaction ${code} does not exist`, "00", "343");
    if (!allowed(code)) return msg("E", `No authorization for transaction ${code}`, "00", "077");
    msg("", "");
    go(code, arg ? { id: arg } : undefined);
  }

  // ------------------------------------------------------------------ start
  async function start() {
    $("#status-user").textContent = S.user;
    $("#user-btn").textContent = S.user.slice(0, 2);
    $("#user-btn").addEventListener("click", async () => {
      if (S.auth) {
        const r = await dialog(`${S.user} - ${(S.me && S.me.name) || ""}`, h("p", null, "Roles: " +
          ((S.me && S.me.roles || []).map(x => x.role).join(", ") || "-")), [
          { label: "Log off", value: () => "off" }, { label: "Change password", value: () => "pw" },
          { label: "AMS", primary: true, value: () => "ams" }]);
        if (r === "off") return logoff();
        if (r === "pw") return changePassword(false);
        if (r === "ams") return go("ZAMS");
        return;
      }
      const r = await ask("User", [{ name: "u", label: "User name", value: S.user }]);
      if (r && r.u.trim()) {
        S.user = r.u.trim().toUpperCase().slice(0, 12);
        try { localStorage.setItem("mm_user", S.user); } catch (e) {}
        $("#status-user").textContent = S.user;
        $("#user-btn").textContent = S.user.slice(0, 2);
      }
    });
    $("#okcode-form").addEventListener("submit", e => {
      e.preventDefault();
      const i = $("#okcode"); okcode(i.value); i.value = ""; i.blur();
    });
    $("#back-btn").addEventListener("click", () => history.length > 1 ? history.back() : go("HOME"));
    document.addEventListener("keydown", e => {
      const k = e.key === "F8" ? "F8" : e.key === "F3" ? "F3" :
        (e.ctrlKey && (e.key === "s" || e.key === "S")) ? "Ctrl+S" : null;
      if (!k) return;
      if (!$("#dialog").hidden) return;
      e.preventDefault();
      if (k === "F3") return history.back();
      if (S.keys && S.keys[k]) S.keys[k]();
    });
    // session window of the desktop client (MM Core Logon / Easy Access): ?session=1&user=..&sso=..
    const sp = new URLSearchParams(location.search);
    if (sp.get("session") === "1") {
      document.body.classList.add("gui-session");
      S.session = true;
      if (sp.get("user")) {
        S.user = sp.get("user").toUpperCase().slice(0, 12);
        try { localStorage.setItem("mm_user", S.user); } catch (e) {}
        $("#status-user").textContent = S.user; $("#user-btn").textContent = S.user.slice(0, 2);
      }
      if (sp.get("sso")) { try { await api("/api/sec/sso", { token: sp.get("sso") }, true); } catch (e) {} }
      history.replaceState(null, "", location.pathname + "?session=1" + location.hash);
    }
    try {
      const st = await api("/api/sec/status", undefined, true);
      S.auth = !!st.auth; S.demo = !!st.demo;
      if (S.auth) {
        try { await loadMe(); } catch (e) { if (e && e.logon) await logon(); else throw e; }
      }
      S.meta = await api("/api/meta");
      await loadMaterials();
    } catch (e) { err(e); return; }
    datalist("dl-plant", S.meta.plants.map(p => [p.werks, `${p.werks} ${p.name}`]));
    datalist("dl-kostl", S.meta.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
    datalist("dl-lifnr", S.meta.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name}`]));
    datalist("dl-bwart", S.meta.movement_types.map(m => [m.bwart, `${m.bwart} ${m.text}`]));
    datalist("tcode-list", Object.values(S.screens).filter(s => s.tcode !== "HOME" && allowed(s.tcode))
      .map(s => [s.tcode, `${s.tcode} - ${s.title}`]));
    window.addEventListener("hashchange", render);
    lifecycle();
    render();
  }
  // tell the server this tab is open; the server stops when all tabs are closed
  function lifecycle() {
    const tab = Math.random().toString(36).slice(2) + Date.now().toString(36);
    const ping = () => fetch("/api/ping", { method: "POST", body: JSON.stringify({ tab }),
      headers: { "Content-Type": "application/json" } }).catch(() => {});
    ping();
    setInterval(ping, 10000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) ping(); });
    window.addEventListener("pagehide", () => {
      navigator.sendBeacon("/api/bye", new Blob([JSON.stringify({ tab })], { type: "text/plain" }));
    });
    $("#power-btn").addEventListener("click", async () => {
      if (!await confirmBox("Stop MM Core", "Stop the MM Core server now? All data is already saved.", "Stop")) return;
      try { await api("/api/shutdown", {}); } catch (e) {}
      $("#titlebar").hidden = true;
      toolbar([]);
      $("#app").innerHTML = "";
      $("#app").append(h("div.stopped", null, h("h2", null, "MM Core is stopped"),
        h("p.muted", null, "All data is saved. You can close this tab. To start again, double-click \u201CStart MM Core\u201D.")));
      msg("S", "Server stopped");
    });
  }
  async function refreshMeta() {
    S.meta = await api("/api/meta");
    S.binLists = {};
    $$("datalist[id^=dl-sloc-]").forEach(d => d.remove());
    datalist("dl-plant", S.meta.plants.map(p => [p.werks, `${p.werks} ${p.name}`]));
    datalist("dl-kostl", S.meta.cost_centers.map(k => [k.kostl, `${k.kostl} ${k.name}`]));
    datalist("dl-lifnr", S.meta.vendors.map(v => [v.lifnr, `${v.lifnr} ${v.name}`]));
  }

  return { S, h, $, $$, api, msg, err, run, dialog, ask, confirmBox, field, inp, sel,
    val, up, datalist, slocList, binList, loadMaterials, matText, matUnit, slocName,
    isBinManaged, alv, exportRows, register, go, toolbar, render, start, refreshMeta,
    allowed, logon, logoff, changePassword, unlockRequest, loadMe,
    fmtQty, fmtAmt, fmtInt, fmtDate, fmtShort, today, enc };
})();
