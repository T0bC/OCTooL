"""
Resource Path Resolution.

Pure, tkinter-free helper for resolving asset paths in both development and PyInstaller-bundled environments. Provides resource_path, the canonical helper used throughout the application.

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


import sys
import os


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
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
        )

    return os.path.join(base_path, relative_path)
