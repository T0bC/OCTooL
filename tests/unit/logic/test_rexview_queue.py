"""
Unit tests for app/logic/rexview/queue_service.py

Tests the QueueService business logic without GUI dependencies.
"""
import pytest
from app.logic.rexview.queue_service import QueueService, ValidationResult
from app.logic.rexview.models import QueueItem


class TestQueueServiceInit:
    """Tests for QueueService initialization."""
    
    @pytest.mark.unit
    def test_init_creates_service(self):
        """GIVEN nothing, WHEN QueueService is created, THEN it initializes correctly."""
        service = QueueService()
        assert service is not None
    
    @pytest.mark.unit
    def test_direction_mapping_exists(self):
        """GIVEN QueueService, WHEN accessing DIRECTION_TO_DIMENSION, THEN it contains expected keys."""
        service = QueueService()
        assert 'XZ' in service.DIRECTION_TO_DIMENSION
        assert 'YZ' in service.DIRECTION_TO_DIMENSION
        assert 'XY' in service.DIRECTION_TO_DIMENSION
    
    @pytest.mark.unit
    def test_valid_directions_list(self):
        """GIVEN QueueService, WHEN accessing VALID_DIRECTIONS, THEN it contains all directions."""
        service = QueueService()
        assert service.VALID_DIRECTIONS == ['XZ', 'YZ', 'XY']


class TestValidateItem:
    """Tests for QueueService.validate_item method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def valid_item(self):
        return QueueItem(
            name="test_file",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/file.oct',
        )
    
    @pytest.mark.unit
    def test_validate_valid_item(self, service, valid_item):
        """GIVEN valid item, WHEN validate_item, THEN is_valid is True."""
        result = service.validate_item(valid_item)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.unit
    def test_validate_returns_validation_result(self, service, valid_item):
        """GIVEN item, WHEN validate_item, THEN returns ValidationResult."""
        result = service.validate_item(valid_item)
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
    
    @pytest.mark.unit
    def test_validate_num_slices_exceeds_range(self, service):
        """GIVEN num_slices > available range, WHEN validate_item, THEN error."""
        item = QueueItem(
            name="test",
            first_slice=1,
            last_slice=10,
            db_min=20,
            db_max=80,
            num_slices=50,  # Exceeds range of 10
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/file.oct',
        )
        result = service.validate_item(item)
        assert result.is_valid is False
        assert any('num_slices' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_empty_file_path(self, service):
        """GIVEN empty file_path, WHEN validate_item, THEN error."""
        item = QueueItem(
            name="test",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='',
        )
        result = service.validate_item(item)
        assert result.is_valid is False
        assert any('file_path' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_single_slice_warning(self, service):
        """GIVEN num_slices=1, WHEN validate_item, THEN warning."""
        item = QueueItem(
            name="test",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=1,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/file.oct',
        )
        result = service.validate_item(item)
        assert result.is_valid is True
        assert any('1 slice' in w for w in result.warnings)


class TestCalculateNumSlices:
    """Tests for QueueService.calculate_num_slices method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.mark.unit
    def test_calculate_with_endpoints(self, service):
        """GIVEN range 1-10 with endpoints, WHEN calculate_num_slices, THEN returns 10."""
        result = service.calculate_num_slices(1, 10, include_endpoints=True)
        assert result == 10
    
    @pytest.mark.unit
    def test_calculate_without_endpoints(self, service):
        """GIVEN range 1-10 without endpoints, WHEN calculate_num_slices, THEN returns 9."""
        result = service.calculate_num_slices(1, 10, include_endpoints=False)
        assert result == 9
    
    @pytest.mark.unit
    def test_calculate_same_slice(self, service):
        """GIVEN same first and last, WHEN calculate_num_slices with endpoints, THEN returns 1."""
        result = service.calculate_num_slices(5, 5, include_endpoints=True)
        assert result == 1
    
    @pytest.mark.unit
    def test_calculate_large_range(self, service):
        """GIVEN large range, WHEN calculate_num_slices, THEN returns correct count."""
        result = service.calculate_num_slices(1, 1000, include_endpoints=True)
        assert result == 1000


