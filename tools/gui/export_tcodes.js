// Writes web/static/tcodes.json (transaction code -> title) from the running app.
// Usage: node tools/gui/export_tcodes.js http://localhost:8080   (needs Playwright)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const url = process.argv[2] || 'http://localhost:8080';
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(url + '/'); await p.waitForTimeout(2500);
  const t = await p.evaluate(() => { const o = {}; for (const [k, v] of Object.entries(App.S.screens)) o[k] = v.title; return o; });
  const out = path.join(__dirname, '..', '..', 'web', 'static', 'tcodes.json');
  fs.writeFileSync(out, JSON.stringify(t, Object.keys(t).sort(), 1) + '\n');
  console.log('wrote', Object.keys(t).length, 'titles to', out);
  await b.close();
})();
