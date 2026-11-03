"""
Unit tests for app/logic/scanalign/export_service.py

Tests output naming, folder claiming, copying, the JSON registration log and
cancellation cleanup on synthetic RexView-style stacks in tmp_path.
"""

import filecmp
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.logic.scanalign.export_service import (
    LOG_FILE_NAME,
    RegistrationExporter,
    next_free_folder,
    output_file_name,
    output_folder_name,
    resolve_exp_number,
    resolve_name,
)
from app.logic.scanalign.matching_service import build_pairs
from app.logic.scanalign.models import SliceRange
from app.logic.scanalign.stack_service import compare_geometry, load_stack, parse_filename
from app.logic.shared.app_config import __version__
from app.logic.shared.paths import natural_sort_key


def make_stack(parent: Path, specimen: str, name: str, exp: int, n_slices: int, first: int = 1):
    """Create <parent>/<specimen>/<exp>_<name>_..._XZ with RexView file names and load it."""
    folder = parent / specimen / f"{exp:02d}_{name}_{n_slices}_Slices_XZ"
    folder.mkdir(parents=True)
    for i in range(n_slices):
        number = first + i
        arr = np.full((20, 30), (number * 7) % 256, dtype=np.uint8)
        Image.fromarray(arr, mode="L").save(
            folder / f"{name}_{exp}_#{number}_{i + 1:04d}.tiff", dpi=(204, 204)
        )
    return load_stack(folder)


@pytest.fixture
def two_stacks(tmp_path):
    """Two scans of the same specimen (T1 and T2) in different export folders."""
    s1 = make_stack(tmp_path, "010RI", "010RI_T1", 1, 20, first=1)
    s2 = make_stack(tmp_path, "010RI", "010RI_T2", 2, 24, first=1)
    return s1, s2


def run_export(s1, s2, r1, r2, n, exporter=None, on_progress=None):
    exporter = exporter or RegistrationExporter()
    pairs = build_pairs(s1, s2, r1, r2, n)
    comparison = compare_geometry(s1.geometry, s2.geometry)
    return exporter.run(s1, s2, r1, r2, pairs, comparison, on_progress)


class TestNaming:
    """Tests for output_folder_name, output_file_name and next_free_folder."""

    @pytest.mark.unit
    def test_output_folder_name(self):
        """GIVEN exp, name and n, WHEN naming, THEN exp is zero-padded and name included."""
        assert output_folder_name(1, "010RI", 25) == "01_010RI_ScanAlign_25"
        assert output_folder_name(12, "010RI_post", 5) == "12_010RI_post_ScanAlign_5"

    @pytest.mark.unit
    def test_output_folder_name_sanitises_name(self):
        """GIVEN unsafe or empty names, WHEN naming, THEN they are replaced or left out."""
        assert output_folder_name(1, 'a<b>:c"d/e\\f|g?h*', 3) == "01_a_b__c_d_e_f_g_h__ScanAlign_3"
        assert output_folder_name(1, "", 3) == "01_ScanAlign_3"
        assert output_folder_name(1, " . ", 3) == "01_ScanAlign_3"

    @pytest.mark.unit
    def test_output_file_name_round_trips(self):
        """GIVEN a generated name, WHEN parsed by stack_service, THEN all parts are recovered."""
        file_name = output_file_name("010RI_T1_x", 3, 688, 7, ".png")
        assert file_name == "010RI_T1_x_3_#688_0007.png"
        assert parse_filename(Path(file_name)) == ("010RI_T1_x", 3, 688, 7)

    @pytest.mark.unit
    def test_next_free_folder_numbers_up(self, tmp_path):
        """GIVEN existing folders, WHEN asking, THEN _2, _3 ... are appended."""
        assert next_free_folder(tmp_path, "01_ScanAlign_5") == "01_ScanAlign_5"
        (tmp_path / "01_ScanAlign_5").mkdir()
        assert next_free_folder(tmp_path, "01_ScanAlign_5") == "01_ScanAlign_5_2"
        (tmp_path / "01_ScanAlign_5_2").mkdir()
        assert next_free_folder(tmp_path, "01_ScanAlign_5") == "01_ScanAlign_5_3"


