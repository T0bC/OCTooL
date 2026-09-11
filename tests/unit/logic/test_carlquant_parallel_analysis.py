"""
Unit tests for app/logic/carlquant/parallel_analysis.py.

Exercises BatchSliceCoordinator: the flat, batch-wide slice queue, result
attribution back to the right specimen, per-specimen eager save/memory-release,
cooperative cancellation (including tasks that were never even submitted when
cancellation hit), the CPU/RAM/queue worker-count policy, sequential vs.
parallel mode selection, and per-slice error isolation. The executor, the
worker function and the data saver are all injected fakes, so nothing here
spawns a real process or touches Excel/disk.

Two fake executors are used:
- ImmediateExecutor: submit() runs synchronously; good enough whenever a test
  does not care about completion order (real ``concurrent.futures.wait`` on
  already-done futures returns them all immediately, so this composes fine
  with the sliding-window submission in ``_run_parallel``).
- ScriptedExecutor (+ scripted_wait): futures resolve lazily -- submit() only
  attaches the job to the Future and leaves it PENDING -- and a monkeypatched
  ``parallel_analysis.wait`` resolves exactly one still-pending future per
  call, whichever the test says should go next. This is what makes result
  attribution under interleaving, save-overlap and cancellation deterministic:
  the real ``wait``/``as_completed`` give no control over "which one finishes
  next", and letting everything resolve synchronously inside submit() would
  leave nothing genuinely pending for a mid-batch cancel() to act on.
"""

import re
from concurrent.futures import Future
from pathlib import Path

import pytest

from app.logic.carlquant import parallel_analysis as pa
from app.logic.carlquant.models import Specimen
from app.logic.carlquant.parallel_analysis import (
    BatchSliceCoordinator,
    detect_available_memory_gb,
)

# ----------------------------------------------------------------------
# Specimen / worker fakes
# ----------------------------------------------------------------------


def _make_specimen(key: int, n_slices: int, specimen_id: str | None = None) -> Specimen:
    """Create a lightweight Specimen with fake image paths, no files on disk.

    worker_fn is faked too, so nothing ever reads these paths. Each image path
    encodes (key, slice_index) so a fake worker can report exactly which
    specimen/slice it was asked to process, making cross-specimen mix-ups
    detectable. ``batch_key`` is stamped on for test bookkeeping only (it is
    not a real Specimen field) so assertions can tell apart specimens that
    intentionally share a specimen_id.
    """
    specimen = Specimen(
        specimen_id=specimen_id or f"SPEC{key}",
        source=Path(f"batch{key}"),
        images=[Path(f"batch{key}_slice{i}.png") for i in range(n_slices)],
        slices=n_slices,
        status="Pending",
        date=0.0,
    )
    specimen.batch_key = key
    return specimen


def _marker_worker(
    slice_idx, image_path, region_config, air_config, num_sound, num_lesion, detection_method
):
    """Fake worker_fn: always succeeds, echoing the image path name as the
    "region_stats" payload so a test can decode which (key, slice) it was."""
    return (slice_idx, image_path.name, None, None, "")


_MARKER_RE = re.compile(r"batch(\d+)_slice(\d+)\.png")


def _parse_marker(name: str) -> tuple[int, int]:
    match = _MARKER_RE.fullmatch(name)
    assert match, f"unexpected marker: {name!r}"
    return int(match.group(1)), int(match.group(2))


def _error_prone_worker(
    slice_idx, image_path, region_config, air_config, num_sound, num_lesion, detection_method
):
    """Fake worker_fn: slice 1 reports an error field, slice 2 raises, rest succeed."""
    if slice_idx == 1:
        return (slice_idx, None, None, None, "synthetic region error")
    if slice_idx == 2:
        raise RuntimeError("synthetic worker crash")
    return (slice_idx, image_path.name, None, None, "")


# ----------------------------------------------------------------------
# Fake data saver
# ----------------------------------------------------------------------


