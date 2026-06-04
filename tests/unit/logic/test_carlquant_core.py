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
    knee_pt,
    exp2_model,
    sigmoid_model,
    fit_exp2_to_profile,
    detect_depth_sigmoid_fit,
    compute_method_stability,
    compute_stable_combined_depth,
    cluster_surface_points,
    fit_surface_curve,
    fit_lesion_depth_curve_robust,
    fit_reference_surface,
    detect_cavitation,
    find_surface_peak,
    calculate_air_threshold,
    process_slice_parallel,
    DepthDetectionMethod,
)
from app.logic.carlquant.specimen_model import RegionConfig, Surface, AirConfig


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
# compute_method_stability
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_stability_too_few_raw_points():
    info = compute_method_stability({"knee_point": [(0, 5)]}, {})
    assert info["knee_point"]["is_stable"] is False
    assert info["knee_point"]["n_points"] == 1


@pytest.mark.unit
def test_stability_few_matching_columns():
    # 3 raw points but none present in lesion_detection_data -> depth_values < 3.
    raw = {"knee_point": [(0, 5), (1, 6), (2, 7)]}
    info = compute_method_stability(raw, lesion_detection_data={})
    assert info["knee_point"]["is_stable"] is False


@pytest.mark.unit
def test_stability_stable_method():
    raw = {"knee_point": [(x, 100 + x) for x in range(5)]}
    ldd = {x: {"surface_y": x} for x in range(5)}  # relative depth constant = 100
    info = compute_method_stability(raw, ldd, stability_threshold=20.0)
    assert bool(info["knee_point"]["is_stable"]) is True
    assert info["knee_point"]["std_depth"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_stable_combined_depth
# ---------------------------------------------------------------------------

def _ldd(knee, inflection, shoulder):
    return {
        0: {
            "surface_y": 100,
            "detection_metadata": {
                "knee_depth": knee,
                "inflection_depth": inflection,
                "shoulder_depth": shoulder,
            },
        }
    }


@pytest.mark.unit
def test_combined_depth_missing_column():
    depth, method = compute_stable_combined_depth({}, {}, ascan_x=0)
    assert np.isnan(depth) and method == "none"


@pytest.mark.unit
def test_combined_depth_inflection_only():
    ldd = _ldd(knee=np.nan, inflection=40.0, shoulder=np.nan)
    stability = {
        "sigmoid_fit": {"is_stable": True, "mean_depth": 40.0, "std_depth": 1.0},
        "knee_point": {"is_stable": False},
        "sigmoid_shoulder": {"is_stable": False},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0)
    assert depth == pytest.approx(40.0)
    assert method == "inflection_only"


@pytest.mark.unit
def test_combined_depth_shape_only_weighted():
    ldd = _ldd(knee=50.0, inflection=np.nan, shoulder=60.0)
    stability = {
        "sigmoid_fit": {"is_stable": False},
        "knee_point": {"is_stable": True, "std_depth": 2.0, "mean_depth": 50.0},
        "sigmoid_shoulder": {"is_stable": True, "std_depth": 4.0, "mean_depth": 60.0},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0,
                                                  preserve_wobbliness=True)
    assert 50.0 <= depth <= 60.0
    assert "knee_point" in method


@pytest.mark.unit
def test_combined_depth_ideal_with_offset():
    ldd = _ldd(knee=50.0, inflection=40.0, shoulder=60.0)
    stability = {
        "sigmoid_fit": {"is_stable": True, "mean_depth": 40.0, "std_depth": 1.0},
        "knee_point": {"is_stable": True, "std_depth": 2.0, "mean_depth": 50.0},
        "sigmoid_shoulder": {"is_stable": True, "std_depth": 4.0, "mean_depth": 60.0},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0)
    assert "inflection_offset" in method
    assert np.isfinite(depth)


@pytest.mark.unit
def test_combined_depth_ideal_no_global_offset():
    # mean shape == inflection mean -> global_offset == 0 branch.
    ldd = _ldd(knee=50.0, inflection=50.0, shoulder=50.0)
    stability = {
        "sigmoid_fit": {"is_stable": True, "mean_depth": 50.0, "std_depth": 1.0},
        "knee_point": {"is_stable": True, "std_depth": 2.0, "mean_depth": 50.0},
        "sigmoid_shoulder": {"is_stable": True, "std_depth": 2.0, "mean_depth": 50.0},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0)
    assert depth == pytest.approx(50.0)


@pytest.mark.unit
def test_combined_depth_fallback_no_stable():
    ldd = _ldd(knee=55.0, inflection=np.nan, shoulder=np.nan)
    stability = {
        "sigmoid_fit": {"is_stable": False, "std_depth": np.inf},
        "knee_point": {"is_stable": False, "std_depth": 3.0},
        "sigmoid_shoulder": {"is_stable": False, "std_depth": np.inf},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0)
    assert depth == pytest.approx(55.0)
    assert method.startswith("fallback_")


@pytest.mark.unit
def test_combined_depth_fallback_none_available():
    ldd = _ldd(knee=np.nan, inflection=np.nan, shoulder=np.nan)
    stability = {
        "sigmoid_fit": {"is_stable": False, "std_depth": np.inf},
        "knee_point": {"is_stable": False, "std_depth": np.inf},
        "sigmoid_shoulder": {"is_stable": False, "std_depth": np.inf},
    }
    depth, method = compute_stable_combined_depth(ldd, stability, ascan_x=0)
    assert np.isnan(depth) and method == "none"


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
    curve = fit_lesion_depth_curve_robust(pts, 0, 20, outlier_threshold=0.1,
                                          curve_name="smoothed_depth")
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
    is_cav, depth = detect_cavitation(primary, reference, region,
                                      cavitation_threshold=10.0)
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
        0, str(path), None, None, num_sound=2, num_lesion=2,
    )
    assert error is None
    assert slice_idx == 0
    assert len(region_stats) == 4
    assert lesion_depth is None


@pytest.mark.unit
def test_process_slice_parallel_bad_path_returns_error():
    slice_idx, region_stats, surface, lesion_depth, error = process_slice_parallel(
        3, "does_not_exist.png", None, None, num_sound=1, num_lesion=1,
    )
    assert slice_idx == 3
    assert error is not None
    assert region_stats is None
