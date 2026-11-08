"""Command-line interface: ``material-selector {goals,rank,chart}``.

Exit codes: 0 ok, 2 usage or data error (bad arguments, missing/unreadable or
malformed CSV, nothing ranked, nothing to plot). Errors are one line on
stderr, never a traceback.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from typing import List, Optional, Sequence

from .data import ALLOWED_CLASSES, Dataset, load_dataset
from .indices import INDICES
from .rank import rank
from .screen import Limits

DISCLAIMER = ("Screening aid only (single representative values, see docs/INDICES.md); "
              "not a design check.")


def _table(headers: Sequence[str], rows: List[Sequence[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    sep = "  ".join("-" * w for w in widths)
    body = ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join([line, sep, *body])


def _fmt(x: Optional[float]) -> str:
    return "-" if x is None else f"{x:.4g}"


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


def positive_int(text: str) -> int:
    """argparse type: integer >= 1."""
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1: {text!r}")
    return n


def _limits(a: argparse.Namespace) -> Limits:
    return Limits(
        min_modulus_gpa=a.min_modulus,
        min_strength_mpa=a.min_strength,
        max_density_kg_m3=a.max_density,
        max_cost_usd_per_kg=a.max_cost,
        classes=a.classes,
    )


def _load(a: argparse.Namespace) -> Dataset:
    ds = load_dataset(a.data)
    print(f"data: {ds.path}")
    if ds.rejected:
        print(f"{len(ds.rejected)} row(s) rejected at load (use -v for reasons).")
        if getattr(a, "verbose", False):
            for label, why in ds.rejected:
                print(f"  rejected: {label}: {why}")
    if not ds.materials:
        raise ValueError(f"{ds.path}: no valid materials in file")
    return ds


def cmd_goals(a: argparse.Namespace) -> int:
    rows = [(i.key, i.formula, i.units, i.description) for i in INDICES.values()]
    print(_table(["goal", "maximise", "units", "description"], rows))
    print(DISCLAIMER)
    return 0


def cmd_rank(a: argparse.Namespace) -> int:
    idx = INDICES[a.goal]
    ds = _load(a)
    res = rank(ds.materials, idx, _limits(a))
    print(f"Goal: {idx.key} - {idx.name}. Maximise {idx.formula} [{idx.units}]")
    if a.verbose:
        for m, why in res.excluded:
            print(f"  excluded: {m.name}: {why}")
        for m, why in res.skipped:
            print(f"  skipped:  {m.name}: {why}")
    if not res:
        print(f"error: no materials ranked ({len(res.excluded)} excluded by limits, "
              f"{len(res.skipped)} skipped for missing data). Relax the limits.",
              file=sys.stderr)
        return 2
    shown = res[: a.top]
    rows = [(str(r.rank), r.material.name, r.material.cls, f"{r.value:.4g}",
             _fmt(r.material.density_kg_m3), _fmt(r.material.modulus_gpa),
             _fmt(r.material.strength_mpa), r.material.strength_basis or "-",
             _fmt(r.material.cost_usd_per_kg))
            for r in shown]
    print(_table(["rank", "material", "class", "index", "rho kg/m3", "E GPa",
                  "sigma MPa", "basis", "USD/kg"], rows))
    print(f"\n{len(res)} ranked, {len(res.excluded)} excluded by limits, "
          f"{len(res.skipped)} skipped (missing data).")
    bases = sorted({r.material.strength_basis for r in res if r.material.strength_basis})
    if len(bases) > 1:
        print(f"Note: strength values mix bases ({', '.join(bases)}); yield, tensile and "
              "flexural strengths are not directly comparable.")
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
    p.add_argument("-v", "--verbose", action="store_true",
                   help="list rejected, excluded and skipped materials with reasons")


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
    r.add_argument("--goal", required=True, choices=list(INDICES))
    r.add_argument("--top", type=positive_int, default=10, help="rows to show (default 10)")
    _add_limits(r)
    r.set_defaults(func=cmd_rank)

    c = sub.add_parser("chart", help="save an Ashby chart PNG")
    c.add_argument("--out", required=True, help="output PNG path")
    c.add_argument("--kind", choices=["modulus", "strength"], default="modulus")
    c.add_argument("--goal", choices=list(INDICES),
                   help="highlight top materials and draw index guide lines")
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
    except (OSError, ValueError) as e:
        msg = str(e).strip() or e.__class__.__name__
        print(f"error: {msg.splitlines()[0]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
