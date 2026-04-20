"""Verse-neighbor lookup for retrieval windows per CR-013."""

from __future__ import annotations

from dataclasses import dataclass

from .store import StoreConn


@dataclass(frozen=True)
class WindowVerse:
    """A verse in the window context."""

    ref: str
    text: str


@dataclass(frozen=True)
class Window:
    """Before and after context around a hit verse."""

    before: tuple[WindowVerse, ...]
    after: tuple[WindowVerse, ...]


def get_window(store: StoreConn, verse_id: str, n: int) -> Window:
    """Get up to N verses before and after a given verse.

    Bounded by chapter/section — does not cross chapter boundaries.

    Args:
        store: Open store connection.
        verse_id: Unique verse identifier.
        n: Number of verses to fetch on each side.

    Returns:
        Window with before and after lists in scripture order.

    Raises:
        KeyError: If verse_id not found.
    """
    if n <= 0:
        return Window(before=(), after=())

    conn = store.conn

    row = conn.execute(
        """
        SELECT book, chapter, verse
        FROM verses
        WHERE verse_id = ?
        """,
        (verse_id,),
    ).fetchone()

    if row is None:
        raise KeyError(f"Verse not found: {verse_id}")

    book = row["book"]
    chapter = row["chapter"]
    current_verse = row["verse"]

    before_rows = conn.execute(
        """
        SELECT ref_canonical, text
        FROM verses
        WHERE book = ? AND chapter = ? AND verse < ?
        ORDER BY verse DESC
        LIMIT ?
        """,
        (book, chapter, current_verse, n),
    ).fetchall()

    before = tuple(
        WindowVerse(ref=r["ref_canonical"], text=r["text"])
        for r in reversed(before_rows)
    )

    after_rows = conn.execute(
        """
        SELECT ref_canonical, text
        FROM verses
        WHERE book = ? AND chapter = ? AND verse > ?
        ORDER BY verse ASC
        LIMIT ?
        """,
        (book, chapter, current_verse, n),
    ).fetchall()

    after = tuple(
        WindowVerse(ref=r["ref_canonical"], text=r["text"])
        for r in after_rows
    )

    return Window(before=before, after=after)
