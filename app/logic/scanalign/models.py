"""
ScanAlign Models.

Pydantic models for the ScanAlign logic layer: stack files, scan geometry,
stack info and the geometry comparison of two scans.

Key contents:
- SliceFile: One image file of an exported stack.
- ScanGeometry: Image size and physical pixel/slice dimensions of a scan.
- StackInfo: A loaded stack folder with files, geometry, issues and warnings.
- GeometryComparison: Result of comparing the geometry of two scans.

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

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SliceFile(BaseModel):
    """One image file of an exported stack."""

    path: Path
    slice_number: int | None = Field(
        default=None, description="Parsed '#N' (1-based, original volume); None if unparsed"
    )
    export_index: int | None = Field(
        default=None, description="Parsed 4-digit export index; None if unparsed"
    )

    model_config = {"frozen": True}


class ScanGeometry(BaseModel):
    """Image size and physical dimensions of a scan."""

    n_slices: int = Field(description="Image files in the folder")
    width_px: int
    height_px: int
    px_size_x_um: float | None = None
    px_size_z_um: float | None = None
    slice_spacing_um: float | None = None
    length_y_mm: float | None = None
    header_dim_y: int | None = Field(default=None, description="Slices in the source volume")
    source: Literal["header", "dpi", "none"] = "none"
    oct_path: Path | None = None


class StackInfo(BaseModel):
    """A loaded stack folder."""

    folder: Path
    specimen: str = Field(description="Name of the folder containing the export folder")
    name: str | None = None
    exp_number: int | None = None
    extension: str = ""
    files: list[SliceFile]
    geometry: ScanGeometry
    gaps: list[int] = Field(default_factory=list)
    duplicates: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GeometryComparison(BaseModel):
    """Result of comparing the geometry of two scans."""

    differs: dict[str, bool]
    kind: Literal["identical", "same_spacing_longer", "same_length_denser", "different", "unknown"]
    verdict: str
