# -*- coding: utf-8 -*-
"""
AnnoLyze Add Columns Panel.

UI for defining dynamic measurement columns: name, keybinding, data type, and
color. New columns are inserted into the results sheet and registered with the
keybinding manager so they can be populated during annotation.

Key contents:
- addColumnsPanel: Panel for creating and registering dynamic columns.
- columnNameEntry / keyBindCombo / dataTypeCombo: Input widgets for column spec.
- addColumnBtn: Validates inputs and appends the column to the results sheet.

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
from app.logic.shared import oct_functions as octF
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors
from tkinter import colorchooser
import customtkinter as ctk
from CTkColorPicker import AskColor
from app.logic.annolyze.measurement_service import MeasurementService

class addColumnsPanel:
    @handle_errors("error in addColumnsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("add_columns")
        self.resultsPanel = context.get_panel("results")
        self.measurement_service = MeasurementService()

        self.column_keybindings = {}
        self.column_data_types = {}
        self.column_colors = {}
        self.selectedColor = "#FFFFFF"

        self.columnNameToolTip = 'Enter the name of the column. e.g GapInterface.'

        self.columnNameEntry = ttk.Entry(self.frame, width=15, bootstyle="success")
        self.columnNameEntry.insert(0, 'GAP')
        self.columnNameEntry.grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=3)
        Tooltip(self.columnNameEntry, text=self.columnNameToolTip , wraplength=200)

        self.keyBindToolTip = 'Select a unique key to bind this column.'

        self.keyBindVar = tk.StringVar()
        self.keyBindDropdown = ttk.Combobox(
            self.frame,
            textvariable=self.keyBindVar,
            state="readonly",
            width=4,
            bootstyle="success"
        )
        self.keyBindDropdown.grid(row=0, column=1, sticky="ew", padx=3, pady=3)
        Tooltip(self.keyBindDropdown, text=self.keyBindToolTip, wraplength=200)

        self.update_available_keys()

        self.dataTypeToolTip = (
            "Select the type of data stored in this column:\n\n"
            "Continuous – A number that can take any value within a range. Used for measurements like length (mm, cm, m), weight (kg), or time (seconds).\n\n"
            "Percentage – A value expressed as a part of 100. Useful for proportions or rates. Example: 85% battery, 12% error rate.\n\n"
            "Boolean – A simple Yes/No or True/False value. Great for binary decisions. Example: Is active? → Yes.\n\n"
            "Categorical – A label or category that describes a group. Not ordered. Example: 'Red', 'Blue', 'Green'.\n\n"
            "Ordinal – Categories that have a meaningful order, but not necessarily equal spacing. Example: 'Low', 'Medium', 'High'.\n\n"
            "Integer – Whole numbers without decimals. Used for counts or discrete values. Example: 1, 42, -7.\n\n"
            "Float – Decimal numbers. More precise than integers. Example: 3.14, -0.001, 0.5.\n\n"
            "Text/String – Free-form text or labels. Can be names, comments, or descriptions. Example: 'Sample A'.\n\n"
        )

        self.dataTypeVar = tk.StringVar()
        self.dataTypeDropdown = ttk.Combobox(
            self.frame,
            textvariable=self.dataTypeVar,
            values=[
                "Continuous", "Percentage", "Boolean", "Categorical", "Ordinal",
                "Integer", "Float", "Text/String",
            ],
            state="readonly",
            width=15,
            bootstyle="success"
        )
        self.dataTypeDropdown.set("Continuous")  # Default selection
        self.dataTypeDropdown.grid(row=0, column=2, sticky="ew", padx=3, pady=3)
        Tooltip(self.dataTypeDropdown, text=self.dataTypeToolTip, wraplength=200)

        # Single color element: an editable hex entry that doubles as a color
        # swatch (its background shows the selected color) and opens the color
        # picker popup on double-click.
        self.colorEntry = tk.Entry(
            self.frame,
            width=9,
            justify="center",
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.colorEntry.insert(0, self.selectedColor)
        self.colorEntry.grid(row=0, column=3, sticky="ew", padx=(3, 0), pady=3)
        self._apply_color_to_entry(self.selectedColor)
        self.colorEntry.bind("<Return>", self._on_hex_entered)
        self.colorEntry.bind("<FocusOut>", self._on_hex_entered)
        self.colorEntry.bind("<Double-Button-1>", lambda e: self.pick_color_ctk())
        Tooltip(
            self.colorEntry,
            text="Type a hex color (e.g. #FF8800) or double-click to open the color picker.",
            wraplength=200
        )

        self.addColumnAndBindingToTableToolTip = 'Add a new custom column to the results table with the specified name, keybinding, data type, and color. The keybinding allows quick data entry using keyboard shortcuts during image annotation.'

        self.addColumnAndBindingToTable = ttk.Button(
            self.frame,
            text='Add Column',
            command=lambda: self.addColumnToTable(
                self.columnNameEntry.get(),
                self.keyBindVar.get(),
                self.dataTypeDropdown.get(),
                self.selectedColor
                ),
            bootstyle="success"
            )
        self.addColumnAndBindingToTable.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=3)
        Tooltip(self.addColumnAndBindingToTable, text=self.addColumnAndBindingToTableToolTip , wraplength=300)

        self.removeColumnButton = ttk.Button(
            self.frame,
            text='Remove Column',
            command=self.removeColumnFromTable,
            bootstyle="danger"
        )
        self.removeColumnButton.grid(row=1, column=2, sticky="ew", padx=3, pady=3)
        Tooltip(self.removeColumnButton, text="Remove the last added custom column", wraplength=300)

    def pick_color_ctk(self):
        pick_color = AskColor(initial_color=self.selectedColor)
        color = pick_color.get()
        if color:
            self.selectedColor = color
            self._set_entry_text(color)
            self._apply_color_to_entry(color)

    def _set_entry_text(self, value):
        self.colorEntry.delete(0, tk.END)
        self.colorEntry.insert(0, value)

    def _on_hex_entered(self, event=None):
        candidate = self._normalize_hex(self.colorEntry.get())
        if candidate:
            self.selectedColor = candidate
        # Always reflect the current valid color (reverts invalid input).
        self._set_entry_text(self.selectedColor)
        self._apply_color_to_entry(self.selectedColor)

    def _normalize_hex(self, value):
        value = value.strip()
        if not value:
            return None
        if not value.startswith('#'):
            value = '#' + value
        body = value[1:]
        hex_digits = '0123456789abcdefABCDEF'
        if len(body) == 3 and all(c in hex_digits for c in body):
            body = ''.join(c * 2 for c in body)
        if len(body) == 6 and all(c in hex_digits for c in body):
            return '#' + body.upper()
        return None

    def _apply_color_to_entry(self, color):
        self.colorEntry.configure(
            bg=color,
            fg=self._contrast_color(color),
            insertbackground=self._contrast_color(color)
        )

    def _contrast_color(self, hex_color):
        body = hex_color.lstrip('#')
        r, g, b = int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return "#000000" if luminance > 140 else "#FFFFFF"


    def update_available_keys(self):
        # Pull used keys from centralized context
        used_keys = []
        if hasattr(self.context, "keybinding_specs") and self.context.keybinding_specs:
            used_keys = [spec[2] for spec in self.context.keybinding_specs if spec[2]]

        # Filter out both used and reserved keys (delegates to MeasurementService)
        available_keys = self.measurement_service.available_keys(used_keys)

        # Update dropdown
        self.keyBindDropdown["values"] = available_keys
        current = self.keyBindDropdown.get()
        if current not in available_keys:
            self.keyBindDropdown.set(available_keys[0] if available_keys else "")

        viewer = getattr(self.context, "keyboard_layout_viewer", None)
        if viewer and viewer.window.winfo_exists():
            viewer.update_highlights()


    @handle_errors("addColumnsPanel.addColumnToTable")
    def addColumnToTable(self, colName, keyBind, dataType, color):
        # Add column to results panel
        self.resultsPanel.add_dynamic_column(colName, color, keyBind)

        # Store keybinding and data type so we can give that to the json config file
        self.column_keybindings[colName] = keyBind
        self.column_data_types[colName] = dataType
        self.column_colors[colName] = self.selectedColor

        if not hasattr(self.context, "keybinding_specs") or self.context.keybinding_specs is None:
            self.context.keybinding_specs = []

        self.context.keybinding_specs.append((colName, color, keyBind, dataType))

        # Activate the keybinding live so it works immediately, without needing
        # to save and reload a config first.
        if keyBind:
            manager = self.context.config_manager.get_keybinding_manager(self.context)
            if manager is not None:
                manager.register_single(keyBind, colName, dataType, color)

        self.update_available_keys()



    @handle_errors("addColumnsPanel.removeColumnFromTable")
    def removeColumnFromTable(self) -> None:
        """
        Remove the last dynamic column from the table and clean up associated metadata.
        """
        removed_col_name = self.resultsPanel.remove_last_dynamic_column()

        if removed_col_name:
            removed_key = self.column_keybindings.get(removed_col_name)
            self.column_keybindings.pop(removed_col_name, None)
            self.column_data_types.pop(removed_col_name, None)
            self.column_colors.pop(removed_col_name, None)

            # Deactivate the live keybinding for the removed column.
            if removed_key:
                manager = self.context.config_manager.get_keybinding_manager(self.context)
                if manager is not None:
                    manager.unregister(removed_key)

            # Ensure keybinding_specs exists
            if not hasattr(self.context, "keybinding_specs") or self.context.keybinding_specs is None:
                self.context.keybinding_specs = []

            # Remove from keybinding_specs
            self.context.keybinding_specs = [
                spec for spec in self.context.keybinding_specs if spec[0] != removed_col_name
            ]
        else:
            self.context.status_bar.update("No column was removed.", level="warning")

        self.update_available_keys()



