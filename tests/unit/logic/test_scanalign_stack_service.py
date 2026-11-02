"""
Unit tests for app/logic/scanalign/stack_service.py

Tests stack loading, filename parsing, geometry and comparison without GUI dependencies.
"""

from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image

from app.logic.rexview.export_service import ExportService
from app.logic.rexview.models import ExportConfig, SliceExportParams
from app.logic.scanalign.models import ScanGeometry
from app.logic.scanalign.stack_service import (
    build_geometry,
    compare_geometry,
    find_oct_file,
    find_slice_issues,
    list_stack_files,
    load_stack,
    parse_filename,
    read_header_metadata,
)
from app.logic.shared.models import OCTMetadata

IMG_W, IMG_H = 100, 50

_HEADER_TAIL = """
    <Study>Test Study</Study>
    <ExperimentNumber>1</ExperimentNumber>
    <BinaryToElectronCountScaling>1.0</BinaryToElectronCountScaling>
    <DataFiles>
        <DataFile Type="RawSpectral" ApoRegionEnd0="64" ScanRegionStart0="0" ScanRegionEnd0="512"/>
        <DataFile Type="Colored" SizeZ="640" SizeX="480"/>
    </DataFiles>
</Ocity>
"""


def make_header(layout: str, dim_y: int = 700) -> str:
    """Header.xml in the plain (newline text) or child-tag layout.

    Real size: Z=2.0 mm, X=6.0 mm, Y=7.0 mm; spacing Y = 10 um.
    """
    if layout == "plain":
        body = (
            f"<SizeReal>2.0\n6.0\n7.0</SizeReal>\n"
            f"<SizePixel>1024\n2652\n{dim_y}</SizePixel>\n"
            f"<PixelSpacing>0.002\n0.0023\n0.01</PixelSpacing>"
        )
    else:
        body = (
            "<SizeReal>\n<SizeZ>2.0</SizeZ>\n<SizeX>6.0</SizeX>\n<SizeY>7.0</SizeY>\n</SizeReal>\n"
            f"<SizePixel>\n<SizeZ>1024</SizeZ>\n<SizeX>2652</SizeX>\n<SizeY>{dim_y}</SizeY>\n"
            "</SizePixel>\n"
            "<PixelSpacing>\n<SizeZ>0.002</SizeZ>\n<SizeX>0.0023</SizeX>\n<SizeY>0.01</SizeY>\n"
            "</PixelSpacing>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<Ocity>\n'
        '<Image Type="RawSpectraAndProcessedIntensity"/>\n' + body + _HEADER_TAIL
    )


def write_oct(path, layout="plain", dim_y=700):
    with ZipFile(path, "w") as zf:
        zf.writestr("Header.xml", make_header(layout, dim_y))
    return path


def save_image(path, value=0, dpi=None):
    arr = np.full((IMG_H, IMG_W), value, dtype=np.uint8)
    kwargs = {"dpi": dpi} if dpi else {}
    Image.fromarray(arr, mode="L").save(path, **kwargs)


def make_export_dir(tmp_path, name="010RI_0001_Mode3D", slices=(1, 2, 3), ext=".tiff"):
    """Create <tmp>/<specimen>/01_..._XZ with real RexView filenames."""
    folder = tmp_path / "010RI" / f"01_{name}_{len(slices)}_Slices_XZ"
    folder.mkdir(parents=True)
    for idx, s in enumerate(slices):
        save_image(folder / f"{name}_1_#{s}_{idx + 1:04d}{ext}", value=s)
    return folder


def geometry(**overrides):
    base = {
        "n_slices": 700,
        "width_px": 2652,
        "height_px": 1024,
        "px_size_x_um": 2.3,
        "px_size_z_um": 2.0,
        "slice_spacing_um": 10.0,
        "length_y_mm": 7.0,
        "header_dim_y": 700,
        "source": "header",
    }
    base.update(overrides)
    return ScanGeometry(**base)


class TestParseFilename:
    """Tests for parse_filename."""

    @pytest.fixture
    def generated(self, sample_xml_dict):
        service = ExportService()
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)

        def build(name, ext, slice_number, export_index):
            params = SliceExportParams(
                file_path="C:/data/test.oct",
                name=name,
                first_slice=1,
                last_slice=100,
                num_slices=10,
            )
            config = ExportConfig(export_format=".tiff" if ext == ".tiff" else ".png")
            filename = service.generate_export_filename(
                params, config, metadata, slice_number, export_index
            )
            # the service only emits .png/.tiff; swap for the .tif variant
            return filename.replace(".tiff", ext) if ext == ".tif" else filename

        return build

    @pytest.mark.unit
    @pytest.mark.parametrize("ext", [".png", ".tiff", ".tif"])
    def test_round_trip_with_underscored_name(self, generated, ext):
        """GIVEN a real generated filename with underscores in the name, WHEN parsed,
        THEN name, exp, slice and index round-trip."""
        filename = generated("010RI_0001_Mode3D", ext, 41, 0)
        assert parse_filename(filename) == ("010RI_0001_Mode3D", 1, 42, 1)

    @pytest.mark.unit
    def test_uppercase_extension(self):
        """GIVEN an uppercase extension, WHEN parsed, THEN it matches."""
        assert parse_filename("a_b_1_#5_0003.PNG") == ("a_b", 1, 5, 3)

    @pytest.mark.unit
    def test_unparsable_returns_none(self):
        """GIVEN a foreign filename, WHEN parsed, THEN None."""
        assert parse_filename("slice_001.png") is None


