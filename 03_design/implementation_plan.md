# AI Repository Implementation Plan

> For Hermes: execute this plan under the lightweight `.agent-loop/*` bridge while keeping `00_control/*` as the governed source of truth.

**Goal:** turn the current pilot from a technically complete vertical slice into a management-usable, restartable local product with visible variance drivers, real-data readiness, and a safe path to heavier infrastructure.

**Architecture:** keep the trust wall unchanged. Numbers continue to come only from the data engine (`engines/data/*`), documents remain evidence only (`engines/docs/*`), and output layers only render audited facts (`serving/*`). Heavy tools are activated only behind adapters after the core path proves stable on real data.

**Working branch:** `chatgpt-ai-tasks`

**Current verified baseline:** `.venv` created, `pip install -r requirements.txt`, `pytest -q` => `28 passed, 1 skipped`.

---

## Phase order

1. **P1 — Finish T8b now**: surface price/volume/mix in the card + dashboard.
2. **P2 — Real-data readiness**: lock the first workflow, ingest one real export, and profile failures before any heavy infra work.
3. **P3 — Heavy adapter activation (T9)**: on-prem LLM, Docling, Cognee, Graphiti, stronger OCR tiers.
4. **P4 — Productization (T10-T11)**: enterprise search only after real-document pain is proven; deployment/scheduling/backup after the local loop is stable.
5. **P5 — Self-evolution (T12)**: only after a golden set and acceptance gate exist.

This sequence is mandatory. Do not jump to P3-P5 before P1-P2 are verified.

---

## Phase P1 — T8b surface price/volume/mix drivers

### Why this is first
The current primary bottleneck is not calculation; it is **surfacing**. The decomposition already exists and reconciles. Management value is still trapped because the card/dashboard do not show the driver split.

### Success criteria
- The manager card shows total variance plus price, volume, and mix components.
- The HTML dashboard shows the same driver split clearly.
- The output still fits the one-A4 budget and keeps evidence on every key number.
- Tests cover the new rendering behavior.
- `run_demo.py` visibly exposes the driver split on sample data.

### Files likely to modify
- `serving/card.py`
- `serving/open_design.py`
- `shared/contracts/models.py`
- `engines/brain/orchestrator.py`
- `tests/test_serving.py`
- `tests/test_card_and_audit.py`
- optionally `run_demo.py` if demo text needs to show the split explicitly

### Bite-sized execution slices

#### P1.1 Add a typed driver payload to the card contract
**Objective:** stop passing driver detail as plain strings only.

**Modify:**
- `shared/contracts/models.py`
- `serving/card.py`

**Expected implementation shape:**
- Add a compact typed structure for the driver decomposition summary on the manager card.
- Keep the existing evidence wall intact.
- Do not exceed the one-A4 constraint.

**Verification:**
- targeted test for model/card validation
- `pytest tests/test_card_and_audit.py -q`

#### P1.2 Thread decomposition output into the orchestrator context
**Objective:** make the render layer receive structured decomposition data, not reconstruct it implicitly.

**Modify:**
- `engines/brain/orchestrator.py`
- possibly `run_demo.py`

**Verification:**
- `pytest tests/test_orchestrator.py -q`
- `pytest tests/test_serving.py -q`

#### P1.3 Render price / volume / mix explicitly on the text card and HTML dashboard
**Objective:** make the management output answer “why did it move?” directly.

**Modify:**
- `serving/card.py`
- `serving/open_design.py`

**UI rule:**
- show total variance and the 3 components together
- keep the current bridge chart
- avoid adding a second noisy chart unless readability clearly improves
- preserve sign-off, confidence, and evidence sections

**Verification:**
- assert the HTML includes labels for price, volume, and mix
- assert the text card includes the same split

#### P1.4 Add regression tests before polishing
**Modify/Test:**
- `tests/test_serving.py`
- `tests/test_card_and_audit.py`

**Minimum checks:**
- the dashboard renders the driver labels
- the card output contains the driver split
- no uncited number is introduced
- card length budget still holds

**Command:**
- `pytest tests/test_serving.py tests/test_card_and_audit.py -q`

#### P1.5 Run full validation and demo
**Command:**
- `. .venv/bin/activate && pytest -q`
- `. .venv/bin/activate && python run_demo.py`

**Expected:**
- green tests
- sample output visibly shows price / volume / mix
- no contract break in the trust wall

#### P1.6 Commit and record evidence
**Command:**
- `git add ...`
- `git commit -m "feat: surface variance drivers in card and dashboard"`

**Evidence to log:**
- test count
- sample visible output path or excerpt
- files changed

---

## Phase P2 — Real-data readiness before heavy tools

### Why this comes before heavy infrastructure
The biggest strategic risk now is overbuilding infra before validating the real first workflow and data shape. A fake-perfect architecture on sample data is a trap.

