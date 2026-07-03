#!/usr/bin/env python3
"""
Reference script for BGC-Prophet pipeline.

Reads amino-acid FASTA from /job/stage/bgc_prophet/genomes/, runs the
BGC-Prophet end-to-end pipeline, and writes results to /job/analysis/bgc_prophet/.

This is a *reference* template. The LLM should copy this to
/job/reproducibility/generated_scripts/bgc-prophet_<YYYYMMDD-HHMMSS>.py,
adapt thresholds / paths to the actual data, then execute it.
"""
import os
import sys
import json
import subprocess

# ── Path conventions (v3 downstream container) ───────────────────────────────
STAGE_DIR     = "/job/stage/bgc_prophet"
ANALYSIS_DIR  = "/job/analysis/bgc_prophet"
GENERATED_DIR = "/job/reproducibility/generated_scripts"


def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    print(result.stdout)
    return result


def main():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(GENERATED_DIR, exist_ok=True)

    # ── Validate inputs ───────────────────────────────────────────────────────
    genomes_dir = os.path.join(STAGE_DIR, "genomes")
    annotator   = os.path.join(STAGE_DIR, "annotator.pt")
    classifier  = os.path.join(STAGE_DIR, "classifier.pt")

    if not os.path.isdir(genomes_dir):
        print(f"Error: Missing genomes directory {genomes_dir}", file=sys.stderr)
        sys.exit(1)

    fasta_files = [f for f in os.listdir(genomes_dir) if f.endswith(".fasta")]
    if not fasta_files:
        print(f"Error: No .fasta files found in {genomes_dir}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(fasta_files)} genome FASTA file(s).")

    # ── Build BGC-Prophet end-to-end command ──────────────────────────────────
    cmd = [
        "bgc_prophet", "pipeline",
        "--genomesDir",   genomes_dir,
        "--modelPath",    annotator if os.path.exists(annotator) else "./annotator.pt",
        "--saveIntermediate",
        "--name",         "task",
        "--threshold",    "0.5",
        "--max_gap",      "3",
        "--min_count",    "2",
        "--outputPath",   ANALYSIS_DIR,
    ]
    if os.path.exists(classifier):
        cmd.extend(["--classifierPath", classifier, "--classify_t", "0.5"])

    run_command(cmd)

    # ── Write reproducibility metadata ───────────────────────────────────────
    meta = {
        "skill": "bgc-prophet",
        "packages": {
            "bgc_prophet": "0.1.1",
            "torch":       "2.0.1",
            "fair-esm":    "2.0.0",
            "biopython":   "1.81",
            "lmdb":        "1.4.1",
            "pandas":      "2.0.3",
            "numpy":       "1.24.3",
            "scikit-learn": "1.3.1",
            "tqdm":        "4.65.0",
        },
        "parameters": {
            "threshold": 0.5,
            "max_gap":   3,
            "min_count": 2,
            "device":    "cuda",
        },
        "random_seed": 42,
        "decisions": "Ran end-to-end BGC-Prophet pipeline with default thresholds.",
    }
    with open(os.path.join(ANALYSIS_DIR, "bgc_prophet_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("BGC-Prophet workflow complete. Results in", ANALYSIS_DIR)


if __name__ == "__main__":
    main()
