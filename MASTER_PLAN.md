# MASTER_PLAN.md — The Decision Intelligence System

> **What this document is.** The other plans in this repo describe three *engines*
> (numbers, documents, memory). This document is the **spine** that turns them into
> one product: a system that reads the mountain of files a manager can't, and hands
> back — in a few words — the headline, the drivers, the risks, the recommended
> action, the evidence, and how much to trust it.
>
> It is written in two registers. **Part A is for the decision-maker** (plain
> language: what it does, why to trust it). **Parts B–H are for the coding agent**
> (architecture, tool contracts, phases). Read Part A once; build from B onward.

---

# PART A — THE VISION (plain language)

## A.1 The problem we are removing

A manager in **any department** of a large TV-and-mobile factory drowns in inputs:
huge SAP Excel exports (one file can reach ~200 MB), long PDFs, approval workflows,
tens of emails, Word documents, sales tables, decks. The cost is not just time. It is
**missed signal**: the variance nobody decomposed, the risk buried on page 40, the
defect trend nobody linked to a supplier change, the fact that *this same problem
happened two quarters ago and we already know the fix.*

## A.2 What the system delivers instead

For any question — or, later, *before* you even ask — the manager gets one tight card:

| Section | Meaning |
|---|---|
| **Executive headline** | One clear answer, in one sentence. |
| **Key numbers** | Calculated facts only — never estimated by an AI. |
| **Main drivers** | What actually caused the movement (price / quantity / mix / fx / …). |
| **Risk / opportunity** | Why management should care. |
| **Recommended action** | What to do next. |
| **Evidence** | Exact source: file, sheet/page, rows/tables, and the calculation used. |
| **Confidence** | High / Medium / Low, derived from data quality — not vibes. |

## A.3 The one rule that makes it trustworthy

> **Numbers come from calculation. Text understanding may use AI. Every claim cites
> its source. No summary omits its confidence.**

A confident wrong number is the only failure that matters here, because the manager
can't check it. Everything in Parts B–H exists to make that failure *structurally
impossible*, not merely unlikely.

## A.4 Who it serves — the whole factory, department by department

This is a **factory-wide** brain, not one department's tool. Every department —
Production, Quality, Supply Chain, Procurement, Planning, Maintenance, Engineering,
Warehouse, Sales, Finance/Controlling, HR, EHS, After-sales — gets its **own second
brain first**. Then those department brains are **federated into one factory brain**
so the CEO and CFO can see and decide across all of them (§B.4).

Each manager's recurring workflow is a **playbook** on the shared engines (§G.1);
each department is an **isolated, access-scoped namespace** (§G.2). One platform,
many brains — not many apps.

---

# PART B — THE ARCHITECTURE: MCP-FIRST

## B.1 The decision that shapes everything

This application is **not a chatbot**. It is a **toolbox** — an **MCP server**
(Model Context Protocol) exposing a clean, professional set of tools. Any AI agent
(Claude, Codex, an in-house agent) connects to it and *drives* the tools. The agent
reasons and writes prose; the tools do the exact, auditable work.

```
        ┌─────────────────────────────────────────────────────────┐
        │   ANY AI AGENT  (Claude / Codex / …)  — the ORCHESTRATOR  │
        │   routes questions, calls tools, composes the summary.    │
        │   MAY compose language.  MAY NOT originate facts.         │
        └───────────────────────────┬─────────────────────────────┘
                                     │  MCP (tool calls in / results out)
        ┌───────────────────────────▼─────────────────────────────┐
        │            THE APPLICATION  =  ONE MCP SERVER             │
        │  a catalog of deterministic, testable, auditable tools    │
        ├───────────────┬───────────────┬───────────────┬──────────┤
        │  DATA ENGINE  │  DOC ENGINE   │ INSIGHT BRAIN │ OUTPUT &  │
        │  (numbers)    │  (text)       │ (memory)      │ QUALITY   │
        └───────┬───────┴───────┬───────┴───────┬───────┴────┬─────┘
                │               │               │            │
          staging DB      doc index        vault + index   summary
          (DuckDB)        (search)         (MD + pgvector)  contract
```

