# Risks

| ID | Date | Risk | Cause | Impact | Prob | Mitigation | Status |
|----|------|------|-------|--------|------|-----------|--------|
| R1 | 2026-06 | Confident wrong number reaches management | synthesis/extraction error | S1 (disaster) | Low | independent audit + sign-off (built) | Mitigated |
| R2 | 2026-06 | Metric ambiguity ("variance"/"margin") across depts | no governed definitions | S1 | Med | semantic/metric layer (Part R; metric registry started) | Open |
| R3 | 2026-06 | Prompt injection via ingested docs/emails | untrusted content + acting tools | S2 | Med | treat retrieved text as data; quarantine learned-from-docs (Part P) | Open |
| R4 | 2026-06 | OCR/handwriting trusted blindly | low-confidence extraction | S1 | Med | quality gate → human-review queue (built) | Mitigated |
| R5 | 2026-06 | Heavy adapters never activated (no infra) | GPU/LLM/graph DB absent | S3 | Med | working local baseline; config switch when ready | Accepted |
| R6 | 2026-06 | Direct-to-main bad commit | owner no-branches directive | S3 | Low | every commit green (tests+lint+CI) | Mitigated |
| R7 | 2026-06 | Real SAP scale/mess breaks assumptions | only sample data tested | S3 | Med | streaming design; run on real export early (T-future) | Open |
| R8 | 2026-06 | Low adoption | black-box distrust / change mgmt | S3 | Med | evidence-cited cards, parallel-run, sign-off ownership | Open |
