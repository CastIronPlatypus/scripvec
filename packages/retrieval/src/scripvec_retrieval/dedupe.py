"""Proximity-based deduplication for CR-013."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ParsedVerseId:
    """Parsed components of a verse_id."""

    book: str
    chapter: int
    verse: int


def parse_verse_id(verse_id: str) -> ParsedVerseId:
    """Parse a verse_id slug into its components.

    Examples:
        "1-nephi-3-7" -> ParsedVerseId(book="1-nephi", chapter=3, verse=7)
        "dandc-88-118" -> ParsedVerseId(book="dandc", chapter=88, verse=118)
    """
    parts = verse_id.rsplit("-", 2)
    if len(parts) < 3:
        raise ValueError(f"Cannot parse verse_id: {verse_id!r}")

    book = parts[0]
    try:
        chapter = int(parts[1])
        verse = int(parts[2])
    except ValueError as e:
        raise ValueError(f"Cannot parse verse_id: {verse_id!r}") from e

    return ParsedVerseId(book=book, chapter=chapter, verse=verse)


def _is_within_proximity(
    kept: ParsedVerseId,
    candidate: ParsedVerseId,
    m: int,
) -> bool:
    """Check if candidate is within M verses of kept.

    Returns False (not proximate) if books or chapters differ.
    """
    if kept.book != candidate.book:
        return False
    if kept.chapter != candidate.chapter:
        return False
    return abs(kept.verse - candidate.verse) <= m


def proximity_dedupe(
    hits: list[tuple[str, T]],
    m: int,
    k: int,
) -> tuple[list[tuple[str, T]], int]:
    """Deduplicate hits by proximity within same chapter/book.

    Args:
        hits: List of (verse_id, score) tuples, pre-sorted by score descending.
        m: Proximity cutoff in verses. Hits within M verses of an already-kept
           hit (and in the same chapter/book) are dropped.
        k: Target number of results to keep.

    Returns:
        Tuple of (kept_hits, dropped_count). kept_hits is truncated to k.
    """
    kept: list[tuple[str, T]] = []
    kept_parsed: list[ParsedVerseId] = []
    dropped_count = 0

    for verse_id, score in hits:
        parsed = parse_verse_id(verse_id)

        is_proximate_to_any_kept = any(
            _is_within_proximity(kp, parsed, m) for kp in kept_parsed
        )

        if is_proximate_to_any_kept:
            dropped_count += 1
        else:
            if len(kept) < k:
                kept.append((verse_id, score))
                kept_parsed.append(parsed)

    return kept, dropped_count
