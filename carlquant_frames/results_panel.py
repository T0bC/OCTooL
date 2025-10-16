# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:48:40 2025

@author: meissnerto
"""

import tkinter as tk
from tksheet import Sheet
from utils.error_handler import handle_errors
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth, SliceResult
from carlquant_frames.data_io import DataLoader


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
        headers += ["LESION_DEPTH_MEAN", "IS_CAVITATED"]
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
            height=180
        )

        STATIC_BG_COLOR = "#2b2b2b"
        STATIC_FG_COLOR = "#dcdcdc"
        HEADER_BG_COLOR = "#3c3c3c"
        HEADER_FG_COLOR = "#ffffff"
        GRID_COLOR = "#444444"

        self.sheet.set_options(
            table_bg=STATIC_BG_COLOR,
            table_fg=STATIC_FG_COLOR,
            header_bg=HEADER_BG_COLOR,
            header_fg=HEADER_FG_COLOR,
            index_bg=HEADER_BG_COLOR,
            index_fg=HEADER_FG_COLOR,
            grid_color=GRID_COLOR,
            outline_color="#666666",
            selected_rows_bg="#44475a",
            selected_rows_fg="#ffffff"
        )


        self.sheet.enable_bindings("copy", "delete", "single_select")
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Set initial column widths
        self._set_column_widths()


    @handle_errors("resultsPanel.load_results_for")
    def load_results_for(self, specimen_id: str):
        print(f"Loading results for {specimen_id}")
        specimen = self.context.specimen_data.get(specimen_id)
        if not specimen:
            self.context.status_bar.update(f"Specimen '{specimen_id}' not found.", level="error")
            return

        if not specimen.results:
            DataLoader.load_results(specimen, self.context.region_config)

        if not specimen.results:
            self.context.status_bar.update(f"No results available for '{specimen_id}'.", level="warning")
            self.sheet.set_sheet_data([])  # Clear table
            # Unlock region dropdown when no data is loaded
            settings_panel = self.context.get_panel("carl_settings")
            if settings_panel:
                settings_panel.lock_region_dropdown(False)
            return

        # Detect region count from loaded data
        first_result = next(iter(specimen.results.values()))
        num_sound = sum(1 for r in first_result.region_stats if r.region_type == "sound")
        num_lesion = sum(1 for r in first_result.region_stats if r.region_type == "lesion")
        
        # Update context region config to match loaded data
        self.context.region_config["sound"] = num_sound
        self.context.region_config["lesion"] = num_lesion
        
        # Update settings panel dropdown to match loaded data and lock it
        settings_panel = self.context.get_panel("carl_settings")
        if settings_panel:
            settings_panel.regionVar.set(num_sound)  # Assuming sound == lesion count
            settings_panel.lock_region_dropdown(True)
        
        # Regenerate headers based on loaded data
        self.headers = self.generate_headers()
        self.sheet.headers(self.headers)
        self._set_column_widths()  # Set column widths after header change

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
            
            # IS_CAVITATED: Use "TRUE"/"FALSE" strings for consistency, blank if no data
            if result.surface and hasattr(result.surface, 'is_cavitated'):
                cavitated_value = "TRUE" if result.surface.is_cavitated else "FALSE"
            else:
                cavitated_value = ""  # Leave blank if no surface data available
            row += [cavitated_value]

            rows.append(row)

        self.sheet.set_sheet_data(rows)
        self._set_column_widths()  # Set column widths after loading data
        self.context.status_bar.update(f"Loaded {len(rows)} slice results for '{specimen_id}' ({num_sound} sound + {num_lesion} lesion regions).", level="info")

    @handle_errors("resultsPanel._set_column_widths")
    def _set_column_widths(self) -> None:
        """ Set column widths based on header length. """
        column_names = self.sheet.headers()

        for i, header in enumerate(column_names):
            width = self._calculate_column_width(header)
            self.sheet.column_width(i, width=width)

        self.sheet.refresh()

    def _calculate_column_width(self, header: str) -> int:
        """
        Calculate column width based on header length.

        Args:
            header (str): Column header text.

        Returns:
            int: Suggested column width.
        """
        base_width = 40  # Minimum width
        char_width = 7   # Approximate width per character
        padding = 20     # Extra space for clarity
        max_width = 250

        return min(max(base_width, len(header) * char_width + padding), max_width)

    @handle_errors("resultsPanel.refresh_display")
    def refresh_display(self):
        """
        Refresh the results display with updated region configuration.
        Reloads the current specimen if one is selected.
        """
        if hasattr(self.context, 'current_specimen_id') and self.context.current_specimen_id:
            self.load_results_for(self.context.current_specimen_id)
        else:
            # No specimen loaded, just update headers
            self.headers = self.generate_headers()
            self.sheet.headers(self.headers)
            self._set_column_widths()
            self.sheet.set_sheet_data([])  # Clear any existing data


