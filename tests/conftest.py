"""
Shared pytest fixtures for OCTooL tests.
"""
import pytest
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from io import BytesIO
from zipfile import ZipFile

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the test fixtures directory."""
    return PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def sample_oct_dir(fixtures_dir) -> Path:
    """Return the sample OCT files directory."""
    return fixtures_dir / "sample_oct_files"


# ============================================================================
# Image Fixtures
# ============================================================================

@pytest.fixture
def sample_grayscale_image() -> Image.Image:
    """Create a sample 256x256 grayscale image for testing."""
    arr = np.random.randint(0, 256, (256, 256), dtype=np.uint8)
    return Image.fromarray(arr, mode='L')


@pytest.fixture
def sample_image_array() -> np.ndarray:
    """Create a sample 256x256 numpy array for testing."""
    return np.random.randint(0, 256, (256, 256), dtype=np.uint8)


@pytest.fixture
def sample_3d_image_stack() -> np.ndarray:
    """Create a sample 3D image stack (10 slices of 256x256)."""
    return np.random.randint(0, 256, (10, 256, 256), dtype=np.uint8)


@pytest.fixture
def sample_complex_bscan() -> np.ndarray:
    """Create a sample complex B-scan array for octToGV testing."""
    # Create complex data similar to OCT spectral processing output
    real = np.random.randn(512, 256).astype(np.float32) * 1000
    imag = np.random.randn(512, 256).astype(np.float32) * 1000
    return real + 1j * imag


# ============================================================================
# XML/Metadata Fixtures
# ============================================================================

@pytest.fixture
def sample_xml_dict() -> dict:
    """Return a sample xmlDict structure matching OCT metadata format."""
    return {
        'xmlDataType': {'Type': 'RawSpectraAndProcessedIntensity'},
        'dataType': 'RawSpectraAndProcessedIntensity',
        'xmlPixelInfo': '2.0\n6.0\n6.0',
        'imgSizemmZ': 2.0,
        'imgSizemmX': 6.0,
        'imgSizemmY': 6.0,
        'pixelDimensions': '512\n512\n128',
        'dimZ': 512,
        'dimX': 512,
        'dimY': 128,
        'imgSize': (512, 128),
        'pixSizeZ': 6.0,
        'studyName': 'Test_Study',
        'expNumber': 1,
        'Nline': 2048,
        'Napo': 64,
        'Nx': 512,
        'offsScale': 1.0,
        'aScanAv': 4,
        'imgResizeFactorX': 1.0,
        'imgResizeFactorY': 1.0,
        'spacingZ': 3.9,
        'spacingX': 11.7,
        'spacingY': 46.9,
        'Modell': 'TEL220PSC2',
        'Serialnumber': 'TEST123',
        'Sensitivity': '76 kHz',
        'Probe_Name': 'OCT-LK4',
        'Wavelength': '1300',
        'Acquisition_DateTime': '2024-01-01 12:00:00',
        'Scan_Duration': 5.0,
        'Software_Version': '5.4.0',
        'is3D': True,
        'videoImageZ': 640,
        'videoImageX': 480,
    }


@pytest.fixture
def sample_xml_dict_2d(sample_xml_dict) -> dict:
    """Return a sample xmlDict for 2D (single B-scan) data."""
    xml_dict = sample_xml_dict.copy()
    xml_dict['dimY'] = 1
    xml_dict['imgSizemmY'] = None
    xml_dict['is3D'] = False
    return xml_dict


# ============================================================================
# Mock Archive Fixtures
# ============================================================================

@pytest.fixture
def mock_oct_archive(sample_xml_dict) -> ZipFile:
    """
    Create a minimal mock OCT archive in memory for testing.
    Contains Header.xml and minimal data files.
    """
    buffer = BytesIO()
    
    with ZipFile(buffer, 'w') as zf:
        # Create minimal Header.xml
        header_xml = """<?xml version="1.0" encoding="utf-8"?>
<Ocity>
    <Image Type="RawSpectraAndProcessedIntensity"/>
    <SizeReal>2.0
6.0
6.0</SizeReal>
    <SizePixel>512
512
128</SizePixel>
    <PixelSpacing>0.0039
0.0117
0.0469</PixelSpacing>
    <Study>Test Study</Study>
    <ExperimentNumber>1</ExperimentNumber>
    <SpectrometerElements>2048</SpectrometerElements>
    <IntensityAveraging><AScans>4</AScans></IntensityAveraging>
    <BinaryToElectronCountScaling>1.0</BinaryToElectronCountScaling>
    <Model>TEL220PSC2</Model>
    <Serial>TEST123</Serial>
    <Probe>OCT-LK4</Probe>
    <CentralWavelength>1300.5</CentralWavelength>
    <Timestamp>1704110400</Timestamp>
    <ScanTime>5.0</ScanTime>
    <OriginalSoftwareVer>5.4.0</OriginalSoftwareVer>
    <DataFiles>
        <DataFile Type="RawSpectral" ApoRegionEnd0="64" ScanRegionStart0="0" ScanRegionEnd0="512"/>
        <DataFile Type="Colored" SizeZ="640" SizeX="480"/>
    </DataFiles>
</Ocity>
"""
        zf.writestr('Header.xml', header_xml)
    
    buffer.seek(0)
    return ZipFile(buffer, 'r')


# ============================================================================
# Export Config Fixtures (for Phase 2+)
# ============================================================================

@pytest.fixture
def default_export_config() -> dict:
    """Return default export configuration values."""
    return {
        'resize_enabled': True,
        'prefer_raw': True,
        'advanced_filter': False,
        'export_format': '.tiff',
        'averaging': 'coherent',
        'tukey_window_size': 0.9,
        'scale_enabled': True,
        'scale_length_um': 500,
        'scale_font_size': 30,
    }


@pytest.fixture
def default_slice_params() -> dict:
    """Return default slice export parameters."""
    return {
        'file_path': '/path/to/file.oct',
        'name': 'TestScan',
        'first_slice': 1,
        'last_slice': 10,
        'num_slices': 5,
        'slice_direction': 'XZ',
        'db_min': 20,
        'db_max': 80,
        'refractive_index': 1.0,
        'dispersion': ('None', '0'),
    }
