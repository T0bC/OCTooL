# -*- coding: utf-8 -*-
"""
CarlQuant Core Analysis Engine.

Core compute functions for the CarlQuant OCT analysis pipeline: surface
detection, region extraction, lesion-depth calculation, and parallel slice
processing. process_slice_parallel lives at module level so it is picklable by
ProcessPoolExecutor on Windows.

Key contents:
- process_slice_parallel: Picklable module-level worker that loads an image and runs the full pipeline.
- detect_surface: Finds the specimen surface using intensity peaks and AIR thresholding.
- extract_regions: Extracts sound/lesion regions and computes statistics.
- calculate_lesion_depth: Calculates lesion depth with knee-point, sigmoid, and combined methods.
- find_surface_peak: Locates the first significant intensity peak after threshold crossing.
- cluster_surface_points: Applies DBSCAN to remove speckle noise from raw surface points.
- fit_surface_curve: Fits a smooth spline curve to detected surface points.

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



from time import sleep
from threading import Thread
from app.logic.carlquant.data_io import DataSaver
from app.logic.carlquant.specimen_model import RegionStats, Surface, LesionDepth
import random
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
from enum import Enum
import gc
import traceback


# =============================================================================
# PARALLEL PROCESSING SUPPORT
# =============================================================================
# IMPORTANT: process_slice_parallel MUST be defined at module level (not nested)
# to be picklable by ProcessPoolExecutor. Worker processes on Windows will
# re-import this module, but multiprocessing.freeze_support() in OCTooL.py
# prevents the GUI from being re-launched in worker processes.

def process_slice_parallel(slice_idx, image_path, region_config, air_config, num_sound, num_lesion, detection_method_str='combined_mean'):
    """
    Process a single slice by loading image on-demand in worker process.
    This function must be at module level to be picklable by ProcessPoolExecutor.
    
    Args:
        slice_idx: Index of the slice being processed
        image_path: Path to the image file (loaded on-demand by worker)
        region_config: Region configuration for this slice
        air_config: AIR configuration for this slice
        num_sound: Number of sound regions to extract
        num_lesion: Number of lesion regions to extract
        detection_method_str: Detection method string (default 'combined_mean')
    
    Returns:
        Tuple of (slice_idx, region_stats, surface, lesion_depth, error)
    """
    try:
        # Load image in worker process (on-demand)
        img = Image.open(image_path).convert('L')
        image_array = np.array(img)
        img.close()
        
        # Detect surface
        surface = detect_surface(image_array, air_config, region_config)
        
        # Extract regions
        if region_config:
            region_stats = extract_regions(
                image_array,
                surface,
                region_config,
                num_sound_regions=num_sound,
                num_lesion_regions=num_lesion
            )
        else:
            # No region config - use dummy data
            region_stats = [
                RegionStats("sound", [random.randint(95, 105) for _ in range(100)],
                            mean=100.0, median=100.0, sd=2.0, se=1.0)
                for _ in range(num_sound)
            ] + [
                RegionStats("lesion", [random.randint(75, 85) for _ in range(100)],
                            mean=80.0, median=80.0, sd=2.0, se=1.0)
                for _ in range(num_lesion)
            ]
        
        # Calculate lesion depth
        if region_config:
            detection_method = DepthDetectionMethod(detection_method_str)
            # Extract filename for better debug output
            from pathlib import Path
            slice_name = Path(image_path).stem if image_path else f"slice_{slice_idx}"
            lesion_depth = calculate_lesion_depth(
                surface,
                region_config,
                image_array,
                search_depth=200,
                detection_method=detection_method,
                stability_threshold=20.0,
                slice_id=slice_name
            )
        else:
            lesion_depth = None
        
        return (slice_idx, region_stats, surface, lesion_depth, None)
    except Exception as e:
        import traceback
        return (slice_idx, None, None, None, f"{str(e)}\n{traceback.format_exc()}")


# =============================================================================
# SURFACE DETECTION ALGORITHMS
# =============================================================================

def find_surface_peak(column: np.ndarray, threshold_idx: int, search_window: int = 250, 
                     min_peak_ratio: float = 0.66) -> int:
    """Find the first significant intensity peak (surface) after threshold crossing."""
    search_end = min(threshold_idx + search_window, len(column))
    search_region = column[threshold_idx:search_end]
    
    if len(search_region) == 0:
        return threshold_idx
    
    # Find the maximum peak in the search region
    max_intensity = np.max(search_region)
    max_offset = np.argmax(search_region)
    
    # Find the first local peak
    for i in range(1, len(search_region) - 1):
        if search_region[i] >= search_region[i-1] and search_region[i] > search_region[i+1]:
            first_peak_intensity = search_region[i]
            
            # Check if first peak is significant enough
            if first_peak_intensity >= min_peak_ratio * max_intensity:
                return threshold_idx + i
            else:
                return threshold_idx + max_offset
    
    return threshold_idx + max_offset


def calculate_air_threshold(image: np.ndarray, air_config) -> float:
    """Calculate intensity threshold based on AIR region."""
    if not air_config or not air_config.point2:
        return np.percentile(image, 50)
    
    x1, y1 = air_config.point1
    x2, y2 = air_config.point2
    
    height, width = image.shape
    x1, x2 = max(0, min(x1, x2)), min(width, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(height, max(y1, y2))
    
    air_region = image[y1:y2, x1:x2]
    air_q95 = np.percentile(air_region, 95)
    threshold = air_q95 * 1.6
    
    return threshold


def cluster_surface_points(raw_points: List[Tuple[int, int]], 
                          epsilon: float = 17, 
                          min_samples: int = 10,
                          min_cluster_size: int = 180) -> Tuple[List[Tuple[int, int]], Optional[List[int]]]:
    """Apply DBSCAN clustering to surface points to remove speckles."""
    from sklearn.cluster import DBSCAN
    if len(raw_points) == 0:
        return raw_points, None
    
    points_array = np.array(raw_points)
    dbscan = DBSCAN(eps=epsilon, min_samples=min_samples)
    cluster_labels = dbscan.fit_predict(points_array)
    
    valid_labels = cluster_labels[cluster_labels >= 0]
    if len(valid_labels) == 0:
        return raw_points, None
    
    unique_labels, counts = np.unique(valid_labels, return_counts=True)
    surface_cluster_ids = unique_labels[counts > min_cluster_size]
    
    if len(surface_cluster_ids) == 0:
        largest_cluster_id = unique_labels[np.argmax(counts)]
        surface_cluster_ids = np.array([largest_cluster_id])
    
    mask = np.isin(cluster_labels, surface_cluster_ids)
    filtered_points = [raw_points[i] for i in range(len(raw_points)) if mask[i]]
    filtered_labels = cluster_labels[mask]
    
    return filtered_points, filtered_labels.tolist()


def fit_surface_curve(surface_points: List[Tuple[int, int]], 
                     x_start: int, 
                     x_end: int,
                     smoothing: float = 0.5,
                     smoothing_multiplier: float = 3.0,
                     spline_degree: int = 5,
                     curve_name: str = "actual_surface") -> Dict[str, List[Tuple[int, int]]]:
    """Fit a smooth spline curve to surface points."""
    from scipy.interpolate import splrep, splev
    if len(surface_points) < 4:
        return {}
    
    points_array = np.array(surface_points)
    x_coords = points_array[:, 0]
    y_coords = points_array[:, 1]
    
    sort_idx = np.argsort(x_coords)
    x_sorted = x_coords[sort_idx]
    y_sorted = y_coords[sort_idx]
    
    try:
        s_param = smoothing * smoothing_multiplier * len(x_sorted)
        tck = splrep(x_sorted, y_sorted, k=spline_degree, s=s_param)
        x_full = np.arange(x_start, x_end)
        y_fitted = splev(x_full, tck)
        fitted_curve = [(int(x), int(y)) for x, y in zip(x_full, y_fitted)]
        return {curve_name: fitted_curve}
    except Exception as e:
        return {}


def fit_lesion_depth_curve_robust(depth_points: List[Tuple[int, int]], 
                                   x_start: int, 
                                   x_end: int,
                                   smoothing: float = 5.0,
                                   smoothing_multiplier: float = 5.0,
                                   spline_degree: int = 2,
                                   median_kernel_size: int = 5,
                                   outlier_threshold: float = 2.0,
                                   curve_name: str = "smoothed_depth") -> Dict[str, List[Tuple[int, int]]]:
    """
    Fit a smooth spline curve to lesion depth points with robust spike removal.
    
    This function handles noisy depth data with spikes (e.g., from dark speckles in OCT images)
    by applying a two-stage approach:
    1. Median filtering to remove isolated spikes (3-4 pixel wide speckles)
    2. Outlier detection and removal before spline fitting
    3. Spline smoothing on cleaned data
    
    Args:
        depth_points: List of (x, y) tuples representing detected lesion depth points
        x_start: Start x-coordinate for the fitted curve
        x_end: End x-coordinate for the fitted curve
        smoothing: Base smoothing factor for spline (default 5.0)
        smoothing_multiplier: Multiplier for smoothing parameter (default 5.0)
        spline_degree: Degree of spline (default 2 for quadratic)
        median_kernel_size: Size of median filter kernel (default 5, must be odd)
                           Larger values remove wider spikes but may over-smooth
        outlier_threshold: Number of standard deviations for outlier detection (default 2.0)
                          Points beyond this threshold are excluded from spline fitting
        curve_name: Name for the returned curve dictionary
    
    Returns:
        Dictionary with curve_name as key and list of (x, y) tuples as fitted curve
    """
    from scipy.interpolate import splrep, splev
    from scipy.signal import medfilt
    if len(depth_points) < 4:
        return {}
    
    points_array = np.array(depth_points)
    x_coords = points_array[:, 0]
    y_coords = points_array[:, 1]
    
    # Sort by x-coordinate
    sort_idx = np.argsort(x_coords)
    x_sorted = x_coords[sort_idx]
    y_sorted = y_coords[sort_idx]
    
    # Step 1: Apply median filter to remove isolated spikes
    # This is effective for 3-4 pixel wide speckles
    if len(y_sorted) >= median_kernel_size:
        # Ensure kernel size is odd
        kernel_size = median_kernel_size if median_kernel_size % 2 == 1 else median_kernel_size + 1
        y_median_filtered = medfilt(y_sorted, kernel_size=kernel_size)
    else:
        y_median_filtered = y_sorted.copy()
    
    # Step 2: Detect and remove outliers based on deviation from median-filtered trend
    # Calculate residuals (difference between original and median-filtered)
    residuals = y_sorted - y_median_filtered
    residual_std = np.std(residuals)
    residual_mean = np.mean(residuals)
    
    # Identify inliers (points within threshold standard deviations)
    inlier_mask = np.abs(residuals - residual_mean) <= (outlier_threshold * residual_std)
    
    # Require at least 4 points for spline fitting
    if np.sum(inlier_mask) < 4:
        # If too many outliers detected, fall back to median-filtered data
        x_clean = x_sorted
        y_clean = y_median_filtered
    else:
        # Use only inliers for spline fitting
        x_clean = x_sorted[inlier_mask]
        y_clean = y_median_filtered[inlier_mask]
    
    # Step 3: Fit spline to cleaned data
    try:
        s_param = smoothing * smoothing_multiplier * len(x_clean)
        tck = splrep(x_clean, y_clean, k=min(spline_degree, len(x_clean) - 1), s=s_param)
        x_full = np.arange(x_start, x_end)
        y_fitted = splev(x_full, tck)
        fitted_curve = [(int(x), int(y)) for x, y in zip(x_full, y_fitted)]
        return {curve_name: fitted_curve}
    except Exception as e:
        return {}


def fit_reference_surface(surface_points: List[Tuple[int, int]],
                          region_config,
                          x_start: int,
                          x_end: int,
                          smoothing: float = 2.0,
                          smoothing_multiplier: float = 5.0,
                          spline_degree: int = 3) -> Dict[str, List[Tuple[int, int]]]:
    """Fit reference surface curve excluding lesion area for cavitation detection.
    
    Uses buffered lesion boundaries to avoid fitting artifacts in transition zones
    between sound and lesion areas. The buffer excludes ~10 pixels on each side of
    the lesion boundaries from the interpolated surface fit.
    """
    if not region_config or len(surface_points) < 4:
        return {}
    
    # Use buffered coordinates to exclude transition zones from interpolated surface fit
    lesion_start_x = region_config.get_buffered_lesion_start_x()
    lesion_end_x = region_config.get_buffered_lesion_end_x()
    
    sound_points = [(x, y) for x, y in surface_points 
                    if x < lesion_start_x or x > lesion_end_x]
    
    if len(sound_points) < 4:
        return {}
    
    return fit_surface_curve(
        sound_points, 
        x_start, 
        x_end, 
        smoothing=smoothing,
        smoothing_multiplier=smoothing_multiplier,
        spline_degree=spline_degree,
        curve_name="interpolated_surface"
    )


def detect_cavitation(primary_curve: List[Tuple[int, int]],
                     reference_curve: List[Tuple[int, int]],
                     region_config,
                     cavitation_threshold: float = 10.0,
                     min_cavitation_ratio: float = 0.3) -> Tuple[bool, float]:
    """Detect surface cavitation by comparing primary and reference curves.
    
    Uses buffered lesion boundaries to match the transition zone logic used in
    sound region extraction and lesion depth detection.
    """
    if not primary_curve or not reference_curve or not region_config:
        return False, 0.0
    
    # Use buffered coordinates for consistency with other analysis functions
    lesion_start_x = region_config.get_buffered_lesion_start_x()
    lesion_end_x = region_config.get_buffered_lesion_end_x()
    
    primary_dict = {x: y for x, y in primary_curve}
    reference_dict = {x: y for x, y in reference_curve}
    
    cavitation_depths = []
    total_points = 0
    
    for x in range(lesion_start_x, lesion_end_x + 1):
        if x in primary_dict and x in reference_dict:
            total_points += 1
            distance = primary_dict[x] - reference_dict[x]
            
            if distance > 0:
                cavitation_depths.append(distance)
    
    if not cavitation_depths or total_points == 0:
        return False, 0.0
    
    mean_cavitation_depth = np.mean(cavitation_depths)
    cavitation_ratio = len(cavitation_depths) / total_points
    
    is_cavitated = (mean_cavitation_depth > cavitation_threshold and 
                   cavitation_ratio >= min_cavitation_ratio)
    
    return is_cavitated, mean_cavitation_depth


# =============================================================================
# REGION EXTRACTION
# =============================================================================

def extract_regions(image: np.ndarray, 
                   surface: Surface, 
                   region_config,
                   num_sound_regions: int = 6,
                   num_lesion_regions: int = 6,
                   region_size: int = 25,
                   surface_offset: int = 10) -> List[RegionStats]:
    """
    Extract pixel values from sound and lesion regions.
    
    Algorithm:
    1. Divide sound areas (left and right of lesion) into num_sound_regions TOTAL (split between left/right)
    2. Divide lesion area into num_lesion_regions
    3. For each region, place 25x25 pixel rectangle 10px below surface
    4. Extract pixel values and calculate statistics
    
    Buffer Zone System:
    - Sound regions use BUFFERED boundaries (±10px from lesion boundaries) to avoid
      extracting from transition zones between sound and lesion areas
    - Lesion regions use ORIGINAL user-defined boundaries for accurate lesion measurement
    - This prevents contamination of sound region statistics with transition artifacts
    
    Args:
        image: 2D numpy array (grayscale image)
        surface: Detected surface with fitted curve
        region_config: Region boundaries (4 points)
        num_sound_regions: TOTAL number of sound regions (split between left and right sides)
        num_lesion_regions: Number of lesion regions
        region_size: Size of extraction rectangle (default 25x25)
        surface_offset: Distance below surface to start extraction (default 10px)
    
    Returns:
        List of RegionStats with region coordinates
    """
    height, width = image.shape
    
    # Extract boundary x-coordinates from 4-point configuration
    specimen_start_x, _ = region_config.specimen_start
    tooth_end_x, _ = region_config.tooth_end
    
    # Use ORIGINAL coordinates for lesion regions (user-defined boundaries)
    lesion_start_x, _ = region_config.lesion_start
    lesion_end_x, _ = region_config.lesion_end
    
    # Use BUFFERED coordinates for sound regions to avoid transition zones
    sound_left_end_x = region_config.get_buffered_sound_left_end_x()
    sound_right_start_x = region_config.get_buffered_sound_right_start_x()
    
    # Define overall boundaries for surface lookup
    x_start = specimen_start_x
    x_end = tooth_end_x
    
    # Use primary surface fit for positioning
    if not surface.fitted_curves or "actual_surface" not in surface.fitted_curves:
        return []
    
    # Convert surface to dictionary for easy lookup
    surface_dict = {x: y for x, y in surface.fitted_curves["actual_surface"]}
    
    region_stats = []
    
    # Helper function to extract region with rotation
    def extract_region_at(center_x: int, region_type: str, region_index: int) -> Optional[RegionStats]:
        """Extract a single region at given x position, rotated to match surface slope."""
        # Get surface y-coordinate at this x
        if center_x not in surface_dict:
            return None
        
        surface_y = surface_dict[center_x]
        
        # Calculate surface slope at this position (using neighboring points)
        slope_window = 10  # Look at ±10 pixels for slope calculation
        x_left = max(x_start, center_x - slope_window)
        x_right = min(x_end - 1, center_x + slope_window)
        
        # Get y values at left and right positions
        y_left = surface_dict.get(x_left, surface_y)
        y_right = surface_dict.get(x_right, surface_y)
        
        # Calculate slope (dy/dx)
        if x_right != x_left:
            slope = (y_right - y_left) / (x_right - x_left)
            angle_rad = np.arctan(slope)
        else:
            angle_rad = 0.0
        
        # Calculate rotated rectangle corners
        # Start with center point offset below surface
        center_y = surface_y + surface_offset + region_size // 2
        
        # Create rotation matrix
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # Define rectangle corners relative to center (before rotation)
        half_size = region_size // 2
        corners = [
            (-half_size, -half_size),  # Top-left
            (half_size, -half_size),   # Top-right
            (half_size, half_size),    # Bottom-right
            (-half_size, half_size)    # Bottom-left
        ]
        
        # Rotate corners and translate to center position
        rotated_corners = []
        for dx, dy in corners:
            rx = dx * cos_a - dy * sin_a + center_x
            ry = dx * sin_a + dy * cos_a + center_y
            rotated_corners.append((int(rx), int(ry)))
        
        # Extract pixels using rotated sampling
        pixel_values = []
        for dy in range(-half_size, half_size):
            for dx in range(-half_size, half_size):
                # Rotate point
                rx = dx * cos_a - dy * sin_a + center_x
                ry = dx * sin_a + dy * cos_a + center_y
                
                # Sample pixel (with bounds checking)
                ix, iy = int(round(rx)), int(round(ry))
                if 0 <= ix < width and 0 <= iy < height:
                    pixel_values.append(int(image[iy, ix]))
        
        if len(pixel_values) == 0:
            return None
        
        # Calculate statistics
        mean_val = float(np.mean(pixel_values))
        median_val = float(np.median(pixel_values))
        sd_val = float(np.std(pixel_values))
        se_val = sd_val / np.sqrt(len(pixel_values))
        
        # Store rotated corners for visualization
        return RegionStats(
            region_type=region_type,
            pixel_values=pixel_values,
            mean=mean_val,
            median=median_val,
            sd=sd_val,
            se=se_val,
            region_index=region_index,
            bounds=tuple(rotated_corners),  # Store 4 corner points instead of bbox
            rotation_angle=float(np.degrees(angle_rad))  # Store rotation in degrees
        )
    
    # Split sound regions between left and right sides
    num_sound_per_side = num_sound_regions // 2
    
    # Calculate positions for sound regions (left side: specimen_start to buffered lesion_start)
    # Uses buffered boundary to avoid transition zone between sound and lesion
    sound_left_width = sound_left_end_x - specimen_start_x
    sound_left_spacing = sound_left_width / (num_sound_per_side + 1)
    
    for i in range(num_sound_per_side):
        center_x = int(specimen_start_x + sound_left_spacing * (i + 1))
        stats = extract_region_at(center_x, "sound", i + 1)
        if stats:
            region_stats.append(stats)
    
    # Calculate positions for lesion regions
    lesion_width = lesion_end_x - lesion_start_x
    lesion_spacing = lesion_width / (num_lesion_regions + 1)
    
    for i in range(num_lesion_regions):
        center_x = int(lesion_start_x + lesion_spacing * (i + 1))
        stats = extract_region_at(center_x, "lesion", i + 1)
        if stats:
            region_stats.append(stats)
    
    # Calculate positions for sound regions (right side: buffered lesion_end to tooth_end)
    # Uses buffered boundary to avoid transition zone between lesion and sound
    sound_right_width = tooth_end_x - sound_right_start_x
    sound_right_spacing = sound_right_width / (num_sound_per_side + 1)
    
    for i in range(num_sound_per_side):
        center_x = int(sound_right_start_x + sound_right_spacing * (i + 1))
        stats = extract_region_at(center_x, "sound", num_sound_per_side + i + 1)
        if stats:
            region_stats.append(stats)
    
    return region_stats


def detect_surface(image: np.ndarray, air_config=None, region_config=None) -> Surface:
    """
    Detect the surface of the specimen in the OCT image.
    
    Algorithm:
    1. Calculate threshold from AIR region
    2. For each A-Scan column, find first pixel > threshold
    3. Find intensity peak within 250 pixels after threshold
    4. Apply DBSCAN clustering to remove speckles
    5. Fit smooth spline curve to surface points

    Returns:
        Surface: Object containing detected surface information
            reference_surface: Object containing detected reference surface information
                               which is using pixels only in the sound area
            spline: Object containing detected spline surface information
                    which is using all pixels above the threshold
    """
    height, width = image.shape
    
    # Step 1: Calculate threshold
    threshold = calculate_air_threshold(image, air_config)
    
    # Step 2: Determine search boundaries
    if region_config:
        x_start = region_config.specimen_start[0]
        x_end = region_config.tooth_end[0]
    else:
        x_start = 0
        x_end = width
    
    # Step 3: Find surface peaks
    imageOffset = 25 # the image contains usually black or white border
    raw_points = []
    for x in range(x_start, x_end):
        column = image[imageOffset:, x]
        above_threshold = np.where(column > threshold)[0]
        
        if len(above_threshold) > 0:
            threshold_idx = above_threshold[0]
            peak_idx = find_surface_peak(column, threshold_idx, search_window=250)
            y = peak_idx + imageOffset
            raw_points.append((x, y))
    
    # Step 4: Apply DBSCAN clustering
    filtered_points, cluster_labels = cluster_surface_points(
        raw_points,
        epsilon=17,
        min_samples=10,
        min_cluster_size=180
    )
    
    # Step 5: Fit spline curve
    fitted_curves = {}
    is_cavitated = False
    cavitation_depth = 0.0
    
    if len(filtered_points) > 3:
        # Primary fit: uses all detected surface points
        fitted_curves = fit_surface_curve(filtered_points, x_start, x_end, curve_name="actual_surface")
        
        # Reference fit: excludes lesion area (for cavitation detection)
        if region_config:
            reference_curves = fit_reference_surface(filtered_points, region_config, x_start, x_end)
            fitted_curves.update(reference_curves)
            
            # Detect cavitation by comparing actual and interpolated surfaces
            if "actual_surface" in fitted_curves and "interpolated_surface" in fitted_curves:
                is_cavitated, cavitation_depth = detect_cavitation(
                    fitted_curves["actual_surface"],
                    fitted_curves["interpolated_surface"],
                    region_config,
                    cavitation_threshold=5.0,
                    min_cavitation_ratio=0.7
                )
    
    return Surface(
        raw_points=filtered_points,
        fitted_curves=fitted_curves,
        cluster_labels=cluster_labels,
        is_cavitated=is_cavitated,
        cavitation_depth=cavitation_depth
    )


# =============================================================================
# LESION DEPTH CALCULATION
# =============================================================================

class DepthDetectionMethod(Enum):
    """Available methods for detecting lesion depth from A-Scan profiles."""
    KNEE_POINT = "knee_point"  # Two-line fitting (best for exponential decay)
    SIGMOID_FIT = "sigmoid_fit"  # Sigmoid inflection point (50% transition)
    SIGMOID_SHOULDER = "sigmoid_shoulder"  # Sigmoid shoulder (15% from upper asymptote)
    COMBINED_MEAN = "combined_mean"  # Mean of knee_point and sigmoid_fit
    
    @classmethod
    def get_default(cls):
        return cls.COMBINED_MEAN  # Use combined method as default

def knee_pt(y, x):
    """
    Find knee point in a curve using two-line fitting method.
    Translated from MATLAB knee_pt function by D. Kroon.
    
    Args:
        y: Y-values (e.g., intensity profile)
        x: X-values (e.g., depth indices)
    
    Returns:
        Tuple of (knee_x_value, knee_index)
    """
    # Convert to numpy arrays
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    
    n = len(x)
    if n < 3:
        return np.nan, -1
    
    # Normalize x and y to [0, 1]
    x_norm = (x - np.min(x)) / (np.max(x) - np.min(x) + 1e-10)
    y_norm = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-10)
    
    # Calculate error for each potential knee point
    error_curve = np.full(n, np.nan)
    idx_map = {}
    
    for idx in range(1, n - 1):
        # Left segment: fit line from start to current point
        x_left = x_norm[:idx + 1]
        y_left = y_norm[:idx + 1]
        
        if len(x_left) > 1:
            # Fit line: y = a*x + b
            A_left = np.vstack([x_left, np.ones(len(x_left))]).T
            try:
                coeffs_left = np.linalg.lstsq(A_left, y_left, rcond=None)[0]
                y_fit_left = A_left @ coeffs_left
                delsfwd = y_left - y_fit_left
            except:
                delsfwd = np.zeros(len(x_left))
        else:
            delsfwd = np.zeros(len(x_left))
        
        # Right segment: fit line from current point to end
        x_right = x_norm[idx:]
        y_right = y_norm[idx:]
        
        if len(x_right) > 1:
            A_right = np.vstack([x_right, np.ones(len(x_right))]).T
            try:
                coeffs_right = np.linalg.lstsq(A_right, y_right, rcond=None)[0]
                y_fit_right = A_right @ coeffs_right
                delsbck = y_right - y_fit_right
            except:
                delsbck = np.zeros(len(x_right))
        else:
            delsbck = np.zeros(len(x_right))
        
        # Total error is sum of absolute errors
        idx_map[idx] = idx
        error_curve[idx] = np.sum(np.abs(delsfwd)) + np.sum(np.abs(delsbck))
    
    # Find minimum error location
    valid_errors = error_curve[~np.isnan(error_curve)]
    if len(valid_errors) == 0:
        return np.nan, -1
    
    loc = np.nanargmin(error_curve)
    res_x = x[loc]
    idx_of_result = loc
    
    return res_x, idx_of_result


def exp2_model(z, a, b, c, d):
    """
    Double exponential decay model for OCT intensity.
    I(z) = a*exp(b*z) + c*exp(d*z)
    """
    return a * np.exp(b * z) + c * np.exp(d * z)


def fit_exp2_to_profile(intensity_profile: np.ndarray, depth_indices: np.ndarray) -> Optional[Tuple[np.ndarray, Dict]]:
    """
    Fit double exponential model to intensity profile.
    
    Returns:
        Tuple of (fitted_curve, params_dict) or None if fitting fails
    """
    from scipy.optimize import curve_fit
    try:
        # Initial guess for parameters
        max_intensity = np.max(intensity_profile)
        p0 = [max_intensity * 0.7, -0.05, max_intensity * 0.3, -0.01]
        
        # Fit the model
        popt, pcov = curve_fit(
            exp2_model, 
            depth_indices, 
            intensity_profile,
            p0=p0,
            maxfev=5000,
            bounds=(
                [0, -1, 0, -1],  # Lower bounds
                [255, 0, 255, 0]  # Upper bounds
            )
        )
        
        # Generate fitted curve
        fitted_curve = exp2_model(depth_indices, *popt)
        
        params = {
            'a': popt[0],
            'b': popt[1],
            'c': popt[2],
            'd': popt[3],
            'success': True
        }
        
        return fitted_curve, params
        
    except Exception:
        return None


# =============================================================================
# ADVANCED LESION DEPTH DETECTION METHODS
# =============================================================================


def sigmoid_model(z, L, U, k, z0):
    """
    Sigmoid model for intensity decay.
    I(z) = L + (U - L) / (1 + exp(k * (z - z0)))
    
    Args:
        z: Depth values
        L: Lower asymptote (background intensity)
        U: Upper asymptote (surface intensity)
        k: Steepness parameter (positive = decay)
        z0: Inflection point (lesion depth)
    """
    return L + (U - L) / (1 + np.exp(k * (z - z0)))


# === Half-span crossing =====================================================
# Deterministic, fit-free depth term. Unlike the sigmoid it cannot fail to
# converge (that fit collapses to z0=0 on some specimens).
#
# Constants calibrated against 328 operator marks over 20 specimens and
# validated against 465 marks on a held-out specimen.

HALF_SPAN_BASE_FRACTION = 0.50      # tunable: >0.50 reads shallower, <0.50 deeper
HALF_SPAN_REFERENCE_SPAN = 110.0    # contrast at which the base fraction applies
HALF_SPAN_CONTRAST_SLOPE = 0.10     # fraction drop per 100 grey values of extra span
HALF_SPAN_FRACTION_LIMITS = (0.15, 0.90)
HALF_SPAN_SMOOTH_WINDOW = 9         # boxcar width, and the sustain length
HALF_SPAN_BACKGROUND_TAIL = 50      # depth window whose median is the background
HALF_SPAN_PEAK_WINDOW = 20          # depth window in which the surface peak is taken

#: Constant px offset added to the combined depth. Tunable; 0.0 is validated.
DEPTH_OFFSET = 0.0


def boxcar(profile: np.ndarray, window: int) -> np.ndarray:
    """Centred boxcar smoothing, preserving length.

    Public because the A-Scan viewer redraws the smoothed profile to explain
    the half-span crossing, and it has to be the same smoothing the detection
    ran on.
    """
    if window <= 1 or profile.size < window:
        return profile.astype(float)
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(profile.astype(float), kernel, mode="same")


def half_span_fraction(span: float) -> float:
    """Threshold fraction for a given contrast span.

    High-contrast lesions cross a fixed threshold too early and read shallow,
    so the fraction is lowered as span rises.
    """
    fraction = (HALF_SPAN_BASE_FRACTION
                - HALF_SPAN_CONTRAST_SLOPE
                * (span - HALF_SPAN_REFERENCE_SPAN) / 100.0)
    return float(np.clip(fraction, *HALF_SPAN_FRACTION_LIMITS))


def detect_depth_half_span(intensity_profile: np.ndarray,
                           fraction: Optional[float] = None) -> Tuple[float, Dict]:
    """Depth where the smoothed profile crosses background + fraction*span.

    The crossing must hold for HALF_SPAN_SMOOTH_WINDOW samples, so a single
    speckle dip cannot trigger it.

    Returns:
        (depth_value, metadata_dict)
    """
    profile = np.asarray(intensity_profile, dtype=float)
    if profile.size == 0:
        return np.nan, {'success': False, 'reason': 'empty_profile'}

    smoothed = boxcar(profile, HALF_SPAN_SMOOTH_WINDOW)
    background = float(np.median(smoothed[-HALF_SPAN_BACKGROUND_TAIL:]))
    peak = float(smoothed[:HALF_SPAN_PEAK_WINDOW].max())
    span = peak - background

    metadata = {'success': False, 'method': 'half_span',
                'background': background, 'peak': peak, 'span': span}

    if span <= 1:
        metadata['reason'] = 'no_contrast'
        return np.nan, metadata

    if fraction is None:
        fraction = half_span_fraction(span)
    threshold = background + fraction * span
    metadata.update({'fraction': fraction, 'threshold': threshold})

    below = np.flatnonzero(smoothed < threshold)
    if below.size == 0:
        metadata['reason'] = 'never_crosses'
        return np.nan, metadata

    for index in below:
        if np.all(smoothed[index:index + HALF_SPAN_SMOOTH_WINDOW] < threshold):
            metadata['success'] = True
            return float(index), metadata

    # Crossed but never sustained; the first crossing is the best estimate.
    metadata['success'] = True
    metadata['sustained'] = False
    return float(below[0]), metadata


def detect_depth_sigmoid_fit(intensity_profile: np.ndarray, depth_indices: np.ndarray) -> Tuple[float, int, Dict]:
    """
    Detect lesion depth by fitting sigmoid and finding inflection point.
    Best for smooth S-shaped transitions.
    
    Args:
        intensity_profile: Intensity values along depth
        depth_indices: Corresponding depth indices
    
    Returns:
        Tuple of (depth_value, depth_index, metadata_dict)
    """
    from scipy.optimize import curve_fit
    if len(intensity_profile) < 5:
        return np.nan, -1, {'success': False, 'reason': 'insufficient_data'}
    
    try:
        # Initial parameter guesses
        U_init = np.max(intensity_profile[:len(intensity_profile)//3])  # Surface intensity
        L_init = np.min(intensity_profile[len(intensity_profile)//2:])  # Background intensity
        z0_init = depth_indices[len(depth_indices) // 2]  # Middle point
        k_init = 0.1  # Moderate steepness
        
        # Fit sigmoid model
        popt, pcov = curve_fit(
            sigmoid_model,
            depth_indices,
            intensity_profile,
            p0=[L_init, U_init, k_init, z0_init],
            maxfev=5000,
            bounds=(
                [0, 0, 0.001, depth_indices[0]],  # Lower bounds
                [255, 255, 2.0, depth_indices[-1]]  # Upper bounds
            )
        )
        
        L, U, k, z0 = popt
        
        # Calculate key points on sigmoid curve:
        # 1. Inflection point (z0): maximum rate of change (50% transition)
        # 2. Lower shoulder: where the decay has nearly reached the noise floor

        # Inflection point
        depth_value = z0
        depth_idx = np.argmin(np.abs(depth_indices - z0))

        # Lower shoulder.
        #
        # NOTE: shoulder_intensity below is a solve parameter, NOT the intensity
        # at the returned depth. Substituting it into the inverse sigmoid gives
        # the closed form z0 + ln(1/0.15 - 1)/k = z0 + 1.7346/k, which lands
        # where the curve has fallen to 15% ABOVE the noise floor L. So the
        # shoulder is always DEEPER than the inflection, not closer to the
        # surface. (Verify before "simplifying" this expression: replacing it
        # with L + 0.15*(U - L) is not equivalent and moves the result ~34 px.)
        #
        # The 1/k factor is why this measure is unreliable -- a shallow fit
        # (small k) sends it far past the lesion. Measured worst of all terms
        # (29.8 px mean, 94.4 px worst), which is why the combination rule does
        # not use it. Still emitted: renderers and stored configs read it.
        intensity_range = U - L
        shoulder_intensity = U - 0.15 * intensity_range

        try:
            shoulder_depth = z0 - (1/k) * np.log((U - L)/(shoulder_intensity - L) - 1)
            shoulder_idx = np.argmin(np.abs(depth_indices - shoulder_depth))
            shoulder_depth = float(shoulder_depth)
        except (ValueError, ZeroDivisionError):
            shoulder_depth = np.nan
            shoulder_idx = -1
        
        # Generate fitted curve
        fitted_curve = sigmoid_model(depth_indices, *popt)
        
        metadata = {
            'success': True,
            'method': 'sigmoid_fit',
            'L': L,
            'U': U,
            'k': k,
            'z0': z0,
            'inflection_depth': float(z0),
            'inflection_idx': depth_idx,
            'shoulder_depth': shoulder_depth,
            'shoulder_idx': shoulder_idx,
            'shoulder_intensity': float(shoulder_intensity),
            'fitted_curve': fitted_curve.tolist()
        }
        
        return depth_value, depth_idx, metadata
        
    except Exception as e:
        return np.nan, -1, {'success': False, 'reason': str(e)}


def compute_method_stability(method_raw_points: dict, 
                            lesion_detection_data: dict,
                            stability_threshold: float = 20.0) -> dict:
    """
    Compute stability metrics for each detection method.
    
    Uses ABSOLUTE standard deviation to measure consistency of depth detection
    across A-scans. Lower SD indicates more stable (less wobbly) detection.
    
    This is better than CV (std/mean) because:
    - CV unfairly penalizes shallow detections (small mean → high CV)
    - Absolute SD directly measures wobbliness regardless of depth
    - A straight line at any depth will have low SD
    
    Args:
        method_raw_points: Dict mapping method names to list of (x, y) points
        lesion_detection_data: Dict containing per-column detection metadata
        stability_threshold: SD threshold (in pixels) above which a method is unstable
                           Recommended: 10-20 pixels for typical OCT images
        
    Returns:
        Dict with stability info:
        {
            'method_name': {
                'cv': float,  # Kept for backward compatibility (now actually SD)
                'is_stable': bool,  # True if SD <= threshold
                'n_points': int,  # Number of valid detections
                'mean_depth': float,
                'std_depth': float
            }
        }
    """
    stability_info = {}
    
    for method_name, raw_points in method_raw_points.items():
        if len(raw_points) < 3:  # Need at least 3 points for meaningful statistics
            stability_info[method_name] = {
                'cv': np.inf,
                'is_stable': False,
                'n_points': len(raw_points),
                'mean_depth': np.nan,
                'std_depth': np.nan
            }
            continue
        
        # Extract depth values (relative to surface) for this method
        depth_values = []
        for x, abs_y in raw_points:
            if x in lesion_detection_data:
                surface_y = lesion_detection_data[x]['surface_y']
                relative_depth = abs_y - surface_y
                depth_values.append(relative_depth)
        
        if len(depth_values) < 3:
            stability_info[method_name] = {
                'cv': np.inf,
                'is_stable': False,
                'n_points': len(depth_values),
                'mean_depth': np.nan,
                'std_depth': np.nan
            }
            continue
        
        # Compute statistics
        mean_depth = np.mean(depth_values)
        std_depth = np.std(depth_values)
        
        # Use ABSOLUTE standard deviation as stability metric
        # (not CV, because CV unfairly penalizes shallow detections)
        stability_metric = std_depth
        
        stability_info[method_name] = {
            'cv': stability_metric,  # Field name kept for compatibility, but now contains SD
            'is_stable': stability_metric <= stability_threshold,
            'n_points': len(depth_values),
            'mean_depth': mean_depth,
            'std_depth': std_depth
        }
    
    return stability_info


#: Lateral SD (px) of the combined depth above which a slice is judged to carry
#: no usable lesion signal. Measured over 45 slices / 793 operator marks: lesion
#: slices reach 14.0, the one no-lesion slice 22.6. Any value in 15-18 gives
#: zero false positives on that data, which has n=1 no-lesion slices.
NO_LESION_SD = 15.0

#: Depth reported when the no-lesion gate fires: the detected surface line.
#: Depth is measured from the interpolated surface, so on a cavitated slice with
#: no lesion beneath this is the cavitation depth. Every slice reports a number.
NO_LESION_DEPTH = 0.0

#: ``depth_method_used`` value marking a slice with no usable lesion signal,
#: whether from the lateral-scatter gate or from every method being unstable.
NO_LESION_METHOD = "no_lesion_surface"


#: Lateral SD (px) below which a method's per-column trace is considered a
#: usable lesion boundary. A real boundary is laterally smooth; scatter above
#: this means the term is tracking speckle, not tissue.
#:
#: Measured over 20 slices: half-span clears this on 18, and the two slices it
#: fails are the ones where it should fail (one no-lesion, one near-sound).
METHOD_STABILITY_SD = 12.0

#: Order the cascade falls through once half-span is rejected.
_FALLBACK_METHODS = ("knee_point", "sigmoid_fit")

#: detection_metadata key holding each method's raw per-column depth.
_METHOD_METADATA_KEY = {
    "half_span": "half_span_depth",
    "knee_point": "knee_depth",
    "sigmoid_fit": "inflection_depth",
}


def method_depth_series(lesion_detection_data: dict, method: str) -> dict:
    """Per-column raw depth for one method, keyed by column x.

    Reads ``detection_metadata``, never the top-level column keys, so it is
    unaffected by the combined result being written back onto the column.
    """
    key = _METHOD_METADATA_KEY[method]
    series = {}
    for ascan_x, column in lesion_detection_data.items():
        value = (column.get('detection_metadata') or {}).get(key, np.nan)
        if value is not None and np.isfinite(value):
            series[ascan_x] = float(value)
    return series


def is_method_stable(depth_series: dict,
                     stability_sd: float = METHOD_STABILITY_SD) -> bool:
    """True when a method's depths hold together laterally across the slice.

    Needs at least 3 columns; fewer is not a trace, and its SD is meaningless.
    """
    values = np.asarray(list(depth_series.values()), dtype=float)
    if values.size < 3:
        return False
    return bool(np.std(values) <= stability_sd)


def select_depth_method(lesion_detection_data: dict,
                        stability_sd: float = METHOD_STABILITY_SD) -> tuple:
    """Pick which method supplies this slice's lesion depth.

    Half-span is the primary measure: it is fit-free, cannot fail to converge,
    and tracks the visible lesion boundary most closely. It is used alone
    whenever it is stable, rather than being averaged with the other terms --
    a median over all three was measured to be *wobblier* than half-span by
    itself (SD 12.83 vs 7.48 on one cavitated slice), because the terms are
    near-ordered rather than independent, so an unstable term keeps dragging
    the median off the good one.

    The fallbacks exist because the two remaining terms are biased in opposite,
    known directions: the knee reads deep (deeper than half-span in 81.5% of
    8713 columns) and the sigmoid inflection reads shallow (shallower in 97.7%,
    median ratio 0.455, since it marks the 50% intensity transition rather than
    the lesion end). Averaging them cancels the two biases; either one alone is
    a last resort, reported because a biased depth is still more informative
    than reporting no lesion at all.

    Returns:
        (method_name, depth_series) -- ``method_name`` is one of
        ``half_span``, ``mean+knee_point+sigmoid_fit``, ``knee_point``,
        ``sigmoid_fit``, or ``no_lesion_surface`` when nothing is stable.
        ``depth_series`` maps column x to raw depth, empty for the last case.
    """
    half_span = method_depth_series(lesion_detection_data, 'half_span')
    if is_method_stable(half_span, stability_sd):
        return 'half_span', half_span

    stable = {}
    for method in _FALLBACK_METHODS:
        series = method_depth_series(lesion_detection_data, method)
        if is_method_stable(series, stability_sd):
            stable[method] = series

    if len(stable) == len(_FALLBACK_METHODS):
        knee, inflection = (stable[m] for m in _FALLBACK_METHODS)
        shared = knee.keys() & inflection.keys()
        if shared:
            averaged = {x: (knee[x] + inflection[x]) / 2.0 for x in shared}
            return 'mean+' + '+'.join(_FALLBACK_METHODS), averaged

    for method in _FALLBACK_METHODS:
        if method in stable:
            return method, stable[method]

    return NO_LESION_METHOD, {}


def compute_stable_combined_depth(lesion_detection_data: dict,
                                  ascan_x: int,
                                  depth_offset: float = DEPTH_OFFSET,
                                  depth_series: Optional[dict] = None,
                                  method_used: Optional[str] = None) -> tuple:
    """
    Look up one column's depth from the method chosen for the whole slice.

    Which method that is comes from :func:`select_depth_method`, which needs
    every column to judge lateral stability -- so it is decided once per slice
    and passed in here, not re-derived per column.

    Args:
        lesion_detection_data: Per-column detection metadata
        ascan_x: Column to read
        depth_offset: Constant px offset added to the result (tunable, default 0)
        depth_series: Chosen method's per-column depths
        method_used: Name of the chosen method, recorded on each column

    Returns:
        (depth_value, method_used) tuple
    """
    if ascan_x not in lesion_detection_data:
        return np.nan, "none"

    if depth_series is None or method_used is None:
        method_used, depth_series = select_depth_method(lesion_detection_data)

    if ascan_x not in depth_series:
        return np.nan, method_used

    return float(depth_series[ascan_x]) + depth_offset, method_used


def is_no_lesion_slice(combined_depths, no_lesion_sd: float = NO_LESION_SD) -> bool:
    """
    True when the combined depth is laterally unstable over the slice.

    A real lesion boundary is laterally smooth - that is what makes it a
    boundary. Scatter means the thing being tracked is not one.

    Gating on knee or inflection SD instead was measured and rejected: neither
    correlates with its own error (r = -0.06 and +0.01), and both overlap the
    no-lesion slice.
    """
    values = np.asarray([d for d in combined_depths if d is not None], dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return False
    return bool(np.std(values) > no_lesion_sd)


# Default refractive index for tooth material (enamel/dentin)
# Used for cavitation-aware depth correction
TOOTH_REFRACTIVE_INDEX = 1.5

def calculate_lesion_depth(surface: Surface, 
                          region_config,
                          image: np.ndarray,
                          search_depth: int = 200,
                          detection_method: DepthDetectionMethod = None,
                          smooth_depth_points: bool = True,
                          smoothing: float = 5.0,
                          smoothing_multiplier: float = 5.0,
                          spline_degree: int = 3,
                          median_kernel_size: int = 7,
                          outlier_threshold: float = 2,
                          stability_threshold: float = 20.0,
                          method_stability_sd: float = METHOD_STABILITY_SD,
                          depth_offset: float = DEPTH_OFFSET,
                          no_lesion_sd: float = NO_LESION_SD,
                          slice_id = None,
                          refractive_index: float = TOOTH_REFRACTIVE_INDEX) -> Optional[LesionDepth]:
    """
    Calculate lesion depth using various detection methods.
    
    Algorithm:
    1. For each A-Scan column in the lesion region
    2. Extract intensity values from surface downward (search_depth pixels)
    3. Apply selected detection method to find lesion depth
    4. Calculate depth as distance from surface to detected point
    5. [Optional] Apply spline smoothing to depth points to reduce noise
    
    Available Detection Methods:
    - KNEE_POINT: Two-line fitting (best for exponential decay)
    - SIGMOID_FIT: Sigmoid inflection point (50% transition, maximum rate of change)
    - SIGMOID_SHOULDER: Sigmoid shoulder point (15% from upper asymptote, early transition)
    - COMBINED_MEAN: Weighted combination of stable methods (preserves natural lesion texture)
    
    Args:
        surface: Detected surface with fitted curve
        region_config: Region configuration with lesion boundaries
        image: 2D numpy array (grayscale image)
        search_depth: Maximum depth to search below surface (default 200 pixels)
        detection_method: Method to use for depth detection (default combined)
        smooth_depth_points: If True, apply robust spline smoothing to depth points (default True)
        smoothing: Base smoothing factor for depth spline (default 5.0)
        smoothing_multiplier: Multiplier for smoothing (default 5.0)
        spline_degree: Degree of spline for depth smoothing (default 2)
        median_kernel_size: Size of median filter kernel for spike removal (default 5)
                           Larger values (e.g., 7) remove wider spikes from speckles
        outlier_threshold: Number of standard deviations for outlier detection (default 2.0)
                          Lower values (e.g., 1.5) are more aggressive at removing spikes
        stability_threshold: SD threshold in pixels for per-method stability reporting
        method_stability_sd: SD threshold in pixels deciding which method is
            trusted to supply the depth. Separate from stability_threshold,
            which only labels methods in the diagnostics report.
                           (default 20.0). Diagnostic only; the combination does not
                           branch on it.
        depth_offset: Constant pixel offset added to the combined depth (default 0.0).
                     Positive reads deeper, negative shallower. 0.0 is the validated
                     value; provided so a study can nudge the result if needed.
        no_lesion_sd: Lateral SD (px) of the combined depth above which the slice is
                     judged to have no lesion and is reported at the surface
                     (default 15.0). See NO_LESION_SD.
        refractive_index: Refractive index of tooth material for cavitation depth correction (default 1.5)
                         When cavitation is present, the subsurface lesion depth (below actual surface)
                         is divided by this value to convert from optical to physical depth.
                         Air (n=1) portion of cavitation requires no correction.
    
    Returns:
        LesionDepth object with depth measurements, or None if no valid surface
    """
    # Use default detection method if not specified
    if detection_method is None:
        detection_method = DepthDetectionMethod.get_default()
    
    # Extract BUFFERED lesion boundaries from region config
    # Use buffered coordinates to match the transition zone logic:
    # - Sound regions are extracted with 10px buffer from lesion boundaries
    # - Lesion depth should be detected in the same buffered area for consistency
    start_x = region_config.get_buffered_lesion_start_x()
    end_x = region_config.get_buffered_lesion_end_x()
    
    # Validate surface exists
    if not surface.fitted_curves or "actual_surface" not in surface.fitted_curves:
        return None
    
    # Always use actual surface for intensity profile extraction
    # This is the real tooth surface where we detect lesion depth
    surface_dict = {x: y for x, y in surface.fitted_curves["actual_surface"]}
    
    # For cavitated lesions, also get interpolated surface to calculate total depth
    # Interpolated surface spans over cavitation using only sound areas
    interpolated_dict = None
    if surface.is_cavitated and "interpolated_surface" in surface.fitted_curves:
        interpolated_dict = {x: y for x, y in surface.fitted_curves["interpolated_surface"]}
    height, width = image.shape
    depth_points = []
    lesion_detection_data = {}  # Store per-column lesion detection data for visualization
    
    # Always initialize raw points collection for all methods
    # This allows visualization and analysis regardless of selected method
    method_raw_points = {
        'knee_point': [],
        'sigmoid_fit': [],
        'sigmoid_shoulder': []
    }
    
    # Process every column in lesion region
    for ascan_x in range(start_x, end_x):
        if ascan_x not in surface_dict:
            continue
        
        surface_y = surface_dict[ascan_x]
        
        # Extract intensity profile from surface downward
        surface_y_int = int(surface_y)
        start_y = surface_y_int
        end_y = min(height, start_y + search_depth)
        
        if end_y - start_y < 10:  # Need minimum points for detection
            continue
        
        # Get intensity values
        intensity_profile = image[start_y:end_y, ascan_x].astype(float)
        # Depth indices start from 0 but represent depth from surface (including offset)
        depth_indices = np.arange(len(intensity_profile))
        
        # =====================================================================
        # ALWAYS COMPUTE ALL DETECTION METHODS
        # This ensures all depth data is available for visualization, analysis,
        # and the A-Scan viewer, regardless of which method the user selected.
        # The detection_method parameter only controls which depth is used for
        # the primary output (summary table, saved images).
        # =====================================================================
        
        # Method 1: Knee point with exp2 fit
        fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
        if fit_result is not None:
            knee_fitted_curve, fit_params = fit_result
            knee_depth, knee_idx = knee_pt(knee_fitted_curve, depth_indices)
        else:
            knee_fitted_curve, fit_params = None, None
            knee_depth, knee_idx = knee_pt(intensity_profile, depth_indices)
        
        # Method 2: Sigmoid fit (inflection and shoulder)
        sigmoid_depth, sigmoid_idx, sigmoid_meta = detect_depth_sigmoid_fit(
            intensity_profile, depth_indices
        )
        
        # Extract sigmoid results
        inflection_depth = sigmoid_meta.get('inflection_depth', np.nan) if sigmoid_meta.get('success') else np.nan
        inflection_idx = sigmoid_meta.get('inflection_idx', -1) if sigmoid_meta.get('success') else -1
        shoulder_depth = sigmoid_meta.get('shoulder_depth', np.nan) if sigmoid_meta.get('success') else np.nan
        shoulder_idx = sigmoid_meta.get('shoulder_idx', -1) if sigmoid_meta.get('success') else -1
        
        # Method 3: Half-span crossing (fit-free, cannot fail to converge)
        half_span_depth, half_span_meta = detect_depth_half_span(intensity_profile)

        # Store all method results in metadata (always available now)
        detection_metadata = {
            'knee_depth': knee_depth,
            'knee_idx': knee_idx,
            'inflection_depth': inflection_depth,
            'inflection_idx': inflection_idx,
            'shoulder_depth': shoulder_depth,
            'shoulder_idx': shoulder_idx,
            'half_span_depth': half_span_depth,
            'half_span_span': half_span_meta.get('span', np.nan),
            'half_span_fraction': half_span_meta.get('fraction', np.nan),
            # Every term the half-span crossing is built from, so the result
            # stays reconstructable from a saved config: this is a measurement
            # that has to be auditable after the fact, not just reproducible
            # by re-running. The smoothed profile is not stored -- it is a
            # boxcar of the intensity profile, which is stored, so it is
            # recomputed for display rather than duplicated on disk.
            'half_span_background': half_span_meta.get('background', np.nan),
            'half_span_peak': half_span_meta.get('peak', np.nan),
            'half_span_threshold': half_span_meta.get('threshold', np.nan),
            'half_span_smooth_window': HALF_SPAN_SMOOTH_WINDOW,
            'half_span_sustained': half_span_meta.get('sustained', True),
            'half_span_success': half_span_meta.get('success', False),
            'half_span_reason': half_span_meta.get('reason'),
            'sigmoid_success': sigmoid_meta.get('success', False),
            'fit_params': fit_params
        }
        
        # Copy additional sigmoid metadata if available
        if sigmoid_meta.get('success'):
            detection_metadata.update({
                'sigmoid_params': {
                    'L': sigmoid_meta.get('L'),
                    'U': sigmoid_meta.get('U'),
                    'k': sigmoid_meta.get('k'),
                    'z0': sigmoid_meta.get('z0')
                },
                'shoulder_intensity': sigmoid_meta.get('shoulder_intensity')
            })
        
        # Select which method's depth to use for primary output based on user selection
        if detection_method == DepthDetectionMethod.KNEE_POINT:
            depth_value = knee_depth
            depth_idx = knee_idx
            fitted_curve = knee_fitted_curve
            detection_metadata['method'] = 'knee_point'
            detection_metadata['used_fitting'] = fitted_curve is not None
            
        elif detection_method == DepthDetectionMethod.SIGMOID_FIT:
            depth_value = inflection_depth
            depth_idx = inflection_idx
            fitted_curve = np.array(sigmoid_meta['fitted_curve']) if 'fitted_curve' in sigmoid_meta else None
            detection_metadata['method'] = 'sigmoid_fit'
        
        elif detection_method == DepthDetectionMethod.SIGMOID_SHOULDER:
            depth_value = shoulder_depth
            depth_idx = shoulder_idx
            fitted_curve = np.array(sigmoid_meta['fitted_curve']) if 'fitted_curve' in sigmoid_meta else None
            detection_metadata['method'] = 'sigmoid_shoulder'
        
        elif detection_method == DepthDetectionMethod.COMBINED_MEAN:
            # For COMBINED_MEAN, use knee point as placeholder
            # The actual combined depth will be computed AFTER all A-Scans are processed
            depth_value = knee_depth
            depth_idx = knee_idx
            fitted_curve = knee_fitted_curve
            detection_metadata['method'] = 'combined_mean'
        
        # Store result if valid
        if not np.isnan(depth_value) and depth_idx >= 0:
            # Convert relative depth to absolute y-coordinate (using actual surface)
            lesion_bottom_y = start_y + depth_value
            
            # Calculate actual depth from surface with refractive index correction
            # For cavitated lesions, split depth into two parts:
            # 1. Cavitation depth (air, n=1): from interpolated surface to actual surface - no correction
            # 2. Subsurface depth (tooth, n~1.5): from actual surface to lesion bottom - divide by n
            # This accounts for OCT measuring optical path length, not physical distance
            if interpolated_dict is not None and ascan_x in interpolated_dict:
                interpolated_y = interpolated_dict[ascan_x]
                actual_y = surface_dict[ascan_x]
                
                # Cavitation depth: air gap from interpolated to actual surface (n=1, no correction)
                cavitation_depth = actual_y - interpolated_y
                
                # Subsurface depth: from actual surface into tooth material
                # depth_value is already relative to actual surface (profile starts at surface_y_int)
                subsurface_optical_depth = depth_value
                
                # Convert subsurface optical depth to physical depth using refractive index
                # physical_depth = optical_depth / n (OCT measures optical path length)
                subsurface_physical_depth = subsurface_optical_depth / refractive_index
                
                # Total corrected depth = air gap + corrected subsurface depth
                actual_depth_from_surface = cavitation_depth + subsurface_physical_depth
            else:
                # Non-cavitated: apply refractive index correction to entire depth
                # The depth is measured in tooth material throughout
                actual_depth_from_surface = depth_value / refractive_index
            
            depth_points.append((ascan_x, lesion_bottom_y, actual_depth_from_surface))
            
            # Collect raw points for all methods (used for stability analysis in COMBINED_MEAN)
            method_depth_keys = {
                'knee_point': 'knee_depth',
                'sigmoid_fit': 'inflection_depth',
                'sigmoid_shoulder': 'shoulder_depth'
            }
            for method_name, depth_key in method_depth_keys.items():
                depth = detection_metadata.get(depth_key, np.nan)
                if not np.isnan(depth):
                    abs_y = surface_y_int + depth
                    method_raw_points[method_name].append((ascan_x, abs_y))
            
            # Store data for visualization (for A-Scan viewer)
            lesion_detection_data[ascan_x] = {
                'intensity': intensity_profile.tolist(),
                'depth_idx': depth_indices.tolist(),
                'knee_idx': depth_idx,  # Name kept for compatibility
                'surface_y': surface_y_int,  # Original surface position
                'profile_start_y': start_y,  # Where profile extraction started
                # See the combined branch below for why these two are kept
                # apart: _px is drawn, _corrected is reported.
                'lesion_depth_px': depth_value,
                'lesion_depth_corrected': actual_depth_from_surface,
                'fitted_curve': fitted_curve.tolist() if fitted_curve is not None else None,
                'fit_params': fit_params,
                'detection_metadata': detection_metadata
            }
    
    if len(depth_points) == 0:
        # No valid depth points found
        return None
    
    # For COMBINED_MEAN method: combine per column, then apply the no-lesion gate.
    if detection_method == DepthDetectionMethod.COMBINED_MEAN:
        # Reported for diagnostics only; nothing branches on it.
        stability_info = compute_method_stability(
            method_raw_points,
            lesion_detection_data,
            stability_threshold=stability_threshold
        )

        # Stage 1: choose one method for the whole slice, then read each column
        # from it. The choice needs every column's depths to judge lateral
        # stability, so it cannot be made per column.
        ascan_xs = sorted(lesion_detection_data.keys())
        #
        # Deliberately NOT stability_threshold: that one only labels methods
        # in the diagnostics report above, and its 20.0 default is too loose
        # to reject a method here. Which method is trusted is a separate,
        # tighter decision -- see METHOD_STABILITY_SD.
        chosen_method, chosen_series = select_depth_method(
            lesion_detection_data, stability_sd=method_stability_sd
        )
        combined_by_x = {}
        for ascan_x in ascan_xs:
            combined_by_x[ascan_x] = compute_stable_combined_depth(
                lesion_detection_data, ascan_x, depth_offset=depth_offset,
                depth_series=chosen_series, method_used=chosen_method
            )

        # Stage 2: the gate acts on the combined depth's own lateral scatter,
        # so it cannot be evaluated until stage 1 has run.
        no_lesion = is_no_lesion_slice(
            [d for d, _ in combined_by_x.values()], no_lesion_sd=no_lesion_sd
        )

        depth_points = []
        for ascan_x in ascan_xs:
            combined_depth, method_used = combined_by_x[ascan_x]
            if no_lesion or method_used == NO_LESION_METHOD:
                combined_depth, method_used = NO_LESION_DEPTH, NO_LESION_METHOD

            if not np.isnan(combined_depth):
                surface_y = lesion_detection_data[ascan_x]['surface_y']
                
                # Convert to absolute y-coordinate
                lesion_bottom_y = surface_y + combined_depth
                
                # Refractive index correction, for the reported value only.
                # Acquisition runs at n=1, so pixels are raw optical path: a
                # depth in tooth reads ~1.5x too deep and must be divided,
                # while a cavitation is air and must not be.
                #
                # Cavitated columns therefore split into two segments:
                # 1. Interpolated (sound) surface to actual surface -- air, n=1
                # 2. Actual surface to lesion bottom -- tooth, divided by n
                if interpolated_dict is not None and ascan_x in interpolated_dict:
                    interpolated_y = interpolated_dict[ascan_x]
                    actual_y = surface_dict[ascan_x]
                    cavitation_depth = actual_y - interpolated_y
                    subsurface_physical_depth = combined_depth / refractive_index
                    actual_depth_from_surface = cavitation_depth + subsurface_physical_depth
                else:
                    # Non-cavitated: entire depth is in tooth material
                    actual_depth_from_surface = combined_depth / refractive_index
                
                # (x, y) is a pixel position for drawing; the third element is
                # the corrected depth, and is what reaches Excel via mean_depth.
                depth_points.append((ascan_x, lesion_bottom_y, actual_depth_from_surface))

                # Two spaces, deliberately kept apart:
                #   lesion_depth_px       - raw pixels, what the image shows.
                #     Everything drawn uses this, so a line lands on the
                #     boundary the operator can see. Operator marks are made on
                #     uncorrected images too, so the calibration constants and
                #     the validation scores live in this space as well.
                #   lesion_depth_corrected - physical depth after refractive
                #     index. Reported to Excel for downstream statistics; never
                #     drawn, because it does not correspond to a pixel row.
                column = lesion_detection_data[ascan_x]
                column['lesion_depth_px'] = combined_depth
                column['lesion_depth_corrected'] = actual_depth_from_surface
                column['detection_metadata']['depth_method_used'] = method_used
        
        if len(depth_points) == 0:
            return None
    
    # Extract depth values for statistics
    depths = [d for _, _, d in depth_points]
    # Convert to (x, y) format for compatibility
    raw_depth_points = [(x, y) for x, y, _ in depth_points]
    
    # Apply robust spline smoothing to depth points if requested
    smoothed_depth_points = None
    if smooth_depth_points and len(raw_depth_points) >= 4:
        # Use robust fitting to handle spikes from OCT speckles
        # This applies median filtering and outlier detection before spline smoothing
        smoothed_curves = fit_lesion_depth_curve_robust(
            raw_depth_points,
            start_x,
            end_x,
            smoothing=smoothing,
            smoothing_multiplier=smoothing_multiplier,
            spline_degree=spline_degree,
            median_kernel_size=median_kernel_size,
            outlier_threshold=outlier_threshold,
            curve_name="smoothed_depth"
        )
        
        if "smoothed_depth" in smoothed_curves:
            smoothed_depth_points = smoothed_curves["smoothed_depth"]
    
    return LesionDepth(
        depth_points=raw_depth_points,
        mean_depth=np.mean(depths),
        median_depth=np.median(depths),
        sd=np.std(depths),
        se=np.std(depths) / np.sqrt(len(depths)),
        lesion_detection_data=lesion_detection_data if len(lesion_detection_data) > 0 else None,
        smoothed_depth_points=smoothed_depth_points
    )
