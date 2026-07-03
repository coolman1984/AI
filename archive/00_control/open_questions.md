# Open Questions

## Resolved (P2.1 decision)

- **First workflow:** Monthly material cost variance review for Cost Control / Finance.
  This is now the locked first real workflow for the pilot.

## Still open

1. **Real export provider and timing**
   - Who will provide the first real export?
   - What period will it cover?
   - Is delivery manual download or a recurring handoff?

2. **Pilot sign-off chain**
   - Who signs off the monthly material cost variance card?
   - Is one named approver enough, or is a second Finance approval required?

3. **On-prem infrastructure owner (later gate)**
   - Who owns the future on-prem model / graph / OCR environment?
   - Not needed for the current slice; needed before heavy infrastructure starts.

4. **Deployment and backup owner (later gate)**
   - Who will own deployment, backup, restore, and failure alerts?
   - Not needed for the current slice; needed before productization.

## Real-data issue promotion template (E.4)

When P2.2 / E.1 profiling or first real ingest surfaces a material failure, promote it
before starting new code:

| Field | Required content |
|-------|------------------|
| Issue ID | `I#` in `05_validation/issue_tracker.md` |
| Source | file path, sheet/page, and run_id |
| Symptom | what failed visibly (totals, locale, schema drift, OCR, etc.) |
| Owner | named human or role |
| Status | `Open`, `Blocked`, or `Resolved` |
| Next action | one concrete follow-on task row in `00_control/task_queue.md` |
| Evidence | pytest name, profile output, or reject sample — never management numbers |

Promotion rule: no material real-data finding stays only in run notes. If it needs code,
add a task row first; if it needs owner input, add an open question first.

> **Gate note:** heavy infrastructure remains blocked until the workflow is locked,
> one real export is profiled, and the infrastructure owner is known.
