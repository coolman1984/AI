---
name: knowledge-search
description: Use whenever the user asks what the system knows about a process, workflow, KPI, document family, contradiction, claim, or version history and the job is to retrieve compact linked records instead of loading the whole architecture or dumping raw documents.
---

# Skill — Knowledge Search

## Mission

Answer "what do we know about process X?" by retrieving linked registry records,
workflow versions, claims, open questions, and contradictions from stored knowledge.

## Use this skill when
- the user asks what the system knows about a process, workflow, KPI, or document family
- the task needs version history, valid-time selection, or workflow diffs
- the task needs open questions, contradictions, or linked claims for a topic
- routine retrieval should load one skill instead of the whole architecture plan

## Do not use this skill for
- primary document extraction or OCR
- numeric variance computation
- final executive sign-off or release gating

## Input contract
- natural-language query or entity/topic string
- optional period for valid-time questions
- optional family id or document id when known

## Output contract
- matching workflow versions, registry hits, claims, open questions, contradictions
- ontology-resolved entity edges when available
- compact result object safe for agent context

## Raw data ban
- no raw full-document dumps in the response
- return linked record summaries and citations only

## Inputs expected
- natural-language query or entity/topic string
- optional period for valid-time questions (for example `2025-Q2`)
- optional family id or document id when known

## Outputs expected
- matching workflow family versions with valid-time metadata
- registry document hits with family/version labels
- claims explicitly labeled `CLAIM — not a verified fact`
- open questions with status and owner
- contradictions that require human resolution
- compact result object safe for agent context

## Shared rules from the core contract
- preserve source identity and citations in every hit
- facts and claims must remain visually separated
- contradictions are surfaced, never auto-resolved
- missing knowledge must be visible, not invented

## Standard workflow
1. search stored registry and workflow families for the topic
2. include relevant claims, open questions, and contradictions when matched
3. label claims as claims, not facts
4. return compact linked records for downstream audit or reporting skills

## Key checks
- workflow versions include valid-time and ingest-time separately
- duplicate source hashes reconcile instead of creating phantom versions
- non-comparable comparison fields stay explicit
- no raw full-document dumps in the response

## Token budget
- target: <= 1,500 tokens of retrieved knowledge per query
- hard cap: 20 items per section in the search response

## Invariants
- no LLM calls inside registry/search/diff modules
- any future graph or vector backend must sit behind `engines/brain/search.py`
- search never promotes claims into facts
- synthesis uses canonical entity IDs from `engines/brain/ontology.py`
- factory comparison requires `compare_factories` availability gate
- idea synthesis outputs are labeled `AI-SUGGESTED IDEA` only

## Existing repo anchors
- `engines/brain/search.py`
- `engines/brain/ontology.py`, `engines/brain/edges.py`
- `engines/brain/comparison.py` (`compare_factories`)
- `engines/brain/idea_synthesis.py`
- `tests/test_knowledge_search.py`, `tests/test_ontology.py`
