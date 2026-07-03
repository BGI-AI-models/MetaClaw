#!/usr/bin/env python3
"""
Reference script for MGM microbiome foundation model.

Reads abundance data from /job/stage/mgm/, runs the MGM construct + predict
workflow, and writes results to /job/analysis/mgm/.

This is a *reference* template. The LLM should copy this to
/job/reproducibility/generated_scripts/mgm_<YYYYMMDD-HHMMSS>.py,
adapt it to the actual data (file names, modes, hyperparameters),
then execute the customised script.
"""
import os
import sys
import json
import subprocess

# ── Path conventions (v3 downstream container) ───────────────────────────────
STAGE_DIR     = "/job/stage/mgm"
ANALYSIS_DIR  = "/job/analysis/mgm"
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

    # ── Locate abundance table ────────────────────────────────────────────────
    abundance_path = None
    for fname in ("abundance.csv", "abundance.tsv", "abundance.h5"):
        candidate = os.path.join(STAGE_DIR, fname)
        if os.path.exists(candidate):
            abundance_path = candidate
            break

    if abundance_path is None:
        print(f"Error: No abundance file found in {STAGE_DIR}", file=sys.stderr)
        sys.exit(1)

    corpus_path = os.path.join(ANALYSIS_DIR, "corpus.pkl")
    model_path  = os.path.join(ANALYSIS_DIR, "models", "pretrained_model")
    pred_dir    = os.path.join(ANALYSIS_DIR, "predictions")

    os.makedirs(os.path.join(ANALYSIS_DIR, "models"), exist_ok=True)
    os.makedirs(pred_dir, exist_ok=True)

    # ── Step 1: construct corpus ──────────────────────────────────────────────
    run_command([
        "mgm", "construct",
        "-i", abundance_path,
        "-o", corpus_path,
    ])

    # ── Step 2: pretrain (skip if checkpoint already exists) ─────────────────
    if not os.path.exists(model_path):
        run_command([
            "mgm", "pretrain",
            "-i", corpus_path,
            "-o", model_path,
        ])

    # ── Step 3: predict (only when labels are present) ───────────────────────
    labels_path = os.path.join(STAGE_DIR, "labels.csv")
    if os.path.exists(labels_path):
        run_command([
            "mgm", "predict", "-E",
            "-i", corpus_path,
            "-l", labels_path,
            "-m", model_path,
            "-o", os.path.join(pred_dir, "predictions.csv"),
        ])
    else:
        print("No labels.csv found — skipping supervised prediction.")

    # ── Write reproducibility metadata ───────────────────────────────────────
    meta = {
        "skill": "mgm",
        "packages": {
            "microformer_mgm": "0.5.8",
            "torch":           "2.0.1",
            "transformers":    "4.33.3",
            "pytorch_lightning": "2.0.6",
            "accelerate":      "0.23.0",
            "pandas":          "2.0.3",
            "numpy":           "1.24.3",
            "scikit-learn":    "1.3.1",
            "tqdm":            "4.65.0",
        },
        "parameters": {
            "abundance_path": abundance_path,
            "corpus_path":    corpus_path,
            "model_path":     model_path,
        },
        "random_seed": 42,
        "decisions": "Constructed corpus, pretrained model if absent, ran prediction when labels present.",
    }
    with open(os.path.join(ANALYSIS_DIR, "mgm_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("MGM workflow complete. Results in", ANALYSIS_DIR)


if __name__ == "__main__":
    main()
