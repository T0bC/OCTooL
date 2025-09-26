# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:16:49 2025

@author: meissnerto
"""

from tkinter import ttk, filedialog
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors

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
        if folder_path:
            self.context.path_to_carlquant_data = folder_path
            print(f"Selected CarlQuant folder: {folder_path}")
            # Future: trigger parsing or validation logic here

    @handle_errors("loadImagePanel.startAnalyzing")
    def startAnalyzing(self):
        print("Start Analyzing triggered")
        # Future: validate folder, load config, trigger analysis pipeline
