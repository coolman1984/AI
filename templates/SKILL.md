---
skill_id: SK-XXX
version: 1.0.0
risk_level: low
status: active
---

# Skill: <name>

## Purpose
One paragraph: what business outcome this produces and for whom.

## Use this skill when
- <trigger 1>
- <trigger 2>

## Do NOT use this skill when
- <anti-trigger and which skill to use instead>

## Inputs
| Input | Required | Format | Example |
|---|---|---|---|

## Outputs
| Output | Location | Format | Consumer |
|---|---|---|---|

## Allowed tools
Only these tool_ids: <list>. Anything else is a skill violation — stop and report.

## Forbidden actions
- <explicit list — the agent must refuse, not work around>

## Workflow
1. <step> — tool: <tool_id> — evidence written: <what>
2. <step> — gate: <gate name> — on fail: <recovery ref>
3. ...
(Every step names its tool or gate. No step says "figure out".)

## Validation
| Gate | Pass condition | On fail |
|---|---|---|

## Evidence requirements
What must exist in the ledger before this skill may report success.

## Failure recovery
| Failure | Detection | Recovery |
|---|---|---|

## Known edge cases
- <case>: <handling>

## Examples
### Example 1: <realistic case with real-shaped fake data>
Input → key steps → output → evidence produced.

## Tests
- tests/<file>::<test> — what it proves.

## Improvement notes
Link lessons that shaped this version: [[lesson-...]]. Next known weakness: <one line>.
