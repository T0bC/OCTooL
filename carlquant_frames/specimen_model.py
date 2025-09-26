# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 15:48:56 2025

@author: Tobias Meissner
"""

from dataclasses import dataclass
from pathlib import Path

@dataclass
class Specimen:
    specimen_id: str
    source: Path
    images: list[Path]
    slices: int
    regions: str
    status: str
    date: float
