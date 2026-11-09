# MM Core — Engineering Review and Work Order

Review date: 2026-11-09 · Code base: `main` at commit `08b03cb` (29,279 lines: Python engines, JSON API, vanilla-JS SPA)

This file is a **work order for the engineer (or coding model) who will fix and complete the system**. Nothing in the code was changed by this review. Every item says where the problem is, how it was proven, why it happens, how to fix it, and how to know the fix is done.

---

## 0. ملخص لصاحب المشروع (بالعربي)

البرنامج شغال والدفاتر متوازنة في البيانات التجريبية النهارده، لكن المراجعة لقت **مشاكل حقيقية مثبتة بالتجربة**، أهمها:

1. **قنبلة موقوتة في التقويم:** أي يوم في شهر مارس، البرنامج مش هيعرف يحمّل البيانات التجريبية، وكل الاختبارات هتفشل. والاختبارات نفسها بتنجح النهارده بالصدفة: في تواريخ تانية من السنة (أول الشهر، آخر الشهر، ومن يناير لحد نص يونيو) جزء منها بيفشل.
2. **مفيش إقفال سنة مالية:** ميزان المراجعة في سنة جديدة مش بيتوازن، لأن أرباح السنة اللي فاتت مش بتترحّل.
3. **المبيعات مش مربوطة بتخطيط الإنتاج:** لو عميل طلب كمية مش موجودة، الـ MRP مش بيشوف الطلب ومش بيقترح إنتاج أو شراء.
4. **ثغرات رقابية في الفلوس:**
   - نفس الفاتورة ممكن يتعمل عليها مرتجع كامل أكتر من مرة.
   - فاتورة المورد ممكن تتسجل مرتين بنفس الرقم.
   - فاتورة المورد لو اتسجلت غلط مفيش طريقة تتلغي.
   - تسوية الضريبة ممكن تتعمل مرتين لنفس الشهر.
5. **الموردين بالدولار:** أوامر الشراء وفواتيرها بتتسجل بالجنيه كأنها جنيه، من غير فرق عملة.
6. **مفيش تسجيل دخول ولا صلاحيات:** أي حد يغيّر اسم المستخدم من الشاشة ويعدّي كل ضوابط "الشخص التاني يعتمد".
7. **حوالي 75 حالة** لو المستخدم ساب خانة فاضية أو كتب حاجة غلط، البرنامج بيطلع "Internal error" بدل رسالة مفهومة.

التقرير فيه كمان قايمة بكل اللي ناقص عن SAP الحقيقي في كل موديول (الجرد الفعلي، ضريبة الخصم والإضافة، الدفعات المقدمة، إلخ)، واقتراحات تخلّي النظام يستحمل التوسع، وخطة تنفيذ على 6 مراحل بالترتيب.

**القرار المطلوب منك:** توافق على ترتيب المراحل في القسم 12، أو تقول أي مرحلة تتقدم. المرحلة 1 (القنبلة الموقوتة والاختبارات) لازم تتعمل قبل شهر مارس في كل الأحوال.

باقي الملف بالإنجليزي لأنه موجّه للي هيكتب الكود، وفيه أسماء ملفات ودوال.

---

## 1. Instructions for the implementer

### 1.1 Ground rules of this code base (do not break them)

- **Python standard library only** for the application (`sqlite3`, `http.server`). No pip dependencies. The PowerPoint generators in `tools/manuals/` are the only Node code and are not needed at run time.
- **Integers everywhere for money and quantity**: amounts in cents, quantities in 1/1000 ("milli"), percentages in basis points, exchange rates × 100000. Use `mm.util.rdiv`, `value_of`, `price_of`. Never `float`, never `round()`.
- **All FI documents go through `fi.document.write`**; all goods movements through `mm.posting.post_goods_movement`; CO documents through `co.core.post_co_doc`; CO-PA through `co.period_end._copa_post`.
- **Business errors are `mm.util.MMError(msg, msg_class, msg_no)`**. The HTTP layer turns them into HTTP 422 with an SAP-style message. Any other exception becomes HTTP 500 "Internal error" and is a bug.
- **Every write must be inside `with transaction(conn):`** (`mm/db.py`). The connection is in autocommit mode; a write outside a transaction is committed immediately and is not protected by `WRITE_LOCK`.
- **Schema changes**: new tables go in the module's `schema.py`; new columns on existing tables go in the `*_COLUMN_ADDS` dict so that existing databases are upgraded in `mm.db.connect`. Use **named-column INSERTs** only.
- **Front end**: `App.register(tcode, {title, render})`, `api(path, body)` (a body means POST; do not pass `{method, body}`), helpers `alv`, `toolbar`, `field`, `inp`, `sel`.
- **Brand**: the product is "MM Core". Do not add third-party brand names.
- **Git**: develop on the working branch, push, open a PR, merge. Deliver a zip with `git archive`. `Start MM Core.bat` must keep working.

### 1.2 How to verify

```bash
python3 -m unittest discover -s tests
```

```bash
python3 -m qa.runner
```

Today these give 115/115 tests and 86/86 cases. After Phase 1 they must also pass under a faked calendar date (section 11.1 gives the harness).

### 1.3 Evidence labels used below

- **[PROVEN]** — reproduced by running code against a freshly seeded database during this review. The reproduction is described so it can be turned into a regression test.
- **[CODE]** — found by reading the code; not executed. Reproduce first, then fix.
- **[GAP]** — functionality that a real SAP system has and this system lacks.

### 1.4 Severity

| Level | Meaning |
|---|---|
| **S1** | Wrong books, lost control over money or stock, or the system cannot start. Fix first. |
| **S2** | A process is broken or has a dead end; a user cannot finish or undo a business case. |
| **S3** | Robustness: crashes on bad input, misleading messages, performance. |
| **S4** | Missing feature or clean-up. |

---

## 2. What was reviewed and how

| Activity | Result |
|---|---|
| Read the core engines line by line: `mm/db.py`, `mm/posting.py`, `mm/util.py`, `fi/document.py`, `fi/ap.py`, `fi/ar.py`, `fi/gl.py`, `fi/aa.py`, `co/integration.py`, `co/period_end.py`, `sd/order.py`, `sd/delivery.py`, `sd/billing.py` (create/cancel), `pp/order.py`, `pp/planning.py`, `pur/po.py`, `web/server.py`, `run.py` | Findings in sections 3–8 |
| API fuzz: called all 285 routes with an empty body and with a junk body | 76 real unhandled exceptions (section 6) |
| Scenario experiments on a seeded in-memory system (MM, FI, SD, PP, PUR) | 14 defects proven (section 3) |
| Calendar experiments: seeded the system with `datetime.date.today()` faked to 14 different dates, and ran the whole test suite under 4 of them | Seed crash on every March date; 2–6 tests fail on each of the 4 suite dates (BUG-001, section 9) |
| Browser sweep (Playwright): opened all 369 registered screens and pressed "Execute" where present | No JavaScript exceptions; 6 screens call an API that answers 404 (section 6.3) |
| Data invariants on the seeded system (document balance, stock quantity = valuation quantity, standard-price value, sub-ledger = reconciliation account) | All hold on the seed data |
| Not reviewed in depth | `md/material.py`, `md/partner.py`, `co/costing.py`, `co/planning.py`, `co/copa.py`, `pur/sourcing.py`, `pur/analytics.py`, `sd/pricing.py`, `sd/service.py`, `pp/master.py`, `pp/subcon.py`, `pp/service.py`, all `*_screens.js` files (only swept, not read), `office/com_bridge.py`. A second pass over these is recommended after Phase 2. |

---

## 3. Proven defects (fix these first)

### BUG-001 · S1 · The system cannot seed demo data on any day in March [PROVEN]

**Where:** `fi/seed.py:177` (`d = lambda day: datetime.date(y, p, day).isoformat()`), used with `d(29)` at `fi/seed.py:218` and `:223`, and `d(30)` at `:229`. The same unclamped lambda is in `co/seed.py:224`, `md/seed.py:179`, `pur/seed.py:59`.

**Proof:** with today faked to 2026-03-01, 03-02, 03-15, 03-31, 2027-03-10 → `ValueError: day is out of range for month` at `fi/seed.py:218`. With 2028-03-10 (leap year) → same error at `:229`. All other tested months seed correctly.

**Why:** the "sample month" is the previous month. In March that is February, which has no day 29 (or 30).

**Consequences every March:**
- A first start, and `tools/Reset - fresh demo data.bat`, crash before the server starts. With `pythonw` the window is hidden, so the user sees nothing at all.
- **All** tests fail, because every test module seeds a database. `ZQA_TEST` therefore shows everything red.
- Worse: the seed is **not atomic** (`mm/seed.py:20-43` runs hundreds of separate transactions). After the crash the database is half filled. On the next start `seed()` sees that `plant` has rows, returns `None`, and the server starts on a database with no customers, no sales, no production data.

**Fix:**
1. Add one helper, for example `mm.util.day_in_month(y, m, day)` that returns `datetime.date(y, m, min(day, calendar.monthrange(y, m)[1]))`, and use it in every seed (`sd/seed.py:74` and `pp/seed.py` already clamp this way).
2. In `fi/seed.py` the second payment run uses `d(29)` as run date and `d(29)+N` as next date; after clamping make sure "next date > run date" still holds (`fi/ap.py:327` raises otherwise).
3. Make the seed all-or-nothing: write a marker `settings('seed_state','running')` at the start and `'complete'` at the end. In `run.py` and `mm.seed.seed`, if the marker is `'running'`, delete the database file and seed again (or refuse to start with a clear message). Do not rely on "plant has rows".
4. In `run.py`, wrap seeding in `try/except`, write the traceback to `data/mm_core.log`, and when started hidden, open the browser on a small static error page instead of dying silently.

**Done when:** the fake-date harness (section 11.1) seeds successfully for every day of 2026, 2027 and 2028 (1,096 dates; run it once, it takes about 20 minutes, then keep a reduced set in the test suite: the 1st, 2nd, 15th, 28th–31st of every month plus 29 Feb 2028).

---

### BUG-002 · S1 · No fiscal-year closing: the trial balance of a new year does not balance [PROVEN]

**Where:** `fi/reports.py:126` `trial_balance`. For P&L accounts the opening balance starts at 1 January of the requested year; for balance-sheet accounts it is cumulative. There is no retained-earnings carry-forward and no year-end program.

