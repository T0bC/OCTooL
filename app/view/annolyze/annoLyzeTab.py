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


import tkinter as tk
from tkinter import ttk
from app.view.shared.error_handler import handle_errors
from app.view.annolyze.load_images_panel import loadImagePanel as loadImage
from app.view.annolyze.annotate_images_panel import annotatePanel as annotateImages
from app.view.annolyze.results_panel import resultsPanel as resultsPanel
from app.view.annolyze.add_columns_panel import addColumnsPanel as addColumnsPanel
from app.view.annolyze.metadata_panel import metadataPanel as metadataPanel
from app.view.annolyze.config_manager import ConfigManager


@handle_errors("annoLyzeTab.addContent")
def addContent(self, frame):
    self.annoLyzeTabFrame = frame
    self.context.root = self.annoLyzeTabFrame
    self.context.config_manager = ConfigManager()
    self.attach_status_bar(self.context)

    # Configure columns
    self.annoLyzeTabFrame.columnconfigure(0, minsize=50, weight=0)
    self.annoLyzeTabFrame.columnconfigure(1, weight=1, minsize=800)
    self.annoLyzeTabFrame.rowconfigure(2, weight=0)  # Status bar

    # Configure rows
    self.annoLyzeTabFrame.rowconfigure(0, weight=0)  # Controls and results
    self.annoLyzeTabFrame.rowconfigure(1, weight=1)  # Image viewer

    # Left-side controls stacked vertically
    self.controlsContainer = ttk.Frame(self.annoLyzeTabFrame)
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
    self.resultsFrame = ttk.LabelFrame(self.annoLyzeTabFrame, text='Results', relief=tk.RIDGE)
    self.resultsFrame.grid(row=0, column=1, sticky="nsew", padx=(10, 5), pady=5)
    self.context.register_frame("results", self.resultsFrame)

    # Image Viewer Frame (dominates vertical space)
    self.imgFrame = ttk.LabelFrame(self.annoLyzeTabFrame, text='Image Viewer', relief=tk.RIDGE)
    self.imgFrame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("anno_image", self.imgFrame)


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
    self.context.register_panel("anno_image", self.imgPanel)
