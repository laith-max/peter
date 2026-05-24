# Timestamp Capture & Attestation Procedure

This document specifies how each Monte Carlo simulation run's start and
end are recorded, attested, and uplinked from the deployed Jetson Orin
Nano Super devices. It is a forward-looking procedure: it describes the
mechanism, not any particular run. Real attestation records will
accumulate in the analysis environment as runs occur; they are **not**
checked into this repository.

> **Scope note.** This procedure governs the *timing* attestation only.
> The substantive run artefacts (model parameters, validation metrics,
> architectural-change rationale) are captured separately under the
> protocol in [`data-acquisition-protocol.md`](./data-acquisition-protocol.md).

## 1. Goals

For each run we want a record that, taken together, lets a third party
verify *when* the run executed without relying on the operator's word:

- A **start marker** and **end marker** signed on-device.
- A **monotonic ↔ wall-clock pairing** so that wall-clock drift can be
  detected and corrected.
- An **NTP state snapshot** at start and end, so periods of unsynced
  operation are visible.
- A **device identity binding** so the marker cannot be replayed by a
  different device.
- An **append-only chain** so a marker cannot be silently rewritten or
  deleted after the fact.

What this procedure does **not** do: it does not prove that the
computations between markers were the ones claimed. That requires
artefact hashing (model bundle hash, dataset hash, output hash), which
is captured in the run record itself, not here.

## 2. On-Device Sources of Time

Three clocks are read at every marker:

| Clock                  | Source                                  | Used for                              |
|------------------------|-----------------------------------------|---------------------------------------|
| `CLOCK_MONOTONIC_RAW`  | Linux kernel, unaffected by NTP slew    | Duration measurement                  |
| `CLOCK_REALTIME` (UTC) | NTP-disciplined wall clock              | Human-readable wall time              |
| RTC (`/dev/rtc0`)      | Battery-backed hardware clock           | Cross-check on boot, brownout recovery|

Markers store all three plus the NTP state (`chronyc tracking`
fields: stratum, root delay, root dispersion, last offset, leap status).

## 3. Marker Format

A marker is a JSON object. Field names are stable; new fields may be
added but existing fields must not change meaning.

```jsonc
{
  "marker_type": "run_start",          // or "run_end"
  "run_id": "<uuid v4>",               // shared by start/end of one run
  "device_id": "<from site.json>",
  "site_id": "<from site.json>",
  "seq": <uint64>,                     // strictly increasing on this device
  "prev_marker_hash": "<hex sha256>",  // hash of the previous marker on this device
  "monotonic_ns": <int>,
  "wall_utc": "<RFC3339 with ns precision>",
  "rtc_utc": "<RFC3339>",
  "boot_id": "<from /proc/sys/kernel/random/boot_id>",
  "ntp": {
    "stratum": <int>,
    "leap_status": "normal" | "insert" | "delete" | "not_synchronised",
    "last_offset_seconds": <float>,
    "root_delay_seconds": <float>,
    "root_dispersion_seconds": <float>,
    "reference_id": "<string>"
  },
  "software": {
    "image_digest": "<hex sha256 of the deployed JetPack image manifest>",
    "model_bundle_digest": "<hex sha256 of the active model bundle>",
    "code_commit": "<git sha of the code that emitted the marker>"
  },
  "attestation": {
    "scheme": "ed25519-tee-v1",
    "key_id": "<device attestation key id>",
    "signature": "<base64 ed25519 signature over the canonicalised marker>"
  }
}
```

The signature covers the canonical-JSON encoding of the marker with the
`attestation.signature` field set to the empty string.

### 3.1 Step 3 Run-Block Context Fields

For Step 3 Monte Carlo runs, three additional fields extend the marker
so that downstream analysis can group runs by block and trace each block
back to the architectural change that authorised it.

```jsonc
"run_block": <uint>,                       // 1-based block index
"block_label": "<snake_case_label>",       // snake_case label fixed in the ACR
"architectural_change_ref": "<acr-id>"     // identifier of the authorising ACR
```

Field semantics:

- **`run_block`** — 1-based integer index of the block under which this
  run was scheduled. Block indices are assigned in the architectural
  change record (ACR) at the time the block opens and are never
  re-used. The historical Run Block table (Runs 1–150, 320–400,
  600–750, etc.) is the *narrative* view; `run_block` is the
  machine-readable handle.
- **`block_label`** — short snake_case label fixed in the ACR. Once a
  marker has been signed carrying a given label, the label MUST NOT be
  edited; subsequent ACRs that change the substantive configuration
  open a new block with a new label rather than mutating the old one.
- **`architectural_change_ref`** — stable identifier of the ACR that
  authorised the configuration this run executed under. ACRs live in
  the project's change-control system, not in this repo; the reference
  is what lets a third party correlate a marker with the documented
  rationale for the run's configuration.

Constraints (enforced at ingest, see §7):

- All three fields MUST be present together or absent together. A
  marker with two of three is rejected.
- `run_block` and `block_label` MUST agree with the ACR identified by
  `architectural_change_ref` as of the time the marker was signed.
