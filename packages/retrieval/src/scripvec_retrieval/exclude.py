"""Exclusion filtering for CR-014."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from .embed import embed
from .store import dense_topk, open_store

T = TypeVar("T")


def compute_exclusion_set(text: str, m: int, index_dir: Path) -> list[str]:
    """Compute the exclusion set by embedding text and finding top-m similar verses.

    Args:
        text: The exclusion query text to embed.
        m: Number of top similar verses to include in exclusion set.
        index_dir: Path to the index directory containing corpus.sqlite.

    Returns:
        List of verse_ids for the top-m most similar verses.

    Raises:
        RuntimeError: On embedding error, >8K token input, or index access error.
        FileNotFoundError: If index directory doesn't exist.
    """
    query_vec = embed(text)

    store = open_store(index_dir / "corpus.sqlite")
    try:
        hits = dense_topk(store, query_vec, k=m)
        return [hit.verse_id for hit in hits]
    finally:
        store.conn.close()


def filter_by_exclusion(
    hits: list[tuple[str, T]],
    exclusion_set: set[str],
) -> list[tuple[str, T]]:
    """Filter hits by excluding verse_ids in the exclusion set.

    Args:
        hits: List of (verse_id, score) tuples in ranked order.
        exclusion_set: Set of verse_ids to exclude.

    Returns:
        Filtered list preserving the original ranking order.
    """
    return [(verse_id, score) for verse_id, score in hits if verse_id not in exclusion_set]
