# Phase B-F Build Cards -- Executive Assistant Expansion

Source: `03_design/assistant_master_plan.md` sections 3-4 and
`03_design/current_implementation_plan.md`. Phase A cards remain in
`03_design/phase_a_cards.md` and are not repeated here.

Each card is one write -> review -> test cycle. Each new capability must ship
with engine code, tests, a skill card, a routing-map entry, and an MCP tool.

---

## B.1 -- Native PPTX extractor

**Goal:** Read PowerPoint decks into the same `Document` and `Page` shape used by
PDF/text extraction, preserving slide numbers as page numbers.

**Files:**
- `engines/docs/pptx.py` (new) -- `PptxExtractor.extract(path) -> Document`.
- `engines/docs/extract.py` (edit) -- route `.pptx` to `PptxExtractor` unless Docling is explicitly configured.
- `engines/docs/AGENTS.md` (edit) -- add PPTX public interface.
- `agent_skills/document_evidence_extraction.md` (edit) -- document PPTX path.
- `AGENT_SKILL_MAP.md` (edit) -- route PowerPoint/deck tasks.
- `mcp_server/server.py` (edit) -- expose `extract_document` or `ingest_deck` tool.

**Test file:** `tests/test_pptx_extraction.py`
- Creates a synthetic `.pptx` with two slides and one table.
- Extractor returns `Document.source_format == "pptx"`.
- Slide 1 text appears in `pages[0].text`; slide number is `page_no == 1`.
- Table text is not silently lost; it is either in page text or `Document.tables`.
- Unsupported or empty decks return warnings, not crashes.

**Acceptance criteria:**
- No LLM calls in the extractor.
- Slide numbers are stable and citation-ready.
- Full pytest and ruff pass.

**Dependencies:** A0 gate.

---

## B.2 -- Chunked map-reduce coverage

**Goal:** Summarize long documents/decks without silent truncation; every page or
slide must be assigned to a chunk and accounted for in the merge.

**Files:**
- `engines/docs/summarize.py` (new) -- chunk manifest, map summaries, merge summary, coverage report.
- `engines/docs/report_reader.py` (edit) -- replace hard truncation for deck/report summarization.
- `engines/docs/AGENTS.md` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `summarize_document`.

**Test file:** `tests/test_chunked_summary.py`
- A 60-slide synthetic document creates multiple chunks.
- Coverage manifest includes every page exactly once.
- If one page cannot fit or is missing, the run returns blocked/needs_review instead of a partial summary.
- Merge output includes source chunk ids and warnings.
- No raw full deck text is put into a single prompt.

**Acceptance criteria:**
- No silent truncation path remains for long report/deck summarization.
- Coverage report is persisted with the run.
- Full pytest and ruff pass.

**Dependencies:** A0 gate, B.1.

---

## B.3 -- WorkflowRecord schema

**Goal:** Store deck understanding as a structured workflow record: purpose,
steps, owners, KPIs, changes, risks, and open questions, each with citations.

**Files:**
- `engines/docs/workflow_record.py` (new) -- `WorkflowRecord`, `WorkflowField`, validation.
- `shared/contracts/models.py` (edit only if shared contract placement is chosen).
- `engines/docs/AGENTS.md` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `extract_workflow_record`.

**Test file:** `tests/test_workflow_record.py`
- Missing citation on any required field raises `ValueError`.
- Required fields include purpose, steps, roles/owners, KPIs, what_changed, open_questions.
- Page/slide locators are preserved.
- Record serializes to deterministic JSON.

**Acceptance criteria:**
- Workflow records are evidence objects, not free-form summaries.
- No field can enter the record without a locator.
- Full pytest and ruff pass.

**Dependencies:** B.1, B.2.

---

## B.4 -- Original-language retention and provenance stamp

**Goal:** Store Korean source text beside every English field and stamp every
record with hash, run id, model, prompt version, and deterministic confidence inputs.

**Files:**
- `engines/docs/workflow_record.py` (edit).
- `engines/docs/provenance.py` (new).
- `engines/docs/AGENTS.md` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit).

**Test file:** `tests/test_provenance_stamp.py`
- Every translated field has `source_text`, `translated_text`, `language`, and locator.
- Record stamp includes source hash, ingest run id, model name, model version or configured id, prompt version, timestamp.
- Confidence value is computed from deterministic inputs, not LLM self-report.
- Re-running the same source hash produces the same source identity.

