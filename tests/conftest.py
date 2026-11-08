from pathlib import Path

import pytest

from material_selector.data import Material

REPO = Path(__file__).resolve().parents[1]
DATA_CSV = REPO / "data" / "materials.csv"

STEEL = Material("Steel (ref)", "metal", 7850, 210, 250, "yield", 1.0)
ALUMINIUM = Material("Aluminium (ref)", "metal", 2700, 70, 275, "yield", 3.0)


@pytest.fixture
def steel():
    return STEEL


@pytest.fixture
def aluminium():
    return ALUMINIUM


@pytest.fixture
def fixture_materials():
    return [
        STEEL,
        ALUMINIUM,
        Material("CFRP (ref)", "composite", 1550, 70, 600, "tensile", 40.0),
        Material("Nylon (ref)", "polymer", 1140, 2.5, 70, "tensile", 4.0),
        Material("Alumina (ref)", "ceramic", 3900, 370, 350, "flexural", 20.0),
        Material("No cost (ref)", "metal", 4430, 114, 880, "yield", None),
        Material("No modulus (ref)", "polymer", 950, None, 30, "tensile", 2.0),
    ]


SAMPLE_CSV = """name,class,density_kg_m3,modulus_GPa,strength_MPa,strength_basis,cost_usd_per_kg,source_name,source_url,notes
Steel (ref),metal,7850,210,250,yield,1.0,Example,https://example.org/a,
Aluminium (ref),metal,2700,70,275,yield,3.0,Example,https://example.org/b,
CFRP (ref),composite,1550,70,600,tensile,40,Example,https://example.org/c,quasi-isotropic
Nylon (ref),polymer,1140,2.5,70,tensile,4,Example,https://example.org/d,
Blank cost (ref),metal,4430,114,880,yield,,Example,https://example.org/e,
"""


@pytest.fixture
def sample_csv(tmp_path):
    p = tmp_path / "materials.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    return p
