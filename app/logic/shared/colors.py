"""
Shared Colour Helpers.

Pure colour conversion and contrast math (no tkinter): hex <-> RGB(A) conversion,
WCAG relative luminance and contrast-aware font colour selection. Single source
of truth replacing the per-module copies previously spread across the
annotation, carlquant, display and sheet-panel code.

Key contents:
- hex_to_rgb: Converts a ``#RRGGBB`` string to an (r, g, b) tuple.
- hex_to_rgba: Converts a ``#RRGGBB`` string to an (r, g, b, a) tuple.
- rgb_to_hex: Converts r, g, b integers to a lowercase ``#rrggbb`` string.
- luminance: Computes WCAG relative luminance of a hex color in [0, 1].
- choose_font_color: Returns black or white for best contrast against a background.

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

import re

_HEX_COLOR_RE = re.compile(r"#?([0-9a-fA-F]{6})")


def hex_to_rgb(color: str, default: tuple[int, int, int] | None = None) -> tuple[int, int, int]:
    """
    Convert a ``#RRGGBB`` hex string (case-insensitive, '#' optional) to (r, g, b).

    Anything else (named colours, short forms, wrong length, non-strings) is
    invalid: ``default`` is returned if given, otherwise ``ValueError`` is raised.
    """
    match = _HEX_COLOR_RE.fullmatch(color) if isinstance(color, str) else None
    if match is None:
        if default is not None:
            return default
        raise ValueError(f"Invalid hex color: {color!r}")
    digits = match.group(1)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def hex_to_rgba(
    color: str, alpha: int = 255, default: tuple[int, int, int] | None = None
) -> tuple[int, int, int, int]:
    """
    Convert a ``#RRGGBB`` hex string to (r, g, b, alpha).

    ``default`` is an RGB tuple used when ``color`` is invalid; without it an
    invalid colour raises ``ValueError``.
    """
    r, g, b = hex_to_rgb(color, default)
    return (r, g, b, alpha)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert r, g, b (0-255) to a lowercase ``#rrggbb`` string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) of a ``#RRGGBB`` color, in [0, 1]."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def adjust(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = adjust(r), adjust(g), adjust(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def choose_font_color(bg_color: str) -> str:
    """Return black or white for best contrast against ``bg_color``."""
    return "#FFFFFF" if luminance(bg_color) < 0.5 else "#000000"