**Acceptance criteria:**
- Disputed translation can be traced back to original Korean text.
- No model-generated confidence score is accepted.
- Full pytest and ruff pass.

**Dependencies:** B.3.

---

## B.5 -- Korean-English glossary and critical-term check

**Goal:** Feed a growing factory glossary into translation and flag critical
term disagreements through back-translation spot checks.

**Files:**
- `engines/docs/glossary.py` (new).
- `engines/docs/translation_check.py` (new).
- `engines/docs/report_reader.py` or `engines/docs/summarize.py` (edit to pass glossary context).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `check_translation_terms`.

**Test file:** `tests/test_translation_check.py`
- Glossary match ratio is computed from text and glossary entries.
- Unknown critical term creates a review flag.
- Back-translation disagreement on a KPI term creates a review flag.
- The module does not ask an LLM to invent a numeric confidence score.

**Acceptance criteria:**
- Glossary grows through explicit accepted entries only.
- Critical-term disagreement blocks the brief gate until reviewed.
- Full pytest and ruff pass.

**Dependencies:** B.3, B.4.

---

## B.6 -- Non-numeric brief audit

**Goal:** Add an independent audit path for claims that are not pure numbers:
second extraction, citation re-check, disagreement routing, and human review.

**Files:**
- `engines/audit/brief_audit.py` (new).
- `engines/audit/AGENTS.md` (edit).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `audit_brief_claims`.

**Test file:** `tests/test_brief_audit.py`
- A matching independent extraction passes.
- A claim with unsupported citation fails.
- A materially different second extraction creates `needs_human=True`.
- Numeric claims still defer to `engines/docs/verify.py`.

**Acceptance criteria:**
- "Audited brief" has a real non-numeric audit, not a prompt promise.
- Disagreements never auto-merge.
- Full pytest and ruff pass.

**Dependencies:** A0 gate, B.3.

---

## B.7 -- Korean image-share measurement

**Goal:** Measure scanned/image-only share in HQ decks and route low-confidence
Korean OCR pages to review before deciding whether VLM work is urgent.

**Files:**
- `engines/docs/image_profile.py` (new).
- `engines/docs/ocr.py` (edit only for Korean language configuration hooks).
- `engines/docs/AGENTS.md` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `profile_deck_images`.

**Test file:** `tests/test_korean_ocr_profile.py`
- Born-digital slide is counted separately from image-only slide.
- Korean OCR unavailable creates a clear readiness warning.
- Low-confidence OCR marks the page `needs_review`.
- Summary reports image-only share and review count.

**Acceptance criteria:**
- VLM escalation is based on measurement, not guesswork.
- Low-confidence Korean text never becomes trusted knowledge.
- Full pytest and ruff pass.

**Dependencies:** B.1.

---

## B.8 -- Email and attachment intake baseline

**Goal:** Add an email intake module that extracts body, metadata, and attachments
into the same governed document spine and registry path.

**Files:**
- `engines/email/extract.py` (new).
- `engines/email/AGENTS.md` (new).
- `engines/docs/extract.py` (edit only for attachment handoff if needed).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `ingest_email`.

**Test file:** `tests/test_email_extraction.py`
- Synthetic `.eml` body, sender, date, subject are extracted.
- Attachment is routed through document extraction and keeps parent email id.
- Default privacy tier is Tier 1 unless metadata explicitly marks Tier 2.
- Failed attachment extraction records a failure instead of stopping the whole email.

**Acceptance criteria:**
- Email data follows the same privacy and evidence rules as documents.
- No email content is sent externally.
- Full pytest and ruff pass.

**Dependencies:** A0 gate; B.1 helpful but not blocking.

---

## B.9 -- First HQ deck brief gate

**Goal:** Run the full Tier 2 HQ deck path and produce the first owner-reviewed
one-page brief with slide citations and audit result.

