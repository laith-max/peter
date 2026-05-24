"""Self-tests for the privacy filter.

Runs at boot via systemd / `python -m jetson_logging`. The supervisor
refuses to start the inference pipeline if any of these fail. Logic is
exercised against the in-repo valid fixture so the suite is deterministic;
the boot gate separately validates the *real* deployed config (see
`jetson_logging.__main__`).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jetson_logging.config import load_validated
from jetson_logging.filters.privacy import (
    PrivacyConfig,
    PrivacyFilterError,
    apply,
    apply_many,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "site.valid.json"
SCHEMA = Path(__file__).resolve().parents[1] / "config" / "event_schema.json"


def _good_record() -> dict:
    return {
        "timestamp_wall": "2026-04-29T10:00:00Z",
        "timestamp_monotonic": 12345.6,
        "site_id": "urban_large",
        "device_id": "jetson-ul-01",
        "room_id": "room-3",
        "event_type": "occupancy_change",
        "confidence": 0.91,
    }


class PrivacyFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = load_validated(FIXTURE)
        self.cfg = PrivacyConfig.from_site_config(self.raw)

    def test_allowed_record_passes_unchanged(self) -> None:
        record = _good_record()
        self.assertEqual(apply(record, self.cfg), record)

    def test_unknown_fields_are_stripped(self) -> None:
        record = _good_record()
        record["internal_debug_blob"] = "should never leave the device"
        out = apply(record, self.cfg)
        assert out is not None
        self.assertNotIn("internal_debug_blob", out)

    def test_forbidden_pattern_drops_record(self) -> None:
        record = {"room_id": "room-3", "frame_b64": "..."}
        self.assertIsNone(apply(record, self.cfg))

    def test_forbidden_pattern_substring_drops_record(self) -> None:
        record = {"room_id": "room-3", "audio_raw_chunk": b"\x00\x01"}
        self.assertIsNone(apply(record, self.cfg))

    def test_nested_forbidden_key_drops_record(self) -> None:
        # A forbidden token nested under a non-allow-listed key must still
        # drop the whole record, not be silently stripped.
        record = {"room_id": "room-3", "meta": {"frame_b64": "..."}}
        self.assertIsNone(apply(record, self.cfg))

    def test_forbidden_key_is_case_insensitive(self) -> None:
        record = {"room_id": "room-3", "FaceVector": [0.1, 0.2]}
        self.assertIsNone(apply(record, self.cfg))

    def test_excluded_room_drops_record(self) -> None:
        record = {"room_id": "opt-out-room-1", "event_type": "occupancy_change"}
        self.assertIsNone(apply(record, self.cfg))

    def test_excluded_room_match_is_normalized(self) -> None:
        cfg = PrivacyConfig.from_site_config(
            {
                "allowed_event_fields": ["room_id", "event_type"],
                "forbidden_field_patterns": ["frame"],
                "excluded_rooms": ["7"],
                "event_confidence_floor": 0.0,
            }
        )
        # int room id, surrounding whitespace, and casing all normalize.
        self.assertIsNone(apply({"room_id": 7, "event_type": "x"}, cfg))
        self.assertIsNone(apply({"room_id": " 7 ", "event_type": "x"}, cfg))

    def test_missing_room_id_drops_record(self) -> None:
        record = {"event_type": "occupancy_change", "confidence": 0.9}
        self.assertIsNone(apply(record, self.cfg))

    def test_low_confidence_dropped(self) -> None:
        record = _good_record()
        record["confidence"] = 0.5  # floor is 0.6
        self.assertIsNone(apply(record, self.cfg))

    def test_unparseable_confidence_dropped(self) -> None:
        record = _good_record()
        record["confidence"] = "high"
        self.assertIsNone(apply(record, self.cfg))

    def test_nested_value_under_allowed_key_dropped(self) -> None:
        record = _good_record()
        record["aggregate_bin"] = {"smuggled": "payload"}
        self.assertIsNone(apply(record, self.cfg))

    def test_forbidden_token_in_value_dropped(self) -> None:
        record = _good_record()
        record["event_type"] = "face_detected"  # value carries a forbidden token
        self.assertIsNone(apply(record, self.cfg))

    def test_empty_after_filter_dropped(self) -> None:
        cfg = PrivacyConfig.from_site_config(
            {
                "allowed_event_fields": ["event_type"],
                "forbidden_field_patterns": ["frame"],
                "excluded_rooms": [],
                "event_confidence_floor": 0.0,
            }
        )
        # room_id present (so not dropped for that reason) but not allow-listed
        # and no other allow-listed field survives -> drop, not emit {}.
        self.assertIsNone(apply({"room_id": "room-3"}, cfg))

    def test_empty_allowlist_rejected_at_config_time(self) -> None:
        bad = {**self.raw, "allowed_event_fields": []}
        with self.assertRaises(PrivacyFilterError):
            PrivacyConfig.from_site_config(bad)

    def test_allowlist_intersecting_forbidden_pattern_rejected(self) -> None:
        bad = {
            **self.raw,
            "allowed_event_fields": self.raw["allowed_event_fields"]
            + ["face_embedding"],
        }
        with self.assertRaises(PrivacyFilterError):
            PrivacyConfig.from_site_config(bad)

    def test_allowlist_forbidden_intersection_is_case_insensitive(self) -> None:
        bad = {
            **self.raw,
            "allowed_event_fields": self.raw["allowed_event_fields"] + ["FaceVector"],
        }
        with self.assertRaises(PrivacyFilterError):
            PrivacyConfig.from_site_config(bad)

    def test_apply_many_filters_and_drops(self) -> None:
        records = [
            _good_record(),
            {"room_id": "opt-out-room-1", "event_type": "occupancy_change"},
            {"room_id": "room-3", "frame_b64": "..."},
        ]
        out = apply_many(records, self.cfg)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["room_id"], "room-3")

    def test_allowlist_consistent_with_event_schema(self) -> None:
        # The on-device allow-list must cover everything the off-device schema
        # requires and must not permit anything the schema does not define.
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        allowed = set(self.cfg.allowed_event_fields)
        self.assertTrue(set(schema["required"]).issubset(allowed))
        self.assertTrue(allowed.issubset(set(schema["properties"])))


if __name__ == "__main__":
    unittest.main()
