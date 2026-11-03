"""
ScanAlign range panel / link strip tests.

Exercise the RangePanel state logic and the LinkStrip range mode with a real Tk
root (skipped when no display is available) and lightweight fake viewers.

Key contents:
- TestRangePanel: Ranges, warnings, N clamping, pairs, stack change.
- TestLinkStripRangeMode: Mapping in both directions, label and pair marker.

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

import tkinter as tk
from pathlib import Path
from tkinter import ttk

import pytest
import ttkbootstrap  # noqa: F401 - patches ttk widgets with bootstyle support

from app.logic.scanalign.models import ScanGeometry, SliceFile, StackInfo
from app.view.scanalign.link_strip import LinkStrip
from app.view.scanalign.range_panel import RangePanel


@pytest.fixture(scope="module")
def tk_root():
    """One shared Tk root per module (creating many roots on Windows is flaky)."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    yield root
    root.destroy()


def make_stack(n):
    files = [
        SliceFile(path=Path(f"s_1_#{i + 1}_{i + 1:04d}.png"), slice_number=i + 1) for i in range(n)
    ]
    geometry = ScanGeometry(n_slices=n, width_px=10, height_px=10)
    return StackInfo(folder=Path("exp"), specimen="spec", files=files, geometry=geometry)


class FakeViewer:
    def __init__(self, parent, role, n):
        self.role = role
        self.stack = make_stack(n)
        self.canvas = tk.Canvas(parent)
        self.current_index = 0
        self.listeners = []

    @property
    def slice_count(self):
        return len(self.stack.files)

    def add_index_listener(self, callback):
        self.listeners.append(callback)

    def show_index(self, index, notify=False):
        changed = index != self.current_index
        self.current_index = index
        if changed:
            for callback in self.listeners:
                callback(self.role, index, notify)

    def user_scroll(self, index):
        self.current_index = index
        for callback in self.listeners:
            callback(self.role, index, True)


class FakeContext:
    def __init__(self, root):
        self.frames = {
            "scan_link": ttk.Frame(root),
            "scan_range": ttk.Frame(root),
        }
        self.panels = {}

    def get_frame(self, name):
        return self.frames[name]

    def get_panel(self, name, required=True):
        return self.panels.get(name)


@pytest.fixture
def setup(tk_root):
    context = FakeContext(tk_root)
    v1 = FakeViewer(tk_root, 1, 100)
    v2 = FakeViewer(tk_root, 2, 200)
    context.panels.update({"scan_viewer_1": v1, "scan_viewer_2": v2})
    link = LinkStrip(context, "scan_link")
    context.panels["scan_link"] = link
    panel = RangePanel(context, "scan_range")
    context.panels["scan_range"] = panel
    yield context, v1, v2, link, panel
    for frame in context.frames.values():
        frame.destroy()
    v1.canvas.destroy()
    v2.canvas.destroy()


def set_range(panel, v1, v2, r1, r2):
    v1.current_index = r1[0]
    panel.set_first(1)
    v1.current_index = r1[1]
    panel.set_last(1)
    v2.current_index = r2[0]
    panel.set_first(2)
    v2.current_index = r2[1]
    panel.set_last(2)