## B.2 Why MCP-first is the correct call (not a fashion)

- **It turns your trust rule into a wall.** The agent literally has no tool that
  returns a number except the Data Engine. It *cannot* hand-roll a total; it can
  only call `data.query` and report what came back.
- **Separation of deterministic vs generative.** Calculations, SQL, search, and
  storage are code — tested, repeatable, identical every run. Only language is
  generated. The two never blur.
- **Reusable by any agent, today and later.** Claude today, a cheaper model
  tomorrow, an autonomous monitoring agent next year — all speak MCP. You build the
  capability once.
- **Auditable.** Every answer is a sequence of tool calls with inputs and outputs.
  That trace *is* the evidence trail in §A.2.

## B.3 The trust boundary (the single most important diagram)

```
   AI may ORIGINATE:   prose, structure, the choice of which tool to call.
   AI may NEVER ORIGINATE:   a number, a quote, a citation, a confidence score.
   ─────────────────────────────────────────────────────────────────────────
   Every number      → produced by  data.*      (and carries the query that made it)
   Every quote/page  → produced by  docs.*      (and carries file + page/table ref)
   Every past fact   → produced by  brain.*     (and carries the vault file ref)
   Every summary     → validated by report.make_manager_summary, which REJECTS
                       any numeric claim lacking a tool-produced evidence ref.
```

If a summary contains a number with no attached evidence ref, the output tool
refuses to emit it. That refusal is the whole guarantee.

## B.4 Department brains, then the factory brain

The unit of rollout is the **department**. Each department gets its **own second
brain** — its own scoped slice of the *same* shared engines:

- its own **vault namespace** (the forever archive of its notes/records/decisions),
- its own **staging + index** (its numbers and its documents),
- its own **playbooks** (its recurring workflows),
- its own **access scope** (who in that department may see what).

You do **not** build a separate app per department. You build **one platform** that
hosts many department brains. Onboarding a department = *configuration* (its sources,
playbooks, roles), never new code.

```
   Production │ Quality │ Supply Chain │ Procurement │ Planning │ Maintenance
   Engineering │ Warehouse │ Sales │ Finance/Controlling │ HR │ EHS │ After-sales
        each = one DEPARTMENT BRAIN  (scoped vault + index + playbooks + access)
                                  │
                   ┌──────────────▼───────────────┐
                   │        THE FACTORY BRAIN       │
                   │  federation OVER the department │
                   │  brains, governed by access:    │
                   │  CEO / CFO see across;           │
                   │  a dept manager sees their scope.│
                   └────────────────────────────────┘
```

**Why department-first, then federate.** A department brain is provable and useful on
its own — it earns trust fast and keeps the data bounded. The factory brain is then a
*retrieval layer over the department brains*, not a 13th pile of data. And it is
exactly where leadership's real value lives: the questions that **cross** departments
— *"did the panel shortage in Supply Chain cause the Quality rework spike and the
Sales commit miss?"* — which no single department's files can answer alone.

---

# PART C — THE THREE ENGINES (build specs already exist)

These are the existing plans, reframed as MCP-exposed engines:

| Engine | What it owns | Build spec | Source-of-truth principle |
|---|---|---|---|
| **Data Engine** | Exact numbers from Excel/CSV/SAP | `IMPLEMENTATION_PLAN.md` | DuckDB staging; heavy math in SQL; rejects + run.log |
| **Document Engine** | Text/tables from PDF/Word/PPT | `IMPLEMENTATION_PLAN_DOCS.md` | one normalized JSON per doc; OCR for scans; `schema/document.schema.json` |
| **Insight Brain** | Durable memory + retrieval | `IMPLEMENTATION_PLAN_SECONDBRAIN.md` | Markdown vault = archive; Postgres/pgvector = disposable lens |

`ARCHITECTURE.md` states the founding principle behind all three: *the AI reads a
map of the data, never the data.* MCP-first is that principle enforced in wiring.

## C.1 The scale & SAP reality (why the engines are built this way)