class TestListStackFiles:
    """Tests for list_stack_files."""

    @pytest.mark.unit
    def test_numeric_sort(self, tmp_path):
        """GIVEN slices #2 and #10, WHEN listed, THEN #2 comes before #10."""
        folder = make_export_dir(tmp_path, slices=(10, 2, 1))
        numbers = [f.slice_number for f in list_stack_files(folder)]
        assert numbers == [1, 2, 10]

    @pytest.mark.unit
    def test_ignores_non_images_and_subfolders(self, tmp_path):
        """GIVEN other files and a subfolder, WHEN listed, THEN only images appear."""
        folder = make_export_dir(tmp_path, slices=(1, 2))
        (folder / "notes.txt").write_text("x")
        (folder / "sub").mkdir()
        save_image(folder / "sub" / "x_1_#1_0001.png")
        assert len(list_stack_files(folder)) == 2

    @pytest.mark.unit
    def test_case_insensitive_extension(self, tmp_path):
        """GIVEN an uppercase .TIF file, WHEN listed, THEN it is included."""
        folder = tmp_path / "s" / "exp"
        folder.mkdir(parents=True)
        save_image(folder / "n_1_#1_0001.TIF")
        assert len(list_stack_files(folder)) == 1

    @pytest.mark.unit
    def test_natural_sort_fallback_with_warning(self, tmp_path):
        """GIVEN unparsable names, WHEN the stack is loaded, THEN natural order and a warning."""
        folder = tmp_path / "spec" / "exp"
        folder.mkdir(parents=True)
        for n in (10, 2, 1):
            save_image(folder / f"slice_{n}.png")
        files = list_stack_files(folder)
        assert [f.path.name for f in files] == ["slice_1.png", "slice_2.png", "slice_10.png"]
        assert all(f.slice_number is None for f in files)

        info = load_stack(folder)
        assert any("RexView pattern" in w for w in info.warnings)


class TestFindSliceIssues:
    """Tests for find_slice_issues."""

    @pytest.mark.unit
    def test_gaps_and_duplicates(self, tmp_path):
        """GIVEN missing and repeated slice numbers, WHEN analysed, THEN both are reported."""
        folder = make_export_dir(tmp_path, slices=(1, 2, 2, 5))
        # duplicates get unique export indices from make_export_dir, so names differ
        gaps, duplicates = find_slice_issues(list_stack_files(folder))
        assert gaps == [3, 4]
        assert duplicates == [2]

    @pytest.mark.unit
    def test_no_issues(self, tmp_path):
        """GIVEN a contiguous stack, WHEN analysed, THEN no issues."""
        folder = make_export_dir(tmp_path, slices=(1, 2, 3))
        assert find_slice_issues(list_stack_files(folder)) == ([], [])

    @pytest.mark.unit
    def test_warnings_summarize_at_most_five_numbers(self, tmp_path):
        """GIVEN many gaps, WHEN loaded, THEN the warning lists five numbers plus a remainder."""
        folder = make_export_dir(tmp_path, slices=(1, 12))
        info = load_stack(folder)
        warning = next(w for w in info.warnings if "Missing" in w)
        assert "(10)" in warning
        assert "2, 3, 4, 5, 6" in warning
        assert "(+5 more)" in warning


class TestLoadStackErrors:
    """Tests for load_stack failure and warning cases."""

    @pytest.mark.unit
    def test_empty_folder_raises(self, tmp_path):
        """GIVEN an empty folder, WHEN loaded, THEN ValueError."""
        with pytest.raises(ValueError, match="No PNG/TIFF images found"):
            load_stack(tmp_path)

    @pytest.mark.unit
    def test_mixed_extensions_warning(self, tmp_path):
        """GIVEN png and tiff files, WHEN loaded, THEN a mixed-extension warning."""
        folder = make_export_dir(tmp_path, slices=(1, 2))
        save_image(folder / "010RI_0001_Mode3D_1_#3_0003.png")
        info = load_stack(folder)
        assert any("Mixed file extensions" in w for w in info.warnings)


