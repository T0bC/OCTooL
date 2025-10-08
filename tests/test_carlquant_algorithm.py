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

# Add parent directory to path so we can import from carlquant_frames
sys.path.insert(0, str(Path(__file__).parent.parent))

from carlquant_frames.specimen_model import (
    RegionStats, Surface, LesionDepth, RegionConfig, AirConfig
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
    
    # Step 5: Placeholder for curve fitting (to be implemented later)
    fitted_curves = {}
    
    return Surface(
        raw_points=filtered_points,
        fitted_curves=fitted_curves,
        cluster_labels=cluster_labels
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

# =============================================================================
# REGION EXTRACTION
# =============================================================================

def extract_regions(image: np.ndarray, 
                   surface: Surface, 
                   region_config: RegionConfig,
                   num_sound_regions: int = 3,
                   num_lesion_regions: int = 3) -> List[RegionStats]:
    """
    Extract pixel values from sound and lesion regions.
    
    Algorithm steps (to be implemented):
    1. Define vertical boundaries from region_config (4 points)
    2. Divide sound region (specimen_start to lesion_start) into num_sound_regions
    3. Divide lesion region (lesion_start to lesion_end) into num_lesion_regions
    4. Extract pixel values from each region (below surface)
    5. Calculate statistics for each region
    
    Args:
        image: 2D numpy array (grayscale image)
        surface: Detected surface
        region_config: Region boundaries (4 points: specimen_start, lesion_start, lesion_end, tooth_end)
        num_sound_regions: Number of sound regions to extract
        num_lesion_regions: Number of lesion regions to extract
    
    Returns:
        List of RegionStats (sound regions first, then lesion regions)
    """
    height, width = image.shape
    
    # Extract boundary x-coordinates from 4-point configuration
    specimen_start_x, _ = region_config.specimen_start
    lesion_start_x, _ = region_config.lesion_start
    lesion_end_x, _ = region_config.lesion_end
    tooth_end_x, _ = region_config.tooth_end
    
    region_stats = []
    
    # TODO: Implement region extraction algorithm
    # Placeholder: Generate dummy regions
    
    # Sound regions (left of start_x)
    for i in range(num_sound_regions):
        pixel_values = list(np.random.randint(95, 105, size=100))  # Dummy data
        region_stats.append(RegionStats(
            region_type="sound",
            pixel_values=pixel_values,
            mean=np.mean(pixel_values),
            median=np.median(pixel_values),
            sd=np.std(pixel_values),
            se=np.std(pixel_values) / np.sqrt(len(pixel_values))
        ))
    
    # Lesion regions (between start_x and end_x)
    for i in range(num_lesion_regions):
        pixel_values = list(np.random.randint(75, 85, size=100))  # Dummy data
        region_stats.append(RegionStats(
            region_type="lesion",
            pixel_values=pixel_values,
            mean=np.mean(pixel_values),
            median=np.median(pixel_values),
            sd=np.std(pixel_values),
            se=np.std(pixel_values) / np.sqrt(len(pixel_values))
        ))
    
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

def calculate_lesion_depth(surface: Surface, 
                          region_config: RegionConfig,
                          image: np.ndarray) -> LesionDepth:
    """
    Calculate lesion depth within the specified boundary.
    
    Algorithm steps (to be implemented):
    1. Identify lesion bottom boundary (intensity-based or manual)
    2. Calculate vertical distance from surface to lesion bottom
    3. Compute statistics (mean, median, std, se)
    
    Args:
        surface: Detected surface
        region_config: Region configuration with lesion boundaries
        image: 2D numpy array (grayscale image)
    
    Returns:
        LesionDepth object with depth measurements
    """
    # Extract lesion boundaries from region config
    start_x, _ = region_config.lesion_start
    end_x, _ = region_config.lesion_end
    
    # TODO: Implement lesion depth calculation
    # Placeholder: Generate dummy depth points
    depth_points = []
    for x in range(start_x, end_x, 10):
        depth = 20 + int(5 * np.sin(x / 30))  # Dummy varying depth
        depth_points.append((x, depth))
    
    depths = [d for _, d in depth_points]
    
    return LesionDepth(
        depth_points=depth_points,
        mean_depth=np.mean(depths),
        median_depth=np.median(depths),
        sd=np.std(depths),
        se=np.std(depths) / np.sqrt(len(depths))
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
                 num_lesion_regions: int = 3) -> Tuple[List[RegionStats], Surface, LesionDepth]:
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
    lesion_depth = calculate_lesion_depth(surface, region_config, image_array)
    
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
