"""Screening limits (docs/INDICES.md, "Screening limits").

Limits are inclusive (>= for minimums, <= for maximums). A material with a
missing value never passes a limit that uses that value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .data import Material


@dataclass(frozen=True)
class Limits:
    min_modulus_gpa: Optional[float] = None
    min_strength_mpa: Optional[float] = None
    max_density_kg_m3: Optional[float] = None
    max_cost_usd_per_kg: Optional[float] = None
    classes: Optional[Sequence[str]] = None


def failures(m: Material, limits: Optional[Limits]) -> List[str]:
    """Return the reasons ``m`` fails ``limits`` (empty list = passes)."""
    if limits is None:
        return []
    out = []

    def check_min(value, bound, label, unit):
        if bound is None:
            return
        if value is None:
            out.append(f"{label} missing (limit >= {bound:g} {unit})")
        elif value < bound:
            out.append(f"{label} {value:g} < {bound:g} {unit}")

    def check_max(value, bound, label, unit):
        if bound is None:
            return
        if value is None:
            out.append(f"{label} missing (limit <= {bound:g} {unit})")
        elif value > bound:
            out.append(f"{label} {value:g} > {bound:g} {unit}")

    check_min(m.modulus_gpa, limits.min_modulus_gpa, "modulus", "GPa")
    check_min(m.strength_mpa, limits.min_strength_mpa, "strength", "MPa")
    check_max(m.density_kg_m3, limits.max_density_kg_m3, "density", "kg/m^3")
    check_max(m.cost_usd_per_kg, limits.max_cost_usd_per_kg, "cost", "USD/kg")
    if limits.classes:
        allowed = {c.strip().lower() for c in limits.classes}
        if (m.cls or "").lower() not in allowed:
            out.append(f"class '{m.cls or 'missing'}' not in {sorted(allowed)}")
    return out


def screen(
    materials: Iterable[Material], limits: Optional[Limits]
) -> Tuple[List[Material], List[Tuple[Material, str]]]:
    """Split materials into (passed, [(excluded, reason), ...])."""
    passed, excluded = [], []
    for m in materials:
        f = failures(m, limits)
        if f:
            excluded.append((m, "; ".join(f)))
        else:
            passed.append(m)
    return passed, excluded
