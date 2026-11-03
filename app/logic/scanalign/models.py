"""
ScanAlign Models.

Pydantic models for the ScanAlign logic layer: stack files, scan geometry,
stack info and the geometry comparison of two scans.

Key contents:
- SliceFile: One image file of an exported stack.
- ScanGeometry: Image size and physical pixel/slice dimensions of a scan.
- StackInfo: A loaded stack folder with files, geometry, issues and warnings.
- GeometryComparison: Result of comparing the geometry of two scans.
- SliceRange: Inclusive first/last 0-based positions chosen in one stack.
- SlicePair: One matched slice pair (k, positions and '#' numbers of both scans).
- ExportResult: Outcome of a ScanAlign export (folders, file count, cancelled).
- RegistrationScanInfo / RegistrationPairEntry / RegistrationLog: Self-contained
  content of the scanalign_registration.json written into both output folders.

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

from pydantic import BaseModel, Field, model_validator


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


class SliceRange(BaseModel):
    """Inclusive range of 0-based positions in ``stack.files``."""

    first: int
    last: int

    @model_validator(mode="after")
    def _check_order(self) -> "SliceRange":
        if not 0 <= self.first < self.last:
            raise ValueError(
                f"Invalid range: need 0 <= first < last, got {self.first}, {self.last}"
            )
        return self

    @property
    def length(self) -> int:
        """Number of slices in the range."""
        return self.last - self.first + 1


class SlicePair(BaseModel):
    """One matched slice pair; ``k`` is shared by both output files."""

    k: int = Field(description="1-based pair index")
    index1: int = Field(description="0-based position in stack 1")
    index2: int = Field(description="0-based position in stack 2")
    slice1: int = Field(description="'#' number of stack 1 used in the output name")
    slice2: int = Field(description="'#' number of stack 2 used in the output name")


class ExportResult(BaseModel):
    """Outcome of a ScanAlign export."""

    folders: tuple[Path, Path]
    n_files: int
    cancelled: bool = False


class RegistrationScanInfo(BaseModel):
    """Description of one scan inside the registration log."""

    source_folder: Path
    oct_path: Path | None = None
    specimen: str
    name: str | None = None
    exp: int
    n_slices: int
    geometry: ScanGeometry
    warnings: list[str] = Field(default_factory=list)
    range_positions: tuple[int, int] = Field(description="First/last 0-based position")
    range_slice_numbers: tuple[int, int] = Field(description="First/last '#' number")
    output_folder: Path


class RegistrationPairEntry(BaseModel):
    """One pair with the source and output file names of both scans."""

    k: int
    slice1: int
    slice2: int
    source1: str
    source2: str
    output1: str
    output2: str


class RegistrationLog(BaseModel):
    """Content of ``scanalign_registration.json`` (dump with ``model_dump(mode="json")``).

    ``scan`` is the scan whose folder holds this file, ``partner`` the other one.
    ``offset``, ``scale`` and the pair entries are always expressed with Scan 1
    (``role == "reference"``) as reference and Scan 2 (``"moving"``) as second.
    """

    schema_version: int = 1
    octool_version: str
    created: str = Field(description="ISO timestamp with local timezone")
    role: Literal["reference", "moving"]
    scan: RegistrationScanInfo
    partner: RegistrationScanInfo
    n: int
    offset: int = Field(description="first position of scan 2 minus scan 1")
    scale: float = Field(description="range length of scan 2 / scan 1")
    comparison: GeometryComparison
    pairs: list[RegistrationPairEntry]
