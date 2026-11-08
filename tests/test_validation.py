"""Tests for the red-team fixes: validation, exit codes, data path, notes."""

import os
import subprocess
import sys

import pytest

from material_selector.cli import main
from material_selector.data import (
    ALLOWED_CLASSES, ENV_VAR, build_dataset, default_data_path, load_dataset, parse_number,
)

from conftest import SAMPLE_CSV

HEADER = SAMPLE_CSV.splitlines()[0]


def write(tmp_path, text, name="m.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def row(name="X", cls="metal", rho="7850", E="210", s="250", basis="yield", cost="1"):
    return {"name": name, "class": cls, "density_kg_m3": rho, "modulus_GPa": E,
            "strength_MPa": s, "strength_basis": basis, "cost_usd_per_kg": cost,
            "source_name": "x", "source_url": "https://example.org", "notes": ""}


# 1. header validation, empty CSV, nothing ranked -> exit 2

def test_missing_column_is_clear_error(tmp_path, capsys):
    p = write(tmp_path, "name,class,density_kg_m3\nA,metal,7850\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_dataset(p)
    assert main(["--data", str(p), "rank", "--goal", "tie_stiffness"]) == 2
    err = capsys.readouterr().err
    assert "missing required column" in err and "modulus_GPa" in err
    assert "Traceback" not in err


def test_empty_file_exit_2(tmp_path, capsys):
    p = write(tmp_path, "")
    assert main(["--data", str(p), "rank", "--goal", "tie_stiffness"]) == 2
    assert "empty" in capsys.readouterr().err


def test_header_only_exit_2(tmp_path, capsys):
    p = write(tmp_path, HEADER + "\n")
    assert main(["--data", str(p), "rank", "--goal", "tie_stiffness"]) == 2
    assert "no valid materials" in capsys.readouterr().err


def test_zero_ranked_exit_2(sample_csv, capsys):
    rc = main(["--data", str(sample_csv), "rank", "--goal", "tie_stiffness",
               "--min-modulus", "1000"])
    assert rc == 2
    assert "no materials ranked" in capsys.readouterr().err


# 2. resolved data path printed; no cwd fallback

def test_rank_and_chart_print_data_path(sample_csv, tmp_path, capsys):
    main(["--data", str(sample_csv), "rank", "--goal", "tie_stiffness"])
    assert f"data: {sample_csv}" in capsys.readouterr().out
    main(["--data", str(sample_csv), "chart", "--out", str(tmp_path / "c.png")])
    assert f"data: {sample_csv}" in capsys.readouterr().out


def test_env_var_used(sample_csv, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(sample_csv))
    assert default_data_path() == sample_csv


def test_no_cwd_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    (tmp_path / "data").mkdir()
    cwd_csv = write(tmp_path / "data", SAMPLE_CSV, "materials.csv")
    monkeypatch.chdir(tmp_path)
    assert default_data_path() != cwd_csv


# 3. number parsing, plausibility, limit argument types

def test_thousands_separator_parsed():
    assert parse_number("7,800") == 7800.0
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("") is None


@pytest.mark.parametrize("bad", ["abc", "7,80", "nan", "inf", "-inf", "12 GPa"])
def test_bad_numbers_raise(bad):
    with pytest.raises(ValueError):
        parse_number(bad)


@pytest.mark.parametrize("kw, field", [
    ({"rho": "abc"}, "density_kg_m3"),
    ({"E": "nan"}, "modulus_GPa"),
    ({"rho": "99"}, "density_kg_m3"),
    ({"rho": "25001"}, "density_kg_m3"),
    ({"E": "0.0009"}, "modulus_GPa"),
    ({"E": "1201"}, "modulus_GPa"),
    ({"s": "0.09"}, "strength_MPa"),
    ({"s": "20001"}, "strength_MPa"),
    ({"cost": "-1"}, "cost_usd_per_kg"),
    ({"cls": "unobtainium"}, "class"),
])
def test_implausible_or_bad_rows_rejected_with_reason(kw, field):
    ds = build_dataset([row(**kw)])
    assert ds.materials == []
    assert len(ds.rejected) == 1
    assert field in ds.rejected[0][1]


def test_plausibility_bounds_inclusive():
    ds = build_dataset([row(rho="100", E="0.001", s="0.1"),
                        row(name="Y", rho="25000", E="1200", s="20000")])
    assert len(ds.materials) == 2 and not ds.rejected


def test_thousands_row_loads():
    ds = build_dataset([row(rho="7,800")])
    assert ds.materials[0].density_kg_m3 == 7800.0


def test_rejected_rows_reported_in_cli(tmp_path, capsys):
    p = write(tmp_path, SAMPLE_CSV + "Bad (ref),metal,abc,200,250,yield,1,x,https://e.org,\n")
    assert main(["--data", str(p), "rank", "--goal", "tie_stiffness", "-v"]) == 0
    out = capsys.readouterr().out
    assert "1 row(s) rejected" in out
    assert "rejected: Bad (ref): density_kg_m3 not a number" in out


@pytest.mark.parametrize("flag", ["--min-modulus", "--min-strength", "--max-density",
                                  "--max-cost"])
@pytest.mark.parametrize("value", ["nan", "inf", "-1", "abc"])
def test_bad_limit_values_rejected_by_argparse(sample_csv, flag, value, capsys):
    with pytest.raises(SystemExit) as e:
        main(["--data", str(sample_csv), "rank", "--goal", "tie_stiffness", flag, value])
    assert e.value.code == 2


# 4. OSError / ValueError -> exit 2, no traceback; UTF-8 output

def test_data_path_is_directory(tmp_path, capsys):
    assert main(["--data", str(tmp_path), "rank", "--goal", "tie_stiffness"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error:") and "Traceback" not in err


def test_chart_with_nothing_plottable(tmp_path, capsys):
    p = write(tmp_path, HEADER + "\nNo E (ref),metal,7850,,250,yield,1,x,https://e.org,\n")
    rc = main(["--data", str(p), "chart", "--out", str(tmp_path / "x.png"), "--kind", "modulus"])
    assert rc == 2
    assert "no materials" in capsys.readouterr().err


def test_non_ascii_names_under_legacy_console_encoding(tmp_path):
    p = write(tmp_path, HEADER + "\nΩ-中 steel (ref),metal,7850,210,250,yield,1,x,https://e.org,\n")
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    r = subprocess.run([sys.executable, "-m", "material_selector", "--data", str(p), "rank",
                        "--goal", "tie_stiffness"], capture_output=True, env=env)
    assert r.returncode == 0, r.stderr
    assert b"Traceback" not in r.stderr


# 5. disclaimer everywhere, mixed strength basis note

def test_disclaimer_on_goals_and_chart(sample_csv, tmp_path, capsys):
    main(["goals"])
    assert "Screening aid only" in capsys.readouterr().out
    main(["--data", str(sample_csv), "chart", "--out", str(tmp_path / "c.png")])
    assert "Screening aid only" in capsys.readouterr().out


def test_mixed_basis_note(sample_csv, capsys):
    main(["--data", str(sample_csv), "rank", "--goal", "tie_strength"])
    out = capsys.readouterr().out
    assert "mix bases" in out and "tensile" in out and "yield" in out


def test_no_basis_note_when_single_basis(sample_csv, capsys):
    main(["--data", str(sample_csv), "rank", "--goal", "tie_strength", "--class", "metal"])
    assert "mix bases" not in capsys.readouterr().out


# 6. --top >= 1

@pytest.mark.parametrize("cmd", [["rank", "--goal", "tie_stiffness"],
                                 ["chart", "--out", "x.png"]])
@pytest.mark.parametrize("value", ["0", "-3", "two"])
def test_top_must_be_positive(sample_csv, cmd, value):
    with pytest.raises(SystemExit) as e:
        main(["--data", str(sample_csv), *cmd, "--top", value])
    assert e.value.code == 2


# wood class

def test_wood_is_valid_class(tmp_path, capsys):
    assert "wood" in ALLOWED_CLASSES
    p = write(tmp_path, HEADER + "\nOak (ref),wood,755,12,100,flexural,0.8,x,https://e.org,\n")
    assert main(["--data", str(p), "rank", "--goal", "beam_stiffness", "--class", "wood"]) == 0
    assert "Oak (ref)" in capsys.readouterr().out


def test_wood_has_plot_colour():
    from material_selector.plot import CLASS_COLOURS
    assert set(ALLOWED_CLASSES) <= set(CLASS_COLOURS)
