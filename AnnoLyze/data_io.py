# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 10:19:44 2025

@author: Tobias Meissner
"""

from pathlib import Path
import json
from typing import Optional
from app.logic.annolyze.data_service import DataService

class DataLoader:
    def __init__(self, base_folder: Path, context):
        self.base_folder = base_folder
        self.context = context
        self.sample_name = base_folder.name
        self.data_service = DataService()

    def find_file(self, pattern: str) -> Optional[Path]:
        return self.data_service.find_file(self.base_folder, pattern, self.sample_name)

    def load_config(self):
        config_path = self.find_file("*config.json")
        if config_path:
            config = self.context.config_manager.load_config(str(config_path))
            if config:
                # Reset resultsPanel before applying new config
                results_panel = self.context.get_panel("results")
                if results_panel:
                    results_panel.reset_table()

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
                annotate_panel = self.context.get_panel("anno_image")
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
                headers, data = self.data_service.load_results(results_path)
                if not headers:
                    self.context.status_bar.update("Results file is empty.", level="warning")
                    return
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
        self.annotate_panel = context.get_panel("anno_image")
        self.add_columns_panel = context.get_panel("add_columns")
        self.config_manager = context.config_manager
        self.data_service = DataService()

        self.operator = self.metadata_panel.operatorEntry.get()
        self.measurement = self.metadata_panel.measurementEntry.get()
        self.sample_folder = Path(context.image_folder)
        self.data_folder = self.data_service.build_data_folder(
            self.sample_folder, self.operator, self.measurement
        )
        self.data_folder.mkdir(exist_ok=True)

    def save_config(self):
        # Build config using centralized logic
        config = self.config_manager.build_config(
            self.metadata_panel,
            self.results_panel,
            self.add_columns_panel
        )

        # Construct structured save path
        config_path = self.data_folder / f"{self.sample_folder.name}_config.json"

        try:
            self.data_service.save_config(config, config_path)
            self.context.status_bar.update(f"Config saved to: {config_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save config: {e}", level="error")


    def save_annotations(self):
        json_path = (
            self.data_folder / "annotations" / f"{self.sample_folder.name}_annotations.json"
        )

        try:
            self.data_service.save_annotations(self.annotate_panel.slice_annotations, json_path)
            self.context.status_bar.update(f"Annotations saved to: {json_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save annotations: {e}", level="error")

    def save_results(self):
        csv_path = self.data_folder / "results" / f"{self.sample_folder.name}_results.csv"

        headers = self.results_panel.sheet.headers()
        data = self.results_panel.sheet.get_sheet_data()

        try:
            self.data_service.save_results(headers, data, csv_path)
            self.context.status_bar.update(f"Measurements saved to: {csv_path}", level="success")
        except Exception as e:
            self.context.status_bar.update(f"Failed to save measurements: {e}", level="error")

    def save_all(self):
        self.save_config()
        self.save_annotations()
        self.save_results()
        self.context.status_bar.update("All data saved successfully.", level="success")

