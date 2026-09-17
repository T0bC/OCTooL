#!/usr/bin/env python3
"""Unit tests for loadImagePanel.validate_specimen_coordinates.

This decides which specimens get highlighted red in the Specimen table and
whether "Start Analyzing" is allowed to proceed at all, but had zero test
coverage. The panel is tkinter-bound, so the instance is built with
``__new__`` (skipping the constructor and its widgets) and given just the
``context.specimen_data`` the method actually reads.
"""

from types import SimpleNamespace

import pytest

from app.logic.carlquant.specimen_model import AirConfig, RegionConfig, SpecimenConfig
from app.view.carlquant.load_images_panel import loadImagePanel


def make_panel(specimen_data=None):
    panel = loadImagePanel.__new__(loadImagePanel)
    panel.context = SimpleNamespace(specimen_data=specimen_data or {})
    return panel


def make_specimen(config=None):
    return SimpleNamespace(config=config)


def complete_region_config(slice_index=0):
    return RegionConfig(
        slice_index=slice_index,
        specimen_start=(10, 10),
        lesion_start=(20, 10),
        lesion_end=(30, 10),
        tooth_end=(40, 10),
    )


def complete_air_config(slice_index=0):
    return AirConfig(slice_index=slice_index, point1=(5, 5), point2=(15, 15))


@pytest.mark.unit
def test_no_specimens_is_valid():
    """GIVEN no specimen data at all, THEN validation trivially passes."""
    panel = make_panel(specimen_data=None)

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is True
    assert invalid == {}


@pytest.mark.unit
def test_empty_specimen_dict_is_valid():
    """GIVEN an empty specimen dict, THEN validation trivially passes."""
    panel = make_panel(specimen_data={})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is True
    assert invalid == {}


@pytest.mark.unit
def test_missing_config_flags_both_region_and_air():
    """GIVEN a specimen with no config at all, THEN both kinds are reported missing."""
    panel = make_panel({"spec_a": make_specimen(config=None)})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is False
    assert invalid == {"spec_a": ["Region boundaries", "AIR coordinates"]}


@pytest.mark.unit
def test_config_with_empty_regions_and_air_flags_both():
    """GIVEN a config with no slices configured, THEN both kinds are reported missing."""
    config = SpecimenConfig(specimen_id="spec_a", regions={}, air={})
    panel = make_panel({"spec_a": make_specimen(config=config)})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is False
    assert invalid == {"spec_a": ["Region boundaries", "AIR coordinates"]}


@pytest.mark.unit
def test_region_missing_a_point_is_flagged_incomplete():
    """GIVEN a region config missing one of its four points, THEN it's flagged incomplete."""
    incomplete_region = RegionConfig(
        slice_index=0,
        specimen_start=(10, 10),
        lesion_start=None,
        lesion_end=(30, 10),
        tooth_end=(40, 10),
    )
    config = SpecimenConfig(
        specimen_id="spec_a",
        regions={0: incomplete_region},
        air={0: complete_air_config()},
    )
    panel = make_panel({"spec_a": make_specimen(config=config)})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is False
    assert invalid == {"spec_a": ["Region boundaries (incomplete)"]}


@pytest.mark.unit
def test_air_missing_second_point_is_flagged_incomplete():
    """GIVEN an AIR config with only one of its two points, THEN it's incomplete."""
    incomplete_air = AirConfig(slice_index=0, point1=(5, 5), point2=None)
    config = SpecimenConfig(
        specimen_id="spec_a",
        regions={0: complete_region_config()},
        air={0: incomplete_air},
    )
    panel = make_panel({"spec_a": make_specimen(config=config)})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is False
    assert invalid == {"spec_a": ["AIR coordinates (incomplete)"]}


@pytest.mark.unit
def test_fully_configured_specimen_is_valid():
    """GIVEN complete region and AIR config, THEN the specimen passes with nothing missing."""
    config = SpecimenConfig(
        specimen_id="spec_a",
        regions={0: complete_region_config()},
        air={0: complete_air_config()},
    )
    panel = make_panel({"spec_a": make_specimen(config=config)})

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is True
    assert invalid == {}


@pytest.mark.unit
def test_one_invalid_specimen_does_not_flag_a_valid_sibling():
    """GIVEN a mix of complete and incomplete specimens, THEN only the bad one is reported."""
    good_config = SpecimenConfig(
        specimen_id="good",
        regions={0: complete_region_config()},
        air={0: complete_air_config()},
    )
    panel = make_panel(
        {
            "good": make_specimen(config=good_config),
            "bad": make_specimen(config=None),
        }
    )

    is_valid, invalid = panel.validate_specimen_coordinates()

    assert is_valid is False
    assert list(invalid.keys()) == ["bad"]
