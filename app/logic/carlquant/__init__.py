"""
CarlQuant Logic Package

Pure, tkinter-free business logic for the CarlQuant OCT lesion-quantification
module: surface detection, region extraction, lesion-depth calculation, keyframe
interpolation, and data I/O. Fully importable and unit-testable headlessly.
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
