# -*- coding: utf-8 -*-
"""
Test Configuration Loader for CarlQuant Algorithm Development

This module provides utilities to load test specimens with their configurations
(regions and AIR settings) for algorithm development and testing.

Created on Mon Oct 06 11:50:00 2025
@author: meissnerto
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import from carlquant_frames
sys.path.insert(0, str(Path(__file__).parent.parent))

from carlquant_frames.data_io import DataLoader
from carlquant_frames.specimen_model import Specimen


class TestConfig:
    """Configuration for test data paths and specimens."""

    # Define your test data paths here
    # Modify these paths to point to your actual test data locations
    TEST_DATA_PATHS = [
        #Path(r"W:/ZM2-MF/01_Labor/07_Software/06_Development_python/OCT_Dev/OCTexVIEW/testData/mixed_carl_quant_test_data")
        Path(r"/Users/tmc/Documents/03_Arbeit/09_Software_Dev/03_octDev/OCTexVIEW/testData/exported/")
    ]

    @staticmethod
    def add_test_path(path: str):
        """
        Add a test data path dynamically.

        Args:
            path: String path to test specimen folder
        """
        test_path = Path(path)
        if test_path.exists() and test_path not in TestConfig.TEST_DATA_PATHS:
            TestConfig.TEST_DATA_PATHS.append(test_path)
            return True
        return False


def load_test_specimens() -> dict[str, Specimen]:
    """
    Load all test specimens with their configurations.

    This function:
    1. Scans TEST_DATA_PATHS for image stacks
    2. Loads region and AIR configurations from saved JSON files
    3. Returns Specimen objects ready for algorithm testing

    Returns:
        dict: specimen_id -> Specimen object with loaded configs
    """
    test_specimens = {}

    for test_path in TestConfig.TEST_DATA_PATHS:
        if not test_path.exists():
            print(f"Warning: Test path does not exist: {test_path}")
            continue

        # Use DataLoader to find and load specimens
        specimens = DataLoader.find_image_stacks(test_path)

        for specimen_id, specimen in specimens.items():
            # Load configuration from any available Data_ folder
            specimen.config = DataLoader.load_specimen_config(specimen)
            
            # Verify that configuration exists
            if specimen.config is None:
                print(f"Warning: No configuration found for {specimen_id}")
                print(f"  Please define regions/AIR in the main app first.")

            test_specimens[specimen_id] = specimen
            print(f"Loaded test specimen: {specimen_id}")
            print(f"  Images: {len(specimen.images)}")
            print(f"  Regions configured: {len(specimen.config.regions) if specimen.config else 0}")
            print(f"  AIR configured: {len(specimen.config.air) if specimen.config else 0}")

    return test_specimens


def load_single_specimen(specimen_path: str) -> Specimen:
    """
    Load a single specimen from a specific path.

    Useful for quick testing of a specific specimen without modifying
    the TEST_DATA_PATHS list.

    Args:
        specimen_path: Path to specimen folder containing images

    Returns:
        Specimen object or None if not found
    """
    path = Path(specimen_path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return None

    specimens = DataLoader.find_image_stacks(path.parent)
    specimen_id = path.name

    if specimen_id in specimens:
        specimen = specimens[specimen_id]
        # Load configuration from any available Data_ folder
        specimen.config = DataLoader.load_specimen_config(specimen)
        
        print(f"Loaded specimen: {specimen_id}")
        print(f"  Images: {len(specimen.images)}")
        print(f"  Regions configured: {len(specimen.config.regions) if specimen.config else 0}")
        print(f"  AIR configured: {len(specimen.config.air) if specimen.config else 0}")
        return specimen
    else:
        print(f"Error: No specimen found at {path}")
        return None


def get_test_specimen_summary() -> str:
    """
    Get a summary of all configured test specimens.

    Returns:
        str: Formatted summary of test specimens
    """
    specimens = load_test_specimens()

    if not specimens:
        return "No test specimens configured. Add paths to TestConfig.TEST_DATA_PATHS"

    summary = f"Test Specimens Summary ({len(specimens)} total)\n"
    summary += "=" * 60 + "\n"

    for specimen_id, specimen in specimens.items():
        summary += f"\n{specimen_id}:\n"
        summary += f"  Path: {specimen.source}\n"
        summary += f"  Slices: {specimen.slices}\n"

        if specimen.config:
            summary += f"  Regions: {len(specimen.config.regions)} slices configured\n"
            summary += f"  AIR: {len(specimen.config.air)} slices configured\n"

            # Show sample configuration from first slice
            if specimen.config.regions:
                first_slice = min(specimen.config.regions.keys())
                region = specimen.config.regions[first_slice]
                summary += f"  Sample region (slice {first_slice}): {region.start_point} -> {region.end_point}\n"

            if specimen.config.air:
                first_slice = min(specimen.config.air.keys())
                air = specimen.config.air[first_slice]
                summary += f"  Sample AIR (slice {first_slice}): {air.point1} -> {air.point2}\n"
        else:
            summary += "  WARNING: No configuration found!\n"

    return summary


# Example usage and testing
if __name__ == "__main__":
    print("CarlQuant Test Configuration Loader")
    print("=" * 60)
    print()

    # Print summary of configured test specimens
    print(get_test_specimen_summary())
    print()

    # Example: Add a test path dynamically
    # TestConfig.add_test_path(r"W:\path\to\your\test\data")

    # Example: Load a single specimen for quick testing
    # specimen = load_single_specimen(r"W:\path\to\specific\specimen")
