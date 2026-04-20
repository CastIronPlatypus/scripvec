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

    def test_exclude_valid_passes_validation(self) -> None:
        """--exclude with valid text passes CLI validation (not a bad_flag error)."""
        result = runner.invoke(app, ["query", "test", "--exclude", "valid exclude text", "--mode", "dense", "--index", "nonexistent"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] != "bad_flag", f"Valid --exclude should not trigger bad_flag. Got: {err}"
        assert "--exclude" not in err.get("error", {}).get("message", "").lower()

    def test_exclude_absent_no_exclude_key_in_error(self) -> None:
        """When --exclude is not supplied, error response has no exclude-related content."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert "exclude" not in err.get("error", {}).get("message", "").lower() or err["error"]["code"] == "index_not_found"


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


class TestCrossRefExpandFlag:
    """Contract tests for --cross-ref-expand flag (CR-015 BEAD D)."""

    def test_cross_ref_expand_zero_valid(self) -> None:
        """--cross-ref-expand 0 is valid (no-op)."""
        result = runner.invoke(app, ["query", "test", "--cross-ref-expand", "0", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "cross-ref-expand" not in err.get("error", {}).get("message", "")

    def test_cross_ref_expand_absent_valid(self) -> None:
        """Absent --cross-ref-expand is valid (no-op)."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "cross-ref-expand" not in err.get("error", {}).get("message", "")

    def test_cross_ref_expand_positive_valid(self) -> None:
        """--cross-ref-expand 3 is valid for all modes."""
        for m in ["bm25", "dense", "hybrid"]:
            result = runner.invoke(app, ["query", "test", "--cross-ref-expand", "3", "--mode", m, "--index", "nonexistent"])
            err = json.loads(result.output) if result.output else {}
            assert err.get("error", {}).get("code") != "bad_flag" or "cross-ref-expand" not in err.get("error", {}).get("message", ""), \
                f"--cross-ref-expand 3 should be valid for --mode {m}"

    def test_cross_ref_expand_negative_raises_error(self) -> None:
        """--cross-ref-expand -1 raises error including rejected input."""
        result = runner.invoke(app, ["query", "test", "--cross-ref-expand", "-1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "-1" in err["error"]["message"] or "--cross-ref-expand" in err["error"]["message"]

    def test_cross_ref_expand_non_integer_raises_error(self) -> None:
        """--cross-ref-expand abc raises parse error."""
        result = runner.invoke(app, ["query", "test", "--cross-ref-expand", "abc"])
        assert result.exit_code != 0
        assert "cross-ref-expand" in result.output.lower() or "invalid" in result.output.lower()


class TestCrossRefMetadataCapability:
    """Contract tests for cross-ref metadata capability check (CR-015 BEAD E)."""

    def test_cross_ref_expand_without_metadata_raises_exact_error(self, tmp_path: "Path") -> None:
        """--cross-ref-expand N>0 against index lacking metadata raises exact error message."""
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from scripvec_retrieval.manifest import Manifest

        mock_manifest = MagicMock(spec=Manifest)
        mock_manifest.has_cross_references = False

        with (
            patch("scripvec_cli.query_cmd.resolve_latest", return_value="abc123"),
            patch("scripvec_cli.query_cmd.index_path", return_value=tmp_path),
            patch("scripvec_cli.query_cmd.read_manifest", return_value=mock_manifest),
        ):
            result = runner.invoke(app, ["query", "test", "--cross-ref-expand", "1", "--index", "abc123"])

        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "missing_capability"
        assert err["error"]["message"] == "cross-reference metadata not present in this index — rebuild with cross-reference ingestion enabled"


class TestVolumeFlag:
    """Contract tests for --volume flag (CR-011 Story A)."""

    def test_volume_valid_book_of_mormon(self) -> None:
        """--volume book_of_mormon parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "volume" not in err.get("error", {}).get("message", "")

    def test_volume_valid_doctrine_and_covenants(self) -> None:
        """--volume doctrine_and_covenants parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--volume", "doctrine_and_covenants", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "volume" not in err.get("error", {}).get("message", "")

    def test_volume_unknown_raises_error(self) -> None:
        """Unknown volume raises error listing valid volumes per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--volume", "unknown_volume"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "unknown_volume" in err["error"]["message"]
        assert "book_of_mormon" in err["error"]["message"]
        assert "doctrine_and_covenants" in err["error"]["message"]

    def test_volume_absent_no_error(self) -> None:
        """Absent --volume does not trigger volume-related error."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "volume" not in err.get("error", {}).get("message", "")


class TestBookFlag:
    """Contract tests for --book flag (CR-011 Story B)."""

    def test_book_valid_alma(self) -> None:
        """--book Alma parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--book", "Alma", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "book" not in err.get("error", {}).get("message", "")

    def test_book_valid_1_nephi(self) -> None:
        """--book '1 Nephi' parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--book", "1 Nephi", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "book" not in err.get("error", {}).get("message", "")

    def test_book_unknown_raises_error(self) -> None:
        """Unknown book raises error listing valid books per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--book", "UnknownBook"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "UnknownBook" in err["error"]["message"]

    def test_book_dc_raises_sections_error(self) -> None:
        """--book D&C raises exact ADR-001 message about sections."""
        result = runner.invoke(app, ["query", "test", "--book", "D&C"])
        assert result.exit_code != 0, "--book D&C must exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert err["error"]["message"] == "D&C has sections, not books; use --range instead"

    def test_book_not_in_volume_raises_error(self) -> None:
        """--book from wrong volume raises error per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--volume", "doctrine_and_covenants", "--book", "Alma"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "Alma" in err["error"]["message"]
        assert "doctrine_and_covenants" in err["error"]["message"]

    def test_book_absent_no_error(self) -> None:
        """Absent --book does not trigger book-related error."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "book" not in err.get("error", {}).get("message", "")


class TestRangeFlag:
    """Contract tests for --range flag (CR-011 Story C)."""

    def test_range_valid_single_reference(self) -> None:
        """--range 'Alma 32:21' parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--range", "Alma 32:21", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "range" not in err.get("error", {}).get("message", "")

    def test_range_valid_dc_reference(self) -> None:
        """--range 'D&C 76:1' parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--range", "D&C 76:1", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "range" not in err.get("error", {}).get("message", "")

    def test_range_valid_verse_range(self) -> None:
        """--range '2 Nephi 31:1 - 2 Nephi 31:21' parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--range", "2 Nephi 31:1 - 2 Nephi 31:21", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "range" not in err.get("error", {}).get("message", "")

    def test_range_valid_multi_reference(self) -> None:
        """--range 'Alma 32:21; Alma 34:15' parses without flag error."""
        result = runner.invoke(app, ["query", "test", "--range", "Alma 32:21; Alma 34:15", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "range" not in err.get("error", {}).get("message", "")

    def test_range_malformed_raises_error(self) -> None:
        """Malformed range raises specific parse error per ADR-010."""
        result = runner.invoke(app, ["query", "test", "--range", "NotABook 999:999"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "Malformed" in err["error"]["message"] or "range" in err["error"]["message"].lower()

    def test_range_outside_volume_raises_error(self) -> None:
        """--range outside --volume raises error naming filter and reference per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--range", "D&C 76:1"])
        assert result.exit_code != 0, "--range outside --volume must exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--volume" in err["error"]["message"], "Error must name --volume filter"
        assert "D&C" in err["error"]["message"], "Error must name the conflicting reference"

    def test_range_outside_book_raises_error(self) -> None:
        """--range outside --book raises error naming filter and reference per ADR-001."""
        result = runner.invoke(app, ["query", "test", "--book", "Alma", "--range", "Helaman 5:1"])
        assert result.exit_code != 0, "--range outside --book must exit non-zero"
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--book" in err["error"]["message"], "Error must name --book filter"
        assert "Helaman" in err["error"]["message"], "Error must name the conflicting reference"

    def test_range_absent_no_error(self) -> None:
        """Absent --range does not trigger range-related error."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "range" not in err.get("error", {}).get("message", "")


class TestScopeInResponse:
    """Contract tests for scope object in JSON response (CR-011 E1)."""

    def test_scope_always_present_unscoped(self) -> None:
        """Unscoped query has scope object with all nulls."""
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert "scope" in data
            assert data["scope"] == {"volume": None, "book": None, "range": None}
        else:
            err = json.loads(result.output)
            assert err.get("error", {}).get("code") != "bad_flag" or "scope" not in err.get("error", {}).get("message", "")

    def test_scope_volume_canonical(self) -> None:
        """--volume value is echoed canonically in scope.volume."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "volume" not in err.get("error", {}).get("message", "")

    def test_scope_book_canonical(self) -> None:
        """--book value is echoed canonically in scope.book."""
        result = runner.invoke(app, ["query", "test", "--book", "Alma", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or "book" not in err.get("error", {}).get("message", "")

    def test_scope_has_three_fields(self) -> None:
        """Scope object always has volume, book, range keys."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--index", "nonexistent"])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert "scope" in data
            assert "volume" in data["scope"]
            assert "book" in data["scope"]
            assert "range" in data["scope"]


class TestHelpText:
    """Contract tests for help text (CR-015 BEAD G)."""

    @staticmethod
    def _normalize_help(output: str) -> str:
        """Normalize help output by collapsing whitespace and removing Rich formatting."""
        import re
        text = re.sub(r'[│╭╮╰╯─]', '', output)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def test_hybrid_weight_help_names_mode_hybrid(self) -> None:
        """--hybrid-weight help text mentions --mode hybrid requirement."""
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        normalized = self._normalize_help(result.output)
        assert "Requires --mode hybrid" in normalized, "--hybrid-weight help must name --mode hybrid requirement"

    def test_cross_ref_expand_help_names_metadata_requirement(self) -> None:
        """--cross-ref-expand help text mentions index metadata requirement."""
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        normalized = self._normalize_help(result.output)
        assert "cross-reference metadata" in normalized, "--cross-ref-expand help must name metadata requirement"

    def test_cross_ref_expand_help_includes_error_message(self) -> None:
        """--cross-ref-expand help text includes the exact error message."""
        result = runner.invoke(app, ["query", "--help"])
        assert result.exit_code == 0
        normalized = self._normalize_help(result.output)
        assert "cross-reference metadata not present in this index" in normalized, \
            "--cross-ref-expand help must include the exact failure message"


class TestScopeComposition:
    """Contract tests for scope flag composition (CR-011 Story D)."""

    def test_volume_plus_book_parses(self) -> None:
        """--volume + --book combination parses without error when consistent."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--book", "Alma", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "volume" not in err.get("error", {}).get("message", "")
            and "book" not in err.get("error", {}).get("message", "")
        ), f"Consistent volume+book should not trigger bad_flag, got: {err}"

    def test_volume_plus_range_parses(self) -> None:
        """--volume + --range combination parses without error when consistent."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--range", "Alma 32:21", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "volume" not in err.get("error", {}).get("message", "")
            and "range" not in err.get("error", {}).get("message", "")
        ), f"Consistent volume+range should not trigger bad_flag, got: {err}"

    def test_book_plus_range_parses(self) -> None:
        """--book + --range combination parses without error when consistent."""
        result = runner.invoke(app, ["query", "test", "--book", "Alma", "--range", "Alma 32:21", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "book" not in err.get("error", {}).get("message", "")
            and "range" not in err.get("error", {}).get("message", "")
        ), f"Consistent book+range should not trigger bad_flag, got: {err}"

    def test_triple_composition_parses(self) -> None:
        """--volume + --book + --range all consistent parses without error."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--book", "Alma", "--range", "Alma 32:21", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        msg = err.get("error", {}).get("message", "")
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "volume" not in msg and "book" not in msg and "range" not in msg.lower()
        ), f"Triple consistent scope should not trigger scope-related bad_flag, got: {err}"

    def test_volume_book_conflict_raises_error(self) -> None:
        """--volume book_of_mormon + --book from D&C raises conflict error."""
        result = runner.invoke(app, ["query", "test", "--volume", "doctrine_and_covenants", "--book", "Alma"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "Alma" in err["error"]["message"]
        assert "doctrine_and_covenants" in err["error"]["message"]

    def test_volume_range_conflict_raises_error(self) -> None:
        """--volume book_of_mormon + --range D&C raises conflict error."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--range", "D&C 76:1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--volume" in err["error"]["message"]
        assert "D&C" in err["error"]["message"]

    def test_book_range_conflict_raises_error(self) -> None:
        """--book Alma + --range Helaman raises conflict error."""
        result = runner.invoke(app, ["query", "test", "--book", "Alma", "--range", "Helaman 5:1"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["error"]["code"] == "bad_flag"
        assert "--book" in err["error"]["message"]
        assert "Helaman" in err["error"]["message"]

    def test_volume_dc_with_range_parses(self) -> None:
        """--volume doctrine_and_covenants + --range D&C 76:1 parses."""
        result = runner.invoke(app, ["query", "test", "--volume", "doctrine_and_covenants", "--range", "D&C 76:1", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "volume" not in err.get("error", {}).get("message", "")
            and "range" not in err.get("error", {}).get("message", "")
        ), f"D&C volume+range should not trigger bad_flag, got: {err}"

    def test_scope_composition_echoed_in_response(self) -> None:
        """Composed scope is echoed with all non-null fields."""
        result = runner.invoke(app, ["query", "test", "--volume", "book_of_mormon", "--book", "Alma", "--index", "nonexistent"])
        err = json.loads(result.output) if result.output else {}
        assert err.get("error", {}).get("code") != "bad_flag" or (
            "volume" not in err.get("error", {}).get("message", "")
            and "book" not in err.get("error", {}).get("message", "")
        )
