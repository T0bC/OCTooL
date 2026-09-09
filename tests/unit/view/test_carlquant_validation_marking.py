#!/usr/bin/env python3
"""Unit tests for the validation-mode marking logic in image_viewer_panel.

The panel is tkinter-bound, so these tests exercise its mark-editing methods
directly on an instance created without ``__init__`` and without any widgets.
That covers the parts that decide *what is stored* -- adding, deleting,
undoing, clearing, and the specimen-switch guard -- which is where a bug would
silently corrupt ground truth.
"""

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
    path.write_text('{"specimen_id": "some_other_specimen", "lesion_end": {"0": [[1.0, 2.0]]}}')

    messages = []
    panel.context.status_bar = SimpleNamespace(
        update=lambda text, level=None: messages.append((text, level))
    )

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
    panel.context.get_panel = lambda name: results_panel if name == "carl_results" else None


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


# ============================================================================
# A-scan column indicator survives a full redraw
# ============================================================================


class FakeCanvas:
    """Records canvas operations without a display."""

    def __init__(self, width=800, height=600):
        self._width = width
        self._height = height
        self.lines = []
        self.deleted = []
        self._next_id = 1

    def create_line(self, *coords, **kwargs):
        item = self._next_id
        self._next_id += 1
        self.lines.append((item, coords, kwargs))
        return item

    def delete(self, target):
        self.deleted.append(target)
        if target == "all":
            self.lines = []

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height


class FakeImage:
    """Matches the real OCT slice shape: taller than wide vs the canvas.

    An earlier fixture was 1000x400 -- wider than tall -- which fits the canvas
    by width and hid the height-constrained framing the real images need.
    """

    def __init__(self, width=1164, height=1024):
        self.width = width
        self.height = height


def make_indicator_panel(tmp_path):
    """Panel with just enough state to draw the A-scan indicator."""
    panel, specimen = make_panel(tmp_path)
    panel.canvas = FakeCanvas()
    panel.rawImage = FakeImage()
    panel.zoom_level = 1.0
    panel.image_offset_x = 0
    panel.image_offset_y = 0
    panel.fitted_width = panel.rawImage.width
    panel.fitted_height = panel.rawImage.height
    panel.ascan_indicator_line = None
    panel.ascan_indicator_column = None
    panel.analysis_zoom_active = False
    return panel, specimen


@pytest.mark.unit
def test_indicator_remembers_its_column(tmp_path):
    """GIVEN an indicator drawn, WHEN checking, THEN the column is retained.

    A full redraw rebuilds the canvas; without the remembered column the line
    could not be restored, which made it vanish on slider release.
    """
    panel, _ = make_indicator_panel(tmp_path)
    panel.draw_ascan_indicator(450)

    assert panel.ascan_indicator_column == 450
    assert panel.ascan_indicator_line is not None


@pytest.mark.unit
def test_clearing_keeps_the_column_so_a_redraw_restores_it(tmp_path):
    """GIVEN a cleared indicator, WHEN redrawing, THEN it comes back."""
    panel, _ = make_indicator_panel(tmp_path)
    panel.draw_ascan_indicator(450)
    panel.clear_ascan_indicator()

    assert panel.ascan_indicator_line is None
    assert panel.ascan_indicator_column == 450

    panel.draw_ascan_indicator(panel.ascan_indicator_column)
    assert panel.ascan_indicator_line is not None


@pytest.mark.unit
def test_forgetting_stops_the_indicator_coming_back(tmp_path):
    """GIVEN the viewer closed, WHEN forgetting, THEN no redraw restores it.

    on_close triggers a redraw right after clearing, which would otherwise
    reinstate the indicator for a viewer that is gone.
    """
    panel, _ = make_indicator_panel(tmp_path)
    panel.draw_ascan_indicator(450)
    panel.forget_ascan_indicator()

    assert panel.ascan_indicator_line is None
    assert panel.ascan_indicator_column is None


# ============================================================================
# Zoom to analysis region
# ============================================================================


def add_region_config(specimen, slice_index=0, lesion_start=400, lesion_end=800):
    """Give a specimen a lesion region on one slice."""
    region = SimpleNamespace(
        lesion_start=(lesion_start, 0),
        lesion_end=(lesion_end, 0),
    )
    specimen.config = SimpleNamespace(regions={slice_index: region})
    return specimen


@pytest.mark.unit
def test_lesion_bounds_pad_into_the_sound_enamel(tmp_path):
    """GIVEN a lesion region, WHEN bounding, THEN padding is added on both sides."""
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=400, lesion_end=800)

    x_start, x_end = panel.lesion_region_bounds(specimen, 0)

    assert x_start == 400 - panel.ANALYSIS_ZOOM_PADDING
    assert x_end == 800 + panel.ANALYSIS_ZOOM_PADDING


@pytest.mark.unit
def test_lesion_bounds_are_clamped_to_the_image(tmp_path):
    """GIVEN a lesion at the image edge, WHEN bounding, THEN padding is clipped."""
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(
        specimen, lesion_start=10, lesion_end=make_indicator_panel(tmp_path)[0].rawImage.width - 10
    )

    x_start, x_end = panel.lesion_region_bounds(specimen, 0)

    assert x_start == 0
    assert x_end == panel.rawImage.width


@pytest.mark.unit
def test_lesion_bounds_none_without_a_region_config(tmp_path):
    """GIVEN no region set, WHEN bounding, THEN None is returned rather than a guess."""
    panel, specimen = make_indicator_panel(tmp_path)
    specimen.config = None

    assert panel.lesion_region_bounds(specimen, 0) is None


