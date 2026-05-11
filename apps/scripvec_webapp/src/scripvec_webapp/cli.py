"""Async subprocess wrapper for the `scripvec` CLI (CR-010).

The webapp never imports retrieval code; it invokes the CLI binary and consumes its
JSON output per the ADR-007 contract. This module owns the subprocess plumbing.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from typing import Any


class CliNotFoundError(RuntimeError):
    """Raised when the `scripvec` CLI binary cannot be located on PATH."""


class CliInvocationError(RuntimeError):
    """Raised when the CLI exits non-zero or returns malformed JSON.

    Carries the CLI's exit code and parsed error payload (if any) so the FastAPI
    layer can map them to HTTP status codes.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.payload = payload or {}


@dataclass(frozen=True)
class CliRunner:
    """Configured invoker for the `scripvec` CLI.

    Attributes:
        binary: Resolved path (or name) of the CLI executable.
        cwd: Working directory for the subprocess. Set to the repo root so the CLI
            sees the workspace's `data/` and `.scripvec_config.json`.
    """

    binary: str
    cwd: str

    @classmethod
    def discover(cls, *, binary: str | None = None, cwd: str | None = None) -> CliRunner:
        """Locate the CLI and build a runner.

        Args:
            binary: Explicit binary path, or `None` to look up `SCRIPVEC_BIN` env
                var, then fall back to `shutil.which("scripvec")`.
            cwd: Working directory, or `None` to use `SCRIPVEC_REPO_ROOT` env var,
                then fall back to the current working directory.

        Raises:
            CliNotFoundError: If no binary can be resolved.
        """
        resolved = binary or os.environ.get("SCRIPVEC_BIN") or shutil.which("scripvec")
        if not resolved:
            raise CliNotFoundError(
                "Could not find the `scripvec` CLI. Set SCRIPVEC_BIN or run "
                "`uv sync` to install the workspace."
            )
        working = cwd or os.environ.get("SCRIPVEC_REPO_ROOT") or os.getcwd()
        return cls(binary=resolved, cwd=working)

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            self.binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode if proc.returncode is not None else -1,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def _run_json(self, args: list[str]) -> dict[str, Any]:
        code, stdout, stderr = await self._run(args)
        parsed_payload: dict[str, Any] | None = None
        try:
            parsed = json.loads(stdout) if stdout.strip() else {}
            if isinstance(parsed, dict):
                parsed_payload = parsed
        except json.JSONDecodeError:
            parsed_payload = None

        if code != 0:
            raw_message = parsed_payload.get("message") if parsed_payload else None
            message = (
                raw_message
                if isinstance(raw_message, str)
                else f"scripvec {' '.join(args)} exited {code}"
            )
            raise CliInvocationError(
                message,
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
                payload=parsed_payload,
            )

        if parsed_payload is None:
            raise CliInvocationError(
                f"scripvec {' '.join(args)} did not return valid JSON",
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
            )
        return parsed_payload

    async def _run_json_any(self, args: list[str]) -> Any:
        """Like `_run_json` but allows non-dict JSON (e.g., index list is an array)."""
        code, stdout, stderr = await self._run(args)
        try:
            parsed = json.loads(stdout) if stdout.strip() else None
        except json.JSONDecodeError as exc:
            raise CliInvocationError(
                f"scripvec {' '.join(args)} did not return valid JSON: {exc}",
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
            ) from exc

        if code != 0:
            payload = parsed if isinstance(parsed, dict) else None
            raw_message = payload.get("message") if payload else None
            message = (
                raw_message
                if isinstance(raw_message, str)
                else f"scripvec {' '.join(args)} exited {code}"
            )
            raise CliInvocationError(
                message,
                exit_code=code,
                stdout=stdout,
                stderr=stderr,
                payload=payload,
            )
        return parsed

    async def version(self) -> dict[str, Any]:
        """Return `{cli_version, embedding_model, latest_index_hash}`."""
        return await self._run_json(["--version"])

    async def index_list(self) -> list[dict[str, Any]]:
        """Return array of index metadata, sorted by hash ascending."""
        result = await self._run_json_any(["index", "list"])
        if not isinstance(result, list):
            raise CliInvocationError(
                "scripvec index list did not return a JSON array",
                exit_code=0,
                stdout=json.dumps(result),
            )
        return result

    async def query(
        self,
        text: str,
        *,
        k: int = 10,
        mode: str = "hybrid",
        index: str = "latest",
        show_scores: bool = True,
    ) -> dict[str, Any]:
        """Run a query and return the parsed JSON response."""
        args = [
            "query",
            text,
            "--k",
            str(k),
            "--mode",
            mode,
            "--format",
            "json",
            "--index",
            index,
        ]
        if show_scores:
            args.append("--show-scores")
        return await self._run_json(args)

    async def feedback(
        self,
        *,
        query_id: str,
        verse_id: str,
        grade: int,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Record relevance feedback for a single result."""
        args = [
            "feedback",
            "feedback",
            "--query-id",
            query_id,
            "--verse-id",
            verse_id,
            "--grade",
            str(grade),
        ]
        if note:
            args.extend(["--note", note])
        return await self._run_json(args)
