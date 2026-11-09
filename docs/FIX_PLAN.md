# MM Core — Detailed Fix and Build Plan

Companion to `docs/ENGINEERING_REVIEW.md`. That file lists **what is wrong** and the evidence. This file gives, for every item, **exactly how to fix or build it**: the data model, the functions and their steps, the screens, the error messages, the edge cases, the migration of existing databases, the tests, and the acceptance criteria.

No code was changed for this plan. A short prototype of Phase 1 was built to check that the design works and then taken out again (section 3.0). Its results are recorded here as evidence.

Date: 2026-11-09 · Base: `main` at `e4be26c`.

---

## 0. ملخص لصاحب المشروع

**الملف ده إيه؟** خطة شغل كاملة. لكل مشكلة اتلقت في المراجعة مكتوب: نغيّر إيه بالظبط، في أنهي ملف، الجداول الجديدة، الخطوات، الشاشات، الرسائل، وإزاي نتأكد إن المشكلة اتحلت. اللي هيبرمج يمشي عليها خطوة خطوة من غير ما يحتاج يخمّن.

**جربت جزء من الحل قبل ما أكتبه، علشان أتأكد إنه ينفع، وبعدين شلته:**

1. **ساعة موحّدة للبرنامج**، والاختبارات تشتغل بتاريخ ثابت. بعدها الـ 115 اختبار نجحوا كلهم وإحنا عاملين نفسنا في 15 مارس، و2 يناير، و31 ديسمبر، و28 فبراير. يعني الحل ده بيقفل مشكلة "الاختبارات بتنجح بالصدفة" نهائيًا.
2. **مشكلة مارس اتحلّت:** تحميل البيانات التجريبية اشتغل يوم 1 و15 و31 مارس. وكمان بقى "كله أو لا شيء"، وبقى أسرع (أقل من نص ثانية).
3. **اكتشافين جداد:**
   - ميزان المراجعة مش متوازن في كل شهور السنة ما عدا نوفمبر وديسمبر، مش في أول السنة بس.
   - قفل الشهر الحالي بيسجّل قيدين بتاريخ آخر الشهر، يعني في المستقبل.
4. **تصحيح:** حساب "الأرباح المرحّلة" (081000) موجود أصلًا في دليل الحسابات، فمش محتاجين نعمل حساب جديد زي ما قال التقرير الأول.

**الخطة 6 مراحل بالترتيب**، وكل مرحلة لها بند "خلصت إمتى" واضح:

1. **المرحلة 1:** تاريخ البرنامج والاختبارات وتحميل البيانات.
2. **المرحلة 2:** الدفاتر والضوابط المالية (إقفال السنة، إلغاء فاتورة المورد، منع التكرار، حدود المرتجعات).
3. **المرحلة 3:** متانة البرنامج والحماية من الإدخال الغلط ومن مواقع الإنترنت.
4. **المرحلة 4:** ربط المبيعات بالإنتاج، والعملات الأجنبية، وتعديل أوامر البيع والتسليمات.
5. **المرحلة 5:** تسجيل الدخول والصلاحيات وسجل المراجعة.
6. **المرحلة 6:** الحاجات الناقصة المهمة (الجرد الفعلي، ضريبة الخصم والإضافة، حجز الفواتير المخالفة، المقاصة اليدوية، إشعار دائن المورد، الدفعات المقدمة، فترات المخازن، استيراد البيانات، الطباعة).

**التقدير:** حوالي 25 لـ 35 يوم شغل لمبرمج واحد، والمرحلة 1 لوحدها يوم أو اتنين. المرحلة 1 لازم تخلص قبل أول مارس.

باقي الملف بالإنجليزي لأنه موجّه للي هيكتب الكود.

---

## 1. How to use this plan

### 1.1 Relationship to the review

Every heading here carries the ID from `ENGINEERING_REVIEW.md` (BUG-, CODE-, ROB-, SEC-, LINK-, GAP-, TEST-, DOC-). Read the evidence there, the solution here. New items found while prototyping have IDs starting with `NEW-`.

### 1.2 Rules that apply to every change

1. Python standard library only. Integer cents / milli / basis points. `mm.util.rdiv` for every division. No `float`, no `round()` on money.
2. Every write inside `with transaction(conn):`. After Phase 1 nested blocks are savepoints, so an inner failure is always undone.
3. New tables → the module's `schema.py`. New columns on existing tables → `*_COLUMN_ADDS` (existing databases are upgraded at start). Named-column INSERTs only.
4. Business errors → `MMError(text, msg_class, msg_no)`. New message numbers are listed per item. Never let a `KeyError`, `TypeError` or `ValueError` reach the HTTP layer.
5. Every function that changes master data writes change documents through `md.changes.log`.
6. Every new process step gets: an engine function, an API route, a screen (registered T-code, reachable from the menu), at least one unit test, and a test case in `qa/catalog.py` (so it shows in ZQA_TEST and in the manuals).
7. After every phase:
   - run the full unit tests, `python -m qa.runner` and the calendar test;
   - regenerate the manuals if the catalog changed;
   - update `README.md`;
   - open a PR, merge it and deliver a zip.

### 1.3 Definition of done for the whole plan

- `python3 -m unittest discover -s tests` passes when the computer date is any day of 2026–2028 (calendar harness, section 3.6).
- `tests/test_api_fuzz.py` finds zero non-business exceptions on all routes.
- `qa/invariants.py` reports zero violations after the seed and after every test module.
- Every control claimed in `qa/catalog.py` is enforced by code and covered by a negative test.
- No message in the system names a transaction that does not exist.

### 1.4 Size scale used below

| Size | Meaning |
|---|---|
| S | under half a day |
| M | half a day to two days |
| L | more than two days |

---

## 2. Order of work and dependencies

```
Phase 1  clock ─┬─ savepoints ── atomic seed ── fixed test date ── calendar test
                └─ date clamping in seeds ── no future-dated documents
Phase 2  carry-forward (needs clock for tests)
         inv_item table ── MR8M ── GR-reversal guard ── credit memo (Phase 6)
         FBRA ── depreciation reversal
         duplicate-invoice check
         reference limits for returns/credits
         rsnum on mat_doc_item ── reservation-aware reversal
         run tables for VAT / FX / payment run
         integer billing
         cross-year CO key ── settlement-to-material rule
         invariant checker (uses all of the above)
Phase 3  parse helpers ── fuzz test
         engine functions for API writes
         open_db/migrate split ── WAL ── schema version ── indexes ── backup ── log
         Origin/Host/Content-Type checks
Phase 4  sales requirements in MRP ── shared ATP ── PIR consumption at order entry
         currency on PO ── GR in FC ── MIRO in FC ── (later) SD currency
         delivery change/delete ── rejection rule ── credit re-check
         operation sequence
         sales order change (VA02 full)
         commitments
Phase 5  users/roles/sessions ── authorisation checks ── audit log ── approval inbox
Phase 6  physical inventory · invoice tolerances/blocks · withholding tax · manual clearing ·
         vendor credit memo · down payments · posting periods per account type ·
         MM periods · data import · print forms
```

| Phase | Items | Size | Must finish before |
|---|---|---|---|
| 1 | BUG-001, TEST-001, CODE-003, NEW-01, NEW-02, NEW-03, ROB-002 (log only) | M (1–2 days) | 1 March (seed crash date) |
| 2 | BUG-002, 004, 005, 006, 007, 008, 009, 012, CODE-001, 002, 004, TEST-004 | L (6–8 days) | first real month-end |
| 3 | ROB-001, ROB-002, ROB-003, BUG-014, CODE-005…011, SEC-002, SEC-003, TEST-002 | L (4–5 days) | any use beyond one PC |
| 4 | BUG-003, 010, 011, 013, GAP-SD-01, GAP-SD-04, LINK-07, LINK-12, CODE-007 | L (6–8 days) | real sales/production use |
| 5 | SEC-001, GAP-X-01, GAP-X-03 | L (3–4 days) | more than one user |
| 6 | GAP-MM-01, GAP-MM-02/03, GAP-PUR-01/02/03, GAP-FI-02/03/04, GAP-X-04/07, DOC-* | L (6–10 days) | go-live |

---

## 3. Phase 1 — Time bombs and test stability

### 3.0 Prototype evidence (built, measured, removed)

A prototype of 3.1–3.5 was implemented on the working branch and then reverted; the patch is kept outside the repository (it touched 39 files, +201 / −69 lines). Measured results:

| Check | Before | With prototype |
|---|---|---|
| Unit tests with computer date 2026-03-15 | all fail (seed crash) | 115 / 115 pass |
| … 2026-01-02 | 6 fail | 115 / 115 pass |
| … 2026-12-31 | 2 fail | 115 / 115 pass |
| … 2027-02-28 | not run | 115 / 115 pass |
| Seed on business date 1, 15, 31 March 2026 and 1 March 2028 | crash | seeds; books balanced; FI = CO-PA; stock = G/L |
| Seed duration (in memory) | about 1.5 s, hundreds of transactions | 0.44 s, one transaction |
| Trial balance sums to zero | only in Nov/Dec 2026 | unchanged — needs BUG-002 (section 4.1) |
| Documents dated after the business date | 37 on day 3 of a month | 2 on day 9 (NEW-02) |

The prototype confirmed three design points that are easy to get wrong:

1. The seed can only be made one transaction **after** savepoints exist, because `mm/seed.py` catches the error of each failed demo posting and continues (`mm/seed.py:117`, `:172`, `:251`). Without savepoints the half-written failed posting would be committed.
2. The clock must be **per thread**, because `ZQA_TEST` runs the whole test suite inside a web-request thread of the live server. A global clock would put every other user's postings on the test date while the suite runs.
3. Many functions have a parameter called `today`, so the clock module must be imported under another name (the prototype used `from mm import util as mmclock`).

### 3.1 NEW-01 / TEST-001 · Central business clock · S

**Problem.** 87 call sites read the computer date directly (`datetime.date.today()`, `datetime.datetime.now()`, and `mm.util.now_ts()`); tests and the seed cannot control "today". Files: `mm/util.py`, `mm/seed.py`, `mm/reports.py`, `co/seed.py`, `fi/seed.py`, `fi/reports.py`, `pur/sourcing.py`, `pur/mrp.py`, `pur/analytics.py`, `md/reports.py`, `pp/service.py`, `pp/seed.py`, `pp/order.py`, `pp/reports.py`, `pp/planning.py`, `sd/service.py`, `sd/seed.py`, `sd/billing.py`, `sd/reports.py`, `web/qa_api.py`, `web/pur_api.py`, `web/co_api.py`, `web/pp_api.py`, `web/server.py`, `web/sd_api.py`, `web/fi_api.py`, `qa/runner.py`.

