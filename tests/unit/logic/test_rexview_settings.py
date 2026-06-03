"""
Unit tests for app/logic/rexview/settings_service.py

Tests the SettingsService business logic without GUI dependencies.
"""
import pytest
from app.logic.rexview.settings_service import SettingsService, ValidationResult
from app.logic.rexview.models import SettingsConfig


class TestSettingsServiceInit:
    """Tests for SettingsService initialization."""
    
    @pytest.mark.unit
    def test_init_creates_service(self):
        """GIVEN nothing, WHEN SettingsService is created, THEN it initializes correctly."""
        service = SettingsService()
        assert service is not None
    
    @pytest.mark.unit
    def test_defaults_dict_exists(self):
        """GIVEN SettingsService, WHEN accessing DEFAULTS, THEN it contains expected keys."""
        service = SettingsService()
        assert 'resize_enabled' in service.DEFAULTS
        assert 'export_format' in service.DEFAULTS
        assert 'dispersion_type' in service.DEFAULTS


class TestGetDefaults:
    """Tests for SettingsService.get_defaults method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_get_defaults_returns_settings_config(self, service):
        """GIVEN service, WHEN get_defaults is called, THEN returns SettingsConfig."""
        result = service.get_defaults()
        assert isinstance(result, SettingsConfig)
    
    @pytest.mark.unit
    def test_get_defaults_has_correct_values(self, service):
        """GIVEN service, WHEN get_defaults is called, THEN values match DEFAULTS dict."""
        result = service.get_defaults()
        assert result.resize_enabled == service.DEFAULTS['resize_enabled']
        assert result.export_format == service.DEFAULTS['export_format']
        assert result.db_min == service.DEFAULTS['db_min']
        assert result.db_max == service.DEFAULTS['db_max']
    
    @pytest.mark.unit
    def test_get_default_value_valid_setting(self, service):
        """GIVEN valid setting name, WHEN get_default_value, THEN returns correct value."""
        assert service.get_default_value('resize_enabled') is True
        assert service.get_default_value('export_format') == '.tiff'
        assert service.get_default_value('dispersion_coefficient') == -100
    
    @pytest.mark.unit
    def test_get_default_value_invalid_setting(self, service):
        """GIVEN invalid setting name, WHEN get_default_value, THEN raises KeyError."""
        with pytest.raises(KeyError, match="Unknown setting"):
            service.get_default_value('invalid_setting')


class TestValidateExportConfig:
    """Tests for SettingsService.validate_export_config method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.fixture
    def valid_config(self):
        return SettingsConfig()
    
    @pytest.mark.unit
    def test_validate_valid_config(self, service, valid_config):
        """GIVEN valid config, WHEN validate_export_config, THEN is_valid is True."""
        result = service.validate_export_config(valid_config)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.unit
    def test_validate_returns_validation_result(self, service, valid_config):
        """GIVEN config, WHEN validate_export_config, THEN returns ValidationResult."""
        result = service.validate_export_config(valid_config)
        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
    
    @pytest.mark.unit
    def test_validate_invalid_refractive_index_low(self, service):
        """GIVEN refractive_index < 0.1, WHEN validate, THEN error."""
        # Pydantic will reject this at creation, so we test the service validation
        # by creating a config that bypasses Pydantic validation
        config = SettingsConfig()
        # Manually set invalid value for testing service logic
        object.__setattr__(config, 'refractive_index', 0.05)
        result = service.validate_export_config(config)
        assert result.is_valid is False
        assert any('refractive_index' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_invalid_refractive_index_high(self, service):
        """GIVEN refractive_index > 5.0, WHEN validate, THEN error."""
        config = SettingsConfig()
        object.__setattr__(config, 'refractive_index', 6.0)
        result = service.validate_export_config(config)
        assert result.is_valid is False
        assert any('refractive_index' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_invalid_slice_range(self, service):
        """GIVEN first_slice > last_slice, WHEN validate, THEN error."""
        # Create config bypassing Pydantic validation using model_construct
        config = SettingsConfig.model_construct(
            resize_enabled=True,
            prefer_raw=True,
            advanced_filter=False,
            export_format='.tiff',
            averaging='coherent',
            tukey_window_size=0.9,
            show_error=False,
            scale_enabled=True,
            scale_length_um=500,
            scale_font_size=30,
            first_slice=10,
            last_slice=5,
            num_equidistant_slices=25,
            db_min=30,
            db_max=100,
            dispersion_type='Quadratic',
            dispersion_coefficient=-100,
            slice_direction='XZ',
            refractive_index=1.0,
        )
        result = service.validate_export_config(config)
        assert result.is_valid is False
        assert any('first_slice' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_scale_settings_when_enabled(self, service):
        """GIVEN scale_enabled with invalid scale_length, WHEN validate, THEN error."""
        config = SettingsConfig()
        object.__setattr__(config, 'scale_length_um', 0)
        result = service.validate_export_config(config)
        assert result.is_valid is False
        assert any('scale_length_um' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_warning_dispersion_ignored(self, service):
        """GIVEN dispersion_type=None with non-zero coefficient, WHEN validate, THEN warning."""
        config = SettingsConfig(dispersion_type='None', dispersion_coefficient=50)
        result = service.validate_export_config(config)
        assert any('ignored' in w.lower() for w in result.warnings)


class TestParseDispersion:
    """Tests for SettingsService.parse_dispersion method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_parse_valid_quadratic(self, service):
        """GIVEN valid Quadratic dispersion, WHEN parse_dispersion, THEN returns tuple."""
        result = service.parse_dispersion(('Quadratic', '-100'))
        assert result == ('Quadratic', -100)
    
    @pytest.mark.unit
    def test_parse_valid_none(self, service):
        """GIVEN valid None dispersion, WHEN parse_dispersion, THEN returns tuple."""
        result = service.parse_dispersion(('None', '0'))
        assert result == ('None', 0)
    
    @pytest.mark.unit
    def test_parse_positive_coefficient(self, service):
        """GIVEN positive coefficient, WHEN parse_dispersion, THEN returns correct value."""
        result = service.parse_dispersion(('Quadratic', '20'))
        assert result == ('Quadratic', 20)
    
    @pytest.mark.unit
    def test_parse_invalid_type(self, service):
        """GIVEN invalid dispersion type, WHEN parse_dispersion, THEN raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dispersion type"):
            service.parse_dispersion(('Linear', '50'))
    
    @pytest.mark.unit
    def test_parse_invalid_coefficient_string(self, service):
        """GIVEN non-numeric coefficient, WHEN parse_dispersion, THEN raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dispersion coefficient"):
            service.parse_dispersion(('Quadratic', 'abc'))
    
    @pytest.mark.unit
    def test_parse_coefficient_out_of_range_low(self, service):
        """GIVEN coefficient < -100, WHEN parse_dispersion, THEN raises ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            service.parse_dispersion(('Quadratic', '-150'))
    
    @pytest.mark.unit
    def test_parse_coefficient_out_of_range_high(self, service):
        """GIVEN coefficient > 100, WHEN parse_dispersion, THEN raises ValueError."""
        with pytest.raises(ValueError, match="out of range"):
            service.parse_dispersion(('Quadratic', '150'))


class TestValidateSliceRange:
    """Tests for SettingsService.validate_slice_range method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_validate_valid_range(self, service):
        """GIVEN valid slice range, WHEN validate_slice_range, THEN is_valid is True."""
        result = service.validate_slice_range(first_slice=1, last_slice=100, total_slices=128)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.unit
    def test_validate_first_equals_last(self, service):
        """GIVEN first_slice == last_slice, WHEN validate_slice_range, THEN is_valid."""
        result = service.validate_slice_range(first_slice=50, last_slice=50, total_slices=128)
        assert result.is_valid is True
    
    @pytest.mark.unit
    def test_validate_first_greater_than_last(self, service):
        """GIVEN first_slice > last_slice, WHEN validate_slice_range, THEN error."""
        result = service.validate_slice_range(first_slice=100, last_slice=50, total_slices=128)
        assert result.is_valid is False
        assert any('first_slice' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_first_less_than_one(self, service):
        """GIVEN first_slice < 1, WHEN validate_slice_range, THEN error."""
        result = service.validate_slice_range(first_slice=0, last_slice=50, total_slices=128)
        assert result.is_valid is False
        assert any('first_slice' in e and '>= 1' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_last_exceeds_total(self, service):
        """GIVEN last_slice > total_slices, WHEN validate_slice_range, THEN error."""
        result = service.validate_slice_range(first_slice=1, last_slice=150, total_slices=128)
        assert result.is_valid is False
        assert any('last_slice' in e and 'exceeds' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_first_exceeds_total(self, service):
        """GIVEN first_slice > total_slices, WHEN validate_slice_range, THEN error."""
        result = service.validate_slice_range(first_slice=150, last_slice=200, total_slices=128)
        assert result.is_valid is False
        assert any('first_slice' in e and 'exceeds' in e for e in result.errors)


class TestCalculateNumSlices:
    """Tests for SettingsService.calculate_num_slices method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_calculate_range(self, service):
        """GIVEN first and last slice, WHEN calculate_num_slices, THEN returns correct count."""
        assert service.calculate_num_slices(1, 10) == 10
        assert service.calculate_num_slices(5, 15) == 11
        assert service.calculate_num_slices(1, 1) == 1
    
    @pytest.mark.unit
    def test_calculate_large_range(self, service):
        """GIVEN large range, WHEN calculate_num_slices, THEN returns correct count."""
        assert service.calculate_num_slices(1, 1000) == 1000


class TestCalculateEquidistantIndices:
    """Tests for SettingsService.calculate_equidistant_indices method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_calculate_equidistant_basic(self, service):
        """GIVEN range 1-100 with 5 slices, WHEN calculate, THEN returns equidistant indices."""
        result = service.calculate_equidistant_indices(first_slice=1, last_slice=100, num_slices=5)
        assert len(result) == 5
        assert result[0] == 1
        assert result[-1] == 100
    
    @pytest.mark.unit
    def test_calculate_equidistant_single(self, service):
        """GIVEN num_slices=1, WHEN calculate, THEN returns middle index."""
        result = service.calculate_equidistant_indices(first_slice=1, last_slice=100, num_slices=1)
        assert len(result) == 1
        assert result[0] == 50  # Middle of 1-100
    
    @pytest.mark.unit
    def test_calculate_equidistant_zero(self, service):
        """GIVEN num_slices=0, WHEN calculate, THEN returns empty list."""
        result = service.calculate_equidistant_indices(first_slice=1, last_slice=100, num_slices=0)
        assert result == []
    
    @pytest.mark.unit
    def test_calculate_equidistant_more_than_range(self, service):
        """GIVEN num_slices > range, WHEN calculate, THEN returns all indices in range."""
        result = service.calculate_equidistant_indices(first_slice=1, last_slice=5, num_slices=10)
        assert len(result) == 5
        assert result == [1, 2, 3, 4, 5]
    
    @pytest.mark.unit
    def test_calculate_equidistant_two_slices(self, service):
        """GIVEN num_slices=2, WHEN calculate, THEN returns first and last."""
        result = service.calculate_equidistant_indices(first_slice=1, last_slice=100, num_slices=2)
        assert len(result) == 2
        assert result[0] == 1
        assert result[1] == 100


class TestValidateDbRange:
    """Tests for SettingsService.validate_db_range method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_validate_valid_range(self, service):
        """GIVEN valid dB range, WHEN validate_db_range, THEN is_valid is True."""
        result = service.validate_db_range(db_min=30, db_max=100)
        assert result.is_valid is True
    
    @pytest.mark.unit
    def test_validate_min_equals_max(self, service):
        """GIVEN db_min == db_max, WHEN validate_db_range, THEN error."""
        result = service.validate_db_range(db_min=50, db_max=50)
        assert result.is_valid is False
        assert any('less than' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_min_greater_than_max(self, service):
        """GIVEN db_min > db_max, WHEN validate_db_range, THEN error."""
        result = service.validate_db_range(db_min=80, db_max=50)
        assert result.is_valid is False
    
    @pytest.mark.unit
    def test_validate_min_out_of_range(self, service):
        """GIVEN db_min out of range, WHEN validate_db_range, THEN error."""
        result = service.validate_db_range(db_min=-10, db_max=100)
        assert result.is_valid is False
        assert any('db_min' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_max_out_of_range(self, service):
        """GIVEN db_max out of range, WHEN validate_db_range, THEN error."""
        result = service.validate_db_range(db_min=30, db_max=150)
        assert result.is_valid is False
        assert any('db_max' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_narrow_range_warning(self, service):
        """GIVEN narrow dB range, WHEN validate_db_range, THEN warning."""
        result = service.validate_db_range(db_min=45, db_max=55)
        assert any('narrow' in w.lower() for w in result.warnings)
    
    @pytest.mark.unit
    def test_validate_wide_range_warning(self, service):
        """GIVEN wide dB range, WHEN validate_db_range, THEN warning."""
        result = service.validate_db_range(db_min=0, db_max=120)
        assert any('wide' in w.lower() for w in result.warnings)


class TestGetDispersionRecommendation:
    """Tests for SettingsService.get_dispersion_recommendation method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_recommendation_1500nm(self, service):
        """GIVEN 1500nm wavelength, WHEN get_dispersion_recommendation, THEN returns -100."""
        assert service.get_dispersion_recommendation(1500) == -100
        assert service.get_dispersion_recommendation(1550) == -100
    
    @pytest.mark.unit
    def test_recommendation_1310nm(self, service):
        """GIVEN 1310nm wavelength, WHEN get_dispersion_recommendation, THEN returns 20."""
        assert service.get_dispersion_recommendation(1310) == 20
        assert service.get_dispersion_recommendation(1300) == 20
    
    @pytest.mark.unit
    def test_recommendation_other(self, service):
        """GIVEN other wavelength, WHEN get_dispersion_recommendation, THEN returns 0."""
        assert service.get_dispersion_recommendation(850) == 0
        assert service.get_dispersion_recommendation(1000) == 0


class TestMergeWithDefaults:
    """Tests for SettingsService.merge_with_defaults method."""
    
    @pytest.fixture
    def service(self):
        return SettingsService()
    
    @pytest.mark.unit
    def test_merge_empty_dict(self, service):
        """GIVEN empty dict, WHEN merge_with_defaults, THEN returns defaults."""
        result = service.merge_with_defaults({})
        assert result.resize_enabled == service.DEFAULTS['resize_enabled']
        assert result.export_format == service.DEFAULTS['export_format']
    
    @pytest.mark.unit
    def test_merge_partial_dict(self, service):
        """GIVEN partial dict, WHEN merge_with_defaults, THEN merges correctly."""
        result = service.merge_with_defaults({'export_format': '.png', 'db_min': 20})
        assert result.export_format == '.png'
        assert result.db_min == 20
        assert result.resize_enabled == service.DEFAULTS['resize_enabled']
    
    @pytest.mark.unit
    def test_merge_returns_settings_config(self, service):
        """GIVEN dict, WHEN merge_with_defaults, THEN returns SettingsConfig."""
        result = service.merge_with_defaults({})
        assert isinstance(result, SettingsConfig)


class TestSettingsConfigModel:
    """Tests for SettingsConfig Pydantic model."""
    
    @pytest.mark.unit
    def test_default_values(self):
        """GIVEN no arguments, WHEN creating SettingsConfig, THEN uses defaults."""
        config = SettingsConfig()
        assert config.resize_enabled is True
        assert config.export_format == '.tiff'
        assert config.db_min == 30
        assert config.db_max == 100
    
    @pytest.mark.unit
    def test_dispersion_property(self):
        """GIVEN config, WHEN accessing dispersion property, THEN returns tuple."""
        config = SettingsConfig(dispersion_type='Quadratic', dispersion_coefficient=-50)
        assert config.dispersion == ('Quadratic', '-50')
    
    @pytest.mark.unit
    def test_from_gui_state_basic(self):
        """GIVEN GUI state values, WHEN from_gui_state, THEN creates correct config."""
        config = SettingsConfig.from_gui_state(
            resize_state='selected',
            prefer_raw_state=('selected',),
            advanced_filter_state='',
            export_format='.png',
            averaging='incoherent',
            tukey_size='0.5',
            error_state='selected',
            scale_state=('selected',),
            scale_length='250',
            scale_font_size='24',
            first_slice='10',
            last_slice='50',
            num_equidistant_slices='15',
            db_min=25,
            db_max=95,
            dispersion_type='Quadratic',
            dispersion_coefficient='-80',
            slice_direction='YZ',
            refractive_index='1.4',
        )
        
        assert config.resize_enabled is True
        assert config.prefer_raw is True
        assert config.advanced_filter is False
        assert config.export_format == '.png'
        assert config.averaging == 'incoherent'
        assert config.tukey_window_size == 0.5
        assert config.show_error is True
        assert config.scale_enabled is True
        assert config.scale_length_um == 250
        assert config.scale_font_size == 24
        assert config.first_slice == 10
        assert config.last_slice == 50
        assert config.num_equidistant_slices == 15
        assert config.db_min == 25
        assert config.db_max == 95
        assert config.dispersion_type == 'Quadratic'
        assert config.dispersion_coefficient == -80
        assert config.slice_direction == 'YZ'
        assert config.refractive_index == 1.4
    
    @pytest.mark.unit
    def test_from_gui_state_placeholder_values(self):
        """GIVEN placeholder slice values, WHEN from_gui_state, THEN parses as None."""
        config = SettingsConfig.from_gui_state(
            resize_state='selected',
            prefer_raw_state=('selected',),
            advanced_filter_state='',
            export_format='.tiff',
            averaging='coherent',
            tukey_size='0.9',
            error_state='',
            scale_state=('selected',),
            scale_length='500',
            scale_font_size='30',
            first_slice='First',
            last_slice='Last',
        )
        
        assert config.first_slice is None
        assert config.last_slice is None
    
    @pytest.mark.unit
    def test_from_gui_state_unselected_states(self):
        """GIVEN unselected GUI states, WHEN from_gui_state, THEN booleans are False."""
        config = SettingsConfig.from_gui_state(
            resize_state='',
            prefer_raw_state=(),
            advanced_filter_state='',
            export_format='.tiff',
            averaging='coherent',
            tukey_size='0.9',
            error_state='',
            scale_state=(),
            scale_length='500',
            scale_font_size='30',
        )
        
        assert config.resize_enabled is False
        assert config.prefer_raw is False
        assert config.advanced_filter is False
        assert config.show_error is False
        assert config.scale_enabled is False
    
    @pytest.mark.unit
    def test_validation_db_range(self):
        """GIVEN db_min >= db_max, WHEN creating SettingsConfig, THEN raises ValueError."""
        with pytest.raises(ValueError, match="db_min"):
            SettingsConfig(db_min=80, db_max=50)
    
    @pytest.mark.unit
    def test_validation_slice_range(self):
        """GIVEN first_slice > last_slice, WHEN creating SettingsConfig, THEN raises ValueError."""
        with pytest.raises(ValueError, match="first_slice"):
            SettingsConfig(first_slice=100, last_slice=50)
