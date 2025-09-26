# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 10:19:44 2025

@author: meissnerto
"""

from pathlib import Path
import json
import csv

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
    def __init__(self, base_folder: Path, context):
        self.base_folder = base_folder
        self.context = context
        self.sample_name = base_folder.name

    # ... include methods like save_config, save_annotations, save_results
