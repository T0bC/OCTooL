# -*- coding: utf-8 -*-
"""
Created on Fri Sep 12 11:50:18 2025

@author: meissnerto
"""

from errorHandler import handle_errors
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tksheet import Sheet
from ttkbootstrap import Style

class UndoPanel:
    @handle_errors("UndoPanel.__init__")
    def __init__(self, context, undo_stack):
        """Initialize the UndoPanel with context and undo stack, and set up the UI components."""
        self.context = context
        self.root = context.root
        self.undo_stack = undo_stack

        self.frame = tk.Toplevel(self.root)
        self.frame.title("Undo History")
        self.frame.geometry("600x400")
        self.frame.transient(self.root)
        self.frame.grab_set()

        #äself.style = Style(theme="darkly")  # Or match your main theme

        self._setup_sheet()
        self._setup_controls()

    def _setup_sheet(self):
        """Configure and display the sheet widget for undo history."""
        self.sheet = Sheet(self.frame, headers=["Time", "Slice", "Column", "Old Value", "New Value", "Feature", "Annotation ID"])
        self.sheet.header_font = ("Segoe UI", 12, "bold")
        self.sheet.set_options(header_fg="#F5F5F5", header_bg="#2B2B2B")

        self.sheet.grid_color = "#444444"
        self.sheet.table_bg = "#1E1E1E"
        self.sheet.table_fg = "#E0E0E0"

        self.sheet.enable_bindings((
            "single_select",  # allows single cell selection
            "row_select",     # enables row selection
            "right_click_popup_menu",
            "rc_select",
            "copy",
        ))

        self.sheet.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self._populate_sheet()
        self.sheet.bind("<Double-Button-1>", self._on_double_click)

    def _on_double_click(self, event):
        """Handle double-click events on the sheet to trigger undo and close the panel."""
        clicked_row = self.sheet.get_currently_selected()[0]
        if clicked_row is not None:
            self._undo_to_index(clicked_row)
            self.frame.destroy()


    def _undo_to_index(self, index):
        annotate_panel = self.context.get_panel("image")

        while len(self.undo_stack) > index:
            action = self.undo_stack.pop()

            # Undo sheet value
            self.context.get_panel("results").sheet.set_cell_data(
                action["row"], action["col"], action["old_value"]
            )

            # Remove only the matching annotation
            annotation_id = action.get("annotation_id")
            slice_index = action["row"]

            if annotation_id and annotate_panel:
                annotations = annotate_panel.slice_annotations.get(slice_index, [])
                filtered = [a for a in annotations if a.get("id") != annotation_id]
                annotate_panel.slice_annotations[slice_index] = filtered
                annotate_panel.draw_annotation()
                annotate_panel.save_current_annotations()


    def _undo_to_selected(self):
        """Undo actions up to the currently selected row in the sheet."""
        selected = self.sheet.get_currently_selected()
        if selected:
            self._undo_to_index(selected[0])
            self.frame.destroy()


    def _populate_sheet(self):
        """Populate the sheet with undo history data and apply cell highlighting."""
        data = []

        for entry in self.undo_stack:
            ts = entry.get("timestamp").strftime("%H:%M:%S")
            slice_str = str(entry["row"] + 1)
            col_name = entry["col_name"]
            old_value = entry.get("old_value", "")
            new_value = entry.get("new_value", "")
            feature = entry.get("feature", "")
            annotation_id = entry.get("annotation_id", "")

            data.append([ts, slice_str, col_name, old_value, new_value, feature, annotation_id])


        self.sheet.set_sheet_data(data)

        for i, entry in enumerate(self.undo_stack):
            bg_color = entry.get("color", "#2C2C2C")  # fallback to dark gray
            fg_color = self.choose_font_color(bg_color)

            for col in range(len(self.sheet.headers())):
                self.sheet.highlight_cells(
                    cells=[(i, col)],
                    bg=bg_color,
                    fg=fg_color,
                    overwrite=True
                )
        self._set_column_widths()
        self._resize_to_fit_table()

    def _setup_controls(self):
        """Create and place control buttons for undo and closing the panel."""
        undo_btn = ttk.Button(self.frame, text="Undo to Selected", command=self._undo_to_selected)
        undo_btn.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        close_btn = ttk.Button(self.frame, text="Close", command=self.frame.destroy)
        close_btn.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

    # %% font color calulation
    def get_luminance(self, hex_color: str) -> float:
        """Calculate the relative luminance of a hex color.

        Args:
            hex_color (str): Hexadecimal color string.

        Returns:
            float: Luminance value between 0 and 1.
        """
        hex_color = hex_color.lstrip("#")
        r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

        def adjust(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def choose_font_color(self, bg_color: str) -> str:
        """Determine appropriate font color (black or white) based on background luminance.

        Args:
            bg_color (str): Background color in hexadecimal format.

        Returns:
            str: Font color in hexadecimal format.
        """
        luminance = self.get_luminance(bg_color)
        return "#FFFFFF" if luminance < 0.5 else "#000000"

    # %% Column width logic

    def _set_column_widths(self) -> None:
        """Set the width of each column in the sheet based on header text length."""
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

    # %% window size

    def _resize_to_fit_table(self):
        """Resize the undo panel window to fit the dimensions of the sheet table."""
        # Calculate total width
        total_width = sum(self.sheet.column_width(col) for col in range(len(self.sheet.headers())))
        total_width += 80  # padding for borders and scrollbars

        # Estimate total height
        row_height = self.sheet.row_height(0)  # assuming uniform row height
        total_height = row_height * (self.sheet.total_rows() + 1)  # +1 for header
        total_height += 80  # padding for buttons and borders

        # Apply new geometry
        self.frame.geometry(f"{total_width}x{total_height}")
