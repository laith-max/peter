"""tegrastats collector — 1 Hz device-health sampler.

Wraps `tegrastats --interval 1000` and emits parsed scalar samples that
the supervisor can append to the local encrypted log. Only fields
whitelisted here are emitted; the raw tegrastats line is discarded.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from typing import Iterator


TEGRASTATS_BIN = "/usr/bin/tegrastats"

_RAM_RE = re.compile(r"RAM (\d+)/(\d+)MB")
_CPU_RE = re.compile(r"CPU \[(?P<cores>[^\]]+)\]")
_GPU_RE = re.compile(r"GR3D_FREQ (\d+)%")
_TEMP_RE = re.compile(r"(?P<zone>[A-Za-z_]+)@(?P<c>-?\d+(?:\.\d+)?)C")
_POWER_RE = re.compile(r"VDD_(?P<rail>[A-Z0-9_]+) (?P<mw>\d+)mW")


@dataclass(frozen=True)
class TegraSample:
    timestamp_wall: float
    timestamp_monotonic: float
    ram_used_mb: int | None
    ram_total_mb: int | None
    gpu_load_pct: int | None
    cpu_loads_pct: tuple[int, ...]
    temps_c: dict[str, float]
    power_mw: dict[str, int]


def parse_line(line: str) -> TegraSample:
    now_wall = time.time()
    now_mono = time.monotonic()

    ram_used = ram_total = None
    if m := _RAM_RE.search(line):
        ram_used, ram_total = int(m.group(1)), int(m.group(2))

    gpu = None
    if m := _GPU_RE.search(line):
        gpu = int(m.group(1))

    cpu_loads: tuple[int, ...] = ()
    if m := _CPU_RE.search(line):
        # Each core entry looks like "12%@1497" or "off".
        cores = m.group("cores").split(",")
        loads: list[int] = []
        for c in cores:
            c = c.strip()
            if c.endswith("off"):
                loads.append(0)
                continue
            pct, _, _ = c.partition("%")
            try:
                loads.append(int(pct))
            except ValueError:
                continue
        cpu_loads = tuple(loads)

    temps = {m.group("zone"): float(m.group("c")) for m in _TEMP_RE.finditer(line)}
    power = {m.group("rail"): int(m.group("mw")) for m in _POWER_RE.finditer(line)}

    return TegraSample(
        timestamp_wall=now_wall,
        timestamp_monotonic=now_mono,
        ram_used_mb=ram_used,
        ram_total_mb=ram_total,
        gpu_load_pct=gpu,
        cpu_loads_pct=cpu_loads,
        temps_c=temps,
        power_mw=power,
    )


def stream(interval_ms: int = 1000, binary: str = TEGRASTATS_BIN) -> Iterator[TegraSample]:
    """Spawn tegrastats and yield parsed samples until the process exits.

    tegrastats normally runs until terminated, so the stream ending on its
    own means the process died. If it died with a non-zero exit code we
    raise `RuntimeError` (surfacing stderr) rather than yield an empty
    stream — a missing or failing binary must be observable, not silent.
    Early closure by the consumer (e.g. breaking out of iteration) is not
    treated as an error.
    """
    proc = subprocess.Popen(
        [binary, "--interval", str(interval_ms)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            yield parse_line(line)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    # Reached only on natural completion (not when the consumer closes the
    # generator early, in which case GeneratorExit propagates above).
    err = proc.stderr.read().strip() if proc.stderr else ""
    if proc.returncode not in (0, None):
        raise RuntimeError(
            f"tegrastats exited with code {proc.returncode}: {err or '<no stderr>'}"
        )
