"""Unit tests for floor filtering (CR-012 B2, B3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _apply_dense_floor_filter(
    hits: list[tuple[str, float]], floor: float | None
) -> list[tuple[str, float]]:
    """Apply dense-mode absolute floor filtering."""
    if floor is not None and floor > 0.0:
        return [(vid, score) for vid, score in hits if score >= floor]
    return hits


def _apply_bm25_floor_filter(
    hits: list[tuple[str, float]], floor: float | None
) -> list[tuple[str, float]]:
    """Apply BM25-mode relative floor filtering (ratio of top score)."""
    if floor is not None and floor > 0.0 and hits:
        top_score = hits[0][1]
        threshold = floor * top_score
        return [(vid, score) for vid, score in hits if score >= threshold]
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
        result = _apply_dense_floor_filter(hits, 0.55)
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
        result = _apply_dense_floor_filter(hits, 0.50)
        assert result == []

    def test_floor_zero_is_noop(self) -> None:
        """Floor 0.0 keeps all hits."""
        hits = [
            ("v1", 0.82),
            ("v2", 0.31),
        ]
        result = _apply_dense_floor_filter(hits, 0.0)
        assert result == hits

    def test_floor_none_is_noop(self) -> None:
        """Floor None keeps all hits."""
        hits = [
            ("v1", 0.82),
            ("v2", 0.31),
        ]
        result = _apply_dense_floor_filter(hits, None)
        assert result == hits

    def test_floor_boundary_exact_match_kept(self) -> None:
        """Hit with score exactly at floor is kept (>= not >)."""
        hits = [
            ("v1", 0.55),
            ("v2", 0.54),
        ]
        result = _apply_dense_floor_filter(hits, 0.55)
        assert len(result) == 1
        assert result[0][0] == "v1"

    def test_floor_one_keeps_only_perfect_scores(self) -> None:
        """Floor 1.0 keeps only hits with score exactly 1.0."""
        hits = [
            ("v1", 1.0),
            ("v2", 0.99),
            ("v3", 0.50),
        ]
        result = _apply_dense_floor_filter(hits, 1.0)
        assert len(result) == 1
        assert result[0][0] == "v1"


class TestBM25FloorFilter:
    """Tests for BM25-mode relative floor culling (CR-012 B3)."""

    def test_floor_drops_below_ratio_of_top(self) -> None:
        """Top hit 24.7, floor 0.3 drops all below 7.41."""
        hits = [
            ("v1", 24.7),
            ("v2", 18.5),
            ("v3", 10.0),
            ("v4", 7.41),
            ("v5", 5.0),
            ("v6", 3.0),
        ]
        result = _apply_bm25_floor_filter(hits, 0.3)
        assert len(result) == 4
        assert [vid for vid, _ in result] == ["v1", "v2", "v3", "v4"]
        threshold = 0.3 * 24.7
        assert all(score >= threshold for _, score in result)

    def test_zero_hits_returns_empty_no_error(self) -> None:
        """Zero-hit query with floor returns empty cleanly (no divide-by-zero)."""
        hits: list[tuple[str, float]] = []
        result = _apply_bm25_floor_filter(hits, 0.5)
        assert result == []

    def test_floor_one_keeps_only_top_score_ties(self) -> None:
        """Floor 1.0 keeps only hits tied with top score."""
        hits = [
            ("v1", 24.7),
            ("v2", 24.7),
            ("v3", 20.0),
        ]
        result = _apply_bm25_floor_filter(hits, 1.0)
        assert len(result) == 2
        assert [vid for vid, _ in result] == ["v1", "v2"]

    def test_floor_zero_is_noop(self) -> None:
        """Floor 0.0 keeps all hits."""
        hits = [
            ("v1", 24.7),
            ("v2", 5.0),
        ]
        result = _apply_bm25_floor_filter(hits, 0.0)
        assert result == hits

    def test_floor_none_is_noop(self) -> None:
        """Floor None keeps all hits."""
        hits = [
            ("v1", 24.7),
            ("v2", 5.0),
        ]
        result = _apply_bm25_floor_filter(hits, None)
        assert result == hits

    def test_floor_culls_all_except_top(self) -> None:
        """High floor culls everything except top hit."""
        hits = [
            ("v1", 24.7),
            ("v2", 12.0),
            ("v3", 5.0),
        ]
        result = _apply_bm25_floor_filter(hits, 0.9)
        threshold = 0.9 * 24.7
        assert len(result) == 1
        assert result[0][0] == "v1"
