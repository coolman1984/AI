# RISK_AND_GAPS_AUDIT.md — Senior Critique of MASTER_PLAN

> **Reviewer stance:** written as if by one person wearing three hats with ~30 years
> each — **senior software architect**, **UX designer**, and **factory operations
> leader**. The job here is to attack the plan, not flatter it. Everything below is a
> weakness, risk, gap, or missing technology in `MASTER_PLAN.md`, with how to fix it and
> what the wider field already does better (web-researched, sources at the end).

**Severity legend** (same scale as `REVIEW.md`):
**S1** silent-wrong-output (worst — confident wrong answer) · **S2** crash / data-loss /
security · **S3** scale / robustness · **S4** polish / clarity.

---

## 0. BOTTOM LINE UP FRONT (the verdict)

The architecture's *spine is correct* — MCP-first, calculation-integrity, evidence,
in-house, modular, AI-reads-the-map. But the plan is **strong on extraction and weak on
the three things that actually decide whether a factory C-suite trusts it:**
**(1) governed meaning** (no semantic layer → cross-department numbers are apples vs
oranges), **(2) verified trust** (evidence-refs alone do not stop citation fabrication;
there is no verifier, no injection defense, and a self-contradiction on the in-house
rule), and **(3) it cannot learn** (no skills, no memory of mistakes, no outcome
feedback — your central concern). It is also **over-engineered on the build chain and
under-engineered on operations** (no observability, temporal data model, orchestration,
or UX for the people who actually read the output).

**If you fix only five things:** add a **semantic/metrics layer**, a **verifier-critic +
prompt-injection defense**, resolve the **in-house-vs-external-LLM contradiction**, add
the **learning system**, and add a **one-A4 report methodology + minimal UX with a
feedback channel.** The rest is important but secondary to these.

---

## 1. TOP 12 RISKS (ranked — fix from the top)

| # | Sev | Risk | Why it bites this plan | Fix (short) |
|---|-----|------|------------------------|-------------|
| 1 | **S1** | **No governed semantic/metrics layer** | The federation promise ("did the panel shortage cause the quality + sales miss?") dies if "cost/margin/scrap/yield" are defined differently per department & file. `column_map.yaml` maps *columns*, not *metrics*. | Add a **semantic layer** (dbt Semantic Layer or **Cube** — Cube ships an MCP server + row-level access). Metrics defined once, in code, versioned, auditable. |
| 2 | **S2** | **In-house rule contradicts the tech stack** | Part G.5 says *nothing leaves the network*; Part K sets synthesis = "Claude (Anthropic), swappable" — an **external API**. The moment you summarize, factory data leaves. | Decide now: run an **on-prem synthesis model** (Qwen/Llama/DeepSeek via vLLM) — or relax G.5 explicitly. Today the plan is internally inconsistent. |
| 3 | **S1** | **Citation fabrication / synthesis hallucination** | Research shows agentic synthesis blends two real chunks into a claim supported by neither ("hybrid ghost"), and reinforces wrong answers that *sound* complete. Evidence-refs are necessary, not sufficient. | Add a **verifier/critic** pass: re-check every citation by chunk/row ID, **recompute every number**, block any uncited claim. |
| 4 | **S2** | **Prompt injection via ingested emails/PDFs/screenshots** | OWASP #1 LLM risk. The system *reads untrusted content* and *has acting tools* (`store_decision`, `register_template`). With self-learning added, an injection can **permanently poison skills/memory** ("zombie agents"). The plan has no threat model. | Treat all ingested content as **data, never instructions**; privilege separation; output validation; never auto-act on document-derived instructions; quarantine + human approval for any memory/skill write derived from documents. |
| 5 | **S1** | **"Test-green = done" ≠ correct** (the cheap-coder chain) | Weak models **overfit to tests**; messy-data edge tests are themselves error-prone; if Codex's *contract or test* is subtly wrong, the wrong thing is faithfully built. No one reviews the tests. | Tests are **reviewed like prod code**; add **property-based + mutation testing**, adversarial/golden datasets, and an architect (human) gate on contracts + tests for S1/security modules. |
| 6 | **S1** | **No learning / self-correction loop** (your point) | The system stores decisions but never learns from outcomes or mistakes. It will repeat the same error forever. | Add the **Learning System** (Part 4): skill library + memory tiers + error memory + reflection + outcome tracking. |
| 7 | **S1** | **Temporal/lineage data model underspecified** | "vs budget / vs last quarter" and **reproducing a past report** require immutable, versioned period snapshots and durable lineage. "Store the SQL + rows" doesn't scale to 600k rows/fact. | **Bitemporal fact model**, immutable per-period snapshots, lineage = query hash + filter predicate + data-version, not raw rows. |
| 8 | **S1** | **No reconciliation to the system of record** | If the brain's number ≠ the official SAP closing by even $1, finance discards the whole system. | Add a **certification/tie-out** step against the ERP official report; show "ties to SAP: ✅/✗". |
| 9 | **S2/S3** | **No production observability** | The eval harness is for *build*. Nothing traces a *live* wrong answer — you can't debug what you can't see. | **LLM tracing** (Langfuse/Phoenix), per-answer lineage, eval-in-prod, drift detection — from Phase 0. |
| 10 | **S3** | **Concurrency & serving not designed** | DuckDB is single-writer; ingest-during-query, index rebuilds, many simultaneous managers. No job queue, no serving store. | **Orchestration** (Temporal/Prefect/Dagster) + a job queue; serve from Postgres, not the staging DuckDB. |
| 11 | **S2/S3** | **MCP-only, no UI — the C-suite won't type prompts** | CEOs/CFOs want a **pushed brief**, drill-down, and a way to say "this is wrong." No UI also means **no feedback channel**, which the learning loop *needs*. Plus no Arabic RTL output UI. | Thin **serving/UX layer**: one-A4 brief renderer, evidence drill-down, **feedback capture**, scheduled push, RTL support. |
| 12 | **S2** | **Retrieval quality is hand-waved** | `search_documents` doesn't specify hybrid (BM25+dense) search, **reranking** (the single biggest RAG quality lift), chunking, or table-aware retrieval. Retrieval *mismatch* (not hallucination) is the #1 agentic-RAG failure. | Hybrid search + **local cross-encoder reranker** (bge-reranker), layout/table-aware chunking. |

