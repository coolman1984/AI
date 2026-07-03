# Factory Brain — Complete Project Map

**Purpose of this file:** A single comprehensive reference that any AI agent can read to
understand *everything* in this repository: what it builds, how it is organized, what
every module does, how the phases and tests are structured, and what state the project
is in. Read this first, then descend into individual `AGENTS.md` files and skill files
as needed.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Name** | Factory Brain (`factory-brain`) |
| **Type** | Factory-wide Decision Intelligence System |
| **Domain** | TV/Mobile manufacturing plant under Korean HQ |
| **Python** | 3.11+ |
| **Test framework** | pytest |
| **Linter** | ruff (select: E/F/I/UP/B, line-length 100) |
| **Package manager** | uv (`uv.lock` present) |
| **Branch policy** | Single `main` branch only. No branches ever. |
| **Pilot** | Finance / Costing (first department lens) |
| **Status** | Feature-complete on synthetic data through Phase F. Blocked only on real SAP export (P2.2/E.1). |

**Core mission** (from `03_design/assistant_master_plan.md:12-33`):
1. Extract everything (spreadsheets, PDFs, PPTX, emails, scans) into governed local DBs
2. Preserve everything forever with citations, versions, time history — nothing is lost
3. Understand fast — 50-slide Korean HQ deck → English one-page brief in under an hour
4. Combine knowledge continuously — cross-linked, contradictions surfaced, ideas labeled
5. Support decisions — evidence-backed briefs and meeting packs for C-suite
6. Serve other AI agents efficiently — packaged as skill library + tools + routing map

**Catastrophic failure mode (designed against everywhere):** A confident wrong claim or
number reaching an executive.

---

## 2. Complete Directory Tree

