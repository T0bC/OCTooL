# CarlQuant Algorithm Testing Environment

This testing environment provides a standalone workspace for developing and testing the CarlQuant OCT analysis algorithms before integrating them into the main application.

## Overview

The testing environment consists of three main components:

1. **`test_carlquant_config.py`** - Test data configuration and loading
2. **`test_carlquant_algorithm.py`** - Algorithm development module
3. **`test_carlquant_viewer.py`** - Lightweight image viewer for visual testing

## Quick Start

### 1. Configure Test Data Paths

Edit `test_carlquant_config.py` and add paths to your test specimens:

```python
TEST_DATA_PATHS = [
    Path(r"W:\path\to\test\specimen1"),
    Path(r"W:\path\to\test\specimen2"),
]
```

**Important:** Your test specimens must have region and AIR configurations already defined using the main application. The configurations are stored in `Data_*/specimen_config.json` files.

### 2. Run the Test Viewer

```bash
python tests/test_carlquant_viewer.py
```

This opens a standalone GUI where you can:
- Load test specimens
- Navigate through image slices
- Run the algorithm on individual slices
- Visualize results with overlays

### 3. Develop Algorithms

Edit `test_carlquant_algorithm.py` to implement your algorithms:

```python
def detect_surface(image: np.ndarray, air_config: Optional[AirConfig] = None) -> Surface:
    """
    Implement your surface detection algorithm here.
    
    Steps:
    1. Use AIR region to determine threshold
    2. Find first non-air pixels in each column
    3. Apply smoothing/filtering
    4. Fit curves (polynomial, spline, etc.)
    """
    # Your implementation here
    pass
```

### 4. Test Incrementally

1. Implement one algorithm function (e.g., `detect_surface`)
2. Run the viewer and click "Run Algorithm"
3. Check visual results on your test images
4. Iterate and refine
5. Move to next function (e.g., `extract_regions`)

### 5. Port to Main Application

Once your algorithms work in the test environment, integrate them into `carlquant_frames/carl_quant_core.py`:

```python
def run_carl_quant(context):
    def worker():
        for specimen_id, specimen in context.specimen_data.items():
            for slice_index in range(specimen.slices):
                # Get configuration
                region_config = specimen.config.regions.get(slice_index)
                air_config = specimen.config.air.get(slice_index)
                
                # Load image
                img = Image.open(specimen.images[slice_index]).convert('L')
                image_array = np.array(img)
                
                # Run your algorithms (imported from test module or copied)
                surface = detect_surface(image_array, air_config)
                region_stats = extract_regions(image_array, surface, region_config, ...)
                lesion_depth = calculate_lesion_depth(surface, ...)
                
                # Store results
                DataSaver.store_slice_result(specimen, slice_index, region_stats, surface, lesion_depth)
```

## File Structure

```
tests/
├── test_carlquant_config.py      # Test data configuration
├── test_carlquant_algorithm.py   # Algorithm implementations
├── test_carlquant_viewer.py      # Visual testing GUI
└── README_CARLQUANT_TESTING.md   # This file
```

## Algorithm Functions to Implement

### Surface Detection
- `detect_surface()` - Main surface detection
- `calculate_air_threshold()` - Threshold from AIR region

### Region Extraction
- `extract_regions()` - Extract pixel values from regions
- `extract_region_pixels()` - Helper for pixel extraction

### Clustering
- `perform_clustering()` - Optional clustering analysis

### Lesion Depth
- `calculate_lesion_depth()` - Main depth calculation
- `detect_lesion_bottom()` - Find lesion boundary

### Full Pipeline
- `process_slice()` - Orchestrates all steps

## Data Structures

Your algorithms should return data structures compatible with `specimen_model.py`:

### Surface
```python
Surface(
    raw_points=[(x1, y1), (x2, y2), ...],  # List of (x, y) coordinates
    fitted_curves={
        "actual_surface": [(x1, y1), ...],      # Fitted to all detected points
        "interpolated_surface": [(x1, y1), ...]  # Fitted from sound areas only (for cavitation)
    }
)
```

### RegionStats
```python
RegionStats(
    region_type="sound",  # or "lesion"
    pixel_values=[100, 102, 98, ...],
    mean=100.0,
    median=100.0,
    sd=2.0,
    se=0.2
)
```

### LesionDepth
```python
LesionDepth(
    depth_points=[(x1, depth1), (x2, depth2), ...],
    mean_depth=20.5,
    median_depth=20.0,
    sd=1.0,
    se=0.1
)
```

## Configuration Data Available

For each slice, you have access to:

### RegionConfig
```python
region_config = specimen.config.regions[slice_index]
# Contains:
#   start_point: (x, y)  # Left boundary of lesion
#   end_point: (x, y)    # Right boundary of lesion
```

### AirConfig
```python
air_config = specimen.config.air[slice_index]
# Contains:
#   point1: (x, y)       # Top-left corner of AIR rectangle
#   point2: (x, y)       # Bottom-right corner of AIR rectangle
```

## Workflow Example

1. **Define test data:**
   ```python
   # In test_carlquant_config.py
   TEST_DATA_PATHS = [Path(r"W:\TestData\Specimen_001")]
   ```

2. **Implement surface detection:**
   ```python
   # In test_carlquant_algorithm.py
   def detect_surface(image, air_config):
       threshold = calculate_air_threshold(image, air_config)
       surface_points = []
       for x in range(image.shape[1]):
           for y in range(image.shape[0]):
               if image[y, x] > threshold:
                   surface_points.append((x, y))
                   break
       return Surface(raw_points=surface_points, fitted_curves={})
   ```

3. **Test visually:**
   - Run `test_carlquant_viewer.py`
   - Select specimen
   - Click "Run Algorithm"
   - Check if surface detection looks correct

4. **Iterate:**
   - Adjust algorithm parameters
   - Test on different slices
   - Test on different specimens

5. **Move to next algorithm:**
   - Implement `extract_regions()`
   - Test again
   - Continue until complete

## Tips

- **Start simple:** Get basic versions working before optimizing
- **Use visualization:** The viewer shows overlays to verify correctness
- **Test on multiple images:** Different sizes, different specimens
- **Cache results:** The viewer caches results per slice for quick comparison
- **Print debug info:** Use `print()` statements in algorithms during development
- **Compare with MATLAB:** Port your MATLAB logic step by step

## Integration Checklist

Before integrating into main app:

- [ ] All algorithm functions implemented
- [ ] Tested on multiple specimens
- [ ] Tested on different image sizes
- [ ] Results look correct visually
- [ ] Statistics are reasonable
- [ ] No crashes or errors
- [ ] Code is clean and documented
- [ ] Data structures match `specimen_model.py`

## Troubleshooting

**"No test specimens found"**
- Check that TEST_DATA_PATHS contains valid paths
- Ensure paths contain image files (jpg, png, tif, tiff)

**"No configuration found"**
- Use the main app to define regions and AIR for test specimens
- Configuration is saved in `Data_*/specimen_config.json`

**Algorithm errors**
- Check that image coordinates are within bounds
- Verify that region_config and air_config exist for the slice
- Print intermediate values to debug

**Display issues**
- Ensure overlay colors are visible (red, yellow, cyan, green)
- Check that coordinates are correctly converted to display space

## Next Steps

1. Add your test data paths to `test_carlquant_config.py`
2. Run the viewer to verify test data loads correctly
3. Start implementing algorithms in `test_carlquant_algorithm.py`
4. Test incrementally with the viewer
5. Port working code to `carl_quant_core.py`
6. Test in the main application

Good luck with your algorithm development!
