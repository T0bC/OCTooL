#!/usr/bin/env python3
"""Unit tests for the RangeSlider helpers and widget.

The value/pixel helpers are pure functions and need no display. The widget test
creates a real Tk root and is skipped when none is available; mouse events are
simulated by calling the internal handlers with fake event objects.
"""

import tkinter as tk
from types import SimpleNamespace

import pytest

from app.view.shared.range_slider import (
    RangeSlider,
    clamp_range,
    nearest_knob,
    pixel_to_value,
    value_to_pixel,
)

# %% Pure helpers


@pytest.mark.unit
@pytest.mark.parametrize("value, expected", [(0, 10), (60, 110), (120, 210)])
def test_value_to_pixel_ends_and_middle(value, expected):
    """GIVEN a 0..120 slider on pixels 10..210, THEN ends and middle map linearly."""
    assert value_to_pixel(value, 0, 120, 10, 210) == pytest.approx(expected)


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, 1, 30, 60, 99, 120])
def test_mapping_round_trip(value):
    """GIVEN a value, THEN value -> pixel -> value returns the same integer."""
    pixel = value_to_pixel(value, 0, 120, 7, 213)
    assert pixel_to_value(pixel, 0, 120, 7, 213) == value


@pytest.mark.unit
def test_pixel_to_value_clamps_outside_track():
    """GIVEN x beyond the track, THEN the value is clamped to the bounds."""
    assert pixel_to_value(-50, 0, 120, 10, 210) == 0
    assert pixel_to_value(999, 0, 120, 10, 210) == 120


@pytest.mark.unit
def test_pixel_to_value_returns_rounded_int():
    """GIVEN x between two values, THEN the nearest integer is returned."""
    result = pixel_to_value(10 + 200 * 30.4 / 120, 0, 120, 10, 210)
    assert result == 30
    assert isinstance(result, int)


@pytest.mark.unit
def test_clamp_range_clamps_to_bounds():
    """GIVEN values outside the bounds, THEN both are clamped."""
    assert clamp_range(-10, 500, 0, 120) == (0, 120)


@pytest.mark.unit
def test_clamp_range_fixes_low_above_high():
    """GIVEN low > high, THEN the pair is ordered."""
    assert clamp_range(90, 30, 0, 120) == (30, 90)


@pytest.mark.unit
def test_clamp_range_allows_equal_values():
    """GIVEN equal values, THEN they are kept (no minimum gap)."""
    assert clamp_range(50, 50, 0, 120) == (50, 50)


@pytest.mark.unit
def test_nearest_knob_picks_closer_knob():
    """GIVEN separate knobs, THEN the closer one is grabbed."""
    assert nearest_knob(40, 50, 150) == "low"
    assert nearest_knob(140, 50, 150) == "high"
    assert nearest_knob(100, 50, 150) == "low"  # exact tie goes to low


@pytest.mark.unit
def test_nearest_knob_overlap_left_and_right():
    """GIVEN overlapping knobs, THEN left click grabs low, right/on grabs high."""
    assert nearest_knob(80, 100, 100) == "low"
    assert nearest_knob(120, 100, 100) == "high"
    assert nearest_knob(100, 100, 100) == "high"


@pytest.mark.unit
def test_nearest_knob_overlap_at_ends():
    """GIVEN both knobs at one end, THEN the knob that can still move is grabbed."""
    assert nearest_knob(200, 200, 200, x_min=10, x_max=200) == "low"
    assert nearest_knob(10, 10, 10, x_min=10, x_max=200) == "high"


# %% Widget


