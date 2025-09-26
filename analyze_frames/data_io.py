# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 10:19:44 2025

@author: Tobias Meissner
"""

from pathlib import Path
import json
import csv
from datetime import datetime

class DataLoader:
    def __init__(self, base_folder: Path, context):
        self.base_folder = base_folder
        self.context = context
        self.sample_name = base_folder.name

    def find_file(self, pattern: str) -> Path | None:
        matches = list(self.base_folder.rglob(pattern))
        if self.sample_name:
            prioritized = [f for f in matches if self.sample_name in f.name]
            return prioritized[0] if prioritized else (matches[0] if matches else None)
        return matches[0] if matches else None

    def load_config(self):
        config_path = self.find_file("*config.json")
        if config_path:
            config = self.context.config_manager.load_config(str(config_path))
            if config:
                self.context.config_manager.apply_config(config, self.context)
                self.context.safe_status_update(f"Config loaded from: {config_path}", level="success")
            else:
                self.context.safe_status_update("Config file found but failed to load.", level="error")
        else:
            self.context.safe_status_update("No config file found.", level="warning")

    def load_annotations(self):
        annotation_path = self.find_file("*annotations.json")
        if annotation_path:
            try:
                with open(annotation_path, "r", encoding="utf-8") as f:
                    annotations = json.load(f)
                self.context.loaded_annotations = annotations
                annotate_panel = self.context.get_panel("image")
                if annotate_panel:
                    annotate_panel.load_annotations(annotations)
                self.context.safe_status_update(f"Annotations loaded from: {annotation_path}", level="success")
            except Exception as e:
                self.context.safe_status_update(f"Failed to load annotations: {e}", level="error")
        else:
            self.context.safe_status_update("No annotations file found.", level="warning")

    def load_results(self):
        results_path = self.find_file("*results.csv")
        if results_path:
            try:
                with open(results_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                if not rows:
                    self.context.status_bar.update("Results file is empty.", level="warning")
                    return
                headers, data = rows[0], rows[1:]
                results_panel = self.context.get_panel("results")
                if results_panel:
                    results_panel.sheet.headers(headers)
                    results_panel.sheet.set_sheet_data(data)
                    results_panel.sheet.refresh()
                    results_panel._set_column_widths()
                    self.context.status_bar.update(f"Results loaded from: {results_path}", level="success")
            except Exception as e:
                self.context.status_bar.update(f"Failed to load results: {e}", level="error")
        else:
            self.context.status_bar.update("No results file found.", level="warning")




class DataSaver:
    def __init__(self, context):
        self.context = context
        self.metadata_panel = context.get_panel("metadata")
        self.results_panel = context.get_panel("results")
        self.annotate_panel = context.get_panel("image")
        self.add_columns_panel = context.get_panel("add_columns")
        self.config_manager = context.config_manager

        self.operator = self.metadata_panel.operatorEntry.get()
        self.measurement = self.metadata_panel.measurementEntry.get()
        self.sample_folder = Path(context.image_folder)
        self.data_folder = self.sample_folder / f"Data_{self.operator}_{self.measurement}"
        self.data_folder.mkdir(exist_ok=True)

    def save_config(self):
        config = self.config_manager.default_config.copy()

        # Metadata
        config["metadata"] = {
            "operator": self.operator,
            "measurement": self.measurement,
            "system": self.metadata_panel.systemEntry.get()
        }

        # Dynamic Columns
        config["columns"]["dynamic_columns"] = []
        for i, (col_name, color) in enumerate(self.results_panel.dynamic_col_specs):
            keybinding = getattr(self.add_columns_panel, 'column_keybindings', {}).get(col_name, "")
            data_type = getattr(self.add_columns_panel, 'column_data_types', {}).get(col_name, "")
            position_after = self.results_panel.dynamic_col_specs[i - 1][0] if i > 0 else "SLICE"

            config["columns"]["dynamic_columns"].append({
                "name": col_name,
                "keybinding": keybinding,
                "position_after": position_after,
                "order": i,
                "data_type": data_type,
                "color": color
            })

        config["config_info"]["created_date"] = datetime.now().isoformat()

        config_path = self.data_folder / f"{self.sample_folder.name}_config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.context.status_bar.update(f"Config saved to: {config_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save config: {e}", level="error")


    def save_annotations(self):
        annotation_folder = self.data_folder / "annotations"
        annotation_folder.mkdir(exist_ok=True)
        json_path = annotation_folder / f"{self.sample_folder.name}_annotations.json"

        json_data = {}
        for slice_index, annotations in self.annotate_panel.slice_annotations.items():
            slice_key = f"slice_{slice_index}"
            json_data[slice_key] = [
                {
                    "id": a.get("id"),
                    "feature": a.get("feature", "unknown"),
                    "points": a.get("points"),
                    "mode": a.get("mode"),
                    "color": a.get("color"),
                    "locked": a.get("locked", False),
                    "timestamp": a.get("timestamp", datetime.now().isoformat())
                }
                for a in annotations
            ]

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2)
            self.context.status_bar.update(f"Annotations saved to: {json_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save annotations: {e}", level="error")

    def save_results(self):
        results_folder = self.data_folder / "results"
        results_folder.mkdir(exist_ok=True)
        csv_path = results_folder / f"{self.sample_folder.name}_results.csv"

        headers = self.results_panel.sheet.headers()
        data = self.results_panel.sheet.get_sheet_data()

        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)
            self.context.status_bar.update(f"Measurements saved to: {csv_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save measurements: {e}", level="error")

