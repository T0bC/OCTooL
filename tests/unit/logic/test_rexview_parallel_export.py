"""
Unit tests for app/logic/rexview/parallel_export.py

Tests the ParallelExportCoordinator logic without spawning real processes by
injecting a fake executor factory.
"""
from concurrent.futures import Future
from unittest.mock import Mock

import pytest

from app.logic.rexview.parallel_export import ParallelExportCoordinator
from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportResult


def _params(path='C:/data/scan.oct'):
    return SliceExportParams(
        file_path=path,
        name='S',
        first_slice=1,
        last_slice=10,
        num_slices=5,
        slice_direction='XZ',
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


class TestRun:
    @pytest.mark.unit
    def test_runs_all_files(self):
        def worker(file_path, params, config):
            return ExportResult(file_path=file_path, exported_files=['x.tiff'])

        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f'C:/d/{i}.oct', _params(f'C:/d/{i}.oct'), config) for i in range(3)]

        results = coord.run(tasks)

        assert len(results) == 3
        assert {r.file_path for r in results} == {t[0] for t in tasks}
        assert FakeExecutor.instances[0].max_workers == 3

    @pytest.mark.unit
    def test_progress_callback_called_per_result(self):
        def worker(file_path, params, config):
            return ExportResult(file_path=file_path)

        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f'C:/d/{i}.oct', _params(), config) for i in range(2)]
        cb = Mock()

        coord.run(tasks, progress_callback=cb)

        assert cb.call_count == 2
        assert all(isinstance(c.args[0], ExportResult) for c in cb.call_args_list)

    @pytest.mark.unit
    def test_cancellation_submits_no_tasks(self):
        worker = Mock(return_value=ExportResult(file_path='x'))
        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4,
        )
        config = ExportConfig()
        tasks = [(f'C:/d/{i}.oct', _params(), config) for i in range(3)]

        coord.cancel()
        results = coord.run(tasks)

        assert results == []
        worker.assert_not_called()

    @pytest.mark.unit
    def test_worker_exception_becomes_error_result(self):
        def worker(file_path, params, config):
            raise RuntimeError('kaboom')

        coord = ParallelExportCoordinator(
            worker_fn=worker, executor_factory=FakeExecutor, cpu_count=4,
        )
        config = ExportConfig()
        tasks = [('C:/d/bad.oct', _params('C:/d/bad.oct'), config)]

        results = coord.run(tasks)

        assert len(results) == 1
        assert results[0].error is not None
        assert 'kaboom' in results[0].error
        assert results[0].file_path == 'C:/d/bad.oct'
        assert results[0].exported_files == []
