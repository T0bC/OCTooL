# -*- coding: utf-8 -*-
"""
CarlQuant Detection Validation Scoring.

Scores the automatic lesion-depth detection against operator-annotated ground
truth (see ``ground_truth.py``). Pure functions with no UI imports: every number
shown in validation mode comes from here.

Sign convention, used throughout this project:

    +  detection is too DEEP    (below the operator's mark)
    -  detection is too SHALLOW

Scoring happens at two scales and both are reported. Per-column error is what an
A-scan reader sees; the specimen mean is what downstream analysis consumes, and
a consistently signed bias does *not* cancel under averaging -- so the two can
rank methods differently. Reporting only one hides that.

Interpolation is **display only**. ``interpolate_marks`` fills the gaps between
an operator's ~18 marks so every column can show a reference, but scoring reads
real marks alone -- an inferred value must never reach a reported error.

Key contents:
- METHODS: The depth measures compared, in report order.
- interpolate_marks: Smooth curve through one slice's marks, for display.
- interpolated_mark_at: Interpolated ground-truth depth at one column.
- nearest_analysed_column: Maps a mark's x to the nearest analysed A-scan column.
- method_depth: Reads one method's depth from a column, handling the naming trap.
- method_errors: Signed per-mark errors for one method.
- score_slice: Per-method median / |median| / p90 / n for one slice.
- score_specimen: Aggregates per-slice results at both scales.

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



from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

#: Depth measures compared against ground truth, in the order they are reported.
#: "combined" is the value the app actually reports; the rest are its ingredients
#: plus the shoulder, which is displayed but is not part of the rule.
METHODS = ["combined", "half_span", "knee", "inflection", "shoulder"]

#: Human-readable labels for the results table.
METHOD_LABELS = {
    "combined": "Combined",
    "half_span": "Half-Span",
    "knee": "Knee Point",
    "inflection": "Inflection",
    "shoulder": "Shoulder",
}

#: Keys inside ``detection_metadata`` holding each component method's depth.
#:
#: ``knee_depth`` here is always the raw knee point. The slice's final result
#: is a separate top-level key (``lesion_depth_px``), so "combined" is absent
#: from this map and read separately in ``method_depth``.
_METADATA_KEYS = {
    "half_span": "half_span_depth",
    "knee": "knee_depth",
    "inflection": "inflection_depth",
    "shoulder": "shoulder_depth",
}

#: How far from a mark's x an analysed column may sit and still be scored (px).
DEFAULT_TOLERANCE = 3

#: ``depth_method_used`` value marking a slice the no-lesion gate fired on.
NO_LESION_METHOD = "no_lesion_surface"


def interpolate_marks(
        marks: Sequence[Tuple[float, float]]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Smooth curve through the operator marks of one slice.

    An operator places roughly 18 marks across a ~375 px lesion, a median of
    ~22 px apart, so most A-scan columns fall between marks and have no ground
    truth of their own. Interpolating gives every column in the marked range a
    reference to display.

    The curve passes *through* the marks rather than smoothing them: each mark
    is a deliberate operator judgement, not a noisy detection, so moving one
    would misrepresent what was clicked.

    Uses PCHIP -- a smooth cubic that is also shape-preserving, so it cannot
    overshoot between two marks. A plain cubic spline was measured on the 793
    collected marks first and overshot by up to **35 px** on slice 0 of the
    held-out specimen, across a 29 px gap; that is deeper than the lesions
    being measured, so it would have invented a lesion end no operator marked.
    Rare (3 of 441 gaps) but severe, and silent.

    Clipped to the marked range -- outside the first and last mark there is no
    operator judgement to infer from, and extrapolating would invent one.

    Returns:
        ``(x, y)`` arrays at 1 px spacing over the marked range, or None if
        there are too few marks to fit.
    """
    if marks is None or len(marks) < 2:
        return None

    points = np.array(sorted(marks, key=lambda mark: mark[0]), dtype=float)
    # Average duplicate columns; the interpolator needs strictly increasing x.
    unique_x, inverse = np.unique(points[:, 0], return_inverse=True)
    if unique_x.size < 2:
        return None
    unique_y = np.array([points[inverse == index, 1].mean()
                         for index in range(unique_x.size)])

    # Round *inwards*: marks have fractional x, so flooring the first / ceiling
    # the last would put grid points outside the marked range, where a
    # non-extrapolating curve is undefined.
    x_full = np.arange(int(np.ceil(unique_x[0])), int(np.floor(unique_x[-1])) + 1,
                       dtype=float)
    if x_full.size == 0:
        return None

    if unique_x.size < 3:
        # PCHIP needs three points; two marks define a straight line anyway.
        return x_full, np.interp(x_full, unique_x, unique_y)

    try:
        from scipy.interpolate import PchipInterpolator
        curve = PchipInterpolator(unique_x, unique_y, extrapolate=False)
        return x_full, np.asarray(curve(x_full), dtype=float)
    except Exception:
        # A curve that will not fit falls back to a straight join, which is
        # still better than showing nothing between marks.
        return x_full, np.interp(x_full, unique_x, unique_y)


