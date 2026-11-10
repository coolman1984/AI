// Browser sweep: opens every registered screen of a running MM Core (developer mode),
// presses Execute where there is one and fails on page errors, console errors,
// HTTP 5xx, internal errors, menu codes without screen and every BI report / dashboard.
// Usage: node tools/qa/sweep.js http://localhost:8091      (exit code 1 = problems)
const { chromium } = require('playwright');
(async () => {
  const base = process.argv[2] || 'http://localhost:8091';
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1500, height: 900 } });
  let errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  p.on('console', m => { if (m.type() === 'error' && !/status of 4\d\d/.test(m.text())) errs.push('CONSOLE ' + m.text().slice(0, 150)); });
  p.on('response', r => { if (r.status() >= 500) errs.push('HTTP ' + r.status() + ' ' + r.url().replace(base, '')); });
  await p.goto(base + '/'); await p.waitForTimeout(1500);
  const info = await p.evaluate(() => { const reg = Object.keys(App.S.screens); const menu = [];
    const walk = it => { if (typeof it === 'string') { if (!it.startsWith('!')) menu.push(it); } else it[1].forEach(walk); };
    App.MENU.forEach(walk); return { reg, menuMissing: [...new Set(menu)].filter(c => !App.S.screens[c]) }; });
  const bad = [];
  if (info.menuMissing.length) bad.push('MENU codes without screen: ' + info.menuMissing.join(' '));
  for (const code of info.reg) {
    errs = [];
    await p.evaluate(c => { location.hash = '#/' + c; }, code); await p.waitForTimeout(350);
    const ex = p.locator('#app-toolbar button:has-text("Execute")');
    if (await ex.count()) { try { await ex.first().click({ timeout: 800 }); await p.waitForTimeout(350); } catch (e) {} }
    const st = await p.locator('#status-msg').innerText().catch(() => '');
    if (errs.length) bad.push(code + ' :: ' + [...new Set(errs)].join(' ; '));
    else if (/Internal error/i.test(st)) bad.push(code + ' :: ' + st.slice(0, 120));
  }
  const reps = await p.evaluate(async () => (await App.api('/api/bi/catalog')).tree.flatMap(c => c.groups.flatMap(g => g.reports.map(r => r.id))));
  for (const id of reps) {
    errs = [];
    await p.evaluate(i => { location.hash = '#/ZBI?id=' + i; }, id); await p.waitForTimeout(500);
    if (errs.length) bad.push('BI ' + id + ' :: ' + [...new Set(errs)].join(' ; '));
    await p.evaluate(() => { location.hash = '#/HOME'; }); await p.waitForTimeout(150);
  }
  console.log('screens', info.reg.length, 'BI reports', reps.length, 'problems', bad.length);
  bad.forEach(x => console.log('  ' + x));
  await b.close();
  process.exit(bad.length ? 1 : 0);
})();