class TestFallbacks:
    """Tests for resolve_exp_number and resolve_name."""

    @pytest.mark.unit
    def test_exp_from_stack(self, two_stacks):
        """GIVEN a parsed exp number, WHEN resolving, THEN it is used."""
        assert resolve_exp_number(two_stacks[1]) == 2

    @pytest.mark.unit
    def test_exp_from_folder_name(self, two_stacks):
        """GIVEN no parsed exp, WHEN resolving, THEN the folder's leading digits are used."""
        stack = two_stacks[1].model_copy(update={"exp_number": None})
        assert resolve_exp_number(stack) == 2

    @pytest.mark.unit
    def test_exp_default_is_one(self, two_stacks, tmp_path):
        """GIVEN neither exp nor a numbered folder, WHEN resolving, THEN 1 is returned."""
        stack = two_stacks[0].model_copy(
            update={"exp_number": None, "folder": tmp_path / "plain_folder"}
        )
        assert resolve_exp_number(stack) == 1

    @pytest.mark.unit
    def test_name_falls_back_to_specimen(self, two_stacks):
        """GIVEN no parsed name, WHEN resolving, THEN the specimen is used."""
        assert resolve_name(two_stacks[0]) == "010RI_T1"
        stack = two_stacks[0].model_copy(update={"name": None})
        assert resolve_name(stack) == "010RI"


