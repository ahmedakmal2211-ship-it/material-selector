"""Round 2: optional columns, ties, rank bands, filters, formats, show, pareto, charts."""

import csv
import io
import json

import pytest

from material_selector.cli import main
from material_selector.data import Material, build_dataset, load_dataset
from material_selector.indices import INDICES
from material_selector.plot import _convex_hull, ashby_chart, class_envelope
from material_selector.rank import pareto, rank, rank_bands, tie_marks
from material_selector.screen import Limits, failures

from conftest import SAMPLE_CSV

BASE = SAMPLE_CSV.splitlines()[0]
HEADER = BASE + ",cost_confidence,cost_source_url,anisotropic"

# rho = 1000 kg/m3 (1 Mg/m3) and strength 100 MPa, so tie_strength_cost = 100 / C.
COST_CSV = HEADER + """
A cheap (ref),metal,1000,50,100,yield,1,x,https://e.org/a,,estimated,,no
B mid (ref),metal,1000,60,100,yield,1.5,x,https://e.org/b,,sourced,https://e.org/price,no
C dear (ref),composite,1000,70,100,tensile,4,x,https://e.org/c,,estimated,,yes
"""


def write(tmp_path, text, name="m.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def row(**kw):
    r = {"name": "X", "class": "metal", "density_kg_m3": "7850", "modulus_GPa": "210",
         "strength_MPa": "250", "strength_basis": "yield", "cost_usd_per_kg": "1",
         "source_name": "x", "source_url": "https://e.org", "notes": ""}
    r.update(kw)
    return r


@pytest.fixture
def cost_csv(tmp_path):
    return write(tmp_path, COST_CSV)


# ---- optional columns -------------------------------------------------------

def test_optional_columns_default_when_absent(sample_csv):
    m = load_dataset(sample_csv).materials[0]
    assert (m.cost_confidence, m.cost_source_url, m.anisotropic) == ("estimated", "", False)


def test_optional_columns_default_when_blank():
    m = build_dataset([row(cost_confidence="", cost_source_url="", anisotropic="")]).materials[0]
    assert (m.cost_confidence, m.cost_source_url, m.anisotropic) == ("estimated", "", False)


def test_optional_columns_parsed(cost_csv):
    by = {m.name: m for m in load_dataset(cost_csv).materials}
    assert by["B mid (ref)"].cost_confidence == "sourced"
    assert by["B mid (ref)"].cost_source_url == "https://e.org/price"
    assert by["C dear (ref)"].anisotropic is True
    assert by["A cheap (ref)"].anisotropic is False


def test_optional_values_case_insensitive():
    m = build_dataset([row(cost_confidence="Sourced", anisotropic="YES")]).materials[0]
    assert m.cost_confidence == "sourced" and m.anisotropic


@pytest.mark.parametrize("kw, field", [
    ({"cost_confidence": "guess"}, "cost_confidence"),
    ({"cost_source_url": "www.e.org"}, "cost_source_url"),
    ({"anisotropic": "maybe"}, "anisotropic"),
])
def test_bad_optional_values_rejected(kw, field):
    ds = build_dataset([row(**kw)])
    assert not ds.materials
    assert field in ds.rejected[0][1]


# ---- ties ---------------------------------------------------------------------

def test_tie_marks_hand_values():
    # 97 is 3% below 100 -> '~'; 90 is 7.2% below 97 -> ''; 89.5 is 0.56% below 90 -> '~'
    assert tie_marks([100, 97, 90, 89.5], 5) == ["", "~", "", "~"]
    assert tie_marks([100, 97], 2) == ["", ""]
    assert tie_marks([100, 95], 5) == ["", ""]  # exactly 5% is not < 5%


def test_rank_sets_tie_and_cli_column(sample_csv, capsys):
    # Steel 26.75 and aluminium 25.93 on tie_stiffness differ by 3.1% -> tie
    res = rank(load_dataset(sample_csv).materials, "tie_stiffness")
    names = {r.material.name: r for r in res}
    assert names["Aluminium (ref)"].tie == "~"
    main(["--data", str(sample_csv), "rank", "--goal", "tie_stiffness", "--tie-tol", "1",
          "--format", "json"])
    recs = json.loads(capsys.readouterr().out)
    assert not any(r["tie"] for r in recs if r["name"] == "Aluminium (ref)")


# ---- rank bands -----------------------------------------------------------------

def test_rank_bands_hand_values():
    # values 100, 66.67, 25 with factors 2, 1.25, 2:
    # ranges A [50, 200], B [53.3, 83.3], C [12.5, 50]
    # A: best 1 (nothing above 200), worst 3 (B hi 83.3 >= 50, C hi 50 >= 50)
    # B: best 1 (A lo 50, C lo 12.5 < 83.3), worst 2 (A hi 200 >= 53.3; C hi 50 < 53.3)
    # C: best 2 (B lo 53.3 > 50; A lo 50 not > 50), worst 3
    assert rank_bands([100, 100 / 1.5, 25], [2, 1.25, 2]) == [(1, 3), (1, 2), (2, 3)]


def test_rank_bands_factor_one_is_nominal():
    assert rank_bands([3, 2, 1], [1, 1, 1]) == [(1, 1), (2, 2), (3, 3)]


def test_default_cost_factors():
    from material_selector.rank import DEFAULT_COST_FACTORS
    assert DEFAULT_COST_FACTORS == {"estimated": 2.0, "sourced": 1.5}


def test_rank_band_only_for_cost_goals(cost_csv):
    mats = load_dataset(cost_csv).materials
    assert all(r.band is None for r in rank(mats, "tie_strength"))
    # defaults F = 2 (A, C estimated), 1.5 (B sourced):
    # A [50, 200], B [44.4, 100], C [12.5, 50]
    # A: best 1, worst 3 (B hi 100 >= 50, C hi 50 >= 50)
    # B: best 1 (A lo 50 < 100), worst 3 (A hi 200, C hi 50 >= 44.4)
    # C: best 1 (A lo 50 not > 50, B lo 44.4 < 50), worst 3
    res = rank(mats, "tie_strength_cost")
    assert [r.band_text for r in res] == ["1-3", "1-3", "1-3"]
    res = rank(mats, "tie_strength_cost", cost_factors={"estimated": 2.0, "sourced": 1.25})
    assert [r.band_text for r in res] == ["1-3", "1-2", "2-3"]
    res = rank(mats, "tie_strength_cost", cost_factors={"estimated": 1.0, "sourced": 1.0})
    assert [r.band_text for r in res] == ["1-1", "2-2", "3-3"]


def test_rank_band_cli(cost_csv, capsys):
    rc = main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost"])
    out = capsys.readouterr().out
    assert rc == 0 and "rank band" in out and "1-3" in out and "sourced" in out
    rc = main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost",
               "--cost-factor-estimated", "1", "--cost-factor-sourced", "1", "--format", "csv"])
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert [r["rank_band"] for r in rows] == ["1-1", "2-2", "3-3"]


