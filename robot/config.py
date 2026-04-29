"""Frozen configuration dataclasses.

All numbers here are placeholder defaults chosen to make the mock paths
behave plausibly. They are not tuned for any specific physical platform
and must be replaced before running against real hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PhysicalParams:
    mass_kg: float = 12.0
    inertia_z_kgm2: float = 0.35
    wheelbase_m: float = 0.30
    track_m: float = 0.28
    wheel_radius_m: float = 0.075
    drivetrain_efficiency: float = 0.85


@dataclass(frozen=True)
class SafetyLimits:
    max_speed_mps: float = 1.5
    max_yaw_rate_radps: float = 2.5
    max_torque_nm: float = 4.0
    max_motor_temp_c: float = 85.0
    min_state_of_charge: float = 0.10
    watchdog_timeout_s: float = 0.250


@dataclass(frozen=True)
class ControlGains:
    heading_kp: float = 3.5
    heading_kd: float = 0.4
    speed_kp: float = 2.0
    arrival_decel_radius_m: float = 0.40
    arrival_tolerance_m: float = 0.05


@dataclass(frozen=True)
class WorldConfig:
    cell_size_m: float = 0.05
    width_cells: int = 256
    height_cells: int = 256
    origin_x_m: float = -6.4
    origin_y_m: float = -6.4


@dataclass(frozen=True)
class LoopRates:
    control_hz: int = 100
    safety_hz: int = 200
    perception_hz: int = 30


@dataclass(frozen=True)
class RobotConfig:
    physical: PhysicalParams = field(default_factory=PhysicalParams)
    safety: SafetyLimits = field(default_factory=SafetyLimits)
    gains: ControlGains = field(default_factory=ControlGains)
    world: WorldConfig = field(default_factory=WorldConfig)
    loop: LoopRates = field(default_factory=LoopRates)


def default_config() -> RobotConfig:
    return RobotConfig()
