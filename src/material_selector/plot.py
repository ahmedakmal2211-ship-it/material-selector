"""Ashby charts (log-log) saved as PNG. Uses the non-GUI Agg backend."""

from __future__ import annotations

import math
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

    Each class gets a light padded-hull envelope; anisotropic rows are drawn
    hollow. With ``goal``, the top-``top`` materials by that index are ringed, and if
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
    by_class = {}
    for m in pts:
        by_class.setdefault(m.cls, []).append((m.density_mg_m3, getattr(m, attr)))
    for cls, xy in by_class.items():
        colour = CLASS_COLOURS.get(cls, OTHER_COLOUR)
        hull = class_envelope(xy)
        ax.fill([p[0] for p in hull], [p[1] for p in hull], color=colour, alpha=0.10,
                zorder=1, linewidth=0)
        ax.plot([p[0] for p in hull] + [hull[0][0]], [p[1] for p in hull] + [hull[0][1]],
                color=colour, alpha=0.45, linewidth=0.8, zorder=1)
    # legend proxy per class: hollow if every plotted row of the class is
    # anisotropic, filled otherwise (mixed classes show filled; see hollow key)
    all_aniso = {c: all(m.anisotropic for m in pts if m.cls == c) for c in by_class}
    for m in pts:
        colour = CLASS_COLOURS.get(m.cls, OTHER_COLOUR)
        if m.cls not in seen:
            if all_aniso[m.cls]:
                ax.scatter([], [], s=40, facecolor="white", edgecolor=colour, linewidth=1.5,
                           label=m.cls)
            else:
                ax.scatter([], [], s=36, color=colour, edgecolor="white", label=m.cls)
            seen.add(m.cls)
        x, y = m.density_mg_m3, getattr(m, attr)
        if m.anisotropic:  # hollow marker
            ax.scatter([x], [y], s=40, facecolor="white", edgecolor=colour, linewidth=1.5,
                       zorder=3)
        else:
            ax.scatter([x], [y], s=36, color=colour, edgecolor="white", linewidth=0.6,
                       zorder=3)
        texts.append(ax.annotate(m.name, (x, y), xytext=(5, 2), textcoords="offset points",
                                 fontsize=6.5, color="#333333", zorder=4))
    if any(m.anisotropic for m in pts):
        ax.scatter([], [], s=40, facecolor="white", edgecolor="#555555", linewidth=1.5,
                   label="hollow = anisotropic (along-fibre/grain value)")

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
    ringed = set()
    if goal is not None:
        idx = get_index(goal) if isinstance(goal, str) else goal
        title += f"  |  goal: {idx.key} (maximise {idx.formula})"
        ranked = rank(mats, idx, limits)
        best = [r for r in ranked[: max(top, 0)] if r.material in pts]
        best_ids = {id(r.material) for r in best}
        ringed = {i for i, m in enumerate(pts) if id(m) in best_ids}
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
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, fontsize=8,
              frameon=False)
    fig.text(0.01, 0.005, "Screening aid only; single representative values. See docs/INDICES.md.",
             fontsize=7, color="#555555")
    fig.tight_layout()
    _declutter(fig, texts, ringed)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


def _convex_hull(points):
    """Andrew's monotone chain; returns hull vertices counter-clockwise."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def class_envelope(xy, pad: float = 0.07, n: int = 16):
    """Padded convex hull around a class's points, computed in log10 space.

    Each point is replaced by a ring of ``n`` points of radius ``pad`` decades,
    so one or two points still give a closed bubble. Returns data coordinates.
    """
    ring = []
    for x, y in xy:
        lx, ly = math.log10(x), math.log10(y)
        for k in range(n):
            t = 2 * math.pi * k / n
            ring.append((lx + pad * math.cos(t), ly + pad * math.sin(t)))
    return [(10 ** a, 10 ** b) for a, b in _convex_hull(ring)]


def _declutter(fig, texts, ringed=(), max_iter: int = 60) -> None:
    """Place point labels so they overlap neither each other nor any marker.

    Greedy, top-down. For each label, candidate offsets are tried in order:
    right of the point, then left of it, at vertical shifts 0, -s, +s, -2s, ...
    (s = 7 pt). The first candidate that stays inside the axes and clears every
    already-placed label and every other point's marker (ringed points get a
    larger keep-out) wins; if none does, the least-bad inside position is used.
    Labels moved away from their point get a thin leader line.
    """
    if not texts:
        return
    from matplotlib.transforms import Bbox

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax = texts[0].axes
    px = fig.dpi / 72.0
    step = 7.0  # points
    axbox = ax.get_window_extent(renderer)

    obstacles = []  # (owner index, bbox) for every marker in display coords
    for i, t in enumerate(texts):
        cx, cy = ax.transData.transform(t.xy)
        r = (7.5 if i in ringed else 4.0) * px
        obstacles.append((i, Bbox.from_extents(cx - r, cy - r, cx + r, cy + r)))

    def box(t):
        return t.get_window_extent(renderer).expanded(1.02, 1.1)

    def cost(j, b, placed):
        inside = (b.x0 >= axbox.x0 and b.x1 <= axbox.x1
                  and b.y0 >= axbox.y0 and b.y1 <= axbox.y1)
        n = sum(1 for pb in placed if b.overlaps(pb))
        n += sum(1 for owner, ob in obstacles if owner != j and b.overlaps(ob))
        return (0 if inside else 1000) + n

    shifts = [0.0]
    for k in range(1, max_iter // 2 + 1):
        shifts += [-k * step, k * step]

    order = sorted(range(len(texts)), key=lambda i: -ax.transData.transform(texts[i].xy)[1])
    placed = []
    for j in order:
        t = texts[j]
        best = None
        for dy in shifts:
            for ha, dx in (("left", 5.0), ("right", -5.0)):
                t.set_ha(ha)
                t.set_position((dx, 2.0 + dy))
                c = cost(j, box(t), placed)
                if best is None or c < best[0]:
                    best = (c, ha, dx, dy)
                if c == 0:
                    break
            if best[0] == 0:
                break
        _, ha, dx, dy = best
        t.set_ha(ha)
        t.set_position((dx, 2.0 + dy))
        placed.append(box(t))

    # draw a thin leader for labels pushed away from their point
    for t in texts:
        if abs(t.get_position()[1] - 2.0) > 6:
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
        # (text is right-aligned so it grows leftwards; keep it inside the axes)
        xm = x1 / 1.03
        ym = (value * xm) ** (1.0 / k)
        va = "bottom"
        if ym > y1 / 1.25:  # too close to the top: hang it just below the top edge
            ym = y1 / 1.05
            xm = min(ym ** k / value, x1 / 1.03)
            va = "top"
        if y0 < ym < y1 and x0 < xm <= x1:
            txt = f"{value:.0f}" if value >= 100 else f"{value:.3g}"
            ax.annotate(f"M={txt}", (xm, ym), fontsize=6.5, color="#D55E00",
                        ha="right", va=va, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                                  edgecolor="none", alpha=0.85))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
