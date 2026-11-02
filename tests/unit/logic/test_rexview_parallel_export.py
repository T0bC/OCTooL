"""
Unit tests for app/logic/rexview/parallel_export.py

Tests the ParallelExportCoordinator logic without spawning real processes by
injecting a fake executor factory.
"""

import queue
import threading
from concurrent.futures import Future
from unittest.mock import Mock

import pytest

from app.logic.rexview import export_worker
from app.logic.rexview.models import ExportConfig, ExportResult, SliceExportParams
from app.logic.rexview.parallel_export import ParallelExportCoordinator


def _params(path="C:/data/scan.oct"):
    return SliceExportParams(
        file_path=path,
        name="S",
        first_slice=1,
        last_slice=10,
        num_slices=5,
        slice_direction="XZ",
    )


class FakeExecutor:
    """Synchronous stand-in for ProcessPoolExecutor that returns resolved futures."""

    instances = []
    run_initializer = False

    def __init__(self, max_workers=None, initializer=None, initargs=()):
        self.max_workers = max_workers
        self.initializer = initializer
        self.initargs = initargs
        self.shutdown_calls = []
        if initializer is not None and FakeExecutor.run_initializer:
            initializer(*initargs)
        self.submitted = []
        FakeExecutor.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def shutdown(self, wait=True, cancel_futures=False):
        self.shutdown_calls.append((wait, cancel_futures))

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
    FakeExecutor.run_initializer = False
    yield
    FakeExecutor.instances.clear()
    FakeExecutor.run_initializer = False
    export_worker.reset_worker_state()


class TestComputeWorkerCount:
    @pytest.mark.unit
    def test_caps_to_cpu_minus_one(self):
        coord = ParallelExportCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=20) == 7

    @pytest.mark.unit
    def test_caps_to_queue_length(self):
        coord = ParallelExportCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=3) == 3

    @pytest.mark.unit
    def test_caps_to_max_cap(self):
        coord = ParallelExportCoordinator(cpu_count=32, max_workers_cap=4)
        assert coord.compute_worker_count(queue_len=20) == 4

    @pytest.mark.unit
    def test_requested_override_is_respected(self):
        coord = ParallelExportCoordinator(cpu_count=8, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=20, requested=2) == 2

    @pytest.mark.unit
    def test_never_below_one(self):
        coord = ParallelExportCoordinator(cpu_count=1, max_workers_cap=16)
        assert coord.compute_worker_count(queue_len=0) == 1

    @pytest.mark.unit
    def test_memory_cap_limits_workers(self):
        # 5 GB available, 2 GB per worker -> at most 2 workers despite 7 cpu cores.
        coord = ParallelExportCoordinator(
            cpu_count=8,
            max_workers_cap=16,
            available_memory_gb=5.0,
            gb_per_worker=2.0,
        )
        assert coord.compute_worker_count(queue_len=20) == 2

    @pytest.mark.unit
    def test_memory_cap_never_below_one(self):
        coord = ParallelExportCoordinator(
            cpu_count=8,
            max_workers_cap=16,
            available_memory_gb=1.0,
            gb_per_worker=8.0,
        )
        assert coord.compute_worker_count(queue_len=20) == 1


class TestRun:
    @pytest.mark.unit
    def test_runs_all_files(self):
        def worker(file_path, params, config):
            return ExportResult(file_path=file_path, exported_files=["x.tiff"])

        coord = ParallelExportCoordinator(
            worker_fn=worker,
            executor_factory=FakeExecutor,
            cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f"C:/d/{i}.oct", _params(f"C:/d/{i}.oct"), config) for i in range(3)]

        results = coord.run(tasks)

        assert len(results) == 3
        assert {r.file_path for r in results} == {t[0] for t in tasks}
        assert FakeExecutor.instances[0].max_workers == 3

    @pytest.mark.unit
    def test_progress_callback_called_per_result(self):
        def worker(file_path, params, config):
            return ExportResult(file_path=file_path)

        coord = ParallelExportCoordinator(
            worker_fn=worker,
            executor_factory=FakeExecutor,
            cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f"C:/d/{i}.oct", _params(), config) for i in range(2)]
        cb = Mock()

        coord.run(tasks, progress_callback=cb)

        assert cb.call_count == 2
        assert all(isinstance(c.args[0], ExportResult) for c in cb.call_args_list)

    @pytest.mark.unit
    def test_cancellation_submits_no_tasks(self):
        worker = Mock(return_value=ExportResult(file_path="x"))
        coord = ParallelExportCoordinator(
            worker_fn=worker,
            executor_factory=FakeExecutor,
            cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f"C:/d/{i}.oct", _params(), config) for i in range(3)]

        coord.cancel()
        results = coord.run(tasks)

        assert results == []
        worker.assert_not_called()

    @pytest.mark.unit
    def test_worker_exception_becomes_error_result(self):
        def worker(file_path, params, config):
            raise RuntimeError("kaboom")

        coord = ParallelExportCoordinator(
            worker_fn=worker,
            executor_factory=FakeExecutor,
            cpu_count=4,
        )
        config = ExportConfig()
        tasks = [("C:/d/bad.oct", _params("C:/d/bad.oct"), config)]

        results = coord.run(tasks)

        assert len(results) == 1
        assert results[0].error is not None
        assert "kaboom" in results[0].error
        assert results[0].file_path == "C:/d/bad.oct"
        assert results[0].exported_files == []


