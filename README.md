# peter

Field-test deployment of AI monitoring devices across four ECEC centres
in NSW, running on NVIDIA Jetson Orin Nano Super edge hardware.

## Layout

- [`docs/methodology.md`](docs/methodology.md) — site selection (2 × 2
  urban/regional × large/small), governance dataset sources, study design
  rationale.
- [`docs/jetson-processing.md`](docs/jetson-processing.md) — hardware and
  software stack on the Orin Nano Super, privacy boundary, failure
  modes considered.
- [`docs/data-acquisition-protocol.md`](docs/data-acquisition-protocol.md)
  — what is captured, what is persisted, consent and notification,
  retention, access control, incident workflow.
- [`jetson-logging/`](jetson-logging/) — device-side logging, privacy
  filter (the chokepoint), tegrastats collector, retention sweeper, and
  self-tests that gate the inference pipeline at boot.

## Privacy posture (read this first)

Raw video and raw audio are processed on-device and never persisted or
uplinked. Only event records and aggregates pass the privacy filter in
[`jetson-logging/filters/privacy.py`](jetson-logging/filters/privacy.py).
The supervisor refuses to start inference if the filter's self-tests
fail at boot.
