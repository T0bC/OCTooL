"""
Unit tests for app/logic/annolyze/models.py factory/serialization helpers.
"""
import pytest

from app.logic.annolyze.models import (
    AnnotationConfig,
    ColumnSpec,
    MetadataConfig,
)


class TestMetadataConfig:
    @pytest.mark.unit
    def test_from_gui_state_coerces_to_str(self):
        """GIVEN numeric gui values, WHEN from_gui_state, THEN stored as strings."""
        meta = MetadataConfig.from_gui_state(operator="TM", measurement=2, system="OCT")
        assert meta.operator == "TM"
        assert meta.measurement == "2"
        assert meta.system == "OCT"


class TestColumnSpecRoundTrip:
    @pytest.mark.unit
    def test_to_and_from_config_dict(self):
        """GIVEN a ColumnSpec, WHEN to_config_dict then from_config_dict, THEN equal."""
        spec = ColumnSpec(name="GAP", keybinding="g", data_type="Continuous", color="#FF0000")
        restored = ColumnSpec.from_config_dict(spec.to_config_dict())
        assert restored == spec


class TestAnnotationConfigRoundTrip:
    @pytest.mark.unit
    def test_to_dict_from_dict(self):
        """GIVEN an AnnotationConfig, WHEN to_dict then from_dict, THEN data preserved."""
        config = AnnotationConfig(
            metadata=MetadataConfig(operator="CR", measurement="3", system="uCT"),
            columns=[ColumnSpec(name="A", keybinding="a", data_type="Boolean")],
        )
        restored = AnnotationConfig.from_dict(config.to_dict())
        assert restored.metadata.operator == "CR"
        assert restored.columns[0].name == "A"