@pytest.mark.parametrize("value", ["0.5", "-1", "nan"])
def test_cost_factor_must_be_at_least_one(cost_csv, value):
    with pytest.raises(SystemExit) as e:
        main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost",
              "--cost-factor-estimated", value])
    assert e.value.code == 2


# ---- filters --------------------------------------------------------------------

def test_strength_basis_filter(cost_csv, capsys):
    res = rank(load_dataset(cost_csv).materials, "tie_strength",
               Limits(strength_bases=["tensile"]))
    assert [r.material.name for r in res] == ["C dear (ref)"]
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength",
          "--strength-basis", "yield", "--strength-basis", "tensile", "--format", "json"])
    assert len(json.loads(capsys.readouterr().out)) == 3


def test_strength_basis_missing_fails():
    m = Material("x", "metal", 7850, 210, 250, "", 1)
    assert failures(m, Limits(strength_bases=["yield"]))


def test_isotropic_only(cost_csv, capsys):
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength", "--isotropic-only",
          "--format", "json"])
    names = [r["name"] for r in json.loads(capsys.readouterr().out)]
    assert "C dear (ref)" not in names and len(names) == 2


def test_sourced_cost_only_applies_to_cost_goals_only(cost_csv):
    mats = load_dataset(cost_csv).materials
    lim = Limits(sourced_cost_only=True)
    assert [r.material.name for r in rank(mats, "tie_strength_cost", lim)] == ["B mid (ref)"]
    assert len(rank(mats, "tie_strength", lim)) == 3


def test_mixed_basis_note_still_printed(cost_csv, capsys):
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength"])
    assert "mix bases" in capsys.readouterr().out


# ---- output formats ------------------------------------------------------------------

def test_json_is_pure_and_complete(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost",
                 "--format", "json"]) == 0
    cap = capsys.readouterr()
    recs = json.loads(cap.out)  # stdout must parse as JSON on its own
    for k in ("rank", "tie", "rank_band", "index_value", "cost_confidence",
              "cost_source_url", "anisotropic", "strength_basis", "source_url", "notes"):
        assert k in recs[0]
    assert "Screening aid only" in cap.err and "data:" in cap.err
    assert "Screening aid only" not in cap.out


