"""
AnnoLyze Display Service.

Pure presentation math (no tkinter): relative luminance, contrast-aware font
colour, and header-based column-width estimation. Deduplicates identical
helpers previously copied in results_panel.py and undo_panel.py.

Key contents:
- DisplayService: Pure presentation math for colors, luminance, and column widths.
- luminance: Computes WCAG relative luminance of a hex color in [0, 1].
- choose_font_color: Returns black or white for best contrast against a background.
- calculate_column_width: Estimates pixel width from header text length.

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
    """Pure color/luminance and column-width helpers."""

    def luminance(self, hex_color: str) -> float:
        """Relative luminance (WCAG) of a ``#RRGGBB`` color, in [0, 1]."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

        def adjust(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = adjust(r), adjust(g), adjust(b)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def choose_font_color(self, bg_color: str) -> str:
        """Return black or white for best contrast against ``bg_color``."""
        return "#FFFFFF" if self.luminance(bg_color) < 0.5 else "#000000"

    def calculate_column_width(self, header: str) -> int:
        """Estimate a column width (px) from the header text length."""
        return min(max(BASE_WIDTH, len(header) * CHAR_WIDTH + PADDING), MAX_WIDTH)
