"""Hardware abstraction layer.

Two implementations:
  - JetsonHAL: stubs for the on-vehicle sensor/actuator suite. The real
    BMI323 (I2C IMU), CAN-FD motor controller, UART heartbeat, and CSI
    camera bring-up are non-trivial and platform-dependent; without the
    vendor specs and a Jetson host this class is a thin scaffolding
    that imports the relevant Linux interfaces lazily and raises a
    clear error if a method is invoked without the underlying device.
  - MockHAL: deterministic in-process fakes that let the rest of the
    stack run on a desktop.
A factory `make_hal()` selects automatically and can be forced.
"""

from __future__ import annotations

import math
import os
import platform
import time
from dataclasses import dataclass
from typing import Protocol

from .config import RobotConfig
from .dynamics import Command, Plant


# ---------------------------------------------------------------------------
# Common HAL interface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImuSample:
    timestamp_s: float
    accel_mps2: tuple[float, float, float]
    gyro_radps: tuple[float, float, float]
    temperature_c: float


@dataclass(frozen=True)
class MotorTelemetry:
    timestamp_s: float
    motor_temp_c: float
    state_of_charge: float
    bus_voltage_v: float


class HAL(Protocol):
    def read_imu(self) -> ImuSample: ...
    def write_motor_command(self, cmd: Command) -> None: ...
    def read_motor_telemetry(self) -> MotorTelemetry: ...
    def send_heartbeat(self) -> None: ...
    def grab_frame(self):  # noqa: ANN201
        ...
    def shutdown(self) -> None: ...


# ---------------------------------------------------------------------------
# MockHAL — desktop-friendly fake
# ---------------------------------------------------------------------------


class MockHAL:
    """In-process fake. Drives a Plant so reads stay self-consistent
    with the commands written. Suitable for desktop smoke tests.
    """

    def __init__(self, config: RobotConfig) -> None:
        self.config = config
        self.plant = Plant(config.physical, config.safety)
        self._last_cmd = Command()
        self._last_step_s = time.monotonic()
        self._heartbeats = 0

    def _advance(self) -> None:
        now = time.monotonic()
        dt = now - self._last_step_s
        self._last_step_s = now
        if dt > 0:
            self.plant.step(self._last_cmd, dt)

    def read_imu(self) -> ImuSample:
        self._advance()
        s = self.plant.state
        # Body-frame: accel mostly forward, yaw rate from state.
        accel = (1.0 if abs(s.speed_mps) > 1e-3 else 0.0, 0.0, 9.81)
        gyro = (0.0, 0.0, s.yaw_rate_radps)
        return ImuSample(
            timestamp_s=time.monotonic(),
            accel_mps2=accel,
            gyro_radps=gyro,
            temperature_c=s.motor_temp_c - 5.0,
        )

    def write_motor_command(self, cmd: Command) -> None:
        self._last_cmd = cmd

    def read_motor_telemetry(self) -> MotorTelemetry:
        self._advance()
        s = self.plant.state
        return MotorTelemetry(
            timestamp_s=time.monotonic(),
            motor_temp_c=s.motor_temp_c,
            state_of_charge=s.state_of_charge,
            bus_voltage_v=24.0 * s.state_of_charge + 18.0,
        )

    def send_heartbeat(self) -> None:
        self._heartbeats += 1

    def grab_frame(self):  # noqa: ANN201
        return None  # MockDetector ignores frames

    def shutdown(self) -> None:
        self._last_cmd = Command()


# ---------------------------------------------------------------------------
# JetsonHAL — stubs
# ---------------------------------------------------------------------------


class JetsonHAL:
    """Jetson-side HAL. Stubbed.

    Real implementation needs:
      - smbus2 (or libgpiod / iio) for the BMI323 IMU at its provisioned
        I2C address; vendor-specific register map and scale factors.
      - python-can or socketcan for CAN-FD motor commands; vendor-
        specific PDO layout.
      - pyserial for the UART heartbeat to the supervisor MCU.
      - jetson_utils.videoSource for the CSI cameras.
    None of those specs are available in this scaffold, so the methods
    here raise NotImplementedError rather than guess at register maps.
    """

    def __init__(self, config: RobotConfig) -> None:
        self.config = config
        self._imports_ok = self._try_imports()
        if not self._imports_ok:
            raise RuntimeError(
                "JetsonHAL requested but Jetson-side dependencies are unavailable; "
                "use MockHAL on desktop"
            )

    @staticmethod
    def _try_imports() -> bool:
        try:
            import smbus2  # noqa: F401
            import can  # noqa: F401
            import serial  # noqa: F401
            from jetson_utils import videoSource  # noqa: F401
        except ImportError:
            return False
        return True

    def read_imu(self) -> ImuSample:
        raise NotImplementedError("BMI323 register map not specified")

    def write_motor_command(self, cmd: Command) -> None:
        raise NotImplementedError("CAN-FD PDO layout not specified")

    def read_motor_telemetry(self) -> MotorTelemetry:
        raise NotImplementedError("CAN-FD PDO layout not specified")

    def send_heartbeat(self) -> None:
        raise NotImplementedError("UART heartbeat protocol not specified")

    def grab_frame(self):  # noqa: ANN201
        raise NotImplementedError("CSI camera bring-up not specified")

    def shutdown(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _looks_like_jetson() -> bool:
    if platform.system() != "Linux":
        return False
    model_path = "/proc/device-tree/model"
    if not os.path.exists(model_path):
        return False
    try:
        with open(model_path, "rb") as f:
            return b"jetson" in f.read().lower()
    except OSError:
        return False


def make_hal(config: RobotConfig, force_mock: bool = False) -> HAL:
    if force_mock or not _looks_like_jetson():
        return MockHAL(config)
    try:
        return JetsonHAL(config)
    except RuntimeError:
        return MockHAL(config)