**Proof:** with today faked to 2026-01-02 the sum of all closing balances of `trial_balance(2026, 1, 1)` is −1,198,143.46 instead of 0; on 2026-06-01 it is −91,812.50; on 2026-04-29 it is −727,489.39. `statements()` reports `balanced: True` on the same data because it computes the result of prior years separately, so the two reports disagree.

**Fix:**
1. Add a retained-earnings account to `fi/config.py` `CHART` (for example `330000 "Retained earnings"`, type BS, FSV node in equity).
2. Add `fi/gl.py: carry_forward(conn, gjahr, user)` (SAP F.16 / FAGLGVTR): for the closed year, sum every P&L account; store the result per year in a new table `fi_carry_forward(gjahr PRIMARY KEY, amount, run_at, usnam)`. Do **not** post a document; like SAP, the carry-forward is a balance, and it must be re-runnable (replace the row).
3. In `trial_balance`, `_bs_values` and `statements`, read retained earnings as: the stored carry-forward rows for years `< gjahr`, plus, for prior years with no row yet, the computed P&L sum (so reports are right even before the program is run, and show a warning "balance carry-forward for YYYY not yet run").
4. Add the screen `F.16` and an entry in the FI closing cockpit `ZFI_PROCESS`.
5. Open periods: `posting_period` holds a single interval (`fi/document.py:41` `period_open`). Add account-type rows later (section 8.3); for now make the closing cockpit warn when today is outside the open interval, because on 1 January nothing can be posted until someone widens OB52.

**Done when:** for any faked date, `sum(row.closing for row in trial_balance(year, 1, month)) == 0`, and `statements()` and `trial_balance()` show the same result for the year.

---

### BUG-003 · S1 · Sales orders are invisible to MRP and to the stock/requirements list [PROVEN]

**Where:** `pp/planning.py:162` `_elements`. It reads planned independent requirements, dependent requirements, reservations, forecasts, planned orders, production orders, purchase orders and requisitions. It never reads `sd_vbep` (schedule lines) or `sd_lips` (deliveries).

**Proof:** a sales order for 117 pieces of FG-3002 with 67 in stock is confirmed for 67 and leaves 50 as a backorder. `stock_requirements('FG-3002')` shows no element for the order, and `mrp_run` creates nothing for the missing 50.

**Why it matters:** Order-to-Cash and Plan-to-Produce are not linked. The only link today is that billing type F2 consumes the planned independent requirement of the month. A backorder never triggers production or purchasing; the planner cannot see customer demand in MD04.

**Fix:**
1. In `_elements` add requirement elements:
   - `VC` "Customer order": for every open schedule line of sales documents with `vbtyp='C'`, not rejected (`abgru` empty), not credit-blocked if you want SAP behaviour (SAP still shows them), quantity = ordered quantity minus quantity already in deliveries. Date = material availability date `mbdat` of the schedule line.
   - `VJ` "Delivery": open quantity of deliveries without goods issue (`sd_likp.wbstk<>'C'`), date = planned goods-issue date.
   - Returns (`vbtyp='H'`) are receipts into blocked stock; leave them out of MRP.
2. Planning strategy: today the PIR is reduced when an F2 invoice is posted. Change the consumption to strategy 40 behaviour: a sales order consumes the PIR of its month at order entry (backward 30 days / forward 30 days is enough), and the PIR is finally reduced at goods issue, not at billing. Keep it configurable per material (`material_plant.strgr`, values `10` make-to-stock without consumption, `40` with consumption). Update `pp/planning.py:148` `consumption()` and the place in `sd/billing.py` that reduces the PIR today.
3. `sd/order.py:56` `atp()` must use the same element list as MRP (one function for both), otherwise ATP and MD04 disagree.
4. Show the new element types in MD04 (`pp_screens.js`) and in the pegging list `MD09`.

**Done when:** a new test creates a backorder, runs MRP, finds a planned order (or requisition) covering the shortage dated before the requested delivery date, and after `V_V2` rescheduling the order is confirmed against that receipt.

---

### BUG-004 · S2 · Three kinds of documents can never be reversed (dead ends) [PROVEN]

**Where:** `fi/gl.py:89` `reverse`. It refuses documents from MIRO, F110, AFAB and documents with cleared items, and tells the user to use "MR8M", "FBRA" or "AFAB repeat". None of the three exists: there is no function and no screen named `MR8M` or `FBRA` in the whole repository.

**Proof:** `gl.reverse` on a MIRO document answers "comes from MIRO - reverse it there (MBST, VF11, MR8M, AFAB repeat)". `grep -rn "MR8M\|FBRA" web/static` finds only message texts.

**Fix — add three functions and their screens:**

1. **`fi/ap.py: cancel_invoice(conn, belnr, gjahr, budat, user, reason)` (MR8M).**
   - Find the MIRO document; refuse if the vendor line is cleared (ask for FBRA first).
   - Rebuild the inverse of every line, including the stock line `BSX` and the `PRD` line.
   - Undo what `miro` did outside FI: `po_item.remng -= qty`, `po_item.reewr -= net`. For a moving-average material, undo the price-difference-to-stock: subtract the stock amount again, **but only as far as stock still exists** (`covered = min(qty, lbkum)`); the rest goes to `PRD` — the same rule as in `miro` (`fi/ap.py:149-170`). Write a `price_history` row.
   - To do this the invoice must remember its items. Today nothing links an invoice to PO items except the `ebeln/ebelp/menge` on the GR/IR line. Add a table `inv_item(belnr, gjahr, buzei, ebeln, ebelp, menge, wrbtr, to_stock, to_prd)` written by `miro`, and use it in `cancel_invoice`. This table is also the missing "PO history" for invoices (ME23N).
   - Mark both documents with `stblg`.
2. **`fi/gl.py: reset_clearing(conn, augbl, gjahr, user, reverse=False)` (FBRA).**
   - Set `augbl`/`augdt` back to NULL for every item cleared by `augbl`.
   - With `reverse=True` also reverse the clearing document itself (the payment), which is what a user needs after a wrong payment. A payment that created a residual item must refuse if the residual item is itself cleared.
   - For `F110` documents also set the `payrun` row back to a state that shows which payments were reset (do not delete the run).
3. **`fi/aa.py: reverse_depreciation(conn, gjahr, perio, user)`.** Allowed only for the last posted period. Posts the inverse document and inserts negative `asset_item` rows (`reverse` in `fi/gl.py:124` already copies asset items negatively; reuse that).

**Done when:** tests post and cancel a MIRO invoice for (a) a moving-average material with stock, (b) the same after the stock was consumed, (c) a standard-price material, (d) an account-assigned item — and after each the books balance, `remng` is back, GR/IR for the PO item is as before the invoice, and the valuation equals the state before the invoice in case (a).

---

### BUG-005 · S1 · A billing document can be returned and credited without limit [PROVEN]

**Where:** `sd/order.py:212` `_reference` and `sd/order.py:124` `create`.

**Proof:** invoice for 2 pieces; two returns (`auart='RE'`) each for the full 2 pieces referencing the same invoice item are both accepted (documents 60000003 and 60000004). A credit memo request (`CR`) for 1 piece at a price of 999,999.00 against the same invoice is accepted with net value 999,999.00.

**Why:** when a document is created with reference to a billing item there is no check of what was already referenced. The only protection is billing block 08 on credit memo requests (two-person approval) — and there is no authentication (SEC-001).

**Fix:**
1. In `create`, for every item with `vgbel`/`vgpos` pointing to a billing item, compute `already = sum(kwmeng)` of all non-rejected items of documents with the same `vbtyp` family referencing the same billing item (use `sd_vbfa`, which already records the flow, or query `sd_vbap` directly). Raise `MMError("Item %d: quantity %s exceeds the billed quantity %s minus quantity already returned %s", "V1", "019")` when `already + qty > fkimg`.
2. For `CR` (value credit without return) limit the **value**: `sum(netwr of CR items referencing the billing item) <= billing item net − value already credited by returns`.
3. For `DR` (debit memo) no upper limit, but keep block 08.
4. Quotations: `sd/order.py:199` sets the quotation to completed (`gbstk='C'`) as soon as one order references it, even for part of the quantity. Track the referenced quantity per quotation item the same way and complete the quotation only when every item is fully referenced.

**Done when:** a test proves the second return is rejected, a partial return of 1 followed by a return of 1 is accepted and a third is rejected, and a credit memo above the remaining value is rejected.

---

### BUG-006 · S2 · Reversing a goods issue to a production order does not reopen the reservation [PROVEN]

**Where:** `mm/posting.py:58` `cancel_document`. `_post_item` calls `pp.order.withdrawn` for movement types 261/262/201/202 (`mm/posting.py:336-338`), but `cancel_document` builds its lines directly and never calls it. `pp/order.py:490` `cancel_confirmation` works around this by calling `withdrawn` itself after `cancel_document`.

**Proof:** production order, picking list posted (`pp_resb.enmng` 36000 of 36000), `cancel_document` on the picking document: `enmng` stays 36000 and the order no longer appears in the picking list. The components are back in stock, the order has no material cost, and the system believes the components were issued.

**Fix:** in the loop of `cancel_document`, after each reversed line with original movement type 261/262/201/202 and an order or reservation, call `withdrawn(conn, line, {"rsnum": ..., "rspos": ...}, reversed_bwart, qty)`. For that, the material document item must store the reservation: add columns `rsnum`, `rspos` to `mat_doc_item` (via `MM_COLUMN_ADDS`), fill them in `_insert_line` from `raw`, and use them in the reversal. Then remove the extra `withdrawn` loop from `cancel_confirmation` (`pp/order.py:506-508`), otherwise the reservation would be reduced twice.

**Done when:** a test posts picking, cancels the material document, sees `enmng == 0` and the item back in `picking_list`; and the existing confirmation-cancel test still passes with the workaround removed.

---

### BUG-007 · S1 · A goods receipt can be cancelled after its invoice was posted [PROVEN]

**Where:** `mm/posting.py:58` `cancel_document` and `_post_item` (movement types 102/122).

**Proof:** PO for 5, goods receipt 5, two invoices for 2 each (so `remng = 4000`), then `cancel_document` on the receipt: accepted; `po_item` ends with `wemng = 0`, `remng = 4000`. GR/IR is left with invoices and no receipt.

**Fix:** before reversing or returning a PO receipt, check `po_item.wemng − qty >= po_item.remng`. If not, raise `MMError("Goods receipt cannot be reversed: %s already invoiced - cancel the invoice first (MR8M)", "M7", "033")`. Apply the same check to 102 and 122 in `_post_item` (`mm/posting.py:272-275`). SAP allows a return (122) after invoice and expects a credit memo; that needs the credit memo function (GAP-FI-02), so until then block it.

