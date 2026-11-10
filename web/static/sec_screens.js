/* MM Core - AMS (ID & Authorization): self-service home, approval inbox,
   SU01 users, PFCG roles, SUIM information system, SU53, SM04 sessions, SM20 audit log */
"use strict";
(() => {
const { h, $, api, msg, run, register, go, toolbar, fmtDate, dialog, confirmBox, alv, S } = App;

const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const stCls = t => /Locked|Expired/.test(t || "") ? "neg" : "pos";
const fld = (label, el, req) => h("div.field", null, h("label" + (req ? ".req" : ""), null, label), h("div.val", null, el));
const input = (v, o) => h("input.f", Object.assign({ value: v == null ? "" : v, autocomplete: "off" }, o || {}));
const REQ = { O: "Waiting for approval", A: "Approved", R: "Rejected" };
const TYP = { ROLE: "Access request", UNLOCK: "Unlock", PWRESET: "Password reset" };

async function showPassword(r) {
  if (r && r.password) await dialog("Initial password", h("div", null,
    h("p", null, "Give this initial password to the user personally. It must be changed at the first logon:"),
    h("p.ams-pw", null, r.password)), [{ label: "OK", primary: true }]);
}

// ------------------------------------------------------------------ ZAMS - AMS home
register("ZAMS", { title: "AMS - ID & Authorization", async render(app) {
  const me = await run(() => api("/api/sec/me")); if (!me) return;
  const req = async () => {
    const roles = await run(() => api("/api/sec/roles")); if (!roles) return;
    const rs = h("select.f", null, roles.map(r => h("option", { value: r.name }, `${r.name} - ${r.text}`)));
    const vt = input("", { type: "date" }), why = h("textarea.f", { rows: 3 });
    const r = await dialog("Access Request", h("div.form-grid", { style: { gridTemplateColumns: "1fr" } },
      fld("Role", rs, true), fld("Valid to (empty = unlimited)", vt), fld("Business reason", why, true),
      h("div.note", null, "The request goes to the approval inbox (ZINBOX) of the administrator. You cannot approve your own request.")),
      [{ label: "Cancel", value: () => null }, { label: "Send request", primary: true, value: () => ({ typ: "ROLE", role: rs.value, valid_to: vt.value, reason: why.value }) }]);
    if (!r) return;
    const x = await run(() => api("/api/sec/request", r)); if (x) { msg("S", x.message); go("ZAMS"); App.render(); }
  };
  toolbar([{ label: "Access Request", primary: true, onClick: req },
    { label: "Unlock / Change Password", onClick: () => App.changePassword(false) },
    { label: "Approval inbox", onClick: () => go("ZINBOX") }]);
  if (me.dev) app.append(panel(null, h("p", null, "User logon is switched OFF for now: no password, everyone may do everything. To switch it on run tools\\Login ON.bat and start MM Core again.")));
  const head = h("div.ams-hero", null,
    h("div.ams-hero-ico", null, h("span", null, "👤"), h("b", null, "🔒")),
    h("div", null, h("div.ams-hero-t", null, "AMS"), h("div.ams-hero-s", null, "ID & Authorization")),
    h("div.ams-hero-btns", null,
      h("button.btn.primary", { type: "button", on: { click: req } }, "Access Request"),
      h("button.btn.primary", { type: "button", on: { click: () => App.changePassword(false) } }, "Unlock / Change Password")));
  const assign = alv({ rows: (me.roles || []).map(r => Object.assign({}, r, { last: me.last_login, status: me.status_text || "Available" })),
    columns: [{ key: "role", label: "Role" }, { key: "text", label: "Description" },
      { key: "valid_from", label: "From Date", type: "date" }, { key: "valid_to", label: "To Date", type: "date" },
      { key: "last", label: "Last Login" }, { key: "status", label: "Status", cls: r => stCls(r.status) }],
    emptyText: "No roles assigned - use Access Request" });
  const info = h("table.ams-info", null, [["ID", me.bname], ["Name", me.name], ["Company", me.company],
    ["Business Area", me.busarea], ["Cost Center", me.kostl], ["E-mail", me.email],
    ["Password changed", me.pw_changed], ["Valid", `${fmtDate(me.valid_from)} - ${fmtDate(me.valid_to)}`]]
    .map(([k, v]) => h("tr", null, h("th", null, k), h("td", null, v || "-"))));
  const recent = h("ul.ams-recent", null,
    [["ZAMS", "AMS Home"], ["ZINBOX", "Approval inbox"], ["SU53", "Last failed authorization check"]]
      .concat((me.recent || []).filter(t => App.allowed(t) && S.screens[t]).map(t => [t, (S.screens[t] || {}).title || t]))
      .map(([t, l]) => h("li", null, h("a", { href: "#/" + t }, `${l}`), h("span.code", null, t))));
  const reqs = alv({ rows: (me.requests || []).map(r => Object.assign({}, r, { typ_t: TYP[r.typ], st: REQ[r.status] })),
    columns: [{ key: "reqid", label: "Request", type: "int" }, { key: "typ_t", label: "Type" }, { key: "role", label: "Role" },
      { key: "reason", label: "Reason" }, { key: "created", label: "Created" }, { key: "st", label: "Status" },
      { key: "decided_by", label: "Decided by" }, { key: "note", label: "Note" }], emptyText: "No requests" });
  app.append(head, panel(`My Assignment: ${(me.roles || []).length}`, assign),
    h("div.ams-cols", null, panel("My Information", info), panel("Recent Menu", recent)),
    panel("My Requests", reqs));
} });

// ------------------------------------------------------------------ ZINBOX - approval inbox
register("ZINBOX", { title: "Approval Inbox (my work items)", async render(app) {
  const body = h("div");
  app.append(body);
  const load = async () => {
    const rows = await run(() => api("/api/sec/inbox")); if (!rows) return;
    body.innerHTML = "";
    const count = {};
    rows.forEach(r => { count[r.typ] = (count[r.typ] || 0) + 1; });
    body.append(h("div.kpis", null, Object.keys(count).length ? Object.entries(count).map(([k, v]) =>
      h("div.kpi", null, h("div.k", null, k), h("div.v", null, String(v)))) :
      h("div.kpi", null, h("div.k", null, "Work items"), h("div.v.pos", null, "0"), h("div.s", null, "nothing waiting for you"))));
    body.append(alv({ rows, title: "Waiting for my approval",
      columns: [{ key: "typ", label: "Type" }, { key: "key", label: "Object" }, { key: "text", label: "Description" },
        { key: "date", label: "Date", type: "date" }, { key: "value", label: "Value", type: "amt" },
        { key: "by", label: "Requested / entered by" },
        { key: "act", label: "Action", render: r => r.own ? h("span.neg", null, "own document (two-person rule)") :
          r.typ === "Access request" ? h("span", null,
            h("button.btn.primary", { type: "button", on: { click: () => decide(r, true) } }, "Approve"), " ",
            h("button.btn", { type: "button", on: { click: () => decide(r, false) } }, "Reject")) :
          h("a", { href: "#/" + r.tcode + "?id=" + encodeURIComponent(r.key.split("/")[0]) }, `Process in ${r.tcode}`) }],
      emptyText: "Nothing is waiting for your approval" }));
  };
  const decide = async (r, yes) => {
    const note = yes ? "" : ((await App.ask("Reject request " + r.key, [{ name: "note", label: "Reason for the rejection" }])) || {}).note;
    if (!yes && note === undefined) return;
    const x = await run(() => api("/api/sec/admin/request/decide", { reqid: r.key, approve: yes, note }));
    if (x) { msg("S", x.message); await showPassword(x); load(); }
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ SU01 - users
async function userForm(u, roles) {
  const isNew = !u.bname;
  const f = { bname: input(u.bname, { readonly: !isNew || null }), name: input(u.name), company: input(u.company),
    busarea: input(u.busarea), kostl: input(u.kostl), email: input(u.email),
    valid_from: input(u.valid_from, { type: "date" }), valid_to: input(u.valid_to && u.valid_to < "9999" ? u.valid_to : "", { type: "date" }) };
  const have = {};
  (u.roles || []).forEach(r => { have[r.role] = r; });
  const checks = roles.map(r => {
    const c = h("input", { type: "checkbox", checked: !!have[r.name] });
    const vt = input(have[r.name] && have[r.name].valid_to < "9999" ? have[r.name].valid_to : "", { type: "date" });
    return { r, c, vt, row: h("tr", null, h("td", null, c), h("td", null, h("b", null, r.name)), h("td", null, r.text), h("td", null, vt)) };
  });
  const body = h("div.su01", null,
    h("h3.ams-sub", null, "Address and logon data"),
    h("div.form-grid", null, fld("User", f.bname, true), fld("Full name", f.name, true), fld("Company", f.company),
      fld("Business area", f.busarea), fld("Cost center", f.kostl), fld("E-mail", f.email),
      fld("Valid from", f.valid_from), fld("Valid to", f.valid_to)),
    h("h3.ams-sub", null, "Roles"),
    h("table.grid.ams-roles", null, h("thead", null, h("tr", null, h("th", null, ""), h("th", null, "Role"), h("th", null, "Description"), h("th", null, "Valid to"))),
      h("tbody", null, checks.map(x => x.row))),
    isNew ? h("div.note", null, "An initial password is generated; the user must change it at the first logon.") : null);
  const r = await dialog(isNew ? "Create user (SU01)" : `Change user ${u.bname} (SU01)`, body, [
    { label: "Cancel", value: () => null }, { label: "Save", primary: true, value: () => {
      const o = {}; for (const k in f) o[k] = f[k].value;
      o.create = isNew;
      o.roles = checks.filter(x => x.c.checked).map(x => ({ role: x.r.name,
        valid_from: (have[x.r.name] || {}).valid_from || "", valid_to: x.vt.value }));
      return o; } }]);
  if (!r) return null;
  return run(() => api("/api/sec/admin/user", r));
}

register("SU01", { title: "User Maintenance", async render(app) {
  let cur = null;
  const body = h("div");
  app.append(body);
  const load = async () => {
    const rows = await run(() => api("/api/sec/admin/users")); if (!rows) return;
    body.innerHTML = "";
    const locked = rows.filter(r => r.status).length;
    body.append(h("div.kpis", null, h("div.kpi", null, h("div.k", null, "Users"), h("div.v", null, String(rows.length))),
      h("div.kpi", null, h("div.k", null, "Locked / expired"), h("div.v" + (locked ? ".neg" : ".pos"), null, String(locked)), h("div.s", null, "long-term unused after 90 days"))));
    body.append(alv({ rows, title: "Users (select a line)", onRow: r => { cur = r; msg("I", `User ${r.bname} selected`); },
      columns: [{ key: "bname", label: "User", link: r => edit(r) }, { key: "name", label: "Full name" }, { key: "busarea", label: "Business area" },
        { key: "roles", label: "Roles" }, { key: "status_text", label: "Status", cls: r => stCls(r.status_text) },
        { key: "last_login", label: "Last logon" }, { key: "valid_to", label: "Valid to", type: "date" },
        { key: "failed", label: "Failed logons", type: "int" }] }));
  };
  const roles = async () => (await run(() => api("/api/sec/admin/roles"))) || [];
  const edit = async r => {
    const u = await run(() => api("/api/sec/admin/user/" + encodeURIComponent(r.bname))); if (!u) return;
    const x = await userForm(u, await roles()); if (x) { msg("S", x.message); load(); }
  };
  const act = async (a, text) => {
    if (!cur) return msg("E", "Select a user in the list first", "01", "120");
    if (!await confirmBox(text, `${text}: ${cur.bname} - ${cur.name}?`)) return;
    const x = await run(() => api(`/api/sec/admin/user/${encodeURIComponent(cur.bname)}/${a}`, {}));
    if (x) { msg("S", x.message); await showPassword(x); cur = null; load(); }
  };
  toolbar([{ label: "Create", primary: true, onClick: async () => {
      const x = await userForm({}, await roles()); if (x) { msg("S", x.message); await showPassword(x); load(); } } },
    { label: "Change", onClick: () => cur ? edit(cur) : msg("E", "Select a user in the list first", "01", "120") },
    { label: "Lock", onClick: () => act("lock", "Lock user") },
    { label: "Unlock", onClick: () => act("unlock", "Unlock user") },
    { label: "Reset password", onClick: () => act("reset", "New initial password for") },
    { label: "Delete", danger: true, onClick: () => act("delete", "Delete user") },
    { label: "Refresh", key: "F8", onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ PFCG - roles
register("PFCG", { title: "Role Maintenance", async render(app) {
  const cat = await run(() => api("/api/sec/admin/catalog")); if (!cat) return;
  const list = h("div"), detail = h("div");
  app.append(h("div.ams-cols", null, list, detail));
  const objs = [["S_AREA", "S_AREA - Activity in an application area"]].concat(Object.entries(cat.objects).map(([k, v]) => [k, `${k} - ${v}`])).concat([["*", "* - all objects"]]);
  const show = r => {
    r = r || { name: "", text: "", tcodes: [], auths: [] };
    const name = input(r.name, { readonly: r.name ? true : null }), text = input(r.text);
    const tc = h("textarea.f", { rows: 5 }, r.tcodes.join(" "));
    const tb = h("tbody");
    const addRow = a => {
      a = a || { object: "S_AREA", value: "*", actvt: "03" };
      const o = h("select.f", null, objs.map(([v, t]) => h("option", { value: v, selected: v === a.object }, t)));
      const v = input(a.value, { list: "dl-areas" });
      const ac = h("select.f", null, Object.entries(cat.activities).map(([k, t]) => h("option", { value: k, selected: k === a.actvt }, `${k} ${t}`)));
      const tr = h("tr", null, h("td", null, o), h("td", null, v), h("td", null, ac),
        h("td", null, h("button.btn", { type: "button", on: { click: () => tr.remove() } }, "✕")));
      tr._get = () => ({ object: o.value, value: v.value || "*", actvt: ac.value });
      tb.append(tr);
    };
    (r.auths || []).forEach(addRow);
    const save = async () => {
      const auths = Array.from(tb.children).map(tr => tr._get());
      const x = await run(() => api("/api/sec/admin/role", { name: name.value, text: text.value,
        tcodes: tc.value.split(/[\s,;]+/).filter(Boolean), auths }));
      if (x) { msg("S", x.message); load(name.value.toUpperCase()); }
    };
    detail.innerHTML = "";
    detail.append(panel(r.name ? `Role ${r.name}` : "New role",
      h("div.form-grid", null, fld("Role", name, true), fld("Description", text)),
      h("h3.ams-sub", null, "Menu - transactions the role may start"),
      tc, h("div.note", null, "Transaction codes, patterns (ME*), whole menu areas (@SD @MM @PUR @PP @FI @CO @MD @CA @BC) or * for all."),
      h("h3.ams-sub", null, "Authorizations - what the role may do"),
      h("table.grid.ams-roles", null, h("thead", null, h("tr", null, h("th", null, "Object"), h("th", null, "Value (area, release code, *)"), h("th", null, "Activity"), h("th", null, ""))), tb),
      h("p", null, h("button.btn", { type: "button", on: { click: () => addRow() } }, "+ Authorization"), " ",
        h("button.btn.primary", { type: "button", on: { click: save } }, "Save role"),
        r.name ? h("span", null, " ", h("button.btn.danger", { type: "button", on: { click: async () => {
          if (!await confirmBox("Delete role", `Delete role ${r.name}?`)) return;
          const x = await run(() => api(`/api/sec/admin/role/${encodeURIComponent(r.name)}/delete`, {}));
          if (x) { msg("S", x.message); load(); } } } }, "Delete")) : null)));
  };
  const load = async sel => {
    const rows = await run(() => api("/api/sec/admin/roles")); if (!rows) return;
    list.innerHTML = "";
    list.append(alv({ rows: rows.map(r => Object.assign({}, r, { tc: r.tcodes.join(" "), n: r.tcodes.length })), title: "Roles",
      onRow: show, columns: [{ key: "name", label: "Role", link: show }, { key: "text", label: "Description" },
        { key: "tc", label: "Transactions" }, { key: "users", label: "Users", type: "int" }] }));
    const s = rows.find(r => r.name === sel); if (s) show(s); else if (!detail.innerHTML) show(rows[0]);
  };
  App.datalist("dl-areas", Object.entries(cat.areas).map(([k, v]) => [k, `${k} ${v}`]).concat([["*", "* all"]]));
  toolbar([{ label: "Create role", primary: true, onClick: () => show(null) }, { label: "Refresh", key: "F8", onClick: () => load() }]);
  load();
} });

// ------------------------------------------------------------------ SUIM - information system
register("SUIM", { title: "User Information System", async render(app, params) {
  const tc = input(params.tcode || "", { placeholder: "e.g. VKM1" }), us = input(params.user || "", { placeholder: "e.g. SALES1" });
  const out = h("div");
  app.append(panel("Who can do what", h("div.form-grid", null, fld("Transaction (users who may start it)", tc), fld("User (what the user may start)", us))), out);
  const exec = async () => {
    if (!tc.value.trim() && !us.value.trim()) return msg("E", "Enter a transaction code or a user name", "01", "120");
    const q = tc.value.trim() ? "tcode=" + encodeURIComponent(tc.value.trim()) : "user=" + encodeURIComponent(us.value.trim());
    const r = await run(() => api("/api/sec/admin/suim?" + q)); if (!r) return;
    out.innerHTML = "";
    if (r.by === "tcode") {
      out.append(alv({ rows: r.rows.map(x => Object.assign({}, x, { chg: x.change ? "Change" : "Display only" })), title: `Users with transaction ${tc.value.toUpperCase()}`,
        columns: [{ key: "bname", label: "User" }, { key: "name", label: "Name" }, { key: "roles", label: "Through role" },
          { key: "chg", label: "Activity" }, { key: "locked", label: "Lock" }] }));
    } else {
      out.append(panel(`Roles: ${r.roles.join(", ") || "-"}`, alv({ rows: r.auths, title: "Authorizations", columns: [
        { key: "object", label: "Object" }, { key: "value", label: "Value" }, { key: "actvt", label: "Activity" }] })),
      alv({ rows: r.tcodes.map(x => Object.assign({}, x, { chg: x.change ? "Change" : "Display only", title: (S.screens[x.tcode] || {}).title || "" })),
        title: `Transactions of ${us.value.toUpperCase()}`, columns: [{ key: "tcode", label: "Transaction" }, { key: "title", label: "Text" },
          { key: "areas", label: "Area" }, { key: "chg", label: "Activity" }] }));
    }
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]);
  if (params.tcode || params.user) exec();
} });

// ------------------------------------------------------------------ SU53
register("SU53", { title: "Last Failed Authorization Check", async render(app) {
  const r = await run(() => api("/api/sec/su53")); if (!r) return;
  app.append(panel(null, r.kind ? h("table.ams-info", null, [["User", S.user], ["Time", r.ts], ["Object", r.kind],
    ["Value", r.what], ["What was refused", r.detail], ["Transaction", r.tcode]].map(([k, v]) => h("tr", null, h("th", null, k), h("td", null, v || "-"))))
    : h("p", null, "No authorization check has failed for you since the server was started."),
    h("p.note", null, "Send this screen to the administrator together with an Access Request (AMS) if you need the authorization.")));
  toolbar([{ label: "Access Request", primary: true, onClick: () => go("ZAMS") }]);
} });

// ------------------------------------------------------------------ SM04 - sessions
register("SM04", { title: "User Sessions", async render(app) {
  const body = h("div"); let cur = null;
  app.append(body);
  const load = async () => {
    const rows = await run(() => api("/api/sec/admin/sessions")); if (!rows) return;
    body.innerHTML = "";
    body.append(alv({ rows, title: "Logged-on users", onRow: r => { cur = r; },
      columns: [{ key: "bname", label: "User" }, { key: "created", label: "Logged on" }, { key: "idle_min", label: "Idle (min)", type: "int" },
        { key: "ip", label: "Terminal" }, { key: "id", label: "Session" }] }));
  };
  toolbar([{ label: "End session", danger: true, onClick: async () => {
      if (!cur) return msg("E", "Select a session first", "01", "120");
      const x = await run(() => api("/api/sec/admin/session/end", { id: cur.id })); if (x) { msg("S", x.message); load(); } } },
    { label: "Refresh", key: "F8", primary: true, onClick: load }]);
  load();
} });

// ------------------------------------------------------------------ SM20 - audit log
register("SM20", { title: "Security Audit Log", async render(app) {
  const u = input(""), d1 = input(App.today(), { type: "date" }), d2 = input(App.today(), { type: "date" });
  const ac = h("select.f", null, ["", "LOGON", "LOGON_FAIL", "LOGOFF", "AUTH_FAIL", "EXECUTE", "DISPLAY", "USER_CREATE", "USER_CHANGE",
    "USER_LOCK", "USER_UNLOCK", "PW_RESET", "PW_CHANGE", "ROLE_CHANGE", "ROLE_ASSIGN", "REQUEST_ROLE", "REQUEST_APPROVE", "REQUEST_REJECT"]
    .map(x => h("option", { value: x }, x || "(all)")));
  const out = h("div");
  app.append(panel("Selection", h("div.form-grid", null, fld("User", u), fld("From", d1), fld("To", d2), fld("Event", ac))), out);
  const exec = async () => {
    const q = new URLSearchParams({ user: u.value.trim(), d1: d1.value, d2: d2.value, action: ac.value });
    const rows = await run(() => api("/api/sec/admin/audit?" + q)); if (!rows) return;
    out.innerHTML = "";
    out.append(alv({ rows, title: "Audit log", rowClass: r => /FAIL/.test(r.action) ? ".neg" : "",
      columns: [{ key: "ts", label: "Time" }, { key: "bname", label: "User" }, { key: "action", label: "Event" },
        { key: "tcode", label: "Transaction" }, { key: "object", label: "Object" }, { key: "objkey", label: "Key / function" },
        { key: "detail", label: "Detail" }, { key: "ip", label: "Terminal" }] }));
  };
  toolbar([{ label: "Execute", key: "F8", primary: true, onClick: exec }]);
  exec();
} });
})();
