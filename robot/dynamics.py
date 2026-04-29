"""Plant model.

PLACEHOLDER. The original manifest described this file as a "direct
port of the Rev B^4 simulator's plant model"; that source is not
available here, so this module provides a simple kinematic + first-order
torque-response stand-in that has roughly the right shape (state space,
step signature, command interface) and is sufficient for desktop
smoke-testing of the rest of the stack. Replace before relying on it
for anything beyond integration plumbing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import PhysicalParams, SafetyLimits


@dataclass
class State:
    x_m: float = 0.0
    y_m: float = 0.0
    theta_rad: float = 0.0
    speed_mps: float = 0.0
    yaw_rate_radps: float = 0.0
    motor_temp_c: float = 25.0
    state_of_charge: float = 1.0


@dataclass
class Command:
    theta_cmd_rad: float = 0.0
    tau_cmd_nm: float = 0.0


class Plant:
    def __init__(self, physical: PhysicalParams, safety: SafetyLimits) -> None:
        self.p = physical
        self.s = safety
        self.state = State()
        self._tau_filtered_nm = 0.0

    def reset(self, state: State | None = None) -> None:
        self.state = state if state is not None else State()
        self._tau_filtered_nm = 0.0

    def step(self, cmd: Command, dt: float) -> State:
        if dt <= 0.0:
            return self.state

        # First-order torque response (placeholder time constant).
        tau_target = max(-self.s.max_torque_nm, min(self.s.max_torque_nm, cmd.tau_cmd_nm))
        tau_tau_s = 0.05
        alpha = dt / (tau_tau_s + dt)
        self._tau_filtered_nm += alpha * (tau_target - self._tau_filtered_nm)

        # Linear acceleration from drive torque (very rough placeholder).
        accel = (
            self._tau_filtered_nm
            * self.p.drivetrain_efficiency
            / (self.p.mass_kg * self.p.wheel_radius_m)
        )
        self.state.speed_mps = max(
            -self.s.max_speed_mps,
            min(self.s.max_speed_mps, self.state.speed_mps + accel * dt),
        )

        # Heading tracks command via simple proportional yaw rate.
        theta_err = _wrap_pi(cmd.theta_cmd_rad - self.state.theta_rad)
        yaw_rate = max(
            -self.s.max_yaw_rate_radps,
            min(self.s.max_yaw_rate_radps, 4.0 * theta_err),
        )
        self.state.yaw_rate_radps = yaw_rate
        self.state.theta_rad = _wrap_pi(self.state.theta_rad + yaw_rate * dt)

        # Pose integration.
        self.state.x_m += self.state.speed_mps * math.cos(self.state.theta_rad) * dt
        self.state.y_m += self.state.speed_mps * math.sin(self.state.theta_rad) * dt

        # Trivial thermal + battery placeholders so safety has signals to look at.
        self.state.motor_temp_c += (
            (abs(self._tau_filtered_nm) * 0.05 - 0.02 * (self.state.motor_temp_c - 25.0))
            * dt
        )
        self.state.state_of_charge = max(
            0.0, self.state.state_of_charge - 5e-5 * abs(self.state.speed_mps) * dt
        )
        return self.state


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a