class TestRegistrationExporter:
    """Tests for RegistrationExporter.run."""

    @pytest.mark.unit
    def test_copies_are_byte_identical_and_k_ordered(self, two_stacks):
        """GIVEN two stacks, WHEN exporting, THEN N byte-identical files per folder in k order."""
        s1, s2 = two_stacks
        r1, r2 = SliceRange(first=2, last=17), SliceRange(first=5, last=20)
        result = run_export(s1, s2, r1, r2, 6)
        pairs = build_pairs(s1, s2, r1, r2, 6)

        assert not result.cancelled
        assert result.n_files == 12
        for folder, stack, column in ((result.folders[0], s1, 1), (result.folders[1], s2, 2)):
            images = sorted(folder.glob("*.tiff"), key=natural_sort_key)
            assert len(images) == 6
            parsed = [parse_filename(p) for p in images]
            assert [p[3] for p in parsed] == [1, 2, 3, 4, 5, 6]
            for pair, image in zip(pairs, images, strict=True):
                index = pair.index1 if column == 1 else pair.index2
                assert filecmp.cmp(stack.files[index].path, image, shallow=False)

    @pytest.mark.unit
    def test_folder_names_and_location(self, two_stacks):
        """GIVEN scans in the same parent, WHEN exporting, THEN folders are distinct siblings."""
        s1, s2 = two_stacks
        result = run_export(s1, s2, SliceRange(first=0, last=9), SliceRange(first=0, last=9), 4)
        assert result.folders[0] == s1.folder.parent / "01_010RI_T1_ScanAlign_4"
        assert result.folders[1] == s2.folder.parent / "02_010RI_T2_ScanAlign_4"

    @pytest.mark.unit
    def test_same_parent_and_exp_get_distinct_folders(self, tmp_path):
        """GIVEN two scans with the same exp, name and parent, WHEN exporting, THEN _2 is used."""
        s1 = make_stack(tmp_path, "010RI", "010RI_T1", 1, 10)
        folder2 = tmp_path / "010RI" / "01_other_XZ"
        folder2.mkdir()
        for i in range(10):
            Image.fromarray(np.zeros((20, 30), dtype=np.uint8), mode="L").save(
                folder2 / f"010RI_T1_1_#{i + 1}_{i + 1:04d}.tiff"
            )
        s2 = load_stack(folder2)
        result = run_export(s1, s2, SliceRange(first=0, last=9), SliceRange(first=0, last=9), 3)
        assert result.folders[0].name == "01_010RI_T1_ScanAlign_3"
        assert result.folders[1].name == "01_010RI_T1_ScanAlign_3_2"
        assert result.folders[0] != result.folders[1]

    @pytest.mark.unit
    def test_existing_folder_is_left_untouched(self, two_stacks):
        """GIVEN an existing output folder, WHEN exporting, THEN it is not written into."""
        s1, s2 = two_stacks
        existing = s1.folder.parent / "01_010RI_T1_ScanAlign_4"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        result = run_export(s1, s2, SliceRange(first=0, last=9), SliceRange(first=0, last=9), 4)
        assert result.folders[0].name == "01_010RI_T1_ScanAlign_4_2"
        assert [p.name for p in existing.iterdir()] == ["keep.txt"]

    @pytest.mark.unit
    def test_json_log_in_both_folders(self, two_stacks):
        """GIVEN a finished export, WHEN reading the logs, THEN both are complete and mirrored."""
        s1, s2 = two_stacks
        r1, r2 = SliceRange(first=2, last=17), SliceRange(first=5, last=20)
        result = run_export(s1, s2, r1, r2, 6)

        log1 = json.loads((result.folders[0] / LOG_FILE_NAME).read_text(encoding="utf-8"))
        log2 = json.loads((result.folders[1] / LOG_FILE_NAME).read_text(encoding="utf-8"))
        assert log1["schema_version"] == 1
        assert log1["octool_version"] == __version__
        assert log1["created"]
        assert (log1["role"], log2["role"]) == ("reference", "moving")
        assert log1["scan"] == log2["partner"]
        assert log1["partner"] == log2["scan"]
        assert log1["scan"]["output_folder"] == str(result.folders[0])
        assert log1["scan"]["range_positions"] == [2, 17]
        assert log1["scan"]["range_slice_numbers"] == [3, 18]
        assert log1["partner"]["range_slice_numbers"] == [6, 21]
        assert log1["n"] == 6
        assert log1["offset"] == 3
        assert log1["scale"] == pytest.approx(1.0)
        assert log1["comparison"]["kind"] == log2["comparison"]["kind"]
        assert log1["pairs"] == log2["pairs"]
        assert len(log1["pairs"]) == 6
        first = log1["pairs"][0]
        assert first["k"] == 1
        assert first["slice1"] == 3
        assert first["slice2"] == 6
        assert first["source1"] == s1.files[2].path.name
        assert first["source2"] == s2.files[5].path.name
        assert (result.folders[0] / first["output1"]).is_file()
        assert (result.folders[1] / first["output2"]).is_file()

    @pytest.mark.unit
    def test_progress_is_reported(self, two_stacks):
        """GIVEN a progress callback, WHEN exporting, THEN it ends at (total, total)."""
        s1, s2 = two_stacks
        calls = []
        run_export(
            s1,
            s2,
            SliceRange(first=0, last=9),
            SliceRange(first=0, last=9),
            3,
            on_progress=lambda done, total: calls.append((done, total)),
        )
        assert calls[-1] == (6, 6)
        assert [c[0] for c in calls] == sorted(c[0] for c in calls)

    @pytest.mark.unit
    def test_cancel_removes_only_created_folders(self, two_stacks):
        """GIVEN a cancel mid-way, WHEN exporting, THEN created folders vanish, others stay."""
        s1, s2 = two_stacks
        existing = s1.folder.parent / "01_010RI_T1_ScanAlign_4"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        before = sorted(p.name for p in s1.folder.parent.iterdir())

        exporter = RegistrationExporter()

        def cancel_midway(done, total):
            if done == 3:
                exporter.cancel()

        result = run_export(
            s1,
            s2,
            SliceRange(first=0, last=9),
            SliceRange(first=0, last=9),
            4,
            exporter=exporter,
            on_progress=cancel_midway,
        )
        assert result.cancelled
        assert sorted(p.name for p in s1.folder.parent.iterdir()) == before
        assert (existing / "keep.txt").is_file()
        assert not any(f.exists() for f in result.folders)

    @pytest.mark.unit
    def test_missing_source_raises_and_creates_nothing(self, two_stacks):
        """GIVEN a deleted source file, WHEN exporting, THEN ValueError and no folders."""
        s1, s2 = two_stacks
        before = sorted(p.name for p in s1.folder.parent.iterdir())
        s2.files[9].path.unlink()
        with pytest.raises(ValueError, match="no longer exist"):
            run_export(s1, s2, SliceRange(first=0, last=9), SliceRange(first=0, last=9), 4)
        assert sorted(p.name for p in s1.folder.parent.iterdir()) == before

    @pytest.mark.unit
    def test_copy_error_cleans_up_and_reraises(self, two_stacks, monkeypatch):
        """GIVEN a failing copy, WHEN exporting, THEN the error propagates and folders vanish."""
        s1, s2 = two_stacks
        before = sorted(p.name for p in s1.folder.parent.iterdir())

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("app.logic.scanalign.export_service.shutil.copy2", boom)
        with pytest.raises(OSError, match="disk full"):
            run_export(s1, s2, SliceRange(first=0, last=9), SliceRange(first=0, last=9), 4)
        assert sorted(p.name for p in s1.folder.parent.iterdir()) == before
