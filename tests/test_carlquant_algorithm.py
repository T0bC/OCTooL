# -*- coding: utf-8 -*-
"""
CarlQuant Algorithm Development Module

This module contains the core algorithms for OCT image analysis:
- Surface detection
- Region extraction
- Clustering analysis
- Lesion depth calculation

Develop and test each function incrementally, then port to carl_quant_core.py

Created on Mon Oct 06 11:50:00 2025
@author: meissnerto
"""

import sys
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from sklearn.cluster import DBSCAN
from scipy.interpolate import splrep, splev
from scipy.optimize import curve_fit

# Add parent directory to path so we can import from carlquant_frames
sys.path.insert(0, str(Path(__file__).parent.parent))

from carlquant_frames.specimen_model import (
    RegionStats, Surface, LesionDepth, RegionConfig, AirConfig
)
from carlquant_frames.carl_quant_core import (
    DepthDetectionMethod,
    detect_depth_sigmoid_fit,
    fit_exp2_to_profile
)


# =============================================================================
# SURFACE DETECTION
# =============================================================================

def detect_surface(image: np.ndarray, air_config: Optional[AirConfig] = None, region_config: Optional[RegionConfig] = None) -> Surface:
    """
    Detect the surface of the specimen in the OCT image.
    
    Algorithm:
    1. Calculate threshold from AIR region (if provided)
    2. For each A-Scan column, find first pixel > threshold
    3. Find intensity peak within 250 pixels after threshold (actual surface)
    4. Apply DBSCAN clustering to remove speckles
    5. Filter points to keep only those in surface cluster(s)
    
    Args:
        image: 2D numpy array (grayscale image)
        air_config: AIR configuration with threshold region
        region_config: Region configuration with specimen boundaries
    
    Returns:
        Surface object with raw_points (peaks), cluster_labels, and fitted_curves
    """
    height, width = image.shape
    
    # Step 1: Calculate threshold based on AIR region
    threshold = calculate_air_threshold(image, air_config)
    
    # Step 2: Determine search boundaries (specimen start to end)
    if region_config:
        x_start = region_config.specimen_start[0]
        x_end = region_config.tooth_end[0]
    else:
        # No region config, search entire width
        x_start = 0
        x_end = width
    
    # Step 3: For each column (A-Scan) within boundaries, find surface peak
    # Skip first 25 pixels (typically white/black band)
    imageOffset = 25
    raw_points = []
    for x in range(x_start, x_end):
        column = image[imageOffset:, x]  # Skip first 25 pixels
        
        # Find first pixel that exceeds threshold
        above_threshold = np.where(column > threshold)[0]
        
        if len(above_threshold) > 0:
            threshold_idx = above_threshold[0]  # First pixel above threshold
            
            # Find the actual surface peak after threshold crossing
            peak_idx = find_surface_peak(column, threshold_idx, search_window=250)
            
            # Convert back to image coordinates
            y = peak_idx + imageOffset
            raw_points.append((x, y))
    
    # Step 4: Apply DBSCAN clustering to remove speckles
    # DBSCAN parameters - adjust in cluster_surface_points() for tuning
    filtered_points, cluster_labels = cluster_surface_points(
        raw_points,
        epsilon=17,          # Max distance between neighboring points (pixels)
        min_samples=10,      # Min points to form a cluster
        min_cluster_size=180 # Min cluster size to be considered surface
    )
    
    # Step 5: Fit smooth spline curve to surface points
    fitted_curves = {}
    is_cavitated = False
    cavitation_depth = 0.0
    
    if len(filtered_points) > 3:  # Need at least 4 points for spline
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
                    cavitation_threshold=5.0,  # Mean depth threshold in pixels
                    min_cavitation_ratio=0.7   # At least 70% of points must be cavitated
                )
    
    return Surface(
        raw_points=filtered_points,
        fitted_curves=fitted_curves,
        cluster_labels=cluster_labels,
        is_cavitated=is_cavitated,
        cavitation_depth=cavitation_depth
    )


def find_surface_peak(column: np.ndarray, threshold_idx: int, search_window: int = 250, 
                     min_peak_ratio: float = 0.66) -> int:
    """
    Find the first significant intensity peak (surface) after threshold crossing.
    
    The first pixel above threshold is not necessarily the surface peak.
    This function searches for the first local maximum (peak) within a window
    after the threshold crossing. If the first peak is too small compared to
    the maximum peak, it selects the maximum instead (avoiding tiny peaks).
    
    Args:
        column: 1D array of pixel intensities (A-Scan)
        threshold_idx: Index where threshold was first crossed
        search_window: Number of pixels to search after threshold (default 250)
        min_peak_ratio: Minimum ratio of first peak to max peak (default 0.33 = 1/3)
    
    Returns:
        Index of the peak position (surface)
    """
    # Define search range: from threshold point to threshold + search_window
    search_end = min(threshold_idx + search_window, len(column))
    search_region = column[threshold_idx:search_end]
    
    if len(search_region) == 0:
        return threshold_idx
    
    # Find the maximum peak in the search region
    max_intensity = np.max(search_region)
    max_offset = np.argmax(search_region)
    
    # Find the first local peak (where intensity stops increasing)
    for i in range(1, len(search_region) - 1):
        # Check if current point is a local maximum
        # (higher than both neighbors)
        if search_region[i] >= search_region[i-1] and search_region[i] > search_region[i+1]:
            first_peak_intensity = search_region[i]
            
            # Check if first peak is significant enough (at least 1/3 of max peak)
            if first_peak_intensity >= min_peak_ratio * max_intensity:
                # First peak is significant, use it
                peak_idx = threshold_idx + i
                return peak_idx
            else:
                # First peak too small, use maximum peak instead
                peak_idx = threshold_idx + max_offset
                return peak_idx
    
    # Fallback: if no local peak found, use the maximum in the search region
    peak_idx = threshold_idx + max_offset
    return peak_idx


