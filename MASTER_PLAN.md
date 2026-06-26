# MASTER_PLAN.md — Factory-Wide Decision Intelligence System

> **The one sentence that fixes everything:**
> Numbers come from queries, never from AI guessing. AI synthesizes calculated facts
> and text into concise, evidence-backed management thinking. The whole system is a
> set of tools (an MCP server) that any AI agent drives.

This is the **single authoritative architecture and build plan.** It supersedes and
consolidates the earlier `MASTER_PLAN` draft and the `DECISION_INTELLIGENCE_PLAN.md`
opinion. The original `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN*.md`, and `REVIEW.md`
remain as the **detailed engine specs** this plan orchestrates — they are not
replaced. (See Part N for what changed in this revision and why.)

It is written in two registers. **Part A is for the decision-maker** (plain language).
**Parts B–N are for the build chain** (architecture, contracts, phases). The build
chain is **Architect → Codex → cheaper coding models** — Part I defines exactly how
the plan is handed down so weaker models can implement it safely.

### The three rules everything obeys
1. **Golden Rule (premise).** Code writes code from samples; engines execute code
   against volumes. *The AI never reads the raw data — it reads profiles and writes
   code your machine runs.*
2. **Calculation-Integrity Rule (trust).** Every number comes from a SQL query against
   the database. A synthesis model may **never** originate a number. This is enforced
   physically: a numeric question cannot reach the synthesis model until the Data
   Engine has returned calculated facts.
3. **Decision-Memory Rule (value).** Every useful output is stored as a fact, driver,
   risk, recommendation, decision, action, or lesson — *with evidence*. The brain
   stores *why*, not just *what*. That is what makes it a brain, not a report.

---

# PART A — THE VISION (plain language)

## A.1 The problem we remove
A manager in **any department** of a large TV-and-mobile factory drowns in inputs:
SAP Excel exports up to ~200 MB, long PDFs, approval workflows, tens of emails, Word
docs, sales tables, decks, screenshots. The cost is not just time — it is **missed
signal**: the variance nobody decomposed, the risk buried on page 40, the defect
trend nobody tied to a supplier change, the fact that *this happened last quarter and
we already know the fix.*

## A.2 What it delivers — one card, every time
For any question (and later, *before* you ask), the manager gets one tight card:

| Section | Meaning |
|---|---|
| **Executive headline** | One clear answer, one sentence. |
| **Key numbers** | Calculated facts only — never AI-estimated. |
| **Main drivers** | What caused the movement (price / qty / mix / fx / usage / …). |
| **Risk / opportunity** | Why management should care, and the time horizon. |
| **Recommended action** | What to do next — with an owner and a deadline. |
| **Evidence** | Exact source: file, sheet/page, rows/tables, and the calculation. |
| **Confidence** | High / Medium / Low, from real data quality (Part E.4) — not vibes. |

Same shape, every department, every time. Zero interpretation overhead.

## A.3 The trust rule, stated for a human
> **Numbers are calculated, never guessed. Every claim cites its source. No answer
> hides its confidence. Anything uncertain is flagged for a human — never silently
> turned into a fact.** Everything below exists to make a confident-but-wrong number
> *structurally impossible*, because that is the only failure a manager can't catch.

## A.4 Who it serves — the whole factory, department by department
Every department — Production, Quality, Supply Chain, Procurement, Planning,
Maintenance, Engineering, Warehouse, Sales, Finance/Controlling, HR, EHS, After-sales
— gets its **own second brain first**. Then those brains **federate into one factory
brain** so the CEO and CFO decide across all of them. **One platform, many brains —
not many apps.** Finance/Costing is the pilot (Part L). Privacy is locked: **all
processing stays in-house** (Part G.5).

---

# PART B — ARCHITECTURE: MCP-FIRST

## B.1 The decision that shapes everything
This is **not a chatbot**. It is a **toolbox — an MCP server** (Model Context
Protocol) exposing a clean, professional catalog of tools. Any AI agent (Claude,
Codex, an in-house agent) connects and *drives* the tools. The agent reasons and
writes prose; the tools do the exact, auditable work.

