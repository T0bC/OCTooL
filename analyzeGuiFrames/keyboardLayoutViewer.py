# -*- coding: utf-8 -*-
"""
Created on Mon Sep 22 15:56:23 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from tkinter import ttk

class KeyboardLayoutViewer:
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.key_specs = []

        self.window = tk.Toplevel(self.root)
        self.window.title("Keyboard Layout Viewer")
        self.window.update_idletasks()
        self.window.geometry("")  # Let Tkinter calculate optimal size

        self.window.resizable(True, True)

        self.keyboard_frame = ttk.Frame(self.window)
        self.keyboard_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.key_buttons = {}

        self.table_frame = ttk.Frame(self.window)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.table = ttk.Treeview(
            self.table_frame,
            columns=("Key", "Column", "DataType"),
            show="headings"
        )
        self.table.heading("Key", text="Key")
        self.table.heading("Column", text="Column Name")
        self.table.heading("DataType", text="Data Type")

        self.table.column("Key", width=60, anchor="center")
        self.table.column("Column", width=150, anchor="w")
        self.table.column("DataType", width=120, anchor="w")

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
        self.key_specs = getattr(self.context.get_panel("results"), "dynamic_col_specs_full", [])

        for key, btn in self.key_buttons.items():
            btn.config(background="SystemButtonFace")  # Reset

        for key in ['f', 'h']:
            if key in self.key_buttons:
                self.key_buttons[key].config(bg="black", fg="white", text=key.upper())


        for col_name, color, key in self.key_specs:
            if key in self.key_buttons:
                self.key_buttons[key].config(background=color)
                # Optional: add tooltip or label text
                self.key_buttons[key].tooltip_text = f"{col_name}"

        self.table.delete(*self.table.get_children())  # Clear existing rows

        for col_name, color, key in self.key_specs:
            data_type = self.context.config_manager.get_data_type_for_column(col_name)  # Or use a fallback
            tag = f"tag_{key}"
            self.apply_row_color(tag, color)
            self.table.insert("", "end", values=(key, col_name, data_type), tags=(tag,))

        self.table.update_idletasks()
        self.window.update_idletasks()

        # Resize window to fit content
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        self.window.geometry(f"{width}x{height}")



    def apply_row_color(self, tag, color):
        style_name = f"{tag}.Treeview"
        style = ttk.Style()
        style.configure(style_name, background=color)
        self.table.tag_configure(tag, background=color)


