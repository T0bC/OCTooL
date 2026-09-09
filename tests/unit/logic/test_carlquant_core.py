"""
Unit tests for app/logic/carlquant/carl_quant_core.py numeric helpers.

Focuses on the pure fitting/detection helpers and their guarded fallback
branches using small synthetic profiles (no real instrument data, no GUI).
"""

import numpy as np
import pytest
from PIL import Image

from app.logic.carlquant import carl_quant_core as core
from app.logic.carlquant.carl_quant_core import (
    NO_LESION_METHOD,
    DepthDetectionMethod,
    calculate_air_threshold,
    cluster_surface_points,
    compute_stable_combined_depth,
    detect_cavitation,
    detect_depth_sigmoid_fit,
    exp2_model,
    find_surface_peak,
    fit_exp2_to_profile,
    fit_lesion_depth_curve_robust,
    fit_reference_surface,
    fit_surface_curve,
    is_method_stable,
    knee_pt,
    process_slice_parallel,
    sigmoid_model,
)
from app.logic.carlquant.specimen_model import AirConfig, RegionConfig, Surface

# ---------------------------------------------------------------------------
# Simple math models
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_exp2_model():
    z = np.array([0.0, 1.0])
    out = exp2_model(z, 1.0, -0.1, 2.0, -0.2)
    assert out[0] == pytest.approx(3.0)


@pytest.mark.unit
def test_sigmoid_model_monotonic_decay():
    z = np.arange(0, 10)
    out = sigmoid_model(z, 0.0, 10.0, 1.0, 5.0)
    assert out[0] > out[-1]


# ---------------------------------------------------------------------------
# knee_pt
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_knee_pt_too_few_points():
    res_x, idx = knee_pt([1, 2], [0, 1])
    assert np.isnan(res_x) and idx == -1


@pytest.mark.unit
def test_knee_pt_finds_bend():
    x = np.arange(20)
    # Sharp knee: flat then rising.
    y = np.concatenate([np.zeros(10), np.arange(10) * 5.0])
    res_x, idx = knee_pt(y, x)
    assert idx > 0
    assert 0 <= res_x <= 19


# ---------------------------------------------------------------------------
# fit_exp2_to_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fit_exp2_success():
    depth = np.arange(60, dtype=float)
    profile = 200 * np.exp(-depth / 20.0) + 20
    result = fit_exp2_to_profile(profile, depth)
    assert result is not None
    _, params = result
    assert params["success"] is True


@pytest.mark.unit
def test_fit_exp2_failure_returns_none():
    # Empty profile -> np.max raises -> caught -> None.
    assert fit_exp2_to_profile(np.array([]), np.array([])) is None


# ---------------------------------------------------------------------------
# detect_depth_sigmoid_fit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sigmoid_fit_insufficient_data():
    depth, idx, meta = detect_depth_sigmoid_fit(np.array([1, 2, 3]), np.array([0, 1, 2]))
    assert np.isnan(depth) and idx == -1
    assert meta["success"] is False


@pytest.mark.unit
def test_sigmoid_fit_success():
    depth_indices = np.arange(60, dtype=float)
    profile = sigmoid_model(depth_indices, 20.0, 200.0, 0.3, 30.0)
    depth, idx, meta = detect_depth_sigmoid_fit(profile, depth_indices)
    assert meta["success"] is True
    assert idx >= 0


# ---------------------------------------------------------------------------
# is_method_stable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_stability_needs_at_least_three_columns():
    # Two points always look perfectly consistent; that is not a trace.
    assert is_method_stable({0: 40.0, 1: 40.0}) is False


@pytest.mark.unit
def test_stability_flat_trace_is_stable():
    assert is_method_stable({x: 40.0 for x in range(5)}) is True


@pytest.mark.unit
def test_stability_scattered_trace_is_not():
    scattered = {x: 40.0 + (40.0 if x % 2 else -40.0) for x in range(5)}
    assert is_method_stable(scattered) is False


@pytest.mark.unit
def test_stability_threshold_is_the_boundary():
    # SD of [-6, +6] alternating is exactly 6.0.
    trace = {x: 40.0 + (6.0 if x % 2 else -6.0) for x in range(4)}
    assert is_method_stable(trace, stability_sd=6.0) is True
    assert is_method_stable(trace, stability_sd=5.9) is False


