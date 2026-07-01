# Bottlenecks

| ID | Date | Type | Description | Smallest removal action | Status |
|----|------|------|-------------|------------------------|--------|
| B1 | 2026-06-30 | Output quality gap | Variance was total-level; managers want price/qty/mix drivers | Built price_volume_mix (T8); reconciles to the cent | Resolved (E11) |
| B5 | 2026-06-30 | Output surfacing gap | Decomposition exists but was not shown on the card/dashboard | Surfaced it with explicit standard-cost labeling (T8b) | Resolved (E14) |
| B2 | 2026-06-30 | Technical limitation | Heavy backends (LLM/graph DB/GPU) absent in this env | Provision one on-prem LLM + Kuzu → flip config switches (T9) | Blocked (needs infra) |
| B3 | 2026-06-30 | Missing data | No real SAP-scale export tested | Obtain one real export; run ingest/profile (P2) | Active (next) |
| B4 | 2026-06-30 | Mission ambiguity | Exact first finance workflow unconfirmed | One owner answer (open_questions.md) | Open |

Current primary bottleneck: **B3** — no real SAP-scale export has been profiled yet.
The next safe move is P2: lock the first workflow and run one real export through the ingest/profile path.
