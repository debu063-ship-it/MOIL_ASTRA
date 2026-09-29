#!/usr/bin/env python3
"""
MOIL SIH26009 — Master Runner for Reviewed Data Capping, Feature Engineering & Statistical Inference Pipeline
=============================================================================================================
Executes the four reviewed workflow stages sequentially:
  1. cap_and_flag_reviewed.py        -> Generates data/capped_reviewed/ and model-ready splits
  2. feature_engineering_reviewed.py -> Recomputes derived features and outputs documentation
  3. validate_capping_reviewed.py    -> Audits accounting identities, temperature ordering, and ranges
  4. statistical_inference_reviewed.py -> Computes FDR-corrected MWU, Moran's I, and spatial validation

Usage:
  python scripts/run_reviewed_pipeline.py
"""

import sys
import subprocess
from pathlib import Path

BASE = Path(r"c:\Users\Debu018\Downloads\MOIL SIH26009")
SCRIPTS_DIR = BASE / "scripts"

stages = [
    ("Stage 1: Reviewed Capping & Outlier Flagging", SCRIPTS_DIR / "cap_and_flag_reviewed.py"),
    ("Stage 2: Reviewed Feature Engineering & Recomputation", SCRIPTS_DIR / "feature_engineering_reviewed.py"),
    ("Stage 3: Data Integrity & Capping Validation Suite", SCRIPTS_DIR / "validate_capping_reviewed.py"),
    ("Stage 4: Reviewed Statistical Inference & Hypothesis Testing", SCRIPTS_DIR / "statistical_inference_reviewed.py"),
]

print("=" * 90)
print("MOIL SIH26009 — EXECUTING REVIEWED PIPELINE END-TO-END")
print("=" * 90)

for title, script_path in stages:
    print(f"\n>>> Running {title}...")
    cmd = [sys.executable, str(script_path)]
    result = subprocess.run(cmd, cwd=str(BASE))
    if result.returncode != 0:
        print(f"\n[ERROR] Pipeline failed at {title} with exit code {result.returncode}!")
        sys.exit(result.returncode)
    print(f"--- Finished {title} successfully ---")

print("\n" + "=" * 90)
print("[SUCCESS] All 4 pipeline stages executed cleanly end-to-end!")
print("Outputs available in:")
print("  - Data files: data/capped_reviewed/")
print("  - Reports & Documentation: outputs/data_capping_review/")
print("  - Diagnostic plots: outputs/eda_plots/")
print("=" * 90)
