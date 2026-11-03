"""
Unit tests for app/logic/scanalign/overlay.py

Tests grayscale conversion, resampling into Scan 2's grid, the four overlay modes
and compose() on small synthetic images.
"""

import numpy as np
import pytest
from PIL import Image

from app.logic.scanalign.models import ScanGeometry
from app.logic.scanalign.overlay import (
    blend,
    checkerboard,
    compose,
    compose_arrays,
    difference,
    fusion,
    resample_to,
    to_gray,
)
from app.logic.scanalign.view_geometry import GridMap, grid_map, inverse_point


def geom(w, h, px) -> ScanGeometry:
    return ScanGeometry(n_slices=1, width_px=w, height_px=h, px_size_x_um=px, px_size_z_um=px)


def gray_image(arr) -> Image.Image:
    return Image.fromarray(np.asarray(arr, dtype=np.uint8), "L")


IDENTITY = grid_map(geom(8, 8, 1.0), geom(8, 8, 1.0))


class TestToGray:
    """Tests for to_gray."""

    @pytest.mark.unit
    def test_l_unchanged(self):
        """GIVEN an L image, WHEN converting, THEN values are unchanged."""
        arr = np.arange(12, dtype=np.uint8).reshape(3, 4)
        assert np.array_equal(to_gray(gray_image(arr)), arr)

    @pytest.mark.unit
    def test_rgb_converted(self):
        """GIVEN a white RGB image, WHEN converting, THEN a uint8 array of 255 results."""
        out = to_gray(Image.new("RGB", (4, 3), (255, 255, 255)))
        assert out.dtype == np.uint8
        assert out.shape == (3, 4)
        assert (out == 255).all()

    @pytest.mark.unit
    def test_16bit_high_byte(self):
        """GIVEN an I;16 image, WHEN converting, THEN the high byte is kept."""
        arr = np.array([[0, 256, 65535]], dtype=np.uint16)
        out = to_gray(Image.fromarray(arr))
        assert out.dtype == np.uint8
        assert out.tolist() == [[0, 1, 255]]


class TestResample:
    """Tests for resample_to."""

    @pytest.mark.unit
    def test_identity(self):
        """GIVEN equal geometry, WHEN resampling, THEN the array is unchanged and fully valid."""
        arr = np.random.default_rng(0).integers(0, 256, (8, 8), dtype=np.uint8)
        out, mask = resample_to(gray_image(arr), IDENTITY, (8, 8))
        assert np.array_equal(out, arr)
        assert mask.all()

    @pytest.mark.unit
    def test_scale_two_places_pixel_at_mapped_position(self):
        """GIVEN Scan 1 pixels twice as large, WHEN resampling, THEN a marker is mapped."""
        m = grid_map(geom(8, 8, 2.0), geom(16, 16, 1.0))
        arr = np.zeros((8, 8), dtype=np.uint8)
        arr[3, 5] = 255
        out, mask = resample_to(gray_image(arr), m, (16, 16))
        assert out.shape == (16, 16)
        assert mask.all()
        zz, xx = np.unravel_index(np.argmax(out), out.shape)
        # scan-1 pixel centre (5.5, 3.5) maps to scan-2 (11, 7); pixels 10/11 and 6/7 straddle it
        assert xx in (10, 11)
        assert zz in (6, 7)

    @pytest.mark.unit
    def test_affine_coefficients_invert_the_map(self):
        """GIVEN a map, WHEN a Scan 2 pixel is read, THEN it holds the Scan 1 value."""
        m = grid_map(geom(10, 10, 3.0), geom(12, 12, 2.0))
        # Scan 1 holds its own x coordinate (columns 0..9 -> 0, 20, ... 180)
        arr = np.tile(np.arange(10, dtype=np.uint8) * 20, (10, 1))
        out, mask = resample_to(gray_image(arr), m, (12, 12))
        for x2 in (4, 6, 8):
            x1, _ = inverse_point(m, x2 + 0.5, 6.5)
            expected = np.interp(x1 - 0.5, np.arange(10), np.arange(10) * 20)
            assert mask[6, x2]
            assert out[6, x2] == pytest.approx(expected, abs=1.5)

    @pytest.mark.unit
    def test_mask_marks_covered_area(self):
        """GIVEN Scan 1 smaller on Scan 2's grid, WHEN resampling, THEN only the centre is valid."""
        m = grid_map(geom(8, 8, 1.0), geom(8, 8, 2.0))  # sx = 0.5 -> 4x4 centred block
        out, mask = resample_to(gray_image(np.full((8, 8), 200)), m, (8, 8))
        assert mask[2:6, 2:6].all()
        assert mask.sum() == 16
        assert (out[~mask] == 0).all()


