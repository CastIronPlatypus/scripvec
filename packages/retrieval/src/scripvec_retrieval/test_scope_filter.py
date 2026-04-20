"""Unit tests for scope_filter.py — post-retrieval scope filtering."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripvec_reference.reference import Reference

from .scope import Scope
from .scope_filter import filter_by_scope


@dataclass(frozen=True)
class MockHit:
    """Mock hit for testing scope filter."""

    book: str
    chapter: int
    verse: int


def make_hit(book: str, chapter: int, verse: int) -> MockHit:
    """Create a mock hit for testing."""
    return MockHit(book=book, chapter=chapter, verse=verse)


class TestFilterByScope:
    """Tests for filter_by_scope function."""

    def test_empty_scope_returns_all(self) -> None:
        """Empty scope (all None) returns all hits unchanged."""
        hits = [make_hit("Alma", 32, 21), make_hit("1 Nephi", 3, 7)]
        scope = Scope(volume=None, book=None, range_refs=None)
        result = filter_by_scope(hits, scope)
        assert result == hits

    def test_volume_only_filter(self) -> None:
        """Volume-only scope filters correctly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("D&C", 121, 1),
            make_hit("1 Nephi", 3, 7),
        ]
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope(hits, scope)
        assert len(result) == 2
        assert result[0].book == "Alma"
        assert result[1].book == "1 Nephi"

    def test_book_only_filter(self) -> None:
        """Book-only scope filters correctly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("Alma", 5, 46),
            make_hit("1 Nephi", 3, 7),
        ]
        scope = Scope(volume=None, book="Alma", range_refs=None)
        result = filter_by_scope(hits, scope)
        assert len(result) == 2
        assert all(h.book == "Alma" for h in result)

    def test_range_only_single_reference(self) -> None:
        """Range with single reference filters exactly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("Alma", 32, 22),
            make_hit("Alma", 5, 46),
        ]
        ref = Reference(book="Alma", chapter=32, verse=21)
        scope = Scope(volume=None, book=None, range_refs=(ref,))
        result = filter_by_scope(hits, scope)
        assert len(result) == 1
        assert result[0].verse == 21

    def test_range_only_range_filter(self) -> None:
        """Range filter includes verses within range (inclusive)."""
        hits = [
            make_hit("Alma", 32, 19),
            make_hit("Alma", 32, 20),
            make_hit("Alma", 32, 21),
            make_hit("Alma", 32, 22),
            make_hit("Alma", 32, 23),
        ]
        start = Reference(book="Alma", chapter=32, verse=20)
        end = Reference(book="Alma", chapter=32, verse=22)
        scope = Scope(volume=None, book=None, range_refs=((start, end),))
        result = filter_by_scope(hits, scope)
        assert len(result) == 3
        assert [h.verse for h in result] == [20, 21, 22]

    def test_range_multi_chapter_range(self) -> None:
        """Range spanning multiple chapters filters correctly."""
        hits = [
            make_hit("Alma", 31, 38),
            make_hit("Alma", 32, 1),
            make_hit("Alma", 32, 21),
            make_hit("Alma", 33, 1),
            make_hit("Alma", 33, 5),
            make_hit("Alma", 34, 1),
        ]
        start = Reference(book="Alma", chapter=32, verse=1)
        end = Reference(book="Alma", chapter=33, verse=2)
        scope = Scope(volume=None, book=None, range_refs=((start, end),))
        result = filter_by_scope(hits, scope)
        assert len(result) == 3
        assert result[0] == make_hit("Alma", 32, 1)
        assert result[1] == make_hit("Alma", 32, 21)
        assert result[2] == make_hit("Alma", 33, 1)

    def test_volume_plus_book_composition(self) -> None:
        """Volume + book composition filters correctly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("1 Nephi", 3, 7),
            make_hit("D&C", 121, 1),
        ]
        scope = Scope(volume="book_of_mormon", book="Alma", range_refs=None)
        result = filter_by_scope(hits, scope)
        assert len(result) == 1
        assert result[0].book == "Alma"

    def test_volume_plus_range_composition(self) -> None:
        """Volume + range composition filters correctly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("Alma", 32, 22),
            make_hit("D&C", 121, 1),
        ]
        ref = Reference(book="Alma", chapter=32, verse=21)
        scope = Scope(volume="book_of_mormon", book=None, range_refs=(ref,))
        result = filter_by_scope(hits, scope)
        assert len(result) == 1
        assert result[0].verse == 21

    def test_book_plus_range_composition(self) -> None:
        """Book + range composition filters correctly."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("Alma", 5, 46),
            make_hit("1 Nephi", 3, 7),
        ]
        ref = Reference(book="Alma", chapter=32, verse=21)
        scope = Scope(volume=None, book="Alma", range_refs=(ref,))
        result = filter_by_scope(hits, scope)
        assert len(result) == 1
        assert result[0].chapter == 32 and result[0].verse == 21

    def test_triple_composition(self) -> None:
        """Volume + book + range composition filters correctly (intersection)."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("Alma", 32, 22),
            make_hit("1 Nephi", 32, 21),
            make_hit("D&C", 32, 21),
        ]
        ref = Reference(book="Alma", chapter=32, verse=21)
        scope = Scope(volume="book_of_mormon", book="Alma", range_refs=(ref,))
        result = filter_by_scope(hits, scope)
        assert len(result) == 1
        assert result[0] == make_hit("Alma", 32, 21)

    def test_order_preserved(self) -> None:
        """Order of kept hits is preserved."""
        hits = [
            make_hit("Alma", 5, 1),
            make_hit("Alma", 32, 21),
            make_hit("Alma", 10, 5),
            make_hit("Alma", 1, 1),
        ]
        scope = Scope(volume=None, book="Alma", range_refs=None)
        result = filter_by_scope(hits, scope)
        assert result == hits

    def test_chapter_boundary_inclusive_start(self) -> None:
        """Range start is inclusive at chapter start."""
        hits = [
            make_hit("Alma", 32, 1),
            make_hit("Alma", 32, 2),
        ]
        start = Reference(book="Alma", chapter=32, verse=1)
        end = Reference(book="Alma", chapter=32, verse=5)
        scope = Scope(volume=None, book=None, range_refs=((start, end),))
        result = filter_by_scope(hits, scope)
        assert len(result) == 2

    def test_chapter_boundary_inclusive_end(self) -> None:
        """Range end is inclusive at chapter end."""
        hits = [
            make_hit("Alma", 32, 40),
            make_hit("Alma", 32, 41),
            make_hit("Alma", 32, 42),
        ]
        start = Reference(book="Alma", chapter=32, verse=40)
        end = Reference(book="Alma", chapter=32, verse=41)
        scope = Scope(volume=None, book=None, range_refs=((start, end),))
        result = filter_by_scope(hits, scope)
        assert len(result) == 2
        assert result[0].verse == 40
        assert result[1].verse == 41

    def test_empty_hits_returns_empty(self) -> None:
        """Empty hits list returns empty list."""
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope([], scope)
        assert result == []

    def test_no_matches_returns_empty(self) -> None:
        """No matching hits returns empty list."""
        hits = [make_hit("D&C", 121, 1)]
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope(hits, scope)
        assert result == []

    def test_multiple_ranges_or_logic(self) -> None:
        """Multiple range_refs use OR logic (match any)."""
        hits = [
            make_hit("Alma", 32, 21),
            make_hit("1 Nephi", 3, 7),
            make_hit("Mosiah", 5, 2),
        ]
        ref1 = Reference(book="Alma", chapter=32, verse=21)
        ref2 = Reference(book="1 Nephi", chapter=3, verse=7)
        scope = Scope(volume=None, book=None, range_refs=(ref1, ref2))
        result = filter_by_scope(hits, scope)
        assert len(result) == 2
        assert result[0].book == "Alma"
        assert result[1].book == "1 Nephi"