**Done when:** the reproduction above is rejected, and after `cancel_invoice` (BUG-004) the reversal is accepted.

---

### BUG-008 · S1 · The same vendor invoice can be posted twice [PROVEN]

**Where:** `fi/ap.py:96` `miro` and `fi/ap.py:52` `vendor_invoice`.

**Proof:** two `miro` calls with the same PO, vendor, reference `DUP-1`, date and amount give documents 5100000035 and 5100000036.

**Fix:** add `fi/ap.py: _check_duplicate(conn, lifnr, xblnr, bldat, gross_fc, waers)`: look for a non-reversed vendor document (`acc_doc.stblg IS NULL`, item `koart='K'`, same `lifnr`) with the same `xblnr` (case-insensitive, trimmed) and the same document date; same amount makes it an error, different amount a warning. Skip when `xblnr` is empty, but then make the reference mandatory for `KR`/`RE` document types (SAP standard). Honour a vendor master flag `reprf` ("check double invoice", default on; add the column to `vendor` through `MD_COLUMN_ADDS` and the field to the vendor accounting view). Call it from `miro`, `vendor_invoice` and `fi/aa.py:acquire`.

**Done when:** the reproduction raises message `F5 117`, and a test shows that after cancelling the first invoice the second can be posted.

---

### BUG-009 · S1 · Three period-end programs can be run twice with wrong results [PROVEN for a, c · CODE for b]

**a) VAT settlement** — `fi/gl.py:266` `vat_settlement`. Run twice for the same period: two documents (100000018 and 100000019). The report `vat_report` excludes `FB41` documents, so the second run transfers the same tax again and the tax accounts end with the wrong sign.
*Fix:* table `vat_run(d1, d2, belnr, gjahr, usnam, ts)`; refuse a period that overlaps a settled period; allow "reverse settlement" which reverses the FB41 document with `gl.reverse` and deletes the row. Better: settle by **clearing** — mark the settled tax items with `augbl` and let the report use `augbl IS NULL`.

**b) Foreign-currency valuation** — `fi/gl.py:173` `fx_valuation`. There is no check that the key date was already valued. A second update run posts the same differences again. *Fix:* table `fx_run(key_date PRIMARY KEY, belnr, ...)`; refuse or offer "reverse and repeat". Also the planned reversal relies on someone running F.81 the next day; post the reversal document immediately with the next-day date (if that period is open) as SAP does.

**c) Payment run** — `fi/ap.py:374` uses `INSERT OR REPLACE INTO payrun`. *Proof:* after an executed run `ZZ1`, calling the proposal again for the same date/identifier sets the status from `PAID` back to `PROPOSAL`, and a second execution is then accepted. Items are not paid twice (they are cleared), but the run log is overwritten and newly due items are paid under an identifier that was already closed. *Fix:* check the existing row first; if `status='PAID'` raise for both proposal and execution; a proposal may be replaced only while `status='PROPOSAL'`; add "delete proposal".

**Also in this family (CODE):**
- `fi/gl.py:211` `grir_clearing` creates an `acc_doc` header with **no items** (one such header exists in the seed data). Use a proper clearing number without a header, or write a zero-balance two-line document; fix `fi/reports.py` consumers if they assume items exist.
- `fi/aa.py:137` `depreciation_run` is safe to repeat (it posts planned − posted). Keep that pattern as the model for the others.

---

### BUG-010 · S1 · Purchasing ignores foreign currency [PROVEN]

**Where:** `pur/po.py:51` writes `po_header.waers = "EGP"` for every vendor. `mm/posting.py` values receipts with `po_item.netpr` as local currency. `fi/ap.py:96` `miro` posts `wrbtr = amount`, calls `_tax_lines(base, 100000, 1)` and `write(...)` without `waers`/`kursf`.

**Proof:** vendor 300001 has currency USD. A PO for 10 pieces at 10.00, receipt, invoice: the invoice document has `waers = 'EGP'`, and the vendor line of 114.00 is posted on the foreign reconciliation account 161000 as EGP. `fi/ap.py:52` `vendor_invoice` (FB60) for the same vendor posts in USD with the day's rate. So one vendor has open items in two different meanings of "amount"; payments, FX valuation and the vendor balance are wrong for imported goods.

**Fix:**
1. `po_header.waers` = vendor currency (allow override on the PO), `po_header.wkurs` = rate at PO date (information only). Info records and contracts get a currency column (`PUR_COLUMN_ADDS`), default vendor currency.
2. Goods receipt: `ext = to_local(value_of(qty, netpr, peinh), rate(conn, waers, budat))` in `mm/posting.py` (`ref == "PO"` branch, `mm/posting.py:258`). Store the rate used on the material document item (new columns `waers`, `kursf`, `wrbtr`), because the invoice needs the GR value in local currency.
3. Invoice: post in document currency with the rate of the posting date. GR/IR is debited with the **GR local value** for the invoiced quantity (take it from the stored GR lines, FIFO over receipts not yet invoiced), and the difference between invoice local value and GR local value caused by the rate goes to the stock account (moving average, with stock coverage) or to an exchange-rate-difference account `KDM` (add to `mm/config.py` account determination) — SAP's behaviour.
4. Planned freight (`frb`) is in PO currency as well.
5. `fi/ar.py:36` `customer_invoice` and all of SD are local-currency only (`sd/order.py` has no currency at all). Add `waers` to `customer`, `sd_vbak`, `billing`; price conditions get a currency; billing posts in document currency. This is a larger change; do it in Phase 4 after purchasing.

**Done when:** a test with a USD vendor shows: GR at rate A values stock at `qty × price × A`; invoice at rate B has `acc_doc.waers='USD'`, vendor item `wrbtr` in USD and `dmbtr = wrbtr × B`; GR/IR for the item is zero; the difference `(B − A)` is on stock or `KDM`; payment at rate C posts a realised difference; books balance.

---

### BUG-011 · S2 · Sales order items can be rejected while a delivery is open, and deliveries cannot be deleted [PROVEN]

**Where:** `sd/order.py:348` `change` uses `delivered_qty`, which counts only deliveries with goods issue (`wbstk='C'`, `sd/order.py:430`). `sd/delivery.py` has no delete or change function.

**Proof:** order with 3 pieces, delivery created (no goods issue yet), item rejected with a rejection reason — accepted. Then goods issue for the delivery — accepted. Stock leaves for a rejected item, and the item can no longer be billed normally.

**Second effect:** `sd/delivery.py:67` counts every delivery line (`done`) regardless of status. A delivery that is created by mistake, or whose goods issue was reversed with VL09, keeps the order quantity reserved forever because it cannot be deleted.

**Fix:**
1. `change`: reject only when there is no delivery line at all for the item (`SELECT 1 FROM sd_lips WHERE vgbel=? AND vgpos=?`); message "delete the delivery first (VL02N)".
2. Add `sd/delivery.py: delete(conn, vbeln, user)`: allowed when `wbstk <> 'C'`; delete `sd_lips`, `sd_likp`, the `sd_vbfa` rows and call `_status` on the order. Add `change(conn, vbeln, items)` to reduce a delivery quantity before goods issue. Add buttons in `VL02N` and API routes.
3. `post_gi`: re-check that the order item is not rejected and the order is not credit-blocked or delivery-blocked at goods-issue time (SAP checks credit again at delivery and goods issue).

---

### BUG-012 · S2 · Billing and several inputs use floating point for money [CODE for the rounding · PROVEN for the crash]

**Where:** `sd/billing.py:96-99`: `f = q / p["kwmeng"]`, then `round(p["kzwi1"] * f)`, `round(p["kzwi2"] * f)`, `round(p["freight"] * f)`. `sd/order.py:268`: `price = int(round(float(it["price"]) * 100))`. `pur/po.py`: `rabatt = int(round(float(...) * 100))`. `fi/gl.py:51`: exchange rate through `float`.

**Why it is wrong:** the project rule is exact integer arithmetic. `round()` rounds half to even, floats lose precision on large values, and each partial invoice is rounded on its own, so the partial invoices of one order item are not guaranteed to add up to the item value. This was not demonstrated with a concrete number in the review (the attempt used the wrong key type for partial deliveries, see CODE-011); write the property test below first.

**Proven part:** `order.create(... items=[{"matnr": "FG-3001", "qty": "1", "price": "abc"}])` raises `ValueError: could not convert string to float` → HTTP 500.

**Fix:** use `rdiv(value * q, kwmeng)` for every part, and for the **last** partial billing of an item (billed quantity reaches the order quantity) take "order item value − already billed" for gross, discount, freight and tax so the totals match to the cent. Replace every `float()` on money, price, percentage and rate input with `parse_amount` / a new `parse_pct` / a new `parse_rate` built on `Decimal` in `mm/util.py`. `grep -n "float(" --include=*.py -r mm co fi pur md pp sd web` lists the places.

**Done when:** a property test bills an item in 1…n random partial deliveries and the sums of gross, discount, freight and tax equal the order item exactly; and `{"price": "abc"}` returns HTTP 422, not 500.

---

### BUG-013 · S2 · Operations can be confirmed in any order; the last operation posts the goods receipt first [PROVEN]

**Where:** `pp/order.py:394` `confirm`.

**Proof:** order for FG-3003 with operations 0010 (control key PP01) and 0020 (PP03, automatic goods receipt). Confirming 0020 before 0010 is accepted, and it posts the finished product into stock although nothing was produced or issued yet.

**Fix:** add a field `sequence_check` to `pp/config.py` `ORDER_TYPES` (values: none / warning / error; default error for PP01). In `confirm`, the confirmed yield + scrap of an operation may not exceed the yield of the previous internal operation (`lmnga` of the predecessor; for the first operation the limit is the order quantity + tolerance). External operations (PP02) count as done when their purchase order has a goods receipt. The QA catalog already claims this control ("Confirm in sequence", `qa/catalog.py`, process PTP) — the claim is false today.

