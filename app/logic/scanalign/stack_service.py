"""
ScanAlign Stack Service.

Pure business logic (no tkinter) for loading an exported RexView image stack:
filename parsing, sorting, slice-issue detection, header/DPI geometry and the
geometry comparison of two scans.

Key contents:
- parse_filename: Parses a RexView export filename from the right.
- list_stack_files: Lists and sorts the image files of a stack folder.
- find_slice_issues: Detects gaps and duplicate slice numbers.
- find_oct_file / read_header_metadata: Locates and reads the source .oct header.
- build_geometry: Builds the ScanGeometry from header metadata or image DPI.
- load_stack: Loads a complete StackInfo for a folder.
- compare_geometry: Compares the geometry of two scans.

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

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

from PIL import Image

from app.logic.carlquant.data_io import IMAGE_EXTENSIONS
from app.logic.scanalign.models import (
    GeometryComparison,
    ScanGeometry,
    SliceFile,
    StackInfo,
)
from app.logic.shared.models import OCTMetadata
from app.logic.shared.paths import natural_sort_key

logger = logging.getLogger(__name__)

FILENAME_RE = re.compile(
    r"^(?P<name>.+)_(?P<exp>\d+)_#(?P<slice>\d+)_(?P<idx>\d+)\.(?P<ext>png|tiff?)$",
    re.IGNORECASE,
)

_IMAGE_SUFFIXES = frozenset(Path(pattern).suffix.lower() for pattern in IMAGE_EXTENSIONS)
_MAX_LISTED_NUMBERS = 5


def parse_filename(path: Path) -> tuple[str, int, int, int] | None:
    """Parse ``{name}_{exp}_#{slice}_{idx}{ext}`` into ``(name, exp, slice, idx)``."""
    match = FILENAME_RE.match(Path(path).name)
    if match is None:
        return None
    return (
        match.group("name"),
        int(match.group("exp")),
        int(match.group("slice")),
        int(match.group("idx")),
    )


def list_stack_files(folder: Path) -> list[SliceFile]:
    """List the image files of ``folder`` (non-recursive), sorted.

    Sorted by ``(slice_number, export_index)`` when every file parses, otherwise
    all files are sorted by natural file-name order.
    """
    paths = [
        p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    ]
    files: list[SliceFile] = []
    for path in paths:
        parsed = parse_filename(path)
        files.append(
            SliceFile(
                path=path,
                slice_number=parsed[2] if parsed else None,
                export_index=parsed[3] if parsed else None,
            )
        )
    if all(f.slice_number is not None for f in files):
        files.sort(key=lambda f: (f.slice_number, f.export_index))
    else:
        files.sort(key=lambda f: natural_sort_key(f.path))
    return files


def find_slice_issues(files: list[SliceFile]) -> tuple[list[int], list[int]]:
    """Return ``(gaps, duplicates)`` of the parsed slice numbers.

    Gaps are the missing numbers between min and max; duplicates are numbers
    occurring more than once.
    """
    numbers = [f.slice_number for f in files if f.slice_number is not None]
    if not numbers:
        return [], []
    present = set(numbers)
    gaps = [n for n in range(min(numbers), max(numbers) + 1) if n not in present]
    counts = Counter(numbers)
    duplicates = sorted(n for n, c in counts.items() if c > 1)
    return gaps, duplicates


def _select_oct(folder: Path, name: str | None) -> tuple[Path | None, str | None]:
    """Pick the .oct next to the export folder; returns ``(path, warning)``."""
    parent = Path(folder).parent
    try:
        candidates = sorted(
            p for p in parent.iterdir() if p.is_file() and p.suffix.lower() == ".oct"
        )
    except OSError:
        return None, None
    if not candidates:
        return None, None
    if name:
        for candidate in candidates:
            if candidate.stem == name:
                return candidate, None
    if len(candidates) == 1:
        return candidates[0], None
    # Several candidates, none matching the parsed name: prefer one named in the folder.
    in_folder = [c for c in candidates if c.stem in Path(folder).name]
    if in_folder:
        return max(in_folder, key=lambda c: len(c.stem)), None
    return candidates[0], (
        f"Several .oct files found; using {candidates[0].name} (none matches the export name)"
    )


