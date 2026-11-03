"""
Unit tests for app/logic/scanalign/view_geometry.py

Tests the physical/fallback grid map, point mapping and the zoom/pan transfer
between two viewer canvases.
"""

import pytest

from app.logic.scanalign.models import ScanGeometry
from app.logic.scanalign.view_geometry import (
    grid_map,
    inverse_point,
    map_point,
    map_view,
)


def geom(w=100, h=50, px_x=None, px_z=None) -> ScanGeometry:
    return ScanGeometry(n_slices=10, width_px=w, height_px=h, px_size_x_um=px_x, px_size_z_um=px_z)


class TestGridMap:
    """Tests for grid_map."""

    @pytest.mark.unit
    def test_physical_when_all_spacings_known(self):
        """GIVEN both scans with spacings, WHEN mapping, THEN sx/sz are um1/um2 and physical."""
        m = grid_map(geom(100, 50, 4.0, 3.0), geom(200, 80, 2.0, 1.5))
        assert m.physical is True
        assert m.sx == pytest.approx(2.0)
        assert m.sz == pytest.approx(2.0)
        assert m.c1 == (50.0, 25.0)
        assert m.c2 == (100.0, 40.0)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "g1,g2",
        [
            (geom(), geom(px_x=2.0, px_z=2.0)),
            (geom(px_x=2.0, px_z=2.0), geom(px_x=2.0)),
            (geom(px_x=2.0, px_z=0.0), geom(px_x=2.0, px_z=2.0)),
        ],
    )
    def test_fallback_when_spacing_missing(self, g1, g2):
        """GIVEN a missing or zero spacing, WHEN mapping, THEN pixels map 1:1, not physical."""
        m = grid_map(g1, g2)
        assert m.physical is False
        assert (m.sx, m.sz) == (1.0, 1.0)


class TestPointMapping:
    """Tests for map_point and inverse_point."""

    @pytest.mark.unit
    def test_centres_map_onto_each_other(self):
        """GIVEN a grid map, WHEN mapping the Scan 1 centre, THEN it lands on the Scan 2 centre."""
        m = grid_map(geom(100, 50, 4.0, 4.0), geom(200, 80, 2.0, 2.0))
        assert map_point(m, *m.c1) == pytest.approx(m.c2)

    @pytest.mark.unit
    def test_round_trip(self):
        """GIVEN a point, WHEN mapped forward and back, THEN the original is recovered."""
        m = grid_map(geom(100, 50, 4.0, 3.0), geom(200, 80, 2.0, 1.0))
        x2, z2 = map_point(m, 12.5, 7.25)
        assert inverse_point(m, x2, z2) == pytest.approx((12.5, 7.25))

    @pytest.mark.unit
    def test_scale_applied_about_centre(self):
        """GIVEN sx=2, WHEN mapping a point 10 px right of the centre, THEN it is 20 px right."""
        # centre x is 50, so 60 -> 50 + 10 * 2 = 70
        m = grid_map(geom(100, 50, 2.0, 2.0), geom(100, 50, 1.0, 1.0))
        assert map_point(m, 60.0, 25.0) == pytest.approx((70.0, 25.0))


class TestMapView:
    """Tests for map_view."""

    @pytest.mark.unit
    def test_identity_for_equal_geometry(self):
        """GIVEN equal geometry and canvases, WHEN mapping, THEN zoom and offset are unchanged."""
        m = grid_map(geom(100, 50, 2.0, 2.0), geom(100, 50, 2.0, 2.0))
        result = map_view(2.0, -30.0, -10.0, (400, 300), (400, 300), m, True)
        assert result == pytest.approx((2.0, -30.0, -10.0))

    @pytest.mark.unit
    def test_spacing_ratio_halves_zoom_forward(self):
        """GIVEN sx=2, WHEN mapping 1->2, THEN zoom halves and the centre point is centred."""
        m = grid_map(geom(100, 50, 2.0, 2.0), geom(200, 100, 1.0, 1.0))
        zoom, ox, oy = map_view(4.0, -100.0, -50.0, (400, 300), (400, 300), m, True)
        assert zoom == pytest.approx(2.0)
        # source centre image point: ((200+100)/4, (150+50)/4) = (75, 50) -> (150, 100)
        assert 150.0 * zoom + ox == pytest.approx(200.0)
        assert 100.0 * zoom + oy == pytest.approx(150.0)

    @pytest.mark.unit
    def test_backward_doubles_zoom_and_inverts_forward(self):
        """GIVEN a forward result, WHEN mapped backward, THEN the source view is recovered."""
        m = grid_map(geom(100, 50, 2.0, 2.0), geom(200, 100, 1.0, 1.0))
        fwd = map_view(4.0, -100.0, -50.0, (400, 300), (500, 250), m, True)
        back = map_view(*fwd, (500, 250), (400, 300), m, False)
        assert back == pytest.approx((4.0, -100.0, -50.0))
