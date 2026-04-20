"""Tests for ADR-014 extracted-reference bounding by scope (CR-011 F-story)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from scripvec_retrieval.scope import Scope
from scripvec_retrieval.scope_filter import filter_by_scope


@dataclass(frozen=True)
class MockReference:
    """Mock Reference for testing scope filtering."""
    book: str
    chapter: int
    verse: int


class TestExtractedReferenceScopeBounding:
    """Tests for scope bounding of extracted references per ADR-014."""

    def test_unscoped_preserves_all_refs(self) -> None:
        """Unscoped queries preserve ADR-014 behavior byte-identically."""
        refs = [
            MockReference(book="1 Nephi", chapter=1, verse=1),
            MockReference(book="Alma", chapter=32, verse=21),
            MockReference(book="D&C", chapter=89, verse=1),
        ]
        scope = Scope(volume=None, book=None, range_refs=None)
        result = filter_by_scope(refs, scope)
        assert result == refs

    def test_volume_scope_filters_refs(self) -> None:
        """Volume scope drops refs outside the volume."""
        refs = [
            MockReference(book="1 Nephi", chapter=1, verse=1),
            MockReference(book="Alma", chapter=32, verse=21),
            MockReference(book="D&C", chapter=89, verse=1),
        ]
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope(refs, scope)
        assert len(result) == 2
        assert all(r.book != "D&C" for r in result)

    def test_book_scope_filters_refs(self) -> None:
        """Book scope drops refs from other books."""
        refs = [
            MockReference(book="1 Nephi", chapter=1, verse=1),
            MockReference(book="1 Nephi", chapter=3, verse=7),
            MockReference(book="Alma", chapter=32, verse=21),
        ]
        scope = Scope(volume=None, book="1 Nephi", range_refs=None)
        result = filter_by_scope(refs, scope)
        assert len(result) == 2
        assert all(r.book == "1 Nephi" for r in result)

    def test_refs_inside_scope_preserved(self) -> None:
        """Force-inclusion per ADR-014 applies for refs inside scope."""
        refs = [
            MockReference(book="Alma", chapter=32, verse=21),
            MockReference(book="Alma", chapter=32, verse=22),
        ]
        scope = Scope(volume="book_of_mormon", book="Alma", range_refs=None)
        result = filter_by_scope(refs, scope)
        assert len(result) == 2
        assert result == refs

    def test_all_refs_dropped_when_outside_scope(self) -> None:
        """All refs dropped when none are in scope."""
        refs = [
            MockReference(book="D&C", chapter=89, verse=1),
            MockReference(book="D&C", chapter=121, verse=45),
        ]
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope(refs, scope)
        assert result == []

    def test_empty_refs_returns_empty(self) -> None:
        """Empty refs list returns empty list."""
        refs: list[MockReference] = []
        scope = Scope(volume="book_of_mormon", book=None, range_refs=None)
        result = filter_by_scope(refs, scope)
        assert result == []
