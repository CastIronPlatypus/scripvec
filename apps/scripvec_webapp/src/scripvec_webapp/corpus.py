"""On-demand chapter loader from data/raw/bcbooks JSON files.

Per CR-010, chapter context display is a separate axis from the CLI's `--window`
option: it is an on-demand lookup keyed by canonical reference. The webapp reads
the canonical bcbooks JSON directly rather than going through the index — this
keeps chapter lookups working even before an index has been built.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Verse:
    """A single verse in a chapter."""

    reference: str
    verse: int
    text: str


@dataclass(frozen=True)
class Chapter:
    """A loaded chapter, in canonical verse order."""

    book: str
    chapter: int
    verses: tuple[Verse, ...]
    breadcrumb: str


class ChapterNotFoundError(KeyError):
    """Raised when a requested chapter does not exist in the corpus."""


def _data_root() -> Path:
    """Locate the repo's `data/raw/bcbooks` directory.

    Honors `SCRIPVEC_DATA_DIR` for test/deploy overrides; otherwise walks up from
    this file looking for the workspace's `data/raw/bcbooks`.
    """
    override = os.environ.get("SCRIPVEC_DATA_DIR")
    if override:
        return Path(override)

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "raw" / "bcbooks"
        if candidate.is_dir():
            return parent / "data"

    return Path.cwd() / "data"


@lru_cache(maxsize=1)
def _load_book_of_mormon() -> dict[str, dict[int, Chapter]]:
    """Return {book_name: {chapter_num: Chapter}} for the Book of Mormon."""
    path = _data_root() / "raw" / "bcbooks" / "book-of-mormon.json"
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    out: dict[str, dict[int, Chapter]] = {}
    for book in data.get("books", []):
        book_name = book.get("book")
        if not book_name:
            continue
        chapters: dict[int, Chapter] = {}
        for chapter in book.get("chapters", []):
            chapter_num = int(chapter["chapter"])
            verses = tuple(
                Verse(
                    reference=v.get(
                        "reference", f"{book_name} {chapter_num}:{v['verse']}"
                    ),
                    verse=int(v["verse"]),
                    text=v.get("text", ""),
                )
                for v in chapter.get("verses", [])
            )
            chapters[chapter_num] = Chapter(
                book=book_name,
                chapter=chapter_num,
                verses=verses,
                breadcrumb=f"{book_name} › Chapter {chapter_num}",  # noqa: RUF001
            )
        out[book_name] = chapters
    return out


@lru_cache(maxsize=1)
def _load_doctrine_and_covenants() -> dict[int, Chapter]:
    """Return {section_num: Chapter} for the Doctrine & Covenants."""
    path = _data_root() / "raw" / "bcbooks" / "doctrine-and-covenants.json"
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    out: dict[int, Chapter] = {}
    for section in data.get("sections", []):
        section_num = int(section["section"])
        verses = tuple(
            Verse(
                reference=v.get("reference", f"D&C {section_num}:{v['verse']}"),
                verse=int(v["verse"]),
                text=v.get("text", ""),
            )
            for v in section.get("verses", [])
        )
        out[section_num] = Chapter(
            book="D&C",
            chapter=section_num,
            verses=verses,
            breadcrumb=f"D&C › Section {section_num}",  # noqa: RUF001
        )
    return out


def clear_cache() -> None:
    """Reset the in-memory chapter cache (used by tests)."""
    _load_book_of_mormon.cache_clear()
    _load_doctrine_and_covenants.cache_clear()


def get_chapter(book: str, chapter: int) -> Chapter:
    """Load a single chapter by book name + chapter number.

    Args:
        book: Canonical book name (e.g., "1 Nephi", "Alma", "D&C").
        chapter: 1-indexed chapter or D&C section number.

    Raises:
        ChapterNotFoundError: If the (book, chapter) pair is not in the corpus.
    """
    if book == "D&C":
        dnc = _load_doctrine_and_covenants()
        if chapter not in dnc:
            raise ChapterNotFoundError(f"D&C section {chapter} not found")
        return dnc[chapter]

    bom = _load_book_of_mormon()
    if book not in bom:
        raise ChapterNotFoundError(f"Unknown book: {book!r}")
    if chapter not in bom[book]:
        raise ChapterNotFoundError(f"{book} chapter {chapter} not found")
    return bom[book][chapter]


def list_books() -> dict[str, list[int]]:
    """Return {book: sorted list of chapter numbers} for the whole corpus.

    Useful for the front-end filter UI (scene 02 book list).
    """
    out: dict[str, list[int]] = {}
    for book, chapters in _load_book_of_mormon().items():
        out[book] = sorted(chapters.keys())
    dnc = _load_doctrine_and_covenants()
    if dnc:
        out["D&C"] = sorted(dnc.keys())
    return out
