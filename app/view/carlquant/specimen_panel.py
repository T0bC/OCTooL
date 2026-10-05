"""
CarlQuant Specimen Panel.

Spreadsheet panel (tksheet) listing all loaded specimens with ID, slice count,
and analysis state. Supports multi-row selection, status colouring (new,
completed, invalid), and keyboard navigation.

Key contents:
- specimenPanel: tksheet grid for specimen management and selection.
- _setup_sheet: Configures the sheet with ID, SLICES, and STATE columns.
- add_specimen / remove_specimen: Modify the specimen list.
- update_state: Changes the status colour (green for completed, red for invalid).
- Selection tracking: Supports range selection with Shift and Ctrl.

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

from app.view.shared.error_handler import handle_errors
from app.view.shared.sheet_panel import TABLE_BG, TABLE_FG, BaseSheetPanel

COMPLETED_BG_COLOR = "#16472a"
COMPLETED_FG_COLOR = "#dcdcdc"
INVALID_BG_COLOR = "#8B0000"  # Dark red for specimens with missing coordinates
INVALID_FG_COLOR = "#FFFFFF"


class specimenPanel(BaseSheetPanel):
    @handle_errors("specimenPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_specimen")
        self.last_selected_row = None  # Anchor for range selection
        self.selected_rows = set()  # Tracks all currently selected rows
        self.invalid_specimen_rows = (
            set()
        )  # Tracks rows with missing coordinates (persistent red highlight)

        self.headers = ["SPECIMEN_ID", "SLICES", "STATE"]
        self._setup_sheet()

    def _setup_sheet(self):
        self._build_sheet(
            self.frame,
            self.headers,
            ("copy", "delete", "single_select", "row_select", "drag_select"),
        )
        # Register select callback - uses selection_boxes for Shift+Click range detection
        self.sheet.extra_bindings("select", func=self.on_cell_selected)

        # Set initial column widths
        self.fit_column_widths(include_content=True)

    @handle_errors("specimenPanel.on_cell_selected")
    def on_cell_selected(self, event):
        """
        Handle row selection with Shift+Click range support.

        Flow:
        1. Parse selection_boxes for range detection (Shift+Click)
        2. If range: populate selected_rows set, keep first row displayed
        3. If single: populate selected_rows set, display specimen
        4. Apply visual highlighting to all selected rows
        """
        if not isinstance(event, dict):
            return

        # Try to extract row range from selection_boxes (indicates Shift+Click)
        selection_boxes = event.get("selection_boxes", {})
        if selection_boxes:
            box = next(iter(selection_boxes.keys()))  # Get first (and only) box
            start_row = box.from_r
            end_row = box.upto_r - 1  # upto_r is exclusive

            # Populate selected_rows set with range
            self.selected_rows = set(range(start_row, end_row + 1))

            # For range selection: keep first row displayed, don't reload specimen
            if start_row != end_row:
                self.last_selected_row = min(self.selected_rows)
                self._highlight_selected_rows()
                return

        # Single selection: extract row from 'selected' field
        selected_info = event.get("selected")
        if not selected_info or not hasattr(selected_info, "row") or selected_info.row is None:
            return

        current_row = int(selected_info.row)
        self.selected_rows = {current_row}

        # Display specimen and update highlighting
        self._display_specimen(current_row)

    def _display_specimen(self, row_index):
        """Display a specimen in the viewer and results panels."""
        specimen_id = self.sheet.get_cell_data(row_index, 0)
        specimen_data = self.context.specimen_data.get(specimen_id)

        if specimen_data:
            self.context.current_specimen_id = specimen_id

            # MEMORY OPTIMIZATION: Reload results from disk if they were cleared
            # Results are cleared after saving to reduce memory usage during batch processing
            # They are reloaded on-demand when user selects a specimen for viewing
            if not specimen_data.results and specimen_data.config:
                from app.logic.carlquant import DataLoader

                # Reload annotations (surface, lesion_depth, extraction_regions) from JSON
                # Use load_annotations=True to load the full data now that user wants to view it
                DataLoader.load_specimen_config(specimen_data, load_annotations=True)

            viewer_panel = self.context.get_panel("carl_image")
            viewer_panel.display_image(0)

            results_panel = self.context.get_panel("carl_results")
            results_panel.load_results_for(specimen_id)

            specimen_data.status = "Displayed"
            self.sheet.set_cell_data(row_index, 2, "Displayed")

            # Highlight the current selection
            self._highlight_selected_rows()

            # Update anchor point for range selection
            self.last_selected_row = row_index

    def _highlight_selected_rows(self):
        """Apply highlighting to all selected rows with proper priority."""
        # First, restore all rows to their default colors
        for row_idx in range(self.sheet.total_rows()):
            status = self.sheet.get_cell_data(row_idx, 2)

            # Priority 1: Invalid specimens (missing coordinates) - always red
            if row_idx in self.invalid_specimen_rows:
                self.sheet.highlight_rows(
                    rows=[row_idx], bg=INVALID_BG_COLOR, fg=INVALID_FG_COLOR, redraw=False
                )
            # Priority 2: Analyzed/Completed rows (green) - persistent even when selected
            elif status in ["Analyzed", "Completed"]:
                self.sheet.highlight_rows(
                    rows=[row_idx], bg=COMPLETED_BG_COLOR, fg=COMPLETED_FG_COLOR, redraw=False
                )
            # Priority 3: Selected rows (golden highlight)
            elif row_idx in self.selected_rows:
                highlight_bg = "#ffd966"
                highlight_fg = self.choose_font_color(highlight_bg)
                self.sheet.highlight_rows(
                    rows=[row_idx], bg=highlight_bg, fg=highlight_fg, redraw=False
                )
            # Priority 4: Default color
            else:
                self.sheet.highlight_rows(rows=[row_idx], bg=TABLE_BG, fg=TABLE_FG, redraw=False)

        self.sheet.refresh()

    @handle_errors("specimenPanel.highlight_completed_row")
    def highlight_completed_row(self, row_index: int) -> None:
        """
        Highlight a row with green color to indicate it has been completed.

        Args:
            row_index (int): The row index to highlight.
        """
        # Only highlight if this is not the currently selected row
        if row_index != self.last_selected_row:
            self.sheet.highlight_rows(
                rows=[row_index], bg=COMPLETED_BG_COLOR, fg=COMPLETED_FG_COLOR, redraw=True
            )

    @handle_errors("specimenPanel.highlight_invalid_row")
    def highlight_invalid_row(self, row_index: int) -> None:
        """
        Highlight a row with red color to indicate missing coordinates.
        Adds row to persistent invalid tracking set.

        Args:
            row_index (int): The row index to highlight.
        """
        self.invalid_specimen_rows.add(row_index)
        self.sheet.highlight_rows(
            rows=[row_index], bg=INVALID_BG_COLOR, fg=INVALID_FG_COLOR, redraw=False
        )

    @handle_errors("specimenPanel.clear_all_highlights")
    def clear_all_highlights(self) -> None:
        """
        Clear all validation error highlighting and restore default colors for all rows.
        Preserves analyzed/completed row highlighting and current selection.
        Clears the invalid specimen tracking set.
        """
        # Clear invalid specimen tracking
        self.invalid_specimen_rows.clear()

        for row_idx in range(self.sheet.total_rows()):
            status = self.sheet.get_cell_data(row_idx, 2)

            # Priority 1: Analyzed/Completed rows (green) - always preserve
            if status in ["Analyzed", "Completed"]:
                self.sheet.highlight_rows(
                    rows=[row_idx], bg=COMPLETED_BG_COLOR, fg=COMPLETED_FG_COLOR, redraw=False
                )
            # Priority 2: Selected rows (golden)
            elif row_idx in self.selected_rows:
                highlight_bg = "#ffd966"
                highlight_fg = self.choose_font_color(highlight_bg)
                self.sheet.highlight_rows(
                    rows=[row_idx], bg=highlight_bg, fg=highlight_fg, redraw=False
                )
            # Priority 3: Default color
            else:
                self.sheet.highlight_rows(rows=[row_idx], bg=TABLE_BG, fg=TABLE_FG, redraw=False)

        self.sheet.refresh()
