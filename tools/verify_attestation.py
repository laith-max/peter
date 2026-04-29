"""Off-device verifier for Jetson attestation markers.

Implements §8 of docs/timestamp-attestation-procedure.md:

  1. Recompute each prev_marker_hash and check the chain.
  2. Verify each signature against the registered public key.
  3. Report seq gaps, NTP-unsynced windows, RTC <-> wall divergence
     beyond a configurable threshold.
  4. Pair run_start / run_end markers by run_id and report incomplete
     runs.

The verifier produces a report; it does not modify the marker store.

Signatures use ed25519 (scheme "ed25519-tee-v1"). Verification uses
PyNaCl when available; if PyNaCl is not installed, signature checks
are skipped and a warning is added to the report rather than letting
the verifier silently pass.

Canonical-JSON encoding for hashing/signing matches RFC 8785 (JCS):
  - sort object keys lexicographically
  - no insignificant whitespace
  - UTF-8 output
  - signature field cleared to "" before encoding for both hash and
    signature verification

Usage:
  python -m tools.verify_attestation \
      --markers path/to/markers.jsonl \
      --registry path/to/device_registry.json \
      [--rtc-tolerance-s 5.0] \
      [--ntp-max-stratum 4]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


GENESIS_HASH = "0" * 64
SCHEME = "ed25519-tee-v1"


# ---------------------------------------------------------------------------
# Canonical JSON (RFC 8785 / JCS-compatible for the subset we use)
# ---------------------------------------------------------------------------


def _canonicalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonicalise(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalise(v) for v in value]
    return value


def canonical_json(marker: dict[str, Any]) -> bytes:
    return json.dumps(
        _canonicalise(marker),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")


def marker_payload_for_hashing(marker: dict[str, Any]) -> bytes:
    """Canonical bytes used for both hashing and signature verification.

    The signature field is cleared before encoding so that the same
    bytes can be reproduced after the marker is signed.
    """
    payload = json.loads(json.dumps(marker))  # deep copy via JSON roundtrip
    if "attestation" in payload and isinstance(payload["attestation"], dict):
        payload["attestation"]["signature"] = ""
    return canonical_json(payload)


def marker_hash(marker: dict[str, Any]) -> str:
    return hashlib.sha256(marker_payload_for_hashing(marker)).hexdigest()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceEntry:
    device_id: str
    public_key_b64: str
    provisioned_at: datetime


def load_registry(path: Path) -> dict[str, DeviceEntry]:
    raw = json.loads(path.read_text())
    out: dict[str, DeviceEntry] = {}
    for entry in raw.get("devices", []):
        out[entry["device_id"]] = DeviceEntry(
            device_id=entry["device_id"],
            public_key_b64=entry["public_key_b64"],
            provisioned_at=datetime.fromisoformat(
                entry["provisioned_at"].replace("Z", "+00:00")
            ),
        )
    return out


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def _try_import_nacl():
    try:
        from nacl.signing import VerifyKey  # type: ignore
        from nacl.exceptions import BadSignatureError  # type: ignore
        return VerifyKey, BadSignatureError
    except ImportError:
        return None, None


def verify_signature(
    marker: dict[str, Any],
    entry: DeviceEntry,
    *,
    nacl_classes=None,
) -> tuple[bool, str]:
    if nacl_classes is None:
        nacl_classes = _try_import_nacl()
    VerifyKey, BadSignatureError = nacl_classes
    if VerifyKey is None:
        return False, "pynacl not installed; signature not verified"

    att = marker.get("attestation") or {}
    if att.get("scheme") != SCHEME:
        return False, f"unexpected scheme {att.get('scheme')!r}"
    sig_b64 = att.get("signature") or ""
    try:
        sig = base64.b64decode(sig_b64)
        pub = base64.b64decode(entry.public_key_b64)
    except (ValueError, TypeError) as e:
        return False, f"base64 decode error: {e}"

    try:
        VerifyKey(pub).verify(marker_payload_for_hashing(marker), sig)
        return True, ""
    except BadSignatureError:
        return False, "signature does not verify"
    except Exception as e:  # surface the real reason rather than swallow
        return False, f"signature verification error: {e}"


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    code: str
    detail: str
    marker_seq: int | None = None
    device_id: str | None = None


@dataclass
class VerifyReport:
    issues: list[Issue] = field(default_factory=list)
    accepted_count: int = 0
    rejected_count: int = 0
    incomplete_run_ids: list[str] = field(default_factory=list)
    devices_seen: set[str] = field(default_factory=set)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    def ok(self) -> bool:
        return not self.errors and not self.incomplete_run_ids


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


@dataclass
class VerifyOptions:
    rtc_tolerance_s: float = 5.0
    ntp_max_stratum: int = 4
    require_signatures: bool = True


def _parse_iso(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def verify_markers(
    markers: Iterable[dict[str, Any]],
    registry: dict[str, DeviceEntry],
    options: VerifyOptions | None = None,
) -> VerifyReport:
    opts = options or VerifyOptions()
    report = VerifyReport()
    nacl_classes = _try_import_nacl()
    if opts.require_signatures and nacl_classes[0] is None:
        report.add(
            Issue(
                severity="warning",
                code="nacl_missing",
                detail="pynacl not installed; signatures will not be verified",
            )
        )

    last_by_device: dict[str, dict[str, Any]] = {}
    seen_run_starts: dict[str, dict[str, Any]] = {}
    seen_run_ends: dict[str, dict[str, Any]] = {}

    for marker in markers:
        device_id = marker.get("device_id", "<missing>")
        seq = marker.get("seq")
        report.devices_seen.add(device_id)

        # 1. Chain check.
        prev = last_by_device.get(device_id)
        expected_prev_hash = marker_hash(prev) if prev else GENESIS_HASH
        if marker.get("prev_marker_hash") != expected_prev_hash:
            report.add(
                Issue(
                    severity="error",
                    code="chain_break",
                    detail=(
                        f"prev_marker_hash mismatch (expected {expected_prev_hash[:12]}…, "
                        f"got {str(marker.get('prev_marker_hash'))[:12]}…)"
                    ),
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
            report.rejected_count += 1
            # We still try the rest of the checks for diagnostic value,
            # but do not advance last_by_device on a broken chain.
            continue

        # 2. Sequence check.
        if prev is not None and seq != prev.get("seq", -1) + 1:
            report.add(
                Issue(
                    severity="error",
                    code="seq_gap",
                    detail=(
                        f"seq {seq} expected {prev.get('seq', -1) + 1}"
                    ),
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
            report.rejected_count += 1
            continue
        if prev is None and seq != 0:
            report.add(
                Issue(
                    severity="error",
                    code="genesis_seq",
                    detail=f"genesis seq must be 0 (got {seq})",
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
            report.rejected_count += 1
            continue

        # 3. Signature check.
        entry = registry.get(device_id)
        if entry is None:
            report.add(
                Issue(
                    severity="error",
                    code="unknown_device",
                    detail=f"device {device_id!r} not in registry",
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
            report.rejected_count += 1
            continue

        if opts.require_signatures and nacl_classes[0] is not None:
            ok, why = verify_signature(marker, entry, nacl_classes=nacl_classes)
            if not ok:
                report.add(
                    Issue(
                        severity="error",
                        code="bad_signature",
                        detail=why,
                        marker_seq=seq if isinstance(seq, int) else None,
                        device_id=device_id,
                    )
                )
                report.rejected_count += 1
                continue

        # 4. Provisioning window.
        wall = _parse_iso(marker.get("wall_utc", ""))
        if wall is not None and wall < entry.provisioned_at:
            report.add(
                Issue(
                    severity="error",
                    code="pre_provisioning",
                    detail=(
                        f"wall_utc {wall.isoformat()} predates provisioning "
                        f"{entry.provisioned_at.isoformat()}"
                    ),
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
            report.rejected_count += 1
            continue

        # 5. NTP / RTC checks (warnings, not rejections).
        ntp = marker.get("ntp") or {}
        if ntp.get("leap_status") == "not_synchronised":
            report.add(
                Issue(
                    severity="warning",
                    code="ntp_unsynced",
                    detail="leap_status=not_synchronised at marker emission",
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )
        elif isinstance(ntp.get("stratum"), int) and ntp["stratum"] > opts.ntp_max_stratum:
            report.add(
                Issue(
                    severity="warning",
                    code="ntp_high_stratum",
                    detail=f"stratum {ntp['stratum']} > {opts.ntp_max_stratum}",
                    marker_seq=seq if isinstance(seq, int) else None,
                    device_id=device_id,
                )
            )

        rtc = _parse_iso(marker.get("rtc_utc", ""))
        if wall is not None and rtc is not None:
            divergence_s = abs((wall - rtc).total_seconds())
            if divergence_s > opts.rtc_tolerance_s:
                report.add(
                    Issue(
                        severity="warning",
                        code="rtc_divergence",
                        detail=(
                            f"rtc-wall divergence {divergence_s:.2f}s > "
                            f"{opts.rtc_tolerance_s:.2f}s"
                        ),
                        marker_seq=seq if isinstance(seq, int) else None,
                        device_id=device_id,
                    )
                )

        # 6. Run pairing.
        run_id = marker.get("run_id")
        if run_id and marker.get("marker_type") == "run_start":
            seen_run_starts[run_id] = marker
        if run_id and marker.get("marker_type") == "run_end":
            seen_run_ends[run_id] = marker

        last_by_device[device_id] = marker
        report.accepted_count += 1

    # 7. Incomplete runs.
    for run_id in seen_run_starts.keys() - seen_run_ends.keys():
        report.incomplete_run_ids.append(run_id)
        report.add(
            Issue(
                severity="warning",
                code="incomplete_run",
                detail=f"run_id {run_id} has run_start but no run_end",
            )
        )

    return report


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: invalid JSON: {e}") from e


def render_report(report: VerifyReport) -> str:
    lines: list[str] = []
    lines.append(
        f"accepted={report.accepted_count} rejected={report.rejected_count} "
        f"devices={len(report.devices_seen)} "
        f"errors={len(report.errors)} warnings={len(report.warnings)} "
        f"incomplete_runs={len(report.incomplete_run_ids)}"
    )
    for issue in report.issues:
        loc = ""
        if issue.device_id is not None:
            loc += f" device={issue.device_id}"
        if issue.marker_seq is not None:
            loc += f" seq={issue.marker_seq}"
        lines.append(f"  [{issue.severity}] {issue.code}{loc}: {issue.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Verify Jetson attestation markers (off-device).",
    )
    p.add_argument("--markers", required=True, type=Path, help="JSONL of markers")
    p.add_argument("--registry", required=True, type=Path, help="device registry JSON")
    p.add_argument("--rtc-tolerance-s", type=float, default=5.0)
    p.add_argument("--ntp-max-stratum", type=int, default=4)
    p.add_argument(
        "--skip-signatures",
        action="store_true",
        help="skip signature verification (use only when pynacl is unavailable)",
    )
    args = p.parse_args(argv)

    registry = load_registry(args.registry)
    options = VerifyOptions(
        rtc_tolerance_s=args.rtc_tolerance_s,
        ntp_max_stratum=args.ntp_max_stratum,
        require_signatures=not args.skip_signatures,
    )
    report = verify_markers(iter_jsonl(args.markers), registry, options)
    print(render_report(report))
    return 0 if report.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
