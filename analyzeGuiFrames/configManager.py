# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 15:21:37 2025

@author: meissnerto
"""

import json
import os
from datetime import datetime
from tkinter import filedialog, messagebox
from errorHandler import handle_errors
from analyzeGuiFrames.keyBindingManager import KeybindingManager
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_version = "1.0"
        self.default_config = {
            "metadata": {
                "operator": "TM",
                "measurement": "A",
                "system": "OCT"
            },
            "columns": {
                "dynamic_columns": []
            },
            "ui_settings": {
                "sheet_width": 800,
                "sheet_height": 400
            },
            "config_info": {
                "created_date": datetime.now().isoformat(),
                "version": self.config_version,
                "description": "OCT Analysis Configuration"
            }
        }

    @handle_errors("ConfigManager.save_config")
    def save_config(self, metadata_panel, results_panel, add_columns_panel):
        config = self.default_config.copy()

        # Metadata
        config["metadata"] = {
            "operator": metadata_panel.operatorEntry.get(),
            "measurement": metadata_panel.measurementEntry.get(),
            "system": metadata_panel.systemEntry.get()
        }

        # Dynamic Columns
        config["columns"]["dynamic_columns"] = []
        for i, (col_name, color) in enumerate(results_panel.dynamic_col_specs):
            keybinding = getattr(add_columns_panel, 'column_keybindings', {}).get(col_name, "")
            data_type = getattr(add_columns_panel, 'column_data_types', {}).get(col_name, "")
            position_after = results_panel.dynamic_col_specs[i - 1][0] if i > 0 else "SLICE"

            config["columns"]["dynamic_columns"].append({
                "name": col_name,
                "keybinding": keybinding,
                "position_after": position_after,
                "order": i,
                "data_type": data_type,
                "color": color
            })

        config["config_info"]["created_date"] = datetime.now().isoformat()

        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="oct_analysis_config.json"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Success", f"Configuration saved to:\n{filename}")
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
        return False

    @handle_errors("ConfigManager.save_config_to_folder")
    def save_config_to_folder(self, folder_path, metadata_panel, results_panel, add_columns_panel):
        config = self.default_config.copy()

        # Metadata
        config["metadata"] = {
            "operator": metadata_panel.operatorEntry.get(),
            "measurement": metadata_panel.measurementEntry.get(),
            "system": metadata_panel.systemEntry.get()
        }

        # Dynamic Columns
        config["columns"]["dynamic_columns"] = []
        for i, (col_name, color) in enumerate(results_panel.dynamic_col_specs):
            keybinding = getattr(add_columns_panel, 'column_keybindings', {}).get(col_name, "")
            data_type = getattr(add_columns_panel, 'column_data_types', {}).get(col_name, "")
            position_after = results_panel.dynamic_col_specs[i - 1][0] if i > 0 else "SLICE"

            config["columns"]["dynamic_columns"].append({
                "name": col_name,
                "keybinding": keybinding,
                "position_after": position_after,
                "order": i,
                "data_type": data_type,
                "color": color
            })

        config["config_info"]["created_date"] = datetime.now().isoformat()

        config_path = Path(folder_path) / "config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"Config saved to: {config_path}")
        except Exception as e:
            print(f"Failed to save config: {e}")

    @handle_errors("ConfigManager.load_config")
    def load_config(self, filename=None):
        if not filename:
            filename = filedialog.askopenfilename(
                title="Load Configuration",
                filetypes=[("JSON files", "*.json")]
            )

        if filename and os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config if self.validate_config(config) else None
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
        return None

    def validate_config(self, config):
        return all(key in config for key in ["metadata", "columns", "config_info"])

    @handle_errors("ConfigManager.apply_config")
    def apply_config(self, config, context):
        try:
            metadata_panel = context.get_panel("metadata")
            results_panel = context.get_panel("results")
            add_columns_panel = context.get_panel("add_columns")
            annotate_panel = context.get_panel("image")

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
                results_panel.add_dynamic_column(col_name, color)

                # Set column width
                try:
                    col_index = results_panel.sheet.headers().index(col_name)
                    results_panel.sheet.column_width(col_index, width=col.get("width", 100))
                except Exception as e:
                    print(f"Failed to set width for {col_name}: {e}")

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

            column_map = {}
            for col in config["columns"]["dynamic_columns"]:
                key = col.get("keybinding")
                col_name = col["name"]
                data_type = col.get("data_type", "Text/String")
                color = col.get("color")
                if key:
                    column_map[key] = {
                        "col_name": col_name,
                        "data_type": data_type,
                        "color": color
                    }

            keybinding_manager = KeybindingManager(
                canvas=annotate_panel.canvas,
                sheet=results_panel.sheet,
                column_map=column_map,
                annotate_panel=annotate_panel
            )
            keybinding_manager.register_keybindings()

            print(f"Registered keybinding: <{key}> for column '{col_name}' with type '{data_type}'")

            messagebox.showinfo("Success", "Configuration loaded successfully!")
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply configuration:\n{str(e)}")
            return False
