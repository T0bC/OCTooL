"""
Unit tests for app/logic/carlquant/data_io.py.

Covers JSON config round-trip (regions + AIR + computed annotations), Excel
results round-trip, image-stack discovery, annotated-image rendering, and the
error/fallback branches in DataLoader/DataSaver.
"""
import json

import numpy as np
import pytest
from PIL import Image

from app.logic.carlquant.data_io import (
    DataLoader,
    DataSaver,
    convert_to_json_serializable,
    natural_key,
)
from app.logic.carlquant.specimen_model import (
    Specimen,
    SpecimenConfig,
    RegionConfig,
    AirConfig,
    SliceResult,
    RegionStats,
    Surface,
    LesionDepth,
)


def _make_specimen(source, *, operator="OP", measurement=1, with_images=0):
    """Build a Specimen rooted at ``source`` with operator/measurement metadata."""
    images = []
    for i in range(with_images):
        p = source / f"slice_{i:03d}.png"
        Image.new("L", (40, 30), color=128).save(p)
        images.append(p)

    spec = Specimen(
        specimen_id="tooth1",
        source=source,
        images=images,
        slices=max(with_images, 1),
        status="New",
        date=0.0,
    )
    spec.operator = operator
    spec.measurement = measurement
    return spec


def _populate_config(spec):
    cfg = SpecimenConfig(specimen_id=spec.specimen_id)
    cfg.regions[0] = RegionConfig(
        slice_index=0,
        specimen_start=(5, 10),
        lesion_start=(15, 10),
        lesion_end=(25, 10),
        tooth_end=(35, 10),
        is_keyframe=True,
        buffer_pixels=8,
    )
    cfg.air[0] = AirConfig(
        slice_index=0,
        point1=(1, 2),
        point2=(3, 4),
        is_keyframe=True,
    )
    spec.config = cfg


