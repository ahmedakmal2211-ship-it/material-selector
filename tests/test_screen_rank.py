from material_selector.data import Material, load_materials
from material_selector.rank import rank
from material_selector.screen import Limits, failures, screen


def test_limits_inclusive_at_boundary(steel):
    lim = Limits(min_modulus_gpa=210, min_strength_mpa=250, max_density_kg_m3=7850,
                 max_cost_usd_per_kg=1.0, classes=["metal"])
    assert failures(steel, lim) == []


def test_limits_just_outside_boundary_fail(steel):
    assert failures(steel, Limits(min_modulus_gpa=210.001))
    assert failures(steel, Limits(min_strength_mpa=250.001))
    assert failures(steel, Limits(max_density_kg_m3=7849.999))
    assert failures(steel, Limits(max_cost_usd_per_kg=0.999))
    assert failures(steel, Limits(classes=["polymer"]))


def test_missing_value_never_passes_a_limit_that_uses_it():
    m = Material("blank", "metal", None, None, None, "", None)
    for lim in (Limits(min_modulus_gpa=0), Limits(min_strength_mpa=0),
                Limits(max_density_kg_m3=1e9), Limits(max_cost_usd_per_kg=1e9)):
        assert failures(m, lim), lim


def test_missing_value_ignored_when_limit_not_used():
    m = Material("no cost", "metal", 4430, 114, 880, "", None)
    assert failures(m, Limits(min_modulus_gpa=100)) == []


def test_class_filter_case_insensitive(steel):
    assert failures(steel, Limits(classes=["Metal"])) == []


def test_screen_splits(fixture_materials):
    passed, excluded = screen(fixture_materials, Limits(classes=["metal"]))
    assert all(m.cls == "metal" for m in passed)
    assert len(passed) + len(excluded) == len(fixture_materials)
    assert all(reason for _, reason in excluded)


def test_rank_sorted_and_numbered(fixture_materials):
    res = rank(fixture_materials, "beam_stiffness")
    values = [r.value for r in res]
    assert values == sorted(values, reverse=True)
    assert [r.rank for r in res] == list(range(1, len(res) + 1))


def test_rank_aluminium_above_steel_beam_stiffness(steel, aluminium):
    res = rank([steel, aluminium], "beam_stiffness")
    assert [r.material for r in res] == [aluminium, steel]


def test_rank_skips_missing_with_reason(fixture_materials):
    res = rank(fixture_materials, "tie_strength_cost")
    names = [r.material.name for r in res]
    assert "No cost (ref)" not in names
    skipped = {m.name: why for m, why in res.skipped}
    assert "cost" in skipped["No cost (ref)"]
    assert len(res) + len(res.skipped) == len(fixture_materials)


def test_rank_skips_missing_modulus(fixture_materials):
    res = rank(fixture_materials, "beam_stiffness")
    assert "No modulus (ref)" in {m.name for m, _ in res.skipped}


def test_rank_with_limits(fixture_materials):
    res = rank(fixture_materials, "beam_stiffness", Limits(max_density_kg_m3=3000))
    assert all(r.material.density_kg_m3 <= 3000 for r in res)
    assert res.excluded


def test_rank_never_crashes_on_bad_rows():
    bad = [Material("zero density", "metal", 0, 210, 250, "", 1),
           Material("negative E", "metal", 7850, -1, 250, "", 1),
           Material("empty", "", None, None, None, "", None)]
    for goal in ("tie_stiffness", "beam_stiffness", "beam_stiffness_cost"):
        res = rank(bad, goal)
        assert len(res) == 0
        assert len(res.skipped) == 3


def test_load_csv_blank_is_missing(sample_csv):
    mats = load_materials(sample_csv)
    by = {m.name: m for m in mats}
    assert by["Blank cost (ref)"].cost_usd_per_kg is None
    assert by["Steel (ref)"].density_kg_m3 == 7850.0
    assert by["CFRP (ref)"].cls == "composite"