```
        ANY AI AGENT (Claude / Codex / …) — the ORCHESTRATOR
        routes questions, calls tools, composes the card.
        MAY originate language.  MAY NOT originate facts.
                              │  MCP (tool calls in / results out)
        ┌─────────────────────▼─────────────────────────────────┐
        │           THE APPLICATION = ONE MCP SERVER             │
        │     deterministic, testable, auditable tools           │
        ├───────────┬───────────┬───────────┬───────────┬───────┤
        │ DATA      │ DOCUMENT  │ EMAIL     │ INSIGHT   │ OUTPUT│
        │ ENGINE    │ ENGINE    │ ENGINE    │ BRAIN     │ & GOV │
        │ (numbers) │ (text)    │ (.eml)    │ (memory)  │       │
        └─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴───┬───┘
              ▼           ▼           ▼           ▼         ▼
        staging DB    doc index   email index  vault+index  card +
        (DuckDB)      (search)    (threads)    (MD+pgvector) quality
                                  │
                   PER-DEPARTMENT BRAINS  →  FACTORY BRAIN (federation)
                                  │
                   KNOWLEDGE VAULT (plain Markdown, git, forever)
```

## B.2 Why MCP-first is correct
- **It turns the trust rule into a wall.** The agent has *no tool that returns a
  number except the Data Engine.* It cannot hand-roll a total; it can only call
  `query_numbers` and report what came back.
- **Separation of deterministic vs generative.** Calculations, SQL, search, storage =
  code (tested, repeatable). Only language is generated. The two never blur.
- **Reusable by any agent.** Claude, Codex, Kimi, a future autonomous watcher — all
  speak MCP. Build the capability once.
- **Auditable.** Every answer is a trace of tool calls with inputs/outputs. That trace
  *is* the evidence trail in A.2.

## B.3 The trust boundary (the most important diagram)
```
  AI may ORIGINATE:   prose, structure, which tool to call.
  AI may NEVER ORIGINATE:   a number, a quote, a citation, a confidence score.
  Every number     → data.*   (carries the SQL that produced it)
  Every quote/page → docs.* / email.*  (carries file + page/table/thread ref)
  Every past fact  → brain.*  (carries the vault file ref)
  Every card       → summarize_for_manager, which REJECTS any numeric claim
                     lacking a tool-produced evidence ref.
```

