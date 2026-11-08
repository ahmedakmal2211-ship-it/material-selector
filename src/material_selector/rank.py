"""Rank screened materials by a performance index (higher is better)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union

from .data import Material
from .indices import Index, get_index
from .screen import Limits, screen


@dataclass(frozen=True)
class RankedMaterial:
    rank: int
    material: Material
    value: float


class RankResult(list):
    """A list of RankedMaterial plus what was left out and why."""

    def __init__(self, items=(), excluded=None, skipped=None):
        super().__init__(items)
        self.excluded: List[Tuple[Material, str]] = list(excluded or [])
        self.skipped: List[Tuple[Material, str]] = list(skipped or [])


def rank(
    materials: Iterable[Material],
    index: Union[str, Index],
    limits: Optional[Limits] = None,
) -> RankResult:
    """Screen, then sort by index value descending; ties keep input order.

    Returns a list of RankedMaterial (rank starts at 1). ``.excluded`` holds
    materials removed by limits, ``.skipped`` those missing a value the index
    needs; both are (material, reason) pairs. Never raises on bad rows.
    """
    idx = get_index(index) if isinstance(index, str) else index
    passed, excluded = screen(materials, limits)
    scored, skipped = [], []
    for m in passed:
        miss = idx.missing(m)
        if miss:
            skipped.append((m, f"missing or non-positive {', '.join(miss)} for {idx.key}"))
            continue
        scored.append((m, idx.value(m)))
    scored.sort(key=lambda t: t[1], reverse=True)
    result = RankResult(excluded=excluded, skipped=skipped)
    result.extend(RankedMaterial(i + 1, m, v) for i, (m, v) in enumerate(scored))
    return result
