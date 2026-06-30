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
| `define_metric` / `query_metric` | semantic | Define / run a **governed metric** — one definition of cost/margin/variance (Part R) |
| `audit_report` | audit | **Independent** re-run + re-verify of a draft card; returns pass/flag + **certainty score** + issues (Part O) |
| `raise_review_questions` | audit | Generate deep **multiple-choice** questions for the human when uncertain or high-stakes (Part O.5) |
| `approve_report` | audit | Record the **accountable human sign-off** before release: who · when · what was shown · what changed (Part O.6) |
| `propose_skill` / `use_skill` | learning | Skill lifecycle — propose (validated, gated) and reuse procedures (Part P) |
| `record_outcome` | learning | Track whether a decision's action actually worked — "did it work?" (Part P) |
| `wiki_update` / `wiki_query` / `wiki_lint` | wiki | Maintain / query / validate the AI wiki: raw → wiki → index, with provenance (Part Q) |

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
| Excel reading | **openpyxl `read_only`** | streams; won't OOM |
| Clean / shape dataframes | **Polars** (Rust; replaces pandas) | fast, low-memory on wide SAP tables |
| Document extraction (PDF/Word/PPT, layout + tables) | **Docling** (primary; local) | structured text + tables + reading order |
| PDF metadata / pages | **pypdf** | encryption check, page count |
| PDF render for OCR | **PyMuPDF (fitz)** *(AGPL — internal use; Docling covers most needs)* | fast page-image export |
| OCR (offline, EN+AR) — **cascade** | **Tesseract** → **RapidOCR** → PaddleOCR → Surya → **VLM** (olmOCR-2/PaddleOCR-VL/GOT-OCR2/DeepSeek-OCR) | escalate to the best engine when reading is poor; in-house; handwriting/low-confidence → human review |
| Word / PPT (fallback) | **python-docx / python-pptx** | when Docling needs a fallback |
| Legacy `.doc`/`.ppt` | **LibreOffice headless** (serial) | convert to modern |
| Email | stdlib `email` + `mail-parser` | separate engine; attachments recurse |
| File-type detection | **python-magic** + extension fallback | extensions lie |
| Output validation | **jsonschema** | validate against `document.schema.json` |
| Encoding sniff | **charset-normalizer** | per-file; logged |
| Config | **pyyaml** | `config.yaml`, `column_map.yaml`, lenses, templates |
| Index / FTS / relations | **Postgres** (Supabase) | disposable, rebuildable from vault |
| Vector search | **pgvector** | one DB for v1 |
| Synthesis AI | **on-prem model (Qwen / Llama / DeepSeek via vLLM) by default**, swappable | reasoning, summaries, recommendations — *kept in-house to honor G.5; external (Claude) only if G.5 is explicitly relaxed* |
| Embeddings AI | **local embeddings (e.g. bge / Qwen-embed), swappable** | semantic vectors, in-house |
| Knowledge-graph memory | **Cognee** (Apache-2.0; local: Kuzu+LanceDB+SQLite) | entities/relations from docs; hybrid graph+vector |
| Temporal knowledge graph | **Graphiti** (Apache-2.0; Kuzu/FalkorDB) | facts that change over time — "what changed Q2→Q3" (fills the temporal gap) |
| Graph database | **Kuzu** (embedded, light) / FalkorDB; Neo4j only if needed | backs Cognee + Graphiti |
| Enterprise search (later) | **Onyx** (self-host) | search across all factory docs + ready connectors; v2/v3 |
| Output / design (UX) | **Open Design** (nexu-io; local-first) | dashboards/decks/reports; HTML/PDF/PPTX export; driven by Codex/Hermes |
| Orchestrator agent | **Hermes** (pattern; MIT) | drives the MCP tools; its skills/memory feed the *gated* learning engine (Part P) |
| Markdown vault | **python-frontmatter + markdown-it-py** | parse + links |
| MCP server | **MCP Python SDK** | the interface for AI agents |
| Tests | **pytest** | regressions are silent otherwise |
| Python | **3.11+** | |

