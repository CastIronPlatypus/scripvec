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
    """Contract tests for --floor flag (CR-012 B1, B6)."""

    def test_floor_valid_in_range(self) -> None:
        """Valid floor value in range parses without immediate error."""
        result = runner.invoke(app, ["query", "test", "--floor", "0.5", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", ""), \
            f"Floor 0.5 should not trigger bad_flag, got: {err}"

    def test_floor_boundary_zero(self) -> None:
        """Floor 0.0 is valid (lower boundary)."""
        result = runner.invoke(app, ["query", "test", "--floor", "0.0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", ""), \
            f"Floor 0.0 should be valid, got: {err}"

    def test_floor_boundary_one(self) -> None:
        """Floor 1.0 is valid (upper boundary)."""
        result = runner.invoke(app, ["query", "test", "--floor", "1.0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", ""), \
            f"Floor 1.0 should be valid, got: {err}"

    def test_floor_integer_zero(self) -> None:
        """Floor 0 (integer) parses same as 0.0."""
        result = runner.invoke(app, ["query", "test", "--floor", "0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", ""), \
            f"Floor 0 should be valid, got: {err}"

    def test_floor_out_of_range_high(self) -> None:
        """Floor > 1.0 raises structured error naming mode and range (ADR-001)."""
        result = runner.invoke(app, ["query", "test", "--floor", "1.5", "--mode", "dense"])
        assert result.exit_code != 0, "Out-of-range floor should exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag", f"Expected error code 'bad_flag', got: {err['error']['code']}"
        assert "--floor" in err["error"]["message"], f"Error message should name --floor, got: {err['error']['message']}"
        assert "[0.0, 1.0]" in err["error"]["message"], f"Error message should state range, got: {err['error']['message']}"
        assert "dense" in err["error"]["message"], f"Error message should name mode, got: {err['error']['message']}"

    def test_floor_out_of_range_low(self) -> None:
        """Floor < 0.0 raises structured error naming mode and range (ADR-001)."""
        result = runner.invoke(app, ["query", "test", "--floor", "-0.1", "--mode", "hybrid"])
        assert result.exit_code != 0, "Out-of-range floor should exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag", f"Expected error code 'bad_flag', got: {err['error']['code']}"
        assert "--floor" in err["error"]["message"], f"Error message should name --floor, got: {err['error']['message']}"
        assert "[0.0, 1.0]" in err["error"]["message"], f"Error message should state range, got: {err['error']['message']}"
        assert "hybrid" in err["error"]["message"], f"Error message should name mode, got: {err['error']['message']}"

    def test_floor_out_of_range_bm25_mode(self) -> None:
        """Floor out of range in BM25 mode names the mode (ADR-001)."""
        result = runner.invoke(app, ["query", "test", "--floor", "2.0", "--mode", "bm25"])
        assert result.exit_code != 0, "Out-of-range floor should exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag", f"Expected error code 'bad_flag', got: {err['error']['code']}"
        assert "bm25" in err["error"]["message"], f"Error message should name bm25 mode, got: {err['error']['message']}"

    def test_floor_non_numeric(self) -> None:
        """Non-numeric floor raises parse error naming the flag (ADR-001)."""
        result = runner.invoke(app, ["query", "test", "--floor", "abc"])
        assert result.exit_code != 0, "Non-numeric floor should exit non-zero"
        assert "floor" in result.output.lower() or "invalid" in result.output.lower(), \
            f"Error should name floor or indicate invalid input, got: {result.output}"

    def test_floor_absent(self) -> None:
        """Absent --floor leaves floor unset (not 0.0)."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "floor" not in err.get("error", {}).get("message", ""), \
            f"Absent floor should not trigger floor-related bad_flag, got: {err}"


class TestWindowFlag:
    """Contract tests for --window flag (CR-013 B1)."""

    def test_window_parses_valid_value(self) -> None:
        """Valid window value parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--window", "3", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "window" not in err.get("error", {}).get("message", "")

    def test_window_zero_valid(self) -> None:
        """Window 0 is valid (no-op)."""
        result = runner.invoke(app, ["query", "test", "--window", "0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "window" not in err.get("error", {}).get("message", "")

    def test_window_negative_raises_error(self) -> None:
        """Negative window raises structured error per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--window", "-1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--window" in err["error"]["message"]
        assert ">= 0" in err["error"]["message"]

    def test_window_absent_uses_config_default(self) -> None:
        """Absent --window uses config default, not hard-coded value."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "window" not in err.get("error", {}).get("message", "")

    def test_window_non_integer_raises_error(self) -> None:
        """Non-integer window raises parse error."""
        result = runner.invoke(app, ["query", "test", "--window", "abc"])
        assert result.exit_code != 0
        assert "window" in result.output.lower() or "invalid" in result.output.lower()


class TestDedupeFlag:
    """Contract tests for --dedupe / --no-dedupe flags (CR-013 B5)."""

    def test_dedupe_absent_defaults_true(self) -> None:
        """No flag → effective dedupe = True (default on)."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "dedupe" not in err.get("error", {}).get("message", "")

    def test_dedupe_flag_parses(self) -> None:
        """--dedupe → True (explicit enable)."""
        result = runner.invoke(app, ["query", "test", "--dedupe", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "dedupe" not in err.get("error", {}).get("message", "")

    def test_no_dedupe_flag_parses(self) -> None:
        """--no-dedupe → False (explicit disable)."""
        result = runner.invoke(app, ["query", "test", "--no-dedupe", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "dedupe" not in err.get("error", {}).get("message", "")

    def test_both_dedupe_flags_raises_error(self) -> None:
        """--dedupe --no-dedupe → error, exit non-zero."""
        result = runner.invoke(app, ["query", "test", "--dedupe", "--no-dedupe"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--dedupe" in err["error"]["message"]
        assert "--no-dedupe" in err["error"]["message"]


class TestExcludeFlag:
    """Contract tests for --exclude flag (CR-014)."""

    def test_exclude_with_bm25_mode_raises_error(self) -> None:
        """--exclude with --mode bm25 raises error naming both flag and mode."""
        result = runner.invoke(app, ["query", "test", "--exclude", "avoid this", "--mode", "bm25"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--exclude" in err["error"]["message"]
        assert "bm25" in err["error"]["message"].lower()
        assert "vector" in err["error"]["message"].lower() or "analog" in err["error"]["message"].lower()

    def test_exclude_empty_string_raises_error(self) -> None:
        """--exclude '' raises error naming the flag and empty problem."""
        result = runner.invoke(app, ["query", "test", "--exclude", ""])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--exclude" in err["error"]["message"]
        assert "empty" in err["error"]["message"].lower() or "whitespace" in err["error"]["message"].lower()

    def test_exclude_whitespace_only_raises_error(self) -> None:
        """--exclude with whitespace-only text raises error."""
        result = runner.invoke(app, ["query", "test", "--exclude", "   "])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--exclude" in err["error"]["message"]

    def test_exclude_oversize_raises_error(self) -> None:
        """--exclude with text exceeding 8K token cap raises error."""
        oversize_text = "word " * 50000
        result = runner.invoke(app, ["query", "test", "--exclude", oversize_text])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--exclude" in err["error"]["message"]
        assert "token" in err["error"]["message"].lower() or "limit" in err["error"]["message"].lower()


class TestHybridWeightFlag:
    """Contract tests for --hybrid-weight flag (CR-015 BEAD A)."""

    def test_hybrid_weight_valid_integer_ratio(self) -> None:
        """--hybrid-weight 2:1 parses successfully in hybrid mode."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "2:1", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "hybrid-weight" not in err.get("error", {}).get("message", "")

    def test_hybrid_weight_valid_float_ratio(self) -> None:
        """--hybrid-weight 1.5:0.5 parses successfully."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "1.5:0.5", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "hybrid-weight" not in err.get("error", {}).get("message", "")

    def test_hybrid_weight_with_bm25_raises_error(self) -> None:
        """--hybrid-weight with --mode bm25 raises error naming mode conflict."""
        result = runner.invoke(app, ["query", "test", "--mode", "bm25", "--hybrid-weight", "1:1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--hybrid-weight" in err["error"]["message"]
        assert "bm25" in err["error"]["message"].lower()

    def test_hybrid_weight_with_dense_raises_error(self) -> None:
        """--hybrid-weight with --mode dense raises error naming mode conflict."""
        result = runner.invoke(app, ["query", "test", "--mode", "dense", "--hybrid-weight", "1:1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--hybrid-weight" in err["error"]["message"]
        assert "dense" in err["error"]["message"].lower()

    def test_hybrid_weight_malformed_non_numeric(self) -> None:
        """--hybrid-weight foo raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "foo"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "foo" in err["error"]["message"]

    def test_hybrid_weight_malformed_missing_half(self) -> None:
        """--hybrid-weight 1: raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "1:"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "1:" in err["error"]["message"]

    def test_hybrid_weight_malformed_negative(self) -> None:
        """--hybrid-weight -1:2 raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "-1:2"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "-1:2" in err["error"]["message"]

    def test_hybrid_weight_malformed_both_zero(self) -> None:
        """--hybrid-weight 0:0 raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "0:0"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "0:0" in err["error"]["message"]

    def test_hybrid_weight_malformed_too_many_colons(self) -> None:
        """--hybrid-weight 1:2:3 raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--mode", "hybrid", "--hybrid-weight", "1:2:3"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "1:2:3" in err["error"]["message"]