# ---------------------------------------------------------------------------
# compute_stable_combined_depth
# ---------------------------------------------------------------------------


def _ldd(knee, inflection, shoulder, half_span=np.nan, n_columns=5):
    """A slice whose every column carries the same depths.

    Constant depths mean SD is 0, so every method counts as stable unless a
    test deliberately adds scatter. The cascade judges stability across
    columns, so a single-column fixture cannot exercise it.
    """
    return {
        x: {
            "surface_y": 100,
            "detection_metadata": {
                "knee_depth": knee,
                "inflection_depth": inflection,
                "shoulder_depth": shoulder,
                "half_span_depth": half_span,
            },
        }
        for x in range(n_columns)
    }


def _ldd_scattered(method_key, spread, n_columns=5, **fixed):
    """A slice where one method wobbles laterally and the rest hold steady."""
    ldd = _ldd(knee=np.nan, inflection=np.nan, shoulder=np.nan, n_columns=n_columns)
    for i, x in enumerate(sorted(ldd)):
        metadata = ldd[x]["detection_metadata"]
        metadata.update(fixed)
        metadata[method_key] = 40.0 + (spread if i % 2 else -spread)
    return ldd


@pytest.mark.unit
def test_combined_depth_missing_column():
    depth, method = compute_stable_combined_depth({}, ascan_x=0)
    assert np.isnan(depth) and method == "none"


@pytest.mark.unit
def test_half_span_wins_when_stable():
    # Half-span is the primary measure: stable means it is used alone, not
    # averaged with terms that are biased deep (knee) and shallow (inflection).
    ldd = _ldd(knee=60.0, inflection=20.0, shoulder=90.0, half_span=40.0)
    depth, method = compute_stable_combined_depth(ldd, ascan_x=0)
    assert depth == pytest.approx(40.0)
    assert method == "half_span"


@pytest.mark.unit
def test_shoulder_never_contributes():
    # The shoulder is deliberately not a term; a wild value must not move it.
    base, _ = compute_stable_combined_depth(
        _ldd(knee=60.0, inflection=20.0, shoulder=90.0, half_span=40.0), ascan_x=0
    )
    wild, _ = compute_stable_combined_depth(
        _ldd(knee=60.0, inflection=20.0, shoulder=9000.0, half_span=40.0), ascan_x=0
    )
    assert base == pytest.approx(wild)


@pytest.mark.unit
def test_unstable_half_span_falls_back_to_mean_of_two():
    # Knee reads deep and inflection shallow, so their mean cancels the two
    # biases -- the only case where terms are averaged.
    ldd = _ldd_scattered("half_span_depth", spread=40.0, knee_depth=60.0, inflection_depth=20.0)
    depth, method = compute_stable_combined_depth(ldd, ascan_x=0)
    assert depth == pytest.approx(40.0)
    assert method == "mean+knee_point+sigmoid_fit"


@pytest.mark.unit
def test_falls_through_to_knee_when_inflection_also_unstable():
    ldd = _ldd_scattered("half_span_depth", spread=40.0, knee_depth=55.0)
    for i, x in enumerate(sorted(ldd)):
        ldd[x]["detection_metadata"]["inflection_depth"] = 10.0 + (40.0 if i % 2 else -40.0)
    depth, method = compute_stable_combined_depth(ldd, ascan_x=0)
    assert depth == pytest.approx(55.0)
    assert method == "knee_point"


@pytest.mark.unit
def test_inflection_alone_is_the_last_resort():
    # Biased shallow by design, but a biased depth beats reporting none.
    ldd = _ldd_scattered("half_span_depth", spread=40.0, inflection_depth=18.0)
    for i, x in enumerate(sorted(ldd)):
        ldd[x]["detection_metadata"]["knee_depth"] = 70.0 + (40.0 if i % 2 else -40.0)
    depth, method = compute_stable_combined_depth(ldd, ascan_x=0)
    assert depth == pytest.approx(18.0)
    assert method == "sigmoid_fit"


@pytest.mark.unit
def test_no_method_stable_reports_no_lesion():
    ldd = _ldd(knee=np.nan, inflection=np.nan, shoulder=np.nan)
    depth, method = compute_stable_combined_depth(ldd, ascan_x=0)
    assert np.isnan(depth) and method == NO_LESION_METHOD