class TestModes:
    """Tests for blend, checkerboard, difference and fusion."""

    a1 = np.full((4, 4), 100, dtype=np.uint8)
    a2 = np.full((4, 4), 200, dtype=np.uint8)

    @pytest.mark.unit
    def test_blend_extremes_and_mix(self):
        """GIVEN alpha 0, 1 and 0.5, WHEN blending, THEN Scan 1, Scan 2 and the mean result."""
        assert (blend(self.a1, self.a2, 0.0) == 100).all()
        assert (blend(self.a1, self.a2, 1.0) == 200).all()
        assert (blend(self.a1, self.a2, 0.5) == 150).all()

    @pytest.mark.unit
    def test_checkerboard_pattern(self):
        """GIVEN tile 2, WHEN making a checkerboard, THEN tiles alternate starting with Scan 1."""
        out = checkerboard(self.a1, self.a2, 2)
        assert (out[:2, :2] == 100).all()
        assert (out[:2, 2:] == 200).all()
        assert (out[2:, :2] == 200).all()
        assert (out[2:, 2:] == 100).all()

    @pytest.mark.unit
    def test_difference_is_absolute(self):
        """GIVEN either order, WHEN differencing, THEN the absolute difference results."""
        assert (difference(self.a1, self.a2) == 100).all()
        assert (difference(self.a2, self.a1) == 100).all()

    @pytest.mark.unit
    def test_fusion_channels(self):
        """GIVEN two images, WHEN fusing, THEN R=Scan 2, G=Scan 1, B=Scan 2."""
        out = fusion(self.a1, self.a2)
        assert out.shape == (4, 4, 3)
        assert (out[..., 0] == 200).all()
        assert (out[..., 1] == 100).all()
        assert (out[..., 2] == 200).all()


class TestCompose:
    """Tests for compose."""

    @pytest.mark.unit
    @pytest.mark.parametrize("mode", ["blend", "checker", "difference"])
    def test_gray_modes_return_l_of_scan2_size(self, mode):
        """GIVEN different image sizes, WHEN composing, THEN the result is L at Scan 2's size."""
        m = grid_map(geom(8, 8, 1.0), geom(12, 10, 1.0))
        out = compose(gray_image(np.zeros((8, 8))), gray_image(np.zeros((10, 12))), m, mode)
        assert out.mode == "L"
        assert out.size == (12, 10)

    @pytest.mark.unit
    def test_fusion_returns_rgb(self):
        """GIVEN fusion mode, WHEN composing, THEN the result is RGB at Scan 2's size."""
        out = compose(
            gray_image(np.zeros((8, 8))), gray_image(np.zeros((8, 8))), IDENTITY, "fusion"
        )
        assert out.mode == "RGB"
        assert out.size == (8, 8)

    @pytest.mark.unit
    def test_outside_mask_behaviour(self):
        """GIVEN Scan 1 covering only the centre, WHEN composing, THEN outside is Scan 2 / 0."""
        m = GridMap(0.5, 0.5, (4.0, 4.0), (4.0, 4.0), True)
        img1 = gray_image(np.full((8, 8), 100))
        img2 = gray_image(np.full((8, 8), 200))
        assert compose(img1, img2, m, "blend").getpixel((0, 0)) == 200
        assert compose(img1, img2, m, "blend").getpixel((4, 4)) == 150
        assert compose(img1, img2, m, "checker").getpixel((0, 0)) == 200
        assert compose(img1, img2, m, "difference").getpixel((0, 0)) == 0
        assert compose(img1, img2, m, "difference").getpixel((4, 4)) == 100
        assert compose(img1, img2, m, "fusion").getpixel((0, 0)) == (200, 0, 200)

    @pytest.mark.unit
    def test_compose_arrays_matches_compose(self):
        """GIVEN a cached resample, WHEN using compose_arrays, THEN it equals compose()."""
        m = grid_map(geom(8, 8, 1.0), geom(8, 8, 2.0))
        img1 = gray_image(np.arange(64).reshape(8, 8))
        img2 = gray_image(np.full((8, 8), 90))
        a1, mask = resample_to(img1, m, img2.size)
        for mode in ("blend", "checker", "difference", "fusion"):
            expected = compose(img1, img2, m, mode)
            assert compose_arrays(a1, mask, img2, mode).tobytes() == expected.tobytes()

    @pytest.mark.unit
    def test_unknown_mode_raises(self):
        """GIVEN an unknown mode, WHEN composing, THEN ValueError is raised."""
        img = gray_image(np.zeros((8, 8)))
        with pytest.raises(ValueError):
            compose(img, img, IDENTITY, "nope")  # type: ignore[arg-type]