class TestValidateEquidistantSlices:
    """Tests for QueueService.validate_equidistant_slices method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.mark.unit
    def test_validate_valid_equidistant(self, service):
        """GIVEN valid num_slices within range, WHEN validate, THEN is_valid."""
        result = service.validate_equidistant_slices(
            num_slices=25,
            first_slice=1,
            last_slice=100,
        )
        assert result.is_valid is True
    
    @pytest.mark.unit
    def test_validate_exceeds_range(self, service):
        """GIVEN num_slices > range, WHEN validate, THEN error with message."""
        result = service.validate_equidistant_slices(
            num_slices=50,
            first_slice=1,
            last_slice=10,
        )
        assert result.is_valid is False
        assert any('NumSlices' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_zero_slices(self, service):
        """GIVEN num_slices=0, WHEN validate, THEN error."""
        result = service.validate_equidistant_slices(
            num_slices=0,
            first_slice=1,
            last_slice=100,
        )
        assert result.is_valid is False
        assert any('positive' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_negative_slices(self, service):
        """GIVEN negative num_slices, WHEN validate, THEN error."""
        result = service.validate_equidistant_slices(
            num_slices=-5,
            first_slice=1,
            last_slice=100,
        )
        assert result.is_valid is False

    @pytest.mark.unit
    def test_validate_boundary_full_range(self, service):
        """GIVEN num_slices exactly equals inclusive range, WHEN validate, THEN is_valid."""
        result = service.validate_equidistant_slices(
            num_slices=100,
            first_slice=1,
            last_slice=100,
        )
        assert result.is_valid is True

    @pytest.mark.unit
    def test_validate_single_slice_range(self, service):
        """GIVEN first == last with num_slices=1, WHEN validate, THEN is_valid."""
        result = service.validate_equidistant_slices(
            num_slices=1,
            first_slice=5,
            last_slice=5,
        )
        assert result.is_valid is True


class TestGetDimensionKeyForDirection:
    """Tests for QueueService.get_dimension_key_for_direction method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.mark.unit
    def test_xz_returns_dimy(self, service):
        """GIVEN 'XZ', WHEN get_dimension_key, THEN returns 'dimY'."""
        assert service.get_dimension_key_for_direction('XZ') == 'dimY'
    
    @pytest.mark.unit
    def test_yz_returns_dimx(self, service):
        """GIVEN 'YZ', WHEN get_dimension_key, THEN returns 'dimX'."""
        assert service.get_dimension_key_for_direction('YZ') == 'dimX'
    
    @pytest.mark.unit
    def test_xy_returns_dimz(self, service):
        """GIVEN 'XY', WHEN get_dimension_key, THEN returns 'dimZ'."""
        assert service.get_dimension_key_for_direction('XY') == 'dimZ'
    
    @pytest.mark.unit
    def test_invalid_returns_none(self, service):
        """GIVEN invalid direction, WHEN get_dimension_key, THEN returns None."""
        assert service.get_dimension_key_for_direction('INVALID') is None


class TestUpdateSliceRange:
    """Tests for QueueService.update_slice_range method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.mark.unit
    def test_update_returns_dict(self, service):
        """GIVEN range, WHEN update_slice_range, THEN returns dict with keys."""
        result = service.update_slice_range(1, 100)
        assert 'first' in result
        assert 'last' in result
        assert 'num_slices' in result
    
    @pytest.mark.unit
    def test_update_calculates_correctly(self, service):
        """GIVEN range 10-50, WHEN update_slice_range, THEN calculates 41 slices."""
        result = service.update_slice_range(10, 50, include_endpoints=True)
        assert result['first'] == 10
        assert result['last'] == 50
        assert result['num_slices'] == 41


class TestReorderItems:
    """Tests for QueueService.reorder_items method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def sample_items(self):
        return [
            QueueItem(name=f"file_{i}", first_slice=1, last_slice=100, db_min=20, db_max=80,
                     num_slices=50, refractive_index=1.0, dispersion_coefficient=20,
                     slice_direction='XZ', data_type='Processed', status='in queue',
                     file_path=f'/path/file_{i}.oct')
            for i in range(5)
        ]
    
    @pytest.mark.unit
    def test_reorder_move_to_end(self, service, sample_items):
        """GIVEN items, WHEN move first to last, THEN order changes correctly."""
        result = service.reorder_items(sample_items, 0, 4)
        assert result[4].name == 'file_0'
        assert result[0].name == 'file_1'
    
    @pytest.mark.unit
    def test_reorder_move_to_start(self, service, sample_items):
        """GIVEN items, WHEN move last to first, THEN order changes correctly."""
        result = service.reorder_items(sample_items, 4, 0)
        assert result[0].name == 'file_4'
        assert result[1].name == 'file_0'
    
    @pytest.mark.unit
    def test_reorder_same_position(self, service, sample_items):
        """GIVEN items, WHEN move to same position, THEN order unchanged."""
        result = service.reorder_items(sample_items, 2, 2)
        assert [item.name for item in result] == [item.name for item in sample_items]
    
    @pytest.mark.unit
    def test_reorder_invalid_from_index(self, service, sample_items):
        """GIVEN invalid from_index, WHEN reorder, THEN raises IndexError."""
        with pytest.raises(IndexError):
            service.reorder_items(sample_items, 10, 0)
    
    @pytest.mark.unit
    def test_reorder_invalid_to_index(self, service, sample_items):
        """GIVEN invalid to_index, WHEN reorder, THEN raises IndexError."""
        with pytest.raises(IndexError):
            service.reorder_items(sample_items, 0, 10)


