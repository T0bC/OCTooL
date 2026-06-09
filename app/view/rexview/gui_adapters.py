"""
RexView GUI Adapters.

Pure conversion functions that bridge Tkinter widget states (strings, tuples,
checkbutton states) to typed logic-layer models. Keeps the view layer decoupled
from model construction details.

Key contents:
- settings_config_from_gui_state: Builds SettingsConfig from global/custom panel states.
- export_config_from_gui_state: Builds ExportConfig from global panel states.
- slice_export_params_from_treeview_row: Builds SliceExportParams from a TreeView row.
- queue_item_from_treeview_values: Builds QueueItem from raw TreeView cell values.
- image_display_config_from_gui_state: Builds ImageDisplayConfig for the preview canvas.

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

from typing import Optional, Tuple

from app.logic.rexview.models import (
    SettingsConfig,
    ExportConfig,
    SliceExportParams,
    QueueItem,
    ImageDisplayConfig,
)


def _parse_optional_slice(value: Optional[str], placeholder: str) -> Optional[int]:
    """Parse an optional slice entry, treating placeholders/blanks as ``None``."""
    if value and value not in (placeholder, ''):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def settings_config_from_gui_state(
    resize_state: str,
    prefer_raw_state: tuple,
    advanced_filter_state: str,
    export_format: str,
    averaging: str,
    tukey_size: str,
    error_state: str,
    scale_state: tuple,
    scale_length: str,
    scale_font_size: str,
    first_slice: Optional[str] = None,
    last_slice: Optional[str] = None,
    num_equidistant_slices: str = '25',
    db_min: int = 30,
    db_max: int = 100,
    dispersion_type: str = 'Quadratic',
    dispersion_coefficient: str = '-100',
    slice_direction: str = 'XZ',
    refractive_index: str = '1.0',
) -> SettingsConfig:
    """Build a :class:`SettingsConfig` from tkinter widget states."""
    return SettingsConfig(
        resize_enabled=resize_state == 'selected',
        prefer_raw=prefer_raw_state == ('selected',),
        advanced_filter=advanced_filter_state == 'selected',
        export_format=export_format,
        averaging=averaging,
        tukey_window_size=float(tukey_size),
        show_error=error_state == 'selected',
        scale_enabled=scale_state == ('selected',),
        scale_length_um=int(scale_length),
        scale_font_size=int(scale_font_size),
        first_slice=_parse_optional_slice(first_slice, 'First'),
        last_slice=_parse_optional_slice(last_slice, 'Last'),
        num_equidistant_slices=int(num_equidistant_slices),
        db_min=db_min,
        db_max=db_max,
        dispersion_type=dispersion_type,
        dispersion_coefficient=int(dispersion_coefficient),
        slice_direction=slice_direction,
        refractive_index=float(refractive_index),
    )


def export_config_from_gui_state(
    resize_state: str,
    prefer_raw_state: tuple,
    advanced_filter_state: str,
    export_format: str,
    averaging: str,
    tukey_size: str,
    scale_state: tuple,
    scale_length: str,
    scale_font_size: str,
    worker_count: Optional[int] = None,
) -> ExportConfig:
    """Build an :class:`ExportConfig` from tkinter widget states."""
    return ExportConfig(
        resize_enabled=resize_state == 'selected',
        prefer_raw=prefer_raw_state == ('selected',),
        advanced_filter=advanced_filter_state == 'selected',
        export_format=export_format,
        averaging=averaging,
        tukey_window_size=float(tukey_size),
        scale_enabled=scale_state == ('selected',),
        scale_length_um=int(scale_length),
        scale_font_size=int(scale_font_size),
        worker_count=worker_count,
    )


def slice_export_params_from_treeview_row(
    path: str,
    name: str,
    first: str,
    last: str,
    num_slices: str,
    slice_dir: str,
    db_min: str,
    db_max: str,
    refr_ind: str,
    dispersion: Tuple[str, str],
) -> SliceExportParams:
    """Build :class:`SliceExportParams` from TreeView row string values."""
    return SliceExportParams(
        file_path=path,
        name=name,
        first_slice=int(first),
        last_slice=int(last),
        num_slices=int(num_slices),
        slice_direction=slice_dir,
        db_min=int(db_min),
        db_max=int(db_max),
        refractive_index=float(refr_ind),
        dispersion=dispersion,
    )


def queue_item_from_treeview_values(
    name: str,
    first: str,
    last: str,
    db_min: str,
    db_max: str,
    num_slices: str,
    refr_ind: str,
    disp_coeff: str,
    slice_dir: str,
    data_type: str,
    status: str,
    path: str,
) -> QueueItem:
    """Build a :class:`QueueItem` from TreeView row string values."""
    return QueueItem(
        name=name,
        first_slice=int(first),
        last_slice=int(last),
        db_min=int(db_min),
        db_max=int(db_max),
        num_slices=int(num_slices),
        refractive_index=float(refr_ind),
        dispersion_coefficient=int(disp_coeff),
        slice_direction=slice_dir,
        data_type=data_type,
        status=status,
        file_path=path,
    )


def image_display_config_from_gui_state(
    slice_index: int,
    slice_direction: str,
    db_min: str,
    db_max: str,
    resize_state: str,
    refractive_index: str,
    scale_state: tuple,
    scale_length: str,
    scale_font_size: str,
    data_type: str,
    averaging: str,
    tukey_size: str,
    advanced_filter_state: str,
    dispersion: Tuple[str, str],
    canvas_width: int,
    canvas_height: int,
) -> ImageDisplayConfig:
    """Build an :class:`ImageDisplayConfig` from tkinter widget states."""
    return ImageDisplayConfig(
        slice_index=slice_index,
        slice_direction=slice_direction,
        db_min=int(db_min),
        db_max=int(db_max),
        resize_enabled=resize_state == 'selected',
        refractive_index=float(refractive_index),
        scale_enabled=scale_state == ('selected',),
        scale_length_um=int(scale_length),
        scale_font_size=int(scale_font_size),
        data_type=data_type,
        averaging=averaging,
        tukey_window_size=float(tukey_size),
        advanced_filter=advanced_filter_state == 'selected',
        dispersion=dispersion,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
