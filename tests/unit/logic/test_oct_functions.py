"""
Unit tests for app/logic/shared/oct_functions.py

Tests pure functions that don't require GUI components.
"""
import pytest
import numpy as np
from PIL import Image
from io import BytesIO
from zipfile import ZipFile

from app.logic.shared import oct_functions as octF


class TestOctToGV:
    """Tests for the octToGV function (complex to grayscale conversion)."""
    
    @pytest.mark.unit
    def test_octToGV_returns_correct_shape(self, sample_complex_bscan):
        """GIVEN a complex B-scan array, WHEN octToGV is called, THEN output shape matches input."""
        result = octF.octToGV(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='')
        assert result.shape == sample_complex_bscan.shape
    
    @pytest.mark.unit
    def test_octToGV_output_range(self, sample_complex_bscan):
        """GIVEN a complex B-scan, WHEN octToGV is called, THEN output is clipped to 0-255."""
        result = octF.octToGV(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='')
        assert result.min() >= 0
        assert result.max() <= 255
    
    @pytest.mark.unit
    def test_octToGV_with_advanced_filter(self, sample_complex_bscan):
        """GIVEN a complex B-scan, WHEN advancedFilter='selected', THEN dark speckles are filtered."""
        result_no_filter = octF.octToGV(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='')
        result_filtered = octF.octToGV(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='selected')
        
        # Filtered result should have fewer very dark pixels
        dark_pixels_no_filter = np.sum(result_no_filter < 50)
        dark_pixels_filtered = np.sum(result_filtered < 50)
        assert dark_pixels_filtered <= dark_pixels_no_filter
    
    @pytest.mark.unit
    def test_octToGV_db_range_affects_output(self, sample_complex_bscan):
        """GIVEN different dB ranges, WHEN octToGV is called, THEN outputs differ."""
        result_narrow = octF.octToGV(sample_complex_bscan, dBmin=40, dBmax=60, advancedFilter='')
        result_wide = octF.octToGV(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='')
        
        # Different dB ranges should produce different results
        assert not np.allclose(result_narrow, result_wide)


