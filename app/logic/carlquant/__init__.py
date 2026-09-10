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

from typing import TYPE_CHECKING

# Symbols are resolved lazily (PEP 562) so that importing a single submodule --
# notably ``specimen_worker`` inside a spawned process pool worker -- does not
# drag in the whole service layer (numpy, PIL, openpyxl, data_io). On Windows and
# macOS ``multiprocessing`` uses the ``spawn`` start method, so every worker pays
# this import cost from scratch; keeping it minimal is what makes batch analysis
# fast there.
_LAZY_EXPORTS = {
    # Services
    "AnalysisService": "app.logic.carlquant.analysis_service",
    "SliceAnalysis": "app.logic.carlquant.analysis_service",
    "SpecimenAnalysisResult": "app.logic.carlquant.analysis_service",
    "DataLoader": "app.logic.carlquant.data_service",
    "DataSaver": "app.logic.carlquant.data_service",
    "InterpolationService": "app.logic.carlquant.interpolation_service",
    # Interpolation descriptors
    "CoordinateDescriptor": "app.logic.carlquant.interpolation_service",
    "REGION_DESCRIPTOR": "app.logic.carlquant.interpolation_service",
    "AIR_DESCRIPTOR": "app.logic.carlquant.interpolation_service",
    # Models
    "AirConfig": "app.logic.carlquant.models",
    "DepthDetectionMethod": "app.logic.carlquant.models",
    "LesionDepth": "app.logic.carlquant.models",
    "RegionConfig": "app.logic.carlquant.models",
    "RegionStats": "app.logic.carlquant.models",
    "SliceResult": "app.logic.carlquant.models",
    "Specimen": "app.logic.carlquant.models",
    "SpecimenConfig": "app.logic.carlquant.models",
    "Surface": "app.logic.carlquant.models",
}

if TYPE_CHECKING:  # pragma: no cover - import-time hints for type checkers only
    from app.logic.carlquant.analysis_service import (
        AnalysisService,
        SliceAnalysis,
        SpecimenAnalysisResult,
    )
    from app.logic.carlquant.data_service import DataLoader, DataSaver
    from app.logic.carlquant.interpolation_service import (
        AIR_DESCRIPTOR,
        REGION_DESCRIPTOR,
        CoordinateDescriptor,
        InterpolationService,
    )
    from app.logic.carlquant.models import (
        AirConfig,
        DepthDetectionMethod,
        LesionDepth,
        RegionConfig,
        RegionStats,
        SliceResult,
        Specimen,
        SpecimenConfig,
        Surface,
    )


def __getattr__(name: str):
    """Import and cache a public symbol on first access (PEP 562)."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so later lookups skip __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


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
