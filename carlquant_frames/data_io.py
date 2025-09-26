# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 15:33:07 2025

@author: Tobias Meissner
"""

from pathlib import Path
from fnmatch import fnmatch
import re
import os
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

class DataSaver:
    @staticmethod
    def save_results(specimen_id: str, results: list, target_path: Path):
        # Future: write results to disk
        pass
