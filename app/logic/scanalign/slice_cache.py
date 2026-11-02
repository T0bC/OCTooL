"""
ScanAlign Slice Cache.

Pure business logic (no tkinter) for scrolling large image stacks: a low-res
preview of every slice held in one numpy array plus an LRU of full-resolution
slices loaded on demand by background threads.

Key contents:
- choose_preview_factor / preview_budget_bytes: Preview memory sizing helpers.
- SliceCache: Thread-safe preview array and full-resolution LRU cache.

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
import logging
import math
import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from app.logic.shared.concurrency import Cancellable, compute_worker_count

logger = logging.getLogger(__name__)

_MB = 1024 * 1024
_MIN_BUDGET = 128 * _MB
_MAX_BUDGET = 512 * _MB
_DEFAULT_BUDGET = 256 * _MB


def choose_preview_factor(n: int, width: int, height: int, budget_bytes: int) -> int:
    """Smallest reduction factor ``f >= 2`` so ``n * ceil(w/f) * ceil(h/f) <= budget``."""
    factor = 2
    while n * math.ceil(width / factor) * math.ceil(height / factor) > budget_bytes:
        if factor >= max(width, height):
            break
        factor += 1
    return factor


def preview_budget_bytes(available_gb: float | None) -> int:
    """Preview memory budget: 10 % of available RAM clamped to 128-512 MB (256 MB if unknown)."""
    if available_gb is None:
        return _DEFAULT_BUDGET
    return int(max(_MIN_BUDGET, min(_MAX_BUDGET, 0.10 * available_gb * 1024**3)))


class SliceCache(Cancellable):
    """Thread-safe low-res preview array plus an LRU of full-resolution slices."""

    def __init__(
        self,
        files: list[Path],
        full_size: tuple[int, int],
        *,
        preview_factor: int,
        lru_capacity: int = 16,
        preview_workers: int | None = None,
    ) -> None:
        self._files = [Path(f) for f in files]
        self._full_size = (int(full_size[0]), int(full_size[1]))
        self._factor = max(1, int(preview_factor))
        self._capacity = max(1, int(lru_capacity))
        self._preview_workers = preview_workers
        n = len(self._files)
        w, h = self._full_size
        self._preview = np.zeros(
            (n, math.ceil(h / self._factor), math.ceil(w / self._factor)), dtype=np.uint8
        )
        self._loaded = np.zeros(n, dtype=bool)
        self._lru: OrderedDict[int, Image.Image] = OrderedDict()
        self._lock = threading.Lock()
        self._progress_lock = threading.Lock()
        self._done = 0
        self._closed = False
        # Generation counters: a newer request_full/prefetch supersedes queued older
        # ones, so fast scrolling does not build up a backlog of stale full-res loads.
        self._request_gen = 0
        self._prefetch_gen = 0
        self._preview_executor: ThreadPoolExecutor | None = None
        self._full_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-full")

    # -- preview ---------------------------------------------------------

    @property
    def preview_progress(self) -> tuple[int, int]:
        """``(processed, total)`` preview slices."""
        with self._progress_lock:
            return self._done, len(self._files)

    def start_preview(
        self,
        on_progress: Callable[[int, int], None] | None = None,
        on_done: Callable[[bool], None] | None = None,
    ) -> None:
        """Load all slices as downscaled previews in the background.

        ``on_progress(done, total)`` is called from worker threads; ``on_done(cancelled)``
        once after the last slice was processed (or skipped because of cancellation).
        """
        total = len(self._files)
        if self._closed:
            return
        if total == 0:
            if on_done:
                on_done(self.is_cancelled)
            return
        workers = self._preview_workers or compute_worker_count(total, max_workers_cap=4)
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scan-preview")
        self._preview_executor = executor
        with self._progress_lock:
            self._done = 0

        def work(i: int) -> None:
            if not self.is_cancelled:
                try:
                    with Image.open(self._files[i]) as img:
                        small = img.convert("L").reduce(self._factor)
                    arr = np.asarray(small, dtype=np.uint8)
                    rows = min(arr.shape[0], self._preview.shape[1])
                    cols = min(arr.shape[1], self._preview.shape[2])
                    self._preview[i, :rows, :cols] = arr[:rows, :cols]
                    self._loaded[i] = True
                except Exception:  # noqa: BLE001 - one bad slice must not stop the rest
                    logger.warning("Preview load failed for %s", self._files[i], exc_info=True)
            with self._progress_lock:
                self._done += 1
                done = self._done
            if on_progress and not self.is_cancelled:
                on_progress(done, total)
            if done == total and on_done:
                on_done(self.is_cancelled)

        try:
            for i in range(total):
                executor.submit(work, i)
        except RuntimeError:  # executor shut down by close()
            pass

    def get_preview(self, i: int) -> Image.Image | None:
        """Preview of slice ``i`` scaled to the full size (NEAREST), or None if not loaded."""
        if not (0 <= i < len(self._files)) or not self._loaded[i]:
            return None
        return Image.fromarray(self._preview[i]).resize(self._full_size, Image.NEAREST)

    # -- full resolution --------------------------------------------------

    def get_full_cached(self, i: int) -> Image.Image | None:
        """Full-res slice from the LRU, or None."""
        with self._lock:
            img = self._lru.get(i)
            if img is not None:
                self._lru.move_to_end(i)
            return img

    def get_full(self, i: int) -> Image.Image:
        """Load slice ``i`` synchronously (or from the LRU) and cache it."""
        cached = self.get_full_cached(i)
        if cached is not None:
            return cached
        with Image.open(self._files[i]) as img:
            img.load()
            loaded = img.copy()
        with self._lock:
            self._lru[i] = loaded
            self._lru.move_to_end(i)
            while len(self._lru) > self._capacity:
                self._lru.popitem(last=False)
        return loaded

    def request_full(self, i: int, callback: Callable[[int, Image.Image], None]) -> None:
        """Load slice ``i`` on the full-res executor; ``callback(i, image)`` runs on the worker.

        A request is skipped if a newer ``request_full`` was issued before it started.
        """
        self._request_gen += 1
        gen = self._request_gen

        def work() -> None:
            if self.is_cancelled or gen != self._request_gen:
                return
            try:
                img = self.get_full(i)
            except Exception:  # noqa: BLE001
                logger.warning("Full-res load failed for %s", self._files[i], exc_info=True)
                return
            if not self.is_cancelled:
                callback(i, img)

        self._submit_full(work)

    def prefetch(self, i: int, direction: int, count: int = 3) -> None:
        """Asynchronously load the next ``count`` slices in ``direction`` into the LRU.

        Superseded by a newer ``prefetch`` call: remaining targets are then skipped.
        """
        if direction == 0:
            return
        self._prefetch_gen += 1
        gen = self._prefetch_gen
        step = 1 if direction > 0 else -1
        targets = [
            i + step * k for k in range(1, count + 1) if 0 <= i + step * k < len(self._files)
        ]

        def work() -> None:
            for t in targets:
                if self.is_cancelled or gen != self._prefetch_gen:
                    return
                try:
                    self.get_full(t)
                except Exception:  # noqa: BLE001
                    logger.warning("Prefetch failed for %s", self._files[t], exc_info=True)

        if targets:
            self._submit_full(work)

    def _submit_full(self, fn: Callable[[], None]) -> None:
        if self._closed or self.is_cancelled:
            return
        with contextlib.suppress(RuntimeError):  # shut down concurrently
            self._full_executor.submit(fn)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Cancel pending work and shut down the executors. Idempotent."""
        self.cancel()
        self._closed = True
        if self._preview_executor is not None:
            self._preview_executor.shutdown(wait=False, cancel_futures=True)
        self._full_executor.shutdown(wait=False, cancel_futures=True)
