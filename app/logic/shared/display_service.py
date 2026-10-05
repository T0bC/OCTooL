"""
Shared Display Service.

Pure presentation math (no tkinter): header-based column-width estimation.
Colour helpers live in app/logic/shared/colors.py.

Key contents:
- DisplayService: Pure presentation math for column widths.
- calculate_column_width: Estimates pixel width from header text length.
- calculate_column_width_for_content: Estimates pixel width from header and cell content.

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

# Column width heuristics (kept identical to the original panel logic).
BASE_WIDTH = 40
CHAR_WIDTH = 7
PADDING = 20
MAX_WIDTH = 250


class DisplayService:
    """Pure column-width helpers."""

    def calculate_column_width(self, header: str) -> int:
        """Estimate a column width (px) from the header text length."""
        return min(max(BASE_WIDTH, len(header) * CHAR_WIDTH + PADDING), MAX_WIDTH)

    def calculate_column_width_for_content(self, header: str, cell_values: list[str]) -> int:
        """Width (px) fitting the longer of header and longest cell, capped at MAX_WIDTH."""
        longest = max((len(str(v)) for v in cell_values), default=0)
        width = max(len(header) * CHAR_WIDTH + PADDING, longest * CHAR_WIDTH + PADDING, BASE_WIDTH)
        return min(width, MAX_WIDTH)
