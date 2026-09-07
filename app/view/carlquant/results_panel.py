# -*- coding: utf-8 -*-
"""
CarlQuant Results Panel.

Spreadsheet panel (tksheet) showing per-slice analysis results: sound and lesion
region statistics, lesion depth, and cavitation flag. Supports A-Scan viewer
launch and row highlighting for navigation.

Key contents:
- resultsPanel: tksheet grid with dynamic headers based on region counts.
- generate_headers: Builds column headers from the current sound/lesion config.
- _setup_sheet: Initialises the sheet widget and binds selection events.
- highlight_row: Colour-codes rows for navigation and A-Scan viewer state.
- AScanViewer integration: Opens the intensity-profile popup for a selected row.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""


import tkinter as tk
from tkinter import ttk
from tksheet import Sheet
from app.view.shared.error_handler import handle_errors
from app.logic.carlquant import RegionStats, Surface, LesionDepth, SliceResult, DataLoader
from app.view.carlquant.ascan_viewer import AScanViewer
from app.logic.carlquant.annotation_colors import ROW_HIGHLIGHT_NAVIGATION_COLOR, ROW_HIGHLIGHT_ASCAN_COLOR
from app.logic.carlquant import validation as val
from app.logic.carlquant.ground_truth import has_ground_truth


class resultsPanel:
    @handle_errors("resultsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_results")

        self.headers = ['MEASUREMENT', 'VALUE', 'UNIT', 'CONFIDENCE']
        self.highlighted_row = None  # Track currently highlighted row
        self.highlight_color = ROW_HIGHLIGHT_NAVIGATION_COLOR  # Current highlight color (green or purple)
        self.active_ascan_viewer = None  # Track active A-Scan viewer for checkbox synchronization
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
        
        # Bind click events
        self.sheet.bind("<Button-1>", self._on_single_click)  # Single-click for navigation
        self.sheet.bind("<Double-Button-1>", self._on_double_click)  # Double-click for A-Scan viewer
        
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        # Set initial column widths
        self._set_column_widths()

        self._setup_validation_ui()

    # ============================================================================
    # VALIDATION MODE
    # ============================================================================

    @handle_errors("resultsPanel._setup_validation_ui")
    def _setup_validation_ui(self):
        """Build the Validation Mode toggle and its error readout.

        The readout stays hidden until validation mode is enabled, so the
        results grid is unchanged for everyone not measuring accuracy.
        """
        self.validation_enabled = tk.BooleanVar(value=False)

        self.validationFrame = ttk.Frame(self.frame)
        self.validationFrame.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.validationFrame.columnconfigure(1, weight=1)

        self.validationCheck = ttk.Checkbutton(
            self.validationFrame,
            text="Validation Mode",
            variable=self.validation_enabled,
            command=self._on_validation_toggled,
            bootstyle="success-round-toggle"
        )
        self.validationCheck.grid(row=0, column=0, sticky="w", padx=(2, 8))

        # Marking with the detection overlay visible makes the marks drift
        # toward it and the comparison circular, so the state is called out.
        self.overlayHintLabel = ttk.Label(self.validationFrame, text="")
        self.overlayHintLabel.grid(row=0, column=1, sticky="w")

        self.validationResultsFrame = ttk.Frame(self.frame)
        self.validationSheet = None

    def _image_panel(self):
        """The image viewer panel, which owns the marks."""
        return self.context.get_panel("carl_image")

    @handle_errors("resultsPanel._on_validation_toggled")
    def _on_validation_toggled(self):
        """Switch marking on or off and show or hide the readout."""
        enabled = self.validation_enabled.get()

        image_panel = self._image_panel()
        if image_panel:
            image_panel.set_validation_mode(enabled)
            image_panel.validation_changed_callback = (
                self.refresh_validation_scores if enabled else None)

        if enabled:
            self.validationResultsFrame.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
            self.refresh_validation_scores()
        else:
            self.validationResultsFrame.grid_remove()
            self.overlayHintLabel.config(text="")

    @handle_errors("resultsPanel.refresh_validation_scores")
    def refresh_validation_scores(self):
        """Recompute and redisplay the per-slice and per-specimen errors."""
        if not self.validation_enabled.get():
            return

        image_panel = self._image_panel()
        if image_panel is None:
            return

        self._update_overlay_hint(image_panel)

        specimen = self._current_specimen()
        if specimen is None:
            self._render_validation_message("No specimen selected.")
            return

        marks_by_slice = image_panel.ground_truth_marks
        if not marks_by_slice:
            self._render_validation_message(
                "No marks yet. Press 'h' to hide the overlay, then click the "
                "true lesion end.")
            return

        per_slice = {}
        for slice_index, marks in marks_by_slice.items():
            detection_data = self._lesion_detection_data(specimen, slice_index)
            if detection_data:
                per_slice[slice_index] = val.score_slice(detection_data, marks)

        if not per_slice:
            self._render_validation_message(
                "Marked slices have no analysis results yet. Run the analysis "
                "to score them.")
            return

        current_slice = image_panel.current_slice_index()
        self._render_validation_table(per_slice, current_slice)

    def _update_overlay_hint(self, image_panel):
        """Warn while the detection overlay is visible during marking."""
        if getattr(image_panel, "overlays_visible", False):
            self.overlayHintLabel.config(
                text="Overlay VISIBLE - press 'h' to hide it before marking",
                bootstyle="warning")
        else:
            self.overlayHintLabel.config(
                text="Overlay hidden - marks are independent", bootstyle="secondary")

    def _current_specimen(self):
        """The Specimen currently selected, or None."""
        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})
        if not specimen_id or specimen_id not in specimen_data:
            return None
        return specimen_data[specimen_id]

    def _lesion_detection_data(self, specimen, slice_index):
        """Per-column detection data for one slice, or None if not analysed."""
        result = (specimen.results or {}).get(slice_index)
        lesion_depth = getattr(result, "lesion_depth", None) if result else None
        return getattr(lesion_depth, "lesion_detection_data", None) if lesion_depth else None

    def _ensure_validation_sheet(self):
        """Create the readout sheet on first use."""
        if self.validationSheet is not None:
            return

        self.validationSheet = Sheet(
            self.validationResultsFrame,
            headers=["METHOD", "MEDIAN", "|MEDIAN|", "P90", "N",
                     "SPECIMEN MEAN |MED|", "SPECIMEN ERROR"],
            show_table=True,
            show_row_index=False,
            show_header=True,
            show_x_scrollbar=True,
            show_y_scrollbar=False,
            height=170
        )
        self.validationSheet.set_options(
            table_bg="#2b2b2b", table_fg="#dcdcdc",
            header_bg="#3c3c3c", header_fg="#ffffff",
            grid_color="#444444", outline_color="#666666"
        )
        self.validationSheet.enable_bindings("copy", "single_select")
        self.validationSheet.grid(row=0, column=0, sticky="nsew")

        self.validationSummaryLabel = ttk.Label(
            self.validationResultsFrame, text="", bootstyle="secondary")
        self.validationSummaryLabel.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.validationResultsFrame.columnconfigure(0, weight=1)
        self.validationResultsFrame.grid_rowconfigure(0, weight=1)

    def _render_validation_message(self, message):
        """Show an explanatory message in place of the table."""
        self._ensure_validation_sheet()
        self.validationSheet.set_sheet_data([], reset_col_positions=False)
        self.validationSummaryLabel.config(text=message)

    def _render_validation_table(self, per_slice, current_slice):
        """Render per-slice errors for the current slice plus specimen aggregates.

        Both scales are shown deliberately: per-column accuracy is what an
        A-scan reader sees, while the specimen mean is what downstream analysis
        consumes, and a consistently signed bias does not cancel under
        averaging -- so the two can rank methods differently.
        """
        self._ensure_validation_sheet()

        specimen_summary = val.score_specimen(per_slice)
        slice_result = per_slice.get(current_slice)

        rows = []
        for method in val.METHODS:
            slice_scores = (slice_result or {}).get("methods", {}).get(method, {})
            specimen_scores = specimen_summary["methods"][method]
            has_slice_marks = bool(slice_scores.get("n"))

            rows.append([
                val.METHOD_LABELS[method],
                val.format_error(slice_scores.get("median")) if has_slice_marks else "--",
                val.format_error(slice_scores.get("abs_median"), signed=False) if has_slice_marks else "--",
                val.format_error(slice_scores.get("p90"), signed=False) if has_slice_marks else "--",
                str(slice_scores.get("n", 0)) if has_slice_marks else "--",
                val.format_error(specimen_scores["mean_abs_median"], signed=False),
                val.format_error(specimen_scores["specimen_error"]),
            ])

        self.validationSheet.set_sheet_data(rows, reset_col_positions=False)

        summary = (
            f"Slice {current_slice + 1}: "
            f"{(slice_result or {}).get('n_marks', 0)} marks   |   "
            f"Specimen: {specimen_summary['n_slices']} slices, "
            f"{specimen_summary['n_marks']} marks   |   "
            f"Operator mean depth: "
            f"{val.format_error(specimen_summary['operator_mean_depth'], signed=False)} px"
        )
        if slice_result and slice_result.get("gated"):
            summary += "   |   GATED: no lesion detected, depth = surface line"
        if specimen_summary["gated_slices"]:
            gated = ", ".join(str(index + 1) for index in specimen_summary["gated_slices"])
            summary += f"   |   Gated slices: {gated}"

        self.validationSummaryLabel.config(text=summary)


    @handle_errors("resultsPanel.load_results_for")
    def load_results_for(self, specimen_id: str):
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
        
        # Highlight current slice if image viewer is active
        self.sync_highlight_to_current_slice()

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
    
    # ============================================================================
    # ROW HIGHLIGHTING - Centralized Methods
    # ============================================================================
    
    @handle_errors("resultsPanel.highlight_row")
    def highlight_row(self, row, color=None):
        """
        Highlight a specific row with the given color.
        
        Args:
            row: Row index to highlight (0-based)
            color: Hex color string. If None, uses self.highlight_color
        """
        if row is None:
            return
        
        # Clear previous highlighting
        if self.highlighted_row is not None:
            self.sheet.dehighlight_rows([self.highlighted_row])
        
        # Use provided color or current highlight color
        highlight_color = color if color is not None else self.highlight_color
        
        # Highlight the row
        self.sheet.highlight_rows(
            [row],
            bg=highlight_color,
            fg="#ffffff"
        )
        self.highlighted_row = row
    
    @handle_errors("resultsPanel.set_highlight_color")
    def set_highlight_color(self, color):
        """
        Set the highlight color and re-highlight the current row if any.
        
        Args:
            color: Hex color string (e.g., ROW_HIGHLIGHT_NAVIGATION_COLOR or ROW_HIGHLIGHT_ASCAN_COLOR)
        """
        self.highlight_color = color
        
        # Re-highlight current row with new color
        if self.highlighted_row is not None:
            self.highlight_row(self.highlighted_row, color)
    
    @handle_errors("resultsPanel.sync_highlight_to_current_slice")
    def sync_highlight_to_current_slice(self):
        """
        Synchronize row highlighting with the currently displayed slice in the image viewer.
        Called when navigating slices via slider, arrow keys, or mouse wheel.
        """
        # Get current specimen and slice from image viewer
        image_panel = self.context.get_panel("carl_image")
        if not image_panel:
            return
        
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return
        
        # Get current slice index (0-based) from image viewer
        try:
            current_slice_index = int(image_panel.scale.get() - 1)  # Convert from 1-based to 0-based
        except (ValueError, AttributeError):
            return
        
        # Find the row that matches this slice
        # Row data format: [SPECIMEN_ID, SLICE, ...]
        # SLICE is 1-based in the table
        target_slice_display = current_slice_index + 1  # Convert to 1-based for comparison
        
        for row_idx in range(self.sheet.total_rows()):
            row_data = self.sheet.get_row_data(row_idx)
            if len(row_data) >= 2:
                row_specimen_id = row_data[0]
                row_slice = row_data[1]
                
                if row_specimen_id == specimen_id and row_slice == target_slice_display:
                    # Found matching row - highlight it
                    self.highlight_row(row_idx)
                    return
    
    @handle_errors("resultsPanel._on_single_click")
    def _on_single_click(self, event):
        """
        Handle single-click event on a row.
        Highlights the row and navigates both image viewer and A-Scan viewer (if open) to the selected slice.
        """
        # Get the clicked row
        row = self.sheet.identify_row(event, exclude_index=True)
        
        if row is not None:
            # Highlight the clicked row
            self.highlight_row(row)
            
            # Get row data
            row_data = self.sheet.get_row_data(row)
            
            # Extract specimen_id and slice_index from row data
            specimen_id = row_data[0] if len(row_data) > 0 else None
            slice_index = row_data[1] if len(row_data) > 1 else None
            
            if specimen_id is None or slice_index is None:
                return
            
            # Navigate image viewer to the selected slice
            self._navigate_to_slice(specimen_id, slice_index)
            
            # If A-Scan viewer is open, update it to the new slice
            if self.active_ascan_viewer and self.active_ascan_viewer.dialog and self.active_ascan_viewer.dialog.winfo_exists():
                self.active_ascan_viewer.update_to_slice(specimen_id, slice_index)
    
    def _navigate_to_slice(self, specimen_id, slice_index):
        """
        Navigate the image viewer to a specific specimen and slice.
        
        Args:
            specimen_id: ID of the specimen
            slice_index: Slice index (1-based from table)
        """
        # Get the image viewer panel
        image_panel = self.context.get_panel("carl_image")
        if not image_panel:
            return
        
        # Set the current specimen if different
        if self.context.current_specimen_id != specimen_id:
            self.context.current_specimen_id = specimen_id
        
        # Navigate to the correct slice (convert from 1-based to 0-based)
        image_panel.display_image(slice_index - 1)
        
        # Ensure overlays are visible
        if not image_panel.overlays_visible:
            image_panel.toggle_overlays()
    
    @handle_errors("resultsPanel._on_double_click")
    def _on_double_click(self, event):
        """
        Handle double-click event on a row.
        Highlights the row and opens/updates the A-Scan viewer.
        
        If an A-Scan viewer is already open, it will be updated to show the new slice
        instead of creating a new instance.
        """
        # Get the clicked row
        row = self.sheet.identify_row(event, exclude_index=True)
        
        if row is not None:
            # Highlight the clicked row (will use purple if A-Scan viewer is open, green otherwise)
            self.highlight_row(row)
            
            # Get row data
            row_data = self.sheet.get_row_data(row)
            
            # Extract specimen_id and slice_index from row data
            specimen_id = row_data[0] if len(row_data) > 0 else None
            slice_index = row_data[1] if len(row_data) > 1 else None
            
            if specimen_id is None or slice_index is None:
                self.context.status_bar.update("Invalid row data", level="error")
                return
            
            # Check if A-Scan viewer is already open
            if self.active_ascan_viewer and self.active_ascan_viewer.dialog and self.active_ascan_viewer.dialog.winfo_exists():
                # Update existing viewer to new slice
                self.active_ascan_viewer.update_to_slice(specimen_id, slice_index)
            else:
                # Create new A-Scan viewer
                main_window = self.root.winfo_toplevel()
                
                viewer = AScanViewer(
                    main_window, 
                    self.context.style, 
                    self.context,
                    specimen_id=specimen_id,
                    slice_index=slice_index,
                    row_data=row_data
                )
                viewer.show()
                
                # Track active A-Scan viewer for checkbox synchronization with image viewer
                self.active_ascan_viewer = viewer
                
                # Switch to purple highlighting when A-Scan viewer opens
                self.set_highlight_color(ROW_HIGHLIGHT_ASCAN_COLOR)


