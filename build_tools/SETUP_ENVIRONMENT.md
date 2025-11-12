# OCTexVIEW Environment Setup Guide

This guide helps you create a clean conda environment for compiling OCTexVIEW with PyInstaller.

## Why Pip-Only Installation?

Using pip instead of conda for package installation significantly reduces the final executable size when building with PyInstaller. Conda packages often include additional dependencies and binaries that inflate the build size.

## Setup Instructions

### 1. Create a New Conda Environment

```bash
# Create a minimal conda environment with only Python
conda create -n octexview_build python=3.11 -y

# Activate the environment
conda activate octexview_build
```

**Important:** Use Python 3.11 for best compatibility with all dependencies.

### 2. Install All Dependencies with Pip

```bash
# Navigate to the OCTexVIEW directory
cd w:\ZM2-MF\01_Labor\07_Software\06_Development_python\OCT_Dev\OCTexVIEW

# Install all required packages
pip install -r requirements.txt

# Install PyInstaller for building
pip install pyinstaller>=6.0.0
```

### 3. Verify Installation

```bash
# Check that all packages are installed
pip list

# Test the application
python OCTexVIEW.py
```

## Required Dependencies

The following third-party libraries are required for OCTexVIEW:

### Core Scientific Computing
- **numpy** - Array operations and numerical computing
- **scipy** - Scientific algorithms (interpolation, optimization, signal processing)

### Image Processing
- **Pillow (PIL)** - Image loading, manipulation, and export

### Machine Learning
- **scikit-learn** - DBSCAN clustering for cavitation detection

### GUI Framework
- **ttkbootstrap** - Modern themed tkinter widgets
- **tksheet** - Spreadsheet-like table widgets for results display

### Data Processing & Export
- **openpyxl** - Excel file generation for results export

### XML Parsing
- **beautifulsoup4** - XML parsing for OCT metadata
- **lxml** - XML parser backend

### Plotting
- **matplotlib** - A-Scan viewer plots and data visualization

## Building with PyInstaller

After setting up the environment, you can build the executable:

```bash
# Build the application
pyinstaller OCTexVIEW.spec

# Or use the one-file mode
pyinstaller --onefile --windowed OCTexVIEW.py
```

## Updating Dependencies

When you add new dependencies to the codebase:

1. Add the package to `requirements.txt` with version constraints
2. Update this document if the dependency serves a new purpose
3. Test the build to ensure compatibility with PyInstaller

## Troubleshooting

### Import Errors
If you get import errors, ensure all packages in `requirements.txt` are installed:
```bash
pip install -r requirements.txt --upgrade
```

### PyInstaller Build Issues
- Clear PyInstaller cache: `pyinstaller --clean OCTexVIEW.spec`
- Check for hidden imports in the spec file
- Verify all data files (fonts, icons) are included

### Version Conflicts
If you encounter version conflicts:
```bash
# Remove the environment and start fresh
conda deactivate
conda env remove -n octexview_build
# Then follow setup instructions again
```

## Notes

- **Test files only:** The following packages are only used in test files and are NOT required for production builds:
  - opencv-python (cv2)
  - tifffile
  - open3d

- **Standard library:** The application also uses many Python standard library modules (tkinter, json, pathlib, etc.) which are included with Python and don't need separate installation.

## Environment Export

To share your exact environment configuration:

```bash
# Export pip packages
pip freeze > requirements_frozen.txt

# Or export full conda environment
conda env export > environment.yml
```
