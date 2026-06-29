# Factory Second Brain — Project Overview

> The readable front door. Deep detail lives in `MASTER_PLAN.md` (architecture),
> `RISK_AND_GAPS_AUDIT.md` (risks), and `BUILD.md` (the working code). This document
> answers the 15 core questions in plain, professional language.

**What is already real (not a plan):** the numeric trust loop runs today — `python
run_demo.py` ingests messy finance data, cleans it, computes a cited variance, **audits it
independently**, asks the human when unsure, and releases only after sign-off. 9 tests
pass. Everything below builds outward from that proven core.

---

## 1. The project in simple, professional language

The Factory Second Brain is an **operational AI brain for a factory.** It reads the
factory's files (Excel, PDF, Word, PowerPoint, scans, emails), turns the mess into clean
structured knowledge, **remembers** the facts, the relationships between them, and **how
they changed over time**, then answers questions, explains problems, recommends actions,
and presents the answer as a one-page card, dashboard, or deck.

It is **not** a chatbot, a file store, or a dashboard. It is a **decision-support system**.
Its defining rule: **the AI never invents a number.** Numbers come from calculation;
text understanding may use AI; every claim cites its source; nothing reaches a manager
until it has been **independently audited and signed off by a named human.** Because in a
factory, the dangerous failure is not a crash — it is a *confident wrong number* reaching
the CEO.

It is **local-first** (data stays in-house) and grows **one department at a time.**

---

## 2. Architecture (text diagram)

```
                         HERMES (orchestrator agent)
                   plans · calls tools · asks the human · coordinates
                                     │  via MCP (safe tool calls)
   ┌─────────────────────────────────────────────────────────────────────┐
   │  1 INGEST      files → folders / Excel / PDF / scans / emails         │
   │  2 EXTRACT     Docling · PyMuPDF/pypdf · OCR · OpenPyXL                │
   │  3 CLEAN       Polars  (names, dates, missing, noise, locale)         │
   │  4 ANALYZE     DuckDB  (SQL: variance, trends, aggregates) ← NUMBERS  │
   │  5 KNOW        Cognee  (entities + relationships)                     │
   │  6 REMEMBER    Graphiti (what changed, when, why, proven by what)     │
   │  7 REASON      Hermes  (answer · explain · recommend)                 │
   │  ── AUDIT ──   independent re-run + certainty + ASK HUMAN + SIGN-OFF  │ ★
   │  8 SEARCH      Onyx    (enterprise search — later, many departments)  │
   │  9 PRESENT     Open Design (dashboard / HTML / PDF / PPTX)            │
   └─────────────────────────────────────────────────────────────────────┘
        RAW (immutable)  →  VAULT (Markdown, source of truth)  →  indexes (rebuildable)
```

★ The audit + human sign-off step is the spine of trust. It is not optional.

---

## 3. Each tool's role

| Tool | Role |
|---|---|
| **Hermes** | Orchestrator: plans the task, calls tools, reads results, asks follow-up questions, coordinates the whole flow. |
| **Docling** | Primary extractor for PDF / Word / PowerPoint — text, tables, layout, reading order. |
| **PyMuPDF / pypdf / OCR** | Fallback for scanned PDFs, images, hard files. OCR is offline (PaddleOCR, EN+AR). |
| **OpenPyXL** | Reads Excel safely (streaming, no out-of-memory on big SAP exports). |
| **Polars** | Cleans and transforms large tables fast (columns, dates, missing values, locale numbers). |
| **DuckDB** | The analytical engine — SQL over the numbers: variances, trends, aggregations. **The only source of numbers.** |
| **Cognee** | Knowledge memory — turns extracted facts into connected entities and relationships. |
| **Graphiti** | Temporal memory — tracks how facts/relationships/costs/suppliers/decisions change over time. |
| **Onyx** | Enterprise search across many departments and documents — added later, when scale demands. |
| **Open Design** | Visual output — dashboards, HTML/PDF reports, PPTX-style presentations. Output only. |
| **MCP** | The safe, consistent connection layer between the agent and every tool. |

---

## 4. Data flow — from file to decision

