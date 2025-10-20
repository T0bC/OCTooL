#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze PyInstaller Build Size

Analyzes the dist folder to identify large files and suggest optimizations.
Provides detailed breakdown by file type, package, and size.

Usage: 
    python analyze_build_size.py [dist_path]
    
    If dist_path is not provided, defaults to: dist/OCTexVIEW

Author: Auto-generated for OCTexVIEW optimization
"""

import os
import sys
from pathlib import Path
from collections import defaultdict


def get_dir_size(path):
    """Calculate total size of a directory recursively."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except PermissionError:
        pass
    return total


def format_size(bytes_size):
    """Format bytes to human-readable size."""
    if bytes_size < 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def get_all_files(dist_path):
    """
    Get all files in the distribution with their sizes.
    
    Returns:
        List of tuples: (relative_path, size_bytes, absolute_path)
    """
    files = []
    for root, dirs, filenames in os.walk(dist_path):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            try:
                size = os.path.getsize(filepath)
                rel_path = os.path.relpath(filepath, dist_path)
                files.append((rel_path, size, filepath))
            except OSError:
                pass
    return files


def analyze_by_extension(files):
    """Analyze files grouped by extension."""
    ext_stats = defaultdict(lambda: {'count': 0, 'size': 0, 'files': []})
    
    for rel_path, size, abs_path in files:
        ext = Path(rel_path).suffix.lower() or 'no_extension'
        ext_stats[ext]['count'] += 1
        ext_stats[ext]['size'] += size
        ext_stats[ext]['files'].append((rel_path, size))
    
    return ext_stats


def analyze_by_package(files):
    """Analyze files grouped by likely package/library."""
    package_stats = defaultdict(lambda: {'count': 0, 'size': 0, 'files': []})
    
    # Common package patterns
    package_patterns = {
        'numpy': ['numpy', 'np'],
        'scipy': ['scipy'],
        'pandas': ['pandas', 'pd'],
        'matplotlib': ['matplotlib', 'mpl'],
        'PIL': ['PIL', 'pillow'],
        'tkinter': ['tkinter', 'tk', '_tkinter'],
        'ttkbootstrap': ['ttkbootstrap'],
        'cv2': ['cv2', 'opencv'],
        'sklearn': ['sklearn', 'scikit'],
    }
    
    for rel_path, size, abs_path in files:
        path_lower = rel_path.lower()
        matched = False
        
        for package, patterns in package_patterns.items():
            if any(pattern in path_lower for pattern in patterns):
                package_stats[package]['count'] += 1
                package_stats[package]['size'] += size
                package_stats[package]['files'].append((rel_path, size))
                matched = True
                break
        
        if not matched:
            # Categorize as 'other' or by first directory
            first_dir = Path(rel_path).parts[0] if Path(rel_path).parts else 'root'
            package_stats[first_dir]['count'] += 1
            package_stats[first_dir]['size'] += size
            package_stats[first_dir]['files'].append((rel_path, size))
    
    return package_stats


def identify_duplicates(files):
    """Identify potential duplicate files by name and size."""
    file_signatures = defaultdict(list)
    
    for rel_path, size, abs_path in files:
        filename = Path(rel_path).name
        signature = (filename, size)
        file_signatures[signature].append(rel_path)
    
    duplicates = {sig: paths for sig, paths in file_signatures.items() if len(paths) > 1}
    return duplicates


def suggest_optimizations(files, ext_stats, package_stats):
    """Generate optimization suggestions based on analysis."""
    suggestions = []
    total_size = sum(size for _, size, _ in files)
    
    # Check for large DLL files
    dll_size = ext_stats.get('.dll', {}).get('size', 0)
    if dll_size > 10 * 1024 * 1024:  # > 10 MB
        pct = (dll_size / total_size) * 100
        suggestions.append({
            'priority': 'HIGH',
            'category': 'DLL Files',
            'size': dll_size,
            'percentage': pct,
            'suggestion': 'Large DLL files detected. Consider excluding unused libraries in .spec file.'
        })
    
    # Check for large PYD files (Python extensions)
    pyd_size = ext_stats.get('.pyd', {}).get('size', 0)
    if pyd_size > 5 * 1024 * 1024:  # > 5 MB
        pct = (pyd_size / total_size) * 100
        suggestions.append({
            'priority': 'MEDIUM',
            'category': 'PYD Files',
            'size': pyd_size,
            'percentage': pct,
            'suggestion': 'Python extension modules. Check if all are necessary.'
        })
    
    # Check specific packages
    package_checks = {
        'numpy': (20 * 1024 * 1024, 'Consider if all numpy features are needed'),
        'scipy': (30 * 1024 * 1024, 'Scipy is large. Exclude unused submodules in .spec'),
        'pandas': (25 * 1024 * 1024, 'Pandas is large. Consider lighter alternatives if possible'),
        'matplotlib': (20 * 1024 * 1024, 'Matplotlib includes many backends. Exclude unused ones'),
    }
    
    for package, (threshold, suggestion) in package_checks.items():
        pkg_size = package_stats.get(package, {}).get('size', 0)
        if pkg_size > threshold:
            pct = (pkg_size / total_size) * 100
            suggestions.append({
                'priority': 'MEDIUM',
                'category': package,
                'size': pkg_size,
                'percentage': pct,
                'suggestion': suggestion
            })
    
    # Check for test files
    test_files = [f for f, s, _ in files if 'test' in f.lower() or 'tests' in f.lower()]
    if test_files:
        test_size = sum(s for _, s, _ in files if any(t in _[0].lower() for t in ['test', 'tests']))
        if test_size > 1 * 1024 * 1024:  # > 1 MB
            suggestions.append({
                'priority': 'HIGH',
                'category': 'Test Files',
                'size': test_size,
                'percentage': (test_size / total_size) * 100,
                'suggestion': f'Found {len(test_files)} test files. These should be excluded!'
            })
    
    return suggestions


