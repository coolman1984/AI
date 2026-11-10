# Fix status - Engineering Review and Fix Plan

State after phases 1 - 6 of `docs/FIX_PLAN.md`:

- 161 automated tests pass.
- 123 / 123 QA cases pass across 9 processes, on the fixed business date 9 Nov 2026.
- The data consistency check (ZQA_CHECK) is clean.

Every review item is listed below as **done**, **partial** (what is missing is named) or **open** (not built; reason given).

## Defects (BUG), code (CODE), robustness (ROB), security (SEC), tests (TEST)

| ID | Status | Where |
|---|---|---|
| BUG-001 seed fails on some dates | done | atomic seed, date clamping, `tests/test_calendar.py` (12 dates) |
| BUG-002 no fiscal-year closing | done | F.16 carry-forward, retained earnings, trial balance |
| BUG-003 sales orders invisible to MRP | done | VC/VJ elements, strategy 40 consumption |
| BUG-004 no reversal of invoice / payment / depreciation | done | MR8M, FBRA, ZAFAB_REV |
| BUG-005 billing above the reference | done | return / credit limits V1 019 / 023 / 024 |
| BUG-006 goods issue reversal loses the reservation | done | rsnum / rspos on the material document |
| BUG-007 GR reversal below invoiced qty | done | `_check_not_invoiced` |
| BUG-008 duplicate vendor invoice | done | F5 117, reference mandatory |
| BUG-009 period-end programs run twice | done | `vat_run`, `fx_run`, `grir_run` |
| BUG-010 foreign currency | **partial** | Purchasing (PO, GR, MIRO, payment) is done. Sales bills in the customer currency, but sales prices stay in EGP |
| BUG-011 delivery change / delete | done | VL02N |
| BUG-012 rounding in billing | done | integer split |
| BUG-013 operation sequence | done | RU 006 / 007, scrap reasons |
| BUG-014 SQL writes in API handlers | done | guard test `Layers` |
| CODE-001 … CODE-011 | done | see phases 1 - 3 |
| ROB-001 input parsing | done | parse helpers, fuzz test over all routes |
| ROB-002 server / database plumbing | done | WAL, migrations, backup / restore, log file |
| ROB-003 UI fixes | done | |
| SEC-001 no authentication | done | Logon, roles, transaction / area / object checks, SM20, AMS (phase 5) |
| SEC-002 / SEC-003 foreign sites, error leaks | done | Host / Origin / Content-Type checks; 500 responses carry only a reference |
| TEST-001 … TEST-005 | done | fixed clock, API tests, invariants, negative cases |

## Priority-A gaps

| ID | Status | Where |
|---|---|---|
| GAP-MM-01 physical inventory | done | MI01 / MI03 / MI04 / MI11 / MI20 / MI07 / MICN, posting block M7 140 |
| GAP-MM-02 MM periods | done | MMPV / MMRV, `valuation_hist` |
| GAP-MM-03 stock on a past date | done | MB5B. MB5K covers the stock / G/L comparison |
| GAP-PUR-01 MR8M, credit memo, subsequent debit | done | |
| GAP-PUR-02 tolerances, payment block | done | MRBR |
| GAP-PUR-03 / GAP-FI-05 withholding tax | done | ZWHT, ZWHT_RPT (form 41), deducted at invoice |
| GAP-FI-05 rest of the Egyptian localisation | **partial** | VAT return layout (form 10), stamp duty and the real ETA e-invoice submission are not built. The submission needs the tax-authority API credentials and network access |
| GAP-FI-01 year-end | done | |
| GAP-FI-02 manual clearing, FBRA | done | F-44 / F-32 / F-03 |
| GAP-FI-03 down payments | done | F-47 / F-37 / F-48 / F-29 / F-54 / F-39 |
| GAP-FI-04 periods per account type, periods 13 - 16 | done | OB52 |
| GAP-CO-01 / GAP-CO-02 commitments, cross-year | done | KSB2 / KOB2 |
| GAP-SD-01 … GAP-SD-04 | done | VA02, VL02N, limits, credit at every step |
| GAP-PP-01 | done | |
| GAP-MD-01 | done | |
| GAP-X-01 users and authorisations | done | ZAMS, ZINBOX, SU01, PFCG, SUIM, SU53, SM04, SM20 |
| GAP-X-02 backup, log, migrations | done | |
| GAP-X-04 print forms (B) | done | ZPRINT with 8 forms and an output log |
| GAP-X-07 data import (B) | done | ZIMPORT with 11 objects |
| DOC-001 three quotations | done | ME 394 / 395, release R1 with a reason |
| DOC-002 … DOC-007 | done | Catalog, manuals (English and Arabic) and README regenerated |

## Not built yet (priority B / C - design notes in FIX_PLAN 8.10)

None of these were in the A list of the plan. Each one is a separate project:

- Batches and shelf life.
- Special stocks and stock transport orders.
- Warehouse tasks.
- Service entry sheet.
- Scheduling agreements.
- House banks and the bank statement import.
- Asset acquisition from a PO, transfer and asset under construction.
- Actual costing / material ledger.
- Budgets and availability control.
- Profit centers.
- Job scheduler.
- Arabic user interface.
- Multiple company codes.