class TestFindOctFile:
    """Tests for find_oct_file."""

    @pytest.mark.unit
    def test_none_without_oct(self, tmp_path):
        """GIVEN no .oct, WHEN searching, THEN None."""
        folder = make_export_dir(tmp_path)
        assert find_oct_file(folder, "010RI_0001_Mode3D") is None

    @pytest.mark.unit
    def test_prefers_matching_stem(self, tmp_path):
        """GIVEN several .oct files, WHEN searching, THEN the one matching the name wins."""
        folder = make_export_dir(tmp_path)
        write_oct(tmp_path / "010RI" / "aaa_other.oct")
        wanted = write_oct(tmp_path / "010RI" / "010RI_0001_Mode3D.oct")
        assert find_oct_file(folder, "010RI_0001_Mode3D") == wanted

    @pytest.mark.unit
    def test_several_without_match_warns(self, tmp_path):
        """GIVEN several unrelated .oct files, WHEN loaded, THEN first is used, with a warning."""
        folder = make_export_dir(tmp_path)
        write_oct(tmp_path / "010RI" / "aaa.oct")
        write_oct(tmp_path / "010RI" / "bbb.oct")
        info = load_stack(folder)
        assert info.geometry.oct_path.name == "aaa.oct"
        assert any("Several .oct" in w for w in info.warnings)


class TestReadHeaderMetadata:
    """Tests for read_header_metadata."""

    @pytest.mark.unit
    @pytest.mark.parametrize("layout", ["plain", "child"])
    def test_reads_both_layouts(self, tmp_path, layout):
        """GIVEN either header layout, WHEN read, THEN sizes and spacing are parsed."""
        oct_path = write_oct(tmp_path / "scan.oct", layout)
        metadata = read_header_metadata(oct_path)
        assert metadata is not None
        assert metadata.img_size_mm_x == 6.0
        assert metadata.img_size_mm_y == 7.0
        assert metadata.img_size_mm_z == 2.0
        assert metadata.dim_y == 700
        assert metadata.spacing_y == pytest.approx(10.0)

    @pytest.mark.unit
    def test_corrupt_file_returns_none(self, tmp_path):
        """GIVEN a file that is not a zip, WHEN read, THEN None."""
        bad = tmp_path / "bad.oct"
        bad.write_bytes(b"not a zip")
        assert read_header_metadata(bad) is None


class TestBuildGeometry:
    """Tests for build_geometry and its use in load_stack."""

    @pytest.mark.unit
    @pytest.mark.parametrize("layout", ["plain", "child"])
    def test_header_geometry(self, tmp_path, layout):
        """GIVEN an .oct next to the export, WHEN loaded, THEN geometry comes from the header."""
        folder = make_export_dir(tmp_path)
        write_oct(tmp_path / "010RI" / "010RI_0001_Mode3D.oct", layout, dim_y=3)
        info = load_stack(folder)
        g = info.geometry

        assert g.source == "header"
        assert (g.width_px, g.height_px) == (IMG_W, IMG_H)
        assert g.n_slices == 3
        assert g.px_size_x_um == pytest.approx(6.0 * 1000 / IMG_W)
        assert g.px_size_z_um == pytest.approx(2.0 * 1000 / IMG_H)
        assert g.slice_spacing_um == pytest.approx(10.0)
        assert g.length_y_mm == 7.0
        assert g.header_dim_y == 3
        assert g.oct_path.name == "010RI_0001_Mode3D.oct"
        assert info.specimen == "010RI"
        assert info.name == "010RI_0001_Mode3D"
        assert info.exp_number == 1
        assert info.extension == ".tiff"
        assert not any("slices" in w for w in info.warnings)

    @pytest.mark.unit
    def test_subset_warning(self, tmp_path):
        """GIVEN fewer exported files than header dim_y, WHEN loaded, THEN a subset warning."""
        folder = make_export_dir(tmp_path)
        write_oct(tmp_path / "010RI" / "010RI_0001_Mode3D.oct", dim_y=700)
        info = load_stack(folder)
        assert "Export contains 3 of 700 slices" in info.warnings

    @pytest.mark.unit
    def test_dpi_fallback_without_oct(self, tmp_path):
        """GIVEN no .oct and image DPI 204, WHEN loaded, THEN px size is 1000/dpi (about 4.9 um)."""
        folder = make_export_dir(tmp_path)
        for f in folder.iterdir():
            save_image(f.with_suffix(".png"), dpi=(204, 204))
            f.unlink()
        info = load_stack(folder)
        g = info.geometry

        assert g.source == "dpi"
        assert g.px_size_x_um == pytest.approx(4.9, abs=0.05)
        assert g.px_size_z_um == pytest.approx(4.9, abs=0.05)
        assert g.slice_spacing_um is None
        assert g.length_y_mm is None
        assert any("No .oct file" in w for w in info.warnings)

    @pytest.mark.unit
    def test_source_none_without_dpi(self, tmp_path):
        """GIVEN no .oct and no DPI, WHEN loaded, THEN source is none."""
        folder = make_export_dir(tmp_path, ext=".png")
        info = load_stack(folder)
        assert info.geometry.source == "none"
        assert info.geometry.px_size_x_um is None

    @pytest.mark.unit
    def test_corrupt_oct_falls_back_with_warning(self, tmp_path):
        """GIVEN an unreadable .oct, WHEN loaded, THEN DPI/none fallback and a warning."""
        folder = make_export_dir(tmp_path)
        (tmp_path / "010RI" / "010RI_0001_Mode3D.oct").write_bytes(b"junk")
        info = load_stack(folder)
        assert info.geometry.source in ("dpi", "none")
        assert any("Could not read Header.xml" in w for w in info.warnings)

    @pytest.mark.unit
    def test_build_geometry_direct(self, tmp_path):
        """GIVEN metadata, WHEN build_geometry is called directly, THEN source is header."""
        folder = make_export_dir(tmp_path)
        files = list_stack_files(folder)
        metadata = read_header_metadata(write_oct(tmp_path / "x.oct"))
        g = build_geometry(files, metadata, files[0].path)
        assert g.source == "header"
        assert g.oct_path is None


