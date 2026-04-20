"""Post-retrieval scope filter per CR-011 F3."""

from __future__ import annotations

from typing import Protocol, Sequence, TypeVar, Union

from scripvec_reference.reference import Reference, Range

from .scope import BOOK_TO_VOLUME, Scope


class VerseHit(Protocol):
    """Protocol for verse-like objects that can be scope-filtered."""

    @property
    def book(self) -> str: ...

    @property
    def chapter(self) -> int: ...

    @property
    def verse(self) -> int: ...


T = TypeVar("T", bound=VerseHit)


def _verse_in_reference(hit: VerseHit, ref: Reference) -> bool:
    """Check if a verse matches a single reference (exact match)."""
    return (
        hit.book == ref.book
        and hit.chapter == ref.chapter
        and hit.verse == ref.verse
    )


def _verse_in_range(hit: VerseHit, range_: Range) -> bool:
    """Check if a verse falls within a range (inclusive).

    Range is a tuple of (start_ref, end_ref). A verse is in range if:
    - Same book as the range
    - Chapter >= start and <= end (or within if different chapters)
    - Verse within the chapter bounds
    """
    start, end = range_

    if hit.book != start.book or hit.book != end.book:
        return False

    if start.chapter == end.chapter:
        return (
            hit.chapter == start.chapter
            and hit.verse >= start.verse
            and hit.verse <= end.verse
        )

    if hit.chapter < start.chapter or hit.chapter > end.chapter:
        return False

    if hit.chapter == start.chapter:
        return hit.verse >= start.verse

    if hit.chapter == end.chapter:
        return hit.verse <= end.verse

    return True


def _verse_matches_range_refs(
    hit: VerseHit, range_refs: tuple[Union[Reference, Range], ...]
) -> bool:
    """Check if a verse matches any of the reference specs."""
    for ref_or_range in range_refs:
        if isinstance(ref_or_range, tuple):
            if _verse_in_range(hit, ref_or_range):
                return True
        else:
            if _verse_in_reference(hit, ref_or_range):
                return True
    return False


def filter_by_scope(hits: Sequence[T], scope: Scope) -> list[T]:
    """Filter hits to only those within the specified scope.

    Args:
        hits: Sequence of verse-like objects with book, chapter, verse attributes.
        scope: Canonical Scope object with optional volume, book, and range_refs.

    Returns:
        List of hits within scope, preserving original order.
    """
    if scope.volume is None and scope.book is None and scope.range_refs is None:
        return list(hits)

    result: list[T] = []

    for hit in hits:
        if scope.volume is not None:
            hit_volume = BOOK_TO_VOLUME.get(hit.book)
            if hit_volume != scope.volume:
                continue

        if scope.book is not None:
            if hit.book != scope.book:
                continue

        if scope.range_refs is not None:
            if not _verse_matches_range_refs(hit, scope.range_refs):
                continue

        result.append(hit)

    return result
