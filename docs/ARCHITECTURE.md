# NERP architecture

NERP is a complete ERP for an Egyptian manufacturing company: sales, purchasing, inventory, production,
quality, maintenance, finance, controlling, Egyptian taxes, HR and payroll, external audit, BI, an AI
assistant and mobile notifications. It is modelled on SAP S/4HANA processes and transaction codes,
with generic names only (no third-party branding).

This page explains how the code is put together. Reference lists are generated from the code:
[SCREENS](SCREENS.md) · [API](API.md) · [ERROR_CODES](ERROR_CODES.md) · [TESTS](TESTS.md) ·
[CHANGELOG](CHANGELOG.md). Lessons learned and decisions: [KNOWLEDGE](KNOWLEDGE.md).

## 1. Principles (non-negotiable)

| Rule | Why |
|---|---|
| Python **standard library only** (server, engines, desktop client); front end **plain JavaScript**, no frameworks | Runs on any Windows PC with one click, no installs, nothing to break |
| Amounts in **cents** (int), quantities in **milli** (int), rates ×100000 | No rounding errors; use `mm.util` parse helpers, `rdiv`, `value_of` |
| **Writes only in the engines** - never SQL writes in `web/*.py` | One place for the business rules; the API is a thin layer |
| Every user input through a **parse helper** (`parse_amount`, `parse_date`, `parse_int`, `parse_pct` …) | Clean errors instead of crashes (checked by the fuzz test) |
| Business date from **`mm.util.today()/now()`** | The demo clock and tests can move the date |
| Every bug fix starts with a **failing test** | The bug never comes back |
| SQLite in WAL mode, one file in `data/` | Simple backup (copy the file), fast enough for one company |

## 2. Layers

```
Browser (web/static/*.js)          Desktop client (gui/)        Phone (mobile/, android/)
        │  JSON over HTTP (same API)            │                          │
        ▼                                       ▼                          ▼
web/server.py  - routing (@route), logon/session, authorization (sec/), Host/Origin checks
web/*_api.py   - one file per area: reads parameters, calls engines, returns dicts
        │
        ▼
Engines (packages)  - all business rules and all writes, inside transaction(conn)
        │
        ▼
mm/db.py  - SQLite connection, schema install chain, migrations, savepoints
```

## 3. Packages

| Package | Area | Main modules |
|---|---|---|
| `mm` | Core + inventory: DB, clock, parse helpers, material documents, posting, periods, Excel read/write, import | `db`, `util`, `posting`, `inventory`, `periods`, `xlsx`, `dataimport`, `board`, `seed`, `demo_ceramic` |
| `md` | Master data: material views, customer, vendor, change documents, checks | `material`, `partner`, `changes`, `checks` |
| `sd` | Sales: pricing, orders, ATP, credit, delivery, billing, returns, rebates, service | `order`, `pricing`, `credit`, `delivery`, `billing`, `rebate` |
| `pur` | Purchasing: requisitions, release, sourcing, RFQ, contracts, PO, MRP, import/LC, follow-up | `pr`, `po`, `sourcing`, `mrp`, `importfile`, `analytics` |
| `pp` | Production: BOM, routing, planning, orders, confirmations, subcontracting, boards, daily meeting | `master`, `planning`, `order`, `board`, `daily` |
| `mes` | GMES shop-floor execution: stations, serial numbers, bookings with route enforcement and operator certification, genealogy, andon, SPC, hourly / quality / WIP / cycle / operator reports | `track`, `reports`, `seed` |
| `tile` | Ceramic tiles: sorting into grade / shade / caliber lots, one shade + caliber per delivery item (hook in the goods issue of `sd.delivery`), lab tests by ISO 13006 group, first-choice rate, gas / power per m2, sales in m2 / boxes / pallets (hook in `sd.order` item creation), export report and documents | `lots`, `energy`, `pack`, `export` |
| `customs` | Customs clearance (own menu "Customs & Clearance", authorization area CU, role CUSTOMS_CLERK): import declarations from the import file (ACID, CIF at the customs rate, duty, import VAT code VI, payment into the import file costs), export declarations from a delivery (origin certificate, B/L, export support), tariff and HS codes, days in port | `engine`, `schema` |
| `qm` | Quality (inspection lots, results, decisions, notifications) and plant maintenance | `quality`, `maintenance` |
| `fi` | Financial accounting: central document, AP, AR, assets, bank, cheques, cash, WHT, closing, reports, currencies and exchange rates | `document`, `ap`, `ar`, `aa`, `clearing`, `reports`, `currency`, `cbe` |
| `co` | Controlling: cost centers, orders, product costing, actuals, period end, CO-PA, budget | `master`, `costing`, `actual`, `period_end`, `copa`, `budget` |
| `tax` | Egyptian taxes: law register, returns (VAT form 10, WHT form 41, salary form 4, CIT), e-invoice (ETA), tax audit, adviser review | `rules`, `returns`, `eta`, `audit`, `review` |
| `hr` | HR and Egyptian payroll: employees, org, leave, payroll, posting to FI/CO; skills matrix; time clock and evaluation; training, appraisal, end of service; HR analytics | `engine`, `payroll`, `extras`, `reports`, `skills`, `time`, `talent`, `analytics` |
| `extaudit` | External audit for audit firms (Egyptian Accounting Standards): engagement, materiality, PBC list, queries, adjustments, analytics, Excel pack | `engagement`, `analytics`, `pack`, `standards` |
| `ai` | "Ask NERP" assistant (read-only tools, Claude API with basic-mode fallback), the daily review and the What-If simulator | `tools`, `agent`, `review`, `whatif` |
| `notify` | Daily briefing and alerts to Telegram, e-mail, WhatsApp (approved templates) | `engine`, `channels` |
| `bi` | BI reports and dashboards | `engine`, `catalog`, `dashboards` |
| `sec` | Users, roles, authorization objects/areas, logon, approval inbox, audit log | `users`, `auth`, `config`, `inbox` |
| `qa` | Process catalog (swimlanes, controls, test cases), test runner, invariants, e-Learning | `catalog`, `runner`, `invariants`, `lms` |
| `gui`, `mobile`, `android`, `office` | Desktop client, phone gateway, Android app, Office COM bridge | |
| `web` | HTTP server, API files, static front end | `server`, `*_api`, `static/` |

