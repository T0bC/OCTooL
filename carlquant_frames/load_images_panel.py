# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:16:49 2025

@author: meissnerto
"""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from fnmatch import fnmatch
import os
import re
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors
from carlquant_frames.data_io import DataLoader
from carlquant_frames.carl_quant_core import run_carl_quant
import threading


class loadImagePanel:
    @handle_errors("loadImagePanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_load")

        self.frame.columnconfigure(0, weight=1)

        # Select Folder Button
        self.selectFolderTooltip = 'Choose a folder containing CarlQuant data files (e.g., CSV, JSON, etc.)'
        self.selectFolderBtn = ttk.Button(
            self.frame,
            text='Select Folder',
            command=self.selectFolder,
            bootstyle="primary"
        )
        self.selectFolderBtn.grid(row=0, column=0, sticky="ew", pady=3)
        Tooltip(self.selectFolderBtn, text=self.selectFolderTooltip, wraplength=200)

        # Start Analyzing Button
        self.startAnalyzingTooltip = 'Begin analyzing the selected CarlQuant data folder'
        self.startAnalyzingBtn = ttk.Button(
            self.frame,
            text='Start Analyzing',
            command=self.startAnalyzing,
            bootstyle="success"
        )
        self.startAnalyzingBtn.grid(row=1, column=0, sticky="ew", pady=3)
        Tooltip(self.startAnalyzingBtn, text=self.startAnalyzingTooltip, wraplength=200)


    @handle_errors("loadImagePanel.selectFolder")
    def selectFolder(self):
        folder_path = filedialog.askdirectory(title="Select CarlQuant Data Folder")
        if not folder_path:
            self.context.status_bar.update("No folder selected.", level="warning")
            return

        root = Path(folder_path)
        self.context.path_to_carlquant_data = root
        self.context.specimen_data = DataLoader.find_image_stacks(root)

        specimen_panel = self.context.get_panel("carl_specimen")
        rows = []
        for specimen_id, specimen in self.context.specimen_data.items():
            rows.append([
                specimen.specimen_id,
                specimen.slices,
                specimen.regions,
                specimen.status
            ])
        specimen_panel.sheet.set_sheet_data(rows)
        self.context.status_bar.update(f"Found {len(rows)} specimen(s).", level="info")


    @handle_errors("loadImagePanel.startAnalyzing")
    def startAnalyzing(self):
        print("Start Analyzing triggered")

        # Ensure region config exists
        if not hasattr(self.context, "region_config"):
            self.context.region_config = {"sound": 3, "lesion": 3}

        # Ensure specimen data exists and is non-empty
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            self.context.status_bar.update("No specimens loaded. Please select a folder first.", level="warning")
            return

        # Add lock for thread safety
        if not hasattr(self.context, "result_lock"):
            self.context.result_lock = threading.Lock()

        metadata = getattr(self.context, "analysis_metadata", {})
        operator = metadata.get("operator", "").strip()
        measurement = metadata.get("measurement", None)

        if not operator or measurement is None:
            self.prompt_for_metadata()
            return

        specimens_with_prior_runs = [
            s for s in self.context.specimen_data.values()
            if s.previous_runs and not hasattr(s, "analysis_choice")
        ]

        if specimens_with_prior_runs:
            self.prompt_overwrite_or_new(specimens_with_prior_runs)
            return

        run_carl_quant(self.context)


    def prompt_for_metadata(self):
        popup = tk.Toplevel(self.root)
        # set position of the popup to the center of the main UI
        popup.update_idletasks()

        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()

        pos_x = main_x + (main_width // 2) - (popup_width // 2)
        pos_y = main_y + (main_height // 2) - (popup_height // 2)

        popup.geometry(f"+{pos_x}+{pos_y}")

        popup.title("Enter Analysis Metadata")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="Operator Initials:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        operator_var = tk.StringVar()
        tk.Entry(popup, textvariable=operator_var).grid(row=0, column=1, padx=10, pady=5)

        tk.Label(popup, text="Measurement Number:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        measurement_var = tk.StringVar()
        tk.Entry(popup, textvariable=measurement_var).grid(row=1, column=1, padx=10, pady=5)

        def submit():
            operator = operator_var.get().strip()
            try:
                measurement = int(measurement_var.get())
            except ValueError:
                self.context.status_bar.update("Measurement must be an integer.", level="warning")
                return

            self.context.analysis_metadata = {
                "operator": operator,
                "measurement": measurement
            }

            popup.destroy()
            self.startAnalyzing()  # Retry analysis now that metadata is set

        ttk.Button(popup, text="Submit", command=submit).grid(row=2, column=0, columnspan=2, pady=10)

    def prompt_overwrite_or_new(self, specimens_with_prior_runs):
        popup = tk.Toplevel(self.root)

        # set position of the popup to the center of the main UI
        popup.update_idletasks()

        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()

        pos_x = main_x + (main_width // 2) - (popup_width // 2)
        pos_y = main_y + (main_height // 2) - (popup_height // 2)

        popup.geometry(f"+{pos_x}+{pos_y}")

        popup.title("Existing Results Detected")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="Some specimens already have saved results.\nChoose how to proceed:", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, pady=10)

        self.specimen_choices = {}

        for i, specimen in enumerate(specimens_with_prior_runs, start=1):
            tk.Label(popup, text=f"{specimen.specimen_id}").grid(row=i, column=0, sticky="w", padx=10)

            existing = ", ".join([f.name for f in specimen.previous_runs])
            tk.Label(popup, text=f"Existing: {existing}", wraplength=200).grid(row=i, column=1, sticky="w")

            choice_var = tk.StringVar(value="new")
            self.specimen_choices[specimen.specimen_id] = choice_var

            ttk.Combobox(popup, textvariable=choice_var, state="readonly",
                         values=["overwrite", "new", "skip"], width=10).grid(row=i, column=2, padx=5)

        def submit():
            for specimen in specimens_with_prior_runs:
                choice = self.specimen_choices[specimen.specimen_id].get()
                specimen.analysis_choice = choice  # Inject into specimen for later use

            popup.destroy()
            self.startAnalyzing()  # Retry analysis with updated choices

        ttk.Button(popup, text="Confirm", command=submit).grid(row=len(specimens_with_prior_runs)+1, column=0, columnspan=3, pady=10)

