"""
RexView File Discovery Service.

Pure business logic for OCT file discovery and metadata extraction — no tkinter
dependencies. Handles file scanning, metadata parsing, and queue entry creation
extracted from pick_files_panel.py.

Key contents:
- DiscoveryResult: Dataclass holding discovered files, count, and errors.
- FileDiscoveryService: Scans folders for .oct files and extracts metadata.
- scan_directory: Recursively searches a directory for OCT archives.
- extract_metadata: Parses Header.xml and returns FileMetadata with default settings.
- create_queue_item: Builds a QueueItem from discovered file metadata.

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


from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from pathlib import Path
import os
from fnmatch import fnmatch

from app.logic.rexview.models import QueueItem, FileMetadata, ExportSettings
from app.logic.rexview.validation import ValidationResult


@dataclass
class DiscoveryResult:
    """Result of a file discovery operation."""
    files: List[Path]
    total_found: int
    errors: List[str]


class FileDiscoveryService:
    """
    Pure business logic for OCT file discovery and metadata extraction.
    
    This service encapsulates all file discovery logic without any GUI
    dependencies. It can be fully tested with pytest without requiring tkinter.
    """
    
    # OCT file extension pattern
    OCT_PATTERN = '*.oct'
    
    # Default dB values by data type
    DEFAULT_DB_VALUES = {
        'Processed': {'min': 20, 'max': 80},
        'Raw': {'min': 30, 'max': 100},
        'RawSpectra': {'min': 30, 'max': 100},
        'RawSpectraAndProcessedIntensity': {'min': 30, 'max': 100},
    }
    
    # Special serial numbers with custom dispersion
    SPECIAL_SERIAL_DISPERSION = {
        'M00427924': -100,
    }
    
    # Default dispersion coefficient
    DEFAULT_DISPERSION = 20
    
    def __init__(
        self,
        xml_reader: Optional[Callable[[str, str], str]] = None,
        xml_dict_reader: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        """
        Initialize FileDiscoveryService.
        
        Args:
            xml_reader: Optional callable to read a single XML value from OCT files.
                       Signature: (file_path: str, key: str) -> str
                       If not provided, metadata extraction will require explicit values.
            xml_dict_reader: Optional callable to read the full XML metadata dict in
                       a single pass. Signature: (file_path: str) -> dict.
                       Preferred over xml_reader for performance, since it parses the
                       OCT header only once per file instead of once per key.
        """
        self._xml_reader = xml_reader
        self._xml_dict_reader = xml_dict_reader
    
    def scan_directory(
        self,
        folder_path: Path,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DiscoveryResult:
        """
        Scan a directory for OCT files.
        
        Args:
            folder_path: Path to directory to scan
            recursive: If True, scan subdirectories
            progress_callback: Optional callback(current, total) for progress updates
            
        Returns:
            DiscoveryResult with list of found files
        """
        oct_files = []
        errors = []
        
        try:
            folder_path = Path(folder_path)
            if not folder_path.exists():
                errors.append(f"Directory does not exist: {folder_path}")
                return DiscoveryResult(files=[], total_found=0, errors=errors)
            
            if not folder_path.is_dir():
                errors.append(f"Path is not a directory: {folder_path}")
                return DiscoveryResult(files=[], total_found=0, errors=errors)
            
            if recursive:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        if fnmatch(file, self.OCT_PATTERN):
                            oct_files.append(Path(root) / file)
            else:
                for file in folder_path.iterdir():
                    if file.is_file() and fnmatch(file.name, self.OCT_PATTERN):
                        oct_files.append(file)
            
            oct_files = sorted(oct_files)
            
        except PermissionError as e:
            errors.append(f"Permission denied: {e}")
        except Exception as e:
            errors.append(f"Error scanning directory: {e}")
        
        return DiscoveryResult(
            files=oct_files,
            total_found=len(oct_files),
            errors=errors,
        )
    
    def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate that a file is a valid OCT file.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            errors.append(f"File does not exist: {file_path}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        if not file_path.is_file():
            errors.append(f"Path is not a file: {file_path}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        if not fnmatch(file_path.name, self.OCT_PATTERN):
            errors.append(f"File does not have .oct extension: {file_path.name}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Check file size
        try:
            size = file_path.stat().st_size
            if size == 0:
                errors.append("File is empty")
            elif size < 1000:
                warnings.append("File is very small, may be corrupted")
        except Exception as e:
            warnings.append(f"Could not check file size: {e}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def extract_metadata(
        self,
        file_path: Path,
        data_type: Optional[str] = None,
        serial_number: Optional[str] = None,
        dim_x: Optional[int] = None,
        dim_y: Optional[int] = None,
        dim_z: Optional[int] = None,
    ) -> FileMetadata:
        """
        Extract metadata from an OCT file.
        
        If xml_reader was provided at init, it will be used to read values.
        Otherwise, explicit values must be provided.
        
        Args:
            file_path: Path to OCT file
            data_type: OCT data type (if not using xml_reader)
            serial_number: Device serial number (if not using xml_reader)
            dim_x: X dimension (if not using xml_reader)
            dim_y: Y dimension (if not using xml_reader)
            dim_z: Z dimension (if not using xml_reader)
            
        Returns:
            FileMetadata with extracted information
        """
        file_path = Path(file_path)
        file_name = file_path.stem
        
        # Prefer the single-pass dict reader: it parses the OCT header only once
        # per file instead of once per key, which is dramatically faster.
        if self._xml_dict_reader is not None:
            xml_dict = self._xml_dict_reader(str(file_path))
            data_type = data_type or xml_dict.get('dataType')
            serial_number = serial_number or xml_dict.get('Serialnumber')
            dim_x = dim_x or int(xml_dict.get('dimX') or 1)
            dim_y = dim_y or int(xml_dict.get('dimY') or 1)
            dim_z = dim_z or int(xml_dict.get('dimZ') or 1)
        elif self._xml_reader is not None:
            path_str = str(file_path)
            data_type = data_type or self._xml_reader(path_str, 'dataType')
            serial_number = serial_number or self._xml_reader(path_str, 'Serialnumber')
            dim_x = dim_x or int(self._xml_reader(path_str, 'dimX') or 1)
            dim_y = dim_y or int(self._xml_reader(path_str, 'dimY') or 1)
            dim_z = dim_z or int(self._xml_reader(path_str, 'dimZ') or 1)
        
        return FileMetadata(
            file_path=str(file_path),
            file_name=file_name,
            data_type=data_type or 'Processed',
            serial_number=serial_number,
            dim_x=dim_x or 1,
            dim_y=dim_y or 1,
            dim_z=dim_z or 1,
        )
    
    def get_default_db_values(self, data_type: str) -> Dict[str, int]:
        """
        Get default dB values for a data type.
        
        Args:
            data_type: OCT data type
            
        Returns:
            Dict with 'min' and 'max' keys
        """
        return self.DEFAULT_DB_VALUES.get(
            data_type,
            self.DEFAULT_DB_VALUES['Raw']
        )
    
    def get_dispersion_coefficient(self, serial_number: Optional[str]) -> int:
        """
        Get dispersion coefficient based on serial number.
        
        Args:
            serial_number: Device serial number
            
        Returns:
            Dispersion coefficient
        """
        if serial_number and serial_number in self.SPECIAL_SERIAL_DISPERSION:
            return self.SPECIAL_SERIAL_DISPERSION[serial_number]
        return self.DEFAULT_DISPERSION
    
    def parse_metadata_file(self, file_path: Path) -> Dict[str, ExportSettings]:
        """
        Parse a metadata sidecar file for export settings.
        
        The metadata file contains lines specifying view direction, slice range,
        and number of equidistant slices. Format: <VIEW>:<START-END>:<COUNT>:<RI>
        
        Args:
            file_path: Path to the metadata .txt file
            
        Returns:
            Dictionary mapping view keys (XZ, YZ, XY) to ExportSettings
            
        Raises:
            ValueError: If a line is incorrectly formatted
            RuntimeError: If the file cannot be read
        """
        export_settings = {}
        
        def parse_line(line: str) -> tuple:
            tokens = line.strip().split(":")
            tokens = [t.strip() for t in tokens if t.strip()]
            
            view = "XZ"
            range_str = None
            count = None
            ri = 1.0
            
            if len(tokens) == 1 and "-" in tokens[0]:
                range_str = tokens[0]
            elif len(tokens) == 2 and "-" in tokens[0]:
                range_str = tokens[0]
                try:
                    count = int(tokens[1])
                except ValueError:
                    ri = float(tokens[1])
            elif len(tokens) == 3 and "-" in tokens[1]:
                view = tokens[0].upper()
                range_str = tokens[1]
                count = int(tokens[2])
            elif len(tokens) == 4:
                view = tokens[0].upper()
                range_str = tokens[1]
                count = int(tokens[2])
                ri = float(tokens[3])
            else:
                raise ValueError(f"Unrecognized format in line: {line}")
            
            try:
                start, end = map(int, range_str.split("-"))
            except Exception:
                raise ValueError(f"Invalid range format: {range_str}")
            
            if count is None:
                count = end - start + 1
            
            return view, ExportSettings(
                start=start,
                end=end,
                num_equidistant_slices=count,
                refractive_index=ri,
            )
        
        try:
            file_path = Path(file_path)
            with open(file_path, "r") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    view, settings = parse_line(line)
                    export_settings[view] = settings
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to parse metadata file: {e}")
        
        return export_settings
    
    def get_sidecar_path(self, oct_file_path: Path) -> Path:
        """
        Get the path to the sidecar metadata file for an OCT file.
        
        Args:
            oct_file_path: Path to OCT file
            
        Returns:
            Path to sidecar .txt file
        """
        oct_file_path = Path(oct_file_path)
        return oct_file_path.parent / (oct_file_path.stem + ".txt")
    
    def get_default_export_settings(self, dim_y: int) -> Dict[str, ExportSettings]:
        """
        Get default export settings when no sidecar file exists.
        
        Args:
            dim_y: Y dimension (number of slices in XZ direction)
            
        Returns:
            Dictionary with default XZ export settings
        """
        return {
            "XZ": ExportSettings(
                start=1,
                end=dim_y,
                num_equidistant_slices=dim_y,
                refractive_index=1.0,
            )
        }
    
    def handle_metadata_parsing(
        self,
        sidecar_path: Path,
        dim_y: int,
        show_errors: bool = False,
    ) -> tuple:
        """
        Parse metadata file with fallback to defaults.
        
        Args:
            sidecar_path: Path to sidecar .txt file
            dim_y: Y dimension for default fallback
            show_errors: Whether to report errors (for UI callback)
            
        Returns:
            Tuple of (export_settings dict, error_message or None)
        """
        sidecar_path = Path(sidecar_path)
        
        if not sidecar_path.exists():
            error_msg = None
            if show_errors:
                error_msg = f"No metadata file found at:\n{sidecar_path}\n\nFalling back to full-range export (1 to {dim_y})."
            return self.get_default_export_settings(dim_y), error_msg
        
        try:
            settings = self.parse_metadata_file(sidecar_path)
            return settings, None
        except ValueError as ve:
            error_msg = None
            if show_errors:
                error_msg = f"Error parsing metadata file:\n{ve}\n\nUsing default range as fallback."
            return self.get_default_export_settings(dim_y), error_msg
        except RuntimeError as re:
            error_msg = None
            if show_errors:
                error_msg = f"Unable to read metadata file:\n{re}\n\nUsing default range as fallback."
            return self.get_default_export_settings(dim_y), error_msg
    
    def build_queue_items_for_file(
        self,
        file_path: Path,
        metadata: FileMetadata,
        export_settings: Dict[str, ExportSettings],
    ) -> List[QueueItem]:
        """
        Build queue items for a file based on metadata and export settings.
        
        Args:
            file_path: Path to OCT file
            metadata: Extracted file metadata
            export_settings: Export settings from sidecar or defaults
            
        Returns:
            List of QueueItem objects
        """
        db_values = self.get_default_db_values(metadata.data_type)
        disp_coeff = self.get_dispersion_coefficient(metadata.serial_number)
        
        items = []
        for direction, settings in export_settings.items():
            item = QueueItem(
                name=metadata.file_name,
                first_slice=settings.start,
                last_slice=settings.end,
                db_min=db_values['min'],
                db_max=db_values['max'],
                num_slices=settings.num_equidistant_slices,
                refractive_index=settings.refractive_index,
                dispersion_coefficient=disp_coeff,
                slice_direction=direction,
                data_type=metadata.data_type,
                status='in queue',
                file_path=str(file_path),
            )
            items.append(item)
        
        return items
    
    def process_file(
        self,
        file_path: Path,
        show_errors: bool = False,
    ) -> tuple:
        """
        Process a single OCT file and return queue items.
        
        This is the main entry point for processing a file, combining
        validation, metadata extraction, sidecar parsing, and queue item creation.
        
        Args:
            file_path: Path to OCT file
            show_errors: Whether to report errors
            
        Returns:
            Tuple of (list of QueueItem, error_message or None)
        """
        file_path = Path(file_path)
        
        # Validate file
        validation = self.validate_file(file_path)
        if not validation.is_valid:
            return [], validation.errors[0] if validation.errors else "Unknown error"
        
        # Extract metadata
        metadata = self.extract_metadata(file_path)
        
        # Get sidecar path and parse
        sidecar_path = self.get_sidecar_path(file_path)
        export_settings, error_msg = self.handle_metadata_parsing(
            sidecar_path,
            metadata.dim_y,
            show_errors,
        )
        
        # Build queue items
        items = self.build_queue_items_for_file(file_path, metadata, export_settings)
        
        return items, error_msg
    
    def process_directory(
        self,
        folder_path: Path,
        show_errors: bool = False,
        progress_callback: Optional[Callable[[int, int], bool]] = None,
    ) -> tuple:
        """
        Process all OCT files in a directory.
        
        Args:
            folder_path: Path to directory
            show_errors: Whether to report errors
            progress_callback: Optional callback(current, total) -> should_continue
            
        Returns:
            Tuple of (list of QueueItem, list of error messages)
        """
        discovery = self.scan_directory(folder_path)
        
        if discovery.errors:
            return [], discovery.errors
        
        if not discovery.files:
            return [], [f"No OCT files found in: {folder_path}"]
        
        all_items = []
        all_errors = []
        
        for i, file_path in enumerate(discovery.files):
            if progress_callback:
                should_continue = progress_callback(i + 1, discovery.total_found)
                if not should_continue:
                    break
            
            items, error = self.process_file(file_path, show_errors)
            all_items.extend(items)
            if error:
                all_errors.append(error)
        
        return all_items, all_errors
