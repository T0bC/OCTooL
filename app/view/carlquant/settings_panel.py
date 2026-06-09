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


from tkinter import ttk
import tkinter as tk
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors
from app.logic.carlquant import DepthDetectionMethod

class settingsPanel:
    @handle_errors("settingsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_settings")

        self.frame.columnconfigure(0, weight=0)

        # Compact row with Regions and Method
        self.compactFrame = ttk.Frame(self.frame)
        self.compactFrame.grid(row=0, column=0, sticky="ew", pady=(5, 2))
        self.compactFrame.columnconfigure(0, weight=1, uniform="col", minsize=50)
        self.compactFrame.columnconfigure(1, weight=1, uniform="col", minsize=50)

        # Region Count Dropdown (compact)
        self.regionLabel = ttk.Label(self.compactFrame, text="Regions (n):")
        self.regionLabel.grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.regionVar = tk.IntVar(value=6)
        self.regionDropdown = ttk.Combobox(
            self.compactFrame, 
            textvariable=self.regionVar, 
            state="readonly",
            width=1,  # Minimum width, will expand with sticky="ew"
            bootstyle="success"
        )
        self.regionDropdown['values'] = list(range(2, 12, 2))  # 2, 4, 6, 8, 10
        self.regionDropdown.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        
        Tooltip(self.regionDropdown,
                text="Number of regions to extract from the specimen.\n"
                     "Must be an even number for equal split between sound and lesion areas.",
                wraplength=250)

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
            
            # Note: Region dropdown should be locked when data is loaded,
            # so this callback should only fire when no data is present.
            # Refresh results panel to reflect new region count
            results_panel = self.context.get_panel("carl_results")
            if results_panel:
                results_panel.refresh_display()

        self.regionDropdown.bind("<<ComboboxSelected>>", update_region_config)

        # Detection Method Dropdown (compact, same row)
        self.methodLabel = ttk.Label(self.compactFrame, text="Method:")
        self.methodLabel.grid(row=0, column=1, sticky="w", padx=(0, 5))

        # Map display names to internal values (shortened)
        self.method_display_to_value = {
            "Combined": "combined_mean",
            "Knee Point": "knee_point",
            "Inflection": "sigmoid_fit",
            "Shoulder": "sigmoid_shoulder"
        }
        self.method_value_to_display = {v: k for k, v in self.method_display_to_value.items()}

        self.methodVar = tk.StringVar(value="Combined")
        self.methodDropdown = ttk.Combobox(
            self.compactFrame, 
            textvariable=self.methodVar, 
            state="readonly",
            width=1,  # Minimum width, will expand with sticky="ew"
            bootstyle="success"
        )
        self.methodDropdown['values'] = list(self.method_display_to_value.keys())
        self.methodDropdown.grid(row=1, column=1, sticky="ew")
        
        # Updated tooltip with consistent formatting
        method_tooltip = (
            "Lesion depth detection algorithm:\n\n"
            "• Combined (Recommended) – Intelligently combines multiple methods using stability analysis. "
            "Filters out unstable methods (SD > 20px) and uses weighted averaging to preserve natural lesion texture. "
            "Provides the most robust results across different lesion types.\n\n"
            "• Knee Point – Two-line fitting to find the transition point where intensity decay changes slope. "
            "Best for sharp exponential decay patterns. Fits an exponential model and finds the 'elbow' point.\n\n"
            "• Inflection – Sigmoid curve inflection point (50% transition, maximum rate of change). "
            "Ideal for smooth S-shaped intensity transitions.\n\n"
            "• Shoulder – Sigmoid shoulder point (15% from upper asymptote). "
            "Detects the early transition region, useful for identifying the start of lesion penetration."
        )
        
        Tooltip(self.methodDropdown, text=method_tooltip, wraplength=400)

        # Register in context (store internal value)
        self.context.detection_method = self.method_display_to_value[self.methodVar.get()]

        # Update context on change
        def update_detection_method(event):
            display_name = self.methodVar.get()
            self.context.detection_method = self.method_display_to_value[display_name]

        self.methodDropdown.bind("<<ComboboxSelected>>", update_detection_method)

        # Operator and Measurement Entry (aligned with compact frame)
        self.metaFrame = ttk.Frame(self.frame)
        self.metaFrame.grid(row=1, column=0, sticky="ew", pady=(10, 2))
        self.metaFrame.columnconfigure(0, weight=1, uniform="col", minsize=100)
        self.metaFrame.columnconfigure(1, weight=1, uniform="col", minsize=100)

        # Operator label
        self.operatorLabel = ttk.Label(self.metaFrame, text="Operator:")
        self.operatorLabel.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.operatorVar = tk.StringVar()
        self.operatorEntry = ttk.Entry(
            self.metaFrame, 
            textvariable=self.operatorVar,
            width=1,  # Minimum width, will expand with sticky="ew"
            bootstyle="success"
        )
        self.operatorEntry.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        Tooltip(self.operatorEntry, 
                text="Enter the operator's name or initials.\n"
                     "This will be included in the analysis metadata.",
                wraplength=250)

        # Measurement label
        self.measurementLabel = ttk.Label(self.metaFrame, text="Measurement:")
        self.measurementLabel.grid(row=0, column=1, sticky="w", padx=(0, 5))
        
        self.measurementVar = tk.StringVar()
        self.measurementEntry = ttk.Entry(
            self.metaFrame, 
            textvariable=self.measurementVar,
            width=1,  # Minimum width, will expand with sticky="ew"
            bootstyle="success"
        )
        self.measurementEntry.grid(row=1, column=1, sticky="ew")
        Tooltip(self.measurementEntry,
                text="Enter the measurement number or ID.\n"
                     "Must be a numeric value for tracking purposes.",
                wraplength=250)


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

    def lock_region_dropdown(self, lock: bool = True):
        """Lock or unlock the region dropdown.
        
        Args:
            lock: If True, disable the dropdown. If False, enable it.
        """
        if lock:
            self.regionDropdown.config(state="disabled")
        else:
            self.regionDropdown.config(state="readonly")

