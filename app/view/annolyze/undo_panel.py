"""
AnnoLyze Undo Panel.

Modal window displaying the full undo history as a tksheet grid. Each row shows
timestamp, slice, column, old/new values, feature, and annotation ID. Allows the
user to step back through recorded changes.

Key contents:
- UndoPanel: Toplevel undo-history viewer.
- _setup_sheet: Configures the tksheet with undo history columns.
- _setup_controls: Adds navigation and revert buttons.
- refresh: Reloads the sheet from the current undo stack.

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

from app.view.shared.error_handler import handle_errors
from app.view.shared.sheet_panel import BaseSheetPanel


class UndoPanel(BaseSheetPanel):
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

        # äself.style = Style(theme="darkly")  # Or match your main theme

        self._setup_sheet()
        self._setup_controls()

    def _setup_sheet(self):
        """Configure and display the sheet widget for undo history."""
        self._build_sheet(
            self.frame,
            [
                "Time",
                "Slice",
                "Column",
                "Old Value",
                "New Value",
                "Feature",
                "Annotation ID",
            ],
            ("single_select", "row_select", "right_click_popup_menu", "rc_select", "copy"),
            columnspan=2,
            show_row_index=False,
        )

        self._populate_sheet()
        self.sheet.bind("<Double-Button-1>", self._on_double_click)

    def _on_double_click(self, event):
        """Handle double-click events on the sheet to trigger undo and close the panel."""
        clicked_row = self.sheet.get_currently_selected()[0]
        if clicked_row is not None:
            self._undo_to_index(clicked_row)
            self.frame.destroy()

    def _undo_to_index(self, index):
        annotate_panel = self.context.get_panel("anno_image")

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
                    cells=[(i, col)], bg=bg_color, fg=fg_color, overwrite=True
                )
        self.fit_column_widths()
        self._resize_to_fit_table()

    def _setup_controls(self):
        """Create and place control buttons for undo and closing the panel."""
        undo_btn = ttk.Button(self.frame, text="Undo to Selected", command=self._undo_to_selected)
        undo_btn.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        close_btn = ttk.Button(self.frame, text="Close", command=self.frame.destroy)
        close_btn.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

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
