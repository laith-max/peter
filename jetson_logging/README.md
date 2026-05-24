# jetson-logging

Device-side logging, privacy filtering, and retention for the ECEC
field-test deployment on NVIDIA Jetson Orin Nano Super hardware.

This module is the **only** path between the inference pipeline and any
durable storage or network sink on the device. If a record was not
emitted through `filters.privacy.apply()`, it must not be written or
uplinked. See [`docs/data-acquisition-protocol.md`](../docs/data-acquisition-protocol.md).

## Layout

```
jetson-logging/
├── collectors/
│   └── tegrastats.py     # device-health collector (1 Hz)
├── filters/
│   └── privacy.py        # the privacy chokepoint
├── config.py             # site-config loader + validator
├── config/
│   ├── site.json         # per-device site/room/excluded-room config (template)
│   └── event_schema.json # JSON schema for emitted event records
├── retention.py          # on-device retention sweeper
└── tests/
    ├── fixtures/site.valid.json
    ├── test_privacy.py   # privacy-filter self-tests
    ├── test_config.py    # config loader/validator tests
    └── test_retention.py # retention sweeper tests
```

## Boot gate

`python -m jetson_logging` is the boot gate the supervisor relies on. It
**loads and validates the real `config/site.json`**, then runs the
privacy-filter self-tests. A non-zero exit is a refusal to start the
inference pipeline:

- an unconfigured or misconfigured device fails config validation (e.g. a
  template placeholder, an empty `excluded_rooms`, an allow-listed field
  that matches a forbidden pattern);
- a broken filter fails the self-tests.

This is the same command used by the Docker `HEALTHCHECK`, so the shipped
placeholder template intentionally fails until the device is configured.

Run the pieces directly during development:

```
python -m unittest discover -s jetson_logging/tests -t .
JETSON_LOGGING_CONFIG=jetson_logging/tests/fixtures/site.valid.json python -m jetson_logging
```

## Configuration

Per-device configuration lives in `config/site.json` (one file per
Jetson). The committed file is a **template** with `REPLACE_ME` /
`example-room-id` placeholders; the device refuses to start until they are
replaced. The path can be overridden with `JETSON_LOGGING_CONFIG`.

| Field | Type | Notes |
|-------|------|-------|
| `site_id` | string | One of `urban_large`, `urban_small`, `regional_large`, `regional_small`. |
| `device_id` | string | Short stable id, e.g. `jetson-ul-01`. |
| `excluded_rooms` | string[] | Opt-out rooms; vision/audio stay disabled. Matched case-insensitively after stringifying. Must be non-empty and free of placeholders. |
| `event_confidence_floor` | number 0–1 | Events with `confidence` below this are dropped by the filter. |
| `local_retention_days` | int > 0 | Retention window used by `retention.py`. |
| `aggregate_bin_seconds` | int | Per-minute aggregate bin size. |
| `uplink_interval_seconds` | int | Uplink batch interval (store-and-forward if the link is down). |
| `allowed_event_fields` | string[] | Allow-list of fields permitted to leave the pipeline; everything else is stripped. Must cover the event schema's required fields. |
| `forbidden_field_patterns` | string[] | Tokens that must never appear in a record (any key at any depth, or any allow-listed value). Validation rejects any allow-listed field matching one. |

Required fields (`site_id`, `device_id`, `excluded_rooms`,
`allowed_event_fields`, `forbidden_field_patterns`,
`event_confidence_floor`, `local_retention_days`) are checked at boot by
`config.validate()`.

## Retention

Run from a systemd timer once per hour. With no `--days` the window is read
from `local_retention_days` in the validated site config:

```
python -m jetson_logging.retention /var/log/jetson
```

Symlinks under the log directory are never followed or removed.