```
G:\AI\
│
├── AGENTS.md                       # Root agent operating manual (read order, rules, build chain, commands)
├── AGENT_CORE_CONTRACT.md          # Shared contract all agent skills must obey (run identity, evidence, trust)
├── AGENT_SKILL_MAP.md              # Lightweight routing: which skill file to load for which task
├── PROJECT_MAP.md                  # ★ THIS FILE — complete project reference
├── BUILD.md                        # Build/run instructions
├── CLAUDE.md                       # AI team orchestration workflow
├── FACTORY_SECOND_BRAIN.md         # Historical project overview (superseded)
├── MASTER_PLAN.md                  # Original master plan (superseded by v2)
├── README.md                       # (not present at root — see 04_execution/README.md)
├── config.yaml                     # Main configuration (AI providers, roles, audit thresholds, tool switches)
├── column_map.yaml                 # Human-reviewed column name canonicalization mapping
├── pyproject.toml                  # Project metadata, pytest config, ruff config
├── requirements.txt                # Core pinned dependencies (DuckDB, Polars, PyMuPDF, etc.)
├── requirements-optional.txt       # Heavy/infra-dependent optional deps (Docling, Cognee, etc.)
├── run_demo.py                     # End-to-end demo script
├── uv.lock                         # Lock file for uv package manager
│
├── .brain/                         # (gitignored) Runtime runtime data: memories, claims, ledger
├── .github/workflows/
│   └── ci.yml                      # CI: ruff check + pytest on push to main
├── .gitignore                      # Ignores .venv, __pycache__, .brain/, out/, caches
│
├── 00_control/                     # Governance and project control documents (17 files)
│   ├── assumptions.md              # Explicit project assumptions
│   ├── bottlenecks.md              # Current bottlenecks and constraints
│   ├── decisions.md                # Decision log
│   ├── evaluation_report.md        # Evaluation results
│   ├── evidence_log.md             # Evidence tracking
│   ├── memory_index.md             # Memory index
│   ├── mission.md                  # Mission statement
│   ├── open_questions.md           # Open questions
│   ├── plan_review.md              # Plan review notes
│   ├── progress.md                 # Progress tracking
│   ├── project_scope.md            # Project scope definition
│   ├── restart_notes.md            # Session resumption guide
│   ├── risks.md                    # Risk register
│   ├── run_log.md                  # Run log
│   ├── session_state.md            # Session state
│   ├── success_contract.md         # Success criteria
│   └── task_queue.md               # ★ Master task queue (87 rows, A0-F.10 + T-series)
│
├── 01_inputs/                      # Raw input source inventory
│   └── source_inventory.md         # Inventory of data sources
│
├── 02_understanding/               # Requirements and terminology
│   ├── data_map.md                 # Data mapping
│   ├── extracted_requirements.md   # Extracted requirements
│   └── terminology.md              # Domain terminology
│
├── 03_design/                      # Architecture and design documents
│   ├── assistant_master_plan.md    # ★ CURRENT approved architecture (v2, 342 lines — READ THIS)
│   ├── architecture.md             # Pointer to master plan
│   ├── codex_planning_prompt.md    # Codex expansion prompt
│   ├── current_implementation_plan.md  # ★ Live execution plan (252 lines)
│   ├── implementation_plan.md      # Historical (superseded)
│   ├── oss_reference_evaluation.md # OSS tool evaluation against v2 plan
│   ├── phase_a_cards.md            # ★ Current Phase A build cards (289 lines)
│   ├── phase_b_to_f_cards.md       # Phase B-F build cards (1055 lines)
│   ├── rollback_plan.md            # Rollback plan
│   ├── skill_os_blueprint.md       # FOREMAN blueprint — skill-OS governance layer over the engines (2026-07-03)
│   ├── foreman_build_plan.md       # FOREMAN phased build plan — code-writer execution order (2026-07-03)
│   ├── foreman_review_brief.md     # FOREMAN review charter — hand to a reviewer agent before building (2026-07-03)
│   ├── unified-ingestion-spine.md  # Bilingual (AR/EN) ingestion spine design
│   ├── validation_plan.md          # Validation plan
│   └── reviews/
│       └── opus_critique.md        # Adversarial review of v1 architecture (184 lines)
│
├── 04_execution/                   # Execution state
│   └── README.md
│
├── 05_validation/                  # Validation artifacts
│   ├── error_log.md
│   ├── issue_tracker.md
│   ├── quality_checks.md
│   └── test_results.md
│
├── 06_final_outputs/               # Final outputs
│   ├── handover_notes.md
│   └── proof_of_completion.md
│
├── agent_skills/                   # ★ 7 files — 6 capability skills + 1 external inventory
│   ├── audit_and_trust.md          # Release gating, independent re-check
│   ├── cost_variance_analysis.md   # Price/volume/mix driver decomposition
│   ├── document_evidence_extraction.md  # PDF/PPTX/OCR extraction
│   ├── EXTERNAL_SKILLS_INVENTORY.md  # Map of external skill libraries in Downloads/Skills
│   ├── knowledge_search.md         # Retrieval from stored knowledge
│   ├── management_reporting.md     # Executive output shaping
│   └── spreadsheet_ingestion.md    # Tabular data ingest/clean
│
├── archive/                        # Superseded historical docs (8 files — do not read unless needed)
│   ├── ARCHITECTURE.md
│   ├── CODEX_PLAN.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── IMPLEMENTATION_PLAN_DOCS.md
│   ├── IMPLEMENTATION_PLAN_SECONDBRAIN.md
│   ├── PROJECT_STATE_AND_ROADMAP.md
│   ├── REVIEW.md
│   └── RISK_AND_GAPS_AUDIT.md
│
├── data/sample/                    # Sample data for demo/testing
│   ├── budget_approval_2026.pdf            # Text PDF (budget evidence)
│   ├── budget_approval_scanned.pdf         # Scanned PDF (triggers OCR cascade)
│   ├── finance_actuals.csv                 # Finance actuals (messy — has total rows, duplicates)
│   ├── finance_actuals_2026_06.csv         # Next period actuals
│   ├── finance_budget.csv                  # Finance budget baseline
│   ├── finance_standards.csv               # Standards for driver decomposition
│   ├── planning_actuals.csv                # Planning department actuals
│   └── planning_plan.csv                   # Planning baseline
│
├── downloads/                      # Cloned OSS reference repos (not built, for reference only)
│   ├── cognee/                     # Knowledge graph memory (KuzuDB + LanceDB)
│   ├── docling/                    # IBM Docling — hard-layout document parser
│   ├── graphiti/                   # Temporal knowledge graph
│   ├── mail-parser/                # Email parsing library
│   └── pdfplumber/                 # PDF table extraction
│
├── engines/                        # ★ CORE — 6 processing engines (the brains)
│   ├── __init__.py
│   ├── audit/                      # Independent audit + human sign-off (Part O)
│   │   ├── __init__.py
│   │   ├── AGENTS.md
│   │   ├── audit.py                # Independent re-run + certainty + sign-off enforcement
│   │   └── brief_audit.py          # Non-numeric brief claim audit
│   ├── brain/                      # Memory, claims, registry, ontology, search, orchestrator
│   │   ├── __init__.py
│   │   ├── AGENTS.md               # 59 lines — full interface documentation
│   │   ├── claims.py               # ClaimsStore (physically separate from facts)
│   │   ├── comparison.py           # IR quarter + factory comparison
│   │   ├── contradictions.py       # Contradiction surfacing across claims/records
│   │   ├── edges.py                # Typed cross-workflow edges
│   │   ├── factory.py              # Multi-department factory brain
│   │   ├── idea_synthesis.py       # Labeled AI-SUGGESTED IDEA synthesis
│   │   ├── memory.py               # Knowledge + temporal memory (local + Cognee/Graphiti adapters)
│   │   ├── ontology.py             # Canonical entity IDs
│   │   ├── open_questions.py       # Queryable open questions
│   │   ├── orchestrator.py         # Full pipeline orchestrator
│   │   ├── registry.py             # Document registry
│   │   ├── search.py               # Knowledge search contract
│   │   ├── workflow_diff.py        # Version diff view
│   │   └── workflow_family.py      # Workflow families + versioning
│   ├── data/                       # ★ THE ONLY SOURCE OF TRUSTED NUMBERS (DuckDB, Polars)
│   │   ├── __init__.py
│   │   ├── AGENTS.md               # 26 lines — full interface documentation
│   │   ├── clean.py                # Data cleaning: totals detection, dupes, locale amounts
│   │   ├── drivers.py              # Price/volume/mix decomposition
│   │   ├── ingest.py               # CSV/Excel/PDF table ingestion spine
│   │   ├── pdf_tables.py           # PDF table extraction
│   │   ├── query_readiness.py      # Cross-source query readiness
│   │   ├── types.py                # Column type inference
│   │   └── variance.py             # Governed variance computation
│   ├── docs/                       # Document evidence extraction (PDF, PPTX, OCR)
│   │   ├── __init__.py
│   │   ├── AGENTS.md               # 55 lines — full interface documentation
│   │   ├── docling_adapter.py      # Docling hard-layout parser adapter
│   │   ├── extract.py              # Main document extraction
│   │   ├── glossary.py             # Korean-English factory glossary
│   │   ├── image_profile.py        # Image-only share measurement
│   │   ├── llm_bridge.py           # LLM bridge abstraction (single chokepoint)
│   │   ├── models.py               # Document data models
│   │   ├── ocr.py                  # OCR cascade (Tesseract→RapidOCR→PaddleOCR→Surya→VLM)
│   │   ├── pptx.py                 # Native PPTX extractor
│   │   ├── prompt_builder.py       # Prompt construction with injection defense
│   │   ├── provenance.py           # Provenance stamping
│   │   ├── rapidocr_adapter.py     # RapidOCR integration
│   │   ├── report_reader.py        # Legacy report reader (LLM bridge, gated)
│   │   ├── run_state.py            # Resumable run state
│   │   ├── search.py               # Document search
│   │   ├── summarize.py            # Chunked map-reduce summarization
│   │   ├── translation_check.py    # Back-translation spot check
│   │   ├── verify.py               # ★ Deterministic figure verifier (Korean-units-aware)
│   │   └── workflow_record.py      # Structured workflow understanding
│   ├── email/                      # Email + attachment intake
│   │   ├── __init__.py
│   │   ├── AGENTS.md
│   │   └── extract.py
│   ├── learning/                   # Feedback, outcomes, gated self-evolution
│   │   ├── __init__.py
│   │   ├── AGENTS.md
│   │   ├── evolution.py            # Gated self-evolution (DSPy/GEPA)
│   │   ├── feedback.py             # Owner feedback loop
│   │   ├── learning.py             # Learning engine core
│   │   └── outcomes.py             # Decision-outcome linkage
│   └── wiki/                       # Durable knowledge artifacts
│       ├── __init__.py
│       ├── AGENTS.md
│       └── artifacts.py            # Git-backed markdown knowledge artifacts
│
├── eval/                           # Golden evaluation set
│   ├── AGENTS.md
│   ├── README.md
│   ├── golden_manifest.json        # 3 fixtures: workflow-record, brief-claims, coverage
│   ├── runner.py                   # Golden eval runner (155 lines)
│   └── fixtures/
│       ├── brief-claims-audit.json
│       ├── extraction-coverage.json
│       └── workflow-record-basic.json
│
├── gov/                            # Governance layer
│   ├── __init__.py
│   ├── access.py                   # Role-scoped access control (G.1)
│   ├── ledger.py                   # External-call append-only ledger (A0.4)
│   └── privacy.py                  # Two-tier privacy gate (A0.4, D14)
│
├── lenses/                         # Department lens configurations (Part F)
│   ├── finance.yaml                # ★ Pilot — Finance / Cost Control
│   └── planning.yaml               # Second department — Planning (config-only, no new code needed)
│
├── mcp_server/                     # MCP tool surface — all capabilities as MCP tools
│   ├── __init__.py
│   └── server.py                   # 701-line dispatch table (Part D tools)
│
├── ops/                            # Operations layer
│   ├── AGENTS.md
│   ├── alerts.py                   # Alerting
│   ├── backup.py                   # Backup/restore
│   ├── scheduler.py                # Scheduled ingestion
│   └── session_state.py            # Session persistence
│
├── research/skills/                # Cloned OSS skill repos for reference (not integrated)
│   ├── RESEARCH_REPORT.md          # Evaluation of top 5 skill repos
│   ├── addyosmani/agent-skills/    # 24 reference skills (MIT)
│   ├── anthropics/skills/          # 17 reference skills (no license)
│   ├── ComposioHQ/awesome-claude-skills/  # 864 reference skills (no license)
│   ├── mattpocock/skills/          # 34 reference skills (MIT)
│   └── obra/superpowers/           # 14 reference skills (MIT)
│
├── schema/
│   └── document.schema.json        # JSON Schema for normalized document output (177 lines)
│
├── serving/                        # Executive output serving
│   ├── __init__.py
│   ├── AGENTS.md
│   ├── card.py                     # One-A4 manager card (177 lines)
│   ├── decision_brief.py           # Decision brief generator
│   ├── meeting_pack.py             # Meeting pack assembler
│   ├── open_design.py              # HTML/PPTX rendering + dashboard
│   ├── report_article.py           # Report/article generator
│   └── signoff.py                  # Named human sign-off enforcement (86 lines)
│
├── shared/                         # Shared contracts and governed metrics
│   ├── __init__.py
│   ├── lenses.py                   # Lens loader (33 lines)
│   ├── contracts/
│   │   ├── __init__.py
│   │   └── models.py               # ★ Data contracts — the system's type spine (162 lines)
│   └── metrics/
│       ├── __init__.py
│       └── registry.py             # Governed metric definitions (24 lines, Part R)
│
├── reports/                        # External reports
│   ├── PLAN_RISK_AUDIT_AND_UPGRADE_REPORT_SUMMARY.md
│   ├── PLAN_RISK_AUDIT_AND_UPGRADE_REPORT.md
│   └── target_report.json
│
└── tests/                          # ★ 55 test files — each tests one module/feature
    ├── __init__.py
    ├── test_brief_audit.py         # Non-numeric brief audit
    ├── test_card_and_audit.py      # Card + audit integration
    ├── test_chunked_summary.py     # Chunked map-reduce coverage
    ├── test_claims.py              # ClaimsStore (A0.1)
    ├── test_contradictions.py      # Contradiction surfacing
    ├── test_data_pipeline.py       # Data engine pipeline
    ├── test_decision_brief.py      # Decision brief generator
    ├── test_docling_adapter.py     # Docling adapter
    ├── test_document_registry.py   # Document registry
    ├── test_documents.py           # Document engine
    ├── test_drivers.py             # Price/volume/mix decomposition
    ├── test_email_extraction.py    # Email intake
    ├── test_executive_signoff.py   # Sign-off enforcement
    ├── test_factory_comparison_gate.py  # Factory comparison gate
    ├── test_factory.py             # Multi-department factory brain
    ├── test_feedback_loop.py       # Owner feedback
    ├── test_gated_evolution.py     # Gated self-evolution
    ├── test_golden_eval.py         # Golden eval runner
    ├── test_hq_deck_brief.py       # HQ deck brief
    ├── test_idea_synthesis.py      # AI-SUGGESTED IDEA synthesis
    ├── test_ingestion_spine.py     # Unified ingestion spine
    ├── test_ir_comparison.py       # Samsung IR comparison
    ├── test_knowledge_artifacts.py # Git-backed artifacts
    ├── test_knowledge_search.py    # Knowledge search
    ├── test_korean_ocr_profile.py  # Korean image-share / OCR
    ├── test_learning.py            # Learning engine
    ├── test_llm_chokepoint.py      # LLM chokepoint + bypass guard (A0.5)
    ├── test_mcp_access.py          # MCP access control
    ├── test_meeting_pack.py        # Meeting pack
    ├── test_memory.py              # Knowledge + temporal memory
    ├── test_nasty_data.py          # Number-safety prevention gate (Sprint 1, 2026-07-03)
    ├── test_ocr_cascade.py         # OCR cascade
    ├── test_ontology.py            # Ontology + edges
    ├── test_open_questions.py      # Open questions + outcomes
    ├── test_ops_backup.py          # Backup/restore
    ├── test_orchestrator.py        # Pipeline orchestrator
    ├── test_pdf_tables.py          # PDF table extraction
    ├── test_pptx_extraction.py     # PPTX extraction (B.1)
    ├── test_privacy.py             # Privacy tier gate (A0.4)
    ├── test_prompt_injection.py    # Prompt injection defense (A0.6)
    ├── test_provenance_stamp.py    # Provenance stamping
    ├── test_query_readiness.py     # Query readiness
    ├── test_report_article.py      # Report/article generator
    ├── test_report_reader.py       # Report reader (A0.7)
    ├── test_resumable_runs.py      # Resumable runs
    ├── test_serving_outputs.py     # Serving outputs
    ├── test_serving.py             # Serving layer + provenance tags (A0.8)
    ├── test_session_state.py       # Session state
    ├── test_skill_contracts.py     # Skill contract linting
    ├── test_translation_check.py   # Translation checks
    ├── test_verify.py              # Figure verifier (A0.2 + A0.3)
    ├── test_workflow_diff.py       # Workflow diff
    ├── test_workflow_family.py     # Workflow families
    └── test_workflow_record.py     # Workflow records
```

