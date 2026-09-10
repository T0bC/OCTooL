"""
Unit tests for app/logic/carlquant/parallel_analysis.py

Tests the ParallelSpecimenCoordinator logic without spawning real processes by
injecting a fake executor factory and a stub worker function.
"""

from concurrent.futures import Future
from pathlib import Path

import pytest

from app.logic.carlquant.analysis_service import SpecimenAnalysisResult
from app.logic.carlquant.parallel_analysis import ParallelSpecimenCoordinator
from app.logic.carlquant.specimen_model import Specimen


def _specimen(specimen_id="S1", slices=25):
    return Specimen(
        specimen_id=specimen_id,
        source=Path("C:/data") / specimen_id,
        images=[Path(f"C:/data/{specimen_id}/{i}.png") for i in range(slices)],
        slices=slices,
        status="Pending",
        date=0.0,
    )


def _ok_worker(specimen, num_sound, num_lesion, detection_method):
    return SpecimenAnalysisResult(
        specimen_id=specimen.specimen_id,
        status="Completed",
        processed_count=specimen.slices,
        total_slices=specimen.slices,
        saved=True,
    )


class FakeExecutor:
    """Synchronous stand-in for ProcessPoolExecutor that returns resolved futures."""

    instances = []

    def __init__(self, max_workers=None):
        self.max_workers = max_workers
        self.submitted = []
        FakeExecutor.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args):
        self.submitted.append(args)
        fut = Future()
        try:
            fut.set_result(fn(*args))
        except Exception as e:  # mirror executor behavior
            fut.set_exception(e)
        return fut


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeExecutor.instances.clear()
    yield
    FakeExecutor.instances.clear()


class TestComputeWorkerCount:
    @pytest.mark.unit
    def test_caps_to_cpu_minus_one(self):
        coord = ParallelSpecimenCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=200) == 7

    @pytest.mark.unit
    def test_caps_to_queue_length(self):
        coord = ParallelSpecimenCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=3) == 3

    @pytest.mark.unit
    def test_caps_to_max_cap(self):
        # The real motivation: a 40-core box must not spawn 39 workers.
        coord = ParallelSpecimenCoordinator(cpu_count=40)
        assert coord.compute_worker_count(queue_len=200) == 8

    @pytest.mark.unit
    def test_requested_override_is_respected(self):
        coord = ParallelSpecimenCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=200, requested=2) == 2

    @pytest.mark.unit
    def test_never_below_one(self):
        coord = ParallelSpecimenCoordinator(cpu_count=1, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=0) == 1

    @pytest.mark.unit
    def test_memory_cap_limits_workers(self):
        coord = ParallelSpecimenCoordinator(
            cpu_count=8,
            max_workers_cap=16,
            available_memory_gb=5.0,
            gb_per_worker=2.0,
        )
        assert coord.compute_worker_count(queue_len=200) == 2

    @pytest.mark.unit
    def test_memory_cap_never_below_one(self):
        coord = ParallelSpecimenCoordinator(
            cpu_count=8,
            max_workers_cap=16,
            available_memory_gb=0.5,
            gb_per_worker=4.0,
        )
        assert coord.compute_worker_count(queue_len=200) == 1


