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
                    
                    # Load configuration if available
                    specimen.config = DataLoader.load_specimen_config(specimen)
                    if specimen.config:
                        # Update display values based on loaded config
                        regions_count = len(specimen.config.regions)
                        air_count = len(specimen.config.air)
                        specimen.regions = f"{regions_count} regions" if regions_count > 0 else ""
                    
                    specimen_data[specimen_id] = specimen
        return specimen_data

    @staticmethod
    def load_specimen_config(specimen: Specimen) -> SpecimenConfig:
        """Load specimen configuration from JSON file if it exists."""
        try:
            # Look for config file in any Data_ folder
            for data_folder in specimen.previous_runs:
                config_file = data_folder / f"{specimen.specimen_id}_config.json"
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    
                    # Parse the JSON data into our data structures
                    config = SpecimenConfig(specimen_id=specimen.specimen_id)
                    
                    # Load regions
                    if 'regions' in config_data:
                        for slice_idx_str, region_data in config_data['regions'].items():
                            slice_idx = int(slice_idx_str)
                            config.regions[slice_idx] = RegionConfig(
                                slice_index=slice_idx,
                                start_point=tuple(region_data['start_point']),
                                end_point=tuple(region_data['end_point'])
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
                    
                    return config
            
            return None
        except Exception:
            return None

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
            row += [result.lesion_depth.mean_depth]
            ws_summary.append(row)

        # === Sheet 2: Region Pixels ===
        ws_pixels = wb.create_sheet("Region Pixels")
        pixel_headers = ["SLICE", "REGION_TYPE", "REGION_INDEX"]
        pixel_headers += [f"PIXEL_{i+1}" for i in range(100)]  # Assuming 100 pixels per region
        ws_pixels.append(pixel_headers)

        for slice_index, result in specimen.results.items():
            for idx, region in enumerate(result.region_stats):
                row = [slice_index, region.region_type, idx + 1]
                row += region.pixel_values
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
            for x, y in result.lesion_depth.depth_points:
                ws_surface.append([slice_index, "lesion_depth", x, y])

        # === Save to disk ===
        operator = getattr(specimen, "operator", "OP")
        measurement = getattr(specimen, "measurement", 1)
        save_folder = specimen.source / f"Data_{operator}_{measurement}"
        save_folder.mkdir(exist_ok=True)

        target_file = save_folder / f"{specimen.specimen_id}_results.xlsx"
        wb.save(target_file)

    @staticmethod
    def save_specimen_config(specimen: Specimen):
        """Save specimen configuration (REGIONS and AIR) to JSON file."""
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
                "start_point": list(region_config.start_point),
                "end_point": list(region_config.end_point)
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
        
        # Save to JSON file
        config_file = save_folder / f"{specimen.specimen_id}_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

    @staticmethod
    def update_specimen_region(specimen: Specimen, slice_index: int, start_point: tuple, end_point: tuple):
        """Update region configuration for a specific slice."""
        if not specimen.config:
            specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
        
        specimen.config.regions[slice_index] = RegionConfig(
            slice_index=slice_index,
            start_point=start_point,
            end_point=end_point
        )
        
        # Auto-save configuration
        DataSaver.save_specimen_config(specimen)

    @staticmethod
    def update_specimen_air(specimen: Specimen, slice_index: int, point1: tuple, point2: tuple = None):
        """Update AIR configuration for a specific slice."""
        if not specimen.config:
            specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
        
        specimen.config.air[slice_index] = AirConfig(
            slice_index=slice_index,
            point1=point1,
            point2=point2
        )
        
        # Auto-save configuration
        DataSaver.save_specimen_config(specimen)


