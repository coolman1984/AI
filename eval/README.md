# Golden Evaluation Set

Curated fixtures for regression gates on deck extraction, citation support, and brief
generation. Uses synthetic/public payloads until the owner supplies approved samples.

## Run

```bash
python -m pytest tests/test_golden_eval.py -q
```

Or via MCP: `run_golden_eval`.

## Manifest

`golden_manifest.json` lists fixture ids, `source_type`, `fixture_path`, `expected_claims`,
and `expected_citations`. Missing fixture files block the eval.

## Gate

T12 gated self-evolution runs only when `run_golden_eval` reports `passed: true`.