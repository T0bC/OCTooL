"""
CarlQuant Batch Slice Coordinator.

Pure business logic (no tkinter) that analyses a whole batch of specimens with a
single, long-lived ProcessPoolExecutor fed a *flat* queue of slice tasks.

Parallelism is at the *slice* axis, batch-wide. The previous layout opened one
pool per specimen: with ~25 slices per specimen and the ``spawn`` start method
used on Windows and macOS, every specimen paid a fresh round of pool creation
plus the lazy ``scipy``/``sklearn`` imports each worker performs on its first
slice (~2.7 s per worker start). It also inserted a barrier between specimens
and left every core idle while the parent wrote Excel and annotated images.

One pool for the whole batch pays startup once, never idles between specimens,
and lets the parent save specimen N while the workers already compute N+1. On
the reference dataset (15 specimens x 25 slices, 20 physical cores) this measured
1.66x faster on compute and ~2.05x end to end including saves.

Slice results arrive interleaved, so each task carries the position of its
specimen in the batch and the parent keys results back by that position. A
positional key is used rather than ``specimen_id`` so that two specimens sharing
an id can never have their slices merged into one Excel file.

The coordinator is fully unit-testable: the executor factory, the worker
function and the data saver are injectable, so tests can run synchronously
without spawning real processes.

Key contents:
- BatchSliceCoordinator: Owns one pool and drives a flat queue of slice tasks.
- compute_worker_count: CPU/RAM/queue-bounded worker-count policy.
- run: Submits every slice of every specimen, saves each specimen as it finishes.
- detect_available_memory_gb: Stdlib-only available-RAM probe for the RAM cap.

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

import gc
import os
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from app.logic.carlquant.analysis_service import (
    DEFAULT_DETECTION_METHOD,
    SpecimenAnalysisResult,
)
from app.logic.carlquant.carl_quant_core import process_slice_parallel
from app.logic.carlquant.data_service import DataSaver

#: Tasks kept in flight per worker. Large enough that a worker never waits for
#: the parent to refill the queue, small enough that the Futures holding
#: finished slice results (~1.4 MB each) do not accumulate over a long batch.
WINDOW_PER_WORKER = 4


def detect_available_memory_gb() -> float | None:
    """Best-effort available-RAM probe in GiB, or None if it cannot be determined.

    Deliberately stdlib-only: ``psutil`` is not a declared dependency of OCTooL
    and adding one for a worker-count heuristic is not worth it. Any failure
    yields None, which simply disables the RAM cap.
    """
    try:
        if sys.platform == "win32":
            import ctypes

            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return status.ullAvailPhys / (1024**3)

        with open("/proc/meminfo") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024**2)
    except Exception:  # noqa: BLE001 - a probe must never break the analysis
        return None
    return None


@dataclass
class _SliceTask:
    """One unit of work: a single slice, tagged with its specimen's batch slot."""

    specimen_key: int
    slice_index: int
    image_path: Path
    region_config: object | None
    air_config: object | None


@dataclass
class _SpecimenState:
    """Parent-side bookkeeping for one specimen while its slices are in flight."""

    specimen: object
    specimen_id: str
    total: int
    remaining: int
    processed: int = 0
    finalized: bool = False
    saved: bool = False
    status: str = "Pending"


@dataclass
class _RunContext:
    """Mutable per-run state shared by the execution strategies."""

    states: list[_SpecimenState]
    total_slices: int
    save: bool
    result_lock: object | None
    results: list[SpecimenAnalysisResult]
    on_status: Callable[[str], None] | None
    on_slice_done: Callable[[int, int], None] | None
    on_specimen_done: Callable[[SpecimenAnalysisResult], None] | None
    on_error: Callable[[str], None] | None
    is_cancelled: Callable[[], bool] | None
    completed: int = 0
    cancelled: bool = False

    def emit_status(self, message: str) -> None:
        if self.on_status is not None:
            self.on_status(message)

    def emit_error(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)

    def check_cancelled(self) -> bool:
        """True the first time cancellation is observed, False on later calls."""
        if self.cancelled or self.is_cancelled is None:
            return False
        if self.is_cancelled():
            self.cancelled = True
            return True
        return False