- A marker MUST NOT claim membership in a block whose ACR was issued
  after the marker's `wall_utc`. There is no mechanism for a marker to
  retroactively join a block that did not exist when it was signed.

### 3.2 Scope of the Run-Block Fields

These fields capture *which authorised configuration* a run was
executed under and *which block it belongs to*. They do not:

- Establish that the architectural change was substantively justified —
  that is the ACR's review, not the marker's job.
- Establish block boundaries on their own. The mapping from run-id
  ranges to blocks is a property of the ACR sequence; any tabular
  summary (e.g. "Runs 1–150 → block 1") is a derived view over the
  marker stream and the ACR registry, not an authoritative input.

## 4. Attestation Key Material

- Each device holds an **ed25519 attestation keypair** generated inside
  the Orin Nano Super's secure element at provisioning time.
- The private key never leaves the secure element. Markers are signed
  via the secure-element API.
- The public key, the `device_id`, and the provisioning timestamp are
  recorded in the project's device registry at provisioning. The
  registry is the source of truth for verifying signatures off-device.
- **Key rotation** invalidates all subsequent markers under the old key
  unless the new public key is registered before rotation. The runbook
  for rotation is out of scope for this document and lives in the
  operations handbook.

## 5. The Append-Only Chain

Every marker references the SHA-256 of the previous marker emitted on
the same device (`prev_marker_hash`). The genesis marker for a device
uses the all-zero hash. This forms a per-device hash chain.

Properties this gives us:

- A marker cannot be silently inserted into the past without
  invalidating every subsequent `prev_marker_hash`.
- A gap in `seq` is visible at ingest and must be reconciled
  (e.g. against store-and-forward queues) before the marker is admitted.
- Deletion of a marker is detectable as a `seq`/`prev_marker_hash`
  break.

The chain is local to one device. Cross-device ordering relies on
wall-clock timestamps and is therefore weaker; analyses that require
strict cross-device ordering must say so explicitly.

## 6. Run Lifecycle

```
operator      device                              ingest endpoint
   |             |                                       |
   |--- start -->|                                       |
   |             |  emit run_start marker (signed)       |
   |             |  append to local chain                |
   |             |  enqueue for uplink ----------------> |
   |             |                                       |
   |        ... run executes ...                         |
   |             |                                       |
   |--- end --->|                                        |
   |             |  emit run_end marker (signed)         |
   |             |  append to local chain                |
   |             |  enqueue for uplink ----------------> |
   |             |                                       |
```

Operator commands enter via the local supervisor's authenticated socket;
the supervisor — not the operator's shell — is what calls the
secure-element signing API.

If the device crashes between `run_start` and `run_end`, no `run_end`
marker is produced. The run is treated as **incomplete** at ingest and
is excluded from any analysis that requires both markers. Boot-time
recovery emits a `boot` marker (not `run_end`) so the gap is visible
rather than papered over.

## 7. Uplink and Ingest

- Markers are uplinked over mTLS, batched with the same store-and-forward
  queue used for event records.
- Ingest verifies, in this order, and rejects any marker that fails:
  1. JSON-schema validity.
  2. Signature against the public key registered for `device_id`.
  3. `prev_marker_hash` matches the last accepted marker on that device
     (or zero, for the genesis marker).
  4. `seq` is exactly `last_accepted_seq + 1`.
  5. `wall_utc` is within a configured tolerance of ingest-receive time
     **after** accounting for `ntp.last_offset_seconds`.
  6. Run-block fields (§3.1) are either all present or all absent. If
     present, `architectural_change_ref` resolves to a known ACR whose
     `issued_at <= marker.wall_utc`, and the ACR's recorded
     `(run_block, block_label)` matches the marker.
- Rejections are logged with a reason code and surfaced on the ingest
  dashboard. They are not silently dropped.

## 8. Off-Device Verification

A standalone verifier at [`tools/verify_attestation.py`](../tools/verify_attestation.py)
takes a sequence of markers for one device and:

1. Recomputes each `prev_marker_hash` and checks the chain.
2. Verifies each signature against the registered public key.
3. Reports any `seq` gaps, NTP-unsynced windows, or RTC↔wall divergence
   beyond a configurable threshold.
4. Pairs `run_start` / `run_end` markers by `run_id` and reports
   incomplete runs.

The verifier produces a report; it does not modify the marker store.

## 9. What This Procedure Does Not Establish

- It does not establish that the device's wall clock was correct in
  absolute terms, only that its NTP discipline state at each marker is
  recorded and that monotonic durations between markers are accurate to
  kernel-clock precision.
- It does not establish anything about runs that pre-date the
  provisioning of a device's attestation key. Markers can only be
  trusted from the provisioning timestamp onward, which is recorded in
  the device registry.
- It does not retroactively attest to any run for which markers were
  not emitted at the time of execution. There is no mechanism in this
  procedure for back-dating a marker, and any record purporting to do so
  should be rejected at ingest.

## 10. Open Items

- Device registry schema and storage location — to be specified in the
  operations handbook; cross-link from here once it lands.
- Key-rotation runbook — likewise.
