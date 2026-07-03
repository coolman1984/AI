# Agent Core Contract

This file defines the shared contract that all agent skills in this repository must obey.

It is the central spine that preserves consistency while allowing the work to be split into specialized skills.

---

## Purpose

Every skill may specialize in a different part of the workflow, but they must all speak the same operational language.

That means the same:
- run identity
- storage targets
- naming rules
- trust logic
- evidence expectations
- failure semantics
- delivery semantics

If those differ by skill, the system becomes expensive, brittle, and non-restartable.

---

## Shared objects every skill must understand

### 1. Run identity
Every important execution should carry:
- `run_id`
- `task_id` when applicable
- `source_type`
- `source_path`
- `source_sheet` or equivalent sub-source when applicable
- `started_at`
- `finished_at`
- `status`

### 2. Source identity
Every result must preserve where it came from:
- original file path
- worksheet / page / slide / message / attachment when applicable
- row index or field locator when possible
- extraction method
- parser or transform assumptions

### 3. Evidence identity
Every released claim must be traceable to:
- source location
- calculation method
- query or transform path
- confidence level
- rejection or exception state if relevant

---

## Skill input contract

Every skill should declare these inputs explicitly:
- mission of the current task
- required source(s)
- expected upstream artifact(s)
- acceptance condition
- blocking conditions

If the upstream artifact is missing, the skill should fail clearly instead of inventing a substitute.

---

## Skill output contract

Every skill should produce outputs that are easy for the next skill to consume.

Minimum output metadata:
- `artifact_type`
- `artifact_path` or storage target
- `run_id`
- `status`
- `confidence`
- `evidence_summary`
- `issues_found`
- `recommended_next_step`

---

## Naming rules

The same concept must use the same name across all skills whenever possible.

Prefer stable repository language such as:
- product_code
- cost_center
- material_cost_variance
- actual_amount
- budget_amount
- source_type
- run_id
- reject_reason
- evidence
- sign_off

Do not let one skill rename core concepts casually.

If a business synonym is needed, map it in a dictionary or terminology file instead of changing the contract.

---

## Storage rules

### Raw inputs
Never overwrite raw files.

### Working outputs
Intermediate artifacts belong in governed execution or temporary folders, not ad-hoc locations.

### Durable outputs
Decision-ready artifacts and source-of-truth notes belong in the governed project locations already used by this repository.

### Rejections
Rejected rows or failed extraction units must be persisted with a reason. Silent dropping is forbidden.

---

## Trust rules

1. No generated number may be treated as a fact.
2. Numeric conclusions must come from the trusted data/query path.
3. Output layers render; they do not calculate.
4. Audit is independent from the primary build path.
5. Low-confidence evidence must surface as review work, not as polished certainty.
6. Human sign-off is required before release to decision-makers.

---

## Failure contract

A skill must distinguish clearly between:
- success
- partial success
- blocked
- failed
- needs human review

A partial result is allowed only if it is labeled honestly and the missing piece is explicit.

---

## Confidence contract

Use confidence to express release readiness, not style.

Recommended semantic levels:
- High — evidence and reconciliation are sufficient for the current stage
- Medium — useful, but review is still needed before release
- Low — incomplete, weakly grounded, or operationally risky

If a number mismatch or evidence gap exists, the result cannot be treated as High.

---

## Handoff rule

Each skill should end by making the next step obvious.

Good handoff:
- what was produced
- where it was stored
- what remains unresolved
- which skill should load next

Bad handoff:
- vague prose
- no artifact path
- no confidence
- no evidence
- no next-step instruction

---

## Priority rule

When there is tension between elegance and trust, choose trust.

When there is tension between breadth and restartability, choose restartability.

When there is tension between speed and evidence, choose evidence.

That is the operating center of this system.