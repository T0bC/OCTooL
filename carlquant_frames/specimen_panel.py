# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:49:04 2025

@author: meissnerto
"""

from tksheet import Sheet
from utils.error_handler import handle_errors

STATIC_BG_COLOR = "#2b2b2b"
STATIC_FG_COLOR = "#dcdcdc"
HEADER_BG_COLOR = "#3c3c3c"
HEADER_FG_COLOR = "#ffffff"
GRID_COLOR = "#444444"

class specimenPanel:
    @handle_errors("specimenPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_specimen")
        self.last_selected_row = None

        self.headers = ['SPECIMEN_ID', 'SLICES', 'REGIONS', 'AIR', 'STATE']
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

        self.sheet.enable_bindings("copy", "delete", "single_select")
        self.sheet.enable_bindings("single_select", "cell_select")
        self.sheet.extra_bindings("cell_select", func=self.on_row_selected)
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        
        # Set initial column widths
        self._set_column_widths()

    @handle_errors("specimenPanel.on_row_selected")
    def on_row_selected(self, event):
        row_index = self.sheet.get_currently_selected()[0]
        specimen_id = self.sheet.get_cell_data(row_index, 0)
        specimen_data = self.context.specimen_data.get(specimen_id)

        if specimen_data:
            self.context.current_specimen_id = specimen_id
            
            # MEMORY OPTIMIZATION: Reload results from disk if they were cleared
            # Results are cleared after saving to reduce memory usage during batch processing
            # They are reloaded on-demand when user selects a specimen for viewing
            if not specimen_data.results and specimen_data.config:
                from carlquant_frames.data_io import DataLoader
                # Reload annotations (surface, lesion_depth, extraction_regions) from JSON
                DataLoader.load_specimen_config(specimen_data)

            viewer_panel = self.context.get_panel("carl_image")
            viewer_panel.display_image(0)

            results_panel = self.context.get_panel("carl_results")
            results_panel.load_results_for(specimen_id)

            specimen_data.status = "Displayed"
            self.sheet.set_cell_data(row_index, 4, "Displayed")

            # Clear previous highlight
            if self.last_selected_row is not None:
                self.sheet.highlight_rows(
                    rows=[self.last_selected_row],
                    bg="#2b2b2b",
                    fg="#dcdcdc",
                    redraw=False
                )

            # Apply new highlight
            highlight_bg = "#ffd966"
            highlight_fg = self.choose_font_color(highlight_bg)
            self.sheet.highlight_rows(rows=[row_index], bg=highlight_bg, fg=highlight_fg, redraw=True)

            # Update tracker
            self.last_selected_row = row_index


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