"""Integrity checks on the shipped data/materials.csv (skipped if absent)."""

import pytest

from material_selector.data import ALLOWED_CLASSES, REQUIRED_COLUMNS, read_rows
from material_selector.indices import INDICES
from material_selector.data import load_dataset, load_materials

from conftest import DATA_CSV

pytestmark = pytest.mark.skipif(
    not DATA_CSV.is_file(), reason=f"{DATA_CSV} not present yet; data integrity tests skipped"
)

NUMERIC = ("density_kg_m3", "modulus_GPa", "strength_MPa", "cost_usd_per_kg")


@pytest.fixture(scope="module")
def rows():
    return read_rows(DATA_CSV)


def test_row_count(rows):
    assert len(rows) >= 25


def test_required_columns(rows):
    missing = set(REQUIRED_COLUMNS) - set(rows[0].keys())
    assert not missing, f"missing columns: {missing}"


def test_names_unique_and_present(rows):
    names = [r["name"].strip() for r in rows]
    assert all(names)
    assert len(names) == len(set(names))


def test_class_allowed(rows):
    bad = [(r["name"], r["class"]) for r in rows if r["class"].strip().lower() not in ALLOWED_CLASSES]
    assert not bad


def test_numbers_positive(rows):
    bad = []
    for r in rows:
        for c in NUMERIC:
            try:
                if float(r[c]) <= 0:
                    bad.append((r["name"], c, r[c]))
            except ValueError:
                bad.append((r["name"], c, r[c]))
    assert not bad, bad


def test_density_plausible(rows):
    bad = [(r["name"], r["density_kg_m3"]) for r in rows
           if not 500 <= float(r["density_kg_m3"]) <= 25000]
    assert not bad


def test_modulus_plausible(rows):
    bad = [(r["name"], r["modulus_GPa"]) for r in rows
           if not 0.1 <= float(r["modulus_GPa"]) <= 1200]
    assert not bad


def test_source_url(rows):
    bad = [(r["name"], r["source_url"]) for r in rows if not r["source_url"].strip().startswith("http")]
    assert not bad


def test_no_rows_rejected_at_load():
    ds = load_dataset(DATA_CSV)
    assert not ds.rejected, ds.rejected


def test_every_index_ranks_whole_dataset():
    mats = load_materials(DATA_CSV)
    for idx in INDICES.values():
        values = [idx.value(m) for m in mats]
        assert all(v is not None and v > 0 for v in values), idx.key
