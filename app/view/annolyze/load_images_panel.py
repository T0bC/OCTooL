# -*- coding: utf-8 -*-
"""
AnnoLyze Load Images Panel.

Folder picker and image loader for the AnnoLyze tab. Discovers PNG/JPG/TIFF
image stacks, populates the annotation canvas, and loads any existing
annotations, results, or config files from the sample folder.

Key contents:
- loadImagePanel: Panel with Select Folder and Load Config buttons.
- globalPickerThread: Background thread for recursive image discovery.
- load_images: Populates the canvas and results sheet from discovered files.
- DataLoader integration: Loads config, annotations, and results on demand.

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
        # Start from a clean slate: a newly loaded folder must not inherit the
        # previous folder's config, annotations or results.
        self._reset_state()

        # Display first image
        annotate_panel = self.context.get_panel("anno_image")
        if annotate_panel:
            annotate_panel.display_image()

        # Load config, annotations, results using DataLoader
        loader = DataLoader(self.folderPath, self.context)
        loader.load_config()
        loader.load_annotations()
        loader.load_results()

    def _reset_state(self):
        """Clear config, annotations and results from any previously loaded folder."""
        # Reset results table and dynamic columns
        results_panel = self.context.get_panel("results", required=False)
        if results_panel:
            results_panel.reset_table()

        # Clear annotations and remove any keybindings from a previous config
        annotate_panel = self.context.get_panel("anno_image", required=False)
        if annotate_panel:
            annotate_panel.slice_annotations.clear()

        # Deactivate all live keybindings via the shared manager. Fall back to
        # spec-based unbinding if the manager hasn't been created yet.
        manager = getattr(self.context, "keybinding_manager", None)
        if manager is not None:
            manager.clear_all()
        elif annotate_panel is not None:
            window = getattr(annotate_panel, "window", None)
            if window is not None:
                for spec in getattr(self.context, "keybinding_specs", None) or []:
                    key = spec[2]
                    try:
                        window.unbind(f"<{key.lower()}>")
                    except Exception:
                        pass

        # Reset the add-columns panel's keybinding/data-type bookkeeping
        add_columns_panel = self.context.get_panel("add_columns", required=False)
        if add_columns_panel:
            for attr in ("column_keybindings", "column_data_types", "column_colors"):
                mapping = getattr(add_columns_panel, attr, None)
                if isinstance(mapping, dict):
                    mapping.clear()

        # Drop cached config/annotations/keybindings so stale state can't leak through
        self.context.loaded_annotations = None
        self.context.keybinding_specs = []
        if hasattr(self.config_manager, "active_config"):
            self.config_manager.active_config = self.config_manager.default_config

        # Refresh keyboard-layout highlights and available-key dropdown
        viewer = getattr(self.context, "keyboard_layout_viewer", None)
        if viewer is not None and getattr(viewer, "window", None) is not None:
            try:
                if viewer.window.winfo_exists():
                    viewer.update_highlights()
            except Exception:
                pass
        if add_columns_panel and hasattr(add_columns_panel, "update_available_keys"):
            add_columns_panel.update_available_keys()