@pytest.mark.unit
def test_a_wild_half_span_column_no_longer_hides_behind_the_median():
    # Under the old median-of-three a single 999 px column was absorbed by the
    # other terms. The cascade instead rejects half-span for the whole slice,
    # which is the point: one bad column means the trace is not a boundary.
    ldd = _ldd(knee=50.0, inflection=48.0, shoulder=np.nan, half_span=52.0)
    ldd[0]["detection_metadata"]["half_span_depth"] = 999.0
    _, method = compute_stable_combined_depth(ldd, ascan_x=1)
    assert method != "half_span"


@pytest.mark.unit
@pytest.mark.parametrize("offset", [-5.0, 0.0, 5.0])
def test_combined_depth_offset_shifts_one_to_one(offset):
    ldd = _ldd(knee=60.0, inflection=20.0, shoulder=np.nan, half_span=40.0)
    depth, _ = compute_stable_combined_depth(ldd, ascan_x=0, depth_offset=offset)
    assert depth == pytest.approx(40.0 + offset)


# ---------------------------------------------------------------------------
# Half-span crossing
# ---------------------------------------------------------------------------


def _step_profile(edge=50, high=200.0, low=60.0, length=200):
    """Bright plateau, linear decay, then background."""
    decay = np.linspace(high, low, 20)
    return np.concatenate([np.full(edge, high), decay, np.full(length - edge - decay.size, low)])


@pytest.mark.unit
def test_half_span_finds_the_crossing():
    depth, meta = core.detect_depth_half_span(_step_profile(edge=50))
    assert meta["success"]
    assert 50 <= depth <= 75  # within the decay, not before it
    assert meta["span"] == pytest.approx(140.0, abs=5.0)


@pytest.mark.unit
def test_half_span_tracks_edge_position():
    shallow, _ = core.detect_depth_half_span(_step_profile(edge=30))
    deep, _ = core.detect_depth_half_span(_step_profile(edge=80))
    assert deep > shallow + 40


@pytest.mark.unit
def test_half_span_flat_profile_has_no_contrast():
    depth, meta = core.detect_depth_half_span(np.full(200, 100.0))
    assert np.isnan(depth)
    assert meta["reason"] == "no_contrast"


@pytest.mark.unit
def test_half_span_empty_profile():
    depth, meta = core.detect_depth_half_span(np.array([]))
    assert np.isnan(depth) and not meta["success"]


@pytest.mark.unit
def test_half_span_ignores_single_speckle_dip():
    # One deep spike must not satisfy the sustained-crossing requirement.
    clean = _step_profile(edge=80)
    spiked = clean.copy()
    spiked[20] = 0.0
    depth_clean, _ = core.detect_depth_half_span(clean)
    depth_spiked, _ = core.detect_depth_half_span(spiked)
    assert depth_spiked == pytest.approx(depth_clean, abs=6.0)
    assert depth_spiked > 40


@pytest.mark.unit
def test_half_span_fraction_falls_with_contrast():
    assert core.half_span_fraction(core.HALF_SPAN_REFERENCE_SPAN) == pytest.approx(
        core.HALF_SPAN_BASE_FRACTION
    )
    assert core.half_span_fraction(200.0) < core.HALF_SPAN_BASE_FRACTION
    assert core.half_span_fraction(20.0) > core.HALF_SPAN_BASE_FRACTION


@pytest.mark.unit
def test_half_span_fraction_is_clipped():
    low, high = core.HALF_SPAN_FRACTION_LIMITS
    assert core.half_span_fraction(1e6) == pytest.approx(low)
    assert core.half_span_fraction(-1e6) == pytest.approx(high)


@pytest.mark.unit
def test_half_span_higher_fraction_reads_shallower():
    # The documented tuning direction of HALF_SPAN_BASE_FRACTION.
    profile = _step_profile(edge=60)
    shallow, _ = core.detect_depth_half_span(profile, fraction=0.70)
    deep, _ = core.detect_depth_half_span(profile, fraction=0.30)
    assert shallow < deep


# ---------------------------------------------------------------------------
# No-lesion gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_lesion_gate_quiet_on_smooth_boundary():
    # A real boundary is laterally smooth.
    assert not core.is_no_lesion_slice([50.0 + 0.5 * i % 3 for i in range(100)])


@pytest.mark.unit
def test_no_lesion_gate_fires_on_scatter():
    rng = np.random.default_rng(0)
    assert core.is_no_lesion_slice(rng.normal(50.0, 30.0, 200).tolist())