**Files:**
- `serving/decision_brief.py` (new minimal deck brief renderer or staging function).
- `engines/docs/report_reader.py` / `engines/docs/summarize.py` (edit only for integration).
- `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `build_hq_deck_brief`.

**Test file:** `tests/test_hq_deck_brief.py`
- Synthetic deck produces a one-page brief object.
- Every claim has slide citation.
- Unsupported claim is absent from trusted brief and present in claims/review output.
- Brief includes coverage report, glossary flags, audit status, and sign-off placeholder.

**Acceptance criteria:**
- Owner can compare brief to original deck.
- B gate evidence is recordable without using factory Tier 1 data.
- Full pytest and ruff pass.

**Dependencies:** B.1-B.7.

---

## C.1 -- Document registry

**Goal:** Create one queryable registry of every ingested document with hash,
tier, family, version, run id, and status.

**Files:**
- `engines/brain/registry.py` (new).
- `engines/brain/AGENTS.md` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `register_document` and `get_document_registry`.

**Test file:** `tests/test_document_registry.py`
- Same file hash deduplicates instead of creating a second current record.
- Registry stores source path, hash, tier, status, family id, version label, ingest run id.
- Status transitions are valid and reject unknown statuses.

**Acceptance criteria:**
- Registry becomes the map of the second brain.
- Dedup is hash-based, not filename-only.
- Full pytest and ruff pass.

**Dependencies:** B gate.

---

## C.2 -- Workflow families and versioning

**Goal:** Group workflow records into version families with valid-time separated
from ingest-time.

**Files:**
- `engines/brain/workflow_family.py` (new).
- `engines/brain/registry.py` (edit).
- `engines/brain/AGENTS.md` (edit).
- `agent_skills/knowledge_search.md` (new or edit if created earlier).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `register_workflow_version`.

**Test file:** `tests/test_workflow_family.py`
- v1 and v2 share a family id but different version ids.
- Valid-time and ingest-time are stored separately.
- Query "what was true in Q2 2025" selects by valid-time.
- Duplicate source hash reconciles instead of creating a phantom version.

**Acceptance criteria:**
- Time questions are answerable without guessing.
- Re-ingestion is deterministic.
- Full pytest and ruff pass.

**Dependencies:** C.1.

---

## C.3 -- Workflow diff view

**Goal:** Show "what changed since v1" for a workflow family using cited
WorkflowRecord fields.

**Files:**
- `engines/brain/workflow_diff.py` (new).
- `engines/brain/AGENTS.md` (edit).
- `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `diff_workflow_versions`.

**Test file:** `tests/test_workflow_diff.py`
- Added, removed, and changed fields are classified separately.
- Each diff item carries old and new citations where available.
- Missing old/new version raises a clear error.

**Acceptance criteria:**
- Owner can absorb a new rollout through a deterministic diff.
- Diff does not synthesize unstated reasons.
- Full pytest and ruff pass.

**Dependencies:** C.2.

---

## C.4 -- Open questions and decision outcomes

**Goal:** Make open questions queryable and link workflow records to decision
memory/outcomes.

**Files:**
- `engines/brain/open_questions.py` (new).
- `engines/learning/outcomes.py` (new).
- `engines/brain/AGENTS.md` (edit).
- `agent_skills/audit_and_trust.md` and `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `list_open_questions`, `resolve_open_question`, `link_decision_outcome`.

**Test file:** `tests/test_open_questions.py`
- Open question has status, source, owner, evidence, and optional resolver.
- Resolving a question records by-what evidence.
- Workflow record can reference a decision/outcome id.
- Resolved items remain queryable historically.

**Acceptance criteria:**
- Unknowns are stored, not hidden in prose.
- Decision learning can trace back to the workflow that triggered it.
- Full pytest and ruff pass.

**Dependencies:** C.1, B.3.

---

## C.5 -- Knowledge artifacts in git

**Goal:** Write summaries, workflow records, and briefs as deterministic markdown
artifacts that are durable, diffable, and hash-deduplicated.

**Files:**
- `engines/wiki/artifacts.py` (new).
- `engines/wiki/AGENTS.md` (new).
- `engines/docs/workflow_record.py` (edit only for export hook if needed).
- `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `write_knowledge_artifact`.

**Test file:** `tests/test_knowledge_artifacts.py`
- Artifact path is deterministic from source hash and record type.
- Markdown contains citations and provenance stamp.
- Same source hash updates/reconciles expected artifact, not duplicate clutter.
- No git command is executed by the engine test; engine only writes files.

**Acceptance criteria:**
- Knowledge can survive `.brain` rebuilds.
- Artifacts are human-readable.
- Full pytest and ruff pass.

**Dependencies:** C.1, C.2.

---

## C.6 -- Samsung IR quarter comparison

**Goal:** Prove temporal comparison on public Samsung IR PDFs before using
private factory reports.

