import subprocess
import sys

from material_selector.cli import main
from material_selector.plot import ashby_chart


def test_goals_lists_all(capsys):
    assert main(["goals"]) == 0
    out = capsys.readouterr().out
    for g in ("tie_stiffness", "beam_stiffness", "panel_strength", "column_buckling"):
        assert g in out


def test_rank_cli(sample_csv, capsys):
    assert main(["--data", str(sample_csv), "rank", "--goal", "beam_stiffness", "--top", "3"]) == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln[:1].isdigit() and "ranked," not in ln]
    assert len(lines) == 3
    assert "CFRP (ref)" in lines[0]


def test_rank_cli_limits_and_class(sample_csv, capsys):
    rc = main(["--data", str(sample_csv), "rank", "--goal", "tie_strength_cost",
               "--class", "metal", "--max-cost", "3", "--min-modulus", "70", "-v"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Steel (ref)" in out and "Aluminium (ref)" in out
    assert "excluded: CFRP (ref)" in out
    assert "excluded: Blank cost (ref)" in out  # missing cost fails --max-cost


def test_missing_data_file_is_clean_error(tmp_path, capsys):
    assert main(["--data", str(tmp_path / "nope.csv"), "rank", "--goal", "tie_stiffness"]) == 2


def test_python_dash_m_entry_point():
    r = subprocess.run([sys.executable, "-m", "material_selector", "goals"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "beam_stiffness" in r.stdout


def test_plot_writes_png(fixture_materials, tmp_path):
    out = ashby_chart(fixture_materials, tmp_path / "m.png", kind="modulus",
                      goal="beam_stiffness", top=3)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    out2 = ashby_chart(fixture_materials, tmp_path / "s.png", kind="strength",
                       goal="tie_strength")
    assert out2.stat().st_size > 1000


def test_plot_goal_on_other_property_and_cost_goal(fixture_materials, tmp_path):
    # no guide lines possible, but must still render
    ashby_chart(fixture_materials, tmp_path / "a.png", kind="strength", goal="beam_stiffness")
    ashby_chart(fixture_materials, tmp_path / "b.png", kind="modulus", goal="beam_stiffness_cost")


def test_chart_cli(sample_csv, tmp_path, capsys):
    out = tmp_path / "c.png"
    assert main(["--data", str(sample_csv), "chart", "--out", str(out), "--kind", "modulus",
                 "--goal", "beam_stiffness"]) == 0
    assert out.exists()


def test_chart_out_without_extension_gets_png(tmp_path, capsys):
    from material_selector.cli import main

    target = tmp_path / "noext"
    code = main(["chart", "--kind", "modulus", "--out", str(target)])
    assert code == 0
    assert (tmp_path / "noext.png").exists()
    assert "noext.png" in capsys.readouterr().out
