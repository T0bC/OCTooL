# PyInstaller Build Optimization Guide for OCTexVIEW

This guide explains how to create an optimized, minimal-size executable distribution of OCTexVIEW using automated module tracking and PyInstaller optimization.

## Problem Statement

When building with PyInstaller, the default distribution includes many unused modules and libraries, resulting in:
- **Large distribution size** (200-500 MB)
- **Unnecessary DLL files** from third-party libraries
- **Wasted disk space** from unused features
- **Manual trial-and-error** to identify required files

## Solution Overview

This automated solution tracks actual module usage during comprehensive testing, then generates an optimized PyInstaller configuration that includes only what's needed.

**Expected Results:**
- ✅ **50-75% size reduction** (from ~300 MB to ~75-150 MB)
- ✅ **Automated process** - no manual DLL testing
- ✅ **Comprehensive coverage** - all features work
- ✅ **Reproducible builds** - consistent results

---

## Quick Start

```bash
# 1. Install PyInstaller
pip install pyinstaller

# 2. Track module usage (MOST IMPORTANT STEP)
python build_tools/track_module_usage.py
# → Exercise ALL features, then press Ctrl+C

# 3. Generate optimized spec file
python build_tools/generate_pyinstaller_spec.py

# 4. Build the executable
pyinstaller build_tools/OCTexVIEW.spec

# 5. Analyze the build
python build_tools/analyze_build_size.py

# 6. Test the executable
cd dist\OCTexVIEW
OCTexVIEW.exe
```

---

## Detailed Workflow

### Step 1: Track Module Usage

**Purpose:** Identify which Python modules are actually imported during app execution.

```bash
python build_tools/track_module_usage.py
```

**What to do:**
1. The application will start automatically
2. **Thoroughly exercise ALL features:**
   - **Export Tab:**
     - Click "Select Folder" and "Select File"
     - Change all settings (aspect ratio, format, etc.)
     - Add files to queue
     - Click "Export!" (you can cancel immediately)
   - **Analyze Tab:**
     - Load images
     - Add custom columns
     - Annotate images (draw points/lines)
     - Save configuration
     - Open undo history
   - **CarlQuant Tab:**
     - Load specimen images
     - Change detection method
     - Start analysis
     - View results
     - Open A-Scan viewer
     - Toggle all overlay options
   - **Dialogs:**
     - Click "Help" button
     - Click "About" button
3. Press **Ctrl+C** in the terminal when done
4. Review `module_usage.json` (created automatically)

**Output:** `module_usage.json` - Complete list of imported modules

**Tips:**
- The more thorough your testing, the better the optimization
- Don't skip any features - missing modules will cause runtime errors
- Load actual data files if possible
- Click every button, checkbox, and dropdown

---

### Step 2: Generate Optimized Spec File

**Purpose:** Create a PyInstaller configuration that excludes unused modules.

```bash
# Standard build (folder distribution)
python build_tools/generate_pyinstaller_spec.py

# OR single-file executable
python build_tools/generate_pyinstaller_spec.py --onefile

# OR debug mode (with console window)
python build_tools/generate_pyinstaller_spec.py --debug
```

**What it does:**
- Reads `module_usage.json`
- Identifies unused modules to exclude
- Adds hidden imports for dynamically loaded modules
- Configures data files (icons, fonts)
- Generates `OCTexVIEW.spec`

**Output:** `OCTexVIEW.spec` - Optimized PyInstaller configuration

**Options:**
- `--onefile`: Single executable (slower startup, easier distribution)
- `--debug`: Enable console window and verbose output (for troubleshooting)

---

### Step 3: Build with PyInstaller

**Purpose:** Create the executable distribution.

```bash
pyinstaller OCTexVIEW.spec
```

**What happens:**
- PyInstaller analyzes dependencies
- Compiles Python code
- Bundles required modules and DLLs
- Creates `dist/OCTexVIEW/` folder

**Build time:** 2-10 minutes depending on your system