class _FakeDataSaver:
    """Duck-typed stand-in for DataSaver: records calls instead of touching
    Excel/disk. ``call_log`` interleaves store/save calls in call order (keyed
    by each specimen's ``batch_key``) so tests can assert on ordering."""

    def __init__(self):
        self.store_calls: list[tuple] = []
        self.save_results_calls: list = []
        self.save_annotated_calls: list = []
        self.call_log: list[tuple] = []

    def store_slice_result(self, specimen, idx, region_stats, surface, lesion_depth):
        specimen.results[idx] = (region_stats, surface, lesion_depth)
        self.store_calls.append((specimen, idx, region_stats, surface, lesion_depth))
        self.call_log.append(("store", specimen.batch_key, idx))

    def save_results(self, specimen):
        self.save_results_calls.append(specimen)
        self.call_log.append(("save_results", specimen.batch_key))

    def save_annotated_images(self, specimen):
        self.save_annotated_calls.append(specimen)
        self.call_log.append(("save_annotated_images", specimen.batch_key))


# ----------------------------------------------------------------------
# Fake executors
# ----------------------------------------------------------------------


class ImmediateExecutor:
    """Fake executor whose submit() runs the job synchronously and returns an
    already-resolved Future. Good enough whenever a test does not care about
    completion order: real ``concurrent.futures.wait`` returns already-done
    futures immediately without blocking."""

    def __init__(self, *, max_workers=None):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def submit(self, fn, *args, **kwargs):
        future: Future = Future()
        future.set_running_or_notify_cancel()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - mirrors a worker crash
            future.set_exception(exc)
        else:
            future.set_result(result)
        return future


class ScriptedExecutor:
    """Fake executor whose futures resolve lazily, in an order the test
    controls via a monkeypatched ``parallel_analysis.wait`` (see
    ``scripted_wait`` below). ``submit`` only stashes the job on a still-PENDING
    Future and tags it with the (specimen_key, slice_index) parsed out of the
    image path it was given -- ``_run_parallel`` never hands the task object
    itself to the executor, only the unpacked call args, so the image path is
    the only thing available to identify a future's origin from the outside.
    """

    def __init__(self, *, max_workers=None):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def submit(self, fn, *args, **kwargs):
        future: Future = Future()
        future._octool_run = lambda: fn(*args, **kwargs)
        future._octool_key = _parse_marker(args[1].name)
        return future


def scripted_wait(order_fn):
    """Build a stand-in for ``concurrent.futures.wait(..., return_when=FIRST_COMPLETED)``.

    Resolves exactly one still-pending ScriptedExecutor future per call --
    whichever has the lowest ``order_fn(future)`` among the futures passed in
    -- mirroring FIRST_COMPLETED without real concurrency. This is what makes
    result attribution under interleaving, save-overlap and cancellation
    deterministic: with everything resolved eagerly there would be nothing
    left "pending" for a mid-batch cancel() to act on, and the real wait() has
    no notion of "resolve this one next" to script against.
    """

    def fake_wait(fs, timeout=None, return_when=None):
        futures = list(fs)
        pending = [f for f in futures if not f.done()]
        if pending:
            target = min(pending, key=order_fn)
            target.set_running_or_notify_cancel()
            try:
                result = target._octool_run()
            except Exception as exc:  # noqa: BLE001 - mirrors a worker crash
                target.set_exception(exc)
            else:
                target.set_result(result)
        done = {f for f in futures if f.done()}
        not_done = {f for f in futures if not f.done()}
        return done, not_done

    return fake_wait


def _order_fn(order: list[tuple[int, int]]):
    """order: (specimen_key, slice_index) pairs in the desired resolution order."""
    ranks = {pair: i for i, pair in enumerate(order)}
    return lambda future: ranks[future._octool_key]


# ----------------------------------------------------------------------
# 1. Result attribution
# ----------------------------------------------------------------------


