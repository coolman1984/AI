# CODEX_PLAN.md — Lead-Engineer Kickoff Brief (start here, Codex)

**You are Codex / GPT-5.5, the lead engineer.** The architecture is fixed in
`MASTER_PLAN.md`. Your job is to turn it into a clean, test-anchored scaffold that
cheaper implementer models (DeepSeek V4 Pro / V4 Flash, Kimi K2.7, MiniMax M3) can
fill in one Task Card at a time. Read `AGENTS.md` and `MASTER_PLAN.md` first.

> **Operating rule:** contracts-first, test-first. You write the interfaces and the
> failing tests; implementers write code until tests pass. You do NOT write business
> logic in Phase 0. **All commits go to `main`. Never create another branch.**

---

## 0. Your immediate task = PHASE 0 (Foundation). Implement nothing yet.

Deliver a runnable skeleton: the repo structure, every `AGENTS.md`, the contracts, the
**failing** tests, config, dependencies, and CI. Definition of Done is at the bottom.

### 0.1 Create the repository structure (per `MASTER_PLAN.md` Part H.4)
```
/AGENTS.md                 (exists)        /CODEX_PLAN.md (exists)  /MASTER_PLAN.md (exists)
/shared/contracts/         + AGENTS.md     ← MCP tool schemas + JSON schemas (the seams)
/engines/data/             + AGENTS.md     ← DuckDB, SAP ingest, profile, clean, variance, templates
/engines/docs/             + AGENTS.md     ← PDF/Word/PPT extraction + offline OCR (EN+AR)
/engines/email/            + AGENTS.md     ← .eml threads, approvals, recursive attachments
/engines/brain/            + AGENTS.md     ← vault + pgvector index + decision memory + synthesis
/mcp_server/               + AGENTS.md     ← exposes the Part D tool catalog over MCP
/lenses/                   + AGENTS.md     ← per-department lens configs (finance.yaml first)
/templates/                + AGENTS.md     ← file template registry (file_templates.yaml)
/playbooks/finance/        + AGENTS.md     ← pilot workflows (e.g. monthly_close)
/eval/                     + AGENTS.md     ← golden-set trust harness
/tests/                                    ← pytest suites mirroring each module
/config.yaml                               ← paths, locale, AI providers, lenses, templates, ROLES/ACCESS
/requirements.txt                          ← pinned (see Part K)
/.github/workflows/ci.yml                  ← install + pytest + ruff on every push to main
```

### 0.2 Write the contracts (the seams) in `shared/contracts/`
For every tool in `MASTER_PLAN.md` Part D, define a typed signature + a JSON schema:
`ingest_files, query_numbers, compute_variance, search_documents, search_emails,
search_knowledge, get_data_quality, summarize_for_manager, store_decision,
retrieve_decisions, retrieve_by_topic, set_lens, get_warnings, register_template,
project_module_report`. Each contract states inputs, outputs, and the **evidence-ref**
field that every fact-returning tool must include. These are frozen interfaces:
changing one later requires owner sign-off (see `AGENTS.md`).

### 0.3 Write FAILING tests (red) for each contract
One test file per tool/module under `/tests/`, asserting the contract's shape and its
invariants (e.g. `query_numbers` result carries the SQL + rows; `summarize_for_manager`
**raises** if a numeric claim lacks an evidence ref; `compute_variance` bridge sums to
the total). Tests must run and fail for the right reason (not-implemented), so an
implementer knows exactly when a card is done.

### 0.4 Write every `AGENTS.md` (one per module)
≤ ~1 page each: purpose · public interface · inputs/outputs · invariants · what it must
NEVER do · allowed libraries + import examples · exact test command · known edge cases
(pull the edge cases from `MASTER_PLAN.md` Part J).

### 0.5 Config, dependencies, CI
- `requirements.txt` pinned from Part K. `config.yaml` with swappable `ai.synthesis` /
  `ai.embeddings` providers (keys from env vars, never committed), the lens registry,
  the template registry path, and **roles/access scopes** (Part G.1).
- CI runs `pip install -r requirements.txt && pytest && ruff check .` on every push.

---

## 1. The Task Card you produce for implementers (one per atomic unit)
After Phase 0, expand each later phase into cards in this exact format:
```
TASK <id> — <short title>
Module:       engines/data
Files:        engines/data/variance.py      (edit ONLY this)
Read first:   engines/data/AGENTS.md  +  shared/contracts/data.tools.*
Contract:     compute_variance(actual, baseline, dims) -> VarianceBridge   (frozen)
Depends on:   TASK <id> (must be green first)
Do:           <one explicit paragraph; copy-pasteable commands>
Done when:    `pytest tests/data/test_variance.py` is green
Never:        load whole files into memory · touch another module · invent columns
Assign to:    <model, per routing below>
```

## 2. Model routing (assign each card by difficulty — see `MASTER_PLAN.md` I.4)
| Card type | Assign to |
|---|---|
| Contracts, tests, cross-cutting refactor, integration, golden-set | **Codex (you)** |
| MCP server + long-horizon agent/tool wiring, self-correcting multi-file | **Kimi K2.7 Code** |
| Hard isolated logic (variance math, SQL, SAP parsers) at low cost | **DeepSeek V4 Pro** |
| Bulk/boilerplate, glue, config, test scaffolding | **DeepSeek V4 Flash** |
| Image/screenshot/OCR-tuning, very-long-context reads | **MiniMax M3** |

## 3. The loop (how the chain runs, every phase)
1. You expand the phase into Task Cards (small, isolated, one file each).
2. You ensure each card's test exists and is red.
3. Implementers each take one card → make its test green → commit to `main`.
4. You integrate, run the full suite + the golden set (`/eval`), fix cross-cutting issues.
5. Phase DoD green (incl. trust gate) → proceed to the next phase. Do not proceed on red.

## 4. Guardrails (why the chain stays safe — see `MASTER_PLAN.md` I.5)
- Pinned deps + per-module allowed-libs lists kill hallucinated APIs.
- "Edit ONLY this file" + isolated modules kill scope creep.
- Test-first + CI on every push kills silent breakage.
- Implementers read only their module `AGENTS.md` + the card + the test — never the whole
  repo (even at 1M context: cost + degradation).

---

## Phase 0 — Definition of Done
- [ ] Full repo tree from §0.1 exists; every listed folder has an `AGENTS.md`.
- [ ] `shared/contracts/` defines all Part D tools (signatures + JSON schemas), each with
      an evidence-ref field where it returns facts.
- [ ] `/tests/` has a red test per contract; `pytest` runs and fails only as
      "not implemented yet" (no import/collection errors).
- [ ] `requirements.txt` pinned; `config.yaml` has providers + lenses + templates +
      roles/access; `.github/workflows/ci.yml` runs install + pytest + ruff on push.
- [ ] `ruff check .` passes on the scaffold; `ruff format .` is clean.
- [ ] Root `AGENTS.md` commands work; a trivial MCP tool is callable over MCP, scoped to
      a department.
- [ ] Everything committed and pushed to **`main`** (no other branch created).

## After Phase 0
Proceed to **Phase 1 (Data — Ingest)** from `MASTER_PLAN.md` Part L: write the cards for
streaming a 200 MB SAP export into DuckDB (text-first, chunked), with the failing tests,
and assign them per §2. Then continue down Part L, phase by phase, gate by gate.
