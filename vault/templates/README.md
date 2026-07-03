# Vault Note Templates — Frontmatter + Structure

## Business Rule
```yaml
---
type: business_rule
title: "<rule title>"
rule_owner: "<name>"
source_doc: "<document name>"
status: active
---
# <rule title>

## Statement
<one-sentence rule>

## Rationale
<why this rule exists>

## Applies to
<which datasets, periods, or workflows>

## Exceptions
<known exceptions>
```

## Dataset
```yaml
---
type: dataset
title: "<dataset name>"
fingerprint: "<sha256>"
period: "<period>"
status: active
---
# <dataset name>

## Source
<where the data comes from>

## Columns
<column list with dtypes>

## Known quirks
<quirks, edge cases, notes>
```

## Column Mapping
```yaml
---
type: column_mapping
title: "<mapping name>"
dataset: "<dataset fingerprint>"
confirmer: "<name>"
date: "<YYYY-MM-DD>"
status: confirmed
---
# <mapping name>

## Source → Canonical
| Source Column | Canonical Name | dtype |
|---|---|---|
