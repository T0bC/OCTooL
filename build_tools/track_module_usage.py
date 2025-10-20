#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module Usage Tracker for PyInstaller Optimization

This script tracks all modules imported during application runtime to help
optimize PyInstaller builds by identifying actually used dependencies.

Usage:
    python track_module_usage.py
    
Then run your application normally and exercise all features.
Press Ctrl+C when done to generate the report.

Author: Auto-generated for OCTexVIEW optimization
"""

import sys
import os
import json
from datetime import datetime
from collections import defaultdict


class ModuleTracker:
    """Tracks all module imports during runtime with enhanced analysis."""
    
    def __init__(self, output_file="module_usage.json"):
        self.output_file = output_file
        self.imported_modules = set()
        self.module_files = {}
        self.import_counts = defaultdict(int)
        self.import_order = []
        self.original_import = None
        self._tracking_active = False
        
    def custom_import(self, name, *args, **kwargs):
        """Custom import hook that tracks all imports."""
        # Call original import first
        module = self.original_import(name, *args, **kwargs)
        
        if self._tracking_active:
            # Track the module
            if name not in self.imported_modules:
                self.import_order.append(name)
            self.imported_modules.add(name)
            self.import_counts[name] += 1
            
            # Try to get the file location
            if hasattr(module, '__file__') and module.__file__:
                self.module_files[name] = os.path.abspath(module.__file__)
        
        return module
    
    def start_tracking(self):
        """Start tracking module imports."""
        if self._tracking_active:
            print("Warning: Tracking already active!")
            return
            
        # Store original import
        self.original_import = __builtins__.__import__
        __builtins__.__import__ = self.custom_import
        self._tracking_active = True
        
        print("=" * 70)
        print("MODULE USAGE TRACKER - STARTED")
        print("=" * 70)
        print("Instructions:")
        print("  1. The application will now start")
        print("  2. Click EVERY button, checkbox, and menu item")
        print("  3. Open EVERY tab (Export, Analyze, CarlQuant)")
        print("  4. Load sample data and perform all operations:")
        print("     - Export: Select files, change settings, export")
        print("     - Analyze: Load images, annotate, add columns")
        print("     - CarlQuant: Load images, analyze, view results")
        print("  5. Open Help and About dialogs")
        print("  6. Press Ctrl+C in this terminal when done")
        print("=" * 70)
        print("")
    
    def stop_tracking(self):
        """Stop tracking and restore original import."""
        if not self._tracking_active:
            return
            
        __builtins__.__import__ = self.original_import
        self._tracking_active = False
        
        print("\n" + "=" * 70)
        print("MODULE USAGE TRACKER - STOPPED")
        print("=" * 70)
    
    def save_report(self):
        """Save the tracking report to JSON with enhanced metadata."""
        # Categorize modules
        stdlib_modules = self._categorize_stdlib()
        third_party = self._categorize_third_party()
        local_modules = self._categorize_local()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_modules": len(self.imported_modules),
            "modules": sorted(list(self.imported_modules)),
            "module_files": self.module_files,
            "import_counts": dict(self.import_counts),
            "import_order": self.import_order[:100],  # First 100 for reference
            "top_level_packages": self._get_top_level_packages(),
            "categorized": {
                "stdlib": sorted(list(stdlib_modules)),
                "third_party": sorted(list(third_party)),
                "local": sorted(list(local_modules))
            },
            "statistics": {
                "stdlib_count": len(stdlib_modules),
                "third_party_count": len(third_party),
                "local_count": len(local_modules)
            }
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\nReport saved to: {self.output_file}")
        print(f"Total modules tracked: {len(self.imported_modules)}")
        
        return report
    
    def _get_top_level_packages(self):
        """Extract top-level package names."""
        packages = set()
        for module in self.imported_modules:
            top_level = module.split('.')[0]
            packages.add(top_level)
        return sorted(list(packages))
    
    def _categorize_stdlib(self):
        """Identify standard library modules."""
        stdlib = set()
        stdlib_prefixes = {
            'os', 'sys', 'io', 're', 'json', 'xml', 'html', 'http', 'urllib',
            'email', 'collections', 'itertools', 'functools', 'operator',
            'pathlib', 'datetime', 'time', 'calendar', 'math', 'random',
            'statistics', 'decimal', 'fractions', 'string', 'textwrap',
            'unicodedata', 'codecs', 'struct', 'pickle', 'copy', 'pprint',
            'enum', 'types', 'weakref', 'gc', 'inspect', 'traceback',
            'threading', 'multiprocessing', 'subprocess', 'socket', 'ssl',
            'asyncio', 'queue', 'contextvars', 'abc', 'typing', 'dataclasses',
            'warnings', 'logging', 'argparse', 'configparser', 'tempfile',
            'shutil', 'zipfile', 'tarfile', 'csv', 'sqlite3', 'dbm',
            'tkinter', 'turtle', 'cmd', 'pdb', 'profile', 'timeit',
            'unittest', 'doctest', 'test', 'importlib', 'pkgutil',
            'modulefinder', 'runpy', 'ast', 'symtable', 'token', 'keyword',
            'heapq', 'bisect', 'array', 'sched', 'mutex', 'contextlib',
            '_thread', 'dummy_threading', 'ctypes', 'mmap', 'readline',
            'rlcompleter', 'platform', 'errno', 'signal', 'locale',
            'gettext', 'getopt', 'curses', 'wave', 'chunk', 'colorsys',
            'imghdr', 'sndhdr', 'sunau', 'aifc', 'audioop', 'cgi', 'cgitb',
            'wsgiref', 'base64', 'binascii', 'quopri', 'uu', 'hashlib',
            'hmac', 'secrets', 'zlib', 'gzip', 'bz2', 'lzma', 'zipimport',
            'fnmatch', 'linecache', 'fileinput', 'filecmp', 'glob',
            'mailbox', 'mimetypes', 'encodings', 'builtins', '__future__'
        }
        
        for module in self.imported_modules:
            top_level = module.split('.')[0]
            if top_level in stdlib_prefixes or top_level.startswith('_'):
                stdlib.add(module)
        
        return stdlib
    
    def _categorize_third_party(self):
        """Identify third-party packages."""
        third_party = set()
        known_third_party = {
            'numpy', 'scipy', 'pandas', 'matplotlib', 'PIL', 'cv2',
            'sklearn', 'torch', 'tensorflow', 'keras', 'flask', 'django',
            'requests', 'beautifulsoup4', 'lxml', 'openpyxl', 'xlrd',
            'ttkbootstrap', 'ttkthemes', 'pillow', 'imageio', 'skimage'
        }
        
        stdlib = self._categorize_stdlib()
        local = self._categorize_local()
        
        for module in self.imported_modules:
            if module not in stdlib and module not in local:
                top_level = module.split('.')[0]
                # Check if it's a known third-party or not in local modules
                if top_level in known_third_party or not module.startswith(tuple(self._get_local_prefixes())):
                    third_party.add(module)
        
        return third_party
    
    def _categorize_local(self):
        """Identify local project modules."""
        local = set()
        local_prefixes = self._get_local_prefixes()
        
        for module in self.imported_modules:
            if module.startswith(tuple(local_prefixes)):
                local.add(module)
        
        return local
    
    def _get_local_prefixes(self):
        """Get prefixes for local modules based on project structure."""
        # These are OCTexVIEW-specific modules
        return [
            'MainGui', 'exportTab', 'analyzingTab', 'carl_quant',
            'export_frames', 'analyze_frames', 'carlquant_frames',
            'utils', 'base', 'load_images_panel'
        ]
    
    def print_summary(self):
        """Print a summary of tracked modules."""
        top_packages = self._get_top_level_packages()
        stdlib = self._categorize_stdlib()
        third_party = self._categorize_third_party()
        local = self._categorize_local()
        
        print("\n" + "=" * 70)
        print("MODULE USAGE SUMMARY")
        print("=" * 70)
        print(f"Total modules imported: {len(self.imported_modules)}")
        print(f"  - Standard library: {len(stdlib)}")
        print(f"  - Third-party packages: {len(third_party)}")
        print(f"  - Local modules: {len(local)}")
        print(f"\nTop-level packages: {len(top_packages)}")
        
        print("\n" + "-" * 70)
        print("THIRD-PARTY PACKAGES (these affect build size):")
        print("-" * 70)
        third_party_tops = set()
        for module in third_party:
            third_party_tops.add(module.split('.')[0])
        
        for pkg in sorted(third_party_tops):
            count = sum(1 for m in third_party if m.split('.')[0] == pkg)
            most_used = max((self.import_counts.get(m, 0), m) for m in third_party if m.split('.')[0] == pkg)
            print(f"  - {pkg:30s} ({count:3d} submodules, max imports: {most_used[0]})")
        
        print("\n" + "-" * 70)
        print("MOST FREQUENTLY IMPORTED MODULES:")
        print("-" * 70)
        sorted_counts = sorted(self.import_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        for module, count in sorted_counts:
            print(f"  {count:4d}x  {module}")
        
        print("\n" + "=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print("  1. Review module_usage.json")
        print("  2. Run: python build_tools/generate_pyinstaller_spec.py")
        print("  3. Build with: pyinstaller OCTexVIEW.spec")
        print("  4. Analyze: python build_tools/analyze_build_size.py")
        print("=" * 70)


if __name__ == "__main__":
    # Add parent directory to path so we can import OCTexVIEW
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    
    # Save output to parent directory
    output_path = os.path.join(parent_dir, "module_usage.json")
    
    # Initialize tracker
    tracker = ModuleTracker(output_path)
    
    # Start tracking
    tracker.start_tracking()
    
    try:
        # Import and run the main application
        # This will trigger the import of OCTexVIEW.py which starts the GUI
        import OCTexVIEW
        
    except KeyboardInterrupt:
        print("\n\n[Interrupted by user - this is expected]")
    except Exception as e:
        print(f"\n\nError during tracking: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop tracking and save report
        tracker.stop_tracking()
        tracker.save_report()
        tracker.print_summary()
