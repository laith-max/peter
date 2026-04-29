"""3-rate cooperative loop entrypoint.

Schedules three logical loops on a single thread:
  - control    @ control_hz   (default 100 Hz)
  - safety     @ safety_hz    (default 200 Hz)
  - perception @ perception_hz (default  30 Hz)

This is a cooperative scheduler, not a real-time one. It uses
time.monotonic() for deadline tracking and assumes each loop's body
fits comfortably inside its period; if a loop runs long the scheduler
will catch up by skipping at most one period rather than spiralling.

CLI:
  python -m robot.main --duration 5 --mock
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from dataclasses import dataclass

from .config import RobotConfig, default_config
from .control import WaypointFollower
from .dynamics import Command, State
from .hal import HAL, make_hal
from .perception import Detector, make_detector
from .planner import OccupancyGrid, plan_world
from .safety import (
    ComplianceMonitor,
    TripReason,
    clamp_command,
    safe_stop_command,
)


log = logging.getLogger("robot.main")


@dataclass
class LoopStats:
    control_ticks: int = 0
    safety_ticks: int = 0
    perception_ticks: int = 0
    detections_seen: int = 0
    trips: int = 0
    distance_travelled_m: float = 0.0


def _build_demo_path(config: RobotConfig) -> list[tuple[float, float]]:
    """Plan a short demo path through an empty grid for smoke-testing."""
    grid = OccupancyGrid.empty(config.world)
    # Place a small obstacle so the planner has something non-trivial to do.
    grid.block_rect(1.0, -0.3, 1.4, 0.3)
    path = plan_world(grid, (0.0, 0.0), (3.0, 0.0))
    return path or [(3.0, 0.0)]


def _state_from_hal(hal: HAL, state: State) -> State:
    """Update the state held in main from HAL telemetry.

    On the mock path the HAL drives its own internal Plant, so we
    mirror its state directly. On a real platform this would fuse
    IMU + wheel odometry; that's out of scope for the scaffold.
    """
    telemetry = hal.read_motor_telemetry()
    state.motor_temp_c = telemetry.motor_temp_c
    state.state_of_charge = telemetry.state_of_charge
    if hasattr(hal, "plant"):
        plant_state = hal.plant.state  # type: ignore[attr-defined]
        state.x_m = plant_state.x_m
        state.y_m = plant_state.y_m
        state.theta_rad = plant_state.theta_rad
        state.speed_mps = plant_state.speed_mps
        state.yaw_rate_radps = plant_state.yaw_rate_radps
    return state


def run(
    config: RobotConfig,
    duration_s: float,
    *,
    force_mock: bool = False,
) -> LoopStats:
    hal: HAL = make_hal(config, force_mock=force_mock)
    detector: Detector = make_detector(force_mock=force_mock)
    monitor = ComplianceMonitor(config.safety)
    follower = WaypointFollower(config.gains, config.safety)
    follower.set_path(_build_demo_path(config))

    state = State()
    stats = LoopStats()

    period_control = 1.0 / config.loop.control_hz
    period_safety = 1.0 / config.loop.safety_hz
    period_perception = 1.0 / config.loop.perception_hz

    t_start = time.monotonic()
    t_end = t_start + duration_s
    next_control = t_start
    next_safety = t_start
    next_perception = t_start
    last_control_t = t_start

    last_x = state.x_m
    last_y = state.y_m

    while True:
        now = time.monotonic()
        if now >= t_end:
            break

        # ----- Safety loop (highest rate) -----
        if now >= next_safety:
            _state_from_hal(hal, state)
            report = monitor.evaluate(state)
            stats.safety_ticks += 1
            if report.tripped:
                stats.trips += 1
                hal.write_motor_command(safe_stop_command())
                if report.reason != TripReason.OK:
                    log.warning(
                        "safety trip: %s — %s", report.reason.value, report.detail
                    )
                    monitor.reset()
            next_safety += period_safety
            if next_safety <= now:
                next_safety = now + period_safety

        # ----- Control loop -----
        if now >= next_control:
            dt = now - last_control_t
            last_control_t = now
            cmd, status = follower.step(state, dt if dt > 0 else period_control)
            cmd = clamp_command(cmd, config.safety)
            hal.write_motor_command(cmd)
            hal.send_heartbeat()
            monitor.heartbeat()
            stats.control_ticks += 1
            stats.distance_travelled_m += math.hypot(
                state.x_m - last_x, state.y_m - last_y
            )
            last_x, last_y = state.x_m, state.y_m
            if status.finished:
                log.info("waypoint follower finished")
                break
            next_control += period_control
            if next_control <= now:
                next_control = now + period_control

        # ----- Perception loop -----
        if now >= next_perception:
            frame = hal.grab_frame()
            detections = detector.detect(frame)
            stats.perception_ticks += 1
            stats.detections_seen += len(detections)
            next_perception += period_perception
            if next_perception <= now:
                next_perception = now + period_perception

        next_deadline = min(next_control, next_safety, next_perception, t_end)
        sleep_s = next_deadline - time.monotonic()
        if sleep_s > 0:
            time.sleep(sleep_s)

    hal.shutdown()
    return stats


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Robot reference stack — desktop runner.")
    p.add_argument("--duration", type=float, default=2.0, help="run time in seconds")
    p.add_argument("--mock", action="store_true", help="force mock HAL + detector")
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = default_config()
    stats = run(config, args.duration, force_mock=args.mock)
    log.info(
        "done: control=%d safety=%d perception=%d detections=%d trips=%d distance=%.2fm",
        stats.control_ticks,
        stats.safety_ticks,
        stats.perception_ticks,
        stats.detections_seen,
        stats.trips,
        stats.distance_travelled_m,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
