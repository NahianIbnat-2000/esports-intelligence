"""Concentration and competitive-balance measures.

All functions take raw non-negative quantities (wins, titles, ...) and are
explicit about what is being concentrated. They return None when the input
cannot support the measure (empty, or total of zero).

Herfindahl-Hirschman Index:   HHI = sum_i s_i^2,  s_i = x_i / sum_j x_j  (0..1; x10,000 for the
                              antitrust scale)
Normalised HHI:               HHI* = (HHI - 1/N) / (1 - 1/N)   (0 = equal shares, 1 = one holder)
Gini coefficient:             G = sum_i sum_j |x_i - x_j| / (2 N^2 mean(x))
Lorenz curve:                 cumulative share of the total held by the bottom k/N of holders
Noll-Scully ratio:            sd(win%) / (0.5 / sqrt(G)), G = mean games per team; equals 1 when
                              results are as dispersed as coin flips would make them
"""
from __future__ import annotations

import numpy as np


def _arr(x) -> np.ndarray:
    a = np.asarray(list(x), dtype=float)
    if np.any(a < 0):
        raise ValueError("values must be non-negative")
    return a


def hhi(values) -> float | None:
    a = _arr(values)
    if a.size == 0 or a.sum() == 0:
        return None
    s = a / a.sum()
    return float(np.sum(s ** 2))


def hhi_normalised(values) -> float | None:
    a = _arr(values)
    h = hhi(a)
    if h is None or a.size < 2:
        return None
    n = a.size
    return float((h - 1 / n) / (1 - 1 / n))


def gini(values) -> float | None:
    a = _arr(values)
    if a.size == 0 or a.sum() == 0:
        return None
    a = np.sort(a)
    n = a.size
    # equivalent closed form of the mean absolute difference definition
    return float((2 * np.sum(np.arange(1, n + 1) * a) / (n * a.sum())) - (n + 1) / n)


def lorenz_curve(values) -> list[dict] | None:
    a = _arr(values)
    if a.size == 0 or a.sum() == 0:
        return None
    a = np.sort(a)
    cum = np.concatenate([[0.0], np.cumsum(a) / a.sum()])
    pop = np.linspace(0, 1, a.size + 1)
    return [{"population_share": float(p), "cumulative_share": float(c)} for p, c in zip(pop, cum)]


def noll_scully(win_pcts, games_per_team) -> float | None:
    w = np.asarray(list(win_pcts), dtype=float)
    g = np.asarray(list(games_per_team), dtype=float)
    if w.size < 2 or np.any(g <= 0):
        return None
    ideal = 0.5 / np.sqrt(g.mean())
    return float(np.std(w, ddof=0) / ideal)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | tuple[None, None]:
    if n == 0:
        return (None, None)
    p = successes / n
    denom = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (float(centre - half), float(centre + half))
