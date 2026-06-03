"""
Unit tests for app/logic/annolyze/config_service.py
"""
import json

import pytest

from app.logic.annolyze.config_service import ConfigService
from app.logic.annolyze.models import AnnotationConfig, ColumnSpec, MetadataConfig


@pytest.fixture
def service():
    return ConfigService()


@pytest.fixture
def metadata():
    return MetadataConfig(operator="TM", measurement="2", system="OCT")


@pytest.fixture
def columns():
    return [
        ColumnSpec(name="GAP", keybinding="g", data_type="Continuous", color="#FF0000"),
        ColumnSpec(name="NOTE", keybinding="n", data_type="Text/String", color="#00FF00"),
    ]


class TestDefaultConfig:
    @pytest.mark.unit
    def test_default_has_required_keys(self, service):
        """GIVEN service, WHEN default_config, THEN it validates."""
        assert service.validate_config(service.default_config())


class TestBuildConfig:
    @pytest.mark.unit
    def test_build_sets_position_after(self, service, metadata, columns):
        """GIVEN ordered columns, WHEN build_config, THEN position_after chains names."""
        config = service.build_config(metadata, columns)
        dyn = config["columns"]["dynamic_columns"]
        assert dyn[0]["position_after"] == "SLICE"
        assert dyn[1]["position_after"] == "GAP"

    @pytest.mark.unit
    def test_build_sets_order(self, service, metadata, columns):
        """GIVEN columns, WHEN build_config, THEN order is the list index."""
        config = service.build_config(metadata, columns)
        dyn = config["columns"]["dynamic_columns"]
        assert [c["order"] for c in dyn] == [0, 1]

    @pytest.mark.unit
    def test_build_preserves_metadata(self, service, metadata, columns):
        """GIVEN metadata, WHEN build_config, THEN metadata is preserved."""
        config = service.build_config(metadata, columns)
        assert config["metadata"]["operator"] == "TM"
        assert config["metadata"]["measurement"] == "2"


class TestValidateConfig:
    @pytest.mark.unit
    def test_missing_key_is_invalid(self, service):
        """GIVEN config missing config_info, WHEN validate, THEN False."""
        assert service.validate_config({"metadata": {}, "columns": {}}) is False

    @pytest.mark.unit
    def test_non_dict_is_invalid(self, service):
        """GIVEN a non-dict, WHEN validate, THEN False."""
        assert service.validate_config(["not", "a", "dict"]) is False


class TestGetDataType:
    @pytest.mark.unit
    def test_returns_declared_type(self, service, metadata, columns):
        """GIVEN config with GAP=Continuous, WHEN get_data_type_for_column, THEN Continuous."""
        config = service.build_config(metadata, columns)
        assert service.get_data_type_for_column(config, "GAP") == "Continuous"

    @pytest.mark.unit
    def test_unknown_column_defaults_to_text(self, service, metadata, columns):
        """GIVEN unknown column, WHEN get_data_type_for_column, THEN 'Text/String'."""
        config = service.build_config(metadata, columns)
        assert service.get_data_type_for_column(config, "MISSING") == "Text/String"


class TestColumnMap:
    @pytest.mark.unit
    def test_only_keybound_columns_included(self, service, metadata):
        """GIVEN one column without keybinding, WHEN build_column_map, THEN it is excluded."""
        cols = [
            ColumnSpec(name="A", keybinding="a", data_type="Continuous"),
            ColumnSpec(name="B", keybinding="", data_type="Boolean"),
        ]
        config = service.build_config(metadata, cols)
        column_map = service.build_column_map(config)
        assert "a" in column_map
        assert column_map["a"]["col_name"] == "A"
        assert len(column_map) == 1


class TestParseConfig:
    @pytest.mark.unit
    def test_parse_returns_model(self, service, metadata, columns):
        """GIVEN a config dict, WHEN parse_config, THEN AnnotationConfig round-trips."""
        config = service.build_config(metadata, columns)
        model = service.parse_config(config)
        assert isinstance(model, AnnotationConfig)
        assert model.metadata.operator == "TM"
        assert [c.name for c in model.columns] == ["GAP", "NOTE"]


class TestFileIO:
    @pytest.mark.unit
    def test_save_then_load_round_trip(self, service, metadata, columns, tmp_path):
        """GIVEN a config, WHEN save then load, THEN content matches."""
        config = service.build_config(metadata, columns)
        path = tmp_path / "sub" / "test_config.json"
        saved = service.save_config_to_file(config, path)
        assert saved.exists()
        loaded = service.load_config_from_file(path)
        assert loaded["metadata"]["operator"] == "TM"

    @pytest.mark.unit
    def test_load_missing_raises(self, service, tmp_path):
        """GIVEN a missing path, WHEN load_config_from_file, THEN FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            service.load_config_from_file(tmp_path / "nope.json")

    @pytest.mark.unit
    def test_load_invalid_returns_none(self, service, tmp_path):
        """GIVEN an invalid config file, WHEN load, THEN returns None."""
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        assert service.load_config_from_file(path) is None