The inputs are not toy files. A single SAP raw export can be **~200 MB of Excel**,
there are many of them across every department, plus heavy PDF / Word / email /
approval-workflow volume. Two consequences, already baked into the engine specs:

- **Never load a 200 MB sheet into memory or into an AI prompt.** The Data Engine
  lands it text-first into DuckDB (streamed/chunked) and does all heavy math in SQL
  that spills to disk. An AI only ever sees the tiny profile and the small aggregated
  result — never the rows.
- **SAP exports are messy in predictable ways.** ALV-grid junk rows, embedded
  subtotal/total rows, the header on row 4 not row 1, UTF-16/Latin-1 encodings,
  locale decimals (`1.234,56`), and layouts tied to the transaction it came from
  (MB51, COOIS, KSB1, …). `data.ingest_table` must strip the junk, detect
  encoding/locale, and **record every assumption in the run log — never silently.**
  This is precisely the messy-data defense in `ARCHITECTURE.md` §3.

---

# PART D — THE MCP TOOL CATALOG (the technology, made concrete)

This is the public surface of the application. Tools are grouped by engine. Each is
deterministic, returns structured JSON, and — where it returns a fact — returns the
**evidence ref** that produced it. Names are the contract; do not rename.

### D.1 Data Engine — `data.*`  (numbers; the only source of numbers)

| Tool | Does | Returns (incl. evidence) |
|---|---|---|
| `data.ingest_table(path)` | Land Excel/CSV/SAP export into staging DB (text-first, chunked, idempotent) | `table_id`, rows_in, rows_landed |
| `data.profile_table(table_id)` | Build the tiny schema map (cols, types, nulls, ranges, weird values, date range) | `schema_profile` |
| `data.classify_file(profile)` | Label the file: monthly-close / budget / cost-rollup / variance / … | `file_type`, confidence |
| `data.query(spec)` | Run an aggregation **in the engine** (group/sum/join) | `result` + **the exact SQL** + row counts |
| `data.compute_variance(actual, baseline, dims)` | Decompose Δ into **price / quantity / mix / usage / scrap / fx / timing** | variance bridge + per-driver contribution + SQL |
| `data.reconcile(report)` | Conservation checks: rows_in == clean + rejected; totals tie | pass/fail + discrepancies |

### D.2 Document Engine — `docs.*`  (text; the only source of quotes/pages)

| Tool | Does | Returns (incl. evidence) |
|---|---|---|
| `docs.ingest_document(path)` | Normalize PDF/Word/PPT → one JSON (reading order, tables, OCR for scans) | `doc_id`, warnings |
| `docs.profile_document(doc_id)` | Topics, doc type, key entities, page/slide count, OCR confidence | `doc_profile` |
| `docs.search(query, filters)` | **Hybrid** keyword + semantic search over the corpus | passages + **file + page/table ref** each |
| `docs.get_passage(ref)` | Fetch the exact cited text/table for evidence | passage text/table |

### D.3 Insight Brain — `brain.*`  (durable memory; the only source of past facts)

| Tool | Does | Returns |
|---|---|---|
| `brain.upsert_note(...)` / `brain.link(...)` | Write to the Markdown vault (truth) + reindex | vault path |
| `brain.search(query)` | Hybrid (+ later graph) search across all stored knowledge | notes + vault refs |
| `brain.save_decision(record)` | Store a **decision-memory** item (§E) with evidence + confidence | decision_id |
| `brain.recall(query)` | "What did we do last time?" / "all foam cost issues" | past decisions + evidence |
| `brain.detect_recurrence(pattern)` | Surface "same pattern happened in Q2" | matching prior episodes |

### D.4 Orchestration, Output & Quality — `route.* / report.* / quality.*`

| Tool | Does |
|---|---|
| `route.classify_question(q)` | number / document / knowledge / mixed → which engines to use |
| `quality.data_quality_score(inputs)` | High/Med/Low from rejects, missing cols, OCR confidence |
| `report.make_manager_summary(payload)` | Assemble the §A.2 card; **reject any number without an evidence ref**; attach confidence |

### D.5 Early Warning — `watch.*`  (v2; proactive, not reactive)

