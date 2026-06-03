"""
CarlQuant Logic Models

Boundary data structures for the CarlQuant analysis pipeline. These are the
tkinter-free domain models that cross the view/logic boundary.

The canonical dataclass definitions currently live in
``CarlQuant.specimen_model`` (pure, tkinter-free) and the detection-method enum
in ``CarlQuant.carl_quant_core``. They are surfaced here so the logic layer has a
single, stable import location independent of the legacy view package. When the
view panels are relocated to ``app/view/carlquant`` these definitions can be moved
physically into this module without changing any logic-layer imports.
"""
from CarlQuant.specimen_model import (
    RegionStats,
    Surface,
    LesionDepth,
    RegionConfig,
    AirConfig,
    SpecimenConfig,
    SliceResult,
    Specimen,
)
from CarlQuant.carl_quant_core import DepthDetectionMethod

__all__ = [
    "RegionStats",
    "Surface",
    "LesionDepth",
    "RegionConfig",
    "AirConfig",
    "SpecimenConfig",
    "SliceResult",
    "Specimen",
    "DepthDetectionMethod",
]
