# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:48:40 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tksheet import Sheet
from utils.error_handler import handle_errors
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth, SliceResult
from carlquant_frames.data_io import DataLoader
from carlquant_frames.ascan_viewer import AScanViewer


class resultsPanel:
    @handle_errors("resultsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_results")

        self.headers = ['MEASUREMENT', 'VALUE', 'UNIT', 'CONFIDENCE']
        self.highlighted_row = None  # Track currently highlighted row
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
        
        # Bind double-click event
        self.sheet.bind("<Double-Button-1>", self._on_double_click)
        
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
        # Sort by slice_index (ascending) for consistent display
        for slice_index, result in sorted(specimen.results.items(), key=lambda x: x[0]):
            # Display slice as 1-based for humans (slice 0 becomes 1, etc.)
            row = [specimen.specimen_id, slice_index + 1]

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
    
    @handle_errors("resultsPanel._on_double_click")
    def _on_double_click(self, event):
        """
        Handle double-click event on a row.
        Highlights the row and opens the A-Scan viewer.
        """
        # Get the clicked row
        row = self.sheet.identify_row(event, exclude_index=True)
        
        if row is not None:
            # Clear previous highlighting
            if self.highlighted_row is not None:
                self.sheet.dehighlight_rows([self.highlighted_row])
            
            # Highlight the clicked row with a nice green shade
            # Using a dark green that matches the dark theme
            GREEN_HIGHLIGHT = "#2d5016"  # Dark green shade for dark theme
            self.sheet.highlight_rows(
                [row],
                bg=GREEN_HIGHLIGHT,
                fg="#ffffff"
            )
            self.highlighted_row = row
            
            # Get row data
            row_data = self.sheet.get_row_data(row)
            
            # Extract specimen_id and slice_index from row data
            specimen_id = row_data[0] if len(row_data) > 0 else None
            slice_index = row_data[1] if len(row_data) > 1 else None
            
            if specimen_id is None or slice_index is None:
                self.context.status_bar.update("Invalid row data", level="error")
                return
            
            # Get the main window and style from context
            main_window = self.root.winfo_toplevel()
            
            # Open A-Scan viewer (non-blocking)
            viewer = AScanViewer(
                main_window, 
                self.context.style, 
                self.context,
                specimen_id=specimen_id,
                slice_index=slice_index,
                row_data=row_data
            )
            viewer.show()