**Design.**
1. In `mm/util.py` add a thread-local holder and four functions:
   - `set_clock(day)` — sets the business date of the current thread (a `date`, an ISO string, or `None` for "use the computer date"); returns the previous value so the caller can restore it.
   - `today()` — the business date, or the computer date when none is set.
   - `now()` — the business date combined with the current time of day.
   - `day_in_month(y, m, day, cap=None)` — the date `y-m-day`, clamped to the last day of the month; if `cap` is in the same month and earlier, clamped to `cap`.
2. `parse_date(None)` and `now_ts()` use `today()` / `now()`.
3. Replace every direct call in the files above by `mmclock.today()` / `mmclock.now()` with the import `from mm import util as mmclock`. Do not use the name `today` for the import (parameter clash).
4. Add a guard test: `grep` over `mm co fi pur md pp sd web qa` for `date.today()` and `datetime.now()` outside `mm/util.py`; the test fails if any is found.

**Acceptance.** The guard test passes; the calendar harness (3.6) shows the same results whatever the computer date is.

### 3.2 CODE-003 · Savepoints for nested transactions · S

**Problem.** `mm/db.py` `transaction`: a nested block only increments a counter; on an error inside a nested block nothing is undone unless the outermost block also fails.

**Design.**
1. On entry: depth 0 → `BEGIN IMMEDIATE`; depth n > 0 → `SAVEPOINT sp<n>`.
2. On exit without error: depth 0 → `COMMIT`; otherwise `RELEASE sp<n>`.
3. On exit with error: depth 0 → `ROLLBACK`; otherwise `ROLLBACK TO sp<n>` followed by `RELEASE sp<n>` (both are needed: `ROLLBACK TO` keeps the savepoint open).
4. If `BEGIN`/`SAVEPOINT` itself fails, release the write lock before re-raising (the current code would leave the lock held).
5. `next_number` must run inside a transaction: wrap its body in `with transaction(conn)` (free when nested).

**Behaviour changes to check:**
- `post_goods_movement(check_only=True)` (`mm/posting.py:44`) raises `_CheckOK` inside its transaction to roll back. Called at top level this already worked; called inside another transaction it now also rolls back correctly. Same for `fi/ap.py` `miro_simulate`.
- Collective actions that catch `MMError` per item and continue (`pp/service.py:139` `mass_forecast`, `web/pp_api.py:284` collective release) now keep the successful items and drop only the failed ones. Wrap each of these collective loops in one outer transaction after this change so the whole run is consistent.

**Acceptance.** New test: open a transaction, call a function that writes and then raises inside a nested block, catch the error, write something else, commit → only the second write exists.

### 3.3 BUG-001 · Atomic seed · S

**Design.**
1. `mm.seed.seed(conn, business_date=None)`:
   - return `None` if `plant` has rows (unchanged);
   - when `business_date` is given, `set_clock(business_date)` and restore the old value in `finally`;
   - run the whole demo inside one `with transaction(conn)` (requires 3.2).
2. Because the seed is now one transaction, a crash leaves an empty database, which is seeded again at the next start. No separate "seed state" marker is needed. Add one anyway as documentation: `settings('seeded', <date>)` is already written at the end (`mm/seed.py:265`); keep it.
3. The one demo posting that fails every time (`mm/seed.py` history day 15: consumption of 9 × SP-4002 from storage location 0004 hits a stock deficit) is caught today and reported in the return value. Make the demo deterministic and clean: before posting a random consumption, cap the quantity at the available unrestricted stock, or skip the posting if the stock is zero. The seed's return value must be an empty list.

### 3.4 BUG-001 · Date clamping in all seeds · S

**Design.**
- Previous-month samples (`co/seed.py:224`, `fi/seed.py:177`, `md/seed.py:179`, `pur/seed.py:59`): `d(day)` = `day_in_month(y, p, day)` — clamped to the month's last day. In February `d(29)` and `d(30)` become the 28th (29th in a leap year).
- Check after clamping in `fi/seed.py`:
  - The first payment run `PR1` runs on `d(15)` with next date `d(29)`.
  - The second run `PR2` runs on `d(29)`, and its next date is `d(29)` + N days.
  - The customer payment is on `d(30)`.
  - All of these stay valid after clamping, because `payment_run` only requires next date > run date (`fi/ap.py:327`).
- Current-month samples (`sd/seed.py:75`, `pp/seed.py:142`): `d(day)` = `day_in_month(y, m, day, cap=today())`. On day 1 of a month the whole sales/production story happens on day 1. This is legal: quotation validity, ATP and delivery-date logic use "≥" comparisons. The prototype seeded on the 1st, 15th and 31st without errors.

### 3.5 NEW-02 · No documents dated after the business date · S

**Problem (new).** Even with clamping, the seed posts two FI documents on the **last day of the current month**:
- `KKAO` work in process for order 1000004;
- `KO88` settlement of order 1000006 to material SP-4001.

