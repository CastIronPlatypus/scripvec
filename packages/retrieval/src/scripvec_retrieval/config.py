"""EmbedConfig and environment/config-file loader per ADR-005."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EmbedConfig:
    """Immutable embedding configuration with non-empty invariants."""

    base_url: str
    api_key: str
    model: str
    dim: int

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url must be non-empty")
        if not self.api_key:
            raise ValueError("api_key must be non-empty")
        if not self.model:
            raise ValueError("model must be non-empty")
        if self.dim <= 0:
            raise ValueError("dim must be positive")


def _read_optional_config_file() -> dict[str, Any]:
    """Read optional non-committed config file. Returns empty dict if absent."""
    config_path = Path.cwd() / ".scripvec_config.json"
    if not config_path.exists():
        return {}
    try:
        with config_path.open() as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise RuntimeError(f"Config file {config_path} must contain a JSON object")
        return data
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Config file {config_path} is corrupt: {e}") from e


def load_embed_config() -> EmbedConfig:
    """Load embedding config from env vars, falling back to optional config file.

    Env vars (checked first):
        OPENAI_BASE_URL - base URL for OpenAI-compatible endpoint
        OPENAI_API_KEY - API key / bearer token
        SCRIPVEC_EMBED_MODEL - model identifier string
        SCRIPVEC_EMBED_DIM - embedding dimension (integer)

    Falls back to .scripvec_config.json in cwd for any missing values.

    Raises:
        RuntimeError: if any required field cannot be resolved (per ADR-001)
    """
    file_config = _read_optional_config_file()

    base_url = os.environ.get("OPENAI_BASE_URL") or file_config.get("base_url")
    api_key = os.environ.get("OPENAI_API_KEY") or file_config.get("api_key")
    model = os.environ.get("SCRIPVEC_EMBED_MODEL") or file_config.get("model")
    dim_str = os.environ.get("SCRIPVEC_EMBED_DIM") or file_config.get("dim")

    missing: list[str] = []
    if not base_url:
        missing.append("base_url (OPENAI_BASE_URL)")
    if not api_key:
        missing.append("api_key (OPENAI_API_KEY)")
    if not model:
        missing.append("model (SCRIPVEC_EMBED_MODEL)")
    if dim_str is None:
        missing.append("dim (SCRIPVEC_EMBED_DIM)")

    if missing:
        raise RuntimeError(
            f"Cannot resolve embedding config: missing {', '.join(missing)}. "
            "Set environment variables or provide .scripvec_config.json"
        )

    try:
        dim = int(dim_str)  # type: ignore[arg-type]
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"dim must be an integer, got {dim_str!r}") from e

    return EmbedConfig(base_url=base_url, api_key=api_key, model=model, dim=dim)


# Defaults for exclude config — defined exactly once per bead sv-gpr
_EXCLUDE_M_DEFAULT = 10
_EXCLUDE_BUFFER_DEFAULT = 20


@dataclass(frozen=True)
class ExcludeConfig:
    """Immutable exclusion configuration per CR-014."""

    exclude_m: int
    exclude_buffer: int

    def __post_init__(self) -> None:
        if self.exclude_m < 1:
            raise ValueError("exclude_m must be >= 1")
        if self.exclude_buffer < 0:
            raise ValueError("exclude_buffer must be >= 0")


@dataclass(frozen=True)
class WindowConfig:
    """Immutable window configuration per CR-013."""

    window_default: int

    def __post_init__(self) -> None:
        if self.window_default < 0:
            raise ValueError("window_default must be >= 0")


def load_window_config() -> WindowConfig:
    """Load window config from config file.

    Config keys (required):
        window_default - default N for --window flag

    Raises:
        RuntimeError: if window_default is missing or malformed (per ADR-001)
    """
    file_config = _read_optional_config_file()

    window_default_raw = file_config.get("window_default")

    if window_default_raw is None:
        raise RuntimeError(
            "Cannot resolve window config: missing window_default. "
            "Add window_default to .scripvec_config.json"
        )

    try:
        window_default = int(window_default_raw)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"window_default must be an integer, got {window_default_raw!r}") from e

    return WindowConfig(window_default=window_default)


def load_exclude_config() -> ExcludeConfig:
    """Load exclusion config from optional config file, with defaults.

    Config keys (optional, fall back to defaults):
        exclude_m - top-M verses for exclusion set
        exclude_buffer - extra hits retrieved before exclusion

    Raises:
        RuntimeError: if values are malformed (per ADR-001)
    """
    file_config = _read_optional_config_file()

    exclude_m_raw = file_config.get("exclude_m", _EXCLUDE_M_DEFAULT)
    exclude_buffer_raw = file_config.get("exclude_buffer", _EXCLUDE_BUFFER_DEFAULT)

    try:
        exclude_m = int(exclude_m_raw)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"exclude_m must be an integer, got {exclude_m_raw!r}") from e

    try:
        exclude_buffer = int(exclude_buffer_raw)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"exclude_buffer must be an integer, got {exclude_buffer_raw!r}") from e

    return ExcludeConfig(exclude_m=exclude_m, exclude_buffer=exclude_buffer)
