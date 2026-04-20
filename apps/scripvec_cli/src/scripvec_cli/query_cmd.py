"""CLI command for scripvec query."""

from __future__ import annotations

import json
from enum import Enum
from typing import Annotated

import typer

from scripvec_retrieval.config import load_window_config
from scripvec_retrieval.embed import MAX_TOKENS, estimate_token_count
from scripvec_retrieval.manifest import read_manifest
from scripvec_retrieval.paths import index_path, resolve_latest
from scripvec_retrieval.query import QueryResult, query
from scripvec_retrieval.scope import (
    BOOK_TO_VOLUME,
    CANONICAL_VOLUMES,
    BookNotInVolumeError,
    MalformedRangeError,
    RangeOutsideScopeError,
    Scope,
    UnknownBookError,
    UnknownVolumeError,
    VolumeHasNoBooksError,
)

from . import query_log
from .errors import ExitCode, emit_error


class Mode(str, Enum):
    bm25 = "bm25"
    dense = "dense"
    hybrid = "hybrid"


class Format(str, Enum):
    json = "json"
    text = "text"


_SESSION_ID = query_log.new_session_id()


def _run_query(
    text: str,
    k: int,
    mode: str,
    index: str,
    floor: float | None = None,
    window: int = 0,
    dedupe: bool = True,
    exclude: str | None = None,
    scope: Scope | None = None,
    hybrid_weight: tuple[float, float] | None = None,
    cross_ref_expand: int = 0,
) -> QueryResult:
    """Execute query and return result."""
    return query(text, k=k, mode=mode, index=index, floor=floor, window=window, dedupe=dedupe, exclude=exclude, scope=scope, hybrid_weight=hybrid_weight, cross_ref_expand=cross_ref_expand)


def _to_log_record(
    result: QueryResult,
    query_id: str,
) -> query_log.QueryLogRecord:
    """Convert QueryResult to log record."""
    log_rows = tuple(
        query_log.ResultLogRow(
            verse_id=r.verse_id,
            bm25_rank=r.scores.get("bm25_rank"),
            dense_rank=r.scores.get("dense_rank"),
            rrf_score=r.score,
        )
        for r in result.results
    )

    return query_log.create_record(
        session_id=_SESSION_ID,
        query_id=query_id,
        index_hash=result.index,
        mode=result.mode,
        query=result.query,
        k=result.k,
        results=log_rows,
        latency_ms=result.latency_ms.get("total", 0.0),
    )


def _format_text(result: QueryResult, show_scores: bool) -> str:
    """Format result as human-readable text."""
    lines = [f"Query: {result.query}", f"Mode: {result.mode}, K: {result.k}, Index: {result.index}", ""]

    for r in result.results:
        forced_marker = " [FORCED]" if r.forced else ""
        score_str = f" (score: {r.score:.4f})" if show_scores else ""
        lines.append(f"{r.rank}. {r.ref}{forced_marker}{score_str}")
        lines.append(f"   {r.text[:100]}..." if len(r.text) > 100 else f"   {r.text}")
        lines.append("")

    return "\n".join(lines)


def _format_scope(scope: Scope | None) -> dict[str, str | None]:
    """Format Scope as JSON-serializable dict with canonical values."""
    if scope is None:
        return {"volume": None, "book": None, "range": None}

    range_str: str | None = None
    if scope.range_refs is not None:
        from scripvec_reference.reference import canonical
        parts = []
        for ref_or_range in scope.range_refs:
            if isinstance(ref_or_range, tuple):
                start, end = ref_or_range
                parts.append(f"{canonical(start.book, start.chapter, start.verse)}-{canonical(end.book, end.chapter, end.verse)}")
            else:
                parts.append(canonical(ref_or_range.book, ref_or_range.chapter, ref_or_range.verse))
        range_str = ", ".join(parts)

    return {
        "volume": scope.volume,
        "book": scope.book,
        "range": range_str,
    }


