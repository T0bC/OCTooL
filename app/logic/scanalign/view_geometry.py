"""
ScanAlign View Geometry.

Pure coordinate mapping between the pixel grids of two scans, aligned by physical
size (micrometres per pixel) and image centre. Used to keep the zoom/pan of the two
viewers on the same physical region and to resample Scan 1 into Scan 2's grid.
If the pixel spacing is unknown, pixels are mapped 1:1 (centred).

Key contents:
- GridMap: Scale factors (Scan 2 px per Scan 1 px) and image centres of both scans.
- grid_map: Builds the GridMap from two ScanGeometry objects.
- map_point: Scan 1 image point -> Scan 2 image point.
- inverse_point: Scan 2 image point -> Scan 1 image point.
- map_view: Transfers zoom/offset of one viewer canvas to the other.

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

from typing import NamedTuple

from app.logic.scanalign.models import ScanGeometry


class GridMap(NamedTuple):
    """Mapping between the pixel grids of Scan 1 and Scan 2."""

    sx: float
    sz: float
    c1: tuple[float, float]
    c2: tuple[float, float]
    physical: bool


def _known(value: float | None) -> bool:
    return value is not None and value > 0


def grid_map(g1: ScanGeometry, g2: ScanGeometry) -> GridMap:
    """Build the grid map; physical only if all four pixel sizes are known and > 0."""
    c1 = (g1.width_px / 2, g1.height_px / 2)
    c2 = (g2.width_px / 2, g2.height_px / 2)
    if all(_known(v) for v in (g1.px_size_x_um, g1.px_size_z_um, g2.px_size_x_um, g2.px_size_z_um)):
        sx = g1.px_size_x_um / g2.px_size_x_um  # type: ignore[operator]
        sz = g1.px_size_z_um / g2.px_size_z_um  # type: ignore[operator]
        return GridMap(sx, sz, c1, c2, True)
    return GridMap(1.0, 1.0, c1, c2, False)


def map_point(m: GridMap, x1: float, z1: float) -> tuple[float, float]:
    """Map a Scan 1 image point to the Scan 2 image."""
    return (x1 - m.c1[0]) * m.sx + m.c2[0], (z1 - m.c1[1]) * m.sz + m.c2[1]


def inverse_point(m: GridMap, x2: float, z2: float) -> tuple[float, float]:
    """Map a Scan 2 image point to the Scan 1 image."""
    return (x2 - m.c2[0]) / m.sx + m.c1[0], (z2 - m.c2[1]) / m.sz + m.c1[1]


def map_view(
    zoom: float,
    ox: float,
    oy: float,
    src_canvas: tuple[float, float],
    dst_canvas: tuple[float, float],
    m: GridMap,
    forward: bool,
) -> tuple[float, float, float]:
    """Transfer an effective zoom/offset from the source canvas to the destination canvas.

    The image point at the source canvas centre is mapped to the destination image
    (``forward``: Scan 1 -> Scan 2, else Scan 2 -> Scan 1) and placed at the destination
    canvas centre. The X spacing alone drives the zoom ratio.

    Returns:
        ``(zoom, ox, oy)`` for the destination viewer.
    """
    px = (src_canvas[0] / 2 - ox) / zoom
    pz = (src_canvas[1] / 2 - oy) / zoom
    if forward:
        qx, qz = map_point(m, px, pz)
        dst_zoom = zoom / m.sx
    else:
        qx, qz = inverse_point(m, px, pz)
        dst_zoom = zoom * m.sx
    return dst_zoom, dst_canvas[0] / 2 - qx * dst_zoom, dst_canvas[1] / 2 - qz * dst_zoom
