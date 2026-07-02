# Executive Assistant Master Plan — v2 (FINAL DRAFT for owner approval)

Author: Fable (lead architect). Version 2, 2026-07-02.
Inputs: full-project review (Sonnet), adversarial critique (Opus — verdict
"SOUND WITH CHANGES", all findings incorporated), owner's vision statements.
Codex review skipped by owner decision. Supersedes v1 in this same file.

---

## 0. Mission

The owner leads AI transformation at a TV/Mobile factory under a Korean HQ.
This system is his **main executive assistant**. It must:

1. **Extract everything** — spreadsheets, SAP exports, PDFs, PPTX decks, emails,
   scans — into governed local databases and the second brain.
2. **Preserve everything forever** — core workflows, process logic, decisions,
   ideas, reports, articles — with citations, versions, and time history. Nothing
   is ever lost.
3. **Understand fast** — a 50-slide Korean HQ deck becomes an English one-page
   brief (every claim linked to its slide) in under an hour.
4. **Combine knowledge continuously** — old + new workflows cross-linked so
   contradictions surface and better ideas emerge, safely labeled as ideas.
5. **Support decisions** — evidence-backed briefs and meeting packs the owner
   uses with senior managers, the CFO, and the CEO.
6. **Serve other AI agents efficiently** — the assistant is packaged as a
   **skill library with tools and a routing map**, so any work agent loads only
   the one skill + tools it needs and spends minimum tokens.

Catastrophic failure mode (design against it everywhere): **a confident wrong
claim or number reaching an executive.**

## 1. Architecture principle: the assistant is a skill library

