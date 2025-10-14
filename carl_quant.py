# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 13:58:13 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils.error_handler import handle_errors
from carlquant_frames.load_images_panel import loadImagePanel as loadImage
from carlquant_frames.settings_panel import settingsPanel as settingsPanel
from carlquant_frames.specimen_panel import specimenPanel as specimenPanel
from carlquant_frames.results_panel import resultsPanel as resultsPanel
from carlquant_frames.image_viewer_panel import image_viewer_panel as imagePanel

@handle_errors("carl_quant.addContent")
def addContent(self, frame):
    self.carlQuantFrame = frame
    self.context.root = self.carlQuantFrame

    # Layout configuration
    # Column 0 → Controls container (holds Load Data + Settings)
    self.carlQuantFrame.columnconfigure(0, minsize=50, weight=0)
    # Column 1 → Left pane of PanedWindow (Specimen table)
    self.carlQuantFrame.columnconfigure(1, weight=1, minsize=400)
    # Column 2 → Right pane of PanedWindow (Results table)
    self.carlQuantFrame.columnconfigure(2, weight=1, minsize=400)
    # Row 0 → Top row (Controls container + PanedWindow with Specimen + Results)
    self.carlQuantFrame.rowconfigure(0, weight=0)
    # Row 1 → Middle row (Data Viewer frame spanning all columns)
    self.carlQuantFrame.rowconfigure(1, weight=1)
    # Row 2 → Bottom row (Status bar, if present)
    self.carlQuantFrame.rowconfigure(2, weight=0)


    # Controls container
    self.controlsContainer = ttk.Frame(self.carlQuantFrame)
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
        self.carlQuantFrame, 
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
    self.tablePane.after(100, lambda: self.tablePane.sash_place(0, 500, 0))

    # Viewer Frame
    self.viewerFrame = ttk.LabelFrame(self.carlQuantFrame, text='Image Viewer', relief=tk.RIDGE)
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