**Files:**
- `engines/brain/comparison.py` (new).
- `engines/docs/report_reader.py` or registry ingestion hooks (edit only for public corpus path).
- `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `compare_public_ir_quarters`.

**Test file:** `tests/test_ir_comparison.py`
- Two synthetic/public-like period records compare revenue/KPI claims only when citations exist.
- Missing comparable field returns "not comparable" instead of invented analysis.
- Output includes period labels and source citations.

**Acceptance criteria:**
- First comparison proof uses zero private data.
- Non-comparable items are explicit.
- Full pytest and ruff pass.

**Dependencies:** C.1-C.3.

---

## C.7 -- Contradiction-surfacing view

**Goal:** Surface conflicts between claims/workflow records without auto-resolving
them.

**Files:**
- `engines/brain/contradictions.py` (new).
- `engines/brain/claims.py` (edit only if query helpers are needed).
- `agent_skills/audit_and_trust.md` and `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `find_contradictions`.

**Test file:** `tests/test_contradictions.py`
- Same entity/KPI with different cited values creates a contradiction.
- Same value with different wording does not create a false contradiction.
- Output lists both sources and requires human resolution.

**Acceptance criteria:**
- Safer value arrives before generative synthesis.
- Contradictions are visible, not hidden by merge logic.
- Full pytest and ruff pass.

**Dependencies:** C.1, C.2, C.4.

---

## C.8 -- Knowledge search skill and tool

**Goal:** Let an agent ask "what do we know about process X?" and get linked
records, claims, versions, contradictions, and open questions.

**Files:**
- `engines/brain/search.py` (new).
- `agent_skills/knowledge_search.md` (new).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `search_knowledge`.

**Test file:** `tests/test_knowledge_search.py`
- Search returns workflow records and family versions.
- Claims are labeled as claims, not facts.
- Open questions and contradictions are included when relevant.
- Result shape is compact and agent-safe.

**Acceptance criteria:**
- Routine retrieval loads one skill, not the whole plan.
- Facts and claims remain visually separated.
- Full pytest and ruff pass.

**Dependencies:** C.1-C.7.

---

## D.1 -- Decision brief generator

**Goal:** Generate a one-page decision brief from stored evidence: question,
evidence, options, risks, recommendation, and sign-off line.

**Files:**
- `serving/decision_brief.py` (new).
- `serving/AGENTS.md` (edit).
- `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `build_decision_brief`.

**Test file:** `tests/test_decision_brief.py`
- Brief refuses evidence-free claims.
- Numeric evidence renders with provenance tags.
- Brief has sign-off status and cannot mark itself released.
- Output stays within one-page budget fields.

**Acceptance criteria:**
- No freestyled executive recommendation without evidence.
- Sign-off line is mandatory.
- Full pytest and ruff pass.

**Dependencies:** C gate, B.6, C.8.

---

## D.2 -- Meeting pack assembler

**Goal:** Assemble CFO/CEO meeting packs from audited numbers, workflow knowledge,
risks, open questions, and talking points.

**Files:**
- `serving/meeting_pack.py` (new).
- `serving/AGENTS.md` (edit).
- `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `build_meeting_pack`.

**Test file:** `tests/test_meeting_pack.py`
- Pack pulls from stores by topic and period.
- Missing audited number is labeled missing, not invented.
- Open questions are included with status.
- Pack includes release/sign-off state.

**Acceptance criteria:**
- Pack is built from stores, never raw prompt memory.
- Missing evidence is visible.
- Full pytest and ruff pass.

**Dependencies:** D.1.

---

## D.3 -- Report and article generator

**Goal:** Produce management reports, process explainers, and rollout summaries
from stored knowledge with citations.

**Files:**
- `serving/report_article.py` (new).
- `serving/AGENTS.md` (edit).
- `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `build_report_article`.

**Test file:** `tests/test_report_article.py`
- Each paragraph includes source citations or is rejected.
- Output types have explicit templates.
- Numbers use provenance tags and cannot be generated by template text.

**Acceptance criteria:**
- Publishable outputs come from stored knowledge.
- Unsupported prose is blocked or routed to review.
- Full pytest and ruff pass.

**Dependencies:** D.1.

---

## D.4 -- All-output sign-off enforcement

**Goal:** Extend named human sign-off beyond finance cards to every executive
output type.

**Files:**
- `serving/signoff.py` (new).
- `serving/open_design.py` (edit).
- `serving/decision_brief.py`, `serving/meeting_pack.py`, `serving/report_article.py` (edit).
- `agent_skills/audit_and_trust.md` and `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `sign_off_output`.