@pytest.mark.unit
def test_no_lesion_gate_threshold_is_the_boundary():
    values = [0.0, 20.0] * 50  # SD == 10
    assert not core.is_no_lesion_slice(values, no_lesion_sd=15.0)
    assert core.is_no_lesion_slice(values, no_lesion_sd=5.0)


@pytest.mark.unit
def test_no_lesion_gate_ignores_nan_and_empty():
    assert not core.is_no_lesion_slice([])
    assert not core.is_no_lesion_slice([np.nan, np.nan])
    assert not core.is_no_lesion_slice([50.0, np.nan, 50.5])


@pytest.mark.unit
def test_no_lesion_gate_quiet_on_perfectly_flat_boundary():
    # SD is exactly 0; a flat boundary is the clearest possible lesion end.
    assert not core.is_no_lesion_slice([50.0] * 50, no_lesion_sd=0.0)


# ---------------------------------------------------------------------------
# cluster_surface_points
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cluster_surface_points_empty():
    pts, labels = cluster_surface_points([])
    assert pts == [] and labels is None


@pytest.mark.unit
def test_cluster_surface_points_dense_cluster():
    pts = [(x, 100) for x in range(200)]
    filtered, labels = cluster_surface_points(pts, min_cluster_size=10)
    assert len(filtered) > 0
    assert labels is not None


# ---------------------------------------------------------------------------
# fit_surface_curve / fit_lesion_depth_curve_robust / fit_reference_surface
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fit_surface_curve_too_few_points():
    assert fit_surface_curve([(0, 0), (1, 1)], 0, 10) == {}


@pytest.mark.unit
def test_fit_surface_curve_success():
    pts = [(x, 100 + (x % 3)) for x in range(50)]
    curve = fit_surface_curve(pts, 0, 50)
    assert "actual_surface" in curve
    assert len(curve["actual_surface"]) == 50


@pytest.mark.unit
def test_fit_lesion_depth_curve_too_few():
    assert fit_lesion_depth_curve_robust([(0, 0), (1, 1)], 0, 10) == {}


@pytest.mark.unit
def test_fit_lesion_depth_curve_with_spike():
    pts = [(x, 120) for x in range(40)]
    pts[20] = (20, 250)  # spike that median filtering should suppress
    curve = fit_lesion_depth_curve_robust(pts, 0, 40, curve_name="smoothed_depth")
    assert "smoothed_depth" in curve


@pytest.mark.unit
def test_fit_lesion_depth_curve_all_outliers_fallback():
    # Alternating values create large residuals -> inlier_mask may drop below 4,
    # exercising the median-filtered fallback branch.
    pts = [(x, 100 if x % 2 == 0 else 200) for x in range(20)]
    curve = fit_lesion_depth_curve_robust(
        pts, 0, 20, outlier_threshold=0.1, curve_name="smoothed_depth"
    )
    assert isinstance(curve, dict)


@pytest.mark.unit
def test_fit_reference_surface_no_region():
    assert fit_reference_surface([(0, 0)] * 10, None, 0, 10) == {}


@pytest.mark.unit
def test_fit_reference_surface_success():
    region = RegionConfig(
        slice_index=0,
        specimen_start=(0, 100),
        lesion_start=(20, 100),
        lesion_end=(30, 100),
        tooth_end=(50, 100),
    )
    pts = [(x, 100) for x in range(50)]
    curve = fit_reference_surface(pts, region, 0, 50)
    assert "interpolated_surface" in curve


# ---------------------------------------------------------------------------
# detect_cavitation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detect_cavitation_empty_inputs():
    assert detect_cavitation([], [], None) == (False, 0.0)


@pytest.mark.unit
def test_detect_cavitation_detected():
    region = RegionConfig(
        slice_index=0,
        specimen_start=(0, 100),
        lesion_start=(10, 100),
        lesion_end=(40, 100),
        tooth_end=(50, 100),
    )
    # Primary surface dips well below reference across the lesion span.
    primary = [(x, 150) for x in range(60)]
    reference = [(x, 100) for x in range(60)]
    is_cav, depth = detect_cavitation(primary, reference, region, cavitation_threshold=10.0)
    assert is_cav is True
    assert depth == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# find_surface_peak / calculate_air_threshold
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_find_surface_peak_empty_region():
    col = np.zeros(10)
    assert find_surface_peak(col, threshold_idx=15) == 15


