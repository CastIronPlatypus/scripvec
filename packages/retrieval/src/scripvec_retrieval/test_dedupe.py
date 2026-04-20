"""Tests for dedupe.py per CR-013 B4."""

from __future__ import annotations

import pytest

from scripvec_retrieval.dedupe import ParsedVerseId, parse_verse_id, proximity_dedupe


class TestParseVerseId:
    """Tests for parse_verse_id helper."""

    def test_standard_book(self) -> None:
        result = parse_verse_id("1-nephi-3-7")
        assert result == ParsedVerseId(book="1-nephi", chapter=3, verse=7)

    def test_dandc(self) -> None:
        result = parse_verse_id("dandc-88-118")
        assert result == ParsedVerseId(book="dandc", chapter=88, verse=118)

    def test_alma(self) -> None:
        result = parse_verse_id("alma-32-21")
        assert result == ParsedVerseId(book="alma", chapter=32, verse=21)

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_verse_id("invalid")

    def test_non_numeric_chapter_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_verse_id("alma-abc-21")


class TestProximityDedupe:
    """Tests for proximity_dedupe (CR-013 B4)."""

    def test_same_chapter_close_pair_drops_lower(self) -> None:
        """Same-chapter close pair → lower-scored dropped."""
        hits = [
            ("alma-32-21", 0.9),
            ("alma-32-22", 0.8),
        ]
        kept, dropped = proximity_dedupe(hits, m=2, k=10)
        assert kept == [("alma-32-21", 0.9)]
        assert dropped == 1

    def test_cross_chapter_close_verse_numbers_both_kept(self) -> None:
        """Cross-chapter close verse-numbers → both kept."""
        hits = [
            ("alma-32-1", 0.9),
            ("alma-33-1", 0.8),
        ]
        kept, dropped = proximity_dedupe(hits, m=5, k=10)
        assert kept == hits
        assert dropped == 0

    def test_cross_book_close_verse_numbers_both_kept(self) -> None:
        """Cross-book close verse-numbers → both kept."""
        hits = [
            ("alma-32-1", 0.9),
            ("mosiah-32-1", 0.8),
        ]
        kept, dropped = proximity_dedupe(hits, m=5, k=10)
        assert kept == hits
        assert dropped == 0

    def test_score_ordering_respected(self) -> None:
        """Higher score wins the keep."""
        hits = [
            ("alma-32-25", 0.95),
            ("alma-32-24", 0.90),
            ("alma-32-26", 0.85),
        ]
        kept, dropped = proximity_dedupe(hits, m=2, k=10)
        assert kept == [("alma-32-25", 0.95)]
        assert dropped == 2

    def test_dropped_count_accurate(self) -> None:
        """dropped count is correct under various inputs."""
        hits = [
            ("alma-32-1", 0.9),
            ("alma-32-2", 0.8),
            ("alma-32-10", 0.7),
            ("alma-32-11", 0.6),
            ("alma-32-20", 0.5),
        ]
        kept, dropped = proximity_dedupe(hits, m=2, k=10)
        assert len(kept) + dropped == len(hits)
        assert dropped == 2

    def test_kept_truncated_to_k(self) -> None:
        """Kept list truncated to exactly k."""
        hits = [
            ("alma-1-1", 0.9),
            ("alma-2-1", 0.8),
            ("alma-3-1", 0.7),
            ("alma-4-1", 0.6),
            ("alma-5-1", 0.5),
        ]
        kept, dropped = proximity_dedupe(hits, m=2, k=3)
        assert len(kept) == 3
        assert kept == [("alma-1-1", 0.9), ("alma-2-1", 0.8), ("alma-3-1", 0.7)]

    def test_fewer_than_k_kept_if_fewer_input(self) -> None:
        """If fewer than k non-proximate hits, return fewer."""
        hits = [
            ("alma-32-1", 0.9),
            ("alma-32-2", 0.8),
        ]
        kept, dropped = proximity_dedupe(hits, m=5, k=10)
        assert len(kept) == 1
        assert kept == [("alma-32-1", 0.9)]
        assert dropped == 1

    def test_empty_hits_returns_empty(self) -> None:
        """Empty hits list returns empty result."""
        kept, dropped = proximity_dedupe([], m=5, k=10)
        assert kept == []
        assert dropped == 0

    def test_m_zero_keeps_all_unique(self) -> None:
        """M=0 only dedupes exact verse matches."""
        hits = [
            ("alma-32-1", 0.9),
            ("alma-32-2", 0.8),
            ("alma-32-3", 0.7),
        ]
        kept, dropped = proximity_dedupe(hits, m=0, k=10)
        assert kept == hits
        assert dropped == 0

    def test_exact_duplicate_dropped(self) -> None:
        """Exact same verse_id in hits is dropped."""
        hits = [
            ("alma-32-1", 0.9),
            ("alma-32-1", 0.8),
        ]
        kept, dropped = proximity_dedupe(hits, m=0, k=10)
        assert kept == [("alma-32-1", 0.9)]
        assert dropped == 1

    def test_mixed_books_and_chapters(self) -> None:
        """Complex scenario with multiple books and chapters."""
        hits = [
            ("1-nephi-3-7", 0.95),
            ("1-nephi-3-8", 0.90),
            ("alma-32-21", 0.85),
            ("alma-32-23", 0.80),
            ("dandc-88-118", 0.75),
            ("dandc-88-119", 0.70),
        ]
        kept, dropped = proximity_dedupe(hits, m=2, k=10)
        expected_kept = [
            ("1-nephi-3-7", 0.95),
            ("alma-32-21", 0.85),
            ("dandc-88-118", 0.75),
        ]
        assert kept == expected_kept
        assert dropped == 3
