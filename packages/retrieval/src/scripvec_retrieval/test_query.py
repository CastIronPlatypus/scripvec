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


class TestScopeBufferWidening:
    """Tests for scope buffer widening per CR-011."""

    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    @patch("scripvec_retrieval.query.load_scope_config")
    def test_scoped_query_widens_retrieval_by_buffer(
        self,
        mock_scope_cfg,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
    ) -> None:
        """Scoped query retrieves k * scope_buffer candidates."""
        from scripvec_retrieval.config import DedupeConfig, ScopeConfig

        mock_scope_cfg.return_value = ScopeConfig(scope_buffer=5)
        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=3, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        mock_run_bm25.return_value = [("alma-32-21", 0.9)]
        mock_proximity_dedupe.return_value = ([("alma-32-21", 0.9)], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store
        mock_get_verse.return_value = VerseRecord(
            verse_id="alma-32-21",
            ref_canonical="Alma 32:21",
            book="Alma",
            chapter=32,
            verse=21,
            text="Test text",
        )

        scope = Scope(volume=None, book="Alma", range_refs=None)
        result = query("test query", k=10, mode="bm25", index="abc123", scope=scope)

        mock_run_bm25.assert_called_once()
        call_args = mock_run_bm25.call_args
        assert call_args[0][2] == 50

    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_unscoped_query_uses_k_directly(
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
    ) -> None:
        """Unscoped query uses k directly (byte-identical to pre-scope behavior)."""
        from scripvec_retrieval.config import DedupeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=3, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        mock_run_bm25.return_value = [("alma-32-21", 0.9)]
        mock_proximity_dedupe.return_value = ([("alma-32-21", 0.9)], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store
        mock_get_verse.return_value = VerseRecord(
            verse_id="alma-32-21",
            ref_canonical="Alma 32:21",
            book="Alma",
            chapter=32,
            verse=21,
            text="Test text",
        )

        result = query("test query", k=10, mode="bm25", index="abc123", scope=None)

        mock_run_bm25.assert_called_once()
        call_args = mock_run_bm25.call_args
        assert call_args[0][2] == 10

    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    @patch("scripvec_retrieval.query.load_scope_config")
    def test_scoped_query_filters_out_of_scope_hits(
        self,
        mock_scope_cfg,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
    ) -> None:
        """Scoped query filters out-of-scope hits after retrieval."""
        from scripvec_retrieval.config import DedupeConfig, ScopeConfig

        mock_scope_cfg.return_value = ScopeConfig(scope_buffer=5)
        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=0, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        all_hits = [
            ("alma-32-21", 0.9),
            ("1-nephi-3-7", 0.8),
            ("alma-32-22", 0.7),
            ("mosiah-4-9", 0.6),
        ]
        mock_run_bm25.return_value = all_hits
        mock_proximity_dedupe.side_effect = lambda hits, m, k: (hits[:k], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store

        def fake_get_verse(store, verse_id):
            book_map = {
                "alma-32-21": ("Alma", 32, 21),
                "1-nephi-3-7": ("1 Nephi", 3, 7),
                "alma-32-22": ("Alma", 32, 22),
                "mosiah-4-9": ("Mosiah", 4, 9),
            }
            book, ch, vs = book_map[verse_id]
            return VerseRecord(
                verse_id=verse_id,
                ref_canonical=f"{book} {ch}:{vs}",
                book=book,
                chapter=ch,
                verse=vs,
                text=f"Text for {verse_id}",
            )

        mock_get_verse.side_effect = fake_get_verse

        scope = Scope(volume=None, book="Alma", range_refs=None)
        result = query("test query", k=2, mode="bm25", index="abc123", scope=scope, dedupe=False)

        assert len(result.results) == 2
        assert result.results[0].verse_id == "alma-32-21"
        assert result.results[1].verse_id == "alma-32-22"

    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    @patch("scripvec_retrieval.query.load_scope_config")
    def test_scoped_query_returns_fewer_than_k_if_insufficient_matches(
        self,
        mock_scope_cfg,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
    ) -> None:
        """Scoped query returns < K hits if scope keeps fewer than K; no padding."""
        from scripvec_retrieval.config import DedupeConfig, ScopeConfig

        mock_scope_cfg.return_value = ScopeConfig(scope_buffer=5)
        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=0, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        all_hits = [
            ("1-nephi-3-7", 0.9),
            ("mosiah-4-9", 0.8),
            ("alma-32-21", 0.7),
        ]
        mock_run_bm25.return_value = all_hits
        mock_proximity_dedupe.side_effect = lambda hits, m, k: (hits[:k], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store

        def fake_get_verse(store, verse_id):
            book_map = {
                "alma-32-21": ("Alma", 32, 21),
                "1-nephi-3-7": ("1 Nephi", 3, 7),
                "mosiah-4-9": ("Mosiah", 4, 9),
            }
            book, ch, vs = book_map[verse_id]
            return VerseRecord(
                verse_id=verse_id,
                ref_canonical=f"{book} {ch}:{vs}",
                book=book,
                chapter=ch,
                verse=vs,
                text=f"Text for {verse_id}",
            )

        mock_get_verse.side_effect = fake_get_verse

        scope = Scope(volume=None, book="Alma", range_refs=None)
        result = query("test query", k=10, mode="bm25", index="abc123", scope=scope, dedupe=False)

        assert len(result.results) == 1
        assert result.results[0].verse_id == "alma-32-21"


class TestHybridExclusionPreRRF:
    """Tests for hybrid mode exclusion applied pre-RRF per CR-014 B8."""

    @patch("scripvec_retrieval.query.filter_by_exclusion")
    @patch("scripvec_retrieval.query.compute_exclusion_set")
    @patch("scripvec_retrieval.query.load_exclude_config")
    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query.rrf")
    @patch("scripvec_retrieval.query._run_dense")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_exclusion_applied_to_both_streams_before_rrf(
        self,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_run_dense,
        mock_rrf,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
        mock_exclude_cfg,
        mock_compute_exclusion,
        mock_filter_by_exclusion,
    ) -> None:
        """Exclusion is applied to BM25 and dense before RRF in hybrid mode."""
        from scripvec_retrieval.config import DedupeConfig, ExcludeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=0, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        bm25_hits = [("v1", 0.9), ("v2", 0.8), ("v3", 0.7)]
        dense_hits = [("v2", 0.95), ("v1", 0.85), ("v4", 0.75)]
        mock_run_bm25.return_value = bm25_hits
        mock_run_dense.return_value = dense_hits

        mock_exclude_cfg.return_value = ExcludeConfig(exclude_m=10, exclude_buffer=20)
        mock_compute_exclusion.return_value = ["v2"]

        filtered_bm25 = [("v1", 0.9), ("v3", 0.7)]
        filtered_dense = [("v1", 0.85), ("v4", 0.75)]
        filter_call_count = [0]

        def mock_filter(hits, exclusion_set):
            filter_call_count[0] += 1
            return [h for h in hits if h[0] not in exclusion_set]

        mock_filter_by_exclusion.side_effect = mock_filter

        fused = [("v1", 0.05), ("v3", 0.03), ("v4", 0.02)]
        mock_rrf.return_value = fused
        mock_proximity_dedupe.side_effect = lambda hits, m, k: (hits[:k], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store
        mock_get_verse.return_value = VerseRecord(
            verse_id="v1",
            ref_canonical="Test 1:1",
            book="Test",
            chapter=1,
            verse=1,
            text="Test text",
        )

        result = query(
            "test query",
            k=3,
            mode="hybrid",
            index="abc123",
            exclude="exclude this",
            dedupe=False,
        )

        assert filter_call_count[0] == 2

        rrf_call_args = mock_rrf.call_args
        bm25_arg = rrf_call_args[0][0]
        dense_arg = rrf_call_args[0][1]
        assert ("v2", 0.8) not in bm25_arg
        assert ("v2", 0.95) not in dense_arg

    @patch("scripvec_retrieval.query.filter_by_exclusion")
    @patch("scripvec_retrieval.query.compute_exclusion_set")
    @patch("scripvec_retrieval.query.load_exclude_config")
    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query.rrf")
    @patch("scripvec_retrieval.query._run_dense")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_exclude_info_populated_in_hybrid_response(
        self,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_run_dense,
        mock_rrf,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
        mock_exclude_cfg,
        mock_compute_exclusion,
        mock_filter_by_exclusion,
    ) -> None:
        """ExcludeInfo is populated in hybrid response when --exclude is used."""
        from scripvec_retrieval.config import DedupeConfig, ExcludeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=0, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        mock_run_bm25.return_value = [("v1", 0.9)]
        mock_run_dense.return_value = [("v1", 0.95)]

        mock_exclude_cfg.return_value = ExcludeConfig(exclude_m=10, exclude_buffer=20)
        mock_compute_exclusion.return_value = ["excluded-1", "excluded-2"]
        mock_filter_by_exclusion.side_effect = lambda hits, ex: hits

        mock_rrf.return_value = [("v1", 0.05)]
        mock_proximity_dedupe.side_effect = lambda hits, m, k: (hits[:k], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store
        mock_get_verse.return_value = VerseRecord(
            verse_id="v1",
            ref_canonical="Test 1:1",
            book="Test",
            chapter=1,
            verse=1,
            text="Test text",
        )

        result = query(
            "test query",
            k=3,
            mode="hybrid",
            index="abc123",
            exclude="exclude this text",
            dedupe=False,
        )

        assert result.exclude is not None
        assert result.exclude.text == "exclude this text"
        assert result.exclude.set_size == 10
        assert result.exclude.excluded_verse_ids == ("excluded-1", "excluded-2")

    @patch("scripvec_retrieval.query.get_verse")
    @patch("scripvec_retrieval.query.open_store")
    @patch("scripvec_retrieval.query.proximity_dedupe")
    @patch("scripvec_retrieval.query.rrf")
    @patch("scripvec_retrieval.query._run_dense")
    @patch("scripvec_retrieval.query._run_bm25")
    @patch("scripvec_retrieval.query._resolve_index")
    @patch("scripvec_retrieval.query.read_manifest")
    @patch("scripvec_retrieval.query._drift_check_endpoint")
    @patch("scripvec_retrieval.query.extract_references")
    @patch("scripvec_retrieval.query.load_dedupe_config")
    def test_exclude_info_absent_when_no_exclude(
        self,
        mock_dedupe_cfg,
        mock_extract_refs,
        mock_drift_check,
        mock_read_manifest,
        mock_resolve_index,
        mock_run_bm25,
        mock_run_dense,
        mock_rrf,
        mock_proximity_dedupe,
        mock_open_store,
        mock_get_verse,
    ) -> None:
        """ExcludeInfo is None in hybrid response when --exclude not used."""
        from scripvec_retrieval.config import DedupeConfig

        mock_dedupe_cfg.return_value = DedupeConfig(proximity_m=0, k_buffer=3)
        mock_extract_refs.return_value = []
        mock_resolve_index.return_value = ("abc123", MagicMock())
        mock_read_manifest.return_value = MagicMock(
            embed_endpoint="https://api.test.com",
            embed_model="test-model",
            embed_dim=1536,
        )

        mock_run_bm25.return_value = [("v1", 0.9)]
        mock_run_dense.return_value = [("v1", 0.95)]
        mock_rrf.return_value = [("v1", 0.05)]
        mock_proximity_dedupe.side_effect = lambda hits, m, k: (hits[:k], 0)

        mock_store = MagicMock()
        mock_open_store.return_value = mock_store
        mock_get_verse.return_value = VerseRecord(
            verse_id="v1",
            ref_canonical="Test 1:1",
            book="Test",
            chapter=1,
            verse=1,
            text="Test text",
        )

        result = query(
            "test query",
            k=3,
            mode="hybrid",
            index="abc123",
            exclude=None,
            dedupe=False,
        )

        assert result.exclude is None