---

## 2. RISKS BY LENS

### 2A — Software Architecture & Logic (S1–S3)
- **Single point of failure in the handoff.** Architect→Codex contracts/tests gate
  *everything*; a wrong contract propagates silently. Mitigation: contracts reviewed by a
  human + a second model; contract = spec + examples + counter-examples.
- **No integration / E2E / contract tests** — only per-card unit tests. The hard bugs
  live at the seams (engine interop, MCP serialization, evidence-ref propagation end to
  end). Add contract tests between modules and a thin E2E suite per phase.
- **Non-deterministic components can't be unit-tested** (Question Router, synthesis,
  verifier). Need **LLM-as-judge eval with rubrics**, snapshot/regression suites, and a
  fixed golden set — the plan mentions eval but treats stochastic components like
  deterministic ones.
- **Vault-as-truth at scale (S3).** Thousands of Markdown files + binary attachments →
  git performance, merge conflicts, history bloat. Plan needs vault sharding, Git LFS for
  binaries, and a write-path that serializes vault edits.
- **Embedding migration cost (S2).** Changing the embedding model = re-embed everything.
  Store **embedding model + dimension + version** per vector; plan a re-embed job.
- **"AI never reads the data" is overstated.** For synthesis the AI *does* read retrieved
  chunks — the rule is about *volume*, not zero-data. State this precisely or engineers
  will be confused (and may skip needed retrieval).
- **Contract/schema/vault-format evolution** has a rule ("ask first") but **no migration
  strategy or versioning** for schemas, the vault format, or metric definitions.

