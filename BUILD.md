# BUILD.md — what is built and how to run it

This is the **first working vertical slice** of the Factory Decision Intelligence System:
the **numeric trust loop** for Finance, with all seven tool layers (MASTER_PLAN K.1)
connected — real where they run today, adapter-stubbed where they need heavy infra.

## Run it
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q          # 9 tests pass
python run_demo.py # full pipeline on sample finance data
```

## What runs for real today
ingest (**DuckDB**, text-first) → clean (**Polars**: total-row + duplicate + locale
defenses, conservation law) → **governed metric** variance bridge → **one-A4 manager
card** (every number carries evidence; refuses uncited numbers) → **independent audit**
(re-runs the totals in DuckDB SQL as a four-eyes check vs the Polars path, scores
certainty, raises a deep multiple-choice question when data quality is low) → **accountable
human sign-off** → **memory** (local knowledge + temporal stores) → **HTML render**.

The demo deliberately uses messy sample data (an embedded total row, a duplicate, an
unparseable amount) so you can see the defenses fire and the audit ask the human.

## What is stubbed behind a clean adapter (needs infra/models — `requirements-optional.txt`)
| Layer | Adapter | Plug in |
|---|---|---|
| Doc extraction / OCR | `engines/docs/extract.py` | Docling, PaddleOCR (offline EN+AR) |
| Knowledge graph | `engines/brain/memory.py` `CogneeMemory` | Cognee (Kuzu+LanceDB) |
| Temporal graph | `engines/brain/memory.py` `GraphitiMemory` | Graphiti (Kuzu/FalkorDB) |
| Output/design | `serving/open_design.py` `OpenDesignRenderer` | nexu-io/open-design |
| Enterprise search | (v2-v3) | Onyx |
| Synthesis / embeddings | `config.yaml` `ai.*` | on-prem model via vLLM |

Each stub raises a clear "install X and wire here" error, and `config.yaml` switches the
real tool on (e.g. `tools.knowledge_memory: cognee`). The architecture is the contract;
swapping a stub for the real tool changes no other module.

## Invariant (MASTER_PLAN trust wall + Part O)
Numbers come only from the data engine; every number on the card is cited; the audit layer
re-checks independently; and **nothing is marked released without a named human sign-off.**
