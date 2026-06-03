"""
Unit tests for app/logic/annolyze/measurement_service.py
"""
import pytest

from app.logic.annolyze.measurement_service import MeasurementService


@pytest.fixture
def service():
    return MeasurementService()


class TestContinuous:
    @pytest.mark.unit
    def test_adds_to_existing_value(self, service):
        """GIVEN current 1.50 and measured 2.25, WHEN apply_continuous, THEN '3.75'."""
        assert service.apply_continuous("1.50", 2.25) == "3.75"

    @pytest.mark.unit
    def test_empty_current_treated_as_zero(self, service):
        """GIVEN empty current, WHEN apply_continuous, THEN equals measured."""
        assert service.apply_continuous("", 4.0) == "4.00"

    @pytest.mark.unit
    def test_none_measured_returns_none(self, service):
        """GIVEN measured None, WHEN apply_continuous, THEN None (no-op)."""
        assert service.apply_continuous("1.0", None) is None

    @pytest.mark.unit
    def test_invalid_measured_returns_none(self, service):
        """GIVEN non-numeric measured, WHEN apply_continuous, THEN None."""
        assert service.apply_continuous("1.0", "abc") is None


class TestBoolean:
    @pytest.mark.unit
    def test_empty_becomes_yes(self, service):
        """GIVEN empty cell, WHEN toggle_boolean, THEN 'YES'."""
        assert service.toggle_boolean("") == "YES"

    @pytest.mark.unit
    def test_yes_becomes_no(self, service):
        """GIVEN 'YES', WHEN toggle_boolean, THEN 'NO'."""
        assert service.toggle_boolean("YES") == "NO"

    @pytest.mark.unit
    def test_no_becomes_yes(self, service):
        """GIVEN 'NO', WHEN toggle_boolean, THEN 'YES'."""
        assert service.toggle_boolean("NO") == "YES"


class TestPercentage:
    @pytest.mark.unit
    def test_increments_by_five(self, service):
        """GIVEN '10%', WHEN increment_percentage, THEN '15%'."""
        assert service.increment_percentage("10%") == "15%"

    @pytest.mark.unit
    def test_caps_at_hundred(self, service):
        """GIVEN '98%', WHEN increment_percentage, THEN '100%'."""
        assert service.increment_percentage("98%") == "100%"

    @pytest.mark.unit
    def test_empty_starts_at_step(self, service):
        """GIVEN empty, WHEN increment_percentage, THEN '5%'."""
        assert service.increment_percentage("") == "5%"


class TestCategoricalOrdinal:
    @pytest.mark.unit
    def test_categorical_empty_becomes_zero(self, service):
        """GIVEN empty, WHEN increment_categorical, THEN '0'."""
        assert service.increment_categorical("") == "0"

    @pytest.mark.unit
    def test_categorical_increments(self, service):
        """GIVEN '2', WHEN increment_categorical, THEN '3'."""
        assert service.increment_categorical("2") == "3"

    @pytest.mark.unit
    def test_ordinal_empty_becomes_one(self, service):
        """GIVEN empty, WHEN increment_ordinal, THEN '1'."""
        assert service.increment_ordinal("") == "1"


class TestParsing:
    @pytest.mark.unit
    def test_parse_integer_ok(self, service):
        """GIVEN '42', WHEN parse_integer, THEN 42."""
        assert service.parse_integer("42") == 42

    @pytest.mark.unit
    def test_parse_integer_rejects_decimal(self, service):
        """GIVEN '4.2', WHEN parse_integer, THEN ValueError."""
        with pytest.raises(ValueError):
            service.parse_integer("4.2")

    @pytest.mark.unit
    def test_parse_float_accepts_comma(self, service):
        """GIVEN '3,14', WHEN parse_float, THEN 3.14."""
        assert service.parse_float("3,14") == pytest.approx(3.14)

    @pytest.mark.unit
    def test_parse_text_trims(self, service):
        """GIVEN '  note ', WHEN parse_text, THEN 'note'."""
        assert service.parse_text("  note ") == "note"


class TestKeyHelpers:
    @pytest.mark.unit
    def test_reserved_keys_excluded(self, service):
        """GIVEN no used keys, WHEN available_keys, THEN f and h are excluded."""
        keys = service.available_keys([])
        assert "f" not in keys and "h" not in keys

    @pytest.mark.unit
    def test_used_keys_excluded(self, service):
        """GIVEN used key 'a', WHEN available_keys, THEN 'a' is excluded."""
        assert "a" not in service.available_keys(["a"])

    @pytest.mark.unit
    def test_feature_from_annotation_id(self, service):
        """GIVEN 'GAP_3', WHEN feature_from_annotation_id, THEN 'GAP'."""
        assert service.feature_from_annotation_id("GAP_3") == "GAP"

    @pytest.mark.unit
    def test_feature_from_none(self, service):
        """GIVEN None, WHEN feature_from_annotation_id, THEN None."""
        assert service.feature_from_annotation_id(None) is None
