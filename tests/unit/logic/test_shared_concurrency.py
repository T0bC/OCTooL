"""
Unit tests for app/logic/shared/concurrency.py

Covers the shared worker-count policy and the Cancellable mixin.
"""

from app.logic.shared.concurrency import (
    Cancellable,
    compute_worker_count,
    detect_available_memory_gb,
)


class TestComputeWorkerCount:
    def test_defaults_to_cpu_minus_one(self):
        """GIVEN 8 CPUs and a big queue, WHEN computing, THEN 7 workers are used."""
        assert compute_worker_count(100, max_workers_cap=24, cpu_count=8) == 7

    def test_cap_limits_workers(self):
        """GIVEN 64 CPUs and cap 8, WHEN computing, THEN the cap wins."""
        assert compute_worker_count(100, max_workers_cap=8, cpu_count=64) == 8

    def test_queue_length_bounds_workers(self):
        """GIVEN 3 queued tasks, WHEN computing, THEN at most 3 workers are used."""
        assert compute_worker_count(3, max_workers_cap=24, cpu_count=16) == 3

    def test_empty_queue_does_not_bound_workers(self):
        """GIVEN queue_len 0, WHEN computing, THEN the queue bound is skipped."""
        assert compute_worker_count(0, max_workers_cap=24, cpu_count=8) == 7

    def test_requested_overrides_cpu_default(self):
        """GIVEN an explicit request, WHEN computing, THEN it replaces cpu-1."""
        assert compute_worker_count(100, 2, max_workers_cap=24, cpu_count=16) == 2

    def test_requested_is_clamped_to_cap_and_queue(self):
        """GIVEN an oversized request, WHEN computing, THEN cap and queue still apply."""
        assert compute_worker_count(100, 50, max_workers_cap=8, cpu_count=4) == 8
        assert compute_worker_count(5, 50, max_workers_cap=8, cpu_count=4) == 5

    def test_memory_caps_workers(self):
        """GIVEN 1 GiB free at 0.25 GiB/worker, WHEN computing, THEN 4 workers."""
        result = compute_worker_count(
            100,
            max_workers_cap=24,
            cpu_count=16,
            available_memory_gb=1.0,
            gb_per_worker=0.25,
        )
        assert result == 4

    def test_memory_ignored_without_gb_per_worker(self):
        """GIVEN no gb_per_worker, WHEN memory is known, THEN no memory cap applies."""
        result = compute_worker_count(
            100, max_workers_cap=24, cpu_count=16, available_memory_gb=0.1
        )
        assert result == 15

    def test_never_below_one(self):
        """GIVEN a single CPU and almost no RAM, WHEN computing, THEN result is 1."""
        assert compute_worker_count(100, max_workers_cap=24, cpu_count=1) == 1
        result = compute_worker_count(
            100,
            max_workers_cap=24,
            cpu_count=16,
            available_memory_gb=0.01,
            gb_per_worker=0.25,
        )
        assert result == 1
        assert compute_worker_count(100, 0, max_workers_cap=24, cpu_count=4) == 1

    def test_detects_cpu_count_when_not_given(self, monkeypatch):
        """GIVEN no cpu_count, WHEN computing, THEN os.cpu_count() is used."""
        monkeypatch.setattr("app.logic.shared.concurrency.os.cpu_count", lambda: 6)
        assert compute_worker_count(100, max_workers_cap=24) == 5

    def test_cpu_count_none_falls_back_to_one(self, monkeypatch):
        """GIVEN os.cpu_count() returns None, WHEN computing, THEN 1 worker."""
        monkeypatch.setattr("app.logic.shared.concurrency.os.cpu_count", lambda: None)
        assert compute_worker_count(100, max_workers_cap=24) == 1


class TestDetectAvailableMemory:
    def test_returns_positive_float_or_none(self):
        """GIVEN any platform, WHEN probing, THEN None or a positive float, never raises."""
        value = detect_available_memory_gb()
        assert value is None or (isinstance(value, float) and value > 0)


class TestCancellable:
    def test_initially_not_cancelled(self):
        """GIVEN a fresh instance, THEN is_cancelled is False."""
        assert Cancellable().is_cancelled is False

    def test_cancel_sets_flag(self):
        """GIVEN an instance, WHEN cancel is called, THEN is_cancelled is True."""
        obj = Cancellable()
        obj.cancel()
        assert obj.is_cancelled is True

    def test_reset_clears_flag(self):
        """GIVEN a cancelled instance, WHEN reset is called, THEN is_cancelled is False."""
        obj = Cancellable()
        obj.cancel()
        obj.reset()
        assert obj.is_cancelled is False

    def test_subclass_without_super_init(self):
        """GIVEN a subclass whose __init__ skips super().__init__, THEN it still works."""

        class Worker(Cancellable):
            def __init__(self):
                self.name = "w"

        worker = Worker()
        assert worker.is_cancelled is False
        worker.cancel()
        assert worker.is_cancelled is True
        worker.reset()
        assert worker.is_cancelled is False

    def test_flag_is_per_instance(self):
        """GIVEN two instances, WHEN one is cancelled, THEN the other is unaffected."""
        first, second = Cancellable(), Cancellable()
        first.cancel()
        assert second.is_cancelled is False
        assert Cancellable().is_cancelled is False
