"""Tests for the on-device retention sweeper."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from jetson_logging import retention


class SweepTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.now = time.time()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make(self, name: str, age_days: float) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        mtime = self.now - age_days * 86400
        os.utime(path, (mtime, mtime))
        return path

    def test_deletes_old_keeps_recent(self) -> None:
        old = self._make("old.log", age_days=20)
        recent = self._make("recent.log", age_days=2)
        removed = retention.sweep(self.dir, 14, now=self.now)
        self.assertEqual(removed, [old])
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_prunes_empty_dirs(self) -> None:
        self._make("sub/old.log", age_days=20)
        retention.sweep(self.dir, 14, now=self.now)
        self.assertFalse((self.dir / "sub").exists())

    def test_missing_dir_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            retention.sweep(self.dir / "nope", 14)

    def test_nonpositive_days_raises(self) -> None:
        with self.assertRaises(ValueError):
            retention.sweep(self.dir, 0)

    def test_skips_symlinks(self) -> None:
        outside = Path(self._tmp.name).parent / "outside_target.log"
        outside.write_text("keep me", encoding="utf-8")
        old_mtime = self.now - 100 * 86400
        os.utime(outside, (old_mtime, old_mtime))
        try:
            link = self.dir / "link.log"
            link.symlink_to(outside)
            removed = retention.sweep(self.dir, 14, now=self.now)
            self.assertEqual(removed, [])
            self.assertTrue(outside.exists())
            self.assertTrue(link.is_symlink())
        finally:
            outside.unlink(missing_ok=True)

    def test_main_reads_days_from_config(self) -> None:
        fixture = Path(__file__).resolve().parent / "fixtures" / "site.valid.json"
        old = self._make("old.log", age_days=20)
        recent = self._make("recent.log", age_days=2)
        prev = os.environ.get("JETSON_LOGGING_CONFIG")
        os.environ["JETSON_LOGGING_CONFIG"] = str(fixture)
        try:
            rc = retention.main([str(self.dir)])  # no --days -> config's 14
        finally:
            if prev is None:
                os.environ.pop("JETSON_LOGGING_CONFIG", None)
            else:
                os.environ["JETSON_LOGGING_CONFIG"] = prev
        self.assertEqual(rc, 0)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())


if __name__ == "__main__":
    unittest.main()