They come from `pp/seed.py` "period end of the current month" (`period_end.overhead / wip / variances / settle` with the month's last day as posting date). On 9 November they are dated 30 November.

**Design.** The demo must not run the period-end of a month that is not over. Two options:
1. Run the current-month period-end functions with the business date as posting date (they accept `gjahr, perio`; the posting date is derived in `co/period_end.py` and `pp/service.py` as end of period — add an optional `budat` parameter that defaults to end of period but is capped at `today()`).
2. Do not run current-month period-end in the seed at all; leave it as an exercise.

**Choose option 1.** The demo then shows WIP and settlement results, and nothing is in the future.

**Acceptance.** The calendar test asserts `SELECT COUNT(*) FROM acc_doc WHERE budat > business_date` = 0 and the same for `mat_doc`, `co_doc`, `billing`.

### 3.6 TEST-001 · Fixed date for tests, calendar test, runner · S

**Design.**
1. New file `tests/fixture.py`:
   - puts the repository root on `sys.path`;
   - calls `mm.util.set_clock(FIXED)` with `FIXED = 2026-11-09`;
   - exports `T` and `TODAY`.
2. Every test module imports `fixture` right after its `sys.path` line and uses `fixture.T` instead of `datetime.date.today()`. The prototype did this for 8 modules; 115 tests stayed green.
3. `qa/runner.py`:
   - saves the clock (`old = set_clock(FIXED)`) before discovery and restores it in `finally`;
   - removes `fixture` from `sys.modules` together with the `test_*` modules;
   - writes the business date into the run log;
   - shows it in ZQA_TEST.
4. New `tests/test_calendar.py`. For each date below, set the clock, seed a fresh in-memory database and assert:
   - balance sheet balanced;
   - FI = CO-PA for the business month and the previous month;
   - stock = G/L;
   - trial balance closing balances sum to 0;
   - no document dated after the business date.

   Dates: 2026-01-01, 2026-01-02, 2026-01-31, 2026-02-28, 2026-03-01, 2026-03-31, 2026-04-30, 2026-06-01, 2026-12-31, 2027-01-01, 2028-02-29, 2028-03-01. About 0.5 s per date.
5. Keep a long version of the same check outside the normal run (`python -m qa.calendar all`), stepping through every day of 2026–2028. It is run before every release and takes about 10 minutes.

**Acceptance.** `test_calendar.py` passes. Until BUG-002 is done, the trial-balance assertion fails for every month except November and December (measured in the prototype). Implement 4.1 in the same PR or mark that one assertion as expected-failure with a reference to BUG-002.

### 3.7 ROB-002 (part) · Start-up errors and log file · S

**Design.**
1. `run.py`:
   - configure `logging` to `data/mm_core.log` (rotating, 5 × 1 MB) plus the console;
   - wrap `connect` + `seed` in `try/except`;
   - on error, log the traceback, then start a minimal server that serves one static page "MM Core could not start — details in data/mm_core.log" with the first line of the error, and open the browser on it (the user starts with `pythonw`, so there is no console);
   - exit with code 1 when started with `--no-browser`.
2. `web/server.py` `_dispatch`: on any non-business exception, log the traceback with a reference (time stamp + random 6 characters) and return `{"type": "E", "text": "Internal error - reference <ref> (see data/mm_core.log)"}` (also SEC-003).

---
## 4. Phase 2 — Books and financial controls

### 4.1 BUG-002 · Fiscal-year balance carry-forward · M

**Facts confirmed while planning:**
- `fi/config.py:50` already defines `081000 "Retained earnings"` (BS, FSV node `P10` Equity), and FSV node `P15 "Profit / loss of the period (not carried forward)"` exists. **Use 081000; do not create a new account.**
- `fi/reports.py:155` `_bs_values` computes the "result" as the sum of **all** P&L postings ever made up to the key date, and `statements` puts it in `P15`. So the balance sheet balances, but `P15` is labelled "of the period" while it contains every prior year. That is a second, hidden reporting error.
- `fi/reports.py:126` `trial_balance` opens P&L accounts at 1 January and balance-sheet accounts cumulatively, so the prior-year result is missing and the total is not zero (−1,198,143.46 on 2 January 2026 in the demo; non-zero in every month except November and December, because the demo history starts in July).

**Design (SAP-like: carry-forward is a balance, not a document).**

1. Table `fi_carry_forward`:

   | Column | Type | Meaning |
   |---|---|---|
   | `gjahr` | INTEGER PK | year that was closed |
   | `amount` | INTEGER | sum of all P&L line items of that year, in cents (debit +). The negative of this is the profit |
   | `hkont` | TEXT | target account, always `081000` for now |
   | `run_at`, `usnam` | TEXT | who / when |

2. `fi/gl.py: carry_forward(conn, gjahr, user)` (T-code F.16, alias FAGLGVTR):
   - computes the P&L sum of `gjahr`;
   - stores or replaces the row (re-runnable: postings made later into the old year are picked up by running it again);
   - returns the amount and the list of P&L accounts with their year balance.
   - Refuse when `gjahr >= today().year` (year not over).
3. Helper `fi/reports.py: retained_earnings(conn, gjahr)` returns:
   - the sum of the stored rows for all years before `gjahr`, **plus**
   - the computed P&L sum of every earlier year that has no row yet.

   It also returns the list of those "missing" years, so the screens can warn "balance carry-forward for 2025 not yet run (F.16)".
4. Change `trial_balance(gjahr, …)`:
   - Account 081000 gets an extra opening amount equal to `retained_earnings(gjahr)`.
   - Show it as a separate line "Balance carry-forward" so the user sees where the number comes from.
   - The total of all closing balances is then zero.
5. Change `_bs_values(conn, upto, gjahr)`:
   - balance-sheet accounts as today;
   - add `retained_earnings(gjahr)` to 081000;
   - compute `result` from the P&L postings **of the year of `upto` only** (from 1 January of that year to `upto`).

   `statements` then shows:
   - P15 = result of the current year up to the key date;
   - P10 = equity including all prior years.
6. FI closing cockpit (`ZFI_PROCESS`, `fi/reports.py` closing status): add step "Balance carry-forward" with status per year, and a warning row when the open posting periods (OB52) do not contain today.
7. Screen `F.16`: year field, "Test run" (show amounts) and "Execute".
8. CO and asset year change are separate (sections 4.11 and 8.10).

**Migration.** No data change. Existing databases get correct reports immediately; F.16 rows are optional because of the fallback in step 3.

**Tests.**
- Calendar test (3.6): trial balance sums to zero for all dates.
- New `test_fi.YearEnd`:
  - after seeding with business date 2027-01-15, run `carry_forward(2026)`;
  - check the 081000 opening in the 2027 trial balance equals −(2026 P&L);
  - post a late 2026 document, re-run, the amount changes accordingly;
  - `statements(2027, 1, 1)` P15 contains only January 2027 postings.

**Message numbers.** `F5 210` "Fiscal year %s is not yet over"; warning `F5 211` "Balance carry-forward for %s not yet run (F.16)".

### 4.2 BUG-004 · Reversal of invoices, payments and depreciation · L

#### 4.2.1 Invoice item table (prerequisite, also the purchase-order history for invoices)

Table `inv_item`:

| Column | Meaning |
|---|---|
| `belnr`, `gjahr`, `buzei` | the GR/IR line of the MIRO document |
| `ebeln`, `ebelp` | PO item |
| `menge` | invoiced quantity (milli; negative for a credit memo) |
| `net` | net invoice amount of the item (cents, local) |
| `grir` | amount debited to GR/IR |
| `freight` | amount to planned-delivery-cost clearing |
| `to_stock` | part of the price difference posted to stock |
| `to_prd` | part posted to price differences (or to the expense for account-assigned items) |
| `stock_before` | `lbkum` of the material at posting (for audit) |
| `cancelled` | 0/1 |

`miro` writes one row per item (`fi/ap.py:96`; the values already exist in local variables `grir`, `fr`, `to_stock`, `diff - to_stock`).

**Migration of old MIRO documents.** A one-time back-fill in the schema upgrade, for every `acc_doc` with `tcode='MIRO'`:
- one row per item with `ktosl='WRX'` (ebeln, ebelp, menge, amount);
- `to_stock` from the `BSX` line with the same ebeln/ebelp;
- `to_prd` from the `PRD` line, or from the expense line for account-assigned items;
- `freight` from the `FRE` line.

#### 4.2.2 MR8M — cancel a logistics invoice

`fi/ap.py: cancel_invoice(conn, belnr, gjahr, budat, user, reason="01")`.

**Checks:**
1. The document exists, `tcode='MIRO'`, and it is not already reversed (`stblg` empty). Message `M8 150`.
2. The vendor line is not cleared. Message `M8 151`: "Invoice %s is paid or cleared - reset clearing first (FBRA)".
3. The posting period is open (the FI writer checks this anyway).

**Steps:**
1. Build the inverse of every line of the original document:
   - same accounts, same CO objects, same tax codes;
   - amounts negated;
   - `wrbtr` negated in document currency.

   This also reverses the tax, the GR/IR, freight and PRD lines.
2. For each `inv_item` row with `to_stock ≠ 0`, the stock part needs special handling:
   - read the material's valuation now;
   - `back = min(to_stock, value that can still be taken)`. Covered quantity = `min(menge, lbkum now)`; `back = rdiv(to_stock × covered, menge)`;
   - the inverse `BSX` line gets `-back`;
   - the remainder `to_stock - back` goes to `PRD` (the stock that received the difference has been consumed);
   - update `valuation.salk3 -= back`; for moving-average materials recalculate `verpr`;
   - write a `price_history` row "MR8M".
3. `po_item.remng -= menge`, `po_item.reewr -= net`.
4. Write the FI document with document type `RE`, T-code `MR8M`, text "Cancellation of %s".
5. Set `stblg` on both documents (as `fi/gl.py:reverse` does), and mark the `inv_item` rows as cancelled.
6. The original vendor open item and the cancellation's vendor line clear each other: set `augbl` on both to the cancellation document number.

**Screen** `MR8M`: document number, year, reversal reason (01 error, 02 wrong price, 03 wrong quantity), posting date, "Simulate", "Cancel". Show the resulting lines before posting.

**PO history (ME23N):** add a tab "Invoices" listing `inv_item` rows with links to the FI documents and the cancellation status.

**Tests** — four cases, each ending with books balanced, `remng` restored, GR/IR of the item as before, and stock = G/L:
- (a) moving-average material with stock unchanged → valuation identical to the state before the invoice;
- (b) moving-average material whose stock was consumed after the invoice → the difference lands on PRD;
- (c) standard-price material;
- (d) account-assigned item (K) → the expense is reversed on the cost center, and the CO document is reversed too (`co.integration.post_from_fi` creates the CO line automatically from the FI lines).

#### 4.2.3 FBRA — reset clearing

`fi/gl.py: reset_clearing(conn, augbl, gjahr, user, reverse=False, budat=None)`.

**Steps:**
1. Find all items with `augbl = augbl` (and clearing-year logic: `augdt` year).
2. Refuse when the clearing document is a payment whose residual item (`rebzg`) is itself cleared later. Message `F5 820`.
3. Set `augbl = NULL`, `augdt = NULL` on all of them **except** the line items of the clearing document itself, if `reverse=True` (they are cleared by the reversal in step 4).
4. If `reverse=True`: call `reverse(conn, augbl, gjahr, budat, "01", user)`. Today `reverse` refuses documents with cleared items, so call it after step 3, and let it accept `F110` / `F-53` / `F-28` / `FF67` payment documents. The blocking list in `fi/gl.py:99` must then contain only `MIGO`, `VF01`, `MIRO`, `AFAB` and asset documents.
5. If the clearing document came from a payment run, add a JSON note to the `payrun` row ("payment %s reset on %s by %s"). Do not delete the run.
6. If the clearing came from `vat_settlement` (after 4.7, VAT settlement uses clearing) or from `grir_clearing`, the same function applies.

**Screen** `FBRA`: clearing document, year, option "Reset and reverse". Show the list of items that will be reopened.

**Tests:**
- pay a vendor invoice, run FBRA with reverse → the invoice is open again, the bank is back, the books balance;
- a partial payment with a residual item cleared later → refused.

#### 4.2.4 Depreciation reversal

`fi/aa.py: reverse_depreciation(conn, gjahr, perio, user)`.

**Rules:**
- Allowed only for the latest period that has posted depreciation (no later `bwasl='AFA'` rows). Message `AA 020`.
- Find the AFAB document of the period:
  - `asset_item.bwasl='AFA'` rows for that period share one `belnr`;
  - reverse it through `fi/gl.py:reverse`, which must accept `tcode='AFAB'` when called with an internal flag `_allow_source=True`. Keep the user-facing FB08 refusal.
- `reverse` already writes negative `asset_item` rows (`fi/gl.py:124-128`).

**Note.** Re-running AFAB is already safe (it posts planned − posted). Reversal is still needed for one case: when a wrong asset was capitalised and must be corrected before depreciation.

**Tests:** reverse the last period → planned − posted for that period equals the planned amount again; AFAB re-posts the same amount.

#### 4.2.5 Messages to correct

- `fi/gl.py:101`: "Document %s comes from %s - reverse it there (MBST, VF11, MR8M)". Remove "AFAB repeat" or point to the new depreciation reversal.
- `fi/gl.py:108`: keep "(FBRA)" — it now exists.

### 4.3 BUG-005 · Limits for returns, credit and debit memos · M

**Design.**
1. `sd/order.py` new function `referenced_qty(conn, vgbel, vgpos, families)`. It sums `kwmeng` of non-rejected items of non-cancelled sales documents whose `vgbel/vgpos` point to the billing item and whose document category is in `families`:
   - returns family = `RE`;
   - credit family = `CR`.
2. In `_add_item` (or before the loop in `create`), when the reference is a billing item (`ref["vbtyp"] == "M"`):
   - **Returns (`RE`):**
     - `qty + referenced_qty(RE) ≤ fkimg` of the billing item;
     - message `V1 019` "Item %d: quantity %s exceeds billed %s minus already returned %s".
   - **Credit memo requests (`CR`):**
     - value check `net of this item + credited value so far ≤ billing item net − value of returns (at invoice price)`;
     - credited value so far = sum of `netwr` of `CR` items referencing the billing item;
     - message `V1 023`.
   - **Debit memo requests (`DR`):** no upper limit; billing block 08 stays.
3. Quotation completion (`sd/order.py:199`):
   - per quotation item, compute `ordered = referenced_qty(... C family)`;
   - set the quotation `gbstk='C'` only when every non-rejected item is fully ordered, `'B'` when partly;
   - `_reference` already refuses `gbstk='C'` — keep that;
   - for partly referenced quotations, propose only the open quantities.
4. Display:
   - `VA03` for a billing document: show "returned" and "credited" per item;
   - `VF03`: same.

**Tests:**
- full return, then a second return → refused;
- 1 + 1 of 2 → accepted, third → refused;
- credit memo above the remaining value → refused;
- quotation for 12, order for 5 → quotation partly referenced, second order for 7 accepted, third refused.

### 4.4 BUG-006 · Reservation-aware reversal of goods issues · S

**Design.**
1. Add `rsnum TEXT`, `rspos INTEGER` to `mat_doc_item` (`MM_COLUMN_ADDS`). `_insert_line` writes them from the raw item (`raw.get("rsnum")`, `raw.get("rspos")`); pass `raw` through `_post_item` into the line dict.
2. `cancel_document`:
   - for every original line with `bwart` in 261, 262, 201, 202 that has an order or a reservation, call `pp.order.withdrawn` after posting the reversed line;
   - use the reversed movement type (261 → 262 and so on);
   - pass `{"rsnum": l["rsnum"], "rspos": l["rspos"]}`; when these are empty (old documents), fall back to the order lookup that `withdrawn` already does.
3. Remove the duplicated adjustment loop from `pp/order.py:cancel_confirmation` (lines 506–508), otherwise backflush reversals reduce `enmng` twice.
4. **Migration (best effort, old documents):**
   - fill `rsnum` = `aufnr` for lines with `aufnr` and `bwart` 261/262;
   - leave `rspos` empty — `withdrawn` finds the position by material.

**Tests:**
- picking + MBST → `enmng` back to 0 and the order back in `CO27`;
- the existing confirmation-cancel test still passes;
- new invariant 7 (section 4.12) holds.

### 4.5 BUG-007 · Goods receipt cannot be reversed below the invoiced quantity · S

**Design.**
- In `_post_item` for `ref == "PO"` and `bwart` in (102, 122) — and in `cancel_document` for an original 101/123 line with `ebeln` — check `po_item.wemng − qty ≥ po_item.remng`.
- Message `M7 033`: "Goods receipt cannot be reversed: %s already invoiced - cancel the invoice first (MR8M) or post a credit memo".
- Exception: account-assigned items with "GR non-valuated" do not exist today; ignore.

**Tests:**
- the review reproduction is refused;
- after MR8M it is accepted.

### 4.6 BUG-008 · Duplicate vendor invoice check · S

**Design.**
1. Vendor master column `reprf INTEGER DEFAULT 1` (`MD_COLUMN_ADDS` on `vendor`), shown in the vendor accounting view (FK02 / XK02) with change document.
2. Make the reference (`xblnr`) mandatory for document types `KR`, `RE`, `KG` (FB60, MIRO, FB65, F-90). Message `F5 116`.
3. `fi/ap.py: _check_duplicate(conn, lifnr, xblnr, bldat, gross, waers, exclude=None)`:
   - normalise `xblnr` (upper case, trimmed, inner spaces removed);
   - search vendor lines `koart='K' AND lifnr=?` of documents with `stblg IS NULL`, the same normalised `xblnr`, `bldat` and `waers`;
   - same gross amount → error `F5 117` "Invoice %s of vendor %s already posted as document %s";
   - different amount → warning in the result (the screen shows it, posting continues).
4. Call it from `miro`, `vendor_invoice` and `fi/aa.py: acquire` (with vendor), but only when the vendor's `reprf` is set.

**Tests:**
- the review reproduction raises `F5 117`;
- after MR8M of the first invoice the second posts;
- a vendor with `reprf=0` can post twice.

### 4.7 BUG-009 · Re-runnable period-end programs · M

**a) VAT settlement — settle by clearing (SAP behaviour).**
1. `vat_report` keeps working on uncleared tax lines: add `AND i.augbl IS NULL` for the settlement mode. Keep a "display all" mode for the report.
2. `vat_settlement` posts the FB41 document, then sets `augbl = <FB41 document>` on every tax line it settled, **and** on the FB41 tax lines themselves.
3. A second run for the same period finds nothing to settle → message `FF 010` (already exists).
4. FBRA (4.2.3) with reverse reopens the period.
5. Table `vat_run(d1, d2, belnr, gjahr, payable, usnam, ts)` for the closing cockpit (status "VAT settled for 10/2026").

