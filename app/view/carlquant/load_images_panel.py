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
from app.logic.carlquant import DataLoader, DataSaver
from app.view.carlquant.analysis_runner import run_carl_quant
import threading
from app.view.shared import dialogs


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

        # Button Frame for Remove and Clear Coords (side-by-side)
        button_frame = ttk.Frame(self.frame)
        button_frame.grid(row=1, column=0, sticky="ew", pady=3)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # Remove Selected Button
        self.removeSelectedTooltip = 'Remove the selected specimen(s) from the list to exclude from processing. Use Shift+Click to select multiple rows.'
        self.removeSelectedBtn = ttk.Button(
            button_frame,
            text='Remove',
            command=self.removeSelected,
            bootstyle="danger"
        )
        self.removeSelectedBtn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        Tooltip(self.removeSelectedBtn, text=self.removeSelectedTooltip, wraplength=200)

        # Clear Coordinates Button
        self.clearCoordsTooltip = 'Clear all REGION boundaries and AIR reference coordinates (air/empty space area) for the selected specimen, resetting it to a fresh state'
        self.clearCoordsBtn = ttk.Button(
            button_frame,
            text='Clear Coords',
            command=self.clear_specimen_coordinates,
            bootstyle="warning"
        )
        self.clearCoordsBtn.grid(row=0, column=1, sticky="ew", padx=(2, 0))
        Tooltip(self.clearCoordsBtn, text=self.clearCoordsTooltip, wraplength=200)

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
        """Select folder and check metadata before loading specimens."""
        folder_path = filedialog.askdirectory(title="Select CarlQuant Data Folder")
        if not folder_path:
            self.context.status_bar.update("No folder selected.", level="warning")
            return
        
        # Store folder path temporarily
        self.pending_folder_path = Path(folder_path)
        
        # Check if metadata fields are already filled
        settings_panel = self.context.get_panel("carl_settings")
        if settings_panel:
            operator = settings_panel.operatorVar.get().strip()
            measurement_str = settings_panel.measurementVar.get().strip()
            
            # Only prompt if fields are empty
            if operator and measurement_str:
                try:
                    measurement = int(measurement_str)
                    # Metadata is valid, store it and proceed
                    self.context.analysis_metadata = {
                        "operator": operator,
                        "measurement": measurement
                    }
                    self.load_specimens_with_metadata()
                    return
                except ValueError:
                    pass  # Invalid measurement, will prompt
        
        # Prompt for metadata if not set or invalid
        prompt_for_metadata(
            self.root, 
            self.context, 
            callback=self.load_specimens_with_metadata,
            title="Enter Metadata for Analysis"
        )
    
    def load_specimens_with_metadata(self):
        """
        Load specimens after metadata is set, checking for existing results.
        
        Logic:
        - Uses operator and measurement metadata to identify the target Data_{operator}_{measurement} folder
        - If a matching folder exists, loads configuration and results from it
        - If no matching folder exists (different operator/measurement), specimen is marked as "New"
        - This allows re-analysis with different metadata without overwriting previous results
        """
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
        
        # Load specimens (excludes 'annotations' folders automatically)
        self.context.specimen_data = DataLoader.find_image_stacks(root)
        
        # Check each specimen for matching Data_{operator}_{measurement} folder
        for specimen_id, specimen in self.context.specimen_data.items():
            # Store metadata in specimen for saving operations
            specimen.operator = operator
            specimen.measurement = measurement
            
            # Check if a Data folder exists for this specific operator/measurement combination
            expected_data_folder = specimen.source / f"Data_{operator}_{measurement}"
            
            if expected_data_folder.exists() and expected_data_folder.is_dir():
                # Matching data folder found - reload config (lightweight, no annotations yet)
                # This loads only regions/air coordinates, not the heavy 20MB annotation data
                specimen.config = DataLoader.load_specimen_config(specimen, load_annotations=False)
                if specimen.config:
                    # Check if annotations exist (without loading them)
                    if hasattr(specimen, '_has_annotations') and specimen._has_annotations:
                        specimen.status = "Analyzed"
                        # Note: Annotations will be loaded on-demand when user clicks the specimen
                        # This significantly speeds up initial folder loading
            else:
                # No matching Data folder - specimen will be analyzed fresh with current metadata
                # Other Data folders (different operator/measurement) are preserved and ignored
                pass
        
        # Update specimen panel display
        specimen_panel = self.context.get_panel("carl_specimen")
        rows = []
        for specimen_id, specimen in self.context.specimen_data.items():
            rows.append([
                specimen.specimen_id,
                specimen.slices,
                specimen.status
            ])
        specimen_panel.sheet.set_sheet_data(rows)
        specimen_panel._set_column_widths()
        
        # Run validation check to identify specimens with missing coordinates
        is_valid, invalid_specimens = self.validate_specimen_coordinates()
        
        # Apply highlighting based on status
        for row_idx, row_data in enumerate(rows):
            specimen_id = row_data[0]
            status = row_data[2]
            
            # Priority 1: Highlight analyzed/completed specimens in green
            if status in ["Analyzed", "Completed"]:
                specimen_panel.highlight_completed_row(row_idx)
            # Priority 2: Highlight specimens with missing coordinates in red
            elif specimen_id in invalid_specimens:
                specimen_panel.highlight_invalid_row(row_idx)
        
        specimen_panel.sheet.refresh()
        
        # Update status bar with summary
        num_analyzed = sum(1 for row in rows if row[2] in ["Analyzed", "Completed"])
        num_invalid = len(invalid_specimens)
        
        status_parts = [f"Loaded {len(rows)} specimen(s)"]
        if num_analyzed > 0:
            status_parts.append(f"{num_analyzed} analyzed")
        if num_invalid > 0:
            status_parts.append(f"{num_invalid} missing coordinates")
        
        self.context.status_bar.update(
            f"{' | '.join(status_parts)} for {operator} measurement {measurement}", 
            level="success" if num_invalid == 0 else "warning"
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
        """Remove selected specimen(s) from the table and specimen_data. Supports multi-selection."""
        # Check if specimen data exists
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            self.context.status_bar.update("No specimens loaded.", level="warning")
            return
        
        # Get specimen panel
        specimen_panel = self.context.get_panel("carl_specimen")
        if not specimen_panel:
            self.context.status_bar.update("Specimen panel not found.", level="error")
            return
        
        # Get selected rows (supports multi-selection)
        if not specimen_panel.selected_rows:
            self.context.status_bar.update("No specimen selected. Please select a row first.", level="warning")
            return
        
        # Sort rows in descending order to delete from bottom to top (avoids index shifting issues)
        rows_to_delete = sorted(specimen_panel.selected_rows, reverse=True)
        
        # Collect specimen IDs and remove from specimen_data
        removed_ids = []
        for row_index in rows_to_delete:
            specimen_id = specimen_panel.sheet.get_cell_data(row_index, 0)
            
            if not specimen_id:
                continue
            
            # Remove from specimen_data dictionary
            if specimen_id in self.context.specimen_data:
                del self.context.specimen_data[specimen_id]
                removed_ids.append(specimen_id)
            
            # Remove row from table
            specimen_panel.sheet.delete_row(row_index)
        
        # Update column widths after deletion
        specimen_panel._set_column_widths()
        
        # Clear current specimen if it was among the removed ones
        if hasattr(self.context, 'current_specimen_id') and self.context.current_specimen_id in removed_ids:
            self.context.current_specimen_id = None
            
            # Clear viewer and results panels if methods exist
            viewer_panel = self.context.get_panel("carl_image")
            if viewer_panel and hasattr(viewer_panel, 'clear_display'):
                viewer_panel.clear_display()
            
            results_panel = self.context.get_panel("carl_results")
            if results_panel and hasattr(results_panel, 'clear_results'):
                results_panel.clear_results()
        
        # Clear selection tracking
        specimen_panel.selected_rows.clear()
        specimen_panel.last_selected_row = None
        
        # Update status bar
        if len(removed_ids) == 1:
            self.context.status_bar.update(
                f"Removed specimen '{removed_ids[0]}' from processing list.", 
                level="success"
            )
        else:
            self.context.status_bar.update(
                f"Removed {len(removed_ids)} specimens from processing list.", 
                level="success"
            )

    @handle_errors("loadImagePanel.clear_specimen_coordinates")
    def clear_specimen_coordinates(self):
        """Clear all REGION and AIR reference coordinates for the selected specimen.
        
        AIR (Air Reference) defines areas containing actual air (empty space) used
        for normalization in OCT analysis.
        """
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
        
        if not specimen_id or specimen_id not in self.context.specimen_data:
            self.context.status_bar.update("Could not identify specimen.", level="error")
            return
        
        specimen = self.context.specimen_data[specimen_id]
        
        # Check if specimen has config
        if not specimen.config:
            self.context.status_bar.update(f"Specimen '{specimen_id}' has no configuration to clear.", level="warning")
            return
        
        # Check if there are any coordinates to clear
        has_regions = bool(specimen.config.regions)
        has_air = bool(specimen.config.air)
        
        if not has_regions and not has_air:
            self.context.status_bar.update(f"Specimen '{specimen_id}' has no coordinates to clear.", level="warning")
            return
        
        # Clear all coordinates
        specimen.config.regions.clear()
        specimen.config.air.clear()
        
        # Save cleared configuration to JSON
        DataSaver.save_specimen_config(specimen)
        
        # Refresh image viewer if this specimen is currently displayed
        if hasattr(self.context, 'current_specimen_id') and self.context.current_specimen_id == specimen_id:
            viewer_panel = self.context.get_panel("carl_image")
            if viewer_panel and hasattr(viewer_panel, 'refresh_display'):
                viewer_panel.refresh_display()
        
        self.context.status_bar.update(
            f"Cleared all coordinates for specimen '{specimen_id}'.", 
            level="success"
        )

    @handle_errors("loadImagePanel.validate_specimen_coordinates")
    def validate_specimen_coordinates(self):
        """
        Validate that all specimens have required coordinates set.
        
        Returns:
            tuple: (is_valid, invalid_specimens)
                - is_valid (bool): True if all specimens are valid
                - invalid_specimens (dict): {specimen_id: [missing_items]}
        """
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            return True, {}
        
        invalid_specimens = {}
        
        for specimen_id, specimen in self.context.specimen_data.items():
            missing_items = []
            
            # Check if specimen has any configuration
            if not specimen.config:
                missing_items.extend(["Region boundaries", "AIR coordinates"])
            else:
                # Check if regions are defined for at least one slice
                if not specimen.config.regions:
                    missing_items.append("Region boundaries")
                else:
                    # Validate that region boundaries have all 4 points
                    for slice_idx, region_config in specimen.config.regions.items():
                        if not all([
                            region_config.specimen_start,
                            region_config.lesion_start,
                            region_config.lesion_end,
                            region_config.tooth_end
                        ]):
                            missing_items.append("Region boundaries (incomplete)")
                            break
                
                # Check if AIR coordinates are defined for at least one slice
                if not specimen.config.air:
                    missing_items.append("AIR coordinates")
                else:
                    # Validate that AIR coordinates have both points
                    for slice_idx, air_config in specimen.config.air.items():
                        if not air_config.point1 or not air_config.point2:
                            missing_items.append("AIR coordinates (incomplete)")
                            break
            
            if missing_items:
                invalid_specimens[specimen_id] = missing_items
        
        is_valid = len(invalid_specimens) == 0
        return is_valid, invalid_specimens
    
    @handle_errors("loadImagePanel.highlight_invalid_specimens")
    def highlight_invalid_specimens(self, invalid_specimens):
        """
        Highlight rows in the specimen panel that have missing coordinates.
        
        Args:
            invalid_specimens (dict): {specimen_id: [missing_items]}
        """
        specimen_panel = self.context.get_panel("carl_specimen")
        if not specimen_panel:
            return
        
        # First clear all previous validation highlights
        specimen_panel.clear_all_highlights()
        
        # Highlight invalid specimens with red color
        for row_idx in range(specimen_panel.sheet.total_rows()):
            specimen_id = specimen_panel.sheet.get_cell_data(row_idx, 0)
            
            if specimen_id in invalid_specimens:
                specimen_panel.highlight_invalid_row(row_idx)
        
        specimen_panel.sheet.refresh()
    
    @handle_errors("loadImagePanel.show_validation_error_dialog")
    def show_validation_error_dialog(self, invalid_specimens):
        """
        Show a concise dialog about missing coordinates.
        
        Args:
            invalid_specimens (dict): {specimen_id: [missing_items]}
        """
        num_invalid = len(invalid_specimens)
        
        # Build concise error message
        if num_invalid == 1:
            error_message = (
                "1 specimen has missing coordinates and cannot be analyzed.\n\n"
                "Please define the missing Region boundaries and/or AIR coordinates.\n\n"
                "Invalid specimens are highlighted in RED in the table."
            )
        else:
            error_message = (
                f"{num_invalid} specimens have missing coordinates and cannot be analyzed.\n\n"
                "Please define the missing Region boundaries and/or AIR coordinates.\n\n"
                "Invalid specimens are highlighted in RED in the table."
            )
        
        # Show error dialog (anchored to the app root, not a throwaway tk.Tk())
        dialogs.show_error(self.root, "Missing Coordinates", error_message)
    
    @handle_errors("loadImagePanel.refresh_validation_status")
    def refresh_validation_status(self):
        """
        Refresh validation status and clear red highlighting for specimens
        that now have valid coordinates. This is called after coordinates are saved.
        """
        # Re-validate all specimens
        is_valid, invalid_specimens = self.validate_specimen_coordinates()
        
        specimen_panel = self.context.get_panel("carl_specimen")
        if not specimen_panel:
            return
        
        # Clear all highlights first
        specimen_panel.clear_all_highlights()
        
        # Re-apply red highlighting only to specimens that are still invalid
        if invalid_specimens:
            for row_idx in range(specimen_panel.sheet.total_rows()):
                specimen_id = specimen_panel.sheet.get_cell_data(row_idx, 0)
                
                if specimen_id in invalid_specimens:
                    specimen_panel.highlight_invalid_row(row_idx)
        
        specimen_panel.sheet.refresh()
    
    @handle_errors("loadImagePanel.startAnalyzing")
    def startAnalyzing(self):
        """Start analysis - metadata is guaranteed to be set at this point."""
        # Ensure region config exists
        if not hasattr(self.context, "region_config"):
            self.context.region_config = {"sound": 3, "lesion": 3}

        # Ensure specimen data exists and is non-empty
        if not hasattr(self.context, "specimen_data") or not self.context.specimen_data:
            self.context.status_bar.update("No specimens loaded. Please select a folder first.", level="warning")
            return
        
        # Validate that all specimens have required coordinates
        is_valid, invalid_specimens = self.validate_specimen_coordinates()
        
        if not is_valid:
            # Highlight invalid specimens in the table
            self.highlight_invalid_specimens(invalid_specimens)
            
            # Show error dialog with details
            self.show_validation_error_dialog(invalid_specimens)
            
            # Update status bar
            self.context.status_bar.update(
                f"{len(invalid_specimens)} specimen(s) have missing coordinates. Analysis cannot start.",
                level="error"
            )
            return

        # Add lock for thread safety
        if not hasattr(self.context, "result_lock"):
            self.context.result_lock = threading.Lock()

        # Metadata is guaranteed to be set from selectFolder
        # No need to check or prompt - just run analysis
        run_carl_quant(self.context)

