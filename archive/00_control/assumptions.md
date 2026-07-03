# Assumptions

| ID | Date | Assumption | Reason | Risk | How to verify | Impact if wrong |
|----|------|------------|--------|------|---------------|-----------------|
| A1 | 2026-06 | Sample data shape mirrors real SAP exports (grain=sub_assembly, etc.) | needed to build the loop before real data | Med | run on a real export | column-map rework (isolated to lens) |
| A2 | 2026-06 | An on-prem LLM (Qwen/Llama/DeepSeek via vLLM) will be available for synthesis + Cognee/Graphiti extraction | in-house rule | Med | provision infra | synthesis/graph stays adapter-only |
| A3 | 2026-06 | A local graph DB (Kuzu/FalkorDB) will host Cognee/Graphiti | their requirement | Low | install | temporal/knowledge stay on local JSON store (still functional) |
| A4 | 2026-06 | First finance workflow ≈ monthly cost variance vs budget | matches pilot framing | Low | confirm with owner | re-scope sample + metric (config) |
| A5 | 2026-06 | Tesseract + eng/ara packs available in deploy env | OCR baseline | Low | `tesseract --version` | OCR falls to review queue |
