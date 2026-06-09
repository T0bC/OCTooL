"""
RexView Queue Service.

Pure business logic for export queue management — no tkinter dependencies.
Handles queue item validation, manipulation, and calculations extracted from
tree_view_panel.py.

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


from typing import Dict, List, Optional, Tuple, Any

from app.logic.rexview.models import QueueItem
from app.logic.rexview.validation import (
    ValidationResult,
    db_range_error,
    slice_order_error,
    num_slices_error,
)

__all__ = ['QueueService', 'ValidationResult']


class QueueService:
    """
    Stateless utility for export queue operations.
    
    This service encapsulates all queue management logic without any GUI
    dependencies. It holds no mutable state (construct once, call methods)
    and can be fully tested with pytest without requiring tkinter.
    """
    
    # Direction to dimension mapping
    DIRECTION_TO_DIMENSION = {
        'XZ': 'dimY',
        'YZ': 'dimX',
        'XY': 'dimZ',
    }
    
    # Valid slice directions
    VALID_DIRECTIONS = ['XZ', 'YZ', 'XY']
    
    def __init__(self):
        pass
    
    def validate_item(self, item: QueueItem) -> ValidationResult:
        """
        Validate a queue item's parameters.
        
        Args:
            item: QueueItem to validate
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        # Validate slice range (shared invariants - see app.logic.rexview.validation)
        slice_error = slice_order_error(item.first_slice, item.last_slice)
        if slice_error:
            errors.append(slice_error)
        
        # Validate dB range
        db_error = db_range_error(item.db_min, item.db_max)
        if db_error:
            errors.append(db_error)
        
        # Validate num_slices against range
        slices_error = num_slices_error(item.first_slice, item.last_slice, item.num_slices)
        if slices_error:
            errors.append(slices_error)
        
        # Validate slice direction
        if item.slice_direction not in self.VALID_DIRECTIONS:
            errors.append(f"Invalid slice_direction: {item.slice_direction}")
        
        # Validate refractive index
        if not (0.1 <= item.refractive_index <= 5.0):
            errors.append(f"refractive_index ({item.refractive_index}) must be between 0.1 and 5.0")
        
        # Validate file path is not empty
        if not item.file_path:
            errors.append("file_path cannot be empty")
        
        # Warnings
        if item.num_slices == 1:
            warnings.append("Only 1 slice will be exported")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def calculate_num_slices(
        self,
        first_slice: int,
        last_slice: int,
        include_endpoints: bool = True,
    ) -> int:
        """
        Calculate the number of slices in a range.
        
        Args:
            first_slice: First slice number (1-indexed)
            last_slice: Last slice number (1-indexed)
            include_endpoints: If True, includes both endpoints (last - first + 1)
                             If False, excludes last endpoint (last - first)
            
        Returns:
            Number of slices in the range
        """
        if include_endpoints:
            return last_slice - first_slice + 1
        else:
            return last_slice - first_slice
    
    def validate_equidistant_slices(
        self,
        num_slices: int,
        first_slice: int,
        last_slice: int,
    ) -> ValidationResult:
        """
        Validate that the requested number of equidistant slices fits in the range.
        
        Args:
            num_slices: Requested number of equidistant slices
            first_slice: First slice in range
            last_slice: Last slice in range
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        available_range = last_slice - first_slice + 1
        
        if num_slices <= 0:
            errors.append("num_slices must be positive")
        elif num_slices > available_range:
            errors.append(
                f"The input value for 'NumSlices' [{num_slices}] is larger than "
                f"the chosen export range [{available_range}]! "
                f"Please consider adapting the export range (First & Last) or the number of slices!"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def get_dimension_key_for_direction(self, direction: str) -> Optional[str]:
        """
        Get the XML dimension key for a slice direction.
        
        Args:
            direction: Slice direction ('XZ', 'YZ', 'XY')
            
        Returns:
            Dimension key ('dimX', 'dimY', 'dimZ') or None if invalid
        """
        return self.DIRECTION_TO_DIMENSION.get(direction)
    
    def update_slice_range(
        self,
        first_slice: int,
        last_slice: int,
        include_endpoints: bool = True,
    ) -> Dict[str, int]:
        """
        Calculate updated slice range values.
        
        Args:
            first_slice: First slice number
            last_slice: Last slice number
            include_endpoints: Whether to include endpoints in count
            
        Returns:
            Dict with 'first', 'last', and 'num_slices' keys
        """
        num_slices = self.calculate_num_slices(first_slice, last_slice, include_endpoints)
        return {
            'first': first_slice,
            'last': last_slice,
            'num_slices': num_slices,
        }
    
    def update_direction_for_item(
        self,
        current_item: QueueItem,
        new_direction: str,
        dimension_value: int,
    ) -> Dict[str, Any]:
        """
        Calculate updated values when changing slice direction.
        
        Args:
            current_item: Current queue item
            new_direction: New slice direction
            dimension_value: New dimension value for the direction
            
        Returns:
            Dict with updated 'slice_direction', 'last_slice', and 'num_slices'
        """
        return {
            'slice_direction': new_direction,
            'last_slice': dimension_value,
            'num_slices': dimension_value,
        }
    
    def create_updated_item(
        self,
        item: QueueItem,
        updates: Dict[str, Any],
    ) -> QueueItem:
        """
        Create a new QueueItem with updated values.
        
        Args:
            item: Original queue item
            updates: Dictionary of field updates
            
        Returns:
            New QueueItem with updates applied
        """
        item_dict = item.model_dump()
        item_dict.update(updates)
        return QueueItem(**item_dict)
    
    def validate_batch_update(
        self,
        items: List[QueueItem],
        updates: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate that a batch update can be applied to all items.
        
        Args:
            items: List of queue items to update
            updates: Dictionary of field updates
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        if not items:
            warnings.append("No items to update")
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)
        
        items_without_path = sum(1 for item in items if not item.file_path)
        if items_without_path > 0:
            warnings.append(f"{items_without_path} item(s) have no valid path")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def reorder_items(
        self,
        items: List[QueueItem],
        from_index: int,
        to_index: int,
    ) -> List[QueueItem]:
        """
        Reorder items in the queue by moving an item from one position to another.
        
        Args:
            items: List of queue items
            from_index: Current index of item to move
            to_index: Target index for the item
            
        Returns:
            New list with reordered items
            
        Raises:
            IndexError: If indices are out of bounds
        """
        if from_index < 0 or from_index >= len(items):
            raise IndexError(f"from_index {from_index} out of bounds")
        if to_index < 0 or to_index >= len(items):
            raise IndexError(f"to_index {to_index} out of bounds")
        
        result = list(items)
        item = result.pop(from_index)
        result.insert(to_index, item)
        return result
    
    def add_item(
        self,
        items: List[QueueItem],
        new_item: QueueItem,
        position: Optional[int] = None,
    ) -> Tuple[List[QueueItem], ValidationResult]:
        """
        Add an item to the queue with validation.
        
        Args:
            items: Current list of queue items
            new_item: Item to add
            position: Optional position to insert at (default: end)
            
        Returns:
            Tuple of (updated list, validation result)
        """
        validation = self.validate_item(new_item)
        
        if not validation.is_valid:
            return items, validation
        
        result = list(items)
        if position is None:
            result.append(new_item)
        else:
            result.insert(position, new_item)
        
        return result, validation
    
    def remove_item(
        self,
        items: List[QueueItem],
        index: int,
    ) -> List[QueueItem]:
        """
        Remove an item from the queue by index.
        
        Args:
            items: Current list of queue items
            index: Index of item to remove
            
        Returns:
            New list with item removed
            
        Raises:
            IndexError: If index is out of bounds
        """
        if index < 0 or index >= len(items):
            raise IndexError(f"index {index} out of bounds")
        
        result = list(items)
        result.pop(index)
        return result
    
    def remove_items(
        self,
        items: List[QueueItem],
        indices: List[int],
    ) -> List[QueueItem]:
        """
        Remove multiple items from the queue by indices.
        
        Args:
            items: Current list of queue items
            indices: List of indices to remove
            
        Returns:
            New list with items removed
        """
        indices_set = set(indices)
        return [item for i, item in enumerate(items) if i not in indices_set]
    
    def get_items_by_status(
        self,
        items: List[QueueItem],
        status: str,
    ) -> List[QueueItem]:
        """
        Filter items by status.
        
        Args:
            items: List of queue items
            status: Status to filter by
            
        Returns:
            List of items matching the status
        """
        return [item for item in items if item.status == status]
    
    def update_item_status(
        self,
        item: QueueItem,
        new_status: str,
    ) -> QueueItem:
        """
        Create a new item with updated status.
        
        Args:
            item: Original queue item
            new_status: New status value
            
        Returns:
            New QueueItem with updated status
        """
        return self.create_updated_item(item, {'status': new_status})
