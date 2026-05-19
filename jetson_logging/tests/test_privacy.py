"""Self-tests for the privacy filter.

Runs at boot via systemd. The supervisor refuses to start the inference
pipeline if any of these fail.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from filters.privacy import PrivacyConfig, PrivacyFilterError, apply, apply_many


SITE_CONFIG = {
    "allowed_event_fields": [
        "timestamp_wall",
        "timestamp_monotonic",
        "site_id",
        "device_id",
        "room_id",
        "event_type",
        "confidence",
        "aggregate_bin",
    ],
    "forbidden_field_patterns": [
        "frame",
        "image",
        "pcm",
        "audio_raw",
        "spectrogram",
        "embedding",
        "face",
        "name",
    ],
    "excluded_rooms": ["opt-out-room-1"],
}


class PrivacyFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = PrivacyConfig.from_site_config(SITE_CONFIG)

    def test_allowed_record_passes_unchanged(self) -> None:
        record = {
            "timestamp_wall": "2026-04-29T10:00:00Z",
            "timestamp_monotonic": 12345.6,
            "site_id": "urban_large",
            "device_id": "jetson-ul-01",
            "room_id": "room-3",
            "event_type": "occupancy_change",
            "confidence": 0.91,
        }
        out = apply(record, self.cfg)
        self.assertEqual(out, record)

    def test_unknown_fields_are_stripped(self) -> None:
        record = {
            "timestamp_wall": "2026-04-29T10:00:00Z",
            "timestamp_monotonic": 12345.6,
            "site_id": "urban_large",
            "device_id": "jetson-ul-01",
            "room_id": "room-3",
            "event_type": "occupancy_change",
            "confidence": 0.91,
            "internal_debug_blob": "should never leave the device",
        }
        out = apply(record, self.cfg)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertNotIn("internal_debug_blob", out)

    def test_forbidden_pattern_drops_record(self) -> None:
        record = {
            "timestamp_wall": "2026-04-29T10:00:00Z",
            "room_id": "room-3",
            "frame_b64": "...",
        }
        self.assertIsNone(apply(record, self.cfg))

    def test_forbidden_pattern_substring_drops_record(self) -> None:
        # "audio_raw_chunk" contains "audio_raw" → must drop.
        record = {
            "timestamp_wall": "2026-04-29T10:00:00Z",
            "room_id": "room-3",
            "audio_raw_chunk": b"\x00\x01",
        }
        self.assertIsNone(apply(record, self.cfg))

    def test_excluded_room_drops_record(self) -> None:
        record = {
            "timestamp_wall": "2026-04-29T10:00:00Z",
            "room_id": "opt-out-room-1",
            "event_type": "occupancy_change",
            "confidence": 0.9,
        }
        self.assertIsNone(apply(record, self.cfg))

    def test_empty_allowlist_rejected_at_config_time(self) -> None:
        bad = {**SITE_CONFIG, "allowed_event_fields": []}
        with self.assertRaises(PrivacyFilterError):
            PrivacyConfig.from_site_config(bad)

    def test_allowlist_intersecting_forbidden_pattern_rejected(self) -> None:
        bad = {
            **SITE_CONFIG,
            "allowed_event_fields": SITE_CONFIG["allowed_event_fields"]
            + ["face_embedding"],
        }
        with self.assertRaises(PrivacyFilterError):
            PrivacyConfig.from_site_config(bad)

    def test_apply_many_filters_and_drops(self) -> None:
        records = [
            {
                "timestamp_wall": "2026-04-29T10:00:00Z",
                "site_id": "urban_large",
                "device_id": "jetson-ul-01",
                "room_id": "room-3",
                "event_type": "occupancy_change",
                "confidence": 0.9,
            },
            {"room_id": "opt-out-room-1", "event_type": "occupancy_change"},
            {"room_id": "room-3", "frame_b64": "..."},
        ]
        out = apply_many(records, self.cfg)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["room_id"], "room-3")


if __name__ == "__main__":
    unittest.main()
