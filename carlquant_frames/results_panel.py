# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:48:40 2025

@author: meissnerto
"""

import tkinter as tk
from tksheet import Sheet
from utils.error_handler import handle_errors
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth, SliceResult


class resultsPanel:
    @handle_errors("resultsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_results")

        self.headers = ['MEASUREMENT', 'VALUE', 'UNIT', 'CONFIDENCE']
        self._setup_sheet()

    def generate_headers(self):
        num_sound = self.context.region_config.get("sound", 3)
        num_lesion = self.context.region_config.get("lesion", 3)

        headers = ["SPECIMEN_ID", "SLICE"]
        headers += [f"SOUND_{i+1}" for i in range(num_sound)]
        headers += [f"LESION_{i+1}" for i in range(num_lesion)]
        headers += ["LESION_DEPTH_MEAN"]
        return headers


    def _setup_sheet(self):
        self.headers = self.generate_headers()
        self.sheet = Sheet(
            self.frame,
            headers=self.headers,
            show_table=True,
            show_row_index=True,
            show_header=True,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            width=400,
            height=180
        )
        self.sheet.enable_bindings("copy", "delete", "single_select")
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)


    @handle_errors("resultsPanel.load_results_for")
    def load_results_for(self, specimen_id: str):
        print(f"Loading results for {specimen_id}")
        specimen = self.context.specimen_data.get(specimen_id)
        if not specimen:
            self.context.status_bar.update(f"Specimen '{specimen_id}' not found.", level="error")
            return

        if not specimen.results:
            self.context.status_bar.update(f"No results available for '{specimen_id}'.", level="warning")
            self.sheet.set_sheet_data([])  # Clear table
            return

        # Regenerate headers in case region config changed
        self.headers = self.generate_headers()
        self.sheet.headers(self.headers)

        # Populate results table with summary
        rows = []
        for slice_index, result in specimen.results.items():
            row = [specimen.specimen_id, slice_index]

            # Sound region medians
            sound_regions = [r for r in result.region_stats if r.region_type == "sound"]
            row += [f"{r.median:.2f}" for r in sound_regions]

            # Lesion region medians
            lesion_regions = [r for r in result.region_stats if r.region_type == "lesion"]
            row += [f"{r.median:.2f}" for r in lesion_regions]

            # Lesion depth mean
            row += [f"{result.lesion_depth.mean_depth:.2f}"]

            rows.append(row)

        self.sheet.set_sheet_data(rows)
        self.context.status_bar.update(f"Loaded {len(rows)} slice results for '{specimen_id}'.", level="info")