(Owner's directive.) The system is not one monolithic app an agent must swallow
whole. It is:

- **Skills** — small, single-purpose capability documents (`agent_skills/*.md`,
  which already exist) each describing: purpose, exact tools to call, inputs,
  outputs, invariants, and its edge cases.
- **Tools** — the deterministic engines behind each skill, exposed through the
  MCP server (query numbers, ingest document, search knowledge, render brief…).
- **A map** — one small routing file (`AGENT_SKILL_MAP.md`, exists) that tells
  any agent which skill to load for which task. An agent reads the map (tiny),
  loads one skill (small), calls tools (cheap) — and never loads the whole
  architecture. Token cost per task stays near the minimum possible.

Every new capability in this plan ships as: engine code + tests + a skill card +
a map entry + an MCP tool. That is the definition of "done" for a feature.

## 2. Non-negotiables (inherited + hardened)

Golden Rule (AI reads maps, engines read volumes) · Calculation-Integrity (no
generated numbers — now enforced by a code verifier, not a prompt request) ·
Decision-Memory (every result stored with evidence) · tests gate every change ·
two-tier privacy in **code** (D14) · no code without a task-queue row · one
branch `main` (the lingering `chatgpt-ai-tasks` branch must be explicitly closed
or sanctioned by the owner — currently reality contradicts the rule).

---

## 3. THE 50 MAJOR IMPROVEMENTS

### A. Trust & safety rails (the hard gate before anything touches a real deck)

1. **Deterministic figure verifier.** Code (not prompts) extracts every numeric
   token from every LLM claim, normalizes it (thousands separators, decimal
   marks, percentages), and requires an exact match in the cited page/slide
   text. No match → claim rejected/quarantined. This is THE anti-invention
   guarantee. (Opus CRIT-1.)
2. **Korean-units-aware verification.** The verifier understands 억 (10⁸), 만
   (10⁴), 천 (10³), Korean date and number formats — so "3억 → 300,000" (wrong
   by 1000×) fails verification even though the digits "3" match. (Opus CRIT.)
3. **Physically separate FACTS and CLAIMS stores.** Facts = audited,
   SQL-sourced only. Claims = LLM-originated, different files, different API
   modules. No code path can promote a claim into facts. (Opus §2.1.)
4. **Single LLM chokepoint with a bypass guard.** All LLM calls go through one
   bridge that checks tier → requires citations → runs the verifier → writes
   only to claims. A repo-wide guard test fails the build if any module calls an
   LLM directly. (Opus §2.2 + bypass gap.)
5. **Provenance tags on every number at render time.** Every figure in every
   executive output visibly carries AUDITED-FROM-QUERY or CLAIMED-FROM-DECK
   (with citation). A serving test fails any untagged number or unmarked mix.
   (Opus §2.3.)
6. **Citation-support verification.** The LLM chooses page numbers — that is a
   generated citation, forbidden by AGENTS.md. Code must confirm the cited page
   actually contains the claim's numbers and key terms, else reject. (Opus §2.4.)
7. **Prompt-injection defense as a first-class hard case.** Document text is
   untrusted input: delimit it, instruct against embedded commands, and rely on
   the real backstops — the verifier and the code rule that LLM output can never
   reach the numeric path. Add an injection test deck to the test suite. (Opus
   CRIT; risk R3 has been open since June.)
8. **Privacy tier gate in code (`gov/privacy.py`).** Every document carries a
   tier; default = Tier 1 (in-house only); the LLM bridge refuses Tier-1 content
   at code level. Due to D14 only marked HQ workflow docs may go to cloud AI.
9. **External-call ledger.** Every call that leaves the machine is logged: what
   document, which tier check, which model, when, prompt hash. Auditable proof
   that no Tier-1 content ever left.
10. **Non-numeric audit defined.** The existing audit layer re-runs
    calculations; briefs need an equivalent: a second, independent model
    re-extracts key claims from the same source and citations are re-checked;
    disagreements go to human review. Otherwise "audited brief" is hollow.
    (Opus §4 weak-#11.)

### B. Knowledge engine — ingestion & understanding

11. **Native PPTX input extractor** producing the same `Document` shape as the
    PDF path (python-pptx for input; the gated Docling adapter stays as the
    later upgrade for hard layouts).
12. **Real chunked map-reduce summarization with coverage accounting.** No
    silent truncation ever: every page/slide is covered by some chunk, the merge
    step reports coverage, and if full coverage is impossible the run blocks and
    routes to review. (Opus CRIT-2.)
13. **Repair and commit `report_reader`** (implementation is mission-correct;
    its stale tests get rewritten to match), registered with a task-queue row —
    the first test of the restored discipline.
14. **WorkflowRecord schema** — the structured knowledge unit per workflow:
    purpose, steps, roles/owners, KPIs, what-changed, open questions — every
    field cited to slide/page.
15. **Original-language retention per field.** Korean source text stored beside
    every English field — enables re-translation, dispute resolution, and
    re-verification when models improve. (Opus §3.3.)
16. **Full provenance stamp on every record.** Source file hash, ingest run ID,
    model + version, prompt version, deterministic translation-confidence score
    — so anything can be re-run and re-verified years later. (Opus §3.4.)
17. **Korean↔English factory glossary** fed into every translation prompt;
    grows with each deck; deterministically computed confidence (glossary match
    ratio), never LLM-asked. (Opus governance note.)
18. **Back-translation spot check.** For critical terms/KPIs, translate the
    English back to Korean with a second model and compare; disagreements
    flagged for the owner. Trust gets an objective definition: N consecutive
    decks with zero critical-term corrections. (Opus §4 weak-#9.)
19. **Email + attachment intake** (existing IS5 plan) joins the same spine
    later — same registry, same tiers, same verifier.
20. **Scanned/image-only Korean handling.** Measure the image-only share on the
    first 5 real decks; install Korean OCR language data; if the image-share is
    high, escalate priority of the VLM adapter — otherwise human review absorbs
    it. Decision by measurement, not guess. (Opus HIGH-4.)

### C. Memory, storage & preservation ("never lose anything")

21. **Document registry** — one queryable table of everything ever ingested:
    source, hash, date, tier, version-family, status. The registry is the map of
    the second brain.
22. **Workflow families & versioning.** HQ process X: v1, v2… with valid-time
    (when the process was actually in force) separate from ingest-time —
    bitemporal, so "what was true in Q2 2025?" is answerable. (Opus §3.2.)
23. **"What changed since v1" diff view** per family — the owner's fastest way
    to absorb a new rollout.
24. **Canonical entity IDs / ontology.** Processes, roles, KPIs bound to stable
    IDs (extending the metric registry idea in MASTER_PLAN Part R) so two decks
    naming the same thing differently still link. Synthesis is a graph over IDs,
    not strings. (Opus §3.1.)
25. **Typed cross-workflow edges as first-class data:** depends-on,
    conflicts-with, refines, supersedes — recorded from day one in the flat
    store, ready for a graph DB later. (Opus §3.5.)
26. **Open questions as first-class queryable items** with status
    (open/resolved/by-what). New ideas are born when new knowledge resolves an
    old unknown. (Opus §3.6.)
27. **Decision↔outcome linkage.** Workflow records reference decision-memory
    IDs (the learning engine half-exists); the system can show which past
    choices produced which results.
28. **Knowledge artifacts in git.** Every summary/brief/record written as
    markdown and committed — durable, diffable, human-readable; `.brain` JSON
    backed up on a schedule in the ops phase. Re-ingesting the same deck
    reconciles by file hash instead of duplicating (dedup rule). (Opus HIGH gap.)

### D. Comparison & synthesis (value, carefully staged)

29. **Quarter-over-quarter comparison on the Samsung IR corpus** (18 public
    PDFs already on disk) — proves temporal comparison with zero privacy risk.
30. **Contradiction-surfacing view** over claims: where do two workflows/reports
    disagree? Safer than generative synthesis and immediately useful. (Opus:
    do this INSTEAD of generative synthesis in v1.)
31. **Factory-vs-factory comparison** built only when other factories' reports
    actually exist (cut from the early build — was speculative). (Opus §5.)
32. **Idea-synthesis briefs ("combine old+new into new ideas") ship LAST**,
    gated behind a proven claims boundary, and every output is labeled
    AI-SUGGESTED IDEA with citations to its inputs. High value, highest risk —
    earns its place by the rails built before it.
33. **Knowledge search skill.** Ask "what do we know about process X?" and get
    the linked records, claims (tagged), versions, and open questions — the
    everyday retrieval workhorse that makes the brain feel alive.

### E. Executive outputs & decision support

34. **Decision brief generator** — one page: question, evidence (every item
    provenance-tagged), options, risks, recommendation, sign-off line.
    Generalizes the proven card+audit machinery beyond finance.
35. **Meeting pack assembler** — for a CFO/CEO meeting: relevant audited
    numbers, relevant workflow knowledge, open risks, suggested talking points;
    built from stores, never freestyled.
36. **Report & article generator** — several output types (management report,
    process explainer article, rollout summary) rendered from stored knowledge
    with citations, so knowledge is not just stored but publishable on demand.
37. **Named human sign-off for ALL executive outputs** (extends the finance
    rule), enforced in serving with a test — nothing reaches management wearing
    the system's name without a human owner.
38. **Existing dashboard + PPTX rendering reused** as the presentation layer
    for all of the above (already built and tested).
39. **Owner feedback loop on briefs.** Each brief records the owner's verdict
    (useful / corrected / wrong) — feeding the glossary, the golden set, and
    trust metrics.

### F. Skill library & agent token economy (owner's directive)

40. **Every capability ships as a skill card + map entry + MCP tool** (the
    definition of done — see §1). Existing `agent_skills/` and
    `AGENT_SKILL_MAP.md` become the live catalog, kept in sync by rule.
41. **MCP server enforces access control at dispatch** (`gov/access.py` exists
    but is not enforced at the tool layer — review finding; close it).
42. **Skill cards carry token budgets and output contracts** — each declares
    its expected input size, its compressed output shape, and forbids dumping
    raw data into agent context (the Golden Rule made operational per skill).
43. **Fallback model order + resumable runs everywhere.** OpenCode throttling
    sits on the critical path twice (build-time writer, runtime LLM bridge);
    both get configured fallback chains and every ingestion run is resumable
    from its last completed chunk.
44. **The AI build team stays the standing operating model** — Fable directs
    (minimum tokens), cheap models write, better models review, Sonnet gates
    with tests, Opus/Codex opine on high-stakes calls only; all documented in
    CLAUDE.md (done) and enforced by habit.
45. **Session-state persistence.** After every meaningful work session, restart
    notes update automatically so any future session (or another agent) resumes
    without re-explaining — Fable token exhaustion becomes a non-event.

### G. Operations, reliability & governance

46. **Golden evaluation set.** Curated deck+report samples with known-correct
    extractions; every pipeline change runs against it; regressions block. This
    is also the gate self-learning waits for (T12 stays gated).
47. **Doc consolidation — off the critical path.** Collapse the ~9 overlapping
    top-level plan docs into MASTER_PLAN + live 00_control + per-module
    AGENTS.md. Janitorial: delegated to fast-worker, parallel to real work,
    never blocking safety or Phase B. (Opus HIGH-3.)
48. **First real SAP export (P2.2) remains the #1 unblocking event** — the day
    it arrives it outranks everything; IS2.3 (multi-sheet Excel) and IS2.4
    (type inference) finish the tabular spine to receive it.
49. **Scheduled ingestion, backup/restore drill, and alerting** in the ops
    phase (T11) — the brain only counts as "never loses anything" after a
    restore has actually been rehearsed.
50. **Quarterly plan review ritual.** The owner + Fable re-read this plan's
    success measures against reality each quarter; the plan is a living
    contract, not a monument — because "the expectation is very big and the
    changes are a lot" (owner), and the next years of AI change are certain to
    bend any static plan.

---

## 4. Phases and gates (Opus-corrected ordering)

- **A0 — SAFETY RAILS (hard gate; blocks all LLM-on-real-document work).**
  Items 1–10 above: verifier (units-aware), facts/claims physical split,
  chokepoint + bypass guard, tier gate + ledger, injection defense, provenance
  tags, citation verification, non-numeric audit definition. GATE: all green
  with tests; a test proves Tier-1 content cannot reach the LLM bridge; a test
  proves an uncited/unverifiable claim cannot be stored.
- **A1 — JANITORIAL (parallel, non-blocking).** Doc consolidation (47),
  report_reader repair + task-queue row (13), branch-policy reconciliation.
- **B — FIRST HQ DECK END-TO-END.** PPTX extractor (11), chunked map-reduce
  (12), WorkflowRecord + glossary + provenance (14–17), one real Korean deck →
  brief. GATE: owner judges the brief faithful and useful next to the original;
  image-only share measured (20).
- **C — CORPUS, REGISTRY & COMPARISON.** Registry (21), families/versioning
  (22–23), Samsung IR corpus ingested (29), contradiction view (30), knowledge
  search (33). GATE: a quarter-over-quarter brief the owner would show a
  colleague.
- **D — EXECUTIVE INTERFACE.** Decision briefs (34), meeting packs (35),
  reports/articles (36), sign-off enforcement (37), feedback loop (39). GATE:
  the owner uses one in a real management meeting and it holds up.
- **E — REAL FACTORY DATA (parallel, event-driven).** P2.2 + IS2.3/IS2.4 (48)
  the moment a real export lands.
- **F — SCALE-UP (numeric triggers, not dates).** Ontology/graph memory when
  the registry passes ~50 documents (24–25 mature into T9), Korean OCR/VLM by
  measured image-share (20), enterprise search by proven retrieval pain (T10),
  ops hardening (49), idea synthesis last (32), self-learning only after the
  golden set exists (46 → T12).

## 5. Hard cases (expanded — 18)

1. Scanned/image-only Korean deck → measure share, Korean OCR data, review
   queue; VLM adapter by evidence.
2. Deck exceeds context → chunked map-reduce with coverage accounting; block
   rather than truncate.
3. LLM invents a step/figure → deterministic verifier (1) + citation-support
   check (6) + claims-only storage (3) + non-numeric audit (10).
4. HQ v2 contradicts v1 → families + diff view; contradictions surfaced, never
   auto-merged.
5. Two factories define a KPI differently → entity IDs + metric registry;
   comparisons mark "not directly comparable."
6. Mixed-sensitivity document → default Tier 1; owner explicitly marks Tier 2;
   the safe default absorbs mistakes.
7. Provider throttled mid-run → fallback chains + resumable runs (43).
8. Fable token exhaustion → delegation rules + session-state persistence (45).
9. Mistranslated critical term → glossary (17) + back-translation check (18) +
   objective trust definition.
10. Knowledge loss/corruption → git-committed artifacts (28) + rehearsed
    restore (49).
11. Unsigned output reaching an executive → sign-off enforced in serving with
    tests (37).
12. Model/provider disappears → LLMBridge abstraction; swap in one place.
13. **Prompt injection via document content** → delimiting + verifier backstop
    + injection test deck (7).
14. **Korean number scaling (억/만)** → units-aware verifier (2).
15. **Same deck ingested twice, different claims** → hash-based dedup +
    reconciliation rule (28).
16. **A module bypasses the LLM chokepoint** → repo-wide guard test (4).
17. **Human-review queue overload** → measured image-only rate before scaling
    (20); if the queue becomes the system, stop and re-plan.
18. **Registry tier misassignment at scale** → periodic tier audit against the
    external-call ledger (9).

## 6. Explicitly NOT doing yet

Enterprise search before retrieval pain · self-learning before the golden set ·
natural-language Q&A chat before storage+calc are proven on real data ·
multi-department rollout before the pilot is trusted · graph/memory infra
before the ~50-document gate · generative idea synthesis before the claims
boundary is proven in production.

## 7. Success measures

- HQ deck → owner-ready brief < 1 hour, every claim clickable to its slide.
- Zero unverified claims in storage; zero Tier-1 content in the external-call
  ledger; zero untagged numbers in any executive output (all: auditable).
- Quarter-over-quarter Samsung comparison brief the owner would show a
  colleague.
- The owner walks into a CFO/CEO meeting with a system-built pack — and comes
  back saying it held up.
- Any work agent can complete a routine task through the skill map loading
  ≤ 1 skill card — token usage per task measurably minimal.

## 8. Immediate next actions (upon owner approval)

1. Sonnet converts Phase A0 + A1 into task-queue rows (cards with named tests).
2. Pipeline builds A0 card-by-card (writer → reviewer → Sonnet gate).
3. Owner supplies one real HQ deck (any old one) for Phase B's gate.
4. Owner decides: close or sanction the `chatgpt-ai-tasks` branch.
