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

        return cls(
            volume=canonical_volume,
            book=canonical_book,
            range_refs=canonical_range,
        )