**Related, same function [CODE]:**
- `pp/order.py:436-437` `if fin and op["vornr"] == last: q = max(q, 0)` does nothing. Intention was probably: on the final confirmation, backflush the **remaining** open quantity of backflush components. Decide and implement or delete.
- The 10 % over-confirmation tolerance (`pp/order.py:413`) and the 10 % over-delivery tolerance for order receipts (`mm/posting.py:230`) are hard-coded. Move both to `ORDER_TYPES` (or to the material master, where `uebto` already exists for purchasing).
- `pp/order.py:371` `post_picking` does not limit the quantity to the open reservation quantity.
- A goods receipt for the order is accepted when no component was issued and no operation confirmed (proved: order ends `DLV` with `igmng = 0`). SAP allows it but most plants forbid it; add a warning message in the result and a status `MSPT`-like hint in `COOIS`.

---

### BUG-014 · S2 · Changes made directly in the API layer bypass the engines [CODE, lines verified]

**Where and what:**

| File:line | Statement | What is bypassed |
|---|---|---|
| `web/fi_api.py:206` | `UPDATE vendor SET zterm=…, sperr=…` | transaction + write lock, change documents (`md.changes.log`), and the **dual control** for sensitive vendor fields (FK08) |
| `web/fi_api.py:319` | `UPDATE customer SET zterm=…, klimk=…` | same; the **credit limit** changes without any log |
| `web/pur_api.py:335` | `UPDATE material_plant SET dismm=…, minbe=…` | change documents for MRP parameters |
| `web/sd_api.py:148` | `UPDATE sd_cond SET loevm=1` | no log who deleted a price; `int(None)` crash |
| `web/qa_api.py:51` | `INSERT OR REPLACE INTO settings` + `c.commit()` | harmless, but `commit()` is a no-op in autocommit mode |

**Fix:** move each into its engine module (`md/partner.py`, `md/material.py`, `sd/pricing.py`) as a function that opens a transaction, validates, writes change documents, and — for credit limit and payment terms — marks the change as sensitive if the policy says so. API handlers must contain no SQL writes. Add a test that greps `web/*.py` for `execute("UPDATE|INSERT|DELETE` and fails if any is found.

---

## 4. Defects found by reading (reproduce, then fix)

### CODE-001 · S1 · Period-end closing ignores costs of previous fiscal years

`co/period_end.py` selects with `gjahr=? AND perio<=?` in `_prod_orders` (`:205`), `_order_actuals` (`:260`), the balance in `settle` (`:362`). A production order released in December and delivered in January has its December costs ignored when January is closed: the variance and the settlement are computed from January costs only, and the order never reaches balance zero. WIP calculation in `pp/service.py` has the same pattern (check `wip`).

*Fix:* replace the year filter by a period key: `(gjahr*12 + perio) <= (Y*12 + P)`. Add a helper `co.core.upto(gjahr, perio)` that returns the SQL fragment and parameters, and use it everywhere. Add a test with an order that crosses the year end (needs the injectable clock from TEST-001).

### CODE-002 · S1 · Settlement to material breaks the standard-price rule

`co/period_end.py:415` `_settle_to_material` adds the order balance to `valuation.salk3` whenever stock exists, also when the material has price control `S`. For standard price the stock value must stay `lbkum × stprs`; the whole balance must go to the price-difference account. Today only moving-average materials use this path (refurbishment order for SP-4001), so the seed data is not affected. *Fix:* `to_stock = bal if v["vprsv"] == "V" and v["lbkum"] > 0 else 0`. Also write a `price_history` row when the moving price changes, like every other price-changing posting.

### CODE-003 · S2 · Nested transactions have no savepoints

`mm/db.py:153` `transaction`: an inner `with transaction(conn)` only increases a counter. If inner code raises and an **outer** caller catches the exception and continues, the inner writes stay and are committed with the outer transaction. Today the only loops that catch `MMError` (`pp/service.py:139`, `web/pp_api.py:284`) are outside a transaction, so nothing is wrong yet. It is a trap for the next feature (mass processing).

*Fix:* on nested entry execute `SAVEPOINT sp_<depth>`; on nested exit `RELEASE` or, on exception, `ROLLBACK TO sp_<depth>` then `RELEASE`. Also key `_DEPTH` by the connection object itself (a `WeakKeyDictionary` cannot hold `sqlite3.Connection`; store the depth as an attribute on a small wrapper or in a dict keyed by `id` that is cleaned in `__exit__` — it is cleaned today, keep that).

### CODE-004 · S2 · `fi.document.write` can be called outside a transaction

`write` (`fi/document.py:89`) does not open a transaction itself. All current callers do. A future caller that forgets gets a half document after any error. *Fix:* wrap the body in `with transaction(conn):` (nesting is free) — same for `fi.document.clear`, `co.core.post_co_doc`, `mm.db.next_number`.

### CODE-005 · S3 · Unknown tax code crashes MIRO

`fi/ap.py:36` `_tax_lines` does `TAX_CODES[code]`; `miro` takes `header["mwskz"]` without validation, and its error text hard-codes "14 % VAT". Validate the code and its type (input tax) as `vendor_invoice` does at `fi/ap.py:72`. Also `int(it.get("ebelp"))` (`fi/ap.py:110`) crashes when the item number is missing.

### CODE-006 · S3 · Info record price is overwritten by every purchase order

`pur/po.py:147` calls `save_info_record` with the PO price for every item unless `info_update` is false. A one-off manual price becomes the default price of the next order. SAP's info update only stores "last purchase order"; conditions are maintained in ME12. *Fix:* update only `info_record.ebeln/ebelp` (last document); change the price only when the PO was created from an awarded quotation.

### CODE-007 · S3 · Second credit-limit rule that disagrees with the first

`fi/ar.py:24` `check_credit` (used by FB70) counts only open FI items; `sd/order.py:108` `credit_check` counts open items + open order value + oldest open item. Use one function (the SD one) from both places. `exposure` (`sd/order.py:92`) also ignores open returns and credit memo requests and open deliveries are counted through the order (fine).

### CODE-008 · S3 · Bank statement stores Python repr and parses signs with float

`fi/gl.py:281` `bank_statement`: `str(lines)` is stored instead of JSON; the sign of a line is found with `float(str(amount).replace(",", ""))`, which reads "1,5" as 15. Use `json.dumps` and `mm.util._to_decimal`.

### CODE-009 · S3 · FS00 changes are partly in memory only

`fi/gl.py:22` `save_gl_account` updates `mm.config.GL_ACCOUNTS` / `PNL_ACCOUNTS` in the running process. After a restart, MM reports that use those dicts for texts or P&L classification do not know accounts created in FS00. On conflict the statement does not update `typ` and `recon`. *Fix:* load both dicts from `gl_account` in `mm.db.connect` (or better, stop using the dicts and read the table).

### CODE-010 · S3 · Rush order creates its delivery outside the order's transaction

`sd/order.py:204-209`: the order is committed, then the delivery is created. If delivery creation fails the user gets an error although the order exists. Create the delivery inside the same transaction, or return the order number with a warning.

### CODE-011 · S4 · Dead code and small inconsistencies

- `pp/planning.py:303-306`: variable `need` is computed and never used; exception messages 10/15 (bring forward / postpone a fixed receipt) are therefore never produced. Implement rescheduling proposals or delete the loop.
- `pp/planning.py:327-331` (and again at `:416`): the number range `PLAF` is created inside `mrp_run`; register it in `pp/schema.py` like the others.
- `pp/planning.py:435` `convert`: the "already converted" check runs outside the transaction.
- `sd/order.py:280` `_ = sign`: the sign for returns is computed and discarded.
- `sd/delivery.py:73-76`: `items` must have **string** keys; integer keys are silently ignored and the caller gets the misleading message "No schedule lines due". Normalise keys with `str()`.
- `co/integration.py:21`: `check_order(for_gr=True)` allows `PP01`, `ZP03`, `ZREF` while `co/period_end.py:206` treats `ZP07` as a production order type too. Put the list in one place (`pp/config.py`).
- `fi/aa.py:140`: a first `budat` assignment is immediately overwritten.

---

## 5. Process links that are missing or weak

| # | From → To | State today | What to build |
|---|---|---|---|
| LINK-01 | Sales order → MRP / MD04 | Missing (BUG-003) | Requirement elements for orders and deliveries; PIR consumption at order entry |
| LINK-02 | Sales order → production (make-to-order) | Missing | Requirement type per item category; planned/production order with account assignment to the sales order item (`kdauf`, `kdpos`); sales-order stock `E` |
| LINK-03 | Purchasing → foreign currency → FI | Broken (BUG-010) | Currency on PO, GR, invoice |
| LINK-04 | Invoice verification → cancel | Dead end (BUG-004) | MR8M |
| LINK-05 | Payment → undo | Dead end (BUG-004) | FBRA |
| LINK-06 | Goods issue reversal → reservation | Broken (BUG-006) | Reservation reference on material document item |
| LINK-07 | Purchase requisition / PO → CO commitments | Missing | Table `co_commit(objnr, kstar, gjahr, perio, refbn, amount)`; written at PR/PO create/change, reduced at GR/invoice; shown in KSB1-style commitment report (KSB2 / KOB2) and in plan/actual reports |
| LINK-08 | Internal order budget → availability control | Missing | KO22 budget per order; check in `co.integration.derive_assignments` (warning at 90 %, error at 100 %) |
| LINK-09 | Asset purchase → purchasing | Missing | Account assignment category `A` on PO item (`pur/po.py:57` allows only K/F); GR or invoice capitalises the asset via `fi.aa` |
| LINK-10 | Quality → goods receipt | Partial (stock type Q only) | Inspection lot at GR for materials with QM active; usage decision posts 321 / 122 / 350-type movements; results feed vendor evaluation |
| LINK-11 | Year end → CO | Broken (CODE-001) | Cross-year period key |
| LINK-12 | Delivery → credit | Weak | Credit re-check at delivery creation and goods issue |
| LINK-13 | Vendor return (122 after invoice) → credit memo | Missing | MIRO credit memo / subsequent debit-credit |
| LINK-14 | Stock transfer between plants → purchasing/SD | Only one-step 301 | Stock transport order (PO type UB, 351 → stock in transit → 101) |
| LINK-15 | Dunning → FI | No posting | Dunning charges and interest posting; dunning block on item and customer |
| LINK-16 | E-invoice → tax authority | Local JSON + hash only (`sd/billing.py:270`) | Real submission is a separate integration project: token-based signature, item coding (GS1/EGS), document UUID returned by the authority, status polling, rejection handling. Keep the current function as "prepare"; add `sd_einv.status` values SUBMITTED / VALID / REJECTED and a submit adapter interface |
| LINK-17 | Plant 1100 | Material FG-3001 has MRP type PD in plant 1100, but `mrp_run` defaults to plant 1000 (`pp/planning.py:254`) | Check that MD01 passes the plant from the screen; run MRP per plant in a loop for "all plants" |