**b) FX valuation.**
1. Table `fx_run(key_date PRIMARY KEY, belnr, gjahr, reversal_belnr, usnam, ts)`.
2. Update run refuses a key date that has a run without reversal. Message `F5 830`. Offer "Reverse and repeat".
3. Post the reversal **immediately**: second document dated key date + 1, if that period is open, otherwise leave `stodt` for F.81 as today. This removes the dependency on someone running F.81.
4. Valuation must include **G/L accounts managed in foreign currency** (bank accounts in USD) later; note it as GAP-FI-14 (B).

**c) Payment run status.**
1. Replace `INSERT OR REPLACE INTO payrun` (`fi/ap.py:374`):
   - read the row for (`laufd`, `laufi`);
   - if `status='PAID'` → error `F0 002` for proposal and execution alike;
   - if `status='PROPOSAL'` → update the row;
   - otherwise insert.
2. Add `delete_proposal(conn, laufd, laufi)`.
3. Execution must pay the **stored proposal** (the items the user saw), not a freshly computed list:
   - read `payments` from the row;
   - re-check that each item is still open;
   - skip and report items that are not.

   This is the SAP rule "proposal → edit → payment".
4. Add an "exclude item" action on the proposal screen (`F110` tab "Proposal").

**d) GR/IR clearing header without items** (`fi/gl.py:211`).
1. Do not create an `acc_doc` header. Clearing only needs a clearing number:
   - take the number from range `FI_01` as today;
   - store `augbl` on the items;
   - record the run in a table `grir_run(budat, augbl, items, usnam, ts)`.
2. **Migration:** delete headers without items whose `tcode='F.13'` (the demo has one) — they are not documents.

**Tests:**
- VAT twice → second refused; FBRA → can settle again;
- FX twice → refused;
- payment run: proposal after payment → refused; payment pays exactly the proposed items;
- invariant 1 (no header without items) holds.

### 4.8 BUG-012 · Integer arithmetic in billing and input parsing · M

**Design.**
1. New helpers in `mm/util.py` (all `Decimal`-based, raising `MMError 00 088` on bad input):
   - `parse_price(text)` → cents;
   - `parse_pct(text)` → basis points;
   - `parse_rate(text)` → × 100000;
   - `parse_int(text, what, lo, hi)`.
2. Replace:
   - `sd/order.py:268` → `parse_price`;
   - `pur/po.py` `rabatt` → `parse_pct`;
   - `fi/gl.py:51` → `parse_rate`;
   - `grep -rn "float(" mm co fi pur md pp sd` for the remaining ones (keep `float` only where a value is formatted for display).
3. Partial billing (`sd/billing.py:96`):
   - for every pricing field (gross, discount, freight, cost, tax) compute `already = sum over earlier non-cancelled billing items of the same order item`;
   - if `billed_qty + q == kwmeng` (last part), take `field_total − already`;
   - otherwise `rdiv(field_total × q, kwmeng)`.

   Do the same for `cogs` from the delivery (already exact) and for the CO-PA values derived from these fields.
4. Tax at billing is recomputed per document from the net (`sd/billing.py: post`). Keep that, but check: if the order item tax was computed on net + freight, the billing must use the same base (`sd/pricing.py`).

**Tests:**
- property test: items with random price/discount/freight/quantity, billed in random partial deliveries — sums equal the order item exactly;
- `price="abc"` → HTTP 422.

### 4.9 CODE-001 · Cross-year periods in Controlling · M

**Design.**
1. `co/core.py: upto(gjahr, perio, alias="")` returns the SQL fragment `(gjahr*12+perio) <= ?` and the parameter `gjahr*12+perio`.
2. Use it instead of `gjahr=? AND perio<=?` in:
   - `co/period_end.py:_prod_orders`, `_order_actuals`, `settle` (order balance);
   - `pp/service.py: wip`;
   - every CO report that shows an order's cumulative balance (`co/reports.py: order_analysis`, `order_list`).

   Cost-center reports stay per year.
3. Index `co_item(objnr, gjahr, perio)` (also section 6.2).
4. Variance calculation (`variances`):
   - targets use `o.wemng` (cumulative), actuals become cumulative over years — this is correct for production orders (SAP calculates variances cumulatively);
   - store the result per period as today.

**Tests** (needs the clock): release an order and issue components on 2026-12-20, confirm and receive on 2027-01-10, close January → variance includes the December material, the order balance is zero after settlement.

### 4.10 CODE-002 · Settlement to standard-price material · S

`co/period_end.py:415`:
- `to_stock = bal if v and v["vprsv"] == "V" and v["lbkum"] > 0 else 0`;
- when `verpr` changes, write a `price_history` row "KO88 settlement".

Test: a ZREF order for a standard-price spare part → the full balance goes to PRD; `salk3` = `lbkum × stprs`.

### 4.11 CODE-004 · Writers protect themselves · S

Wrap the bodies of these functions in `with transaction(conn)` (free when nested):
- `fi.document.write`, `fi.document.clear`;
- `co.core.post_co_doc`, `co.core.reverse_co_doc`;
- `co.period_end._copa_post`;
- `md.changes.log`.

### 4.12 TEST-004 · Invariant checker · M

`qa/invariants.py: check(conn) → list of violations`. Each violation is a dict with `rule`, `object`, `expected`, `actual`, `hint`.

| # | Rule | Query idea |
|---|---|---|
| 1 | Every FI document balances; no header without items | group `acc_doc_item` by `belnr, gjahr`; left join headers |
| 2 | `valuation.lbkum = Σ quant.qty` per material/plant | join |
| 3 | Standard price: `salk3 = value_of(lbkum, stprs, peinh)`; moving average: `lbkum=0 ⇒ salk3=0`, `salk3 ≥ 0` | |
| 4 | Stock G/L per valuation class = Σ `salk3` | `mm.reports.consistency_check` |
| 5 | Vendor / customer / asset reconciliation accounts = sub-ledger | sum by `koart` vs by recon `hkont` |
| 6 | GR/IR per PO item = value received − value invoiced; `remng ≤ wemng` | `mat_doc_item` + `inv_item` |
| 7 | `orders.wemng` = Σ 101 − Σ 102 for the order; `pp_resb.enmng` = Σ 261 − Σ 262 per reservation | needs 4.4 columns |
| 8 | Sales: delivered ≤ ordered (+ tolerance); billed ≤ delivered; returned ≤ billed | `sd_lips`, `billing_item`, `sd_vbap` |
| 9 | CO primary costs = FI per cost element and period; closed orders have zero balance; `co.reports.reconcile` ok | |
| 10 | `augbl` set ⇔ `augdt` set; every clearing group sums to zero | |
| 11 | `number_range.current ≥` highest used number per object | |
| 12 | No document dated after today (warning, not error) | |

**Where it runs:**
- screen `ZQA_CHECK` (Execute → list, drill-down links);
- in the calendar test;
- at the end of each test module (`tearDownModule`);
- in the QA runner (shown as a process "Data consistency").

---

## 5. Phase 3 — Robust API and platform

### 5.1 ROB-001 · Input parsing and the API fuzz test · M

**Design.**
1. Helpers in `mm/util.py`:
   - `parse_int`, `parse_year` (1900–2999), `parse_period` (1–16);
   - `parse_key(text, what)` — required non-empty key, upper-cased;
   - `require(body, *names)` — returns the values or raises `00 055` "Enter %s".
2. Replace the two generic helpers `web/co_api.py:25` and `web/fi_api.py:18` (they parse `gjahr`, `perio`, `pfrom`, `pto` from the query) with these.
3. Go through the 76 call sites listed in the review (section 6.1). In each case replace `int(x)` by `parse_int(x, "<field>")` and `body["x"]` by `require(...)`. Two special cases:
   - `sd/order.py:388` `reschedule`: raise `V1 302` when the order does not exist;
   - `pp/reports.py:32` and `web/pp_api.py:137`: parse dates with `parse_date`.
4. New `tests/test_api_fuzz.py` (harness in review section 11.2):
   - every route, with an empty body and with a junk body;
   - pass = `MMError` or a normal result;
   - fail = any other exception, or a transaction left open (`conn.in_transaction`).
   - Skip only `shutdown`, `bye`, `qa/run` and the Office routes. For Office routes, test only that they answer a business error when Office is missing.
5. `_dispatch` keeps returning HTTP 500 for unknown errors, but with the generic text and log reference (3.7).

