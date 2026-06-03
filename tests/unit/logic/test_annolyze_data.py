"""
Unit tests for app/logic/annolyze/data_service.py (context-free I/O).
"""
import json
from pathlib import Path

import pytest

from app.logic.annolyze.data_service import DataService


@pytest.fixture
def service():
    return DataService()


class TestFindFile:
    @pytest.mark.unit
    def test_finds_matching_file(self, service, tmp_path):
        """GIVEN a config file, WHEN find_file('*config.json'), THEN it is found."""
        (tmp_path / "sample_config.json").write_text("{}", encoding="utf-8")
        result = service.find_file(tmp_path, "*config.json")
        assert result is not None and result.name == "sample_config.json"

    @pytest.mark.unit
    def test_returns_none_when_no_match(self, service, tmp_path):
        """GIVEN no match, WHEN find_file, THEN returns None."""
        assert service.find_file(tmp_path, "*config.json") is None

    @pytest.mark.unit
    def test_prioritizes_sample_name(self, service, tmp_path):
        """GIVEN two matches, WHEN find_file with sample_name, THEN prioritizes that file."""
        (tmp_path / "other_config.json").write_text("{}", encoding="utf-8")
        (tmp_path / "MySample_config.json").write_text("{}", encoding="utf-8")
        result = service.find_file(tmp_path, "*config.json", sample_name="MySample")
        assert result.name == "MySample_config.json"

    @pytest.mark.unit
    def test_finds_file_recursively(self, service, tmp_path):
        """GIVEN nested file, WHEN find_file, THEN rglob locates it."""
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "x_results.csv").write_text("h\n", encoding="utf-8")
        assert service.find_file(tmp_path, "*results.csv") is not None


class TestBuildDataFolder:
    @pytest.mark.unit
    def test_builds_expected_name(self, service, tmp_path):
        """GIVEN operator/measurement, WHEN build_data_folder, THEN Data_<op>_<m>."""
        folder = service.build_data_folder(tmp_path, "TM", "1")
        assert folder.name == "Data_TM_1"


class TestAnnotationsIO:
    @pytest.mark.unit
    def test_save_then_load_round_trip(self, service, tmp_path):
        """GIVEN slice annotations, WHEN save then load, THEN slice keys preserved as ints."""
        slice_annotations = {
            0: [{"id": "GAP_0", "feature": "GAP", "points": [(1, 2), (3, 4)],
                 "mode": "line", "color": "#FFF", "locked": True}],
        }
        path = tmp_path / "annotations" / "a.json"
        service.save_annotations(slice_annotations, path)
        assert path.exists()
        loaded = service.load_annotations(path)
        assert 0 in loaded
        assert loaded[0][0]["id"] == "GAP_0"


class TestResultsIO:
    @pytest.mark.unit
    def test_save_then_load_round_trip(self, service, tmp_path):
        """GIVEN headers and rows, WHEN save then load CSV, THEN content matches."""
        headers = ["SPECIMEN_NAME", "SLICE"]
        data = [["A", "1"], ["B", "2"]]
        path = tmp_path / "results" / "r.csv"
        service.save_results(headers, data, path)
        loaded_headers, loaded_data = service.load_results(path)
        assert loaded_headers == headers
        assert loaded_data == data

    @pytest.mark.unit
    def test_load_empty_file_returns_empty(self, service, tmp_path):
        """GIVEN an empty CSV, WHEN load_results, THEN returns ([], [])."""
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        assert service.load_results(path) == ([], [])


class TestConfigIO:
    @pytest.mark.unit
    def test_save_config_creates_file(self, service, tmp_path):
        """GIVEN a config, WHEN save_config, THEN JSON file is written."""
        path = tmp_path / "Data_TM_1" / "c.json"
        service.save_config({"metadata": {}}, path)
        assert json.loads(path.read_text(encoding="utf-8")) == {"metadata": {}}
