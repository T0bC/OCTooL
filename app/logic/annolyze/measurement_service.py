"""
AnnoLyze Measurement Service

Pure value-transform logic for keybinding-driven data entry - no tkinter, no
sheet access. Extracted from AnnoLyze/key_binding_manager.py so the per-type
cell computations can be unit-tested headlessly.

Each transform takes the *current* cell value (as stored, a string) and returns
the *new* value to store. Parsing helpers raise ``ValueError`` on bad input.
"""
import string
from typing import List, Optional, Set

# Keys reserved by the annotation canvas (fit-curve / toggle overlays).
RESERVED_KEYS = ("f", "h")

# Categorical starts at -1 so the first press yields 0; ordinal starts at 0.
CATEGORICAL_START = -1
ORDINAL_START = 0
PERCENTAGE_STEP = 5
PERCENTAGE_MAX = 100


class MeasurementService:
    """Pure per-data-type cell value transforms and key filtering."""

    def apply_continuous(self, current_value, measured_value) -> Optional[str]:
        """
        Add ``measured_value`` to the (numeric) ``current_value``.

        Returns the formatted ``"%.2f"`` sum, or ``None`` if ``measured_value``
        is missing/invalid (matching the original no-op behavior).
        """
        if measured_value is None:
            return None
        try:
            measured = float(measured_value)
        except (ValueError, TypeError):
            return None
        try:
            current = float(current_value)
        except (ValueError, TypeError):
            current = 0.0
        return f"{current + measured:.2f}"

    def toggle_boolean(self, current_value) -> str:
        """Toggle a YES/NO boolean cell. Empty/falsey becomes 'YES'."""
        falsey = {"NO", "0", "FALSE", ""}
        return "YES" if str(current_value).strip().upper() in falsey else "NO"

    def increment_percentage(self, current_value, step: int = PERCENTAGE_STEP) -> str:
        """Increment a ``N%`` cell by ``step``, capped at 100%."""
        try:
            current = int(str(current_value).replace("%", "").strip())
        except (ValueError, TypeError):
            current = 0
        return f"{min(current + step, PERCENTAGE_MAX)}%"

    def increment_categorical(self, current_value) -> str:
        """Increment a categorical index; uninitialized cells become '0'."""
        try:
            current = int(current_value)
        except (ValueError, TypeError):
            current = CATEGORICAL_START
        return str(current + 1)

    def increment_ordinal(self, current_value) -> str:
        """Increment an ordinal score; uninitialized cells become '1'."""
        try:
            current = int(current_value)
        except (ValueError, TypeError):
            current = ORDINAL_START
        return str(current + 1)

    # ------------------------------------------------------------------
    # Manual entry parsing
    # ------------------------------------------------------------------
    def parse_integer(self, raw: str) -> int:
        """Parse a whole number. Raises ``ValueError`` on decimals/garbage."""
        raw = str(raw).strip()
        if "." in raw:
            raise ValueError("Please enter a whole number for Integer data.")
        return int(raw)

    def parse_float(self, raw: str) -> float:
        """Parse a float, accepting comma decimals. Raises ``ValueError`` on garbage."""
        return float(str(raw).strip().replace(",", "."))

    def parse_text(self, raw: str) -> str:
        """Return trimmed text."""
        return str(raw).strip()

    # ------------------------------------------------------------------
    # Keybinding helpers
    # ------------------------------------------------------------------
    def available_keys(
        self,
        used_keys: Optional[List[str]] = None,
        reserved: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Return lowercase ascii letters that are neither used nor reserved.

        ``used_keys`` are keys already bound to columns; ``reserved`` defaults
        to the canvas-reserved keys.
        """
        used = set(used_keys or [])
        reserved_set = set(reserved) if reserved is not None else set(RESERVED_KEYS)
        return [k for k in string.ascii_lowercase if k not in used and k not in reserved_set]

    def feature_from_annotation_id(self, annotation_id: Optional[str]) -> Optional[str]:
        """Extract the feature/label prefix from an annotation id like 'GAP_0'."""
        if not annotation_id:
            return None
        return annotation_id.split("_")[0]
