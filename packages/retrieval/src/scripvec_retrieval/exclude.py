"""Exclusion filtering for CR-014."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def filter_by_exclusion(
    hits: list[tuple[str, T]],
    exclusion_set: set[str],
) -> list[tuple[str, T]]:
    """Filter hits by excluding verse_ids in the exclusion set.

    Args:
        hits: List of (verse_id, score) tuples in ranked order.
        exclusion_set: Set of verse_ids to exclude.

    Returns:
        Filtered list preserving the original ranking order.
    """
    return [(verse_id, score) for verse_id, score in hits if verse_id not in exclusion_set]
