"""
AnnoLyze Keyboard Layout Viewer.

Floating window that visualises the current key-to-column bindings. Shows a
keyboard grid with coloured keys and a detail table of bound columns, data types,
and activation status.

Key contents:
- KeyboardLayoutViewer: Toplevel window displaying bound keys and column metadata.
- update_highlights: Refreshes keys and table when bindings change; fits the window to the rows.
- save_as_png: Saves keyboard + table as a PNG reference image.
- on_close: Hides the window so it can be reopened later.

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
from tkinter import filedialog, ttk

from app.logic.annolyze.keyboard_layout_image import (
    KEYBOARD_ROW_OFFSETS,
    KEYBOARD_ROWS,
    UNBOUND_KEY_BG,
    UNBOUND_KEY_FG,
    render_keyboard_layout,
)
from app.view.shared import dialogs
from app.view.shared.sheet_panel import BaseSheetPanel

TABLE_HEADERS = ["Key", "Column Name", "Data Type", "Status"]

# Reserved keys - hardcoded system bindings
RESERVED_BINDINGS = {
    "f": ("Fit Bezier Curve", "System Function"),
    "h": ("Toggle Annotation Overlays", "System Function"),
}


class KeyboardLayoutViewer(BaseSheetPanel):
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.context.keyboard_layout_viewer = self

        self.key_specs = []

        self.window = tk.Toplevel(self.root)
        self.window.title("Keyboard Layout Viewer")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window.resizable(True, True)

        # Keyboard and toolbar keep their natural height; only the table
        # grows when the window is resized, so it stays right under the keys.
        self.keyboard_frame = ttk.Frame(self.window)
        self.keyboard_frame.pack(side="top", anchor="w", padx=10, pady=(10, 4))

        self.key_buttons = {}

        self.toolbar_frame = ttk.Frame(self.window)
        self.toolbar_frame.pack(side="top", fill="x", padx=10, pady=(0, 4))
        ttk.Button(self.toolbar_frame, text="Save as PNG...", command=self.save_as_png).pack(
            side="left"
        )

        self.table_frame = ttk.Frame(self.window)
        self.table_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self._build_sheet(
            self.table_frame,
            TABLE_HEADERS,
            ("single_select", "copy"),
            show_row_index=False,
            height=200,
            width=480,
        )
        self.sheet.set_column_widths([60, 200, 120, 100])

        self.draw_keyboard()

    def draw_keyboard(self):
        for row_index, (row, offset) in enumerate(
            zip(KEYBOARD_ROWS, KEYBOARD_ROW_OFFSETS, strict=True)
        ):
            for col_index, key in enumerate(row):
                btn = tk.Label(
                    self.keyboard_frame,
                    text=key.upper(),
                    width=5,
                    height=2,
                    font=("Segoe UI", 12, "bold"),
                    relief="raised",
                    bd=2,
                    anchor="center",
                )
                btn.grid(row=row_index, column=offset + col_index, padx=2, pady=2)
                self.key_buttons[key] = btn

        self.update_highlights()

    def _key_colors(self) -> dict[str, tuple[str, str]]:
        """Key -> (bg, fg) for every reserved and user-bound key."""
        colors = {key: ("black", "white") for key in RESERVED_BINDINGS}
        for _col_name, color, key, _data_type in self.key_specs:
            colors[key] = (color, self.choose_font_color(color))
        return colors

    def _table_rows(self) -> list[tuple[list[str], str, str]]:
        """(cell values, bg, fg) per table row: reserved keys first, then user keys."""
        rows = [
            ([key.upper(), purpose, data_type, "Reserved"], "black", "white")
            for key, (purpose, data_type) in RESERVED_BINDINGS.items()
        ]
        for col_name, color, key, data_type in self.key_specs:
            rows.append(
                (
                    [key.upper(), col_name, data_type, "User-defined"],
                    color,
                    self.choose_font_color(color),
                )
            )
        return rows

    def update_highlights(self):
        if not self.window.winfo_exists():
            return

        # Always pull fresh specs
        self.key_specs = getattr(self.context, "keybinding_specs", [])

        key_colors = self._key_colors()
        for key, btn in self.key_buttons.items():
            if btn.winfo_exists():
                # Unbound keys use the same light grey as the saved PNG, so they stand
                # apart from the black reserved keys on the dark theme.
                bg, fg = key_colors.get(key, (UNBOUND_KEY_BG, UNBOUND_KEY_FG))
                btn.config(background=bg, fg=fg, text=key.upper())

        col_names = {key: col_name for col_name, _color, key, _data_type in self.key_specs}
        for key, col_name in col_names.items():
            if key in self.key_buttons:
                self.key_buttons[key].tooltip_text = f"{col_name}"

        rows = self._table_rows()
        self.sheet.dehighlight_all(redraw=False)
        self.sheet.set_sheet_data([values for values, _, _ in rows], reset_col_positions=False)
        for i, (_values, bg, fg) in enumerate(rows):
            self.sheet.highlight_rows([i], bg=bg, fg=fg, redraw=False)
        self.sheet.refresh()

        self._fit_window_to_rows(len(rows))

    def _fit_window_to_rows(self, num_rows: int) -> None:
        """Size the table to show every row, capped so the window fits the screen."""
        self.window.update_idletasks()
        row_heights = self.sheet.get_row_heights()
        row_height = int(row_heights[0]) if row_heights else 24
        scrollbar = getattr(self.sheet, "xscroll", None)
        scrollbar_height = scrollbar.winfo_reqheight() if scrollbar else 17

        # +1 row for the header (same single-line height as a data row)
        table_height = (num_rows + 1) * row_height + scrollbar_height + 4

        fixed_height = (
            self.keyboard_frame.winfo_reqheight() + self.toolbar_frame.winfo_reqheight() + 40
        )
        max_table_height = self.window.winfo_screenheight() - fixed_height - 120
        self.sheet.height_and_width(height=max(row_height * 3, min(table_height, max_table_height)))

        self.window.update_idletasks()
        self.window.geometry(f"{self.window.winfo_reqwidth()}x{self.window.winfo_reqheight()}")

    def save_as_png(self):
        """Save keyboard and binding table as a PNG reference image."""
        file_path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save Keyboard Layout",
            defaultextension=".png",
            initialfile="keyboard_layout.png",
            filetypes=[("PNG image", "*.png")],
        )
        if not file_path:
            return

        try:
            image = render_keyboard_layout(self._key_colors(), TABLE_HEADERS, self._table_rows())
            image.save(file_path, "PNG")
        except (OSError, ValueError) as e:
            dialogs.show_error(self.window, "Save Failed", f"Could not save image:\n{e}")
            return

        self.context.safe_status_update(f"Keyboard layout saved to: {file_path}", level="success")

    def on_close(self):
        self.context.keyboard_layout_viewer = None
        self.window.destroy()
