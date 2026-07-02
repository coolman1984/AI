"""Privacy tier helpers for outbound document-processing decisions."""

from __future__ import annotations

from enum import StrEnum


class Tier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"


def classify_tier(doc_metadata: dict | None) -> Tier:
    metadata = doc_metadata or {}
    raw_tier = str(metadata.get("tier", "")).strip().lower()
    if raw_tier == Tier.TIER_2.value:
        return Tier.TIER_2
    return Tier.TIER_1


def assert_can_send_external(tier: Tier) -> None:
    if tier is Tier.TIER_1:
        raise PermissionError("Tier 1 content cannot be sent to external services.")