**Acceptance.** Zero failures in `test_api_fuzz.py`.

### 5.2 BUG-014 · No SQL writes in API handlers · S

Move each statement into an engine function with transaction, validation and change document:

| From | New function | Notes |
|---|---|---|
| `web/fi_api.py:206` (vendor payment terms / posting block) | `md/partner.py: change_vendor_company(conn, lifnr, data, user)` | payment terms and posting block are sensitive → the dual-control rule of FK08 applies when the policy table says so |
| `web/fi_api.py:319` (customer payment terms / credit limit) | `md/partner.py: change_customer_credit(conn, kunnr, data, user)` | credit limit change: change document; above a threshold (configurable) needs confirmation by a second user (FD32 dual control) |
| `web/pur_api.py:335` (MRP parameters) | `md/material.py: change_mrp_view(conn, matnr, werks, data, user)` | validate MRP type, lot size, values ≥ 0 |
| `web/sd_api.py:148` (condition delete) | `sd/pricing.py: delete_condition(conn, knumh, user)` | change document object `COND` |
| `web/qa_api.py:51` | `qa/lms.py: set_status(...)` | remove `c.commit()` |

Guard test: scan `web/*.py` for `execute("INSERT|UPDATE|DELETE` → must be empty.

### 5.3 ROB-002 · Database and server plumbing · M

1. **Split `connect`.**
   - `mm.db.open_db(path)` opens the database and sets the pragmas `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=30000`.
   - `mm.db.migrate(conn)` creates the schema, runs the column upgrades and the numbered migrations (point 2), and inserts default rows.
   - `run.py` calls `migrate` once at start. `web/server.db()` calls only `open_db` (one connection per thread, reused while the thread lives).
   - `connect()` stays as `open_db + migrate` for tests and tools.
2. **Schema version.**
   - `settings('schema_version', N)`;
   - `mm/migrations.py` holds an ordered list of steps `(number, description, function)`;
   - `migrate` runs every step above the stored version inside one transaction and stores the new version;
   - the back-fills of this plan (4.2.1, 4.4, 4.7d) become migration steps.
3. **Indexes** (migration step):
   - `acc_doc_item(hkont)`, `acc_doc_item(koart, lifnr, augbl)`, `acc_doc_item(koart, kunnr, augbl)`;
   - `acc_doc(budat)`, `acc_doc(awkey)`;
   - `mat_doc_item(ebeln, ebelp)`, `mat_doc_item(aufnr)`;
   - `po_item(matnr, werks)`;
   - `co_item(objnr, gjahr, perio)`;
   - `copa_item(gjahr, perio)`;
   - `sd_vbap(matnr)`, `sd_lips(vgbel, vgpos)`;
   - `billing_item(aubel, aupos)`;
   - `pp_resb(matnr, werks)`;
   - `pr_item(matnr, werks)`.

   Verify each with `EXPLAIN QUERY PLAN` on FBL1N, KSB1, MB51, MD04 and the cockpits.
4. **HTTP/1.1.** Set `Handler.protocol_version = "HTTP/1.1"`; every response already sends `Content-Length`; static files too. Browsers then reuse connections (fewer threads, fewer DB opens).
5. **Backup.**
   - `run.py --backup` and `tools/Backup.bat` copy the database with `sqlite3.Connection.backup` to `data/backup/mm_YYYYMMDD_HHMMSS.db`;
   - an automatic backup is taken before `--reset` and once per day at first start;
   - keep the last 14;
   - `run.py --restore <file>` copies a backup back, after stopping a running server.
6. **Integrity.** At start, run `PRAGMA quick_check`. On failure, log it and open the error page from 3.7 with the advice to restore a backup.
7. **Static path.** `web/server.py:404`: replace the `startswith` test by `os.path.commonpath([full, STATIC]) == STATIC`.
8. **Host option.** `run.py --host` other than 127.0.0.1 / localhost is refused until Phase 5 is done. Message: "Remote access requires user login (Phase 5)".

### 5.4 SEC-002 / SEC-003 · Requests from other web sites · S

In `_dispatch`, before routing:
1. `Host` header must be `localhost:<port>` or `127.0.0.1:<port>`. Otherwise answer 403 (DNS-rebinding protection).
2. For POST:
   - `Content-Type` must start with `application/json` → otherwise 415. A JSON content type cannot be sent by a plain HTML form or a "simple" cross-site `fetch`; the browser sends a pre-flight that this server does not answer, so the request is blocked.
   - If an `Origin` header is present it must equal `http://localhost:<port>` or `http://127.0.0.1:<port>` → otherwise 403.
3. Static GET requests stay open.
4. `core.js` `api()` already sends `Content-Type: application/json` for POST. `navigator.sendBeacon` for `/api/bye` sends `text/plain`; change it to a `Blob` with type `application/json`, or exempt `/api/bye` and `/api/ping` (harmless).
5. Error texts: generic message with reference (3.7).

**Test.** Requests with a foreign `Origin`, a missing content type or a foreign `Host` → 403/415; normal UI calls pass (browser sweep).

### 5.5 ROB-003 · User-interface fixes · S

1. `ME23N`, `KSB5`, `ME9F`, `ZMM03_LF`, `ZXD03_LF`, `ZXK03_LF`: do not call the API when the key field is empty; show the selection screen with an "Execute" button.
2. Add to `web/static/menu.js` (or delete): `OKEON FAGLB03 S_ALR_87012284 ME52N ME12 ME1L ME13 ME03 ME61 ME6H S_ALR_87012182 S_ALR_87012089 CS12 MC82 KKAO VKM3 IW53`. Suggested places:
   - Procurement → Master data: ME12, ME13, ME03, ME1L;
   - Procurement → Reporting: ME61, ME6H;
   - Procurement → Requisition: ME52N;
   - FI → Reporting: FAGLB03, S_ALR_87012284, S_ALR_87012182, S_ALR_87012089;
   - CO → Master data: OKEON;
   - PP → BOM: CS12;
   - PP → SOP: MC82;
   - CO → Period end: KKAO;
   - Sales → Credit: VKM3;
   - Service: IW53.
3. Add a permanent UI smoke test `tests/ui/smoke.js` (optional, Node + Playwright): open every screen, press Execute, fail on page errors and HTTP ≥ 500.

### 5.6 CODE-005 … CODE-011 · Small corrections · S each

| ID | Fix |
|---|---|
| CODE-005 | `miro`: validate `mwskz` like `vendor_invoice` (input tax code); `ebelp` through `parse_int`; message text without the hard-coded "14 %" |
| CODE-006 | `pur/po.py:147`: info-record update writes only `ebeln/ebelp` ("last PO"); prices change only through ME12 or an awarded quotation; flag on the PO item "info update" for the buyer who wants it |
| CODE-007 | One credit function: `fi.ar.check_credit` calls `sd.order.credit_check` (open items + open orders + oldest overdue); exposure includes open credit-memo requests as negative and open deliveries via their orders (no double count) |
| CODE-008 | `bank_statement`: store `json.dumps(lines)`; sign and amount through `Decimal` |
| CODE-009 | `mm.config.GL_ACCOUNTS`/`PNL_ACCOUNTS` are loaded from `gl_account` in `migrate` and refreshed by `save_gl_account`; `ON CONFLICT` updates `typ` and `recon` only when the account has no postings, otherwise error `FH 030` |
| CODE-010 | Rush order: delivery created inside the order's transaction; if it fails, the order is still saved and the message says "delivery could not be created: …" |
| CODE-011 | `mrp_run`: implement exception messages 10 (bring forward) and 15 (postpone) for fixed receipts, or delete the unused loop; register number range `PLAF` in `pp/schema.py`; `convert`: check inside the transaction; `_ = sign` in `sd/order.py:280` removed; `delivery.create(items=…)` normalises keys with `str()`; one list of production order types in `pp/config.py` used by `co/integration.py:21` and `co/period_end.py:206`; `fi/aa.py:140` dead assignment removed |

### 5.7 TEST-002 · API happy-path tests · M

`tests/test_api_flows.py` drives the four main cycles (P2P, O2C, plan-to-produce, record-to-report) through the route handlers (`web.server.ROUTES`), not the engines. It checks:
- every amount and quantity in the JSON equals the database value divided by 100 / 1000;
- no field is mis-scaled. The `AMT`/`QTY` name sets in each `*_api.py` decide scaling by field name; a new field in the wrong set is caught here.

Medium term: replace name-based scaling by explicit conversion where the dict is built.

---
## 6. Phase 4 — Close the process gaps

### 6.1 BUG-003 · Sales requirements in MRP, one availability logic · L

**Design.**
1. **One element function.** Move `pp/planning.py: _elements` into `pp/elements.py: elements(conn, matnr, werks, today, exclude_sd=None)`. It is used by MD04, MRP, ATP (`sd/order.py: atp`) and pegging (MD09).
2. **New requirement elements:**

   | Type | Source | Quantity | Date |
   |---|---|---|---|
   | `VC` customer order | `sd_vbep` of documents with `vbtyp='C'`, item not rejected, item category relevant for delivery | ordered quantity of the schedule line minus quantity already in deliveries (`sd_lips` for this item, any status) | `mbdat` (material availability date) |
   | `VJ` delivery | `sd_lips` of deliveries with `wbstk<>'C'` | `lfimg` | delivery's planned goods-issue date `wadat` |
   | `VR` returns (later) | not a requirement; returned goods arrive in blocked stock | — | — |

   **Credit-blocked orders.** They stay requirements (SAP shows them). A material master flag can exclude them later.
3. **ATP uses the same list.**
   - `atp()` takes stock − safety stock (if the checking group says so) + receipts − requirements up to each date, excluding the order being checked (`exclude_sd`), and confirms against the cumulative ATP quantity.
   - Today `atp()` subtracts "committed sales" separately (`committed_sales`); that function disappears.
4. **PIR consumption (strategy 40).**
   - Use the existing column `material_plant.strgr` (planning strategy group: `10` make-to-stock net requirements, `40` planning with final assembly). Fill it with `40` for FERT where it is empty.
   - For strategy 40 the sales order item **consumes** the PIR of its month (backward 30 days, then forward 30 days) at order entry.
   - Store the consumption in table `pp_pir_consumption(vbeln, posnr, month, qty)`.
   - The PIR's open quantity is reduced by the consumed quantity. The order is then the requirement, so the PIR is not counted twice.
   - Goods issue reduces the PIR permanently. Rejecting an order item or reducing its quantity gives the consumption back.
   - Remove the consumption at billing (`sd/billing.py` / `pp/planning.py:148` `consumption()` with `bedae` logic). Today "consumed by sales (billing)" is mentioned in the docstring at `pp/planning.py:7`.
   - Strategy 10: PIR reduced at goods issue only, and sales orders are **not** MRP requirements (classic make-to-stock). Add this as a strategy choice, but the demo uses 40.
