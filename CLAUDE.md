# MM Core - rules for changes

- Python standard library only (server, engines, desktop client). Front end: plain JS, no frameworks.
- Amounts in cents, quantities in milli, rates x100000; use `mm.util` parse helpers and `rdiv`/`value_of`.
- Writes only in the engines (never SQL writes in `web/*.py`); every user input through a parse helper.
- Business date: `mm.util.today()/now()` (never `datetime.date.today()` directly).
- Every bug fix: add a failing test first, then fix. Every new screen: in `web/static/menu.js`, and
  refresh `web/static/tcodes.json` with `tools/gui/export_tcodes.js`. Every new test: map it in `qa/catalog.py`.
- Before a pull request: `python tools/qa/check_all.py` must say ALL CHECKS PASSED, and the browser
  sweep `node tools/qa/sweep.js http://localhost:PORT` (server with `run.py --dev`) must exit 0.
- The GitHub workflow "MM Core quality gate" must be green before merging.
- `Start MM Core.bat` and `MM Core Logon.bat` must keep working (one-click start).
