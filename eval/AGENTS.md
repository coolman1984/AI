# eval — golden evaluation set

**Does:** Curated regression fixtures for deck/report extraction, citation support, and brief
generation gates. The golden runner validates fixture manifests and reports pass/fail per
fixture. Self-learning (T12) is gated on this eval passing.

**Public interface:** `runner.load_manifest`, `runner.validate_manifest`, `runner.run_golden_eval`.

**Files:**
- `golden_manifest.json` — fixture ids, source types, expected claims/citations.
- `fixtures/` — synthetic/public fixture payloads only until owner approves real samples.
- `runner.py` — manifest validation and per-fixture evaluation.

**Invariants:** missing fixture files block the eval with a clear error; no private Tier 1
data in fixtures; golden pass is required before gated self-evolution runs.