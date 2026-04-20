"""Unit tests for dense-mode floor filtering (CR-012 B2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _apply_floor_filter(
    hits: list[tuple[str, float]], floor: float | None
) -> list[tuple[str, float]]:
    """Apply floor filtering logic (extracted for testability)."""
    if floor is not None and floor > 0.0:
        return [(vid, score) for vid, score in hits if score >= floor]
    return hits


class TestDenseFloorFilter:
    """Tests for dense-mode absolute floor culling."""

    def test_floor_keeps_hits_at_or_above_threshold(self) -> None:
        """Fixture: [0.82, 0.71, 0.55, 0.42, 0.31], floor 0.55 keeps three."""
        hits = [
            ("v1", 0.82),
            ("v2", 0.71),
            ("v3", 0.55),
            ("v4", 0.42),
            ("v5", 0.31),
        ]
        result = _apply_floor_filter(hits, 0.55)
        assert len(result) == 3
        assert [vid for vid, _ in result] == ["v1", "v2", "v3"]
        assert all(score >= 0.55 for _, score in result)

    def test_floor_culls_all_returns_empty(self) -> None:
        """All hits below floor returns empty list."""
        hits = [
            ("v1", 0.42),
            ("v2", 0.31),
            ("v3", 0.25),
        ]
        result = _apply_floor_filter(hits, 0.50)
        assert result == []

    def test_floor_zero_is_noop(self) -> None:
        """Floor 0.0 keeps all hits."""
        hits = [
            ("v1", 0.82),
            ("v2", 0.31),
        ]
        result = _apply_floor_filter(hits, 0.0)
        assert result == hits

    def test_floor_none_is_noop(self) -> None:
        """Floor None keeps all hits."""
        hits = [
            ("v1", 0.82),
            ("v2", 0.31),
        ]
        result = _apply_floor_filter(hits, None)
        assert result == hits

    def test_floor_boundary_exact_match_kept(self) -> None:
        """Hit with score exactly at floor is kept (>= not >)."""
        hits = [
            ("v1", 0.55),
            ("v2", 0.54),
        ]
        result = _apply_floor_filter(hits, 0.55)
        assert len(result) == 1
        assert result[0][0] == "v1"

    def test_floor_one_keeps_only_perfect_scores(self) -> None:
        """Floor 1.0 keeps only hits with score exactly 1.0."""
        hits = [
            ("v1", 1.0),
            ("v2", 0.99),
            ("v3", 0.50),
        ]
        result = _apply_floor_filter(hits, 1.0)
        assert len(result) == 1
        assert result[0][0] == "v1"
