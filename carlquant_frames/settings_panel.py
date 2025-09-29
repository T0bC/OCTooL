# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:23:35 2025

@author: meissnerto
"""

from tkinter import ttk
import tkinter as tk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors

class settingsPanel:
    @handle_errors("settingsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_settings")

        self.frame.columnconfigure(0, weight=1)

        # Region Count Dropdown
        self.regionLabel = ttk.Label(self.frame, text="Number of Regions:")
        self.regionLabel.grid(row=0, column=0, sticky="w", pady=(5, 2))

        self.regionVar = tk.IntVar(value=3)
        self.regionDropdown = ttk.Combobox(self.frame, textvariable=self.regionVar, state="readonly")
        self.regionDropdown['values'] = list(range(2, 10))  # 2 to 9 regions
        self.regionDropdown.grid(row=1, column=0, sticky="ew", pady=2)

        # Register in context
        self.context.region_config = {
            "sound": self.regionVar.get(),
            "lesion": self.regionVar.get()
        }

        # Update context on change
        def update_region_config(event):
            count = self.regionVar.get()
            self.context.region_config["sound"] = count
            self.context.region_config["lesion"] = count

        self.regionDropdown.bind("<<ComboboxSelected>>", update_region_config)


        # Dummy Dropdown
        self.dropdownLabel = ttk.Label(self.frame, text="Select Mode:")
        self.dropdownLabel.grid(row=2, column=0, sticky="w", pady=(10, 2))

        self.modeVar = tk.StringVar()
        self.dropdown = ttk.Combobox(self.frame, textvariable=self.modeVar, state="readonly")
        self.dropdown['values'] = ["Mode 1", "Mode 2", "Mode 3"]
        self.dropdown.current(0)
        self.dropdown.grid(row=3, column=0, sticky="ew", pady=2)

        # Operator Entry
        self.operatorLabel = ttk.Label(self.frame, text="Operator Initials:")
        self.operatorLabel.grid(row=4, column=0, sticky="w", pady=(10, 2))

        self.operatorVar = tk.StringVar()
        self.operatorEntry = ttk.Entry(self.frame, textvariable=self.operatorVar)
        self.operatorEntry.grid(row=5, column=0, sticky="ew", pady=2)

        # Measurement Entry (Integer only)
        self.measurementLabel = ttk.Label(self.frame, text="Measurement Number:")
        self.measurementLabel.grid(row=6, column=0, sticky="w", pady=(10, 2))

        self.measurementVar = tk.StringVar()
        self.measurementEntry = ttk.Entry(self.frame, textvariable=self.measurementVar)
        self.measurementEntry.grid(row=7, column=0, sticky="ew", pady=2)

        # Register metadata in context
        def update_metadata(*args):
            operator = self.operatorVar.get().strip()
            try:
                measurement = int(self.measurementVar.get())
            except ValueError:
                measurement = None

            self.context.analysis_metadata = {
                "operator": operator,
                "measurement": measurement
            }

        self.operatorVar.trace_add("write", update_metadata)
        self.measurementVar.trace_add("write", update_metadata)

