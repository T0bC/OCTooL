"""
CarlQuant Data Service.

Pure, tkinter-free file/Excel/JSON I/O for CarlQuant: discovering image stacks,
loading/saving specimen configurations, results, and annotated images. Wraps
the loaders/savers in data_io and exposes them from the logic layer's stable
import location.

Key contents:
- Re-exports DataLoader, DataSaver, convert_to_json_serializable, natural_key,
  and IMAGE_EXTENSIONS from data_io as the stable logic-layer import location.

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


from app.logic.carlquant.data_io import (
    DataLoader,
    DataSaver,
    convert_to_json_serializable,
    natural_key,
    IMAGE_EXTENSIONS,
)

__all__ = [
    "DataLoader",
    "DataSaver",
    "convert_to_json_serializable",
    "natural_key",
    "IMAGE_EXTENSIONS",
]