## 4. How a feature is built (the pattern)

1. **Schema** - `package/schema.py` with `install(conn)`; add the call to the install chain at the end of
   `mm/db.py` (current order: … `tax` → `qm` → `ai` → `notify` → `extaudit` → `ai.whatif` → `mes` → `fi.currency` → `tile` → `customs`).
2. **Engine** - functions `fn(conn, …, user)`; validate with parse helpers; raise
   `MMError(text, class, number)`; write inside `with transaction(conn):`. Pick a free message number
   range (see [ERROR_CODES](ERROR_CODES.md)).
3. **API** - `web/<area>_api.py` with `@route("GET"|"POST", regex)`; import the file in `web/server.py`;
   map the path prefix to an authorization area in `sec/config.API_AREAS` (first prefix match wins;
   put more specific prefixes first).
4. **Screen** - `register(code, {title, render(app, params)})` in `web/static/<area>_screens.js`
   (include it in `web/static/index.html`); helpers `App.h, api, run, msg, ask, field, inp, sel, val,
   alv, toolbar, go`. Add the code to `web/static/menu.js`, then refresh `web/static/tcodes.json`
   with `node tools/gui/export_tcodes.js http://localhost:PORT`.
5. **Tests** - `tests/test_<area>.py` (in-memory DB: `connect(":memory:")` + `seed.seed(c)`); map every
   test in `qa/catalog.py`.
6. **Docs** - README section, this file if the structure changed, [KNOWLEDGE](KNOWLEDGE.md), then
   `python tools/docs/build_docs.py`.

## 5. Authorization

* Roles in `sec/config.DEMO_ROLES`: `(text, [tcode patterns], [(object, value, activity)])`.
  `D = [("*", "*", "03")]` = display everything except HR (HR needs an explicit grant).
* Areas (`S_AREA`): SD, MM, PUR, PP, FI, CO, MD, HR, CA, BC, AU, CU …; `area_allowed(profile, area, "02"|"03")`.
* The server checks the API area of every request: GET = display (03), POST = change (02).
* Logon can be switched off (developer / single-user mode) - then everything is allowed.
* Read-only features that show several modules (AI tools, daily review, notifications) filter by the
  areas the user may display.

## 6. Quality gate

* `python tools/qa/check_all.py`: unit + end-to-end tests, process catalog, data consistency of a fresh
  demo system, pyflakes, generated docs up to date.
* `node tools/qa/sweep.js http://localhost:PORT` (server `python run.py --dev --reset --no-browser --port PORT`):
  opens every screen in a real browser and fails on any error.
* The fuzz test sends malformed input to every POST route.

## 7. Running

* `Start NERP.bat` (one click) → `python run.py` → browser on the home page.
* `NERP Logon.bat` → desktop client. `python run.py --dev --reset` = fresh demo data, logon off.
* `python run.py --reset --demo ceramic` = ceramic tile factory demo instead (`mm/demo_ceramic.py`: master data
  and opening balances through the ZIMPORT takeover objects, then this month's business through the engines).
* Data in `data/`; backup with `tools/Backup database.bat`.