---

## 6. Robustness

### 6.1 ROB-001 · S3 · 76 API calls answer "Internal error" on empty or wrong input [PROVEN]

All 285 routes were called with `{}` and with a junk body/query. 225 calls answered with a proper business error; **76 raised an unhandled Python exception**. In the browser the user sees "Internal error: int() argument must be …".

| Pattern | Places (file:line of the raising statement) |
|---|---|
| `int(None)` / `int('x')` for year, period, ids | helper `web/co_api.py:25`, helper `web/fi_api.py:18`, `web/co_api.py:234`, `:257`, `:265`, `:367`, `:500`, `web/fi_api.py:109`, `web/server.py:246`, `web/sd_api.py:148`, `co/planning.py:38`, `:74`, `co/period_end.py:59`, `:219`, `:269`, `:352`, `co/copa.py:148`, `fi/aa.py:139`, `pur/po.py:197`, `pp/order.py:493`, `sd/reports.py:166` |
| `KeyError` on `body["…"]` | `web/server.py:145`, `web/fi_api.py:85`, `web/pur_api.py:207`, `:228`, `:235`, `:284`, `:300`, `pp/order.py:377` |
| `float('None')` | `fi/gl.py:51` |
| `date.fromisoformat('junk')` | `web/pp_api.py:137`, `pp/reports.py:32` |
| `None[...]` for a document that does not exist | `sd/order.py:388` (`reschedule` of unknown order) |

**Fix (a few shared helpers, not 76 separate patches):**
1. Add to `mm/util.py`: `parse_int(text, what, lo=None, hi=None)`, `parse_year`, `parse_period` (1–12/16), `require(body, *keys)` — all raising `MMError("Enter …", "00", "055")`.
2. Replace the two helpers `web/co_api.py:25` and `web/fi_api.py:18` to use them; this removes about half of the list.
3. In `web/server.py:_dispatch`, catch `(KeyError, TypeError, ValueError)` raised **in the handler frame itself** is not safe as a general rule (it would hide real bugs). Instead keep the 500 for unknown exceptions but: log the traceback to `data/mm_core.log`, return a message without the Python text ("Internal error — see log, reference <timestamp>"), and add the test below so the list stays at zero.
4. Add `tests/test_api_fuzz.py`: iterate `web.server.ROUTES` exactly as in section 11.2 and fail on any exception that is not `MMError`.

### 6.2 ROB-002 · S3 · Server and database plumbing

- **A new database connection per request.** `web/server.py:30` keeps the connection in `threading.local`; `ThreadingHTTPServer` with HTTP/1.0 creates a new thread per request, so `connect()` runs for every request: all `CREATE TABLE IF NOT EXISTS` scripts, the column-upgrade checks and ~100 `INSERT OR IGNORE` for the chart of accounts (measured: 3 ms on a 1.5 MB database, growing with size). Those writes happen outside `WRITE_LOCK`. Connections are never closed. *Fix:* split `connect()` into `open_db(path)` (just open + pragmas) and `migrate(conn)` (schema, upgrades, defaults) which runs once at start in `run.py`. Use a small connection pool or one connection per thread with a bounded thread pool; set `protocol_version = "HTTP/1.1"` with correct `Content-Length` (already sent) to reuse connections.
- **Journal mode.** The database runs with `journal_mode=delete`. Use `PRAGMA journal_mode=WAL` and `synchronous=NORMAL`: readers are no longer blocked by a writer, and a crash during a write is safer. Add `PRAGMA busy_timeout`.
- **No schema version.** Add `settings('schema_version', N)` and a list of migration steps in `mm/db.py`; `ADD COLUMN` alone cannot rename, drop, backfill or add indexes conditionally.
- **No foreign keys.** `PRAGMA foreign_keys = ON` is set but no table declares a reference, so it does nothing. Do not add FKs to old tables now (data risk); add them for new tables, and add the invariant checker (TEST-004) instead.
- **Few indexes** (13 for 108 tables). Missing ones that matter as data grows: `acc_doc_item(hkont)`, `acc_doc_item(koart, lifnr, augbl)`, `acc_doc_item(koart, kunnr, augbl)`, `acc_doc(budat)`, `acc_doc(awkey)`, `mat_doc_item(ebeln, ebelp)`, `mat_doc_item(aufnr)`, `po_item(matnr, werks)`, `co_item(objnr, gjahr, perio)`, `copa_item(gjahr, perio)`, `sd_vbap(matnr)`, `sd_lips(vgbel, vgpos)`, `billing_item(aubel, aupos)`, `pp_resb(matnr, werks)`, `pr_item(matnr, werks)`. Check each with `EXPLAIN QUERY PLAN` on the heavy reports (FBL1N, KSB1, MB51, MD04, cockpit queries).
- **No backup.** Add `tools/Backup.bat` → `python run.py --backup` using `sqlite3.Connection.backup` into `data/backup/mm_YYYYMMDD_HHMMSS.db`, an automatic backup before `--reset`, and `PRAGMA integrity_check` at start.
- **No log file.** With `pythonw` every traceback is lost. Log to `data/mm_core.log` (rotating, standard `logging`).
- **Static path check** `web/server.py:404` uses `full.startswith(STATIC)` without a trailing separator; a sibling directory named `static_x` would pass. Use `os.path.commonpath`.
- **`--host` option** (`run.py:67`) lets the server listen on all interfaces while there is no authentication. Refuse any host other than loopback until SEC-001 is done.

### 6.3 ROB-003 · S4 · User-interface findings from the sweep

- Six display screens call their API with an empty key when opened without a document and get HTTP 404 in the console: `ME23N`, `KSB5`, `ME9F`, `ZMM03_LF`, `ZXD03_LF`, `ZXK03_LF`. Guard: do not call when the key is empty; show the selection fields.
- 17 registered screens are not reachable from the menu: `OKEON FAGLB03 S_ALR_87012284 ME52N ME12 ME1L ME13 ME03 ME61 ME6H S_ALR_87012182 S_ALR_87012089 CS12 MC82 KKAO VKM3 IW53`. Add them to `web/static/menu.js` or remove them.
- The message "reverse it there (… MR8M …)" and "(FBRA)" name transactions that do not exist (BUG-004).
- The sweep only opens screens and presses Execute. Create/change screens were clicked through per module in earlier work but there is no permanent UI test (TEST-003).

---

## 7. Security and controls

### SEC-001 · S1 · No authentication and no authorisations [PROVEN by reading]

`web/server.py:351` takes the user name from the `X-User` header, default `OWNER`. `web/static/core.js:416` lets anyone type a different name. Every segregation-of-duties rule in the system compares user names: credit release (`sd/order.py:420`), billing block 08 (`sd/order.py:357`), vendor bank confirmation FK08, requisition/PO release. They are all bypassed by typing another name. The QA catalog presents these as tested controls; they are tested, but only against an honest caller.

**Build (minimum that makes the controls real):**
1. Tables `usr(bname PRIMARY KEY, name, pw_salt, pw_hash, locked, valid_to, lang)`, `usr_role(bname, role)`, `role_auth(role, object, field, value)`. Password hashing with `hashlib.pbkdf2_hmac('sha256', …, 200_000)`.
2. Login page + session cookie (`HttpOnly`, `SameSite=Strict`, random 32-byte token in a `session` table with expiry). `Handler.user` reads the session, never a header. Keep `X-User` only when the server is started with `--dev`.
3. Authorisation check at two levels: (a) transaction start — role must contain the T-code (`S_TCODE`); the front end hides menu entries, the API enforces by mapping each route to a T-code or activity; (b) a few business objects: company code / plant / purchasing group / sales organisation / release code / document type / "release credit" / "confirm sensitive change".
4. Seed roles: `SALES_CLERK`, `CREDIT_MANAGER`, `BUYER`, `PURCH_MANAGER`, `WAREHOUSE`, `PLANNER`, `SHOPFLOOR`, `AP_CLERK`, `AR_CLERK`, `GL_ACCOUNTANT`, `CONTROLLER`, `MD_MAINTAINER`, `MD_APPROVER`, `ADMIN`, and demo users for each. Screens `SU01` (users) and a simple `PFCG` (roles).
5. Change every "second person" rule to check an authorisation **and** a different user.
6. Audit log table `audit_log(ts, bname, tcode, object, key, action)` for logon, failed logon, master-data display of bank data, and every release/approval.

### SEC-002 · S1 · Any web page can post into the system (CSRF)

The API accepts a JSON body whatever the `Content-Type` is and checks neither `Origin` nor `Host`. A page on the internet opened in the same browser can send `fetch('http://localhost:8080/api/…', {method:'POST', body:'{…}'})` as a "simple request" — no pre-flight — and post documents, stop the server (`/api/shutdown`) or make the Office bridge open local files (`/api/office/excel-read` takes any path).

*Fix:* in `_dispatch`, for every POST require `Content-Type: application/json` (this forces a CORS pre-flight, which the server does not answer), reject requests whose `Origin` header is present and is not the server's own origin, and reject `Host` values other than `localhost:<port>` / `127.0.0.1:<port>` (DNS-rebinding protection). After SEC-001 add a CSRF token bound to the session.

### SEC-003 · S3 · Error messages leak internals

`web/server.py:387` returns the Python exception text. Return a generic text plus a reference; write details to the log.

---

## 8. Missing functionality compared with a real SAP system

Priority: **A** = needed for a plant to run for real; **B** = needed soon after; **C** = nice to have. Each line names where it plugs in.

