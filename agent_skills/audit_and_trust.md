# Skill — Audit and Trust

## Mission

Act as the release gate between analysis and decision-making by independently re-checking important results, surfacing uncertainty, and enforcing human accountability.

## Use this skill when
- a result may be shown to a manager
- the user asks if the output is safe to trust
- there are conflicting numbers, data quality concerns, or missing evidence
- a sign-off step is required

## Do not use this skill for
- primary raw ingestion
- initial report drafting from scratch
- replacing the main data engine’s calculations

## Inputs expected
- draft result or card
- trusted numeric source path
- evidence summary
- data quality context
- sign-off context when applicable

## Outputs expected
- pass or fail gate
- reconciliation result
- certainty view
- required human questions if confidence is insufficient
- release recommendation

## Shared rules from the core contract
- audit must be independent from the primary result path
- a mismatch must fail loudly
- no human sign-off means no final release
- low confidence must become review work, not hidden prose

## Standard workflow
1. re-check the key numbers independently
2. reconcile totals, counts, and bridge logic
3. inspect evidence coverage
4. score certainty based on quality, materiality, and traceability
5. route unresolved issues to human review
6. record sign-off state clearly

## Key checks
- number match within tolerance
- conservation checks hold
- evidence exists for every critical claim
- sign-off identity is recorded when required
- uncertainty is surfaced explicitly

## Never do
- never approve an unsigned output
- never convert a failed check into a soft warning if the result is for management use
- never let presentation quality substitute for audit quality
- never collapse evidence and opinion into one thing

## Typical downstream handoff
Usually hands off to:
- `agent_skills/management_reporting.md` when re-shaping is needed
- or directly to final governed outputs when the artifact is already suitable

## Existing repo anchors
- `engines/audit/AGENTS.md`
- `engines/audit/audit.py`
- `tests/test_card_and_audit.py`

## Definition of done
Done means:
- the result is clearly passed, failed, or blocked
- the trust reason is explicit
- human review points are named when needed
- release readiness is unambiguous