## B.4 Department brains, then the factory brain
The unit of rollout is the **department**. Each gets its own scoped slice of the same
shared engines: its own **vault namespace**, **staging + index**, **lens + playbooks**
(Part F), and **access scope** (Part G.1). You do not build N apps — you build one
platform that *hosts* N department brains. Onboarding a department = configuration,
not code. The **factory brain** is a federated retrieval layer *over* the department
brains, governed by access — it is where the CEO's cross-department questions live
(*"did the panel shortage in Supply Chain cause the Quality rework spike and the Sales
miss?"*), which no single department's files can answer alone.

---

# PART C — THE FOUR EVIDENCE ENGINES

Detailed build specs already exist; this plan orchestrates them. Each engine is an
MCP-exposed module that **produces facts, never invents them.**

| Engine | Owns | Detailed spec | Source-of-truth principle |
|---|---|---|---|
| **Data Engine** | Numbers from Excel/CSV/SAP | `IMPLEMENTATION_PLAN.md` | DuckDB staging; heavy math in SQL; rejects + run.log |
| **Document Engine** | Text/tables from PDF/Word/PPT (+OCR) | `IMPLEMENTATION_PLAN_DOCS.md` | one normalized JSON per doc; `schema/document.schema.json` |
| **Email Engine** *(NEW)* | `.eml` threads, senders, approvals, attachments | *(new spec — Part C.2)* | thread-preserving; attachments recurse into Data/Doc engines |
| **Insight Brain** | Durable memory + retrieval + synthesis | `IMPLEMENTATION_PLAN_SECONDBRAIN.md` | Markdown vault = archive; Postgres/pgvector = disposable lens |

## C.1 Scale & SAP reality (why the engines are built this way)
A single SAP raw export can be **~200 MB, 272 columns, ~600k rows**, and there are
many, across every department, plus heavy PDF/email/approval volume.
- **Never load a 200 MB sheet into memory or a prompt.** Stream text-first into DuckDB
  (`openpyxl read_only`, chunked append, disk spill); all heavy math in SQL. An AI
  sees only the tiny profile and the small aggregated result.
- **SAP exports are messy in predictable ways** (ALV banners, embedded subtotal/total
  rows, header on row 4, UTF-16/Latin-1, locale `1.234,56`, transaction-specific
  layouts like MB51/COOIS/KSB1). `ingest_files` strips junk, detects encoding/locale,
  and **logs every assumption — never silently.** Full defenses in Part J.

## C.2 Email Engine (the piece the earlier draft of mine missed)
Emails are not documents — they carry threads, sender/date, approval chains, and
attachments. The Email Engine: parses `.eml` → sender, subject, date, body, **thread**,
attachments; feeds **each attachment back** into the Data or Document engine; makes
**approval workflows traceable** (who approved what, when, in what chain); and exposes
`search_emails` returning threads with full metadata + evidence refs.

## C.3 Template Registry (the other thing I had missed)
Standard repeated files must not be re-profiled blindly every month.

| Mode | How | Confidence |
|---|---|---|
| **Template-matched** | Known SAP export → matched to a registered template (expected columns, header row, sheet structure, classification) | High — no confirmation |
| **Inferred** | Unknown file → profile + classify, log confidence, **wait for human confirmation** | Low until confirmed; once confirmed it *becomes* a template |

The registry is a committed YAML config. By month three, most files match instantly.
No blind fuzzy-matching of critical columns — ever (Part J.1).

---

# PART D — THE MCP TOOL CATALOG (the public surface)

Names are the contract; do not rename. Every fact-returning tool also returns the
**evidence ref** that produced it. Each tool is scoped by the caller's department +
role (Part G.1).

| Tool | Engine | Does |
|---|---|---|
| `ingest_files` | all | Drop Excel/CSV/PDF/Word/PPT/.eml into the system (idempotent, resumable) |
| `query_numbers` | data | Numeric question → SQL runs → calculated facts **+ the SQL + rows** |
| `compute_variance` | data | Decompose Δ into price / qty / mix / usage / scrap / fx / timing + bridge |
| `search_documents` | docs | Document question → passages + file/page/table refs |
| `search_emails` | email | Email question → threads, senders, dates, attachments |
| `search_knowledge` | brain | Broad question → vault notes/decisions (hybrid keyword+semantic) |
| `get_data_quality` | gov | Confidence/quality score behind any answer (Part E.4) |
| `summarize_for_manager` | brain | Build the A.2 card; **reject any number without evidence**; attach confidence |
| `store_decision` | brain | Store decision: what, why, evidence, action, owner, date |
| `retrieve_decisions` | brain | "What did we do last time this happened?" |
| `retrieve_by_topic` | brain | "Show me all foam cost issues" — across everything |
| `set_lens` | brain | Switch the active department lens (Part F) |
| `get_warnings` | gov | Active warnings / early warnings for the current lens (Part E.5) |
| `register_template` | data | Promote a confirmed file layout into the Template Registry (C.3) |
| `project_module_report` | gov | Health report of any code module without reading it (Part H.3) |

---

# PART E — THE INSIGHT BRAIN (manager-ready thinking)

## E.1 Question Router (the gatekeeper)
Every question is classified and routed — this is where the Calculation-Integrity Rule
is physically enforced.

| Question type | Routed to | Example |
|---|---|---|
| Numeric / calculation | Data Engine (SQL) | "Total material cost variance vs budget?" |
| Document / text | Document / Email Engine | "What does the supplier-hold policy say?" |
| Knowledge / cross-source | Vault (+ graph later) | "All previous foam cost issues and what we did" |
| Mixed (number + why) | Data for facts → Vault for context → synthesis | "Why did TV material cost rise last quarter?" |

The active **department lens** (Part F) shapes interpretation and framing.

## E.2 Manager Summary Template
The seven-section card in A.2, rendered the same way every time, by
`summarize_for_manager`, which refuses to emit a numeric claim without a tool-produced
evidence ref.

## E.3 Decision Memory (first-class)
Every useful output becomes a typed, evidence-linked record in the vault:

| Type | Example | Originated by |
|---|---|---|
| Fact | "TV material cost rose USD X vs budget." | `query_numbers` (calculated) |
| Driver | "Mainly LCM price + quantity mix." | `compute_variance` |
| Risk | "Margin impact continues if BOM price holds." | agent, from facts |
| **Recommendation** | "Negotiate supplier; review part A." | agent — marked *proposed* |
| **Decision** | "Management **approved** supplier negotiation." | **human-signed** (G.4) |
| Action | "Procurement reviews part A by month-end." | human-assigned, tracked to close |
| Lesson | "Same pattern occurred in Q2 — fix was X." | `retrieve_by_topic` / recurrence |

**Recommendation ≠ Decision.** The system *proposes*; a human *approves*. Only a
human-signed decision becomes settled fact (G.4).

## E.4 Confidence + Data-Quality Score (concrete thresholds)
| Confidence | Condition |
|---|---|
| **High** | Rejects < 1%, no missing required columns, OCR unused or high-confidence, sources agree |
| **Medium** | Rejects 1–5%, or OCR medium-confidence, or minor missing columns |
| **Low** | Rejects > 5%, or OCR low-confidence, or major missing columns, or sources disagree |

OCR/screenshots are lower-trust by default; weak-confidence Arabic/English/handwriting
enters a **human-review queue** and may not become a trusted fact without review (J.2).

## E.5 Recommendations, Warnings, Early Warnings
- **Recommendations** — derived from drivers + past decisions.
- **Warnings** — things to look at now (reject pile, missing data, budget overrun).
- **Early warnings** — *proactive*; pattern/recurrence detection across periods (Part
  L Phase, the `watch.*` layer): "this variance pattern preceded a cost spike in Q2."

---

# PART F — THE DEPARTMENT LENS MODEL

Each department has a **lens config** (committed YAML) defining what matters to it and
how to frame its card. The same engines serve every lens; the Router uses the active
lens to decide what to query and how to summarize. A **playbook** is a named recurring
workflow *on* a lens (e.g. Finance "monthly close": which files, which variances, which
card). New department = new lens + playbooks = **configuration, not code.**

| Department | Lens focus | Example question |
|---|---|---|
| Finance/Costing *(pilot)* | Variance, margin, budget, cost rollup | "Why did TV material cost increase?" |
| Production | Output, yield, scrap, downtime, BOM accuracy | "Which line has the most scrap?" |
| Quality | Defect rates, holds, RMA, supplier quality | "Which suppliers caused the most RMAs?" |
| Procurement | Supplier cost, PO trends, price changes, lead times | "Which suppliers raised prices?" |
| Supply Chain | Inventory, stockouts, lead times, shipping | "What's at risk of stockout this month?" |
| Sales | Customer mix, revenue, pricing, channel | "Which customers shifted mix?" |
| R&D | BOM changes, specs, design changes | "What changed on the MX BOM this quarter?" |
| HR | Headcount, overtime, attrition | "Where are overtime spikes?" |
| Maintenance | Downtime, MTBF, backlog | "Which lines have the highest downtime?" |

---

# PART G — GOVERNANCE & TRUST (what keeps it safe)

## G.1 Access control (day-one constraint)
Every record, file, and vault note carries an **owner/scope** (department, plant,
region). `query_numbers`, `search_*`, and `brain.*` filter by the caller's role: a
plant manager sees one plant; the CFO sees finance across plants; the CEO sees all.
Retrofitting row-level security later is painful and dangerous — it is wired in from
Phase 0.

## G.2 Evaluation harness (or you never *know* it's right)
A committed **golden set** of known-answer questions (e.g. 30 finance Q&A, hand-
verified). Every release **tests retrieval and calculation separately** — a system can
sound perfect while retrieving the wrong evidence (the cited Haystack point). The
harness gates every phase. Lives in `/eval`.

## G.3 Nothing vanishes silently
Unparseable rows → `rejects.csv`. Failed documents → `failures.csv`. Every assumption →
`run.log`. Conservation laws asserted: `rows_in == clean + rejected`,
`docs_in == docs_out + failures`. A human skims rejects/failures **every run**.

## G.4 Human-in-the-loop sign-off
A recommendation is `proposed`; it becomes a `decision` only on human approval
(signature + timestamp recorded). The brain distinguishes the two forever, so it never
treats its own suggestion as fact.

## G.5 Offline / in-house (LOCKED)
**All processing stays in-house. No factory document, SAP export, email, screenshot,
OCR image, or approval leaves the company network.** OCR runs offline (Tesseract /
PaddleOCR, EN+AR). Any future external provider must be explicit, configurable, and
approved before use.

---

# PART H — CODE ARCHITECTURE FOR AI-REVIEWABILITY

The biggest risk is not a wrong number — it is **a million lines of code no human and
no AI can hold in their head.** Same trick as the data: *the AI reads a map of the
code, never all the code.* This matters double here because the actual coders are
**cheaper, weaker models** (Part I) that hang or break things when given too much.

## H.1 Module rules (enforced, not suggested)
- **One responsibility per module.** Engines, MCP server, playbooks, shared contracts
  are separate. A module never reaches inside another — it calls only through a
  published **contract** (an MCP tool schema or a typed function signature).
- **Hard size caps.** A file past its cap is split; a module past its cap becomes two.
  Reviewability is a budget, kept on purpose.
- **Seams are explicit and versioned.** The MCP tool schemas (Part D) and the JSON
  schemas (`schema/`) ARE the contracts. A model understands a module from its
  contract without reading its internals — the entire point of a seam.

## H.2 The map: `AGENTS.md` everywhere (Codex-native)
We standardize on **`AGENTS.md`** (plural) — the format **Codex reads natively** and
hierarchically (nearest file wins; OpenAI's own repo ships 88 of them).
- **Root `AGENTS.md`** — table of contents of the whole system; every module one line,
  with a pointer to its own `AGENTS.md`, plus exact **build/test/lint commands** and
  the **always / ask-first / never** safety rules (incl. git-safety). An agent starts
  here, always.
- **One `AGENTS.md` per module** (≤ ~1 page): *what it does · public interface ·
  inputs/outputs · invariants · what it must NEVER do · allowed libraries + import
  examples · where its tests are · exact commands.*
- **These docs are part of "done."** A change that alters an interface but not its
  `AGENTS.md` fails review. The map can never drift from the territory.

## H.3 Reports on demand
`project_module_report` lists, per module: public surface, dependencies, test status,
open TODOs — a health report on any part *without reading it*. This is your "AI makes
reports, doesn't read all the code" requirement, made real.

## H.4 Repository shape (one platform, clear seams)
```
/AGENTS.md                 ← root map + commands + safety rules: start here
/shared/contracts/         ← MCP tool schemas + JSON schemas (the seams)   + AGENTS.md
/engines/data/             ← DuckDB, SAP ingest, variance, templates       + AGENTS.md
/engines/docs/             ← PDF/Word/PPT extraction + offline OCR          + AGENTS.md
/engines/email/            ← .eml threads, approvals, recursive attachments + AGENTS.md
/engines/brain/            ← vault + index + decision memory + synthesis    + AGENTS.md
/mcp_server/               ← exposes the tool catalog over MCP              + AGENTS.md
/lenses/                   ← per-department lens configs (finance.yaml …)   + AGENTS.md
/templates/                ← file template registry (file_templates.yaml)   + AGENTS.md
/playbooks/finance/        ← the pilot department's workflows               + AGENTS.md
/eval/                     ← golden-set trust harness (G.2)                 + AGENTS.md
/vault/                    ← forever-safe Markdown knowledge base (gitignored content)
/tests/                    ← pytest suites mirroring each module
```

---

# PART I — THE BUILD CHAIN: Architect → Codex → cheaper coders

This plan is implemented by a **pipeline of models**, not one. Designing for that is
the difference between a clean system and a mess weak models can't maintain.

## I.1 Roles
| Stage | Model(s) | Produces |
|---|---|---|
| **Architect** | (this plan) | the architecture, contracts, phases, rules, edge-case defenses |
| **Lead Engineer** | **Codex / GPT-5.5** | expands each phase into **task cards** (I.3), writes contracts as stubs + the **tests** (red), scaffolds the repo + every `AGENTS.md`, integrates, runs the full suite, handles cross-cutting refactors |
| **Implementers** | **Kimi K2.7 / DeepSeek V4 Pro / V4 Flash / MiniMax M3** | implement one task card at a time — fill code until its (already-written) test passes |

## I.2 The safety mechanism: contracts-first, test-first
Because the implementers are cheaper/weaker, **the strong model writes the interface
and the test before they touch code.** A task becomes: *"make `tests/data/
test_variance.py` pass, by implementing `compute_variance` per the contract, editing
only `engines/data/variance.py`."* A weak model can't go far wrong when the test
defines done, the contract is fixed, and the module is isolated. This is TDD used as a
guardrail for weak coders.

## I.3 The Task Card (Codex fills one per atomic task; implementers consume it)
```
TASK <id> — <short title>
Module:       engines/data
Files:        engines/data/variance.py   (edit ONLY this)
Read first:   engines/data/AGENTS.md  +  shared/contracts/data.tools.json
Contract:     compute_variance(actual, baseline, dims) -> VarianceBridge   (fixed)
Depends on:   TASK 0xx (must be green first)
Do:           <one explicit paragraph; copy-pasteable commands>
Done when:    `pytest tests/data/test_variance.py` is green   (test already exists)
Never:        load whole files into memory · touch another module · invent columns
Assign to:    DeepSeek V4 Pro    (per routing, I.4)
```

## I.4 Model routing (match task difficulty to model — research-grounded)
| Task type | Model | Why |
|---|---|---|
| Plan expansion, contracts, tests, cross-cutting refactor, integration | **Codex / GPT-5.5** | long-horizon, repo-wide, 1M ctx, strong validation; AGENTS.md-native |
| The MCP server + long-horizon agent/tool workflows, self-correcting multi-file work | **Kimi K2.7 Code** | token-efficient long runs, MCP-native, self-correction |
| Hard isolated logic (variance math, SQL, SAP parsers) at low cost | **DeepSeek V4 Pro** | SWE-bench 80.6% ≈ frontier at ~1/10 cost |
| Bulk/boilerplate, glue, config, test scaffolding | **DeepSeek V4 Flash** | top-quartile coding, ~$0.14/$0.28 per M — very cheap/fast |
| Image/screenshot/OCR-tuning tasks, very-long-context reads | **MiniMax M3** | native multimodal, 1M ctx, SWE-Bench Pro ≈ GPT-5.5 |

## I.5 Guardrails against weak-model failure modes
- **Hallucinated APIs** → pinned `requirements.txt`; each `AGENTS.md` lists allowed
  libraries + import examples.
- **Scope creep** → atomic cards; "edit ONLY this file"; "never touch another module."
- **Silent breakage** → test-first; CI runs the suite + the golden set (G.2) on every
  change; red blocks merge.
- **Context overflow / hang** → implementers read only the module `AGENTS.md` + the
  card + the test, never the whole repo (even with 1M context — cost and degradation).
- **Style drift** → `AGENTS.md` code-style + a single formatter/linter command.
- **Unsafe git** → root `AGENTS.md` always/ask-first/never git rules; branch discipline.

## I.6 Note on 1M context windows
Every model in the chain has ~1M context — but "it fits" is not "use it." Big context
costs money and degrades weak models. The map-not-territory discipline (Part H) stands:
feed the smallest correct slice.

---

# PART J — MESSY-DATA & OCR COMMITMENTS (finance pilot)

The pilot must survive real factory inputs. Items beyond `ARCHITECTURE.md` §3 /
`REVIEW.md` are marked **NEW**.

## J.1 Numbers (Data Engine)
| Edge case | Defense | Owner |
|---|---|---|
| **Total/subtotal rows embedded in detail rows** (sum → double-count) **NEW** | Detect via template rules, labels (`Total`/`Gesamt`/`المجموع`), blank key cols, repeated rollup patterns, and numeric reconciliation → flag `total_row`, **exclude from detail aggregates** unless template says otherwise | `ingest_files` + validate |
| Header not on row 1 | Detect once, **save as template setting**; low-confidence → human confirm | template registry |
| 272 mixed/dirty columns; first rows lie | Profile (random + weirdest samples); coerce + quarantine to rejects | profile + clean |
| 200 MB won't fit RAM | Stream into DuckDB; math in SQL (spills to disk) | `ingest_files` |
| SAP junk (ALV banners, encoding, locale `1.234,56`, negatives in parens) | Strip + detect + parse by declared locale; quarantine unparseable with reason | `ingest_files` |
| Same concept, many column names | Human-reviewed `column_map.yaml`; **no blind fuzzy match** on critical fields | clean |
| Duplicate / re-ingested rows | Global row-id, idempotent load, duplicate flagging | per `REVIEW.md` A1–A4 |
| Money summed as float drifts | `DECIMAL(18,4)` for money columns at clean stage | clean |
| Schema drift over months | `schema_profile.json` committed; git diff shows it; assert expected columns, **fail loudly** | profile |

## J.2 Documents, emails & images (the hard frontier)
| Edge case | Defense | Owner |
|---|---|---|
| Mixed PDF (text + scanned pages) | Per-page scanned flag; OCR only image pages; merge in reading order | docs |
| PDFs/decks/emails with many tables needing OCR | Table-aware extraction; table text appears once | docs |
| **Bilingual English + Arabic, RTL, mixed scripts** **NEW** | Offline OCR with EN+AR models; per-region script detection; preserve RTL order; keep original + normalized text; never translate silently | docs OCR |
| **Screenshots** (not clean scans) | Deskew/denoise/threshold before OCR; low-confidence cells → review | docs OCR |
| **Handwriting** (often EN+AR, partial) **NEW** | Best-effort OCR + **confidence per block**; handwriting/low-confidence **flagged → human-review queue, never silently trusted** | docs OCR + `get_data_quality` |
| Cropped/missing screenshot content | Mark incomplete; the card **discloses the gap** instead of filling it | docs + summary |
| One bad file crashes the batch | Per-file try/except → `failures.csv` + reason; batch continues | all |
| Legacy `.doc`/`.ppt` | LibreOffice headless, **serial** with isolated UserInstallation profiles | docs |

> **Honest limit.** Offline Arabic-handwriting OCR is the least reliable input in the
> whole system. We do not pretend to read it perfectly: extract best-effort, score
> confidence, **surface low confidence loudly**, route to human review. Uncertain in →
> visible, never silent. (This is *why* the offline trade-off in G.5 is acceptable.)

---

# PART K — TECHNOLOGY STACK (consolidated)

| Concern | Use | Rationale |
|---|---|---|
| Heavy storage + aggregation | **DuckDB** | spills to disk; 200 MB+ files; friendly SQL |
| Excel reading | **openpyxl `read_only`** (+ pandas only for tiny results) | streams; won't OOM |
| PDF text + tables | **pdfplumber** | reading order + tables |
| PDF metadata / pages | **pypdf** | encryption check, page count |
| PDF render for OCR | **PyMuPDF (fitz)** | fast page-image export |
| OCR (offline, EN+AR) | **Tesseract / PaddleOCR** + `pytesseract` | in-house; EN+AR; handwriting → review |
| Word / PPT | **python-docx / python-pptx** | paragraphs, tables, slides, notes |
| Legacy `.doc`/`.ppt` | **LibreOffice headless** (serial) | convert to modern |
| Email | stdlib `email` + `mail-parser` | separate engine; attachments recurse |
| File-type detection | **python-magic** + extension fallback | extensions lie |
| Output validation | **jsonschema** | validate against `document.schema.json` |
| Encoding sniff | **charset-normalizer** | per-file; logged |
| Config | **pyyaml** | `config.yaml`, `column_map.yaml`, lenses, templates |
| Index / FTS / relations | **Postgres** (Supabase) | disposable, rebuildable from vault |
| Vector search | **pgvector** | one DB for v1 |
| Synthesis AI | **Claude (Anthropic), swappable** | reasoning, summaries, recommendations |
| Embeddings AI | **Voyage AI (or OpenAI/Cohere), swappable** | semantic vectors (Claude has no embeddings API) |
| Markdown vault | **python-frontmatter + markdown-it-py** | parse + links |
| MCP server | **MCP Python SDK** | the interface for AI agents |
| Tests | **pytest** | regressions are silent otherwise |
| Python | **3.11+** | |

**AI providers are swappable via `config.yaml`** (synthesis and embeddings configured
separately; keys from env vars, never committed) — this is also how the build-chain
models (Codex / DeepSeek / Kimi / MiniMax) are selected per task. System deps installed
separately: Tesseract, LibreOffice, libmagic, Postgres+pgvector.

---

# PART L — ROADMAP (foundation first, then grow)

> **Do not start a phase until the previous phase's Definition of Done is green;** a
> trust gate (G.2) is part of every DoD. Platform built once (Phases 0–4 + brain);
> departments onboarded by configuration (v2); factory brain federates (v3).

### v1 — Pilot department: Finance / Costing
| Phase | Builds | Deliverable |
|---|---|---|
| **0. Foundation** | MCP server skeleton; `config.yaml` (providers, lenses, templates, **roles/access**); git-vault scaffold; DuckDB setup; **root + per-module `AGENTS.md`**; pinned `requirements.txt`; CI + empty golden set | a tool callable over MCP, scoped to a department; CI green |
| **1. Data — Ingest** | Streaming Excel/SAP/CSV → DuckDB (text-first, chunked, multi-sheet/file). Handles 200 MB+. | `ingest_files` live; 200 MB file ingests with no OOM |
| **2. Data — Profile + Classify + Templates** | Schema profile; template-match vs infer (C.3) | profile + `file_templates.yaml`; classification works |
| **3. Data — Clean** | Coerce types; quarantine rejects; **total-row defense (J.1)**; duplicates; money `DECIMAL` | clean tables; `rejects.csv`; `run.log` |
| **4. Data — Query** | SQL variance/driver breakdown | `query_numbers` + `compute_variance` live; reconciles to the cent |
| **5. Document Engine** | PDF/Word/PPT → normalized JSON; offline OCR (EN+AR); resumable | `search_documents` live; mixed-evidence card cites a page |
| **6. Email Engine** | `.eml` parse; attachments recurse; approval chains | `search_emails` live |
| **7. Question Router** | Classify number/doc/knowledge/mixed; apply lens | routing live |
| **8. Manager Summary** | Template renderer; evidence enforced; confidence (E.4) | `summarize_for_manager` live |
| **9. Decision Memory** | Store/retrieve decisions, drivers, actions, lessons; **human sign-off (G.4)** | `store_decision`/`retrieve_decisions` round-trip |
| **10. Vault + Index** | Markdown vault (dept-namespaced) + pgvector; rebuildable | delete index → rebuild from vault → identical |
| **11. Validate + Quality** | Conservation laws; data-quality score; evidence audit; golden set | `get_data_quality` live; `validate` exits 0; golden set passes |

**v1 success =** Finance drops real files (SAP exports, Excel, PDFs, decks, emails,
approvals, screenshots) → asks a management question → gets a structured card with
calculated numbers, drivers, evidence links, quality/OCR warnings, and confidence →
stores the decision → later retrieves what was decided and why.

### v2 — Department expansion
Apply the same engines to Production, Quality, Supply Chain, Sales, R&D, HR,
Procurement, Maintenance. Each = lens config + vault subtree + role scope. **No
rebuild.** DoD: two departments give correctly different, correctly scoped answers; a
third onboards with zero engine-code change.

### v3 — Factory-wide brain (federation)
Cross-department retrieval + **GraphRAG-style** relationships/community summaries;
CEO/CFO lens; **early-warning** (`watch.*`) across periods and departments. DoD: a
cross-department question returns one card citing each department, respecting access.

### v4 — Continuous intelligence (later)
Automated ingestion; predictive warnings; decision-outcome tracking ("did the action
work?").

---

# PART M — DEFINITION OF DONE (v1 pilot)

- [ ] `ingest_files` handles a 200 MB+ Excel with zero OOM
- [ ] Embedded total/subtotal rows are detected and excluded (J.1) — proven by a test
- [ ] Every document JSON validates against `schema/document.schema.json`
- [ ] `mcp_server` exposes the full Part D tool catalog, **scoped by role** (G.1)
- [ ] `query_numbers("material cost variance vs budget")` returns a number **with rows cited**
- [ ] `summarize_for_manager` matches the template with evidence + confidence
- [ ] `store_decision` + `retrieve_decisions` round-trip; recommendation vs decision distinct (G.4)
- [ ] `validate` exits 0 (conservation laws pass); golden set passes (G.2)
- [ ] `rebuild_index` reconstructs the index from the vault alone
- [ ] `rejects.csv` + `failures.csv` exist (even if empty) and are skimmed every run
- [ ] Every module has an `AGENTS.md` (purpose, interface, commands, edge cases, never-do)
- [ ] OCR outputs carry confidence + human-review status for screenshots, EN/AR, handwriting
- [ ] All processing verified in-house; no external calls except configured AI providers (G.5)

---

# PART N — REVISION RATIONALE (what changed and why)

Honest record of this consolidation, so we never re-litigate it.

**Adopted from `DECISION_INTELLIGENCE_PLAN.md` (it was right, my earlier draft wasn't):**
- **Email Engine** as a separate engine (threads, approvals, recursive attachments). I
  had wrongly folded email into "documents."
- **Template Registry** (template-matched vs inferred) — recurring SAP files shouldn't
  be re-profiled blindly; this makes each month faster and safer.
- **Department Lens Model** as explicit config; **consolidated tech stack**; **concrete
  confidence thresholds**; **Definition-of-Done** checklist.

**Kept from my version (the other draft lacked these):**
- **Access control / role scoping** (G.1) — essential for CEO vs plant-manager; absent
  there.
- **Evaluation harness as a real phase** (G.2) — there it was only a research aside.
- **Recommendation-vs-Decision human sign-off** (G.4); the **trust boundary** as a hard
  structural wall (B.3).

**New in this revision (driven by the build-chain requirement + research):**
- **Part I — the Architect → Codex → cheap-coders pipeline**: contracts-first, test-
  first, the Task Card, model routing, and weak-model guardrails. This is the core new
  idea: the plan is shaped so *weaker* models can implement it without breaking things.
- **Standardized on `AGENTS.md`** (plural, hierarchical) because **Codex reads it
  natively** — making the whole repo Codex-compatible by construction.
- Folded SAP-scale, total-row, and bilingual/handwriting OCR defenses into one
  committed edge-case register (Part J).

**Wrong assumptions I corrected:** email-as-document; profile-every-file-every-time;
under-specifying for weak implementers; loose `AGENT.md` naming.

---

# MY RECOMMENDATION (the sharp answer)

**Pilot = Finance/Costing. Build the foundation once, prove it on Finance, then repeat
by configuration.** Finance is the right pilot: real pain, the most structured data
(SAP), and it exercises the hardest part — exact numbers, variance drivers, cited
evidence — on day one. It stays a **factory platform piloted on Finance**, not a
finance app.

**Order:** (1) Phase 0 + the Part H/I discipline — the modular skeleton, the
`AGENTS.md` maps, the contracts and tests — *the powerful foundation built so it stays
reviewable at a million lines and so weak models can build on it.* (2) The Data Engine
trust wall on a real 200 MB SAP file, including the total-row defense. (3) The Finance
card end-to-end. Documents/email/OCR come after the numbers loop is trustworthy.

**Next concrete step:** hand Part L Phase 0 to Codex with the instruction *"scaffold
the repo, write every `AGENTS.md`, define the contracts in `/shared/contracts`, and
write the failing tests — implement nothing yet."* That produces the skeleton the cheap
models then fill, card by card. Say the word and I'll prepare that exact Codex hand-off
brief.
