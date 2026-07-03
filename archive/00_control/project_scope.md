# Project Scope

## In scope (now)
- Numeric trust loop: ingest (DuckDB) → clean (Polars, messy-data defenses) → governed
  variance → one-A4 cited card → independent audit → human sign-off.
- Documents: pypdf extraction + OCR cascade (Tesseract→RapidOCR→…→VLM) + `search_documents`.
- Memory: decision, knowledge (relations), temporal (change over time) — local, real.
- Output: HTML dashboard (SVG chart) + PPTX.
- Multi-department by lens config; role-scoped access; cross-department factory brief.

## In scope (later / adapters ready)
- Heavy backends behind config switches: Docling, PaddleOCR/Surya/VLM-OCR, Cognee, Graphiti,
  Onyx, Open Design app, on-prem synthesis LLM (vLLM) — activate when infra exists.
- price/qty/mix variance decomposition; real SAP-scale data; deployment; gated self-evolution.

## Out of scope (deliberately, until value is proven)
- Boiling the ocean (all departments at once); ISA-95/OPC UA/full Dagster/DataHub now;
  sending any factory data to external services (in-house only).