def find_oct_file(folder: Path, name: str | None) -> Path | None:
    """Find the source ``.oct`` in the folder containing the export folder.

    Prefers the file whose stem equals ``name``.
    """
    return _select_oct(folder, name)[0]


def read_header_metadata(oct_path: Path) -> OCTMetadata | None:
    """Read Header.xml of an ``.oct`` archive; None on any failure."""
    from app.logic.shared.oct_functions import getXMLAttributes, readXMLContent, unzipOCTData

    archive = None
    try:
        archive = unzipOCTData(oct_path)
        xml_content = readXMLContent(archive, "Header.xml", "xml")
        return OCTMetadata.from_xml_dict(getXMLAttributes(xml_content))
    except Exception:  # noqa: BLE001 - the caller reports a warning
        logger.warning("Could not read header of %s", oct_path, exc_info=True)
        return None
    finally:
        if archive is not None:
            archive.close()


def build_geometry(
    files: list[SliceFile],
    metadata: OCTMetadata | None,
    first_image_path: Path,
    oct_path: Path | None = None,
) -> ScanGeometry:
    """Build the geometry from header metadata, falling back to the image DPI.

    RexView writes px/mm into the DPI field (labelled as inch), so a DPI of 204
    means 204 px/mm, i.e. a pixel size of ``1000 / dpi`` um.
    """
    with Image.open(first_image_path) as img:
        width, height = img.size
        dpi = img.info.get("dpi")

    n_slices = len(files)
    if metadata is not None:
        spacing = metadata.spacing_y if metadata.spacing_y > 0 else None
        if spacing is None and metadata.img_size_mm_y and metadata.dim_y:
            spacing = metadata.img_size_mm_y * 1000 / metadata.dim_y
        return ScanGeometry(
            n_slices=n_slices,
            width_px=width,
            height_px=height,
            px_size_x_um=(
                metadata.img_size_mm_x * 1000 / width if metadata.img_size_mm_x else None
            ),
            px_size_z_um=(
                metadata.img_size_mm_z * 1000 / height if metadata.img_size_mm_z else None
            ),
            slice_spacing_um=spacing,
            length_y_mm=metadata.img_size_mm_y,
            header_dim_y=metadata.dim_y,
            source="header",
            oct_path=oct_path,
        )

    dpi_x = dpi_y = None
    try:
        if dpi and float(dpi[0]) > 0 and float(dpi[1]) > 0:
            dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
    except (TypeError, ValueError, IndexError):
        pass
    return ScanGeometry(
        n_slices=n_slices,
        width_px=width,
        height_px=height,
        px_size_x_um=1000 / dpi_x if dpi_x else None,
        px_size_z_um=1000 / dpi_y if dpi_y else None,
        source="dpi" if dpi_x else "none",
    )


def _summarize_numbers(label: str, numbers: list[int]) -> str:
    shown = ", ".join(str(n) for n in numbers[:_MAX_LISTED_NUMBERS])
    extra = len(numbers) - _MAX_LISTED_NUMBERS
    suffix = f" (+{extra} more)" if extra > 0 else ""
    return f"{label} ({len(numbers)}): {shown}{suffix}"


