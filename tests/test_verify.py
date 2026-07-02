"""Tests for the deterministic figure verifier."""

from __future__ import annotations

import ast
from pathlib import Path

from engines.docs.verify import (
    extract_numeric_tokens,
    figure_matches,
    normalize_korean_unit,
)


def test_extract_numeric_tokens_normalizes_commas():
    assert extract_numeric_tokens("Revenue reached 1,234 units.") == ["1234"]


def test_extract_numeric_tokens_preserves_percentages():
    assert extract_numeric_tokens("Margin improved by 12%.") == ["12%"]


def test_normalize_korean_unit_eok():
    assert normalize_korean_unit("3", "억") == 300_000_000.0


def test_normalize_korean_unit_man():
    assert normalize_korean_unit("25", "만") == 250_000.0


def test_normalize_korean_unit_cheon():
    assert normalize_korean_unit("7", "천") == 7_000.0


def test_figure_matches_for_plain_number_with_commas():
    assert figure_matches("Revenue was 1,234 units.", "Revenue was 1234 units.")


def test_figure_matches_for_percentage():
    assert figure_matches("Margin improved by 12%.", "Margin improved by 12%.")


def test_figure_matches_rejects_wrong_korean_scale():
    claim = "Revenue was 300,000 KRW."
    source = "매출은 3억 원이었다."
    assert not figure_matches(claim, source)


def test_figure_matches_accepts_eok_scaled_value():
    claim = "Revenue was 300,000,000 KRW."
    source = "매출은 3억 원이었다."
    assert figure_matches(claim, source)


def test_verify_module_is_pure():
    source = Path("engines/docs/verify.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned_imports = {"subprocess", "requests"}
    banned_names = {"opencode", "OpencodeLLM"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".")[0] for alias in node.names}
            assert not (imported & banned_imports)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned_imports
        if isinstance(node, ast.Name):
            assert node.id not in banned_names
