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
  delivered: **NERP_v60**).
* **Documentation in every pull request** (see section 5 and `CLAUDE.md`), so no knowledge is lost.
* **GitHub Actions budget is used up:** run `check_all` and the browser sweep locally and say so in
  the pull request.
* **No third-party branding:** generic names only (no company, audit firm or product names of others,
  no copied characters or logos). The program is called **NERP**.
* Commits end with the co-author / session trailer; no model names in commits or pull requests.

## 2. Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11 | Temporary admission (`customs/ta.py`): regime TA on the import declaration; no posting at the guarantee step (duty / VAT stored per line only); balances open at the release, deadline = release + `ta_months` (12, setting - VERIFY with the broker, extensions exist); discharge at the release of an export declaration by exploding the exported products' BOM (multi-level, scrap % included) down to the TA materials, earliest deadline first, only balances released on or before the export day; the rest can be cleared for home use (duty into the import file, VAT code VI). BOM = estimate of the official input/output standards | Exporters save duty and VAT on imported inputs without a separate spreadsheet |
| 2026-11 | Customs (`customs` package, ZCUS): an import declaration needs an import file (ZIMP01) so the duty flows through the existing import costs and landed cost (ZIMP_LAND) - no second costing path; import VAT gets its own tax code VI (input, 154000) and VAT return line 4a; customs value = CIF x customs rate (system rate unless entered); the ACID number (19 digits) is required before any further import step; steps only forward, never future-dated; tariff rates, free days (4) and storage per day are user settings - the demo values are examples, VERIFY with a broker | Customs inside the purchase cost and the VAT return, not a separate island |
| 2026-11 | Tiles in boxes / pallets (`tile/pack.py`): order items of tile products are rounded UP to full boxes when the order is created (`sd.order._add_item`, not for returns / credit / debit memos; VA02 quantity changes are not rounded); BOX / PAL entered in the item field "unit"; gross weight = m2 x kg/m2 + 0.6 kg per carton + 25 kg per pallet | Customers get full boxes; the warehouse ships boxes |
| 2026-11 | Export (`tile/export.py`, ZSD_EXPORT): export = channel 20 or a customer outside Egypt; forms PACKLIST and ORIGIN (data sheet for the chamber of commerce / preferential certificate - not the certificate itself); HS 6907.21 / .22 / .23 from the ISO group - VERIFY with the customs broker; the takeover MATERIAL object now extends an existing material by a new plant / sales area line | Export documents from the delivery, no retyping |
| 2026-11 | Ceramics (`tile` package): lots are a sub-ledger next to MM stock (MM keeps quantities per material / bin; a lot = shade + caliber of one sorting) instead of batch management in the posting engine - no change to the posting logic or the standard demo; the goods issue of a delivery calls `tile.lots.on_goods_issue` (no-op without tile products) and refuses a shade / caliber mix; `reconcile` shows lots = stock | Shade-consistent deliveries without the risk of rebuilding inventory posting |
| 2026-11 | Grade 1 = GR 101 on the order, grade 2 = 501 into its own material at its price (offset 399990, a simplification - grade 2 is not a by-product of the order in CO), grade 3 / broken = scrap quantity in the sorting only; first choice = grade 1 / all sorted | Grade 2 has its own price list |
| 2026-11 | Lab limits = ISO 13006 groups by water absorption (BIa ≤ 0.5 %, BIb ≤ 3, BIIa ≤ 6, BIIb ≤ 10, BIII > 10) with minimum breaking strength 1300 / 1100 / 1000 / 800 / 600 N, planarity 0.5 %, size 0.6 %: defaults from general knowledge of the standard - VERIFY against the certified standard | Honest about what was not checked |
| 2026-11 | Energy per m2 = daily meter difference ÷ m2 sorted that day (grade 1 + 2); idle days count in cost but not per m2; "high" = more than 10 % above the average of the 28 days before; demo gas 8.50 EGP/m3 and power 2.34 EGP/kWh are illustrative tariffs | Gas is the biggest variable cost in tiles |
| 2026-11 | Ceramic factory demo (`mm/demo_ceramic.py`, `run.py --demo ceramic`): a separate, on-demand demo instead of changing the standard demo (~270 tests depend on it); master data and opening balances go through the ZIMPORT takeover objects (tests the go-live path), this month's business through the engines (`mm/demo_ceramic_ops.py`); equity is the plug that brings 399999 to zero; profile of the largest Egyptian tile makers with generic names; its Excel workbook is generated from the same rows | Realistic industry data without breaking the standard demo, and a real test of the takeover |
| 2026-11 | Exchange rates in the morning briefing (`notify.engine.fx_text`): main currencies + those with rates in use (max 6 lines), change vs previous rate, flags for old rates, currencies used without a rate and a failed CBE update today; shown to everybody (rates are public) | The owner sees the dollar every morning |
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

* Process catalog ids (`qa/catalog.py`) must be unique - P2P-34 was used twice for a while (ceramic demo moved to P2P-35); check with `grep -o '("[A-Z0-9]*-[0-9]*"' qa/catalog.py | sort | uniq -d`.
* `tools/docs/build_docs.py` collects error codes only from files git already tracks: after adding a new package run `git add` first, then build_docs (otherwise check_all says ERROR_CODES.md is out of date).
* Lots of goods already in stock at go-live must be created with `tile.lots.opening_lot` (the demo does it), otherwise the goods issue finds no lot. Returns (651) and GI reversals do not give m2 back to a lot yet - correct with a new opening lot.
* With the test clock (2026-11-09) all demo sortings fall on the same day (dates are capped at today); the energy "high day" test therefore builds its own days.
* Ceramic demo: only the payment terms 0001 / NT30 / NT60 / Z210 exist and only the countries in `md.config.COUNTRIES` (ES, JO, IQ, LY, KW were added); unit **M2** was added for tiles. Semi-finished and finished goods need `plant.beskz = E`, otherwise "procured externally - no production order". Production orders need plan activity prices (KP26) for the month - the demo plans them for this and next month. Export customers use distribution channel 10 (the takeover material sheet has one sales view per row). Exchange rates (USD, EUR ...) are saved from the go-live date; they are not part of the Excel workbook.

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
