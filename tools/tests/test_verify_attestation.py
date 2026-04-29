"""Tests for tools/verify_attestation.py.

All marker data here is generated in-process by tools.tests.fixtures.synthetic
and is explicitly NOT from any real device.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.verify_attestation import (
    GENESIS_HASH,
    VerifyOptions,
    marker_hash,
    verify_markers,
)
from tools.tests.fixtures.synthetic import (
    make_chain,
    make_registry,
    make_signer,
    sign_marker,
)


def _registry_from_signer(public_key_b64: str, device_id: str = "test-device-1"):
    raw = make_registry(
        device_id,
        public_key_b64,
        provisioned_before=datetime(2099, 1, 1, tzinfo=timezone.utc) - timedelta(days=1),
    )
    from tools.verify_attestation import DeviceEntry

    out = {}
    for entry in raw["devices"]:
        out[entry["device_id"]] = DeviceEntry(
            device_id=entry["device_id"],
            public_key_b64=entry["public_key_b64"],
            provisioned_at=datetime.fromisoformat(
                entry["provisioned_at"].replace("Z", "+00:00")
            ),
        )
    return out


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.sk, self.pub = make_signer()
        self.registry = _registry_from_signer(self.pub)

    def test_clean_chain_passes(self):
        chain = make_chain(self.sk)
        report = verify_markers(chain, self.registry)
        self.assertEqual(report.rejected_count, 0)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.incomplete_run_ids, [])
        self.assertTrue(report.ok())

    def test_chain_break_detected(self):
        chain = make_chain(self.sk)
        chain[2]["prev_marker_hash"] = "f" * 64  # tamper
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.errors}
        self.assertIn("chain_break", codes)
        self.assertFalse(report.ok())

    def test_seq_gap_detected(self):
        chain = make_chain(self.sk)
        # Drop the second marker, then re-sign the third with corrected
        # prev_marker_hash so chain_break doesn't mask the seq gap.
        del chain[1]
        chain[1]["prev_marker_hash"] = marker_hash(chain[0])
        chain[1] = sign_marker(chain[1], self.sk)
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.errors}
        self.assertIn("seq_gap", codes)

    def test_bad_signature_detected(self):
        chain = make_chain(self.sk)
        # Flip a bit inside an otherwise-signed marker without resigning.
        chain[1]["site_id"] = "urban_small"
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.errors}
        self.assertTrue("bad_signature" in codes or "chain_break" in codes)

    def test_unknown_device_rejected(self):
        chain = make_chain(self.sk, device_id="rogue-device")
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.errors}
        self.assertIn("unknown_device", codes)

    def test_pre_provisioning_rejected(self):
        chain = make_chain(self.sk)
        # Move provisioning to AFTER the markers' wall time.
        from tools.verify_attestation import DeviceEntry

        late_registry = {
            "test-device-1": DeviceEntry(
                device_id="test-device-1",
                public_key_b64=self.pub,
                provisioned_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
            )
        }
        report = verify_markers(chain, late_registry)
        codes = {i.code for i in report.errors}
        self.assertIn("pre_provisioning", codes)

    def test_incomplete_run_warned(self):
        chain = make_chain(self.sk)
        # Find run_id of last run, drop its run_end, re-stitch chain.
        end_idx = max(
            i for i, m in enumerate(chain) if m["marker_type"] == "run_end"
        )
        del chain[end_idx]
        report = verify_markers(chain, self.registry)
        self.assertGreaterEqual(len(report.incomplete_run_ids), 1)
        codes = {i.code for i in report.warnings}
        self.assertIn("incomplete_run", codes)

    def test_ntp_unsynced_warning(self):
        chain = make_chain(self.sk)
        # Re-emit the boot marker with leap_status not_synchronised.
        chain[0]["ntp"]["leap_status"] = "not_synchronised"
        chain[0] = sign_marker(chain[0], self.sk)
        # Re-stitch downstream prev hashes + signatures.
        for i in range(1, len(chain)):
            chain[i]["prev_marker_hash"] = marker_hash(chain[i - 1])
            chain[i] = sign_marker(chain[i], self.sk)
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.warnings}
        self.assertIn("ntp_unsynced", codes)

    def test_rtc_divergence_warning(self):
        chain = make_chain(self.sk)
        # Skew rtc_utc on the boot marker by 30 seconds.
        wall = chain[0]["wall_utc"]
        from datetime import datetime as dt

        skewed = (
            dt.fromisoformat(wall.replace("Z", "+00:00")) + timedelta(seconds=30)
        ).isoformat().replace("+00:00", "Z")
        chain[0]["rtc_utc"] = skewed
        chain[0] = sign_marker(chain[0], self.sk)
        for i in range(1, len(chain)):
            chain[i]["prev_marker_hash"] = marker_hash(chain[i - 1])
            chain[i] = sign_marker(chain[i], self.sk)
        report = verify_markers(
            chain, self.registry, VerifyOptions(rtc_tolerance_s=5.0)
        )
        codes = {i.code for i in report.warnings}
        self.assertIn("rtc_divergence", codes)

    def test_genesis_hash_required(self):
        chain = make_chain(self.sk)
        chain[0]["prev_marker_hash"] = "1" * 64  # not the all-zero genesis
        chain[0] = sign_marker(chain[0], self.sk)
        report = verify_markers(chain, self.registry)
        codes = {i.code for i in report.errors}
        self.assertIn("chain_break", codes)


if __name__ == "__main__":
    unittest.main()
