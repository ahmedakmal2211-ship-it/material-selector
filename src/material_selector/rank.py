"""Rank screened materials by a performance index (higher is better).

Also: tie marking, cost-uncertainty rank bands and two-goal Pareto fronts.
Definitions are in docs/INDICES.md, section "Uncertainty".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .data import Material
from .indices import Index, get_index
from .screen import Limits, screen

DEFAULT_TIE_TOL_PCT = 5.0
DEFAULT_COST_FACTORS = {"estimated": 2.0, "sourced": 1.5}


@dataclass(frozen=True)
class RankedMaterial:
    rank: int
    material: Material
    value: float
    tie: str = ""  # "~" when within tie_tol % of the material ranked just above
    band: Optional[Tuple[int, int]] = None  # (best, worst) rank under cost uncertainty

    @property
    def band_text(self) -> str:
        return "" if self.band is None else f"{self.band[0]}-{self.band[1]}"


class RankResult(list):
    """A list of RankedMaterial plus what was left out and why."""

    def __init__(self, items=(), excluded=None, skipped=None):
        super().__init__(items)
        self.excluded: List[Tuple[Material, str]] = list(excluded or [])
        self.skipped: List[Tuple[Material, str]] = list(skipped or [])


def uses_cost(idx: Index) -> bool:
    return "cost_usd_per_kg" in idx.requires


def tie_marks(values: List[float], tol_pct: float) -> List[str]:
    """'~' for each value (sorted descending) within tol_pct % of the one above.

    Relative difference = (above - this) / above * 100, strictly less than
    tol_pct. The first value is never marked. A run "x, ~, ~" is one tie group.
    """
    marks = [""] * len(values)
    for i in range(1, len(values)):
        above = values[i - 1]
        if above > 0 and (above - values[i]) / above * 100.0 < tol_pct:
            marks[i] = "~"
    return marks


def rank_bands(values: List[float], factors: List[float]) -> List[Tuple[int, int]]:
    """Best/worst rank of each material when every cost is uncertain by x/÷ factor.

    A cost index is proportional to 1/C_m, so material i's index can lie
    anywhere in [v_i / F_i, v_i * F_i].
      best_i  = 1 + #{j != i : v_j / F_j >  v_i * F_i}   (i cheapest, all others dearest)
      worst_i = 1 + #{j != i : v_j * F_j >= v_i / F_i}   (i dearest, all others cheapest)
    Ties count for i at its best and against it at its worst.
    """
    lo = [v / f for v, f in zip(values, factors)]
    hi = [v * f for v, f in zip(values, factors)]
    n = len(values)
    out = []
    for i in range(n):
        best = 1 + sum(1 for j in range(n) if j != i and lo[j] > hi[i])
        worst = 1 + sum(1 for j in range(n) if j != i and hi[j] >= lo[i])
        out.append((best, worst))
    return out


def _score(materials, idx, limits):
    passed, excluded = screen(materials, limits, uses_cost(idx))
    scored, skipped = [], []
    for m in passed:
        miss = idx.missing(m)
        if miss:
            skipped.append((m, f"missing or non-positive {', '.join(miss)} for {idx.key}"))
            continue
        scored.append((m, idx.value(m)))
    return scored, excluded, skipped


def rank(
    materials: Iterable[Material],
    index: Union[str, Index],
    limits: Optional[Limits] = None,
    tie_tol: float = DEFAULT_TIE_TOL_PCT,
    cost_factors: Optional[Dict[str, float]] = None,
) -> RankResult:
    """Screen, then sort by index value descending; ties keep input order.

    Returns a list of RankedMaterial (rank starts at 1) with tie marks, and for
    cost goals a (best, worst) rank band from ``cost_factors`` (by
    cost_confidence; defaults in DEFAULT_COST_FACTORS). ``.excluded`` holds
    materials removed by limits, ``.skipped`` those missing a value the index
    needs; both are (material, reason) pairs. Never raises on bad rows.
    """
    idx = get_index(index) if isinstance(index, str) else index
    scored, excluded, skipped = _score(materials, idx, limits)
    scored.sort(key=lambda t: t[1], reverse=True)
    values = [v for _, v in scored]
    marks = tie_marks(values, tie_tol)
    bands: List[Optional[Tuple[int, int]]] = [None] * len(scored)
    if uses_cost(idx) and scored:
        f = dict(DEFAULT_COST_FACTORS, **(cost_factors or {}))
        bands = rank_bands(values, [f[m.cost_confidence] for m, _ in scored])
    result = RankResult(excluded=excluded, skipped=skipped)
    result.extend(RankedMaterial(i + 1, m, v, marks[i], bands[i])
                  for i, (m, v) in enumerate(scored))
    return result


def pareto(
    materials: Iterable[Material],
    goal1: Union[str, Index],
    goal2: Union[str, Index],
    limits: Optional[Limits] = None,
) -> RankResult:
    """Non-dominated materials for two goals (higher is better for both).

    j dominates i if v1_j >= v1_i and v2_j >= v2_i with at least one strict.
    Returns RankedMaterial items sorted by goal1 descending; ``value`` is the
    goal1 value and the goal2 values are in ``result.values2`` (same order).
    """
    i1 = get_index(goal1) if isinstance(goal1, str) else goal1
    i2 = get_index(goal2) if isinstance(goal2, str) else goal2
    mats = list(materials)
    s1, ex1, sk1 = _score(mats, i1, limits)
    s2, ex2, sk2 = _score(mats, i2, limits)
    v2 = {id(m): v for m, v in s2}
    both = [(m, v, v2[id(m)]) for m, v in s1 if id(m) in v2]
    front = [
        (m, a, b) for m, a, b in both
        if not any((a2 >= a and b2 >= b) and (a2 > a or b2 > b) for _, a2, b2 in both)
    ]
    front.sort(key=lambda t: t[1], reverse=True)
    skipped = sk1 + [(m, r) for m, r in sk2 if all(m is not x for x, _ in sk1)]
    res = RankResult([RankedMaterial(i + 1, m, a) for i, (m, a, _) in enumerate(front)],
                     excluded=ex1 + [e for e in ex2 if all(e[0] is not x for x, _ in ex1)],
                     skipped=skipped)
    res.values2 = [b for _, _, b in front]
    res.considered = len(both)
    return res