### 8.1 Materials management and warehouse

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-MM-01 | A | Physical inventory documents: MI01 create, MI04 count, MI20 difference list, MI07 post, MI11 recount; freeze book inventory; posting block during count | Tables `inv_doc(iblnr, gjahr, werks, lgort, budat, status)`, `inv_item(iblnr, zeili, matnr, lgpla, insmk, buchm, menge, counted, posted, mblnr)`. MI07 posts 701/702 through `post_goods_movement` with reference to the inventory document. Block goods movements for materials with an active count (flag on `material_plant` or check table). ABC cycle counting list (MICN) later. Today only direct 701/702 exists; the QA catalog step "Physical count" points to MB52. |
| GAP-MM-02 | A | MM period closing (MMPV) and previous-period postings | Table `mm_period(bukrs, gjahr, perio, allow_prev)`. Check in `post_goods_movement`: posting date must be in the current or (if allowed) previous MM period. Period-end stock snapshot table `valuation_hist(matnr, bwkey, gjahr, perio, lbkum, salk3, price)` written by MMPV — needed for stock-on-posting-date (MB5B) and for year-end. |
| GAP-MM-03 | A | Stock on a past date (MB5B) and stock/GL reconciliation list (MB5L) | Compute from current stock minus later movements, or from GAP-MM-02 snapshots. |
| GAP-MM-04 | B | Batches and shelf life | `batch(matnr, charg, werks, hsdat, vfdat, lifnr, status)`; `charg` on `quant`, `mat_doc_item`, `sd_lips`, `pp_resb`; FEFO strategy next to FIFO; batch where-used. Paint and granules in the demo are natural batch materials. |
| GAP-MM-05 | B | Special stocks: vendor consignment (K), sales-order stock (E), stock in transit | Column `sobkz` + owner key on `quant`; valuation rules per special stock. |
| GAP-MM-06 | B | Stock transport orders and two-step transfers (303/305, 351) | See LINK-14. |
| GAP-MM-07 | B | Reservations as documents for cost centers exist (MB21); missing: reservation list by requirement date with goods-issue reference check, automatic closing | Small. |
| GAP-MM-08 | B | Warehouse tasks: transfer orders/tasks for put-away and picking, bin-to-bin transfer screen, bin capacity, bin stock list by storage type | Today bins are attributes of a goods movement. Add `wm_task(tanum, typ, matnr, vlpla, nlpla, qty, status, ref)` and confirm step; make it optional per storage location. |
| GAP-MM-09 | C | Split valuation, LIFO/FIFO valuation, lowest-value principle | Only if required by the auditor. |
| GAP-MM-10 | C | Handling units, serial numbers in stock (serial numbers exist only as equipment after delivery) | |

### 8.2 Purchasing and invoice verification

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-PUR-01 | A | Invoice cancel (MR8M), credit memo, subsequent debit/credit | BUG-004; credit memo = `miro(..., credit=True)` with reversed signs and `remng` reduced. |
| GAP-PUR-02 | A | Invoice tolerances and payment block: price variance, quantity variance, date variance → invoice posted but blocked (`zlspr='R'`), release in MRBR | Table `tolerance(key, lower_abs, upper_abs, lower_pct, upper_pct)`. `payment_run` and `pay` must skip blocked items (check `md.checks.payment_exception` covers only the vendor level). |
| GAP-PUR-03 | A | Withholding tax on vendor payments/invoices (Egyptian "خصم وإضافة") | Vendor master: WHT type/code, exemption certificate dates. Tax table `wht_code(code, pct, hkont, base='net'|'gross')`. Post at invoice or at payment per type; report by vendor/quarter (form 41 data). Without this, vendor payments are not legally correct in Egypt. |
| GAP-PUR-04 | B | GR/IR maintenance (MR11) for items that will never be invoiced/delivered | Posts the open GR/IR balance to stock/price difference and sets a "final invoice" flag. |
| GAP-PUR-05 | B | Service procurement: service entry sheet (ML81N) with acceptance, instead of a goods receipt for a service line | |
| GAP-PUR-06 | B | Purchase order output: a printable/PDF PO form and message status; today only a "printed" flag (`pur/po.py:251`) | HTML print template is enough; reuse for RFQ, delivery note, invoice. |
| GAP-PUR-07 | B | PO change beyond quantity/date/completion/deletion: price change with re-release, add item, change account assignment; PO version history | `pur/po.py:193` `change_po`. |
| GAP-PUR-08 | B | Scheduling agreements with delivery schedule; ERS (self-billing, MRRL); invoicing plans; down payments to vendors (F-47/F-48) with clearing against the invoice | |
| GAP-PUR-09 | C | Three-quotations rule | The QA catalog lists "Three quotations above the limit" as a control, but no code enforces it (`pur/sourcing.py` only ranks quotations). Either implement (PO above a value needs an RFQ with ≥ 3 quotations or an override reason) or correct the catalog text (DOC-001). |
| GAP-PUR-10 | C | Inbound deliveries / advance shipping notice, confirmations, expediting (ME91F reminders) | |

### 8.3 Financial accounting

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-FI-01 | A | Year-end: balance carry-forward, retained earnings | BUG-002. |
| GAP-FI-02 | A | Reset clearing (FBRA); manual clearing of open items (F-44 vendor, F-32 customer, F-03 G/L) including clearing invoice against credit memo with no payment | BUG-004; today clearing happens only inside a payment. |
| GAP-FI-03 | A | Down payments (customer F-29, vendor F-48) with special G/L indicator, and their clearing | Add `umskz` to `acc_doc_item`, alternative reconciliation accounts. |
| GAP-FI-04 | A | Posting periods per account type (+, A, D, K, M, S) and special periods 13–16; authorisation group for the "previous period" | `posting_period` becomes a table with rows; `period_open(conn, budat, koart)`. |
| GAP-FI-05 | A | Egyptian localisation: withholding tax (GAP-PUR-03), VAT return layout (form 10), stamp duty, e-receipt; real e-invoice submission (LINK-16) | |
| GAP-FI-06 | B | Parked and held documents (FV50/FV60), recurring entries (FBD1/F.14), sample documents | |
| GAP-FI-07 | B | Bank: house banks and bank accounts as master data, bank clearing accounts (outgoing/incoming) so that F110/F-53 post to a clearing account and the statement clears it; statement import (MT940/CSV); cheque register; payment medium file; payment methods on vendor and item | Today every payment posts straight to 113100 (`fi/ap.py:236`), and the manual statement handles only customer receipts and charges (`fi/gl.py:281`). |
| GAP-FI-08 | B | Cash journal (FBCJ) for petty cash | |
| GAP-FI-09 | B | Dunning: charges, interest calculation, dunning block, dunning notice print | `fi/ar.py:89` `dunning_run`. |
| GAP-FI-10 | B | Assets: acquisition from purchase order, transfer (ABUMN), partial retirement, asset under construction with settlement (AIAB), unplanned depreciation, change of useful life with recalculation, depreciation catch-up when an asset is capitalised late, more keys than straight line, fiscal-year change for assets (AJRW/AJAB) | `fi/aa.py`. |
| GAP-FI-11 | B | Reclassification at closing: GR/IR split into delivered-not-invoiced / invoiced-not-delivered (F.19), vendors with debit balances, customers with credit balances, receivables by remaining term | |
| GAP-FI-12 | B | Cash discount with tax correction; payment on account without open items; tolerance groups for payment differences | `fi/ap.py:236` `pay`. |
| GAP-FI-13 | C | Multiple company codes, intercompany postings, profit centers/segments, parallel ledgers, document splitting | See section 10. |

### 8.4 Controlling

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-CO-01 | A | Commitments (LINK-07) | |
| GAP-CO-02 | A | Cross-year order processing (CODE-001) and CO year-end: carry-forward of order balances and commitments | |
| GAP-CO-03 | B | Order budgets and availability control (LINK-08); cost center budgets | |
| GAP-CO-04 | B | Actual costing / material ledger: period-end price per material (periodic unit price), multi-level settlement of variances to consumption and stock, revaluation of cost of sales. The owner's reference screenshots show an "Actual Costing" process manual, so this is expected | Large. Needs GAP-MM-02 snapshots, a material-ledger document per goods movement category (receipts, consumption, price differences), and a closing run `CKMLCP` with steps: selection → single-level price determination → multi-level → revaluation of consumption → post closing. Plan as its own project. |
| GAP-CO-05 | B | Plan versions, plan copy, plan/actual by period with seasonality; activity price actual calculation (KSII) and revaluation of orders at actual prices | `co/planning.py` has iterative plan prices only. |
| GAP-CO-06 | B | Profit center accounting, or segments on the FI line | |
| GAP-CO-07 | B | CO-PA: top-down distribution (KE28), planning by characteristic beyond customer/material, realignment after master-data change, valuation with cost estimate components at billing (cost component split to value fields — check `co/copa.py` whether COGS is split or one field) | |
| GAP-CO-08 | C | Statistical orders, order groups, settlement to several receivers by amount, results analysis versions for WIP, template allocation | `co/period_end.py:350` raises for the whole run when one order has no settlement rule; collect errors per order instead and continue (after CODE-003 savepoints). Same for `variances` (`:276`). |
| GAP-CO-09 | C | Hard-coded cost elements `400000`, `895000`, `649000`, `649100` in `co/period_end.py` | Move to `co/config.py`. `grep -rn '"[0-9]\{6\}"' --include=*.py mm co fi pur md pp sd` finds 48 hard-coded account numbers outside config and seed files. |

### 8.5 Sales and distribution

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-SD-01 | A | Change a sales order: quantity, price/conditions, dates per item, add and delete items, partner change — with new pricing, new ATP, new credit check and document changes | `sd/order.py:348` `change` supports six header fields and item rejection only. |
| GAP-SD-02 | A | Delivery change and delete (BUG-011); delivery split by ship-to/date; collective delivery run VL10 as an action (the due list exists) | |
| GAP-SD-03 | A | Reference limits for returns and credit memos (BUG-005) | |
| GAP-SD-04 | A | Credit management: re-check at delivery and goods issue, at order change; blocked-document list with release/reject/forward; credit exposure update by open deliveries and billing documents separately; risk categories | |
| GAP-SD-05 | B | Output: order confirmation, delivery note, picking list, invoice as printable forms; invoice numbering rules required by tax law | |
| GAP-SD-06 | B | Down payment requests and milestone billing; invoice lists; pro-forma invoice; billing due list as collective run with split criteria (payer, terms, billing date) — check `VF04` posts one invoice per delivery today | |
| GAP-SD-07 | B | Rebate agreements and settlement; free goods; condition exclusion; manual header conditions; pricing date/exchange rate handling; price change approval | `sd/pricing.py`. |
| GAP-SD-08 | B | Foreign currency and export: currency on order/billing (BUG-010 point 5), export data | |
| GAP-SD-09 | B | Make-to-order, third-party order (PO created from the sales order), consignment fill-up/issue/return, intercompany sales | LINK-02. |
| GAP-SD-10 | C | Shipment and freight cost documents, packing, routes and transportation scheduling beyond the fixed `PICK_DAYS` | |
| GAP-SD-11 | C | Sales organisation is hard-coded `"1000"` (`sd/order.py`, `sd/delivery.py:91` shipping point `"1000"`) | Section 10. |

