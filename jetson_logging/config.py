"""Loading and validation for the per-device site configuration.

This module is the single entry point for turning the on-disk
``config/site.json`` into a validated configuration. The boot self-test
(``python -m jetson_logging``) loads and validates the *real* deployed
config through here, so a device that is unconfigured or misconfigured
fails the gate and the supervisor refuses to start inference.

The config path can be overridden with the ``JETSON_LOGGING_CONFIG``
environment variable (used by tests and by the retention sweeper).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "JETSON_LOGGING_CONFIG"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "site.json"

# Site identifiers permitted by the event schema. Kept in sync with
# config/event_schema.json by test_config.test_site_ids_match_schema.
SITE_IDS = frozenset(
    {"urban_large", "urban_small", "regional_large", "regional_small"}
)

# Values shipped in the template that must be replaced before a device may
# start. Validation rejects any of these appearing in the deployed config.
PLACEHOLDERS = frozenset({"REPLACE_ME", "example-room-id"})

_REQUIRED_LIST_FIELDS = (
    "excluded_rooms",
    "allowed_event_fields",
    "forbidden_field_patterns",
)


class ConfigError(Exception):
    """Raised when the device configuration is missing or invalid."""


def config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve which config file to use: explicit arg, env var, then default."""
    if path is not None:
        return Path(path)
    env = os.environ.get(CONFIG_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_CONFIG_PATH


def load_raw(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load and parse the site config JSON. Does not validate semantics."""
    p = config_path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"site config not found: {p}") from e
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"site config is not valid JSON ({p}): {e}") from e
    if not isinstance(cfg, dict):
        raise ConfigError(
            f"site config must be a JSON object, got {type(cfg).__name__}"
        )
    return cfg


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return value in PLACEHOLDERS
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_placeholder(v) for v in value)
    return False


def _check_number(cfg: dict[str, Any], key: str, lo: float, hi: float) -> None:
    value = cfg.get(key)
    # bool is a subclass of int; reject it explicitly.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{key} is required and must be a number in [{lo}, {hi}]")
    if not (lo <= value <= hi):
        raise ConfigError(f"{key} must be in [{lo}, {hi}], got {value}")


def validate(cfg: dict[str, Any]) -> None:
    """Validate device config against the documented contract.

    Raises :class:`ConfigError` on the first problem found. Enforces the
    README promise that the device refuses to start when required fields
    are missing/empty or still hold template placeholders.
    """
    for key in ("site_id", "device_id"):
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{key} is required and must be a non-empty string")
        if value in PLACEHOLDERS:
            raise ConfigError(f"{key} still holds a template placeholder: {value!r}")

    if cfg["site_id"] not in SITE_IDS:
        raise ConfigError(
            f"site_id {cfg['site_id']!r} is not one of {sorted(SITE_IDS)}"
        )

    for key in _REQUIRED_LIST_FIELDS:
        value = cfg.get(key)
        if not isinstance(value, list) or not value:
            raise ConfigError(f"{key} is required and must be a non-empty list")
        if not all(isinstance(v, str) and v.strip() for v in value):
            raise ConfigError(f"{key} must contain only non-empty strings")
        if _contains_placeholder(value):
            raise ConfigError(f"{key} still holds a template placeholder")

    _check_number(cfg, "event_confidence_floor", 0.0, 1.0)

    retention = cfg.get("local_retention_days")
    if not isinstance(retention, int) or isinstance(retention, bool) or retention <= 0:
        raise ConfigError("local_retention_days must be a positive integer")


def load_validated(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load, parse, and validate the site config. Raises on any problem."""
    cfg = load_raw(path)
    validate(cfg)
    return cfg
