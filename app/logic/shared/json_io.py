"""
Shared JSON I/O.

Single place for reading and writing JSON files so every caller gets UTF-8
encoding and (for writes) crash-safe, atomic replacement of the target file.

Key contents:
- read_json: Reads a JSON file as UTF-8 and returns the decoded data.
- write_json_atomic: Writes JSON via a temp file in the same folder, then os.replace.

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
from typing import Any


def read_json(path: str | Path) -> Any:
    """Read and decode a UTF-8 JSON file."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(
    path: str | Path,
    data: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = True,
) -> Path:
    """Write ``data`` as UTF-8 JSON to ``path`` atomically.

    The data is written to a temporary file in the destination folder and then
    moved into place, so an interrupted or failed save leaves any previous file
    intact rather than truncating it. Missing parent folders are created.

    Returns:
        The path written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".tmp",
        prefix=f"{path.stem}_",
        dir=path.parent,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        try:
            json.dump(data, handle, indent=indent, ensure_ascii=ensure_ascii)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return path
