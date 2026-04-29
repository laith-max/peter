"""Occupancy grid + 8-connected A* with corner-cut prevention,
spiral goal-snap, and line-of-sight smoothing.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .config import WorldConfig


Cell = tuple[int, int]


@dataclass
class OccupancyGrid:
    cells: np.ndarray  # uint8: 0 = free, 1 = blocked
    cell_size_m: float
    origin_x_m: float
    origin_y_m: float

    @classmethod
    def empty(cls, cfg: WorldConfig) -> "OccupancyGrid":
        cells = np.zeros((cfg.height_cells, cfg.width_cells), dtype=np.uint8)
        return cls(cells, cfg.cell_size_m, cfg.origin_x_m, cfg.origin_y_m)

    @property
    def height(self) -> int:
        return int(self.cells.shape[0])

    @property
    def width(self) -> int:
        return int(self.cells.shape[1])

    def in_bounds(self, c: Cell) -> bool:
        r, k = c
        return 0 <= r < self.height and 0 <= k < self.width

    def is_free(self, c: Cell) -> bool:
        return self.in_bounds(c) and self.cells[c[0], c[1]] == 0

    def world_to_cell(self, x_m: float, y_m: float) -> Cell:
        k = int((x_m - self.origin_x_m) / self.cell_size_m)
        r = int((y_m - self.origin_y_m) / self.cell_size_m)
        return (r, k)

    def cell_to_world(self, c: Cell) -> tuple[float, float]:
        r, k = c
        x = self.origin_x_m + (k + 0.5) * self.cell_size_m
        y = self.origin_y_m + (r + 0.5) * self.cell_size_m
        return (x, y)

    def block_rect(self, x0: float, y0: float, x1: float, y1: float) -> None:
        r0, k0 = self.world_to_cell(min(x0, x1), min(y0, y1))
        r1, k1 = self.world_to_cell(max(x0, x1), max(y0, y1))
        r0 = max(0, r0); k0 = max(0, k0)
        r1 = min(self.height - 1, r1); k1 = min(self.width - 1, k1)
        self.cells[r0:r1 + 1, k0:k1 + 1] = 1


_NEIGHBOURS: tuple[tuple[int, int], ...] = (
    (-1, 0), (1, 0), (0, -1), (0, 1),
    (-1, -1), (-1, 1), (1, -1), (1, 1),
)


def _heuristic(a: Cell, b: Cell) -> float:
    dr = abs(a[0] - b[0])
    dk = abs(a[1] - b[1])
    return (dr + dk) + (math.sqrt(2.0) - 2.0) * min(dr, dk)


def _spiral_snap(grid: OccupancyGrid, c: Cell, max_radius: int = 24) -> Cell | None:
    """Find the nearest free cell to `c` by scanning concentric rings."""
    if grid.in_bounds(c) and grid.is_free(c):
        return c
    for radius in range(1, max_radius + 1):
        for dr in range(-radius, radius + 1):
            for dk in range(-radius, radius + 1):
                if max(abs(dr), abs(dk)) != radius:
                    continue
                cand = (c[0] + dr, c[1] + dk)
                if grid.in_bounds(cand) and grid.is_free(cand):
                    return cand
    return None


def astar(grid: OccupancyGrid, start: Cell, goal: Cell) -> list[Cell] | None:
    start = _spiral_snap(grid, start) or start
    goal = _spiral_snap(grid, goal) or goal
    if not (grid.is_free(start) and grid.is_free(goal)):
        return None

    open_heap: list[tuple[float, int, Cell]] = []
    counter = 0
    heapq.heappush(open_heap, (_heuristic(start, goal), counter, start))
    came_from: dict[Cell, Cell] = {}
    g_score: dict[Cell, float] = {start: 0.0}

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            return _reconstruct(came_from, current)

        for dr, dk in _NEIGHBOURS:
            n = (current[0] + dr, current[1] + dk)
            if not grid.is_free(n):
                continue
            # Corner-cut prevention: diagonal step requires both adjacent
            # orthogonal cells to be free.
            if dr != 0 and dk != 0:
                if not grid.is_free((current[0] + dr, current[1])):
                    continue
                if not grid.is_free((current[0], current[1] + dk)):
                    continue
            step = math.sqrt(2.0) if dr != 0 and dk != 0 else 1.0
            tentative = g_score[current] + step
            if tentative < g_score.get(n, math.inf):
                came_from[n] = current
                g_score[n] = tentative
                f = tentative + _heuristic(n, goal)
                counter += 1
                heapq.heappush(open_heap, (f, counter, n))
    return None


def _reconstruct(came_from: dict[Cell, Cell], end: Cell) -> list[Cell]:
    path = [end]
    while end in came_from:
        end = came_from[end]
        path.append(end)
    path.reverse()
    return path


def _line_of_sight(grid: OccupancyGrid, a: Cell, b: Cell) -> bool:
    r0, k0 = a
    r1, k1 = b
    dr = abs(r1 - r0)
    dk = abs(k1 - k0)
    sr = 1 if r0 < r1 else -1
    sk = 1 if k0 < k1 else -1
    err = dr - dk
    while True:
        if not grid.is_free((r0, k0)):
            return False
        if (r0, k0) == (r1, k1):
            return True
        e2 = 2 * err
        if e2 > -dk:
            err -= dk
            r0 += sr
        if e2 < dr:
            err += dr
            k0 += sk


def smooth(grid: OccupancyGrid, path: list[Cell]) -> list[Cell]:
    """Greedy line-of-sight smoothing."""
    if len(path) <= 2:
        return list(path)
    out = [path[0]]
    i = 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not _line_of_sight(grid, path[i], path[j]):
            j -= 1
        out.append(path[j])
        i = j
    return out


def plan_world(
    grid: OccupancyGrid,
    start_xy: tuple[float, float],
    goal_xy: tuple[float, float],
) -> list[tuple[float, float]] | None:
    start = grid.world_to_cell(*start_xy)
    goal = grid.world_to_cell(*goal_xy)
    cells = astar(grid, start, goal)
    if cells is None:
        return None
    cells = smooth(grid, cells)
    return [grid.cell_to_world(c) for c in cells]


def path_length_m(path: Iterable[tuple[float, float]]) -> float:
    pts = list(path)
    total = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        total += math.hypot(dx, dy)
    return total
