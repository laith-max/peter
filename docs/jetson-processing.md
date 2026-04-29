# On-Device Processing — NVIDIA Jetson Orin Nano Super

## Hardware Selection

On-device processing was performed on NVIDIA Jetson Orin Nano Super edge
computing hardware (8 GB LPDDR5, 67 TOPS sparse INT8, 1024-core Ampere
GPU with 32 tensor cores, 6-core Arm Cortex-A78AE CPU). The Orin Nano
Super was selected over comparable embedded accelerators (Coral Edge TPU,
Hailo-8) on three grounds:

1. **Inference headroom for multi-modal models.** The deployment runs
   audio activity classification, visual room-occupancy estimation, and a
   pose/proximity model concurrently. The Super profile (25 W MAXN_SUPER)
   sustains all three at the target frame rates without thermal
   throttling under typical centre ambient conditions (22–28 °C).
2. **CUDA/TensorRT toolchain parity** with the lab development
   environment, which removed an entire class of "works on the bench,
   fails on the device" model-conversion bugs from the deployment risk
   register.
3. **Local-only inference.** All raw sensor streams are processed
   on-device; only de-identified feature vectors and event records are
   persisted or transmitted (see [Privacy boundary](#privacy-boundary)).
   This is a hard requirement of the ethics approval, not a performance
   optimisation, and a less capable accelerator would have forced
   off-device processing for at least one modality.

## Software Stack

| Layer            | Component                                   |
|------------------|---------------------------------------------|
| OS               | JetPack 6.x (L4T 36.x, Ubuntu 22.04)        |
| Runtime          | CUDA 12.x, cuDNN 9.x, TensorRT 10.x         |
| Inference        | DeepStream 7.x for video; ONNX Runtime for audio |
| Orchestration    | systemd units per modality + a supervisor   |
| Logging          | `jetson-logging/` (this repo)               |
| Telemetry uplink | mTLS to the project ingest endpoint         |

Models are converted to TensorRT engines pinned to the specific Orin Nano
Super SM (`sm_87`); engines are rebuilt on-device at first boot to bind
to the actual GPU clock profile rather than shipped pre-built.

## Privacy Boundary

The device enforces a strict on-device boundary:

- **Raw video frames** never leave the device, never touch persistent
  storage. Frames are processed in a ring buffer in GPU memory and
  overwritten in place.
- **Raw audio** is windowed (1 s frames), classified, and discarded.
  No PCM, no spectrograms, and no embeddings that could be inverted to
  speech are persisted.
- **Outputs** are reduced to event records (timestamp, room id,
  event type, confidence) and aggregate counts (per-minute activity
  bins). These are the only artefacts written to disk or uplinked.

The privacy filter that enforces this is implemented in
[`jetson-logging/filters/privacy.py`](../jetson-logging/filters/privacy.py)
and is the single chokepoint between the inference pipeline and any
durable sink.

## Failure Modes Considered

- **Thermal throttling** — devices are mounted with the reference active
  cooler; `tegrastats` thermal samples are logged and used as a covariate
  in any latency analysis.
- **Power events** — sites without UPS receive a brown-out-tolerant PSU;
  on unexpected reboot the supervisor refuses to start inference until
  the privacy filter self-test passes.
- **Clock drift** — devices NTP-sync to a project-controlled stratum-2
  source; event timestamps include both the device monotonic clock and
  the wall clock so post-hoc drift correction is possible.
- **Model staleness** — model bundles are signed; the device refuses
  unsigned bundles and refuses to roll back to bundles older than the
  current deployment without an explicit operator override.