5. **MD04 screen.** Show the new types with links: VC → VA03, VJ → VL03N. **MD09 pegging:** a planned order shows which sales orders it covers.
6. **MRP run.**
   - Sales elements appear automatically, because MRP reads `elements()`.
   - Add exception message `20` "Requirement date in the past" for overdue sales schedule lines.
7. **Rescheduling.** After an MRP run that creates receipts, `V_V2` (`sd/order.py: reschedule`) confirms backorders against them. Add a "reschedule all backorders" action in `V.02`.

**Tests:**
- backorder of 50 FG-3002 → MRP → planned order of ≥ 50 dated ≤ material availability date; convert, release, confirm, GR → `V_V2` confirms the order fully;
- strategy 40: PIR 200 for the month, order 30 → open PIR 170 and MRP requirement total 200 (not 230);
- rejecting the order → PIR open 200 again.

### 6.2 BUG-010 · Foreign currency in purchasing (then sales) · L

**Data model (`PUR_COLUMN_ADDS`, `MM_COLUMN_ADDS`):**

| Table | New columns |
|---|---|
| `po_header` | `waers` (already exists — fill it with the vendor currency), `wkurs` (rate at PO date ×100000, information) |
| `info_record`, `contract` | `waers` |
| `mat_doc_item` | `waers`, `kursf`, `wrbtr` (value in PO currency) |
| `inv_item` (4.2.1) | `wrbtr` |

**Rules:**
1. **PO creation.** `waers` = vendor currency, or overridden on the PO. Prices are in PO currency. `_value` (release strategy) converts to local currency at the PO date rate.
2. **Goods receipt (`mm/posting.py` `ref == "PO"`):**
   - `ext_fc = value_of(qty, netpr, peinh)`;
   - `kursf = rate(conn, waers, budat)` (error `SG 105` when no rate exists);
   - `ext = to_local(ext_fc, kursf)`;
   - store `waers`, `kursf`, `wrbtr` on the line.

   Freight (`frb`) is in PO currency too: convert the same way.
3. **Invoice (`miro`):**
   - document currency = PO currency; `kursf` = rate of the posting date;
   - per item, the GR/IR line is debited with the **local value of the receipts being invoiced** — not with the invoice rate. Take the GR local value from `mat_doc_item` receipts of the item, oldest first, quantity not yet invoiced (the same FIFO logic as `remng`);
   - in document currency, GR/IR = `value_of(qty, netpr, peinh)` in FC;
   - the exchange-rate difference = invoice local − GR local, split like a price difference:
     - moving-average material with stock coverage → stock;
     - rest → account key `KDM` (new in `mm/config.py` account determination, account e.g. `231600 "Exchange rate differences from invoice"`);
   - tax lines in FC converted at the invoice rate;
   - the vendor line is balanced in both currencies by `_balance_partner` (already exists).
4. **Payment.** `fi/ap.py: pay` already supports FC and realised differences — no change.
5. **FX valuation.** Already handles FC open items — no change.
6. **GR/IR in FC.** The GR/IR account then holds lines with different currencies. F.13 clears by **local** balance per PO item (already the case). If FC = 0 but local ≠ 0 after rounding, post the rest to `KDM` in F.13.

**Sales (second step, separate PR):** add `waers` to `customer` (column does not exist yet), `sd_vbak`, `billing`; condition records per currency; billing posts in document currency through `fi.document.write(..., waers, kursf)`; CO-PA in local currency.

**Tests:** the scenario in review BUG-010 "Done when", plus:
- partial invoices at two different rates → GR/IR of the item ends at zero local after F.13;
- MR8M of an FC invoice.

### 6.3 BUG-011 · Delivery change/delete, rejection rule, checks at goods issue · M

1. `sd/order.py: change` — rejection allowed only when `SELECT 1 FROM sd_lips WHERE vgbel=? AND vgpos=?` finds nothing. Message `V1 306` "Item %d has delivery %s - delete or reduce it first (VL02N)".
2. `sd/delivery.py: delete(conn, vbeln, user)`:
   - only when `wbstk <> 'C'`;
   - delete `sd_lips`, `sd_likp` and the `sd_vbfa` rows with `vbeln = delivery`;
   - recalculate the order status;
   - change document object `LIEFERUNG`.
3. `sd/delivery.py: change(conn, vbeln, items, user)`: reduce `lfimg` per item before goods issue (0 = delete the line); not above the open order quantity.
4. Reversed goods issue (VL09) leaves the delivery as "not posted" — it can now be deleted or posted again (already possible).
5. `post_gi` re-checks:
   - order item not rejected;
   - order not delivery-blocked;
   - **credit** (6.6).
6. **Screens.** `VL02N`: "Delete delivery" and editable quantities before goods issue.
7. **Delivery quantity rule.**
   - `done` in `delivery.create` keeps counting all delivery lines (open and posted) — correct.
   - Old wrong deliveries can now be deleted, so nothing remains blocked forever.

**Tests:** the review reproduction is refused; delete delivery then reject → accepted; reduce the delivery to 1 of 3 → the next delivery proposes 2.

### 6.4 BUG-013 · Operation sequence and confirmation details · M

1. `pp/config.py` `ORDER_TYPES[...]["sequence"]` = `"E"` (error) for PP01/ZP03/ZREF/ZP07, `"W"` for SM01.
2. `confirm`:
   - predecessor = previous operation in `vornr` order whose control key is not external;
   - **limit** = predecessor `lmnga` (yield) + tolerance; for the first operation the limit is the order quantity + tolerance;
   - external predecessors count with the GR quantity of their purchase order (`po_item.wemng` of `pp_oper.banfn → ebeln`);
   - message `RU 006` "Operation %s: quantity %s exceeds the yield %s of the previous operation %s".
3. **Final confirmation backflush.**
   - On the final confirmation of the **last** operation, backflush the **remaining** open quantity of backflush components that belong to this operation or have no operation: `q = bdmng − enmng`.
   - Replace the no-op at `pp/order.py:436-437`.
4. **Scrap reason.** Add `grund` (reason code) to `confirmation`; required when scrap > 0. Codes in `pp/config.py`: 01 material defect, 02 machine, 03 operator, 04 setup. Show them in the order report.
5. **Tolerances.** Over-confirmation % and over-delivery % per order type in `ORDER_TYPES` (default 10 %). Replace the literals at `pp/order.py:413` and `mm/posting.py:230`.
6. **Picking quantity.** `post_picking` refuses `qty > open reservation qty` unless the order type allows over-withdrawal. Message `M7 102`.
7. **GR without issue.** The order GR result includes a warning when no component was issued and no operation confirmed; COOIS shows status `NOCONF`.

**Tests:** the review reproduction is refused; 0010 confirmed 5 of 10 → 0020 can confirm up to 5 (+10 %); final confirmation backflushes the rest.

### 6.5 GAP-SD-01 · Full sales order change (VA02) · L

`sd/order.py: change(conn, vbeln, data, user)` gains item changes:

| Change | Rules |
|---|---|
| Quantity | Not below delivered quantity. Re-price only quantity-dependent conditions (scales); re-run ATP for the item; give back / take PIR consumption (6.1); change document |
| Price / discount | Allowed while not billed; manual change requires a reason code; new pricing through `pricing.price_item` with manual values; margin warning as on create |
| Requested date | Re-run ATP for all open schedule lines |
| Add item | Same path as create (`_add_item`), next item number |
| Delete item | Only when nothing references it (no delivery, no billing); otherwise reject with reason |
| Ship-to | Must be a partner of the sold-to |

After every change:
- recompute totals;
- run the credit check again if the value went up (6.6);
- recompute incompletion;
- write change documents per field.

The screen `VA02` gets editable item lines.

### 6.6 GAP-SD-04 / LINK-12 / CODE-007 · Credit management at every step · M

1. **One function.** `sd/credit.py: check(conn, kunnr, add_value, today, exclude=None, step)`, with `step` in `order`, `change`, `delivery`, `goods_issue`. It reuses `exposure` and the oldest-overdue rule.
2. **Order create / change.** Blocks the order (`cmgst='B'`) as today.
3. **Delivery create.** Refuses for a blocked order (exists).
   - New: re-check when the order was released more than N days ago (`CREDIT["recheck_days"]`, default 7) and the exposure grew since.
4. **Goods issue.** Re-check; if it fails, refuse goods issue with `VL 466` and block the order again.
5. **Release list (VKM1).**
   - Actions: release, reject (item rejection with reason 60 "credit"), forward to another credit manager (note).
   - The release stays valid for `CREDIT["release_days"]` days or until the value increases by more than 10 %.
6. **Exposure.**
   - Open items + open orders (not yet delivered) + open deliveries (not yet billed) + billed-not-posted;
   - minus open credit-memo requests;
   - no double counting: an order item counts its open quantity only, a delivery its unbilled quantity.

### 6.7 LINK-07 · Commitments in Controlling · M

1. **Table `co_commit`:** `objnr`, `kstar`, `gjahr`, `perio`, `refbt` (PR/PO), `refbn`, `refbz`, `amount` (local), `qty`.
2. **Who writes it:**
   - a PR item with account assignment K or F writes a commitment;
   - a PO item created from it moves the commitment from PR to PO;
   - the GR (for account-assigned items) or the invoice (when no GR) reduces it proportionally;
   - PO deletion, the "delivery completed" flag and PR rejection remove the rest.
3. **Cost element.** `sakto` of the item (primary cost element).
4. **Reports:**
   - KSB1 / KOB1 show commitments in a separate column "Commitment";
   - cost-center plan/actual (S_ALR_87013611) gets "Actual + commitment" and "Available";
   - new line-item report `KSB2` / `KOB2`.
5. **Year end.** Open commitments roll into the new year on the delivery date's period.

### 6.8 LINK-17 · MRP for every plant · S

`MD01` screen sends the plant; "all plants" runs `mrp_run` per plant with MRP-relevant materials. `pur/mrp.run` (reorder point) per plant too.

---

## 7. Phase 5 — Users, authorisations, audit

### 7.1 SEC-001 · Login and sessions · M

1. **Tables:**
   - `usr(bname PK, name, pw_salt, pw_hash, locked, valid_from, valid_to, lang, last_login, failed)`;
   - `usr_session(token PK, bname, created, last_seen, ip)`;
   - `role(name PK, text)`, `usr_role(bname, role)`;
   - `role_tcode(role, tcode)`;
   - `role_auth(role, object, field, value)`.
2. **Passwords.**
   - `hashlib.pbkdf2_hmac("sha256", pw, salt, 200000)`, 16-byte random salt;
   - minimum 8 characters; change forced at first login;
   - five failed logins lock the user.
