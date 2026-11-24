# NERP knowledge base

What we learned while building NERP: decisions, traps in the code and the data, and how the owner
wants the work done. Read this before changing NERP; add to it in every pull request that teaches
something new (newest entries at the top of each section).

## 1. How the owner wants the work done

* **Language of replies:** simple, non-technical Egyptian Arabic; conclusion first, then a short
  logical explanation; enough meaning to decide easily.
* **Delivery:** every change goes to a pull request that is **merged automatically** (no asking).
  After the merge a zip of the whole program is delivered:
  `git archive --format=zip --prefix=NERP/ HEAD` → `NERP_vNN.zip` (version +1 each time; last
  delivered: **NERP_v55**).
* **Documentation in every pull request** (see section 5 and `CLAUDE.md`), so no knowledge is lost.
* **GitHub Actions budget is used up:** run `check_all` and the browser sweep locally and say so in
  the pull request.
* **No third-party branding:** generic names only (no company, audit firm or product names of others,
  no copied characters or logos). The program is called **NERP**.
* Commits end with the co-author / session trailer; no model names in commits or pull requests.

## 2. Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11 | Central bank rates (`fi/cbe.py`): tolerant HTML reader (rows with a known currency name EN / AR + numbers; no CSS classes), mid = (buy + sell) / 2, per 100 from the name, page date (never future), safety limit on jumps, daily run in the notify scheduler thread with 15-minute retry; the CBE site could NOT be reached from the build environment, so the reader was built from the usual table layout and is configurable | Rates without manual typing, safe against wrong reads |
| 2026-11 | Exchange rates for all currencies (ZFX, `fi/currency.py`): ISO 4217 currency master; rates still stored EGP per 1 unit x 100000 in `exch_rate` (postings unchanged); weak currencies entered per 100 / 1,000 (factor) and divided on save; OB08 validates against the master and refuses EGP; demo rates are illustrative, not market data | One place for every currency without touching the posting logic |
| 2026-11 | HR: positive time recording (`hr/time.py`), talent (`hr/talent.py`), analytics (`hr/analytics.py`); Labour Law 14/2025 values as configurable defaults (15 / 21 / 30 / 45 leave days, 7 casual, 3 months notice, 7-day overtime notice) from secondary sources - marked VERIFY; settlement is an estimate, dismissal compensation shown as contingent | Close the HR gap with rules HR can change |
| 2026-11 | GMES (mes package): own design after ISA-95 / MESA-11 (no third-party GMES copied); serial = 1 unit; stations perform (line, operation) of the routing; operator certification from HR skills (`hr_skill` / `hr_qual`, owned by HR); FPY from first attempts, RTY = product, DPMO with station opportunities; confirmation to the order per operation = units passed - already confirmed (manual CO11N counts too) | Close the production-tracking gap without double counting |
| 2026-11 | What-If in the Copilot: tool `what_if` (area CO) for the AI; basic mode reads levers from the question (`agent._whatif_args`: one number per clause, keyword → lever, "down" words make it negative); "لو سمحت" is not a what-if | Ask in plain words, no screen needed |
| 2026-11 | What-If simulator (ZWHATIF): own generic design (the TV-show app the owner mentioned could not be verified and must not be copied); model = year so far from the financial statements, annualised; every lever linear so the goal seek is exact; dollar moves imported share (foreign vendors / payables) and export share (account 800100) | A decision tool on real figures, no copying |
| 2026-11 | The morning briefing ends with the daily review (yesterday's before 4 pm, allowed modules only); module texts say "today", so the briefing replaces it with "yesterday"; a review error never stops the briefing | One message with figures and an opinion |
| 2026-11 | Generated reference docs (screens, API, error codes, tests, change log) + `check_all` fails when stale | Docs can never drift from the code |
| 2026-11 | Copilot and daily review in Arabic **and** English (switch remembered per browser); answers follow the question's language | Foreign managers / customers |
| 2026-11 | Daily review (ZDAY): "normal" = average working day (Friday off) of the last 28 days; a problem always means "needs attention"; before 4 pm show yesterday | A fair opinion: the day must be over, rare events are not "bad" |
| 2026-11 | WhatsApp "auto" mode: free text, fall back to an approved template on Meta error 131047 (outside the 24-hour window) | The daily briefing must arrive every day on any normal mobile number |
| 2026-11 | External audit area follows the Egyptian Accounting Standards (EAS) and Egyptian Standards on Auditing (ISA numbering); unconfirmed EAS numbers marked "verify" | Correct references for Egyptian audit firms; honest about what was not confirmed |
| 2026-11 | Auditor proposes adjustments, only an FI user posts them (document type SA, tcode ZAUD_AJE) | Segregation of duties |
| 2026-11 | AI assistant: Claude API via stdlib `urllib`, read-only tools with the user's authorizations, basic mode without internet | Works offline; never changes data |
| 2026-11 | Notifications scheduler runs as a thread started in `run.py` | No extra service to install |

## 3. Traps in the code (read before you touch these)

* **Role table** key column is `name` (not `role`); user-role table is `usr_role (bname, role)`.
* **Reconciliation accounts** (customers 140000, vendors 160000/161000, down payments 164000/170000,
  assets) cannot be posted directly by `fi.document.write` (F5 562). Use the adjustment accounts
  (140099, 161099) or post through the customer / vendor / asset.
* **P&L accounts need a CO object** (KI 235): pass `kostl` (cost center, e.g. 4100) or an order, unless
  `default_aa` has a default for the cost element.
* Fixed asset values from `fi.aa.values`: accumulated depreciation is **negative** -
  `cost + depreciation = net book value`. Asset text column is `txt`.
* `fi.reports.statements(...)["result"]` is signed: an extra expense makes it **more negative**.
* `pm_notif.created` is the date the record was created (seed date); the breakdown day is `start`.
* `po_header.erdat` is a timestamp of the seed run; use `bedat` for the order date.
* `hr_overtime.hours` and confirmation quantities are in **milli** (6000 = 6 hours).
* Billing value of a day: `billing` with `cancelled=0` and `vbtyp IN ('M','O','P')` (credit memos 'O'
  are already negative; 'N' = cancellation document, excluded).
* An API request object in tools/tests may not have `_auth_on`: use `getattr(req, "_auth_on", None)`.
* The fuzz test posts junk to every route: ids must go through `parse_int`, never `int()`.
* Server threads: per-request state (e.g. the language of the daily review, the "day not over" flag) is
  kept in `threading.local()`, never in a module-level dict.
* The aging report code is **S_ALR_87012168** (customers); S_ALR_87012178 does not exist.
* Mixed Arabic + English text in one label renders garbled in RTL/LTR layouts - use one language per
  label or isolate with `dir`.
* Meta WhatsApp templates: parameters may not contain line breaks, tabs or 5+ spaces; the body may
  not start or end with a variable; names are `a-z0-9_`.

## 4. Traps in the demo data

* Demo QM parts must be posted in the **current month** (the CO period of earlier months is closed).
* The demo breakdown is dated before the PP sample month (otherwise the OEE test changes).
* October payroll run is released but **not posted** → payroll vs ledger shows a 740k difference; the
  audit analytics explain it ("payroll run not posted yet"). This is intended.
* Demo GMES: order 1000004 has 30 serials, 21 finished, 1 scrapped, 1 in repair; bookings on the last 3 days (none today), so the cockpit for today shows 0 output - use the day before. The demo line plan is only added where none exists (`INSERT OR IGNORE`), otherwise the ZPP_BOARD tests change.
* Tests set `NERP_NO_NETWORK=1` (tests/fixture.py): network calls (central bank) fail at once instead of reaching the internet - the fuzz test posts to every route, including "update from the central bank".
* If the CBE changes its page and no rates are found, the log says "No exchange rate table found": open the page in a browser, check the address in the settings, or paste the rates in "Enter many rates".
* Exchange rates are stored per 1 unit with 5 decimals: a very weak currency (e.g. IDR, VND) keeps about 3 significant digits per unit - always enter them per 1,000 (factor), never per unit.
* Employees with `time_rec = 0` (management by default) are not evaluated by the time clock - otherwise every manager shows as absent. Demo: only the factory staff 10003-10017 clock in.
* Time evaluation keeps `ot_posted` when a day is evaluated again, so approved overtime is never paid twice.
* `pp.order.confirm` checks the operation sequence: confirm earlier operations before later ones.
* The demo P&L is a loss and material cost exceeds sales → the What-If shows "no break-even" and the goal seek for profit 0 needs > +200 % price (out of range). Intended for the demo; real data differs.
* The demo has 21 overdue tax returns → Taxes are "needs attention" in the daily review. Intended.
* Journal entry testing flags 6 of 324 documents in the demo (weekend / round / large flags apply to
  manual entries only, otherwise almost everything is flagged).

## 5. Documentation map (keep it current)

| File | What | Updated |
|---|---|---|
| `README.md` | User-facing features, how to start, one section per area | By hand, every user-facing change |
| `docs/ARCHITECTURE.md` | Layers, packages, the feature pattern, authorization, quality gate | By hand, when the structure changes |
| `docs/KNOWLEDGE.md` | This page | By hand, whenever something was learned or decided |
| `docs/GUIDE_AR.md` | دليل سريع بالعربي لصاحب الشركة والمستخدمين | By hand, every user-facing change |
| `docs/SCREENS.md`, `API.md`, `ERROR_CODES.md`, `TESTS.md` | Reference lists | **Generated**: `python tools/docs/build_docs.py` (checked by `check_all`) |
| `docs/CHANGELOG.md` | Merged pull requests | **Generated** from git history |
| `docs/ENGINEERING_REVIEW.md`, `FIX_PLAN.md`, `FIX_STATUS.md` | The 2026 engineering review and its fix plan | Historical |
