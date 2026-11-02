"""
RexView Parallel Export Coordinator.

Pure business logic (no tkinter) that distributes per-file OCT exports across
multiple processes using a ProcessPoolExecutor. Each file is an independent
unit of CPU-bound work, so file-level parallelism scales well with low
overhead. The coordinator is fully unit-testable: the executor factory and the
worker function are injectable, so tests can run synchronously without spawning
real processes.

Key contents:
- ParallelExportCoordinator: Distributes per-file exports across a process pool.
- compute_worker_count: Binds instance config to the shared worker-count policy.
- Cancellation (cancel/reset/is_cancelled) comes from the shared Cancellable mixin.
- run: Submits tasks to the executor, collects ExportResults and streams per-slice progress.
- cancel / shutdown: Signal workers through a shared event; shutdown force-terminates
  any worker processes that outlive a short grace period.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""

from __future__ import annotations

import contextlib
import multiprocessing
import queue
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

from app.logic.rexview.export_worker import export_one_file, init_worker
from app.logic.rexview.models import ExportConfig, ExportResult, SliceExportParams
from app.logic.shared.concurrency import Cancellable, compute_blas_threads, compute_worker_count

# A task is a (file_path, params, config) tuple dispatched to a worker.
ExportTask = tuple[str, SliceExportParams, ExportConfig]

# Called with (file_path, slices_done, slices_total) for every exported slice.
SliceProgressCallback = Callable[[str, int, int], None]


def _default_ipc() -> tuple[object, object]:
    """Create the cross-process progress queue and cancel event."""
    return multiprocessing.Queue(), multiprocessing.Event()


class ParallelExportCoordinator(Cancellable):
    """Coordinate process-parallel export of multiple OCT files."""

    #: Hard upper bound on worker processes regardless of CPU count.
    DEFAULT_MAX_WORKERS_CAP = 8

    def __init__(
        self,
        worker_fn: Callable[..., ExportResult] = export_one_file,
        executor_factory: Callable[..., object] = ProcessPoolExecutor,
        cpu_count: int | None = None,
        max_workers_cap: int | None = None,
        available_memory_gb: float | None = None,
        gb_per_worker: float | None = None,
        ipc_factory: Callable[[], tuple[object, object]] = _default_ipc,
    ):
        """
        Args:
            worker_fn: Top-level, picklable callable invoked per file.
            executor_factory: Callable returning a context-manager executor with
                a ``submit`` method (defaults to ``ProcessPoolExecutor``). It is
                called with ``max_workers``, ``initializer`` and ``initargs``.
            cpu_count: Override for the detected CPU count (mainly for tests).
            max_workers_cap: Hard cap on worker processes.
            available_memory_gb: Optional available RAM budget in GiB. When given
                together with ``gb_per_worker``, the worker count is additionally
                capped so the pool does not exhaust memory (raw-spectral exports
                hold large arrays per process).
            gb_per_worker: Estimated peak RAM per worker process in GiB.
            ipc_factory: Returns ``(progress_queue, cancel_event)``; the queue
                needs ``get(timeout=)``/``put`` and the event ``set``/``is_set``.
        """
        self._worker_fn = worker_fn
        self._executor_factory = executor_factory
        self._cpu_count = cpu_count
        self._max_workers_cap = max_workers_cap or self.DEFAULT_MAX_WORKERS_CAP
        self._available_memory_gb = available_memory_gb
        self._gb_per_worker = gb_per_worker
        self._ipc_factory = ipc_factory
        # Live state of the current run (set by run(), read by cancel()/shutdown()).
        self._executor: object | None = None
        self._cancel_event: object | None = None

    def compute_worker_count(
        self,
        queue_len: int,
        requested: int | None = None,
    ) -> int:
        """
        Determine the number of worker processes to use.

        Defaults to ``cpu_count - 1`` (leaving a core for the UI), bounded by the
        queue length and a hard cap. An explicit ``requested`` value overrides the
        CPU-based default but is still clamped to ``[1, cap]`` and the queue length.
        """
        return compute_worker_count(
            queue_len,
            requested,
            max_workers_cap=self._max_workers_cap,
            cpu_count=self._cpu_count,
            available_memory_gb=self._available_memory_gb,
            gb_per_worker=self._gb_per_worker,
        )

    def cancel(self) -> None:
        """Stop submitting work, drop queued files and tell running workers to stop.

        Workers finish their current slice and return a cancelled result.
        Safe to call from any thread.
        """
        super().cancel()
        event = self._cancel_event
        if event is not None:
            event.set()
        executor = self._executor
        if executor is not None:
            with contextlib.suppress(Exception):
                executor.shutdown(wait=False, cancel_futures=True)

    def shutdown(self, grace_seconds: float = 3.0) -> None:
        """Cancel, give workers ``grace_seconds`` to exit, then terminate stragglers.

        Intended for application exit so no worker process outlives the app.
        """
        # Snapshot first: ProcessPoolExecutor.shutdown() drops its process table.
        processes = list((getattr(self._executor, "_processes", None) or {}).values())
        self.cancel()
        deadline = time.monotonic() + grace_seconds
        for proc in processes:
            with contextlib.suppress(Exception):
                proc.join(timeout=max(0.0, deadline - time.monotonic()))
        for proc in processes:
            with contextlib.suppress(Exception):
                if proc.is_alive():
                    proc.terminate()
        for proc in processes:
            with contextlib.suppress(Exception):
                proc.join(timeout=2.0)

    @staticmethod
    def _drain_progress(
        progress_queue: object,
        stop: threading.Event,
        callback: SliceProgressCallback | None,
    ) -> None:
        """Forward worker progress messages to ``callback`` until ``stop`` is set."""
        final_pass = False
        while True:
            try:
                file_path, done, total = progress_queue.get(timeout=0.05 if final_pass else 0.1)
            except queue.Empty:
                if final_pass:
                    return
                final_pass = stop.is_set()
                continue
            except (EOFError, OSError, ValueError):
                return
            if callback is not None:
                with contextlib.suppress(Exception):
                    callback(file_path, done, total)

    def run(
        self,
        tasks: Iterable[ExportTask],
        worker_count: int | None = None,
        progress_callback: Callable[[ExportResult], None] | None = None,
        slice_progress_callback: SliceProgressCallback | None = None,
    ) -> list[ExportResult]:
        """
        Execute all export tasks across a pool and collect their results.

        Args:
            tasks: Iterable of (file_path, params, config) tuples.
            worker_count: Optional explicit worker count override.
            progress_callback: Optional callback invoked with each ExportResult
                as it completes (called on the coordinator's thread).
            slice_progress_callback: Optional callback invoked with
                ``(file_path, done, total)`` for every exported slice (called
                on a helper thread, so it must be thread-safe).

        Returns:
            List of ExportResult objects (one per completed task).
        """
        tasks = list(tasks)
        results: list[ExportResult] = []

        if self._cancelled or not tasks:
            return results

        n_workers = self.compute_worker_count(len(tasks), worker_count)
        blas_threads = compute_blas_threads(n_workers, self._cpu_count)

        progress_queue, cancel_event = self._ipc_factory()
        self._cancel_event = cancel_event
        if self._cancelled:
            cancel_event.set()

        stop_drain = threading.Event()
        drain_thread = threading.Thread(
            target=self._drain_progress,
            args=(progress_queue, stop_drain, slice_progress_callback),
            name="rexview-progress-drain",
            daemon=True,
        )
        drain_thread.start()

        try:
            with self._executor_factory(
                max_workers=n_workers,
                initializer=init_worker,
                initargs=(progress_queue, cancel_event, blas_threads),
            ) as executor:
                self._executor = executor
                pending = {}
                for task in tasks:
                    if self._cancelled:
                        break
                    pending[executor.submit(self._worker_fn, *task)] = task

                while pending:
                    # ``wait`` does not report futures cancelled by shutdown(),
                    # so poll ``done()`` (true for cancelled futures as well).
                    wait(list(pending), timeout=0.2, return_when=FIRST_COMPLETED)
                    for future in [f for f in pending if f.done()]:
                        task = pending.pop(future)
                        result = self._collect(future, task)
                        results.append(result)
                        if progress_callback:
                            progress_callback(result)
        finally:
            stop_drain.set()
            drain_thread.join(timeout=5.0)
            self._executor = None
            self._cancel_event = None
            with contextlib.suppress(Exception):
                progress_queue.close()

        return results

    @staticmethod
    def _collect(future, task: ExportTask) -> ExportResult:
        """Turn a finished future into an ExportResult, isolating worker failures."""
        file_path, params = task[0], task[1]
        if future.cancelled():
            return ExportResult(file_path=file_path, cancelled=True)
        try:
            return future.result()
        except Exception as exc:  # noqa: BLE001 - isolate worker failures
            return ExportResult(
                file_path=file_path,
                exported_files=[],
                failed_count=getattr(params, "num_slices", 0),
                error=str(exc),
            )