### 2B — Implementation (the multi-model chain) (S1–S3)
- **Reward hacking / teaching-to-the-test** (see Risk #5). Cheap models will write the
  *minimum* that passes — including hard-coding expected outputs. Mutation testing catches
  this; so does hidden test data.
- **Global incoherence from local isolation.** Each card is isolated by design, which is
  good for safety but risks inconsistent assumptions across cards (naming, error handling,
  units). Codex must own a **conventions doc** + run a periodic coherence pass.
- **Models hallucinate our *own* internal APIs**, not just third-party ones. Every module
  `AGENTS.md` must include real import examples + a stub with docstrings.
- **Generated code is a supply-chain & security risk.** "Test green → merge to main" with
  no SAST/secret-scan/architect review is dangerous for `mcp_server/`, access control, and
  anything touching secrets. Gate security-sensitive modules behind human + SAST review.
- **CI nondeterminism** from LLM-in-loop tests → flaky pipelines. Pin seeds where possible;
  isolate stochastic tests; use cassettes/VCR for recorded model responses.
- **Operating-cost blind spot.** Running 4 providers + embeddings + synthesis per question
  has no cost model, caching, or rate limiting. Add a **semantic cache** and a cost budget.

### 2C — Data & Factory Domain (the 30-year operator's list) (S1–S3)
- **Master-data inconsistency across plants** (material master, cost-center hierarchies,
  UoM). The federation will silently mis-join. Needs a **business glossary + master-data
  governance** (ties to the semantic layer, Risk #1).
- **SAP extraction governance.** Who is authorized to extract? Transport/refresh cadence?
  ALV vs table extracts? The plan assumes files appear; reality is SAP Basis politics and
  authorizations. Define the data-sourcing contract per source.
- **Fiscal calendar reality.** 4-4-5 calendars, fiscal periods ≠ months, plant shutdowns,
  shift patterns. Variance logic that assumes "month" will be wrong at period boundaries.
- **Multi-currency / FX policy.** Month-end vs average rate, intercompany, transfer
  pricing. `compute_variance` lists "fx" but the **rate source and policy is a governance
  decision**, not a code detail.
- **Audit & compliance (S2).** Finance + manufacturing imply SOX-like controls: audit
  logs, segregation of duties, retention, tamper-evident decision memory. The decision
  store must be **audit-grade**, not just a Markdown file.
- **Alert fatigue (S3).** Early warning without severity, thresholds, and suppression =
  ignored alerts. A factory leader knows: too many warnings → all warnings die.
- **Adoption & change management — the #1 reason factory IT fails (S3).** No plan for a
  sponsor, **parallel-run against existing reports to earn trust**, training, or rollout.
  A technically perfect system with no adoption is a failed project.
- **Org politics.** A factory brain that exposes one department's failures to the CEO will
  meet resistance. Governance of *who sees whose failures* is a real design constraint.

### 2D — Security & Trust (S2)
- **Prompt injection** (Risk #4) — the headline security gap.
- **In-house contradiction** (Risk #2) — the synthesis model likely sends data out.
- **Secrets management** for any provider keys; encryption at rest; **RBAC enforcement
  must be tested** (access control that isn't tested isn't access control).
- **DR / backup / RTO-RPO.** Vault in git is good; the index, staging, operational state,
  and decision memory need backup/restore. Factory-critical.
- **No red-team / abuse testing** of the agent surface.

### 2E — UX & Report Methodology (the designer's list) (S2–S4)
- **No report methodology** beyond a 7-section card. Your requirement (1–2 A4 pages, TL;DR)
  needs a real framework — see Part 5 (**BLUF + Minto + SCQA**) with a **hard length
  budget** and **progressive disclosure**.
- **No visualization.** A number without a tiny trend/sparkline and a bridge chart is weak
  for managers. Add minimal, evidence-linked visuals.
- **No trust/verification UX.** Managers must be able to drill into evidence, challenge a
  number, and flag "this is wrong" — the flag is also the **learning signal**.
- **No delivery UX.** How does an early warning reach a CEO — morning brief, mobile push,
  email? Undefined.
- **No bilingual output UX.** Arabic OCR is handled on input; **Arabic/RTL output and UI**
  for Arabic-speaking managers is not.
- **No onboarding/trust-building UX.** Black boxes don't get adopted; confidence and
  evidence must be visible by default.

---

## 3. WHAT'S MISSING (capabilities, not just bugs)

1. **Governed semantic/metrics layer** (single definition of every KPI).
2. **Learning system** — skills, memory, self-correction, outcome feedback (Part 4).
3. **Verifier/critic agent** — independent check of numbers + citations before a human sees them.
4. **Prompt-injection & output guardrails.**
5. **Observability/tracing + production eval.**
6. **Temporal/bitemporal data + lineage/versioning.**
7. **Orchestration + job queue + serving store** (vs ad-hoc scripts on DuckDB).
8. **Hybrid retrieval + reranking + layout/table-aware chunking.**
9. **Data-quality contracts** (Great Expectations / Pandera) as code, per source.
10. **Reconciliation/certification** to the system of record.
11. **UX serving layer + report methodology + feedback channel.**
12. **DR/backup, audit logging, secrets management, RBAC tests.**
13. **Master-data/business-glossary governance.**
14. **Caching** (semantic + result) and a **cost model**.

---

## 4. THE LEARNING SYSTEM (your central ask — designed)

The plan stores *decisions* but never *learns*. Here is the missing loop, grounded in the
field's best work (Voyager skill libraries; Hermes self-created skills + DSPy/GEPA
self-evolution; Letta/Zep/Mem0 memory; Reflexion-style self-correction).

### 4.1 Four kinds of memory (today the plan has ~one)
| Memory | Holds | Tech to model it on |
|---|---|---|
| **Episodic** | What happened: every Q&A trace, decision, the evidence used | Zep (temporal KG: "what was true on date X") / Letta recall |
| **Semantic** | Governed facts & definitions | the **semantic layer** (Part 3.1) + vault |
| **Procedural (Skills)** | Reusable validated *how-to* (e.g., a verified SQL template for "material cost variance by sub-assembly") | **Voyager** skill library + **Hermes `agentskills.io`** format |
| **Working** | Current task scratch | in-session context |

### 4.2 Skill library (so it gets faster and better over time)
After a *successful, non-trivial* task, the agent **proposes a skill** (the SQL/code + a
"when to use" description). A skill is **not free text the model trusts** — it is
**validated by tests + the verifier + a human approval**, then versioned and stored
(FTS5/vector retrieval). Hermes reports ~40% faster on similar tasks after 20+ skills;
Voyager shows skills are compositional and transfer to new problems. For us: the monthly
close gets cheaper and more reliable every cycle.

### 4.3 Self-correction & error memory (what happens when it's wrong)
- A **verifier/critic** recomputes numbers and re-checks citations (Risk #3). On a caught
  error → write an **error-memory** record: *symptom, root cause, the correction.*
- **Reflexion loop:** before finalizing, the agent reviews against the error memory
  ("have we been wrong this way before?") and self-corrects.
- **Human "this is wrong" flag** (the UX feedback channel) is the highest-value error
  signal — it must flow straight into error memory.

### 4.4 Outcome tracking (your "did the action work?")
Link each **decision → the later actuals**. Learn which drivers were right and which
recommendations worked; surface that next time ("last time we blamed LCM price; the real
driver turned out to be mix"). This closes the loop from *report* to *learning*.

### 4.5 Self-evolution (advanced, gated)
Use **DSPy + GEPA** (the technique Hermes uses) to optimize prompts/skills offline against
the **golden set** — but **never auto-deploy**: every evolution must pass eval + human
sign-off and is versioned/rollback-able.

### 4.6 ⚠️ The danger this adds (must design for it)
Self-learning + untrusted documents = **"zombie agents"**: a prompt injection in an email
can write a poisoned skill/memory that persists. **Therefore: anything learned from
document-derived content is quarantined and human-approved before it enters skills/memory.
Learning is sandboxed from untrusted input.** (See Risk #4.)

---

## 5. REPORT METHODOLOGY — ONE A4, NO MORE (designed)

Managers can't read huge reports. Adopt the proven executive frameworks:
**BLUF** (Bottom Line Up Front) + **Minto Pyramid** (answer first, then grouped support)
+ **SCQA** (Situation · Complication · Question · Answer).

**The one-A4 contract (hard budget):**
1. **Headline (1 line, BLUF):** the answer + the verdict + confidence.
2. **So-what (SCQA, ~5 lines):** situation → what changed → why it matters → what to do.
3. **Key numbers (≤5):** calculated facts only, each with a tiny trend/sparkline.
4. **Top drivers (≤3):** with the variance bridge.
5. **Risks / opportunities (≤3) + recommended actions (≤3, owner + deadline).**
6. **Confidence + data quality (1 line).**
7. **Evidence: links only** (drill-down on demand — not on the page).

**Progressive disclosure:** one-line headline → the A4 → full drill-down. Enforce the
length budget *in code* (`summarize_for_manager` rejects over-long output), the same way
it already rejects uncited numbers.

---

## 6. THE "PERFECT" TECHNOLOGIES THE PLAN IS MISSING

| Gap | Recommended tech | Why |
|---|---|---|
| Governed metrics | **Cube** (MCP + row-level access) or **dbt Semantic Layer** | one definition of every KPI; powers AI + BI; auditable lineage |
| On-prem synthesis (fix G.5) | **vLLM** serving **Qwen / Llama / DeepSeek** | keeps data in-house while still synthesizing |
| Agent memory | **Zep** (temporal KG) + **Mem0** (simple/fast); **Letta** if stateful tiers needed | "what was true on date X"; mistake & outcome recall |
| Skills | **Voyager** pattern + **agentskills.io** (Hermes) format | reusable, compositional, transferable how-to |
| Self-evolution | **DSPy + GEPA** | optimize prompts/skills against the golden set |
| Reranking / hybrid search | local **bge-reranker** + **BM25** (Postgres FTS / OpenSearch) | biggest RAG quality lift; fixes retrieval mismatch |
| Doc/table extraction & OCR | **Surya OCR** (multilingual+layout, strong Arabic), **Unstructured.io**, **PaddleOCR** | better tables, bilingual, layout-aware chunking |
| Orchestration | **Temporal** / Prefect / Dagster | resumable, observable, concurrent pipelines |
| Observability / eval | **Langfuse** / Phoenix (Arize) + **Ragas / DeepEval / promptfoo** | trace + evaluate live and in CI |
| Guardrails | **NeMo Guardrails** / Guardrails AI; spotlighting for injection | input/output validation, injection defense |
| Data-quality contracts | **Great Expectations / Pandera** | per-source quality gates as code |
| Vector at scale | pgvector (v1) → **Qdrant / LanceDB / Milvus** | scale beyond the pilot |
| Cross-dept graph | **Neo4j** or **Apache AGE** (in Postgres) + GraphRAG | federation, theme/community questions |
| Caching | **GPTCache** (semantic) + result cache | cost + latency |

---

## 7. SHOULD WE REUSE HERMES AGENT'S CODE? (your direct question)

**Short answer: borrow the *patterns and the open standard* — do NOT fork the whole agent
into our project.**

Findings: Hermes Agent (Nous Research) is **MIT-licensed** (legally reusable), Python 3.11
+ Node.js + `uv`, with **autonomous skill creation** (`skill_manage`, markdown skills in
`~/.hermes/skills/`, the **agentskills.io** open standard), **FTS5 memory** with LLM
summarization, **Honcho** user modeling, and a **DSPy+GEPA self-evolution** companion. Its
subsystems look *discrete-ish* but the README does **not** confirm they're cleanly
extractable as standalone libraries, and the full agent drags in chat backends (Telegram/
Discord/Slack/WhatsApp), 40+ MCP integrations, and a terminal-execution surface.

**Why not fork the whole thing:**
- **Integration & maintenance risk** — it's a general consumer agent, not a governed
  factory system; you'd inherit a large surface you must secure and maintain.
- **Security** — a self-evolving agent that ingests untrusted content is the exact "zombie
  agent" risk (Risk #4); Hermes isn't built to your in-house / access-control / audit bar.
- **Our discipline** — contracts-first, test-first, role-scoped, audit-grade. Extracting
  someone's internals fights that.

**What to do instead (concrete):**
1. **Adopt the `agentskills.io` markdown-skill format** so our skills are standard/portable.
2. **Copy the *pattern*** (skill proposed → validated → versioned → retrieved; FTS5/vector
   recall) but implement it **natively in `engines/learning/`** against our contracts, with
   the **human-approval + injection quarantine** gates Hermes lacks.
3. **Use DSPy + GEPA directly** (they're libraries) for gated self-evolution.
4. **Use a maintained memory library** (Zep/Mem0/Letta) rather than extracting Hermes'
   memory internals.
5. Optionally **run Hermes standalone in a sandbox to learn from it** — but ship our own.

---

## 8. HOW TO FOLD THIS IN — PHASED & MODULAR (not a rewrite)

New modules (each with its own `AGENTS.md`, contracts, tests — same discipline):
```
/engines/semantic/    ← governed metric definitions (Cube/dbt-style)   [Risk #1]
/engines/verify/      ← verifier/critic: recompute numbers, check cites [Risk #3]
/engines/learning/    ← skills + memory tiers + reflection + outcomes   [Part 4]
/gov/security/        ← injection guardrails, audit log, RBAC tests     [Risk #4]
/serving/             ← one-A4 renderer, push briefs, feedback API, RTL  [Part 5]
/ops/observability/   ← tracing, prod eval, drift, cost                 [Risk #9]
```
New contracts/tools: `define_metric` / `query_metric`; `verify_answer`; `propose_skill` /
`use_skill` / `list_skills`; `record_outcome`; `submit_feedback`; `get_brief`.

**Where each lands in the roadmap (the important part):**
- **Move EARLY into v1** (they are correctness/trust, not nice-to-haves):
  **semantic layer**, **verifier/critic**, **injection defense**, **observability**
  (instrument from Phase 0), the **report methodology** (Phase 8), and the **on-prem
  synthesis decision** (Phase 0).
- **v1.5 / v2 — the Learning System**, *after* the deterministic core is trustworthy (you
  cannot learn on top of an untrusted base). Order: **error memory + skill library** first
  (low risk), then **outcome tracking**, then **gated self-evolution** last.
- **v2 — concurrency/serving/orchestration** as multi-department load arrives.
- **v3 — knowledge graph + GraphRAG** for federation themes (already planned).

---

## 9. CONCRETE CHANGES TO MAKE IN `MASTER_PLAN.md`

- [ ] **Resolve the in-house contradiction** (G.5 vs K): name an on-prem synthesis model, or restate G.5.
- [ ] Add **Part: Semantic Layer** and a `define_metric`/`query_metric` tool; make `column_map.yaml` feed it.
- [ ] Add a **verifier/critic** stage between synthesis and the manager; add `verify_answer`.
- [ ] Add a **security/threat-model section**: prompt injection, privilege separation, audit, RBAC tests, DR.
- [ ] Add the **Learning System** part (skills/memory/error/outcome/self-evolution) with the injection quarantine.
- [ ] Replace the manager card with the **one-A4 BLUF/Minto/SCQA methodology + hard length budget**.
- [ ] Add a **serving/UX layer** + **feedback channel** + RTL output; soften "no UI."
- [ ] Add **observability, temporal/lineage data model, orchestration, hybrid-search+rerank, data-quality contracts, reconciliation-to-SAP**.
- [ ] Strengthen the build chain: **tests are reviewed**; add property/mutation tests + SAST + human gate on S1/security modules.
- [ ] Add a **change-management / parallel-run adoption plan** for the Finance pilot.

---

## Sources
- Hermes Agent — [GitHub](https://github.com/NousResearch/hermes-agent) · [self-evolution (DSPy+GEPA)](https://github.com/NousResearch/hermes-agent-self-evolution) · [agentskills.io context](https://ofox.ai/blog/hermes-agent-self-improving-ai-complete/)
- Voyager (skill library) — [site](https://voyager.minedojo.org/) · [paper](https://arxiv.org/abs/2305.16291)
- Agent memory — [Zep vs Mem0 vs Letta (2026)](https://apiscout.dev/guides/zep-vs-mem0-vs-letta-agent-memory-api-2026) · [Agent_Memory_Techniques](https://github.com/NirDiamant/Agent_Memory_Techniques)
- Agentic RAG failure modes — [RAG eval metrics 2026](https://blog.koiro.me/en/2026/04/30/rag-evaluation-metrics-2026/) · [enterprise RAG hallucination root causes](https://ragaboutit.com/5-root-causes-lurking-behind-enterprise-rag-hallucinations/)
- Report methodology — [Minto Pyramid & SCQA](https://modelthinkers.com/mental-model/minto-pyramid-scqa) · [BLUF & frameworks](https://benjaminball.com/blog/guide-to-powerful-presentation-frameworks/)
- Semantic layer — [Cube (semantic layer for AI/BI, MCP + row-level)](https://cube.dev/articles/best-semantic-layer-for-ai-and-bi-2026) · [dbt Semantic Layer](https://www.getdbt.com/product/semantic-layer)
- Prompt injection — [OWASP #1 / defenses 2026](https://www.getastra.com/blog/ai-security/prompt-injection-attacks/) · [Zombie Agents (self-evolving injection)](https://arxiv.org/pdf/2602.15654)
