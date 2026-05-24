# Data Acquisition & Pre-Processing Protocol

This protocol governs all multi-modal data captured by the deployed
Jetson devices. It was ratified by the project ethics committee prior to
any data collection at the four field sites; deviations require a
documented amendment, not an ad-hoc decision in the field.

## 1. Modalities and What Is Persisted

| Modality       | Captured on-device                | Persisted / uplinked                        |
|----------------|-----------------------------------|---------------------------------------------|
| Video          | 1080p30, wide-angle, room-mounted | Event records + per-minute occupancy counts |
| Audio          | 16 kHz mono, ceiling mic          | Activity-class labels (not speech content)  |
| Environmental  | Temp, humidity, lux, CO₂          | 1 Hz scalar series                          |
| Device health  | tegrastats, thermal, clock drift  | 1 Hz scalar series                          |
| Roster context | From governance dataset (offline) | Joined post-hoc, never on-device            |

Raw video and raw audio are explicitly **not** persisted. See the
[privacy boundary](./jetson-processing.md#privacy-boundary).

## 2. Consent and Notification

- **Parents / guardians** were notified in writing prior to deployment;
  opt-out rooms are configured in `jetson-logging/config/site.json`
  (`excluded_rooms:`) and the device refuses to enable any vision/audio
  modality in those rooms.
- **Educators** were briefed in person and provided written consent for
  workforce-relevant data (proximity, room movement). Educators may
  invoke a "pause" via a physical button at the device; pause events are
  themselves logged (timestamp + room only).
- **Visitors** are covered by signage at the centre entrance and at each
  monitored room. The signage text is checked into
  `docs/signage/` (to be added when finalised by the ethics committee).

## 3. Pre-Processing on Device

1. **Sensor → frame buffer** in pinned GPU memory; never written to disk.
2. **Inference** (TensorRT engines) → raw model outputs.
3. **Privacy filter** ([`filters/privacy.py`](../jetson-logging/filters/privacy.py))
   — single chokepoint. Drops anything not on the allow-list of fields.
4. **Event aggregation** — per-minute bins, event records with
   confidence ≥ configured threshold.
5. **Local sink** — append-only encrypted log on the device's eMMC.
6. **Uplink** — mTLS batched upload every N minutes (configurable),
   with store-and-forward if the link is down.

## 4. Pre-Processing Off Device

Off-device pre-processing is performed in a controlled analysis
environment, not on operator workstations. Steps:

- Schema validation against the event record JSON schema
  (`jetson-logging/config/event_schema.json`).
- Join to the governance dataset on `(site_id, room_id, timestamp)`.
- Time alignment: device monotonic clock → wall clock via the recorded
  drift offset; events outside ±2 s tolerance are flagged, not dropped.
- De-duplication on `(device_id, event_id)` — events may be re-uploaded
  after a network outage and the ingest endpoint is idempotent.

## 5. Retention

| Artefact                       | On device     | In analysis env       |
|--------------------------------|---------------|-----------------------|
| Raw sensor streams             | Not persisted | Never received        |
| Encrypted local event log      | 14 days       | n/a                   |
| Uplinked event records         | n/a           | 5 years (per ethics)  |
| Aggregate / derived datasets   | n/a           | 5 years               |
| Device health / `tegrastats`   | 14 days       | 5 years               |

Retention enforcement on-device is implemented in
[`jetson-logging/retention.py`](../jetson-logging/retention.py).

## 6. Access Control

- On-device logs are encrypted at rest (LUKS-backed `/var/log/jetson/`,
  key sealed to the Orin Nano Super's TPM-equivalent secure element).
- Analysis-environment access is role-based: site-level identifiers are
  visible only to two named investigators; all other team members work
  against the pseudonymised dataset.

## 7. Incidents

Any event suggesting the privacy boundary may have been crossed
(e.g. an unexpected file containing raw frames, a model bundle that
fails signature verification, a privacy-filter self-test failure)
triggers an incident workflow:

1. The device is placed in **safe mode** (inference halted, uplink
   halted, local log sealed).
2. The incident is reported to the ethics committee within 72 hours.
3. No data captured during the suspect window is used in analysis until
   the incident is closed.
