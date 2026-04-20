"""Tests for query.py drift check and result handling."""

import os
from unittest.mock import MagicMock, patch

import pytest

from scripvec_retrieval.query import _drift_check_endpoint, query
from scripvec_retrieval.dedupe import proximity_dedupe
from scripvec_retrieval.scope import Scope
from scripvec_retrieval.window import Window, WindowVerse
from scripvec_corpus_ingest.verse import VerseRecord


class TestDriftCheckEndpoint:
    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_matching_config_passes(self) -> None:
        """Matching endpoint config passes."""
        _drift_check_endpoint("https://api.test.com", "test-model", 1536)

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.other.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_url_mismatch_raises(self) -> None:
        """URL mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "base_url" in msg
        assert "api.test.com" in msg
        assert "api.other.com" in msg

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "other-model",
        "SCRIPVEC_EMBED_DIM": "1536",
    })
    def test_model_mismatch_raises(self) -> None:
        """Model mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "model" in msg
        assert "test-model" in msg
        assert "other-model" in msg

    @patch.dict(os.environ, {
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_API_KEY": "test-key",
        "SCRIPVEC_EMBED_MODEL": "test-model",
        "SCRIPVEC_EMBED_DIM": "768",
    })
    def test_dim_mismatch_raises(self) -> None:
        """Dimension mismatch raises with both values."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_endpoint("https://api.test.com", "test-model", 1536)

        msg = str(exc_info.value)
        assert "dim" in msg
        assert "1536" in msg
        assert "768" in msg


class TestDedupeBeforeWindowOrdering:
    """Verify that dedupe runs before window expansion per CR-013."""

    @patch("scripvec_retrieval.query.get_window")
    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_window_only_called_for_surviving_hits(
        self,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
        mock_get_window,
    ) -> None:
        """get_window is only called for hits that survive dedupe."""
        from scripvec_retrieval.config import DedupeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=3, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        all_hits = [
            ("verse-1", 0.9),
            ("verse-2", 0.8),
            ("verse-3", 0.7),
        ]
        surviving_hits = [
            ("verse-1", 0.9),
            ("verse-3", 0.7),
        ]
        mock_run_bm25.return_value = all_hits
        mock_proximity_dedupe.return_value = (surviving_hits, 1)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store

        def fake_get_verse(store, verse_id):
            return VerseRecord(
                verse_id=verse_id,
                ref_canonical=f"Ref {verse_id}",
                book="1 Nephi",
                chapter=1,
                verse=1,
                text=f"Text for {verse_id}",
            )

        mock_get_verse.side_effect = fake_get_verse

        window_calls: list[str] = []

        def fake_get_window(store, verse_id, n):
            window_calls.append(verse_id)
            return Window(before=(), after=())

        mock_get_window.side_effect = fake_get_window

        result = query("test query", k=2, mode="bm25", index="abc123", window=1, dedupe=True)

        assert window_calls == ["verse-1", "verse-3"]
        assert "verse-2" not in window_calls

    @patch("scripvec_retrieval.query.get_window")
    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_overlapping_windows_render_independently(
        self,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
        mock_get_window,
    ) -> None:
        """Each surviving hit gets its own full window, even if windows overlap."""
        from scripvec_retrieval.config import DedupeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=3, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        surviving_hits = [
            ("1-nephi-3-7", 0.9),
            ("1-nephi-3-8", 0.8),
        ]
        mock_run_bm25.return_value = surviving_hits
        mock_proximity_dedupe.return_value = (surviving_hits, 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store

        def fake_get_verse(store, verse_id):
            return VerseRecord(
                verse_id=verse_id,
                ref_canonical=f"Ref {verse_id}",
                book="1 Nephi",
                chapter=3,
                verse=7,
                text=f"Text for {verse_id}",
            )

        mock_get_verse.side_effect = fake_get_verse

        def fake_get_window(store, verse_id, n):
            if verse_id == "1-nephi-3-7":
                return Window(
                    before=(WindowVerse(ref="1 Nephi 3:6", text="verse 6"),),
                    after=(WindowVerse(ref="1 Nephi 3:8", text="verse 8"),),
                )
            else:
                return Window(
                    before=(WindowVerse(ref="1 Nephi 3:7", text="verse 7"),),
                    after=(WindowVerse(ref="1 Nephi 3:9", text="verse 9"),),
                )

        mock_get_window.side_effect = fake_get_window

        result = query("test query", k=2, mode="bm25", index="abc123", window=1, dedupe=True)

        assert len(result.results) == 2

        first_window = result.results[0].window
        assert first_window is not None
        assert len(first_window.before) == 1
        assert first_window.before[0].ref == "1 Nephi 3:6"
        assert len(first_window.after) == 1
        assert first_window.after[0].ref == "1 Nephi 3:8"

        second_window = result.results[1].window
        assert second_window is not None
        assert len(second_window.before) == 1
        assert second_window.before[0].ref == "1 Nephi 3:7"
        assert len(second_window.after) == 1
        assert second_window.after[0].ref == "1 Nephi 3:9"
