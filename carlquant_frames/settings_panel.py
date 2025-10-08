# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:23:35 2025

@author: Tobias Meissner
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

        self.regionVar = tk.IntVar(value=6)
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


        self.metaLabel = ttk.Label(self.frame, text="Operator and Measurement:")
        self.metaLabel.grid(row=2, column=0, columnspan=2 , sticky="w", pady=(10, 2))

        # Operator Entry
        self.metaFrame = ttk.Frame(self.frame)
        self.metaFrame.grid(row=3, column=0, sticky="w", pady=2)

        self.operatorVar = tk.StringVar()
        self.operatorEntry = ttk.Entry(self.metaFrame, textvariable=self.operatorVar, width=11)
        self.operatorEntry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.measurementVar = tk.StringVar()
        self.measurementEntry = ttk.Entry(self.metaFrame, textvariable=self.measurementVar, width=11)
        self.measurementEntry.grid(row=0, column=1, sticky="ew")


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
        
        # Display Options
        self.displayLabel = ttk.Label(self.frame, text="Display Options:")
        self.displayLabel.grid(row=4, column=0, sticky="w", pady=(10, 2))
        
        # Show Surface Peaks checkbox
        self.showSurfacePeaksVar = tk.BooleanVar(value=False)
        self.showSurfacePeaksCheck = ttk.Checkbutton(
            self.frame, 
            text="Show Surface Peaks",
            variable=self.showSurfacePeaksVar
        )
        self.showSurfacePeaksCheck.grid(row=5, column=0, sticky="w", pady=2)
        
        # Show Fitted Curve checkbox
        self.showFittedCurveVar = tk.BooleanVar(value=True)
        self.showFittedCurveCheck = ttk.Checkbutton(
            self.frame,
            text="Show Fitted Curve (Primary)",
            variable=self.showFittedCurveVar
        )
        self.showFittedCurveCheck.grid(row=6, column=0, sticky="w", pady=2)
        
        # Show Reference Curve checkbox
        self.showReferenceCurveVar = tk.BooleanVar(value=False)
        self.showReferenceCurveCheck = ttk.Checkbutton(
            self.frame,
            text="Show Reference Curve",
            variable=self.showReferenceCurveVar
        )
        self.showReferenceCurveCheck.grid(row=7, column=0, sticky="w", pady=2)
        
        # Register display options in context
        self.context.display_options = {
            "show_surface_peaks": self.showSurfacePeaksVar,
            "show_fitted_curve": self.showFittedCurveVar,
            "show_reference_curve": self.showReferenceCurveVar
        }