@pytest.mark.unit
def test_analysis_zoom_frames_the_lesion(tmp_path):
    """GIVEN a lesion region, WHEN zooming, THEN it fills the canvas width."""
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=400, lesion_end=600)
    panel.render_zoomed_image = lambda: None

    assert panel.apply_analysis_zoom() is True

    # Padded region spans 360..640 = 280px, in an 800px canvas.
    assert panel.zoom_level == pytest.approx(800 / 280)
    # Its left edge maps to the canvas left edge.
    assert panel.image_offset_x == pytest.approx(-360 * panel.zoom_level)


@pytest.mark.unit
def test_analysis_zoom_declines_when_it_would_not_magnify(tmp_path):
    """GIVEN a region no smaller than the fitted view, WHEN zooming, THEN nothing changes.

    ``zoom_level`` is an absolute image scale, so the comparison point is the
    fitted scale -- which for these tall slices is height-constrained.
    """
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=0, lesion_end=panel.rawImage.width)
    # A canvas wide and short enough that fitting by height already magnifies
    # more than framing the full-width region would.
    panel.canvas = FakeCanvas(width=400, height=2000)

    assert panel.apply_analysis_zoom() is False
    assert panel.zoom_level == 1.0


@pytest.mark.unit
def test_analysis_zoom_declines_without_a_region(tmp_path):
    """GIVEN no region config, WHEN zooming, THEN nothing changes."""
    panel, specimen = make_indicator_panel(tmp_path)
    specimen.config = None

    assert panel.apply_analysis_zoom() is False
    assert panel.zoom_level == 1.0


@pytest.mark.unit
def test_sync_applies_and_releases_the_zoom(tmp_path):
    """GIVEN the toggle, WHEN switched on then off, THEN the view zooms and restores."""
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=400, lesion_end=600)
    panel.render_zoomed_image = lambda: None

    panel.sync_analysis_zoom(True)
    assert panel.analysis_zoom_active is True
    assert panel.zoom_level > 1.0

    panel.sync_analysis_zoom(False)
    assert panel.analysis_zoom_active is False
    assert panel.zoom_level == 1.0
    assert panel.image_offset_x == 0


@pytest.mark.unit
def test_sync_off_leaves_a_manual_zoom_untouched(tmp_path):
    """GIVEN a zoom the operator set, WHEN the toggle goes off, THEN it survives.

    Only a zoom this feature applied should be undone.
    """
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=400, lesion_end=600)
    panel.render_zoomed_image = lambda: None
    panel.zoom_level = 3.0  # set by the operator, not by the toggle

    panel.sync_analysis_zoom(False)

    assert panel.zoom_level == 3.0


@pytest.mark.unit
def test_overlays_survive_a_partially_initialised_panel():
    """GIVEN none of the subclass state, WHEN drawing overlays, THEN no AttributeError.

    ``draw_specialized_overlays`` is a hook the base class calls from its own
    constructor and on every resize, so it can run before -- or without -- this
    subclass's optional attributes existing.
    """
    panel = image_viewer_panel.__new__(image_viewer_panel)
    panel.context = SimpleNamespace(get_panel=lambda name: None)
    panel.overlays_visible = False
    panel.rawImage = None
    panel.canvas = FakeCanvas()

    panel.draw_specialized_overlays()  # must not raise


def add_surface(specimen, slice_index=0, surface_y=100):
    """Give a specimen a detected surface, as the zoom framing reads it."""
    curves = {"interpolated_surface": [(x, surface_y) for x in range(300, 900, 50)]}
    specimen.results = {slice_index: SimpleNamespace(surface=SimpleNamespace(fitted_curves=curves))}
    return specimen


@pytest.mark.unit
def test_analysis_zoom_keeps_the_lesion_on_screen(tmp_path):
    """GIVEN a lesion near the surface, WHEN zooming, THEN it lands in the viewport.

    The lesion sits in the top ~16% of these images. Centring the whole image
    vertically pushed it off the top of the canvas, which is what made the
    zoom look broken.
    """
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=420, lesion_end=800)
    add_surface(specimen, surface_y=100)
    panel.canvas = FakeCanvas(width=800, height=600)
    panel.render_zoomed_image = lambda: None

    assert panel.apply_analysis_zoom() is True

    zoom = panel.zoom_level
    # A lesion end ~50px below the surface, at the middle of the region.
    lesion_canvas_y = 150 * zoom + panel.image_offset_y
    lesion_canvas_x = 610 * zoom + panel.image_offset_x

    assert 0 <= lesion_canvas_y <= 600
    assert 0 <= lesion_canvas_x <= 800


@pytest.mark.unit
def test_analysis_zoom_never_scrolls_past_the_image_top(tmp_path):
    """GIVEN a shallow surface, WHEN framing, THEN no blank space above the image."""
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=420, lesion_end=800)
    add_surface(specimen, surface_y=5)
    panel.canvas = FakeCanvas(width=800, height=600)
    panel.render_zoomed_image = lambda: None

    panel.apply_analysis_zoom()

    assert panel.image_offset_y <= 0


@pytest.mark.unit
def test_analysis_zoom_without_a_detected_surface_shows_the_top(tmp_path):
    """GIVEN no analysis yet, WHEN framing, THEN the top of the image is shown.

    Closer than centring for these specimens, where the lesion is near the top.
    """
    panel, specimen = make_indicator_panel(tmp_path)
    add_region_config(specimen, lesion_start=420, lesion_end=800)
    specimen.results = {}
    panel.canvas = FakeCanvas(width=800, height=600)
    panel.render_zoomed_image = lambda: None

    assert panel.apply_analysis_zoom() is True
    assert panel.image_offset_y == 0.0
