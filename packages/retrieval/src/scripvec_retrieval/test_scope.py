"""Tests for scope.py — Scope dataclass and canonical normalization."""

import pytest

from scripvec_retrieval.scope import (
    BOOK_TO_VOLUME,
    CANONICAL_VOLUMES,
    VOLUMES_WITH_BOOKS,
    BookNotInVolumeError,
    MalformedRangeError,
    RangeOutsideScopeError,
    Scope,
    UnknownBookError,
    UnknownVolumeError,
    VolumeHasNoBooksError,
    canonicalize_book_for_scope,
    canonicalize_range,
    canonicalize_volume,
)
from scripvec_reference.reference import Reference


class TestCanonicalizeVolume:
    """Tests for volume canonicalization."""

    def test_book_of_mormon_accepted(self) -> None:
        assert canonicalize_volume("book_of_mormon") == "book_of_mormon"

    def test_doctrine_and_covenants_accepted(self) -> None:
        assert canonicalize_volume("doctrine_and_covenants") == "doctrine_and_covenants"

    def test_unknown_volume_raises(self) -> None:
        with pytest.raises(UnknownVolumeError) as exc_info:
            canonicalize_volume("pearl_of_great_price")
        assert exc_info.value.volume == "pearl_of_great_price"
        assert "Unknown volume" in str(exc_info.value)

    def test_case_variant_raises(self) -> None:
        with pytest.raises(UnknownVolumeError):
            canonicalize_volume("Book_of_Mormon")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(UnknownVolumeError):
            canonicalize_volume("")


class TestCanonicalizeBook:
    """Tests for book canonicalization."""

    def test_alma_accepted(self) -> None:
        assert canonicalize_book_for_scope("Alma") == "Alma"

    def test_first_nephi_accepted(self) -> None:
        assert canonicalize_book_for_scope("1 Nephi") == "1 Nephi"

    def test_d_and_c_accepted(self) -> None:
        assert canonicalize_book_for_scope("D&C") == "D&C"

    def test_unknown_book_raises(self) -> None:
        with pytest.raises(UnknownBookError) as exc_info:
            canonicalize_book_for_scope("Genesis")
        assert exc_info.value.book == "Genesis"
        assert "Unknown book" in str(exc_info.value)

    def test_abbreviation_raises(self) -> None:
        with pytest.raises(UnknownBookError):
            canonicalize_book_for_scope("Alm")

    def test_case_variant_raises(self) -> None:
        with pytest.raises(UnknownBookError):
            canonicalize_book_for_scope("alma")


class TestCanonicalizeRange:
    """Tests for range/list canonicalization."""

    def test_single_reference_parsed(self) -> None:
        result = canonicalize_range("Alma 32:21")
        assert len(result) == 1
        assert isinstance(result[0], Reference)
        assert result[0].book == "Alma"
        assert result[0].chapter == 32
        assert result[0].verse == 21

    def test_range_parsed(self) -> None:
        result = canonicalize_range("Alma 32:21 - Alma 32:23")
        assert len(result) == 1
        start, end = result[0]
        assert start.book == "Alma"
        assert start.chapter == 32
        assert start.verse == 21
        assert end.verse == 23

    def test_list_parsed(self) -> None:
        result = canonicalize_range("Alma 32:21; Moroni 7:5")
        assert len(result) == 2
        assert result[0].book == "Alma"
        assert result[1].book == "Moroni"

    def test_malformed_range_raises(self) -> None:
        with pytest.raises(MalformedRangeError) as exc_info:
            canonicalize_range("Alma 32.21")
        assert exc_info.value.range_str == "Alma 32.21"
        assert "Malformed range" in str(exc_info.value)

    def test_unknown_book_in_range_raises(self) -> None:
        with pytest.raises(MalformedRangeError):
            canonicalize_range("Genesis 1:1")


class TestScopeFromFlags:
    """Tests for Scope.from_flags() constructor."""

    def test_all_none_produces_empty_scope(self) -> None:
        scope = Scope.from_flags()
        assert scope.volume is None
        assert scope.book is None
        assert scope.range_refs is None

    def test_volume_only(self) -> None:
        scope = Scope.from_flags(volume="book_of_mormon")
        assert scope.volume == "book_of_mormon"
        assert scope.book is None
        assert scope.range_refs is None

    def test_book_only(self) -> None:
        scope = Scope.from_flags(book="Alma")
        assert scope.volume is None
        assert scope.book == "Alma"
        assert scope.range_refs is None

    def test_range_only(self) -> None:
        scope = Scope.from_flags(range_str="Alma 32:21")
        assert scope.volume is None
        assert scope.book is None
        assert scope.range_refs is not None
        assert len(scope.range_refs) == 1

    def test_all_three_flags(self) -> None:
        scope = Scope.from_flags(
            volume="book_of_mormon",
            book="Alma",
            range_str="Alma 32:21",
        )
        assert scope.volume == "book_of_mormon"
        assert scope.book == "Alma"
        assert scope.range_refs is not None

    def test_unknown_volume_raises(self) -> None:
        with pytest.raises(UnknownVolumeError):
            Scope.from_flags(volume="invalid")

    def test_unknown_book_raises(self) -> None:
        with pytest.raises(UnknownBookError):
            Scope.from_flags(book="Invalid")

    def test_malformed_range_raises(self) -> None:
        with pytest.raises(MalformedRangeError):
            Scope.from_flags(range_str="invalid range")


