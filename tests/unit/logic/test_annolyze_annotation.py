"""
Unit tests for app/logic/annolyze/annotation_service.py

Tests annotation geometry, color, and (de)serialization without GUI.
"""
import math

import pytest

from app.logic.annolyze.annotation_service import AnnotationService
from app.logic.annolyze.models import Annotation


@pytest.fixture
def service():
    return AnnotationService()


class TestPolylineLength:
    @pytest.mark.unit
    def test_empty_points_returns_zero(self, service):
        """GIVEN no points, WHEN polyline_length, THEN returns 0.0."""
        assert service.polyline_length([]) == 0.0

    @pytest.mark.unit
    def test_single_point_returns_zero(self, service):
        """GIVEN one point, WHEN polyline_length, THEN returns 0.0."""
        assert service.polyline_length([(0, 0)]) == 0.0

    @pytest.mark.unit
    def test_straight_line_length(self, service):
        """GIVEN two points 3-4-5 triangle, WHEN polyline_length, THEN returns 5."""
        assert service.polyline_length([(0, 0), (3, 4)]) == pytest.approx(5.0)

    @pytest.mark.unit
    def test_multi_segment_length(self, service):
        """GIVEN three colinear points, WHEN polyline_length, THEN sums segments."""
        assert service.polyline_length([(0, 0), (0, 2), (0, 5)]) == pytest.approx(5.0)


class TestAnnotationLength:
    @pytest.mark.unit
    def test_line_mode_uses_polyline(self, service):
        """GIVEN line mode, WHEN annotation_length, THEN equals polyline length."""
        pts = [(0, 0), (3, 4)]
        assert service.annotation_length(pts, "line") == pytest.approx(5.0)

    @pytest.mark.unit
    def test_too_few_points_returns_zero(self, service):
        """GIVEN < 2 points, WHEN annotation_length, THEN returns 0.0."""
        assert service.annotation_length([(1, 1)], "spline") == 0.0

    @pytest.mark.unit
    def test_spline_with_few_points_falls_back_to_line(self, service):
        """GIVEN spline mode but < 4 points, WHEN annotation_length, THEN line length."""
        pts = [(0, 0), (3, 4)]
        assert service.annotation_length(pts, "spline") == pytest.approx(5.0)

    @pytest.mark.unit
    def test_spline_with_enough_points_returns_positive(self, service):
        """GIVEN 4+ points in spline mode, WHEN annotation_length, THEN positive length."""
        pts = [(0, 0), (1, 1), (2, 0), (3, 1)]
        assert service.annotation_length(pts, "spline") > 0


class TestSplinePoints:
    @pytest.mark.unit
    def test_few_points_returns_original(self, service):
        """GIVEN < 4 points, WHEN spline_points, THEN returns original points."""
        pts = [(0, 0), (1, 1)]
        assert service.spline_points(pts) == [(0, 0), (1, 1)]

    @pytest.mark.unit
    def test_enough_points_returns_requested_count(self, service):
        """GIVEN 4+ points, WHEN spline_points(num=50), THEN returns 50 points."""
        pts = [(0, 0), (1, 1), (2, 0), (3, 1)]
        result = service.spline_points(pts, num=50)
        assert len(result) == 50

    @pytest.mark.unit
    def test_degenerate_points_fall_back_to_original(self, service):
        """GIVEN 4 identical points (spline fit fails), WHEN spline_points, THEN originals returned."""
        pts = [(5, 5), (5, 5), (5, 5), (5, 5)]
        assert service.spline_points(pts) == pts


class TestAnnotationLengthFallback:
    @pytest.mark.unit
    def test_degenerate_spline_falls_back_to_polyline(self, service):
        """GIVEN 4 identical points in spline mode, WHEN annotation_length, THEN falls back (0.0)."""
        pts = [(5, 5), (5, 5), (5, 5), (5, 5)]
        assert service.annotation_length(pts, "spline") == pytest.approx(0.0)


class TestHexToRgba:
    @pytest.mark.unit
    def test_valid_hex_converts(self, service):
        """GIVEN '#FF8000', WHEN hex_to_rgba, THEN returns (255,128,0,255)."""
        assert service.hex_to_rgba("#FF8000") == (255, 128, 0, 255)

    @pytest.mark.unit
    def test_invalid_hex_returns_default(self, service):
        """GIVEN bad color, WHEN hex_to_rgba, THEN returns default yellow."""
        assert service.hex_to_rgba("notacolor") == (255, 255, 178, 255)

    @pytest.mark.unit
    def test_custom_alpha(self, service):
        """GIVEN alpha=128, WHEN hex_to_rgba, THEN alpha channel is 128."""
        assert service.hex_to_rgba("#000000", alpha=128) == (0, 0, 0, 128)


class TestMakeAnnotationId:
    @pytest.mark.unit
    def test_builds_id(self, service):
        """GIVEN label and count, WHEN make_annotation_id, THEN 'label_count'."""
        assert service.make_annotation_id("GAP", 2) == "GAP_2"


class TestSerialization:
    @pytest.mark.unit
    def test_serialize_round_trip(self, service):
        """GIVEN slice annotations, WHEN serialize then deserialize, THEN keys preserved."""
        slice_annotations = {
            0: [{"id": "GAP_0", "feature": "GAP", "points": [(1, 2), (3, 4)],
                 "mode": "line", "color": "#FFFFFF", "locked": True}],
        }
        serialized = service.serialize_slice_annotations(slice_annotations)
        assert "slice_0" in serialized
        restored = service.deserialize_annotations(serialized)
        assert 0 in restored
        assert restored[0][0]["id"] == "GAP_0"

    @pytest.mark.unit
    def test_serialize_points_are_lists(self, service):
        """GIVEN tuple points, WHEN serialize, THEN points become JSON-safe lists."""
        serialized = service.serialize_slice_annotations(
            {1: [{"id": "A_0", "points": [(1, 2)], "mode": "line"}]}
        )
        assert serialized["slice_1"][0]["points"] == [[1, 2]]

    @pytest.mark.unit
    def test_normalize_fills_defaults(self, service):
        """GIVEN sparse dict, WHEN normalize, THEN defaults are filled."""
        result = service.normalize({"points": [(0, 0)]})
        assert result["feature"] == "unknown"
        assert result["mode"] == "line"
        assert result["locked"] is False
        assert result["timestamp"] is not None


class TestAnnotationModel:
    @pytest.mark.unit
    def test_to_serializable_includes_timestamp(self):
        """GIVEN annotation without timestamp, WHEN to_serializable, THEN timestamp set."""
        ann = Annotation(id="X_0", points=[(0, 0)])
        data = ann.to_serializable()
        assert data["timestamp"] is not None
