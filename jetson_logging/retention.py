"""On-device retention sweeper.

Walks the encrypted log directory and removes files older than the
configured retention window. Intended to run from a systemd timer once
per hour, e.g.::

    python -m jetson_logging.retention /var/log/jetson

With no ``--days`` the window is read from the validated site config
(`local_retention_days`).

Operates on file mtime; the writer rotates files daily so mtime is a
faithful proxy for record age. Caveat: any process that *touches* a file
resets its mtime and can therefore extend its retention beyond the window
— writers must not rewrite sealed log files in place.

Symlinks are never followed or removed, so a stray link under the log dir
cannot cause deletion of files outside it.
"""

from __future__ import annotations

import time
from pathlib import Path


def sweep(log_dir: Path, retention_days: int, *, now: float | None = None) -> list[Path]:
    """Delete files under `log_dir` older than `retention_days`.

    Returns the list of paths that were removed. Raises if the directory
    does not exist — callers should treat that as a deployment error
    rather than swallow it. Symlinks are skipped.
    """
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")
    if not log_dir.is_dir():
        raise FileNotFoundError(f"log directory not found: {log_dir}")

    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    removed: list[Path] = []
    for path in log_dir.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path)
        except FileNotFoundError:
            continue
    _prune_empty_dirs(log_dir)
    return removed


def _prune_empty_dirs(root: Path) -> None:
    """Remove directories left empty after a sweep (deepest first). Never
    touches `root` itself or symlinked directories."""
    dirs = [p for p in root.rglob("*") if p.is_dir() and not p.is_symlink()]
    for path in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass  # not empty, or a race — leave it.


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Sweep old Jetson device logs.")
    p.add_argument("log_dir", type=Path)
    p.add_argument(
        "--days",
        type=int,
        default=None,
        help="retention window; defaults to local_retention_days from site config",
    )
    args = p.parse_args(argv)

    days = args.days
    if days is None:
        from jetson_logging import config

        days = config.load_validated()["local_retention_days"]

    removed = sweep(args.log_dir, days)
    for path in removed:
        print(f"removed {path}")
    print(f"total removed: {len(removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