### 8.6 Production

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-PP-01 | A | Sales requirements in MRP (BUG-003); operation sequence (BUG-013) | |
| GAP-PP-02 | B | MRP: rescheduling proposals (CODE-011), planning time fence, net-change planning (planning file), lot-size minimum/maximum/rounding, assembly and component scrap, safety time, planning calendar; MRP for all plants | |
| GAP-PP-03 | B | Capacity: finite scheduling and levelling (CM01 shows load only), shift calendars per work center, order scheduling forward/backward with queue/move times | |
| GAP-PP-04 | B | Order change after release: quantity change with re-explosion, component add/delete/substitute, operation change; read master data again; order split; mass processing actions in COHV (release, TECO, close) — check which exist | `pp/order.py:201` `change` refuses when the status is DLV; verify what it allows before that. |
| GAP-PP-05 | B | Order close (CLSD) with checks: balance zero, no open commitments, no open reservations; un-TECO; deletion flag | |
| GAP-PP-06 | B | Quality in production: inspection lot at order release / goods receipt, results recording, defects, usage decision (LINK-10) | |
| GAP-PP-07 | C | Alternative BOMs and BOM validity dates/engineering change numbers, co-products and by-products, phantom assemblies, repetitive manufacturing backflush (MF50 planning table), kanban, process orders | |

### 8.7 Master data

| ID | Pri | Missing | Design note |
|---|---|---|---|
| GAP-MD-01 | A | All master-data writes through the engine with change documents (BUG-014) | |
| GAP-MD-02 | B | Approval workflow for creation (request → approve → active), not only dual control for bank data; mass change (MM17/XD99 style) with simulation and log; scheduled changes with valid-from date | |
| GAP-MD-03 | B | Guard rails when stock or open documents exist: base unit change, price control change, valuation class change, material type change (MMAM) — verify which are already blocked in `md/material.py` (a test `test_valuation_class_and_price_control_rules` exists) | Second-pass review item. |
| GAP-MD-04 | C | Business partner model (one partner, several roles), classification, document attachments, units of measure conversions in all documents (`md_marm` exists; check that purchasing/sales order units other than the base unit are converted — PO and sales items appear to use the base unit only) | |

### 8.8 Cross-application

| ID | Pri | Missing |
|---|---|---|
| GAP-X-01 | A | Users, roles, authorisations, audit log (SEC-001) |
| GAP-X-02 | A | Backup/restore, log file, schema migrations (ROB-002) |
| GAP-X-03 | B | Approval inbox: one screen listing everything waiting for the current user (PR/PO release, credit blocks, billing block 08, sensitive master-data changes, blocked invoices) |
| GAP-X-04 | B | Print/PDF forms framework (HTML templates + browser print) used by PO, delivery note, invoice, dunning letter, payment advice |
| GAP-X-05 | B | Background jobs: a simple scheduler table for MRP, dunning, payment proposal, depreciation, backup (run when the server is up) |
| GAP-X-06 | B | Arabic user interface and right-to-left layout; texts are hard-coded English strings inside Python and JS — introduce message catalogues keyed by message class/number (the `MMError` class/number pair is already there and makes this feasible) |
| GAP-X-07 | B | Data import: CSV/Excel upload for opening balances, materials, partners, open items, stock (an LSMW-like tool) — required to go live with real data; there is no way to load a real company today except by calling Python |
| GAP-X-08 | C | Document attachments, notes, document archiving |

---

## 9. Tests and QA hardening

### TEST-001 · S1 · The test suite depends on the calendar [PROVEN]

The suite was run with `datetime.date.today()` faked (harness in 11.1):

| Faked today | Result |
|---|---|
| 2026-11-09 (real) | 115 pass |
| any day in March | all fail — seed crash (BUG-001) |
| 2026-01-02 | 6 fail: 4 × end-to-end "trial balance" (BUG-002), `test_pur.Orders.test_contract_call_off_and_target_check`, `test_sd.Reports.test_cockpit_and_books` |
| 2026-06-01 | 5 fail: 4 × trial balance, `test_sd.Reports.test_cockpit_and_books` (first days of a month: the sales sample is dated day 2–8, i.e. in the future, so the cockpit has no sales yet) |
| 2026-04-29 | 6 fail: 4 × trial balance, `test_sd.Orders.test_quotation_to_order_flow` ("Quotation … was valid until 2026-04-28"), `test_sd.Orders.test_exclusion_incompletion_and_references` (credit block) |
| 2026-12-31 | 2 fail: the same two `test_sd.Orders` tests |

**Fix:**
1. **One clock.** Add `mm.util.today()` and `mm.util.now()`; they return the real date unless `mm.util.set_clock(date)` was called. Replace every direct call: `grep -rn "date.today()\|datetime.now()" --include=*.py mm co fi pur md pp sd web qa` lists 87 call sites (the count includes `now_ts()`, which is fine once `now_ts` itself uses the clock).
2. **Seed relative to a business date.** `mm.seed.seed(conn, business_date=None)`; all sample documents are dated on or before the business date. Decide one of two designs and apply it to all module seeds: (a) the "current-month" sample (SD, PP) is dated in the **previous** month like the others, or (b) sample days are spread up to `min(day, business_date.day)`. Design (a) is simpler and removes "documents dated in the future" (37 FI documents when seeding on the 3rd).
3. **Tests fix their date.** Each test module seeds with a fixed business date (for example 2026-11-09) through the clock, so results never depend on the day the suite runs.
4. **A calendar test** (`tests/test_calendar.py`) seeds and checks books for a list of nasty dates: 1 Jan, 2 Jan, 31 Jan, 28 Feb, 29 Feb 2028, 1 Mar, 31 Mar, 30 Apr, 1 Jun, 31 Dec — books balanced, FI = CO-PA, stock = G/L, trial balance sums to zero.
5. `qa/runner.py` passes the same fixed date, and `ZQA_TEST` shows it.

### TEST-002 · S2 · No tests for the API layer

All 115 tests call engine functions. The 285 routes, their parameter parsing and their output conversion (`AMT`/`QTY` field-name sets in each `*_api.py`, which decide by **field name** whether a number is divided by 100 or 1000) are untested. A new field with a name that is in the wrong set is silently mis-scaled (this already happened once: the KPI key `open` in the production cockpit). *Fix:* the fuzz test (6.1), plus one "happy path" API test per process that drives the same cycle as `tests/test_e2e.py` through `web.server.ROUTES` handlers and compares displayed amounts with database values. Consider replacing name-based scaling by explicit typed output (`amt(x)`, `qty(x)` at the place where the dict is built).

### TEST-003 · S3 · No permanent browser test

Playwright scripts were used during development and are not in the repository. Add `tests/ui/smoke.js` (optional, needs Node + Playwright, not part of the standard test run): open every registered screen, press Execute, fail on page errors and HTTP 5xx; plus one scripted click-through per process (create order → delivery → goods issue → billing; PR → PO → GR → invoice; production order → pick → confirm → GR).

### TEST-004 · S2 · An invariant checker for real data

Add `qa/invariants.py` and a screen `ZQA_CHECK` (and run it at the end of every test module):

1. Every FI document balances (`SUM(debit) = SUM(credit)` per `belnr, gjahr`); no header without items.
2. `valuation.lbkum = SUM(quant.qty)` per material and plant.
3. Standard price: `salk3 = value_of(lbkum, stprs, peinh)`; moving average: `lbkum = 0 ⇒ salk3 = 0`, `salk3 >= 0`.
4. `SUM(valuation.salk3)` per valuation class = balance of its stock G/L account (this is `mm.reports.consistency_check`; keep it, add the others).
5. Sub-ledger = reconciliation accounts for vendors, customers, assets.
6. GR/IR balance per PO item = (received − invoiced) value; `po_item.remng <= wemng` unless invoice-before-GR is allowed.
7. `orders.wemng` = sum of 101/102 movements; `pp_resb.enmng` = sum of 261/262 movements with that reservation (needs BUG-006 columns).
8. Sales: delivered quantity ≤ order quantity (+tolerance); billed quantity ≤ delivered quantity; returned quantity ≤ billed quantity.
9. CO: FI primary costs = CO primary postings per cost element and period; orders with status closed have balance zero; CO-PA reconciliation (`co.reports.reconcile`).
10. Open items: `augbl` set ⇔ `augdt` set; clearing groups sum to zero.
11. Number ranges: `number_range.current >=` the highest number used.

### TEST-005 · S3 · Negative-path coverage to add with each fix

Each BUG above ends with "Done when"; turn every reproduction into a test and add it to `qa/catalog.py` as a test case of its process so it appears in `ZQA_TEST` and in the manuals.

---

## 10. Structure for growth

These are not defects today. They decide how expensive every later feature is.

1. **Organisational structure is hard-coded.** Company code, controlling area, purchasing organisation, sales organisation and shipping point are the literal `"1000"` in many places (for example `pur/po.py:50`, `sd/order.py`, `sd/delivery.py:91`); the local currency is the constant `EGP` (`mm/util.py`, `fi/config.py`). Before a second company or plant group is needed: add `bukrs` to `acc_doc`, `plant`, `asset`, `customer`/`vendor` company views; `kokrs` to CO tables; read the currency from the company code. Do it as one mechanical change with a default of `1000`.
2. **Configuration lives in Python dicts** (`MOVEMENT_TYPES`, `DOC_TYPES`, `TAX_CODES`, `PAYMENT_TERMS`, `ORDER_TYPES`, `ITEM_CATS`, `PRICING_PROCS`, account determination `gl_for`). A user cannot change the VAT rate, add a payment term or a movement type without editing code. Move configuration into tables seeded from the dicts, with small maintenance screens (the SAP "SPRO" idea), and validity dates for tax rates.
3. **Layering.** Engines import each other inside functions to avoid cycles (`mm.posting` → `pp.order`, `md.checks`, `co.integration`, `pp.subcon`; `fi.document` → `co.integration`, `md.checks`). Introduce an event/hook registry in `mm/hooks.py` (`on("goods_movement.posted", fn)`) so MM does not need to know PP and SD. This is also where LINK-07 commitments and LINK-10 inspection lots attach without touching the posting core.
4. **One valuation service.** The moving-average update is implemented four times: `mm/posting.py:_val_plus/_val_minus`, `fi/ap.py:149-170` (invoice price difference), `co/period_end.py:415` (settlement to material), `mm/posting.py:change_price`. Put "add value to stock with coverage rule + price history" into one function in `mm/valuation.py`.
5. **Document flow as a table for all modules.** SD has `sd_vbfa`; purchasing derives its history from material and FI documents. A generic `doc_flow(prev_type, prev_no, prev_item, next_type, next_no, next_item, qty, value)` makes MR8M, returns limits, PO history and audit drill-down simple.
6. **Front end.** `web/static/*_screens.js` is 6,000 lines of imperative DOM code with repeated helpers (`panel`, `grid`, `kpi`, `tabsUI`, `msgLink` are re-declared in several files). Move shared helpers into `core.js`, and describe list/selection screens declaratively (fields, columns, API) so that authorisation, field status and translation can be applied in one place.
7. **Performance at volume.** The seed has a few hundred documents. Reports aggregate from line items on every call (`trial_balance` runs one query per account; `sd.reports`, cockpits). Add totals tables (G/L totals per account/period, CO totals per object/cost element/period, stock per period) maintained in the posting functions, or at least the indexes in 6.2 and a load test with 100,000 documents (generator script in `tools/`).
8. **Packaging.** No `pyproject.toml`, no linter configuration, no continuous integration. Add a GitHub Actions workflow that runs the unit tests on Windows and Linux for Python 3.9–3.13, the fuzz test, the calendar test, and `python -m compileall`. Add `ruff` (configuration only; not a run-time dependency).
9. **Windows specifics.** The Office bridge (`office/com_bridge.py`) needs Excel/Outlook and `pywin32` or PowerShell; make sure every route degrades with a clear message on machines without Office (the fuzz run skipped these routes).