class TestResultAttribution:
    @pytest.mark.unit
    def test_interleaved_completion_attributes_slices_to_correct_specimen(self, monkeypatch):
        """GIVEN 3 specimens whose slices resolve interleaved, WHEN run, THEN
        every slice result lands on its own specimen, never a neighbour's."""
        specimens = [_make_specimen(key, 3) for key in range(3)]
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ScriptedExecutor,
            data_saver=saver,
            cpu_count=4,
            available_memory_gb=1000,
        )
        # Round-robin across specimens: spec0.0, spec1.0, spec2.0, spec0.1, ...
        # cpu_count=4 -> 3 workers -> window 12, comfortably fitting all 9
        # tasks in the initial submission so the whole batch resolves in this
        # scripted order (no window/refill interaction to reason about).
        order = [(key, idx) for idx in range(3) for key in range(3)]
        monkeypatch.setattr(pa, "wait", scripted_wait(_order_fn(order)))

        results = coordinator.run(
            specimens,
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=0,
        )

        assert len(saver.store_calls) == 9
        by_key: dict[int, set[int]] = {0: set(), 1: set(), 2: set()}
        for specimen, idx, marker, _surface, _lesion in saver.store_calls:
            key, marker_idx = _parse_marker(marker)
            assert marker_idx == idx  # the worker echoed the slice it was asked for
            assert specimen is specimens[key]  # and it landed on the right specimen
            by_key[key].add(idx)
        assert by_key == {0: {0, 1, 2}, 1: {0, 1, 2}, 2: {0, 1, 2}}
        assert {r.specimen_id for r in results} == {"SPEC0", "SPEC1", "SPEC2"}

    @pytest.mark.unit
    def test_shared_specimen_id_keeps_results_separate(self, monkeypatch):
        """GIVEN two specimens with the same specimen_id, WHEN run, THEN their
        slices are still kept apart -- the coordinator keys by batch position,
        not by specimen_id."""
        specimens = [
            _make_specimen(0, 2, specimen_id="DUP"),
            _make_specimen(1, 2, specimen_id="DUP"),
        ]
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ScriptedExecutor,
            data_saver=saver,
            cpu_count=4,
            available_memory_gb=1000,
        )
        order = [(1, 0), (0, 0), (1, 1), (0, 1)]
        monkeypatch.setattr(pa, "wait", scripted_wait(_order_fn(order)))

        results = coordinator.run(
            specimens,
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=0,
        )

        assert len(results) == 2
        assert all(r.specimen_id == "DUP" for r in results)
        assert all(r.processed_count == 2 and r.total_slices == 2 for r in results)
        for specimen, idx, marker, _surface, _lesion in saver.store_calls:
            key, marker_idx = _parse_marker(marker)
            assert marker_idx == idx
            assert specimen is specimens[key]
        # Each specimen's own results dict holds exactly its own two slices.
        assert set(specimens[0].results.keys()) == {0, 1}
        assert set(specimens[1].results.keys()) == {0, 1}


# ----------------------------------------------------------------------
# 2. Memory release
# ----------------------------------------------------------------------


class TestMemoryRelease:
    @pytest.mark.unit
    def test_save_true_saves_once_per_specimen_and_clears_results(self):
        """GIVEN save=True, WHEN run, THEN each specimen is saved exactly once
        and its in-memory results are cleared afterwards."""
        specimens = [_make_specimen(0, 2), _make_specimen(1, 3)]
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ImmediateExecutor,
            data_saver=saver,
            cpu_count=8,
            available_memory_gb=1000,
        )

        results = coordinator.run(
            specimens, num_sound=1, num_lesion=1, save=True, parallel_threshold=0
        )

        assert saver.save_results_calls == specimens
        assert saver.save_annotated_calls == specimens
        for specimen in specimens:
            assert specimen.results == {}
        assert all(r.saved for r in results)

    @pytest.mark.unit
    def test_save_false_retains_results_and_never_saves(self):
        """GIVEN save=False, WHEN run, THEN results are kept in memory and the
        saver is never invoked."""
        specimen = _make_specimen(0, 2)
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ImmediateExecutor,
            data_saver=saver,
            cpu_count=8,
            available_memory_gb=1000,
        )

        results = coordinator.run(
            [specimen], num_sound=1, num_lesion=1, save=False, parallel_threshold=0
        )

        assert saver.save_results_calls == []
        assert saver.save_annotated_calls == []
        assert len(specimen.results) == 2
        assert results[0].saved is False


