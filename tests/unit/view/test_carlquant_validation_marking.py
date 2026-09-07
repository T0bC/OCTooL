#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the validation-mode marking logic in image_viewer_panel.

The panel is tkinter-bound, so these tests exercise its mark-editing methods
directly on an instance created without ``__init__`` and without any widgets.
That covers the parts that decide *what is stored* -- adding, deleting,
undoing, clearing, and the specimen-switch guard -- which is where a bug would
silently corrupt ground truth.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.logic.carlquant import ground_truth as gt
from app.view.carlquant.image_viewer_panel import image_viewer_panel


class FakeEvent:
    """Minimal stand-in for a tkinter mouse event."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


def make_panel(tmp_path, slice_index=0, specimen_id="1_1.7_E_PBS_KIM"):
    """A panel with validation state set up but no widgets built.

    ``__new__`` avoids the tkinter constructor; only the attributes the marking
    methods touch are provided.
    """
    panel = image_viewer_panel.__new__(image_viewer_panel)

    specimen = SimpleNamespace(
        specimen_id=specimen_id,
        source=tmp_path / specimen_id,
        operator="TM",
        measurement=1,
    )
    panel.context = SimpleNamespace(
        current_specimen_id=specimen_id,
        specimen_data={specimen_id: specimen},
        status_bar=None,
    )

    panel.validation_mode = True
    panel.ground_truth_marks = {}
    panel.ground_truth_dirty = False
    panel.ground_truth_specimen_id = specimen_id
    panel.validation_changed_callback = None
    panel.overlays_visible = False

    # Identity coordinate conversion keeps the tests about mark bookkeeping.
    panel.canvas_to_image_coords = lambda x, y: (x, y)
    panel.current_slice_index = lambda: slice_index
    panel.render_zoomed_image = lambda: None

    return panel, specimen


@pytest.mark.unit
def test_click_adds_a_mark(tmp_path):
    """GIVEN validation mode, WHEN clicking, THEN a mark is stored for the slice."""
    panel, _ = make_panel(tmp_path)
    panel.add_ground_truth_mark(FakeEvent(431, 118))

    assert panel.ground_truth_marks == {0: [(431.0, 118.0)]}
    assert panel.ground_truth_dirty is True


@pytest.mark.unit
def test_click_outside_the_image_adds_nothing(tmp_path):
    """GIVEN a click off the image, WHEN marking, THEN nothing is stored."""
    panel, _ = make_panel(tmp_path)
    panel.canvas_to_image_coords = lambda x, y: (None, None)
    panel.add_ground_truth_mark(FakeEvent(-5, -5))

    assert panel.ground_truth_marks == {}


@pytest.mark.unit
def test_right_click_deletes_the_nearest_mark(tmp_path):
    """GIVEN a mark nearby, WHEN right-clicking, THEN that mark is removed."""
    panel, _ = make_panel(tmp_path)
    panel.ground_truth_marks = {0: [(100.0, 100.0), (200.0, 200.0)]}

    panel.on_validation_right_click(FakeEvent(203, 202))

    assert panel.ground_truth_marks == {0: [(100.0, 100.0)]}


@pytest.mark.unit
def test_right_click_far_away_deletes_nothing(tmp_path):
    """GIVEN no mark within the radius, WHEN right-clicking, THEN nothing is removed."""
    panel, _ = make_panel(tmp_path)
    panel.ground_truth_marks = {0: [(100.0, 100.0)]}

    panel.on_validation_right_click(FakeEvent(300, 300))

    assert panel.ground_truth_marks == {0: [(100.0, 100.0)]}


@pytest.mark.unit
def test_undo_removes_the_most_recent_mark(tmp_path):
    """GIVEN several marks, WHEN undoing, THEN only the last one goes."""
    panel, _ = make_panel(tmp_path)
    panel.ground_truth_marks = {0: [(1.0, 1.0), (2.0, 2.0)]}

    panel.undo_last_ground_truth_mark()

    assert panel.ground_truth_marks == {0: [(1.0, 1.0)]}


@pytest.mark.unit
def test_clearing_the_last_mark_drops_the_slice_entry(tmp_path):
    """GIVEN one mark, WHEN removing it, THEN the slice key is gone, not empty."""
    panel, _ = make_panel(tmp_path)
    panel.ground_truth_marks = {0: [(1.0, 1.0)]}

    panel.undo_last_ground_truth_mark()

    assert panel.ground_truth_marks == {}


@pytest.mark.unit
def test_clear_removes_every_mark_on_the_slice_only(tmp_path):
    """GIVEN marks on two slices, WHEN clearing, THEN the other slice survives."""
    panel, _ = make_panel(tmp_path, slice_index=0)
    panel.ground_truth_marks = {0: [(1.0, 1.0), (2.0, 2.0)], 1: [(3.0, 3.0)]}

    panel.clear_ground_truth_marks_on_slice()

    assert panel.ground_truth_marks == {1: [(3.0, 3.0)]}


@pytest.mark.unit
def test_editing_is_inert_when_validation_mode_is_off(tmp_path):
    """GIVEN validation mode off, WHEN pressing the keys, THEN marks are untouched.

    Validation mode must not change behaviour anywhere when it is disabled.
    """
    panel, _ = make_panel(tmp_path)
    panel.validation_mode = False
    panel.ground_truth_marks = {0: [(1.0, 1.0)]}

    panel.undo_last_ground_truth_mark()
    panel.clear_ground_truth_marks_on_slice()
    panel.on_validation_right_click(FakeEvent(1, 1))

    assert panel.ground_truth_marks == {0: [(1.0, 1.0)]}


@pytest.mark.unit
def test_marks_round_trip_through_disk(tmp_path):
    """GIVEN marks, WHEN saved and reloaded, THEN they come back unchanged."""
    panel, specimen = make_panel(tmp_path)
    panel.add_ground_truth_mark(FakeEvent(431, 118))
    panel.add_ground_truth_mark(FakeEvent(462, 119))
    panel.save_ground_truth_marks()

    assert panel.ground_truth_dirty is False
    assert gt.load_ground_truth(specimen) == {0: [(431.0, 118.0), (462.0, 119.0)]}


@pytest.mark.unit
def test_save_is_skipped_when_nothing_changed(tmp_path):
    """GIVEN no edits, WHEN saving, THEN no file is written."""
    panel, specimen = make_panel(tmp_path)
    panel.save_ground_truth_marks()

    assert gt.has_ground_truth(specimen) is False


@pytest.mark.unit
def test_specimen_switch_saves_then_drops_the_old_marks(tmp_path):
    """GIVEN a specimen switch, WHEN syncing, THEN marks are flushed to the right file.

    Marks are absolute pixels into one image stack, so carrying them into
    another specimen would corrupt that specimen's ground truth.
    """
    panel, first = make_panel(tmp_path, specimen_id="specimen_a")
    panel.add_ground_truth_mark(FakeEvent(10, 20))

    second = SimpleNamespace(
        specimen_id="specimen_b",
        source=tmp_path / "specimen_b",
        operator="TM",
        measurement=1,
    )
    panel.context.specimen_data["specimen_b"] = second
    panel.context.current_specimen_id = "specimen_b"

    panel.sync_ground_truth_to_specimen()

    # The first specimen's marks were written to its own file...
    assert gt.load_ground_truth(first) == {0: [(10.0, 20.0)]}
    # ...and are not carried into the second.
    assert panel.ground_truth_marks == {}
    assert panel.ground_truth_specimen_id == "specimen_b"
    assert gt.has_ground_truth(second) is False


@pytest.mark.unit
def test_mismatched_ground_truth_file_is_refused(tmp_path):
    """GIVEN a file from another specimen, WHEN loading, THEN no marks are adopted."""
    panel, specimen = make_panel(tmp_path)
    path = gt.ground_truth_path(specimen)
    path.parent.mkdir(parents=True)
    path.write_text('{"specimen_id": "some_other_specimen", '
                    '"lesion_end": {"0": [[1.0, 2.0]]}}')

    messages = []
    panel.context.status_bar = SimpleNamespace(
        update=lambda text, level=None: messages.append((text, level)))

    panel.load_ground_truth_marks()

    assert panel.ground_truth_marks == {}
    assert messages and messages[0][1] == "error"


# ============================================================================
# B-scan display follows the A-Scan viewer's toggle, not validation mode
# ============================================================================


class FakeDialog:
    def winfo_exists(self):
        return True


class FakeToggle:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeAScanViewer:
    def __init__(self, show_ground_truth):
        self.dialog = FakeDialog()
        self.show_ground_truth = FakeToggle(show_ground_truth)


def attach_ascan_viewer(panel, viewer):
    """Give the panel a results panel exposing an active A-Scan viewer."""
    results_panel = SimpleNamespace(active_ascan_viewer=viewer)
    panel.context.get_panel = lambda name: (
        results_panel if name == "carl_results" else None)


@pytest.mark.unit
def test_ground_truth_shows_while_marking(tmp_path):
    """GIVEN validation mode on, WHEN checking, THEN ground truth is shown."""
    panel, _ = make_panel(tmp_path)
    attach_ascan_viewer(panel, None)

    assert panel.should_show_ground_truth() is True


@pytest.mark.unit
def test_ground_truth_shows_when_the_ascan_toggle_is_on(tmp_path):
    """GIVEN the A-Scan toggle on, WHEN validation mode is off, THEN it still shows.

    Reading a disagreement means looking at both views, so the B-scan follows
    the A-Scan viewer rather than requiring validation mode as well.
    """
    panel, _ = make_panel(tmp_path)
    panel.validation_mode = False
    attach_ascan_viewer(panel, FakeAScanViewer(show_ground_truth=True))

    assert panel.should_show_ground_truth() is True


@pytest.mark.unit
def test_ground_truth_hidden_when_both_are_off(tmp_path):
    """GIVEN both off, WHEN checking, THEN nothing is drawn."""
    panel, _ = make_panel(tmp_path)
    panel.validation_mode = False
    attach_ascan_viewer(panel, FakeAScanViewer(show_ground_truth=False))

    assert panel.should_show_ground_truth() is False


@pytest.mark.unit
def test_ground_truth_hidden_with_no_ascan_viewer_open(tmp_path):
    """GIVEN no A-Scan viewer, WHEN validation mode is off, THEN nothing is drawn."""
    panel, _ = make_panel(tmp_path)
    panel.validation_mode = False
    attach_ascan_viewer(panel, None)

    assert panel.should_show_ground_truth() is False


@pytest.mark.unit
def test_ground_truth_hidden_when_no_results_panel(tmp_path):
    """GIVEN no results panel, WHEN checking, THEN it fails closed rather than raising."""
    panel, _ = make_panel(tmp_path)
    panel.validation_mode = False
    panel.context.get_panel = lambda name: None

    assert panel.should_show_ground_truth() is False
