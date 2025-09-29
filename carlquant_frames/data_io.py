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
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from carlquant_frames.specimen_model import Specimen


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

                if image_files:
                    specimen_id = subdir.name
                    specimen_data[specimen_id] = Specimen(
                        specimen_id=subdir.name,
                        source=subdir,
                        images=image_files,
                        slices=len(image_files),
                        regions="",
                        status="new",
                        date=subdir.stat().st_mtime
                    )

        return specimen_data


    @staticmethod
    def load_results(specimen_id: str, source_path: Path):
        # Future: load CSV, JSON, or other result formats
        return []

from carlquant_frames.specimen_model import Specimen, SliceResult, RegionStats, Surface, LesionDepth

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


