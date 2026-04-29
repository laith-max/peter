"""On-device retention sweeper.

Walks the encrypted log directory and removes files older than the
configured retention window. Intended to run from a systemd timer once
per hour. Operates on file mtime; the writer rotates files daily so
mtime is a faithful proxy for record age.
"""

from __future__ import annotations

import os
import time
from pathlib import Path


def sweep(log_dir: Path, retention_days: int, *, now: float | None = None) -> list[Path]:
    """Delete files under `log_dir` older than `retention_days`.

    Returns the list of paths that were removed. Raises if the directory
    does not exist — callers should treat that as a deployment error
    rather than swallow it.
    """
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")
    if not log_dir.is_dir():
        raise FileNotFoundError(f"log directory not found: {log_dir}")

    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    removed: list[Path] = []
    for path in log_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path)
        except FileNotFoundError:
            continue
    return removed


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Sweep old Jetson device logs.")
    p.add_argument("log_dir", type=Path)
    p.add_argument("--days", type=int, required=True)
    args = p.parse_args()
    removed = sweep(args.log_dir, args.days)
    for path in removed:
        print(f"removed {path}")
    print(f"total removed: {len(removed)}")
