"""Unit tests for window.py — verse-neighbor lookup."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

import pytest
import sqlite_vec

from .store import StoreConn
from .window import Window, WindowVerse, get_window


@pytest.fixture
def test_store(tmp_path: Path) -> Generator[StoreConn, None, None]:
    """Create an in-memory test store with sample verses."""
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    conn.execute("""
        CREATE TABLE verses (
            rowid INTEGER PRIMARY KEY,
            verse_id TEXT UNIQUE NOT NULL,
            ref_canonical TEXT NOT NULL,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE store_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO store_meta (key, value) VALUES ('dim', '1024')")

    test_verses = [
        ("alma-32-1", "Alma 32:1", "Alma", 32, 1, "And it came to pass..."),
        ("alma-32-2", "Alma 32:2", "Alma", 32, 2, "And it came to pass that..."),
        ("alma-32-3", "Alma 32:3", "Alma", 32, 3, "And they came unto..."),
        ("alma-32-4", "Alma 32:4", "Alma", 32, 4, "And now..."),
        ("alma-32-5", "Alma 32:5", "Alma", 32, 5, "Therefore they were..."),
        ("alma-33-1", "Alma 33:1", "Alma", 33, 1, "Now after Alma..."),
        ("alma-33-2", "Alma 33:2", "Alma", 33, 2, "And Alma said..."),
        ("1-nephi-1-1", "1 Nephi 1:1", "1 Nephi", 1, 1, "I, Nephi..."),
        ("1-nephi-1-2", "1 Nephi 1:2", "1 Nephi", 1, 2, "Yea, I make..."),
    ]

    for verse_id, ref, book, chapter, verse, text in test_verses:
        conn.execute(
            """
            INSERT INTO verses (verse_id, ref_canonical, book, chapter, verse, text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (verse_id, ref, book, chapter, verse, text),
        )
    conn.commit()

    store = StoreConn(conn=conn, dim=1024)
    yield store
    conn.close()


class TestGetWindow:
    """Tests for get_window function."""

    def test_verse_at_position_1_before_empty(self, test_store: StoreConn) -> None:
        """Verse at position 1 of chapter → before is empty."""
        window = get_window(test_store, "alma-32-1", n=2)
        assert window.before == ()
        assert len(window.after) == 2
        assert window.after[0].ref == "Alma 32:2"
        assert window.after[1].ref == "Alma 32:3"

    def test_verse_at_last_position_after_empty(self, test_store: StoreConn) -> None:
        """Verse at last position of chapter → after is empty."""
        window = get_window(test_store, "alma-32-5", n=2)
        assert len(window.before) == 2
        assert window.before[0].ref == "Alma 32:3"
        assert window.before[1].ref == "Alma 32:4"
        assert window.after == ()

    def test_n_larger_than_chapter_clips_cleanly(self, test_store: StoreConn) -> None:
        """N larger than chapter length → clip cleanly, no error."""
        window = get_window(test_store, "alma-32-3", n=100)
        assert len(window.before) == 2
        assert len(window.after) == 2
        assert window.before[0].ref == "Alma 32:1"
        assert window.before[1].ref == "Alma 32:2"
        assert window.after[0].ref == "Alma 32:4"
        assert window.after[1].ref == "Alma 32:5"

    def test_n_zero_both_lists_empty(self, test_store: StoreConn) -> None:
        """N == 0 → both lists empty."""
        window = get_window(test_store, "alma-32-3", n=0)
        assert window.before == ()
        assert window.after == ()

    def test_negative_n_treated_as_zero(self, test_store: StoreConn) -> None:
        """Negative N treated as zero — both lists empty."""
        window = get_window(test_store, "alma-32-3", n=-1)
        assert window.before == ()
        assert window.after == ()

    def test_middle_verse_both_directions(self, test_store: StoreConn) -> None:
        """Middle verse returns entries on both sides."""
        window = get_window(test_store, "alma-32-3", n=2)
        assert len(window.before) == 2
        assert len(window.after) == 2
        assert window.before[0].ref == "Alma 32:1"
        assert window.before[1].ref == "Alma 32:2"
        assert window.after[0].ref == "Alma 32:4"
        assert window.after[1].ref == "Alma 32:5"

    def test_scripture_order_preserved(self, test_store: StoreConn) -> None:
        """Before and after are in scripture order (ascending verse numbers)."""
        window = get_window(test_store, "alma-32-4", n=3)
        refs_before = [v.ref for v in window.before]
        refs_after = [v.ref for v in window.after]
        assert refs_before == ["Alma 32:1", "Alma 32:2", "Alma 32:3"]
        assert refs_after == ["Alma 32:5"]

    def test_does_not_cross_chapter_boundary(self, test_store: StoreConn) -> None:
        """Window does not cross chapter boundaries."""
        window = get_window(test_store, "alma-33-1", n=10)
        assert window.before == ()
        assert len(window.after) == 1
        assert window.after[0].ref == "Alma 33:2"

    def test_does_not_cross_book_boundary(self, test_store: StoreConn) -> None:
        """Window does not cross book boundaries."""
        window = get_window(test_store, "1-nephi-1-1", n=10)
        assert window.before == ()
        assert len(window.after) == 1
        assert window.after[0].ref == "1 Nephi 1:2"

    def test_neighbors_independent_windows(self, test_store: StoreConn) -> None:
        """Two neighboring hits get independent window payloads (no stitching)."""
        window1 = get_window(test_store, "alma-32-2", n=1)
        window2 = get_window(test_store, "alma-32-3", n=1)

        assert len(window1.before) == 1
        assert window1.before[0].ref == "Alma 32:1"
        assert len(window1.after) == 1
        assert window1.after[0].ref == "Alma 32:3"

        assert len(window2.before) == 1
        assert window2.before[0].ref == "Alma 32:2"
        assert len(window2.after) == 1
        assert window2.after[0].ref == "Alma 32:4"

    def test_verse_not_found_raises_keyerror(self, test_store: StoreConn) -> None:
        """Non-existent verse_id raises KeyError."""
        with pytest.raises(KeyError, match="Verse not found"):
            get_window(test_store, "nonexistent-verse", n=2)

    def test_window_verse_contains_text(self, test_store: StoreConn) -> None:
        """WindowVerse objects contain verse text."""
        window = get_window(test_store, "alma-32-3", n=1)
        assert window.before[0].text == "And it came to pass that..."
        assert window.after[0].text == "And now..."
