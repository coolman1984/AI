# Executive Assistant Master Plan (v1 — draft for adversarial review)

Author: Fable (lead). Status: DRAFT — under review by deep-reasoner (Opus) and
Codex. Not yet approved by the owner. Supersedes nothing until agreed.

## 0. Mission (what this system is becoming)

The owner leads AI transformation at a TV/Mobile factory under a Korean HQ.
This project grows from a finance-pilot "trusted numbers" tool into his **main
executive assistant** with three jobs:

1. **Trusted numbers** — exact, audited, human-signed calculations (exists today,
   synthetic-data-proven only).
2. **A knowledge engine that never loses anything** — ingest every HQ workflow
   deck (Korean PPTX ~50 slides), other factories' reports, and internal
   documents; translate, extract the process logic, store it permanently with
   citations, track how it changes over time, and combine old + new knowledge
   into new ideas.
3. **Decision support** — turn (1) + (2) into evidence-backed briefs the owner
   uses with senior managers, the CFO, and the CEO.

Audiences: the owner first; through him, senior managers / CFO / CEO. Nothing
reaches them without audit + named human sign-off (existing rule, unchanged).

## 1. Inherited non-negotiables (unchanged)

Golden Rule (AI reads maps, engines read volumes) · Calculation-Integrity (no
generated numbers) · Decision-Memory (every result stored with evidence) · tests
gate every change · one branch `main` · two-tier privacy (D14: HQ workflow docs
may use cloud AI; factory data never leaves the machine).

**New addition:** the two-tier privacy rule must move from documentation into
**code** (see Pillar 5). A policy that isn't enforced by code will eventually be
violated by accident.

## 2. The five pillars

### Pillar 1 — Trust spine (exists; harden, don't rebuild)
The finance loop (ingest → clean → variance → card → audit → sign-off) is the
strongest asset. Work here is: finish IS2.3 (multi-sheet Excel) and IS2.4 (type
inference), and run the first REAL export (P2.2) the moment it arrives. Real
data remains the single most important unblocking event in the project.

### Pillar 2 — Knowledge engine ("never lose anything")
- **Intake:** add a native PPTX extractor (input side — today python-pptx is
  used only for output) producing the same `Document` shape as the existing PDF
  path. PDF text + OCR cascade already exist.
- **Understanding:** an LLM layer (the `LLMBridge` design already drafted in
  `engines/docs/report_reader.py`) that translates Korean → English and extracts
  a structured **WorkflowRecord**: purpose, steps, roles/owners, KPIs, what
  changed vs. the previous version, open questions — every element cited to its
  slide/page.
- **Claims vs. facts separation (critical):** LLM output is stored as **claims
  with citations**, in a separate class from audited numbers. A claim that
  quotes a figure is verified verbatim against the source text before storage;
  uncited claims are rejected. The Calculation-Integrity rule stays intact: the
  LLM layer can *summarize and translate*, it can never *originate* a number
  into the trusted stores.
- **Storage:** keep the flat JSON knowledge store for now (it is 20KB — fine);
  add a lightweight **document registry** (what was ingested, when, from where,
  tier, version-family). Define a measurable gate (≈50 documents or visible
  slowdown) at which indexing / graph memory (Cognee/Graphiti, task T9) becomes
  justified. Do not build heavy memory infrastructure before the gate.
- **Versioning:** workflows belong to **families** (HQ process X: v1, v2 …).
  The existing temporal memory records changes; a diff view answers "what did HQ
  change since last rollout?"

### Pillar 3 — Comparison & synthesis
- **Factory/report comparison:** side-by-side views over WorkflowRecords and
  report knowledge. Practice corpus: the 18 public Samsung IR PDFs already on
  disk (2024–2026 quarterlies) — quarter-over-quarter comparison proves the
  temporal value with zero privacy risk.
- **Idea synthesis:** cross-link related workflows; surface contradictions
  rather than merging them; generate "synthesis briefs" that are explicitly
  labeled AI-SUGGESTED IDEAS (with citations to their inputs), never facts.

### Pillar 4 — Executive interface
- **Decision brief:** one page per decision — the question, evidence (every
  item cited), options, risks, recommendation, sign-off line. This generalizes
  the existing card + audit machinery beyond finance.
- **Meeting pack:** for a CFO/CEO meeting — relevant numbers from the trust
  spine, relevant workflow knowledge, open risks, suggested talking points.
- Existing HTML dashboard and PPTX export are reused as the rendering layer.

### Pillar 5 — Safety rails in code (new)
- `gov/privacy.py`: every document in the registry carries a tier; **default =
  Tier 1 (in-house only)** unless the owner explicitly marks it Tier 2. The
  LLM bridge refuses Tier-1 content at the code level. Every external call is
  logged (what, when, which model, tier check result) to an auditable ledger.
- **Claims ledger:** every LLM-generated statement stored with source citation,
  model, and date; storage API rejects uncited claims.
- `mcp_server` enforces `gov/access.py` scoping at dispatch (currently not
  visibly enforced — review finding).

## 3. Operating model (the AI team building this)

Roles: Fable plans/directs (minimum tokens) · deepseek-flash writes (fallback:
deepseek-pro when throttled) · deepseek-pro reviews · sonnet-reviewer is the
final gate (tests + rules + diff) · Opus + Codex give opinions on high-stakes
calls only. Discipline fixes from the review:
- **No code without a task-queue row.** (report_reader was written outside
  governance — that stops.)
