"""
Unit tests for app/view/scanalign/view_sync.py

Tests zoom/pan mirroring between two viewers using plain fake viewers (no Tk).
"""

from types import SimpleNamespace

import pytest

from app.logic.scanalign.models import ScanGeometry
from app.view.scanalign.view_sync import ViewSync


def make_stack(w, h, px):
    geometry = ScanGeometry(n_slices=5, width_px=w, height_px=h, px_size_x_um=px, px_size_z_um=px)
    return SimpleNamespace(geometry=geometry)


class FakeViewer:
    def __init__(self, role, stack, canvas=(400, 300)):
        self.role = role
        self.stack = stack
        self.canvas = canvas
        self.zoom = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.fit = True
        self.applied = []
        self.listeners = []

    def add_view_listener(self, callback):
        self.listeners.append(callback)

    def view_state(self):
        return self.zoom, self.ox, self.oy, self.fit, self.canvas

    def apply_view(self, zoom_level, ox, oy):
        self.applied.append((zoom_level, ox, oy))
        self.fit = zoom_level == 1.0
        self.zoom, self.ox, self.oy = zoom_level, ox, oy

    def user_view(self, zoom, ox, oy, fit=False):
        self.zoom, self.ox, self.oy, self.fit = zoom, ox, oy, fit
        for callback in self.listeners:
            callback(self.role)


@pytest.fixture
def viewers():
    """Scan 1 at 2 um/px (100x50), Scan 2 at 1 um/px (200x100): sx = 2."""
    v1 = FakeViewer(1, make_stack(100, 50, 2.0))
    v2 = FakeViewer(2, make_stack(200, 100, 1.0))
    return v1, v2, ViewSync(v1, v2)


class TestViewSync:
    """Tests for ViewSync."""

    @pytest.mark.unit
    def test_zoom_on_viewer1_mirrors_to_viewer2(self, viewers):
        """GIVEN sx=2, WHEN viewer 1 zooms, THEN viewer 2 gets half the zoom, same centre."""
        v1, v2, _ = viewers
        v1.user_view(4.0, -100.0, -50.0)
        zoom, ox, oy = v2.applied[-1]
        assert zoom == pytest.approx(2.0)
        # centre point (75, 50) in scan 1 -> (150, 100) in scan 2, shown at canvas centre
        assert 150 * zoom + ox == pytest.approx(200.0)
        assert 100 * zoom + oy == pytest.approx(150.0)

    @pytest.mark.unit
    def test_zoom_on_viewer2_mirrors_to_viewer1(self, viewers):
        """GIVEN sx=2, WHEN viewer 2 zooms, THEN viewer 1 gets double the zoom."""
        v1, v2, _ = viewers
        v2.user_view(2.0, -100.0, -50.0)
        zoom, ox, oy = v1.applied[-1]
        assert zoom == pytest.approx(4.0)
        assert 75 * zoom + ox == pytest.approx(200.0)
        assert 50 * zoom + oy == pytest.approx(150.0)

    @pytest.mark.unit
    def test_fit_maps_to_fit(self, viewers):
        """GIVEN a zoomed pair, WHEN viewer 1 returns to fit, THEN viewer 2 is set to fit."""
        v1, v2, _ = viewers
        v1.user_view(4.0, -100.0, -50.0)
        v1.user_view(0.5, 10.0, 10.0, fit=True)
        assert v2.applied[-1] == (1.0, 0, 0)

    @pytest.mark.unit
    def test_disabled_is_noop(self, viewers):
        """GIVEN sync off, WHEN viewer 1 zooms, THEN viewer 2 is untouched."""
        v1, v2, sync = viewers
        sync.set_enabled(False)
        v1.user_view(4.0, -100.0, -50.0)
        assert v2.applied == []

    @pytest.mark.unit
    def test_enabling_syncs_viewer2_to_viewer1(self, viewers):
        """GIVEN a zoomed viewer 1 and sync off, WHEN enabling, THEN viewer 2 follows."""
        v1, v2, sync = viewers
        sync.set_enabled(False)
        v1.user_view(4.0, -100.0, -50.0)
        sync.set_enabled(True)
        assert v2.applied[-1][0] == pytest.approx(2.0)

    @pytest.mark.unit
    def test_no_recursion(self, viewers):
        """GIVEN a listener-triggering target, WHEN syncing, THEN apply_view runs only once."""
        v1, v2, _ = viewers
        original = v2.apply_view

        def apply_and_notify(zoom_level, ox, oy):
            original(zoom_level, ox, oy)
            for callback in v2.listeners:
                callback(2)

        v2.apply_view = apply_and_notify
        v1.user_view(4.0, -100.0, -50.0)
        assert len(v2.applied) == 1
        assert v1.applied == []

    @pytest.mark.unit
    def test_missing_stack_is_noop(self, viewers):
        """GIVEN viewer 2 without a stack, WHEN viewer 1 zooms, THEN nothing happens."""
        v1, v2, sync = viewers
        v2.stack = None
        v1.user_view(4.0, -100.0, -50.0)
        assert v2.applied == []
        assert sync.physical is True

    @pytest.mark.unit
    def test_mapped_zoom_of_exactly_one_avoids_fit_sentinel(self, viewers):
        """GIVEN a mapped zoom of 1.0, WHEN applying, THEN 1.0 + 1e-6 is used."""
        v1, v2, _ = viewers
        v1.user_view(2.0, -100.0, -50.0)  # 2.0 / sx(2) = 1.0
        assert v2.applied[-1][0] == pytest.approx(1.0 + 1e-6, abs=1e-9)
        assert v2.applied[-1][0] != 1.0

    @pytest.mark.unit
    def test_physical_flag(self):
        """GIVEN a scan without pixel size, WHEN asking physical, THEN False; pixels map 1:1."""
        v1 = FakeViewer(1, make_stack(100, 50, None))
        v2 = FakeViewer(2, make_stack(100, 50, 1.0))
        sync = ViewSync(v1, v2)
        assert sync.physical is False
        v1.user_view(3.0, -10.0, -10.0)
        assert v2.applied[-1][0] == pytest.approx(3.0)