def analyze_dist_folder(dist_path="dist/OCTexVIEW"):
    """Main analysis function."""
    
    # Check if path exists
    if not os.path.exists(dist_path):
        print(f"Error: {dist_path} not found!")
        print("\nPlease build with PyInstaller first:")
        print("  pyinstaller OCTexVIEW.spec")
        print("\nOr specify a different path:")
        print("  python analyze_build_size.py <path_to_dist>")
        return False
    
    print("=" * 70)
    print("PYINSTALLER BUILD SIZE ANALYSIS")
    print("=" * 70)
    print(f"Analyzing: {os.path.abspath(dist_path)}")
    print("")
    
    # Get all files
    print("Scanning files...")
    files = get_all_files(dist_path)
    total_size = sum(size for _, size, _ in files)
    
    print(f"Found {len(files)} files")
    print(f"Total size: {format_size(total_size)}")
    
    # Analyze by extension
    ext_stats = analyze_by_extension(files)
    
    # Analyze by package
    package_stats = analyze_by_package(files)
    
    # Identify duplicates
    duplicates = identify_duplicates(files)
    
    # Generate suggestions
    suggestions = suggest_optimizations(files, ext_stats, package_stats)
    
    # Print results
    print("\n" + "=" * 70)
    print("TOP 25 LARGEST FILES")
    print("=" * 70)
    sorted_files = sorted(files, key=lambda x: x[1], reverse=True)
    for i, (rel_path, size, _) in enumerate(sorted_files[:25], 1):
        pct = (size / total_size) * 100
        print(f"{i:2d}. {format_size(size):>12s} ({pct:5.1f}%)  {rel_path}")
    
    print("\n" + "=" * 70)
    print("SIZE BY FILE TYPE")
    print("=" * 70)
    sorted_exts = sorted(ext_stats.items(), key=lambda x: x[1]['size'], reverse=True)
    for ext, stats in sorted_exts[:20]:
        pct = (stats['size'] / total_size) * 100
        print(f"{format_size(stats['size']):>12s} ({pct:5.1f}%)  {ext:15s} ({stats['count']:4d} files)")
    
    print("\n" + "=" * 70)
    print("SIZE BY PACKAGE/LIBRARY")
    print("=" * 70)
    sorted_packages = sorted(package_stats.items(), key=lambda x: x[1]['size'], reverse=True)
    for package, stats in sorted_packages[:20]:
        pct = (stats['size'] / total_size) * 100
        print(f"{format_size(stats['size']):>12s} ({pct:5.1f}%)  {package:20s} ({stats['count']:4d} files)")
    
    if duplicates:
        print("\n" + "=" * 70)
        print(f"POTENTIAL DUPLICATES (first 10 of {len(duplicates)})")
        print("=" * 70)
        for i, ((filename, size), paths) in enumerate(list(duplicates.items())[:10], 1):
            print(f"\n{i}. {filename} ({format_size(size)}) - {len(paths)} copies:")
            for path in paths[:3]:
                print(f"   - {path}")
            if len(paths) > 3:
                print(f"   ... and {len(paths) - 3} more")
    
    if suggestions:
        print("\n" + "=" * 70)
        print("OPTIMIZATION SUGGESTIONS")
        print("=" * 70)
        for i, sug in enumerate(sorted(suggestions, key=lambda x: x['size'], reverse=True), 1):
            print(f"\n{i}. [{sug['priority']}] {sug['category']}")
            print(f"   Size: {format_size(sug['size'])} ({sug['percentage']:.1f}% of total)")
            print(f"   → {sug['suggestion']}")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("1. Review the largest files and packages above")
    print("2. Update OCTexVIEW.spec to exclude unused modules:")
    print("   - Add to 'excludes' list in Analysis()")
    print("   - Remove unnecessary data files from 'datas'")
    print("3. Use UPX compression (already enabled in spec)")
    print("4. Consider --onefile mode for single executable")
    print("5. Rebuild: pyinstaller OCTexVIEW.spec")
    print("6. Re-run this analysis to verify improvements")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    # Get parent directory (OCTexVIEW root)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Get dist path from command line or use default
    if len(sys.argv) > 1:
        dist_path = sys.argv[1]
    else:
        dist_path = os.path.join(parent_dir, "dist", "OCTexVIEW")
    
    # Run analysis
    success = analyze_dist_folder(dist_path)
    sys.exit(0 if success else 1)