```
file → extract → clean → analyze (numbers) ─┐
                                            ├→ draft answer (card) → AUDIT → human sign-off → PRESENT → DECISION
        facts → knowledge graph + temporal ─┘                         │
                                                          (re-run · certainty · ask if unsure)
                          every step writes evidence: rejects.csv · run.log · source refs
```

1. **Ingest** a file. 2. **Extract** text/tables. 3. **Clean** (Polars). 4. **Analyze** in
DuckDB → numbers with evidence. 5. Store **relationships** in Cognee. 6. Store **history**
in Graphiti. 7. Hermes **drafts** the answer/card. 8. The **audit** independently re-checks
it and asks the human if unsure. 9. A human **signs off** (accountability). 10. Open Design
**presents** it. The output is a *decision*, not a report.

---

## 5. Memory architecture (four kinds of memory)

| Memory | Holds | Backed by |
|---|---|---|
| **Semantic** (facts) | governed numbers + definitions | DuckDB + the Markdown vault |
| **Relational** (knowledge) | entities & relationships (product ↔ cost center ↔ supplier ↔ PO ↔ variance) | **Cognee** |
| **Temporal** (history) | how a fact/relationship changed, when, why, proven by what | **Graphiti** |
| **Procedural** (skills) + **Episodic** (decisions) | reusable methods learned from work; past decisions, owners, outcomes, lessons | learning store + decision memory |

**The golden rule of memory:** the **Markdown vault is the source of truth** (immutable raw
+ AI-maintained wiki). Cognee / Graphiti / search indexes are **disposable and
rebuildable** from the vault. Knowledge never lives *only* inside a graph database.

---

## 6. Database architecture

```
RAW (immutable files)            ← never rewritten; the forensic record
   │
DuckDB (analytical, numbers)     ← SQL; variances/trends; the only source of numbers
Cognee stores (knowledge)        ← graph (Kuzu) + vectors (LanceDB) + metadata (SQLite)
Graphiti (temporal graph)        ← Kuzu / FalkorDB; bi-temporal "valid from/to"
VAULT (Markdown + git)           ← SOURCE OF TRUTH; every claim carries provenance
   │
Indexes (FTS / vector / graph)   ← rebuildable from RAW + VAULT anytime
```

Boundaries that must not blur: **raw ≠ cleaned ≠ analysis ≠ decisions ≠ assumptions** —
each lives in its own place with its own provenance.

---

## 7. The first pilot department

**Cost Control (Costing).** It is the right pilot because:
- The pain is real and monthly (variance, margin, budget, cost drivers).
- The data is the most structured in the factory (SAP exports).
- Accuracy matters most here — which forces the discipline that benefits every later
  department.
- One success here earns the credibility to expand.

Planning is the natural second department; the engines are shared, so it is a *config*
add, not a rebuild.

---

## 8. Minimum viable version (MVP)

**One question, end to end, trustworthy** — already built and running:
> *"What drove material cost variance vs budget this period?"*

The MVP: ingest one Excel actuals file + one budget file → clean (exclude hidden total
rows, dupes, junk) → governed variance in DuckDB → one-A4 card with every number cited →
**independent audit** that re-computes the totals a second way, scores certainty, and
**asks the human a multiple-choice question when data quality is low** → **human sign-off**
→ rendered output. Nothing else is required for v1 to deliver value.

---

## 9. Future goals (after the core is trusted)

Documents + OCR evidence (Docling/PaddleOCR) · email & approval chains · the learning loop
(skills + error memory + outcome tracking) · the LLM-wiki vault · Cognee/Graphiti at full
strength · Open Design dashboards/decks · early-warning monitoring · second department,
then the **factory-wide brain** (cross-department questions) · Onyx enterprise search ·
scheduled/automated ingestion.

---

## 10. Risks and how to avoid them

| Risk | Avoid by |
|---|---|
| **Confident wrong number** reaching management | the independent audit + human sign-off (already built) |
| **"Variance/margin" means different things** | a governed metrics layer — one definition per KPI |
| **Prompt injection** via emails/PDFs | treat all ingested text as *data, never instructions*; quarantine anything learned from documents |
| **OCR/handwriting trusted blindly** | confidence score + human-review queue; never a silent fact |
| **Cognee vs Graphiti overlap** | keep the boundary: Cognee = structure, Graphiti = time |
| **Over-engineering / cathedral-building** | prove one department's loop before adding tools |
| **No adoption** | parallel-run against the existing manual report to earn trust |
| **Sending data outside** | everything in-house: on-prem model, local graph DB |

