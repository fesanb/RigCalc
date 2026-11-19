"""Stable, UI-facing results for the Vectorworks RigCalc palette.

This package deliberately has no Vectorworks dependency.  A Vectorworks SDK
palette can consume the serializable snapshot while using ``object_refs`` only
inside the active Vectorworks process for selection and zoom commands.
"""

from .snapshot import PaletteRun, build_palette_run
from .history import build_history

__all__ = ["PaletteRun", "build_palette_run", "build_history"]