def _populate_results(spec):
    surface = Surface(
        raw_points=[(0, 5), (1, 6)],
        fitted_curves={"actual_surface": [(0, 5), (1, 6)]},
        is_cavitated=True,
        cavitation_depth=2.5,
    )
    lesion_depth = LesionDepth(
        depth_points=[(0, 12), (1, 13)],
        mean_depth=11.0,
        median_depth=12.0,
        sd=1.0,
        se=0.5,
        smoothed_depth_points=[(0, 11), (1, 12)],
    )
    region_stats = [
        RegionStats("sound", [10, 20], mean=15, median=15, sd=5, se=2,
                    region_index=1, bounds=(0, 0, 10, 10)),
        RegionStats("lesion", [30, 40], mean=35, median=35, sd=5, se=2,
                    region_index=2, bounds=(10, 0, 20, 10)),
    ]
    spec.results[0] = SliceResult(
        slice_index=0,
        region_stats=region_stats,
        surface=surface,
        lesion_depth=lesion_depth,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_natural_key_sorts_numerically():
    """natural_key should order names like a human (slice_2 before slice_10)."""
    from pathlib import Path
    names = [Path("slice_10.png"), Path("slice_2.png"), Path("slice_1.png")]
    names.sort(key=natural_key)
    assert [p.name for p in names] == ["slice_1.png", "slice_2.png", "slice_10.png"]


@pytest.mark.unit
def test_convert_to_json_serializable_numpy_types():
    """numpy scalars/arrays/bools should become native Python types."""
    payload = {
        "i": np.int64(5),
        "f": np.float32(1.5),
        "a": np.array([1, 2, 3]),
        "b": np.bool_(True),
        "nested": [np.int32(7)],
        "plain": "ok",
    }
    out = convert_to_json_serializable(payload)
    assert out["i"] == 5 and isinstance(out["i"], int)
    assert out["f"] == pytest.approx(1.5) and isinstance(out["f"], float)
    assert out["a"] == [1, 2, 3]
    assert out["b"] is True
    assert out["nested"] == [7]
    assert out["plain"] == "ok"
    # Must be JSON-dumpable without error.
    json.dumps(out)


# ---------------------------------------------------------------------------
# Config JSON round-trip
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_config_round_trip(tmp_path):
    """save_specimen_config -> load_specimen_config preserves regions and AIR."""
    spec = _make_specimen(tmp_path)
    _populate_config(spec)

    DataSaver.save_specimen_config(spec)

    config_file = tmp_path / "Data_OP_1" / "tooth1_config.json"
    assert config_file.exists()

    # Fresh specimen reads the saved config back.
    reloaded = _make_specimen(tmp_path)
    reloaded.previous_runs = [tmp_path / "Data_OP_1"]
    cfg = DataLoader.load_specimen_config(reloaded)

    assert cfg is not None
    region = cfg.regions[0]
    assert region.specimen_start == (5, 10)
    assert region.tooth_end == (35, 10)
    assert region.is_keyframe is True
    assert region.buffer_pixels == 8

    air = cfg.air[0]
    assert air.point1 == (1, 2)
    assert air.point2 == (3, 4)


@pytest.mark.unit
def test_annotations_round_trip(tmp_path):
    """Computed annotations survive the save/load cycle into specimen.results."""
    spec = _make_specimen(tmp_path)
    _populate_config(spec)
    _populate_results(spec)

    DataSaver.save_specimen_config(spec, include_annotations=True)

    reloaded = _make_specimen(tmp_path)
    reloaded.previous_runs = [tmp_path / "Data_OP_1"]
    DataLoader.load_specimen_config(reloaded, load_annotations=True)

    assert 0 in reloaded.results
    result = reloaded.results[0]
    assert result.surface.raw_points == [(0, 5), (1, 6)]
    assert result.surface.is_cavitated is True
    assert result.surface.cavitation_depth == pytest.approx(2.5)
    assert result.lesion_depth.mean_depth == pytest.approx(11.0)
    assert result.lesion_depth.smoothed_depth_points == [(0, 11), (1, 12)]
    assert len(result.region_stats) == 2
    assert result.region_stats[0].region_type == "sound"


@pytest.mark.unit
def test_load_config_marks_annotations_without_loading(tmp_path):
    """With load_annotations=False, results stay empty but the flag is set."""
    spec = _make_specimen(tmp_path)
    _populate_config(spec)
    _populate_results(spec)
    DataSaver.save_specimen_config(spec, include_annotations=True)

    reloaded = _make_specimen(tmp_path)
    reloaded.previous_runs = [tmp_path / "Data_OP_1"]
    DataLoader.load_specimen_config(reloaded, load_annotations=False)

    assert reloaded.results == {}
    assert getattr(reloaded, "_has_annotations", False) is True


@pytest.mark.unit
def test_load_config_legacy_two_point_format(tmp_path):
    """Old 2-point region format is converted to the 4-point structure."""
    folder = tmp_path / "Data_OP_1"
    folder.mkdir()
    legacy = {
        "specimen_id": "tooth1",
        "regions": {
            "0": {"start_point": [5, 10], "end_point": [35, 10]}
        },
    }
    (folder / "tooth1_config.json").write_text(json.dumps(legacy))

    spec = _make_specimen(tmp_path)
    spec.previous_runs = [folder]
    cfg = DataLoader.load_specimen_config(spec)

    region = cfg.regions[0]
    assert region.specimen_start == (5, 10)
    assert region.lesion_start == (5, 10)
    assert region.lesion_end == (35, 10)
    assert region.tooth_end == (35, 10)


# ---------------------------------------------------------------------------
# Excel results round-trip
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_results_excel_round_trip(tmp_path):
    """save_results writes an xlsx that load_results reads back."""
    spec = _make_specimen(tmp_path)
    _populate_config(spec)
    _populate_results(spec)

    DataSaver.save_results(spec)

    result_file = tmp_path / "Data_OP_1" / "tooth1_results.xlsx"
    assert result_file.exists()

    reloaded = _make_specimen(tmp_path)
    reloaded.previous_runs = [tmp_path / "Data_OP_1"]
    DataLoader.load_results(reloaded, region_config={"sound": 1, "lesion": 1})

    assert 0 in reloaded.results
    result = reloaded.results[0]
    medians = [r.median for r in result.region_stats]
    assert 15.0 in medians  # sound median
    assert 35.0 in medians  # lesion median
    assert result.lesion_depth.mean_depth == pytest.approx(11.0)


@pytest.mark.unit
def test_store_slice_result(tmp_path):
    """store_slice_result attaches a SliceResult to the specimen."""
    spec = _make_specimen(tmp_path)
    surface = Surface([], {})
    lesion = LesionDepth([], 0, 0, 0, 0)
    DataSaver.store_slice_result(spec, 3, [], surface, lesion)
    assert spec.results[3].slice_index == 3


# ---------------------------------------------------------------------------
# Image stack discovery
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_find_image_stacks(tmp_path):
    """find_image_stacks discovers folders containing images and skips annotations."""
    stack_dir = tmp_path / "specimenA"
    stack_dir.mkdir()
    for i in range(3):
        Image.new("L", (10, 10)).save(stack_dir / f"img_{i}.png")

    # An annotations folder must be ignored even though it has images.
    annot = stack_dir / "annotations"
    annot.mkdir()
    Image.new("L", (10, 10)).save(annot / "img_0.png")

    found = DataLoader.find_image_stacks(tmp_path)
    assert "specimenA" in found
    assert found["specimenA"].slices == 3
    assert "annotations" not in found


# ---------------------------------------------------------------------------
# Error / fallback branches
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_load_config_missing_returns_none(tmp_path):
    """No config file anywhere -> load_specimen_config returns None."""
    spec = _make_specimen(tmp_path)
    spec.previous_runs = []
    assert DataLoader.load_specimen_config(spec) is None


@pytest.mark.unit
def test_load_config_malformed_json_returns_none(tmp_path):
    """Malformed JSON is swallowed and yields None."""
    folder = tmp_path / "Data_OP_1"
    folder.mkdir()
    (folder / "tooth1_config.json").write_text("{not valid json")

    spec = _make_specimen(tmp_path)
    spec.previous_runs = [folder]
    assert DataLoader.load_specimen_config(spec) is None


@pytest.mark.unit
def test_save_config_noop_without_config(tmp_path):
    """save_specimen_config returns early when specimen has no config."""
    spec = _make_specimen(tmp_path)
    spec.config = None
    DataSaver.save_specimen_config(spec)
    assert not (tmp_path / "Data_OP_1").exists()


@pytest.mark.unit
def test_load_results_no_previous_runs_is_noop(tmp_path):
    """load_results returns immediately when there are no previous runs."""
    spec = _make_specimen(tmp_path)
    spec.previous_runs = []
    DataLoader.load_results(spec, region_config={"sound": 1, "lesion": 1})
    assert spec.results == {}


@pytest.mark.unit
def test_load_results_missing_folder_is_noop(tmp_path):
    """load_results returns when the operator/measurement folder is absent."""
    spec = _make_specimen(tmp_path, operator="XX", measurement=9)
    spec.previous_runs = [tmp_path / "Data_OP_1"]
    DataLoader.load_results(spec, region_config={"sound": 1, "lesion": 1})
    assert spec.results == {}


# ---------------------------------------------------------------------------
# Annotated images
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_save_annotated_images(tmp_path):
    """save_annotated_images renders one PNG per result slice."""
    spec = _make_specimen(tmp_path, with_images=1)
    _populate_config(spec)
    _populate_results(spec)

    DataSaver.save_annotated_images(spec)

    annot_dir = tmp_path / "Data_OP_1" / "annotations"
    pngs = list(annot_dir.glob("*.png"))
    assert len(pngs) == 1


@pytest.mark.unit
def test_save_annotated_images_noop_without_results(tmp_path):
    """No results -> no annotations folder is created."""
    spec = _make_specimen(tmp_path, with_images=1)
    DataSaver.save_annotated_images(spec)
    assert not (tmp_path / "Data_OP_1" / "annotations").exists()