def calculate_air_threshold(image: np.ndarray, air_config: Optional[AirConfig] = None) -> float:
    """
    Calculate intensity threshold based on AIR region.
    
    Args:
        image: 2D numpy array (grayscale image)
        air_config: AIR configuration with rectangular region
    
    Returns:
        float: Threshold value for air/tissue boundary
    """
    if not air_config or not air_config.point2:
        # Fallback: use image statistics if no AIR config
        return np.percentile(image, 50)
    
    # Extract AIR region
    x1, y1 = air_config.point1
    x2, y2 = air_config.point2
    
    # Ensure coordinates are within image bounds and properly ordered
    height, width = image.shape
    x1, x2 = max(0, min(x1, x2)), min(width, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(height, max(y1, y2))
    
    air_region = image[y1:y2, x1:x2]
    
    # Calculate 95th percentile to be robust against outliers in AIR
    air_q95 = np.percentile(air_region, 95)
    threshold = air_q95 * 1.6
    
    return threshold


# =============================================================================
# CLUSTERING ANALYSIS
# =============================================================================

def cluster_surface_points(raw_points: List[Tuple[int, int]], 
                          epsilon: float = 17, 
                          min_samples: int = 10,
                          min_cluster_size: int = 180) -> Tuple[List[Tuple[int, int]], Optional[List[int]]]:
    """
    Apply DBSCAN clustering to surface points to remove speckles.
    
    Args:
        raw_points: List of (x, y) surface point coordinates
        epsilon: Maximum distance between neighboring points (pixels)
        min_samples: Minimum points required to form a cluster
        min_cluster_size: Minimum cluster size to be considered surface
    
    Returns:
        Tuple of (filtered_points, cluster_labels)
        - filtered_points: Points belonging to surface clusters only
        - cluster_labels: Cluster ID for each filtered point
    """
    if len(raw_points) == 0:
        return raw_points, None
    
    # Convert points to numpy array for clustering
    points_array = np.array(raw_points)
    
    # Perform DBSCAN clustering
    dbscan = DBSCAN(eps=epsilon, min_samples=min_samples)
    cluster_labels = dbscan.fit_predict(points_array)
    
    # Find the most frequent cluster(s) representing the surface
    # Exclude noise points (label = -1)
    valid_labels = cluster_labels[cluster_labels >= 0]
    
    if len(valid_labels) == 0:
        # No clusters found, return original points
        return raw_points, None
    
    # Count occurrences of each cluster
    unique_labels, counts = np.unique(valid_labels, return_counts=True)
    
    # Find clusters with more than min_cluster_size points
    # This filters out small speckle clusters
    surface_cluster_ids = unique_labels[counts > min_cluster_size]
    
    # If no cluster meets the threshold, use the largest cluster
    if len(surface_cluster_ids) == 0:
        largest_cluster_id = unique_labels[np.argmax(counts)]
        surface_cluster_ids = np.array([largest_cluster_id])
    
    # Filter points: keep only those in surface clusters
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
    """
    Fit a smooth spline curve to surface points to create an intact surface.
    
    After clustering, some x-positions may be missing. This function fits
    a spline to the detected points and evaluates it at all x-positions
    to create a continuous, smooth surface.
    
    Args:
        surface_points: List of (x, y) surface point coordinates
        x_start: Starting x-coordinate for the fitted curve
        x_end: Ending x-coordinate for the fitted curve
        smoothing: Base smoothing factor (0=interpolation, higher=smoother)
        smoothing_multiplier: Multiplier for smoothing (scales with point count)
        spline_degree: Degree of spline (1=linear, 3=cubic, 5=quintic)
        curve_name: Name for the curve in returned dictionary
    
    Returns:
        Dictionary with fitted curve: {curve_name: [(x, y), ...]}
    """
    if len(surface_points) < 4:
        return {}
    
    # Extract x and y coordinates
    points_array = np.array(surface_points)
    x_coords = points_array[:, 0]
    y_coords = points_array[:, 1]
    
    # Sort by x coordinate (required for spline fitting)
    sort_idx = np.argsort(x_coords)
    x_sorted = x_coords[sort_idx]
    y_sorted = y_coords[sort_idx]
    
    # Fit spline using splrep
    # s parameter: smoothing * multiplier * point_count
    try:
        # Create spline representation
        s_param = smoothing * smoothing_multiplier * len(x_sorted)
        tck = splrep(x_sorted, y_sorted, k=spline_degree, s=s_param)
        
        # Evaluate spline at all x positions in the range
        x_full = np.arange(x_start, x_end)
        y_fitted = splev(x_full, tck)
        
        # Create list of (x, y) tuples for the fitted curve
        fitted_curve = [(int(x), int(y)) for x, y in zip(x_full, y_fitted)]
        
        return {curve_name: fitted_curve}
    
    except Exception as e:
        # If spline fitting fails, return empty dict
        print(f"Spline fitting failed: {e}")
        return {}


def fit_reference_surface(surface_points: List[Tuple[int, int]],
                          region_config,
                          x_start: int,
                          x_end: int,
                          smoothing: float = 2.0,
                          smoothing_multiplier: float = 5.0,
                          spline_degree: int = 3) -> Dict[str, List[Tuple[int, int]]]:
    """
    Fit reference surface curve excluding lesion area for cavitation detection.
    
    This creates a "spanning" curve that represents the expected intact surface
    by fitting only to sound tissue points (excluding lesion area). This can be
    compared to the primary fit to detect cavitation.
    
    Uses higher smoothing and lower degree for smoother spanning across lesion.
    
    Args:
        surface_points: List of (x, y) surface point coordinates
        region_config: Region configuration with lesion boundaries
        x_start: Starting x-coordinate for the fitted curve
        x_end: Ending x-coordinate for the fitted curve
        smoothing: Base smoothing factor (higher = smoother spanning)
        smoothing_multiplier: Multiplier for smoothing
        spline_degree: Degree of spline (lower = smoother spanning)
    
    Returns:
        Dictionary with reference curve: {"reference": [(x, y), ...]}
    """
    if not region_config or len(surface_points) < 4:
        return {}
    
    # Get lesion boundaries
    lesion_start_x = region_config.lesion_start[0]
    lesion_end_x = region_config.lesion_end[0]
    
    # Filter out points in lesion area (keep only sound tissue)
    sound_points = [(x, y) for x, y in surface_points 
                    if x < lesion_start_x or x > lesion_end_x]
    
    if len(sound_points) < 4:
        return {}
    
    # Fit spline to sound tissue points only with higher smoothing for spanning
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
    """
    Detect surface cavitation by comparing primary and reference curves.
    
    Cavitation is detected when the primary surface (actual) is significantly
    deeper than the reference surface (expected intact) in the lesion area.
    
    Only considers points where primary is BELOW (deeper than) reference.
    This avoids false positives when reference fit doesn't match curvature.
    
    Args:
        primary_curve: Primary spline fit using all points
        reference_curve: Reference spline fit using only sound tissue
        region_config: Region configuration with lesion boundaries
        cavitation_threshold: Mean vertical distance threshold (pixels, default 20)
        min_cavitation_ratio: Minimum ratio of cavitated points (default 0.3 = 30%)
    
    Returns:
        Tuple of (is_cavitated, mean_cavitation_depth)
        - is_cavitated: True if cavitation detected
        - mean_cavitation_depth: Mean depth where primary > reference (0 if none)
    """
    if not primary_curve or not reference_curve or not region_config:
        return False, 0.0
    
    # Get lesion boundaries
    lesion_start_x = region_config.lesion_start[0]
    lesion_end_x = region_config.lesion_end[0]
    
    # Convert curves to dictionaries for easy lookup
    primary_dict = {x: y for x, y in primary_curve}
    reference_dict = {x: y for x, y in reference_curve}
    
    # Calculate vertical distances in lesion area
    # Only count positive distances (where primary is deeper than reference)
    cavitation_depths = []
    total_points = 0
    
    for x in range(lesion_start_x, lesion_end_x + 1):
        if x in primary_dict and x in reference_dict:
            total_points += 1
            # Distance = primary - reference (positive if primary is deeper/cavitated)
            # In image coordinates: higher y = deeper into tissue
            distance = primary_dict[x] - reference_dict[x]
            
            # Only count points where primary is deeper (cavitated)
            if distance > 0:
                cavitation_depths.append(distance)
    
    if not cavitation_depths or total_points == 0:
        return False, 0.0
    
    # Calculate mean cavitation depth (only from cavitated points)
    mean_cavitation_depth = np.mean(cavitation_depths)
    
    # Calculate ratio of cavitated points
    cavitation_ratio = len(cavitation_depths) / total_points
    
    # Cavitation detected if:
    # 1. Mean depth exceeds threshold AND
    # 2. Sufficient percentage of points are cavitated
    is_cavitated = (mean_cavitation_depth > cavitation_threshold and 
                   cavitation_ratio >= min_cavitation_ratio)
    
    return is_cavitated, mean_cavitation_depth


# =============================================================================
# REGION EXTRACTION
# =============================================================================

def extract_regions(image: np.ndarray, 
                   surface: Surface, 
                   region_config: RegionConfig,
                   num_sound_regions: int = 3,
                   num_lesion_regions: int = 3,
                   region_size: int = 25,
                   surface_offset: int = 10) -> List[RegionStats]:
    """
    Extract pixel values from sound and lesion regions.
    
    Algorithm:
    1. Divide sound areas (left and right of lesion) into num_sound_regions each
    2. Divide lesion area into num_lesion_regions
    3. For each region, place 25x25 pixel rectangle 10px below surface
    4. Extract pixel values and calculate statistics
    
    Args:
        image: 2D numpy array (grayscale image)
        surface: Detected surface with fitted curve
        region_config: Region boundaries (4 points)
        num_sound_regions: Number of sound regions per sound area (left + right)
        num_lesion_regions: Number of lesion regions
        region_size: Size of extraction rectangle (default 25x25)
        surface_offset: Distance below surface to start extraction (default 10px)
    
    Returns:
        List of RegionStats with region coordinates
    """
    height, width = image.shape
    
    # Extract boundary x-coordinates from 4-point configuration
    specimen_start_x, _ = region_config.specimen_start
    lesion_start_x, _ = region_config.lesion_start
    lesion_end_x, _ = region_config.lesion_end
    tooth_end_x, _ = region_config.tooth_end
    
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
    
    # Calculate positions for sound regions (left side: specimen_start to lesion_start)
    sound_left_width = lesion_start_x - specimen_start_x
    sound_left_spacing = sound_left_width / (num_sound_regions + 1)
    
    for i in range(num_sound_regions):
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
    
    # Calculate positions for sound regions (right side: lesion_end to tooth_end)
    sound_right_width = tooth_end_x - lesion_end_x
    sound_right_spacing = sound_right_width / (num_sound_regions + 1)
    
    for i in range(num_sound_regions):
        center_x = int(lesion_end_x + sound_right_spacing * (i + 1))
        stats = extract_region_at(center_x, "sound", num_sound_regions + i + 1)
        if stats:
            region_stats.append(stats)
    
    return region_stats


def extract_region_pixels(image: np.ndarray, 
                         surface_points: List[Tuple[int, int]],
                         x_start: int, 
                         x_end: int,
                         depth: int = 100) -> List[int]:
    """
    Extract pixel values from a vertical region below the surface.
    
    Args:
        image: 2D numpy array (grayscale image)
        surface_points: List of (x, y) surface coordinates
        x_start: Left boundary of region
        x_end: Right boundary of region
        depth: Number of pixels to extract below surface
    
    Returns:
        List of pixel intensity values
    """
    # TODO: Implement pixel extraction
    # 1. Interpolate surface within x_start to x_end
    # 2. For each x, extract pixels from surface to surface+depth
    # 3. Return flattened list of pixel values
    
    pixel_values = []
    # Placeholder implementation
    return pixel_values





# =============================================================================
# LESION DEPTH CALCULATION
# =============================================================================

def knee_pt(y: np.ndarray, x: np.ndarray = None) -> Tuple[float, int]:
    """
    Find the knee point of a curve y=f(x).
    
    Translated from MATLAB knee_pt function by D. Kroon.
    The knee is found by fitting two lines (left and right of each candidate point)
    and minimizing the sum of fitting errors.
    
    Args:
        y: Vector of y values (must be >= 3 elements)
        x: Vector of x values (same size as y). If None, uses 1:length(y)
    
    Returns:
        Tuple of (x_value_at_knee, index_of_knee)
    """
    # Make y a 1D array
    y = np.asarray(y).flatten()
    
    # Check minimum length
    if len(y) < 3:
        return np.nan, -1
    
    # Create or validate x
    if x is None:
        x = np.arange(len(y), dtype=float)
    else:
        x = np.asarray(x).flatten()
    
    # Check dimensions match
    if len(x) != len(y):
        return np.nan, -1
    
    # Sort by x if needed
    if np.any(np.diff(x) < 0):
        sort_idx = np.argsort(x)
        x = x[sort_idx]
        y = y[sort_idx]
        idx_map = sort_idx
    else:
        idx_map = np.arange(len(x))
    
    # Compute cumulative sums for forward (left-of-knee) fits
    sigma_xy = np.cumsum(x * y)
    sigma_x = np.cumsum(x)
    sigma_y = np.cumsum(y)
    sigma_xx = np.cumsum(x * x)
    n = np.arange(1, len(y) + 1, dtype=float)
    
    det = n * sigma_xx - sigma_x * sigma_x
    # Avoid division by zero
    det = np.where(det == 0, 1e-10, det)
    
    mfwd = (n * sigma_xy - sigma_x * sigma_y) / det
    bfwd = -(sigma_x * sigma_xy - sigma_xx * sigma_y) / det
    
    # Compute cumulative sums for backward (right-of-knee) fits
    x_rev = x[::-1]
    y_rev = y[::-1]
    sigma_xy = np.cumsum(x_rev * y_rev)
    sigma_x = np.cumsum(x_rev)
    sigma_y = np.cumsum(y_rev)
    sigma_xx = np.cumsum(x_rev * x_rev)
    
    det = n * sigma_xx - sigma_x * sigma_x
    det = np.where(det == 0, 1e-10, det)
    
    mbck = np.flip((n * sigma_xy - sigma_x * sigma_y) / det)
    bbck = np.flip(-(sigma_x * sigma_xy - sigma_xx * sigma_y) / det)
    
    # Calculate error for each potential breakpoint
    error_curve = np.full(len(y), np.nan)
    
    for breakpt in range(1, len(y) - 1):  # Skip first and last points
        # Errors for left side (forward fit)
        y_fit_fwd = mfwd[breakpt] * x[:breakpt+1] + bfwd[breakpt]
        delsfwd = y_fit_fwd - y[:breakpt+1]
        
        # Errors for right side (backward fit)
        y_fit_bck = mbck[breakpt] * x[breakpt:] + bbck[breakpt]
        delsbck = y_fit_bck - y[breakpt:]
        
        # Sum of absolute errors
        error_curve[breakpt] = np.sum(np.abs(delsfwd)) + np.sum(np.abs(delsbck))
    
    # Find minimum error location
    loc = np.nanargmin(error_curve)
    res_x = x[loc]
    idx_of_result = idx_map[loc]
    
    return res_x, idx_of_result


def exp2_model(z, a, b, c, d):
    """
    Double exponential decay model for OCT intensity.
    I(z) = a*exp(b*z) + c*exp(d*z)
    
    Args:
        z: Depth values
        a, b, c, d: Model parameters
    
    Returns:
        Intensity values
    """
    return a * np.exp(b * z) + c * np.exp(d * z)


def fit_exp2_to_profile(intensity_profile: np.ndarray, depth_indices: np.ndarray) -> Optional[Tuple[np.ndarray, Dict]]:
    """
    Fit double exponential model to intensity profile.
    
    Args:
        intensity_profile: Intensity values
        depth_indices: Corresponding depth indices
    
    Returns:
        Tuple of (fitted_curve, params_dict) or None if fitting fails
        params_dict contains: {'a', 'b', 'c', 'd', 'success'}
    """
    try:
        # Initial guess for parameters
        # a, b (fast decay), c, d (slow decay)
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
                [255, 0, 255, 0]  # Upper bounds (intensity max 255, decay must be negative)
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
        
    except Exception as e:
        print(f"Exp2 fitting failed: {e}")
        return None


def compute_method_stability(method_raw_points: dict, 
                            lesion_detection_data: dict,
                            stability_threshold: float = 0.3) -> dict:
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
                           Recommended: 10-15 pixels for typical OCT images
        
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


def compute_stable_combined_depth(lesion_detection_data: dict, 
                                  stability_info: dict,
                                  x: int,
                                  preserve_wobbliness: bool = True) -> tuple:
    """
    Compute combined depth using only stable methods with optional wobbliness preservation.
    
    When preserve_wobbliness=True, uses weighted averaging where methods with higher
    variability (more wobbly) get MORE weight. This preserves the natural texture of
    irregular lesions instead of smoothing them out.
    
    Args:
        lesion_detection_data: Dict containing per-column detection metadata
        stability_info: Dict with stability metrics for each method
        x: Current x-coordinate
        preserve_wobbliness: If True, weight by SD to preserve variation (default True)
        
    Returns:
        (depth_value, method_used) tuple
        method_used is a string indicating which methods were combined
    """
    if x not in lesion_detection_data:
        return np.nan, "none"
    
    metadata = lesion_detection_data[x].get('detection_metadata', {})
    
    # Collect available depth values and their stability
    available_methods = []
    
    # Knee point
    knee_depth = metadata.get('knee_depth', np.nan)
    if not np.isnan(knee_depth) and stability_info.get('knee_point', {}).get('is_stable', False):
        available_methods.append(('knee_point', knee_depth))
    
    # Sigmoid inflection
    inflection_depth = metadata.get('inflection_depth', np.nan)
    if not np.isnan(inflection_depth) and stability_info.get('sigmoid_fit', {}).get('is_stable', False):
        available_methods.append(('sigmoid_fit', inflection_depth))
    
    # Sigmoid shoulder
    shoulder_depth = metadata.get('shoulder_depth', np.nan)
    if not np.isnan(shoulder_depth) and stability_info.get('sigmoid_shoulder', {}).get('is_stable', False):
        available_methods.append(('sigmoid_shoulder', shoulder_depth))
    
    # If no stable methods, use the most stable one (lowest CV)
    if len(available_methods) == 0:
        # Find method with lowest CV
        min_cv = np.inf
        best_method = None
        best_depth = np.nan
        
        for method_name in ['knee_point', 'sigmoid_fit', 'sigmoid_shoulder']:
            cv = stability_info.get(method_name, {}).get('cv', np.inf)
            if cv < min_cv:
                if method_name == 'knee_point':
                    depth = metadata.get('knee_depth', np.nan)
                elif method_name == 'sigmoid_fit':
                    depth = metadata.get('inflection_depth', np.nan)
                else:  # sigmoid_shoulder
                    depth = metadata.get('shoulder_depth', np.nan)
                
                if not np.isnan(depth):
                    min_cv = cv
                    best_method = method_name
                    best_depth = depth
        
        if best_method is not None:
            return best_depth, f"fallback_{best_method}"
        else:
            return np.nan, "none"
    
    # Combine stable methods
    depths = [d for _, d in available_methods]
    method_names = [m for m, _ in available_methods]
    
    if preserve_wobbliness and len(available_methods) > 1:
        # Weighted average: methods with higher SD get MORE weight
        # This preserves the natural wobbliness of irregular lesions
        weights = []
        for method_name, _ in available_methods:
            sd = stability_info.get(method_name, {}).get('std_depth', 1.0)
            # Use SD as weight (higher SD = more weight)
            # Add small constant to avoid division by zero
            weights.append(max(sd, 0.1))
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Weighted average
        combined_depth = sum(d * w for d, w in zip(depths, weights))
        method_used = "+".join(method_names) + "_weighted"
    else:
        # Simple average (original behavior)
        combined_depth = np.mean(depths)
        method_used = "+".join(method_names)
    
    return combined_depth, method_used


def calculate_lesion_depth(
    surface: Surface,
    region_config: RegionConfig,
    image: np.ndarray,
    search_depth: int = 200,
    smooth_depth_points: bool = True,
    detection_method: str = "knee_point",
    compute_all_methods: bool = False,
    smoothing: float = 5.0,
    smoothing_multiplier: float = 5.0,
    spline_degree: int = 2,
    slice_id: str = "unknown",
    stability_threshold: float = 20.0,
    preserve_wobbliness: bool = True
) -> Optional[LesionDepth]:
    """
    Calculate lesion depth using various detection methods.
    
    Algorithm:
    1. For each A-Scan column in the lesion region
    2. Extract intensity values from surface downward (search_depth pixels)
    3. Apply selected detection method to find lesion depth
    4. Calculate depth as distance from surface to detected point
    5. [Optional] Apply spline smoothing to depth points to reduce noise
    
    Stability-Based Method Selection (for "combined_mean"):
    - Computes ABSOLUTE standard deviation for each method across A-scans
    - SD measures wobbliness/variation in depth detection (in pixels)
    - Methods with SD > stability_threshold are excluded from averaging
    - If no methods are stable, uses the one with lowest SD
    
    Args:
        stability_threshold: SD threshold in pixels (default 20.0 pixels)
                           Lower = stricter (filters out scattered detections)
                           Higher = more lenient (allows more variation)
                           Recommended range: 10-30 pixels for typical OCT images
        preserve_wobbliness: If True, use weighted averaging to preserve natural
                           lesion texture (default True). Methods with higher SD
                           get more weight, preventing over-smoothing
    
    Available Detection Methods:
    - knee_point: Two-line fitting (best for exponential decay)
    - sigmoid_fit: Sigmoid inflection point (50% transition)
    - sigmoid_shoulder: Sigmoid shoulder point (15% from upper asymptote)
    - combined_mean: Mean of knee_point and sigmoid_fit
    
    Args:
        surface: Detected surface with fitted curve
        region_config: Region configuration with lesion boundaries
        image: 2D numpy array (grayscale image)
        search_depth: Maximum depth to search below surface (default 200 pixels)
        smooth_depth_points: If True, apply spline smoothing to depth points (default True)
        smoothing: Base smoothing factor for depth spline (default 5.0)
        smoothing_multiplier: Multiplier for smoothing (default 5.0)
        spline_degree: Degree of spline for depth smoothing (default 2)
    
    Returns:
        LesionDepth object with depth measurements, or None if no valid surface
    """
    # Extract lesion boundaries from region config
    start_x, _ = region_config.lesion_start
    end_x, _ = region_config.lesion_end
    
    # Validate surface exists
    if not surface.fitted_curves or "actual_surface" not in surface.fitted_curves:
        print("WARNING: No surface detected - cannot calculate lesion depth")
        return None
    
    # Convert surface to dictionary for lookup
    surface_dict = {x: y for x, y in surface.fitted_curves["actual_surface"]}
    
    height, width = image.shape
    depth_points = []
    lesion_detection_data = {}  # Store per-column lesion detection data for visualization
    
    # Process every column in lesion region
    for ascan_x in range(start_x, end_x):
        if ascan_x not in surface_dict:
            continue
        
        # Surface y-coordinate 
        surface_y = surface_dict[ascan_x] 
        
        # Extract intensity profile from surface downward
        surface_y_int = int(surface_y)
        start_y = surface_y_int
        end_y = min(height, start_y + search_depth)
        
        if end_y - start_y < 10:  # Need minimum points for knee detection
            continue
        
        # Get intensity values
        intensity_profile = image[start_y:end_y, ascan_x].astype(float)
        # Depth indices start from 0 but represent depth from surface
        depth_indices = np.arange(len(intensity_profile))
        
        # Apply detection method
        depth_value = np.nan
        depth_idx = -1
        detection_metadata = {}
        fitted_curve = None
        fit_params = None
        
        # If compute_all_methods is True, compute all three methods and store in metadata
        if compute_all_methods:
            # Compute knee point with Exp2 fitting
            profile_for_knee = intensity_profile
            knee_fitted_curve = None
            fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
            if fit_result is not None:
                knee_fitted_curve, _ = fit_result
                profile_for_knee = knee_fitted_curve
            knee_depth, knee_idx = knee_pt(profile_for_knee, depth_indices)
            
            # Compute sigmoid (inflection and shoulder)
            sigmoid_depth, sigmoid_idx, sigmoid_meta = detect_depth_sigmoid_fit(
                intensity_profile, depth_indices
            )
            
            # Store all methods in metadata for visualization
            detection_metadata['knee_depth'] = knee_depth
            detection_metadata['knee_idx'] = knee_idx
            # Store Exp2 fitted curve for knee point visualization
            if knee_fitted_curve is not None:
                detection_metadata['exp2_fitted_curve'] = knee_fitted_curve.tolist()
            if sigmoid_meta.get('success'):
                detection_metadata['inflection_depth'] = sigmoid_meta.get('inflection_depth', np.nan)
                detection_metadata['inflection_idx'] = sigmoid_meta.get('inflection_idx', -1)
                detection_metadata['shoulder_depth'] = sigmoid_meta.get('shoulder_depth', np.nan)
                detection_metadata['shoulder_idx'] = sigmoid_meta.get('shoulder_idx', -1)
                if 'fitted_curve' in sigmoid_meta:
                    detection_metadata['sigmoid_fitted_curve'] = sigmoid_meta['fitted_curve']
        
        # Determine which depth value to use for the primary result
        # (this affects depth_points and statistics, but not visualization in compare mode)
        if detection_method == "knee_point":
            # Fit exp2 curve, then find knee point
            fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
            if fit_result is not None:
                fitted_curve, fit_params = fit_result
                depth_value, depth_idx = knee_pt(fitted_curve, depth_indices)
            else:
                fitted_curve, fit_params = None, None
                depth_value, depth_idx = knee_pt(intensity_profile, depth_indices)

            detection_metadata = {
                'method': 'knee_point',
                'used_fitting': fitted_curve is not None,
                'fit_params': fit_params
            }
            
        elif detection_method == "sigmoid_fit":
            if not compute_all_methods:
                depth_value, depth_idx, detection_metadata = detect_depth_sigmoid_fit(
                    intensity_profile, depth_indices
                )
                if 'fitted_curve' in detection_metadata:
                    fitted_curve = np.array(detection_metadata['fitted_curve'])
            else:
                # Use already computed values
                depth_value = detection_metadata.get('inflection_depth', np.nan)
                depth_idx = detection_metadata.get('inflection_idx', -1)
                detection_metadata['method'] = 'sigmoid_fit'
        
        elif detection_method == "sigmoid_shoulder":
            if not compute_all_methods:
                # Use shoulder point from sigmoid fit
                _, _, sigmoid_meta = detect_depth_sigmoid_fit(
                    intensity_profile, depth_indices
                )
                if sigmoid_meta.get('success') and not np.isnan(sigmoid_meta.get('shoulder_depth', np.nan)):
                    depth_value = sigmoid_meta['shoulder_depth']
                    depth_idx = sigmoid_meta['shoulder_idx']
                    detection_metadata = sigmoid_meta.copy()
                    detection_metadata['method'] = 'sigmoid_shoulder'
                    if 'fitted_curve' in sigmoid_meta:
                        fitted_curve = np.array(sigmoid_meta['fitted_curve'])
                else:
                    depth_value, depth_idx = np.nan, -1
                    detection_metadata = {'method': 'sigmoid_shoulder', 'success': False}
            else:
                # Use already computed values
                depth_value = detection_metadata.get('shoulder_depth', np.nan)
                depth_idx = detection_metadata.get('shoulder_idx', -1)
                detection_metadata['method'] = 'sigmoid_shoulder'
        
        elif detection_method == "combined_mean":
            if not compute_all_methods:
                # Run both methods and average
                profile_for_knee = intensity_profile
                knee_fitted_curve = None
                
                fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
                if fit_result is not None:
                    knee_fitted_curve, fit_params = fit_result
                    profile_for_knee = knee_fitted_curve
                
                knee_depth, knee_idx = knee_pt(profile_for_knee, depth_indices)
                sigmoid_depth, sigmoid_idx, sigmoid_meta = detect_depth_sigmoid_fit(
                    intensity_profile, depth_indices
                )
                
                if not np.isnan(knee_depth) and not np.isnan(sigmoid_depth):
                    depth_value = (knee_depth + sigmoid_depth) / 2.0
                    depth_idx = int(np.argmin(np.abs(depth_indices - depth_value)))
                    detection_metadata = {
                        'method': 'combined_mean',
                        'knee_depth': knee_depth,
                        'knee_idx': knee_idx,
                        'sigmoid_depth': sigmoid_depth,
                        'sigmoid_idx': sigmoid_idx,
                        'sigmoid_fitted_curve': sigmoid_meta.get('fitted_curve')
                    }
                    if knee_fitted_curve is not None:
                        fitted_curve = knee_fitted_curve
                elif not np.isnan(knee_depth):
                    depth_value, depth_idx = knee_depth, knee_idx
                    detection_metadata = {'method': 'combined_mean', 'fallback': 'knee_point'}
                elif not np.isnan(sigmoid_depth):
                    depth_value, depth_idx = sigmoid_depth, sigmoid_idx
                    detection_metadata = {'method': 'combined_mean', 'fallback': 'sigmoid_fit'}
                else:
                    depth_value, depth_idx = np.nan, -1
                    detection_metadata = {'method': 'combined_mean', 'success': False}
            else:
                # Use already computed values and average
                knee_depth = detection_metadata.get('knee_depth', np.nan)
                sigmoid_depth = detection_metadata.get('inflection_depth', np.nan)
                
                if not np.isnan(knee_depth) and not np.isnan(sigmoid_depth):
                    depth_value = (knee_depth + sigmoid_depth) / 2.0
                    depth_idx = int(np.argmin(np.abs(depth_indices - depth_value)))
                elif not np.isnan(knee_depth):
                    depth_value = knee_depth
                    depth_idx = detection_metadata.get('knee_idx', -1)
                elif not np.isnan(sigmoid_depth):
                    depth_value = sigmoid_depth
                    depth_idx = detection_metadata.get('inflection_idx', -1)
                else:
                    depth_value, depth_idx = np.nan, -1
                
                detection_metadata['method'] = 'combined_mean'
        
        # Store result if valid
        if not np.isnan(depth_value) and depth_idx >= 0:
            # Convert relative depth to absolute y-coordinate
            lesion_bottom_y = start_y + depth_value
            # Actual depth from surface
            actual_depth_from_surface = depth_value
            
            depth_points.append((ascan_x, lesion_bottom_y, actual_depth_from_surface))
            
            # Ensure fitted_curve is set for A-Scan visualization
            # In compare mode, use exp2_fitted_curve from metadata if available
            if compute_all_methods and fitted_curve is None:
                if 'exp2_fitted_curve' in detection_metadata:
                    fitted_curve = np.array(detection_metadata['exp2_fitted_curve'])
            
            # Store data for visualization (for A-Scan viewer)
            lesion_detection_data[ascan_x] = {
                'intensity': intensity_profile.tolist(),
                'depth_idx': depth_indices.tolist(),
                'knee_idx': depth_idx,  # Name kept for compatibility
                'surface_y': surface_y_int,  # Original surface position
                'profile_start_y': start_y,  # Where profile extraction started
                'knee_depth': depth_value,  # Depth relative to profile start
                'actual_depth': actual_depth_from_surface,  # Total depth from surface
                'fitted_curve': fitted_curve.tolist() if fitted_curve is not None else None,
                'fit_params': fit_params,
                'detection_metadata': detection_metadata
            }
    
    if len(depth_points) == 0:
        # No valid depth points found
        print(f"[Slice {slice_id}] WARNING: No valid lesion depth points detected in range x={start_x} to x={end_x}")
        return None
    
    # Extract depth values for statistics
    depths = [d for _, _, d in depth_points]
    # Convert to (x, y) format for compatibility
    raw_depth_points = [(x, y) for x, y, _ in depth_points]
    
    # Apply spline smoothing to depth points if requested
    smoothed_depth_points = None
    if smooth_depth_points and len(raw_depth_points) >= 4:
        # Use fit_surface_curve to smooth the depth points
        # This reuses the same spline fitting logic used for surface detection
        smoothed_curves = fit_surface_curve(
            raw_depth_points,
            start_x,
            end_x,
            smoothing=smoothing,
            smoothing_multiplier=smoothing_multiplier,
            spline_degree=spline_degree,
            curve_name="smoothed_depth"
        )
        
        if "smoothed_depth" in smoothed_curves:
            smoothed_depth_points = smoothed_curves["smoothed_depth"]
            print(f"[Slice {slice_id}] Applied spline smoothing to {len(raw_depth_points)} depth points -> {len(smoothed_depth_points)} smoothed points")
    
    # If compute_all_methods is True OR using combined_mean, compute smoothed splines for all three methods
    method_splines = None
    if (compute_all_methods or detection_method == "combined_mean") and lesion_detection_data:
        method_splines = {}
        
        # Collect raw points for each method from knee_data
        method_raw_points = {
            "knee_point": [],
            "sigmoid_fit": [],
            "sigmoid_shoulder": []
        }
        
        for ascan_x, detection_info in lesion_detection_data.items():
            surface_y = detection_info['surface_y']
            metadata = detection_info.get('detection_metadata', {})
            
            # Knee point
            # Note: depths in metadata are relative to surface_y (surface_offset is always 0)
            if 'knee_depth' in metadata and not np.isnan(metadata['knee_depth']):
                abs_y = int(surface_y + metadata['knee_depth'])
                method_raw_points["knee_point"].append((ascan_x, abs_y))
            
            # Sigmoid inflection
            if 'inflection_depth' in metadata and not np.isnan(metadata['inflection_depth']):
                abs_y = int(surface_y + metadata['inflection_depth'])
                method_raw_points["sigmoid_fit"].append((ascan_x, abs_y))
            
            # Sigmoid shoulder
            if 'shoulder_depth' in metadata and not np.isnan(metadata['shoulder_depth']):
                abs_y = int(surface_y + metadata['shoulder_depth'])
                method_raw_points["sigmoid_shoulder"].append((ascan_x, abs_y))
        
        # Compute stability metrics for each method
        stability_info = compute_method_stability(method_raw_points, lesion_detection_data, stability_threshold=stability_threshold)
        
        # Log stability results
        print(f"\n[Slice {slice_id}] === Method Stability Analysis ===")
        for method_name, info in stability_info.items():
            status = "STABLE" if info['is_stable'] else "UNSTABLE"
            print(f"[Slice {slice_id}] {method_name:20s}: SD={info['cv']:.1f}px ({status}), n={info['n_points']}, mean={info['mean_depth']:.1f}px")
        
        # Store stability info in method_splines for later access
        method_splines = {'stability_info': stability_info}
        
        # If using combined_mean with stability-based selection, recompute depth_points
        if detection_method == "combined_mean":
            print(f"\n[Slice {slice_id}] === Recomputing Combined Mean with Stability-Based Selection ===")
            
            # Show weighting strategy
            if preserve_wobbliness:
                print(f"[Slice {slice_id}] Using WEIGHTED averaging (preserves wobbliness)")
                stable_methods = [m for m, info in stability_info.items() if info.get('is_stable', False)]
                if len(stable_methods) > 1:
                    print(f"[Slice {slice_id}] Weights based on SD (higher SD = more weight):")
                    for method in stable_methods:
                        sd = stability_info[method].get('std_depth', 0)
                        print(f"[Slice {slice_id}]   {method}: SD={sd:.1f}px")
            else:
                print(f"[Slice {slice_id}] Using SIMPLE averaging (equal weights)")
            
            depth_points = []  # Reset depth points
            
            for ascan_x in sorted(lesion_detection_data.keys()):
                combined_depth, method_used = compute_stable_combined_depth(lesion_detection_data, stability_info, ascan_x, preserve_wobbliness)
                
                if not np.isnan(combined_depth):
                    surface_y = lesion_detection_data[ascan_x]['surface_y']
                    
                    # Convert to absolute y-coordinate
                    lesion_bottom_y = surface_y + combined_depth
                    actual_depth_from_surface = combined_depth
                    
                    depth_points.append((ascan_x, lesion_bottom_y, actual_depth_from_surface))
                    
                    # Update lesion_detection_data with new combined depth
                    lesion_detection_data[ascan_x]['knee_depth'] = combined_depth
                    lesion_detection_data[ascan_x]['actual_depth'] = actual_depth_from_surface
                    lesion_detection_data[ascan_x]['detection_metadata']['combined_method_used'] = method_used
            
            print(f"[Slice {slice_id}] Recomputed {len(depth_points)} depth points using stability-based method selection")
            
            # Recompute statistics with new depth points
            if len(depth_points) > 0:
                depths = [d for _, _, d in depth_points]
                raw_depth_points = [(x, y) for x, y, _ in depth_points]
                
                # Fit spline for the combined mean result
                if len(raw_depth_points) >= 4:
                    combined_curves = fit_surface_curve(
                        raw_depth_points,
                        start_x,
                        end_x,
                        smoothing=smoothing,
                        smoothing_multiplier=smoothing_multiplier,
                        spline_degree=spline_degree,
                        curve_name="combined_mean"
                    )
                    if "combined_mean" in combined_curves:
                        method_splines["combined_mean"] = combined_curves["combined_mean"]
                        print(f"[Slice {slice_id}] Fitted spline for combined_mean: {len(raw_depth_points)} raw points -> {len(combined_curves['combined_mean'])} smoothed points")
        
        # Fit splines for each method using SAME parameters as single method
        for method_name, raw_points in method_raw_points.items():
            if len(raw_points) >= 4:
                smoothed_curves = fit_surface_curve(
                    raw_points,
                    start_x,
                    end_x,
                    smoothing=smoothing,
                    smoothing_multiplier=smoothing_multiplier,
                    spline_degree=spline_degree,
                    curve_name=method_name
                )
                if method_name in smoothed_curves:
                    method_splines[method_name] = smoothed_curves[method_name]
                    print(f"[Slice {slice_id}] Fitted spline for {method_name}: {len(raw_points)} raw points -> {len(smoothed_curves[method_name])} smoothed points")
    
    return LesionDepth(
        depth_points=raw_depth_points,
        mean_depth=np.mean(depths),
        median_depth=np.median(depths),
        sd=np.std(depths),
        se=np.std(depths) / np.sqrt(len(depths)),
        lesion_detection_data=lesion_detection_data if len(lesion_detection_data) > 0 else None,
        smoothed_depth_points=smoothed_depth_points,
        method_splines=method_splines  # Store pre-computed splines for all methods
    )


def detect_lesion_bottom(image: np.ndarray,
                        surface_points: List[Tuple[int, int]],
                        x_start: int,
                        x_end: int) -> List[Tuple[int, int]]:
    """
    Detect the bottom boundary of the lesion.
    
    Args:
        image: 2D numpy array (grayscale image)
        surface_points: List of (x, y) surface coordinates
        x_start: Left boundary of lesion
        x_end: Right boundary of lesion
    
    Returns:
        List of (x, y) coordinates for lesion bottom
    """
    # TODO: Implement lesion bottom detection
    # Methods: intensity gradient, threshold-based, etc.
    bottom_points = []
    return bottom_points


# =============================================================================
# FULL PIPELINE
# =============================================================================

def process_slice(image_path: Path,
                 region_config: RegionConfig,
                 air_config: Optional[AirConfig] = None,
                 num_sound_regions: int = 3,
                 num_lesion_regions: int = 3,
                 detection_method: str = "knee_point",
                 compute_all_methods: bool = False) -> Tuple[List[RegionStats], Surface, LesionDepth]:
    """
    Process a single OCT slice through the complete pipeline.
    
    This is the main function that orchestrates all algorithm steps.
    Use this to test the complete workflow on individual slices.
    
    Args:
        image_path: Path to image file
        region_config: Region boundaries configuration
        air_config: AIR threshold configuration
        num_sound_regions: Number of sound regions to extract
        num_lesion_regions: Number of lesion regions to extract
    
    Returns:
        Tuple of (region_stats, surface, lesion_depth)
    """
    # Load image
    img = Image.open(image_path).convert('L')  # Convert to grayscale
    image_array = np.array(img)
    
    # Step 1: Detect surface
    surface = detect_surface(image_array, air_config, region_config)
    
    # Step 2: Extract regions
    region_stats = extract_regions(
        image_array, 
        surface, 
        region_config,
        num_sound_regions,
        num_lesion_regions
    )
    
    # Step 3: Calculate lesion depth
    # Extract slice ID from image path for logging
    slice_id = Path(image_path).stem if isinstance(image_path, (str, Path)) else "unknown"
    lesion_depth = calculate_lesion_depth(
        surface, region_config, image_array, 
        detection_method=detection_method, 
        compute_all_methods=compute_all_methods,
        slice_id=slice_id
    )
    
    return region_stats, surface, lesion_depth


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def visualize_surface(image: np.ndarray, surface: Surface) -> np.ndarray:
    """
    Create visualization of detected surface on image.
    
    Args:
        image: 2D numpy array (grayscale image)
        surface: Detected surface
    
    Returns:
        RGB image with surface overlay
    """
    # Convert grayscale to RGB for colored overlay
    if len(image.shape) == 2:
        vis_image = np.stack([image] * 3, axis=-1)
    else:
        vis_image = image.copy()
    
    # Draw surface points
    for x, y in surface.raw_points:
        if 0 <= x < vis_image.shape[1] and 0 <= y < vis_image.shape[0]:
            vis_image[y, x] = [255, 0, 0]  # Red for raw points
    
    return vis_image


def visualize_regions(image: np.ndarray, 
                     region_config: RegionConfig,
                     surface: Surface) -> np.ndarray:
    """
    Create visualization of region boundaries on image.
    
    Args:
        image: 2D numpy array (grayscale image)
        region_config: Region boundaries
        surface: Detected surface
    
    Returns:
        RGB image with region overlay
    """
    # Convert grayscale to RGB for colored overlay
    if len(image.shape) == 2:
        vis_image = np.stack([image] * 3, axis=-1)
    else:
        vis_image = image.copy()
    
    # Draw vertical boundaries
    start_x, _ = region_config.start_point
    end_x, _ = region_config.end_point
    
    # Draw start boundary (yellow)
    if 0 <= start_x < vis_image.shape[1]:
        vis_image[:, start_x] = [255, 255, 0]
    
    # Draw end boundary (yellow)
    if 0 <= end_x < vis_image.shape[1]:
        vis_image[:, end_x] = [255, 255, 0]
    
    return vis_image


# =============================================================================
# TESTING AND DEBUGGING
# =============================================================================

if __name__ == "__main__":
    print("CarlQuant Algorithm Development Module")
    print("=" * 60)
    print()
    print("This module contains algorithm functions for:")
    print("  - Surface detection")
    print("  - Region extraction")
    print("  - Clustering analysis")
    print("  - Lesion depth calculation")
    print()
    print("Use test_carlquant_viewer.py to visualize results.")
    print()
    
    # Example: Test on a single image
    # from test_carlquant_config import load_single_specimen
    # specimen = load_single_specimen(r"path\to\specimen")
    # if specimen and specimen.config:
    #     slice_idx = 0
    #     region_config = specimen.config.regions.get(slice_idx)
    #     air_config = specimen.config.air.get(slice_idx)
    #     
    #     region_stats, surface, lesion_depth = process_slice(
    #         specimen.images[slice_idx],
    #         region_config,
    #         air_config
    #     )
    #     
    #     print(f"Processed slice {slice_idx}")
    #     print(f"  Surface points: {len(surface.raw_points)}")
    #     print(f"  Regions: {len(region_stats)}")
    #     print(f"  Lesion depth: {lesion_depth.mean_depth:.2f}")
