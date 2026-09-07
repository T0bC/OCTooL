"""
Unit tests for app/logic/carlquant/validation.py.

Covers the sign convention, the tolerance window for matching marks to analysed
columns, NaN handling, the no-lesion gate, and the two-scale specimen aggregate.

The central trap guarded here is that ``knee_depth`` means two different things
depending on nesting depth: the combined result at the top level of a column,
the raw knee point inside ``detection_metadata``.
"""
import numpy as np
import pytest

from app.logic.carlquant import validation as val


def make_column(surface_y=100.0, combined=20.0, half_span=18.0, knee=25.0,
                inflection=15.0, shoulder=40.0, method_used="median_of_three"):
    """One entry of lesion_detection_data, shaped as carl_quant_core writes it."""
    return {
        "surface_y": surface_y,
        # Top level: the final combined result, under a historical name.
        "knee_depth": combined,
        "detection_metadata": {
            # Nested: the raw component methods.
            "half_span_depth": half_span,
            "knee_depth": knee,
            "inflection_depth": inflection,
            "shoulder_depth": shoulder,
            "combined_method_used": method_used,
        },
    }


def make_slice(columns=(100, 101, 102), **kwargs):
    return {x: make_column(**kwargs) for x in columns}


@pytest.mark.unit
def test_combined_and_knee_read_different_values():
    """GIVEN the knee_depth name collision, WHEN reading, THEN the two differ.

    Getting this wrong makes 'combined' and 'knee' score identically, which
    silently invalidates the whole comparison.
    """
    column = make_column(combined=20.0, knee=25.0)
    assert val.method_depth(column, "combined") == 20.0
    assert val.method_depth(column, "knee") == 25.0


@pytest.mark.unit
def test_detection_below_mark_is_positive():
    """GIVEN a detection deeper than the mark, WHEN scoring, THEN the error is +."""
    data = make_slice(columns=(100,), surface_y=100.0, combined=20.0)
    # Detection lands at y=120; the operator marked y=115 -> 5 px too deep.
    errors = val.method_errors(data, [(100, 115.0)], "combined")
    assert errors.tolist() == [5.0]


@pytest.mark.unit
def test_detection_above_mark_is_negative():
    """GIVEN a detection shallower than the mark, WHEN scoring, THEN the error is -."""
    data = make_slice(columns=(100,), surface_y=100.0, combined=20.0)
    errors = val.method_errors(data, [(100, 128.0)], "combined")
    assert errors.tolist() == [-8.0]


@pytest.mark.unit
def test_nearest_column_within_tolerance():
    """GIVEN a mark between columns, WHEN matching, THEN the closest one is used."""
    data = make_slice(columns=(100, 105))
    assert val.nearest_analysed_column(data, 102.4) == 100
    assert val.nearest_analysed_column(data, 103.6) == 105


@pytest.mark.unit
def test_marks_outside_tolerance_are_skipped():
    """GIVEN a mark far from any analysed column, WHEN scoring, THEN it is skipped.

    Snapping to a distant column would score the wrong A-scan.
    """
    data = make_slice(columns=(100,))
    assert val.nearest_analysed_column(data, 200) is None
    assert val.method_errors(data, [(200, 115.0)], "combined").size == 0


@pytest.mark.unit
def test_nan_depths_are_skipped_not_counted_as_zero():
    """GIVEN a method that failed to converge, WHEN scoring, THEN it is excluded.

    Treating NaN as 0 would score it as a detection exactly at the surface.
    """
    data = {100: make_column(surface_y=100.0, inflection=float("nan"))}
    assert val.method_errors(data, [(100, 115.0)], "inflection").size == 0

    summary = val.score_slice(data, [(100, 115.0)])["methods"]["inflection"]
    assert summary["n"] == 0
    assert not np.isfinite(summary["median"])


@pytest.mark.unit
def test_missing_metadata_value_is_skipped():
    """GIVEN a None depth, WHEN scoring, THEN it is skipped rather than crashing."""
    column = make_column()
    column["detection_metadata"]["shoulder_depth"] = None
    assert not np.isfinite(val.method_depth(column, "shoulder"))


@pytest.mark.unit
def test_empty_marks_return_empty_result_without_raising():
    """GIVEN no marks, WHEN scoring a slice, THEN n=0 everywhere and nothing raises."""
    result = val.score_slice(make_slice(), [])
    assert result["n_marks"] == 0
    for method in val.METHODS:
        assert result["methods"][method]["n"] == 0


@pytest.mark.unit
def test_empty_detection_data_scores_without_raising():
    """GIVEN a slice with no detection data, WHEN scoring, THEN it returns cleanly."""
    result = val.score_slice({}, [(100, 115.0)])
    assert result["methods"]["combined"]["n"] == 0


