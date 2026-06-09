"""
CarlQuant Logic Package.

Pure, tkinter-free business logic for the CarlQuant OCT lesion-quantification
module: surface detection, region extraction, lesion-depth calculation,
keyframe interpolation, and data I/O. Fully importable and unit-testable
headlessly.

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


from app.logic.carlquant.models import (
    RegionStats,
    Surface,
    LesionDepth,
    RegionConfig,
    AirConfig,
    SpecimenConfig,
    SliceResult,
    Specimen,
    DepthDetectionMethod,
)
from app.logic.carlquant.analysis_service import (
    AnalysisService,
    SliceAnalysis,
    SpecimenAnalysisResult,
)
from app.logic.carlquant.interpolation_service import (
    InterpolationService,
    CoordinateDescriptor,
    REGION_DESCRIPTOR,
    AIR_DESCRIPTOR,
)
from app.logic.carlquant.data_service import DataLoader, DataSaver

__all__ = [
    # Models
    "RegionStats",
    "Surface",
    "LesionDepth",
    "RegionConfig",
    "AirConfig",
    "SpecimenConfig",
    "SliceResult",
    "Specimen",
    "DepthDetectionMethod",
    # Services
    "AnalysisService",
    "SliceAnalysis",
    "SpecimenAnalysisResult",
    "InterpolationService",
    "DataLoader",
    "DataSaver",
    # Interpolation descriptors
    "CoordinateDescriptor",
    "REGION_DESCRIPTOR",
    "AIR_DESCRIPTOR",
]
