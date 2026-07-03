---
type: dataset
title: Cost Center Actuals (SAP export)
fingerprint: "seed-001 (placeholder)"
period: "monthly"
status: active
---

# Cost Center Actuals (SAP export)

## Source
SAP CO module, monthly export via transaction KSBT. Dropped into `datasets/inbox/` by the costing team.

## Columns
| Column | Type | Notes |
|---|---|---|
| KOSTL | string | Cost center code |
| WKG001 | float | Amount in local currency |
| BUKRS | string | Company code |
| GJAHR | string | Fiscal year |
| PERIO | string | Period |

## Known quirks
- Header row sometimes missing or translated
- Negative amounts use parenthesis convention `(1,234.56)`
- Subtotal rows embedded in data (rows with "Total" in KOSTL)
