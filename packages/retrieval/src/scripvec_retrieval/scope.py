"""Scope dataclass and canonical normalization per CR-011."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from scripvec_reference.books import canonicalize_book
from scripvec_reference.reference import Reference, Range, parse_list


CANONICAL_VOLUMES: tuple[str, ...] = (
    "book_of_mormon",
    "doctrine_and_covenants",
)

_VOLUME_TABLE: dict[str, str] = {v: v for v in CANONICAL_VOLUMES}

BOOK_TO_VOLUME: dict[str, str] = {
    "1 Nephi": "book_of_mormon",
    "2 Nephi": "book_of_mormon",
    "Jacob": "book_of_mormon",
    "Enos": "book_of_mormon",
    "Jarom": "book_of_mormon",
    "Omni": "book_of_mormon",
    "Words of Mormon": "book_of_mormon",
    "Mosiah": "book_of_mormon",
    "Alma": "book_of_mormon",
    "Helaman": "book_of_mormon",
    "3 Nephi": "book_of_mormon",
    "4 Nephi": "book_of_mormon",
    "Mormon": "book_of_mormon",
    "Ether": "book_of_mormon",
    "Moroni": "book_of_mormon",
    "D&C": "doctrine_and_covenants",
}

VOLUMES_WITH_BOOKS: frozenset[str] = frozenset({"book_of_mormon"})


class UnknownVolumeError(ValueError):
    """Raised when volume name is not in canonical catalog."""

    def __init__(self, volume: str) -> None:
        self.volume = volume
        super().__init__(f"Unknown volume: {volume!r}")


class UnknownBookError(ValueError):
    """Raised when book name is not in canonical catalog."""

    def __init__(self, book: str) -> None:
        self.book = book
        super().__init__(f"Unknown book: {book!r}")


class MalformedRangeError(ValueError):
    """Raised when range string does not parse per ADR-010/011/012."""

    def __init__(self, range_str: str, detail: str) -> None:
        self.range_str = range_str
        self.detail = detail
        super().__init__(f"Malformed range {range_str!r}: {detail}")


class VolumeHasNoBooksError(ValueError):
    """Raised when --book is used against a volume that has sections, not books."""

    def __init__(self, volume: str) -> None:
        self.volume = volume
        super().__init__("D&C has sections, not books; use --range instead")


class BookNotInVolumeError(ValueError):
    """Raised when book does not belong to the specified volume."""

    def __init__(self, book: str, volume: str) -> None:
        self.book = book
        self.volume = volume
        super().__init__(f"Book {book!r} does not belong to volume {volume!r}")


class RangeOutsideScopeError(ValueError):
    """Raised when range references books outside the specified scope."""

    def __init__(self, reference_book: str, scope_filter: str, scope_value: str) -> None:
        self.reference_book = reference_book
        self.scope_filter = scope_filter
        self.scope_value = scope_value
        super().__init__(
            f"Range reference {reference_book!r} is outside {scope_filter} {scope_value!r}"
        )


def canonicalize_volume(raw: str) -> str:
    """Map volume name to canonical form. Raises UnknownVolumeError on unknown input."""
    canonical = _VOLUME_TABLE.get(raw)
    if canonical is None:
        raise UnknownVolumeError(raw)
    return canonical


def canonicalize_book_for_scope(raw: str) -> str:
    """Map book name to canonical form. Raises UnknownBookError on unknown input."""
    try:
        return canonicalize_book(raw)
    except ValueError:
        raise UnknownBookError(raw) from None


def canonicalize_range(raw: str) -> list[Union[Reference, Range]]:
    """Parse range/list per ADR-010/011/012. Raises MalformedRangeError on failure."""
    try:
        return parse_list(raw)
    except ValueError as e:
        raise MalformedRangeError(raw, str(e)) from None


@dataclass(frozen=True)
class Scope:
    """Immutable scope filter for scripture queries.

    All fields are canonicalized at construction time.
    """

    volume: str | None
    book: str | None
    range_refs: tuple[Union[Reference, Range], ...] | None

    @classmethod
    def from_flags(
        cls,
        *,
        volume: str | None = None,
        book: str | None = None,
        range_str: str | None = None,
    ) -> Scope:
        """Create Scope from CLI flags, canonicalizing each field.

        Raises:
            UnknownVolumeError: if volume is not recognized
            UnknownBookError: if book is not recognized
            MalformedRangeError: if range does not parse per ADR-010/011/012
        """
        canonical_volume: str | None = None
        canonical_book: str | None = None
        canonical_range: tuple[Union[Reference, Range], ...] | None = None

        if volume is not None:
            canonical_volume = canonicalize_volume(volume)

        if book is not None:
            canonical_book = canonicalize_book_for_scope(book)

        if range_str is not None:
            parsed = canonicalize_range(range_str)
            canonical_range = tuple(parsed)

        scope = cls(
            volume=canonical_volume,
            book=canonical_book,
            range_refs=canonical_range,
        )
        scope.validate()
        return scope

    def validate(self) -> None:
        """Validate scope consistency per ADR-001.

        Raises:
            VolumeHasNoBooksError: if book is specified against D&C
            BookNotInVolumeError: if book doesn't belong to specified volume
            RangeOutsideScopeError: if range references are outside scope
        """
        if self.book is not None:
            book_volume = BOOK_TO_VOLUME.get(self.book)
            if book_volume is not None and book_volume not in VOLUMES_WITH_BOOKS:
                raise VolumeHasNoBooksError(book_volume)

            if self.volume is not None and book_volume != self.volume:
                raise BookNotInVolumeError(self.book, self.volume)

        if self.range_refs is not None:
            for ref_or_range in self.range_refs:
                if isinstance(ref_or_range, tuple):
                    start, end = ref_or_range
                    self._validate_ref_in_scope(start)
                    self._validate_ref_in_scope(end)
                else:
                    self._validate_ref_in_scope(ref_or_range)

    def _validate_ref_in_scope(self, ref: Reference) -> None:
        """Validate a single reference is within volume/book scope."""
        ref_volume = BOOK_TO_VOLUME.get(ref.book)

        if self.volume is not None and ref_volume != self.volume:
            raise RangeOutsideScopeError(ref.book, "--volume", self.volume)

        if self.book is not None and ref.book != self.book:
            raise RangeOutsideScopeError(ref.book, "--book", self.book)
