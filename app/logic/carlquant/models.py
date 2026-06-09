"""
CarlQuant Logic Models.

Boundary data structures for the CarlQuant analysis pipeline — the tkinter-free domain models that cross the view/logic boundary. Surfaces canonical definitions from specimen_model and carl_quant_core so consumers have a single, stable import location.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
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