def _format_json(result: QueryResult, show_scores: bool, scope: Scope | None = None) -> str:
    """Format result as JSON."""
    floor_data = None
    if result.floor is not None:
        floor_data = {
            "value": result.floor.value,
            "interpretation": result.floor.interpretation,
            "effective_threshold": result.floor.effective_threshold,
        }

    dedupe_data = None
    if result.dedupe is not None:
        dedupe_data = {
            "enabled": result.dedupe.enabled,
            "proximity_verses": result.dedupe.proximity_verses,
            "dropped": result.dedupe.dropped,
        }

    exclude_data = None
    if result.exclude is not None:
        exclude_data = {
            "text": result.exclude.text,
            "set_size": result.exclude.set_size,
            "excluded_verse_ids": list(result.exclude.excluded_verse_ids),
        }

    def _format_result(r: "ResultRow") -> dict:
        res: dict = {
            "rank": r.rank,
            "verse_id": r.verse_id,
            "ref": r.ref,
            "text": r.text,
            "forced": r.forced,
        }
        if show_scores:
            res["score"] = r.score
            res["scores"] = r.scores
        if r.window is not None:
            res["window"] = {
                "before": [{"ref": v.ref, "text": v.text} for v in r.window.before],
                "after": [{"ref": v.ref, "text": v.text} for v in r.window.after],
            }
        if r.cross_references is not None:
            res["cross_references"] = [
                {"ref": xr.ref, "text": xr.text, "tag": xr.tag}
                for xr in r.cross_references
            ]
        return res

    hybrid_weight_data = None
    if result.hybrid_weight is not None:
        hybrid_weight_data = {
            "lexical": result.hybrid_weight.lexical,
            "dense": result.hybrid_weight.dense,
        }
        if result.hybrid_weight.from_config:
            hybrid_weight_data["from_config"] = True

    data: dict = {
        "query": result.query,
        "mode": result.mode,
        "k": result.k,
        "index": result.index,
        "scope": _format_scope(scope),
        "floor": floor_data,
        "dedupe": dedupe_data,
        "latency_ms": result.latency_ms,
        "results": [_format_result(r) for r in result.results],
    }
    if exclude_data is not None:
        data["exclude"] = exclude_data
    if hybrid_weight_data is not None:
        data["hybrid_weight"] = hybrid_weight_data
    return json.dumps(data, indent=2)


