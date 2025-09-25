# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 15:14:14 2021

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils.app_context import AppContext
from analyze_frames.load_images_panel import loadImagePanel as loadImage
from analyze_frames.annotate_images_panel import annotatePanel as annotateImages
from analyze_frames.results_panel import resultsPanel as resultsPanel
from analyze_frames.add_columns_panel import addColumnsPanel as addColumnsPanel
from analyze_frames.metadata_panel import metadataPanel as metadataPanel
from analyze_frames.config_manager import ConfigManager
from utils.status_bar import StatusBar
from utils.error_handler import handle_errors

@handle_errors("analyzingTab.addContent")
def addContent(self, frame):
    self.analyzingTabFrame = frame
    self.context = self.context
    self.context.root = self.analyzingTabFrame
    self.context.config_manager = ConfigManager()
    self.attach_status_bar(self.context)

    # Configure columns
    self.analyzingTabFrame.columnconfigure(0, minsize=50, weight=0)
    self.analyzingTabFrame.columnconfigure(1, weight=1, minsize=800)
    self.analyzingTabFrame.rowconfigure(2, weight=0)  # Status bar

    # Configure rows
    self.analyzingTabFrame.rowconfigure(0, weight=0)  # Controls and results
    self.analyzingTabFrame.rowconfigure(1, weight=1)  # Image viewer

    # Left-side controls stacked vertically
    self.controlsContainer = ttk.Frame(self.analyzingTabFrame)
    self.controlsContainer.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

    self.loadFrame = ttk.LabelFrame(self.controlsContainer, text='Load Images', relief=tk.RIDGE)
    self.loadFrame.pack(fill="x", pady=(0, 2))
    self.context.register_frame("load", self.loadFrame)


    self.addColumnsFrame = ttk.LabelFrame(self.controlsContainer, text='Add Columns', relief=tk.RIDGE)
    self.addColumnsFrame.pack(fill="x", pady=2)
    self.context.register_frame("add_columns", self.addColumnsFrame)

    self.metadataFrame = ttk.LabelFrame(self.controlsContainer, text='Add Metadata', relief=tk.RIDGE)
    self.metadataFrame.pack(fill="x", pady=(2, 0))
    self.context.register_frame("metadata", self.metadataFrame)

    # Right-side results frame
    self.resultsFrame = ttk.LabelFrame(self.analyzingTabFrame, text='Results', relief=tk.RIDGE)
    self.resultsFrame.grid(row=0, column=1, sticky="nsew", padx=(10, 5), pady=5)
    self.context.register_frame("results", self.resultsFrame)

    # Image Viewer Frame (dominates vertical space)
    self.imgFrame = ttk.LabelFrame(self.analyzingTabFrame, text='Data Viewer', relief=tk.RIDGE)
    self.imgFrame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("image", self.imgFrame)

# =============================================================================
#     # Attach to shared status bar (fallback to local instance if missing)
#     status_bar = getattr(self, "statusBar", None)
#     if status_bar is None:
#         status_bar = StatusBar(self.analyzingTabFrame)
#         status_bar.frame.grid(row=2, column=0, columnspan=2, sticky="ew")
#         self.statusBar = status_bar
#     elif status_bar.parent is self.analyzingTabFrame:
#         status_bar.frame.grid(row=2, column=0, columnspan=2, sticky="ew")
#
#     status_bar.attach_context(self.context)
# =============================================================================


    # Create panels and register them
    self.loadPanel = loadImage(self.context)
    self.context.register_panel("load", self.loadPanel)

    self.resultsPanel = resultsPanel(self.context)
    self.context.register_panel("results", self.resultsPanel)

    self.addColumnsPanel = addColumnsPanel(self.context)
    self.context.register_panel("add_columns", self.addColumnsPanel)

    self.metadataPanel = metadataPanel(self.context)
    self.context.register_panel("metadata", self.metadataPanel)
    self.metadataPanel.setup()

    self.imgPanel = annotateImages(self.context)
    self.context.register_panel("image", self.imgPanel)