# ----------------------------------------------------------------------
# 3. Save overlap / early finalisation
# ----------------------------------------------------------------------


class TestSaveOverlap:
    @pytest.mark.unit
    def test_specimen_saved_before_a_later_specimens_last_slice(self, monkeypatch):
        """GIVEN spec0 (2 slices) finishes while spec1 (3 slices) is still in
        flight, WHEN run, THEN spec0 is saved right after its own last slice --
        before spec1's last slice is even processed. Saving is per-specimen and
        eager, not deferred to the end of the whole batch."""
        spec0 = _make_specimen(0, 2)
        spec1 = _make_specimen(1, 3)
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ScriptedExecutor,
            data_saver=saver,
            cpu_count=4,
            available_memory_gb=1000,
        )
        order = [(1, 0), (0, 0), (1, 1), (0, 1), (1, 2)]
        monkeypatch.setattr(pa, "wait", scripted_wait(_order_fn(order)))

        coordinator.run([spec0, spec1], num_sound=1, num_lesion=1, save=True, parallel_threshold=0)

        save_index = saver.call_log.index(("save_results", 0))
        spec1_last_slice_index = saver.call_log.index(("store", 1, 2))
        assert save_index < spec1_last_slice_index
        assert saver.call_log[: save_index + 2] == [
            ("store", 1, 0),
            ("store", 0, 0),
            ("store", 1, 1),
            ("store", 0, 1),
            ("save_results", 0),
            ("save_annotated_images", 0),
        ]


# ----------------------------------------------------------------------
# 4. Cancellation
# ----------------------------------------------------------------------


class _CancelAfterN:
    """is_cancelled callable that flips to True on its N-th invocation."""

    def __init__(self, n: int):
        self._n = n
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls >= self._n


def _cancellation_order(future) -> int:
    """spec0 fully first, then spec1, then spec2 -- so spec2 (20 slices) is
    still trickling in through the submission window (2 workers -> window 8)
    when cancellation hits, leaving some of it never submitted at all."""
    key, idx = future._octool_key
    if key == 0:
        return idx
    if key == 1:
        return 4 + idx
    return 1000 + idx


class TestCancellation:
    @pytest.mark.unit
    def test_completed_partial_and_cancelled_statuses(self, monkeypatch):
        """GIVEN cancellation flips mid-batch, WHEN run, THEN a fully-finished
        specimen is Completed, a specimen with some slices done is Partial, a
        specimen with none done (some cancelled in-flight, the rest never even
        submitted) is Cancelled, and specimen.status matches result.status in
        every case."""
        done = _make_specimen(0, 4, specimen_id="DONE")
        partial = _make_specimen(1, 4, specimen_id="PARTIAL")
        # Deliberately large so the submission window cannot swallow it whole
        # before cancellation hits -- this is what exercises the post-loop
        # sweep that finalises specimens whose tasks were never submitted.
        none = _make_specimen(2, 20, specimen_id="NONE")
        saver = _FakeDataSaver()
        # cpu_count=3 -> 2 workers -> window = max(2*4, 2+1) = 8, which exactly
        # fits done's 4 + partial's 4 tasks in the initial submission; none's
        # tasks only trickle in one at a time via the refill-on-completion path.
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ScriptedExecutor,
            data_saver=saver,
            cpu_count=3,
            available_memory_gb=1000,
        )
        monkeypatch.setattr(pa, "wait", scripted_wait(_cancellation_order))

        # Cancellation fires on the 6th check: done's 4 slices resolve clean
        # (checks 1-4), partial's slice 0 resolves clean (check 5), partial's
        # slice 1 resolves and then cancellation is observed (check 6) --
        # cancelling partial's slices 2-3 and every "none" task the window had
        # already pulled in, in flight.
        results = coordinator.run(
            [done, partial, none],
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=0,
            is_cancelled=_CancelAfterN(6),
        )

        by_id = {r.specimen_id: r for r in results}
        assert by_id["DONE"].status == "Completed"
        assert by_id["DONE"].processed_count == 4

        assert by_id["PARTIAL"].status == "Partial"
        assert by_id["PARTIAL"].processed_count == 2

        assert by_id["NONE"].status == "Cancelled"
        assert by_id["NONE"].processed_count == 0

        assert done.status == by_id["DONE"].status
        assert partial.status == by_id["PARTIAL"].status
        assert none.status == by_id["NONE"].status


