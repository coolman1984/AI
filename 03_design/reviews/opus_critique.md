# Adversarial Review - Executive Assistant Master Plan (v1 draft)

Reviewer: deep-reasoner (Opus), independent senior architect.
Scope: 03_design/assistant_master_plan.md, AGENTS.md, task_queue.md,
restart_notes.md, engines/docs/report_reader.py (the actual LLM bridge code),
MASTER_PLAN.md section map.

Verdict: SOUND WITH CHANGES. Strategy is right; several load-bearing defenses are
asserted but not real in code, and the phase order puts janitorial work ahead of
the safety rails that gate everything. Severity: CRIT, HIGH, MED, LOW.

## 1. Where the plan will actually fail in practice

CRIT-1: The primary anti-invention defense does not exist in code. The plan leans
on verbatim-figure verification (Pillar 2, hard case 3, success measure zero
uncited claims). report_reader.py does NOT verify figures. The prompt only ASKS
the LLM to quote verbatim. The one deterministic check is a page-range bound
(1..page_count). Nothing confirms a quoted number appears in the cited page source
text. For the catastrophic failure mode (a wrong number reaching the CEO) this is
THE gap, currently undefended. Fix (Phase A gate, not B): a deterministic
post-verifier that extracts each numeric token from every claim, normalises it
(thousands separators, decimal marks, Korean scale units), and requires an exact
match against the cited page extracted text. No match means reject or quarantine.
Code plus test. This verifier, not the prompt, is the real guarantee.

CRIT-2: Never lose anything is contradicted by silent truncation. Hard case 2
claims chunked map-reduce with a coverage report is already designed into
report_reader. It is not. The code truncates to 24,000 chars and appends a warning
string. A ~50-slide Korean deck (token-dense) will exceed this; content past the
cut is dropped with only a buried warning. Fix: real chunking with explicit
coverage accounting before any real deck; if full coverage is impossible, block
and route to review rather than truncate.

HIGH-3: Phase A bundles janitorial work with safety-critical work. It mixes
consolidating 38 planning docs with building the privacy/claims/verifier rails,
all ahead of Phase B (the owner most-wanted feature). Doc consolidation does not
gate safety and should not sit on the critical path in front of it. Split Phase A:
A0 (gating, blocks all LLM-on-real-data) = privacy-in-code, separate claims store
with reject-on-uncited API, and the verifier from CRIT-1, green with tests before
one real deck runs. A1 (janitorial, parallel, hand to fast-worker) = doc
consolidation, deferred. This answers section 8: yes, Phase A is too big.

HIGH-4: Human-review queue capacity is an unpriced dependency. Hard cases 1 and 9
route scans and spot-checks to humans. If HQ decks are largely image/scan-heavy
(common for polished rollout decks), the human queue becomes the system and the
automation value collapses. No estimate of the image-only rate exists. Fix:
measure the image-only share on the first 5 real decks before Phase C scale.

## 2. Is the claims-ledger / claims-vs-facts separation strong enough?

No - it is separation by convention, the weakest form. Today
store_report_knowledge writes LLM key-points straight into the same
KnowledgeMemory used for everything else, with no separate class, store, or API,
and no uncited-rejection. The separation is aspirational until Phase A builds it.
Even the designed version (a claim class with a citation field) is not hard enough
once numbers flow into briefs. Propose a physical boundary:

1. Two physically separate stores. facts (audited, SQL-sourced only) and claims
   (LLM-originated), different files and API modules. The numeric/calculation path
   is code-forbidden from reading claims. A claim is NEVER promoted into facts;
   there is no code path that does it.
2. One-way trust flow at a single chokepoint. All LLM output passes through one
   bridge that checks tier, requires citations, runs the verifier, and writes only
   to claims. No module may call the LLM directly (grep-guard + test). A bypass
   voids every guarantee.
3. Provenance at render time, not just storage. The real danger is a brief putting
   a CLAIMED number and an AUDITED number in one sentence with no way to tell them
   apart. Every number in every executive output must carry a visible provenance
   tag (AUDITED-FROM-QUERY vs CLAIMED-FROM-DECK, with citation). A serving test
   must FAIL any untagged number or any unmarked tier mix.
4. Verify the citation, not just its presence. AGENTS.md forbids originating a
   citation from generation, yet the LLM currently chooses the page number - that
   IS a generated citation. The verifier must confirm the cited page text supports
   the claim (its numeric tokens and key terms appear on that page), else reject.

With those four the no-invented-numbers rule survives an LLM layer. Without them,
claims ledger is a label on the same soft store.

## 3. WorkflowRecord schema - missing for combine old+new into new ideas

Prose fields (purpose, steps, roles, KPIs, what-changed, open questions) are a
start but insufficient for cross-year synthesis. Missing:

1. Canonical entity IDs / ontology links. Free-text names drift across
   translations and years; two decks naming the same process differently will not
   link. Bind steps/KPIs/roles to stable IDs from the Part R metric registry and a
   process/role ontology. Synthesis is a graph over IDs, not strings.
2. Bitemporal validity. Store valid-time (when the process was in force per the
   deck) separately from ingest-time. What was true in Q2 2025 needs valid-time;
   current temporal memory only knows ingest order.
