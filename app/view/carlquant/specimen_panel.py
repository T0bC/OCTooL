# -*- coding: utf-8 -*-
"""
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


from tksheet import Sheet
from app.view.shared.error_handler import handle_errors

STATIC_BG_COLOR = "#2b2b2b"
STATIC_FG_COLOR = "#dcdcdc"
HEADER_BG_COLOR = "#3c3c3c"
HEADER_FG_COLOR = "#ffffff"
GRID_COLOR = "#444444"
COMPLETED_BG_COLOR = "#16472a"
COMPLETED_FG_COLOR = "#dcdcdc"
INVALID_BG_COLOR = "#8B0000"  # Dark red for specimens with missing coordinates
INVALID_FG_COLOR = "#FFFFFF"

class specimenPanel:
    @handle_errors("specimenPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_specimen")
        self.last_selected_row = None  # Anchor for range selection
        self.selected_rows = set()  # Tracks all currently selected rows
        self.invalid_specimen_rows = set()  # Tracks rows with missing coordinates (persistent red highlight)

        self.headers = ['SPECIMEN_ID', 'SLICES', 'STATE']
        self._setup_sheet()

    def _setup_sheet(self):
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

        self.sheet.enable_bindings("copy", "delete", "single_select", "row_select", "drag_select")
        # Register select callback - uses selection_boxes for Shift+Click range detection
        self.sheet.extra_bindings("select", func=self.on_cell_selected)
        
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Set initial column widths
        self._set_column_widths()

    
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
        selection_boxes = event.get('selection_boxes', {})
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
        selected_info = event.get('selected')
        if not selected_info or not hasattr(selected_info, 'row') or selected_info.row is None:
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
                    rows=[row_idx],
                    bg=INVALID_BG_COLOR,
                    fg=INVALID_FG_COLOR,
                    redraw=False
                )
            # Priority 2: Analyzed/Completed rows (green) - persistent even when selected
            elif status in ["Analyzed", "Completed"]:
                self.sheet.highlight_rows(
                    rows=[row_idx],
                    bg=COMPLETED_BG_COLOR,
                    fg=COMPLETED_FG_COLOR,
                    redraw=False
                )
            # Priority 3: Selected rows (golden highlight)
            elif row_idx in self.selected_rows:
                highlight_bg = "#ffd966"
                highlight_fg = self.choose_font_color(highlight_bg)
                self.sheet.highlight_rows(rows=[row_idx], bg=highlight_bg, fg=highlight_fg, redraw=False)
            # Priority 4: Default color
            else:
                self.sheet.highlight_rows(
                    rows=[row_idx],
                    bg=STATIC_BG_COLOR,
                    fg=STATIC_FG_COLOR,
                    redraw=False
                )
        
        self.sheet.refresh()


    def get_luminance(self, hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

        def adjust(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    def choose_font_color(self, bg_color: str) -> str:
        luminance = self.get_luminance(bg_color)
        return "#FFFFFF" if luminance < 0.5 else "#000000"


    @handle_errors("specimenPanel._set_column_widths")
    def _set_column_widths(self) -> None:
        """ Set column widths based on header and cell content. """
        column_names = self.sheet.headers()
        
        for i, header in enumerate(column_names):
            # Get all cell values in this column
            cell_values = []
            for row_idx in range(self.sheet.total_rows()):
                cell_data = self.sheet.get_cell_data(row_idx, i)
                if cell_data:
                    cell_values.append(str(cell_data))
            
            # Calculate width based on header and content
            width = self._calculate_column_width(header, cell_values)
            self.sheet.column_width(i, width=width)

        self.sheet.refresh()


    @handle_errors("specimenPanel._calculate_column_width")
    def _calculate_column_width(self, header: str, cell_values: list = None) -> int:
        """
        Calculate column width based on header and cell content (whichever is longer).

        Args:
            header (str): Column header text.
            cell_values (list): List of cell values in this column.

        Returns:
            int: Suggested column width.
        """
        base_width = 40  # Minimum width
        char_width = 7   # Approximate width per character
        padding = 20     # Extra space for clarity
        max_width = 250
        
        # Calculate width needed for header
        header_width = len(header) * char_width + padding
        
        # Calculate width needed for longest cell content
        max_cell_width = base_width
        if cell_values:
            max_cell_length = max(len(str(val)) for val in cell_values) if cell_values else 0
            max_cell_width = max_cell_length * char_width + padding
        
        # Use the larger of header or content width
        calculated_width = max(header_width, max_cell_width, base_width)
        
        return min(calculated_width, max_width)


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
                rows=[row_index],
                bg=COMPLETED_BG_COLOR,
                fg=COMPLETED_FG_COLOR,
                redraw=True
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
            rows=[row_index],
            bg=INVALID_BG_COLOR,
            fg=INVALID_FG_COLOR,
            redraw=False
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
                    rows=[row_idx],
                    bg=COMPLETED_BG_COLOR,
                    fg=COMPLETED_FG_COLOR,
                    redraw=False
                )
            # Priority 2: Selected rows (golden)
            elif row_idx in self.selected_rows:
                highlight_bg = "#ffd966"
                highlight_fg = self.choose_font_color(highlight_bg)
                self.sheet.highlight_rows(rows=[row_idx], bg=highlight_bg, fg=highlight_fg, redraw=False)
            # Priority 3: Default color
            else:
                self.sheet.highlight_rows(
                    rows=[row_idx],
                    bg=STATIC_BG_COLOR,
                    fg=STATIC_FG_COLOR,
                    redraw=False
                )
        
        self.sheet.refresh()