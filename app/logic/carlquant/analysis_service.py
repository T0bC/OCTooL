"""
CarlQuant Analysis Service

Pure, tkinter-free business logic for the CarlQuant OCT analysis pipeline.

This service wraps the pure compute functions in ``CarlQuant.carl_quant_core``
(surface detection, region extraction, lesion-depth calculation) and exposes the
per-slice analysis pipeline that was previously embedded inside the UI/threading
orchestration of ``run_carl_quant``.

Layer rules (see REFACTOR-PLAN.md):
- No tkinter here. Long-running orchestration accepts progress/cancel callbacks.
- Methods accept/return models, not widget references.
- File I/O (Excel/JSON/PNG) is delegated to the tkinter-free DataSaver; the view
  layer owns dialogs, threading and status-bar updates.
"""
from __future__ import annotations

import gc
import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
from PIL import Image

from CarlQuant.carl_quant_core import (
    detect_surface,
    extract_regions,
    calculate_lesion_depth,
    process_slice_parallel,
)
from CarlQuant.data_io import DataSaver
from app.logic.carlquant.models import (
    RegionStats,
    Surface,
    LesionDepth,
    DepthDetectionMethod,
)

# Defaults mirror the values used by run_carl_quant / process_slice_parallel.
DEFAULT_SEARCH_DEPTH = 200
DEFAULT_STABILITY_THRESHOLD = 20.0
DEFAULT_DETECTION_METHOD = "combined_mean"


@dataclass
class SliceAnalysis:
    """Result of analysing a single slice.

    ``lesion_depth`` is ``None`` when no region configuration is available
    (matching the legacy behaviour where depth is only computed for configured
    slices).
    """
    slice_index: int
    region_stats: List[RegionStats]
    surface: Surface
    lesion_depth: Optional[LesionDepth]


# Type alias for the progress callback used by long-running operations.
# Signature: (completed_slices, total_slices, current_slice_index) -> None
ProgressCallback = Callable[[int, int, int], None]


@dataclass
class SpecimenAnalysisResult:
    """Outcome of analysing a whole specimen.

    ``status`` is one of ``"Completed"``, ``"Partial"`` (cancelled after some
    slices) or ``"Cancelled"`` (cancelled before any slice finished).
    """
    specimen_id: str
    status: str
    processed_count: int
    total_slices: int
    saved: bool = False


