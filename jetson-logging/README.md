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
├── config/
│   ├── site.yaml         # per-device site/room/excluded-room config
│   └── event_schema.json # JSON schema for emitted event records
├── retention.py          # on-device retention sweeper
└── tests/
    └── test_privacy.py   # privacy-filter self-tests
```

## Privacy filter self-test

The privacy filter ships a self-test that runs at boot via a systemd
unit (`jetson-logging-selftest.service`). If the self-test fails the
supervisor refuses to start the inference pipeline. To run it manually:

```
python3 -m jetson_logging.tests.test_privacy
```

## Configuration

Per-device configuration lives in `config/site.yaml`. The fields
`site_id`, `device_id`, and `excluded_rooms` are required; the device
refuses to start if any of them is missing or empty.
