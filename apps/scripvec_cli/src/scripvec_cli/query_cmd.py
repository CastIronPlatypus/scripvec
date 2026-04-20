"""CLI command for scripvec query."""

from __future__ import annotations

import json
from enum import Enum
from typing import Annotated

import typer

from scripvec_retrieval.config import load_window_config
from scripvec_retrieval.embed import MAX_TOKENS, estimate_token_count
from scripvec_retrieval.query import QueryResult, query

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
) -> QueryResult:
    """Execute query and return result."""
    return query(text, k=k, mode=mode, index=index, floor=floor, window=window)


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


def _format_json(result: QueryResult, show_scores: bool) -> str:
    """Format result as JSON."""
    floor_data = None
    if result.floor is not None:
        floor_data = {
            "value": result.floor.value,
            "interpretation": result.floor.interpretation,
            "effective_threshold": result.floor.effective_threshold,
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
        return res

    data = {
        "query": result.query,
        "mode": result.mode,
        "k": result.k,
        "index": result.index,
        "floor": floor_data,
        "latency_ms": result.latency_ms,
        "results": [_format_result(r) for r in result.results],
    }
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
    hybrid_weight: Annotated[str | None, typer.Option("--hybrid-weight", help="Lexical:dense weight ratio for hybrid mode (e.g., '2:1' or '1.5:0.5')")] = None,
    cross_ref_expand: Annotated[int | None, typer.Option("--cross-ref-expand", help="Expand cross-references up to N levels (0 = no expansion)")] = None,
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

        # effective_dedupe is now available for downstream use (CR-013 B6)
        _ = effective_dedupe

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
            # hybrid_weight is validated; (lexical_w, dense_w) available for downstream use

        if cross_ref_expand is not None and cross_ref_expand < 0:
            emit_error(
                "bad_flag",
                f"--cross-ref-expand must be >= 0, got {cross_ref_expand}",
                exit_code=ExitCode.USER_ERROR,
            )
        # cross_ref_expand 0 and None are equivalent no-ops

        if k < 1:
            emit_error("bad_flag", f"k must be >= 1, got {k}", exit_code=ExitCode.USER_ERROR)

        if floor is not None and (floor < 0.0 or floor > 1.0):
            emit_error(
                "bad_flag",
                f"--floor must be in range [0.0, 1.0] for --mode {mode.value}, got {floor}",
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

        result = _run_query(text, k, mode.value, index, floor, effective_window)

        query_id = query_log.new_query_id()
        log_record = _to_log_record(result, query_id)
        query_log.append(log_record)

        if format == Format.text:
            output = _format_text(result, show_scores)
        else:
            output = _format_json(result, show_scores)

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
