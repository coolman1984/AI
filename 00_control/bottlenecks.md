# Bottlenecks

| ID | Date | Type | Description | Smallest removal action | Status |
|----|------|------|-------------|------------------------|--------|
| B1 | 2026-06-30 | Output quality gap | Variance was total-level; managers want price/qty/mix drivers | Built price_volume_mix (T8); reconciles to the cent | Resolved (E11) |
| B5 | 2026-06-30 | Output surfacing gap | Decomposition exists but not yet shown on the card/dashboard | Add drivers to the dashboard (T8b) — no infra | Active (next) |
| B2 | 2026-06-30 | Technical limitation | Heavy backends (LLM/graph DB/GPU) absent in this env | Provision one on-prem LLM + Kuzu → flip config switches (T9) | Blocked (needs infra) |
| B3 | 2026-06-30 | Missing data | No real SAP-scale export tested | Obtain one real export; run ingest/profile (T-future) | Open |
| B4 | 2026-06-30 | Mission ambiguity | Exact first finance workflow unconfirmed | One owner answer (open_questions.md) | Open |

Current primary bottleneck: **B5** — surface the price/volume/mix drivers in the output
(T8b), removable now, no infra needed.