**Output:**
- `dist/OCTexVIEW/` - Distribution folder
- `dist/OCTexVIEW/OCTexVIEW.exe` - Main executable

---

### Step 4: Analyze Build Size

**Purpose:** Identify large files and optimization opportunities.

```bash
python build_tools/analyze_build_size.py
```

**What it shows:**
- Total distribution size
- Top 25 largest files
- Size breakdown by file type (.dll, .pyd, etc.)
- Size breakdown by package (numpy, scipy, etc.)
- Potential duplicate files
- Optimization suggestions

**Example output:**
```
Total size: 127.45 MB

TOP 25 LARGEST FILES
1.   15.23 MB ( 11.9%)  numpy.core._multiarray_umath.pyd
2.   12.87 MB ( 10.1%)  scipy.linalg._fblas.pyd
...

OPTIMIZATION SUGGESTIONS
1. [HIGH] Test Files
   Size: 5.23 MB (4.1% of total)
   → Found 23 test files. These should be excluded!
```

---

### Step 5: Test the Executable

**Purpose:** Verify all functionality works in the built version.

```bash
cd dist\OCTexVIEW
OCTexVIEW.exe
```

**Testing checklist:**
- [ ] Application starts without errors
- [ ] All three tabs (Export, Analyze, CarlQuant) open
- [ ] Can load data files
- [ ] All buttons and controls work
- [ ] Can perform actual operations (export, analyze, etc.)
- [ ] Help and About dialogs open
- [ ] No missing module errors

**If you encounter errors:**
1. Note the missing module name
2. Add it to `hiddenimports` in `OCTexVIEW.spec`:
   ```python
   hiddenimports=[
       'missing_module_name',
       # ... other imports
   ],
   ```
3. Rebuild: `pyinstaller OCTexVIEW.spec`
4. Test again

---

## Advanced Usage

### Automated UI Testing

For more comprehensive module tracking, use the automated UI tester:

```bash
python build_tools/automated_ui_test.py
```

This programmatically clicks all buttons and controls to ensure complete coverage.

**Note:** This is experimental and may trigger unexpected dialogs. Manual testing is still recommended.

---

### Iterative Optimization

To further reduce size:

1. **Review large packages** in `analyze_build_size.py` output
2. **Check if they're necessary:**
   - Can you use a lighter alternative?
   - Are you using only a small part of the package?
3. **Exclude unused submodules** in `OCTexVIEW.spec`:
   ```python
   excludes=[
       'scipy.sparse',  # If you don't use sparse matrices
       'pandas.io.sql',  # If you don't use SQL
       'matplotlib.backends.backend_qt5',  # Unused backend
       # ... add more
   ],
   ```
4. **Rebuild and test**

---

### Single-File Executable

For easier distribution (single .exe file):

```bash
python build_tools/generate_pyinstaller_spec.py --onefile
pyinstaller OCTexVIEW.spec
```

**Pros:**
- Single file to distribute
- Simpler for end users

**Cons:**
- Slower startup (extracts to temp folder)
- Larger file size (less compression)
- Antivirus may flag it

---

### Debug Mode

If the built executable crashes silently:

```bash
python build_tools/generate_pyinstaller_spec.py --debug
pyinstaller OCTexVIEW.spec
```

This enables:
- Console window (shows error messages)
- Verbose output
- No stripping of debug symbols

---

## Troubleshooting

### "Module not found" Error

**Problem:** Built executable crashes with `ModuleNotFoundError: No module named 'xyz'`

**Solution:**
1. Add to `hiddenimports` in `OCTexVIEW.spec`:
   ```python
   hiddenimports=[
       'xyz',  # Add the missing module
   ],
   ```
2. Rebuild: `pyinstaller OCTexVIEW.spec`

**Common missing modules:**
- `PIL._tkinter_finder`
- `ttkbootstrap.themes`
- `numpy.core._methods`

---

### "DLL load failed" Error

**Problem:** `ImportError: DLL load failed while importing xyz`

