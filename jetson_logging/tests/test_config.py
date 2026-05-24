"""Tests for site-config loading and validation.

These prove the boot gate actually trips: the shipped placeholder template
must fail validation, and each class of misconfiguration must raise.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jetson_logging import config

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "site.valid.json"
TEMPLATE = Path(__file__).resolve().parents[1] / "config" / "site.json"
SCHEMA = Path(__file__).resolve().parents[1] / "config" / "event_schema.json"


class LoadRawTests(unittest.TestCase):
    def test_missing_file_raises(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load_raw(Path("/nonexistent/site.json"))

    def test_invalid_json_raises(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as f:
            f.write("{ not json ")
            f.flush()
            with self.assertRaises(config.ConfigError):
                config.load_raw(f.name)

    def test_non_object_raises(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True) as f:
            f.write("[1, 2, 3]")
            f.flush()
            with self.assertRaises(config.ConfigError):
                config.load_raw(f.name)


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = config.load_raw(FIXTURE)

    def test_valid_fixture_passes(self) -> None:
        config.validate(self.cfg)  # must not raise

    def test_shipped_template_is_rejected(self) -> None:
        # The committed template still has placeholders, so an unconfigured
        # device must fail the gate.
        with self.assertRaises(config.ConfigError):
            config.validate(config.load_raw(TEMPLATE))

    def test_missing_site_id_rejected(self) -> None:
        del self.cfg["site_id"]
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_placeholder_device_id_rejected(self) -> None:
        self.cfg["device_id"] = "REPLACE_ME"
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_bad_site_id_enum_rejected(self) -> None:
        self.cfg["site_id"] = "lunar_base"
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_empty_excluded_rooms_rejected(self) -> None:
        self.cfg["excluded_rooms"] = []
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_placeholder_in_excluded_rooms_rejected(self) -> None:
        self.cfg["excluded_rooms"] = ["example-room-id"]
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_confidence_floor_out_of_range_rejected(self) -> None:
        self.cfg["event_confidence_floor"] = 1.5
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_confidence_floor_bool_rejected(self) -> None:
        self.cfg["event_confidence_floor"] = True
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)

    def test_nonpositive_retention_rejected(self) -> None:
        self.cfg["local_retention_days"] = 0
        with self.assertRaises(config.ConfigError):
            config.validate(self.cfg)


class SchemaSyncTests(unittest.TestCase):
    def test_site_ids_match_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        enum = set(schema["properties"]["site_id"]["enum"])
        self.assertEqual(set(config.SITE_IDS), enum)


if __name__ == "__main__":
    unittest.main()