---

## 11. Reproduction harnesses (the review scripts are not in the repository — recreate them from here)

### 11.1 Fake the calendar (until TEST-001 introduces `mm.util.set_clock`)

```python
# fake_today.py  — usage: python fake_today.py 2026-03-15
import sys, datetime as _dt
fake = _dt.date.fromisoformat(sys.argv[1])
_D, _DT = _dt.date, _dt.datetime
class FD(_D):
    @classmethod
    def today(cls): return cls(fake.year, fake.month, fake.day)
class FDT(_DT):
    @classmethod
    def now(cls, tz=None): return cls(fake.year, fake.month, fake.day, 10, 0, 0)
_dt.date, _dt.datetime = FD, FDT          # must run before importing the application
sys.path.insert(0, "."); sys.path.insert(0, "tests")
import unittest
suite = unittest.defaultTestLoader.discover("tests", top_level_dir="tests")
res = unittest.TestResult(); suite.run(res)
print(sys.argv[1], "run", res.testsRun, "fail", len(res.failures), "err", len(res.errors))
for t, tb in res.failures + res.errors:
    print("  ", t.id(), "::", tb.strip().splitlines()[-1][:150])
```

To test only the seed, replace the unittest part by `from mm.db import connect; from mm import seed; seed.seed(connect(":memory:"))`.

### 11.2 API fuzz

```python
import os, re, sys, collections, traceback
sys.path.insert(0, ".")
from mm.db import connect; from mm import seed; from mm.util import MMError
import web.server as S
conn = connect(":memory:"); seed.seed(conn); S._local.conn = conn
class Req: user = "FUZZ"; body = {}; headers = {}
SKIP = ("shutdown", "bye", "reset", "qa/run", "office", "excel", "outlook", "export", "com/")
bad = []
for method, rx, fn in S.ROUTES:
    pat = rx.pattern.strip("^$")
    if any(w in pat for w in SKIP): continue
    kw = {k: "1" for k in rx.groupindex}          # numeric path parameters
    for body, q in (({}, {}), ({"items": [{}], "lines": [{}], "matnr": "ZZZ", "qty": "abc",
                               "budat": "99", "id": "x"}, {"id": "x", "gjahr": "x", "perio": "y", "d1": "q"})):
        r = Req(); r.body = body
        try: fn(r, dict(q), **kw)
        except MMError: pass
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)[-1]
            bad.append((method, pat, type(e).__name__, "%s:%s" % (os.path.relpath(tb.filename), tb.lineno)))
assert not bad, bad
```

### 11.3 Scenario reproductions (all on a freshly seeded in-memory database; `TODAY = date.today().isoformat()`)

| Defect | Steps |
|---|---|
| BUG-005 | `order.create(OR, C1001, FG-3001 × 2)` → release credit if `cmgst='B'` → `delivery.create` → `pick` → `post_gi` → `billing.create` → twice: `order.create(dict(auart="RE", vgbel=inv, augru="101", items=[dict(matnr="FG-3001", qty="2", vgbel=inv, vgpos=pos)]))` |
| BUG-006 | `pp.order.create(PP01, FG-3001 × 2, ops=[WC-ASSY])` → `release` → `post_picking(picking_list rows of the order)` → `mm.posting.cancel_document(mblnr, mjahr)` → read `pp_resb.enmng` |
| BUG-007 / 008 | `po.create_po(100005, SP-4002 × 5 @ 58)` → `release_all` → GR 101 × 5 in bin S-02 → `ap.miro(qty 2, xblnr "DUP-1")` twice → `cancel_document` on the GR → read `po_item.wemng, remng` |
| BUG-009a | `gl.vat_settlement(first_of_month, TODAY, TODAY, user)` twice |
| BUG-009c | `ap.payment_run(TODAY, "ZZ1", TODAY+40d, user, execute=True)` → same with `execute=False` → read `payrun.status` → `execute=True` again |
| BUG-010 | `po.create_po(300001, RM-1004 × 10 @ 10.00)` → release → GR in bin C-02-02 → `ap.miro` → read `acc_doc.waers` and the items |
| BUG-011 | order × 3 → `delivery.create` (no goods issue) → `order.change(v, {"items": [{"posnr": 10, "abgru": <any rejection reason>}]})` → `post_gi` |
| BUG-013 | `pp.order.create(PP01, FG-3003 × 1)` → `release` → `confirm(aufnr, "0020", "1")` before operation 0010 |
| BUG-003 | order for (unrestricted stock of FG-3002 + 50) → `planning.stock_requirements("FG-3002")` → `planning.mrp_run` |

---

## 12. Recommended order of work

Each phase is one or more pull requests. Every phase ends with: all tests green under the calendar test, `python -m qa.runner` green, new cases added to `qa/catalog.py`, README updated, zip delivered.

| Phase | Content | Items |
|---|---|---|
| **1 — Stop the time bombs** (small, urgent) | Central clock; seeds clamp dates and are atomic; tests use a fixed business date; calendar test; start-up error page and log file | BUG-001, TEST-001, part of ROB-002 (log) |
| **2 — Books and controls** | Year-end carry-forward; duplicate invoice check; MR8M + invoice item table; FBRA; depreciation reversal; GR-reversal guard; return/credit limits; idempotent VAT / FX / payment run; reservation on material document; billing integer arithmetic; settlement-to-material rule; cross-year CO period key; invariant checker | BUG-002, 004, 005, 006, 007, 008, 009, 012, CODE-001, CODE-002, TEST-004 |
| **3 — Robust API and platform** | Input parsing helpers and fuzz test; API writes moved into engines; savepoints; `write` self-transactional; connection handling, WAL, schema version, indexes, backup; CSRF/Origin/Host checks; UI 404 guards and menu entries | ROB-001, ROB-002, ROB-003, BUG-014, CODE-003, CODE-004, SEC-002, SEC-003 |
| **4 — Close the process gaps** | Sales requirements in MRP and shared ATP; delivery change/delete and rejection rule; operation sequence; sales order change; credit re-check; foreign currency in purchasing, then in sales; commitments | BUG-003, BUG-010, BUG-011, BUG-013, GAP-SD-01, GAP-SD-04, LINK-07, LINK-12 |
| **5 — Users and authorisations** | Login, sessions, roles, authorisation checks, audit log, approval inbox | SEC-001, GAP-X-01, GAP-X-03 |
| **6 — Functional backlog by priority A → B** | Physical inventory, MM periods, invoice tolerances and blocks, withholding tax, manual clearing, down payments, posting periods per account type, bank clearing accounts, print forms, data import; then the B list; actual costing as its own project | Section 8 |

After Phase 2, do a second review pass over the modules that were not read in depth (list in section 2).

---

## 13. Documentation that does not match the code

| ID | Where | Statement | Reality |
|---|---|---|---|
| DOC-001 | `qa/catalog.py`, process P2P, control "Three quotations above the limit", linked to case P2P-05 | Presented as a tested control | The test only checks that the cheapest quotation wins; nothing requires three quotations |
| DOC-002 | `qa/catalog.py`, process PTP, control "Confirm in sequence, scrap with reason", linked to PTP-07 | Presented as a tested control | Sequence is not enforced (BUG-013); scrap has no reason field |
| DOC-003 | `qa/catalog.py`, process INV, step 5 "Physical count" → `MB52` | Looks like a physical inventory process | There are no inventory documents (GAP-MM-01) |
| DOC-004 | `qa/catalog.py`, process R2R, control "Reverse, never delete" | True for FB08 | Not possible for MIRO, payment and depreciation documents (BUG-004) |
| DOC-005 | Messages in `fi/gl.py:101`, `:108` | Tell the user to use MR8M / FBRA | Do not exist |
| DOC-006 | PowerPoint manuals (`web/static/manuals/*.pptx`, English and Arabic) | Generated from the catalog; repeat DOC-001…004 | Regenerate after the catalog is corrected: `python -m qa.runner`, `python -m qa.export qa.json`, `node tools/manuals/make_manuals.js qa.json web/static/manuals`, `node tools/manuals/make_manual_ar.js qa.json web/static/manuals` |
| DOC-007 | "86 test cases, 115 automated tests, all passed" in the test book and README | True on the review date | Date dependent until TEST-001 is done |

---

## 14. What is in good shape (keep it that way)

- Exact integer arithmetic in the MM, FI and CO cores; `rdiv` commercial rounding.
- One FI writer with period, document-type, reconciliation-account and balance checks; CO derivation at the same place.
- Goods movement engine: FIFO quants with goods-receipt date kept through transfers, moving-average and standard price, reversal that restores bins and dates, all-or-nothing posting, "Check" mode.
- On the seed data every invariant in TEST-004 items 1–5 holds, FI = CO-PA reconciles for the sample and the current month, and re-running MRP, overhead, variance and settlement is idempotent.
- Release strategy is reset when a PO value rises; over-delivery, over-confirmation and quantity-below-receipt are blocked.
- 369 screens open without a JavaScript error.
