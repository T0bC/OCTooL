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

@handle_errors("carl_quant.addContent")
def addContent(self, frame):
    self.carlQuantFrame = frame
    self.context.root = self.carlQuantFrame

    # Layout configuration
    self.carlQuantFrame.columnconfigure(0, minsize=50, weight=0)
    self.carlQuantFrame.columnconfigure(1, weight=1, minsize=800)
    self.carlQuantFrame.rowconfigure(2, weight=0)
    self.carlQuantFrame.rowconfigure(0, weight=0)
    self.carlQuantFrame.rowconfigure(1, weight=1)

    # Controls container
    self.controlsContainer = ttk.Frame(self.carlQuantFrame)
    self.controlsContainer.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

    # Load Panel
    self.loadFrame = ttk.LabelFrame(self.controlsContainer, text='Load Data', relief=tk.RIDGE)
    self.loadFrame.pack(fill="x", pady=(0, 2))
    self.context.register_frame("carl_load", self.loadFrame)
    loadImage(self.context)

    # Settings Panel
    self.settingsFrame = ttk.LabelFrame(self.controlsContainer, text='Settings', relief=tk.RIDGE)
    self.settingsFrame.pack(fill="x", pady=(0, 2))
    self.context.register_frame("carl_settings", self.settingsFrame)
    settingsPanel(self.context)

    # Status bar
    self.attach_status_bar(self.context)