def interpolated_mark_at(marks: Sequence[Tuple[float, float]],
                         column_x: float) -> Optional[float]:
    """Interpolated ground-truth y at one column, or None outside the marked range.

    For display only. Scoring uses real marks via :func:`method_errors`, so an
    inferred value can never change a reported error.
    """
    curve = interpolate_marks(marks)
    if curve is None:
        return None

    # Bound by the marks themselves, not the integer grid: a mark at x=540.9
    # is inside the marked range even though the grid stops at 540.
    column_x = float(column_x)
    mark_xs = [float(mark[0]) for mark in marks]
    if column_x < min(mark_xs) or column_x > max(mark_xs):
        return None

    x_full, y_full = curve
    return float(np.interp(column_x, x_full, y_full))


def nearest_analysed_column(lesion_detection_data, x,
                            tolerance: int = DEFAULT_TOLERANCE) -> Optional[int]:
    """Closest analysed A-scan column to ``x``, or None if none is within tolerance.

    Detection runs on a subset of columns, so a mark rarely lands exactly on one.
    Marks with no column nearby are skipped rather than snapped to a distant
    column, which would score the wrong A-scan.
    """
    if not lesion_detection_data:
        return None
    xi = int(round(x))
    candidates = [c for c in range(xi - tolerance, xi + tolerance + 1)
                  if c in lesion_detection_data]
    return min(candidates, key=lambda c: abs(c - xi)) if candidates else None


def method_depth(column: Dict, method: str) -> float:
    """Depth reported by one method for one column, in px below the surface.

    Returns NaN when the method did not produce a value for this column (a fit
    that failed to converge, for instance). NaN is propagated rather than
    replaced by 0, which would score as a detection exactly at the surface.
    """
    if method == "combined":
        # The slice's final result, in raw pixels -- the same space the
        # operator marked in, so the two are directly comparable.
        value = column.get("lesion_depth_px", np.nan)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            # Configs written before the field was split off ``knee_depth``.
            value = column.get("knee_depth", np.nan)
    else:
        metadata = column.get("detection_metadata") or {}
        value = metadata.get(_METADATA_KEYS[method], np.nan)
    if value is None:
        return float(np.nan)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(np.nan)


def method_errors(lesion_detection_data, marks: Sequence[Tuple[float, float]],
                  method: str,
                  tolerance: int = DEFAULT_TOLERANCE) -> np.ndarray:
    """Signed errors (px) of one method against the operator marks.

    ``error = (surface_y at that column + method depth) - mark_y``, so positive
    means the detection sits below the mark, i.e. too deep.
    """
    errors: List[float] = []
    for mark in marks or ():
        mark_x, mark_y = float(mark[0]), float(mark[1])
        column_x = nearest_analysed_column(lesion_detection_data, mark_x, tolerance)
        if column_x is None:
            continue
        column = lesion_detection_data[column_x]
        depth = method_depth(column, method)
        if not np.isfinite(depth):
            continue
        surface_y = column.get("surface_y")
        if surface_y is None:
            continue
        errors.append(float(surface_y) + depth - mark_y)
    return np.array(errors, dtype=float)


def is_gated_slice(lesion_detection_data) -> bool:
    """True if the no-lesion gate fired on this slice.

    A gated slice reports the surface line for every column. It scores normally,
    but the reason its depths are all 0 is worth surfacing rather than hiding.
    """
    for column in (lesion_detection_data or {}).values():
        metadata = column.get("detection_metadata") or {}
        method_used = metadata.get("depth_method_used",
                                   metadata.get("combined_method_used"))
        if method_used == NO_LESION_METHOD:
            return True
    return False


def _summarise(errors: np.ndarray) -> Dict[str, float]:
    """median / |median| / p90 / n for one method's errors."""
    finite = errors[np.isfinite(errors)] if errors.size else errors
    if finite.size == 0:
        # No marks scored: report n=0 and NaN rather than a fabricated 0.0.
        return {"median": float(np.nan), "abs_median": float(np.nan),
                "p90": float(np.nan), "n": 0}
    absolute = np.abs(finite)
    return {
        "median": float(np.median(finite)),
        "abs_median": float(np.median(absolute)),
        "p90": float(np.percentile(absolute, 90)),
        "n": int(finite.size),
    }


def mean_detected_depth(lesion_detection_data, method: str) -> float:
    """Mean depth of one method over every analysed column of a slice.

    This is the slice-level quantity the specimen mean is built from -- the
    number downstream analysis consumes -- as opposed to the per-mark error.
    """
    values = np.array([method_depth(column, method)
                       for column in (lesion_detection_data or {}).values()],
                      dtype=float)
    if values.size == 0 or not np.any(np.isfinite(values)):
        return float(np.nan)
    return float(np.nanmean(values))


