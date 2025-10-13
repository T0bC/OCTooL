# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 11:05:22 2025

@author: meissnerto
"""

from time import sleep
from threading import Thread
from carlquant_frames.data_io import DataSaver
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth
from carlquant_frames.progress_dialog import ProgressDialog
import random
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Optional
from sklearn.cluster import DBSCAN
from scipy.interpolate import splrep, splev
from scipy.optimize import curve_fit
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
from enum import Enum


# =============================================================================
# PARALLEL PROCESSING SUPPORT
# =============================================================================

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
            lesion_depth = calculate_lesion_depth(
                surface,
                region_config,
                image_array,
                search_depth=200,
                use_curve_fitting=True,
                detection_method=detection_method,
                stability_threshold=20.0,
                preserve_wobbliness=True
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
                     curve_name: str = "spline") -> Dict[str, List[Tuple[int, int]]]:
    """Fit a smooth spline curve to surface points."""
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


def fit_reference_surface(surface_points: List[Tuple[int, int]],
                          region_config,
                          x_start: int,
                          x_end: int,
                          smoothing: float = 2.0,
                          smoothing_multiplier: float = 5.0,
                          spline_degree: int = 3) -> Dict[str, List[Tuple[int, int]]]:
    """Fit reference surface curve excluding lesion area for cavitation detection."""
    if not region_config or len(surface_points) < 4:
        return {}
    
    lesion_start_x = region_config.lesion_start[0]
    lesion_end_x = region_config.lesion_end[0]
    
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
        curve_name="reference"
    )


def detect_cavitation(primary_curve: List[Tuple[int, int]],
                     reference_curve: List[Tuple[int, int]],
                     region_config,
                     cavitation_threshold: float = 10.0,
                     min_cavitation_ratio: float = 0.3) -> Tuple[bool, float]:
    """Detect surface cavitation by comparing primary and reference curves."""
    if not primary_curve or not reference_curve or not region_config:
        return False, 0.0
    
    lesion_start_x = region_config.lesion_start[0]
    lesion_end_x = region_config.lesion_end[0]
    
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
    lesion_start_x, _ = region_config.lesion_start
    lesion_end_x, _ = region_config.lesion_end
    tooth_end_x, _ = region_config.tooth_end
    
    # Define overall boundaries for surface lookup
    x_start = specimen_start_x
    x_end = tooth_end_x
    
    # Use primary surface fit for positioning
    if not surface.fitted_curves or "spline" not in surface.fitted_curves:
        return []
    
    # Convert surface to dictionary for easy lookup
    surface_dict = {x: y for x, y in surface.fitted_curves["spline"]}
    
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
    
    # Calculate positions for sound regions (left side: specimen_start to lesion_start)
    sound_left_width = lesion_start_x - specimen_start_x
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
    
    # Calculate positions for sound regions (right side: lesion_end to tooth_end)
    sound_right_width = tooth_end_x - lesion_end_x
    sound_right_spacing = sound_right_width / (num_sound_per_side + 1)
    
    for i in range(num_sound_per_side):
        center_x = int(lesion_end_x + sound_right_spacing * (i + 1))
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
    imageOffset = 25
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
        fitted_curves = fit_surface_curve(filtered_points, x_start, x_end, curve_name="spline")
        
        # Reference fit: excludes lesion area (for cavitation detection)
        if region_config:
            reference_curves = fit_reference_surface(filtered_points, region_config, x_start, x_end)
            fitted_curves.update(reference_curves)
            
            # Detect cavitation by comparing primary and reference curves
            if "spline" in fitted_curves and "reference" in fitted_curves:
                is_cavitated, cavitation_depth = detect_cavitation(
                    fitted_curves["spline"],
                    fitted_curves["reference"],
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
        # 1. Inflection point (z0): Maximum rate of change (50% transition)
        # 2. Shoulder: Upper transition region (~15% from U to L)
        
        # Inflection point (current method)
        depth_value = z0
        depth_idx = np.argmin(np.abs(depth_indices - z0))
        
        # Calculate shoulder point
        # For sigmoid: I(z) = L + (U - L) / (1 + exp(k * (z - z0)))
        # Shoulder: Point where I(z) = U - 0.15*(U - L) (15% down from upper asymptote)
        
        intensity_range = U - L
        shoulder_intensity = U - 0.15 * intensity_range  # 85% of range
        
        # Solve for z where sigmoid equals target intensity
        # I(z) = L + (U - L) / (1 + exp(k * (z - z0))) = target
        # Rearranging: z = z0 - (1/k) * ln((U - L)/(target - L) - 1)
        
        try:
            # Shoulder depth (earlier in profile, closer to surface)
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
                            knee_data: dict,
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
        knee_data: Dict containing per-column detection metadata
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
            if x in knee_data:
                surface_y = knee_data[x]['surface_y']
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


def compute_stable_combined_depth(knee_data: dict, 
                                  stability_info: dict,
                                  x: int,
                                  preserve_wobbliness: bool = True) -> tuple:
    """
    Compute combined depth using only stable methods with optional wobbliness preservation.
    
    When preserve_wobbliness=True, uses weighted averaging where methods with higher
    variability (more wobbly) get MORE weight. This preserves the natural texture of
    irregular lesions instead of smoothing them out.
    
    Args:
        knee_data: Dict containing per-column detection metadata
        stability_info: Dict with stability metrics for each method
        x: Current x-coordinate
        preserve_wobbliness: If True, weight by SD to preserve variation (default True)
        
    Returns:
        (depth_value, method_used) tuple
        method_used is a string indicating which methods were combined
    """
    if x not in knee_data:
        return np.nan, "none"
    
    metadata = knee_data[x].get('detection_metadata', {})
    
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


def calculate_lesion_depth(surface: Surface, 
                          region_config,
                          image: np.ndarray,
                          search_depth: int = 200,
                          detection_method: DepthDetectionMethod = None,
                          use_curve_fitting: bool = True,
                          smooth_depth_points: bool = True,
                          smoothing: float = 5.0,
                          smoothing_multiplier: float = 5.0,
                          spline_degree: int = 2,
                          threshold_percent: float = 0.5,
                          gradient_smooth_window: int = 5,
                          surface_offset: int = 0,
                          stability_threshold: float = 20.0,
                          preserve_wobbliness: bool = True) -> Optional[LesionDepth]:
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
        detection_method: Method to use for depth detection (default KNEE_POINT)
        use_curve_fitting: If True and method=KNEE_POINT, fit exp2 before detection (default True)
        smooth_depth_points: If True, apply spline smoothing to depth points (default True)
        smoothing: Base smoothing factor for depth spline (default 5.0)
        smoothing_multiplier: Multiplier for smoothing (default 5.0)
        spline_degree: Degree of spline for depth smoothing (default 2)
        threshold_percent: For THRESHOLD method, fraction of surface intensity (default 0.5)
        gradient_smooth_window: For MAX_GRADIENT method, smoothing window size (default 5)
        surface_offset: Pixels to skip below surface before starting profile (default 0)
                       This avoids saturated surface peak values in curve fitting
        stability_threshold: SD threshold in pixels for method stability (default 20.0)
                           Methods with SD > threshold are excluded from combining
        preserve_wobbliness: If True, use weighted averaging to preserve lesion texture (default True)
                           Methods with higher SD get more weight
    
    Returns:
        LesionDepth object with depth measurements, or None if no valid surface
    """
    # Use default detection method if not specified
    if detection_method is None:
        detection_method = DepthDetectionMethod.get_default()
    
    # Extract lesion boundaries from region config
    start_x, _ = region_config.lesion_start
    end_x, _ = region_config.lesion_end
    
    # Validate surface exists
    if not surface.fitted_curves or "spline" not in surface.fitted_curves:
        return None
    
    # Select surface based on cavitation status
    # If cavitated, use reference surface (fitted excluding lesion area)
    # Otherwise, use primary spline surface
    if surface.is_cavitated and "reference" in surface.fitted_curves:
        surface_dict = {x: y for x, y in surface.fitted_curves["reference"]}
    else:
        surface_dict = {x: y for x, y in surface.fitted_curves["spline"]}
    
    height, width = image.shape
    depth_points = []
    knee_data = {}  # Store detection data for visualization (name kept for compatibility)
    
    # Process every column in lesion region
    for x in range(start_x, end_x):
        if x not in surface_dict:
            continue
        
        surface_y = surface_dict[x]
        
        # Extract intensity profile from surface downward
        # Skip surface_offset pixels to avoid saturated surface peak (typically 255)
        surface_y_int = int(surface_y)
        start_y = surface_y_int + surface_offset
        end_y = min(height, start_y + search_depth)
        
        if end_y - start_y < 10:  # Need minimum points for detection
            continue
        
        # Get intensity values
        intensity_profile = image[start_y:end_y, x].astype(float)
        # Depth indices start from 0 but represent depth from surface (including offset)
        depth_indices = np.arange(len(intensity_profile))
        
        # Apply detection method
        depth_value = np.nan
        depth_idx = -1
        detection_metadata = {}
        fitted_curve = None
        fit_params = None
        
        if detection_method == DepthDetectionMethod.KNEE_POINT:
            # Original method: optionally fit exp2, then find knee point
            profile_for_knee = intensity_profile
            
            if use_curve_fitting:
                fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
                if fit_result is not None:
                    fitted_curve, fit_params = fit_result
                    profile_for_knee = fitted_curve
            
            depth_value, depth_idx = knee_pt(profile_for_knee, depth_indices)
            detection_metadata = {
                'method': 'knee_point',
                'used_fitting': use_curve_fitting and fitted_curve is not None,
                'fit_params': fit_params
            }
            
        elif detection_method == DepthDetectionMethod.SIGMOID_FIT:
            depth_value, depth_idx, detection_metadata = detect_depth_sigmoid_fit(
                intensity_profile, depth_indices
            )
            # Extract fitted curve if available
            if 'fitted_curve' in detection_metadata:
                fitted_curve = np.array(detection_metadata['fitted_curve'])
        
        elif detection_method == DepthDetectionMethod.SIGMOID_SHOULDER:
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
        
        elif detection_method == DepthDetectionMethod.COMBINED_MEAN:
            # Compute all three methods and store in metadata
            # Method 1: Knee point with exp2 fit
            profile_for_knee = intensity_profile
            knee_fitted_curve = None
            
            if use_curve_fitting:
                fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
                if fit_result is not None:
                    knee_fitted_curve, fit_params = fit_result
                    profile_for_knee = knee_fitted_curve
            
            knee_depth, knee_idx = knee_pt(profile_for_knee, depth_indices)
            
            # Method 2: Sigmoid fit (inflection and shoulder)
            sigmoid_depth, sigmoid_idx, sigmoid_meta = detect_depth_sigmoid_fit(
                intensity_profile, depth_indices
            )
            
            # Store all method results in metadata for stability analysis
            detection_metadata = {
                'method': 'combined_mean',
                'knee_depth': knee_depth,
                'knee_idx': knee_idx,
                'inflection_depth': sigmoid_meta.get('inflection_depth', np.nan) if sigmoid_meta.get('success') else np.nan,
                'inflection_idx': sigmoid_meta.get('inflection_idx', -1) if sigmoid_meta.get('success') else -1,
                'shoulder_depth': sigmoid_meta.get('shoulder_depth', np.nan) if sigmoid_meta.get('success') else np.nan,
                'shoulder_idx': sigmoid_meta.get('shoulder_idx', -1) if sigmoid_meta.get('success') else -1,
            }
            
            # For now, use simple average as placeholder (will be replaced after stability analysis)
            # This ensures we have valid depth_points for the first pass
            valid_depths = []
            if not np.isnan(knee_depth):
                valid_depths.append(knee_depth)
            if not np.isnan(sigmoid_depth):
                valid_depths.append(sigmoid_depth)
            
            if len(valid_depths) > 0:
                depth_value = np.mean(valid_depths)
                depth_idx = int(np.argmin(np.abs(depth_indices - depth_value)))
                
                # Store fitted curve for visualization
                if knee_fitted_curve is not None:
                    fitted_curve = knee_fitted_curve
            else:
                depth_value = np.nan
                depth_idx = -1
                detection_metadata['success'] = False
        
        # Store result if valid
        if not np.isnan(depth_value) and depth_idx >= 0:
            # Convert relative depth to absolute y-coordinate
            # depth_value is relative to start_y, which already includes surface_offset
            lesion_bottom_y = start_y + depth_value
            # Actual depth from surface (including the offset we skipped)
            actual_depth_from_surface = surface_offset + depth_value
            
            depth_points.append((x, lesion_bottom_y, actual_depth_from_surface))
            
            # Store data for visualization (for A-Scan viewer)
            knee_data[x] = {
                'intensity': intensity_profile.tolist(),
                'depth_idx': depth_indices.tolist(),
                'knee_idx': depth_idx,  # Name kept for compatibility
                'surface_y': surface_y_int,  # Original surface position
                'profile_start_y': start_y,  # Where profile extraction started (surface + offset)
                'surface_offset': surface_offset,  # Offset applied
                'knee_depth': depth_value,  # Depth relative to profile start
                'actual_depth': actual_depth_from_surface,  # Total depth from surface
                'fitted_curve': fitted_curve.tolist() if fitted_curve is not None else None,
                'fit_params': fit_params,
                'detection_metadata': detection_metadata
            }
    
    if len(depth_points) == 0:
        # No valid depth points found
        return None
    
    # For COMBINED_MEAN method: perform stability analysis and recompute with weighted averaging
    if detection_method == DepthDetectionMethod.COMBINED_MEAN:
        # Collect raw points for each method
        method_raw_points = {
            'knee_point': [],
            'sigmoid_fit': [],
            'sigmoid_shoulder': []
        }
        
        for x in range(start_x, end_x):
            if x not in knee_data:
                continue
            
            metadata = knee_data[x].get('detection_metadata', {})
            surface_y = knee_data[x]['surface_y']
            profile_start_y = knee_data[x]['profile_start_y']
            
            # Knee point
            knee_depth = metadata.get('knee_depth', np.nan)
            if not np.isnan(knee_depth):
                abs_y = profile_start_y + knee_depth
                method_raw_points['knee_point'].append((x, abs_y))
            
            # Sigmoid inflection
            inflection_depth = metadata.get('inflection_depth', np.nan)
            if not np.isnan(inflection_depth):
                abs_y = profile_start_y + inflection_depth
                method_raw_points['sigmoid_fit'].append((x, abs_y))
            
            # Sigmoid shoulder
            shoulder_depth = metadata.get('shoulder_depth', np.nan)
            if not np.isnan(shoulder_depth):
                abs_y = profile_start_y + shoulder_depth
                method_raw_points['sigmoid_shoulder'].append((x, abs_y))
        
        # Compute stability metrics
        stability_info = compute_method_stability(
            method_raw_points,
            knee_data,
            stability_threshold=stability_threshold
        )
        
        # Recompute depth points using stable weighted combination
        depth_points = []
        for x in range(start_x, end_x):
            if x not in knee_data:
                continue
            
            # Get weighted combined depth
            combined_depth, method_used = compute_stable_combined_depth(
                knee_data,
                stability_info,
                x,
                preserve_wobbliness=preserve_wobbliness
            )
            
            if not np.isnan(combined_depth):
                surface_y = knee_data[x]['surface_y']
                profile_start_y = knee_data[x]['profile_start_y']
                
                # Convert relative depth to absolute y-coordinate
                lesion_bottom_y = profile_start_y + combined_depth
                # Actual depth from surface
                actual_depth_from_surface = surface_offset + combined_depth
                
                depth_points.append((x, lesion_bottom_y, actual_depth_from_surface))
                
                # Update knee_data with combined result
                knee_data[x]['knee_depth'] = combined_depth
                knee_data[x]['actual_depth'] = actual_depth_from_surface
                knee_data[x]['detection_metadata']['combined_method_used'] = method_used
        
        if len(depth_points) == 0:
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
    
    return LesionDepth(
        depth_points=raw_depth_points,
        mean_depth=np.mean(depths),
        median_depth=np.median(depths),
        sd=np.std(depths),
        se=np.std(depths) / np.sqrt(len(depths)),
        knee_data=knee_data if len(knee_data) > 0 else None,
        smoothed_depth_points=smoothed_depth_points
    )


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def run_carl_quant(context):
    """
    Run CarlQuant analysis with progress dialog and cancellation support.
    
    The progress dialog shows:
    - Overall specimen progress
    - Current specimen being processed
    - Slice progress within each specimen
    - Cancel button for graceful interruption
    
    Cancellation behavior:
    - Waits for current slice(s) to finish processing
    - Saves results for completed specimens
    - Does not corrupt Excel/JSON files
    """
    def worker():
        # Prepare specimen list
        specimen_list = list(context.specimen_data.items())
        specimen_ids = [sid for sid, _ in specimen_list]
        
        # Create progress dialog on main thread
        progress_dialog = None
        def create_dialog():
            nonlocal progress_dialog
            progress_dialog = ProgressDialog(
                context.root,
                total_specimens=len(specimen_list),
                specimen_names=specimen_ids
            )
        
        context.root.after(0, create_dialog)
        
        # Wait for dialog to be created
        while progress_dialog is None:
            time.sleep(0.01)
        
        cancelled = False
        
        try:
            for specimen_idx, (specimen_id, specimen) in enumerate(specimen_list):
                # Check for cancellation before starting new specimen
                if progress_dialog.is_cancelled():
                    cancelled = True
                    context.status_bar.update("Analysis cancelled by user", level="warning")
                    break
                
                # Update progress dialog
                progress_dialog.update_specimen(
                    specimen_idx,
                    specimen_id,
                    specimen.slices
                )
                
                # User choice to reanalyze a specimen
                choice = getattr(specimen, "analysis_choice", "new")
                if choice == "skip":
                    context.status_bar.update(f"Skipped specimen {specimen_id} (user choice)", level="info")
                    
                    # Update specimen status to "Skipped"
                    specimen.status = "Skipped"
                    specimen_panel = context.get_panel("carl_specimen")
                    if specimen_panel:
                        for row_idx in range(specimen_panel.sheet.total_rows()):
                            if specimen_panel.sheet.get_cell_data(row_idx, 0) == specimen_id:
                                specimen_panel.sheet.set_cell_data(row_idx, 4, "Skipped")
                                specimen_panel._set_column_widths()
                                break
                    
                    progress_dialog.complete_specimen(specimen_idx)
                    continue
                elif choice == "overwrite":
                    specimen.measurement = context.analysis_metadata.get("measurement", 1)
                elif choice == "new":
                    specimen.measurement = context.analysis_metadata.get("measurement", 1)

                specimen.operator = context.analysis_metadata.get("operator", "OP")

                # Get region configuration
                num_sound = context.region_config.get("sound", 3)
                num_lesion = context.region_config.get("lesion", 3)
                
                # Prepare slice tasks
                slice_tasks = []
                for slice_index in range(specimen.slices):
                    image_path = specimen.images[slice_index]
                    region_config = None
                    air_config = None
                    if specimen.config:
                        region_config = specimen.config.regions.get(slice_index)
                        air_config = specimen.config.air.get(slice_index)
                    slice_tasks.append((slice_index, image_path, region_config, air_config))
                
                # Auto-detect parallel processing: use parallel if >10 slices
                use_parallel = len(slice_tasks) > 10
                num_workers = max(1, multiprocessing.cpu_count() - 1)
                
                start_time = time.time()
                processed_count = 0
                
                if use_parallel and num_workers > 1:
                    # PARALLEL PROCESSING WITH ON-DEMAND LOADING
                    effective_workers = min(num_workers, len(slice_tasks))
                    
                    progress_dialog.update_status(
                        f"Processing {len(slice_tasks)} slices with {effective_workers} workers...",
                        color="blue"
                    )
                    
                    # Get detection method from context
                    detection_method_str = getattr(context, 'detection_method', 'combined_mean')
                    
                    with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                        # Submit tasks - each worker loads its own image on-demand
                        future_to_slice = {}
                        for slice_idx, image_path, region_config, air_config in slice_tasks:
                            # Check for cancellation before submitting
                            if progress_dialog.is_cancelled():
                                cancelled = True
                                break
                            
                            future = executor.submit(
                                process_slice_parallel,
                                slice_idx, image_path, region_config, air_config, num_sound, num_lesion, detection_method_str
                            )
                            future_to_slice[future] = slice_idx
                        
                        if cancelled:
                            break
                        
                        for future in as_completed(future_to_slice):
                            # Check for cancellation (wait for current futures to complete)
                            if progress_dialog.is_cancelled():
                                cancelled = True
                                # Don't break immediately - let submitted tasks finish
                            
                            slice_idx = future_to_slice[future]
                            try:
                                result_idx, region_stats, surface, lesion_depth, error = future.result()
                                
                                if error:
                                    context.status_bar.update(f"Error on slice {result_idx + 1}", level="error")
                                else:
                                    # Store results with thread safety
                                    if hasattr(context, "result_lock"):
                                        with context.result_lock:
                                            DataSaver.store_slice_result(specimen, result_idx, region_stats, surface, lesion_depth)
                                    else:
                                        DataSaver.store_slice_result(specimen, result_idx, region_stats, surface, lesion_depth)
                                    
                                    processed_count += 1
                                    
                                    # Update progress dialog
                                    progress_dialog.update_slice(processed_count - 1, len(slice_tasks))
                                    progress_dialog.update_status(
                                        f"Completed slice {result_idx + 1}",
                                        color="blue"
                                    )
                                    
                            except Exception as e:
                                context.status_bar.update(f"Exception on slice {slice_idx + 1}: {e}", level="error")
                    
                    # MEMORY CLEANUP: Force garbage collection after parallel processing
                    import gc
                    gc.collect()
                    
                    # If cancelled during parallel processing, break specimen loop
                    if cancelled:
                        break
                
                else:
                    # SEQUENTIAL PROCESSING
                    progress_dialog.update_status(
                        f"Processing {len(slice_tasks)} slices sequentially...",
                        color="blue"
                    )
                    
                    for slice_idx, image_path, region_config, air_config in slice_tasks:
                        # Check for cancellation before each slice
                        if progress_dialog.is_cancelled():
                            cancelled = True
                            break
                        
                        try:
                            # Load image
                            progress_dialog.update_status(
                                f"Loading image for slice {slice_idx + 1}...",
                                color="blue"
                            )
                            img = Image.open(image_path).convert('L')
                            image_array = np.array(img)
                            img.close()  # MEMORY CLEANUP: Explicitly close PIL image
                            del img
                            
                            # Detect surface
                            progress_dialog.update_status(
                                f"Detecting surface (slice {slice_idx + 1})...",
                                color="blue"
                            )
                            surface = detect_surface(image_array, air_config, region_config)
                            
                            # Extract regions
                            if region_config:
                                progress_dialog.update_status(
                                    f"Extracting regions (slice {slice_idx + 1})...",
                                    color="blue"
                                )
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
                                progress_dialog.update_status(
                                    f"Calculating lesion depth (slice {slice_idx + 1})...",
                                    color="blue"
                                )
                                # Get detection method from context (default to COMBINED_MEAN)
                                detection_method_str = getattr(context, 'detection_method', 'combined_mean')
                                detection_method = DepthDetectionMethod(detection_method_str)
                                
                                lesion_depth = calculate_lesion_depth(
                                    surface,
                                    region_config,
                                    image_array,
                                    search_depth=200,
                                    use_curve_fitting=True,
                                    detection_method=detection_method,
                                    stability_threshold=20.0,
                                    preserve_wobbliness=True
                                )
                            else:
                                lesion_depth = None
                            
                            # Store results
                            progress_dialog.update_status(
                                f"Storing results (slice {slice_idx + 1})...",
                                color="blue"
                            )
                            if hasattr(context, "result_lock"):
                                with context.result_lock:
                                    DataSaver.store_slice_result(specimen, slice_idx, region_stats, surface, lesion_depth)
                            else:
                                DataSaver.store_slice_result(specimen, slice_idx, region_stats, surface, lesion_depth)
                            
                            processed_count += 1
                            
                            # Update progress dialog
                            progress_dialog.update_slice(slice_idx, len(slice_tasks))
                            progress_dialog.update_status(
                                f"Completed slice {slice_idx + 1}",
                                color="green"
                            )
                        
                        except Exception as e:
                            context.status_bar.update(f"Error on slice {slice_idx + 1}: {e}", level="error")
                        finally:
                            # MEMORY CLEANUP: Ensure image_array is released
                            if 'image_array' in locals():
                                del image_array
                    
                    # If cancelled during sequential processing, break specimen loop
                    if cancelled:
                        break

                # Save results after all slices are processed (or if cancelled mid-specimen)
                try:
                    DataSaver.save_results(specimen)
                    progress_dialog.update_status(
                        f"Saved results for {specimen_id}",
                        color="green"
                    )
                    
                    # MEMORY CLEANUP: Clear results from memory after saving to disk
                    # Results will be reloaded from JSON when user selects specimen for viewing
                    specimen.results.clear()
                    import gc
                    gc.collect()
                    
                    # Update specimen status to "Completed"
                    specimen.status = "Completed"
                    
                    # Update the specimen panel table
                    specimen_panel = context.get_panel("carl_specimen")
                    if specimen_panel:
                        # Find the row for this specimen
                        for row_idx in range(specimen_panel.sheet.total_rows()):
                            if specimen_panel.sheet.get_cell_data(row_idx, 0) == specimen_id:
                                specimen_panel.sheet.set_cell_data(row_idx, 4, "Completed")
                                # Refresh column widths to accommodate new status
                                specimen_panel._set_column_widths()
                                break
                    
                    # Lock region dropdown after analysis completes
                    settings_panel = context.get_panel("carl_settings")
                    if settings_panel:
                        context.root.after(0, lambda: settings_panel.lock_region_dropdown(True))
                    
                except Exception as e:
                    context.status_bar.update(f"Error saving results for {specimen_id}: {e}", level="error")
                
                # Mark specimen as complete
                progress_dialog.complete_specimen(specimen_idx)

            # Analysis complete or cancelled
            if cancelled:
                context.status_bar.update("Analysis cancelled by user", level="warning")
            else:
                context.status_bar.update("CarlQuant analysis complete.", level="success")
        
        finally:
            # Close progress dialog
            if progress_dialog:
                progress_dialog.finish(cancelled=cancelled)

    Thread(target=worker, daemon=True).start()

