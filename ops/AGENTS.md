# ops — scheduled ingestion, backup, restore, alerting

**Does:** Operational durability for the second brain: scheduled ingestion with failure
alerts, backup/restore drills for `.brain` stores and `knowledge/` artifacts, and session
state automation.

**Public interface:**
- `scheduler.run_scheduled_ingestion`
- `backup.run_backup`, `backup.restore_backup`, `backup.list_backups`
- `alerts.AlertStore`
- `session_state.write_session_state`, `session_state.update_restart_notes`

**Invariants:** backups exclude unapproved external secrets; failed scheduled ingestion
creates a queryable alert; restore drills target explicit directories.