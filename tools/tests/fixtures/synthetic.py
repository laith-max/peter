"""Synthetic marker generator for verifier tests.

SYNTHETIC — NOT FROM A REAL DEVICE.
=====================================================================
Every marker produced by this module is signed with an in-process
ed25519 keypair generated at test time. These artefacts have no
provenance and MUST NOT be presented as evidence of any real Monte
Carlo run, deployment, or device. They exist solely to drive the unit
tests for tools/verify_attestation.py.
=====================================================================
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from nacl.signing import SigningKey

from tools.verify_attestation import GENESIS_HASH, SCHEME, marker_hash, marker_payload_for_hashing


def make_signer() -> tuple[SigningKey, str]:
    sk = SigningKey.generate()
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode("ascii")
    return sk, pub_b64


def sign_marker(marker: dict[str, Any], sk: SigningKey) -> dict[str, Any]:
    marker = json.loads(json.dumps(marker))
    marker.setdefault("attestation", {})
    marker["attestation"]["scheme"] = SCHEME
    marker["attestation"]["key_id"] = "test-key-1"
    marker["attestation"]["signature"] = ""
    payload = marker_payload_for_hashing(marker)
    sig = sk.sign(payload).signature
    marker["attestation"]["signature"] = base64.b64encode(sig).decode("ascii")
    return marker


def make_chain(
    sk: SigningKey,
    *,
    device_id: str = "test-device-1",
    site_id: str = "urban_large",
    start_wall: datetime | None = None,
    runs: list[tuple[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Build a valid signed chain: one boot marker, then run_start/run_end pairs.

    `runs` is a list of (run_id, duration_seconds). If None, two short
    runs are emitted.
    """
    if start_wall is None:
        start_wall = datetime(2099, 1, 1, tzinfo=timezone.utc)
    if runs is None:
        runs = [(str(uuid.uuid4()), 0.5), (str(uuid.uuid4()), 1.0)]

    chain: list[dict[str, Any]] = []
    seq = 0
    prev_hash = GENESIS_HASH
    wall = start_wall
    monotonic_ns = 0

    def base(marker_type: str, run_id: str | None = None) -> dict[str, Any]:
        nonlocal seq, prev_hash, wall, monotonic_ns
        m: dict[str, Any] = {
            "marker_type": marker_type,
            "device_id": device_id,
            "site_id": site_id,
            "seq": seq,
            "prev_marker_hash": prev_hash,
            "monotonic_ns": monotonic_ns,
            "wall_utc": wall.isoformat().replace("+00:00", "Z"),
            "rtc_utc": wall.isoformat().replace("+00:00", "Z"),
            "boot_id": "00000000-0000-0000-0000-000000000001",
            "ntp": {
                "stratum": 2,
                "leap_status": "normal",
                "last_offset_seconds": 0.001,
                "root_delay_seconds": 0.005,
                "root_dispersion_seconds": 0.002,
                "reference_id": "TEST",
            },
            "software": {
                "image_digest": "0" * 64,
                "model_bundle_digest": "0" * 64,
                "code_commit": "0" * 40,
            },
        }
        if run_id is not None:
            m["run_id"] = run_id
        return m

    boot = sign_marker(base("boot"), sk)
    chain.append(boot)
    prev_hash = marker_hash(boot)
    seq += 1
    wall += timedelta(seconds=1)
    monotonic_ns += 1_000_000_000

    for run_id, duration_s in runs:
        s = sign_marker(base("run_start", run_id), sk)
        chain.append(s)
        prev_hash = marker_hash(s)
        seq += 1
        wall += timedelta(seconds=duration_s)
        monotonic_ns += int(duration_s * 1e9)

        e = sign_marker(base("run_end", run_id), sk)
        chain.append(e)
        prev_hash = marker_hash(e)
        seq += 1
        wall += timedelta(seconds=0.5)
        monotonic_ns += 500_000_000

    return chain


def make_registry(device_id: str, public_key_b64: str, *, provisioned_before: datetime) -> dict[str, Any]:
    return {
        "devices": [
            {
                "device_id": device_id,
                "public_key_b64": public_key_b64,
                "provisioned_at": provisioned_before.isoformat().replace("+00:00", "Z"),
            }
        ]
    }
