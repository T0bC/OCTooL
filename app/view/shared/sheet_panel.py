"""
Shared tksheet Panel Base.

Single source for the dark palette, the standard Sheet construction and the
helpers every tksheet-based panel needs (column widths, contrast-aware font
colour, header lookup).

Key contents:
- apply_dark_theme: Applies the shared dark palette to a Sheet.
- create_sheet: Builds a themed Sheet with the app's standard options and bindings.
- BaseSheetPanel: Base class for panels that show a tksheet table.
- fit_column_widths: Sizes columns from header text (and optionally content).

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

from tksheet import Sheet

from app.logic.shared.display_service import DisplayService

# Unified dark palette for every tksheet in the app (taken from carlquant).
TABLE_BG = "#2b2b2b"
TABLE_FG = "#dcdcdc"
HEADER_BG = "#3c3c3c"
HEADER_FG = "#ffffff"
GRID_COLOR = "#444444"
OUTLINE_COLOR = "#666666"
SELECTED_ROWS_BG = "#44475a"
SELECTED_ROWS_FG = "#ffffff"


def apply_dark_theme(sheet: Sheet) -> None:
    """Apply the shared dark palette to a sheet."""
    sheet.set_options(
        table_bg=TABLE_BG,
        table_fg=TABLE_FG,
        header_bg=HEADER_BG,
        header_fg=HEADER_FG,
        index_bg=HEADER_BG,
        index_fg=HEADER_FG,
        grid_color=GRID_COLOR,
        outline_color=OUTLINE_COLOR,
        selected_rows_bg=SELECTED_ROWS_BG,
        selected_rows_fg=SELECTED_ROWS_FG,
    )


def create_sheet(
    parent,
    headers,
    bindings,
    *,
    show_row_index=True,
    height=180,
    show_y_scrollbar=True,
    **sheet_kwargs,
) -> Sheet:
    """Create a themed Sheet with the app's standard options and bindings."""
    sheet = Sheet(
        parent,
        headers=list(headers),
        show_table=True,
        show_header=True,
        show_row_index=show_row_index,
        show_x_scrollbar=True,
        show_y_scrollbar=show_y_scrollbar,
        height=height,
        **sheet_kwargs,
    )
    apply_dark_theme(sheet)
    sheet.enable_bindings(*bindings)
    return sheet


class BaseSheetPanel:
    """Shared behaviour for every panel that shows a tksheet table.

    Subclasses call ``self._build_sheet(...)`` in their constructor; it sets
    ``self.sheet``. Secondary sheets (e.g. carlquant validation readout) use
    ``create_sheet`` directly and pass ``sheet=`` to the helpers below.
    """

    display_service = DisplayService()

    def _build_sheet(
        self, parent, headers, bindings, *, row=0, column=0, columnspan=1, **kwargs
    ) -> Sheet:
        """Create the themed ``self.sheet`` and grid it so it fills ``parent``."""
        self.sheet = create_sheet(parent, headers, bindings, **kwargs)
        self.sheet.grid(row=row, column=column, columnspan=columnspan, sticky="nsew")
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(column, weight=1)
        return self.sheet

    # -- column widths -------------------------------------------------
    def fit_column_widths(self, include_content: bool = False, sheet: Sheet | None = None) -> None:
        """Size columns from header text (and optionally cell content)."""
        sheet = sheet or self.sheet
        for i, header in enumerate(sheet.headers()):
            if include_content:
                values = [str(v) for v in sheet.get_column_data(i) if v not in (None, "")]
                width = self.display_service.calculate_column_width_for_content(header, values)
            else:
                width = self.display_service.calculate_column_width(header)
            sheet.column_width(i, width=width)
        sheet.refresh()

    # -- colours ------------------------------------------------------
    def get_luminance(self, hex_color: str) -> float:
        """Relative luminance of a hex color (delegates to DisplayService)."""
        return self.display_service.luminance(hex_color)

    def choose_font_color(self, bg_color: str) -> str:
        """Contrast-aware font color (delegates to DisplayService)."""
        return self.display_service.choose_font_color(bg_color)

    # -- lookup -------------------------------------------------------
    def column_index(self, col_name: str) -> int | None:
        """Index of a header name in ``self.sheet``, or None if absent."""
        headers = self.sheet.headers()
        return headers.index(col_name) if col_name in headers else None