class TestSmooth:
    """Tests for the smooth function (MATLAB-style smoothing)."""
    
    @pytest.mark.unit
    def test_smooth_preserves_length(self):
        """GIVEN an array, WHEN smooth is called, THEN output length matches input."""
        data = np.random.randn(100)
        result = octF.smooth(data, SPAN=5)
        assert len(result) == len(data)
    
    @pytest.mark.unit
    def test_smooth_reduces_noise(self):
        """GIVEN noisy data, WHEN smooth is called, THEN variance is reduced."""
        np.random.seed(42)
        noisy_data = np.sin(np.linspace(0, 4*np.pi, 100)) + np.random.randn(100) * 0.5
        smoothed = octF.smooth(noisy_data, SPAN=7)
        
        # Smoothed data should have lower variance
        assert np.var(smoothed) < np.var(noisy_data)
    
    @pytest.mark.unit
    def test_smooth_with_span_1(self):
        """GIVEN SPAN=1, WHEN smooth is called, THEN output approximately equals input."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = octF.smooth(data, SPAN=1)
        np.testing.assert_array_almost_equal(result, data)


class TestInsertScale:
    """Tests for the insertScale function (scale bar insertion)."""
    
    @pytest.mark.unit
    def test_insertScale_returns_image(self, sample_grayscale_image, sample_xml_dict):
        """GIVEN an image and metadata, WHEN insertScale is called, THEN returns PIL Image."""
        result = octF.insertScale(
            img=sample_grayscale_image.copy(),
            scaleSize=500,
            xmlDict=sample_xml_dict,
            fontSize=20,
            imgSliceDir='XZ'
        )
        assert isinstance(result, Image.Image)
    
    @pytest.mark.unit
    def test_insertScale_preserves_size(self, sample_grayscale_image, sample_xml_dict):
        """GIVEN an image, WHEN insertScale is called, THEN image size is preserved."""
        original_size = sample_grayscale_image.size
        result = octF.insertScale(
            img=sample_grayscale_image.copy(),
            scaleSize=500,
            xmlDict=sample_xml_dict,
            fontSize=20,
            imgSliceDir='XZ'
        )
        assert result.size == original_size
    
    @pytest.mark.unit
    def test_insertScale_modifies_image(self, sample_grayscale_image, sample_xml_dict):
        """GIVEN an image, WHEN insertScale is called, THEN image content is modified."""
        original = sample_grayscale_image.copy()
        result = octF.insertScale(
            img=sample_grayscale_image.copy(),
            scaleSize=500,
            xmlDict=sample_xml_dict,
            fontSize=20,
            imgSliceDir='XZ'
        )
        # Images should differ (scale bar was added)
        assert np.array(result).sum() != np.array(original).sum()
    
    @pytest.mark.unit
    @pytest.mark.parametrize("slice_dir", ['XZ', 'YZ', 'XY'])
    def test_insertScale_handles_all_directions(self, sample_grayscale_image, sample_xml_dict, slice_dir):
        """GIVEN different slice directions, WHEN insertScale is called, THEN no errors occur."""
        result = octF.insertScale(
            img=sample_grayscale_image.copy(),
            scaleSize=500,
            xmlDict=sample_xml_dict,
            fontSize=20,
            imgSliceDir=slice_dir
        )
        assert isinstance(result, Image.Image)


class TestUnzipOCTData:
    """Tests for the unzipOCTData function."""
    
    @pytest.mark.unit
    def test_unzipOCTData_returns_zipfile(self, tmp_path):
        """GIVEN a valid zip file, WHEN unzipOCTData is called, THEN returns ZipFile object."""
        # Create a minimal zip file
        zip_path = tmp_path / "test.oct"
        with ZipFile(zip_path, 'w') as zf:
            zf.writestr('Header.xml', '<Ocity></Ocity>')
        
        result = octF.unzipOCTData(str(zip_path))
        assert isinstance(result, ZipFile)
        result.close()


class TestReadXMLContent:
    """Tests for the readXMLContent function."""
    
    @pytest.mark.unit
    def test_readXMLContent_parses_xml(self, tmp_path):
        """GIVEN a zip with XML, WHEN readXMLContent is called, THEN returns BeautifulSoup object."""
        from bs4 import BeautifulSoup
        
        zip_path = tmp_path / "test.oct"
        xml_content = '<?xml version="1.0"?><Ocity><Study>Test</Study></Ocity>'
        
        with ZipFile(zip_path, 'w') as zf:
            zf.writestr('Header.xml', xml_content)
        
        archive = ZipFile(zip_path, 'r')
        result = octF.readXMLContent(archive, 'Header.xml', 'xml')
        archive.close()
        
        assert isinstance(result, BeautifulSoup)
        assert result.find('Study').getText() == 'Test'


class TestGetXMLAttributes:
    """Tests for the getXMLAttributes function."""
    
    @pytest.mark.unit
    def test_getXMLAttributes_returns_dict(self, mock_oct_archive):
        """GIVEN valid XML content, WHEN getXMLAttributes is called, THEN returns dict."""
        xml_content = octF.readXMLContent(mock_oct_archive, 'Header.xml', 'xml')
        result = octF.getXMLAttributes(xml_content)
        
        assert isinstance(result, dict)
        mock_oct_archive.close()
    
    @pytest.mark.unit
    def test_getXMLAttributes_extracts_dimensions(self, mock_oct_archive):
        """GIVEN valid XML, WHEN getXMLAttributes is called, THEN dimensions are extracted."""
        xml_content = octF.readXMLContent(mock_oct_archive, 'Header.xml', 'xml')
        result = octF.getXMLAttributes(xml_content)
        
        assert 'dimX' in result
        assert 'dimY' in result
        assert 'dimZ' in result
        assert result['dimX'] == 512
        mock_oct_archive.close()
    
    @pytest.mark.unit
    def test_getXMLAttributes_extracts_data_type(self, mock_oct_archive):
        """GIVEN valid XML, WHEN getXMLAttributes is called, THEN dataType is extracted."""
        xml_content = octF.readXMLContent(mock_oct_archive, 'Header.xml', 'xml')
        result = octF.getXMLAttributes(xml_content)
        
        assert 'dataType' in result
        assert result['dataType'] == 'RawSpectraAndProcessedIntensity'
        mock_oct_archive.close()
    
    @pytest.mark.unit
    def test_getXMLAttributes_calculates_resize_factors(self, mock_oct_archive):
        """GIVEN valid XML, WHEN getXMLAttributes is called, THEN resize factors are calculated."""
        xml_content = octF.readXMLContent(mock_oct_archive, 'Header.xml', 'xml')
        result = octF.getXMLAttributes(xml_content)
        
        assert 'imgResizeFactorX' in result
        assert 'imgResizeFactorY' in result
        assert isinstance(result['imgResizeFactorX'], float)
        mock_oct_archive.close()


class TestGetXMLValue:
    """Tests for the getXMLvalue convenience function."""
    
    @pytest.mark.unit
    def test_getXMLvalue_extracts_single_value(self, tmp_path):
        """GIVEN a valid OCT file, WHEN getXMLvalue is called, THEN returns correct value."""
        zip_path = tmp_path / "test.oct"
        xml_content = """<?xml version="1.0"?>
<Ocity>
    <Image Type="Processed"/>
    <SizeReal>2.0
6.0
6.0</SizeReal>
    <SizePixel>512
512
128</SizePixel>
    <PixelSpacing>0.0039
0.0117
0.0469</PixelSpacing>
    <Study>TestStudy</Study>
    <ExperimentNumber>5</ExperimentNumber>
    <SpectrometerElements>2048</SpectrometerElements>
    <IntensityAveraging><AScans>4</AScans></IntensityAveraging>
    <DataFiles></DataFiles>
