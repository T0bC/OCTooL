"""
CarlQuant Data Service

Pure, tkinter-free file/Excel/JSON I/O for CarlQuant: discovering image stacks,
loading/saving specimen configurations, results, and annotated images.

Wraps the loaders/savers in ``app.logic.carlquant.data_io`` (tkinter-free) and
exposes them from the logic layer's stable import location.
"""
from app.logic.carlquant.data_io import (
    DataLoader,
    DataSaver,
    convert_to_json_serializable,
    natural_key,
    IMAGE_EXTENSIONS,
)

__all__ = [
    "DataLoader",
    "DataSaver",
    "convert_to_json_serializable",
    "natural_key",
    "IMAGE_EXTENSIONS",
]
