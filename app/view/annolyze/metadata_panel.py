# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 13:02:23 2025

@author: Tobias Meissner
"""

from tkinter import ttk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors
from app.view.annolyze.keyboard_layout_viewer import KeyboardLayoutViewer
from app.view.shared import dialogs

class metadataPanel:
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("metadata")
        self.config_manager = context.config_manager

    @handle_errors("metadataPanel setup failed.")
    def setup(self):
        # Operator
        self.operatorLabel = ttk.Label(self.frame, text='Operator')
        self.operatorLabel.grid(row=0, column=0, sticky="w", padx=(0, 3), pady=3)

        self.operatorEntry = ttk.Entry(self.frame, width=3, bootstyle="success")
        self.operatorEntry.insert(0, 'TM')
        self.operatorEntry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=3)
        Tooltip(self.operatorEntry, text='Define the Operator Abbreviation: TM or CR or ...', wraplength=200)

        # Measurement
        self.measurementLabel = ttk.Label(self.frame, text='Measurement')
        self.measurementLabel.grid(row=0, column=2, sticky="w", padx=3, pady=3)

        self.measurementEntry = ttk.Entry(self.frame, width=5, bootstyle="success")
        self.measurementEntry.insert(0, '1')
        self.measurementEntry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=3)
        Tooltip(self.measurementEntry, text='Measurement Number 1, 2, ...', wraplength=200)

        # System (moved to row 1)
        self.systemLabel = ttk.Label(self.frame, text='System')
        self.systemLabel.grid(row=1, column=0, sticky="w", padx=(0, 3), pady=3)

        self.systemEntry = ttk.Entry(self.frame, width=5, bootstyle="success")
        self.systemEntry.insert(0, 'OCT')
        self.systemEntry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=3)
        Tooltip(self.systemEntry, text='System: OCT / uCT / SEM / LiMi / ...', wraplength=200)

        # Save Config Button
        self.saveConfig = ttk.Button(
            self.frame,
            text='Save Config',
            width=14,
            command=self.saveConfigToFile,
            bootstyle="primary"
        )
        self.saveConfig.grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=3)
        Tooltip(self.saveConfig, text='Save a config file for layout and key bindings. The config is saved as a "json" file and is to be loaded when analysis begins.', wraplength=200)

        self.showConfigBtn = ttk.Button(
            self.frame,
            text='Show Config',
            command=self.show_keyboard_layout,
            bootstyle="info"
        )
        self.showConfigBtn.grid(row=2, column=1, sticky="ew", padx=(0, 3), pady=3)
        Tooltip(self.showConfigBtn, text='View assigned key bindings in a keyboard layout', wraplength=200)

    @handle_errors("metadataPanel.show_keyboard_layout")
    def show_keyboard_layout(self):
        self.context.keyboard_layout_viewer = KeyboardLayoutViewer(self.context)


    @handle_errors("metadataPanel saveConfig failed.")
    def saveConfigToFile(self):
        results_panel = self.context.get_panel("results")
        add_columns_panel = self.context.get_panel("add_columns")

        if results_panel and add_columns_panel:
            self.config_manager.save_config(self, results_panel, add_columns_panel, self.context)
        else:
            dialogs.show_error(self.root, "Error", "Missing panel references in context")
