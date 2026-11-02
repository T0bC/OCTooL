"""
ScanAlign Stack Viewer Panel.

Canvas viewer for one exported OCT scan stack. Extends BaseCanvasPanel with
cache-backed slice display (low-res preview first, full resolution swapped in
asynchronously), zoom/pan that persist while scrolling, an active-viewer border
and index listeners so the link strip can drive two viewers together.

Key contents:
- StackViewerPanel: Viewer for one scan; set_stack, show_index, add_index_listener.
- display_image: Cache-backed rendering without zoom reset, auto-save or focus steal.
- setup_specialized_bindings: Focus border bound on the canvas only.

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

import contextlib
import tkinter as tk

from PIL import Image, ImageTk

from app.logic.scanalign.models import StackInfo
from app.logic.scanalign.slice_cache import SliceCache
from app.view.shared.base_canvas_panel import BaseCanvasPanel
from app.view.shared.error_handler import handle_errors

_INSTRUCTION_KEY = "scanalign_getting_started"


class StackViewerPanel(BaseCanvasPanel):
    """Viewer for one scan stack (role 1 = reference, role 2 = moving)."""

    def __init__(self, context, frame_key, role=1):
        # State used by hook methods must exist before BaseCanvasPanel.__init__.
        self.role = role
        self.stack: StackInfo | None = None
        self.cache: SliceCache | None = None
        self._listeners = []
        self._suppress_scale = False
        self._current_index = None
        self._showing_preview = False
        self._scale_job = None  # pending coalesced slider change (after_idle id)
        self._pending_scale_index = None
        super().__init__(context, frame_key)
        # Small size request; the grid weights make the canvas grow.
        self.canvas.configure(width=480, height=240)

    # ------------------------------------------------------------------ hooks

    def get_instruction_key(self):
        return _INSTRUCTION_KEY

    def get_image_list(self):
        return self.stack.files if self.stack else []

    def get_image_path(self, index):
        return None  # images come from the SliceCache

    def setup_specialized_bindings(self):
        # Active-viewer border; bound on the canvas only (never on the window).
        self.canvas.bind("<FocusIn>", self._on_focus_in, add="+")
        self.canvas.bind("<FocusOut>", self._on_focus_out, add="+")

    @handle_errors("ScanAlign viewer focus in")
    def _on_focus_in(self, _event=None):
        self.frame.configure(bootstyle="info")

    @handle_errors("ScanAlign viewer focus out")
    def _on_focus_out(self, _event=None):
        self.frame.configure(bootstyle="default")

    # ----------------------------------------------------------------- public

    @property
    def current_index(self):
        """0-based index of the displayed slice, or None if no stack is shown."""
        return self._current_index

    @property
    def slice_count(self):
        return len(self.stack.files) if self.stack else 0

    def add_index_listener(self, callback):
        """Register ``callback(role, index, user_initiated)`` for index changes."""
        self._listeners.append(callback)

    @handle_errors("ScanAlign set_stack")
    def set_stack(self, stack, cache):
        """Show a new stack: reset zoom/pan, set the slider range, display slice 0."""
        if self._scale_job is not None:
            self.root.after_cancel(self._scale_job)
            self._scale_job = None
        self.stack = stack
        self.cache = cache
        self._current_index = None
        self.rawImage = None
        self.tk_image = None
        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self._set_scale(1, len(stack.files))
        self._fix_label_width()
        self.display_image(0)

    def _fix_label_width(self):
        """Give the slice label a fixed width for this stack.

        The label shares the grid row with the slider, so a label whose width changes
        (e.g. more digits) would resize the slider while scrolling.
        """
        n = len(self.stack.files)
        longest = f"Slice {n} / {n}"
        numbers = [
            f.slice_number
            for i, f in enumerate(self.stack.files)
            if f.slice_number is not None and f.slice_number != i + 1
        ]
        if numbers:
            longest += f"  (#{max(f.slice_number or 0 for f in self.stack.files)})"
        self.scaleValueLabel.configure(width=len(longest) + 1, anchor="e")

    @handle_errors("ScanAlign show_index")
    def show_index(self, index, notify=False):
        """Show slice ``index``; ``notify`` marks the change as user-initiated."""
        self.display_image(index, user_initiated=notify)

    # --------------------------------------------------------------- rendering

    def _set_scale(self, value, count):
        """Configure the slider range / value without triggering its command."""
        self._suppress_scale = True
        try:
            self.scale.configure(from_=1, to=max(1, count))
            self.scale.set(value)
        finally:
            self._suppress_scale = False

    @handle_errors("ScanAlign display_image")
    def display_image(self, index=None, user_initiated=False, from_scale=False):
        """Display slice ``index`` from the cache (zoom/pan are kept).

        ``from_scale``: the change came from dragging the slider, so its value is not
        written back (that would snap the thumb to the integer position mid-drag).
        """
        if not self.stack or self.cache is None:
            self.instructionText()
            return
        n = len(self.stack.files)
        if index is None:
            index = int(round(float(self.scale.get()))) - 1
        if index < 0 or index >= n:
            return

        previous = self._current_index
        changed = previous != index
        direction = 0 if previous is None else (index > previous) - (index < previous)

        full = self.cache.get_full_cached(index)
        showing_preview = False
        if full is not None:
            image = full
        else:
            image = self.cache.get_preview(index)
            if image is not None:
                showing_preview = True
                self.cache.request_full(index, self._on_full_ready)
            else:
                image = self.cache.get_full(index)

        self._current_index = index
        self._showing_preview = showing_preview
        self.rawImage = image
        if not from_scale:
            self._set_scale(index + 1, n)
        self._update_label()
        self.render_zoomed_image()

        if changed and direction:
            self.cache.prefetch(index, direction)
        if changed or previous is None:
            self._notify(index, user_initiated)

    @handle_errors("ScanAlign render_zoomed_image")
    def render_zoomed_image(self):
        """Render like the base class, but only resample the visible part when zoomed.

        The base class resizes the whole image to ``raw * zoom`` (e.g. 9800x3000 px at 3x),
        which is far too slow for scrolling through a zoomed stack.
        """
        if self.rawImage is None:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            # Not laid out yet (tab hidden / before the first <Configure>): the fit size
            # would be 0 px. onResize renders once the canvas has its real size.
            return
        if self.zoom_level == 1.0:
            super().render_zoomed_image()
            return

        zoom = self.zoom_level
        zw = int(self.rawImage.width * zoom)
        zh = int(self.rawImage.height * zoom)
        ox, oy = self.image_offset_x, self.image_offset_y

        # Visible part of the zoomed image, in zoomed-image pixels.
        x0, y0 = max(0, int(-ox)), max(0, int(-oy))
        x1, y1 = min(zw, int(cw - ox)), min(zh, int(ch - oy))
        self.canvas.delete("all")
        if x1 > x0 and y1 > y0:
            box = (x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom)
            visible = self.rawImage.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR, box=box)
            self.tk_image = ImageTk.PhotoImage(visible)
            self.canvas.create_image(ox + x0, oy + y0, image=self.tk_image, anchor=tk.NW)
        self.canvas.update_idletasks()
        self.draw_specialized_overlays()

    @handle_errors("ScanAlign viewer resize")
    def onResize(self, event):
        """Re-render the current slice for the new canvas size (zoom/pan kept).

        The base version keys off ``tk_image``, which is still None when a stack was
        shown before the canvas was laid out, and would show the instructions instead.
        """
        self.width = event.width
        self.height = event.height
        if self.stack and self.rawImage is not None:
            self.render_zoomed_image()
        else:
            self.instructionText()

    def _update_label(self):
        i = self._current_index
        n = len(self.stack.files)
        number = self.stack.files[i].slice_number
        text = f"Slice {i + 1} / {n}"
        # The original volume number only adds information when it differs from the
        # position (subset exports, gaps). No "(preview)" marker: the low-res preview is
        # replaced by the full-res slice within milliseconds, so it would only flicker.
        if number is not None and number != i + 1:
            text += f"  (#{number})"
        self.scaleValue.set(text)

    def _on_full_ready(self, index, image):
        """Full-res slice loaded (worker thread): marshal to Tk."""
        with contextlib.suppress(RuntimeError, tk.TclError):
            self.root.after(0, self._apply_full, index, image)

    @handle_errors("ScanAlign apply full-res slice")
    def _apply_full(self, index, image):
        if index != self._current_index:
            return
        self.rawImage = image
        self._showing_preview = False
        self._update_label()
        self.render_zoomed_image()

    def _notify(self, index, user_initiated):
        for callback in list(self._listeners):
            callback(self.role, index, user_initiated)

    # -------------------------------------------------------------- navigation

    def _step(self, delta):
        if not self.stack or self._current_index is None:
            return
        target = self._current_index + delta
        if 0 <= target < len(self.stack.files):
            self.display_image(target, user_initiated=True)

    @handle_errors("ScanAlign arrow left")
    def on_arrow_left(self, event):
        self._step(-1)

    @handle_errors("ScanAlign arrow right")
    def on_arrow_right(self, event):
        self._step(1)

    @handle_errors("ScanAlign scale change")
    def on_scale_change(self, value):
        """Slider moved: coalesce drag events so only the latest index is rendered."""
        if self._suppress_scale or not self.stack:
            return
        self._pending_scale_index = int(round(float(value))) - 1
        if self._scale_job is None:
            self._scale_job = self.root.after_idle(self._apply_scale_change)

    @handle_errors("ScanAlign apply scale change")
    def _apply_scale_change(self):
        self._scale_job = None
        index = self._pending_scale_index
        if self.stack and index is not None and index != self._current_index:
            self.display_image(index, user_initiated=True, from_scale=True)