class TestAddItem:
    """Tests for QueueService.add_item method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def valid_item(self):
        return QueueItem(
            name="new_file",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/new.oct',
        )
    
    @pytest.mark.unit
    def test_add_to_empty_list(self, service, valid_item):
        """GIVEN empty list, WHEN add_item, THEN list has one item."""
        result, validation = service.add_item([], valid_item)
        assert len(result) == 1
        assert result[0].name == 'new_file'
        assert validation.is_valid is True
    
    @pytest.mark.unit
    def test_add_to_end(self, service, valid_item):
        """GIVEN list with items, WHEN add_item without position, THEN adds to end."""
        existing = [QueueItem(
            name="existing",
            first_slice=1, last_slice=50, db_min=20, db_max=80,
            num_slices=25, refractive_index=1.0, dispersion_coefficient=20,
            slice_direction='XZ', data_type='Processed', status='in queue',
            file_path='/path/existing.oct',
        )]
        result, _ = service.add_item(existing, valid_item)
        assert len(result) == 2
        assert result[1].name == 'new_file'
    
    @pytest.mark.unit
    def test_add_at_position(self, service, valid_item):
        """GIVEN list with items, WHEN add_item at position 0, THEN inserts at start."""
        existing = [QueueItem(
            name="existing",
            first_slice=1, last_slice=50, db_min=20, db_max=80,
            num_slices=25, refractive_index=1.0, dispersion_coefficient=20,
            slice_direction='XZ', data_type='Processed', status='in queue',
            file_path='/path/existing.oct',
        )]
        result, _ = service.add_item(existing, valid_item, position=0)
        assert result[0].name == 'new_file'
        assert result[1].name == 'existing'
    
    @pytest.mark.unit
    def test_add_invalid_item_returns_original(self, service):
        """GIVEN invalid item, WHEN add_item, THEN returns original list."""
        invalid_item = QueueItem(
            name="invalid",
            first_slice=1, last_slice=10, db_min=20, db_max=80,
            num_slices=100,  # Invalid: exceeds range
            refractive_index=1.0, dispersion_coefficient=20,
            slice_direction='XZ', data_type='Processed', status='in queue',
            file_path='/path/invalid.oct',
        )
        original = []
        result, validation = service.add_item(original, invalid_item)
        assert len(result) == 0
        assert validation.is_valid is False


class TestRemoveItem:
    """Tests for QueueService.remove_item method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def sample_items(self):
        return [
            QueueItem(name=f"file_{i}", first_slice=1, last_slice=100, db_min=20, db_max=80,
                     num_slices=50, refractive_index=1.0, dispersion_coefficient=20,
                     slice_direction='XZ', data_type='Processed', status='in queue',
                     file_path=f'/path/file_{i}.oct')
            for i in range(3)
        ]
    
    @pytest.mark.unit
    def test_remove_first(self, service, sample_items):
        """GIVEN items, WHEN remove index 0, THEN first item removed."""
        result = service.remove_item(sample_items, 0)
        assert len(result) == 2
        assert result[0].name == 'file_1'
    
    @pytest.mark.unit
    def test_remove_last(self, service, sample_items):
        """GIVEN items, WHEN remove last index, THEN last item removed."""
        result = service.remove_item(sample_items, 2)
        assert len(result) == 2
        assert result[-1].name == 'file_1'
    
    @pytest.mark.unit
    def test_remove_invalid_index(self, service, sample_items):
        """GIVEN invalid index, WHEN remove_item, THEN raises IndexError."""
        with pytest.raises(IndexError):
            service.remove_item(sample_items, 10)


