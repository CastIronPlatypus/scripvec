"""FastAPI route handlers for the scripvec webapp."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from .cli import CliInvocationError, CliNotFoundError, CliRunner
from .corpus import ChapterNotFoundError, get_chapter, list_books


def _runner_dep() -> CliRunner:
    """FastAPI dependency providing a CliRunner per request."""
    try:
        return CliRunner.discover()
    except CliNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


RunnerDep = Annotated[CliRunner, Depends(_runner_dep)]


def _map_cli_error(exc: CliInvocationError) -> HTTPException:
    """Translate a CLI non-zero exit into an appropriate HTTP error.

    Per the CLI README, exit code 1 = user error, 2 = index not found,
    3 = upstream/embedding error.
    """
    if exc.exit_code == 2:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if exc.exit_code == 1:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.payload or str(exc),
        )
    if exc.exit_code == 3:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.payload or str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=exc.payload or str(exc),
    )


class QueryRequest(BaseModel):
    """Request body for `POST /api/query`."""

    text: str = Field(..., min_length=1, description="Free-text query.")
    k: int = Field(10, ge=1, le=100)
    mode: Literal["bm25", "dense", "hybrid"] = "hybrid"
    index: str = Field("latest", description="Index hash or 'latest'.")
    show_scores: bool = True


class FeedbackRequest(BaseModel):
    """Request body for `POST /api/feedback`."""

    query_id: str
    verse_id: str
    grade: Literal[0, 1, 2]
    note: str | None = None


router = APIRouter(prefix="/api")


@router.get("/version")
async def get_version(runner: RunnerDep) -> dict[str, Any]:
    """Proxy `scripvec --version`."""
    try:
        return await runner.version()
    except CliInvocationError as exc:
        raise _map_cli_error(exc) from exc


@router.get("/indexes")
async def get_indexes(runner: RunnerDep) -> list[dict[str, Any]]:
    """Proxy `scripvec index list`."""
    try:
        return await runner.index_list()
    except CliInvocationError as exc:
        raise _map_cli_error(exc) from exc


@router.post("/query")
async def post_query(req: QueryRequest, runner: RunnerDep) -> dict[str, Any]:
    """Proxy `scripvec query`."""
    try:
        return await runner.query(
            req.text,
            k=req.k,
            mode=req.mode,
            index=req.index,
            show_scores=req.show_scores,
        )
    except CliInvocationError as exc:
        raise _map_cli_error(exc) from exc


@router.post("/feedback")
async def post_feedback(req: FeedbackRequest, runner: RunnerDep) -> dict[str, Any]:
    """Proxy `scripvec feedback feedback`."""
    try:
        return await runner.feedback(
            query_id=req.query_id,
            verse_id=req.verse_id,
            grade=req.grade,
            note=req.note,
        )
    except CliInvocationError as exc:
        raise _map_cli_error(exc) from exc


@router.get("/chapter")
def get_chapter_route(
    book: str = Query(..., description="Canonical book name, e.g. 'Alma' or 'D&C'."),
    chapter: int = Query(..., ge=1, description="Chapter or D&C section number."),
    focus_verse: int | None = Query(
        None, ge=1, description="Verse to highlight in the rendered chapter."
    ),
) -> dict[str, Any]:
    """Return a chapter for the details view (on-demand, per CR-010)."""
    try:
        ch = get_chapter(book, chapter)
    except ChapterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return {
        "book": ch.book,
        "chapter": ch.chapter,
        "breadcrumb": ch.breadcrumb,
        "focus_verse": focus_verse,
        "verses": [
            {"verse": v.verse, "reference": v.reference, "text": v.text}
            for v in ch.verses
        ],
    }


@router.get("/books")
def get_books_route() -> dict[str, list[int]]:
    """Return {book: [chapter_numbers]} for filter-rail population."""
    return list_books()