- Throttling is on the critical path twice (build-time writer + runtime LLM
  bridge): both must have configured fallback model order, and ingestion runs
  must be resumable.

## 4. Phases and gates

- **Phase A — Rails & housekeeping (first).**
  Consolidate the 38 planning docs into three tiers (MASTER_PLAN / 00_control
  live state / per-module AGENTS.md); archive the ~9 stale top-level plans.
  Repair `report_reader` (implementation is mission-correct; rewrite its stale
  tests to match), give it a task-queue row, commit. Build `gov/privacy.py` +
  document registry + claims ledger. GATE: full suite green; privacy gate has
  tests proving Tier-1 content cannot reach the LLM bridge.
- **Phase B — First HQ deck end-to-end.**
  PPTX input extractor (install python-pptx as an input dependency; keep the
  Docling adapter gated as-is). Run ONE real Korean HQ deck: extract → translate
  → WorkflowRecord → stored knowledge → a one-page brief. GATE: the owner reads
  the brief next to the original deck and judges it genuinely useful and
  faithful. This gate is subjective on purpose — he is the user.
- **Phase C — Corpus & comparison.**
  Ingest the Samsung IR corpus (18 PDFs). Build the registry views + comparison
  (quarter-over-quarter first, then factory-vs-factory when other factories'
  reports arrive). GATE: a comparison brief the owner would actually show a
  colleague.
- **Phase D — Decision briefs & meeting packs.**
  Generalize card+audit into the decision-brief format; meeting pack assembly.
  GATE: owner uses one in a real management meeting.
- **Phase E — Real factory export (parallel, whenever it arrives).**
  P2.2 profiling + IS2.3/IS2.4 hardening on real SAP data. This track outranks
  B–D the day real data lands.
- **Phase F — Scale-up (gated, later).**
  Knowledge indexing / graph memory (T9), Korean OCR improvement, on-prem LLM,
  scheduled ingestion, backup/DR, enterprise search (T10/T11). Each item has a
  numeric trigger, not a date.

## 5. Hard cases and their defenses

1. **Scanned/image-only Korean deck** — OCR cascade is weak on Korean today →
   route to human-review queue; add Korean language data to the OCR engines;
   VLM adapter only in Phase F.
2. **Deck too large for one LLM call** — chunked map-reduce summarization with
   per-chunk citations, merged with a coverage report; never silently truncate
   (warnings are mandatory, already designed into report_reader).
3. **LLM invents a step/figure** — verbatim-figure verification + mandatory
   citations + rejection of uncited claims + audit-layer spot-samples of claims
   against sources.
4. **HQ v2 contradicts v1** — family versioning + diff view; contradictions are
   surfaced to the owner, never auto-merged.
5. **Two factories define a KPI differently** — metric-definition registry
   (MASTER_PLAN Part R already envisions this); comparison output marks
   "not directly comparable" instead of pretending.
6. **Mixed-sensitivity document** (HQ deck containing our factory's numbers) —
   intake defaults to Tier 1; the owner explicitly marks Tier 2 per document;
   the safe default protects against mistakes.
7. **Provider throttling mid-run** — resumable ingestion runs; configured
   fallback order across models; build pipeline has the same fallback rule.
8. **Fable token exhaustion** — delegation rules already in CLAUDE.md; session
   state persisted to 00_control/restart_notes.md so any session can resume.
9. **Mistranslated critical Korean term** — a growing Korean↔English factory
   glossary file fed into every translation prompt; low-confidence terms
   flagged; owner spot-checks early decks until trust is earned.
10. **Knowledge loss/corruption** — knowledge artifacts written as markdown and
    committed to git (durable, diffable, human-readable); .brain JSON backed up
    in Phase F; git history is the ultimate undo.
11. **A brief reaching the CEO without sign-off** — the audit + named-sign-off
    gate applies to ALL executive outputs, not just finance cards; enforced in
    serving, tested.
12. **Model/provider disappears or reprices** — LLMBridge abstraction keeps the
    system swappable in one place.

## 6. Explicitly NOT doing yet

Enterprise search before retrieval pain is real · self-learning before a golden
evaluation set exists · natural-language Q&A chat before storage+calc are proven
on real data · multi-department rollout before the pilot department is trusted ·
heavy graph/memory infra before the document-count gate.

## 7. Success measures

- HQ deck → owner-ready one-page brief in under one hour, every claim clickable
  to its slide/page.
- Zero uncited claims in storage; zero Tier-1 content in the external-call
  ledger (auditable).
- Quarter-over-quarter comparison brief from the Samsung corpus the owner would
  show a colleague.
- The owner walks into a CFO/CEO meeting with a meeting pack from this system —
  and comes back saying it held up.

## 8. Open questions for the reviewers (Opus + Codex)

- Is the claims-ledger design strong enough to protect the no-invented-numbers
  rule once an LLM layer exists, or does it need a harder boundary (separate
  store, separate API, separate audit pass)?
- Is Phase A too big? Should doc consolidation be deferred to keep momentum on
  Phase B (the owner's most-wanted feature)?
- WorkflowRecord schema: what fields are missing for "combine old+new knowledge
  into new ideas" to actually work later?
- Anything here that contradicts MASTER_PLAN.md in a way that matters?