def cmd_query(
    text: Annotated[str, typer.Argument(help="Query text to search for")],
    k: Annotated[int, typer.Option("--k", "-k", help="Number of results to return")] = 10,
    mode: Annotated[Mode, typer.Option("--mode", "-m", help="Retrieval mode")] = Mode.hybrid,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format")] = Format.json,
    index: Annotated[str, typer.Option("--index", "-i", help="Index hash or 'latest'")] = "latest",
    show_scores: Annotated[bool, typer.Option("--show-scores", help="Include scores in output")] = False,
    floor: Annotated[float | None, typer.Option("--floor", help="Minimum similarity score [0.0-1.0]")] = None,
    window: Annotated[int | None, typer.Option("--window", help="Include N verses before and after each hit")] = None,
    dedupe: Annotated[bool | None, typer.Option("--dedupe", is_flag=True, flag_value=True, help="Enable proximity deduplication (default)")] = None,
    no_dedupe: Annotated[bool | None, typer.Option("--no-dedupe", is_flag=True, flag_value=True, help="Disable proximity deduplication")] = None,
    exclude: Annotated[str | None, typer.Option("--exclude", help="Text to exclude from results (vector-based)")] = None,
    hybrid_weight: Annotated[str | None, typer.Option("--hybrid-weight", help="Lexical:dense weight ratio for hybrid mode (e.g., '2:1'). Requires --mode hybrid.")] = None,
    cross_ref_expand: Annotated[int | None, typer.Option("--cross-ref-expand", help="Expand cross-references up to N levels (0 = no expansion). Requires index with cross-reference metadata; if missing, fails with 'cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled'.")] = None,
    volume: Annotated[str | None, typer.Option("--volume", help="Filter results to a specific volume (e.g., 'book_of_mormon')")] = None,
    book: Annotated[str | None, typer.Option("--book", help="Filter results to a specific book (e.g., 'Alma')")] = None,
    range_str: Annotated[str | None, typer.Option("--range", help="Filter to references (e.g., 'Alma 30-42', '2 Nephi 31:1-21')")] = None,
) -> None:
    """Search scripture verses using hybrid BM25 + dense retrieval.

    Outputs JSON by default with query results. Appends to queries.jsonl for logging.

    Exit codes:
        0 - Success
        1 - User error (bad flags, build failed)
        2 - Not found (missing index)
        3 - Upstream error (embedding endpoint)

    Example JSON output:
        {
          "query": "faith and works",
          "mode": "hybrid",
          "k": 10,
          "index": "abc123...",
          "results": [{"rank": 1, "verse_id": "...", "ref": "...", "text": "..."}]
        }
    """
    try:
        if dedupe is not None and no_dedupe is not None:
            emit_error(
                "bad_flag",
                "Cannot specify both --dedupe and --no-dedupe",
                exit_code=ExitCode.USER_ERROR,
            )

        effective_dedupe = True
        if no_dedupe:
            effective_dedupe = False


        if exclude is not None and mode == Mode.bm25:
            emit_error(
                "bad_flag",
                "--exclude cannot be used with --mode bm25: vector exclusion has no BM25 analog",
                exit_code=ExitCode.USER_ERROR,
            )

        if exclude is not None:
            if not exclude.strip():
                emit_error(
                    "bad_flag",
                    "--exclude cannot be empty or whitespace-only",
                    exit_code=ExitCode.USER_ERROR,
                )
            exclude_tokens = estimate_token_count(exclude)
            if exclude_tokens > MAX_TOKENS:
                emit_error(
                    "bad_flag",
                    f"--exclude text exceeds {MAX_TOKENS} token limit (estimated {exclude_tokens} tokens)",
                    exit_code=ExitCode.USER_ERROR,
                )

        if hybrid_weight is not None:
            if mode != Mode.hybrid:
                emit_error(
                    "bad_flag",
                    f"--hybrid-weight cannot be used with --mode {mode.value}: only valid for --mode hybrid",
                    exit_code=ExitCode.USER_ERROR,
                )
            parts = hybrid_weight.split(":")
            if len(parts) != 2:
                emit_error(
                    "bad_flag",
                    f"--hybrid-weight must be in format 'lexical:dense', got {hybrid_weight!r}",
                    exit_code=ExitCode.USER_ERROR,
                )
            try:
                lexical_w = float(parts[0])
                dense_w = float(parts[1])
            except ValueError:
                emit_error(
                    "bad_flag",
                    f"--hybrid-weight must contain numeric values, got {hybrid_weight!r}",
                    exit_code=ExitCode.USER_ERROR,
                )
            if lexical_w < 0 or dense_w < 0:
                emit_error(
                    "bad_flag",
                    f"--hybrid-weight values must be non-negative, got {hybrid_weight!r}",
                    exit_code=ExitCode.USER_ERROR,
                )
            if lexical_w == 0 and dense_w == 0:
                emit_error(
                    "bad_flag",
                    f"--hybrid-weight cannot be 0:0 (both weights zero), got {hybrid_weight!r}",
                    exit_code=ExitCode.USER_ERROR,
                )
            effective_hybrid_weight: tuple[float, float] | None = (lexical_w, dense_w)
        else:
            effective_hybrid_weight = None

        if cross_ref_expand is not None and cross_ref_expand < 0:
            emit_error(
                "bad_flag",
                f"--cross-ref-expand must be >= 0, got {cross_ref_expand}",
                exit_code=ExitCode.USER_ERROR,
            )

        if cross_ref_expand is not None and cross_ref_expand > 0:
            idx_hash = resolve_latest() if index == "latest" else index
            idx_dir = index_path(idx_hash)
            if not idx_dir.is_dir():
                emit_error(
                    "index_not_found",
                    f"Index directory not found: {idx_dir}",
                    exit_code=ExitCode.NOT_FOUND,
                )
            manifest = read_manifest(idx_dir / "manifest.json")
            if not manifest.has_cross_references:
                emit_error(
                    "missing_capability",
                    "cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled",
                    exit_code=ExitCode.USER_ERROR,
                )

        if k < 1:
            emit_error("bad_flag", f"k must be >= 1, got {k}", exit_code=ExitCode.USER_ERROR)

        if floor is not None and (floor < 0.0 or floor > 1.0):
            emit_error(
                "bad_flag",
                f"--floor must be in range [0.0, 1.0] for --mode {mode.value}, got {floor}",
                exit_code=ExitCode.USER_ERROR,
            )

        scope_obj: Scope | None = None
        if volume is not None or book is not None or range_str is not None:
            try:
                scope_obj = Scope.from_flags(volume=volume, book=book, range_str=range_str)
            except UnknownVolumeError:
                valid_volumes = ", ".join(sorted(CANONICAL_VOLUMES))
                emit_error(
                    "bad_flag",
                    f"Unknown volume {volume!r}. Valid volumes: {valid_volumes}",
                    exit_code=ExitCode.USER_ERROR,
                )
            except UnknownBookError:
                valid_books = ", ".join(sorted(BOOK_TO_VOLUME.keys()))
                emit_error(
                    "bad_flag",
                    f"Unknown book {book!r}. Valid books: {valid_books}",
                    exit_code=ExitCode.USER_ERROR,
                )
            except VolumeHasNoBooksError:
                emit_error(
                    "bad_flag",
                    "D&C has sections, not books; use --range instead",
                    exit_code=ExitCode.USER_ERROR,
                )
            except BookNotInVolumeError as e:
                emit_error(
                    "bad_flag",
                    f"Book {e.book!r} does not belong to volume {e.volume!r}",
                    exit_code=ExitCode.USER_ERROR,
                )
            except MalformedRangeError as e:
                emit_error(
                    "bad_flag",
                    f"Malformed range {e.range_str!r}: {e.detail}",
                    exit_code=ExitCode.USER_ERROR,
                )
            except RangeOutsideScopeError as e:
                emit_error(
                    "bad_flag",
                    str(e),
                    exit_code=ExitCode.USER_ERROR,
                )

        effective_window: int
        if window is None:
            window_config = load_window_config()
            effective_window = window_config.window_default
        else:
            effective_window = window

        if effective_window < 0:
            emit_error(
                "bad_flag",
                f"--window must be >= 0, got {effective_window}",
                exit_code=ExitCode.USER_ERROR,
            )

        effective_cross_ref_expand = cross_ref_expand if cross_ref_expand is not None else 0
        result = _run_query(text, k, mode.value, index, floor, effective_window, effective_dedupe, exclude, scope_obj, effective_hybrid_weight, effective_cross_ref_expand)

        query_id = query_log.new_query_id()
        log_record = _to_log_record(result, query_id)
        query_log.append(log_record)

        if format == Format.text:
            output = _format_text(result, show_scores)
        else:
            output = _format_json(result, show_scores, scope_obj)

        typer.echo(output)

    except ValueError as e:
        emit_error("bad_flag", str(e), exit_code=ExitCode.USER_ERROR)
    except FileNotFoundError as e:
        emit_error("index_not_found", str(e), exit_code=ExitCode.NOT_FOUND)
    except RuntimeError as e:
        msg = str(e)
        if "drift" in msg.lower():
            emit_error("endpoint_drift", msg, exit_code=ExitCode.UPSTREAM_ERROR)
        elif "embed" in msg.lower() or "endpoint" in msg.lower():
            emit_error("embedding_endpoint", msg, exit_code=ExitCode.UPSTREAM_ERROR)
        else:
            emit_error("query_failed", msg, exit_code=ExitCode.USER_ERROR)


def register(app: typer.Typer) -> None:
    """Register the query command with the parent app."""
    app.command("query")(cmd_query)