class TestRemoveItems:
    """Tests for QueueService.remove_items method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def sample_items(self):
        return [
            QueueItem(name=f"file_{i}", first_slice=1, last_slice=100, db_min=20, db_max=80,
                     num_slices=50, refractive_index=1.0, dispersion_coefficient=20,
                     slice_direction='XZ', data_type='Processed', status='in queue',
                     file_path=f'/path/file_{i}.oct')
            for i in range(5)
        ]
    
    @pytest.mark.unit
    def test_remove_multiple(self, service, sample_items):
        """GIVEN items, WHEN remove indices [0, 2, 4], THEN those items removed."""
        result = service.remove_items(sample_items, [0, 2, 4])
        assert len(result) == 2
        assert result[0].name == 'file_1'
        assert result[1].name == 'file_3'
    
    @pytest.mark.unit
    def test_remove_empty_list(self, service, sample_items):
        """GIVEN items, WHEN remove empty list, THEN all items remain."""
        result = service.remove_items(sample_items, [])
        assert len(result) == 5


class TestGetItemsByStatus:
    """Tests for QueueService.get_items_by_status method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def mixed_status_items(self):
        items = []
        for i, status in enumerate(['in queue', 'exported', 'in queue', 'error', 'in queue']):
            items.append(QueueItem(
                name=f"file_{i}", first_slice=1, last_slice=100, db_min=20, db_max=80,
                num_slices=50, refractive_index=1.0, dispersion_coefficient=20,
                slice_direction='XZ', data_type='Processed', status=status,
                file_path=f'/path/file_{i}.oct'
            ))
        return items
    
    @pytest.mark.unit
    def test_filter_in_queue(self, service, mixed_status_items):
        """GIVEN mixed status items, WHEN filter 'in queue', THEN returns 3 items."""
        result = service.get_items_by_status(mixed_status_items, 'in queue')
        assert len(result) == 3
    
    @pytest.mark.unit
    def test_filter_exported(self, service, mixed_status_items):
        """GIVEN mixed status items, WHEN filter 'exported', THEN returns 1 item."""
        result = service.get_items_by_status(mixed_status_items, 'exported')
        assert len(result) == 1
    
    @pytest.mark.unit
    def test_filter_nonexistent_status(self, service, mixed_status_items):
        """GIVEN mixed status items, WHEN filter nonexistent status, THEN returns empty."""
        result = service.get_items_by_status(mixed_status_items, 'nonexistent')
        assert len(result) == 0


class TestUpdateItemStatus:
    """Tests for QueueService.update_item_status method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def item(self):
        return QueueItem(
            name="test_file",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/file.oct',
        )
    
    @pytest.mark.unit
    def test_update_status(self, service, item):
        """GIVEN item with status 'in queue', WHEN update to 'exported', THEN status changes."""
        result = service.update_item_status(item, 'exported')
        assert result.status == 'exported'
        assert item.status == 'in queue'  # Original unchanged
    
    @pytest.mark.unit
    def test_update_preserves_other_fields(self, service, item):
        """GIVEN item, WHEN update status, THEN other fields preserved."""
        result = service.update_item_status(item, 'exported')
        assert result.name == item.name
        assert result.first_slice == item.first_slice
        assert result.file_path == item.file_path


class TestCreateUpdatedItem:
    """Tests for QueueService.create_updated_item method."""
    
    @pytest.fixture
    def service(self):
        return QueueService()
    
    @pytest.fixture
    def item(self):
        return QueueItem(
            name="test_file",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/to/file.oct',
        )
    
    @pytest.mark.unit
    def test_update_single_field(self, service, item):
        """GIVEN item, WHEN update one field, THEN only that field changes."""
        result = service.create_updated_item(item, {'db_min': 30})
        assert result.db_min == 30
        assert result.db_max == item.db_max
    
    @pytest.mark.unit
    def test_update_multiple_fields(self, service, item):
        """GIVEN item, WHEN update multiple fields, THEN all change."""
        result = service.create_updated_item(item, {
            'first_slice': 10,
            'last_slice': 90,
            'num_slices': 40,
        })
        assert result.first_slice == 10
        assert result.last_slice == 90
        assert result.num_slices == 40
