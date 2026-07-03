"""Golden evaluation runner (MASTER_PLAN F.1)."""

from __future__ import annotations

import json
from pathlib import Path

_MANIFEST_NAME = "golden_manifest.json"


def _manifest_path(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    return root / _MANIFEST_NAME


def load_manifest(base_dir: str | Path | None = None) -> dict:
    path = _manifest_path(base_dir)
    if not path.exists():
        raise FileNotFoundError(f"golden manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    fixtures = manifest.get("fixtures", [])
    if not fixtures:
        errors.append("manifest has no fixtures")
    required = ("id", "source_type", "fixture_path", "expected_claims", "expected_citations")
    for fixture in fixtures:
        for field in required:
            if field not in fixture:
                errors.append(f"fixture {fixture.get('id', '?')} missing field '{field}'")
        if not isinstance(fixture.get("expected_claims"), list):
            errors.append(f"fixture {fixture.get('id', '?')} expected_claims must be a list")
        if not isinstance(fixture.get("expected_citations"), list):
            errors.append(f"fixture {fixture.get('id', '?')} expected_citations must be a list")
    return errors


def _load_fixture(base_dir: Path, fixture: dict) -> dict:
    fixture_path = base_dir / fixture["fixture_path"]
    if not fixture_path.exists():
        raise FileNotFoundError(
            f"missing fixture file for '{fixture['id']}': {fixture_path}"
        )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _extract_claim_texts(payload: dict, source_type: str) -> list[str]:
    if source_type == "workflow_record":
        texts: list[str] = []
        purpose = payload.get("purpose", {})
        if purpose.get("translated_text"):
            texts.append(purpose["translated_text"])
        for field in ("steps", "roles", "kpis", "what_changed", "open_questions", "risks"):
            for item in payload.get(field, []):
                if item.get("translated_text"):
                    texts.append(item["translated_text"])
        return texts
    if source_type == "brief_claims":
        return [claim.get("text", "") for claim in payload.get("claims", []) if claim.get("text")]
    if source_type == "coverage_report":
        status = payload.get("status", "")
        return [status] if status else []
    return []


def _extract_citation_refs(payload: dict, source_type: str) -> list[str]:
    if source_type == "workflow_record":
        refs: list[str] = []
        for field in ("purpose", "steps", "roles", "kpis", "what_changed", "open_questions", "risks"):
            block = payload.get(field)
            items = [block] if field == "purpose" and isinstance(block, dict) else (block or [])
            if field == "purpose" and isinstance(block, dict):
                items = [block]
            elif isinstance(block, list):
                items = block
            else:
                items = []
            for item in items:
                for citation in item.get("citations", []):
                    locator = citation.get("locator", "")
                    if locator:
                        refs.append(locator)
        return refs
    if source_type == "brief_claims":
        refs = []
        for claim in payload.get("claims", []):
            if claim.get("locator"):
                refs.append(claim["locator"])
            elif claim.get("citation"):
                refs.append(claim["citation"])
        return refs
    if source_type == "coverage_report":
        refs = list(payload.get("chunk_to_pages", {}).keys())
        return refs
    return []


def _evaluate_fixture(base_dir: Path, fixture: dict) -> dict:
    fixture_id = fixture["id"]
    try:
        payload = _load_fixture(base_dir, fixture)
    except FileNotFoundError as exc:
        return {
            "fixture_id": fixture_id,
            "passed": False,
            "blocked": True,
            "error": str(exc),
        }

    source_type = fixture["source_type"]
    actual_claims = _extract_claim_texts(payload, source_type)
    actual_citations = _extract_citation_refs(payload, source_type)
    expected_claims = fixture.get("expected_claims", [])
    expected_citations = fixture.get("expected_citations", [])

    missing_claims = [c for c in expected_claims if c not in actual_claims]
    missing_citations = [c for c in expected_citations if c not in actual_citations]
    passed = not missing_claims and not missing_citations

    return {
        "fixture_id": fixture_id,
        "source_type": source_type,
        "passed": passed,
        "blocked": False,
        "missing_claims": missing_claims,
        "missing_citations": missing_citations,
        "actual_claims": actual_claims,
        "actual_citations": actual_citations,
    }


def run_golden_eval(base_dir: str | Path | None = None) -> dict:
    """Run all golden fixtures and return per-fixture pass/fail report."""
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    manifest = load_manifest(root)
    validation_errors = validate_manifest(manifest)
    if validation_errors:
        return {
            "passed": False,
            "blocked": True,
            "validation_errors": validation_errors,
            "results": [],
        }

    results = [_evaluate_fixture(root, fixture) for fixture in manifest["fixtures"]]
    blocked = any(result.get("blocked") for result in results)
    passed = not blocked and all(result.get("passed") for result in results)
    return {
        "passed": passed,
        "blocked": blocked,
        "fixture_count": len(results),
        "results": results,
    }