"""Privacy filter — the single chokepoint between inference and any sink.

If a record was not returned by `apply()` it must not be written to disk
or uplinked. The self-test in `tests/test_privacy.py` is required to
pass at boot before the supervisor will start the inference pipeline.

The filter is fail-closed: anything ambiguous (missing room, unparseable
confidence, a forbidden token anywhere in the key tree, a non-scalar value
under an allow-listed key) causes the whole record to be dropped rather
than partially emitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping

_SCALAR_TYPES = (str, int, float, bool, type(None))


class PrivacyFilterError(Exception):
    """Raised when the filter detects a configuration that would permit
    raw or re-identifiable data to leave the device."""


@dataclass(frozen=True)
class PrivacyConfig:
    allowed_event_fields: frozenset[str]
    forbidden_field_patterns: frozenset[str]  # stored lower-cased
    excluded_rooms: frozenset[str]  # stored normalized (see _normalize_room)
    confidence_floor: float = 0.0

    @classmethod
    def from_site_config(cls, cfg: Mapping[str, Any]) -> "PrivacyConfig":
        allowed = frozenset(cfg.get("allowed_event_fields") or ())
        forbidden = frozenset(
            (p or "").lower() for p in (cfg.get("forbidden_field_patterns") or ())
        )
        excluded = frozenset(
            _normalize_room(r) for r in (cfg.get("excluded_rooms") or ())
        )
        if not allowed:
            raise PrivacyFilterError("allowed_event_fields must not be empty")

        try:
            floor = float(cfg.get("event_confidence_floor", 0.0))
        except (TypeError, ValueError) as e:
            raise PrivacyFilterError("event_confidence_floor must be a number") from e
        if not (0.0 <= floor <= 1.0):
            raise PrivacyFilterError("event_confidence_floor must be in [0, 1]")

        # Case-insensitive: an allow-listed field must not contain any
        # forbidden token, regardless of casing.
        for field in allowed:
            low = field.lower()
            for pattern in forbidden:
                if pattern and pattern in low:
                    raise PrivacyFilterError(
                        f"allowed field {field!r} matches forbidden pattern {pattern!r}"
                    )
        return cls(allowed, forbidden, excluded, floor)


def _normalize_room(value: Any) -> str:
    """Normalize a room id for membership tests: stringified, trimmed,
    case-folded. This makes the opt-out check robust to int-vs-str,
    surrounding whitespace, and casing differences from raw model output."""
    return str(value).strip().casefold()


def _iter_keys(obj: Any) -> Iterator[Any]:
    """Yield every mapping key at any depth within `obj`."""
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield key
            yield from _iter_keys(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_keys(item)


def _has_forbidden_token(text: str, patterns: frozenset[str]) -> bool:
    low = text.lower()
    return any(p and p in low for p in patterns)


def _has_forbidden_key(record: Mapping[str, Any], patterns: frozenset[str]) -> bool:
    for key in _iter_keys(record):
        if isinstance(key, str) and _has_forbidden_token(key, patterns):
            return True
    return False


def apply(record: Mapping[str, Any], config: PrivacyConfig) -> dict[str, Any] | None:
    """Return a privacy-safe copy of `record`, or None if it must be dropped.

    Drops the record entirely if:
      - `room_id` is missing (fail-closed: we cannot prove it is not an
        opt-out room),
      - the room is on the exclusion list,
      - any forbidden pattern appears in any key at any depth,
      - `confidence` is present and below the configured floor (or
        unparseable),
      - a retained (allow-listed) value is not a JSON scalar, i.e. a nested
        structure that could smuggle data under an allowed key,
      - a retained string value contains a forbidden token,
      - nothing survives the allow-list.

    Otherwise returns a new dict containing only allow-listed scalar fields.
    Fields outside the allow-list are silently stripped — by design: the
    inference pipeline is not trusted to know what is safe.
    """
    room_id = record.get("room_id")
    if room_id is None:
        return None
    if _normalize_room(room_id) in config.excluded_rooms:
        return None

    if _has_forbidden_key(record, config.forbidden_field_patterns):
        return None

    confidence = record.get("confidence")
    if confidence is not None:
        try:
            if float(confidence) < config.confidence_floor:
                return None
        except (TypeError, ValueError):
            return None

    out: dict[str, Any] = {}
    for key, value in record.items():
        if key not in config.allowed_event_fields:
            continue
        if not isinstance(value, _SCALAR_TYPES):
            return None
        if isinstance(value, str) and _has_forbidden_token(
            value, config.forbidden_field_patterns
        ):
            return None
        out[key] = value

    if not out:
        return None
    return out


def apply_many(
    records: Iterable[Mapping[str, Any]], config: PrivacyConfig
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        filtered = apply(record, config)
        if filtered is not None:
            out.append(filtered)
    return out
