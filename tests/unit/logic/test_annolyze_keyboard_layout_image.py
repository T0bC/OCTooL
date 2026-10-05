"""
Unit tests for app/logic/annolyze/keyboard_layout_image.py
"""

import pytest

from app.logic.annolyze.keyboard_layout_image import (
    KEY_GAP,
    KEY_SIZE,
    KEYBOARD_ROWS,
    MARGIN,
    ROW_HEIGHT,
    UNBOUND_KEY_BG,
    render_keyboard_layout,
)

HEADERS = ["Key", "Column Name", "Data Type", "Status"]


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _key_sample_point(key):
    """A pixel inside the key box, away from the centred letter."""
    for row_index, row in enumerate(KEYBOARD_ROWS):
        if key in row:
            offset = (0, 0, 1)[row_index]
            x = MARGIN + (offset + row.index(key)) * (KEY_SIZE + KEY_GAP) + 6
            y = MARGIN + row_index * (KEY_SIZE + KEY_GAP) + 6
            return x, y
    raise KeyError(key)


@pytest.mark.unit
def test_bound_and_unbound_key_colours():
    image = render_keyboard_layout({"q": ("#ff0000", "#ffffff")}, HEADERS, [])
    assert image.getpixel(_key_sample_point("q")) == (255, 0, 0)
    assert image.getpixel(_key_sample_point("w")) == _hex_to_rgb(UNBOUND_KEY_BG)


@pytest.mark.unit
def test_image_height_grows_with_rows():
    row = (["Q", "Length", "Float", "User-defined"], "#00ff00", "#000000")
    small = render_keyboard_layout({}, HEADERS, [row])
    large = render_keyboard_layout({}, HEADERS, [row] * 26)
    assert large.height - small.height == 25 * ROW_HEIGHT


@pytest.mark.unit
def test_table_row_uses_row_background():
    row = (["Q", "Length", "Float", "User-defined"], "#00ff00", "#000000")
    image = render_keyboard_layout({}, HEADERS, [row])
    # First data row sits one header row below the table top; sample its left padding.
    keyboard_height = len(KEYBOARD_ROWS) * (KEY_SIZE + KEY_GAP)
    y = 2 * MARGIN + keyboard_height + ROW_HEIGHT + ROW_HEIGHT // 2
    assert image.getpixel((MARGIN + 3, y)) == (0, 255, 0)


@pytest.mark.unit
def test_long_column_name_widens_image():
    short = render_keyboard_layout({}, HEADERS, [(["Q", "A", "Float", "x"], "#000000", "#ffffff")])
    long_name = "A" * 120
    wide = render_keyboard_layout(
        {}, HEADERS, [(["Q", long_name, "Float", "x"], "#000000", "#ffffff")]
    )
    assert wide.width > short.width
