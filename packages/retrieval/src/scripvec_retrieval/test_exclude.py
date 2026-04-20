"""Tests for exclude.py per CR-014 B3."""

from __future__ import annotations

from scripvec_retrieval.exclude import filter_by_exclusion


class TestFilterByExclusion:
    """Unit tests for filter_by_exclusion (CR-014 B3)."""

    def test_empty_exclusion_set_returns_unchanged(self) -> None:
        """Empty exclusion_set returns hits unchanged."""
        hits = [("v1", 0.9), ("v2", 0.8), ("v3", 0.7)]
        result = filter_by_exclusion(hits, set())
        assert result == hits

    def test_exclusion_covers_all_hits_returns_empty(self) -> None:
        """Exclusion covering all hits returns empty list."""
        hits = [("v1", 0.9), ("v2", 0.8), ("v3", 0.7)]
        exclusion = {"v1", "v2", "v3"}
        result = filter_by_exclusion(hits, exclusion)
        assert result == []

    def test_partial_overlap_returns_correct_subset(self) -> None:
        """Partial overlap returns correct subset in original order."""
        hits = [("v1", 0.9), ("v2", 0.8), ("v3", 0.7), ("v4", 0.6)]
        exclusion = {"v2", "v4"}
        result = filter_by_exclusion(hits, exclusion)
        assert result == [("v1", 0.9), ("v3", 0.7)]

    def test_preserves_ranking_order(self) -> None:
        """Order of surviving hits matches input order."""
        hits = [("v5", 0.95), ("v1", 0.85), ("v3", 0.75), ("v2", 0.65)]
        exclusion = {"v1"}
        result = filter_by_exclusion(hits, exclusion)
        assert result == [("v5", 0.95), ("v3", 0.75), ("v2", 0.65)]

    def test_exclusion_not_in_hits_no_effect(self) -> None:
        """Exclusion set with ids not in hits has no effect."""
        hits = [("v1", 0.9), ("v2", 0.8)]
        exclusion = {"v99", "v100"}
        result = filter_by_exclusion(hits, exclusion)
        assert result == hits

    def test_empty_hits_returns_empty(self) -> None:
        """Empty hits list returns empty list."""
        hits: list[tuple[str, float]] = []
        exclusion = {"v1", "v2"}
        result = filter_by_exclusion(hits, exclusion)
        assert result == []

    def test_works_with_different_score_types(self) -> None:
        """Function works with different score types (int, float)."""
        int_hits = [("v1", 10), ("v2", 8), ("v3", 6)]
        result = filter_by_exclusion(int_hits, {"v2"})
        assert result == [("v1", 10), ("v3", 6)]
