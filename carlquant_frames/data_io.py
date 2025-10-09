# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 15:33:07 2025

@author: meissnerto
"""

from pathlib import Path
from fnmatch import fnmatch
from datetime import datetime
import re
import os
import json
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook
from carlquant_frames.specimen_model import (
    Specimen, SliceResult, RegionStats, LesionDepth, Surface,
    SpecimenConfig, RegionConfig, AirConfig
)



IMAGE_EXTENSIONS = ['*.jpg', '*.png', '*.tif', '*.tiff']

def natural_key(path):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', path.name)]

class DataLoader:
    @staticmethod
    def find_image_stacks(root_folder: Path) -> dict[str, Specimen]:
        specimen_data = {}
        for subdir in root_folder.rglob("*"):
            if subdir.is_dir():
                image_files = sorted([
                    f for f in subdir.iterdir()
                    if f.is_file() and any(fnmatch(f.name.lower(), ext) for ext in IMAGE_EXTENSIONS)
                ], key=natural_key)

                data_folders = [f for f in subdir.iterdir() if f.is_dir() and f.name.startswith("Data_")]

                if image_files:
                    specimen_id = subdir.name
                    specimen = Specimen(
                        specimen_id=subdir.name,
                        source=subdir,
                        images=image_files,
                        slices=len(image_files),
                        regions="",
                        status="new",
                        date=subdir.stat().st_mtime,
                        previous_runs=data_folders
                    )
                    
                    # Don't load configuration here - it will be loaded after metadata is set
                    # This ensures we load from the correct Data_{operator}_{measurement} folder
                    
                    specimen_data[specimen_id] = specimen
        return specimen_data

    @staticmethod
    def load_specimen_config(specimen: Specimen) -> SpecimenConfig:
        """Load specimen configuration from JSON file if it exists.
        
        Also loads computed annotations (surface, lesion_depth, extraction_regions) if available.
        Prioritizes loading from Data_{operator}_{measurement} folder if specimen has metadata.
        """
        try:
            # If specimen has operator/measurement metadata, look for specific folder first
            if hasattr(specimen, 'operator') and hasattr(specimen, 'measurement'):
                target_folder = specimen.source / f"Data_{specimen.operator}_{specimen.measurement}"
                if target_folder.exists():
                    config_file = target_folder / f"{specimen.specimen_id}_config.json"
                    if config_file.exists():
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        return DataLoader._parse_config_data(specimen, config_data)
            
            # Fallback: Look for config file in any Data_ folder (legacy behavior)
            for data_folder in specimen.previous_runs:
                config_file = data_folder / f"{specimen.specimen_id}_config.json"
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    return DataLoader._parse_config_data(specimen, config_data)
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def _parse_config_data(specimen: Specimen, config_data: dict) -> SpecimenConfig:
        """Parse config data from JSON into SpecimenConfig object.
        
        Args:
            specimen: Specimen object
            config_data: Dictionary loaded from JSON
        
        Returns:
            SpecimenConfig object
        """
        # Parse the JSON data into our data structures
        config = SpecimenConfig(specimen_id=specimen.specimen_id)
        
        # Load regions
        if 'regions' in config_data:
            for slice_idx_str, region_data in config_data['regions'].items():
                slice_idx = int(slice_idx_str)
                # Support both old (2-point) and new (4-point) format
                if 'specimen_start' in region_data:
                    # New 4-point format
                    config.regions[slice_idx] = RegionConfig(
                        slice_index=slice_idx,
                        specimen_start=tuple(region_data['specimen_start']),
                        lesion_start=tuple(region_data['lesion_start']),
                        lesion_end=tuple(region_data['lesion_end']),
                        tooth_end=tuple(region_data['tooth_end'])
                    )
                else:
                    # Old 2-point format - convert to 4-point
                    # Assume: specimen_start = start_point, lesion_start = start_point,
                    #         lesion_end = end_point, tooth_end = end_point
                    start_pt = tuple(region_data['start_point'])
                    end_pt = tuple(region_data['end_point'])
                    config.regions[slice_idx] = RegionConfig(
                        slice_index=slice_idx,
                        specimen_start=start_pt,
                        lesion_start=start_pt,
                        lesion_end=end_pt,
                        tooth_end=end_pt
                    )
        
        # Load air configurations
        if 'air' in config_data:
            for slice_idx_str, air_data in config_data['air'].items():
                slice_idx = int(slice_idx_str)
                point2 = tuple(air_data['point2']) if air_data.get('point2') else None
                config.air[slice_idx] = AirConfig(
                    slice_index=slice_idx,
                    point1=tuple(air_data['point1']),
                    point2=point2
                )
        
        # Load computed annotations if available
        if 'annotations' in config_data:
            DataLoader._load_annotations_into_results(specimen, config_data['annotations'])
        
        return config
    
    @staticmethod
    def _load_annotations_into_results(specimen: Specimen, annotations_data: dict):
        """Load computed annotations from JSON into specimen.results.
        
        Args:
            specimen: Specimen object to populate
            annotations_data: Dictionary of annotations keyed by slice index
        """
        for slice_idx_str, slice_annotations in annotations_data.items():
            slice_idx = int(slice_idx_str)
            
            # Initialize result containers
            surface = None
            lesion_depth = None
            region_stats = []
            
            # Load surface detection results
            if 'surface' in slice_annotations:
                surface_data = slice_annotations['surface']
                raw_points = [tuple(pt) for pt in surface_data.get('raw_points', [])]
                fitted_curves = {}
                for curve_name, points in surface_data.get('fitted_curves', {}).items():
                    fitted_curves[curve_name] = [tuple(pt) for pt in points]
                
                surface = Surface(
                    raw_points=raw_points,
                    fitted_curves=fitted_curves,
                    is_cavitated=surface_data.get('is_cavitated', False),
                    cavitation_depth=surface_data.get('cavitation_depth', 0.0)
                )
            
            # Load lesion depth results
            if 'lesion_depth' in slice_annotations:
                ld_data = slice_annotations['lesion_depth']
                depth_points = [tuple(pt) for pt in ld_data.get('depth_points', [])]
                smoothed_points = None
                if 'smoothed_depth_points' in ld_data:
                    smoothed_points = [tuple(pt) for pt in ld_data['smoothed_depth_points']]
                
                lesion_depth = LesionDepth(
                    depth_points=depth_points,
                    mean_depth=ld_data.get('mean_depth', 0.0),
                    median_depth=ld_data.get('median_depth', 0.0),
                    sd=ld_data.get('sd', 0.0),
                    se=ld_data.get('se', 0.0),
                    smoothed_depth_points=smoothed_points
                )
            
            # Load extraction region bounds and statistics
            if 'extraction_regions' in slice_annotations:
                for region_data in slice_annotations['extraction_regions']:
                    # Parse bounds
                    bounds = None
                    if 'bounds' in region_data and region_data['bounds']:
                        bounds_data = region_data['bounds']
                        if isinstance(bounds_data[0], list):
                            # Rotated corners
                            bounds = tuple(tuple(pt) for pt in bounds_data)
                        else:
                            # Simple bbox
                            bounds = tuple(bounds_data)
                    
                    region_stats.append(RegionStats(
                        region_type=region_data.get('region_type', 'sound'),
                        pixel_values=[],  # Not saved in annotations (too large)
                        mean=region_data.get('mean', 0.0),
                        median=region_data.get('median', 0.0),
                        sd=region_data.get('sd', 0.0),
                        se=region_data.get('se', 0.0),
                        region_index=region_data.get('region_index', 0),
                        bounds=bounds if bounds else (0, 0, 0, 0),
                        rotation_angle=region_data.get('rotation_angle', 0.0)
                    ))
            
            # Store the slice result if we have any data
            if surface or lesion_depth or region_stats:
                specimen.results[slice_idx] = SliceResult(
                    slice_index=slice_idx,
                    region_stats=region_stats,
                    surface=surface if surface else Surface([], {}),
                    lesion_depth=lesion_depth if lesion_depth else LesionDepth([], 0, 0, 0, 0)
                )

    @staticmethod
    def load_results(specimen: Specimen, region_config: dict):
        if not specimen.previous_runs:
            return

        try:
            latest_folder = max(specimen.previous_runs, key=lambda p: p.stat().st_mtime)
            result_file = latest_folder / f"{specimen.specimen_id}_results.xlsx"
            if not result_file.exists():
                return

            wb = load_workbook(result_file)
            if "Summary" not in wb.sheetnames:
                return

            ws = wb["Summary"]
            sound_count = region_config.get("sound", 3)
            lesion_count = region_config.get("lesion", 3)
            expected_columns = 1 + sound_count + lesion_count + 1  # slice + regions + depth

            specimen.results.clear()
            for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                if not row or len(row) < expected_columns:
                    continue

                try:
                    slice_index = row[0] if isinstance(row[0], int) else i
                    sound_medians = row[1 : 1 + sound_count]
                    lesion_medians = row[1 + sound_count : 1 + sound_count + lesion_count]
                    lesion_depth_mean = row[1 + sound_count + lesion_count]

                    region_stats = [
                        RegionStats("sound", [], mean=0, median=float(m), sd=0, se=0)
                        for m in sound_medians
                    ] + [
                        RegionStats("lesion", [], mean=0, median=float(m), sd=0, se=0)
                        for m in lesion_medians
                    ]

                    specimen.results[slice_index] = SliceResult(
                        slice_index=slice_index,
                        region_stats=region_stats,
                        surface=Surface([], {}),
                        lesion_depth=LesionDepth([], mean_depth=lesion_depth_mean, median_depth=0, sd=0, se=0)
                    )

                except Exception:
                    continue

        except Exception:
            pass


class DataSaver:
    @staticmethod
    def store_slice_result(specimen: Specimen, slice_index: int,
                           region_stats: list[RegionStats],
                           surface: Surface,
                           lesion_depth: LesionDepth):
        specimen.results[slice_index] = SliceResult(
            slice_index=slice_index,
            region_stats=region_stats,
            surface=surface,
            lesion_depth=lesion_depth
        )

    @staticmethod
    def save_results(specimen: Specimen):
        wb = Workbook()

        # === Sheet 1: Summary ===
        ws_summary = wb.active
        ws_summary.title = "Summary"

        num_sound = sum(1 for r in specimen.results[0].region_stats if r.region_type == "sound")
        num_lesion = sum(1 for r in specimen.results[0].region_stats if r.region_type == "lesion")

        headers = ["SLICE"]
        headers += [f"SOUND_{i+1}_MEDIAN" for i in range(num_sound)]
        headers += [f"LESION_{i+1}_MEDIAN" for i in range(num_lesion)]
        headers += ["LESION_DEPTH_MEAN"]
        ws_summary.append(headers)

        for slice_index, result in specimen.results.items():
            row = [slice_index]
            row += [r.median for r in result.region_stats if r.region_type == "sound"]
            row += [r.median for r in result.region_stats if r.region_type == "lesion"]
            row += [result.lesion_depth.mean_depth if result.lesion_depth else 0]
            ws_summary.append(row)

        # === Sheet 2: Region Pixels ===
        ws_pixels = wb.create_sheet("Region Pixels")
        
        # Create headers: SLICE, PIXEL_INDEX, SOUND_1..SOUND_N, LESION_1..LESION_N
        pixel_headers = ["SLICE", "PIXEL_INDEX"]
        pixel_headers += [f"SOUND_{i+1}" for i in range(num_sound)]
        pixel_headers += [f"LESION_{i+1}" for i in range(num_lesion)]
        ws_pixels.append(pixel_headers)
        
        # Transpose data: one row per pixel instead of one row per region
        for slice_index, result in specimen.results.items():
            # Get all regions for this slice
            sound_regions = [r for r in result.region_stats if r.region_type == "sound"]
            lesion_regions = [r for r in result.region_stats if r.region_type == "lesion"]
            
            # Determine max pixel count across all regions
            max_pixels = max(
                max((len(r.pixel_values) for r in sound_regions), default=0),
                max((len(r.pixel_values) for r in lesion_regions), default=0)
            )
            
            # Write one row per pixel
            for pixel_idx in range(max_pixels):
                row = [slice_index, pixel_idx + 1]
                
                # Add sound region values for this pixel
                for sound_region in sound_regions:
                    if pixel_idx < len(sound_region.pixel_values):
                        row.append(sound_region.pixel_values[pixel_idx])
                    else:
                        row.append(None)  # Empty cell if region has fewer pixels
                
                # Add lesion region values for this pixel
                for lesion_region in lesion_regions:
                    if pixel_idx < len(lesion_region.pixel_values):
                        row.append(lesion_region.pixel_values[pixel_idx])
                    else:
                        row.append(None)  # Empty cell if region has fewer pixels
                
                ws_pixels.append(row)

        # === Sheet 3: Surface & Depth ===
        ws_surface = wb.create_sheet("Surface & Depth")
        ws_surface.append(["SLICE", "TYPE", "X", "Y"])

        for slice_index, result in specimen.results.items():
            for x, y in result.surface.raw_points:
                ws_surface.append([slice_index, "raw_surface", x, y])
            for curve_name, points in result.surface.fitted_curves.items():
                for x, y in points:
                    ws_surface.append([slice_index, f"curve_{curve_name}", x, y])
            if result.lesion_depth and result.lesion_depth.depth_points:
                for x, y in result.lesion_depth.depth_points:
                    ws_surface.append([slice_index, "lesion_depth", x, y])

        # === Save to disk ===
        operator = getattr(specimen, "operator", "OP")
        measurement = getattr(specimen, "measurement", 1)
        save_folder = specimen.source / f"Data_{operator}_{measurement}"
        save_folder.mkdir(exist_ok=True)

        target_file = save_folder / f"{specimen.specimen_id}_results.xlsx"
        wb.save(target_file)
        
        # Save annotations to config JSON (includes surface, lesion_depth, extraction_regions)
        DataSaver.save_specimen_config(specimen, include_annotations=True)

    @staticmethod
    def save_specimen_config(specimen: Specimen, include_annotations: bool = False):
        """Save specimen configuration (REGIONS, AIR, and optionally computed annotations) to JSON file.
        
        Args:
            specimen: Specimen object to save
            include_annotations: If True, save computed annotations (surface, lesion_depth, extraction_regions)
        """
        if not specimen.config:
            return
        
        # Create save folder if it doesn't exist
        operator = getattr(specimen, "operator", "OP")
        measurement = getattr(specimen, "measurement", 1)
        save_folder = specimen.source / f"Data_{operator}_{measurement}"
        save_folder.mkdir(exist_ok=True)
        
        # Prepare data for JSON serialization
        config_data = {
            "specimen_id": specimen.config.specimen_id,
            "regions": {},
            "air": {}
        }
        
        # Convert regions to JSON-serializable format
        for slice_idx, region_config in specimen.config.regions.items():
            config_data["regions"][str(slice_idx)] = {
                "slice_index": region_config.slice_index,
                "specimen_start": list(region_config.specimen_start),
                "lesion_start": list(region_config.lesion_start),
                "lesion_end": list(region_config.lesion_end),
                "tooth_end": list(region_config.tooth_end)
            }
        
        # Convert air configurations to JSON-serializable format
        for slice_idx, air_config in specimen.config.air.items():
            air_data = {
                "slice_index": air_config.slice_index,
                "point1": list(air_config.point1)
            }
            if air_config.point2:
                air_data["point2"] = list(air_config.point2)
            config_data["air"][str(slice_idx)] = air_data
        
        # Save computed annotations if requested and available
        if include_annotations and hasattr(specimen, 'results') and specimen.results:
            config_data["annotations"] = {}
            
            for slice_idx, result in specimen.results.items():
                slice_annotations = {}
                
                # Save surface detection results
                if result.surface:
                    surface_data = {
                        "raw_points": [[int(x), int(y)] for x, y in result.surface.raw_points],
                        "fitted_curves": {}
                    }
                    for curve_name, points in result.surface.fitted_curves.items():
                        surface_data["fitted_curves"][curve_name] = [[int(x), int(y)] for x, y in points]
                    
                    # Save cavitation detection if available
                    if hasattr(result.surface, 'is_cavitated'):
                        surface_data["is_cavitated"] = bool(result.surface.is_cavitated)
                        surface_data["cavitation_depth"] = float(result.surface.cavitation_depth)
                    
                    slice_annotations["surface"] = surface_data
                
                # Save lesion depth results
                if result.lesion_depth:
                    lesion_depth_data = {
                        "depth_points": [[int(x), int(y)] for x, y in result.lesion_depth.depth_points],
                        "mean_depth": float(result.lesion_depth.mean_depth),
                        "median_depth": float(result.lesion_depth.median_depth),
                        "sd": float(result.lesion_depth.sd),
                        "se": float(result.lesion_depth.se)
                    }
                    
                    # Save smoothed depth points if available
                    if hasattr(result.lesion_depth, 'smoothed_depth_points') and result.lesion_depth.smoothed_depth_points:
                        lesion_depth_data["smoothed_depth_points"] = [[int(x), int(y)] for x, y in result.lesion_depth.smoothed_depth_points]
                    
                    slice_annotations["lesion_depth"] = lesion_depth_data
                
                # Save extraction region bounds and statistics
                if result.region_stats:
                    regions_data = []
                    for stats in result.region_stats:
                        region_data = {
                            "region_type": str(stats.region_type),
                            "region_index": int(stats.region_index),
                            "mean": float(stats.mean),
                            "median": float(stats.median),
                            "sd": float(stats.sd),
                            "se": float(stats.se),
                            "rotation_angle": float(stats.rotation_angle)
                        }
                        
                        # Save bounds (can be 4 corner points or simple bbox)
                        if stats.bounds:
                            if isinstance(stats.bounds[0], tuple):
                                # Rotated corners
                                region_data["bounds"] = [[int(x), int(y)] for x, y in stats.bounds]
                            else:
                                # Simple bbox
                                region_data["bounds"] = [int(v) for v in stats.bounds]
                        
                        regions_data.append(region_data)
                    
                    slice_annotations["extraction_regions"] = regions_data
                
                if slice_annotations:
                    config_data["annotations"][str(slice_idx)] = slice_annotations
        
        # Save to JSON file
        config_file = save_folder / f"{specimen.specimen_id}_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

    @staticmethod
    def update_specimen_region(specimen: Specimen, slice_index: int, 
                              specimen_start: tuple, lesion_start: tuple,
                              lesion_end: tuple, tooth_end: tuple,
                              context=None):
        """Update region configuration for a specific slice (4 points).
        
        Args:
            specimen: Specimen to update
            slice_index: Slice index
            specimen_start: Specimen start point
            lesion_start: Lesion start point
            lesion_end: Lesion end point
            tooth_end: Tooth end point
            context: Application context (for metadata)
        """
        if not specimen.config:
            specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
        
        specimen.config.regions[slice_index] = RegionConfig(
            slice_index=slice_index,
            specimen_start=specimen_start,
            lesion_start=lesion_start,
            lesion_end=lesion_end,
            tooth_end=tooth_end
        )
        
        # Store metadata in specimen if available from context
        if context:
            metadata = getattr(context, "analysis_metadata", {})
            operator = metadata.get("operator", "OP")
            measurement = metadata.get("measurement", 1)
            specimen.operator = operator
            specimen.measurement = measurement
        
        # Auto-save configuration
        DataSaver.save_specimen_config(specimen)

    @staticmethod
    def update_specimen_air(specimen: Specimen, slice_index: int, point1: tuple, point2: tuple = None, context=None):
        """Update AIR configuration for a specific slice.
        
        Args:
            specimen: Specimen to update
            slice_index: Slice index
            point1: First point
            point2: Second point
            context: Application context (for metadata)
        """
        if not specimen.config:
            specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
        
        specimen.config.air[slice_index] = AirConfig(
            slice_index=slice_index,
            point1=point1,
            point2=point2
        )
        
        # Store metadata in specimen if available from context
        if context:
            metadata = getattr(context, "analysis_metadata", {})
            operator = metadata.get("operator", "OP")
            measurement = metadata.get("measurement", 1)
            specimen.operator = operator
            specimen.measurement = measurement
        
        # Auto-save configuration
        DataSaver.save_specimen_config(specimen)


