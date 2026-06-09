# -*- coding: utf-8 -*-
"""
AnnoLyze Keyboard Layout Viewer.

Floating window that visualises the current key-to-column bindings. Shows a
keyboard grid with coloured keys and a detail table of bound columns, data types,
and activation status.

Key contents:
- KeyboardLayoutViewer: Toplevel window displaying bound keys and column metadata.
- update_bindings: Refreshes the keyboard grid when columns change.
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
from tkinter import ttk

class KeyboardLayoutViewer:
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.context.keyboard_layout_viewer = self

        self.key_specs = []

        self.window = tk.Toplevel(self.root)
        self.window.title("Keyboard Layout Viewer")
        self.window.update_idletasks()
        self.window.geometry("")  # Let Tkinter calculate optimal size

        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.window.resizable(True, True)

        self.keyboard_frame = ttk.Frame(self.window)
        self.keyboard_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.key_buttons = {}

        self.table_frame = ttk.Frame(self.window)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.table = ttk.Treeview(
            self.table_frame,
            columns=("Key", "Column", "DataType", "Status"),
            show="headings"
        )
        self.table.heading("Key", text="Key")
        self.table.heading("Column", text="Column Name")
        self.table.heading("DataType", text="Data Type")
        self.table.heading("Status", text="Status")

        self.table.column("Key", width=60, anchor="center")
        self.table.column("Column", width=200, anchor="w")
        self.table.column("DataType", width=120, anchor="w")
        self.table.column("Status", width=100, anchor="w")

        self.table.pack(fill="both", expand=True)

        self.draw_keyboard()




    def draw_keyboard(self):
        layout = [
            ("", "q", "w", "e", "r", "t", "z", "u", "i", "o", "p"),
            ("", "a", "s", "d", "f", "g", "h", "j", "k", "l"),
            ("", "", "y", "x", "c", "v", "b", "n", "m")
        ]

        for row_index, row in enumerate(layout):
            for col_index, key in enumerate(row):
                if key == "":
                    continue  # Skip empty spacers
                btn = tk.Label(
                    self.keyboard_frame,
                    text=key.upper(),
                    width=5,
                    height=2,
                    font=("Segoe UI", 12, "bold"),
                    relief="raised",
                    bd=2,
                    anchor="center"
                )
                btn.grid(row=row_index, column=col_index, padx=2, pady=2)
                self.key_buttons[key] = btn


        self.update_highlights()

    def update_highlights(self):
        if not self.window.winfo_exists():
            return

        # Always pull fresh specs
        self.key_specs = getattr(self.context, "keybinding_specs", [])

        # Reset all keys
        for key, btn in self.key_buttons.items():
            if btn.winfo_exists():
                btn.config(background="SystemButtonFace", fg="black", text=key.upper())

        # Reserved keys - hardcoded system bindings
        reserved_bindings = {
            'f': ('Fit Bezier Curve', 'System Function'),
            'h': ('Toggle Annotation Overlays', 'System Function')
        }
        
        for key in ['f', 'h']:
            if key in self.key_buttons and self.key_buttons[key].winfo_exists():
                self.key_buttons[key].config(bg="black", fg="white", text=key.upper())

        # Clear table
        self.table.delete(*self.table.get_children())

        # Add reserved/hardcoded keybindings first
        for key, (purpose, data_type) in reserved_bindings.items():
            tag = f"tag_reserved_{key}"
            self.apply_row_color(tag, "black", fg="white")
            self.table.insert("", "end", values=(key.upper(), purpose, data_type, "Reserved"), tags=(tag,))

        # Populate user-defined keybindings
        for col_name, color, key, data_type in self.key_specs:
            if key in self.key_buttons and self.key_buttons[key].winfo_exists():
                self.key_buttons[key].config(background=color)
                self.key_buttons[key].tooltip_text = f"{col_name}"

            tag = f"tag_{key}"
            self.apply_row_color(tag, color)
            self.table.insert("", "end", values=(key.upper(), col_name, data_type, "User-defined"), tags=(tag,))

        self.table.update_idletasks()
        self.window.update_idletasks()

        # Resize window
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        self.window.geometry(f"{width}x{height}")


    def apply_row_color(self, tag, color, fg=None):
        style_name = f"{tag}.Treeview"
        style = ttk.Style()
        if fg:
            style.configure(style_name, background=color, foreground=fg)
            self.table.tag_configure(tag, background=color, foreground=fg)
        else:
            style.configure(style_name, background=color)
            self.table.tag_configure(tag, background=color)


    def on_close(self):
        self.context.keyboard_layout_viewer = None
        self.window.destroy()

