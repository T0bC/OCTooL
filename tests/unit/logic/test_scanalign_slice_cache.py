"""
Unit tests for app/logic/scanalign/slice_cache.py

Tests the preview/LRU slice cache on a synthetic stack without GUI dependencies.
"""

import threading

import numpy as np
import pytest
from PIL import Image

from app.logic.scanalign.slice_cache import (
    SliceCache,
    choose_preview_factor,
    preview_budget_bytes,
)

N = 20
WIDTH, HEIGHT = 64, 32
TIMEOUT = 10.0
MB = 1024 * 1024


@pytest.fixture
def stack_files(tmp_path):
    """20 slices of 64x32 where the gray value equals the slice index."""
    paths = []
    for i in range(N):
        path = tmp_path / f"slice_{i:02d}.png"
        Image.fromarray(np.full((HEIGHT, WIDTH), i, dtype=np.uint8), mode="L").save(path)
        paths.append(path)
    return paths


@pytest.fixture
def make_cache(stack_files):
    caches = []

    def factory(**kwargs):
        kwargs.setdefault("preview_factor", 2)
        cache = SliceCache(stack_files, (WIDTH, HEIGHT), **kwargs)
        caches.append(cache)
        return cache

    yield factory
    for cache in caches:
        cache.close()


class TestChoosePreviewFactor:
    """Tests for choose_preview_factor."""

    @pytest.mark.unit
    def test_minimum_factor_is_two(self):
        """GIVEN a huge budget, WHEN choosing, THEN the factor is 2."""
        assert choose_preview_factor(10, 100, 100, 10**9) == 2

    @pytest.mark.unit
    def test_factor_grows_with_stack_size(self):
        """GIVEN a real-sized stack and 256 MB, WHEN choosing, THEN the result fits the budget."""
        budget = 256 * MB
        factor = choose_preview_factor(1000, 2652, 1024, budget)
        assert factor > 2
        reduced = -(-2652 // factor) * -(-1024 // factor)
        assert 1000 * reduced <= budget
        previous = -(-2652 // (factor - 1)) * -(-1024 // (factor - 1))
        assert 1000 * previous > budget


class TestPreviewBudgetBytes:
    """Tests for preview_budget_bytes."""

    @pytest.mark.unit
    def test_none_gives_default(self):
        """GIVEN unknown RAM, WHEN computing, THEN 256 MB."""
        assert preview_budget_bytes(None) == 256 * MB

    @pytest.mark.unit
    def test_lower_clamp(self):
        """GIVEN little RAM, WHEN computing, THEN at least 128 MB."""
        assert preview_budget_bytes(0.5) == 128 * MB

    @pytest.mark.unit
    def test_upper_clamp(self):
        """GIVEN lots of RAM, WHEN computing, THEN at most 512 MB."""
        assert preview_budget_bytes(64.0) == 512 * MB

    @pytest.mark.unit
    def test_proportional_in_between(self):
        """GIVEN 3 GB available, WHEN computing, THEN 10 percent (about 307 MB)."""
        assert preview_budget_bytes(3.0) == int(0.1 * 3 * 1024**3)


class TestSliceCachePreview:
    """Tests for SliceCache preview loading."""

    @pytest.mark.unit
    def test_preview_fills_all_slices(self, make_cache):
        """GIVEN a cache, WHEN the preview finishes, THEN every slice has its gray value."""
        cache = make_cache()
        done = threading.Event()
        result = []
        progress = []

        def on_done(cancelled):
            result.append(cancelled)
            done.set()

        assert cache.get_preview(0) is None
        cache.start_preview(lambda d, t: progress.append((d, t)), on_done)
        assert done.wait(TIMEOUT)

        assert result == [False]
        assert max(progress) == (N, N)
        assert cache.preview_progress == (N, N)
        for i in range(N):
            preview = cache.get_preview(i)
            assert preview.size == (WIDTH, HEIGHT)
            assert set(np.asarray(preview).flatten()) == {i}

    @pytest.mark.unit
    def test_cancel_stops_early(self, make_cache):
        """GIVEN a single worker, WHEN cancelled after 3 slices, THEN loading stops early."""
        cache = make_cache(preview_workers=1)
        done = threading.Event()
        result = []

        def on_progress(d, t):
            if d == 3:
                cache.cancel()

        def on_done(cancelled):
            result.append(cancelled)
            done.set()

        cache.start_preview(on_progress, on_done)
        assert done.wait(TIMEOUT)

        assert result == [True]
        assert cache.get_preview(2) is not None
        assert cache.get_preview(N - 1) is None

    @pytest.mark.unit
    def test_odd_size_preview_matches_full_size(self, tmp_path):
        """GIVEN an odd-sized image, WHEN previewed, THEN it is scaled back to full size."""
        path = tmp_path / "odd.png"
        Image.fromarray(np.full((31, 65), 9, dtype=np.uint8), mode="L").save(path)
        cache = SliceCache([path], (65, 31), preview_factor=4)
        try:
            done = threading.Event()
            cache.start_preview(on_done=lambda c: done.set())
            assert done.wait(TIMEOUT)
            assert cache.get_preview(0).size == (65, 31)
        finally:
            cache.close()


class TestSliceCacheFull:
    """Tests for full-resolution access and the LRU."""

    @pytest.mark.unit
    def test_get_full_loads_and_caches(self, make_cache):
        """GIVEN an empty LRU, WHEN get_full is called, THEN it is cached afterwards."""
        cache = make_cache()
        assert cache.get_full_cached(4) is None
        img = cache.get_full(4)
        assert np.asarray(img).max() == 4
        assert cache.get_full_cached(4) is not None

    @pytest.mark.unit
    def test_lru_evicts_least_recently_used(self, make_cache):
        """GIVEN capacity 3, WHEN a 4th slice is loaded, THEN the oldest is evicted."""
        cache = make_cache(lru_capacity=3)
        for i in range(3):
            cache.get_full(i)
        cache.get_full_cached(0)  # touch 0 so 1 becomes the oldest
        cache.get_full(3)

        assert cache.get_full_cached(1) is None
        assert cache.get_full_cached(0) is not None
        assert cache.get_full_cached(2) is not None
        assert cache.get_full_cached(3) is not None

    @pytest.mark.unit
    def test_request_full_delivers_correct_slice(self, make_cache):
        """GIVEN a request, WHEN loaded, THEN the callback gets the right slice."""
        cache = make_cache()
        done = threading.Event()
        received = []

        def callback(i, img):
            received.append((i, int(np.asarray(img).max())))
            done.set()

        cache.request_full(7, callback)
        assert done.wait(TIMEOUT)
        assert received == [(7, 7)]

    @pytest.mark.unit
    def test_newer_request_supersedes_queued_ones(self, make_cache):
        """GIVEN a busy full-res worker, WHEN three requests queue up, THEN only the newest runs."""
        cache = make_cache()
        release = threading.Event()
        cache._submit_full(lambda: release.wait(TIMEOUT))  # occupy the single worker
        delivered = []
        done = threading.Event()

        def callback(i, img):
            delivered.append(i)
            if i == 9:
                done.set()

        for i in (3, 4, 9):
            cache.request_full(i, callback)
        release.set()

        assert done.wait(TIMEOUT)
        assert delivered == [9]
        assert cache.get_full_cached(3) is None

    @pytest.mark.unit
    def test_prefetch_loads_following_slices(self, make_cache):
        """GIVEN prefetch forward, WHEN it completes, THEN the next slices are cached."""
        cache = make_cache()
        cache.prefetch(5, 1, count=3)
        sentinel = threading.Event()
        cache.request_full(0, lambda i, img: sentinel.set())  # same single worker: runs after
        assert sentinel.wait(TIMEOUT)

        for i in (6, 7, 8):
            assert cache.get_full_cached(i) is not None

    @pytest.mark.unit
    def test_prefetch_backward_stays_in_range(self, make_cache):
        """GIVEN prefetch backward near 0, WHEN it completes, THEN only valid slices load."""
        cache = make_cache()
        cache.prefetch(1, -1, count=3)
        sentinel = threading.Event()
        cache.request_full(10, lambda i, img: sentinel.set())
        assert sentinel.wait(TIMEOUT)

        assert cache.get_full_cached(0) is not None


class TestSliceCacheClose:
    """Tests for SliceCache.close."""

    @pytest.mark.unit
    def test_close_is_idempotent(self, make_cache):
        """GIVEN a cache, WHEN closed twice, THEN no error and it is cancelled."""
        cache = make_cache()
        cache.close()
        cache.close()
        assert cache.is_cancelled is True

    @pytest.mark.unit
    def test_requests_after_close_are_ignored(self, make_cache):
        """GIVEN a closed cache, WHEN requesting, THEN nothing is delivered and nothing raises."""
        cache = make_cache()
        cache.close()
        called = threading.Event()
        cache.request_full(1, lambda i, img: called.set())
        cache.prefetch(1, 1)
        assert not called.wait(0.2)
