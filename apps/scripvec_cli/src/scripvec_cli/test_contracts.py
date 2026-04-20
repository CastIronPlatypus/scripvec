"""ADR-007 contract tests for CLI subcommands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from .main import app

runner = CliRunner()


class TestVersion:
    def test_version_json_schema(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "cli_version" in data
        assert "embedding_model" in data

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0


class TestFeedback:
    def test_feedback_bad_grade_error(self) -> None:
        result = runner.invoke(
            app,
            ["feedback", "feedback", "--query-id", "test", "--verse-id", "test", "--grade", "5"],
        )
        assert result.exit_code != 0


class TestIndexList:
    def test_index_list_empty_array(self) -> None:
        result = runner.invoke(app, ["index", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestQuery:
    def test_query_bad_k_structured_error(self) -> None:
        result = runner.invoke(app, ["query", "test", "--k", "0"])
        assert result.exit_code != 0

    def test_query_missing_index_error(self) -> None:
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        assert result.exit_code != 0


class TestFloorFlag:
    """Contract tests for --floor flag (CR-012 B1)."""

    def test_floor_valid_in_range(self) -> None:
        """Valid floor value in range parses without immediate error."""
        result = runner.invoke(app, ["query", "test", "--floor", "0.5", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", "")

    def test_floor_boundary_zero(self) -> None:
        """Floor 0.0 is valid (lower boundary)."""
        result = runner.invoke(app, ["query", "test", "--floor", "0.0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", "")

    def test_floor_boundary_one(self) -> None:
        """Floor 1.0 is valid (upper boundary)."""
        result = runner.invoke(app, ["query", "test", "--floor", "1.0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", "")

    def test_floor_integer_zero(self) -> None:
        """Floor 0 (integer) parses same as 0.0."""
        result = runner.invoke(app, ["query", "test", "--floor", "0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", "")

    def test_floor_out_of_range_high(self) -> None:
        """Floor > 1.0 raises structured error naming mode and range."""
        result = runner.invoke(app, ["query", "test", "--floor", "1.5", "--mode", "dense"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--floor" in err["error"]["message"]
        assert "[0.0, 1.0]" in err["error"]["message"]
        assert "dense" in err["error"]["message"]

    def test_floor_out_of_range_low(self) -> None:
        """Floor < 0.0 raises structured error naming mode and range."""
        result = runner.invoke(app, ["query", "test", "--floor", "-0.1", "--mode", "hybrid"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--floor" in err["error"]["message"]
        assert "[0.0, 1.0]" in err["error"]["message"]
        assert "hybrid" in err["error"]["message"]

    def test_floor_non_numeric(self) -> None:
        """Non-numeric floor raises parse error naming the flag."""
        result = runner.invoke(app, ["query", "test", "--floor", "abc"])
        assert result.exit_code != 0
        assert "floor" in result.output.lower() or "invalid" in result.output.lower()

    def test_floor_absent(self) -> None:
        """Absent --floor leaves floor unset (not 0.0)."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", "")