@pytest.fixture(scope="module")
def tk_root():
    """One shared Tk root per module (creating many roots on Windows is flaky)."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def slider_env(tk_root):
    """Yield (root, slider, calls) with a fresh slider per test."""
    calls = []
    slider = RangeSlider(
        tk_root, from_=0, to=120, low=30, high=100, command=lambda lo, hi: calls.append((lo, hi))
    )
    yield tk_root, slider, calls
    slider.destroy()


def _x_for(slider, value):
    return value_to_pixel(value, slider.from_, slider.to, slider._x_min, slider._x_max)


@pytest.mark.unit
def test_widget_set_and_get_clamp(slider_env):
    """GIVEN out-of-range and reversed values, THEN get() returns the clamped pair."""
    _, slider, _ = slider_env
    assert slider.get() == (30, 100)
    slider.set(-5, 500)
    assert slider.get() == (0, 120)
    slider.set(90, 20)
    assert slider.get() == (20, 90)


@pytest.mark.unit
def test_widget_set_does_not_fire_command(slider_env):
    """GIVEN a command, THEN set() never calls it."""
    _, slider, calls = slider_env
    slider.set(10, 80)
    assert calls == []


@pytest.mark.unit
def test_widget_command_fires_only_on_integer_change(slider_env):
    """GIVEN a drag, THEN the command fires per integer step, not per pixel."""
    _, slider, calls = slider_env
    x_start = _x_for(slider, 30)
    slider._on_press(SimpleNamespace(x=x_start))
    assert calls == []  # pressing exactly on the knob changes nothing

    slider._on_drag(SimpleNamespace(x=x_start + 0.1))  # sub-value motion
    assert calls == []

    slider._on_drag(SimpleNamespace(x=_x_for(slider, 40)))
    slider._on_drag(SimpleNamespace(x=_x_for(slider, 40) + 0.1))
    assert calls == [(40, 100)]

    slider._on_release(SimpleNamespace(x=_x_for(slider, 40)))
    slider._on_drag(SimpleNamespace(x=_x_for(slider, 50)))  # ignored after release
    assert calls == [(40, 100)]
    assert slider.get() == (40, 100)


@pytest.mark.unit
def test_widget_knob_cannot_cross_other_knob(slider_env):
    """GIVEN the low knob dragged past the high knob, THEN it stops at the high value."""
    _, slider, calls = slider_env
    slider._on_press(SimpleNamespace(x=_x_for(slider, 30)))
    slider._on_drag(SimpleNamespace(x=_x_for(slider, 115)))
    assert slider.get() == (100, 100)
    assert calls[-1] == (100, 100)


@pytest.mark.unit
def test_widget_off_centre_press_on_knob_does_not_jump(slider_env):
    """GIVEN a press slightly beside a knob's centre, THEN the knob keeps its value."""
    _, slider, calls = slider_env
    slider._on_press(SimpleNamespace(x=_x_for(slider, 30) + slider._radius / 2))
    assert slider.get() == (30, 100)
    assert calls == []


@pytest.mark.unit
@pytest.mark.parametrize(("target", "expected"), [(40, (40, 60)), (80, (60, 80))])
def test_widget_overlapping_knobs_follow_drag_direction(slider_env, target, expected):
    """GIVEN overlapping knobs in the middle, THEN the first drag direction picks the knob."""
    _, slider, _ = slider_env
    slider.set(60, 60)
    slider._on_press(SimpleNamespace(x=_x_for(slider, 60)))
    slider._on_drag(SimpleNamespace(x=_x_for(slider, target)))
    assert slider.get() == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("start", "click_value", "expected"),
    [
        ((10, 80), 10, (30, 80)),  # low knob -> low default, high untouched
        ((10, 80), 80, (10, 100)),  # high knob -> high default, low untouched
        ((5, 20), 5, (30, 100)),  # low default would cross high -> both reset
        ((110, 115), 115, (30, 100)),  # high default would cross low -> both reset
        ((60, 60), 60, (30, 100)),  # overlapping knobs -> both reset
    ],
)
def test_widget_double_click_resets_knob(slider_env, start, click_value, expected):
    """GIVEN a double-click on a knob, THEN it returns to its initial value."""
    _, slider, calls = slider_env
    slider.set(*start)
    slider._on_double_click(SimpleNamespace(x=_x_for(slider, click_value)))
    assert slider.get() == expected
    assert calls == [expected]


@pytest.mark.unit
def test_widget_double_click_on_track_does_nothing(slider_env):
    """GIVEN a double-click away from both knobs, THEN nothing is reset."""
    _, slider, calls = slider_env
    slider.set(10, 80)
    slider._on_double_click(SimpleNamespace(x=_x_for(slider, 45)))
    assert slider.get() == (10, 80)
    assert calls == []


@pytest.mark.unit
def test_widget_knobs_have_distinct_images(slider_env):
    """GIVEN the two knobs, THEN each is drawn with its own (differently bordered) image."""
    _, slider, _ = slider_env
    images = {slider.itemcget(item, "image") for item in slider.find_withtag("knob")}
    assert len(images) == 2