**Solution:**
1. Find the DLL in your Python installation
2. Add to `binaries` in `OCTexVIEW.spec`:
   ```python
   binaries=[
       ('C:/path/to/missing.dll', '.'),
   ],
   ```
3. Rebuild

---

### Icons/Fonts Not Found

**Problem:** Application runs but icons or fonts are missing

**Solution:**
1. Verify data files in `OCTexVIEW.spec`:
   ```python
   datas=[
       ('icons', 'icons'),
       ('fonts', 'fonts'),
   ],
   ```
2. Rebuild

---

### Build is Still Too Large

**Problem:** Distribution is larger than expected

**Solutions:**

1. **Re-run module tracking** with more thorough testing
2. **Exclude test modules:**
   ```python
   excludes=[
       'pytest', 'unittest', 'doctest',
       'matplotlib.tests', 'numpy.tests',
   ],
   ```
3. **Use UPX compression** (already enabled in spec)
4. **Remove HTML_docs** from data files if not needed
5. **Check for duplicates** in `analyze_build_size.py` output

---

### Antivirus Flags Executable

**Problem:** Antivirus software flags the .exe as malware

**Common with PyInstaller executables. Solutions:**

1. **Use folder distribution** instead of `--onefile`
2. **Code sign the executable** (requires certificate)
3. **Submit to antivirus vendors** for whitelisting
4. **Add exception** in antivirus software

---

## File Reference

### Created Scripts

| File | Purpose |
|------|---------|
| `track_module_usage.py` | Monitors imported modules during runtime |
| `generate_pyinstaller_spec.py` | Creates optimized PyInstaller configuration |
| `automated_ui_test.py` | Automates UI testing for comprehensive coverage |
| `analyze_build_size.py` | Analyzes build size and suggests optimizations |

### Generated Files

| File | Purpose |
|------|---------|
| `module_usage.json` | List of all imported modules (from tracking) |
| `OCTexVIEW.spec` | PyInstaller configuration file |
| `build/` | Temporary build files (can be deleted) |
| `dist/OCTexVIEW/` | Final distribution folder |

---

## Best Practices

### ✅ Do:
- **Test thoroughly** during module tracking
- **Load actual data files** to trigger all imports
- **Test the built executable** before distribution
- **Keep module_usage.json** for future builds
- **Version control** your .spec file

### ❌ Don't:
- **Skip features** during module tracking
- **Manually edit** module_usage.json
- **Delete build artifacts** until testing is complete
- **Assume it works** without testing
- **Distribute** without thorough testing

---

## Performance Comparison

### Before Optimization (Default PyInstaller)
- **Size:** ~300-500 MB
- **Files:** ~500-800 files
- **Includes:** Many unused test modules, documentation, multiple backends

### After Optimization (This Method)
- **Size:** ~75-150 MB (50-75% reduction)
- **Files:** ~200-400 files
- **Includes:** Only used modules and dependencies

### With --onefile
- **Size:** ~100-200 MB (single file)
- **Startup:** Slightly slower (extraction overhead)
- **Distribution:** Easier (single file)

---

## Additional Resources

### PyInstaller Documentation
- https://pyinstaller.org/en/stable/

### UPX Compression
- Download: https://upx.github.io/
- Place `upx.exe` in PATH for automatic compression

### Code Signing (Optional)
- For professional distribution
- Reduces antivirus false positives
- Requires certificate (~$100-300/year)

---

## Support

If you encounter issues:

1. **Check this README** for troubleshooting steps
2. **Review error messages** carefully
3. **Enable debug mode** to see detailed errors
4. **Re-run module tracking** if modules are missing
5. **Check PyInstaller documentation** for specific errors

---

## Summary

This automated approach eliminates the tedious manual process of testing for missing DLLs. By tracking actual module usage during comprehensive testing, you get:

- **Minimal distribution size** with all functionality
- **Automated optimization** without guesswork
- **Reproducible builds** for consistent results
- **Clear analysis** of what's included and why

The key is **thorough testing** during the module tracking phase. The more comprehensive your testing, the better the optimization and the more reliable the final executable.

**Happy building! 🚀**
