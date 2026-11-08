"""Ashby-style material selection: indices, screening limits, ranking and charts.

See docs/INDICES.md for the derivations and assumptions behind every index.
"""

from .data import Material, load_materials, default_data_path
from .indices import INDICES, Index, get_index
from .screen import Limits, screen
from .rank import rank, RankedMaterial

__version__ = "0.1.0"

__all__ = [
    "Material",
    "load_materials",
    "default_data_path",
    "INDICES",
    "Index",
    "get_index",
    "Limits",
    "screen",
    "rank",
    "RankedMaterial",
    "__version__",
]
