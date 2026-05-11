"""Tests for the CliRunner subprocess wrapper.

Uses a Python-based fake `scripvec` script on PATH that emits canned JSON
based on its argv. No real CLI subprocess is invoked.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest

from .cli import CliInvocationError, CliNotFoundError, CliRunner


def _make_fake_cli(tmp_path: Path, script: str) -> str:
    """Write an executable shell script to tmp_path/scripvec and return its dir."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script_path = bin_dir / "scripvec"
    script_path.write_text(script)
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(bin_dir)


def _runner_with(bin_dir: str) -> CliRunner:
    return CliRunner(binary=str(Path(bin_dir) / "scripvec"), cwd=bin_dir)


def test_discover_uses_env_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = _make_fake_cli(
        tmp_path,
        "#!/usr/bin/env bash\necho '{\"cli_version\":\"x\"}'\n",
    )
    monkeypatch.setenv("SCRIPVEC_BIN", str(Path(bin_dir) / "scripvec"))
    runner = CliRunner.discover()
    assert runner.binary.endswith("scripvec")


def test_discover_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCRIPVEC_BIN", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent-path-for-scripvec-test")
    with pytest.raises(CliNotFoundError):
        CliRunner.discover()


def test_version_parses_json(tmp_path: Path) -> None:
    bin_dir = _make_fake_cli(
        tmp_path,
        "#!/usr/bin/env bash\n"
        'echo \'{"cli_version":"0.0.0","embedding_model":"foo","latest_index_hash":"abc"}\'\n',
    )
    runner = _runner_with(bin_dir)
    result = asyncio.run(runner.version())
    assert result == {"cli_version": "0.0.0", "embedding_model": "foo", "latest_index_hash": "abc"}


def test_index_list_returns_array(tmp_path: Path) -> None:
    bin_dir = _make_fake_cli(
        tmp_path,
        "#!/usr/bin/env bash\n"
        'echo \'[{"hash":"abc","is_latest":true}]\'\n',
    )
    runner = _runner_with(bin_dir)
    result = asyncio.run(runner.index_list())
    assert result == [{"hash": "abc", "is_latest": True}]


def test_query_passes_args(tmp_path: Path) -> None:
    # Echo argv to stderr so we can verify, emit valid JSON on stdout
    script = (
        "#!/usr/bin/env bash\n"
        'echo "ARGS=$*" >&2\n'
        'echo \'{"query":"x","mode":"hybrid","k":5,"index":"abc","results":[]}\'\n'
    )
    bin_dir = _make_fake_cli(tmp_path, script)
    runner = _runner_with(bin_dir)
    result = asyncio.run(
        runner.query("faith", k=5, mode="hybrid", index="latest", show_scores=True)
    )
    assert result["query"] == "x"
    assert result["k"] == 5


def test_nonzero_exit_raises_invocation_error(tmp_path: Path) -> None:
    script = (
        "#!/usr/bin/env bash\n"
        'echo \'{"error":"index_not_found","message":"missing"}\'\n'
        "exit 2\n"
    )
    bin_dir = _make_fake_cli(tmp_path, script)
    runner = _runner_with(bin_dir)
    with pytest.raises(CliInvocationError) as ex:
        asyncio.run(runner.version())
    assert ex.value.exit_code == 2
    assert ex.value.payload["error"] == "index_not_found"
    assert "missing" in str(ex.value)


def test_non_json_stdout_raises(tmp_path: Path) -> None:
    bin_dir = _make_fake_cli(
        tmp_path,
        "#!/usr/bin/env bash\necho 'not json'\n",
    )
    runner = _runner_with(bin_dir)
    with pytest.raises(CliInvocationError):
        asyncio.run(runner.version())


def test_feedback_includes_note_when_present(tmp_path: Path) -> None:
    script = (
        "#!/usr/bin/env bash\n"
        'ARGS="$*"\n'
        'if [[ "$ARGS" == *"--note"* ]]; then\n'
        '  echo \'{"status":"recorded","note":true}\'\n'
        'else\n'
        '  echo \'{"status":"recorded","note":false}\'\n'
        'fi\n'
    )
    bin_dir = _make_fake_cli(tmp_path, script)
    runner = _runner_with(bin_dir)
    with_note = asyncio.run(
        runner.feedback(query_id="q", verse_id="v", grade=2, note="hi")
    )
    without_note = asyncio.run(
        runner.feedback(query_id="q", verse_id="v", grade=2)
    )
    assert with_note == {"status": "recorded", "note": True}
    assert without_note == {"status": "recorded", "note": False}


def test_runner_uses_configured_cwd(tmp_path: Path) -> None:
    """Subprocess inherits the runner's `cwd` for working directory."""
    bin_dir = _make_fake_cli(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "echo \"{\\\"pwd\\\":\\\"$(pwd)\\\"}\"\n",
    )
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    runner = CliRunner(binary=str(Path(bin_dir) / "scripvec"), cwd=str(cwd))
    result = asyncio.run(runner.version())
    assert os.path.realpath(result["pwd"]) == os.path.realpath(str(cwd))


def test_invocation_error_carries_payload(tmp_path: Path) -> None:
    script = (
        "#!/usr/bin/env bash\n"
        'echo \'{"error":"bad_flag","message":"k must be >= 1"}\'\n'
        "exit 1\n"
    )
    bin_dir = _make_fake_cli(tmp_path, script)
    runner = _runner_with(bin_dir)
    with pytest.raises(CliInvocationError) as ex:
        asyncio.run(runner.query("x", k=0))
    payload = ex.value.payload
    assert payload["error"] == "bad_flag"
    assert json.dumps(payload)  # round-trippable
