# Issue Tracker
| ID | Issue | Status | Note |
|----|-------|--------|------|
| I1 | Heavy tools (Docling/PaddleOCR/Surya/VLM, Cognee/Graphiti, Onyx, Open Design) need infra | Open-by-design | Real adapters exist; activate only when the gates in `03_design/assistant_master_plan.md` allow it |
| I2 | Price/volume/mix decomposition exists but is not yet surfaced in the manager output | Resolved | Closed by T8b with explicit standard-cost labeling (E14) |
| I3 | Real SAP-scale (200MB/272col) not yet exercised | Open | Needs one real export and profiling before T9 |
| I4 | Current branch policy diverges from the repo's earlier single-main rule | Resolved | Current rule restored: one branch `main`; no new branches |
| I5 | PowerPoint extraction is not yet a first-class ingestion path | Open | Add structured slide/table extraction under IS4 |
| I6 | Email extraction is not yet a first-class ingestion path | Open | Add body + attachment extraction under IS5 |
| I7 | PDF support is starter-level for text; table extraction is not yet promoted into unified storage | Resolved | Closed by IS3: `engines/data/pdf_tables.py` + `tests/test_pdf_tables.py` |
| I8 | There is no unified storage contract yet for cross-source extracted rows and fields | Resolved | Closed by IS1: schema + lifecycle helpers + tests (E17) |

## Real-data issue promotion template (E.4)

Use this row shape when profiling or first real ingest finds something that must not disappear
into notes:

| ID | Issue | Status | Source / run | Owner | Next action | Evidence |
|----|-------|--------|--------------|-------|-------------|----------|
| I9 | _example: locale amount column misparsed on Sheet2_ | Open | `raw/sap_export.xlsx`, run_id=_, sheet=`Sheet2` | _owner_ | Add task row for parser rule before code | `tests/test_ingestion_spine.py::...`, reject `unconvertible_amount` sample |

Rules:
- material failures get an `I#` row here before implementation starts
- each open issue names an owner and a single next action
- resolved issues point to the test or profile evidence that closed them
