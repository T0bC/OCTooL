"""
Resource Path Resolution.

Pure, tkinter-free helpers for resolving asset paths in both development and
PyInstaller-bundled environments, plus the path conventions shared by all
tools (natural file ordering and the Data_<operator>_<measurement> folder).

Key contents:
- resource_path: Resolves a project-relative path to an absolute path,
  switching between sys._MEIPASS (PyInstaller) and the normal project root.
- natural_sort_key: Human-friendly sort key that handles embedded numbers in
  file names (slice_2 before slice_10).
- data_folder: Builds the Data_<operator>_<measurement> output folder path.

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

import os
import re
import sys
from pathlib import Path


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    When running as a PyInstaller bundle, files are in ``sys._MEIPASS``.
    When running as a normal script, files are relative to the project root.

    This module lives at ``app/logic/shared/paths.py`` (three packages deep),
    so deriving the project root requires walking up four directory levels:
    ``paths.py`` -> ``shared`` -> ``logic`` -> ``app`` -> project root.

    Args:
        relative_path: Path relative to the application root (e.g., 'icons/thumb_4.ico')

    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Running as normal Python script: walk up to the project root.
        base_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )

    return os.path.join(base_path, relative_path)


def natural_sort_key(path):
    """
    Sort key that orders file names the way a human would.

    Digit runs compare numerically and text compares case-insensitively, so
    ``slice_2.png`` sorts before ``slice_10.png``.

    Args:
        path: Path whose file name is used for sorting

    Returns:
        List usable as a ``key=`` argument to ``sorted``
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]


def data_folder(source, operator, measurement) -> Path:
    """
    Return the ``Data_<operator>_<measurement>`` folder under a source folder.

    Args:
        source: Specimen/sample folder (str or Path)
        operator: Operator identifier
        measurement: Measurement number

    Returns:
        Path to the output folder (not created)
    """
    return Path(source) / f"Data_{operator}_{measurement}"
