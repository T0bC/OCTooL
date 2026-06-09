# -*- coding: utf-8 -*-
"""
CarlQuant Specimen Models.

Domain dataclasses for the CarlQuant analysis pipeline: region statistics,
detected surfaces, lesion depths, region/AIR configurations, and specimen
results.

Key contents:
- RegionStats: Statistics (mean, median, SD, SE) for a sound or lesion region.
- Surface: Detected surface points, fitted curves, and cavitation flag.
- LesionDepth: Lesion depth points, mean/median/SD/SE, and per-column detection data.
- RegionConfig: 4-point region boundary configuration with buffered accessors.
- AirConfig: 2-point AIR reference area configuration.
- SpecimenConfig: Container for per-slice RegionConfig and AirConfig maps.
- SliceResult: Per-slice aggregation of region_stats, surface, and lesion_depth.
- Specimen: Top-level container for a specimen's images, config, and analysis results.

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



from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional

@dataclass
class RegionStats:
    region_type: str  # "sound" or "lesion"
    pixel_values: List[int]
    mean: float
    median: float
    sd: float
    se: float
    region_index: int = 0  # Region number (1, 2, 3, ...)
    bounds: Tuple = (0, 0, 0, 0)  # Either (left_x, top_y, right_x, bottom_y) or 4 corner points
    rotation_angle: float = 0.0  # Rotation angle in degrees

@dataclass
class Surface:
    raw_points: List[Tuple[int, int]]  # (x, y)
    fitted_curves: Dict[str, List[Tuple[int, int]]]  # e.g. {"actual_surface": [...], "interpolated_surface": [...]}
    cluster_labels: Optional[List[int]] = None  # Cluster ID for each point (-1 for noise)
    is_cavitated: bool = False  # True if cavitation detected
    cavitation_depth: float = 0.0  # Mean vertical distance between actual and interpolated surfaces

@dataclass
class LesionDepth:
    depth_points: List[Tuple[int, int]]  # (x, y) coordinates of lesion bottom (raw detection points)
    mean_depth: float
    median_depth: float
    sd: float
    se: float
    lesion_detection_data: Optional[Dict[int, Dict]] = None  # Per-column lesion detection data for visualization
    # lesion_detection_data format: {x_column: {'intensity': [...], 'depth_idx': [...], 'knee_idx': int, 'detection_metadata': {...}}}
    smoothed_depth_points: Optional[List[Tuple[int, int]]] = None  # Spline-smoothed depth points for cleaner visualization
    method_splines: Optional[Dict[str, List[Tuple[int, int]]]] = None  # Pre-computed splines for all methods when compute_all_methods=True
    # method_splines format: {'knee_point': [(x,y), ...], 'sigmoid_fit': [(x,y), ...], 'sigmoid_shoulder': [(x,y), ...]}

@dataclass
class RegionConfig:
    """Configuration for region boundaries (4 points) for a specific slice.
    
    Implements InterpolatableConfig protocol for keyframe-based interpolation.
    """
    slice_index: int
    specimen_start: Tuple[int, int]  # (x, y) - Left boundary of specimen
    lesion_start: Tuple[int, int]    # (x, y) - Left boundary of lesion
    lesion_end: Tuple[int, int]      # (x, y) - Right boundary of lesion
    tooth_end: Tuple[int, int]       # (x, y) - Right boundary of tooth/specimen
    is_keyframe: bool = False        # True if manually set by user, False if interpolated/propagated
    buffer_pixels: int = 10          # Buffer zone in pixels to avoid transition artifacts
    
    def get_buffered_lesion_start_x(self) -> int:
        """Get lesion start x-coordinate with buffer applied (moved right).
        
        Used for interpolated surface fitting and sound region extraction to avoid
        transition zone artifacts between sound and lesion areas.
        """
        return self.lesion_start[0] + self.buffer_pixels
    
    def get_buffered_lesion_end_x(self) -> int:
        """Get lesion end x-coordinate with buffer applied (moved left).
        
        Used for interpolated surface fitting and sound region extraction to avoid
        transition zone artifacts between sound and lesion areas.
        """
        return self.lesion_end[0] - self.buffer_pixels
    
    def get_buffered_sound_left_end_x(self) -> int:
        """Get end of left sound region with buffer applied (moved left from lesion_start).
        
        Sound area 1 spans from specimen_start to this buffered coordinate.
        """
        return self.lesion_start[0] - self.buffer_pixels
    
    def get_buffered_sound_right_start_x(self) -> int:
        """Get start of right sound region with buffer applied (moved right from lesion_end).
        
        Sound area 2 spans from this buffered coordinate to tooth_end.
        """
        return self.lesion_end[0] + self.buffer_pixels

@dataclass
class AirConfig:
    """Configuration for AIR reference area for a specific slice.
    
    AIR (Air Reference) defines a rectangular region containing actual air (empty space)
    used as a reference for normalization and threshold calculations in OCT analysis.
    
    Implements InterpolatableConfig protocol for keyframe-based interpolation.
    """
    slice_index: int
    point1: Tuple[int, int]       # First diagonal point (x, y)
    point2: Optional[Tuple[int, int]] = None  # Second diagonal point (x, y) for rectangular selection
    is_keyframe: bool = False     # True if manually set by user, False if interpolated/propagated

@dataclass
class SpecimenConfig:
    """Configuration data for a specimen including REGIONS and AIR settings."""
    specimen_id: str
    regions: Dict[int, RegionConfig] = field(default_factory=dict)  # slice_index -> RegionConfig
    air: Dict[int, AirConfig] = field(default_factory=dict)         # slice_index -> AirConfig

@dataclass
class SliceResult:
    slice_index: int
    region_stats: List[RegionStats]
    surface: Surface
    lesion_depth: LesionDepth

@dataclass
class Specimen:
    specimen_id: str
    source: Path
    images: List[Path]
    slices: int
    status: str
    date: float
    results: Dict[int, SliceResult] = field(default_factory=dict)
    previous_runs: List[Path] = field(default_factory=list)
    config: Optional[SpecimenConfig] = None  # Configuration for REGIONS and AIR