def test_csv_is_pure_and_complete(cost_csv, capsys):
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost", "--format", "csv"])
    cap = capsys.readouterr()
    rows = list(csv.DictReader(io.StringIO(cap.out)))
    assert len(rows) == 3
    assert {"tie", "rank_band", "cost_confidence", "anisotropic"} <= set(rows[0])
    assert rows[2]["anisotropic"] == "yes"
    assert "Screening aid only" in cap.err and "Screening aid only" not in cap.out


def test_markdown_format(cost_csv, capsys):
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength", "--format", "markdown"])
    out = capsys.readouterr().out
    assert "| rank | tie |" in out and "|---|" in out and "Screening aid only" in out


def test_top_larger_than_set_is_fine(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "rank", "--goal", "tie_strength", "--top", "999",
                 "--format", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 3


# ---- show -----------------------------------------------------------------------

def test_show_unique_substring(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "show", "MID"]) == 0
    out = capsys.readouterr().out
    for s in ("B mid (ref)", "https://e.org/b", "https://e.org/price", "sourced",
              "cost_confidence", "anisotropic", "tie_strength_cost", "Screening aid only"):
        assert s in out


def test_show_ambiguous_lists_matches(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "show", "(ref)"]) == 2
    err = capsys.readouterr().err
    assert "matches 3" in err and "A cheap (ref)" in err and "C dear (ref)" in err


def test_show_no_match(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "show", "unobtainium"]) == 2
    assert "no material matches" in capsys.readouterr().err


# ---- pareto -----------------------------------------------------------------------

def test_pareto_hand_example():
    # (v1, v2): P (3,1), Q (1,3), R (2,2), S (1,1) dominated by R; T (2,1) dominated by R
    mats = {n: Material(n, "metal", 1000, e, s, "yield", 1)
            for n, e, s in [("P", 9, 1), ("Q", 1, 27), ("R", 4, 8), ("S", 1, 1), ("T", 4, 1)]}
    # tie_stiffness = E/1, beam_strength = s^(2/3)/1 -> P(9,1) Q(1,9) R(4,4) S(1,1) T(4,1)
    res = pareto(mats.values(), "tie_stiffness", "beam_strength")
    assert [r.material.name for r in res] == ["P", "R", "Q"]
    assert res.values2 == pytest.approx([1, 4, 9])


def test_pareto_cli(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "pareto", "--goals", "tie_strength_cost",
                 "tie_stiffness"]) == 0
    out = capsys.readouterr().out
    assert "non-dominated" in out and "A cheap (ref)" in out and "C dear (ref)" in out
    # B: cost index 66.7 < A's 100 and E/rho 60 < C's 70, but neither A nor C beats it on both
    assert "B mid (ref)" in out


def test_pareto_same_goal_twice_is_error(cost_csv, capsys):
    assert main(["--data", str(cost_csv), "pareto", "--goals", "tie_strength",
                 "tie_strength"]) == 2


# ---- unknown goal suggestions ---------------------------------------------------------

@pytest.mark.parametrize("cmd", [["rank", "--goal"], ["chart", "--out", "x.png", "--goal"],
                                 ["pareto", "--goals", "tie_strength"]])
def test_unknown_goal_suggests_closest(sample_csv, cmd, capsys):
    with pytest.raises(SystemExit) as e:
        main(["--data", str(sample_csv), *cmd, "beam_stifness"])
    assert e.value.code == 2
    assert "Did you mean 'beam_stiffness'" in capsys.readouterr().err


def test_goal_dashes_accepted(sample_csv, capsys):
    assert main(["--data", str(sample_csv), "rank", "--goal", "beam-stiffness"]) == 0


# ---- charts -------------------------------------------------------------------------

def test_convex_hull_square():
    hull = _convex_hull([(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)])
    assert sorted(hull) == [(0, 0), (0, 1), (1, 0), (1, 1)]


def test_class_envelope_contains_points():
    import math
    xy = [(1.0, 10.0), (2.0, 50.0), (1.5, 20.0)]
    env = class_envelope(xy, pad=0.05)
    lx = [math.log10(x) for x, _ in env]
    ly = [math.log10(y) for _, y in env]
    for x, y in xy:
        assert min(lx) < math.log10(x) < max(lx) and min(ly) < math.log10(y) < max(ly)
    assert len(class_envelope([(1.0, 1.0)])) >= 8  # single point -> a closed bubble


def test_chart_with_anisotropic_and_envelopes(cost_csv, tmp_path):
    mats = load_dataset(cost_csv).materials
    out = ashby_chart(mats, tmp_path / "e.png", kind="strength", goal="tie_strength", top=50)
    assert out.read_bytes()[:4] == b"\x89PNG"


