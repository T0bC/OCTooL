"""
CarlQuant Analysis Service

Pure, tkinter-free business logic for the CarlQuant OCT analysis pipeline.

This service wraps the pure compute functions in ``CarlQuant.carl_quant_core``
(surface detection, region extraction, lesion-depth calculation) and exposes the
per-slice analysis pipeline that was previously embedded inside the UI/threading
orchestration of ``run_carl_quant``.

Layer rules (see REFACTOR-PLAN.md):
- No tkinter here. Long-running orchestration accepts a ``progress_callback``.
- Methods accept/return models, not widget references.
- I/O (saving results/images) stays with the caller; this service only computes.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
from PIL import Image

from CarlQuant.carl_quant_core import (
    detect_surface,
    extract_regions,
    calculate_lesion_depth,
)
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