@pytest.mark.unit
class TestRangePanel:
    def test_initially_no_ranges(self, setup):
        """GIVEN a fresh panel, THEN there are no ranges or pairs."""
        _, _, _, _, panel = setup
        assert panel.ranges is None
        assert panel.pairs == []
        assert panel.n == 25

    def test_complete_ranges_give_pairs(self, setup):
        """GIVEN both ranges set, THEN N pairs are built and summarised."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (10, 59), (20, 119))
        assert panel.ranges is not None
        assert len(panel.pairs) == 25
        assert panel.pairs[0].index1 == 10
        assert panel.pairs[-1].index2 == 119
        assert "50 / 100 slices" in panel.summary_label.cget("text")
        assert "offset +10" in panel.summary_label.cget("text")

    def test_first_after_last_warns_without_raising(self, setup):
        """GIVEN first >= last, THEN a warning is shown and no pairs exist."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (50, 10), (20, 119))
        assert panel.ranges is None
        assert panel.pairs == []
        assert "first slice must come before" in panel.warning_label.cget("text")

    def test_n_clamped_to_max_pairs(self, setup):
        """GIVEN a range shorter than N, THEN N is clamped to the range length."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (0, 9), (0, 49))
        assert panel.n == 10
        assert len(panel.pairs) == 10

    def test_n_typed_above_max_pairs_is_clamped(self, setup):
        """GIVEN valid ranges, WHEN N above max_pairs is entered, THEN n and pairs use the max."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (0, 9), (0, 49))
        panel.n_var.set("999")
        assert panel.n == 10
        assert panel.n_var.get() == "10"
        assert len(panel.pairs) == 10
        assert panel.warning_label.cget("text") == ""

    def test_invalid_n_warns(self, setup):
        """GIVEN non-numeric or too small N, THEN a warning shows and pairs are empty."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (0, 49), (0, 99))
        panel.n_var.set("abc")
        assert panel.n is None
        assert panel.pairs == []
        assert "N must be" in panel.warning_label.cget("text")
        panel.n_var.set("1")
        assert panel.pairs == []

    def test_stack_change_clears_that_scan(self, setup):
        """GIVEN ranges set, WHEN scan 2 is replaced, THEN ranges and pairs are cleared."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (0, 49), (0, 99))
        panel.on_stack_changed(2)
        assert panel.ranges is None
        assert panel.pairs == []

    def test_listeners_notified(self, setup):
        """GIVEN a listener, WHEN a range changes, THEN it is called."""
        _, v1, _, _, panel = setup
        calls = []
        panel.add_change_listener(lambda: calls.append(1))
        v1.current_index = 5
        panel.set_first(1)
        assert calls

    def test_pair_selection_moves_both_viewers(self, setup):
        """GIVEN pairs, WHEN a row is selected, THEN both viewers show that pair."""
        _, v1, v2, _, panel = setup
        set_range(panel, v1, v2, (10, 59), (20, 119))
        panel.tree.selection_set("3")
        panel.tree.update()
        pair = panel.pairs[3]
        assert (v1.current_index, v2.current_index) == (pair.index1, pair.index2)

    def test_shortcuts_bound_on_canvas(self, setup):
        """GIVEN the panel, THEN F/L (both cases) are bound on each viewer canvas."""
        _, v1, v2, _, _ = setup
        for viewer in (v1, v2):
            for key in ("f", "F", "l", "L"):
                assert viewer.canvas.bind(f"<KeyPress-{key}>")


@pytest.mark.unit
class TestLinkStripRangeMode:
    def test_linked_scroll_maps_via_ranges_both_directions(self, setup):
        """GIVEN ranges of different length and Link on, THEN scrolling maps both ways."""
        _, v1, v2, link, panel = setup
        set_range(panel, v1, v2, (0, 49), (0, 99))
        v1.current_index = 0
        v2.current_index = 0
        link.link_var.set(True)
        link._on_toggle()
        v1.user_scroll(10)
        assert v2.current_index == 20
        v2.user_scroll(60)
        assert v1.current_index == 30

    def test_label_shows_scale(self, setup):
        """GIVEN linked range mode, THEN the label shows the scale (or Δ for scale 1)."""
        _, v1, v2, link, panel = setup
        set_range(panel, v1, v2, (0, 49), (0, 99))
        link.link_var.set(True)
        link._on_toggle()
        assert "Linked by ranges" in link.delta_label.cget("text")
        set_range(panel, v1, v2, (0, 49), (5, 54))
        assert link.delta_label.cget("text") == "Δ = +5 (ranges)"

    def test_ranges_set_while_linked_jump_viewer2(self, setup):
        """GIVEN Link on, WHEN ranges are set, THEN viewer 2 jumps to the mapped position."""
        _, v1, v2, link, panel = setup
        v1.current_index = 0
        v2.current_index = 0
        link.link_var.set(True)
        link._on_toggle()
        set_range(panel, v1, v2, (0, 49), (100, 149))
        v1.current_index = 25
        link.set_ranges(*panel.ranges)
        assert v2.current_index == 125

    def test_pair_marker(self, setup):
        """GIVEN both viewers on a pair, THEN the label contains the pair number."""
        _, v1, v2, link, panel = setup
        set_range(panel, v1, v2, (10, 59), (20, 119))
        pair = panel.pairs[4]
        v1.show_index(pair.index1)
        v2.show_index(pair.index2)
        assert f"pair k={pair.k}" in link.pair_label.cget("text")

    def test_without_ranges_phase1_behaviour(self, setup):
        """GIVEN no ranges, THEN linked scrolling uses the frozen offset."""
        _, v1, v2, link, _ = setup
        v1.current_index = 5
        v2.current_index = 8
        link.link_var.set(True)
        link._on_toggle()
        v1.user_scroll(10)
        assert v2.current_index == 13
        assert link.delta_label.cget("text") == "Δ = +3 slices"
