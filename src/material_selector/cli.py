"""Command-line interface: ``material-selector {goals,rank,show,pareto,chart}``.

Exit codes: 0 ok, 2 usage or data error (bad arguments, unknown goal,
missing/unreadable or malformed CSV, nothing ranked, nothing to plot,
no/ambiguous ``show`` match). Errors are one line on stderr, never a traceback.

With ``rank --format csv|json`` stdout carries only the data; the data path,
notes and the screening-aid line go to stderr.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import math
import os
import sys
from typing import List, Optional, Sequence

from .data import ALLOWED_CLASSES, STRENGTH_BASES, Dataset, Material, load_dataset
from .indices import INDICES
from .rank import DEFAULT_COST_FACTORS, DEFAULT_TIE_TOL_PCT, pareto, rank, uses_cost
from .screen import Limits

DISCLAIMER = ("Screening aid only (single representative values, see docs/INDICES.md); "
              "not a design check.")


class _Out:
    """Routes informational lines to stdout, or stderr for machine formats."""

    def __init__(self, machine: bool = False):
        self.info_stream = sys.stderr if machine else sys.stdout

    def info(self, text: str = "") -> None:
        print(text, file=self.info_stream)


def _table(headers: Sequence[str], rows: List[Sequence[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    sep = "  ".join("-" * w for w in widths)
    body = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    return "\n".join([line.rstrip(), sep, *body])


def _markdown(headers: Sequence[str], rows: List[Sequence[str]]) -> str:
    esc = lambda s: s.replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _fmt(x: Optional[float]) -> str:
    return "-" if x is None else f"{x:.4g}"


# ---- argparse types ---------------------------------------------------------

def nonneg_float(text: str) -> float:
    """argparse type: finite, non-negative float (rejects nan, inf, negatives)."""
    try:
        x = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if math.isnan(x) or math.isinf(x):
        raise argparse.ArgumentTypeError(f"must be finite: {text!r}")
    if x < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0: {text!r}")
    return x


def factor_float(text: str) -> float:
    """argparse type: finite float >= 1 (an x/÷ uncertainty factor)."""
    x = nonneg_float(text)
    if x < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1: {text!r}")
    return x


def positive_int(text: str) -> int:
    """argparse type: integer >= 1."""
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1: {text!r}")
    return n


def goal_name(text: str) -> str:
    """argparse type: a known goal; suggests the closest name otherwise."""
    key = text.strip().lower().replace("-", "_")
    if key in INDICES:
        return key
    close = difflib.get_close_matches(key, list(INDICES), n=1, cutoff=0.5)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    raise argparse.ArgumentTypeError(
        f"unknown goal {text!r}.{hint} Run 'material-selector goals' to list them.")


# ---- helpers ----------------------------------------------------------------

def _limits(a: argparse.Namespace) -> Limits:
    return Limits(
        min_modulus_gpa=a.min_modulus,
        min_strength_mpa=a.min_strength,
        max_density_kg_m3=a.max_density,
        max_cost_usd_per_kg=a.max_cost,
        classes=a.classes,
        strength_bases=a.strength_basis,
        isotropic_only=a.isotropic_only,
        sourced_cost_only=a.sourced_cost_only,
    )


def _load(a: argparse.Namespace, out: Optional[_Out] = None) -> Dataset:
    out = out or _Out()
    ds = load_dataset(a.data)
    out.info(f"data: {ds.path}")
    if ds.rejected:
        out.info(f"{len(ds.rejected)} row(s) rejected at load (use -v for reasons).")
        if getattr(a, "verbose", False):
            for label, why in ds.rejected:
                out.info(f"  rejected: {label}: {why}")
    if not ds.materials:
        raise ValueError(f"{ds.path}: no valid materials in file")
    return ds


def _report_dropped(res, a, out: _Out) -> None:
    if getattr(a, "verbose", False):
        for m, why in res.excluded:
            out.info(f"  excluded: {m.name}: {why}")
        for m, why in res.skipped:
            out.info(f"  skipped:  {m.name}: {why}")


def _basis_note(materials: Sequence[Material], out: _Out) -> None:
    bases = sorted({m.strength_basis for m in materials if m.strength_basis})
    if len(bases) > 1:
        out.info(f"Note: strength values mix bases ({', '.join(bases)}); yield, tensile and "
                 "flexural strengths are not directly comparable.")


PARETO_COST_NOTE = "Note: cost goals in pareto use nominal costs; no rank band applied."


def _sourced_flag_note(a: argparse.Namespace, cost_used: bool) -> None:
    if getattr(a, "sourced_cost_only", False) and not cost_used:
        print("Note: --sourced-cost-only has no effect: the goal does not use cost.",
              file=sys.stderr)


def _material_record(m: Material) -> dict:
    return {
        "name": m.name, "class": m.cls, "density_kg_m3": m.density_kg_m3,
        "modulus_GPa": m.modulus_gpa, "strength_MPa": m.strength_mpa,
        "strength_basis": m.strength_basis, "cost_usd_per_kg": m.cost_usd_per_kg,
        "cost_confidence": m.cost_confidence, "cost_source_url": m.cost_source_url,
        "anisotropic": m.anisotropic, "source_name": m.source_name,
        "source_url": m.source_url, "notes": m.notes,
    }


# ---- commands ---------------------------------------------------------------

def cmd_goals(a: argparse.Namespace) -> int:
    rows = [(i.key, i.formula, i.units, i.description) for i in INDICES.values()]
    print(_table(["goal", "maximise", "units", "description"], rows))
    print(DISCLAIMER)
    return 0


def cmd_rank(a: argparse.Namespace) -> int:
    idx = INDICES[a.goal]
    machine = a.format in ("csv", "json")
    out = _Out(machine)
    ds = _load(a, out)
    _sourced_flag_note(a, uses_cost(idx))
    factors = {"estimated": a.cost_factor_estimated, "sourced": a.cost_factor_sourced}
    res = rank(ds.materials, idx, _limits(a), tie_tol=a.tie_tol, cost_factors=factors)
    out.info(f"Goal: {idx.key} - {idx.name}. Maximise {idx.formula} [{idx.units}]")
    _report_dropped(res, a, out)
    if not res:
        print(f"error: no materials ranked ({len(res.excluded)} excluded by limits, "
              f"{len(res.skipped)} skipped for missing data). Relax the limits.",
              file=sys.stderr)
        return 2
    shown = res[: a.top]
    cost_goal = uses_cost(idx)

    if a.format == "json":
        recs = []
        for r in shown:
            rec = {"rank": r.rank, "tie": r.tie == "~", "rank_band": r.band_text or None,
                   "goal": idx.key, "index_value": r.value, "index_units": idx.units}
            rec.update(_material_record(r.material))
            recs.append(rec)
        print(json.dumps(recs, indent=2))
    elif a.format == "csv":
        buf = io.StringIO()
        fields = ["rank", "tie", "rank_band", "goal", "index_value", "index_units",
                  *_material_record(shown[0].material).keys()]
        w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in shown:
            rec = {"rank": r.rank, "tie": r.tie, "rank_band": r.band_text, "goal": idx.key,
                   "index_value": f"{r.value:.6g}", "index_units": idx.units}
            rec.update(_material_record(r.material))
            rec["anisotropic"] = "yes" if r.material.anisotropic else "no"
            w.writerow({k: ("" if v is None else v) for k, v in rec.items()})
        sys.stdout.write(buf.getvalue())
    else:
        headers = ["rank", "tie", *(["rank band"] if cost_goal else []), "material", "class",
                   "index", "rho kg/m3", "E GPa", "sigma MPa", "basis", "USD/kg",
                   *(["cost"] if cost_goal else []), "aniso"]
        rows = []
        for r in shown:
            m = r.material
            rows.append([str(r.rank), r.tie or "", *([r.band_text] if cost_goal else []),
                         m.name, m.cls, f"{r.value:.4g}", _fmt(m.density_kg_m3),
                         _fmt(m.modulus_gpa), _fmt(m.strength_mpa), m.strength_basis or "-",
                         _fmt(m.cost_usd_per_kg), *([m.cost_confidence] if cost_goal else []),
                         "yes" if m.anisotropic else "no"])
        print((_markdown if a.format == "markdown" else _table)(headers, rows))

    out.info(f"\n{len(res)} ranked, {len(res.excluded)} excluded by limits, "
             f"{len(res.skipped)} skipped (missing data). "
             f"'~' = within {a.tie_tol:g}% of the material above (treat as a tie).")
    if cost_goal:
        out.info(f"Rank band = best-worst rank if each cost is off by x/÷ "
                 f"{a.cost_factor_estimated:g} (estimated) or {a.cost_factor_sourced:g} "
                 "(sourced). See docs/INDICES.md, Uncertainty.")
    _basis_note([r.material for r in res], out)
    if any(r.material.anisotropic for r in shown):
        out.info("Note: anisotropic rows use one along-fibre/grain value; "
                 "use --isotropic-only to drop them.")
    out.info(DISCLAIMER)
    return 0


def _find(materials: Sequence[Material], query: str) -> List[Material]:
    q = query.strip().lower()
    exact = [m for m in materials if m.name.lower() == q]
    return exact or [m for m in materials if q in m.name.lower()]


def cmd_show(a: argparse.Namespace) -> int:
    ds = _load(a)
    hits = _find(ds.materials, a.name)
    if not hits:
        print(f"error: no material matches {a.name!r}", file=sys.stderr)
        return 2
    if len(hits) > 1:
        print(f"error: {a.name!r} matches {len(hits)} materials; be more specific:",
              file=sys.stderr)
        for m in hits:
            print(f"  {m.name}", file=sys.stderr)
        return 2
    m = hits[0]
    rec = _material_record(m)
    rec["anisotropic"] = "yes" if m.anisotropic else "no"
    labels = {"density_kg_m3": "density (kg/m^3)", "modulus_GPa": "modulus E (GPa)",
              "strength_MPa": "strength (MPa)", "cost_usd_per_kg": "cost (USD/kg)"}
    width = max(len(labels.get(k, k)) for k in rec)
    for k, v in rec.items():
        if isinstance(v, float):
            v = f"{v:g}"
        print(f"{labels.get(k, k).ljust(width)}  {v if v not in (None, '') else '-'}")
    if m.cost_confidence == "estimated":
        print("Caution: cost is an estimate (no price source); treat it as order-of-magnitude.")
    print()
    print(_table(["goal", "value", "units"],
                 [(i.key, _fmt(i.value(m)), i.units) for i in INDICES.values()]))
    print(DISCLAIMER)
    return 0


def cmd_pareto(a: argparse.Namespace) -> int:
    g1, g2 = a.goals
    if g1 == g2:
        raise ValueError("--goals needs two different goals")
    i1, i2 = INDICES[g1], INDICES[g2]
    ds = _load(a)
    if uses_cost(i1) or uses_cost(i2):
        print(PARETO_COST_NOTE, file=sys.stderr)
    _sourced_flag_note(a, uses_cost(i1) or uses_cost(i2))
    res = pareto(ds.materials, i1, i2, _limits(a))
    _report_dropped(res, a, _Out())
    if not res:
        print("error: no materials have values for both goals after screening.",
              file=sys.stderr)
        return 2
    print(f"Pareto front: maximise {i1.key} ({i1.formula}) and {i2.key} ({i2.formula})")
    rows = [(r.material.name, r.material.cls, f"{r.value:.4g}", f"{v2:.4g}")
            for r, v2 in zip(res, res.values2)]
    print(_table(["material", "class", i1.key, i2.key], rows))
    print(f"\n{len(res)} non-dominated of {res.considered} with both values "
          f"({len(res.excluded)} excluded by limits, {len(res.skipped)} skipped).")
    print("No other material is at least as good on both goals and better on one.")
    _basis_note([r.material for r in res], _Out())
    print(DISCLAIMER)
    return 0


def cmd_chart(a: argparse.Namespace) -> int:
    from .plot import ashby_chart  # import matplotlib only when needed

    ds = _load(a)
    out_path = a.out if os.path.splitext(a.out)[1] else a.out + ".png"
    out = ashby_chart(ds.materials, out_path, kind=a.kind, goal=a.goal, top=a.top,
                      limits=_limits(a))
    print(f"wrote {out}")
    print(DISCLAIMER)
    return 0


# ---- parser -----------------------------------------------------------------

def _add_limits(p: argparse.ArgumentParser) -> None:
    p.add_argument("--min-modulus", type=nonneg_float, metavar="GPA",
                   help="minimum E, GPa (inclusive)")
    p.add_argument("--min-strength", type=nonneg_float, metavar="MPA",
                   help="minimum strength, MPa (inclusive)")
    p.add_argument("--max-density", type=nonneg_float, metavar="KG_M3",
                   help="maximum density, kg/m^3 (inclusive)")
    p.add_argument("--max-cost", type=nonneg_float, metavar="USD_KG",
                   help="maximum cost, USD/kg (inclusive)")
    p.add_argument("--class", dest="classes", nargs="+", metavar="CLASS",
                   choices=list(ALLOWED_CLASSES),
                   help=f"allowed classes ({' '.join(ALLOWED_CLASSES)})")
    p.add_argument("--strength-basis", action="extend", nargs="+", metavar="BASIS",
                   choices=list(STRENGTH_BASES),
                   help="keep only these strength bases (yield tensile flexural); repeatable")
    p.add_argument("--isotropic-only", action="store_true",
                   help="drop rows flagged anisotropic (composites, wood)")
    p.add_argument("--sourced-cost-only", action="store_true",
                   help="for cost goals, drop rows whose cost is only estimated")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="list rejected, excluded and skipped materials with reasons")


GOALS_HELP = "one of: " + ", ".join(INDICES)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="material-selector",
                                description="Ashby-style material selection. " + DISCLAIMER)
    p.add_argument("--data", metavar="CSV",
                   help="path to materials.csv (default: $MATERIAL_SELECTOR_DATA, "
                        "then the repository's data/materials.csv)")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("goals", help="list design goals (indices)")
    g.set_defaults(func=cmd_goals)

    r = sub.add_parser("rank", help="rank materials for a goal")
    r.add_argument("--goal", required=True, type=goal_name, metavar="GOAL", help=GOALS_HELP)
    r.add_argument("--top", type=positive_int, default=10, help="rows to show (default 10)")
    r.add_argument("--format", choices=["table", "csv", "json", "markdown"], default="table",
                   help="output format (default table); csv/json keep stdout machine-readable")
    r.add_argument("--tie-tol", type=nonneg_float, default=DEFAULT_TIE_TOL_PCT, metavar="PCT",
                   help="mark '~' when within PCT %% of the material above (default 5)")
    r.add_argument("--cost-factor-estimated", type=factor_float, metavar="F",
                   default=DEFAULT_COST_FACTORS["estimated"],
                   help="x/÷ uncertainty on estimated costs for the rank band (default 2.0)")
    r.add_argument("--cost-factor-sourced", type=factor_float, metavar="F",
                   default=DEFAULT_COST_FACTORS["sourced"],
                   help="x/÷ uncertainty on sourced costs for the rank band (default 1.5)")
    _add_limits(r)
    r.set_defaults(func=cmd_rank)

    s = sub.add_parser("show", help="print every property of one material")
    s.add_argument("name", help="case-insensitive name or unique part of it")
    s.set_defaults(func=cmd_show)

    pa = sub.add_parser("pareto", help="non-dominated materials for two goals")
    pa.add_argument("--goals", required=True, nargs=2, type=goal_name, metavar=("G1", "G2"),
                    help=GOALS_HELP)
    _add_limits(pa)
    pa.set_defaults(func=cmd_pareto)

    c = sub.add_parser("chart", help="save an Ashby chart PNG")
    c.add_argument("--out", required=True, help="output PNG path")
    c.add_argument("--kind", choices=["modulus", "strength"], default="modulus")
    c.add_argument("--goal", type=goal_name, metavar="GOAL",
                   help="highlight top materials and draw index guide lines; " + GOALS_HELP)
    c.add_argument("--top", type=positive_int, default=5,
                   help="materials to highlight (default 5)")
    _add_limits(c)
    c.set_defaults(func=cmd_chart)
    return p


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # not a reconfigurable text stream (e.g. captured in tests)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_streams()
    args = build_parser().parse_args(argv)  # argparse exits 2 on bad usage
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as e:
        msg = (e.args[0] if isinstance(e, KeyError) and e.args else str(e)).strip()
        msg = msg or e.__class__.__name__
        print(f"error: {msg.splitlines()[0]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
