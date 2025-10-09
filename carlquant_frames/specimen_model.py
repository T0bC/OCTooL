# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 15:48:56 2025

@author: Tobias Meissner
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
    fitted_curves: Dict[str, List[Tuple[int, int]]]  # e.g. {"spline": [...], "reference": [...]}
    cluster_labels: Optional[List[int]] = None  # Cluster ID for each point (-1 for noise)
    is_cavitated: bool = False  # True if cavitation detected
    cavitation_depth: float = 0.0  # Mean vertical distance between primary and reference curves

@dataclass
class LesionDepth:
    depth_points: List[Tuple[int, int]]  # (x, y) coordinates of lesion bottom (raw knee points)
    mean_depth: float
    median_depth: float
    sd: float
    se: float
    knee_data: Optional[Dict[int, Dict]] = None  # Per-column knee point data for visualization
    # knee_data format: {x_column: {'intensity': [...], 'depth_idx': [...], 'knee_idx': int, 'fits': {...}}}
    smoothed_depth_points: Optional[List[Tuple[int, int]]] = None  # Spline-smoothed depth points for cleaner visualization

@dataclass
class RegionConfig:
    """Configuration for region boundaries (4 points) for a specific slice."""
    slice_index: int
    specimen_start: Tuple[int, int]  # (x, y) - Left boundary of specimen
    lesion_start: Tuple[int, int]    # (x, y) - Left boundary of lesion
    lesion_end: Tuple[int, int]      # (x, y) - Right boundary of lesion
    tooth_end: Tuple[int, int]       # (x, y) - Right boundary of tooth/specimen

@dataclass
class AirConfig:
    """Configuration for AIR threshold area for a specific slice."""
    slice_index: int
    point1: Tuple[int, int]       # First diagonal point (x, y)
    point2: Optional[Tuple[int, int]] = None  # Second diagonal point (x, y) for rectangular selection

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
    regions: str
    status: str
    date: float
    results: Dict[int, SliceResult] = field(default_factory=dict)
    previous_runs: List[Path] = field(default_factory=list)
    config: Optional[SpecimenConfig] = None  # Configuration for REGIONS and AIR