# ----------------------------------------------------------------------
# 5. Worker-count policy
# ----------------------------------------------------------------------


class TestComputeWorkerCount:
    @pytest.mark.unit
    def test_defaults_to_cpu_count_minus_one(self):
        """GIVEN no explicit request, WHEN computing workers, THEN cpu_count - 1."""
        coordinator = BatchSliceCoordinator(cpu_count=9, available_memory_gb=1000)
        assert coordinator.compute_worker_count(queue_len=100) == 8

    @pytest.mark.unit
    def test_bounded_by_queue_length(self):
        """GIVEN a short queue, WHEN computing workers, THEN never more than queue_len."""
        coordinator = BatchSliceCoordinator(cpu_count=9, available_memory_gb=1000)
        assert coordinator.compute_worker_count(queue_len=3) == 3

    @pytest.mark.unit
    def test_bounded_by_max_workers_cap_not_cpu_minus_one(self):
        """GIVEN a 40-CPU host, WHEN computing workers, THEN capped at 24, not 39."""
        coordinator = BatchSliceCoordinator(cpu_count=40, available_memory_gb=1000)
        assert coordinator.compute_worker_count(queue_len=1000) == 24

    @pytest.mark.unit
    def test_bounded_by_ram_budget(self):
        """GIVEN a tight RAM budget, WHEN computing workers, THEN bounded by
        available_memory_gb // gb_per_worker."""
        coordinator = BatchSliceCoordinator(
            cpu_count=9, available_memory_gb=1.0, gb_per_worker=0.25
        )
        assert coordinator.compute_worker_count(queue_len=100) == 4

    @pytest.mark.unit
    def test_never_returns_less_than_one(self):
        """GIVEN a RAM budget that rounds down to zero workers, WHEN computing
        workers, THEN the floor of 1 still applies."""
        coordinator = BatchSliceCoordinator(
            cpu_count=1, available_memory_gb=0.1, gb_per_worker=0.25
        )
        assert coordinator.compute_worker_count(queue_len=1) == 1

    @pytest.mark.unit
    def test_requested_override_is_still_clamped_by_cap(self):
        """GIVEN an explicit requested count above the cap, WHEN computing
        workers, THEN it is still clamped to max_workers_cap."""
        coordinator = BatchSliceCoordinator(cpu_count=9, available_memory_gb=1000)
        assert coordinator.compute_worker_count(queue_len=100, requested=50) == 24


# ----------------------------------------------------------------------
# 6. Mode selection
# ----------------------------------------------------------------------


