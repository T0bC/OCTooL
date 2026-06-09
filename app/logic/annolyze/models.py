"""
AnnoLyze Pydantic Models.

Data models for OCT image annotation, dynamic columns, configuration, and
measurement undo history. These are pure data structures (no tkinter) passed
across the logic/view boundary.

Key contents:
- Annotation: A single poly-line or spline annotation on one image slice.
- MetadataConfig: Operator, measurement, and system metadata for a sample.
- ColumnSpec: Specification for a dynamic results column (name, keybinding, type, color).
- AnnotationConfig: Full analysis configuration combining metadata and column list.
- UndoAction: A single recorded cell change for undo/redo history.

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


from datetime import datetime
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


# A point is stored as (x, y) in image coordinates.
Point = Tuple[float, float]

# Data types a dynamic column can hold.
DataType = Literal[
    "Continuous",
    "Percentage",
    "Boolean",
    "Categorical",
    "Ordinal",
    "Integer",
    "Float",
    "Text/String",
]

# Data types that are not drawn as curves but shown as text overlays.
NON_DRAWN_TYPES = ("Boolean", "Categorical", "Ordinal", "Text/String")


class Annotation(BaseModel):
    """A single annotation (poly-line or spline) on one image slice."""

    id: Optional[str] = Field(default=None, description="Unique annotation id, e.g. 'GAP_0'")
    feature: str = Field(default="unknown", description="Feature/column name this annotation belongs to")
    points: List[Point] = Field(default_factory=list, description="Points in image coordinates")
    mode: Literal["line", "spline"] = Field(default="line", description="Rendering mode")
    color: str = Field(default="#FFFFFF", description="Hex color string")
    locked: bool = Field(default=False, description="Whether the annotation is committed/locked")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of creation")

    model_config = {"validate_assignment": True}

    @classmethod
    def normalize(cls, data: dict) -> "Annotation":
        """Create an Annotation from a loosely-typed dict, filling defaults."""
        return cls(
            id=data.get("id"),
            feature=data.get("feature", "unknown"),
            points=[tuple(p) for p in data.get("points", [])],
            mode=data.get("mode", "line"),
            color=data.get("color", "#FFFFFF"),
            locked=data.get("locked", False),
            timestamp=data.get("timestamp") or datetime.now().isoformat(),
        )

    def to_serializable(self) -> dict:
        """Return a JSON-serializable dict (points as lists)."""
        return {
            "id": self.id,
            "feature": self.feature,
            "points": [list(p) for p in self.points],
            "mode": self.mode,
            "color": self.color,
            "locked": self.locked,
            "timestamp": self.timestamp or datetime.now().isoformat(),
        }


class MetadataConfig(BaseModel):
    """Operator/measurement/system metadata for a sample."""

    operator: str = Field(default="TM")
    measurement: str = Field(default="1")
    system: str = Field(default="OCT")

    @classmethod
    def from_gui_state(cls, *, operator: str, measurement: str, system: str) -> "MetadataConfig":
        return cls(
            operator=str(operator),
            measurement=str(measurement),
            system=str(system),
        )


class ColumnSpec(BaseModel):
    """Specification for a dynamic results column."""

    name: str
    keybinding: str = Field(default="")
    position_after: str = Field(default="SLICE")
    order: int = Field(default=0, ge=0)
    data_type: str = Field(default="Text/String")
    color: str = Field(default="#FFFFFF")

    def to_config_dict(self) -> dict:
        return {
            "name": self.name,
            "keybinding": self.keybinding,
            "position_after": self.position_after,
            "order": self.order,
            "data_type": self.data_type,
            "color": self.color,
        }

    @classmethod
    def from_config_dict(cls, data: dict) -> "ColumnSpec":
        return cls(
            name=data["name"],
            keybinding=data.get("keybinding", ""),
            position_after=data.get("position_after", "SLICE"),
            order=data.get("order", 0),
            data_type=data.get("data_type", "Text/String"),
            color=data.get("color", "#FFFFFF"),
        )


class AnnotationConfig(BaseModel):
    """Full analysis configuration (metadata + dynamic columns + info)."""

    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    columns: List[ColumnSpec] = Field(default_factory=list)
    version: str = Field(default="1.0")
    description: str = Field(default="OCTooL Analysis Configuration")

    @classmethod
    def from_dict(cls, data: dict) -> "AnnotationConfig":
        """Parse a raw config dict (as stored on disk) into a model."""
        meta = data.get("metadata", {})
        cols = data.get("columns", {}).get("dynamic_columns", [])
        info = data.get("config_info", {})
        return cls(
            metadata=MetadataConfig(
                operator=meta.get("operator", "TM"),
                measurement=meta.get("measurement", "1"),
                system=meta.get("system", "OCT"),
            ),
            columns=[ColumnSpec.from_config_dict(c) for c in cols],
            version=info.get("version", "1.0"),
            description=info.get("description", "OCTooL Analysis Configuration"),
        )

    def to_dict(self) -> dict:
        """Serialize to the on-disk config dict format."""
        return {
            "metadata": {
                "operator": self.metadata.operator,
                "measurement": self.metadata.measurement,
                "system": self.metadata.system,
            },
            "columns": {
                "dynamic_columns": [c.to_config_dict() for c in self.columns]
            },
            "ui_settings": {
                "sheet_width": 800,
                "sheet_height": 400,
            },
            "config_info": {
                "created_date": datetime.now().isoformat(),
                "version": self.version,
                "description": self.description,
            },
        }


class UndoAction(BaseModel):
    """A single recorded cell change for undo history."""

    row: int
    col: int
    col_name: str
    old_value: str = Field(default="")
    new_value: str = Field(default="")
    key: str = Field(default="")
    feature: Optional[str] = Field(default=None)
    annotation_id: Optional[str] = Field(default=None)
    color: str = Field(default="#FFFFFF")
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}
