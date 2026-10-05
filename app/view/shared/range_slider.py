#!/usr/bin/env python3
"""
Range Slider.

Two-knob horizontal slider for selecting an integer range (e.g. the lower and
upper dB value). The value/pixel math lives in pure module-level helpers that
need no display; the widget itself is a Canvas styled after ttkbootstrap's
ttk.Scale (same track color, handle size and anti-aliased round handle).

Key contents:
- value_to_pixel / pixel_to_value: Map between slider values and canvas x positions.
- clamp_range: Clamp a (low, high) pair to the bounds and keep low <= high.
- nearest_knob: Decide which knob a click should grab.
- RangeSlider: Canvas widget with two draggable knobs.

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

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk
from PIL.Image import Resampling

# Fallback colors (ttkbootstrap "darkly") used when no live Style instance exists.
_FALLBACK_BG = "#222222"
_FALLBACK_TRACK = "#444444"
_FALLBACK_ACCENT = "#00bc8c"
_FALLBACK_LOW_BORDER = "#3498db"  # darkly "info"
_FALLBACK_HIGH_BORDER = "#f39c12"  # darkly "warning"

# Base sizes (in pixels at ttkbootstrap's baseline scaling), same as ttk.Scale.
_KNOB_DIAMETER = 14
_KNOB_BORDER = 1
_TRACK_THICKNESS = 5
_SUPERSAMPLE = 4


# %% Pure helpers (no Tk)
def value_to_pixel(value, from_, to, x_min, x_max) -> float:
    """
    Map a slider value to a canvas x position.

    Parameters
    ----------
    value : float
        Value in the range ``[from_, to]``.
    from_, to : float
        Slider bounds.
    x_min, x_max : float
        Pixel positions belonging to ``from_`` and ``to``.

    Returns
    -------
    float
        The x position for ``value``.

    """
    if to == from_:
        return float(x_min)
    return x_min + (value - from_) / (to - from_) * (x_max - x_min)


def pixel_to_value(x, from_, to, x_min, x_max) -> int:
    """
    Map a canvas x position to the nearest integer slider value.

    Parameters
    ----------
    x : float
        Canvas x position.
    from_, to : float
        Slider bounds.
    x_min, x_max : float
        Pixel positions belonging to ``from_`` and ``to``.

    Returns
    -------
    int
        Rounded value, clamped to ``[from_, to]``.

    """
    if x_max == x_min:
        return int(from_)
    value = from_ + (x - x_min) / (x_max - x_min) * (to - from_)
    return int(max(from_, min(to, round(value))))


def clamp_range(low, high, from_, to) -> tuple[int, int]:
    """
    Clamp both values to the bounds and enforce ``low <= high``.

    Equal values are allowed (there is no minimum gap). If ``low > high`` the
    two are swapped.

    Returns
    -------
    tuple[int, int]
        The corrected ``(low, high)``.

    """
    low = int(max(from_, min(to, low)))
    high = int(max(from_, min(to, high)))
    if low > high:
        low, high = high, low
    return low, high


def nearest_knob(x, low_px, high_px, x_min=None, x_max=None) -> str:
    """
    Decide which knob a click at ``x`` should grab.

    Rule: the knob whose pixel position is closer to ``x`` wins; an exact tie
    in distance goes to ``"low"``. If the knobs overlap (``low_px == high_px``)
    a click left of them grabs ``"low"`` and a click on or right of them grabs
    ``"high"``, so the two can be pulled apart again. Exception: when both
    knobs sit at the maximum end, ``"low"`` is returned (it can still move
    left), and when both sit at the minimum end, ``"high"`` is returned.

    Parameters
    ----------
    x : float
        Click x position.
    low_px, high_px : float
        Current knob positions.
    x_min, x_max : float, optional
        Pixel ends of the track; needed only to detect the "both at an end"
        exception.

    Returns
    -------
    str
        ``"low"`` or ``"high"``.

    """
    if low_px == high_px:
        if x_max is not None and low_px >= x_max:
            return "low"
        if x_min is not None and low_px <= x_min:
            return "high"
        return "low" if x < low_px else "high"
    return "low" if abs(x - low_px) <= abs(x - high_px) else "high"


# %% Widget
class RangeSlider(tk.Canvas):
    """
    Horizontal slider with two knobs selecting an integer range.

    The widget stretches with its grid cell (``sticky=E+W``). Dragged knobs
    cannot cross each other.
    """

    def __init__(
        self, master, from_=0, to=120, low=None, high=None, command=None, length=160, **kw
    ):
        """
        Create the slider.

        Parameters
        ----------
        master : tk.Misc
            Parent widget.
        from_, to : int
            Slider bounds.
        low, high : int, optional
            Initial knob values; default to the bounds.
        command : callable, optional
            Called as ``command(low, high)`` whenever the integer value pair
            changes through user interaction (dragging or a double-click reset).
        length : int
            Requested width in pixels.
        **kw
            Passed on to ``tk.Canvas``.

        """
        self._colors = self._resolve_colors(master)
        self._knob_size = self._scale(master, _KNOB_DIAMETER)
        self._track_thickness = self._scale(master, _TRACK_THICKNESS)
        self._knob_border = self._scale(master, _KNOB_BORDER)
        self._radius = self._knob_size / 2

        kw.setdefault("background", self._colors["bg"])
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("borderwidth", 0)
        kw.setdefault("width", length)
        kw.setdefault("height", self._knob_size + 2)
        super().__init__(master, **kw)

        self.from_ = from_
        self.to = to
        self.command = command
        self._low, self._high = clamp_range(
            from_ if low is None else low, to if high is None else high, from_, to
        )
        # A double-click on a knob resets it to its initial value.
        self._default_low, self._default_high = self._low, self._high
        # Canvas size tracked from the requested size, then from <Configure> events.
        self._width = int(kw["width"])
        self._height = int(kw["height"])
        self._dragging = None  # "low", "high", "either" (overlapping, undecided) or None
        self._grab_offset = 0.0
        self._press_x = 0.0

        # Same fill, different thin border, so min and max knobs can be told apart.
        # Keep references, otherwise Tk drops the images.
        self._knob_images = {
            "low": self._make_knob_image(self._colors["accent"], self._colors["low_border"]),
            "high": self._make_knob_image(self._colors["accent"], self._colors["high_border"]),
        }

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.tag_bind("knob", "<Enter>", lambda e: self.configure(cursor="hand2"))
        self.tag_bind("knob", "<Leave>", lambda e: self.configure(cursor=""))

        self._draw()

    # %% Theme helpers
    @staticmethod
    def _resolve_colors(master) -> dict:
        """Read the colors from the live ttkbootstrap Style, else use darkly values."""
        colors = {
            "bg": _FALLBACK_BG,
            "track": _FALLBACK_TRACK,
            "accent": _FALLBACK_ACCENT,
            "low_border": _FALLBACK_LOW_BORDER,
            "high_border": _FALLBACK_HIGH_BORDER,
        }
        try:
            from ttkbootstrap import Style
            from ttkbootstrap.style import Colors

            style = Style.get_instance()
            # Ignore an instance that belongs to another (stale) root.
            if style is not None and style.master is master._root():
                theme_colors = style.colors
                colors["bg"] = theme_colors.bg
                colors["accent"] = theme_colors.success
                colors["low_border"] = theme_colors.info
                colors["high_border"] = theme_colors.warning
                # Same track color ttkbootstrap uses for ttk.Scale in dark themes.
                colors["track"] = Colors.update_hsv(theme_colors.selectbg, vd=-0.2)
        except Exception:
            pass
        return colors

    @staticmethod
    def _scale(master, size) -> int:
        """Scale a pixel size like ttkbootstrap does for its ttk.Scale assets."""
        try:
            windowing = master.tk.call("tk", "windowingsystem")
            baseline = 1.000492368291482 if windowing == "aqua" else 1.33398982438864281
            return math.ceil(size * float(master.tk.call("tk", "scaling")) / baseline)
        except tk.TclError:
            return size

    def _make_knob_image(self, color, border_color):
        """Render an anti-aliased round knob (supersampled, then LANCZOS-downsampled)."""
        big = self._knob_size * _SUPERSAMPLE
        image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse(
            (0, 0, big - 1, big - 1),
            fill=color,
            outline=border_color,
            width=self._knob_border * _SUPERSAMPLE,
        )
        image = image.resize((self._knob_size, self._knob_size), Resampling.LANCZOS)
        return ImageTk.PhotoImage(image, master=self)

    # %% Geometry
    @property
    def _x_min(self) -> float:
        return self._radius

    @property
    def _x_max(self) -> float:
        return max(self._radius, self._width - self._radius)

    def _pixel(self, value) -> float:
        return value_to_pixel(value, self.from_, self.to, self._x_min, self._x_max)

    def _draw(self):
        """Redraw track, filled range and knobs."""
        self.delete("all")
        cy = self._height / 2
        half = self._track_thickness / 2
        low_x, high_x = self._pixel(self._low), self._pixel(self._high)

        self.create_rectangle(
            self._x_min,
            cy - half,
            self._x_max,
            cy + half,
            fill=self._colors["track"],
            outline="",
        )
        self.create_rectangle(
            low_x, cy - half, high_x, cy + half, fill=self._colors["accent"], outline=""
        )
        for name, x in (("low", low_x), ("high", high_x)):
            self.create_image(x, cy, image=self._knob_images[name], tags="knob")

    # %% Public API
    def get(self) -> tuple[int, int]:
        """Return the current ``(low, high)`` values."""
        return self._low, self._high

    def set(self, low, high):
        """
        Set both knobs (clamped) and redraw.

        Unlike user interaction this does NOT call ``command``; the caller is
        expected to update any dependent display itself (as the dB panel does
        when it applies its defaults).
        """
        self._low, self._high = clamp_range(low, high, self.from_, self.to)
        self._draw()

    # %% Event handlers
    def _on_configure(self, event):
        self._width = event.width
        self._height = event.height
        self._draw()

    def _on_press(self, event):
        """
        Grab a knob.

        A press on a knob grabs it without moving it (the grab offset is kept so
        the knob does not jump). If both knobs overlap under the press, the
        direction of the first drag motion decides which one moves. A press on
        the track moves the nearest knob to the press position.
        """
        low_x, high_x = self._pixel(self._low), self._pixel(self._high)
        knob = self._knob_at(event.x)
        self._press_x = event.x

        if knob == "either":
            self._dragging = "either"
            self._grab_offset = low_x - event.x
        elif knob is not None:
            self._dragging = knob
            self._grab_offset = (low_x if knob == "low" else high_x) - event.x
        else:
            self._dragging = nearest_knob(event.x, low_x, high_x, self._x_min, self._x_max)
            self._grab_offset = 0
            self._move_dragged_knob(event.x)

    def _on_double_click(self, event):
        """
        Reset the double-clicked knob to its initial value.

        If that would cross the other knob, the other one is reset too, so the
        result is always a valid range. Overlapping knobs are both reset.
        """
        knob = self._knob_at(event.x)
        self._dragging = None  # don't keep dragging with the old grab offset
        if knob is None:
            return
        low, high = self._low, self._high
        if knob in ("low", "either") or self._default_high < low:
            low = self._default_low
        if knob in ("high", "either") or self._default_low > high:
            high = self._default_high
        self._apply(low, high)

    def _on_drag(self, event):
        if self._dragging == "either":
            if event.x == self._press_x:
                return
            self._dragging = "low" if event.x < self._press_x else "high"
        if self._dragging is not None:
            self._move_dragged_knob(event.x + self._grab_offset)

    def _on_release(self, event):
        self._dragging = None

    def _move_dragged_knob(self, x):
        """Move the grabbed knob to ``x`` (not crossing the other) and notify on change."""
        value = pixel_to_value(x, self.from_, self.to, self._x_min, self._x_max)
        if self._dragging == "low":
            self._apply(min(value, self._high), self._high)
        else:
            self._apply(self._low, max(value, self._low))

    def _knob_at(self, x):
        """
        Return the knob under ``x``: ``"low"``, ``"high"``, ``"either"`` if both
        overlap there, or ``None`` if ``x`` is on the bare track.
        """
        low_x, high_x = self._pixel(self._low), self._pixel(self._high)
        on_low = abs(x - low_x) <= self._radius
        on_high = abs(x - high_x) <= self._radius
        if on_low and on_high and low_x == high_x:
            return "either"
        if on_low or on_high:
            return nearest_knob(x, low_x, high_x, self._x_min, self._x_max)
        return None

    def _apply(self, low, high):
        """Store a new (valid) pair from user interaction, redraw and notify on change."""
        if (low, high) == (self._low, self._high):
            return
        self._low, self._high = low, high
        self._draw()
        if self.command is not None:
            self.command(self._low, self._high)
