"""Tests for hybrid mode exclusion per CR-014 — exclusion applied pre-RRF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class MockDenseHit:
    """Mock DenseHit for testing."""

    verse_id: str
    rowid: int
    cosine: float


@dataclass
class MockVerse:
    """Mock Verse for testing."""

    verse_id: str
    ref_canonical: str
    text: str


_MODULE = "scripvec_retrieval.query"


class TestHybridExcludePreRRF:
    """Tests verifying exclusion is applied to each stream BEFORE RRF fusion."""

    @pytest.fixture
    def mock_manifest(self) -> MagicMock:
        """Create a mock manifest."""
        manifest = MagicMock()
        manifest.embed_endpoint = "http://test"
        manifest.embed_model = "test-model"
        manifest.embed_dim = 1024
        return manifest

    @pytest.fixture
    def mock_embed_config(self) -> MagicMock:
        """Create a mock embed config."""
        cfg = MagicMock()
        cfg.base_url = "http://test"
        cfg.model = "test-model"
        cfg.dim = 1024
        return cfg

    @pytest.fixture
    def mock_exclude_config(self) -> MagicMock:
        """Create a mock exclude config."""
        cfg = MagicMock()
        cfg.exclude_m = 3
        cfg.exclude_buffer = 10
        return cfg

    @pytest.fixture
    def mock_dedupe_config(self) -> MagicMock:
        """Create a mock dedupe config."""
        cfg = MagicMock()
        cfg.proximity_m = 3
        cfg.k_buffer = 3
        return cfg

    def test_excluded_verses_not_in_final_results(
        self,
        tmp_path: Path,
        mock_manifest: MagicMock,
        mock_embed_config: MagicMock,
        mock_exclude_config: MagicMock,
        mock_dedupe_config: MagicMock,
    ) -> None:
        """No excluded verse appears in final top-K."""
        excluded_ids = ["v-excluded-1", "v-excluded-2", "v-excluded-3"]
        bm25_hits = [
            ("v-excluded-1", 10.0),
            ("v-bm25-1", 8.0),
            ("v-bm25-2", 6.0),
        ]
        dense_hits = [
            MockDenseHit("v-excluded-2", 1, 0.95),
            MockDenseHit("v-dense-1", 2, 0.85),
            MockDenseHit("v-dense-2", 3, 0.75),
        ]

        fused_after_exclusion = [
            ("v-bm25-1", 0.032),
            ("v-dense-1", 0.030),
            ("v-bm25-2", 0.028),
        ]

        mock_store = MagicMock()
        mock_store.conn = MagicMock()

        def mock_get_verse(store: Any, verse_id: str) -> MockVerse:
            return MockVerse(verse_id=verse_id, ref_canonical=f"Ref {verse_id}", text="text")

        mock_bm25_idx = MagicMock()

        with (
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}.load_embed_config", return_value=mock_embed_config),
            patch(f"{_MODULE}.load_exclude_config", return_value=mock_exclude_config),
            patch(f"{_MODULE}.load_dedupe_config", return_value=mock_dedupe_config),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.compute_exclusion_set", return_value=excluded_ids),
            patch(f"{_MODULE}.load_bm25", return_value=mock_bm25_idx),
            patch(f"{_MODULE}.bm25_topk", return_value=bm25_hits),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.embed", return_value=[0.1] * 1024),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits),
            patch(f"{_MODULE}.rrf", return_value=fused_after_exclusion) as mock_rrf,
            patch(f"{_MODULE}.get_verse", side_effect=mock_get_verse),
            patch(f"{_MODULE}.proximity_dedupe", return_value=(fused_after_exclusion, 0)),
        ):
            from scripvec_retrieval.query import query

            result = query("test query", k=3, mode="hybrid", exclude="exclude text")

            for row in result.results:
                assert row.verse_id not in excluded_ids

    def test_exclusion_applied_before_rrf(
        self,
        tmp_path: Path,
        mock_manifest: MagicMock,
        mock_embed_config: MagicMock,
        mock_exclude_config: MagicMock,
        mock_dedupe_config: MagicMock,
    ) -> None:
        """Exclusion is applied to each stream BEFORE RRF fusion."""
        excluded_ids = ["v-excluded-1"]
        bm25_hits_raw = [
            ("v-excluded-1", 10.0),
            ("v-bm25-1", 8.0),
        ]
        dense_hits_raw = [
            MockDenseHit("v-excluded-1", 1, 0.95),
            MockDenseHit("v-dense-1", 2, 0.85),
        ]

        mock_store = MagicMock()
        mock_store.conn = MagicMock()
        mock_bm25_idx = MagicMock()

        rrf_calls: list[tuple[list, list]] = []

        def capture_rrf(bm25: list, dense: list, top_k: int, **kwargs: Any) -> list:
            rrf_calls.append((list(bm25), list(dense)))
            return [("v-bm25-1", 0.03), ("v-dense-1", 0.025)]

        def mock_get_verse(store: Any, verse_id: str) -> MockVerse:
            return MockVerse(verse_id=verse_id, ref_canonical=f"Ref {verse_id}", text="text")

        with (
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}.load_embed_config", return_value=mock_embed_config),
            patch(f"{_MODULE}.load_exclude_config", return_value=mock_exclude_config),
            patch(f"{_MODULE}.load_dedupe_config", return_value=mock_dedupe_config),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.compute_exclusion_set", return_value=excluded_ids),
            patch(f"{_MODULE}.load_bm25", return_value=mock_bm25_idx),
            patch(f"{_MODULE}.bm25_topk", return_value=bm25_hits_raw),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.embed", return_value=[0.1] * 1024),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits_raw),
            patch(f"{_MODULE}.rrf", side_effect=capture_rrf),
            patch(f"{_MODULE}.get_verse", side_effect=mock_get_verse),
            patch(f"{_MODULE}.proximity_dedupe", return_value=([("v-bm25-1", 0.03), ("v-dense-1", 0.025)], 0)),
        ):
            from scripvec_retrieval.query import query

            query("test query", k=2, mode="hybrid", exclude="exclude text")

            assert len(rrf_calls) == 1
            bm25_to_rrf, dense_to_rrf = rrf_calls[0]

            assert all(vid != "v-excluded-1" for vid, _ in bm25_to_rrf)
            assert all(vid != "v-excluded-1" for vid, _ in dense_to_rrf)

    def test_hybrid_exclude_info_matches_dense_shape(
        self,
        tmp_path: Path,
        mock_manifest: MagicMock,
        mock_embed_config: MagicMock,
        mock_exclude_config: MagicMock,
        mock_dedupe_config: MagicMock,
    ) -> None:
        """Response JSON exclude block is identical structure to dense mode."""
        excluded_ids = ["v-excluded-1", "v-excluded-2"]

        mock_store = MagicMock()
        mock_store.conn = MagicMock()
        mock_bm25_idx = MagicMock()

        def mock_get_verse(store: Any, verse_id: str) -> MockVerse:
            return MockVerse(verse_id=verse_id, ref_canonical=f"Ref {verse_id}", text="text")

        with (
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}.load_embed_config", return_value=mock_embed_config),
            patch(f"{_MODULE}.load_exclude_config", return_value=mock_exclude_config),
            patch(f"{_MODULE}.load_dedupe_config", return_value=mock_dedupe_config),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.compute_exclusion_set", return_value=excluded_ids),
            patch(f"{_MODULE}.load_bm25", return_value=mock_bm25_idx),
            patch(f"{_MODULE}.bm25_topk", return_value=[("v1", 8.0)]),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.embed", return_value=[0.1] * 1024),
            patch(f"{_MODULE}.dense_topk", return_value=[MockDenseHit("v2", 1, 0.85)]),
            patch(f"{_MODULE}.rrf", return_value=[("v1", 0.03)]),
            patch(f"{_MODULE}.get_verse", side_effect=mock_get_verse),
            patch(f"{_MODULE}.proximity_dedupe", return_value=([("v1", 0.03)], 0)),
        ):
            from scripvec_retrieval.query import query

            result = query("test query", k=2, mode="hybrid", exclude="exclude text")

            assert result.exclude is not None
            assert result.exclude.text == "exclude text"
            assert result.exclude.set_size == mock_exclude_config.exclude_m
            assert result.exclude.excluded_verse_ids == tuple(excluded_ids)

    def test_hybrid_no_exclude_returns_none(
        self,
        tmp_path: Path,
        mock_manifest: MagicMock,
        mock_embed_config: MagicMock,
        mock_dedupe_config: MagicMock,
    ) -> None:
        """Hybrid mode without exclude returns exclude=None."""
        mock_store = MagicMock()
        mock_store.conn = MagicMock()
        mock_bm25_idx = MagicMock()

        def mock_get_verse(store: Any, verse_id: str) -> MockVerse:
            return MockVerse(verse_id=verse_id, ref_canonical=f"Ref {verse_id}", text="text")

        with (
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}.load_embed_config", return_value=mock_embed_config),
            patch(f"{_MODULE}.load_dedupe_config", return_value=mock_dedupe_config),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.load_bm25", return_value=mock_bm25_idx),
            patch(f"{_MODULE}.bm25_topk", return_value=[("v1", 8.0)]),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.embed", return_value=[0.1] * 1024),
            patch(f"{_MODULE}.dense_topk", return_value=[MockDenseHit("v2", 1, 0.85)]),
            patch(f"{_MODULE}.rrf", return_value=[("v1", 0.03)]),
            patch(f"{_MODULE}.get_verse", side_effect=mock_get_verse),
            patch(f"{_MODULE}.proximity_dedupe", return_value=([("v1", 0.03)], 0)),
        ):
            from scripvec_retrieval.query import query

            result = query("test query", k=2, mode="hybrid", exclude=None)

            assert result.exclude is None

    def test_excluded_from_both_streams_not_in_results(
        self,
        tmp_path: Path,
        mock_manifest: MagicMock,
        mock_embed_config: MagicMock,
        mock_exclude_config: MagicMock,
        mock_dedupe_config: MagicMock,
    ) -> None:
        """Verse appearing in BOTH BM25 and dense streams gets excluded from both."""
        excluded_ids = ["v-both"]
        bm25_hits = [
            ("v-both", 10.0),
            ("v-bm25-only", 8.0),
        ]
        dense_hits = [
            MockDenseHit("v-both", 1, 0.95),
            MockDenseHit("v-dense-only", 2, 0.85),
        ]

        mock_store = MagicMock()
        mock_store.conn = MagicMock()
        mock_bm25_idx = MagicMock()

        rrf_calls: list[tuple[list, list]] = []

        def capture_rrf(bm25: list, dense: list, top_k: int, **kwargs: Any) -> list:
            rrf_calls.append((list(bm25), list(dense)))
            return [("v-bm25-only", 0.03), ("v-dense-only", 0.025)]

        def mock_get_verse(store: Any, verse_id: str) -> MockVerse:
            return MockVerse(verse_id=verse_id, ref_canonical=f"Ref {verse_id}", text="text")

        with (
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}.load_embed_config", return_value=mock_embed_config),
            patch(f"{_MODULE}.load_exclude_config", return_value=mock_exclude_config),
            patch(f"{_MODULE}.load_dedupe_config", return_value=mock_dedupe_config),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.compute_exclusion_set", return_value=excluded_ids),
            patch(f"{_MODULE}.load_bm25", return_value=mock_bm25_idx),
            patch(f"{_MODULE}.bm25_topk", return_value=bm25_hits),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.embed", return_value=[0.1] * 1024),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits),
            patch(f"{_MODULE}.rrf", side_effect=capture_rrf),
            patch(f"{_MODULE}.get_verse", side_effect=mock_get_verse),
            patch(f"{_MODULE}.proximity_dedupe", return_value=([("v-bm25-only", 0.03), ("v-dense-only", 0.025)], 0)),
        ):
            from scripvec_retrieval.query import query

            result = query("test query", k=2, mode="hybrid", exclude="exclude text")

            assert len(rrf_calls) == 1
            bm25_to_rrf, dense_to_rrf = rrf_calls[0]
            assert all(vid != "v-both" for vid, _ in bm25_to_rrf)
            assert all(vid != "v-both" for vid, _ in dense_to_rrf)

            for row in result.results:
                assert row.verse_id != "v-both"