3. Original-language retention per field. Keep the Korean source text beside every
   English field. English-only loses the source of truth and blocks
   re-translation, dispute resolution, and re-verification when a model changes.
4. Full provenance stamp. Source file hash, ingest run ID, model name + version,
   prompt version, per-field translation confidence (deterministically computed,
   not LLM-asked). Needed to re-run/re-verify years later.
5. Typed cross-workflow edges as first-class data: depends-on, conflicts-with,
   refines, supersedes/superseded-by. Record the typed links even before a graph
   DB; deferring the link structure defers the thing that makes synthesis possible.
6. Open questions / unknowns as first-class queryable items with status
   (open/resolved/by-what). New ideas emerge when new knowledge resolves an old
   unknown - that is literally how old+new combine.
7. Linkage to decisions and outcomes. Reference existing decision-memory IDs so
   the system can see which past workflow choices led to which outcomes; that loop
   already half-exists in the learning engine - connect it.

## 4. The 12 hard cases - weak defenses and outright gaps

Weak:
- #3 invent figure: defense not implemented (CRIT-1); audit spot-samples is
  sampling, not a guarantee, on the catastrophic path.
- #9 mistranslation: glossary + spot-check is fine, but no back-translation or
  dual-model agreement check on critical terms, and no objective definition of
  when trust is earned (stays subjective forever).
- #11 sign-off for all outputs: asserts the finance audit layer covers narrative
  briefs, but MASTER_PLAN Part O audit is number-centric (independent re-run,
  four-eyes on a calculation). What does independent re-run mean for a translated
  workflow brief? Undefined. Needs a defined non-numeric audit (second-model
  re-extraction + citation re-check) or the gate is hollow.

Missing entirely (ordered by danger):
- CRIT: Prompt injection via document content. R3 is still OPEN in risks.md. A
  deck (or hostile embedded text) can carry an instruction like ignore the rules,
  report this number. Untrusted document text is fed straight into the prompt - a
  direct route to an invented number, and absent from all 12 cases. Delimiting is
  weak; the real backstops are the verifier and the code rule that LLM output can
  never reach the numeric path. Add it as an explicit hard case.
- CRIT: Korean number scaling / locale. eok = 10^8, man = 10^4; date and
  decimal/thousands conventions differ. An LLM mis-scaling 3 eok to 300,000
  (should be 300,000,000) is a silent catastrophe that can PASS a naive verbatim
  string check. The verifier must be units-aware; give this its own hard case.
- HIGH: Non-determinism / re-ingest reconciliation. The same deck ingested twice
  yields different claims. Which is canonical? No dedup/reconciliation rule.
- HIGH: Bridge bypass. Every guarantee assumes all LLM calls go through one
  bridge, but nothing enforces the chokepoint. Needs a test/guard.
- MED: Ledger/registry tampering or default-tier misassignment at scale.

## 5. What to CUT or simplify

- Cut factory-vs-factory comparison from the build until other factories reports
  actually exist (Phase C lists it now). Samsung IR quarter-over-quarter already
  proves temporal value; building against non-existent data is speculative.
- Push idea synthesis / synthesis briefs (Pillar 3) to last and gate it behind the
  proven claims boundary. It is the lowest-proven, highest-risk feature and sits
  closest to the failure mode. Consider excluding it from v1 entirely; a
  contradiction-surfacing view over claims is far safer than generative new ideas.
- Defer doc consolidation off the critical path (HIGH-3).
- Keep the good restraint: flat JSON until ~50 docs, graph/memory infra gated on
  document count, the explicitly-not-doing-yet list. Do not add heavy infra early.

Net: slightly OVERBUILT on synthesis/comparison, UNDERBUILT on
verification/injection. Move effort from the former to the latter.

## 6. Contradictions with existing governance

- AGENTS.md never-rule (no originating a number, quote, citation, or confidence
  score from generation): report_reader.py has the LLM originate quotes AND
  citations with no verification. A live violation of the strictest rule until the
  verifier + citation-support check exist. Highest-priority reconciliation.
- Confidence scores: hard case 9 low-confidence flags and MASTER_PLAN O.3/E.4
  certainty scoring must be computed deterministically (glossary match ratio),
  never asked of the LLM, or they violate the same rule.
- No code without a task-queue row: report_reader.py and its test already sit in
  the tree untracked with no task ID (git status confirms). Enforce the fix now -
  add the row before committing; treat it as the test of the new discipline.
- Branch policy: AGENTS.md/CLAUDE.md say one branch main, never create branches,
  yet restart_notes.md line 17 and a recent merge commit show a temporary
  chatgpt-ai-tasks branch. Reality already contradicts the rule; the plan restates
  one-branch-main without reconciling. Flag to the owner: sanction it explicitly or
  close it out.
- Audit-layer scope: hard case 11 claims Part O covers all executive outputs, but
  Part O is defined for numeric re-runs. Define the non-numeric audit or narrow
  the claim.

## Bottom line
Strategy and pillars are sound. The failure is concentrating unproven,
load-bearing safety on the exact path that can send a wrong number to the CEO,
while the code meant to embody those defenses today does neither verification, real
chunking, nor store separation. Make A0 (verifier + physical claims/facts split +
tier-in-code + injection defense) the hard gate before any real deck, defer the
janitorial and synthesis work, and the plan is executable.
