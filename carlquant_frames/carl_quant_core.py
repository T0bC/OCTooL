# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 11:05:22 2025

@author: Tobias Meissner
"""

from time import sleep
from threading import Thread
from carlquant_frames.data_io import DataSaver
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth
import random
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Optional
from sklearn.cluster import DBSCAN
from scipy.interpolate import splrep, splev


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
# MAIN ANALYSIS FUNCTION
# =============================================================================

def run_carl_quant(context):
    def worker():
        for specimen_id, specimen in context.specimen_data.items():

            # user choice to reanalyze a specemin
            choice = getattr(specimen, "analysis_choice", "new")
            if choice == "skip":
                context.status_bar.update(f"Skipped specimen {specimen_id} (user choice)", level="info")
                continue
            elif choice == "overwrite":
                specimen.measurement = context.analysis_metadata.get("measurement", 1)
            elif choice == "new":
                # You could auto-increment or prompt again, but for now:
                specimen.measurement = context.analysis_metadata.get("measurement", 1)

            specimen.operator = context.analysis_metadata.get("operator", "OP")

            # Proceed with slice processing
            for slice_index in range(specimen.slices):
                # Load image for this slice
                image_path = specimen.images[slice_index]
                img = Image.open(image_path).convert('L')
                image_array = np.array(img)
                
                # Get configuration for this slice
                region_config = None
                air_config = None
                if specimen.config:
                    region_config = specimen.config.regions.get(slice_index)
                    air_config = specimen.config.air.get(slice_index)
                
                # Detect surface using real algorithm
                surface = detect_surface(image_array, air_config, region_config)
                
                # TODO: Implement region extraction and lesion depth calculation
                # For now, use dummy data
                num_sound = context.region_config.get("sound", 3)
                num_lesion = context.region_config.get("lesion", 3)

                region_stats = [
                    RegionStats("sound", [random.randint(95, 105) for _ in range(100)],
                                mean=100.0, median=100.0, sd=2.0, se=1.0)
                    for _ in range(num_sound)
                ] + [
                    RegionStats("lesion", [random.randint(75, 85) for _ in range(100)],
                                mean=80.0, median=80.0, sd=2.0, se=1.0)
                    for _ in range(num_lesion)
                ]

                lesion_depth = LesionDepth(
                    depth_points=[(x, 20 + x % 2) for x in range(100)],
                    mean_depth=20.5,
                    median_depth=20.0,
                    sd=1.0,
                    se=0.5
                )

                if hasattr(context, "result_lock"):
                    with context.result_lock:
                        DataSaver.store_slice_result(specimen, slice_index, region_stats, surface, lesion_depth)
                else:
                    DataSaver.store_slice_result(specimen, slice_index, region_stats, surface, lesion_depth)

                context.status_bar.update(f"Processed slice {slice_index + 1} of {specimen_id}", level="success")

            # Save results after all slices are processed
            # Inject metadata into specimen
            specimen.operator = context.analysis_metadata.get("operator", "OP")
            specimen.measurement = context.analysis_metadata.get("measurement", 1)

            # Save results
            DataSaver.save_results(specimen)

            try:
                DataSaver.save_results(specimen)
                context.status_bar.update(f"Saved results for {specimen_id}", level="info")
            except Exception as e:
                context.status_bar.update(f"Error saving results for {specimen_id}: {e}", level="error")

        context.status_bar.update("CarlQuant analysis complete.", level="success")

    Thread(target=worker, daemon=True).start()