| Tool | Does |
|---|---|
| `watch.define_metric(spec)` | Register a metric to track (e.g. material cost vs budget per plant) |
| `watch.set_threshold(metric, rule)` | When to raise a flag (abs/%, trend, recurrence) |
| `watch.scan()` | Run all watches on the latest data; emit warnings *before* anyone asks |

---

# PART E — DECISION MEMORY (the part that makes it valuable)

The brain stores **decisions, reasons, and evidence — not files**. Every useful
result becomes one or more typed records, each linked to its evidence:

| Record type | Example | Originated by |
|---|---|---|
| **Fact** | "TV material cost rose USD X vs budget." | `data.*` (calculated) |
| **Driver** | "Mainly LCM price + quantity mix." | `data.compute_variance` |
| **Risk** | "Margin impact continues if BOM price holds." | agent, from facts |
| **Recommendation** | "Negotiate supplier; review part A." | agent (clearly marked *proposed*) |
| **Decision** | "Management **approved** supplier negotiation." | **human-signed** (§G.4) |
| **Action** | "Procurement to review part A by month-end." | human-assigned, tracked to close |
| **Lesson** | "Same pattern occurred in Q2 — fix was X." | `brain.detect_recurrence` |

**Recommendation ≠ Decision.** The system *proposes*; a human *decides*. Only a
human-signed decision becomes a fact the brain treats as settled (§G.4). Without
this line, the brain starts believing its own suggestions.

---

# PART F — THE LOGIC FLOW (yours, mapped onto tools)

```
1. COLLECT     user drops Excel / PDF / Word / PPT / SAP export
2. CONVERT     data.ingest_table   |  docs.ingest_document
3. PROFILE     data.profile_table  |  docs.profile_document        (the tiny map)
4. UNDERSTAND  data.classify_file  |  docs.profile_document.topics (what is this?)
5. ROUTE       route.classify_question  → numbers / docs / memory / mixed
6. QUERY       data.query / data.compute_variance | docs.search | brain.recall
7. QUALITY     quality.data_quality_score
8. SUMMARIZE   report.make_manager_summary   (the §A.2 card, citations enforced)
9. STORE       brain.save_decision (+ upsert_note)   → the Second Brain
10. RETRIEVE   later: brain.recall / brain.search / detect_recurrence
(v2) WATCH     watch.scan  → proactive early warnings, before step 1
```

The manager experiences steps 8 and 10. Everything else is the machine being honest.

---

# PART G — THE UPGRADES BEYOND THE ORIGINAL PLAN

These are the gaps that separate "useful finance tool" from "company-wide brain."

### G.1 Playbooks (how one tool serves all managers)
A **playbook** is a named, reusable workflow on the engines: which files it expects,
which queries/variances it runs, which summary template it fills, what it watches.
- `monthly_close` (v1), then `sales_pipeline`, `supply_risk`, `ceo_briefing`, …
- New manager = new playbook (config), **not** new system. This is the scale path.

### G.2 Access control (day-one constraint)
Every record and file carries an **owner/scope** (plant, department, region). Tools
filter by the calling user's role: a plant manager sees one plant; the CEO sees all.
Wired into `data.query`, `docs.search`, and `brain.*` from the start — retrofitting
row-level security later is painful and dangerous.

### G.3 Early warning (proactive layer — v2)
The original flow is reactive (ask → answer). "Early warning" means the system
speaks first: `watch.*` scans new data against thresholds and recurrence patterns
and pushes a flagged summary card. This is a distinct phase, not a tweak.

### G.4 Human-in-the-loop sign-off
A recommendation is `proposed`; it becomes a `decision` only when a human approves
it (signature + timestamp recorded). The brain distinguishes the two forever.

### G.5 Evaluation harness (or you never *know* it's right)
Per the research cited (Haystack): test **retrieval and calculation separately**, on
a fixed set of known-answer questions, every release. A "golden set" of e.g. 30
finance questions with hand-verified answers gates every change. Retrieval can be
wrong while the prose sounds perfect — only the harness catches that.

---

# PART H — ROADMAP (build the platform once, roll out by department)