**AI providers are swappable via `config.yaml`** (synthesis and embeddings configured
separately; keys from env vars, never committed) — this is also how the build-chain
models (Codex / DeepSeek / Kimi / MiniMax) are selected per task. System deps installed
separately: Tesseract, LibreOffice, libmagic, Postgres+pgvector, a graph DB (Kuzu).

## K.1 — The Layered Tool Stack (the concrete picks, one map)

Seven roles, each mapped to an engine in this plan. **Think of it as a body:** read →
clean → analyze → remember relations → remember history → search → present, with one
brain coordinating.

| # | Layer (role) | Tools | Maps to |
|---|---|---|---|
| 1 | **Read files** | Docling · PyMuPDF · PaddleOCR · OpenPyXL | Document + Data ingest (Part C) |
| 2 | **Clean + analyze numbers** | Polars · DuckDB | Data Engine + governed metrics (Parts C, R) |
| 3 | **Knowledge memory (relations)** | **Cognee** | Insight Brain graph (Parts E, Q) |
| 4 | **Temporal memory (history)** | **Graphiti** | time-aware memory — fixes the temporal gap (Part E) |
| 5 | **Enterprise search (later)** | **Onyx** | federation / search across departments (Part E, v2–v3) |
| 6 | **Output / design** | **Open Design** | serving / UX layer (Part S) |
| 7 | **Orchestrator** | **Hermes** | the agent that drives the MCP tools (Part B) |