@pytest.mark.unit
def test_gated_no_lesion_slice_scores_without_error():
    """GIVEN a gated no-lesion slice, WHEN scoring, THEN it scores and is flagged.

    Every depth is 0 (the surface line); this must not divide by zero and the
    gating must stay visible rather than looking like a real shallow lesion.
    """
    data = make_slice(columns=(100, 101), surface_y=100.0, combined=0.0,
                      method_used=val.NO_LESION_METHOD)
    result = val.score_slice(data, [(100, 105.0), (101, 107.0)])

    assert result["gated"] is True
    combined = result["methods"]["combined"]
    assert combined["n"] == 2
    # Marks sit 5 and 7 px below the surface; the surface line reads 5-7 shallow.
    assert combined["median"] == pytest.approx(-6.0)
    assert combined["abs_median"] == pytest.approx(6.0)


@pytest.mark.unit
def test_ungated_slice_is_not_flagged():
    """GIVEN a normal slice, WHEN scoring, THEN gated is False."""
    assert val.score_slice(make_slice(), [(100, 115.0)])["gated"] is False


@pytest.mark.unit
def test_score_slice_reports_operator_mean_depth():
    """GIVEN marks, WHEN scoring, THEN their mean depth below the surface is given."""
    data = make_slice(columns=(100, 101), surface_y=100.0)
    result = val.score_slice(data, [(100, 110.0), (101, 120.0)])
    assert result["operator_mean_depth"] == pytest.approx(15.0)


@pytest.mark.unit
def test_score_specimen_reports_both_scales():
    """GIVEN per-slice results, WHEN aggregating, THEN both aggregates are present.

    Per-column accuracy and the specimen mean can rank methods differently
    because a consistently signed bias does not cancel under averaging.
    """
    slices = {
        0: val.score_slice(make_slice(columns=(100,), surface_y=100.0, combined=20.0),
                           [(100, 115.0)]),
        1: val.score_slice(make_slice(columns=(100,), surface_y=100.0, combined=20.0),
                           [(100, 125.0)]),
    }
    summary = val.score_specimen(slices)
    combined = summary["methods"]["combined"]

    assert summary["n_slices"] == 2
    assert summary["n_marks"] == 2
    # Per-column: errors of +5 and -5 -> mean |median| is 5, mean signed is 0.
    assert combined["mean_abs_median"] == pytest.approx(5.0)
    assert combined["mean_median"] == pytest.approx(0.0)
    # Per-specimen: detection means 20 px, operator marks mean (15+25)/2 = 20.
    assert combined["specimen_mean_depth"] == pytest.approx(20.0)
    assert combined["specimen_error"] == pytest.approx(0.0)


@pytest.mark.unit
def test_score_specimen_exposes_signed_bias_that_survives_averaging():
    """GIVEN a consistently signed bias, WHEN aggregating, THEN specimen_error shows it."""
    slices = {
        index: val.score_slice(
            make_slice(columns=(100,), surface_y=100.0, combined=20.0),
            [(100, 110.0)])
        for index in range(3)
    }
    combined = val.score_specimen(slices)["methods"]["combined"]
    # Every slice reads 10 px too deep, so the bias does not cancel.
    assert combined["mean_median"] == pytest.approx(10.0)
    assert combined["specimen_error"] == pytest.approx(10.0)


@pytest.mark.unit
def test_score_specimen_ignores_unannotated_slices():
    """GIVEN slices with no marks, WHEN aggregating, THEN they do not dilute the score."""
    slices = {
        0: val.score_slice(make_slice(columns=(100,), surface_y=100.0, combined=20.0),
                           [(100, 115.0)]),
        1: val.score_slice(make_slice(columns=(100,)), []),
    }
    summary = val.score_specimen(slices)
    assert summary["n_slices"] == 1
    assert summary["methods"]["combined"]["mean_abs_median"] == pytest.approx(5.0)


@pytest.mark.unit
def test_score_specimen_lists_gated_slices():
    """GIVEN a gated slice, WHEN aggregating, THEN its index is reported."""
    slices = {
        0: val.score_slice(make_slice(columns=(100,)), [(100, 115.0)]),
        3: val.score_slice(make_slice(columns=(100,), method_used=val.NO_LESION_METHOD),
                           [(100, 115.0)]),
    }
    assert val.score_specimen(slices)["gated_slices"] == [3]


@pytest.mark.unit
def test_score_specimen_of_nothing_does_not_raise():
    """GIVEN no annotated slices, WHEN aggregating, THEN empty results come back."""
    summary = val.score_specimen({})
    assert summary["n_slices"] == 0
    assert summary["methods"]["combined"]["n"] == 0


@pytest.mark.unit
def test_format_error_shows_placeholder_for_missing():
    """GIVEN no data, WHEN formatting, THEN '--' is shown, never 0.0 or nan."""
    assert val.format_error(float("nan")) == "--"
    assert val.format_error(None) == "--"
    assert val.format_error(1.55) == "+1.6"
    # signed=False drops the leading '+', for columns that are already absolute.
    assert val.format_error(1.55, signed=False) == "1.6"


@pytest.mark.unit
def test_all_methods_are_readable_from_a_column():
    """Every name in METHODS must resolve to a depth, or the table shows blanks."""
    column = make_column()
    for method in val.METHODS:
        assert np.isfinite(val.method_depth(column, method))
