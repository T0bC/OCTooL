"""
Unit tests for app/logic/carlquant/ground_truth.py.

Covers the ground-truth file convention, round-tripping operator marks, the
refusal to load one specimen's marks for another, and the atomic save that
protects existing marks from an interrupted write.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.logic.carlquant import ground_truth as gt


def make_specimen(tmp_path: Path, specimen_id="1_1.7_E_PBS_KIM", operator="TM", measurement=1):
    """Minimal stand-in for a Specimen: ground_truth only reads these fields."""
    return SimpleNamespace(
        specimen_id=specimen_id,
        source=tmp_path / specimen_id,
        operator=operator,
        measurement=measurement,
    )


@pytest.mark.unit
def test_ground_truth_path_sits_beside_the_config(tmp_path):
    """GIVEN a specimen, WHEN resolving the path, THEN it is in its Data_ folder."""
    specimen = make_specimen(tmp_path)
    path = gt.ground_truth_path(specimen)
    assert path.parent.name == "Data_TM_1"
    assert path.name == "1_1.7_E_PBS_KIM_groundtruth.json"


@pytest.mark.unit
def test_ground_truth_path_uses_save_config_defaults(tmp_path):
    """GIVEN no operator metadata, WHEN resolving, THEN the Data_OP_1 default is used."""
    specimen = SimpleNamespace(specimen_id="spec", source=tmp_path / "spec")
    assert gt.ground_truth_path(specimen).parent.name == "Data_OP_1"


@pytest.mark.unit
def test_load_returns_empty_for_missing_file(tmp_path):
    """GIVEN no ground truth, WHEN loading, THEN {} is returned and nothing raises."""
    specimen = make_specimen(tmp_path)
    assert gt.load_ground_truth(specimen) == {}
    assert gt.has_ground_truth(specimen) is False


@pytest.mark.unit
def test_save_load_round_trip(tmp_path):
    """GIVEN marks, WHEN saved and reloaded, THEN the coordinates survive intact."""
    specimen = make_specimen(tmp_path)
    marks = {
        0: [(431.2, 118.4), (462.0, 119.1)],
        11: [(440.5, 96.2)],
    }
    gt.save_ground_truth(specimen, marks)

    assert gt.has_ground_truth(specimen) is True
    assert gt.load_ground_truth(specimen) == marks


@pytest.mark.unit
def test_load_converts_string_slice_keys_to_int(tmp_path):
    """GIVEN JSON string keys, WHEN loading, THEN slice indices are ints."""
    specimen = make_specimen(tmp_path)
    path = gt.ground_truth_path(specimen)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "specimen_id": specimen.specimen_id,
                "lesion_end": {"0": [[1.0, 2.0]], "11": [[3.0, 4.0]]},
            }
        )
    )

    marks = gt.load_ground_truth(specimen)
    assert sorted(marks) == [0, 11]
    assert marks[11] == [(3.0, 4.0)]


@pytest.mark.unit
def test_load_refuses_marks_from_another_specimen(tmp_path):
    """GIVEN a mismatched specimen_id, WHEN loading, THEN it raises rather than lie.

    Marks are absolute pixels into one image stack, so reusing them across
    specimens yields plausible-looking but meaningless errors.
    """
    specimen = make_specimen(tmp_path)
    path = gt.ground_truth_path(specimen)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "specimen_id": "mixed_carl_quant_test_data",
                "lesion_end": {"0": [[1.0, 2.0]]},
            }
        )
    )

    with pytest.raises(gt.GroundTruthMismatchError):
        gt.load_ground_truth(specimen)


@pytest.mark.unit
def test_save_drops_slices_with_no_marks(tmp_path):
    """GIVEN a cleared slice, WHEN saving, THEN it is absent rather than empty."""
    specimen = make_specimen(tmp_path)
    gt.save_ground_truth(specimen, {0: [(1.0, 2.0)], 5: []})

    payload = json.loads(gt.ground_truth_path(specimen).read_text())
    assert list(payload["lesion_end"]) == ["0"]


@pytest.mark.unit
def test_save_is_atomic_when_interrupted(tmp_path, monkeypatch):
    """GIVEN a save that fails mid-write, WHEN it raises, THEN old marks survive."""
    specimen = make_specimen(tmp_path)
    original = {0: [(1.0, 2.0)]}
    gt.save_ground_truth(specimen, original)

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(gt.os, "replace", explode)
    with pytest.raises(OSError):
        gt.save_ground_truth(specimen, {0: [(9.0, 9.0)], 1: [(8.0, 8.0)]})

    assert gt.load_ground_truth(specimen) == original
    # The failed attempt must not leave a temp file behind.
    leftovers = list(gt.ground_truth_path(specimen).parent.glob("*.tmp"))
    assert leftovers == []


@pytest.mark.unit
def test_load_ignores_corrupt_file(tmp_path):
    """GIVEN an unreadable file, WHEN loading, THEN {} is returned, not an exception.

    A corrupt ground-truth file must not stop the specimen from opening.
    """
    specimen = make_specimen(tmp_path)
    path = gt.ground_truth_path(specimen)
    path.parent.mkdir(parents=True)
    path.write_text("{not json")

    assert gt.load_ground_truth(specimen) == {}


@pytest.mark.unit
def test_save_never_touches_the_specimen_config(tmp_path):
    """GIVEN an existing config, WHEN saving ground truth, THEN the config is untouched."""
    specimen = make_specimen(tmp_path)
    config_file = (
        tmp_path / specimen.specimen_id / "Data_TM_1" / f"{specimen.specimen_id}_config.json"
    )
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"specimen_id": "1_1.7_E_PBS_KIM", "regions": {}}')
    before = config_file.read_text()

    gt.save_ground_truth(specimen, {0: [(1.0, 2.0)]})

    assert config_file.read_text() == before


@pytest.mark.unit
def test_real_research_ground_truth_files_load(tmp_path):
    """GIVEN the collected 793 marks, WHEN read in this format, THEN they parse.

    The research files are the format this module was written to accept; if this
    breaks, the existing ground truth cannot be imported.
    """
    research = Path("testData/Data_VARIANT_diagnostics/operator_lesion_end_1_1.7_E_PBS_KIM.json")
    if not research.is_file():
        pytest.skip("research ground truth not present in this checkout")

    specimen = make_specimen(tmp_path)
    path = gt.ground_truth_path(specimen)
    path.parent.mkdir(parents=True)
    path.write_bytes(research.read_bytes())

    marks = gt.load_ground_truth(specimen)
    assert len(marks) == 25
    assert sum(len(v) for v in marks.values()) == 465
