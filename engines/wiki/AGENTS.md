# engines/wiki — durable knowledge artifacts

**Does:** writes deterministic markdown artifacts for workflow records, summaries, and
briefs so knowledge survives `.brain` rebuilds and remains human-readable in git.

**Public interface:** `artifacts.artifact_path_for(source_hash, record_type, base_dir)`,
`artifacts.render_workflow_artifact(record)`, `artifacts.write_knowledge_artifact(record,
record_type, base_dir)`.

**Storage:** `knowledge/{record_type}/{source_hash[:12]}.md` — hash-deduplicated paths;
re-ingesting the same source hash reconciles the existing artifact instead of creating clutter.

**Invariants:** artifacts include citations and provenance stamps; no git commands are run
inside the engine; markdown is deterministic from the input record.

**Never:** promote artifacts to audited facts; never omit provenance or citations.

**Tests:** `pytest tests/test_knowledge_artifacts.py`