### Required decisions before starting P3
1. Is the first real workflow monthly close, costing variance, or another finance question?
2. What real export will be used first?
3. Who owns the on-prem LLM / graph / OCR infrastructure?

### Tasks

#### P2.1 Lock the first workflow in files
**Modify:**
- `00_control/open_questions.md`
- `00_control/mission.md`
- `00_control/success_contract.md`

**Output:**
- one sentence naming the first real finance workflow
- explicit non-goals for phase 1 productionization

#### P2.2 Ingest one real export with profiling only
**Objective:** do not promise production behavior before seeing real dirty data.

**Likely files:**
- `01_inputs/source_inventory.md`
- `02_understanding/data_map.md`
- `05_validation/error_log.md`
- `05_validation/issue_tracker.md`

**Validation:**
- row counts
- duplicate counts
- missing keys
- locale amount issues
- total/subtotal contamination
- standard matching rate for decomposition

#### P2.3 Promote real-data issues into backlog items
**Rule:** every failure from the real export becomes a named issue or task; nothing stays as a chat observation.

---

## Phase P3 — Heavy adapter activation (T9)

### Gate to start
Do not start this phase until all are true:
- P1 complete and green
- one real export profiled
- first workflow locked
- infra owner/environment known

### Activation order

#### P3.1 On-prem synthesis and embeddings
**Target:** config-backed local inference first.

**Files:**
- `config.yaml`
- adapter wiring files using `ai.*`
- deployment notes under `03_design/` and `00_control/`

**Risk to avoid:** never let confidential data fall back silently to an external provider.

#### P3.2 Docling activation
**Goal:** improve layout/table extraction only where pypdf + OCR is insufficient.

**Do not do:** switch the default extractor globally without A/B evidence on hard documents.

#### P3.3 Cognee activation
**Goal:** promote local JSON relations to a real rebuildable knowledge graph.

**Precondition:** prove which questions the local graph cannot answer today.

#### P3.4 Graphiti activation
**Goal:** move from simple temporal history to a true temporal graph only when time-aware questions justify the cost.

**Precondition:** at least 3 real “what changed and when?” cases collected from users.

#### P3.5 Stronger OCR tiers
Activate `PaddleOCR`, `Surya`, or VLM OCR only against documents that actually defeat Tesseract/RapidOCR.

---

## Phase P4 — Productization (T10-T11)

### T10 Onyx enterprise search
Start only if document volume and retrieval pain are proven. Otherwise this is avoidable infrastructure.

### T11 Deployment + scheduled ingestion + backup/DR
Do this after the local supervised loop is stable.

Required outputs:
- deployment target
- schedule owner
- restore test
- backup path
- failure alert path

---

## Phase P5 — Gated self-evolution (T12)

This is explicitly late-stage.

Do not start before:
- golden evaluation set exists
- output acceptance is measurable
- regressions can be caught automatically
- owner agrees on what “better” means

Otherwise self-evolution will optimize noise.

---

## Cross-phase risks and defenses

| Risk | Where it appears | Defense |
|---|---|---|
| Overbuilding infra before proving value | P2-P3 | force real-export profiling before heavy-tool activation |
| Breaking the trust wall by surfacing uncited numbers | P1 | keep evidence-carrying number facts; add regression tests |
| Governance drift between `.agent-loop` and `00_control` | all phases | update both when the next action changes materially |
| Branch drift from owner-written `main` policy | all phases | keep branch small, green, and mergeable; record owner override in decisions |
| OCR optimism on weak scans | P2-P3 | keep quality gate + human-review routing; never trust low-confidence OCR silently |
| Real data shape mismatches standards | P2 | measure unmatched items explicitly and backlog fixes |
| Silent external AI fallback | P3 | config gate + explicit endpoint verification |
| Search/graph sprawl with low ROI | P3-P4 | demand a concrete unanswered query before adding a subsystem |

---

## Non-negotiable stop conditions

Stop and re-plan if any of these occur:
- a proposed UI change requires inventing a number not carried by evidence
- T8b makes the card exceed its one-A4 budget
- a real export exposes a workflow different from the current mission
- heavy-tool activation requires cloud fallback for confidential data
- tests go red and the failure reason is not understood

---

## Verification ladder

### For every coding slice
1. targeted test first
2. targeted test green
3. full `pytest -q`
4. demo run if behavior is user-visible
5. evidence log update
6. run log update

### For every architecture jump
1. precondition file check
2. explicit rollback path
3. adapter activation proof
4. no-regression check on the core path

---

## Recommended next action

Start **P1 / T8b** immediately.

That is the highest-leverage, lowest-risk move because:
- the calculation already exists
- no heavy infra is needed
- it removes the current primary bottleneck
- it upgrades the system from technically complete to manager-usable
