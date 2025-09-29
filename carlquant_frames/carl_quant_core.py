# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 11:05:22 2025

@author: Tobias Meissner
"""

from time import sleep
from threading import Thread
from carlquant_frames.data_io import DataSaver
from carlquant_frames.specimen_model import RegionStats, Surface, LesionDepth
import random

def run_carl_quant(context):
    def worker():
        for specimen_id, specimen in context.specimen_data.items():
            for slice_index in range(specimen.slices):
                sleep(0.5)

                num_sound = context.region_config.get("sound", 3)
                num_lesion = context.region_config.get("lesion", 3)

                region_stats = [
                    RegionStats("sound", [random.randint(95, 105) for _ in range(100)],
                                mean=100.0, median=100.0, sd=2.0, se=1.0)
                    for _ in range(num_sound)
                ] + [
                    RegionStats("lesion", [random.randint(75, 85) for _ in range(100)],
                                mean=80.0, median=80.0, sd=2.0, se=1.0)
                    for _ in range(num_lesion)
                ]

                surface = Surface(
                    raw_points=[(x, 100 + x % 5) for x in range(100)],
                    fitted_curves={"polyfit": [(x, 100 + x % 3) for x in range(100)]}
                )

                lesion_depth = LesionDepth(
                    depth_points=[(x, 20 + x % 2) for x in range(100)],
                    mean_depth=20.5,
                    median_depth=20.0,
                    sd=1.0,
                    se=0.5
                )

                if hasattr(context, "result_lock"):
                    with context.result_lock:
                        DataSaver.store_slice_result(specimen, slice_index, region_stats, surface, lesion_depth)
                else:
                    DataSaver.store_slice_result(specimen, slice_index, region_stats, surface, lesion_depth)

                context.status_bar.update(f"Processed slice {slice_index + 1} of {specimen_id}", level="info")

            # Save results after all slices are processed
            # Inject metadata into specimen
            specimen.operator = context.analysis_metadata.get("operator", "OP")
            specimen.measurement = context.analysis_metadata.get("measurement", 1)

            # Save results
            DataSaver.save_results(specimen)

            try:
                DataSaver.save_results(specimen)
                context.status_bar.update(f"Saved results for {specimen_id}", level="info")
            except Exception as e:
                context.status_bar.update(f"Error saving results for {specimen_id}: {e}", level="error")

        context.status_bar.update("CarlQuant analysis complete.", level="success")

    Thread(target=worker, daemon=True).start()

