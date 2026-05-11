"""Tests for the on-demand chapter loader."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from . import corpus


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    """Each test starts with a clean LRU cache."""
    corpus.clear_cache()
    yield
    corpus.clear_cache()


@pytest.fixture
def fake_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bcbooks = tmp_path / "raw" / "bcbooks"
    bcbooks.mkdir(parents=True)

    bom = {
        "books": [
            {
                "book": "1 Nephi",
                "chapters": [
                    {
                        "chapter": 1,
                        "verses": [
                            {"verse": 1, "reference": "1 Nephi 1:1", "text": "I, Nephi…"},
                            {"verse": 2, "reference": "1 Nephi 1:2", "text": "Yea, I make…"},
                        ],
                    },
                ],
            }
        ]
    }
    (bcbooks / "book-of-mormon.json").write_text(json.dumps(bom))

    dnc = {
        "sections": [
            {
                "section": 18,
                "verses": [
                    {"verse": 10, "reference": "D&C 18:10", "text": "Remember the worth…"},
                    {"verse": 11, "reference": "D&C 18:11", "text": "And he hath risen…"},
                ],
            }
        ]
    }
    (bcbooks / "doctrine-and-covenants.json").write_text(json.dumps(dnc))

    monkeypatch.setenv("SCRIPVEC_DATA_DIR", str(tmp_path))
    return tmp_path


def test_get_chapter_book_of_mormon(fake_corpus: Path) -> None:
    ch = corpus.get_chapter("1 Nephi", 1)
    assert ch.book == "1 Nephi"
    assert ch.chapter == 1
    assert len(ch.verses) == 2
    assert ch.verses[0].verse == 1
    assert ch.verses[0].text.startswith("I, Nephi")
    assert ch.breadcrumb == "1 Nephi › Chapter 1"  # noqa: RUF001


def test_get_chapter_dnc(fake_corpus: Path) -> None:
    ch = corpus.get_chapter("D&C", 18)
    assert ch.book == "D&C"
    assert ch.chapter == 18
    assert len(ch.verses) == 2
    assert ch.verses[0].verse == 10
    assert ch.breadcrumb == "D&C › Section 18"  # noqa: RUF001


def test_unknown_book_raises(fake_corpus: Path) -> None:
    with pytest.raises(corpus.ChapterNotFoundError):
        corpus.get_chapter("Definitely Not A Book", 1)


def test_unknown_chapter_raises(fake_corpus: Path) -> None:
    with pytest.raises(corpus.ChapterNotFoundError):
        corpus.get_chapter("1 Nephi", 999)


def test_unknown_dnc_section_raises(fake_corpus: Path) -> None:
    with pytest.raises(corpus.ChapterNotFoundError):
        corpus.get_chapter("D&C", 999)


def test_list_books_returns_chapters(fake_corpus: Path) -> None:
    books = corpus.list_books()
    assert "1 Nephi" in books
    assert books["1 Nephi"] == [1]
    assert "D&C" in books
    assert books["D&C"] == [18]


def test_missing_files_return_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If data files don't exist, loader returns empty dicts rather than crashing."""
    monkeypatch.setenv("SCRIPVEC_DATA_DIR", str(tmp_path))
    corpus.clear_cache()
    assert corpus.list_books() == {}
    with pytest.raises(corpus.ChapterNotFoundError):
        corpus.get_chapter("Alma", 1)