---

## 3. Architecture Overview

### 3.1 The Core Principle

The system is a **skill library** (not a monolithic app). From `assistant_master_plan.md:35-48`:

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent (any model)                   │
│                                                          │
│   reads: AGENT_SKILL_MAP.md → tiny, finds routing        │
│   loads: one skill file → small, gets exact instructions │
│   calls: MCP tools → cheap, deterministic engine calls    │
│                                                          │
│   NEVER loads the whole architecture on one task          │
└──────────────────────────────────────────────────────────┘
```

Three layers:
1. **Skills** — `agent_skills/*.md` — small single-purpose capability documents
2. **Tools** — deterministic engines behind each skill, exposed via MCP server
3. **Map** — `AGENT_SKILL_MAP.md` — tells any agent which skill to load for which task

### 3.2 The Three Non-Negotiables

| Rule | Meaning | Enforcement |
|---|---|---|
| **Golden Rule** | Code writes code from samples; engines execute against volumes. AI never reads raw data — reads profiles and writes code your machine runs. | Every engine operates on metadata/samples; no raw data in prompts |
| **Calculation-Integrity Rule** | Every number comes from a SQL query. A synthesis model may NEVER originate a number. | `shared/contracts/models.py` — `NumberFact` requires `EvidenceRef`; provenance tags (`AUDITED-FROM-QUERY` vs `CLAIMED-FROM-DECK`) |
| **Decision-Memory Rule** | Every useful output is stored (fact/driver/risk/recommendation/decision/action/lesson) **with evidence**. | `engines/brain/claims.py` — claims physically separate; `engines/learning/` — outcome linkage |

### 3.3 The 7-Layer Tool Stack (Part K.1)

| Layer | Tool | Status |
|---|---|---|
| Read files | Docling, PyMuPDF, OpenPyXL | Native + adapter stubs |
| Clean/analyze | **Polars, DuckDB** | **Real — the only path numbers travel** |
| Knowledge memory | Cognee (Kuzu+LanceDB) | Adapter stubbed |
| Temporal memory | Graphiti (Kuzu/FalkorDB) | Adapter stubbed |
| Enterprise search | Onyx | Future v2-v3 |
| Output/design | Open Design | **Real — HTML + PPTX** |
| Orchestration | Hermes (pattern) | Via `orchestrator.py` |

### 3.4 The 6 Processing Engines

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  data/       │     │  docs/       │     │  email/      │     │  brain/      │
│  ★ Numbers   │     │  PDF/PPTX    │     │  .eml+att.   │     │  Memory      │
│  DuckDB       │     │  OCR cascade │     │  extraction   │     │  Claims      │
│  Polars       │     │  Summarize   │     │              │     │  Registry    │
│  Clean/Var.   │     │  Verify      │     │              │     │  Search      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │                    │
       └────────────────────┼─────────────────────┼────────────────────┘
                            │                     │
                    ┌───────▼───────┐     ┌───────▼───────┐
                    │  audit/       │     │  learning/    │
                    │  Independent  │     │  Feedback     │
                    │  re-check     │     │  Outcomes     │
                    │  Sign-off     │     │  Evolution    │
                    └───────┬───────┘     └───────┬───────┘
                            │                     │
                    ┌───────▼─────────────────────▼───────┐
                    │           serving/ + mcp_server/     │
                    │  Card, Briefs, Packs, Reports, MCP   │
                    └─────────────────────────────────────┘
```

---

## 4. Module-by-Module Deep Dive

### 4.1 `engines/data/` — The Numeric Trust Core

**Purpose:** The ONLY source of trusted numbers in the system. Every number released to an
executive originates from a DuckDB/SQL query or Polars computation in this engine.

| File | Purpose |
|---|---|
| `ingest.py` | Unified ingestion spine: CSV/Excel/PDF-table → DuckDB with row rejection + conservation checks |
| `clean.py` | The single canonical number parser (`parse_amount`) plus row cleaning: detect/exclude embedded total/subtotal rows, config-driven duplicate detection, locale amount parsing (incl. SAP `(1,234.56)`/`1234.56-` negatives). `clean_actuals` and `clean_standards` share one core (`_clean_rows`) — both actuals AND standards get the same defenses, and an optional `qty_col` quarantines bad quantities instead of letting them through |
| `variance.py` | Governed variance computation: actual − budget per dimension, with reconciliation check. `price_volume_mix` requires pre-cleaned input and raises loudly if a null qty/amount slips through, instead of silently coercing it to 0 |
| `drivers.py` | Price/volume/mix decomposition: explains WHY a variance happened (rate × scale × proportion). Cleans BOTH actuals and standards before decomposing; returns `actuals_rejects`/`standards_rejects` separately so neither source's rejects can go unnoticed |
| `types.py` | Per-column type inference: typed values alongside raw text, unconvertible → quarantine |
| `pdf_tables.py` | PDF table extraction into the ingestion spine |
| `query_readiness.py` | Cross-source query readiness verification |

**Invariants:**

- Every row rejected goes to a `rejects.csv` (nothing vanishes) — this now covers standards, not just actuals
- Variance bridge must reconcile to within 0.01 tolerance
- Price + volume + mix must sum to total variance (or decomposition is wrong)
- All processing is deterministic — zero LLM calls in this engine
- (Sprint 1, 2026-07-03) A data-integrity review found and fixed: junk quantities silently
  becoming 0, standards loaded uncleaned, a hardcoded duplicate-key that could false-collide
  on lenses missing certain columns, and an OCR quality score that scored number-dense pages
  as 0. See `tests/test_nasty_data.py` for the regression tests that guard against recurrence.

### 4.2 `engines/docs/` — Document Intelligence

**Purpose:** Ingest and understand PDFs, PowerPoint decks, Word docs, and scanned images.
Extract evidence, run OCR, summarize, verify figures, build workflow understanding.

| File | Purpose |
|---|---|
| `extract.py` | Main document extraction dispatcher |
| `pptx.py` | Native PPTX extractor (thin deterministic path, slide-by-slide) |
| `docling_adapter.py` | Docling hard-layout parser (opt-in for difficult layouts) |
| `ocr.py` | OCR cascade: Tesseract → RapidOCR → PaddleOCR → Surya → VLM |
| `rapidocr_adapter.py` | RapidOCR integration (best balance of speed/accuracy) |
| `image_profile.py` | Image-only slide share measurement (determine OCR load) |
| `verify.py` | Deterministic figure verifier: Korean-unit-aware (억/만/천), citation-support check |
| `summarize.py` | Chunked map-reduce summarization with per-chunk coverage accounting |
| `workflow_record.py` | Structured workflow understanding from decks/documents |
| `glossary.py` | Korean-English factory glossary and critical-term check |
| `translation_check.py` | Back-translation spot check for translated content |
| `provenance.py` | Provenance stamping on every extracted artifact |
| `prompt_builder.py` | Prompt construction with delimiter-based injection defense |
| `llm_bridge.py` | Single LLM chokepoint — all LLM calls go through here |
| `report_reader.py` | Legacy report reader (gated through the chokepoint) |
| `run_state.py` | Resumable run state for long operations |
| `models.py` | Document data models |
| `search.py` | Document search |

**OCR Cascade Logic:**
```
Try Tesseract → confidence >= threshold? → done
     ↓ no
Try RapidOCR → confidence >= threshold? → done
     ↓ no
Try PaddleOCR → confidence >= threshold? → done
     ↓ no
Try Surya → confidence >= threshold? → done
     ↓ no
Route to VLM (last resort) → always confidence-scored
Any result below threshold → HUMAN-REVIEW QUEUE (never silently trusted)
```

### 4.3 `engines/brain/` — Memory, Knowledge, and Orchestration

**Purpose:** The central nervous system. Manages claims, memory, document registry,
knowledge search, ontology, orchestrates the full pipeline.

| File | Purpose |
|---|---|
| `orchestrator.py` | Full pipeline orchestrator — coordinates all engines |
| `memory.py` | Knowledge + temporal memory (local JSON with Cognee/Graphiti adapter stubs) |
| `claims.py` | ClaimsStore — physically separate from facts (`.brain/claims.json`) |
| `registry.py` | Document registry — indexes all ingested documents |
| `workflow_family.py` | Workflow families + versioning (valid-time + ingest-time) |
| `workflow_diff.py` | Version diff view for workflow records |
| `search.py` | Knowledge search across stored claims/memories/registries |
| `ontology.py` | Canonical entity IDs for consistent cross-referencing |
| `edges.py` | Typed cross-workflow edges |
| `contradictions.py` | Contradiction surfacing across claims and records |
| `comparison.py` | IR quarter + factory comparison |
| `factory.py` | Multi-department factory brain (configured via lenses) |
| `open_questions.py` | Queryable open questions attached to workflow records |
| `idea_synthesis.py` | Labeled AI-SUGGESTED IDEA synthesis (always labeled, never disguised as fact) |

**Claims vs Facts (Critical Architectural Decision):**
- **Facts** — numbers from SQL queries via `engines/data/` (stored in DuckDB/knowledge store)
- **Claims** — statements from documents/decks that might be true (stored separately in `.brain/claims.json`)
- A claim can BECOME a fact only when verified against a trusted data source
- This physical separation prevents the catastrophic failure mode

### 4.4 `engines/audit/` — Trust and Verification Layer

**Purpose:** Independent re-run, certainty scoring, and human sign-off enforcement.

| File | Purpose |
|---|---|
| `audit.py` | Numeric audit: independent re-run of all calculations, certainty scoring, deep multiple-choice questions |
| `brief_audit.py` | Non-numeric brief claim audit (Part B.6) |

**Audit flow:**
```
1. Independent re-run all calculations from raw data
2. Compare results with original — must match within recompute_tolerance (0.01)
3. Score certainty per dimension + overall (threshold: 0.80)
4. If certainty < 0.80 → generate deep multiple-choice questions for human
5. If rejects > 5% or rejected $ > 2% → escalate
6. Human must sign off (named, with certainty at approval recorded)
```

### 4.5 `engines/learning/` — Improvement Loop

**Purpose:** Capture feedback, link decisions to outcomes, gate self-evolution.

| File | Purpose |
|---|---|
| `learning.py` | Learning engine core |
| `feedback.py` | Owner feedback capture and trust-loop hooks |
| `outcomes.py` | Decision-outcome linkage |
| `evolution.py` | Gated self-evolution (DSPy/GEPA) — only runs on golden eval set |

### 4.6 `engines/email/` and `engines/wiki/`

| Module | Purpose |
|---|---|
| `engines/email/` | Parse `.eml` messages, preserve metadata, route attachments into document spine |
| `engines/wiki/` | Deterministic markdown artifacts stored in git with dedup and provenance |

### 4.7 `serving/` — Executive Output

| File | Purpose |
|---|---|
| `card.py` | One-A4 manager card generator — BLUF + 5 key numbers + drivers + risks + actions + confidence |
| `decision_brief.py` | One-page decision brief generator |
| `meeting_pack.py` | Meeting pack assembler (multiple briefs + cards) |
| `report_article.py` | Report/article generator |
| `open_design.py` | HTML dashboard + PPTX export |
| `signoff.py` | Named human sign-off enforcement |

**Card validation (from `shared/contracts/models.py`):**
- Every key number MUST carry a resolving `EvidenceRef`
- Max 5 key numbers (one-A4 budget)
- Max 3 drivers, max 5 actions
- Driver numbers also require evidence
- All rendered numbers carry provenance tags: `AUDITED-FROM-QUERY` or `CLAIMED-FROM-DECK`

### 4.8 `shared/contracts/` — Typed Data Contracts

**`models.py`** defines the system's type spine — all the shared dataclasses:

| Contract | Purpose |
|---|---|
| `EvidenceRef` | Where a number/quote came from (source + locator + method). MUST be present before any fact is shown. |
| `RejectRecord` | A rejected row with reason and raw data |
| `NumberFact` | A number with evidence and auto-computed provenance tag |
| `VariancePart` | One dimension's actual/budget/variance |
| `VarianceBridge` | Total variance + parts + reconciliation check |
| `DriverPart` | Price/volume/mix breakdown for one item |
| `VarianceDecomposition` | Why variance happened (P+V+M must sum to total) |
| `DriverSplit` | Compact management summary of drivers |
| `ManagerCard` | One-A4 card — headline, numbers, drivers, risks, actions, confidence, evidence |
| `AuditResult` | Pass/fail, certainty, issues, questions, recomputed values |
| `SignOff` | Named human approval with certainty at time of approval |

### 4.9 `gov/` — Governance Layer

| File | Purpose |
|---|---|
| `access.py` | Role-scoped access control (cfo/analyst/planner/ceo) |
| `privacy.py` | Two-tier privacy gate: Tier 1 = in-house only (default), Tier 2 = external with ledger |
| `ledger.py` | External-call append-only ledger — every external API call is logged immutably |

### 4.10 `mcp_server/` — MCP Tool Surface

`server.py` (701 lines) exposes every engine capability as an MCP tool. The dispatch table
routes tool calls to the correct engine function. Part D of the plan.

### 4.11 `lenses/` — Department Configuration

```yaml
# lenses/finance.yaml — the pilot
department: finance
data_sources: [budget, actuals, standards]
metrics: [cost, variance, drivers]
roles: [cfo, analyst]

# lenses/planning.yaml — second department (config only)
department: planning
data_sources: [plan, actuals]
metrics: [schedule, resource]
```

### 4.12 `ops/` — Operations

Scheduled ingestion (`scheduler.py`), backup/restore (`backup.py`), alerting
(`alerts.py`), session persistence (`session_state.py`).

---

## 5. The Phase Plan

### 5.1 Phase Overview

| Phase | Name | Status | Key Deliverables |
|---|---|---|---|
| **A0** | Safety Rails | **ALL PASSED** | Claims store (A0.1), figure verifier (A0.2), citation support (A0.3), privacy gate (A0.4), LLM chokepoint (A0.5), injection defense (A0.6), report reader repair (A0.7), provenance tags (A0.8) |
| **A1** | Janitorial | **PASSED** | Archive stale docs (A1.1), update routing docs (A1.2) |
| **B** | First HQ Deck E2E | **ALL PASSED** | PPTX extractor (B.1), summarization (B.2), workflow records (B.3), provenance (B.4), glossary (B.5), brief audit (B.6), Korean OCR (B.7), email (B.8), HQ deck brief (B.9), Docling adapter (B.10) |
| **C** | Corpus/Registry/Comparison | **ALL PASSED** | Registry (C.1), families/versioning (C.2), diffs (C.3), open questions (C.4), knowledge artifacts (C.5), IR comparison (C.6), contradictions (C.7), knowledge search (C.8) |
| **D** | Executive Interface | **ALL PASSED** | Decision briefs (D.1), meeting packs (D.2), reports/articles (D.3), sign-off (D.4), rendering (D.5), feedback (D.6) |
| **E** | Real Factory Data | **BLOCKED** | Real export profiling (E.1 — blocked on external data), multi-sheet Excel (E.2), type inference (E.3), issue promotion (E.4) |
| **F** | Scale-Up | **ALL PASSED** | Golden eval (F.1), MCP access (F.2), skill budgets (F.3), resumable runs (F.4), ontology (F.5), factory comparison (F.6), idea synthesis (F.7), scheduled ops (F.8), session state (F.9), quarterly review (F.10) |
| **T12** | Self-Evolution | **PASSED** | Gated self-evolution on golden eval set |

### 5.2 Build Order Dependencies

```
A0 (safety rails) ────┬──→ B (deck E2E) ──→ C (corpus) ──→ D (executive) ──→ F (scale-up)
                       │
                       └──→ E (real data) ── blocked on external SAP export
```

All non-blocked cards through F.10 are **Passed**. E.1 is **Blocked** on external data.

### 5.3 Full Task Queue (from `00_control/task_queue.md`)

The task queue has 87 rows tracking every card from T0 through F.10. Each row has:
- ID, task description, assigned role, status, priority
- Inputs, outputs, validation method
- Evidence reference (test pass / demo / doc review)

**Next best action:** Wait for the first real SAP-scale export (P2.2 / E.1).

---

## 6. Data Flow

### 6.1 Numeric Data Path (the Trust Loop)

```
CSV/Excel/PDF Table
     │
     ▼
engines/data/ingest.py ───→ DuckDB table
     │                          │
     ├── Reject totals/dupes    │
     ├── Parse locale amounts   │
     └── Type inference         │
                                ▼
                    engines/data/clean.py
                                │
                                ▼
                    engines/data/variance.py
                                │
                                ├── VarianceBridge
                                └── VarianceDecomposition (price/volume/mix)
                                          │
                                          ▼
                              engines/audit/audit.py
                              Independent re-run + certainty scoring
                                          │
                               ┌──────────┤
                               ▼          ▼
                         AuditResult    ManagerCard (via serving/card.py)
                               │          │
                               └──────────┘
                                     │
                                     ▼
                               serving/signoff.py
                               Named human sign-off
                                     │
                                     ▼
                               rendered HTML/PPTX
                               (every number tagged AUDITED-FROM-QUERY)
```

### 6.2 Document/Evidence Path

```
PDF/PPTX/Email/Scan
     │
     ▼
engines/docs/extract.py ───→ Text + metadata
     │
     ├── PPTX → native path (pptx.py)
     ├── Scan → OCR cascade (ocr.py)
     ├── Hard layout → Docling (docling_adapter.py)
     │
     ▼
engines/docs/workflow_record.py ───→ Structured workflow understanding
     │
     ├── enges/docs/summarize.py → coverage-tracked summary
     ├── engines/docs/verify.py → deterministic figure verification
     ├── engines/docs/provenance.py → provenance stamping
     │
     ▼
engines/brain/registry.py ───→ Document registered
     │
     ├── claims extracted → claims.py (CLAIMED-FROM-DECK)
     ├── workflow families → workflow_family.py
     ├── open questions → open_questions.py
     └── knowledge search index → search.py
```

---

## 7. Agent System (How AI Agents Work Here)

### 7.1 The Agent Read Order

**Canonical list lives in `AGENTS.md` → "Read order (start here, always)".** This
file does not keep its own copy — that duplication is exactly what let four routing
docs (`AGENTS.md`, `AGENT_SKILL_MAP.md`, `PROJECT_MAP.md`, `CLAUDE.md`) disagree with
each other until it was reconciled. In short, the order is:

```
1. AGENTS.md                     — root operating manual (read order, rules, commands)
2. PROJECT_MAP.md                — ★ this file — full project overview
3. AGENT_SKILL_MAP.md            — routing: which skill for which task
4. AGENT_CORE_CONTRACT.md        — shared contract (run identity, evidence, trust)
5. 03_design/current_implementation_plan.md  — live execution plan (when build order/gates matter)
6. 03_design/assistant_master_plan.md  — architecture context (only when needed)
7. 03_design/phase_a_cards.md    — when working Phase A
8. Relevant skill file(s) only   — e.g., agent_skills/spreadsheet_ingestion.md
9. Nearest module AGENTS.md      — e.g., engines/data/AGENTS.md
```

**NEVER load every skill or every document by default.** Load only what the task needs.

### 7.2 The 6 Skill Files

| Skill File | When to Load | Key MCP Tools |
|---|---|---|
| `spreadsheet_ingestion.md` | Task starts from Excel/CSV/SAP exports | `profile_spreadsheet`, `ingest_spreadsheet` |
| `document_evidence_extraction.md` | Task starts from PDF/PPTX/Word/Scans | `ingest_document`, `ingest_deck`, `search_documents` |
| `cost_variance_analysis.md` | Task asks why cost changed | `query_numbers`, `decompose_variance` |
| `management_reporting.md` | Task needs executive output | `render_card`, `render_brief`, `render_pack` |
| `knowledge_search.md` | Task needs retrieval from stored knowledge | `search_knowledge`, `query_open_questions` |
| `audit_and_trust.md` | Task needs verification/release gating | `audit_numbers`, `audit_claims`, `sign_off` |

**External skill libraries:** The project also keeps a curated inventory of
external skill libraries from `C:\Users\mflma\Downloads\Skills` in
`agent_skills/EXTERNAL_SKILLS_INVENTORY.md`. Use it when you want to borrow
patterns from Addy Osmani agent skills, Anthropic skills, or financial-services
skills without duplicating them.

### 7.3 Agent Skill Composition Patterns

From `AGENT_SKILL_MAP.md`:

| Pattern | Use Case |
|---|---|
| **A — Singe skill, direct** | Task matches exactly one skill |
| **B — Spreadsheet → Variance** | Ingest data, then analyze variance |
| **C — Document → Record** | Ingest deck, then build workflow record |
| **D — Document → Search** | Ingest document, then add to knowledge |
| **E — Analyze → Report** | Run numbers, then render executive output |
| **F — Audit after any numeric path** | Always audit before release |
| **G — Full decision cycle** | Ingest → Analyze → Audit → Report → Sign-off |

### 7.4 Agent Core Contract (from `AGENT_CORE_CONTRACT.md`)

Every skill must use the same:
- **Run identity:** `run_id`, `task_id`, `source_type`, `source_path`, timestamps, status
- **Source identity:** original path, sheet/page/slide, row index, extraction method
- **Evidence identity:** source location, calculation method, confidence level
- **Storage targets:** consistent naming and locations
- **Failure semantics:** success, partial, blocked, failed, needs-human
- **Confidence levels:** High (≥0.90), Medium (≥0.70), Low (<0.70)
- **Priority order:** trust > restartability > evidence

---

## 8. Test Suite Map

### 8.1 How Tests Are Organized

55 test files in `tests/`, one file per module/feature. Run with:
```
pytest                          # entire suite
pytest tests/<module>.py       # specific test
```

### 8.2 Test Categories

| Category | Test Files | What They Verify |
|---|---|---|
| **Safety Rails (A0)** | test_claims, test_verify, test_privacy, test_llm_chokepoint, test_prompt_injection, test_report_reader, test_serving | Physical claims separation, Korean-unit verifier, privacy gate, single chokepoint, injection defense, provenance tags |
| **Data Engine** | test_data_pipeline, test_ingestion_spine, test_pdf_tables, test_query_readiness, test_drivers | Ingestion, cleaning, variance, type inference, price/volume/mix |
| **Document Engine** | test_documents, test_pptx_extraction, test_chunked_summary, test_docling_adapter, test_korean_ocr_profile, test_workflow_record, test_provenance_stamp, test_translation_check, test_email_extraction | Extraction, OCR, summaries, workflow records, provenance |
| **Brain/Memory** | test_orchestrator, test_memory, test_claims, test_document_registry, test_workflow_family, test_workflow_diff, test_open_questions, test_contradictions, test_ir_comparison, test_ontology, test_idea_synthesis, test_knowledge_search, test_knowledge_artifacts, test_factory_comparison_gate, test_factory | Pipeline orchestration, memory, registry, families, diffs, search, contradictions, ontology |
| **Serving** | test_card_and_audit, test_decision_brief, test_meeting_pack, test_report_article, test_hq_deck_brief, test_executive_signoff, test_serving_outputs | Card generation, briefs, packs, reports, sign-off, rendering |
| **Audit** | test_brief_audit, test_card_and_audit | Numeric + non-numeric audit, certainty scoring |
| **Learning** | test_learning, test_feedback_loop, test_gated_evolution | Feedback, outcomes, self-evolution |
| **Ops/Eval** | test_ops_backup, test_session_state, test_golden_eval, test_mcp_access, test_skill_contracts, test_resumable_runs | Backup, sessions, golden eval, MCP access, skill linting |

### 8.3 CI Pipeline (`.github/workflows/ci.yml`)

```
push to main → checkout → Python 3.11 → install tesseract-ocr
→ pip install → ruff check → pytest → all must pass
```

---

## 9. Configuration Reference

### 9.1 `config.yaml`

```yaml
ai:
  synthesis:    { provider: local, model: qwen-on-prem }    # In-house LLM
  embeddings:   { provider: local, model: bge-local }      # In-house embeddings

active_lens: finance               # Pilot department

roles:
  cfo:      { scope: finance:* }   # Full finance access
  analyst:  { scope: finance:costing }  # Costing only
  planner:  { scope: planning }    # Planning department
  ceo:      { scope: * }           # Everything

audit:
  certainty_release_threshold: 0.80    # Below → mandatory human questions
  reject_count_warn_ratio: 0.05        # >5% rejects → warn
  materiality_warn_ratio: 0.02         # >2% rejected $ → escalate
  recompute_tolerance: 0.01            # Independent re-run must match

tools:
  document_extractor: plaintext        # → docling when installed
  ocr_cascade: [tesseract, rapidocr, paddleocr, surya, vlm]
  ocr_quality_threshold: 0.5
  knowledge_memory: local_json         # → cognee when installed
  temporal_memory: local_json          # → graphiti when installed
  renderer: builtin_html               # → open_design when installed
```

### 9.2 `pyproject.toml`

```toml
[project]
name = "factory-brain"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
exclude = ["research", ".venv", "archive"]
select = ["E", "F", "I", "UP", "B"]
```

### 9.3 `requirements.txt`

```
duckdb, polars, pyarrow, openpyxl, pypdf, pymupdf,
pytesseract, pillow, pyyaml, pytest, ruff
```

---

## 10. Project State Summary

### What is built and running:
- Full numeric trust loop: ingest → clean → governed variance → cited manager card
- Independent audit layer: four-eyes re-run, certainty scoring, deep multiple-choice questions
- Named human sign-off enforcement
- Knowledge + temporal memory (local JSON + Cognee/Graphiti adapter stubs)
- Document engine: text PDF, PPTX extraction, OCR cascade (Tesseract + RapidOCR real)
- Chunked map-reduce summarization with coverage accounting
- Workflow records with provenance, glossary, translation checks
- Document registry, workflow families/versioning, diffs
- Open questions, contradictions, knowledge search
- Decision briefs, meeting packs, report/article generators
- Multi-department factory brain by configuration (Finance + Planning)
- HTML dashboard + PPTX export
- Golden evaluation set
- MCP access control, backup/restore, session persistence
- All 6 agent skills fully documented
- All 87 task queue rows through F.10 and T12: **Passed**

### What is blocked:
- **P2.2 / E.1** — waiting on the first real SAP export from the factory (external dependency)

### What is explicitly NOT built yet:
- Onyx enterprise search (future v2-v3)
- Production deployment with real Ollama/vLLM serving
- Real Cognee/Graphiti backend (adapters exist, stubbed to local JSON)

### Key architectural wins (designed against catastrophic failure):
1. **Physical separation of facts vs claims** — claims go to `.brain/claims.json`, never to knowledge/temporal stores
2. **Deterministic figure verifier** understands Korean units (억/만/천) — no LLM in the verification path
3. **Privacy tier gate** — Tier 1 defaults to in-house only
4. **Single LLM chokepoint** — all LLM calls pass through one function
5. **Prompt injection defense** — delimiter wrapping on all user/source text
6. **Every rendered number carries a provenance tag** — `AUDITED-FROM-QUERY` or `CLAIMED-FROM-DECK`
7. **No number originates from generation** — all numbers come from SQL/Polars queries

---

## 11. Quick Reference for Common Operations

```
# Install dependencies
pip install -r requirements.txt

# Run all tests (definition of done)
pytest

# Run one specific test
pytest tests/test_claims.py

# Lint and format
ruff check .
ruff format .

# Run end-to-end demo
python run_demo.py

# CI check (what the CI runs)
ruff check . && pytest
```

**Git policy (strict):** Single `main` branch only. No branches. No force-push. Commit
only when tests pass. Push to `main`.

---

## 12. File Index (Every Python File)

| File Path | Module | Lines | Purpose |
|---|---|---|---|
| `shared/contracts/models.py` | Contracts | 162 | Typed data contracts (EvidenceRef, NumberFact, VarianceBridge, ManagerCard, AuditResult, SignOff) |
| `shared/metrics/registry.py` | Metrics | 24 | Governed metric definitions |
| `shared/lenses.py` | Config | 33 | Lens loader |
| `engines/data/ingest.py` | Data | — | CSV/Excel/PDF table ingestion spine |
| `engines/data/clean.py` | Data | — | Canonical number parser + row cleaning (totals, config-driven dupes, locale/negative amounts, qty quarantine) |
| `engines/data/variance.py` | Data | — | Governed variance computation; raises on unclean input instead of silently zeroing |
| `engines/data/drivers.py` | Data | — | Price/volume/mix decomposition |
| `engines/data/types.py` | Data | — | Column type inference |
| `engines/data/pdf_tables.py` | Data | — | PDF table extraction |
| `engines/data/query_readiness.py` | Data | — | Cross-source query readiness |
| `engines/docs/extract.py` | Docs | — | Main document extraction |
| `engines/docs/pptx.py` | Docs | — | Native PPTX extractor |
| `engines/docs/summarize.py` | Docs | — | Chunked map-reduce summarization |
| `engines/docs/verify.py` | Docs | — | Deterministic figure verifier |
| `engines/docs/ocr.py` | Docs | — | OCR cascade |
| `engines/docs/rapidocr_adapter.py` | Docs | — | RapidOCR integration |
| `engines/docs/docling_adapter.py` | Docs | — | Docling hard-layout parser |
| `engines/docs/image_profile.py` | Docs | — | Image-only share measurement |
| `engines/docs/workflow_record.py` | Docs | — | Structured workflow understanding |
| `engines/docs/provenance.py` | Docs | — | Provenance stamping |
| `engines/docs/glossary.py` | Docs | — | Korean-English factory glossary |
| `engines/docs/translation_check.py` | Docs | — | Back-translation spot check |
| `engines/docs/prompt_builder.py` | Docs | — | Prompt construction + injection defense |
| `engines/docs/llm_bridge.py` | Docs | — | Single LLM chokepoint |
| `engines/docs/report_reader.py` | Docs | — | Legacy report reader |
| `engines/docs/run_state.py` | Docs | — | Resumable run state |
| `engines/docs/search.py` | Docs | — | Document search |
| `engines/docs/models.py` | Docs | — | Document data models |
| `engines/email/extract.py` | Email | — | Email + attachment intake |
| `engines/brain/orchestrator.py` | Brain | — | Full pipeline orchestrator |
| `engines/brain/memory.py` | Brain | — | Knowledge + temporal memory |
| `engines/brain/claims.py` | Brain | — | ClaimsStore |
| `engines/brain/registry.py` | Brain | — | Document registry |
| `engines/brain/workflow_family.py` | Brain | — | Workflow families + versioning |
| `engines/brain/workflow_diff.py` | Brain | — | Workflow diff view |
| `engines/brain/search.py` | Brain | — | Knowledge search |
| `engines/brain/ontology.py` | Brain | — | Canonical entity IDs |
| `engines/brain/edges.py` | Brain | — | Typed cross-workflow edges |
| `engines/brain/contradictions.py` | Brain | — | Contradiction surfacing |
| `engines/brain/comparison.py` | Brain | — | IR quarter + factory comparison |
| `engines/brain/factory.py` | Brain | — | Multi-department factory brain |
| `engines/brain/open_questions.py` | Brain | — | Queryable open questions |
| `engines/brain/idea_synthesis.py` | Brain | — | Labeled AI-SUGGESTED IDEA |
| `engines/audit/audit.py` | Audit | — | Independent audit + sign-off |
| `engines/audit/brief_audit.py` | Audit | — | Non-numeric brief claim audit |
| `engines/learning/learning.py` | Learning | — | Learning engine core |
| `engines/learning/feedback.py` | Learning | — | Owner feedback loop |
| `engines/learning/outcomes.py` | Learning | — | Decision-outcome linkage |
| `engines/learning/evolution.py` | Learning | — | Gated self-evolution |
| `engines/wiki/artifacts.py` | Wiki | — | Git-backed knowledge artifacts |
| `serving/card.py` | Serving | 177 | One-A4 manager card |
| `serving/decision_brief.py` | Serving | — | Decision brief generator |
| `serving/meeting_pack.py` | Serving | — | Meeting pack assembler |
| `serving/report_article.py` | Serving | — | Report/article generator |
| `serving/open_design.py` | Serving | — | HTML/PPTX rendering + dashboard |
| `serving/signoff.py` | Serving | 86 | Named human sign-off enforcement |
| `mcp_server/server.py` | MCP | 701 | MCP tool dispatch table |
| `gov/access.py` | Gov | — | Role-scoped access control |
| `gov/privacy.py` | Gov | — | Two-tier privacy gate |
| `gov/ledger.py` | Gov | — | External-call append-only ledger |
| `ops/scheduler.py` | Ops | — | Scheduled ingestion |
| `ops/backup.py` | Ops | — | Backup/restore |
| `ops/alerts.py` | Ops | — | Alerting |
| `ops/session_state.py` | Ops | — | Session persistence |
| `eval/runner.py` | Eval | 155 | Golden eval runner |
| `run_demo.py` | Demo | — | End-to-end demo script |

---

*End of PROJECT_MAP.md — this file is maintained for AI agent onboarding. Update it when
the architecture or module structure changes significantly.*
