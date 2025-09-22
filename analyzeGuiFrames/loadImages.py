# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 09:54:49 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from toolTip import Tooltip
from pathlib import Path
import os
from concurrent import futures
from fnmatch import fnmatch
from errorHandler import handle_errors
import re
import json
import csv

class loadImagePanel:
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("load")
        self.config_manager = context.config_manager

        # %% LoadImages Button
        self.pickFolderToolTip = 'Choose a folder that contains OCT Image(s). Supported formats are [png, jpg, tif, tiff]'
        self.pickFolderBtn = ttk.Button(
            self.frame,
            text='Select Folder',
            width=14,
            command=self.globalPickerThread,
            bootstyle="primary"
        )
        self.pickFolderBtn.grid(row=0, column=0, sticky="ew", pady=3)
        Tooltip(self.pickFolderBtn, text=self.pickFolderToolTip, wraplength=200)

        # %% Load Config Button
        self.loadConfigToolTip = 'Load a config file for layout and key bindings'
        self.loadConfig = ttk.Button(
            self.frame,
            text='Load Config',
            width=14,
            command=self.loadConfigToTable,
            bootstyle="primary"
        )
        self.loadConfig.grid(row=0, column=1, sticky="ew", pady=3)
        Tooltip(self.loadConfig, text=self.loadConfigToolTip, wraplength=200)

    # %% Load Config Function
    @handle_errors("loadImagePanel loadConfig failed.")
    def loadConfigToTable(self):
        config = self.config_manager.load_config()
        if config:

            if all([config, self.context]):
                self.config_manager.apply_config(config, self.context)

            else:
                messagebox.showerror("Error", "Missing panel references in context")

    # %% Threaded Image Picker
    def globalPickerThread(self):
        self.running = 0
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.getImagePaths)


    @handle_errors("Error in getImagePaths")
    def getImagePaths(self):
        global dir

        # Ask user to select folder
        selected_folder = filedialog.askdirectory(
            initialdir=dir,
            title='Select the Folder Containing Your OCT Images!'
        )
        if not selected_folder:
            self.context.status_bar.update("No folder selected.", level="warning")

            return

        self.folderPath = Path(selected_folder)
        self.context.image_folder = self.folderPath

        config_path = self.folderPath / "config.json"
        if config_path.exists():
            config = self.context.config_manager.load_config(str(config_path))
            if config:
                self.context.config_manager.apply_config(config, self.context)
                self.context.status_bar.update(f"Config loaded from: {config_path}", level="success")

            else:
                self.context.status_bar.update("Config file found but failed to load.", level="error")
        else:
            self.context.status_bar.update("No config file found in folder.", level="warning")

        # Collect image files
        image_extensions = ['*.jpg', '*.png', '*.tif', '*.tiff']
        def natural_key(path):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', path.name)]

        tmpPathList = sorted(
            [file for file in self.folderPath.iterdir()
             if file.is_file() and any(fnmatch(file.name.lower(), ext) for ext in image_extensions)],
            key=natural_key
        )

        if not tmpPathList:
            self.context.status_bar.update("No suitable image files found in the selected folder.", level="error")
            raise ValueError("No suitable image files found in the selected folder.")

        self.tmpFileList = [{
            'name': os.path.basename(path),
            'first': True,
            'last': False,
            'status': 'new',
            'path': path
        } for path in tmpPathList]

        self.context.image_list = self.tmpFileList

        # Display first image
        annotate_panel = self.context.get_panel("image")
        if annotate_panel:
            annotate_panel.display_image()

            # Try to load annotations
            annotation_file = self.folderPath / "annotations" / "annotations.json"
            if annotation_file.exists():
                try:
                    with open(annotation_file, "r", encoding="utf-8") as f:
                        annotations = json.load(f)
                    self.context.loaded_annotations = annotations
                    annotate_panel.load_annotations(annotations)
                    self.context.status_bar.update(f"Loaded annotations from: {annotation_file}", level="success")
                except Exception as e:
                    self.context.status_bar.update(f"Failed to load annotations: {e}", level="error")
            else:
                self.context.status_bar.update("No annotations found in folder.", level="warning")
            self.try_load_results()



    def try_load_annotations(self):
        annotation_file = self.folderPath / "annotations" / "annotations.json"
        if annotation_file.exists():
            with open(annotation_file, "r", encoding="utf-8") as f:
                annotations = json.load(f)
            self.context.loaded_annotations = annotations
            self.context.status_bar.update(f"Loaded annotations from: {annotation_file}", level="success")
        else:
            self.context.status_bar.update("No annotations found in folder.", level="warning")

    def try_load_results(self):
        results_file = self.folderPath / "results" / "measurements.csv"
        if results_file.exists():
            try:
                with open(results_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)

                if not rows:
                    self.context.status_bar.update("Results file is empty.", level="warning")
                    return

                headers = rows[0]
                data = rows[1:]

                results_panel = self.context.get_panel("results")
                if results_panel:
                    results_panel.sheet.headers(headers)
                    results_panel.sheet.set_sheet_data(data)
                    results_panel.sheet.refresh()
                    results_panel._set_column_widths()
                    self.context.status_bar.update(f"Results loaded from: {results_file}", level="success")
            except Exception as e:
                self.context.status_bar.update(f"Failed to load results: {e}", level="error")
        else:
            self.context.status_bar.update("No results file found in folder.", level="warning")