**Test file:** `tests/test_executive_signoff.py`
- Unsigned brief/pack/report cannot render as released.
- Failed audit cannot be signed off as approved.
- Sign-off records approver, timestamp, certainty/audit state, and note.

**Acceptance criteria:**
- Nothing reaches management wearing system approval without a named human.
- Existing finance sign-off behavior remains green.
- Full pytest and ruff pass.

**Dependencies:** D.1-D.3.

---

## D.5 -- Rendering reuse for briefs and packs

**Goal:** Reuse the existing HTML/PPTX rendering layer for decision briefs,
meeting packs, and report summaries.

**Files:**
- `serving/open_design.py` (edit).
- `serving/decision_brief.py`, `serving/meeting_pack.py`, `serving/report_article.py` (edit).
- `serving/AGENTS.md` (edit).
- `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- expose export tool for executive outputs.

**Test file:** `tests/test_serving_outputs.py`
- Signed decision brief renders HTML.
- Signed meeting pack renders HTML and PPTX when `python-pptx` is available.
- Unsigned output produces draft/watermarked state only.
- Renderer never computes numbers.

**Acceptance criteria:**
- One rendering layer serves cards and executive outputs.
- Output-only invariant stays intact.
- Full pytest and ruff pass.

**Dependencies:** D.4.

---

## D.6 -- Owner feedback loop

**Goal:** Record owner verdicts on briefs and packs so corrections feed the
glossary, golden set, and trust metrics.

**Files:**
- `engines/learning/feedback.py` (new).
- `engines/learning/AGENTS.md` (new if missing).
- `00_control/restart_notes.md` (edit for session summary pattern).
- `agent_skills/audit_and_trust.md` and `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `record_output_feedback`.

**Test file:** `tests/test_feedback_loop.py`
- Verdict values are limited to useful, corrected, wrong, or needs_followup.
- Correction links to output id and evidence/citation when applicable.
- Glossary candidate can be produced from a corrected term without auto-accepting it.

**Acceptance criteria:**
- Feedback is structured and reusable.
- Corrections do not silently overwrite trusted records.
- Full pytest and ruff pass.

**Dependencies:** D.4.

---

## E.1 -- Real export profiling gate

**Goal:** When the first real SAP-scale export arrives, profile it safely before
expansion and record issues without sending data outside the machine.

**Files:**
- `engines/data/profile.py` (new).
- `engines/data/AGENTS.md` (edit).
- `00_control/evidence_log.md` and `00_control/task_queue.md` (status updates only after run).
- `agent_skills/spreadsheet_ingestion.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `profile_real_export`.

**Test file:** `tests/test_real_export_profile.py`
- Synthetic wide file profile reports row count, column count, likely totals, duplicates, type candidates.
- Large-file path streams or uses DuckDB; test guards against whole-file materialization.
- No profile value becomes a management number.

**Acceptance criteria:**
- P2.2 can move when owner supplies the export.
- Profile is evidence, not a promise of production readiness.
- Full pytest and ruff pass.

**Dependencies:** A0 gate; external real export availability for final evidence.

---

## E.2 -- Multi-sheet Excel ingestion

**Goal:** Ingest multi-sheet Excel files into the unified spine with sheet-level
run context and reject tracking.

**Files:**
- `engines/data/ingest.py` (edit).
- `engines/data/AGENTS.md` (edit).
- `agent_skills/spreadsheet_ingestion.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add/update `ingest_spreadsheet`.

**Test file:** `tests/test_ingestion_spine.py`
- Synthetic workbook with two sheets creates one tracked run per sheet or a run with `source_sheet`.
- Reject rows include sheet name.
- Conservation holds per sheet and total.

**Acceptance criteria:**
- IS2.3 is complete.
- Sheet context is never lost.
- Full pytest and ruff pass.

**Dependencies:** E.1 or existing IS2.2 path.

---

## E.3 -- Per-column type inference

**Goal:** Keep raw values while adding typed numeric/date values and quarantining
unconvertible critical cells.

