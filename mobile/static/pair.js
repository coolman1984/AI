/* NERP Mobile - pairing page (opens only on the PC itself) */
"use strict";
(() => {
  const $ = s => document.querySelector(s);
  let ip = null;
  async function load() {
    const d = await (await fetch("/m/api/pairinfo", { cache: "no-store" })).json();
    ip = ip && d.ips.includes(ip) ? ip : d.ips[0];
    const i = d.ips.indexOf(ip);
    $("#link").textContent = d.links[i].replace(/#k=.*/, "");
    $("#conn").textContent = d.connected;
    $("#db").textContent = d.db;
    const img = new Image();
    img.src = "/m/api/qr.svg?ip=" + encodeURIComponent(ip) + "&t=" + Date.now();
    img.alt = "QR code for the phone";
    $("#qr").replaceChildren(img);
    const box = $("#ips");
    box.replaceChildren();
    if (d.ips.length > 1) {
      const p = document.createElement("p"); p.className = "mut"; p.textContent = "Other network addresses of this PC (if the phone cannot connect):";
      box.append(p);
      d.ips.forEach(x => { const b = document.createElement("button"); b.className = "btn ghost"; b.type = "button"; b.textContent = x;
        b.addEventListener("click", () => { ip = x; load(); }); box.append(b); });
    }
  }
  async function post(path) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    return r.json();
  }
  $("#renew").addEventListener("click", async () => {
    if (!confirm("Create a new key? Every paired phone has to scan the new QR code.")) return;
    alert((await post("/m/api/renew")).message); load();
  });
  $("#stop").addEventListener("click", async () => {
    if (!confirm("Stop mobile access? The phones show 'no connection' until you start NERP Mobile again.")) return;
    await post("/m/api/stop");
    document.querySelector("main").textContent = "Mobile access stopped. You can close this window.";
  });
  load();
  setInterval(() => fetch("/m/api/pairinfo", { cache: "no-store" }).then(r => r.json()).then(d => { $("#conn").textContent = d.connected; }).catch(() => {}), 5000);
})();