@pytest.mark.unit
def test_find_surface_peak_locates_peak():
    col = np.zeros(50)
    col[20] = 250  # clear peak
    idx = find_surface_peak(col, threshold_idx=0)
    assert 0 <= idx < 50


@pytest.mark.unit
def test_calculate_air_threshold_without_config():
    img = np.full((20, 20), 100, dtype=np.uint8)
    thr = calculate_air_threshold(img, None)
    assert thr == pytest.approx(100.0)


@pytest.mark.unit
def test_calculate_air_threshold_with_region():
    img = np.full((20, 20), 50, dtype=np.uint8)
    air = AirConfig(slice_index=0, point1=(0, 0), point2=(10, 10))
    thr = calculate_air_threshold(img, air)
    assert thr == pytest.approx(50 * 1.6)


# ---------------------------------------------------------------------------
# process_slice_parallel (module-level worker)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_process_slice_parallel_no_region(tmp_path):
    img = np.full((128, 128), 10, dtype=np.uint8)
    img[60:65, :] = 220
    path = tmp_path / "slice_0.png"
    Image.fromarray(img, mode="L").save(path)

    slice_idx, region_stats, surface, lesion_depth, error = process_slice_parallel(
        0,
        str(path),
        None,
        None,
        num_sound=2,
        num_lesion=2,
    )
    assert error is None
    assert slice_idx == 0
    assert len(region_stats) == 4
    assert lesion_depth is None


@pytest.mark.unit
def test_process_slice_parallel_bad_path_returns_error():
    slice_idx, region_stats, surface, lesion_depth, error = process_slice_parallel(
        3,
        "does_not_exist.png",
        None,
        None,
        num_sound=1,
        num_lesion=1,
    )
    assert slice_idx == 3
    assert error is not None
    assert region_stats is None


# ---------------------------------------------------------------------------
# calculate_lesion_depth end to end (synthetic images)
# ---------------------------------------------------------------------------


def _synthetic_slice(lesion_thickness=40, width=160, height=220, noise=0.0, seed=0):
    """Bright surface, a bright lesion band, then darker sound enamel."""
    rng = np.random.default_rng(seed)
    surface_y = 40
    img = np.full((height, width), 30.0)
    img[surface_y : surface_y + 3, :] = 255.0
    img[surface_y + 3 : surface_y + 3 + lesion_thickness, :] = 200.0
    img[surface_y + 3 + lesion_thickness :, :] = 60.0
    if noise:
        img += rng.normal(0.0, noise, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)

    surface = Surface(
        raw_points=[(x, surface_y) for x in range(width)],
        fitted_curves={"actual_surface": [(x, surface_y) for x in range(width)]},
    )
    region = RegionConfig(
        slice_index=0,
        specimen_start=(0, surface_y),
        lesion_start=(20, surface_y),
        lesion_end=(width - 20, surface_y),
        tooth_end=(width - 1, surface_y),
        buffer_pixels=0,
    )
    return img, surface, region


