"""
ScanAlign Overlay.

Composites Scan 1 onto Scan 2 for visual comparison. Scan 1 is resampled into
Scan 2's pixel grid (physical size, centred) so the result lives in viewer 2's
coordinates. Four modes: alpha blend, checkerboard, difference and
magenta/green fusion.

Key contents:
- OverlayMode: Literal of the supported modes.
- DEFAULT_ALPHA, DEFAULT_TILE: Default blend weight and checkerboard tile size.
- to_gray: PIL image -> uint8 grayscale array.
- resample_to: Scan 1 resampled into Scan 2's grid (array + validity mask).
- blend, checkerboard, difference, fusion: The per-mode pixel operations.
- compose: Full composite as PIL image of Scan 2's size.
- compose_arrays: Same from an already resampled Scan 1 (cacheable).

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

from typing import Literal

import numpy as np
from PIL import Image

from app.logic.scanalign.view_geometry import GridMap

OverlayMode = Literal["blend", "checker", "difference", "fusion"]

DEFAULT_ALPHA = 0.5
DEFAULT_TILE = 128


def to_gray(img: Image.Image) -> np.ndarray:
    """Convert a PIL image to a uint8 grayscale array (16-bit modes keep the high byte)."""
    if img.mode == "L":
        return np.asarray(img, dtype=np.uint8)
    if img.mode in ("I;16", "I"):
        arr = np.asarray(img).astype(np.uint16)
        return (arr >> 8).astype(np.uint8)
    return np.asarray(img.convert("L"), dtype=np.uint8)


def resample_to(
    img1: Image.Image, m: GridMap, size2: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    """Resample Scan 1 into Scan 2's pixel grid.

    Returns:
        ``(array, mask)``: uint8 array of shape ``(h, w)`` and a bool mask that is True
        where Scan 1 has data.
    """
    (c1x, c1z), (c2x, c2z) = m.c1, m.c2
    coeffs = (1 / m.sx, 0, c1x - c2x / m.sx, 0, 1 / m.sz, c1z - c2z / m.sz)
    gray = Image.fromarray(to_gray(img1), "L")
    out = gray.transform(size2, Image.AFFINE, coeffs, Image.BILINEAR, fillcolor=0)
    ones = Image.new("L", gray.size, 255)
    mask_img = ones.transform(size2, Image.AFFINE, coeffs, Image.NEAREST, fillcolor=0)
    return np.asarray(out, dtype=np.uint8), np.asarray(mask_img) > 0


def blend(a1: np.ndarray, a2: np.ndarray, alpha: float) -> np.ndarray:
    """Alpha blend; ``alpha`` is the weight of Scan 2."""
    out = a1.astype(np.float32) * (1 - alpha) + a2.astype(np.float32) * alpha
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def checkerboard(a1: np.ndarray, a2: np.ndarray, tile: int) -> np.ndarray:
    """Checkerboard of ``tile`` px squares; the top-left tile shows Scan 1."""
    tile = max(1, int(tile))
    h, w = a2.shape
    use1 = ((np.arange(h)[:, None] // tile + np.arange(w)[None, :] // tile) % 2) == 0
    return np.where(use1, a1, a2)


def difference(a1: np.ndarray, a2: np.ndarray) -> np.ndarray:
    """Absolute difference."""
    return np.abs(a1.astype(np.int16) - a2.astype(np.int16)).astype(np.uint8)


def fusion(a1: np.ndarray, a2: np.ndarray) -> np.ndarray:
    """RGB fusion: Scan 1 green, Scan 2 magenta (R=a2, G=a1, B=a2)."""
    return np.stack([a2, a1, a2], axis=-1)


def compose(
    img1: Image.Image,
    img2: Image.Image,
    m: GridMap,
    mode: OverlayMode,
    alpha: float = DEFAULT_ALPHA,
    tile: int = DEFAULT_TILE,
) -> Image.Image:
    """Composite Scan 1 onto Scan 2; the result has ``img2.size``.

    Outside the area covered by Scan 1, blend/checker show Scan 2 and difference is 0.
    Returns an "RGB" image for fusion, otherwise "L".
    """
    a1, mask = resample_to(img1, m, img2.size)
    return compose_arrays(a1, mask, img2, mode, alpha, tile)


def compose_arrays(
    a1: np.ndarray,
    mask: np.ndarray,
    img2: Image.Image,
    mode: OverlayMode,
    alpha: float = DEFAULT_ALPHA,
    tile: int = DEFAULT_TILE,
) -> Image.Image:
    """Combine an already resampled Scan 1 (``a1`` + ``mask``, see resample_to) with Scan 2.

    Lets callers cache the resampling while only the mode or its parameters change.
    """
    a2 = to_gray(img2)
    if mode == "blend":
        out = np.where(mask, blend(a1, a2, alpha), a2)
    elif mode == "checker":
        out = np.where(mask, checkerboard(a1, a2, tile), a2)
    elif mode == "difference":
        out = np.where(mask, difference(a1, a2), 0).astype(np.uint8)
    elif mode == "fusion":
        return Image.fromarray(fusion(a1, a2), "RGB")
    else:
        raise ValueError(f"Unknown overlay mode: {mode}")
    return Image.fromarray(out.astype(np.uint8), "L")
