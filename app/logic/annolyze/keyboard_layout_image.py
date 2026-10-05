"""
AnnoLyze Keyboard Layout Image.

Renders the key-binding overview (keyboard grid + binding table) as a PIL image
so users can save a PNG reference of which key writes which column. Pure PIL,
no tkinter, so it is testable without a display.

Key contents:
- KEYBOARD_ROWS / KEYBOARD_ROW_OFFSETS: QWERTZ letter layout shared with the viewer.
- render_keyboard_layout: Draws coloured keys above a coloured binding table.

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

from PIL import Image, ImageDraw, ImageFont

# QWERTZ letter rows; the offset shifts a row right by whole key widths.
KEYBOARD_ROWS = (
    ("q", "w", "e", "r", "t", "z", "u", "i", "o", "p"),
    ("a", "s", "d", "f", "g", "h", "j", "k", "l"),
    ("y", "x", "c", "v", "b", "n", "m"),
)
KEYBOARD_ROW_OFFSETS = (0, 0, 1)

# Colours (match the dark sheet palette in app/view/shared/sheet_panel.py).
BACKGROUND = "#2b2b2b"
HEADER_BG = "#3c3c3c"
HEADER_FG = "#ffffff"
GRID_COLOR = "#444444"
UNBOUND_KEY_BG = "#e1e1e1"
UNBOUND_KEY_FG = "#000000"

KEY_SIZE = 48
KEY_GAP = 4
MARGIN = 12
ROW_HEIGHT = 26
CELL_PADDING = 8
MIN_COLUMN_WIDTH = 60


def _load_font(size: int, bold: bool = False):
    """First available TrueType font, falling back to PIL's built-in font."""
    names = (
        ("segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf")
        if bold
        else ("segoeui.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no size argument
        return ImageFont.load_default()


def render_keyboard_layout(
    key_colors: dict[str, tuple[str, str]],
    headers: list[str],
    rows: list[tuple[list[str], str, str]],
) -> Image.Image:
    """
    Render the keyboard grid and binding table as one image.

    Args:
        key_colors: Lower-case key -> (bg, fg) for bound keys. Unbound keys are grey.
        headers: Table header texts.
        rows: One (cell values, bg, fg) tuple per table row.

    Returns:
        Image.Image: RGB image of keyboard (top) and table (bottom).
    """
    key_font = _load_font(16, bold=True)
    cell_font = _load_font(13)
    header_font = _load_font(13, bold=True)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    # Column widths fit the longest text (header or cell) in each column.
    col_widths = []
    for i, header in enumerate(headers):
        texts = [(header, header_font)] + [(str(values[i]), cell_font) for values, _, _ in rows]
        longest = max(measure.textlength(text, font=font) for text, font in texts)
        col_widths.append(max(MIN_COLUMN_WIDTH, int(longest) + 2 * CELL_PADDING))

    key_pitch = KEY_SIZE + KEY_GAP
    keyboard_width = max(
        (offset + len(row)) * key_pitch
        for row, offset in zip(KEYBOARD_ROWS, KEYBOARD_ROW_OFFSETS, strict=True)
    )
    keyboard_height = len(KEYBOARD_ROWS) * key_pitch
    table_width = sum(col_widths)
    table_height = (len(rows) + 1) * ROW_HEIGHT

    width = 2 * MARGIN + max(keyboard_width, table_width)
    height = 3 * MARGIN + keyboard_height + table_height
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Keyboard
    for row_index, (row, offset) in enumerate(
        zip(KEYBOARD_ROWS, KEYBOARD_ROW_OFFSETS, strict=True)
    ):
        y = MARGIN + row_index * key_pitch
        for col_index, key in enumerate(row):
            x = MARGIN + (offset + col_index) * key_pitch
            bg, fg = key_colors.get(key, (UNBOUND_KEY_BG, UNBOUND_KEY_FG))
            box = (x, y, x + KEY_SIZE, y + KEY_SIZE)
            draw.rounded_rectangle(box, radius=4, fill=bg, outline=GRID_COLOR, width=2)
            draw.text(
                (x + KEY_SIZE / 2, y + KEY_SIZE / 2),
                key.upper(),
                fill=fg,
                font=key_font,
                anchor="mm",
            )

    # Table
    top = 2 * MARGIN + keyboard_height
    table_rows = [(headers, HEADER_BG, HEADER_FG, header_font)] + [
        (values, bg, fg, cell_font) for values, bg, fg in rows
    ]
    for row_index, (values, bg, fg, font) in enumerate(table_rows):
        y = top + row_index * ROW_HEIGHT
        x = MARGIN
        for value, col_width in zip(values, col_widths, strict=True):
            draw.rectangle(
                (x, y, x + col_width, y + ROW_HEIGHT), fill=bg, outline=GRID_COLOR, width=1
            )
            draw.text(
                (x + CELL_PADDING, y + ROW_HEIGHT / 2), str(value), fill=fg, font=font, anchor="lm"
            )
            x += col_width

    return image