def mean_operator_depth(lesion_detection_data,
                        marks: Sequence[Tuple[float, float]],
                        tolerance: int = DEFAULT_TOLERANCE) -> float:
    """Mean depth of the operator's marks below the surface, in px.

    The ground-truth analogue of a slice's reported mean depth.
    """
    depths: List[float] = []
    for mark in marks or ():
        mark_x, mark_y = float(mark[0]), float(mark[1])
        column_x = nearest_analysed_column(lesion_detection_data, mark_x, tolerance)
        if column_x is None:
            continue
        surface_y = lesion_detection_data[column_x].get("surface_y")
        if surface_y is None:
            continue
        depths.append(mark_y - float(surface_y))
    return float(np.mean(depths)) if depths else float(np.nan)


def score_slice(lesion_detection_data, marks: Sequence[Tuple[float, float]],
                tolerance: int = DEFAULT_TOLERANCE) -> Dict:
    """Score every method against the marks on one slice.

    Returns a dict with:
        ``methods``  -- per method: median, abs_median, p90, n, mean_depth
        ``n_marks``  -- marks supplied for this slice
        ``gated``    -- whether the no-lesion gate fired
        ``operator_mean_depth`` -- mean marked depth below the surface

    An empty mark list is not an error: it yields n=0 everywhere.
    """
    methods = {}
    for method in METHODS:
        summary = _summarise(method_errors(lesion_detection_data, marks, method, tolerance))
        summary["mean_depth"] = mean_detected_depth(lesion_detection_data, method)
        methods[method] = summary

    return {
        "methods": methods,
        "n_marks": len(marks or ()),
        "gated": is_gated_slice(lesion_detection_data),
        "operator_mean_depth": mean_operator_depth(lesion_detection_data, marks, tolerance),
    }


def score_specimen(per_slice_results: Dict[int, Dict]) -> Dict:
    """Aggregate per-slice scores over a specimen, at both scales.

    Per method, reports:
        ``mean_abs_median``  -- mean of the per-slice |median| errors, i.e.
                                per-column accuracy as an A-scan reader sees it
        ``mean_median``      -- mean of the per-slice signed medians
        ``worst_abs_median`` -- the worst slice
        ``specimen_mean_depth`` -- mean detected depth over annotated slices
        ``specimen_error``   -- specimen_mean_depth minus the operator's, i.e.
                                what downstream analysis actually consumes
        ``n``                -- marks scored

    Both aggregates are required. On the validated data they rank methods
    differently, because a consistently signed bias does not cancel when slices
    are averaged; reporting one alone misrepresents the comparison.
    """
    scored = [result for result in (per_slice_results or {}).values()
              if result and result.get("n_marks")]

    operator_means = [result["operator_mean_depth"] for result in scored
                      if np.isfinite(result.get("operator_mean_depth", np.nan))]
    operator_specimen_mean = float(np.mean(operator_means)) if operator_means else float(np.nan)

    methods: Dict[str, Dict[str, float]] = {}
    for method in METHODS:
        abs_medians, medians, depths, total_n = [], [], [], 0
        for result in scored:
            summary = result["methods"].get(method, {})
            if summary.get("n"):
                abs_medians.append(summary["abs_median"])
                medians.append(summary["median"])
                total_n += summary["n"]
            depth = summary.get("mean_depth", np.nan)
            if np.isfinite(depth):
                depths.append(depth)

        specimen_mean_depth = float(np.mean(depths)) if depths else float(np.nan)
        methods[method] = {
            "mean_abs_median": float(np.mean(abs_medians)) if abs_medians else float(np.nan),
            "mean_median": float(np.mean(medians)) if medians else float(np.nan),
            "worst_abs_median": float(np.max(abs_medians)) if abs_medians else float(np.nan),
            "specimen_mean_depth": specimen_mean_depth,
            "specimen_error": (specimen_mean_depth - operator_specimen_mean
                               if np.isfinite(specimen_mean_depth)
                               and np.isfinite(operator_specimen_mean)
                               else float(np.nan)),
            "n": total_n,
        }

    return {
        "methods": methods,
        "n_slices": len(scored),
        "n_marks": sum(result["n_marks"] for result in scored),
        "operator_mean_depth": operator_specimen_mean,
        "gated_slices": sorted(index for index, result in (per_slice_results or {}).items()
                               if result and result.get("gated")),
    }


def format_error(value: float, signed: bool = True) -> str:
    """Format an error for display, showing '--' rather than a fabricated number.

    A method with no marks must never read as 0.0, which would look like a
    perfect score.
    """
    if value is None or not np.isfinite(value):
        return "--"
    return f"{value:+.1f}" if signed else f"{value:.1f}"
