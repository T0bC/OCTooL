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
    1. Calculate IQR from AIR region (if provided)
    2. For each vertical pixel column (A-Scan) within specimen boundaries, find first pixel > IQR * 1.5
    3. Store raw surface points
    4. (Future) Apply smoothing/filtering and curve fitting
    
    Args:
        image: 2D numpy array (grayscale image)
        air_config: AIR configuration with threshold region
        region_config: Region configuration with specimen boundaries
    
    Returns:
        Surface object with raw_points and fitted_curves
    """
    height, width = image.shape
    
    # Step 1: Calculate threshold based on AIR region
    if air_config and air_config.point2:
        # Extract AIR region
        x1, y1 = air_config.point1
        x2, y2 = air_config.point2
        
        # Ensure coordinates are within image bounds and properly ordered
        x1, x2 = max(0, min(x1, x2)), min(width, max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(height, max(y1, y2))
        
        air_region = image[y1:y2, x1:x2]
        
        # Calculate statistics from AIR region
        air_mean = np.mean(air_region)
        air_std = np.std(air_region)
        air_max = np.max(air_region)
        air_q95 = np.percentile(air_region, 95)
        
        # Threshold: Use maximum value from AIR region
        # Surface should be significantly brighter than air
        # Use 95th percentile to be robust against outliers in AIR
        threshold = air_q95 *1.5
        
        print(f"AIR region: ({x1},{y1}) to ({x2},{y2})")
        print(f"AIR mean={air_mean:.2f}, std={air_std:.2f}, max={air_max:.2f}, Q95={air_q95:.2f}")
        print(f"Threshold={threshold:.2f}")
    else:
        # Fallback: use image statistics if no AIR config
        threshold = np.percentile(image, 50)
        print(f"No AIR config, using fallback threshold={threshold:.2f}")
    
    # Step 2: Determine search boundaries (specimen start to end)
    if region_config:
        x_start = region_config.specimen_start[0]
        x_end = region_config.tooth_end[0]
        print(f"Searching for surface from x={x_start} to x={x_end}")
    else:
        # No region config, search entire width
        x_start = 0
        x_end = width
        print(f"No region config, searching entire width")
    
    # Step 3: For each column (A-Scan) within boundaries, find first pixel above threshold
    # Skip first 25 pixels (typically white/black band)
    imageOffsett = 25
    raw_points = []
    for x in range(x_start, x_end):
        column = image[imageOffsett:, x]  # Skip first 25 pixels
        
        # Find first pixel that exceeds threshold
        above_threshold = np.where(column > threshold)[0]
        
        if len(above_threshold) > 0:
            y = above_threshold[0] + imageOffsett  # First pixel above threshold (add 25 offset back)
            raw_points.append((x, y))
        else:
            # No pixel found above threshold in this column
            # Skip this column or use a default value
            pass
    
    print(f"Detected {len(raw_points)} surface points out of {x_end - x_start} columns")
    
    # Step 4: Placeholder for curve fitting (to be implemented later)
    fitted_curves = {}
    
    return Surface(
        raw_points=raw_points,
        fitted_curves=fitted_curves
    )


def calculate_air_threshold(image: np.ndarray, air_config: AirConfig) -> float:
    """
    Calculate intensity threshold based on AIR region.
    
    Args:
        image: 2D numpy array (grayscale image)
        air_config: AIR configuration with rectangular region
    
    Returns:
        float: Threshold value for air/tissue boundary
    """
    if not air_config or not air_config.point2:
        # Default threshold if no AIR config
        return np.mean(image) * 0.5
    
    # Extract AIR region
    x1, y1 = air_config.point1
    x2, y2 = air_config.point2
    
    # Ensure coordinates are within image bounds
    x1, x2 = max(0, min(x1, x2)), min(image.shape[1], max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(image.shape[0], max(y1, y2))
    
    air_region = image[y1:y2, x1:x2]
    
    # TODO: Implement threshold calculation (mean + N*std, percentile, etc.)
    threshold = np.mean(air_region) + 2 * np.std(air_region)
    
    return threshold


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
# CLUSTERING ANALYSIS
# =============================================================================

def perform_clustering(pixel_values: List[int], n_clusters: int = 2) -> Dict:
    """
    Perform clustering analysis on pixel values.
    
    This can be used to automatically identify sound vs lesion tissue
    or to segment within regions.
    
    Args:
        pixel_values: List of pixel intensity values
        n_clusters: Number of clusters to identify
    
    Returns:
        dict: Clustering results with labels and centroids
    """
    # TODO: Implement clustering (k-means, GMM, etc.)
    # Placeholder
    return {
        "labels": [],
        "centroids": [],
        "n_clusters": n_clusters
    }


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