class AnalysisService:
    """Stateless service exposing the CarlQuant compute pipeline."""

    # ------------------------------------------------------------------
    # Thin delegators to the pure core functions (single import location)
    # ------------------------------------------------------------------
    @staticmethod
    def detect_surface(image: np.ndarray, air_config=None, region_config=None) -> Surface:
        """Detect the specimen surface in an OCT image."""
        return detect_surface(image, air_config, region_config)

    @staticmethod
    def extract_regions(
        image: np.ndarray,
        surface: Surface,
        region_config,
        num_sound_regions: int = 6,
        num_lesion_regions: int = 6,
    ) -> List[RegionStats]:
        """Extract sound/lesion regions and their statistics."""
        return extract_regions(
            image,
            surface,
            region_config,
            num_sound_regions=num_sound_regions,
            num_lesion_regions=num_lesion_regions,
        )

    @staticmethod
    def calculate_lesion_depth(
        surface: Surface,
        region_config,
        image: np.ndarray,
        *,
        search_depth: int = DEFAULT_SEARCH_DEPTH,
        detection_method: DepthDetectionMethod = DepthDetectionMethod.COMBINED_MEAN,
        stability_threshold: float = DEFAULT_STABILITY_THRESHOLD,
        preserve_wobbliness: bool = True,
        slice_id: Optional[str] = None,
    ) -> LesionDepth:
        """Calculate lesion depth from a detected surface and region config."""
        return calculate_lesion_depth(
            surface,
            region_config,
            image,
            search_depth=search_depth,
            detection_method=detection_method,
            stability_threshold=stability_threshold,
            preserve_wobbliness=preserve_wobbliness,
            slice_id=slice_id,
        )

    # ------------------------------------------------------------------
    # Per-slice pipeline (extracted from process_slice_parallel)
    # ------------------------------------------------------------------
    @staticmethod
    def _dummy_region_stats(num_sound: int, num_lesion: int) -> List[RegionStats]:
        """Placeholder stats when no region configuration is present.

        Mirrors the legacy fallback used when a slice has no region config.
        """
        sound = [
            RegionStats(
                "sound",
                [random.randint(95, 105) for _ in range(100)],
                mean=100.0, median=100.0, sd=2.0, se=1.0,
            )
            for _ in range(num_sound)
        ]
        lesion = [
            RegionStats(
                "lesion",
                [random.randint(75, 85) for _ in range(100)],
                mean=80.0, median=80.0, sd=2.0, se=1.0,
            )
            for _ in range(num_lesion)
        ]
        return sound + lesion

    @classmethod
    def analyze_slice(
        cls,
        image: np.ndarray,
        region_config,
        air_config,
        *,
        num_sound: int = 6,
        num_lesion: int = 6,
        detection_method: str = DEFAULT_DETECTION_METHOD,
        slice_index: int = 0,
        slice_id: Optional[str] = None,
    ) -> SliceAnalysis:
        """Run the full per-slice pipeline on an in-memory image array.

        Returns a :class:`SliceAnalysis`. Lesion depth is computed only when a
        ``region_config`` is provided; otherwise placeholder region stats are
        returned and ``lesion_depth`` is ``None`` (legacy-compatible behaviour).
        """
        surface = cls.detect_surface(image, air_config, region_config)

        if region_config:
            region_stats = cls.extract_regions(
                image, surface, region_config,
                num_sound_regions=num_sound,
                num_lesion_regions=num_lesion,
            )
            method = DepthDetectionMethod(detection_method)
            name = slice_id if slice_id is not None else f"slice_{slice_index}"
            lesion_depth = cls.calculate_lesion_depth(
                surface, region_config, image,
                detection_method=method,
                slice_id=name,
            )
        else:
            region_stats = cls._dummy_region_stats(num_sound, num_lesion)
            lesion_depth = None

        return SliceAnalysis(
            slice_index=slice_index,
            region_stats=region_stats,
            surface=surface,
            lesion_depth=lesion_depth,
        )

    @classmethod
    def analyze_image(
        cls,
        image_path,
        region_config,
        air_config,
        *,
        num_sound: int = 6,
        num_lesion: int = 6,
        detection_method: str = DEFAULT_DETECTION_METHOD,
        slice_index: int = 0,
    ) -> SliceAnalysis:
        """Load a grayscale image from disk and run :meth:`analyze_slice`."""
        img = Image.open(image_path).convert("L")
        try:
            image = np.array(img)
        finally:
            img.close()
        slice_id = Path(image_path).stem if image_path else f"slice_{slice_index}"
        return cls.analyze_slice(
            image, region_config, air_config,
            num_sound=num_sound, num_lesion=num_lesion,
            detection_method=detection_method,
            slice_index=slice_index, slice_id=slice_id,
        )

    @classmethod
    def analyze_slices(
        cls,
        slice_tasks,
        *,
        num_sound: int = 6,
        num_lesion: int = 6,
        detection_method: str = DEFAULT_DETECTION_METHOD,
        progress_callback: Optional[ProgressCallback] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[SliceAnalysis]:
        """Analyse a sequence of slices sequentially.

        Args:
            slice_tasks: Iterable of ``(slice_index, image_path, region_config,
                air_config)`` tuples (images are loaded on demand).
            progress_callback: Optional ``(completed, total, slice_index)`` hook
                invoked after each slice (UI updates happen in the view layer).
            is_cancelled: Optional predicate; when it returns ``True`` the loop
                stops and returns the results gathered so far.

        Returns the list of :class:`SliceAnalysis` for processed slices.
        """
        tasks = list(slice_tasks)
        total = len(tasks)
        results: List[SliceAnalysis] = []
        for completed, (slice_index, image_path, region_config, air_config) in enumerate(tasks, start=1):
            if is_cancelled is not None and is_cancelled():
                break
            analysis = cls.analyze_image(
                image_path, region_config, air_config,
                num_sound=num_sound, num_lesion=num_lesion,
                detection_method=detection_method,
                slice_index=slice_index,
            )
            results.append(analysis)
            if progress_callback is not None:
                progress_callback(completed, total, slice_index)
        return results

    # ------------------------------------------------------------------
    # Whole-specimen pipeline (extracted from run_carl_quant)
    # ------------------------------------------------------------------
    @classmethod
    def analyze_specimen(
        cls,
        specimen,
        *,
        num_sound: int,
        num_lesion: int,
        detection_method: str = DEFAULT_DETECTION_METHOD,
        result_lock=None,
        save: bool = True,
        parallel_threshold: int = 10,
        max_workers: Optional[int] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_slice_done: Optional[Callable[[int, int], None]] = None,
        on_mode: Optional[Callable[[str, int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> SpecimenAnalysisResult:
        """Analyse every slice of a specimen, store and (optionally) save results.

        This is the pure, tkinter-free core extracted from ``run_carl_quant``.
        It chooses parallel (process pool) processing for large stacks and
        sequential processing otherwise, stores each slice via
        :class:`DataSaver`, optionally persists results/annotated images, then
        sets ``specimen.status``.

        All UI concerns are injected as optional callbacks:
        ``on_status(msg)`` for progress text, ``on_slice_done(completed_idx,
        total)`` for slice progress, ``on_mode(mode, workers)`` for the
        processing mode, ``on_error(msg)`` for per-slice errors, and
        ``is_cancelled()`` for cooperative cancellation.
        """
        def cancelled_now() -> bool:
            return is_cancelled is not None and is_cancelled()

        def emit_status(message: str) -> None:
            if on_status is not None:
                on_status(message)

        def store(idx, region_stats, surface, lesion_depth) -> None:
            if result_lock is not None:
                with result_lock:
                    DataSaver.store_slice_result(specimen, idx, region_stats, surface, lesion_depth)
            else:
                DataSaver.store_slice_result(specimen, idx, region_stats, surface, lesion_depth)

        # Build per-slice tasks (images loaded on demand).
        slice_tasks = []
        for slice_index in range(specimen.slices):
            image_path = specimen.images[slice_index]
            region_config = None
            air_config = None
            if specimen.config:
                region_config = specimen.config.regions.get(slice_index)
                air_config = specimen.config.air.get(slice_index)
            slice_tasks.append((slice_index, image_path, region_config, air_config))

        total = len(slice_tasks)
        workers = max_workers if max_workers is not None else max(1, multiprocessing.cpu_count() - 1)
        use_parallel = total > parallel_threshold and workers > 1
        processed_count = 0
        cancelled = False

        if use_parallel:
            effective_workers = min(workers, total)
            if on_mode is not None:
                on_mode("parallel", effective_workers)
            emit_status(f"Preparing {effective_workers} workers for parallel processing...")
            with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                emit_status(f"Processing {total} slices with {effective_workers} workers...")
                future_to_slice = {}
                for slice_idx, image_path, region_config, air_config in slice_tasks:
                    if cancelled_now():
                        cancelled = True
                        break
                    future = executor.submit(
                        process_slice_parallel,
                        slice_idx, image_path, region_config, air_config,
                        num_sound, num_lesion, detection_method,
                    )
                    future_to_slice[future] = slice_idx

                if cancelled:
                    for future in future_to_slice:
                        future.cancel()
                else:
                    for future in as_completed(future_to_slice):
                        if cancelled_now() and not cancelled:
                            cancelled = True
                            for pending in future_to_slice:
                                if not pending.done():
                                    pending.cancel()
                            emit_status("Cancelling... waiting for active slices to finish")
                        if future.cancelled():
                            continue
                        result_idx, region_stats, surface, lesion_depth, error = future.result()
                        if error:
                            if on_error is not None:
                                on_error(f"Error on slice {result_idx + 1}")
                            continue
                        store(result_idx, region_stats, surface, lesion_depth)
                        processed_count += 1
                        if on_slice_done is not None:
                            on_slice_done(processed_count - 1, total)
                        if not cancelled:
                            emit_status(f"Completed slice {result_idx + 1}")
            gc.collect()
        else:
            if on_mode is not None:
                on_mode("sequential", 1)
            emit_status(f"Processing {total} slices sequentially...")
            for slice_idx, image_path, region_config, air_config in slice_tasks:
                if cancelled_now():
                    cancelled = True
                    break
                try:
                    analysis = cls.analyze_image(
                        image_path, region_config, air_config,
                        num_sound=num_sound, num_lesion=num_lesion,
                        detection_method=detection_method, slice_index=slice_idx,
                    )
                    store(slice_idx, analysis.region_stats, analysis.surface, analysis.lesion_depth)
                    processed_count += 1
                    if on_slice_done is not None:
                        on_slice_done(slice_idx, total)
                    emit_status(f"Completed slice {slice_idx + 1}")
                except Exception as exc:  # pragma: no cover - defensive per-slice guard
                    if on_error is not None:
                        on_error(f"Error on slice {slice_idx + 1}: {exc}")

        # Persist results once all slices are processed (skip if nothing done).
        saved = False
        if save and (not cancelled or processed_count > 0):
            emit_status("Saving results and images to disc...")
            DataSaver.save_results(specimen)
            DataSaver.save_annotated_images(specimen)
            specimen.results.clear()
            gc.collect()
            saved = True

        if not cancelled:
            status = "Completed"
        elif processed_count == 0:
            status = "Cancelled"
        elif processed_count < total:
            status = "Partial"
        else:
            status = "Completed"
        specimen.status = status

        return SpecimenAnalysisResult(
            specimen_id=specimen.specimen_id,
            status=status,
            processed_count=processed_count,
            total_slices=total,
            saved=saved,
        )