3. **Session.**
   - random 32-byte token in cookie `mmcore_session` (`HttpOnly`, `SameSite=Strict`, path `/`);
   - idle timeout 8 hours;
   - logout deletes the row.
4. **`Handler.user`** returns the session user; the `X-User` header is honoured only when the server runs with `--dev` (tests, tools). API calls without a valid session → 401; the SPA shows the login form.
5. **First start of an existing database.** Create user `ADMIN` with a one-time password printed on the console and written to `data/first_login.txt` (deleted after the first successful login). Demo users (section 7.3) only in a newly seeded demo database.
6. **Screens.**
   - `SU01`: users — create, lock, reset password, assign roles;
   - `PFCG`: roles — T-codes and authorisation values;
   - `SU53`: last failed authorisation check;
   - `SM04`: sessions — list and end.

### 7.2 Authorisation checks · M

1. **Transaction start.**
   - Every API route is mapped to a T-code (a table in `web/auth_map.py`, generated once from the screens' API calls, then maintained).
   - `_dispatch` checks that the user's roles contain the T-code → otherwise 403 with message `00 077` "No authorization for transaction %s".
   - The menu hides T-codes the user may not start.
2. **Business objects** checked inside the engines through `auth.check(conn, user, object, **fields)`:

   | Object | Fields | Used in |
   |---|---|---|
   | `M_BEST_EKG` | purchasing group, activity | PO create/change |
   | `M_EINK_FRG` | release code | PR / PO release |
   | `M_MSEG_BWA` | movement type | goods movements |
   | `M_MSEG_WWA` | plant | goods movements |
   | `V_VBAK_AAT` | order type, activity | sales documents |
   | `V_KNKK_FRE` | credit release | VKM1 |
   | `V_VBRK_FKA` | billing type | billing, cancellation |
   | `F_BKPF_BLA` | document type | FI postings |
   | `F_BKPF_KOA` | account type | FI postings |
   | `F_LFA1_BEK` / `F_KNA1_BED` | sensitive fields confirm | FK08 / FD08 |
   | `F_REGU_BUK` | payment run execute | F110 |
   | `K_CSKS` | cost center | CO postings and reports |
   | `C_AFKO_AWK` | order type | PP orders |

3. **Two-person rules** keep the "different user" check and add the authorisation check:
   - credit release;
   - billing block 08;
   - FK08;
   - payment run execution (proposal user ≠ payment user, configurable);
   - PO release;
   - master-data approval.

### 7.3 Demo roles and users · S

**Roles:** SALES_CLERK, CREDIT_MANAGER, BUYER, PURCH_MANAGER, WAREHOUSE, QUALITY, PLANNER, SHOPFLOOR, AP_CLERK, AR_CLERK, GL_ACCOUNTANT, CONTROLLER, MD_MAINTAINER, MD_APPROVER, AUDITOR (display only), ADMIN.

**Users:** one per role (password = user name, forced change off in the demo only), and the seed's existing user names (DEMO, SALES01, PLANNER, CREDITMGR, SALESMGR) keep working as background users.

### 7.4 Audit log and approval inbox · M

1. **`audit_log(ts, bname, ip, tcode, object, key, action, detail)`.** Written for:
   - logon, failed logon, logout;
   - display of bank data (vendor / customer);
   - every release / approval / reversal / period open-close / user and role change.

   Screen `SM20` with filters.
2. **Approval inbox `ZINBOX`.** One list for the current user of everything waiting for them:
   - PR and PO releases (by release code);
   - credit blocks;
   - billing block 08;
   - sensitive master-data changes;
   - blocked invoices (6.2 / 8.2);
   - payment proposals to execute.

   Each line has a link to the action screen. Show a counter on the home page.

---

## 8. Phase 6 — Missing functions (priority A first)

### 8.1 GAP-MM-01 · Physical inventory · L

1. **Tables:**
   - `inv_doc(iblnr PK, gjahr, werks, lgort, plan_date, count_date, status [CRTD, CNTD, POST], ernam, freeze)`;
   - `inv_doc_item(iblnr, zeili, matnr, lgpla, insmk, buchm (book qty at freeze), menge (counted), xnull (zero count), counted_by, mblnr, zeile, diff_qty, diff_value)`.
2. **Functions** (`mm/inventory.py`):
   - `create(werks, lgort, materials | bins, date, freeze=True)` (MI01). With `freeze`, the book quantity is taken at creation; **posting block**: goods movements for those material/bin combinations are refused while the document is not posted (check in `post_goods_movement`). Message `M7 140`.
   - `count(iblnr, items)` (MI04): quantity or "zero"; a recount creates a new document for the selected items (MI11).
   - `difference_list(iblnr)` (MI20): book vs count, value at the current price, threshold highlight.
   - `post(iblnr, budat, user, reason)` (MI07): posts 701 (surplus) / 702 (shortage) per item through `post_goods_movement` with reference to the inventory document. Items with zero difference are only closed. The value difference goes to the inventory-difference account (exists in account determination for 701/702).
3. **Cycle counting (MICN).** ABC indicator on `material_plant` (`abcin`); a list proposes materials whose last count is older than the interval for their class (A 30, B 90, C 180 days).
4. **Screens:** MI01, MI03 (display), MI04, MI11, MI20, MI07, MICN, and a count sheet print (8.9).
5. **Catalog.** Process INV step 5 points to MI01/MI04, step 6 to MI07 (fixes DOC-003). Test cases: freeze blocks movements; difference posting; zero count.

### 8.2 GAP-PUR-02 · Invoice tolerances and payment block · M

1. **Table `inv_tolerance(key, lower_abs, upper_abs, lower_pct, upper_pct, active)`** with SAP keys:

   | Key | Checks | Default |
   |---|---|---|
   | `PP` | price variance per item | +100.00 or 5 % |
   | `DQ` | quantity variance (invoice > GR not allowed today) | — |
   | `DW` | GR missing (invoice before GR) | — |
   | `BD` | small differences written off automatically | ±1.00 |
2. **`miro`:**
   - a price variance above the tolerance posts the invoice with **payment block** `zlspr='R'` on the vendor line (column on `acc_doc_item`);
   - a small total difference (`BD`) is posted to a "small differences" account instead of asking the user.
3. **Payment.** `pay` and `payment_run` skip items with `zlspr` set. The payment-run exception list shows "payment block R".
4. **MRBR.** Release blocked invoices:
   - list of blocked items with the variance reason;
   - the "release" action clears `zlspr` and writes the audit log;
   - the person who posted the invoice cannot release it (authorisation in Phase 5).
5. **Tests:** price +10 % → blocked; F110 skips it; MRBR releases; F110 pays.

### 8.3 GAP-PUR-03 / GAP-FI-05 · Egyptian withholding tax (WHT) · M

1. **Configuration table `wht_code(code PK, text, pct (bp), base ['NET'|'GROSS'], at ['INVOICE'|'PAYMENT'], hkont, valid_from, valid_to)`.** Seed the common categories:

   | Code | Purchase type | Rate |
   |---|---|---|
   | `W1` | supplies | 1 % |
   | `W3` | services | 3 % |
   | `W5` | professional fees | 5 % |

   The WHT payable account must be added to the chart (e.g. `176000 "Withholding tax payable"`). **Check the current rates with the company's tax adviser before go-live.**
2. **Vendor master** (`md_wht(lifnr, code, exempt_from, exempt_to, certificate_no)`): which codes apply to a vendor and exemption periods.
3. **Posting:**
   - **at invoice (default in Egypt):** `miro` / `vendor_invoice` add a credit line on the WHT account and reduce the vendor line by the WHT amount; the base is the net amount;
   - **at payment:** `pay` computes WHT on the paid net portion and posts it in the payment document.
4. **Report.** WHT by vendor and quarter (data for the tax form "41"): tax ID, name, base, rate, amount; export to Excel through the Office bridge or CSV.
5. **Tests:** invoice 10,000 net service → WHT 300, vendor 11,100 (net + VAT 1,400 − WHT 300); exempt vendor → no WHT.

### 8.4 GAP-FI-02 · Manual clearing of open items · M

`fi/clearing.py: clear_open_items(conn, koart, partner_or_account, items, budat, user, residual=False)`:
- **F-44** (vendor), **F-32** (customer), **F-03** (G/L with open-item management).
- The selected items must sum to zero, or the difference must be within the tolerance → difference to an "expense from payment differences" account; else refuse.
- With `residual=True`, the difference stays open as a residual item.
- Posts a clearing document with document type `AB`, using `fi.document.write` and `clear`.
- The screens list the open items with checkboxes and a running balance.

Also used by the vendor credit memo (8.5).

### 8.5 GAP-PUR-01 · Vendor credit memo and subsequent debit/credit · M

1. **`miro(..., credit=True)`:**
   - the quantity reduces `remng`;
   - the amounts are reversed;
   - used for returns (122) after an invoice.
   - Rule: credit quantity ≤ invoiced − credited, and ≤ returned quantity when the return exists.
2. **Subsequent debit / credit:** value only, `qty` stays, `remng` unchanged; the difference goes to stock (with coverage) or PRD like a price difference.
3. **BUG-007 relaxation.** A 122 return after an invoice becomes allowed **if** the user posts the credit memo afterwards. Add the check "open return quantity not credited" to the GR/IR list.

### 8.6 GAP-FI-03 · Down payments · M

1. Add `umskz` (special G/L indicator: `A` down payment, `F` down-payment request) to `acc_doc_item`.
2. **Alternative reconciliation accounts** per indicator, e.g.:
   - vendor `A` → `164000 "Down payments to vendors"` (asset);
   - customer `A` → `170000 "Customer down payments received"` (liability).
3. **Postings:**
   - **F-47 / F-37:** request (statistical, no balance);
   - **F-48 / F-29:** down payment with bank;
   - **F-54 / F-39:** clear the down payment against the invoice.
   - Payment-run support for requests.
4. **Reports.** Vendor / customer line items show special G/L items separately; the balance sheet shows them on their own accounts.

### 8.7 GAP-FI-04 · Posting periods per account type · S

1. `posting_period` becomes `(variant, koart ['+','A','D','K','M','S'], y1, p1, y2, p2, auth_group)`. Migration: one existing row → `+` row.
2. `period_open(conn, budat, koart)` checks the `+` row and the row for the account type of each line; the FI writer calls it per line.
3. **OB52 screen:** one line per account type; special periods 13–16 for year-end adjustments (posting date 31 December with period 13).
4. **MM period (GAP-MM-02)** separately:
   - table `mm_period(werks, gjahr, perio, prev_open)`;
   - goods movements allowed in the current MM period and, if `prev_open`, the previous one;
   - **MMPV** closes the period and writes `valuation_hist(matnr, bwkey, gjahr, perio, lbkum, salk3, verpr, stprs)`.

   This gives the stock of past periods (MB5B, GAP-MM-03) and is a prerequisite for actual costing (GAP-CO-04).

### 8.8 GAP-X-07 · Data import for go-live · M

**`tools/import/` screen `ZIMPORT`:**
- upload CSV (UTF-8, comma or semicolon, Arabic text allowed);
- choose the object;
- the system shows a preview with validation errors per line;
- "Simulate" then "Post";
- every line goes through the normal engine functions (no direct SQL), in one transaction per file with savepoints per line;
- result log with line number, status and message.

Objects and order of loading:

| # | Object | Engine function |
|---|---|---|
| 1 | G/L accounts | `fi.gl.save_gl_account` |
| 2 | Cost centers, activity types | `co.master` |
| 3 | Materials (all views) | `md.material.create` |
| 4 | Vendors, customers (with bank data, credit limit) | `md.partner` |
| 5 | Info records, conditions | `pur.sourcing`, `sd.pricing` |
| 6 | BOMs, routings, work centers | `pp.master` |
| 7 | Open vendor items, open customer items (with due dates) | `fi.ap.vendor_invoice` / `fi.ar.customer_invoice` against a takeover clearing account |
| 8 | G/L balances | `fi.document.write` against the takeover account |
| 9 | Stock per bin with value (561) | `post_goods_movement` |
| 10 | Assets with accumulated depreciation | `fi.aa.legacy_transfer` |

**After the load:** the takeover clearing account must be zero (check in the cockpit). Templates (header rows) can be downloaded from the screen.

### 8.9 GAP-X-04 · Print forms · M

- One HTML template engine (string templates in `web/static/forms/*.html` filled by a small renderer in `core.js`), with A4 CSS for printing. Company header from `settings`.
- Forms:
  - purchase order;
  - RFQ;
  - delivery note / picking list;
  - invoice (with e-invoice UUID and QR);
  - credit memo;
  - dunning letter;
  - payment advice;
  - inventory count sheet;
  - production order paper.
- Message status per document (printed / e-mailed) replaces the "printed" flag. E-mail through the existing Outlook bridge (`office/com_bridge.py`).

### 8.10 Remaining B items (short design notes)

| ID | Note |
|---|---|
| GAP-MM-04 batches | `charg` on `quant`, `mat_doc_item`, `sd_lips`, `pp_resb`; `batch` table with expiry; FEFO strategy |
| GAP-MM-05/06 special stocks, stock transport | `sobkz` on `quant`; PO type UB with 351/101; stock in transit as a quant with `insmk='T'` |
| GAP-FI-07 bank | house bank table; bank clearing accounts per payment method; F110 and F-53 post to clearing; statement import (CSV/MT940) clears it |
| GAP-FI-10 assets | PO account assignment `A` (LINK-09); ABUMN transfer; partial retirement; AuC with AIAB settlement; useful-life change with recalculation; catch-up depreciation |
| GAP-CO-04 actual costing | after GAP-MM-02; material-ledger categories; periodic unit price; multi-level settlement — own project |
| GAP-SD-05/06 output, down-payment billing, billing due list split | uses 8.9 forms |
| GAP-PP-03/04/05 capacity levelling, order change, CLSD | `pp/order.py: change` with re-explosion; close with checks (balance zero, no commitments, no open reservations) |
| GAP-MD-02 approval workflow, mass change | uses the inbox (7.4) |
| GAP-X-05 job scheduler | table `job(name, cron, last_run, next_run, status)`; a thread in the server runs due jobs (MRP, dunning proposal, backup) |
| GAP-X-06 Arabic UI | message catalogue keyed by `msg_class/msg_no`; UI string table; `dir="rtl"` layout switch; numbers stay Latin |
| Section 10 of the review (company code, config tables, hooks, valuation service, doc flow, front-end helpers, totals tables, CI) | do after Phase 5; one mechanical PR each |

---

## 9. Documentation corrections (DOC-001 … DOC-007)

| ID | Action |
|---|---|
| DOC-001 | P2P control "Three quotations above the limit": either implement (PO above a configurable value requires an RFQ collective number with ≥ 3 quotations, or an override reason with approval) — recommended, small — or change the text to "Price comparison documents the award". Add a negative test |
| DOC-002 | PTP control "Confirm in sequence, scrap with reason": becomes true with 6.4; link to the new test case |
| DOC-003 | INV step 5 → MI01/MI04, step 6 → MI07 after 8.1 |
| DOC-004 | R2R "Reverse, never delete": true after 4.2; add MR8M / FBRA / depreciation reversal test cases |
| DOC-005 | Messages in `fi/gl.py:101/108`: correct per 4.2.5 |
| DOC-006 | Regenerate all manuals after the catalog changes: `python -m qa.runner`; `python -m qa.export qa.json`; `node tools/manuals/make_manuals.js qa.json web/static/manuals <pptx skill dir>`; `node tools/manuals/make_manual_ar.js qa.json web/static/manuals <pptx skill dir>`. Update the Arabic content file `tools/manuals/ar_content.js` where steps change (INV step 5/6, P2P invoice step, R2R reversals) |
| DOC-007 | README: "86 cases / 115 tests" becomes the new numbers and states the fixed business date |

---

## 10. Migration of existing customer databases

Every structural change in this plan is a numbered migration step (5.3). Steps in order:

| Step | Change | Data back-fill |
|---|---|---|
| 1 | `schema_version` setting | — |
| 2 | `mat_doc_item.rsnum/rspos` | `rsnum = aufnr` for 261/262 with order |
| 3 | `inv_item` table | from MIRO documents (4.2.1) |
| 4 | `vendor.reprf` | default 1 |
| 5 | `vat_run`, `fx_run`, `grir_run` | `vat_run` from existing FB41 documents (period from text); delete F.13 headers without items |
| 6 | `fi_carry_forward` | none (fallback computes) |
| 7 | indexes | — |
| 8 | `po_header.waers` | vendor currency for POs **without** goods receipt; POs with receipts keep `EGP` (their documents are already local) and get a note |
| 9 | `pp_pir_consumption` (`material_plant.strgr` already exists) | `strgr = 40` for FERT where empty |
| 10 | `confirmation.grund` | empty |
| 11 | `co_commit` | build from open PR/PO items with account assignment |
| 12 | users, roles, sessions, audit | create ADMIN (7.1 step 5) |
| 13+ | Phase 6 tables | — |

**Before running the migrations:** the start-up takes an automatic backup (5.3 step 5). A failed migration rolls back and opens the error page; the old database stays usable with the previous program version.

---

## 11. New tests by item

| Item | Test (module.class.method) | Catalog case |
|---|---|---|
| 3.1 | `test_platform.Clock.test_no_direct_date_calls` | — |
| 3.2 | `test_platform.Transactions.test_savepoint_rolls_back_inner_only` | — |
| 3.3–3.6 | `test_calendar.Calendar.test_dates` (12 dates) | R2R-11 "Seed and books valid on any date" |
| 4.1 | `test_fi.YearEnd.test_carry_forward`, `…test_trial_balance_zero_new_year` | R2R-12 |
| 4.2 | `test_fi.InvoiceCancel.test_map_with_stock / _consumed / _standard / _account_assigned`, `test_fi.ResetClearing.test_payment_reset`, `test_fi.Assets.test_reverse_depreciation` | P2P-17, P2P-18, R2R-13, R2R-14 |
| 4.3 | `test_sd.References.test_return_limit / _credit_value_limit / _quotation_partial` | O2C-16, O2C-17 |
| 4.4 | `test_pp.Execution.test_picking_reversal_reopens_reservation` | PTP-16 |
| 4.5 | `test_pur.Postings.test_gr_reversal_blocked_after_invoice` | P2P-19 |
| 4.6 | `test_fi.Payables.test_duplicate_invoice` | P2P-20 |
| 4.7 | `test_fi.Closing.test_vat_twice / _fx_twice / _payrun_status / _grir_no_empty_header` | R2R-15 |
| 4.8 | `test_sd.ShippingBilling.test_partial_billing_sums_exact`, fuzz price | O2C-18 |
| 4.9 | `test_co.CrossYear.test_order_across_year_end` | CTL-08 |
| 4.10 | `test_co.ClosingResults.test_settle_to_standard_price_material` | CTL-09 |
| 4.12 | `test_invariants.Invariants.test_seed_clean` (+ teardown in every module) | new process "Data consistency" |
| 5.1 | `test_api_fuzz.Fuzz.test_all_routes` | — |
| 5.2 | `test_platform.Layers.test_no_sql_writes_in_api` | — |
| 5.4 | `test_platform.Http.test_foreign_origin_refused` | — |
| 5.7 | `test_api_flows.*` (4 cycles) | — |
| 6.1 | `test_pp.Planning.test_sales_order_in_mrp`, `…test_pir_consumption_strategy_40` | PTP-17, O2C-19 |
| 6.2 | `test_pur.Currency.test_fc_po_gr_invoice_payment` | P2P-21 |
| 6.3 | `test_sd.Shipping.test_delete_delivery / _reject_with_delivery_refused` | O2C-20 |
| 6.4 | `test_pp.Execution.test_operation_sequence / _final_backflush` | PTP-18 |
| 6.5 | `test_sd.Orders.test_va02_quantity_price_add_delete` | O2C-21 |
| 6.6 | `test_sd.Credit.test_recheck_at_goods_issue` | O2C-22 |
| 6.7 | `test_co.Commitments.test_pr_po_gr_flow` | CTL-10 |
| 7.x | `test_security.*` (login, lockout, tcode check, two-person rules with real users) | new process "Security" |
| 8.1 | `test_mm.Inventory.*` | INV-11…13 |
| 8.2 | `test_fi.Tolerance.*` | P2P-22 |
| 8.3 | `test_fi.WHT.*` | P2P-23 |
| 8.4 | `test_fi.Clearing.*` | R2R-16 |
| 8.5 | `test_fi.Payables.test_credit_memo` | P2P-24 |
| 8.6 | `test_fi.DownPayments.*` | P2P-25, O2C-23 |
| 8.7 | `test_fi.Periods.*`, `test_mm.Periods.*` | R2R-17, INV-14 |

---

## 12. Final checklist per pull request

- [ ] Unit tests green; calendar test green; fuzz test green; invariant checker clean.
- [ ] `python -m qa.runner` green; new cases in `qa/catalog.py`.
- [ ] New/changed screens reachable from the menu; browser smoke test without errors.
- [ ] Migration step added for every schema change; tested on a copy of an existing database.
- [ ] Messages use class/number; no message names a missing transaction.
- [ ] README and, where the catalog changed, the PowerPoint manuals regenerated.
- [ ] PR merged; zip delivered; `Start MM Core.bat` still starts the system.