@pytest.mark.unit
def test_calculate_lesion_depth_emits_half_span_metadata():
    img, surface, region = _synthetic_slice()
    result = core.calculate_lesion_depth(
        surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    assert result is not None
    meta = next(iter(result.lesion_detection_data.values()))["detection_metadata"]
    # shoulder_depth is still emitted: renderers and stored configs read it.
    for key in ("half_span_depth", "knee_depth", "inflection_depth", "shoulder_depth"):
        assert key in meta
    assert meta["depth_method_used"] == "half_span"


@pytest.mark.unit
def test_method_choice_defaults_to_the_tight_threshold():
    """The cascade's default must be METHOD_STABILITY_SD, not something looser.

    A half-span trace scattered well past 12 px was once accepted because the
    choice was wired to a 20.0 reporting threshold, which reported a lesion
    depth on a slice that has none.
    """
    ldd = _ldd_scattered("half_span_depth", spread=40.0, knee_depth=55.0)
    assert core.select_depth_method(ldd)[0] == "knee_point"
    assert core.METHOD_STABILITY_SD == 12.0
    # Loosening it far enough does accept half-span -- so the default is what
    # keeps that trace out, not some other property of the fixture.
    assert core.select_depth_method(ldd, stability_sd=100.0)[0] == "half_span"


@pytest.mark.unit
def test_half_span_construction_terms_are_stored():
    """Every term the crossing is built from survives into the config.

    The A-Scan viewer draws these to explain the method, and a saved result
    has to stay auditable without re-running the analysis.
    """
    img, surface, region = _synthetic_slice()
    result = core.calculate_lesion_depth(
        surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    assert result is not None
    meta = next(iter(result.lesion_detection_data.values()))["detection_metadata"]
    for key in (
        "half_span_background",
        "half_span_peak",
        "half_span_threshold",
        "half_span_smooth_window",
    ):
        assert key in meta, key
    # The threshold has to sit between the two levels that define it.
    assert meta["half_span_background"] <= meta["half_span_threshold"] <= meta["half_span_peak"]


@pytest.mark.unit
def test_stored_threshold_matches_background_plus_fraction_of_span():
    # Guards the stored terms actually describing the reported depth, rather
    # than being recorded from some other pass over the profile.
    img, surface, region = _synthetic_slice()
    result = core.calculate_lesion_depth(
        surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    meta = next(iter(result.lesion_detection_data.values()))["detection_metadata"]
    expected = meta["half_span_background"] + meta["half_span_fraction"] * meta["half_span_span"]
    assert meta["half_span_threshold"] == pytest.approx(expected)


@pytest.mark.unit
def test_boxcar_preserves_length_and_is_public():
    # The A-Scan viewer redraws the smoothed profile with this exact function,
    # so it has to stay importable and length-preserving.
    profile = np.linspace(200.0, 20.0, 60)
    smoothed = core.boxcar(profile, 9)
    assert smoothed.shape == profile.shape


@pytest.mark.unit
def test_calculate_lesion_depth_tracks_lesion_thickness():
    def depth_for(thickness):
        img, surface, region = _synthetic_slice(lesion_thickness=thickness)
        return core.calculate_lesion_depth(
            surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
        )

    thin, thick = depth_for(25), depth_for(70)
    assert thin is not None and thick is not None
    assert thick.mean_depth > thin.mean_depth


@pytest.mark.unit
def test_calculate_lesion_depth_offset_shifts_result():
    img, surface, region = _synthetic_slice()
    base = core.calculate_lesion_depth(
        surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    shifted = core.calculate_lesion_depth(
        surface, region, img, depth_offset=10.0, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    assert base is not None and shifted is not None
    # Offset is applied before the refractive-index division.
    expected = 10.0 / core.TOOTH_REFRACTIVE_INDEX
    assert shifted.mean_depth - base.mean_depth == pytest.approx(expected, abs=0.5)


@pytest.mark.unit
def test_calculate_lesion_depth_no_lesion_gate_reports_surface():
    # Structureless noise -> the combined depth scatters -> gate fires.
    rng = np.random.default_rng(3)
    width, height, surface_y = 160, 220, 40
    img = np.clip(rng.normal(120.0, 45.0, (height, width)), 0, 255)
    img[surface_y : surface_y + 3, :] = 255.0
    img = img.astype(np.uint8)
    surface = Surface(
        raw_points=[(x, surface_y) for x in range(width)],
        fitted_curves={"actual_surface": [(x, surface_y) for x in range(width)]},
    )
    region = RegionConfig(
        slice_index=0,
        specimen_start=(0, surface_y),
        lesion_start=(20, surface_y),
        lesion_end=(width - 20, surface_y),
        tooth_end=(width - 1, surface_y),
        buffer_pixels=0,
    )
    result = core.calculate_lesion_depth(
        surface,
        region,
        img,
        no_lesion_sd=1.0,  # force the gate
        detection_method=DepthDetectionMethod.COMBINED_MEAN,
    )
    assert result is not None
    assert result.mean_depth == pytest.approx(0.0)
    meta = next(iter(result.lesion_detection_data.values()))["detection_metadata"]
    assert meta["depth_method_used"] == "no_lesion_surface"


@pytest.mark.unit
def test_calculate_lesion_depth_gate_quiet_on_clean_lesion():
    img, surface, region = _synthetic_slice(noise=6.0)
    result = core.calculate_lesion_depth(
        surface, region, img, detection_method=DepthDetectionMethod.COMBINED_MEAN
    )
    assert result is not None
    meta = next(iter(result.lesion_detection_data.values()))["detection_metadata"]
    assert meta["depth_method_used"] != "no_lesion_surface"
    assert result.mean_depth > 0.0
