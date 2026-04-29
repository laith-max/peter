"""Mobile-robot reference stack.

Package layout:
  config       — frozen dataclasses for physical params, limits, gains
  dynamics     — plant model (placeholder; not the Rev B^4 port)
  planner      — occupancy grid + A* + smoothing
  control      — waypoint follower
  perception   — TensorRT + Mock detectors
  safety       — compliance monitor + clamp
  hal          — JetsonHAL + MockHAL + make_hal()
  main         — 3-rate cooperative loop entrypoint

Designed so the package imports and runs end-to-end on a desktop using
the mock paths; Jetson-only imports live behind try/except in `hal` and
`perception` and are skipped when the platform doesn't have them.
"""

from .config import (
    PhysicalParams,
    SafetyLimits,
    ControlGains,
    WorldConfig,
    LoopRates,
    RobotConfig,
    default_config,
)

__all__ = [
    "PhysicalParams",
    "SafetyLimits",
    "ControlGains",
    "WorldConfig",
    "LoopRates",
    "RobotConfig",
    "default_config",
]
