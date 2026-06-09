"""
RexView Shared Validation.

Single source of truth for the core domain invariants used across the RexView logic layer. Pydantic models enforce these invariants strictly (raising on construction), while services reuse the same helper functions to build non-raising ValidationResult objects for the GUI. Keeps the rules defined in one place so both layers stay consistent.

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


from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of a non-raising validation operation.

    Attributes:
        is_valid: True when ``errors`` is empty.
        errors: Messages describing hard failures.
        warnings: Non-fatal advisories.
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# --- Core invariant helpers -------------------------------------------------
# Each helper returns an error message string when the invariant is violated,
# or ``None`` when it holds. Models raise on the message; services collect it.

def db_range_error(db_min: int, db_max: int) -> Optional[str]:
    """Return an error message if ``db_min`` is not less than ``db_max``."""
    if db_min >= db_max:
        return f"db_min ({db_min}) must be less than db_max ({db_max})"
    return None


def slice_order_error(
    first_slice: Optional[int],
    last_slice: Optional[int],
) -> Optional[str]:
    """Return an error message if ``first_slice`` exceeds ``last_slice``.

    When either bound is ``None`` the invariant is considered satisfied.
    """
    if first_slice is not None and last_slice is not None:
        if first_slice > last_slice:
            return (
                f"first_slice ({first_slice}) must be <= last_slice ({last_slice})"
            )
    return None


def num_slices_error(first_slice: int, last_slice: int, num_slices: int) -> Optional[str]:
    """Return an error message if ``num_slices`` exceeds the available range."""
    available_range = last_slice - first_slice + 1
    if num_slices > available_range:
        return (
            f"num_slices ({num_slices}) exceeds available range ({available_range})"
        )
    return None
