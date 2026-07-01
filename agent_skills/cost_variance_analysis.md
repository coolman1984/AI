# Skill — Cost Variance Analysis

## Mission

Turn trusted tabular inputs into a grounded explanation of cost movement, with drivers that reconcile exactly to the governed numeric path.

## Use this skill when
- the task is budget vs actual
- the question is why cost changed
- the task needs price / volume / mix or similar driver logic
- the user needs a factor-level explanation, not only totals

## Do not use this skill for
- raw file ingestion
- OCR-heavy extraction
- final manager-card formatting
- release approval

## Inputs expected
- trusted loaded data or query-ready tables
- business lens or analysis period
- relevant comparison basis such as budget, standard, or prior period
- any driver schema already defined for the workflow

## Outputs expected
- reconciled variance result
- driver decomposition
- issues or unmatched items list
- confidence statement about the explanatory quality
- recommended downstream report path

## Shared rules from the core contract
- numbers come from the trusted query path only
- every conclusion must be explainable from evidence
- mismatches must surface, not be rounded away socially
- use central names for business concepts

## Standard workflow
1. confirm the comparison basis
2. confirm the trusted input tables
3. compute the top-line variance
4. decompose into approved driver categories
5. identify the biggest contributors
6. flag unmatched or ambiguous items
7. prepare a downstream explanation package for reporting or audit

## Key checks
- exact reconciliation to the total variance
- no double counting
- no hidden subtotal contamination
- driver logic is stable and named
- unmatched records are measured explicitly

## Never do
- never invent a driver because it “sounds plausible”
- never pass off an unreconciled bridge as final
- never write the executive narrative here if the numeric explanation is still unstable
- never hide uncertainty around standards, mappings, or source drift

## Typical downstream handoff
Usually hands off to:
- `agent_skills/audit_and_trust.md`
- then `agent_skills/management_reporting.md`

## Existing repo anchors
- `engines/data/variance.py`
- `engines/data/drivers.py`
- `shared/contracts/models.py`
- `tests/test_data_pipeline.py`
- `tests/test_drivers.py`

## Definition of done
Done means:
- the variance reconciles exactly
- the driver split is explicit
- evidence-bearing numeric outputs are ready
- unresolved ambiguity is stated clearly before reporting