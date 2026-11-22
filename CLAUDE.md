# NERP - rules for changes

- Python standard library only (server, engines, desktop client). Front end: plain JS, no frameworks.
- Amounts in cents, quantities in milli, rates x100000; use `mm.util` parse helpers and `rdiv`/`value_of`.
- Writes only in the engines (never SQL writes in `web/*.py`); every user input through a parse helper.
- Business date: `mm.util.today()/now()` (never `datetime.date.today()` directly).
- Every bug fix: add a failing test first, then fix. Every new screen: in `web/static/menu.js`, and
  refresh `web/static/tcodes.json` with `tools/gui/export_tcodes.js`. Every new test: map it in `qa/catalog.py`.
- Before a pull request: `python tools/qa/check_all.py` must say ALL CHECKS PASSED, and the browser
  sweep `node tools/qa/sweep.js http://localhost:PORT` (server with `run.py --dev`) must exit 0.
- The GitHub workflow "NERP quality gate" must be green before merging (while the Actions budget is used up:
  run check_all + sweep locally and say so in the pull request).
- `Start NERP.bat` and `NERP Logon.bat` must keep working (one-click start).

## Workflow - standing instructions from the owner (always, without asking)

- After every change: commit on the session branch, push, open a pull request and **merge it yourself**.
  Never ask for permission to merge. Then deliver the zip: `git archive --format=zip --prefix=NERP/ HEAD`
  as `NERP_vNN.zip` (next number after the last one in `docs/KNOWLEDGE.md`, then update that number).
- **Documentation in every pull request - nothing may be lost:**
  - `README.md`: a section for every user-facing feature (what it does, screens, how to use).
  - `docs/GUIDE_AR.md`: the same in simple Egyptian Arabic for the owner and users.
  - `docs/ARCHITECTURE.md`: when packages, layers, the install chain or authorization change.
  - `docs/KNOWLEDGE.md`: every decision, trap, data quirk or setup step learned (newest first).
  - Then `python tools/docs/build_docs.py` (regenerates SCREENS, API, ERROR_CODES, TESTS, CHANGELOG);
    `check_all` fails when the generated docs are stale.
- Replies to the owner: simple, non-technical Egyptian Arabic, conclusion first.
- No third-party brands, company or person names in the program (generic names only); the program is NERP.