**Build order (owner's sequence):** ① Docling + DuckDB + Polars → ② Cognee → ③ Graphiti
→ ④ Open Design → ⑤ Onyx. (Onyx is last: it pays off only once many departments and
sources exist; until then the *agent* is the main user.) This sits inside the Part L
roadmap — extraction in Phases 1–4, Cognee/Graphiti in the brain phases, Open Design at
the manager-card/serving phase, Onyx in v2–v3.

**Architect's guardrails on this stack (non-negotiable):**
- **All local / in-house (G.5).** Cognee, Graphiti, Onyx, and Open Design all run
  self-hosted; point their LLM at the **on-prem** model; no external calls. Prefer the
  light local graph stack (**Kuzu** + LanceDB + SQLite) over a heavy Neo4j install.
- **Cognee and Graphiti are complementary, not redundant.** Cognee = *structure/relations
  extracted from documents*; Graphiti = *how facts change over time*. Keep that boundary
  so we don't run two overlapping graphs.
- **The vault stays the source of truth (Part Q).** Cognee / Graphiti / Onyx / pgvector
  indexes are **disposable and rebuildable** from raw + wiki. Knowledge never lives only
  inside a graph DB.
- **The trust wall still holds.** Numbers come from **DuckDB/Polars via governed metrics
  (Part R)** — the graphs store relations, context, and history, **never the authoritative
  numbers.** The Audit layer + human sign-off (Part O) still gate every output.
- **Open Design is output-only.** It renders the card/dashboard/deck **after** audit +
  sign-off. It never computes or invents a number — it is the beautiful face on the brain,
  not the brain.
- **Hermes is the orchestrator only** (borrow the pattern, don't fork); its learning is
  **quarantined from untrusted input** (Part P zombie-agent rule).
- **License watch:** PyMuPDF is AGPL (Docling covers most needs — prefer Docling); Onyx
  has community + enterprise tiers; confirm Open Design's license before shipping.

---

# PART L — ROADMAP (foundation first, then grow)

> **Do not start a phase until the previous phase's Definition of Done is green;** a
> trust gate (G.2) is part of every DoD. Platform built once (Phases 0–4 + brain);
> departments onboarded by configuration (v2); factory brain federates (v3).

### v1 — Pilot department: Finance / Costing  *(numeric trust loop → audit → learning, before documents)*
| Phase | Builds | Deliverable |
|---|---|---|
| **0. Foundation** | MCP skeleton; `config.yaml` (providers **on-prem synthesis**, lenses, templates, **roles/access**); git-vault scaffold; DuckDB; **root + per-module `AGENTS.md`**; pinned `requirements.txt`; CI + empty golden set; **skeletons for metrics (R), audit (O), learning (P), observability (S)** | a tool callable over MCP, scoped to a department; CI green |
| **1. Data — Ingest** | Streaming Excel/SAP/CSV → DuckDB (text-first, chunked, 200 MB+); **source-adapter interface (S)** | `ingest_files` live; 200 MB no OOM |
| **2. Profile + Classify + Templates** | Schema profile; template-match vs infer (C.3); **data contracts per source (S)** | profile + `file_templates.yaml` |
| **3. Clean** | Coerce; quarantine; **total-row defense (J.1)**; duplicates; money `DECIMAL`; **materiality-weighted rejects (S)** | clean tables; `rejects.csv`; `run.log` |
| **4. Governed metrics + Query** | **Metric layer (R)** — define finance metrics once → governed SQL variance/driver | `define_metric`/`query_metric` + `compute_variance`; reconciles to the cent **and ties to SAP (S)** |
| **5. Manager card** | one-A4 **BLUF/Minto/SCQA** renderer; evidence enforced; **multi-dimensional confidence (S)** | `summarize_for_manager` live |
| **6. AUDIT & human sign-off** | **Independent re-run** + citation re-verify + **certainty score** + **deep MCQ to human** + **accountable approval gate** (Part O) | `audit_report`/`raise_review_questions`/`approve_report` live; **nothing releases without sign-off** |
| **7. Decision + outcome memory** | Store/retrieve decisions; **outcome tracking** ("did it work?"); recommendation ≠ decision (G.4) | `store_decision`/`retrieve_decisions`/`record_outcome` |
| **8. LEARNING loop** | Error memory; corrections → lessons → **skills** (risk-tiered, gated, injection-quarantined) (Part P) | `propose_skill`/`use_skill`; a repeated mistake becomes a regression test |
| **9. Document Engine** | PDF/Word/PPT → JSON; offline OCR (EN+AR); resumable | `search_documents` live |
| **10. Email Engine** | `.eml`; attachments recurse; approval chains | `search_emails` live |
| **11. Wiki vault + index** | raw → AI-wiki → disposable index (Part Q); wiki-lint; rebuildable | `wiki_query` live; delete index → rebuild → identical |
| **12. Validate + Quality + Security** | Conservation; golden set; **red-team / prompt-injection (S)**; observability traces | `validate` exits 0; golden + security pass |

> **Why this order:** prove the numeric loop, then make it **auditable and accountable**
> (Phase 6), then make it **learn** (Phase 8) — all *before* the harder document/OCR work.
> Trust and learning are foundations, not finishing touches.

**v1 success =** Finance drops real files → asks a management question → gets a one-A4
card with calculated numbers, drivers, evidence, and confidence → **the audit layer
independently re-checks it, asks the analyst any uncertain points as multiple-choice,
and a named human signs it off** → only then does it reach the manager/CEO → the
decision + its later outcome are stored, and any correction teaches the system.

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

**Revision 3 (after two senior audits + the owner's audit-layer directive) — added
Parts O–S:**
- **Part O — Audit & Human-Accountability Layer** (the biggest addition): an *independent*
  re-run + reassessment + **calibrated certainty score** + **deep multiple-choice
  questions to the human** + an **accountable, recorded sign-off gate**. Maker-checker /
  four-eyes. *Nothing reaches the CEO unsigned.* This was the key gap both my own audit and
  the second opinion under-weighted, and the owner correctly insisted on it.
- **Part P — Learning Engine** (skills/memory/error/outcome/gated self-evolution, with the
  zombie-agent quarantine). **Part Q — LLM-Wiki vault** (Karpathy/Obsidian: raw → AI-wiki →
  disposable index). **Part R — Governed meaning** (semantic metrics + factory ontology).
  **Part S — register** of in-house-synthesis fix, confidence v2, observability, data
  contracts/lineage, source adapters, security threat model, one-A4 doctrine.
- **Roadmap re-sequenced:** numeric trust loop → **audit** → **learning** *before*
  documents/OCR. Trust and learning are foundations, not finishing touches.
- **Reuse stance (Hermes / Karpathy / Obsidian projects):** borrow the *patterns and open
  standards*, **do not fork** — build our learning/wiki modules natively with the finance
  governance, access control, audit, and injection defenses those general tools lack.
  (License note: Hermes is MIT; keep any AGPL component external behind a CLI only.)

**Revision 4 — concrete tool stack adopted (Part K.1):** the owner's seven-layer map —
Docling/PyMuPDF/PaddleOCR/OpenPyXL (read) · Polars/DuckDB (analyze) · **Cognee**
(relations) · **Graphiti** (history) · **Onyx** (enterprise search, later) · **Open
Design** (output) · **Hermes** (orchestrator). Graphiti directly closes the temporal-data
gap from the audits. Cognee and Graphiti are kept complementary (structure vs. time). All
run in-house; the vault stays source of truth and the Audit + sign-off gate still hold.

---

> **Parts O–S below are the trust / learning / meaning upgrades** added after two
> independent senior audits (`RISK_AND_GAPS_AUDIT.md` + a second-opinion review) and the
> owner's directive for an independent audit layer with human accountability. They are
> sequenced into the roadmap above (Phases 4, 6, 8, 11) — they are not optional extras.

---

# PART O — THE AUDIT & HUMAN-ACCOUNTABILITY LAYER (the last line of defense)

**Why this exists.** The stakes are millions of dollars. A confident *wrong* number that
reaches the CEO and HQ — and gets approved — is a factory-scale disaster. Therefore **no
report reaches a human decision-maker without (1) passing an independent audit and (2) an
explicit, accountable human sign-off.** This is the **maker-checker / four-eyes** control
that finance has used for a century, made into an architectural layer. The system's job
is not to decide — it is to make the *human's* decision **informed, safe, and on the
record.** The human carries the responsibility; the audit layer makes that responsibility
defensible.

```
  CREATION (engines → governed metrics → synthesis → DRAFT card)
        │
        ▼   independent process · different code path · ideally a different model
  ┌─────────────────────  AUDIT LAYER  ─────────────────────┐
  │ O.1 re-run   O.2 reassess   O.3 certainty   O.4 materiality│
  └───────────────┬─────────────────────────────────────────┘
        │ uncertain / high-stakes?
        ▼ yes
  O.5 DEEP MULTIPLE-CHOICE QUESTIONS → the human analyst answers
        │
        ▼
  O.6 ACCOUNTABLE HUMAN SIGN-OFF  (named person · recorded · responsible)
        │  (nothing passes this gate unsigned)
        ▼
  RELEASE to manager / CEO   →   O.8 feeds the LEARNING engine (Part P)
```

### O.1 Independent re-run (four-eyes)
The audit **re-executes the critical calculations by an independent path** (separate
query/code, ideally a separate model) and checks they match the draft **to the cent**.
A mismatch **blocks release** and is flagged. One pipeline can be wrong; two independent
pipelines agreeing is the floor for trust.

### O.2 Logic reassessment
Independently re-checks: reconciliation/conservation (`rows_in == clean + rejected`);
**tie-out to the system of record (SAP official figure)**; no leaked total/subtotal rows;
**every metric uses its governed definition** (Part R); **every claim's citation
re-verified** against real evidence (defeats "hybrid-ghost" fabricated citations); driver
attribution actually supported by the numbers; recommendation consistent with the facts.

### O.3 Certainty scoring (quantified + calibrated)
Produces a **multi-dimensional certainty score** — numbers · drivers · evidence ·
recommendation · data-quality · **materiality** — plus an overall %. It is **calibrated
against history**: when the system said "90% sure," was it right ~90% of the time? The
system must **know what it doesn't know** and **abstain & ask** rather than guess
(selective prediction). A fluent answer is not a correct answer.

### O.4 Materiality-aware escalation
Escalate by **money at stake**, not just error rate. A 0.5% reject pile can be **$2M**.
Rules: low-materiality + high-certainty → light confirm; **high-materiality OR
low-certainty OR sources disagree → mandatory deep review**; very large numbers →
**a second approver** (segregation of duties).

### O.5 Deep human questioning (multiple-choice)
When uncertain or high-stakes, the audit asks the analyst **specific, decision-shaped
multiple-choice questions** — never a vague "is this OK?". Example:
> *"The supplier approval PDF was OCR'd at 62% confidence and drives a **$1.2M** variance.
> Which is correct? (A) $1.2M as read · (B) $1.02M [alternate reading] · (C) open the
> source page · (D) exclude pending human review."*
Answers are recorded **and feed learning** (Part P). This is your requirement: the human
is pulled in *precisely where the machine is unsure*, with the question pre-digested.

### O.6 Accountable human sign-off (the hard gate)
Before release, a **named human approves.** The system records **who, when, what they
were shown, what they changed, and the certainty at approval** — tamper-evident,
audit-grade. **Nothing reaches the CEO without this signature.** A recommendation only
becomes an authorized *decision* at this gate (this *is* the G.4 boundary, enforced).
**Responsibility is explicit and human.**

### O.7 Disaster-prevention guarantee
Because the audit is **independent of the creator**, a single mistaken pipeline cannot
silently reach HQ. The layer's whole purpose is to convert *silent confident wrongness*
into *visible, questioned, signed* output.

### O.8 It makes the system wiser over time
Every flag, every answered question, every human correction, every rejected draft →
**error memory + skill/method update** (Part P, risk-tiered + injection-quarantined).
Next month the audit is sharper and asks **fewer, better** questions. That is
"learn by doing / gain experience," applied to the control itself.

---

# PART P — THE LEARNING ENGINE (skills, memory, self-correction)

The system must **learn from its mistakes**, not wait for the human to fix the same thing
three times. Grounded in the field's best work (Voyager skill libraries; Hermes
self-created skills + DSPy/GEPA self-evolution; Letta/Zep/Mem0 memory; Reflexion
self-correction). Full analysis in `RISK_AND_GAPS_AUDIT.md`.

- **Four memories:** *episodic* (every Q&A/decision trace), *semantic* (governed facts +
  the metric layer + the wiki), *procedural* (**skills**), *working* (per task).
- **Skill library:** after a successful non-trivial task the agent **proposes a skill**
  (the validated SQL/method + "when to use"). A skill is **not free text it trusts** — it
  is validated by tests + the verifier + **human approval**, then versioned and retrieved
  (FTS/vector). The monthly close gets faster and more reliable each cycle.
- **Error memory + reflection:** the audit's catches and the human's corrections become
  durable records (*symptom · root cause · fix*); before finalizing, the agent checks
  "have we been wrong this way before?"
- **Outcome tracking** (your "did the action work?"): link each decision → later actuals;
  learn which drivers/recommendations were actually right.
- **Gated self-evolution (DSPy + GEPA):** optimize prompts/skills offline against the
  golden set — **never auto-deployed**; every change passes eval + human sign-off, and is
  versioned/rollback-able.
- **Risk-tiered promotion:** formatting preference → auto after test; **report method →
  human approval; finance calculation / metric / access rule → owner approval.**
- **⚠️ Zombie-agent defense:** anything learned from *document-derived* content is
  **quarantined and human-approved** before entering skills/memory — a prompt injection in
  an email must never silently write a poisoned skill. Learning is sandboxed from
  untrusted input.

---

# PART Q — THE LLM-WIKI VAULT (Karpathy / Obsidian pattern)

Upgrades the second brain (`IMPLEMENTATION_PLAN_SECONDBRAIN.md`) into a three-tier design:

1. **Immutable raw sources** — SAP exports, documents, emails, screenshots, approvals,
   source snapshots. **Never rewritten.** The forensic record.
2. **AI-maintained Markdown wiki** — pages for entities, metrics, methods, decisions,
   risks, actions, lessons, synthesis. The AI maintains it, but **every claim carries
   provenance** (`extracted` / `calculated` / `inferred` / `human-approved` / `ambiguous`)
   and a link to evidence. Inferred never becomes fact without approval.
3. **Disposable indexes** — FTS + vector + graph, **rebuildable from tiers 1–2 anytime.**

Plus a `.manifest.json` (source tracking), `index.md` / `log.md` / `hot.md` (navigation),
and a **`wiki_lint` gate** (no broken links, no page without frontmatter, no claim without
provenance, no source ingested without a manifest entry). **Borrow the patterns** from
Karpathy's LLM-wiki gist, `Ar9av/obsidian-wiki`, and `obsidian-second-brain` — **do not
fork** any of them (same reasoning as Hermes, Part 7 of the audit).

---

# PART R — GOVERNED MEANING (semantic metrics + factory ontology)

The federation promise dies if "cost / margin / scrap / yield" mean different things per
department or file. `column_map.yaml` maps *columns*; this layer governs *meaning*.

- **Semantic metrics layer (v1):** every KPI defined **once** — name · business
  definition · formula · grain · required dimensions · currency · sign convention · time
  basis · owner · tests · examples. The Router resolves "variance/margin" to its
  **governed definition before any SQL runs.** Pattern: **dbt Semantic Layer** or **Cube**
  (Cube even ships an MCP server + row-level access — a natural fit).
- **Factory ontology (v2, for federation):** an ISA-95-inspired shared vocabulary
  (plant · area · line · work-center · material · BOM · order · cost-center · supplier · …)
  so department lenses share nouns. **v1 needs only the finance metric layer + a few
  shared dimensions** — full ontology is reserved for the federation phase (avoid the
  cathedral).

---

# PART S — FURTHER UPGRADES (concise register; detail in `RISK_AND_GAPS_AUDIT.md`)

| Upgrade | What | Phase |
|---|---|---|
| **In-house synthesis** | On-prem model (vLLM) by default — resolves the G.5 vs K contradiction | 0 |
| **Confidence v2** | Multi-dimensional + **materiality-weighted rejects** (by $ amount, top rejected rows by value; "cannot finalize if rejected amount > threshold") | 3, 5 |
| **Observability / replay** | Trace-id per question, evidence-bundle id, prompt/model/data-snapshot versions (OpenTelemetry GenAI) — debug a live wrong answer | 0, 12 |
| **Data contracts + lineage** | Per-source contracts (cols/types/grain/PK/freshness/owner) + OpenLineage-style lineage + data-quality checks (Great Expectations/Pandera) | 2 |
| **Source adapters** | Excel-export adapter now; **SAP OData / DB-view / delta loads later** — don't hardwire manual exports forever | 1 |
| **Security threat model** | Prompt injection (retrieved text = data, never instructions), Excel/CSV formula injection, file sandboxing, **RBAC tests**, audit logs (OWASP LLM Top-10, NIST GenAI) | 0, 12 |
| **One-A4 doctrine** | BLUF + Minto + SCQA, **hard length budget enforced in code**, progressive disclosure, IBCS-style visuals | 5 |
| **Hybrid retrieval + rerank** | BM25 + dense + local cross-encoder reranker (fixes retrieval mismatch) | 9 |
| **Deployment / DR** | Local or shared-server deploy, backup/restore, scheduled jobs | later |
| **Scope discipline** | ISA-95 / OPC UA / Sparkplug / DataHub / full Dagster are **"reserve space," not v1** — prove the finance loop first | — |

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
card end-to-end, **then the independent Audit & sign-off layer (Part O), then the Learning
loop (Part P)** — make the numbers *trustworthy, accountable, and self-improving* before
touching documents/email/OCR, which come last because they are harder and lower-certainty.

**Non-negotiable:** because a wrong number reaching the CEO/HQ is a million-dollar
disaster, the **independent audit + accountable human sign-off (Part O)** is part of the
definition of done, not a later nicety. The system proposes and checks; **a named human
approves and owns the decision.**

**Next concrete step:** hand Part L Phase 0 to Codex with the instruction *"scaffold
the repo, write every `AGENTS.md`, define the contracts in `/shared/contracts`, and
write the failing tests — implement nothing yet."* That produces the skeleton the cheap
models then fill, card by card. Say the word and I'll prepare that exact Codex hand-off
brief.
