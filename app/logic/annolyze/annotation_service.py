"""
AnnoLyze Annotation Service.

Pure annotation geometry, colour, and (de)serialization logic — no tkinter.
Extracted from the AnnoLyze annotation panel so it can be unit-tested
headlessly.

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


from typing import Dict, List, Optional, Tuple

import numpy as np

from app.logic.annolyze.models import Annotation

Point = Tuple[float, float]

# A cubic spline (k=3) needs at least 4 points; below this we fall back to lines.
MIN_SPLINE_POINTS = 4
DEFAULT_COLOR = "#ffffb2"


class AnnotationService:
    """Pure logic for annotation geometry and serialization."""

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    def polyline_length(self, points: List[Point]) -> float:
        """Total Euclidean length of a poly-line through ``points``."""
        if not points or len(points) < 2:
            return 0.0
        pts = np.asarray(points, dtype=float)
        diffs = np.diff(pts, axis=0)
        return float(np.sum(np.sqrt(np.sum(diffs ** 2, axis=1))))

    def spline_points(self, points: List[Point], num: int = 500) -> List[Point]:
        """
        Sample a cubic spline through ``points``.

        Falls back to the original points if there are fewer than
        ``MIN_SPLINE_POINTS`` or the spline fit fails.
        """
        if len(points) < MIN_SPLINE_POINTS:
            return [tuple(p) for p in points]
        try:
            from scipy.interpolate import splprep, splev
            pts_np = np.asarray(points, dtype=float)
            tck, _ = splprep([pts_np[:, 0], pts_np[:, 1]], s=0, k=3)
            u = np.linspace(0, 1, num)
            x_new, y_new = splev(u, tck)
            return list(zip(x_new.tolist(), y_new.tolist()))
        except Exception:
            return [tuple(p) for p in points]

    def annotation_length(self, points: List[Point], mode: str) -> float:
        """
        Length of an annotation in the given ``mode`` ('line' or 'spline').

        Spline mode with too few points (or a failed fit) falls back to the
        poly-line length.
        """
        if len(points) < 2:
            return 0.0
        if mode == "line" or len(points) < MIN_SPLINE_POINTS:
            return self.polyline_length(points)
        try:
            from scipy.interpolate import splprep, splev
            pts = np.asarray(points, dtype=float)
            tck, _ = splprep([pts[:, 0], pts[:, 1]], s=0, k=3)
            u = np.linspace(0, 1, 1000)
            x_new, y_new = splev(u, tck)
            return float(np.sum(np.sqrt(np.diff(x_new) ** 2 + np.diff(y_new) ** 2)))
        except Exception:
            return self.polyline_length(points)

    # ------------------------------------------------------------------
    # Color
    # ------------------------------------------------------------------
    def hex_to_rgba(self, color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
        """Convert a ``#RRGGBB`` hex string to an RGBA tuple."""
        if isinstance(color, str) and color.startswith("#") and len(color) >= 7:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return (r, g, b, alpha)
        return (255, 255, 178, alpha)  # default yellow

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def make_annotation_id(self, label: str, existing_count: int) -> str:
        """Build a deterministic annotation id like ``GAP_0``."""
        return f"{label}_{existing_count}"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def normalize(self, raw: dict) -> dict:
        """Normalize a loosely-typed annotation dict, filling defaults."""
        return Annotation.normalize(raw).model_dump()

    def serialize_slice_annotations(
        self, slice_annotations: Dict[int, List[dict]]
    ) -> Dict[str, List[dict]]:
        """
        Convert ``{slice_index: [annotation_dict, ...]}`` to the on-disk JSON
        structure ``{"slice_<i>": [serializable, ...]}``.
        """
        result: Dict[str, List[dict]] = {}
        for slice_index, annotations in slice_annotations.items():
            key = f"slice_{slice_index}"
            result[key] = [Annotation.normalize(a).to_serializable() for a in annotations]
        return result

    def deserialize_annotations(
        self, json_data: Dict[str, List[dict]]
    ) -> Dict[int, List[dict]]:
        """
        Convert the on-disk JSON structure back to ``{slice_index: [annotation_dict]}``.
        """
        result: Dict[int, List[dict]] = {}
        for slice_key, annotations in json_data.items():
            slice_index = int(str(slice_key).replace("slice_", ""))
            result[slice_index] = [Annotation.normalize(a).model_dump() for a in annotations]
        return result
