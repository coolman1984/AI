/* NERP - daily briefing and alerts to the mobile.
   ZNOTIF: my messages (in-app inbox) and my subscriptions (Telegram / e-mail / WhatsApp / only NERP).
   ZNOTIF_CONF: channels (bot token, SMTP, WhatsApp Business), all subscriptions, run now, log. */
"use strict";
(() => {
const { h, api, msg, run, ask, confirmBox, field, inp, sel, val, alv, register, go, toolbar } = App;
const panel = (title, ...body) => h("div.panel", null, title ? h("h2", null, title) : null, h("div.panel-body", null, ...body));
const grid = (...f) => h("div.form-grid", null, ...f);
const note = t => h("div.note", null, t);
const badge = (t, cls) => h("span.badge" + (cls ? "." + cls : ""), null, t);
const btn = (t, fn) => h("button.btn", { type: "button", on: { click: fn } }, t);
const STAT = { sent: ["Sent", "U"], inapp: ["In NERP", ""], failed: ["Failed", "B"] };
const CSS = `.nt-msg{border:1px solid #dde4ee;border-radius:12px;padding:10px 14px;margin-bottom:8px;background:#fff;unicode-bidi:plaintext}
.nt-msg.new{border-left:4px solid #0b5cad;background:#f5f9ff}.nt-msg h4{margin:0 0 4px;font-size:15px}.nt-msg .b{white-space:pre-line;font-size:14px;line-height:1.6;color:#2a3a52}
.nt-msg .m{font-size:12px;color:#7a889c;margin-top:6px;display:flex;gap:10px;align-items:center}.nt-help li{margin:4px 0}`;
const style = () => { if (!document.getElementById("nt-css")) { const s = document.createElement("style"); s.id = "nt-css"; s.textContent = CSS; document.head.append(s); } };
const boldify = t => String(t).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");

function subForm(meta, s, onSave, admin) {
  const f = { channel: sel(Object.entries(meta.channels), s ? s.channel : "telegram"), address: inp({ value: s ? s.address : "", w: "l", ph: "Telegram chat id / e-mail / 2010…" }),
    time: inp({ value: s ? s.daily_time : "08:00", w: "s" }), daily: sel([["1", "Yes - every day"], ["0", "No"]], s && !s.daily ? "0" : "1"),
    user: admin ? inp({ value: s ? s.usnam : "", w: "m", upper: true }) : null };
  const cats = Object.entries(meta.cats).map(([k, t]) => { const c = h("input", { type: "checkbox" }); c.checked = s ? s.cats.includes(k) : true; c.dataset.k = k;
    return h("label", { style: { marginRight: "14px", whiteSpace: "nowrap" } }, c, " " + t); });
  return h("div", null, grid(...(admin ? [field("User", f.user)] : []), field("Send to", f.channel), field("Address", f.address), field("Daily briefing", f.daily), field("At (HH:MM)", f.time)),
    h("div", { style: { margin: "8px 0" } }, h("b", null, "Alerts: "), ...cats),
    btn(s ? "Save" : "Add subscription", async () => {
      const body = { id: s && s.id, channel: f.channel.value, address: val(f.address), daily: f.daily.value === "1", daily_time: val(f.time),
        cats: cats.map(l => l.querySelector("input")).filter(c => c.checked).map(c => c.dataset.k) };
      if (admin) body.usnam = val(f.user);
      const r = await run(() => api(admin ? "/api/notif/admin/sub" : "/api/notif/sub", body)); if (r) { msg("S", r.message); onSave(); } }));
}

register("ZNOTIF", { title: "My Daily Briefing and Alerts", async render(app) {
  style();
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/notif/my")); if (!d) return;
    out.innerHTML = "";
    const subList = d.subs.length ? alv({ rows: d.subs.map(s => Object.assign({}, s, { cats_t: s.cats.join(", ") })), title: "Where I get my messages", columns: [
      { key: "channel", label: "Channel", render: r => d.channels[r.channel] }, { key: "address", label: "Address" }, { key: "daily", label: "Daily", render: r => r.daily ? `✓ ${r.daily_time}` : "-" },
      { key: "cats_t", label: "Alerts" }, { key: "x", label: "", render: r => h("span", null, btn("Send test", async () => { const x = await run(() => api("/api/notif/test", { id: r.id })); if (x) msg("S", x.message); }), " ",
        btn("Remove", async () => { if (!await confirmBox("Remove", "Stop these messages?")) return; const x = await run(() => api("/api/notif/delete", { id: r.id })); if (x) { msg("S", x.message); load(); } })) }] })
      : note("You have no subscription yet - add one below to get the morning briefing and alerts on your mobile.");
    out.append(panel(`My messages ${d.unseen ? `(${d.unseen} new)` : ""}`, d.rows.length ? h("div", null, ...d.rows.map(r => h("div.nt-msg" + (r.seen ? "" : ".new"), { dir: "auto" },
      h("h4", null, r.title), h("div.b", { html: boldify(r.text) }), h("div.m", null, r.ts, badge(...(STAT[r.status] || [r.status, ""])), r.channel !== "inapp" ? r.channel : "",
        r.tcode ? h("a", { href: "#", on: { click: e => { e.preventDefault(); go(r.tcode); } } }, "Open " + r.tcode) : "", r.error ? h("span", { style: { color: "#a3182c" } }, r.error) : ""))))
      : note("No messages yet.")),
      subList, panel("Add a subscription", subForm(d, null, load, false),
        h("ul.nt-help", null, h("li", null, "Telegram (free, recommended): open the company's NERP bot in Telegram, press Start, and ask the administrator for your chat id (ZNOTIF_CONF → Find chat ids)."),
          h("li", null, "E-mail: needs the company mail server in ZNOTIF_CONF."), h("li", null, "WhatsApp: needs a Meta WhatsApp Business account; messages work inside the 24-hour window or with approved templates."),
          h("li", null, "Only NERP: the messages appear here."))));
    if (d.unseen) api("/api/notif/seen", {}).catch(() => 0);
  };
  toolbar([{ label: "Refresh", key: "F8", primary: true, onClick: load }, { label: "Settings (admin)", onClick: () => go("ZNOTIF_CONF") }]);
  load();
} });

register("ZNOTIF_CONF", { title: "Daily Briefing and Alerts - Settings", async render(app) {
  style();
  const out = h("div"); app.append(out);
  const load = async () => {
    const d = await run(() => api("/api/notif/admin")); if (!d) return;
    out.innerHTML = "";
    const s = d.settings;
    const f = { enabled: sel([["1", "On"], ["0", "Off"]], s.enabled || "1"), every: inp({ value: s.alert_minutes || "15", w: "s" }),
      tg: inp({ type: "password", w: "l", ph: s.telegram_token || "123456:ABC-…" }),
      host: inp({ value: s.smtp_host || "", w: "m", ph: "smtp.office365.com" }), port: inp({ value: s.smtp_port || "587", w: "s" }), user: inp({ value: s.smtp_user || "", w: "m" }),
      pw: inp({ type: "password", w: "m", ph: s.smtp_password || "" }), from: inp({ value: s.smtp_from || "", w: "m" }), tls: sel([["1", "STARTTLS"], ["0", "None"]], s.smtp_tls || "1"),
      wid: inp({ value: s.wa_phone_id || "", w: "m" }), wtok: inp({ type: "password", w: "l", ph: s.wa_token || "" }) };
    const chats = h("div");
    out.append(h("div.kpis", null, ...["Subscriptions", "Open alerts", "Messages logged"].map((k, i) => h("div.kpi", null, h("div.k", null, k), h("div.v", null, String([d.subs.length, d.alerts.length, d.log.length][i])))),
      h("div.kpi", null, h("div.k", null, "Scheduler"), h("div.v" + (d.state.running ? ".pos" : ".neg"), null, d.state.running ? "Running" : "Not started"), h("div.s", null, d.state.last_error || "checks every minute"))),
      panel("General", grid(field("Messages", f.enabled), field("Check alerts every (minutes)", f.every))),
      panel("Telegram (free, recommended)", grid(field("Bot token", f.tg)), h("ol.nt-help", null,
        h("li", null, "In Telegram open @BotFather → /newbot → choose a name (e.g. \"Factory NERP\") → copy the token here and save."),
        h("li", null, "Every person opens the new bot and presses Start."), h("li", null, "Press 'Find chat ids' and add a subscription with that id.")),
        btn("Find chat ids", async () => { const r = await run(() => api("/api/notif/admin/chats", {})); if (!r) return; chats.innerHTML = "";
          chats.append(r.rows.length ? alv({ rows: r.rows, title: "Chats that pressed Start", columns: [{ key: "chat_id", label: "Chat id" }, { key: "name", label: "Name" }] }) : note("No chats yet - open the bot in Telegram and press Start first.")); }), chats),
      panel("E-mail (SMTP)", grid(field("Server", f.host), field("Port", f.port), field("User", f.user), field("Password", f.pw), field("From", f.from), field("Security", f.tls))),
      panel("WhatsApp (Meta Business Cloud API)", grid(field("Phone number id", f.wid), field("Access token", f.wtok)),
        note("Needs a verified Meta WhatsApp Business account. Meta delivers free-text messages only within 24 hours after the person wrote to the business number; otherwise an approved message template is required.")),
      note("Secrets are shown masked; leave a field empty to keep it, enter - to remove it. They are stored in the NERP database of this computer."),
      alv({ rows: d.subs.map(x => Object.assign({}, x, { cats_t: x.cats.join(", ") })), title: "All subscriptions", columns: [{ key: "usnam", label: "User" },
        { key: "channel", label: "Channel", render: r => d.channels[r.channel] }, { key: "address", label: "Address" }, { key: "daily", label: "Daily", render: r => r.daily ? `✓ ${r.daily_time}` : "-" },
        { key: "cats_t", label: "Alerts" }, { key: "x", label: "", render: r => h("span", null,
          btn("Test", async () => { const x = await run(() => api("/api/notif/admin/test", { id: r.id })); if (x) msg("S", x.message); }), " ",
          btn("Send briefing now", async () => { const x = await run(() => api("/api/notif/admin/daily", { id: r.id })); if (x) { msg("S", x.message); load(); } }), " ",
          btn("Remove", async () => { if (!await confirmBox("Remove", `Remove the subscription of ${r.usnam}?`)) return; const x = await run(() => api("/api/notif/admin/delete", { id: r.id })); if (x) { msg("S", x.message); load(); } })) }] }),
      panel("Add a subscription for a user", subForm(d, null, load, true)),
      alv({ rows: d.alerts, title: "Alerts right now", columns: [{ key: "cat", label: "Type", render: r => d.cats[r.cat] }, { key: "title", label: "Alert" }, { key: "tcode", label: "Screen" }] }),
      alv({ rows: d.log, title: "Message log", columns: [{ key: "ts", label: "Time" }, { key: "usnam", label: "User" }, { key: "kind", label: "Kind" }, { key: "channel", label: "Channel" },
        { key: "title", label: "Title" }, { key: "status", label: "Status", render: r => badge(...(STAT[r.status] || [r.status, ""])) }, { key: "error", label: "Error" }] }));
    toolbar([{ label: "Save", key: "Ctrl+S", primary: true, onClick: async () => {
      const r = await run(() => api("/api/notif/admin/settings", { enabled: f.enabled.value, alert_minutes: val(f.every), telegram_token: f.tg.value, smtp_host: val(f.host),
        smtp_port: val(f.port), smtp_user: val(f.user), smtp_password: f.pw.value, smtp_from: val(f.from), smtp_tls: f.tls.value, wa_phone_id: val(f.wid), wa_token: f.wtok.value }));
      if (r) { msg("S", r.message); load(); } } },
      { label: "Check alerts now", onClick: async () => { const r = await run(() => api("/api/notif/admin/alerts", {})); if (r) { msg("S", r.message); load(); } } },
      { label: "My messages", onClick: () => go("ZNOTIF") }]);
  };
  load();
} });
})();
