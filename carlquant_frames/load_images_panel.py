# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:16:49 2025

"""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from fnmatch import fnmatch
from utils.error_handler import handle_errors
from utils.metadata_prompt import prompt_for_metadata
from utils.tool_tip import Tooltip
from carlquant_frames.data_io import DataLoader
from carlquant_frames.carl_quant_core import run_carl_quant
import threading


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

        # Remove Selected Button
        self.removeSelectedTooltip = 'Remove the selected specimen from the list to exclude it from processing'
        self.removeSelectedBtn = ttk.Button(
            self.frame,
            text='Remove Selected',
            command=self.removeSelected,
            bootstyle="danger"
        )
        self.removeSelectedBtn.grid(row=1, column=0, sticky="ew", pady=3)
        Tooltip(self.removeSelectedBtn, text=self.removeSelectedTooltip, wraplength=200)

        # Start Analyzing Button
        self.startAnalyzingTooltip = 'Begin analyzing the selected CarlQuant data folder'
        self.startAnalyzingBtn = ttk.Button(
            self.frame,
            text='Start Analyzing',
            command=self.startAnalyzing,
            bootstyle="success"
        )
        self.startAnalyzingBtn.grid(row=2, column=0, sticky="ew", pady=3)
        Tooltip(self.startAnalyzingBtn, text=self.startAnalyzingTooltip, wraplength=200)


    @handle_errors("loadImagePanel.selectFolder")
    def selectFolder(self):
        """Select folder and prompt for metadata before loading specimens."""
        folder_path = filedialog.askdirectory(title="Select CarlQuant Data Folder")
        if not folder_path:
            self.context.status_bar.update("No folder selected.", level="warning")
            return
        
        # Store folder path temporarily
        self.pending_folder_path = Path(folder_path)
        
        # Prompt for metadata first, then load specimens
        prompt_for_metadata(
            self.root, 
            self.context, 
            callback=self.load_specimens_with_metadata,
            title="Enter Metadata for Analysis"
        )
    
    def load_specimens_with_metadata(self):
        """Load specimens after metadata is set, checking for existing results."""
        if not hasattr(self, 'pending_folder_path'):
            return
        
        root = self.pending_folder_path
        self.context.path_to_carlquant_data = root
        
        # Get metadata
        metadata = getattr(self.context, "analysis_metadata", {})
        operator = metadata.get("operator", "OP")
        measurement = metadata.get("measurement", 1)
        
        # Update settings panel entry fields
        self.update_settings_panel_metadata(operator, measurement)
        
        # Load specimens
        self.context.specimen_data = DataLoader.find_image_stacks(root)
        
        # Check each specimen for matching Data_{operator}_{measurement} folder
        for specimen_id, specimen in self.context.specimen_data.items():
            # Store metadata in specimen for saving operations
            specimen.operator = operator
            specimen.measurement = measurement
            
            # Check if a Data folder exists for this operator/measurement
            expected_data_folder = specimen.source / f"Data_{operator}_{measurement}"
            
            if expected_data_folder.exists() and expected_data_folder.is_dir():
                # Matching data folder found - reload config and results
                specimen.config = DataLoader.load_specimen_config(specimen)
                if specimen.config:
                    # Update display values
                    regions_count = len(specimen.config.regions)
                    specimen.regions = f"{regions_count} regions" if regions_count > 0 else ""
                    
                    # Check if results were loaded (annotations)
                    if specimen.results:
                        specimen.status = "Analyzed"
                        self.context.status_bar.update(
                            f"Loaded existing results for {specimen_id} (Data_{operator}_{measurement})", 
                            level="success"
                        )
        
        # Update specimen panel display
        specimen_panel = self.context.get_panel("carl_specimen")
        rows = []
        for specimen_id, specimen in self.context.specimen_data.items():
            # Get AIR configuration summary
            air_summary = ""
            if specimen.config and specimen.config.air:
                air_count = len(specimen.config.air)
                air_summary = f"{air_count} points" if air_count > 0 else ""
            
            rows.append([
                specimen.specimen_id,
                specimen.slices,
                specimen.regions,
                air_summary,
                specimen.status
            ])
        specimen_panel.sheet.set_sheet_data(rows)
        specimen_panel._set_column_widths()
        
        self.context.status_bar.update(
            f"Loaded {len(rows)} specimen(s) for {operator} measurement {measurement}", 
            level="success"
        )
        
        # Clear pending path
        delattr(self, 'pending_folder_path')
    
    def update_settings_panel_metadata(self, operator, measurement):
        """Update the settings panel entry fields with metadata."""
        settings_panel = self.context.get_panel("carl_settings")
        if settings_panel:
            settings_panel.operatorVar.set(operator)
            settings_panel.measurementVar.set(str(measurement))

    @handle_errors("loadImagePanel.removeSelected")
    def removeSelected(self):
        """Remove the selected specimen from the table and specimen_data."""
        # Check if specimen data exists
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            self.context.status_bar.update("No specimens loaded.", level="warning")
            return
        
        # Get specimen panel
        specimen_panel = self.context.get_panel("carl_specimen")
        if not specimen_panel:
            self.context.status_bar.update("Specimen panel not found.", level="error")
            return
        
        # Get currently selected row
        selected = specimen_panel.sheet.get_currently_selected()
        if not selected or selected[0] is None:
            self.context.status_bar.update("No specimen selected. Please select a row first.", level="warning")
            return
        
        row_index = selected[0]
        
        # Get specimen ID from the selected row
        specimen_id = specimen_panel.sheet.get_cell_data(row_index, 0)
        
        if not specimen_id:
            self.context.status_bar.update("Could not identify specimen.", level="error")
            return
        
        # Remove from specimen_data dictionary
        if specimen_id in self.context.specimen_data:
            del self.context.specimen_data[specimen_id]
        
        # Remove row from table
        specimen_panel.sheet.delete_row(row_index)
        
        # Update column widths after deletion
        specimen_panel._set_column_widths()
        
        # Clear current specimen if it was the one removed
        if hasattr(self.context, 'current_specimen_id') and self.context.current_specimen_id == specimen_id:
            self.context.current_specimen_id = None
            
            # Clear viewer and results panels if methods exist
            viewer_panel = self.context.get_panel("carl_image")
            if viewer_panel and hasattr(viewer_panel, 'clear_display'):
                viewer_panel.clear_display()
            
            results_panel = self.context.get_panel("carl_results")
            if results_panel and hasattr(results_panel, 'clear_results'):
                results_panel.clear_results()
        
        # Clear highlight tracking if this was the last selected row
        if specimen_panel.last_selected_row == row_index:
            specimen_panel.last_selected_row = None
        elif specimen_panel.last_selected_row is not None and specimen_panel.last_selected_row > row_index:
            # Adjust tracking if a row above was deleted
            specimen_panel.last_selected_row -= 1
        
        self.context.status_bar.update(
            f"Removed specimen '{specimen_id}' from processing list.", 
            level="success"
        )

    @handle_errors("loadImagePanel.startAnalyzing")
    def startAnalyzing(self):
        """Start analysis - metadata is guaranteed to be set at this point."""
        print("Start Analyzing triggered")

        # Ensure region config exists
        if not hasattr(self.context, "region_config"):
            self.context.region_config = {"sound": 3, "lesion": 3}

        # Ensure specimen data exists and is non-empty
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            self.context.status_bar.update("No specimens loaded. Please select a folder first.", level="warning")
            return

        # Add lock for thread safety
        if not hasattr(self.context, "result_lock"):
            self.context.result_lock = threading.Lock()

        # Metadata is guaranteed to be set from selectFolder
        # No need to check or prompt - just run analysis
        run_carl_quant(self.context)