---

## 11. What to build first

1. Foundation: repo, contracts, tests, config (done).
2. **The numeric trust loop**: ingest → clean → governed variance → cited card (done).
3. **The audit + human sign-off layer** (done).
4. Then: the learning loop, then documents/OCR.

---

## 12. What NOT to build yet

- The full factory at once (start with Cost Control).
- Onyx enterprise search (only when many departments/sources exist).
- A heavy knowledge graph before the numbers are trusted.
- Industrial standards (ISA-95/OPC UA), automated ingestion, predictive models — later.
- Anything that isn't proving value for the pilot's monthly decision.

---

## 13. Implementation roadmap

| Stage | Build | Status |
|---|---|---|
| **0 Foundation** | repo, contracts, AGENTS.md, config, CI, tests | ✅ done |
| **1 Numeric trust loop** | DuckDB + Polars ingest/clean + governed variance + cited card | ✅ done |
| **2 Audit + sign-off** | independent re-run, certainty, human questions, accountable approval | ✅ done |
| **3 Learning loop** | decision + outcome memory (gated, injection-quarantined) | ✅ done |
| **4 Documents** | pypdf extraction + OCR confidence gating + `search_documents`; cards cite PDFs | ✅ done (pypdf real; Docling/PaddleOCR adapters) |
| **5 Memory tools** | wire real Cognee + Graphiti; the LLM-wiki vault | then |
| **6 Presentation** | wire Open Design (dashboards/PPTX) | then |
| **7 Second department + factory brain** | Planning lens; cross-department federation; Onyx | later |

---

## 14. Test scenario — one Excel + one PDF

**Inputs:** `cost_actuals_2026_05.xlsx` (monthly material cost actuals) and
`budget_approval_2026.pdf` (the approved budget + an approval signature).

1. **Ingest** both. 2. **OpenPyXL/Polars** read the Excel; **Docling** extracts the PDF's
budget table + the approval text. 3. **Clean**: Polars drops the embedded "Total" row,
flags a duplicate line, quarantines a cell that reads `"N/A"`. 4. **DuckDB** computes
actual vs budget by sub-assembly → e.g. *Frame +$100, Panel −$100, Board +$100, total
+$100*. 5. **Cognee** records *Frame → has_variance → +100* and links it to its cost
center. 6. **Graphiti** records that Frame's variance moved from last month. 7. **Hermes**
drafts the one-A4 card, citing the PDF for the approved budget figure and DuckDB for the
actuals. 8. **Audit** re-computes the +$100 a second way (DuckDB SQL vs Polars), confirms
it matches, sees 38% of rows were rejected, and **asks:** *"3 rows rejected — Accept /
Review / Re-ingest / Hold?"* 9. The analyst answers and **signs off.** 10. **Open Design**
renders the dashboard. *(Steps 1–4, 7–9 already run in `run_demo.py` today; the PDF path
and Cognee/Graphiti wiring are the next builds.)*

---

## 15. How the agent verifies every result

This is the heart of the system (the Audit Layer):

1. **Independent re-run (four-eyes):** recompute every key number by a *different* engine
   (DuckDB SQL vs the Polars path that built the card). They must match to the cent.
2. **Reconcile:** conservation (`rows_in == clean + rejected`), the variance bridge sums to
   its total, and the result ties out to the source of record (SAP official figure).
3. **Check evidence:** every number on the card must resolve to a real source + method;
   any uncited number is refused.
4. **Score certainty** across numbers / evidence / data-quality / materiality — and
   **escalate by money at stake**, not just error rate.
5. **Ask the human** a specific multiple-choice question whenever certainty is low or the
   rejects are material — never guess, never fill a gap silently.
6. **Require a named human sign-off** before release. The human owns the decision; the
   record stores who, when, what they saw, what they changed.

If a number can't be verified, it does not ship. That is the whole promise.

---

**Final mindset:** this is an operational brain — it *reads, remembers, connects,
analyzes, explains, and presents* factory knowledge, and it refuses to be confidently
wrong. Build the trusted loop for Cost Control first; everything else grows from there.
