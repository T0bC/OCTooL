# -*- coding: utf-8 -*-
"""
CarlQuant Tab.

Composes all CarlQuant sub-panels (load images, settings, specimen list, results
sheet, and image viewer) into a single ttk.Frame tab. Uses a PanedWindow layout
so the specimen table and results table share horizontal space.

Key contents:
- addContent: Lays out all CarlQuant sub-panels and registers frames in AppContext.
- attach_status_bar: Connects the shared status bar to the tab.

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
from app.view.carlquant.load_images_panel import loadImagePanel as loadImage
from app.view.carlquant.settings_panel import settingsPanel as settingsPanel
from app.view.carlquant.specimen_panel import specimenPanel as specimenPanel
from app.view.carlquant.results_panel import resultsPanel as resultsPanel
from app.view.carlquant.image_viewer_panel import image_viewer_panel as imagePanel

@handle_errors("carlQuantTab.addContent")
def addContent(self, frame):
    self.carlQuantTabFrame = frame
    self.context.root = self.carlQuantTabFrame

    # Layout configuration
    # Column 0 → Controls container (holds Load Data + Settings)
    self.carlQuantTabFrame.columnconfigure(0, minsize=50, weight=0)
    # Column 1 → Left pane of PanedWindow (Specimen table)
    self.carlQuantTabFrame.columnconfigure(1, weight=1, minsize=400)
    # Column 2 → Right pane of PanedWindow (Results table)
    self.carlQuantTabFrame.columnconfigure(2, weight=1, minsize=400)
    # Row 0 → Top row (Controls container + PanedWindow with Specimen + Results)
    self.carlQuantTabFrame.rowconfigure(0, weight=0)
    # Row 1 → Middle row (Data Viewer frame spanning all columns)
    self.carlQuantTabFrame.rowconfigure(1, weight=1)
    # Row 2 → Bottom row (Status bar, if present)
    self.carlQuantTabFrame.rowconfigure(2, weight=0)


    # Controls container
    self.controlsContainer = ttk.Frame(self.carlQuantTabFrame)
    self.controlsContainer.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

    # Load Frame
    self.loadFrame = ttk.LabelFrame(self.controlsContainer, text='Load Data', relief=tk.RIDGE)
    self.loadFrame.pack(fill="x", pady=(0, 2))
    self.context.register_frame("carl_load", self.loadFrame)

    # Settings Frame
    self.settingsFrame = ttk.LabelFrame(self.controlsContainer, text='Settings', relief=tk.RIDGE)
    self.settingsFrame.pack(fill="x", pady=(0, 2))
    self.context.register_frame("carl_settings", self.settingsFrame)

    # PanedWindow for Specimen and Results
    # Styled to match dark theme
    self.tablePane = tk.PanedWindow(
        self.carlQuantTabFrame, 
        orient=tk.HORIZONTAL,
        sashwidth=6,
        sashpad=2,
        bd=0,  # Remove border
        bg="#2b2b2b",  # Dark background to match theme
        sashrelief=tk.FLAT,  # Flat sash for modern look
        relief=tk.FLAT  # Flat relief for the pane itself
    )
    self.tablePane.grid(row=0, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)

    # Specimen Frame
    self.specimenFrame = ttk.LabelFrame(self.tablePane, text='Specimen', relief=tk.RIDGE)
    self.context.register_frame("carl_specimen", self.specimenFrame)
    self.tablePane.add(self.specimenFrame)

    # Results Frame
    self.resultsFrame = ttk.LabelFrame(self.tablePane, text='Results', relief=tk.RIDGE)
    self.context.register_frame("carl_results", self.resultsFrame)
    self.tablePane.add(self.resultsFrame)
    
    # Set initial pane proportions (30% specimen, 70% results)
    self.tablePane.after(100, lambda: self.tablePane.sash_place(0, 400, 0))

    # Viewer Frame
    self.viewerFrame = ttk.LabelFrame(self.carlQuantTabFrame, text='Image Viewer', relief=tk.RIDGE)
    self.viewerFrame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("carl_image", self.viewerFrame)

    # Status bar
    self.attach_status_bar(self.context)

    # Instantiate and register panels
    self.loadPanel = loadImage(self.context)
    self.context.register_panel("carl_load", self.loadPanel)

    self.settingsPanel = settingsPanel(self.context)
    self.context.register_panel("carl_settings", self.settingsPanel)

    self.specimenPanel = specimenPanel(self.context)
    self.context.register_panel("carl_specimen", self.specimenPanel)

    self.resultsPanel = resultsPanel(self.context)
    self.context.register_panel("carl_results", self.resultsPanel)

    self.imagePanel = imagePanel(self.context)
    self.context.register_panel("carl_image", self.imagePanel)