</Ocity>"""
        
        with ZipFile(zip_path, 'w') as zf:
            zf.writestr('Header.xml', xml_content)
        
        result = octF.getXMLvalue(str(zip_path), 'expNumber')
        assert result == 5


class TestGetXMLAttributesFallbacks:
    """Exercise the defensive fallback branches in getXMLAttributes."""

    @pytest.mark.unit
    def test_malformed_header_triggers_fallbacks(self, tmp_path):
        """GIVEN a malformed/old header, WHEN parsing, THEN safe fallbacks fire."""
        # SizeReal has only 2 entries (imgSizemmY index 2 -> IndexError fallback),
        # no IntensityAveraging tag (safe_nested_text AttributeError fallback),
        # a non-numeric Timestamp (datetime fallback -> 'Unknown'), and a
        # RawSpectral DataFile labelled 'RawSpectra' (Type mismatch -> attribute
        # fallback loop).
        xml = """<?xml version="1.0"?>
<Ocity>
    <Image Type="RawSpectra"/>
    <SizeReal>2.0
6.0</SizeReal>
    <SizePixel>512
512
128</SizePixel>
    <PixelSpacing>0.0039
0.0117
0.0469</PixelSpacing>
    <Study>S</Study>
    <SpectrometerElements>2048</SpectrometerElements>
    <Timestamp>notanumber</Timestamp>
    <BinaryToElectronCountScaling>1.0</BinaryToElectronCountScaling>
    <DataFiles>
        <DataFile Type="RawSpectra" ApoRegionEnd0="64" ScanRegionStart0="0" ScanRegionEnd0="512"/>
    </DataFiles>
</Ocity>"""
        zip_path = tmp_path / "old.oct"
        with ZipFile(zip_path, 'w') as zf:
            zf.writestr('Header.xml', xml)
        archive = ZipFile(zip_path, 'r')
        xml_content = octF.readXMLContent(archive, 'Header.xml', 'xml')
        result = octF.getXMLAttributes(xml_content)
        archive.close()

        assert result['imgSizemmY'] is None        # safe_split IndexError fallback
        assert result['aScanAv'] == 1              # safe_nested_text fallback default
        assert result['Acquisition_DateTime'] == 'Unknown'  # datetime fallback
        assert result['Napo'] == 64                # raw-datafile attribute fallback
        assert result['Nx'] == 512
        assert result['is3D'] is False


class TestCreateVideoImageFromRaw:
    """Tests for createVideoImageFromRaw (packed ARGB decode)."""

    @pytest.mark.unit
    def test_decodes_argb_to_rgb(self):
        x, z = 4, 4
        # Build a packed ARGB buffer: A=255, R=10, G=20, B=30 for every pixel.
        argb = (255 << 24) | (10 << 16) | (20 << 8) | 30
        data = np.full(x * z, argb, dtype=np.uint32).tobytes()

        buffer = BytesIO()
        with ZipFile(buffer, 'w') as zf:
            zf.writestr('data/VideoImage.data', data)
        buffer.seek(0)
        archive = ZipFile(buffer, 'r')

        xml_dict = {'videoImageX': x, 'videoImageZ': z}
        rgb = octF.createVideoImageFromRaw(xml_dict, archive)
        archive.close()

        assert rgb.shape == (x, z, 3)
        assert rgb.dtype == np.uint8
        assert tuple(rgb[0, 0]) == (10, 20, 30)


class TestCreateImageFromRawProcessed:
    """Tests for the Processed branch of createImageFromRaw."""

    @pytest.mark.unit
    def test_processed_branch_returns_uint8(self):
        dimY, dimX, dimZ = 1, 2, 2
        intensity = np.full(dimY * dimX * dimZ, 1112000000, dtype=np.int32).tobytes()

        buffer = BytesIO()
        with ZipFile(buffer, 'w') as zf:
            zf.writestr('data/Intensity.data', intensity)
        buffer.seek(0)
        archive = ZipFile(buffer, 'r')

        xml_dict = {'dimY': dimY, 'dimX': dimX, 'dimZ': dimZ}
        img = octF.createImageFromRaw(
            xml_dict, archive, dBmin=20, dBmax=80, selDataType='Processed',
            averaging='coherent', spectral=0, prefRaw=False, tukeySize=0.9,
            advancedFilter='', dispersion=('None', '0'),
        )
        archive.close()

        assert img.dtype == np.uint8
        assert img.ndim == 3


class TestOctToGVLegacy:
    """Tests for the legacy octToGV implementation."""

    @pytest.mark.unit
    def test_legacy_returns_clipped_output(self, sample_complex_bscan):
        result = octF.octToGV_legacy(sample_complex_bscan, dBmin=20, dBmax=80, advancedFilter='')
        assert result.min() >= 0 and result.max() <= 255

    @pytest.mark.unit
    def test_legacy_advanced_filter_runs(self):
        # Small array with some dark values (< 50) to exercise the outlier loop.
        bscan = np.ones((6, 6), dtype=np.complex128) * (10 + 0j)
        bscan[2, 2] = 1e6 + 0j  # one bright pixel so others fall below threshold
        result = octF.octToGV_legacy(bscan, dBmin=20, dBmax=80, advancedFilter='selected')
        assert result.shape == (6, 6)
