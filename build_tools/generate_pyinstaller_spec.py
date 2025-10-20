#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Optimized PyInstaller Spec File

Reads module_usage.json and creates an optimized OCTexVIEW.spec file
that excludes unused modules and minimizes build size.

Usage: python generate_pyinstaller_spec.py [--onefile]

Options:
    --onefile    Generate single executable instead of folder distribution
    --debug      Enable debug mode (shows console, verbose output)

Author: Auto-generated for OCTexVIEW optimization
"""

import json
import os
import sys
from pathlib import Path


def load_module_usage(filename="module_usage.json"):
    """Load the module usage report."""
    if not os.path.exists(filename):
        print(f"Error: {filename} not found!")
        print("Please run track_module_usage.py first.")
        print("\nUsage:")
        print("  1. python build_tools/track_module_usage.py")
        print("  2. Exercise all app features")
        print("  3. Press Ctrl+C")
        print("  4. python build_tools/generate_pyinstaller_spec.py")
        sys.exit(1)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {filename}")
        print(f"Details: {e}")
        sys.exit(1)


def get_excludes_list(used_packages):
    """
    Generate list of modules to exclude based on what's NOT used.
    
    This is critical for size reduction. We exclude:
    1. Common testing frameworks
    2. Documentation tools
    3. Development tools
    4. Large unused stdlib modules
    5. Unused parts of included packages
    """
    # Comprehensive list of potentially excludable modules
    all_excludables = {
        # Testing frameworks
        'pytest', 'pytest_cov', 'coverage', 'nose', 'nose2', 'unittest',
        'unittest2', 'mock', 'doctest', '_pytest',
        
        # Documentation
        'sphinx', 'sphinx_rtd_theme', 'pydoc', 'pydoc_data',
        
        # Development tools
        'IPython', 'jupyter', 'jupyter_client', 'jupyter_core', 'notebook',
        'ipykernel', 'ipywidgets', 'nbconvert', 'nbformat',
        
        # Debugging/profiling
        'pdb', 'profile', 'pstats', 'cProfile', 'trace', 'bdb',
        
        # Build tools
        'setuptools', 'pip', 'wheel', 'distutils', 'pkg_resources',
        
        # Large test suites
        'matplotlib.tests', 'numpy.tests', 'scipy.tests', 'pandas.tests',
        'PIL.tests', 'tkinter.test',
        
        # Unused matplotlib backends (keep only what's needed)
        'matplotlib.backends.backend_gtk3', 'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_gtk3cairo', 'matplotlib.backends.backend_qt4',
        'matplotlib.backends.backend_qt4agg', 'matplotlib.backends.backend_qt5',
        'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_wxagg',
        
        # Unused parts of scipy (if scipy is used)
        'scipy.weave',
        
        # Unused parts of pandas (if pandas is used)
        'pandas.io.clipboard',
        
        # Other large/unused modules
        'pytz', 'dateutil', 'six.moves', 'past', 'future',
    }
    
    # Only exclude modules that are NOT in the used packages
    excludes = []
    for module in all_excludables:
        top_level = module.split('.')[0]
        # Exclude if the top-level package is not used at all
        if top_level not in used_packages:
            excludes.append(module)
    
    return sorted(excludes)


def get_hidden_imports(used_packages):
    """
    Get list of modules that PyInstaller might miss.
    
    These are modules that are imported dynamically or in non-standard ways.
    """
    hidden = []
    
    # ttkbootstrap needs explicit inclusion
    if 'ttkbootstrap' in used_packages:
        hidden.extend([
            'ttkbootstrap',
            'ttkbootstrap.themes',
        ])
    
    # PIL/Pillow image format plugins
    if 'PIL' in used_packages:
        hidden.extend([
            'PIL._tkinter_finder',
            'PIL.Image',
            'PIL.ImageTk',
            'PIL.ImageDraw',
            'PIL.ImageFont',
        ])
    
    # Tkinter components
    if 'tkinter' in used_packages:
        hidden.extend([
            'tkinter',
            'tkinter.ttk',
            'tkinter.filedialog',
            'tkinter.messagebox',
        ])
    
    # Numpy
    if 'numpy' in used_packages:
        hidden.extend([
            'numpy.core._methods',
            'numpy.core._dtype_ctypes',
        ])
    
    # Scipy
    if 'scipy' in used_packages:
        hidden.extend([
            'scipy.special._ufuncs_cxx',
            'scipy.linalg.cython_blas',
            'scipy.linalg.cython_lapack',
        ])
    
    # Matplotlib
    if 'matplotlib' in used_packages:
        hidden.extend([
            'matplotlib.backends.backend_tkagg',
        ])
    
    return sorted(list(set(hidden)))


def get_data_files():
    """
    Get list of data files to include in the build.
    
    Returns list of tuples: (source_path, destination_path)
    """
    data_files = []
    
    # Get parent directory (OCTexVIEW root)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Icons (required for app icon and UI)
    icons_path = os.path.join(parent_dir, 'icons')
    if os.path.exists(icons_path):
        data_files.append(('icons', 'icons'))
    
    # Fonts (if used by the app)
    fonts_path = os.path.join(parent_dir, 'fonts')
    if os.path.exists(fonts_path):
        data_files.append(('fonts', 'fonts'))
    
    # HTML docs (optional, comment out if not needed in distribution)
    html_docs_path = os.path.join(parent_dir, 'HTML_docs')
    if os.path.exists(html_docs_path):
        # Uncomment next line if you want to include documentation
        # data_files.append(('HTML_docs', 'HTML_docs'))
        pass
    
    # Test data (usually not needed in production)
    # test_data_path = os.path.join(parent_dir, 'testData')
    # if os.path.exists(test_data_path):
    #     data_files.append(('testData', 'testData'))
    
    return data_files


def get_binaries():
    """
    Get list of binary files to include.
    
    Usually empty unless you have custom DLLs.
    """
    binaries = []
    
    # Add custom DLLs here if needed
    # Example:
    # if os.path.exists('custom.dll'):
    #     binaries.append(('custom.dll', '.'))
    
    return binaries


def generate_spec_file(module_usage, output_file="OCTexVIEW.spec", onefile=False, debug=False):
    """Generate the PyInstaller spec file with optimizations."""
    
    used_packages = set(module_usage['top_level_packages'])
    excludes = get_excludes_list(used_packages)
    hidden_imports = get_hidden_imports(used_packages)
    data_files = get_data_files()
    binaries = get_binaries()
    
    # Get parent directory (OCTexVIEW root)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Determine icon path
    icon_path_abs = os.path.join(parent_dir, 'icons', 'thumb_4.ico')
    icon_path = 'icons/thumb_4.ico' if os.path.exists(icon_path_abs) else None
    
    # Output spec file to parent directory
    output_file = os.path.join(parent_dir, output_file)
    
    # Build the spec file content
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# Auto-generated PyInstaller spec file for OCTexVIEW
# Generated: {module_usage['timestamp']}
# Tracked modules: {module_usage['total_modules']}
# Used packages: {len(used_packages)}
# Excluded modules: {len(excludes)}

block_cipher = None

a = Analysis(
    ['OCTexVIEW.py'],
    pathex=[],
    binaries={binaries},
    datas={data_files},
    hiddenimports={hidden_imports},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={excludes},
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files
a.datas = list(set(a.datas))
a.binaries = list(set(a.binaries))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
'''
    
    if onefile:
        # Single file executable
        spec_content += f'''
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OCTexVIEW',
    debug={str(debug)},
    bootloader_ignore_signals=False,
    strip={str(not debug)},
    upx={str(not debug)},
    upx_exclude=[],
    runtime_tmpdir=None,
    console={str(debug)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,'''
        
        if icon_path:
            spec_content += f"\n    icon='{icon_path}',"
        
        spec_content += "\n)\n"
    
    else:
        # Directory distribution (faster startup, easier debugging)
        spec_content += f'''
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OCTexVIEW',
    debug={str(debug)},
    bootloader_ignore_signals=False,
    strip={str(not debug)},
    upx={str(not debug)},
    console={str(debug)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,'''
        
        if icon_path:
            spec_content += f"\n    icon='{icon_path}',"
        
        spec_content += "\n)\n\n"
        
        spec_content += f'''coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip={str(not debug)},
    upx={str(not debug)},
    upx_exclude=[],
    name='OCTexVIEW',
)
'''
    
    # Write the spec file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    # Print summary
    print("=" * 70)
    print("PYINSTALLER SPEC FILE GENERATED")
    print("=" * 70)
    print(f"Output file: {output_file}")
    print(f"Mode: {'Single file' if onefile else 'Directory distribution'}")
    print(f"Debug: {debug}")
    print(f"Console window: {debug}")
    
    print(f"\n{'Used packages':<30} {len(used_packages):>5}")
    print(f"{'Excluded modules':<30} {len(excludes):>5}")
    print(f"{'Hidden imports':<30} {len(hidden_imports):>5}")
    print(f"{'Data files':<30} {len(data_files):>5}")
    print(f"{'Binary files':<30} {len(binaries):>5}")
    
    print("\n" + "-" * 70)
    print("USED PACKAGES:")
    print("-" * 70)
    for pkg in sorted(used_packages):
        count = sum(1 for m in module_usage['modules'] if m.split('.')[0] == pkg)
        print(f"  {pkg:<30} ({count:>3} submodules)")
    
    if excludes:
        print("\n" + "-" * 70)
        print(f"EXCLUDED MODULES (first 20 of {len(excludes)}):")
        print("-" * 70)
        for module in excludes[:20]:
            print(f"  - {module}")
        if len(excludes) > 20:
            print(f"  ... and {len(excludes) - 20} more")
    
    if hidden_imports:
        print("\n" + "-" * 70)
        print("HIDDEN IMPORTS (explicitly included):")
        print("-" * 70)
        for module in hidden_imports:
            print(f"  + {module}")
    
    if data_files:
        print("\n" + "-" * 70)
        print("DATA FILES:")
        print("-" * 70)
        for src, dst in data_files:
            print(f"  {src} -> {dst}")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print(f"  1. Review {output_file}")
    print(f"  2. Build: pyinstaller {output_file}")
    print("  3. Test: dist/OCTexVIEW/OCTexVIEW.exe")
    print("  4. Analyze: python build_tools/analyze_build_size.py")
    print("=" * 70)
    
    return output_file


if __name__ == "__main__":
    # Parse command line arguments
    onefile = '--onefile' in sys.argv
    debug = '--debug' in sys.argv
    
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    # Get parent directory (OCTexVIEW root)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module_usage_path = os.path.join(parent_dir, "module_usage.json")
    
    # Load module usage data
    module_usage = load_module_usage(module_usage_path)
    
    # Generate spec file
    generate_spec_file(module_usage, onefile=onefile, debug=debug)
