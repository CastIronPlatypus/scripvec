"""Tests for exclude.py per CR-014 B2 and B3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .exclude import compute_exclusion_set, filter_by_exclusion


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


@dataclass
class MockDenseHit:
    """Mock DenseHit for testing."""

    verse_id: str
    rowid: int
    cosine: float


_MODULE = "scripvec_retrieval.exclude"


class TestComputeExclusionSet:
    """Unit tests for compute_exclusion_set (CR-014 B2)."""

    def test_returns_expected_verse_ids(self, tmp_path: Path) -> None:
        """Returns verse_ids from top-m dense hits."""
        mock_hits = [
            MockDenseHit(verse_id="alma-32-21", rowid=1, cosine=0.95),
            MockDenseHit(verse_id="1-nephi-3-7", rowid=2, cosine=0.90),
        ]

        mock_vec = [0.1] * 1024
        mock_store = MagicMock()

        with (
            patch(f"{_MODULE}.embed", return_value=mock_vec) as mock_embed,
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.dense_topk", return_value=mock_hits) as mock_topk,
        ):
            result = compute_exclusion_set("test query", m=2, index_dir=tmp_path)

            assert result == ["alma-32-21", "1-nephi-3-7"]
            mock_embed.assert_called_once_with("test query")
            mock_topk.assert_called_once_with(mock_store, mock_vec, k=2)

    def test_upstream_embed_error_propagates(self, tmp_path: Path) -> None:
        """Upstream error from embed client propagates."""
        with patch(f"{_MODULE}.embed", side_effect=RuntimeError("Embedding failed")):
            with pytest.raises(RuntimeError, match="Embedding failed"):
                compute_exclusion_set("test query", m=5, index_dir=tmp_path)

    def test_returns_empty_list_when_no_hits(self, tmp_path: Path) -> None:
        """Returns empty list when dense_topk returns no hits."""
        mock_vec = [0.1] * 1024
        mock_store = MagicMock()

        with (
            patch(f"{_MODULE}.embed", return_value=mock_vec),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.dense_topk", return_value=[]),
        ):
            result = compute_exclusion_set("test query", m=10, index_dir=tmp_path)

            assert result == []