**Files:**
- `engines/data/ingest.py` (edit) or new `engines/data/types.py`.
- `engines/data/AGENTS.md` (edit).
- `agent_skills/spreadsheet_ingestion.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit).

**Test file:** `tests/test_ingestion_spine.py`
- Numeric, date, and text columns are inferred.
- Locale numeric values parse deterministically.
- Unconvertible critical numeric cells are quarantined with reason.
- Raw value remains available beside typed value.

**Acceptance criteria:**
- IS2.4 is complete.
- Type inference never destroys raw evidence.
- Full pytest and ruff pass.

**Dependencies:** E.2.

---

## E.4 -- Real-data issue promotion

**Goal:** Convert real-export profiling failures into named issue rows/cards
instead of burying them in notes.

**Files:**
- `00_control/open_questions.md` (edit).
- `05_validation/issue_tracker.md` (edit).
- `00_control/task_queue.md` (manual row additions only after owner/evaluator decision).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).

**Test file:** none; doc-control gate.
- Evaluator verifies each material real-data failure has an owner, status, and next action.
- No code change is bundled in this card.

**Acceptance criteria:**
- Material real-data findings are not lost after P2.2.
- New implementation work gets its own task row before code starts.

**Dependencies:** E.1-E.3.

---

## F.1 -- Golden evaluation set

**Goal:** Create a curated eval set for deck/report extraction, citation support,
brief generation, and regression gates.

**Files:**
- `eval/AGENTS.md` (new).
- `eval/golden_manifest.json` (new).
- `eval/README.md` (new).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `run_golden_eval`.

**Test file:** `tests/test_golden_eval.py`
- Manifest validates fixture ids, source type, expected claims, expected citations.
- Runner reports pass/fail per fixture.
- Missing fixture blocks eval with clear error.

**Acceptance criteria:**
- Self-learning and model changes have a real gate.
- Golden set uses synthetic/public fixtures until owner provides approved samples.
- Full pytest and ruff pass.

**Dependencies:** B gate.

---

## F.2 -- MCP access control at dispatch

**Goal:** Enforce `gov/access.py` in the MCP dispatch layer so tools cannot be
called outside caller scope.

**Files:**
- `mcp_server/server.py` (edit).
- `gov/access.py` (edit only if scope model needs extension).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).

**Test file:** `tests/test_mcp_access.py`
- Unauthorized role cannot call a scoped finance/factory tool.
- Authorized wildcard role can call allowed tool.
- Unknown tool still raises unknown-tool error, not access leak.
- Existing direct tool functions remain testable.

**Acceptance criteria:**
- Access control is not decorative.
- Dispatch is the enforcement point.
- Full pytest and ruff pass.

**Dependencies:** C gate, F.1 can run in parallel.

---

## F.3 -- Skill token budgets and output contracts

**Goal:** Make every skill card declare token budget, input contract, compressed
output contract, and raw-data ban.

**Files:**
- `agent_skills/*.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `AGENT_CORE_CONTRACT.md` (edit if central schema is needed).

**Test file:** `tests/test_skill_contracts.py`
- Every skill card contains token budget, input contract, output contract, invariants.
- Every skill in map exists on disk.
- Every skill forbids raw data dumps into agent context.

**Acceptance criteria:**
- Skill library becomes enforceable, not informal.
- Token economy principle is checkable.
- Full pytest and ruff pass.

**Dependencies:** C.8.

---

## F.4 -- Fallback models and resumable runs

**Goal:** Make long LLM-backed ingestion resumable and give runtime LLM calls a
configured fallback chain.

**Files:**
- `engines/docs/run_state.py` (new).
- `engines/docs/llm_bridge.py` (new or extracted from `report_reader.py`).
- `engines/docs/report_reader.py` and `engines/docs/summarize.py` (edit).
- `agent_skills/document_evidence_extraction.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit).

**Test file:** `tests/test_resumable_runs.py`
- Completed chunk is skipped on retry.
- Failed provider falls back to next configured provider.
- Tier gate and ledger still run for every external call.
- Run state contains no raw full document text.

**Acceptance criteria:**
- Provider throttling does not force restart from zero.
- Privacy rules survive fallback.
- Full pytest and ruff pass.

**Dependencies:** B.2, B.4, A0 gate.

---

## F.5 -- Ontology and typed workflow edges

**Goal:** Add stable entity IDs and typed cross-workflow edges when registry size
or linking pain justifies graph-like memory.

**Files:**
- `engines/brain/ontology.py` (new).
- `engines/brain/edges.py` (new).
- `engines/brain/AGENTS.md` (edit).
- `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `resolve_entity`, `link_workflow_edge`.

**Test file:** `tests/test_ontology.py`
- Two aliases can resolve to one canonical entity id.
- Conflicting aliases require review, not auto-merge.
- Edges support depends_on, conflicts_with, refines, supersedes.
- Search can return edges for an entity.

**Acceptance criteria:**
- Synthesis uses IDs, not loose strings.
- Graph DB remains optional; flat store works first.
- Full pytest and ruff pass.

**Dependencies:** C gate and measured trigger.

---

## F.6 -- Factory comparison availability gate

**Goal:** Prevent factory-vs-factory comparison unless comparable factory reports
actually exist.

**Files:**
- `engines/brain/comparison.py` (edit).
- `agent_skills/knowledge_search.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `compare_factories`.

**Test file:** `tests/test_factory_comparison_gate.py`
- Missing second factory returns blocked/not_enough_data.
- Different KPI definitions return not_directly_comparable.
- Comparable cited records produce comparison output.

**Acceptance criteria:**
- No speculative factory comparison.
- KPI-definition mismatch is visible.
- Full pytest and ruff pass.

**Dependencies:** C.6, F.5; actual comparable reports.

---

## F.7 -- Idea synthesis, last and labeled

**Goal:** Generate idea briefs only after the claims boundary and contradiction
view are stable, labeling every output as AI-SUGGESTED IDEA.

**Files:**
- `engines/brain/idea_synthesis.py` (new).
- `serving/decision_brief.py` (edit for idea output type).
- `agent_skills/knowledge_search.md` and `agent_skills/management_reporting.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `suggest_ideas`.

**Test file:** `tests/test_idea_synthesis.py`
- Output title/body contains `AI-SUGGESTED IDEA`.
- Every input claim/record has citation.
- Contradicted inputs create a warning and cannot be hidden.
- Unsigned idea cannot render as a recommendation.

**Acceptance criteria:**
- Ideas are clearly not facts or decisions.
- Highest-risk synthesis ships last.
- Full pytest and ruff pass.

**Dependencies:** C.7, D.4, F.1.

---

## F.8 -- Scheduled ingestion, backup, restore, alerting

**Goal:** Prove the brain does not lose knowledge by scheduling ingestion,
backing up stores/artifacts, restoring them, and alerting on failure.

**Files:**
- `ops/AGENTS.md` (new).
- `ops/scheduler.py` (new).
- `ops/backup.py` (new).
- `ops/alerts.py` (new).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `run_backup`, `restore_backup`, `list_ingestion_alerts`.

**Test file:** `tests/test_ops_backup.py`
- Backup includes `.brain` stores and knowledge artifacts.
- Restore into temp directory recreates registry/artifact files.
- Failed scheduled ingestion creates alert.
- Backup does not include unapproved external secrets.

**Acceptance criteria:**
- Restore drill is rehearsed, not theoretical.
- Alerts are queryable.
- Full pytest and ruff pass.

**Dependencies:** C.1, C.5.

---

## F.9 -- Session-state persistence

**Goal:** Preserve meaningful session state so another agent can resume without
re-explaining current status.

**Files:**
- `00_control/session_state.md` (new).
- `00_control/restart_notes.md` (edit).
- `ops/session_state.py` (new, if automation is chosen).
- `agent_skills/audit_and_trust.md` (edit).
- `AGENT_SKILL_MAP.md` (edit).
- `mcp_server/server.py` (edit) -- add `write_session_state`.

**Test file:** `tests/test_session_state.py`
- Session summary records current phase, next action, blockers, evidence pointers.
- Restart notes can be updated from session state without deleting manual notes.
- Sensitive raw data is not written to session state.

**Acceptance criteria:**
- Fable/Codex token exhaustion becomes recoverable.
- Resume documents stay concise and current.
- Full pytest and ruff pass.

**Dependencies:** D.6.

---

## F.10 -- Quarterly plan review ritual

**Goal:** Add the plan-review checklist that keeps the approved plan living and
truthful as the system and AI landscape change.

**Files:**
- `00_control/plan_review.md` (new).
- `00_control/decisions.md` (edit only to record owner decisions).
- `03_design/current_implementation_plan.md` (edit only when review changes build order).
- `AGENT_SKILL_MAP.md` (edit if review changes routing).

**Test file:** none; doc-control gate.
- Evaluator verifies checklist includes success measures, phase gate status, risks,
  owner decisions, and next-quarter changes.

**Acceptance criteria:**
- The plan is reviewed quarterly against reality.
- Any changed architecture decision is recorded in control docs.

**Dependencies:** D gate; then recurring.