def load_stack(folder: Path) -> StackInfo:
    """Load a stack folder: files, geometry, issues and warnings.

    Raises:
        ValueError: if the folder contains no PNG/TIFF images.
    """
    folder = Path(folder)
    files = list_stack_files(folder)
    if not files:
        raise ValueError(f"No PNG/TIFF images found in {folder}")

    warnings: list[str] = []
    parsed = [parse_filename(f.path) for f in files]
    first_parsed = next((p for p in parsed if p is not None), None)
    name = first_parsed[0] if first_parsed else None
    exp_number = first_parsed[1] if first_parsed else None
    if any(p is None for p in parsed):
        warnings.append("Filenames do not follow the RexView pattern; sorted by file name")

    suffixes = {f.path.suffix.lower() for f in files}
    if len(suffixes) > 1:
        warnings.append(f"Mixed file extensions: {', '.join(sorted(suffixes))}")

    gaps, duplicates = find_slice_issues(files)
    if gaps:
        warnings.append(_summarize_numbers("Missing slice numbers", gaps))
    if duplicates:
        warnings.append(_summarize_numbers("Duplicate slice numbers", duplicates))

    oct_path, oct_warning = _select_oct(folder, name)
    if oct_warning:
        warnings.append(oct_warning)
    metadata = None
    if oct_path is not None:
        metadata = read_header_metadata(oct_path)
        if metadata is None:
            warnings.append(f"Could not read Header.xml of {oct_path.name}; using image DPI")
    else:
        warnings.append("No .oct file found next to the export; using image DPI for pixel size")

    geometry = build_geometry(
        files, metadata, files[0].path, oct_path if metadata is not None else None
    )
    if geometry.header_dim_y is not None and geometry.header_dim_y != geometry.n_slices:
        warnings.append(f"Export contains {geometry.n_slices} of {geometry.header_dim_y} slices")
    if geometry.source == "none":
        warnings.append("No pixel size available (no header and no image DPI)")

    return StackInfo(
        folder=folder,
        specimen=folder.parent.name,
        name=name,
        exp_number=exp_number,
        extension=files[0].path.suffix.lower(),
        files=files,
        geometry=geometry,
        gaps=gaps,
        duplicates=duplicates,
        warnings=warnings,
    )


def _differs(a: float | None, b: float | None, rel_tol: float) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) > rel_tol * max(abs(a), abs(b))


def compare_geometry(
    g1: ScanGeometry, g2: ScanGeometry, rel_tol: float = 0.01
) -> GeometryComparison:
    """Compare two scan geometries.

    A value differs when both are present and differ by more than ``rel_tol``
    (relative). ``n_slices`` and ``size`` compare exactly.
    """
    differs = {
        "n_slices": g1.n_slices != g2.n_slices,
        "size": (g1.width_px, g1.height_px) != (g2.width_px, g2.height_px),
        "px_size_x_um": _differs(g1.px_size_x_um, g2.px_size_x_um, rel_tol),
        "px_size_z_um": _differs(g1.px_size_z_um, g2.px_size_z_um, rel_tol),
        "slice_spacing_um": _differs(g1.slice_spacing_um, g2.slice_spacing_um, rel_tol),
        "length_y_mm": _differs(g1.length_y_mm, g2.length_y_mm, rel_tol),
    }

    if None in (g1.slice_spacing_um, g2.slice_spacing_um, g1.length_y_mm, g2.length_y_mm):
        return GeometryComparison(
            differs=differs,
            kind="unknown",
            verdict="Slice spacing or scan length unknown; scans cannot be compared fully.",
        )

    if not any(differs.values()):
        return GeometryComparison(
            differs=differs, kind="identical", verdict="Both scans have identical geometry."
        )

    slice_diff = g2.n_slices - g1.n_slices
    length_diff = g2.length_y_mm - g1.length_y_mm
    if differs["slice_spacing_um"]:
        if not differs["length_y_mm"]:
            denser = 2 if g2.slice_spacing_um < g1.slice_spacing_um else 1
            kind = "same_length_denser"
            verdict = (
                f"Same scan length - Scan {denser} is denser "
                f"({g1.slice_spacing_um:.1f} vs {g2.slice_spacing_um:.1f} um spacing)."
            )
        else:
            kind = "different"
            verdict = (
                "Different slice spacing and scan length "
                f"({g1.slice_spacing_um:.1f} vs {g2.slice_spacing_um:.1f} um, "
                f"{g1.length_y_mm:.1f} vs {g2.length_y_mm:.1f} mm)."
            )
    elif differs["length_y_mm"]:
        longer = 2 if length_diff > 0 else 1
        signed = slice_diff if longer == 2 else -slice_diff
        kind = "same_spacing_longer"
        verdict = (
            f"Same slice spacing - Scan {longer} covers {abs(length_diff):.1f} mm more "
            f"({signed:+d} slices)."
        )
    elif differs["n_slices"]:
        more = 2 if slice_diff > 0 else 1
        kind = "same_spacing_longer"
        verdict = f"Same slice spacing - Scan {more} has {abs(slice_diff)} more slices exported."
    else:
        kind = "different"
        verdict = "Scans differ in image size or pixel size."
    return GeometryComparison(differs=differs, kind=kind, verdict=verdict)
