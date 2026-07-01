# Issue Tracker
| ID | Issue | Status | Note |
|----|-------|--------|------|
| I1 | Heavy tools (Docling/PaddleOCR/Surya/VLM, Cognee/Graphiti, Onyx, Open Design) need infra | Open-by-design | Real adapters exist; activate only after P2 gates in `03_design/implementation_plan.md` |
| I2 | Price/volume/mix decomposition exists but is not yet surfaced in the manager output | Resolved | Closed by T8b with explicit standard-cost labeling (E14) |
| I3 | Real SAP-scale (200MB/272col) not yet exercised | Open | Needs one real export and profiling before T9 |
| I4 | Current branch policy diverges from the repo's earlier single-main rule | Known/controlled | Owner explicitly approved branch `chatgpt-ai-tasks`; keep it small, green, and mergeable |
| I5 | PowerPoint extraction is not yet a first-class ingestion path | Open | Add structured slide/table extraction under IS4 |
| I6 | Email extraction is not yet a first-class ingestion path | Open | Add body + attachment extraction under IS5 |
| I7 | PDF support is starter-level for text; table extraction is not yet promoted into unified storage | Open | Add structured PDF table extraction under IS3 |
| I8 | There is no unified storage contract yet for cross-source extracted rows and fields | Open | Resolve under IS1 before broad query/calculation work |
