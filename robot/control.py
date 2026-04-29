"""Waypoint follower.

Heading-hold P+D on bearing error, with arrival-radius deceleration.
Outputs (theta_cmd, tau_cmd) consumed by the plant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import ControlGains, SafetyLimits
from .dynamics import Command, State


@dataclass
class FollowerStatus:
    waypoint_index: int
    distance_to_goal_m: float
    bearing_error_rad: float
    finished: bool


class WaypointFollower:
    def __init__(
        self,
        gains: ControlGains,
        safety: SafetyLimits,
        waypoints: list[tuple[float, float]] | None = None,
    ) -> None:
        self.gains = gains
        self.safety = safety
        self.waypoints: list[tuple[float, float]] = list(waypoints or [])
        self._idx = 0
        self._last_bearing_err: float | None = None

    def set_path(self, waypoints: list[tuple[float, float]]) -> None:
        self.waypoints = list(waypoints)
        self._idx = 0
        self._last_bearing_err = None

    @property
    def finished(self) -> bool:
        return self._idx >= len(self.waypoints)

    def _advance_if_reached(self, state: State) -> None:
        while self._idx < len(self.waypoints):
            wx, wy = self.waypoints[self._idx]
            d = math.hypot(wx - state.x_m, wy - state.y_m)
            tolerance = self.gains.arrival_tolerance_m
            # All waypoints except the last have a slightly looser tolerance
            # so the follower keeps moving without dwelling.
            if self._idx < len(self.waypoints) - 1:
                tolerance = max(tolerance, self.gains.arrival_tolerance_m * 2.0)
            if d <= tolerance:
                self._idx += 1
                self._last_bearing_err = None
                continue
            return

    def step(self, state: State, dt: float) -> tuple[Command, FollowerStatus]:
        self._advance_if_reached(state)

        if self.finished or not self.waypoints:
            status = FollowerStatus(
                waypoint_index=self._idx,
                distance_to_goal_m=0.0,
                bearing_error_rad=0.0,
                finished=True,
            )
            return Command(theta_cmd_rad=state.theta_rad, tau_cmd_nm=0.0), status

        wx, wy = self.waypoints[self._idx]
        dx = wx - state.x_m
        dy = wy - state.y_m
        distance = math.hypot(dx, dy)
        desired_bearing = math.atan2(dy, dx)

        bearing_err = _wrap_pi(desired_bearing - state.theta_rad)
        if dt > 0 and self._last_bearing_err is not None:
            bearing_rate = (bearing_err - self._last_bearing_err) / dt
        else:
            bearing_rate = 0.0
        self._last_bearing_err = bearing_err

        # Heading hold: P + D on bearing error, expressed as a small
        # heading nudge ahead of the current pose so the plant's yaw loop
        # closes onto it.
        theta_cmd = state.theta_rad + (
            self.gains.heading_kp * bearing_err + self.gains.heading_kd * bearing_rate
        ) * 0.05

        # Speed target: arrival decel inside the radius, otherwise speed_kp on distance.
        target_speed = min(
            self.safety.max_speed_mps,
            self.gains.speed_kp * distance,
        )
        if distance < self.gains.arrival_decel_radius_m:
            target_speed *= max(
                0.0, distance / max(self.gains.arrival_decel_radius_m, 1e-6)
            )

        # Reduce speed when heading is far from desired.
        target_speed *= max(0.0, math.cos(bearing_err))

        speed_err = target_speed - state.speed_mps
        tau_cmd = max(
            -self.safety.max_torque_nm,
            min(self.safety.max_torque_nm, 2.0 * speed_err),
        )

        status = FollowerStatus(
            waypoint_index=self._idx,
            distance_to_goal_m=distance,
            bearing_error_rad=bearing_err,
            finished=False,
        )
        return Command(theta_cmd_rad=theta_cmd, tau_cmd_nm=tau_cmd), status


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a