class TestRun:
    @pytest.mark.unit
    def test_uses_one_pool_for_the_whole_batch(self):
        """The regression this module exists to prevent: one pool, not one per specimen."""
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker,
            executor_factory=FakeExecutor,
            cpu_count=8,
        )
        specimens = [_specimen(f"S{i}") for i in range(20)]

        results = coord.run(specimens, num_sound=3, num_lesion=3, detection_method="combined_mean")

        assert len(FakeExecutor.instances) == 1
        assert len(FakeExecutor.instances[0].submitted) == 20
        assert len(results) == 20
        assert all(r.status == "Completed" for r in results)

    @pytest.mark.unit
    def test_one_task_per_specimen_with_analysis_params(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        coord.run([_specimen("S1")], num_sound=4, num_lesion=5, detection_method="sigmoid")

        (args,) = FakeExecutor.instances[0].submitted
        specimen, num_sound, num_lesion, detection_method = args
        assert specimen.specimen_id == "S1"
        assert (num_sound, num_lesion, detection_method) == (4, 5, "sigmoid")

    @pytest.mark.unit
    def test_worker_count_is_passed_to_executor(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=40
        )
        coord.run(
            [_specimen(f"S{i}") for i in range(50)],
            num_sound=3,
            num_lesion=3,
            detection_method="combined_mean",
        )
        assert FakeExecutor.instances[0].max_workers == 8

    @pytest.mark.unit
    def test_on_mode_reports_once_for_the_batch(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        calls = []
        coord.run(
            [_specimen(f"S{i}") for i in range(10)],
            num_sound=3,
            num_lesion=3,
            detection_method="combined_mean",
            on_mode=lambda mode, workers: calls.append((mode, workers)),
        )
        assert calls == [("parallel", 7)]

    @pytest.mark.unit
    def test_progress_callback_fires_per_specimen(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        seen = []
        coord.run(
            [_specimen(f"S{i}") for i in range(5)],
            num_sound=3,
            num_lesion=3,
            detection_method="combined_mean",
            progress_callback=seen.append,
        )
        assert len(seen) == 5
        assert {r.specimen_id for r in seen} == {f"S{i}" for i in range(5)}

    @pytest.mark.unit
    def test_worker_exception_is_isolated(self):
        def boom(specimen, *_):
            if specimen.specimen_id == "S1":
                raise RuntimeError("bad slice")
            return _ok_worker(specimen, *_)

        coord = ParallelSpecimenCoordinator(
            worker_fn=boom, executor_factory=FakeExecutor, cpu_count=8
        )
        results = coord.run(
            [_specimen("S0"), _specimen("S1"), _specimen("S2")],
            num_sound=3,
            num_lesion=3,
            detection_method="combined_mean",
        )

        by_id = {r.specimen_id: r for r in results}
        assert len(results) == 3
        assert by_id["S1"].status.startswith("Error")
        assert by_id["S1"].saved is False
        assert by_id["S0"].status == "Completed"
        assert by_id["S2"].status == "Completed"

    @pytest.mark.unit
    def test_cancel_before_run_submits_nothing(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        coord.cancel()
        results = coord.run(
            [_specimen("S1")], num_sound=3, num_lesion=3, detection_method="combined_mean"
        )
        assert results == []
        assert FakeExecutor.instances == []

    @pytest.mark.unit
    def test_cancel_during_run_stops_submitting(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )

        def cancel_after_three(result):
            if len(FakeExecutor.instances[0].submitted) >= 3:
                coord.cancel()

        # FakeExecutor runs work eagerly inside submit(), so the callback cannot
        # interleave; drive cancellation from a worker_fn side effect instead.
        submitted = []

        def counting_worker(specimen, *args):
            submitted.append(specimen.specimen_id)
            if len(submitted) == 3:
                coord.cancel()
            return _ok_worker(specimen, *args)

        coord._worker_fn = counting_worker
        coord.run(
            [_specimen(f"S{i}") for i in range(10)],
            num_sound=3,
            num_lesion=3,
            detection_method="combined_mean",
            progress_callback=cancel_after_three,
        )
        assert len(submitted) == 3

    @pytest.mark.unit
    def test_empty_input_returns_empty(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        assert coord.run([], num_sound=3, num_lesion=3, detection_method="combined_mean") == []
        assert FakeExecutor.instances == []

    @pytest.mark.unit
    def test_reset_clears_cancellation(self):
        coord = ParallelSpecimenCoordinator(
            worker_fn=_ok_worker, executor_factory=FakeExecutor, cpu_count=8
        )
        coord.cancel()
        assert coord.is_cancelled is True
        coord.reset()
        assert coord.is_cancelled is False
        results = coord.run(
            [_specimen("S1")], num_sound=3, num_lesion=3, detection_method="combined_mean"
        )
        assert len(results) == 1


class TestSpecimenWorker:
    @pytest.mark.unit
    def test_specimen_is_picklable(self):
        """Specimens cross a process boundary, so this must hold."""
        import pickle

        specimen = _specimen("S1")
        specimen.measurement = 2
        specimen.operator = "TM"

        restored = pickle.loads(pickle.dumps(specimen))

        assert restored.specimen_id == "S1"
        assert restored.slices == 25
        assert restored.measurement == 2
        assert restored.operator == "TM"

    @pytest.mark.unit
    def test_result_is_picklable(self):
        import pickle

        result = SpecimenAnalysisResult("S1", "Completed", 25, 25, True)
        assert pickle.loads(pickle.dumps(result)) == result

    @pytest.mark.unit
    def test_worker_forces_sequential_branch(self):
        """The worker must never open a nested pool inside a pool worker."""
        from app.logic.carlquant import specimen_worker

        assert specimen_worker._NO_NESTED_POOL > 10_000