class _FakeProc:
    def __init__(self, stubborn=False):
        self.stubborn = stubborn
        self.alive = True
        self.terminated = False

    def join(self, timeout=None):
        if not self.stubborn:
            self.alive = False

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.terminated = True
        self.alive = False


def _ipc():
    return queue.Queue(), threading.Event()


class TestSliceProgress:
    @pytest.mark.unit
    def test_worker_slice_reports_reach_callback(self):
        FakeExecutor.run_initializer = True

        def worker(file_path, params, config):
            for done in range(1, 4):
                export_worker.report_slice(file_path, done, 3)
            return ExportResult(file_path=file_path)

        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4, ipc_factory=_ipc
        )
        events = []
        coord.run(
            [("C:/d/a.oct", _params(), ExportConfig())],
            slice_progress_callback=lambda p, d, t: events.append((p, d, t)),
        )

        assert events == [("C:/d/a.oct", 1, 3), ("C:/d/a.oct", 2, 3), ("C:/d/a.oct", 3, 3)]

    @pytest.mark.unit
    def test_callback_errors_do_not_break_run(self):
        FakeExecutor.run_initializer = True

        def worker(file_path, params, config):
            export_worker.report_slice(file_path, 1, 1)
            return ExportResult(file_path=file_path)

        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4, ipc_factory=_ipc
        )
        results = coord.run(
            [("C:/d/a.oct", _params(), ExportConfig())],
            slice_progress_callback=Mock(side_effect=RuntimeError("ui gone")),
        )
        assert len(results) == 1


class TestThreadLimit:
    @pytest.mark.unit
    def test_initializer_gets_blas_thread_share(self):
        coord = ParallelExportCoordinator(
            worker_fn=lambda f, p, c: ExportResult(file_path=f),
            executor_factory=FakeExecutor,
            cpu_count=40,
            max_workers_cap=8,
            ipc_factory=_ipc,
        )
        tasks = [(f"C:/d/{i}.oct", _params(), ExportConfig()) for i in range(10)]
        coord.run(tasks)

        executor = FakeExecutor.instances[0]
        assert executor.max_workers == 8
        assert executor.initializer is export_worker.init_worker
        assert executor.initargs[2] == 5  # 40 cpus // 8 workers

    @pytest.mark.unit
    def test_compute_blas_threads(self):
        from app.logic.shared.concurrency import compute_blas_threads

        assert compute_blas_threads(1, cpu_count=12) == 12
        assert compute_blas_threads(8, cpu_count=40) == 5
        assert compute_blas_threads(8, cpu_count=4) == 1


class TestCancellation:
    @pytest.mark.unit
    def test_cancel_sets_shared_event_and_shuts_pool(self):
        seen = []

        def worker(file_path, params, config):
            coord.cancel()
            seen.append(export_worker.is_cancel_requested())
            return ExportResult(file_path=file_path, cancelled=True)

        FakeExecutor.run_initializer = True
        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4, ipc_factory=_ipc
        )
        tasks = [(f"C:/d/{i}.oct", _params(), ExportConfig()) for i in range(3)]
        results = coord.run(tasks)

        assert seen == [True]  # worker saw the shared event
        assert len(results) == 1  # remaining tasks never submitted
        assert results[0].cancelled
        assert FakeExecutor.instances[0].shutdown_calls == [(False, True)]

    @pytest.mark.unit
    def test_cancelled_future_becomes_cancelled_result(self):
        fut = Future()
        fut.cancel()
        result = ParallelExportCoordinator._collect(fut, ("C:/d/a.oct", _params(), ExportConfig()))
        assert result.cancelled
        assert result.file_path == "C:/d/a.oct"

    @pytest.mark.unit
    def test_shutdown_terminates_stubborn_workers(self):
        coord = ParallelExportCoordinator()
        polite, stubborn = _FakeProc(), _FakeProc(stubborn=True)
        coord._executor = Mock(_processes={1: polite, 2: stubborn})

        coord.shutdown(grace_seconds=0.01)

        assert coord.is_cancelled
        assert stubborn.terminated
        assert not polite.terminated

    @pytest.mark.unit
    def test_shutdown_without_run_is_safe(self):
        coord = ParallelExportCoordinator()
        coord.shutdown(grace_seconds=0.01)
        assert coord.is_cancelled