class TestCatalogs:
    """Tests for catalog completeness and consistency."""

    def test_all_canonical_volumes_present(self) -> None:
        assert "book_of_mormon" in CANONICAL_VOLUMES
        assert "doctrine_and_covenants" in CANONICAL_VOLUMES

    def test_book_to_volume_has_all_bom_books(self) -> None:
        bom_books = [
            "1 Nephi", "2 Nephi", "Jacob", "Enos", "Jarom", "Omni",
            "Words of Mormon", "Mosiah", "Alma", "Helaman",
            "3 Nephi", "4 Nephi", "Mormon", "Ether", "Moroni",
        ]
        for book in bom_books:
            assert BOOK_TO_VOLUME.get(book) == "book_of_mormon"

    def test_d_and_c_mapped_to_doctrine_and_covenants(self) -> None:
        assert BOOK_TO_VOLUME.get("D&C") == "doctrine_and_covenants"

    def test_bom_has_books_dc_does_not(self) -> None:
        assert "book_of_mormon" in VOLUMES_WITH_BOOKS
        assert "doctrine_and_covenants" not in VOLUMES_WITH_BOOKS


class TestScopeImmutability:
    """Tests that Scope is frozen/immutable."""

    def test_scope_is_frozen(self) -> None:
        scope = Scope.from_flags(volume="book_of_mormon")
        with pytest.raises(AttributeError):
            scope.volume = "doctrine_and_covenants"  # type: ignore[misc]

    def test_range_refs_is_tuple(self) -> None:
        scope = Scope.from_flags(range_str="Alma 32:21")
        assert isinstance(scope.range_refs, tuple)


class TestScopeConsistencyValidation:
    """Tests for scope-consistency validation per ADR-001 (F2 bead)."""

    def test_d_and_c_with_book_raises_exact_message(self) -> None:
        """D&C has sections, not books — exact message required."""
        with pytest.raises(VolumeHasNoBooksError) as exc_info:
            Scope.from_flags(book="D&C")
        assert "D&C has sections, not books; use --range instead" in str(exc_info.value)

    def test_book_not_in_volume_raises(self) -> None:
        """Book not belonging to specified volume raises with both names."""
        with pytest.raises(BookNotInVolumeError) as exc_info:
            Scope.from_flags(volume="doctrine_and_covenants", book="Alma")
        assert exc_info.value.book == "Alma"
        assert exc_info.value.volume == "doctrine_and_covenants"
        assert "Alma" in str(exc_info.value)
        assert "doctrine_and_covenants" in str(exc_info.value)

    def test_book_in_correct_volume_succeeds(self) -> None:
        """Book in correct volume passes validation."""
        scope = Scope.from_flags(volume="book_of_mormon", book="Alma")
        assert scope.volume == "book_of_mormon"
        assert scope.book == "Alma"

    def test_range_outside_volume_raises(self) -> None:
        """Range referencing book outside specified volume raises."""
        with pytest.raises(RangeOutsideScopeError) as exc_info:
            Scope.from_flags(volume="doctrine_and_covenants", range_str="Alma 32:21")
        assert exc_info.value.reference_book == "Alma"
        assert exc_info.value.scope_filter == "--volume"
        assert exc_info.value.scope_value == "doctrine_and_covenants"
        assert "Alma" in str(exc_info.value)
        assert "--volume" in str(exc_info.value)
        assert "doctrine_and_covenants" in str(exc_info.value)

    def test_range_outside_book_raises(self) -> None:
        """Range referencing different book than --book raises."""
        with pytest.raises(RangeOutsideScopeError) as exc_info:
            Scope.from_flags(book="Alma", range_str="Helaman 5:12")
        assert exc_info.value.reference_book == "Helaman"
        assert exc_info.value.scope_filter == "--book"
        assert exc_info.value.scope_value == "Alma"
        assert "Helaman" in str(exc_info.value)
        assert "--book" in str(exc_info.value)
        assert "Alma" in str(exc_info.value)

    def test_range_inside_volume_succeeds(self) -> None:
        """Range within specified volume passes validation."""
        scope = Scope.from_flags(volume="book_of_mormon", range_str="Alma 32:21")
        assert scope.volume == "book_of_mormon"
        assert scope.range_refs is not None

    def test_range_inside_book_succeeds(self) -> None:
        """Range within specified book passes validation."""
        scope = Scope.from_flags(book="Alma", range_str="Alma 32:21")
        assert scope.book == "Alma"
        assert scope.range_refs is not None

    def test_range_list_validates_all_refs(self) -> None:
        """All references in a list must be in scope."""
        with pytest.raises(RangeOutsideScopeError):
            Scope.from_flags(book="Alma", range_str="Alma 32:21; Moroni 7:5")

    def test_range_endpoints_both_validated(self) -> None:
        """Both endpoints of a range are validated."""
        with pytest.raises(RangeOutsideScopeError):
            Scope.from_flags(
                volume="book_of_mormon",
                range_str="D&C 76:1 - D&C 76:10",
            )

    def test_all_three_consistent_succeeds(self) -> None:
        """Consistent volume + book + range passes."""
        scope = Scope.from_flags(
            volume="book_of_mormon",
            book="Alma",
            range_str="Alma 32:21 - Alma 32:23",
        )
        assert scope.volume == "book_of_mormon"
        assert scope.book == "Alma"
        assert scope.range_refs is not None

    def test_volume_only_no_validation_needed(self) -> None:
        """Volume-only scope needs no cross-field validation."""
        scope = Scope.from_flags(volume="book_of_mormon")
        assert scope.volume == "book_of_mormon"

    def test_book_only_in_bom_succeeds(self) -> None:
        """Book-only scope for BOM book passes."""
        scope = Scope.from_flags(book="Alma")
        assert scope.book == "Alma"

    def test_range_only_no_cross_validation(self) -> None:
        """Range-only scope has no volume/book to contradict."""
        scope = Scope.from_flags(range_str="Alma 32:21; D&C 76:1")
        assert scope.range_refs is not None
        assert len(scope.range_refs) == 2
