# OCTooL

**OCTooL** is a comprehensive software application designed for the export, analysis, and quantification of Optical Coherence Tomography (OCT) images. Developed specifically for dental and medical research applications, OCTooL provides researchers and clinicians with powerful tools to extract quantitative data from OCT imaging studies.

---

## Table of Contents

- [OCTooL](#octool)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [System Requirements](#system-requirements)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Install Dependencies](#install-dependencies)
    - [Run the Application](#run-the-application)
  - [Application Overview](#application-overview)
    - [RexView Section](#export-section)
    - [AnnoLyze Section](#analyze-section)
    - [CarlQuant Section](#carlquant-section)
  - [Development Setup](#development-setup)
    - [Create Conda Environment](#create-conda-environment)
    - [Development Tools](#development-tools)
  - [Building from Source](#building-from-source)
    - [Install PyInstaller](#install-pyinstaller)
    - [Build the Application](#build-the-application)
    - [Development Mode (Console Enabled)](#development-mode-console-enabled)
    - [Icon Creation](#icon-creation)
    - [Distribution](#distribution)
  - [Contact](#contact)
  - [License](#license)
  - [Acknowledgments](#acknowledgments)
  - [Documentation](#documentation)

---

## Features

- **Batch Processing**: Efficiently process large datasets of OCT images
- **Quantitative Analysis**: Extract precise measurements from tissue structures
- **Interactive Annotation**: Manual annotation tools with customizable data types
- **Advanced Algorithms**: Specialized lesion depth detection algorithms
- **Multi-Format RexView**: RexView to PNG or TIFF formats with customizable parameters
- **Data Integrity**: Automated workflows with comprehensive data persistence
- **Research-Ready Output**: CSV and JSON exports compatible with statistical software

---

## System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux
- **Python Version**: Python 3.14 or higher
- **Memory**: Minimum 8GB RAM (16GB recommended for large datasets)
- **Storage**: At least 2GB free space for installation and temporary files
- **Display**: Minimum 1920x1080 resolution for optimal interface experience

---

## Installation

### Prerequisites

Install Python 3.14 or higher from [python.org](https://www.python.org/downloads/).

### Install Dependencies

1. Clone or download this repository
2. Navigate to the project directory
3. Install required packages:

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
python OCTooL.py
```

---

## Application Overview

OCTooL is organized into three main functional sections, each designed for specific aspects of OCT image analysis:

### RexView Section

<p align="center">
  <img src="HTML_docs/images/01_Export_mainWindow.png" alt="RexView Section Interface" width="800"/>
</p>

The **RexView** section focuses on data preparation and batch processing capabilities. This module is the primary tool for converting OCT raw data files into standard image formats (PNG or TIFF).

**Key Features:**

- **Batch File Processing**: Import and organize large collections of OCT files from folders and subfolders
- **Global Processing Parameters**: Configure export format, averaging methods, aspect ratio correction, and scale bar preferences
- **Custom Settings Per File**: Fine-tune slice ranges, dynamic range (dB), dispersion compensation, and refractive index for individual datasets
- **Preview Capability**: Preview export results before processing entire batches
- **Flexible RexView Options**: Choose between PNG (smaller files) or TIFF (maximum quality) formats
- **Advanced Processing**: Apply apodization windows, local filtering, and coherent/incoherent averaging
- **Multi-View Support**: RexView XZ, YZ, or XY slice orientations

**Primary Use Case**: Preparing raw OCT data for analysis and converting proprietary OCT formats to standard image files for further processing.

---

### AnnoLyze Section

<p align="center">
  <img src="HTML_docs/images/02_Analyze_mainWindow.png" alt="AnnoLyze Section Interface" width="800"/>
</p>

The **AnnoLyze** section provides comprehensive tools for detailed image analysis and manual annotation. This module enables researchers to perform detailed measurements with full manual oversight and quality control.

**Key Features:**

- **Interactive Image Viewer**: Navigate through image stacks with zoom, pan, and overlay controls
- **Flexible Annotation Tools**: Point-based annotations with line or spline interpolation modes
- **Custom Data Columns**: Define unlimited custom columns with 8 different data types (Continuous, Percentage, Boolean, Categorical, Ordinal, Integer, Float, Text/String)
- **Keyboard Shortcuts**: Assign unique key bindings to each column for rapid data entry
- **Visual Organization**: Color-code columns and annotations for easy identification
- **Comprehensive Undo System**: Full undo history with selective multi-action undo capability (Ctrl+Z, Ctrl+U)
- **Metadata Management**: Track operator, measurement session, and imaging system information
- **Auto-Save**: Automatic data persistence 1.5 seconds after each action
- **Results RexView**: RexView to CSV format compatible with Excel, R, Python, and statistical software

**Primary Use Case**: Detailed analysis of individual specimens requiring manual measurements, feature annotation, and quality control with customizable data collection protocols.

---

### CarlQuant Section

<p align="center">
  <img src="HTML_docs/images/03_CarlQuant_mainWindow.png" alt="CarlQuant Section Interface" width="800"/>
</p>

The **CarlQuant** section implements advanced quantitative analysis algorithms specifically developed for OCT lesion depth analysis. This module offers high-throughput automated analysis using validated algorithms.

**Key Features:**

- **Automated Lesion Depth Detection**: Four detection algorithms (Combined, Knee Point, Inflection, Shoulder) with intelligent method selection
- **Region-of-Interest Extraction**: Define sound and lesion tissue regions with configurable region counts (2-10 regions)
- **Surface Detection**: Automatic tissue surface detection with AIR region-based thresholding
- **Batch Processing**: Process multiple specimens with consistent parameters in a single workflow
- **Interactive A-Scan Viewer**: Detailed intensity profile visualization with multiple detection method overlays
- **Cavitation Detection**: Automatic detection of surface cavitation and material loss
- **Multi-Session Analysis**: Perform multiple analyses with different parameters without data loss
- **Memory Optimization**: Efficient memory management for processing hundreds of specimens
- **Comprehensive Output**: Median intensity values per region, mean lesion depth, and cavitation status

**Primary Use Case**: High-throughput quantitative analysis of lesion depth and tissue characteristics using validated algorithms for research studies requiring standardized, reproducible measurements.

---

## Development Setup

### Create Conda Environment

It is recommended to use a conda environment for development. First, install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) if you haven't already.

```bash
# Create conda environment with Python 3.14
conda create -n octdev python=3.14

# Activate conda environment
conda activate octdev

# Install dependencies
pip install -r requirements.txt
```

### Development Tools

You can use any Python IDE or text editor for development. Popular choices include:

- **Visual Studio Code** with Python extension
- **PyCharm**
- **Jupyter Notebook** (for testing individual components)
- **Sublime Text** or **Atom**

---

## Building from Source

OCTooL uses PyInstaller to create standalone executables. The build configuration is managed through a spec file.

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build the Application

The application uses a spec file (`OCTooL.spec`) that contains all build configurations, including:

- Icon file location (`icons/thumb_6.ico`)
- Data files (icons, fonts, documentation)
- Build options and optimizations


To build the application:

```bash
pyinstaller OCTooL.spec
```

The compiled application will be created in the `dist/OCTooL/` directory.

### Development Mode (Console Enabled)

During development, you may want to see console output for debugging. To enable the console window:

1. Open `OCTooL.spec`
2. Find the line `console=False` in the `EXE` section
3. Change it to `console=True`
4. Rebuild with `pyinstaller OCTooL.spec`

This will open a terminal window alongside the GUI, displaying error messages and debug output.

### Icon Creation

The application icon should be in `.ico` format with multiple resolutions (16, 32, 64, 128, 256 pixels). You can:

- Use the included `png_to_ico_script.py` to convert PNG images to ICO format
- Use online tools like [RW Designer](http://www.rw-designer.com/image-to-icon)

Place the icon file in the `icons/` folder and reference it in the spec file.

### Distribution

After building:

1. The `dist/OCTooL/` folder contains the complete application
2. All required files (icons, fonts, documentation) are automatically included via the spec file
3. Distribute the entire `OCTooL` folder to users

**Update Tip**: If you make changes without adding new dependencies, you can simply replace the `OCTooL.exe` file in an existing installation to update the software.

---

## Contact

**Developer**: Tobias Meißner  
**Email**: tobias.meissner@medizin.uni-leipzig.de  
**Institution**: University of Leipzig, Department of Cariology, Endodontology and Periodontology

For bug reports, feature requests, or questions, please contact via email or open an issue on GitHub.

---

## License

This software is developed for academic and research purposes. Please contact the developer for licensing information and usage terms.

---

## Acknowledgments

OCTooL was developed at the University of Leipzig for dental and medical OCT research applications. Special thanks to all contributors and researchers who provided feedback during development.

---

## Documentation

For detailed user instructions, please refer to the complete manual:

- HTML Documentation: `HTML_docs/OCTooL_MANUAL.html`
- Source Documentation: `HTML_docs/OCTooL_MANUAL.qmd`

The manual includes comprehensive guides for each section, keyboard shortcuts, troubleshooting tips, and example workflows.
