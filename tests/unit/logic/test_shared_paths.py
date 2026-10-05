"""
Unit tests for app.logic.shared.paths (natural sort key, Data_ folder helpers)
and app.logic.carlquant.data_io.specimen_data_folder.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.logic.carlquant.data_io import specimen_data_folder
from app.logic.shared.paths import data_folder, natural_sort_key


class TestNaturalSortKey:
    @pytest.mark.unit
    def test_numbers_sort_numerically(self):
        """GIVEN slice_10, slice_2, slice_1, WHEN sorted, THEN 1, 2, 10."""
        paths = [Path("slice_10.png"), Path("slice_2.png"), Path("slice_1.png")]
        paths.sort(key=natural_sort_key)
        assert [p.name for p in paths] == ["slice_1.png", "slice_2.png", "slice_10.png"]

    @pytest.mark.unit
    def test_text_is_case_insensitive(self):
        """GIVEN mixed-case names, WHEN sorted, THEN case is ignored."""
        paths = [Path("b_1.png"), Path("A_2.png"), Path("a_1.png")]
        paths.sort(key=natural_sort_key)
        assert [p.name for p in paths] == ["a_1.png", "A_2.png", "b_1.png"]

    @pytest.mark.unit
    def test_only_file_name_is_used(self):
        """GIVEN equal names in different folders, WHEN keyed, THEN keys are equal."""
        assert natural_sort_key(Path("x/slice_3.png")) == natural_sort_key(Path("y/slice_3.png"))


class TestDataFolder:
    @pytest.mark.unit
    def test_builds_expected_name_from_path(self, tmp_path):
        """GIVEN a Path source, WHEN data_folder, THEN source/Data_<op>_<m>."""
        assert data_folder(tmp_path, "TM", 2) == tmp_path / "Data_TM_2"

    @pytest.mark.unit
    def test_accepts_string_source(self, tmp_path):
        """GIVEN a str source and str measurement, WHEN data_folder, THEN a Path is returned."""
        folder = data_folder(str(tmp_path), "TM", "1")
        assert isinstance(folder, Path)
        assert folder == tmp_path / "Data_TM_1"


class TestSpecimenDataFolder:
    @pytest.mark.unit
    def test_uses_specimen_metadata(self, tmp_path):
        """GIVEN operator/measurement on the specimen, WHEN resolved, THEN they are used."""
        specimen = SimpleNamespace(source=tmp_path, operator="TM", measurement=3)
        assert specimen_data_folder(specimen) == tmp_path / "Data_TM_3"

    @pytest.mark.unit
    def test_defaults_without_metadata(self, tmp_path):
        """GIVEN no operator/measurement, WHEN resolved, THEN Data_OP_1 is used."""
        specimen = SimpleNamespace(source=tmp_path)
        assert specimen_data_folder(specimen) == tmp_path / "Data_OP_1"
