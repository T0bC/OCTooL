"""
CarlQuant Logic Models

Boundary data structures for the CarlQuant analysis pipeline. These are the
tkinter-free domain models that cross the view/logic boundary.

The canonical dataclass definitions live in
``app.logic.carlquant.specimen_model`` and the detection-method enum in
``app.logic.carlquant.carl_quant_core``. They are surfaced here so consumers have
a single, stable import location for the boundary models.
"""
from app.logic.carlquant.specimen_model import (
    RegionStats,
    Surface,
    LesionDepth,
    RegionConfig,
    AirConfig,
    SpecimenConfig,
    SliceResult,
    Specimen,
)
from app.logic.carlquant.carl_quant_core import DepthDetectionMethod

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
