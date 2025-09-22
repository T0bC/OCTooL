# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 11:42:25 2025

@author: meissnerto
"""

import tkinter as tk
from tkinter import ttk
import octFunctions as octF
from toolTip import Tooltip
from errorHandler import handle_errors
from tkinter import colorchooser
import customtkinter as ctk
from CTkColorPicker import AskColor
import string

class addColumnsPanel:
    @handle_errors("error in addColumnsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("add_columns")
        self.resultsPanel = context.get_panel("results")

        self.column_keybindings = {}
        self.column_data_types = {}
        self.column_colors = {}
        self.selectedColor = "#FFFFFF"

        self.columnNameToolTip = 'Enter the name of the column. e.g GapInterface.'

        self.columnNameEntry = ttk.Entry(self.frame, width=15, bootstyle="success")
        self.columnNameEntry.insert(0, 'GAP')
        self.columnNameEntry.grid(row=3, column=0, sticky="ew", pady=3)
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
        self.keyBindDropdown.grid(row=3, column=1, sticky="ew", pady=3)
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
        self.dataTypeDropdown.grid(row=3, column=2, sticky="ew", pady=3)
        Tooltip(self.dataTypeDropdown, text=self.dataTypeToolTip, wraplength=200)

        self.colorPickerButton = tk.Button(
            self.frame,
            text='Pick Color',
            command=self.pick_color_ctk,
            bg=self.selectedColor,
            fg='black',
            width=12
        )
        self.colorPickerButton.grid(row=3, column=3, sticky=tk.W, pady=3)
        Tooltip(self.colorPickerButton, text="Choose a color for this column (hex format)", wraplength=200)

        self.addColumnAndBindingToTableToolTip = 'XXX Do a good tooltip here'

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
        self.addColumnAndBindingToTable.grid(row=4, column=0, sticky="ew" + tk.W, pady=3)
        Tooltip(self.addColumnAndBindingToTable, text=self.addColumnAndBindingToTableToolTip , wraplength=300)

        self.removeColumnButton = ttk.Button(
            self.frame,
            text='Remove Column',
            command=self.removeColumnFromTable,
            bootstyle="danger"
        )
        self.removeColumnButton.grid(row=4, column=2, sticky="ew", pady=3)
        Tooltip(self.removeColumnButton, text="Remove the last added custom column", wraplength=300)

    def pick_color_ctk(self):
        # Disable canvas events
        pick_color = AskColor()
        color = pick_color.get()
        if color:
            self.selectedColor = color
            self.colorPickerButton.config(
                text=self.selectedColor,
                bg=self.selectedColor,
                fg='black'
            )

    def update_available_keys(self):
        reserved_keys = {'f', 'h'}  # Keys to block
        all_keys = list(string.ascii_lowercase)
        used_keys = [spec[2] for spec in getattr(self.resultsPanel, "dynamic_col_specs_full", [])]

        # Filter out both used and reserved keys
        available_keys = [k for k in all_keys if k not in used_keys and k not in reserved_keys]

        self.keyBindDropdown["values"] = available_keys
        if available_keys:
            self.keyBindDropdown.set(available_keys[0])
        else:
            self.keyBindDropdown.set("")


    @handle_errors("addColumnsPanel.addColumnToTable")
    def addColumnToTable(self, colName, keyBind, dataType, color):
        # Add column to results panel
        self.resultsPanel.add_dynamic_column(colName, color, keyBind)
        self.update_available_keys()

        # Store keybinding and data type so we can give that to the json config file
        self.column_keybindings[colName] = keyBind
        self.column_data_types[colName] = dataType
        self.column_colors[colName] = self.selectedColor

    @handle_errors("addColumnsPanel.removeColumnFromTable")
    def removeColumnFromTable(self) -> None:
        """
        Remove the last dynamic column from the table and clean up associated metadata.
        """
        removed_col_name = self.resultsPanel.remove_last_dynamic_column()

        if removed_col_name:
            self.column_keybindings.pop(removed_col_name, None)
            self.column_data_types.pop(removed_col_name, None)
            self.column_colors.pop(removed_col_name, None)
        else:
            self.context.status_bar.update("No column was removed.", level="warning")