class TestModeSelection:
    @pytest.mark.unit
    def test_at_or_under_threshold_is_sequential_and_skips_executor_factory(self):
        """GIVEN a batch at/under the parallel threshold, WHEN run, THEN
        on_mode reports sequential and executor_factory is never called."""

        def _boom_factory(**kwargs):
            raise AssertionError("executor_factory must not be called on the sequential path")

        specimen = _make_specimen(0, 3)
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=_boom_factory,
            data_saver=saver,
            cpu_count=8,
            available_memory_gb=1000,
        )
        modes = []
        coordinator.run(
            [specimen],
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=5,  # 3 slices <= 5 -> sequential
            on_mode=lambda mode, workers: modes.append((mode, workers)),
        )
        assert modes == [("sequential", 1)]

    @pytest.mark.unit
    def test_above_threshold_is_parallel_with_computed_workers(self):
        """GIVEN a batch above the parallel threshold, WHEN run, THEN on_mode
        reports parallel with the computed worker count."""
        specimen = _make_specimen(0, 20)
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ImmediateExecutor,
            data_saver=saver,
            cpu_count=8,
            available_memory_gb=1000,
        )
        modes = []
        coordinator.run(
            [specimen],
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=5,  # 20 slices > 5 -> parallel
            on_mode=lambda mode, workers: modes.append((mode, workers)),
        )
        assert modes == [("parallel", 7)]  # cpu_count - 1, unconstrained by queue/RAM here


# ----------------------------------------------------------------------
# 7. Error isolation
# ----------------------------------------------------------------------


class TestErrorIsolation:
    @pytest.mark.unit
    def test_error_field_and_raised_exception_are_isolated_and_reported(self):
        """GIVEN one slice reporting an error field and another raising, WHEN
        run, THEN both are reported via on_error and counted as unprocessed,
        the other slices still complete, and the specimen ends Partial."""
        specimen = _make_specimen(0, 4)
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_error_prone_worker,
            executor_factory=ImmediateExecutor,
            data_saver=saver,
            cpu_count=8,
            available_memory_gb=1000,
        )
        errors = []
        results = coordinator.run(
            [specimen],
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=0,
            on_error=errors.append,
        )

        assert len(errors) == 2
        assert any("slice 2" in e for e in errors)  # the error-field slice (1-based)
        assert any("synthetic worker crash" in e for e in errors)  # the raised exception

        result = results[0]
        assert result.status == "Partial"
        assert result.processed_count == 2
        assert result.total_slices == 4
        assert {idx for _specimen, idx, *_rest in saver.store_calls} == {0, 3}


# ----------------------------------------------------------------------
# 8. Progress callbacks
# ----------------------------------------------------------------------


class TestProgressCallbacks:
    @pytest.mark.unit
    def test_slice_done_is_batch_wide_and_monotonic(self, monkeypatch):
        """GIVEN two specimens whose slices resolve interleaved, WHEN run, THEN
        on_slice_done reports batch-wide (completed, total) counts increasing
        1..total across both specimens, and on_specimen_done fires once each."""
        spec0 = _make_specimen(0, 2, specimen_id="SPEC0")
        spec1 = _make_specimen(1, 3, specimen_id="SPEC1")
        saver = _FakeDataSaver()
        coordinator = BatchSliceCoordinator(
            worker_fn=_marker_worker,
            executor_factory=ScriptedExecutor,
            data_saver=saver,
            cpu_count=4,
            available_memory_gb=1000,
        )
        order = [(1, 0), (0, 0), (1, 1), (0, 1), (1, 2)]
        monkeypatch.setattr(pa, "wait", scripted_wait(_order_fn(order)))

        progress = []
        done_specimens = []
        coordinator.run(
            [spec0, spec1],
            num_sound=1,
            num_lesion=1,
            save=False,
            parallel_threshold=0,
            on_slice_done=lambda done, total: progress.append((done, total)),
            on_specimen_done=lambda result: done_specimens.append(result.specimen_id),
        )

        assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
        assert done_specimens == ["SPEC0", "SPEC1"]


# ----------------------------------------------------------------------
# detect_available_memory_gb
# ----------------------------------------------------------------------


class TestDetectAvailableMemoryGb:
    @pytest.mark.unit
    def test_returns_none_or_positive_float_and_never_raises(self):
        """GIVEN the real stdlib-only RAM probe, WHEN called, THEN it either
        returns None or a positive float, and never raises."""
        value = detect_available_memory_gb()
        assert value is None or (isinstance(value, float) and value > 0)
