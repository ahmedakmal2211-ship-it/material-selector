"""Loading and validating the materials dataset.

Where the CSV is looked for (first hit wins):

1. an explicit ``path`` argument (CLI: ``--data PATH``);
2. the ``MATERIAL_SELECTOR_DATA`` environment variable;
3. ``data/materials.csv`` in the repository checkout (two levels above this
   package in the ``src`` layout), which also covers ``pip install -e .``.

There is no current-directory fallback, so the file used is never a surprise;
the CLI prints the resolved path. A regular (non-editable) install does not
bundle the CSV: use ``--data`` or ``MATERIAL_SELECTOR_DATA``.

Validation at load:

* the header must contain every column in ``REQUIRED_COLUMNS`` (else ValueError);
* empty property cells load as ``None`` (missing), never as 0;
* numbers may use thousands separators ("7,800"); any other non-numeric text,
  NaN or inf rejects the row with a reason (never silently missing);
* rows with a class outside ``ALLOWED_CLASSES`` or a value outside the
  plausibility ranges in ``PLAUSIBLE`` are rejected with a reason.
"""

from __future__ import annotations

import csv
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

ENV_VAR = "MATERIAL_SELECTOR_DATA"
ALLOWED_CLASSES = ("metal", "polymer", "composite", "ceramic", "wood")
REQUIRED_COLUMNS = (
    "name",
    "class",
    "density_kg_m3",
    "modulus_GPa",
    "strength_MPa",
    "strength_basis",
    "cost_usd_per_kg",
    "source_name",
    "source_url",
    "notes",
)
NUMERIC_COLUMNS = ("density_kg_m3", "modulus_GPa", "strength_MPa", "cost_usd_per_kg")

# column -> (low, high), inclusive. Values outside reject the row.
PLAUSIBLE = {
    "density_kg_m3": (100.0, 25000.0),
    "modulus_GPa": (0.001, 1200.0),
    "strength_MPa": (0.1, 20000.0),
}

_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")


@dataclass(frozen=True)
class Material:
    name: str
    cls: str
    density_kg_m3: Optional[float] = None
    modulus_gpa: Optional[float] = None
    strength_mpa: Optional[float] = None
    strength_basis: str = ""
    cost_usd_per_kg: Optional[float] = None
    source_name: str = ""
    source_url: str = ""
    notes: str = ""

    @property
    def density_mg_m3(self) -> Optional[float]:
        """Density in Mg/m^3 (kg/m^3 / 1000), the unit the indices use."""
        return None if self.density_kg_m3 is None else self.density_kg_m3 / 1000.0


@dataclass
class Dataset:
    path: Optional[Path]
    materials: List[Material] = field(default_factory=list)
    rejected: List[Tuple[str, str]] = field(default_factory=list)  # (row label, reason)


def parse_number(value: Optional[str]) -> Optional[float]:
    """Parse a numeric cell. Empty -> None. Bad text, NaN, inf -> ValueError."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if _THOUSANDS.match(text):
        text = text.replace(",", "")
    try:
        x = float(text)
    except ValueError:
        raise ValueError(f"not a number: {value!r}") from None
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f"not a finite number: {value!r}")
    return x


def _candidates() -> List[Path]:
    paths = []
    env = os.environ.get(ENV_VAR)
    if env:
        paths.append(Path(env))
    paths.append(Path(__file__).resolve().parents[2] / "data" / "materials.csv")
    return paths


def default_data_path() -> Optional[Path]:
    """First existing dataset path from the search order, or None."""
    for p in _candidates():
        if p.is_file():
            return p
    return None


def resolve_path(path: Union[str, Path, None]) -> Path:
    if path is not None:
        return Path(path)
    p = default_data_path()
    if p is None:
        searched = ", ".join(str(c) for c in _candidates())
        raise FileNotFoundError(
            f"materials.csv not found (searched: {searched}). "
            f"Pass --data PATH or set {ENV_VAR}."
        )
    return p


def material_from_row(row: dict) -> Material:
    """Build a Material from a CSV-style dict. Raises ValueError with a reason."""
    nums = {}
    for col in NUMERIC_COLUMNS:
        try:
            nums[col] = parse_number(row.get(col))
        except ValueError as e:
            raise ValueError(f"{col} {e}") from None
    cls = (row.get("class") or "").strip().lower()
    if cls not in ALLOWED_CLASSES:
        raise ValueError(f"class {cls or 'missing'!r} not in {list(ALLOWED_CLASSES)}")
    for col, (lo, hi) in PLAUSIBLE.items():
        v = nums[col]
        if v is not None and not lo <= v <= hi:
            raise ValueError(f"{col}={v:g} outside plausible range {lo:g}-{hi:g}")
    c = nums["cost_usd_per_kg"]
    if c is not None and c <= 0:
        raise ValueError(f"cost_usd_per_kg={c:g} must be positive")
    return Material(
        name=(row.get("name") or "").strip(),
        cls=cls,
        density_kg_m3=nums["density_kg_m3"],
        modulus_gpa=nums["modulus_GPa"],
        strength_mpa=nums["strength_MPa"],
        strength_basis=(row.get("strength_basis") or "").strip().lower(),
        cost_usd_per_kg=c,
        source_name=(row.get("source_name") or "").strip(),
        source_url=(row.get("source_url") or "").strip(),
        notes=(row.get("notes") or "").strip(),
    )


def read_rows(path: Union[str, Path]) -> List[dict]:
    """Read CSV rows, checking the header. Raises ValueError on a bad header."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        if not header:
            raise ValueError(f"{path}: file is empty (no header row)")
        names = [h.strip() for h in header]
        missing = [c for c in REQUIRED_COLUMNS if c not in names]
        if missing:
            raise ValueError(f"{path}: header is missing required column(s): {', '.join(missing)}")
        return [{(k or "").strip(): v for k, v in r.items()} for r in reader]


def build_dataset(rows: Iterable[dict], path: Optional[Path] = None) -> Dataset:
    ds = Dataset(path=path)
    for i, r in enumerate(rows, start=2):  # line 1 is the header
        if not any(isinstance(v, str) and v.strip() for v in r.values()):
            continue  # blank line
        name = (r.get("name") or "").strip()
        label = name or f"line {i}"
        if not name:
            ds.rejected.append((label, "name missing"))
            continue
        try:
            ds.materials.append(material_from_row(r))
        except ValueError as e:
            ds.rejected.append((label, str(e)))
    return ds


def load_dataset(path: Union[str, Path, None] = None) -> Dataset:
    """Load and validate the dataset; rejected rows are kept with reasons."""
    p = resolve_path(path)
    return build_dataset(read_rows(p), p)


def load_materials(path: Union[str, Path, None] = None) -> List[Material]:
    """Load valid materials only (see ``load_dataset`` for rejects)."""
    return load_dataset(path).materials


def materials_from_dicts(rows: Iterable[dict]) -> List[Material]:
    """Build valid materials from CSV-style dicts (handy for tests and scripts)."""
    return build_dataset(rows).materials
