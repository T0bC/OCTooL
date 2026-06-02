"""
RexView Export Service

Pure business logic for OCT image export - no tkinter dependencies.
This service handles the core export pipeline logic extracted from execution_panel.py.
"""
from pathlib import Path
from typing import Callable, Optional, List, Tuple
import numpy as np
from PIL import Image
from scipy import ndimage
import gc

from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportProgress
from app.logic.shared.models import OCTMetadata
from utils import oct_functions as octF


class ExportService:
    """
    Pure business logic for OCT export operations.
    
    This service encapsulates all export logic without any GUI dependencies.
    It can be fully tested with pytest without requiring tkinter.
    """
    
    def __init__(self):
        self._cancelled = False
    
    def cancel(self):
        """Signal the export to stop."""
        self._cancelled = True
    
    def reset(self):
        """Reset the cancellation flag."""
        self._cancelled = False
    
    @property
    def is_cancelled(self) -> bool:
        """Check if export has been cancelled."""
        return self._cancelled
    
    def prepare_export(
        self, 
        params: SliceExportParams, 
        config: ExportConfig,
        metadata: OCTMetadata,
    ) -> dict:
        """
        Validate and prepare export parameters.
        
        Returns a dict with computed values needed for export.
        """
        # Determine which slices to process
        selected_slices = np.linspace(
            params.first_slice - 1,
            params.last_slice - 1,
            params.num_slices
        ).astype(int)
        
        # Determine slices to load based on direction
        if params.slice_direction == 'XZ':
            slices_to_load = selected_slices
        else:
            slices_to_load = np.linspace(
                0, 
                metadata.dim_y - 1, 
                metadata.dim_y
            ).astype(int)
        
        # Determine data type to use
        if (metadata.data_type == 'RawSpectraAndProcessedIntensity' and config.prefer_raw) or \
           metadata.data_type == 'RawSpectra':
            sel_data_type = 'Raw'
        else:
            sel_data_type = 'Processed'
        
        # Create export directory path
        export_dir = params.get_output_path(
            Path(params.file_path).parent,
            metadata.exp_number
        )
        
        return {
            'selected_slices': selected_slices,
            'slices_to_load': slices_to_load,
            'sel_data_type': sel_data_type,
            'export_dir': export_dir,
        }
    
    def load_image_stack(
        self,
        archive,
        metadata: OCTMetadata,
        params: SliceExportParams,
        config: ExportConfig,
        slices_to_load: np.ndarray,
        sel_data_type: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> np.ndarray:
        """
        Load and process the image stack from the OCT archive.
        
        This wraps oct_functions.createImageFromRaw with proper parameters.
        """
        xml_dict = metadata.to_xml_dict()
        
        return octF.createImageFromRaw(
            xmlDict=xml_dict,
            archive=archive,
            dBmin=params.db_min,
            dBmax=params.db_max,
            selDataType=sel_data_type,
            averaging=config.averaging,
            spectral=slices_to_load,
            prefRaw=config.prefer_raw,
            tukeySize=config.tukey_window_size,
            advancedFilter='selected' if config.advanced_filter else '',
            dispersion=params.dispersion,
            update_callback=progress_callback,
        )
    
    def process_slice(
        self,
        img_stack: np.ndarray,
        slice_idx: int,
        image_idx: int,
        params: SliceExportParams,
        config: ExportConfig,
        metadata: OCTMetadata,
    ) -> Image.Image:
        """
        Process a single slice from the image stack.
        
        Applies:
        - Slice extraction based on direction
        - Aspect ratio correction (resize)
        - Refractive index correction
        - Scale bar insertion (optional)
        
        Returns a PIL Image ready for saving.
        """
        img_stack = np.squeeze(img_stack)
        is_2d = img_stack.ndim == 2
        
        # Choose correct index depending on direction
        image_to_export = slice_idx if params.slice_direction == 'XZ' else image_idx
        
        # Extract image slice
        if is_2d:
            img = img_stack
        else:
            if params.slice_direction == 'XZ':
                img = img_stack[image_to_export, :, :]
            elif params.slice_direction == 'YZ':
                img = np.transpose(img_stack[:, :, image_to_export])
            elif params.slice_direction == 'XY':
                img = img_stack[:, image_to_export, :]
        
        # Apply resize if enabled
        if config.resize_enabled:
            resize_x = metadata.img_resize_factor_x
            resize_y = metadata.img_resize_factor_y
            
            if params.slice_direction == 'XZ':
                img = ndimage.zoom(img, zoom=(1, resize_x), order=0)
            elif params.slice_direction == 'YZ':
                img = ndimage.zoom(img, zoom=(1, resize_y), order=0)
            elif params.slice_direction == 'XY' or is_2d:
                img = ndimage.zoom(img, zoom=(resize_y, resize_x), order=0)
        
        # Apply refractive index correction
        if params.refractive_index != 1.0:
            img = ndimage.zoom(img, zoom=(params.refractive_index, 1), order=0)
        
        # Convert to PIL Image
        pil_img = Image.fromarray(img.astype(np.uint8))
        
        # Add scale bar if enabled
        if config.scale_enabled:
            xml_dict = metadata.to_xml_dict()
            pil_img = octF.insertScale(
                img=pil_img,
                scaleSize=config.scale_length_um,
                xmlDict=xml_dict,
                fontSize=config.scale_font_size,
                imgSliceDir=params.slice_direction,
            )
        
        return pil_img
    
    def calculate_dpi(
        self,
        image: Image.Image,
        params: SliceExportParams,
        metadata: OCTMetadata,
    ) -> Tuple[int, int]:
        """Calculate DPI from spatial dimensions for image metadata."""
        if params.slice_direction == 'XZ':
            dpi = (
                round(image.size[0] / metadata.img_size_mm_x) if metadata.img_size_mm_x else 72,
                round(image.size[1] / metadata.img_size_mm_z) if metadata.img_size_mm_z else 72,
            )
        elif params.slice_direction == 'YZ':
            dpi = (
                round(image.size[0] / metadata.img_size_mm_y) if metadata.img_size_mm_y else 72,
                round(image.size[1] / metadata.img_size_mm_z) if metadata.img_size_mm_z else 72,
            )
        else:  # XY
            dpi = (
                round(image.size[0] / metadata.img_size_mm_y) if metadata.img_size_mm_y else 72,
                round(image.size[1] / metadata.img_size_mm_x) if metadata.img_size_mm_x else 72,
            )
        return dpi
    
    def generate_export_filename(
        self,
        params: SliceExportParams,
        config: ExportConfig,
        metadata: OCTMetadata,
        slice_number: int,
        export_index: int,
    ) -> str:
        """Generate the filename for an exported slice."""
        return (
            f"{params.name}_{metadata.exp_number}_"
            f"#{slice_number + 1}_{export_index + 1:04d}{config.export_format}"
        )
    
    def add_exif_metadata(self, image: Image.Image, metadata: OCTMetadata) -> dict:
        """Create EXIF metadata for the exported image."""
        exif = image.getexif()
        # Add custom metadata as needed
        exif[0x9286] = f"OCT Export - {metadata.study_name}"
        return exif
    
    def export_single_slice(
        self,
        image: Image.Image,
        export_path: Path,
        dpi: Tuple[int, int],
        exif: dict,
    ) -> None:
        """Save a single processed slice to disk."""
        # Ensure grayscale mode
        image = image.convert(mode='L')
        image.save(export_path, dpi=dpi, resolution_unit=3, exif=exif)
    
    def export_video_image(
        self,
        archive,
        metadata: OCTMetadata,
        params: SliceExportParams,
        export_dir: Path,
    ) -> Optional[Path]:
        """
        Export the video/preview image from the OCT file.
        
        Returns the path to the exported image, or None if not available.
        """
        try:
            xml_dict = metadata.to_xml_dict()
            video_img_array = octF.createVideoImageFromRaw(
                xmlDict=xml_dict,
                archive=archive,
            )
            video_image = Image.fromarray(video_img_array)
            
            export_name = f"{params.name}_{metadata.exp_number}.jpg"
            export_path = export_dir.parent / export_name
            video_image.save(export_path, format='JPEG', resolution_unit=3)
            
            return export_path
        except Exception:
            return None
    
    def run_export(
        self,
        file_path: str,
        params: SliceExportParams,
        config: ExportConfig,
        progress_callback: Optional[Callable[[ExportProgress], None]] = None,
    ) -> List[Path]:
        """
        Execute the full export pipeline for a single OCT file.
        
        Args:
            file_path: Path to the OCT file
            params: Export parameters
            config: Export configuration
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of paths to exported files
        """
        self.reset()
        exported_files = []
        
        # Open archive and read metadata
        archive = octF.unzipOCTData(file_path)
        xml_content = octF.readXMLContent(archive, 'Header.xml', 'xml')
        xml_dict = octF.getXMLAttributes(xml_content)
        metadata = OCTMetadata.from_xml_dict(xml_dict)
        
        # Prepare export
        prep = self.prepare_export(params, config, metadata)
        prep['export_dir'].mkdir(parents=True, exist_ok=True)
        
        # Load image stack
        def load_callback(status: str):
            if progress_callback:
                progress_callback(ExportProgress(status=f"Loading: {status}"))
        
        img_stack = self.load_image_stack(
            archive=archive,
            metadata=metadata,
            params=params,
            config=config,
            slices_to_load=prep['slices_to_load'],
            sel_data_type=prep['sel_data_type'],
            progress_callback=load_callback,
        )
        
        # Process and export each slice
        selected_slices = prep['selected_slices']
        total_slices = len(selected_slices)
        
        for idx, slice_num in enumerate(selected_slices):
            if self.is_cancelled:
                break
            
            try:
                # Process slice
                processed_img = self.process_slice(
                    img_stack=img_stack,
                    slice_idx=idx,
                    image_idx=slice_num,
                    params=params,
                    config=config,
                    metadata=metadata,
                )
                
                # Calculate DPI and EXIF
                dpi = self.calculate_dpi(processed_img, params, metadata)
                exif = self.add_exif_metadata(processed_img, metadata)
                
                # Generate filename and save
                filename = self.generate_export_filename(
                    params, config, metadata, slice_num, idx
                )
                export_path = prep['export_dir'] / filename
                
                self.export_single_slice(processed_img, export_path, dpi, exif)
                exported_files.append(export_path)
                
                # Update progress
                if progress_callback:
                    progress_callback(ExportProgress(
                        current_slice=idx + 1,
                        total_slices=total_slices,
                        status=f"Exported: {idx + 1}/{total_slices}",
                    ))
                
                gc.collect()
                
            except Exception:
                continue  # Continue with other slices
        
        # Export video image
        self.export_video_image(archive, metadata, params, prep['export_dir'])
        
        # Cleanup
        archive.close()
        gc.collect()
        
        return exported_files
