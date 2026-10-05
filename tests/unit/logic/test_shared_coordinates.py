"""
Unit tests for app.logic.shared.coordinates.CoordinateConverter.
"""

from types import SimpleNamespace

import pytest

from app.logic.shared.coordinates import CoordinateConverter


def _image(width=200, height=100):
    return SimpleNamespace(width=width, height=height)


class TestZoomFactor:
    @pytest.mark.unit
    def test_zoom_one_uses_fitted_over_raw_width(self):
        """GIVEN zoom 1.0 and fitted width 100 for a 200 px image, THEN factor is 0.5."""
        conv = CoordinateConverter(_image(200, 100), 1.0, 0, 0, 100, 50)
        assert conv.current_zoom == 0.5
        assert conv.image_to_canvas(40, 20) == (20.0, 10.0)

    @pytest.mark.unit
    def test_zoom_one_without_fitted_size_is_identity(self):
        """GIVEN zoom 1.0 and no (or falsy) fitted size, THEN the factor is 1.0."""
        for fitted in (None, 0):
            conv = CoordinateConverter(_image(200, 100), 1.0, 0, 0, fitted, fitted)
            assert conv.current_zoom == 1.0

    @pytest.mark.unit
    def test_zoom_other_than_one_uses_zoom_level(self):
        """GIVEN zoom 3.0, WHEN converting, THEN zoom_level is used and fitted size ignored."""
        conv = CoordinateConverter(_image(200, 100), 3.0, 0, 0, 100, 50)
        assert conv.current_zoom == 3.0
        assert conv.image_to_canvas(10, 5) == (30.0, 15.0)


class TestOffsets:
    @pytest.mark.unit
    def test_offsets_applied_image_to_canvas(self):
        """GIVEN pan offsets, WHEN image_to_canvas, THEN offsets are added."""
        conv = CoordinateConverter(_image(), 2.0, 15, -5)
        assert conv.image_to_canvas(10, 10) == (35.0, 15.0)

    @pytest.mark.unit
    def test_offsets_removed_canvas_to_image(self):
        """GIVEN pan offsets, WHEN canvas_to_image, THEN offsets are subtracted before scaling."""
        conv = CoordinateConverter(_image(), 2.0, 15, -5)
        assert conv.canvas_to_image(35, 15) == (10, 10)

    @pytest.mark.unit
    def test_rect_applies_zoom_and_offsets(self):
        """GIVEN zoom and offsets, WHEN image_to_canvas_rect, THEN both corners are mapped."""
        conv = CoordinateConverter(_image(), 2.0, 10, 20)
        assert conv.image_to_canvas_rect(1, 2, 3, 4) == (12.0, 24.0, 16.0, 28.0)


class TestRoundTrip:
    @pytest.mark.unit
    @pytest.mark.parametrize("zoom", [0.5, 1.0, 2.5])
    def test_image_canvas_image_round_trip(self, zoom):
        """GIVEN any zoom and offsets, WHEN image->canvas->image, THEN the point is recovered."""
        conv = CoordinateConverter(_image(200, 100), zoom, 12, 7, 160, 80)
        cx, cy = conv.image_to_canvas(50, 30)
        assert conv.canvas_to_image_unclamped(cx, cy) == pytest.approx((50, 30))
        assert conv.canvas_to_image(cx, cy) == (50, 30)


class TestCanvasToImage:
    @pytest.mark.unit
    def test_in_bounds_returns_ints(self):
        """GIVEN a canvas point inside the image, THEN integer image coordinates are returned."""
        conv = CoordinateConverter(_image(200, 100), 2.0, 0, 0)
        x, y = conv.canvas_to_image(41, 21)
        assert (x, y) == (20, 10)
        assert isinstance(x, int) and isinstance(y, int)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "canvas_x,canvas_y",
        [(-1, 10), (10, -1), (400, 10), (10, 200)],
    )
    def test_out_of_bounds_returns_none(self, canvas_x, canvas_y):
        """GIVEN a canvas point outside the image, THEN (None, None) is returned."""
        conv = CoordinateConverter(_image(200, 100), 2.0, 0, 0)
        assert conv.canvas_to_image(canvas_x, canvas_y) == (None, None)


class TestCanvasToImageUnclamped:
    @pytest.mark.unit
    def test_returns_floats_without_truncation(self):
        """GIVEN a point inside the image, THEN float coordinates are returned untruncated."""
        conv = CoordinateConverter(_image(200, 100), 2.0, 0, 0)
        x, y = conv.canvas_to_image_unclamped(41, 21)
        assert (x, y) == (20.5, 10.5)
        assert isinstance(x, float) and isinstance(y, float)

    @pytest.mark.unit
    def test_outside_bounds_gives_negative_and_oversized_values(self):
        """GIVEN a point outside the image, THEN no clamping or None is applied."""
        conv = CoordinateConverter(_image(200, 100), 2.0, 10, 10)
        assert conv.canvas_to_image_unclamped(0, 0) == (-5.0, -5.0)
        assert conv.canvas_to_image_unclamped(1010, 410) == (500.0, 200.0)
