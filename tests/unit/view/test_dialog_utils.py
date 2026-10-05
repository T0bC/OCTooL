#!/usr/bin/env python3
"""Unit tests for the dialog centering helpers.

The helpers only call ``winfo_*`` getters and ``geometry`` on the widgets they
are given, so plain fake objects stand in for Toplevel/parent windows and no
display is needed.
"""

import pytest

from app.view.shared.dialog_utils import center_on_parent, center_on_screen


class FakeWindow:
    """Minimal stand-in recording the geometry string it is given."""

    def __init__(self, x=0, y=0, width=0, height=0, screen=(1920, 1080)):
        self._x, self._y, self._w, self._h = x, y, width, height
        self._screen = screen
        self.geometry_calls = []
        self.idle_updates = 0

    def winfo_x(self):
        return self._x

    def winfo_y(self):
        return self._y

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def winfo_screenwidth(self):
        return self._screen[0]

    def winfo_screenheight(self):
        return self._screen[1]

    def update_idletasks(self):
        self.idle_updates += 1

    def geometry(self, value):
        self.geometry_calls.append(value)


@pytest.mark.unit
def test_center_on_screen_sets_size_and_position():
    """GIVEN a 1920x1080 screen, THEN a 600x400 dialog sits at the middle."""
    dialog = FakeWindow()

    center_on_screen(dialog, 600, 400)

    assert dialog.geometry_calls == ["600x400+660+340"]


@pytest.mark.unit
def test_center_on_screen_floors_odd_remainders():
    """GIVEN odd leftover space, THEN the offset is floored (integer division)."""
    dialog = FakeWindow(screen=(1001, 801))

    center_on_screen(dialog, 500, 400)

    assert dialog.geometry_calls == ["500x400+250+200"]


@pytest.mark.unit
def test_center_on_parent_centers_over_parent_and_keeps_size():
    """GIVEN a parent at (100, 50) sized 1000x800, THEN the dialog is centred on it."""
    parent = FakeWindow(x=100, y=50, width=1000, height=800)
    dialog = FakeWindow(width=500, height=280)

    center_on_parent(dialog, parent)

    assert dialog.idle_updates == 1
    # Position only: the dialog keeps the size it already has.
    assert dialog.geometry_calls == ["+350+310"]
