#!/usr/bin/env python3
"""
Reference script for ONN4ARG ontology-aware ARG prediction.

Reads protein FASTA from /job/stage/onn4arg/, runs alignment and prediction,
and writes results to /job/analysis/onn4arg/.

This is a *reference* template. The LLM should copy this to
/job/reproducibility/generated_scripts/onn4arg_<YYYYMMDD-HHMMSS>.py,
adapt paths / modes to the actual data, then execute it.

ONN4ARG repository is baked into the downstream-dl image at /repositories/ONN4ARG/.
External tools required: Diamond (blastp) and HHblits.
"""
import os
import sys
import json
import subprocess

# ── Path conventions (v3 downstream container) ───────────────────────────────
STAGE_DIR     = "/job/stage/onn4arg"
ANALYSIS_DIR  = "/job/analysis/onn4arg"
GENERATED_DIR = "/job/reproducibility/generated_scripts"

# ONN4ARG repository lives in the image at a fixed path
REPO_DIR = "/repositories/ONN4ARG"


def run_command(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    print(result.stdout)
    return result


def check_external_tools():
    """Verify Diamond and HHblits are available before running."""
    for tool in ("diamond", "hhblits"):
        result = subprocess.run(["which", tool], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: '{tool}' not found on PATH. "
                  "Ensure the downstream-dl image was built correctly.", file=sys.stderr)
            sys.exit(1)
    print("External tools (diamond, hhblits) verified.")


def main():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(GENERATED_DIR, exist_ok=True)

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    check_external_tools()

    input_fasta = os.path.join(STAGE_DIR, "input.fasta")
    if not os.path.exists(input_fasta):
        print(f"Error: Missing input FASTA {input_fasta}", file=sys.stderr)
        sys.exit(1)

    # Model assets: prefer staged copy, fall back to repo default
    model_dir = os.path.join(STAGE_DIR, "model")
    if not os.path.isdir(model_dir):
        model_dir = os.path.join(REPO_DIR, "model")
    print(f"Using ONN4ARG model directory: {model_dir}")

    # ── Run ONN4ARG quick prediction (runs from repo dir) ─────────────────────
    # predict.sh uses relative paths internally so we must cd into the repo.
    run_command(
        ["bash", "predict.sh", model_dir],
        cwd=REPO_DIR,
    )

    # ── Write reproducibility metadata ───────────────────────────────────────
    meta = {
        "skill": "onn4arg",
        "packages": {
            "torch":    "2.0.1",
            "h5py":     "3.9.0",
            "numpy":    "1.24.3",
            "tqdm":     "4.65.0",
            "diamond":  ">=2.0",
            "hhblits":  ">=3.3",
        },
        "parameters": {
            "input":          input_fasta,
            "model_dir":      model_dir,
            "identity":       30,
            "max_target_seqs": 0,
            "cpu":            1,
        },
        "random_seed": 42,
        "decisions": "Ran ONN4ARG quick prediction mode with default alignment parameters.",
    }
    with open(os.path.join(ANALYSIS_DIR, "onn4arg_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("ONN4ARG workflow complete. Results in", ANALYSIS_DIR)


if __name__ == "__main__":
    main()
