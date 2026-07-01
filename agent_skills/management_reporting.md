# Skill — Management Reporting

## Mission

Turn trusted, audited operational findings into a concise manager-facing output: card, dashboard, presentation, or decision-ready summary.

## Use this skill when
- the task is to produce a card, dashboard, deck, or summary for decision-makers
- the analysis already exists and needs shaping
- the question is how to present the result clearly without losing evidence

## Do not use this skill for
- computing core numbers
- raw ingestion
- approving release without audit status

## Inputs expected
- audited or audit-ready analysis package
- evidence-bearing numbers
- business framing for the current decision
- any output format constraint such as one-page card or deck

## Outputs expected
- concise manager-facing artifact
- explicit main message
- visible drivers where available
- evidence-aware claims only
- recommended action or decision framing

## Shared rules from the core contract
- render, do not calculate
- do not upgrade weak evidence into strong prose
- preserve confidence and sign-off semantics
- keep the next decision obvious

## Standard workflow
1. identify the real management question
2. pull the top facts from the trusted analysis package
3. shape the answer into a small number of high-value points
4. expose key drivers and risks
5. preserve evidence and confidence
6. hand the result to audit or release flow if needed

## Key checks
- does the output answer “what happened, why, and what next?”
- does every important number trace back cleanly?
- is the output short enough for its target format?
- is uncertainty visible rather than buried?

## Never do
- never compute fresh numbers in the report layer
- never hide missing evidence behind polished language
- never overload the output with analysis noise
- never let aesthetics outrank trust

## Typical downstream handoff
Usually hands off to:
- `agent_skills/audit_and_trust.md`
- or directly to human review if audit already passed

## Existing repo anchors
- `serving/AGENTS.md`
- `serving/card.py`
- `serving/open_design.py`
- `tests/test_card_and_audit.py`
- `tests/test_serving.py`

## Definition of done
Done means:
- the artifact is decision-oriented
- no uncited number appears
- confidence and sign-off state are visible
- the output is usable by management, not just technically correct