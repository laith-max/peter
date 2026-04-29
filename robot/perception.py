"""Object detection front-end.

Two implementations behind a common interface:
  - TensorRTDetector wraps NVIDIA's `jetson_inference` (Jetson-only).
  - MockDetector returns deterministic synthetic detections.
A factory chooses based on availability and a `force_mock` flag.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def center(self) -> tuple[float, float]:
        return (
            0.5 * (self.x_min + self.x_max),
            0.5 * (self.y_min + self.y_max),
        )

    @property
    def area(self) -> float:
        return max(0.0, self.x_max - self.x_min) * max(0.0, self.y_max - self.y_min)


class Detector(Protocol):
    def detect(self, frame) -> list[Detection]:  # noqa: ANN001
        ...


class MockDetector:
    """Deterministic stand-in for desktop development.

    Emits a single `person`-class detection that drifts across the frame
    on a slow circle, plus an occasional `obstacle` detection so the
    safety monitor has something to react to.
    """

    def __init__(self, seed: int = 0) -> None:
        self._t0 = time.monotonic()
        self._seed = seed

    def detect(self, frame=None) -> list[Detection]:  # noqa: ANN001
        t = time.monotonic() - self._t0
        cx = 0.5 + 0.25 * math.cos(0.5 * t + self._seed)
        cy = 0.5 + 0.25 * math.sin(0.5 * t + self._seed)
        size = 0.15
        person = Detection(
            label="person",
            confidence=0.92,
            x_min=cx - size / 2,
            y_min=cy - size / 2,
            x_max=cx + size / 2,
            y_max=cy + size / 2,
        )
        out = [person]
        if int(t) % 5 == 0:
            out.append(
                Detection(
                    label="obstacle",
                    confidence=0.71,
                    x_min=0.65,
                    y_min=0.40,
                    x_max=0.85,
                    y_max=0.65,
                )
            )
        return out


class TensorRTDetector:
    """Thin wrapper around `jetson_inference.detectNet`.

    Importing `jetson_inference` will fail off-Jetson; the constructor
    surfaces that failure clearly so the factory can fall back to the
    mock detector instead of crashing the whole stack at startup.
    """

    def __init__(
        self,
        network: str = "ssd-mobilenet-v2",
        threshold: float = 0.5,
    ) -> None:
        try:
            import jetson_inference  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "jetson_inference is not available; use MockDetector instead"
            ) from e
        self._net = jetson_inference.detectNet(network, threshold=threshold)

    def detect(self, frame) -> list[Detection]:  # noqa: ANN001
        if frame is None:
            return []
        raw = self._net.Detect(frame, overlay="none")
        out: list[Detection] = []
        for d in raw:
            label = self._net.GetClassDesc(d.ClassID)
            out.append(
                Detection(
                    label=label,
                    confidence=float(d.Confidence),
                    x_min=float(d.Left) / float(frame.width),
                    y_min=float(d.Top) / float(frame.height),
                    x_max=float(d.Right) / float(frame.width),
                    y_max=float(d.Bottom) / float(frame.height),
                )
            )
        return out


def make_detector(force_mock: bool = False) -> Detector:
    if force_mock:
        return MockDetector()
    try:
        return TensorRTDetector()
    except RuntimeError:
        return MockDetector()
