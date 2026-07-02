"""Deterministic figure verification helpers.

This module is intentionally pure: no I/O, no subprocesses, no network calls.
"""

from __future__ import annotations

from collections import Counter
import re
from decimal import Decimal

_NUMERIC_TOKEN_RE = re.compile(r"(?P<value>\d[\d,]*(?:\.\d+)?)(?P<suffix>%|[억만천])?")
_KOREAN_UNIT_SCALE = {
    "억": Decimal("100000000"),
    "만": Decimal("10000"),
    "천": Decimal("1000"),
}


def _normalize_decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def normalize_korean_unit(value: str, unit: str) -> float:
    if unit not in _KOREAN_UNIT_SCALE:
        raise ValueError(f"Unsupported Korean unit: {unit}")
    base = Decimal(value.replace(",", ""))
    return float(base * _KOREAN_UNIT_SCALE[unit])


def extract_numeric_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _NUMERIC_TOKEN_RE.finditer(text):
        value = match.group("value").replace(",", "")
        suffix = match.group("suffix") or ""
        if suffix == "%":
            tokens.append(f"{_normalize_decimal_text(Decimal(value))}%")
        elif suffix in _KOREAN_UNIT_SCALE:
            scaled = Decimal(str(normalize_korean_unit(value, suffix)))
            tokens.append(_normalize_decimal_text(scaled))
        else:
            tokens.append(_normalize_decimal_text(Decimal(value)))
    return tokens


def figure_matches(claim_text: str, source_text: str) -> bool:
    claim_tokens = extract_numeric_tokens(claim_text)
    if not claim_tokens:
        return False

    source_counter = Counter(extract_numeric_tokens(source_text))
    claim_counter = Counter(claim_tokens)
    return all(source_counter[token] >= count for token, count in claim_counter.items())
