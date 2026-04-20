"""Tests for ADR-006 embed call serialization per CR-014 B13."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class EmbedCall:
    """Recorded embed call with timing."""

    text: str
    start_ts: float
    end_ts: float


class EmbedRecorder:
    """Records embed call timings for serialization testing."""

    def __init__(self, delay_ms: float = 10.0) -> None:
        self.calls: list[EmbedCall] = []
        self.delay_ms = delay_ms
        self._call_count = 0

    def mock_embed(self, text: str, **kwargs: Any) -> list[float]:
        """Mock embed that records timing and simulates work."""
        start = time.perf_counter()
        time.sleep(self.delay_ms / 1000.0)
        end = time.perf_counter()
        self.calls.append(EmbedCall(text=text, start_ts=start, end_ts=end))
        self._call_count += 1
        return [0.1] * 1024

    def assert_no_overlap(self) -> None:
        """Assert no two embed intervals overlap."""
        if len(self.calls) < 2:
            return

        sorted_calls = sorted(self.calls, key=lambda c: c.start_ts)
        for i in range(len(sorted_calls) - 1):
            current = sorted_calls[i]
            next_call = sorted_calls[i + 1]
            assert current.end_ts <= next_call.start_ts, (
                f"Overlap detected: call {i} ended at {current.end_ts:.6f}, "
                f"call {i+1} started at {next_call.start_ts:.6f}"
            )


@dataclass
class MockDenseHit:
    """Mock dense hit for testing."""

    verse_id: str
    rowid: int
    cosine: float


@dataclass
class MockVerse:
    """Mock verse record."""

    verse_id: str
    ref_canonical: str
    text: str


_MODULE = "scripvec_retrieval.query"
_EXCLUDE_MODULE = "scripvec_retrieval.exclude"


class TestEmbedSerializationWithExclude:
    """Tests that embed calls are serialized when --exclude is used (ADR-006)."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock store with connection."""
        store = MagicMock()
        store.conn.close = MagicMock()
        return store

    @pytest.fixture
    def mock_manifest(self) -> MagicMock:
        """Create mock manifest."""
        manifest = MagicMock()
        manifest.embed_endpoint = "https://api.test.com"
        manifest.embed_model = "test-model"
        manifest.embed_dim = 1024
        return manifest

    @pytest.fixture
    def dense_hits(self) -> list[MockDenseHit]:
        """Standard dense hits for tests."""
        return [
            MockDenseHit(verse_id="alma-32-21", rowid=1, cosine=0.9),
            MockDenseHit(verse_id="1-nephi-3-7", rowid=2, cosine=0.85),
            MockDenseHit(verse_id="mosiah-2-17", rowid=3, cosine=0.8),
        ]

    @pytest.fixture
    def bm25_hits(self) -> list[tuple[str, float]]:
        """Standard BM25 hits for tests."""
        return [("mosiah-2-17", 15.5), ("alma-32-21", 14.0), ("1-nephi-3-7", 12.0)]

    @pytest.fixture
    def mock_verse(self) -> MockVerse:
        """Standard mock verse."""
        return MockVerse(
            verse_id="alma-32-21",
            ref_canonical="Alma 32:21",
            text="Faith is not to have a perfect knowledge...",
        )

    def test_dense_mode_with_exclude_no_overlap(
        self,
        mock_store: MagicMock,
        mock_manifest: MagicMock,
        dense_hits: list[MockDenseHit],
        mock_verse: MockVerse,
        tmp_path: Path,
    ) -> None:
        """Dense mode with --exclude runs two embed calls serially."""
        from scripvec_retrieval.query import query

        recorder = EmbedRecorder(delay_ms=5.0)

        with (
            patch(f"{_MODULE}.embed", recorder.mock_embed),
            patch(f"{_EXCLUDE_MODULE}.embed", recorder.mock_embed),
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}._drift_check_endpoint"),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits),
            patch(f"{_MODULE}.get_verse", return_value=mock_verse),
            patch(
                f"{_MODULE}.load_dedupe_config",
                return_value=MagicMock(k_buffer=3, proximity_m=2),
            ),
            patch(
                f"{_MODULE}.load_exclude_config",
                return_value=MagicMock(exclude_m=5, exclude_buffer=10),
            ),
            patch(f"{_MODULE}.proximity_dedupe", side_effect=lambda h, m, k: (h[:k], 0)),
            patch(f"{_EXCLUDE_MODULE}.open_store", return_value=mock_store),
            patch(f"{_EXCLUDE_MODULE}.dense_topk", return_value=dense_hits),
        ):
            result = query(
                "faith and works",
                k=5,
                mode="dense",
                index="latest",
                exclude="exclude this text",
            )

        assert len(recorder.calls) == 2, f"Expected 2 embed calls, got {len(recorder.calls)}"
        recorder.assert_no_overlap()

    def test_hybrid_mode_with_exclude_no_overlap(
        self,
        mock_store: MagicMock,
        mock_manifest: MagicMock,
        dense_hits: list[MockDenseHit],
        bm25_hits: list[tuple[str, float]],
        mock_verse: MockVerse,
        tmp_path: Path,
    ) -> None:
        """Hybrid mode with --exclude runs two embed calls serially."""
        from scripvec_retrieval.query import query

        recorder = EmbedRecorder(delay_ms=5.0)

        with (
            patch(f"{_MODULE}.embed", recorder.mock_embed),
            patch(f"{_EXCLUDE_MODULE}.embed", recorder.mock_embed),
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}._drift_check_endpoint"),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits),
            patch(f"{_MODULE}.load_bm25", return_value=MagicMock()),
            patch(f"{_MODULE}.bm25_topk", return_value=bm25_hits),
            patch(f"{_MODULE}.rrf", return_value=[(h[0], 0.5) for h in bm25_hits]),
            patch(f"{_MODULE}.get_verse", return_value=mock_verse),
            patch(
                f"{_MODULE}.load_dedupe_config",
                return_value=MagicMock(k_buffer=3, proximity_m=2),
            ),
            patch(
                f"{_MODULE}.load_exclude_config",
                return_value=MagicMock(exclude_m=5, exclude_buffer=10),
            ),
            patch(
                f"{_MODULE}.load_hybrid_config",
                return_value=MagicMock(bm25_weight=1.0, dense_weight=1.0),
            ),
            patch(f"{_MODULE}.proximity_dedupe", side_effect=lambda h, m, k: (h[:k], 0)),
            patch(f"{_EXCLUDE_MODULE}.open_store", return_value=mock_store),
            patch(f"{_EXCLUDE_MODULE}.dense_topk", return_value=dense_hits),
        ):
            result = query(
                "faith and works",
                k=5,
                mode="hybrid",
                index="latest",
                exclude="exclude this text",
            )

        assert len(recorder.calls) == 2, f"Expected 2 embed calls, got {len(recorder.calls)}"
        recorder.assert_no_overlap()

    def test_embed_calls_contain_both_query_and_exclude_text(
        self,
        mock_store: MagicMock,
        mock_manifest: MagicMock,
        dense_hits: list[MockDenseHit],
        mock_verse: MockVerse,
        tmp_path: Path,
    ) -> None:
        """Both query text and exclude text are embedded."""
        from scripvec_retrieval.query import query

        recorder = EmbedRecorder(delay_ms=5.0)

        with (
            patch(f"{_MODULE}.embed", recorder.mock_embed),
            patch(f"{_EXCLUDE_MODULE}.embed", recorder.mock_embed),
            patch(f"{_MODULE}._resolve_index", return_value=("abc123", tmp_path)),
            patch(f"{_MODULE}.read_manifest", return_value=mock_manifest),
            patch(f"{_MODULE}._drift_check_endpoint"),
            patch(f"{_MODULE}.extract_references", return_value=[]),
            patch(f"{_MODULE}.open_store", return_value=mock_store),
            patch(f"{_MODULE}.dense_topk", return_value=dense_hits),
            patch(f"{_MODULE}.get_verse", return_value=mock_verse),
            patch(
                f"{_MODULE}.load_dedupe_config",
                return_value=MagicMock(k_buffer=3, proximity_m=2),
            ),
            patch(
                f"{_MODULE}.load_exclude_config",
                return_value=MagicMock(exclude_m=5, exclude_buffer=10),
            ),
            patch(f"{_MODULE}.proximity_dedupe", side_effect=lambda h, m, k: (h[:k], 0)),
            patch(f"{_EXCLUDE_MODULE}.open_store", return_value=mock_store),
            patch(f"{_EXCLUDE_MODULE}.dense_topk", return_value=dense_hits),
        ):
            result = query(
                "faith and works",
                k=5,
                mode="dense",
                index="latest",
                exclude="exclude this text",
            )

        embedded_texts = {c.text for c in recorder.calls}
        assert "exclude this text" in embedded_texts, "Exclude text should be embedded"
        assert "faith and works" in embedded_texts, "Query text should be embedded"