class TestCompareGeometry:
    """Tests for compare_geometry."""

    @pytest.mark.unit
    def test_identical(self):
        """GIVEN equal geometry, WHEN compared, THEN identical with no differences."""
        result = compare_geometry(geometry(), geometry())
        assert result.kind == "identical"
        assert not any(result.differs.values())

    @pytest.mark.unit
    def test_wuerzburg_same_spacing_longer(self):
        """GIVEN 700 vs 900 slices with equal spacing, WHEN compared, THEN Scan 2 is longer."""
        g2 = geometry(n_slices=900, header_dim_y=900, length_y_mm=9.0)
        result = compare_geometry(geometry(), g2)

        assert result.kind == "same_spacing_longer"
        assert result.differs["n_slices"] is True
        assert result.differs["length_y_mm"] is True
        assert result.differs["slice_spacing_um"] is False
        assert "Scan 2" in result.verdict
        assert "2.0 mm" in result.verdict
        assert "+200" in result.verdict

    @pytest.mark.unit
    def test_scan1_longer_is_named(self):
        """GIVEN scan 1 longer, WHEN compared, THEN the verdict names Scan 1."""
        g1 = geometry(n_slices=900, length_y_mm=9.0)
        result = compare_geometry(g1, geometry())
        assert result.kind == "same_spacing_longer"
        assert "Scan 1" in result.verdict
        assert "+200" in result.verdict

    @pytest.mark.unit
    def test_same_length_denser(self):
        """GIVEN equal length but half the spacing in scan 2, WHEN compared, THEN denser."""
        g2 = geometry(n_slices=1400, slice_spacing_um=5.0)
        result = compare_geometry(geometry(), g2)
        assert result.kind == "same_length_denser"
        assert "Scan 2" in result.verdict

    @pytest.mark.unit
    def test_different(self):
        """GIVEN different spacing and length, WHEN compared, THEN different."""
        g2 = geometry(slice_spacing_um=20.0, length_y_mm=14.0, n_slices=700)
        assert compare_geometry(geometry(), g2).kind == "different"

    @pytest.mark.unit
    def test_different_when_only_pixel_size_differs(self):
        """GIVEN only the pixel size differing, WHEN compared, THEN different."""
        result = compare_geometry(geometry(), geometry(px_size_x_um=3.0))
        assert result.kind == "different"
        assert result.differs["px_size_x_um"] is True

    @pytest.mark.unit
    def test_unknown_when_spacing_missing(self):
        """GIVEN a DPI-based scan without spacing or length, WHEN compared, THEN unknown."""
        g2 = geometry(slice_spacing_um=None, length_y_mm=None, source="dpi")
        assert compare_geometry(geometry(), g2).kind == "unknown"

    @pytest.mark.unit
    def test_tolerance(self):
        """GIVEN values within 1 percent, WHEN compared, THEN they do not differ."""
        result = compare_geometry(geometry(), geometry(slice_spacing_um=10.05))
        assert result.differs["slice_spacing_um"] is False
        assert compare_geometry(
            geometry(), geometry(slice_spacing_um=10.05), rel_tol=0.001
        ).differs["slice_spacing_um"]

    @pytest.mark.unit
    def test_missing_value_does_not_count_as_difference(self):
        """GIVEN one missing pixel size, WHEN compared, THEN that key does not differ."""
        result = compare_geometry(geometry(), geometry(px_size_x_um=None))
        assert result.differs["px_size_x_um"] is False
