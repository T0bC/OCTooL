"""
AnnoLyze Config Service.

Pure logic for building, validating, and (de)serialising analysis configuration
files — no tkinter, no dialogs. Extracted from AnnoLyze/config_manager.py. File
I/O methods raise exceptions on failure; the view layer decides how to surface
them.

Key contents:
- ConfigService: Pure logic for building, validating, and serialising analysis configs.
- default_config: Returns the default on-disk config dictionary.
- build_config: Assembles an AnnotationConfig from metadata and ordered column specs.
- validate_config: Checks that a loaded dict contains all required top-level keys.
- parse_config: Converts a raw config dict into typed AnnotationConfig models.
- build_column_map: Creates a {keybinding: column_info} map for the annotation canvas.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""


import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from app.logic.annolyze.models import AnnotationConfig, ColumnSpec, MetadataConfig

CONFIG_VERSION = "1.0"
REQUIRED_KEYS = ("metadata", "columns", "config_info")


class ConfigService:
    """Pure configuration build/validate/serialize logic."""

    def default_config(self) -> dict:
        """Return the default on-disk config dictionary."""
        return AnnotationConfig().to_dict()

    def build_config(
        self,
        metadata: MetadataConfig,
        columns: List[ColumnSpec],
    ) -> dict:
        """
        Build an on-disk config dict from metadata + ordered column specs.

        ``position_after`` is computed from the preceding column's name
        (or ``SLICE`` for the first column), and ``order`` is the list index.
        """
        ordered: List[ColumnSpec] = []
        for i, col in enumerate(columns):
            position_after = columns[i - 1].name if i > 0 else "SLICE"
            ordered.append(
                ColumnSpec(
                    name=col.name,
                    keybinding=col.keybinding,
                    position_after=position_after,
                    order=i,
                    data_type=col.data_type,
                    color=col.color,
                )
            )
        return AnnotationConfig(metadata=metadata, columns=ordered).to_dict()

    def validate_config(self, config: dict) -> bool:
        """Return True if ``config`` contains all required top-level keys."""
        if not isinstance(config, dict):
            return False
        return all(key in config for key in REQUIRED_KEYS)

    def parse_config(self, config: dict) -> AnnotationConfig:
        """Parse a raw config dict into an :class:`AnnotationConfig` model."""
        return AnnotationConfig.from_dict(config)

    def get_data_type_for_column(self, config: dict, col_name: str) -> str:
        """Return the data type for ``col_name``, defaulting to 'Text/String'."""
        for col in config.get("columns", {}).get("dynamic_columns", []):
            if col.get("name") == col_name:
                return col.get("data_type", "Text/String")
        return "Text/String"

    def build_column_map(self, config: dict) -> dict:
        """
        Build ``{key: {col_name, data_type, color}}`` for keybinding registration.

        Only columns that declare a keybinding are included.
        """
        column_map = {}
        for col in config.get("columns", {}).get("dynamic_columns", []):
            key = col.get("keybinding")
            if key:
                column_map[key] = {
                    "col_name": col["name"],
                    "data_type": col.get("data_type", "Text/String"),
                    "color": col.get("color"),
                }
        return column_map

    # ------------------------------------------------------------------
    # File I/O (raise on error; no dialogs)
    # ------------------------------------------------------------------
    def save_config_to_file(self, config: dict, filepath: Union[str, Path]) -> Path:
        """Write ``config`` to ``filepath`` as JSON. Returns the path."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return path

    def load_config_from_file(self, filepath: Union[str, Path]) -> Optional[dict]:
        """
        Load and validate a config from ``filepath``.

        Returns the config dict if valid, ``None`` if validation fails.
        Raises ``FileNotFoundError`` if the file does not exist.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config if self.validate_config(config) else None