> Rule kept from the engine specs: **do not start a phase until the previous phase's
> Definition of Done is green**; a trust gate is part of every DoD. The platform is
> built once (Phases 0–4); departments are then onboarded by *configuration*
> (Phase 5+), and the factory brain federates over them (Phase 6).

### Phase 0 — Foundations
MCP server skeleton + config that is **multi-department from line one**: department
namespaces, roles/access scopes, model + embedding-model names, locale. One trivial
tool callable end-to-end from an external agent.
**DoD:** an agent can list and call a tool over MCP, scoped to a named department.

### Phase 1 — Data Engine + trust wall (at SAP scale)
`data.ingest_table → profile_table → query → compute_variance → reconcile` on real
~200 MB SAP exports (streamed, SQL-in-engine, SAP junk stripped). Evidence ref on
every number, per `IMPLEMENTATION_PLAN.md`.
**DoD:** a 200 MB file ingests without running out of memory; a calculation
reconciles to the cent; `data.reconcile` passes; rejects + run.log visible.

### Phase 2 — Pilot department: one brain, end-to-end  *(the proof)*
Stand up **one department's** brain fully: its files → its playbooks → a manager
card → saved decision, all scoped to that department. **You choose the pilot**
(criteria in §My Recommendation). This proves the *platform* — it does not make the
product that department's app.
**DoD:** for one real period, that department's card is correct, fully cited,
confidence-scored, and retrievable later via `brain.recall`.

### Phase 3 — Document Engine
`docs.ingest_document → search → get_passage` per `IMPLEMENTATION_PLAN_DOCS.md`, so
cards cite PDFs, approvals, emails, and decks alongside numbers.
**DoD:** a mixed-evidence card cites a number *and* a page, each verifiable.

### Phase 4 — Insight Brain (durable, department-scoped memory)
Vault (namespaced per department) + Postgres/pgvector index per
`IMPLEMENTATION_PLAN_SECONDBRAIN.md`; full `brain.*`.
**DoD:** delete the index, rebuild from the vault, retrieval identical.

### Phase 5 — Replicate: onboard more departments
Add departments one at a time — each is **configuration** (sources, playbooks,
roles), not new engine code. Enforce role-scoped tools across all of them (§G.2).
**DoD:** two departments give correctly different, correctly scoped answers; a third
onboards with zero engine-code change.

### Phase 6 — The factory brain (federation, for CEO/CFO)
Cross-department retrieval over the department brains, governed by access (§B.4).
**DoD:** a cross-department question (supply → quality → sales) returns one card
citing evidence from each department, respecting the asker's access scope.

### Phase 7 — Early warning (proactive)
`watch.*`: thresholds, recurrence, proactive cards per department and factory-wide.
**DoD:** a planted regression in new data raises a flagged card with no human asking.

### Phase 8 — Advanced retrieval (GraphRAG, later)
Relationships + community summaries for broad "themes across the whole factory"
questions (the cited GraphRAG work). **Only after** the core loop earns its keep.

---

# MY RECOMMENDATION (the sharp answer)

**Build the shared platform once, then prove it on ONE pilot department — your
choice — before rolling out to all of them.** This is *not* "a finance app." The
architecture in Parts B–G is factory-wide and department-agnostic; a pilot is simply
*where you prove the platform is right* before betting a dozen departments on it.
Trying to onboard every department at once means nothing becomes trustworthy and the
whole effort stalls. Department-first, then federate, is exactly your instinct — the
pilot is just *which* department goes first.

Pick the pilot on three criteria:
1. **Most pain** — where a manager is drowning worst (fastest visible win, real sponsor).
2. **Most-structured data** — so the pilot proves the engine instead of fighting the
   messiest corner of the factory first.
3. **A willing user** — a manager who will actually use it daily and give feedback.

Every other department is then a **repeat of the same recipe** (Phase 5), and the
CEO/CFO factory brain (Phase 6) is the federation on top.

> The reversible choice is *which* department goes first — Parts B–G do not change
> whichever you pick. Tell me your candidate departments (and where the worst data
> pain is) and I'll rank them, or recommend one.
