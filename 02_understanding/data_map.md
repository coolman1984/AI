# Data Contracts (MASTER_PLAN Part R; lenses/*.yaml)
## finance actuals
- key: material_id (blank => total/missing-key reject)
- grain: sub_assembly ; value: amount ; baseline: budget_amount (finance_budget.csv)
- validation: total-row excluded, duplicates flagged, locale amounts parsed, conservation law
## planning actuals
- key: item_id ; grain: sub_assembly ; value: output ; baseline: plan_output
A dataset that violates its contract -> the row is quarantined to rejects with a reason.
