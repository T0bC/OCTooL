# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 15:48:56 2025

@author: meissnerto
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple

@dataclass
class RegionStats:
    region_type: str  # "sound" or "lesion"
    pixel_values: List[int]
    mean: float
    median: float
    sd: float
    se: float

@dataclass
class Surface:
    raw_points: List[Tuple[int, int]]  # (x, y)
    fitted_curves: Dict[str, List[Tuple[int, int]]]  # e.g. {"polyfit": [...], "spline": [...]}

@dataclass
class LesionDepth:
    depth_points: List[Tuple[int, int]]
    mean_depth: float
    median_depth: float
    sd: float
    se: float

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

