# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 09:54:49 2025

@author: Tobias Meissner
"""

from tkinter import ttk, filedialog
from pathlib import Path
import os
from concurrent import futures
from fnmatch import fnmatch
import re
import json
import csv
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors
from app.view.annolyze.data_io import DataLoader
from app.view.shared import dialogs

class loadImagePanel:
    @handle_errors("loadImagePanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("load")
        self.config_manager = context.config_manager


        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        # %% LoadImages Button
        self.pickFolderToolTip = 'Choose a folder that contains OCT Image(s). Supported formats are [png, jpg, tif, tiff]'
        self.pickFolderBtn = ttk.Button(
            self.frame,
            text='Select Folder',
            #width=14,
            command=self.globalPickerThread,
            bootstyle="primary"
        )
        self.pickFolderBtn.grid(row=0, column=0, sticky="ew", pady=3, padx=3)
        Tooltip(self.pickFolderBtn, text=self.pickFolderToolTip, wraplength=200)

        # %% Load Config Button
        self.loadConfigToolTip = 'Load a config file for layout and key bindings'
        self.loadConfig = ttk.Button(
            self.frame,
            text='Load Config',
            #width=14,
            command=self.loadConfigToTable,
            bootstyle="primary"
        )
        self.loadConfig.grid(row=0, column=1, sticky="ew", pady=3, padx=3  )
        Tooltip(self.loadConfig, text=self.loadConfigToolTip, wraplength=200)

    # %% Load Config Function
    @handle_errors("loadImagePanel loadConfig failed.")
    def loadConfigToTable(self):
        config = self.config_manager.load_config()
        if config and self.context:
            results_panel = self.context.get_panel("results")
            if results_panel:
                results_panel.reset_table()
            self.config_manager.apply_config(config, self.context)
        else:
            dialogs.show_error(self.root, "Error", "Missing panel references in context")


    # %% Threaded Image Picker
    def globalPickerThread(self):
        self.running = 0
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.getImagePaths)


    @handle_errors("Error in getImagePaths")
    def getImagePaths(self):
        global dir

        selected_folder = filedialog.askdirectory(
            initialdir=dir,
            title='Select the Folder Containing Your OCT Images!'
        )
        if not selected_folder:
            self.context.status_bar.update("No folder selected.", level="warning")
            return

        self.folderPath = Path(selected_folder)
        self.context.image_folder = self.folderPath
        self.context.sample_name = self.folderPath.name

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
            self.context.safe_status_update("No suitable image files found in the selected folder.", level="error")
            return

        self.tmpFileList = [{
            'name': os.path.basename(path),
            'first': True,
            'last': False,
            'status': 'new',
            'path': path
        } for path in tmpPathList]

        self.context.image_list = self.tmpFileList

        # All work below mutates Tkinter widgets and MUST run on the main
        # thread. getImagePaths runs in a worker thread, so calling Tk widget
        # methods directly here would trigger a non-catchable Tcl crash (the
        # app would die silently). Marshal the UI work back to the main loop.
        self.root.after(0, self._on_images_loaded)

    @handle_errors("Error displaying loaded images")
    def _on_images_loaded(self):
        # Display first image
        annotate_panel = self.context.get_panel("anno_image")
        if annotate_panel:
            annotate_panel.display_image()

        # Load config, annotations, results using DataLoader
        loader = DataLoader(self.folderPath, self.context)
        loader.load_config()
        loader.load_annotations()
        loader.load_results()

