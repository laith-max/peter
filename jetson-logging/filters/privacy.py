"""Privacy filter — the single chokepoint between inference and any sink.

If a record was not returned by `apply()` it must not be written to disk
or uplinked. The self-test in `tests/test_privacy.py` is required to
pass at boot before the supervisor will start the inference pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


class PrivacyFilterError(Exception):
    """Raised when the filter detects a configuration that would permit
    raw or re-identifiable data to leave the device."""


@dataclass(frozen=True)
class PrivacyConfig:
    allowed_event_fields: frozenset[str]
    forbidden_field_patterns: frozenset[str]
    excluded_rooms: frozenset[str]

    @classmethod
    def from_site_config(cls, cfg: Mapping[str, Any]) -> "PrivacyConfig":
        allowed = frozenset(cfg.get("allowed_event_fields") or ())
        forbidden = frozenset(cfg.get("forbidden_field_patterns") or ())
        excluded = frozenset(cfg.get("excluded_rooms") or ())
        if not allowed:
            raise PrivacyFilterError("allowed_event_fields must not be empty")
        for field in allowed:
            for pattern in forbidden:
                if pattern in field:
                    raise PrivacyFilterError(
                        f"allowed field {field!r} matches forbidden pattern {pattern!r}"
                    )
        return cls(allowed, forbidden, excluded)


def apply(record: Mapping[str, Any], config: PrivacyConfig) -> dict[str, Any] | None:
    """Return a privacy-safe copy of `record`, or None if it must be dropped.

    Drops the record entirely if:
      - the room is on the exclusion list,
      - any forbidden pattern appears in any key.

    Otherwise returns a new dict containing only allow-listed fields.
    Fields outside the allow-list are silently stripped — this is by
    design: the inference pipeline is not trusted to know what is safe.
    """
    room_id = record.get("room_id")
    if room_id in config.excluded_rooms:
        return None

    for key in record.keys():
        for pattern in config.forbidden_field_patterns:
            if pattern in key:
                return None

    return {k: v for k, v in record.items() if k in config.allowed_event_fields}


def apply_many(
    records: Iterable[Mapping[str, Any]], config: PrivacyConfig
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        filtered = apply(record, config)
        if filtered is not None:
            out.append(filtered)
    return out
