# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:16:49 2025

@author: Tobias Meissner
"""

from tkinter import ttk, filedialog
from pathlib import Path
from fnmatch import fnmatch
import os
import re
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors
from carlquant_frames.data_io import DataLoader


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
        # Future: validate folder, load config, trigger analysis pipeline
