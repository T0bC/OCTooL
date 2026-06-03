"""
AnnoLyze Data Service

Pure file discovery and data (de)serialization for annotations, results, and
configs - no tkinter and no ``context`` dependency. Extracted from
AnnoLyze/data_io.py per the refactor plan (the old DataLoader/DataSaver read
panel state via ``context``; this layer takes plain data instead).

I/O methods raise on failure; the view decides how to surface errors.
"""
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from app.logic.annolyze.annotation_service import AnnotationService


class DataService:
    """Pure file discovery + annotation/results/config I/O (context-free)."""

    def __init__(self, annotation_service: Optional[AnnotationService] = None):
        self.annotation_service = annotation_service or AnnotationService()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def find_file(
        self,
        base_folder: Union[str, Path],
        pattern: str,
        sample_name: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Recursively find a file matching ``pattern`` under ``base_folder``.

        If ``sample_name`` is given, files whose name contains it are
        prioritized. Returns ``None`` if nothing matches.
        """
        base = Path(base_folder)
        matches = list(base.rglob(pattern))
        if not matches:
            return None
        if sample_name:
            prioritized = [f for f in matches if sample_name in f.name]
            if prioritized:
                return prioritized[0]
        return matches[0]

    def build_data_folder(
        self,
        sample_folder: Union[str, Path],
        operator: str,
        measurement: str,
    ) -> Path:
        """Return the ``Data_<operator>_<measurement>`` path under the sample folder."""
        return Path(sample_folder) / f"Data_{operator}_{measurement}"

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    def load_annotations(self, filepath: Union[str, Path]) -> Dict[int, List[dict]]:
        """Load annotations JSON and return ``{slice_index: [annotation_dict]}``."""
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        return self.annotation_service.deserialize_annotations(json_data)

    def save_annotations(
        self,
        slice_annotations: Dict[int, List[dict]],
        filepath: Union[str, Path],
    ) -> Path:
        """Serialize ``slice_annotations`` to ``filepath`` as JSON. Returns the path."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        json_data = self.annotation_service.serialize_slice_annotations(slice_annotations)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return path

    # ------------------------------------------------------------------
    # Results (CSV)
    # ------------------------------------------------------------------
    def load_results(self, filepath: Union[str, Path]) -> Tuple[List[str], List[List[str]]]:
        """
        Load a results CSV. Returns ``(headers, rows)``.

        Returns ``([], [])`` when the file is empty.
        """
        path = Path(filepath)
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            return [], []
        return rows[0], rows[1:]

    def save_results(
        self,
        headers: List[str],
        data: List[List],
        filepath: Union[str, Path],
    ) -> Path:
        """Write ``headers`` + ``data`` to a CSV at ``filepath``. Returns the path."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        return path

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def save_config(self, config: dict, filepath: Union[str, Path]) -> Path:
        """Write a config dict to ``filepath`` as JSON. Returns the path."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return path
