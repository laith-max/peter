"""Safety monitor + command clamp.

Two layers of defence-in-depth:
  - ComplianceMonitor watches state at the safety loop rate and trips on
    speed / yaw rate / motor temp / state-of-charge / heartbeat issues.
  - clamp_command() runs on every control output regardless of monitor
    state and saturates commands to the configured limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from .config import SafetyLimits
from .dynamics import Command, State


class TripReason(str, Enum):
    OK = "ok"
    OVER_SPEED = "over_speed"
    OVER_YAW = "over_yaw"
    OVER_TEMP = "over_temp"
    LOW_BATTERY = "low_battery"
    WATCHDOG = "watchdog"


@dataclass
class ComplianceReport:
    tripped: bool
    reason: TripReason
    detail: str = ""
    history: list[tuple[float, TripReason, str]] = field(default_factory=list)


class ComplianceMonitor:
    def __init__(self, limits: SafetyLimits) -> None:
        self.limits = limits
        self._last_heartbeat_s = time.monotonic()
        self._tripped = False
        self._reason = TripReason.OK
        self._history: list[tuple[float, TripReason, str]] = []

    def heartbeat(self) -> None:
        self._last_heartbeat_s = time.monotonic()

    def reset(self) -> None:
        self._tripped = False
        self._reason = TripReason.OK
        self._last_heartbeat_s = time.monotonic()

    def evaluate(self, state: State) -> ComplianceReport:
        now = time.monotonic()
        reason = TripReason.OK
        detail = ""

        if abs(state.speed_mps) > self.limits.max_speed_mps + 1e-3:
            reason = TripReason.OVER_SPEED
            detail = f"speed {state.speed_mps:.2f} > {self.limits.max_speed_mps:.2f}"
        elif abs(state.yaw_rate_radps) > self.limits.max_yaw_rate_radps + 1e-3:
            reason = TripReason.OVER_YAW
            detail = (
                f"yaw {state.yaw_rate_radps:.2f} > {self.limits.max_yaw_rate_radps:.2f}"
            )
        elif state.motor_temp_c > self.limits.max_motor_temp_c:
            reason = TripReason.OVER_TEMP
            detail = (
                f"motor {state.motor_temp_c:.1f}C > {self.limits.max_motor_temp_c:.1f}C"
            )
        elif state.state_of_charge < self.limits.min_state_of_charge:
            reason = TripReason.LOW_BATTERY
            detail = (
                f"soc {state.state_of_charge:.2f} < {self.limits.min_state_of_charge:.2f}"
            )
        elif now - self._last_heartbeat_s > self.limits.watchdog_timeout_s:
            reason = TripReason.WATCHDOG
            detail = f"no heartbeat for {now - self._last_heartbeat_s:.3f}s"

        if reason != TripReason.OK and not self._tripped:
            self._tripped = True
            self._reason = reason
            self._history.append((now, reason, detail))
        elif reason == TripReason.OK and not self._tripped:
            self._reason = TripReason.OK

        return ComplianceReport(
            tripped=self._tripped,
            reason=self._reason,
            detail=detail,
            history=list(self._history),
        )


def clamp_command(cmd: Command, limits: SafetyLimits) -> Command:
    return Command(
        theta_cmd_rad=cmd.theta_cmd_rad,
        tau_cmd_nm=max(-limits.max_torque_nm, min(limits.max_torque_nm, cmd.tau_cmd_nm)),
    )


def safe_stop_command() -> Command:
    return Command(theta_cmd_rad=0.0, tau_cmd_nm=0.0)
