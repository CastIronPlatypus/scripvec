"""Cross-reference retrieval per CR-015."""

from __future__ import annotations

from dataclasses import dataclass

from .store import StoreConn, get_verse


@dataclass(frozen=True)
class CrossRefEntry:
    """Raw cross-reference entry from the corpus."""

    target_verse_id: str
    tag: str


def get_cross_references(store: StoreConn, verse_id: str, n: int) -> list[CrossRefEntry]:
    """Get up to N cross-references for a verse.

    Args:
        store: Open store connection.
        verse_id: Source verse identifier.
        n: Maximum number of cross-references to return.

    Returns:
        List of CrossRefEntry in footnote order, capped at n.
        Empty list if verse has no cross-references or table doesn't exist.
    """
    if n <= 0:
        return []

    try:
        cursor = store.conn.execute(
            """
            SELECT target_verse_id, tag
            FROM cross_references
            WHERE source_verse_id = ?
            ORDER BY footnote_order
            LIMIT ?
            """,
            (verse_id, n),
        )
        return [CrossRefEntry(target_verse_id=row[0], tag=row[1]) for row in cursor.fetchall()]
    except Exception:
        return []


def has_cross_ref_table(store: StoreConn) -> bool:
    """Check if the cross_references table exists in the store."""
    cursor = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cross_references'"
    )
    return cursor.fetchone() is not None
