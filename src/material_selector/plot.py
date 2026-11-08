"""Ashby charts (log-log) saved as PNG. Uses the non-GUI Agg backend."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401

from .data import Material  # noqa: E402
from .indices import Index, get_index  # noqa: E402
from .rank import rank  # noqa: E402
from .screen import Limits  # noqa: E402

# Okabe-Ito colour-blind-safe palette.
CLASS_COLOURS = {
    "metal": "#0072B2",
    "polymer": "#E69F00",
    "composite": "#009E73",
    "ceramic": "#CC79A7",
    "wood": "#8B5A2B",
}
OTHER_COLOUR = "#7F7F7F"

KINDS = {
    "modulus": ("modulus_gpa", "Young's modulus E (GPa)"),
    "strength": ("strength_mpa", "Strength sigma_f (MPa)"),
}


def ashby_chart(
    materials: Iterable[Material],
    out: Union[str, Path],
    kind: str = "modulus",
    goal: Union[str, Index, None] = None,
    top: int = 5,
    limits: Optional[Limits] = None,
    n_guides: int = 4,
    dpi: int = 150,
) -> Path:
    """Plot density vs modulus or strength on log-log axes and save a PNG.

    With ``goal``, the top-``top`` materials by that index are ringed, and if
    the index is of the form P^n/rho for the charted property P, guide lines
    of constant index (slope 1/n) are drawn, the first through the best one.
    Materials missing density or the charted property are left off the chart.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {list(KINDS)}")
    attr, ylabel = KINDS[kind]
    mats: List[Material] = list(materials)
    pts = [
        m for m in mats
        if m.density_kg_m3 and m.density_kg_m3 > 0 and getattr(m, attr) and getattr(m, attr) > 0
    ]
    if not pts:
        raise ValueError("no materials with both density and the charted property")

    fig, ax = plt.subplots(figsize=(11, 8))
    seen = set()
    texts = []
    for m in pts:
        colour = CLASS_COLOURS.get(m.cls, OTHER_COLOUR)
        label = m.cls if m.cls not in seen else None
        seen.add(m.cls)
        x, y = m.density_mg_m3, getattr(m, attr)
        ax.scatter([x], [y], s=36, color=colour, edgecolor="white", linewidth=0.6,
                   zorder=3, label=label)
        texts.append(ax.annotate(m.name, (x, y), xytext=(5, 2), textcoords="offset points",
                                 fontsize=6.5, color="#333333", zorder=4))

    ax.set_xscale("log")
    ax.set_yscale("log")
    xs = [m.density_mg_m3 for m in pts]
    ys = [getattr(m, attr) for m in pts]
    ax.set_xlim(min(xs) / 1.25, max(xs) * 2.2)  # room on the right for labels
    ax.set_ylim(min(ys) / 1.6, max(ys) * 1.6)
    plain = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(plain)
        axis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(subs=(1.0, 2.0, 5.0)))
    ax.set_xlabel("Density rho (Mg/m^3)")
    ax.set_ylabel(ylabel)

    title = f"Density vs {kind}"
    idx = None
    if goal is not None:
        idx = get_index(goal) if isinstance(goal, str) else goal
        title += f"  |  goal: {idx.key} (maximise {idx.formula})"
        ranked = rank(mats, idx, limits)
        best = [r for r in ranked[: max(top, 0)] if r.material in pts]
        if best:
            ax.scatter([r.material.density_mg_m3 for r in best],
                       [getattr(r.material, attr) for r in best],
                       s=160, facecolor="none", edgecolor="#D55E00", linewidth=1.6,
                       zorder=5, label=f"top {len(best)} by {idx.key}")
        if best and idx.exponent and idx.property == kind:
            _guides(ax, idx, best[0].value, n_guides)

    ax.set_title(title, fontsize=10)
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.12)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=6, fontsize=8,
              frameon=False)
    fig.text(0.01, 0.005, "Screening aid only; single representative values. See docs/INDICES.md.",
             fontsize=7, color="#555555")
    fig.tight_layout()
    _declutter(fig, texts)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


def _declutter(fig, texts, max_iter: int = 60) -> None:
    """Nudge overlapping point labels apart vertically (simple greedy pass)."""
    if not texts:
        return
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    step = 7.0  # points
    for _ in range(max_iter):
        boxes = [t.get_window_extent(renderer).expanded(1.02, 1.1) for t in texts]
        moved = False
        order = sorted(range(len(texts)), key=lambda i: -boxes[i].y0)
        for a_pos, i in enumerate(order):
            for j in order[a_pos + 1:]:
                if boxes[i].overlaps(boxes[j]):
                    xo, yo = texts[j].get_position()
                    texts[j].set_position((xo, yo - step))
                    boxes[j] = texts[j].get_window_extent(renderer).expanded(1.02, 1.1)
                    moved = True
        if not moved:
            break
    # draw a thin leader for labels pushed away from their point
    for t in texts:
        if t.get_position()[1] < -6:
            t.axes.annotate("", xy=t.xy, xytext=t.get_position(), textcoords="offset points",
                        arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5,
                                        shrinkA=0, shrinkB=2), zorder=3)


def _guides(ax, idx: Index, best_value: float, n: int) -> None:
    """Lines of constant M = P^k / rho, i.e. P = (M rho)^(1/k): slope 1/k."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    k = idx.exponent
    xs = [x0, x1]
    for i in range(n):
        value = best_value / (2.0 ** i)
        ys = [(value * x) ** (1.0 / k) for x in xs]
        ax.plot(xs, ys, linestyle="--", color="#D55E00", alpha=0.55 - 0.08 * i,
                linewidth=1.0, zorder=2,
                label=f"{idx.formula} = const (slope {1.0 / k:g})" if i == 0 else None)
        # label each line at the right edge, or the top edge if it leaves there first
        xm = x1 / 1.03
        ym = (value * xm) ** (1.0 / k)
        if ym > y1 / 1.05:
            ym = y1 / 1.25
            xm = ym ** k / value
        if y0 < ym < y1 and x0 < xm <= x1:
            txt = f"{value:.0f}" if value >= 100 else f"{value:.3g}"
            ax.annotate(f"M={txt}", (xm, ym), fontsize=6.5, color="#D55E00",
                        ha="right", va="bottom")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