class BatchSliceCoordinator:
    """Analyse every slice of every specimen through one shared process pool."""

    #: Hard upper bound on worker processes. Measured: 39 workers beat 20 by only
    #: ~5% while costing 6.1 GB of RSS, so the extra processes are not worth it.
    DEFAULT_MAX_WORKERS_CAP = 24

    #: Peak RAM per worker in GiB (156 MB measured on the widest specimen, plus
    #: headroom). Applied only when an available-memory figure could be obtained.
    DEFAULT_GB_PER_WORKER = 0.25

    #: Below this many slices in the whole batch, a pool cannot pay for itself.
    DEFAULT_PARALLEL_THRESHOLD = 10

    def __init__(
        self,
        worker_fn: Callable[..., tuple] = process_slice_parallel,
        executor_factory: Callable[..., object] = ProcessPoolExecutor,
        data_saver=DataSaver,
        cpu_count: int | None = None,
        max_workers_cap: int | None = None,
        available_memory_gb: float | None = None,
        gb_per_worker: float | None = None,
    ):
        """
        Args:
            worker_fn: Top-level, picklable per-slice callable returning
                ``(slice_idx, region_stats, surface, lesion_depth, error)``.
            executor_factory: Callable returning a context-manager executor with
                ``submit`` (defaults to ``ProcessPoolExecutor``).
            data_saver: Object exposing ``store_slice_result``, ``save_results``
                and ``save_annotated_images`` (defaults to :class:`DataSaver`).
            cpu_count: Override for the detected CPU count (mainly for tests).
            max_workers_cap: Hard cap on worker processes.
            available_memory_gb: Available RAM budget in GiB. When omitted it is
                probed; when the probe fails the RAM cap is skipped.
            gb_per_worker: Estimated peak RAM per worker process in GiB.
        """
        self._worker_fn = worker_fn
        self._executor_factory = executor_factory
        self._saver = data_saver
        self._cpu_count = cpu_count
        self._max_workers_cap = max_workers_cap or self.DEFAULT_MAX_WORKERS_CAP
        self._available_memory_gb = available_memory_gb
        self._gb_per_worker = gb_per_worker or self.DEFAULT_GB_PER_WORKER

    # ------------------------------------------------------------------
    # Worker-count policy
    # ------------------------------------------------------------------
    def compute_worker_count(self, queue_len: int, requested: int | None = None) -> int:
        """Determine the number of worker processes for a batch of ``queue_len`` slices.

        Defaults to ``cpu_count - 1`` (leaving a core for the UI), then bounds by
        a hard cap, the queue length and -- when available RAM is known -- a
        memory budget. An explicit ``requested`` value replaces the CPU-based
        default but is still clamped.
        """
        cpu = self._cpu_count if self._cpu_count is not None else (os.cpu_count() or 1)
        base = requested if requested is not None else max(cpu - 1, 1)
        bounded = min(base, self._max_workers_cap)
        if queue_len > 0:
            bounded = min(bounded, queue_len)

        memory_gb = self._available_memory_gb
        if memory_gb is None:
            memory_gb = detect_available_memory_gb()
        if memory_gb is not None and self._gb_per_worker:
            bounded = min(bounded, int(memory_gb // self._gb_per_worker))

        return max(1, bounded)

    # ------------------------------------------------------------------
    # Batch pipeline
    # ------------------------------------------------------------------
    def run(
        self,
        specimens: Iterable,
        *,
        num_sound: int,
        num_lesion: int,
        detection_method: str = DEFAULT_DETECTION_METHOD,
        save: bool = True,
        result_lock=None,
        worker_count: int | None = None,
        parallel_threshold: int | None = None,
        on_mode: Callable[[str, int], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_slice_done: Callable[[int, int], None] | None = None,
        on_specimen_done: Callable[[SpecimenAnalysisResult], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> list[SpecimenAnalysisResult]:
        """Analyse all specimens through one pool and save each as it completes.

        Args:
            specimens: Specimen objects, already carrying any UI-stamped metadata
                (``operator``, ``measurement``) and their loaded ``config``.
            num_sound: Number of sound regions to extract per slice.
            num_lesion: Number of lesion regions to extract per slice.
            detection_method: Lesion-depth detection method name.
            save: Persist results and annotated images per specimen, then release
                that specimen's results. Leaving this off keeps every result in
                memory and is only appropriate for tests and small batches.
            result_lock: Optional lock serialising ``store_slice_result``.
            worker_count: Explicit worker-count override.
            parallel_threshold: Minimum batch slice count for parallel execution.
            on_mode: ``(mode, workers)``, invoked once before work starts.
            on_status: Progress text.
            on_slice_done: ``(completed_slices, total_slices)`` for the whole
                batch -- the flat layout has no meaningful per-specimen slice
                position, since several specimens are in flight at once.
            on_specimen_done: Invoked with each :class:`SpecimenAnalysisResult`
                as its specimen finishes, in completion order.
            on_error: Per-slice error text.
            is_cancelled: Cooperative cancellation probe.

        Returns:
            SpecimenAnalysisResult objects in completion order.
        """
        states, tasks = self._build_queue(specimens)
        results: list[SpecimenAnalysisResult] = []
        if not states:
            return results

        context = _RunContext(
            states=states,
            total_slices=len(tasks),
            save=save,
            result_lock=result_lock,
            results=results,
            on_status=on_status,
            on_slice_done=on_slice_done,
            on_specimen_done=on_specimen_done,
            on_error=on_error,
            is_cancelled=is_cancelled,
        )

        # Specimens with no slices never receive a result, so close them upfront.
        for state in states:
            if state.total == 0:
                self._finalize(state, context)
        if not tasks:
            return results

        threshold = (
            parallel_threshold
            if parallel_threshold is not None
            else self.DEFAULT_PARALLEL_THRESHOLD
        )
        workers = self.compute_worker_count(len(tasks), worker_count)
        use_parallel = len(tasks) > threshold and workers > 1
        if not use_parallel:
            workers = 1
        if on_mode is not None:
            on_mode("parallel" if use_parallel else "sequential", workers)

        if use_parallel:
            self._run_parallel(
                tasks,
                context,
                workers=workers,
                num_sound=num_sound,
                num_lesion=num_lesion,
                detection_method=detection_method,
            )
        else:
            self._run_sequential(
                tasks,
                context,
                num_sound=num_sound,
                num_lesion=num_lesion,
                detection_method=detection_method,
            )

        # Anything still open (cancelled before its slices resolved) closes here.
        for state in states:
            if not state.finalized:
                self._finalize(state, context)
        return results

    def _build_queue(self, specimens: Iterable) -> tuple[list[_SpecimenState], list[_SliceTask]]:
        """Flatten every specimen into one queue of slice tasks."""
        states: list[_SpecimenState] = []
        tasks: list[_SliceTask] = []
        for specimen in specimens:
            key = len(states)
            states.append(
                _SpecimenState(
                    specimen=specimen,
                    specimen_id=getattr(specimen, "specimen_id", "?"),
                    total=specimen.slices,
                    remaining=specimen.slices,
                )
            )
            for slice_index in range(specimen.slices):
                region_config = None
                air_config = None
                if specimen.config:
                    region_config = specimen.config.regions.get(slice_index)
                    air_config = specimen.config.air.get(slice_index)
                tasks.append(
                    _SliceTask(
                        specimen_key=key,
                        slice_index=slice_index,
                        image_path=specimen.images[slice_index],
                        region_config=region_config,
                        air_config=air_config,
                    )
                )
        return states, tasks

    # ------------------------------------------------------------------
    # Execution strategies
    # ------------------------------------------------------------------
    def _run_parallel(
        self,
        tasks: list[_SliceTask],
        context: _RunContext,
        *,
        workers: int,
        num_sound: int,
        num_lesion: int,
        detection_method: str,
    ) -> None:
        """Stream every slice through one pool, keeping a bounded set in flight.

        Submitting all 7500-odd tasks of a large batch upfront would keep every
        Future -- and the ~1.4 MB slice result each one holds -- alive until the
        run ends, which is exactly the parent-side growth that saving and
        clearing per specimen is meant to avoid. A sliding window drops each
        Future as soon as its result has been stored, and has the side benefit
        that cancelling simply stops feeding the queue.
        """
        context.emit_status(f"Preparing {workers} workers for parallel processing...")
        window = max(workers * WINDOW_PER_WORKER, workers + 1)
        pending_tasks = iter(tasks)
        in_flight: dict = {}

        def submit_next() -> bool:
            """Submit one more task, returning False once the queue is drained."""
            task = next(pending_tasks, None)
            if task is None:
                return False
            future = executor.submit(
                self._worker_fn,
                task.slice_index,
                task.image_path,
                task.region_config,
                task.air_config,
                num_sound,
                num_lesion,
                detection_method,
            )
            in_flight[future] = task
            return True

        with self._executor_factory(max_workers=workers) as executor:
            context.emit_status(
                f"Processing {context.total_slices} slices with {workers} workers..."
            )
            while len(in_flight) < window and submit_next():
                pass

            while in_flight:
                done, _ = wait(list(in_flight), return_when=FIRST_COMPLETED)

                if context.check_cancelled():
                    context.emit_status("Cancelling... waiting for active slices to finish")
                    # Futures that have not started yet drop out immediately;
                    # the ones already running are collected below as usual.
                    for future in list(in_flight):
                        if future not in done and future.cancel():
                            self._on_slice_resolved(in_flight.pop(future), None, context)

                for future in done:
                    task = in_flight.pop(future, None)
                    if task is None:
                        continue
                    if future.cancelled():
                        payload = None
                    else:
                        try:
                            payload = future.result()
                        except Exception as exc:  # noqa: BLE001 - isolate worker failures
                            context.emit_error(f"Error on slice {task.slice_index + 1}: {exc}")
                            payload = None
                    self._on_slice_resolved(task, payload, context)

                if not context.cancelled:
                    while len(in_flight) < window and submit_next():
                        pass
        gc.collect()

    def _run_sequential(
        self,
        tasks: list[_SliceTask],
        context: _RunContext,
        *,
        num_sound: int,
        num_lesion: int,
        detection_method: str,
    ) -> None:
        """Run the same worker inline, for tiny batches or single-core hosts."""
        context.emit_status(f"Processing {context.total_slices} slices sequentially...")
        for task in tasks:
            if context.check_cancelled():
                break
            try:
                payload = self._worker_fn(
                    task.slice_index,
                    task.image_path,
                    task.region_config,
                    task.air_config,
                    num_sound,
                    num_lesion,
                    detection_method,
                )
            except Exception as exc:  # noqa: BLE001 - defensive per-slice guard
                context.emit_error(f"Error on slice {task.slice_index + 1}: {exc}")
                payload = None
            self._on_slice_resolved(task, payload, context)

    # ------------------------------------------------------------------
    # Result handling
    # ------------------------------------------------------------------
    def _on_slice_resolved(
        self,
        task: _SliceTask,
        payload: tuple | None,
        context: _RunContext,
    ) -> None:
        """Attribute one finished (or cancelled/failed) slice to its specimen."""
        state = context.states[task.specimen_key]
        state.remaining -= 1

        if payload is not None:
            result_idx, region_stats, surface, lesion_depth, error = payload
            if error:
                context.emit_error(f"Error on slice {result_idx + 1} of {state.specimen_id}")
            else:
                self._store(
                    context, state.specimen, result_idx, region_stats, surface, lesion_depth
                )
                state.processed += 1
                context.completed += 1
                if context.on_slice_done is not None:
                    context.on_slice_done(context.completed, context.total_slices)
                context.emit_status(f"Completed slice {result_idx + 1} of {state.specimen_id}")

        if state.remaining <= 0 and not state.finalized:
            self._finalize(state, context)

    def _store(self, context: _RunContext, specimen, idx, region_stats, surface, lesion_depth):
        """Hand one slice result to the saver, serialised if a lock was supplied."""
        if context.result_lock is not None:
            with context.result_lock:
                self._saver.store_slice_result(specimen, idx, region_stats, surface, lesion_depth)
        else:
            self._saver.store_slice_result(specimen, idx, region_stats, surface, lesion_depth)

    def _finalize(self, state: _SpecimenState, context: _RunContext) -> None:
        """Save a finished specimen, release its results and record its status.

        Clearing ``specimen.results`` here is what keeps parent memory flat: one
        specimen holds ~35 MB of slice results, so a 300-specimen batch would
        otherwise accumulate roughly 10 GB in the parent process. The save runs
        on the calling thread while the pool keeps computing later specimens.
        """
        state.finalized = True

        if context.save and state.processed > 0:
            context.emit_status(f"Saving results for {state.specimen_id}...")
            self._saver.save_results(state.specimen)
            self._saver.save_annotated_images(state.specimen)
            state.specimen.results.clear()
            state.saved = True
            gc.collect()

        if state.total == 0:
            status = "Cancelled" if context.cancelled else "Completed"
        elif state.processed >= state.total:
            status = "Completed"
        elif state.processed == 0:
            status = "Cancelled" if context.cancelled else "Failed"
        else:
            status = "Partial"

        state.status = status
        state.specimen.status = status
        result = SpecimenAnalysisResult(
            specimen_id=state.specimen_id,
            status=status,
            processed_count=state.processed,
            total_slices=state.total,
            saved=state.saved,
        )
        context.results.append(result)
        if context.on_specimen_done is not None:
            context.on_specimen_done(result)