def test_chart_cli_with_filters(cost_csv, tmp_path):
    assert main(["--data", str(cost_csv), "chart", "--out", str(tmp_path / "f.png"),
                 "--goal", "beam_stiffness", "--isotropic-only"]) == 0


def test_every_goal_has_index_entry():
    assert set(INDICES) >= {"tie_strength_cost", "beam_stiffness_cost"}


def test_show_cautions_estimated_cost_only(cost_csv, capsys):
    main(["--data", str(cost_csv), "show", "cheap"])
    assert "Caution: cost is an estimate" in capsys.readouterr().out
    main(["--data", str(cost_csv), "show", "mid"])
    assert "Caution" not in capsys.readouterr().out


def test_guide_labels_inside_axes(tmp_path):
    import matplotlib.pyplot as plt
    from material_selector import plot as P
    mats = load_dataset(write(tmp_path, COST_CSV)).materials
    captured = {}
    orig = plt.close
    plt.close = lambda fig=None: captured.setdefault("fig", fig)
    try:
        P.ashby_chart(mats, tmp_path / "g.png", kind="strength", goal="tie_strength")
    finally:
        plt.close = orig
    fig = captured["fig"]
    ax = fig.axes[0]
    r = fig.canvas.get_renderer()
    box = ax.get_window_extent(r)
    labels = [t for t in ax.texts if t.get_text().startswith("M=")]
    assert labels
    for t in labels:
        bb = t.get_window_extent(r)
        assert box.x0 - 1 <= bb.x0 and bb.x1 <= box.x1 + 1, t.get_text()
        assert box.y0 - 1 <= bb.y0 and bb.y1 <= box.y1 + 1, t.get_text()
    orig(fig)


def test_pareto_cost_goal_note_on_stderr(cost_csv, capsys):
    main(["--data", str(cost_csv), "pareto", "--goals", "tie_strength_cost", "tie_stiffness"])
    cap = capsys.readouterr()
    assert "cost goals in pareto use nominal costs; no rank band applied" in cap.err
    main(["--data", str(cost_csv), "pareto", "--goals", "tie_strength", "tie_stiffness"])
    assert "nominal costs" not in capsys.readouterr().err


def test_sourced_cost_only_no_effect_note(cost_csv, capsys):
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength", "--sourced-cost-only"])
    assert "--sourced-cost-only has no effect" in capsys.readouterr().err
    main(["--data", str(cost_csv), "rank", "--goal", "tie_strength_cost", "--sourced-cost-only"])
    assert "no effect" not in capsys.readouterr().err
    main(["--data", str(cost_csv), "pareto", "--goals", "tie_strength", "tie_stiffness",
          "--sourced-cost-only"])
    assert "no effect" in capsys.readouterr().err


def _render(mats, tmp_path, **kw):
    import matplotlib.pyplot as plt
    from material_selector import plot as P
    captured = {}
    orig = plt.close
    plt.close = lambda fig=None: captured.setdefault("fig", fig)
    try:
        P.ashby_chart(mats, tmp_path / "r.png", **kw)
    finally:
        plt.close = orig
    return captured["fig"], orig


def test_point_labels_inside_axes_and_not_overlapping(fixture_materials, tmp_path):
    fig, close = _render(fixture_materials, tmp_path, kind="modulus", goal="beam_stiffness")
    ax = fig.axes[0]
    r = fig.canvas.get_renderer()
    axbox = ax.get_window_extent(r)
    names = {m.name for m in fixture_materials}
    boxes = [t.get_window_extent(r) for t in ax.texts if t.get_text() in names]
    assert boxes
    for b in boxes:
        assert axbox.x0 - 1 <= b.x0 and b.x1 <= axbox.x1 + 1
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not a.overlaps(b)
    guides = [t for t in ax.texts if t.get_text().startswith("M=")]
    assert all(t.get_bbox_patch() is not None for t in guides)
    close(fig)


def test_legend_hollow_only_for_fully_anisotropic_classes(cost_csv, tmp_path):
    mats = load_dataset(cost_csv).materials  # composite row is anisotropic, metals not
    fig, close = _render(mats, tmp_path, kind="modulus")
    leg = fig.axes[0].get_legend()
    handles = dict(zip([t.get_text() for t in leg.get_texts()], getattr(leg, "legend_handles", None) or leg.legendHandles))
    import matplotlib.colors as mc
    assert mc.to_hex(handles["composite"].get_facecolor()[0]) == "#ffffff"
    assert mc.to_hex(handles["metal"].get_facecolor()[0]) != "#ffffff"
    close(fig)
