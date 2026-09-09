"""
CarlQuant Ground-Truth Storage.

Loads and saves operator-annotated "true lesion end" marks for a specimen.
Marks are the reference against which the automatic lesion-depth detection is
scored in validation mode; they are operator judgement, never derived from the
detection itself.

Ground truth lives in a file that sits *beside* the specimen config but is never
part of it, so a validation session cannot corrupt study data:

    <specimen.source>/Data_<operator>_<measurement>/<specimen_id>_groundtruth.json

Marks are absolute image pixel coordinates ``(x, y)`` into one image stack, so a
file only means anything for the specimen it was recorded on. Loading a file
whose ``specimen_id`` does not match is refused rather than silently producing
plausible nonsense.

Key contents:
- ground_truth_path: Resolves the ground-truth file location for a specimen.
- has_ground_truth: True if a ground-truth file exists for the specimen.
- load_ground_truth: Reads marks keyed by integer slice index; {} if absent.
- save_ground_truth: Atomically writes marks, preserving operator metadata.

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
import os
import tempfile
from pathlib import Path

#: Filename suffix identifying a ground-truth file within a Data_ folder.
GROUND_TRUTH_SUFFIX = "_groundtruth.json"

#: Written into the file so it is self-describing when read outside the app.
GROUND_TRUTH_DESCRIPTION = "Operator-annotated true lesion end, absolute image (x, y) pixels."

Marks = dict[int, list[tuple[float, float]]]


class GroundTruthMismatchError(ValueError):
    """A ground-truth file holds marks for a different specimen.

    Marks are absolute pixel coordinates into one image stack, so applying one
    specimen's marks to another produces plausible-looking but meaningless
    errors. This is raised instead of returning the marks anyway.
    """


def _data_folder(specimen) -> Path:
    """Data_<operator>_<measurement> folder for a specimen.

    Mirrors the convention used by ``DataLoader.save_specimen_config`` --
    including its defaults -- so ground truth lands beside the config it
    describes rather than in a folder of its own.
    """
    operator = getattr(specimen, "operator", "OP")
    measurement = getattr(specimen, "measurement", 1)
    return Path(specimen.source) / f"Data_{operator}_{measurement}"


def ground_truth_path(specimen) -> Path:
    """Path of the ground-truth file for a specimen (may not exist)."""
    return _data_folder(specimen) / f"{specimen.specimen_id}{GROUND_TRUTH_SUFFIX}"


def has_ground_truth(specimen) -> bool:
    """True if a ground-truth file exists for this specimen."""
    return ground_truth_path(specimen).is_file()


def load_ground_truth(specimen) -> Marks:
    """Load operator marks for a specimen, keyed by integer slice index.

    Returns an empty dict when no ground truth has been recorded -- that is the
    normal state for most specimens and is not an error. Malformed slice entries
    are skipped so one bad key cannot cost the operator a whole session's marks.

    Raises:
        GroundTruthMismatchError: the file was recorded on another specimen.
    """
    path = ground_truth_path(specimen)
    if not path.is_file():
        return {}

    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        # An unreadable or corrupt file must not stop the specimen from opening.
        return {}

    if not isinstance(payload, dict):
        return {}

    stored_id = payload.get("specimen_id")
    if stored_id and stored_id != specimen.specimen_id:
        raise GroundTruthMismatchError(
            f"{path} holds marks for {stored_id!r}, not "
            f"{specimen.specimen_id!r}. Marks are absolute pixel coordinates "
            f"into one image stack and cannot be reused across specimens."
        )

    marks: Marks = {}
    for slice_key, points in (payload.get("lesion_end") or {}).items():
        try:
            slice_index = int(slice_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(points, list):
            continue
        parsed = [
            (float(point[0]), float(point[1]))
            for point in points
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]
        if parsed:
            marks[slice_index] = parsed
    return marks


def save_ground_truth(specimen, marks: Marks) -> Path:
    """Write operator marks for a specimen, atomically.

    The write goes to a temporary file in the destination folder and is then
    moved into place, so an interrupted save leaves the previous marks intact
    rather than truncating them.

    Slices with no marks are dropped rather than stored as empty lists, so
    clearing a slice removes it from the file.

    Returns:
        The path written to.
    """
    path = ground_truth_path(specimen)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "description": GROUND_TRUTH_DESCRIPTION,
        "specimen_id": specimen.specimen_id,
        "operator": getattr(specimen, "operator", "OP"),
        "measurement": getattr(specimen, "measurement", 1),
        "lesion_end": {
            str(slice_index): [[float(x), float(y)] for x, y in points]
            for slice_index, points in sorted(marks.items())
            if points
        },
    }

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".tmp",
        prefix=f"{specimen.specimen_id}_groundtruth_",
        dir=str(path.parent),
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return path
