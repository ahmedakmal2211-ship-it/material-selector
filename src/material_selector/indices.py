"""Performance indices from docs/INDICES.md. Every index is to be MAXIMISED.

Units: rho in Mg/m^3 (converted from the dataset's kg/m^3), E in GPa,
sigma_f in MPa, C_m in USD/kg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from .data import Material

# Material attribute needed -> human label used in skip reasons.
FIELD_LABELS = {
    "density_kg_m3": "density",
    "modulus_gpa": "modulus",
    "strength_mpa": "strength",
    "cost_usd_per_kg": "cost",
}


@dataclass(frozen=True)
class Index:
    key: str
    name: str
    description: str
    units: str
    formula: str
    requires: Tuple[str, ...]
    func: Callable[..., float]
    exponent: Optional[float] = None  # n in M = P^n / rho, for chart guide lines
    property: Optional[str] = None  # "modulus" or "strength": the charted property

    def missing(self, m: Material) -> Tuple[str, ...]:
        """Labels of required values that are missing or not positive."""
        out = []
        for f in self.requires:
            v = getattr(m, f)
            if v is None or v <= 0:
                out.append(FIELD_LABELS[f])
        return tuple(out)

    def value(self, m: Material) -> Optional[float]:
        """Index value, or None when a required value is missing/non-positive."""
        if self.missing(m):
            return None
        rho = m.density_mg_m3
        return self.func(rho=rho, E=m.modulus_gpa, s=m.strength_mpa, c=m.cost_usd_per_kg)


_D, _E, _S, _C = "density_kg_m3", "modulus_gpa", "strength_mpa", "cost_usd_per_kg"

_LIST = [
    Index("tie_stiffness", "Light, stiff tie",
          "Tension member, fixed length and stiffness, minimum mass.",
          "GPa/(Mg/m^3)", "E/rho", (_D, _E),
          lambda rho, E, s, c: E / rho, 1.0, "modulus"),
    Index("tie_strength", "Light, strong tie",
          "Tension member, fixed length and load, minimum mass.",
          "MPa/(Mg/m^3)", "sigma_f/rho", (_D, _S),
          lambda rho, E, s, c: s / rho, 1.0, "strength"),
    Index("tie_strength_cost", "Cheapest strong tie",
          "Tension member, fixed length and load, minimum material cost.",
          "MPa/((USD/kg)*(Mg/m^3))", "sigma_f/(C_m*rho)", (_D, _S, _C),
          lambda rho, E, s, c: s / (c * rho), None, "strength"),
    Index("beam_stiffness", "Light, stiff beam",
          "Beam in bending, square solid section, fixed stiffness, minimum mass.",
          "GPa^(1/2)/(Mg/m^3)", "E^(1/2)/rho", (_D, _E),
          lambda rho, E, s, c: E ** 0.5 / rho, 0.5, "modulus"),
    Index("beam_strength", "Light, strong beam",
          "Beam in bending, square solid section, fixed load, minimum mass.",
          "MPa^(2/3)/(Mg/m^3)", "sigma_f^(2/3)/rho", (_D, _S),
          lambda rho, E, s, c: s ** (2.0 / 3.0) / rho, 2.0 / 3.0, "strength"),
    Index("beam_stiffness_cost", "Cheapest stiff beam",
          "Beam in bending, square solid section, fixed stiffness, minimum material cost.",
          "GPa^(1/2)/((USD/kg)*(Mg/m^3))", "E^(1/2)/(C_m*rho)", (_D, _E, _C),
          lambda rho, E, s, c: E ** 0.5 / (c * rho), None, "modulus"),
    Index("panel_stiffness", "Light, stiff panel",
          "Panel in bending, fixed width, free thickness, fixed stiffness, minimum mass.",
          "GPa^(1/3)/(Mg/m^3)", "E^(1/3)/rho", (_D, _E),
          lambda rho, E, s, c: E ** (1.0 / 3.0) / rho, 1.0 / 3.0, "modulus"),
    Index("panel_strength", "Light, strong panel",
          "Panel in bending, fixed width, free thickness, fixed load, minimum mass.",
          "MPa^(1/2)/(Mg/m^3)", "sigma_f^(1/2)/rho", (_D, _S),
          lambda rho, E, s, c: s ** 0.5 / rho, 0.5, "strength"),
    Index("column_buckling", "Light column (elastic buckling)",
          "Column against Euler buckling, square solid section, minimum mass. "
          "Alias of beam_stiffness.",
          "GPa^(1/2)/(Mg/m^3)", "E^(1/2)/rho", (_D, _E),
          lambda rho, E, s, c: E ** 0.5 / rho, 0.5, "modulus"),
]

INDICES: Dict[str, Index] = {i.key: i for i in _LIST}


def get_index(key: str) -> Index:
    try:
        return INDICES[key]
    except KeyError:
        raise KeyError(f"unknown goal '{key}'. Known: {', '.join(INDICES)}") from None
