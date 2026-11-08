"""Hand-checked values from docs/INDICES.md, written as literals (3 s.f.).

Hand working (rho in Mg/m^3):
  steel  rho=7.85 E=210 s=250:  210/7.85=26.75; 250/7.85=31.85;
         sqrt(210)=14.49 -> /7.85=1.846; cbrt(210)=5.944 -> /7.85=0.757
  alum.  rho=2.70 E=70  s=275:  70/2.70=25.93; sqrt(70)=8.367 -> /2.70=3.099;
         275^(2/3)=42.29 -> /2.70=15.66
"""

import pytest

from material_selector.data import Material
from material_selector.indices import INDICES, get_index

REL = 5e-3  # agreement to 3 significant figures


@pytest.mark.parametrize(
    "goal, expected",
    [
        ("tie_stiffness", 26.8),
        ("tie_strength", 31.8),
        ("beam_stiffness", 1.85),
        ("column_buckling", 1.85),
        ("panel_stiffness", 0.757),
    ],
)
def test_steel_values(steel, goal, expected):
    assert INDICES[goal].value(steel) == pytest.approx(expected, rel=REL)


@pytest.mark.parametrize(
    "goal, expected",
    [
        ("tie_stiffness", 25.9),
        ("beam_stiffness", 3.10),
        ("beam_strength", 15.7),
    ],
)
def test_aluminium_values(aluminium, goal, expected):
    assert INDICES[goal].value(aluminium) == pytest.approx(expected, rel=REL)


def test_cost_indices_hand_values(steel):
    # steel C_m = 1.0 USD/kg: sigma/(C rho) = 250/(1*7.85) = 31.8; sqrt(E)/(C rho) = 1.85
    assert INDICES["tie_strength_cost"].value(steel) == pytest.approx(31.8, rel=REL)
    assert INDICES["beam_stiffness_cost"].value(steel) == pytest.approx(1.85, rel=REL)


def test_panel_strength_hand_value(steel):
    # sqrt(250) = 15.81; / 7.85 = 2.01
    assert INDICES["panel_strength"].value(steel) == pytest.approx(2.01, rel=REL)


def test_density_converted_to_mg_m3():
    m = Material("x", "metal", 1000, 1, 1, "", 1)
    assert m.density_mg_m3 == 1.0
    assert INDICES["tie_stiffness"].value(m) == pytest.approx(1.0)


def test_aluminium_beats_steel_on_beam_stiffness(steel, aluminium):
    s = INDICES["beam_stiffness"].value(steel)
    a = INDICES["beam_stiffness"].value(aluminium)
    assert a > s
    assert a / s == pytest.approx(1.68, rel=0.01)  # 3.099 / 1.846


def test_steel_and_aluminium_about_equal_on_tie_stiffness(steel, aluminium):
    s = INDICES["tie_stiffness"].value(steel)
    a = INDICES["tie_stiffness"].value(aluminium)
    assert abs(a - s) / s < 0.05


def test_every_index_has_metadata():
    expected = {"tie_stiffness", "tie_strength", "tie_strength_cost", "beam_stiffness",
                "beam_strength", "beam_stiffness_cost", "panel_stiffness",
                "panel_strength", "column_buckling"}
    assert set(INDICES) == expected
    for key, idx in INDICES.items():
        assert idx.key == key
        assert idx.name and idx.description and idx.units and idx.formula


def test_column_buckling_is_alias_of_beam_stiffness(aluminium):
    assert INDICES["column_buckling"].value(aluminium) == INDICES["beam_stiffness"].value(aluminium)


def test_missing_value_returns_none_not_crash():
    m = Material("x", "metal", 7850, None, 250, "", None)
    assert INDICES["tie_stiffness"].value(m) is None
    assert INDICES["tie_strength_cost"].value(m) is None
    assert INDICES["tie_strength"].value(m) is not None


def test_unknown_goal():
    with pytest.raises(KeyError):
        get_index("nope")
