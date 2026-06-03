# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 15:21:37 2025

@author: Tobias Meissner
"""

import json
import os
from datetime import datetime
from tkinter import filedialog, messagebox
from utils.error_handler import handle_errors
from AnnoLyze.key_binding_manager import KeybindingManager
from app.logic.annolyze.config_service import ConfigService
from app.logic.annolyze.models import MetadataConfig, ColumnSpec
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_version = "1.0"
        self.config_service = ConfigService()
        self.default_config = self.config_service.default_config()

    def _collect_metadata(self, metadata_panel) -> MetadataConfig:
        """Collector: read metadata widget state into a model."""
        return MetadataConfig.from_gui_state(
            operator=metadata_panel.operatorEntry.get(),
            measurement=metadata_panel.measurementEntry.get(),
            system=metadata_panel.systemEntry.get(),
        )

    def _collect_columns(self, results_panel, add_columns_panel) -> list:
        """Collector: read dynamic column widget state into ColumnSpec models."""
        keybindings = getattr(add_columns_panel, 'column_keybindings', {})
        data_types = getattr(add_columns_panel, 'column_data_types', {})
        return [
            ColumnSpec(
                name=col_name,
                keybinding=keybindings.get(col_name, ""),
                data_type=data_types.get(col_name, ""),
                color=color,
            )
            for col_name, color in results_panel.dynamic_col_specs
        ]

    def build_config(self, metadata_panel, results_panel, add_columns_panel) -> dict:
        metadata = self._collect_metadata(metadata_panel)
        columns = self._collect_columns(results_panel, add_columns_panel)
        return self.config_service.build_config(metadata, columns)


    @handle_errors("ConfigManager.save_config")
    def save_config(self, metadata_panel, results_panel, add_columns_panel, context, filepath=None):
        """
        Save configuration to file.
        
        Args:
            filepath: If provided, saves to this path. If None, prompts user with dialog.
        """
        config = self.build_config(metadata_panel, results_panel, add_columns_panel)
        
        # Prompt user for location if no filepath provided
        if filepath is None:
            filepath = filedialog.asksaveasfilename(
                title="Save Configuration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            show_dialog = True
        else:
            show_dialog = False
        
        if filepath:
            try:
                self.config_service.save_config_to_file(config, filepath)
                context.status_bar.update(f"Config saved to: {filepath}", level="success")
                if show_dialog:
                    messagebox.showinfo("Success", f"Configuration saved to:\n{filepath}")
            except Exception as e:
                context.status_bar.update(f"Failed to save config: {e}", level="error")
                if show_dialog:
                    messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")

    @handle_errors("ConfigManager.save_config_to_folder")
    def save_config_to_folder(self, folder_path, metadata_panel, results_panel, add_columns_panel, context):
        """
        Auto-save config to a specific folder (convenience wrapper for annotation auto-save).
        """
        config_path = Path(folder_path) / "config.json"
        self.save_config(metadata_panel, results_panel, add_columns_panel, context, filepath=str(config_path))


    @handle_errors("ConfigManager.load_config")
    def load_config(self, filename=None):
        if not filename:
            filename = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[("JSON files", "*.json")]
            )

        if filename and os.path.exists(filename):
            try:
                config = self.config_service.load_config_from_file(filename)
                if config:
                    self.active_config = config
                    return config
                return None
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")

        return None


    def validate_config(self, config):
        return self.config_service.validate_config(config)

    @handle_errors("ConfigManager.apply_config")
    def apply_config(self, config, context):
        try:
            metadata_panel = context.get_panel("metadata")
            results_panel = context.get_panel("results")
            add_columns_panel = context.get_panel("add_columns")
            annotate_panel = context.get_panel("anno_image")

            # Apply metadata
            for key in ["operator", "measurement", "system"]:
                entry = getattr(metadata_panel, f"{key}Entry", None)
                if entry:
                    entry.delete(0, 'end')
                    entry.insert(0, config["metadata"].get(key, ""))

            # Apply dynamic columns
            results_panel.dynamic_col_specs.clear()
            results_panel.dynamic_insert_index = 2

            columns_to_add = sorted(config["columns"]["dynamic_columns"], key=lambda x: x.get("order", 0))
            for col in columns_to_add:
                col_name = col["name"]
                color = col.get("color", "#FFFFFF")
                keyBind = None
                results_panel.add_dynamic_column(col_name, color, keyBind)

                # Set column width
                try:
                    col_index = results_panel.sheet.headers().index(col_name)
                    results_panel.sheet.column_width(col_index, width=col.get("width", 100))
                except Exception as e:
                    context.status_bar.update(f"Failed to set width for {col_name}: {e}", level="error")

                # Update add_columns_panel attributes
                if hasattr(add_columns_panel, 'column_keybindings'):
                    add_columns_panel.column_keybindings[col_name] = col.get("keybinding", "")
                if hasattr(add_columns_panel, 'add_keybinding'):
                    add_columns_panel.add_keybinding(col_name, col.get("keybinding", ""))
                if hasattr(add_columns_panel, 'column_data_types'):
                    add_columns_panel.column_data_types[col_name] = col.get("data_type", "")
                if hasattr(add_columns_panel, 'column_colors'):
                    add_columns_panel.column_colors[col_name] = color

            results_panel.sheet.refresh()

            column_map = self.config_service.build_column_map(config)

            keybinding_manager = KeybindingManager(
                canvas=annotate_panel.canvas,
                sheet=results_panel.sheet,
                column_map=column_map,
                annotate_panel=annotate_panel
            )
            keybinding_manager.register_keybindings()

            # store information for keybinding and show keybind layout purposes
            context.keybinding_specs = [
                (info["col_name"], info["color"], key, info["data_type"])
                for key, info in column_map.items()
            ]


            # Update dropdown to reflect used keys
            if hasattr(add_columns_panel, "update_available_keys"):
                add_columns_panel.update_available_keys()

            if hasattr(context, "keyboard_layout_viewer") and context.keyboard_layout_viewer:
                context.keyboard_layout_viewer.update_highlights()


            for key, info in column_map.items():
                context.status_bar.update(
                    f"Registered keybinding: <{key}> for column '{info['col_name']}' with type '{info['data_type']}'",
                    level="success"
                )

            #messagebox.showinfo("Success", "Configuration loaded successfully!")
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply configuration:\n{str(e)}")
            return False

    def get_data_type_for_column(self, col_name):
        config = getattr(self, "active_config", self.default_config)
        return self.config_service.get_data_type_for_column(config, col_name)

