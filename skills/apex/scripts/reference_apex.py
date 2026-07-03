#!/usr/bin/env python3
"""
Reference script for APEX pathogen antimicrobial activity prediction.

Reads peptide FASTA from /job/stage/apex/, runs the APEX ensemble model,
and writes predicted MICs to /job/analysis/apex/.

This is a *reference* template. The LLM should copy this to
/job/reproducibility/generated_scripts/apex_<YYYYMMDD-HHMMSS>.py,
adapt it to the actual data, then execute the customised script.

APEX source code and pretrained models are baked into the downstream-dl image
at /repositories/apex-pathogen-main/.
"""
import os
import sys
import json
import glob
import math

import numpy as np
import pandas as pd
import torch
from Bio import SeqIO
from tqdm import tqdm

# ── Path conventions (v3 downstream container) ───────────────────────────────
STAGE_DIR     = "/job/stage/apex"
ANALYSIS_DIR  = "/job/analysis/apex"
GENERATED_DIR = "/job/reproducibility/generated_scripts"

# APEX source lives in the image at a fixed path
APEX_REPO  = "/repositories/apex-pathogen-main"
MODELS_DIR = os.path.join(APEX_REPO, "APEX_pathogen_models")

# Make APEX modules importable
sys.path.insert(0, APEX_REPO)
from APEX_models import AMP_model          # noqa: E402
from utils import make_vocab, onehot_encoding  # noqa: E402


def main():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(GENERATED_DIR, exist_ok=True)

    # ── Locate input FASTA ────────────────────────────────────────────────────
    input_fasta = os.path.join(STAGE_DIR, "peptides.fasta")
    if not os.path.exists(input_fasta):
        print(f"Error: Missing input FASTA {input_fasta}", file=sys.stderr)
        sys.exit(1)

    # ── Device selection ─────────────────────────────────────────────────────
    use_gpu    = torch.cuda.is_available()
    device_str = "cuda" if use_gpu else "cpu"
    print(f"Device: {device_str}")

    # ── Pathogen list (must match training order) ─────────────────────────────
    pathogen_list = [
        "A. baumannii ATCC 19606",
        "E. coli ATCC 11775",
        "E. coli AIC221",
        "E. coli AIC222",
        "K. pneumoniae ATCC 13883",
        "P. aeruginosa PA01",
        "P. aeruginosa PA14",
        "S. aureus ATCC 12600",
        "S. aureus (ATCC BAA-1556) - MRSA",
        "vancomycin-resistant E. faecalis ATCC 700802",
        "vancomycin-resistant E. faecium ATCC 700221",
    ]

    max_len = 52
    word2idx, _ = make_vocab()

    # ── Load pretrained ensemble models ──────────────────────────────────────
    model_files = sorted(glob.glob(os.path.join(MODELS_DIR, "APEX_*")))
    if not model_files:
        print(f"Error: No APEX models found in {MODELS_DIR}", file=sys.stderr)
        sys.exit(1)

    apex_models = []
    for mpath in model_files:
        model = torch.load(mpath, map_location=device_str)
        model.eval()
        apex_models.append(model)
    print(f"Loaded {len(apex_models)} APEX ensemble models.")

    # ── Load and validate peptide sequences ──────────────────────────────────
    seq_list = []
    skipped  = 0
    for record in SeqIO.parse(input_fasta, "fasta"):
        sequence = str(record.seq)
        if len(sequence) <= 50:
            seq_list.append(sequence)
        else:
            print(f"Warning: {record.id} has {len(sequence)} aa (>50) — skipped.", file=sys.stderr)
            skipped += 1

    if skipped:
        print(f"Skipped {skipped} sequences exceeding 50 aa.", file=sys.stderr)
    if not seq_list:
        print("Error: No valid sequences loaded (must be <= 50 aa)", file=sys.stderr)
        sys.exit(1)

    seq_array  = np.array(seq_list)
    batch_size = 8192

    # ── Ensemble prediction ───────────────────────────────────────────────────
    AMP_sum = None
    for ensemble_id, model in enumerate(apex_models):
        model = model.to(device_str).eval()
        data_len    = len(seq_array)
        num_batches = int(math.ceil(data_len / batch_size))
        print(f"Predicting with model {ensemble_id + 1}/{len(apex_models)} "
              f"({data_len} sequences, {num_batches} batches)")

        AMP_pred = None
        for i in tqdm(range(num_batches)):
            seq_batch = seq_array[i * batch_size:(i + 1) * batch_size]
            seq_rep   = onehot_encoding(seq_batch, max_len, word2idx)
            X_seq     = torch.LongTensor(seq_rep).to(device_str)
            with torch.no_grad():
                batch_out = model(X_seq).cpu().numpy()
            # Transform log-scale output back to MIC (µM)
            batch_out = 10 ** (6 - batch_out)
            AMP_pred  = batch_out if AMP_pred is None else np.vstack([AMP_pred, batch_out])

        AMP_sum = AMP_pred if AMP_sum is None else AMP_sum + AMP_pred

    AMP_pred = AMP_sum / len(apex_models)
    df = pd.DataFrame(data=AMP_pred, columns=pathogen_list, index=seq_list)

    output_csv = os.path.join(ANALYSIS_DIR, "Predicted_MICs.csv")
    df.to_csv(output_csv)
    print(f"MIC predictions saved to {output_csv}")

    # ── Write reproducibility metadata ───────────────────────────────────────
    meta = {
        "skill": "apex",
        "packages": {
            "torch":         torch.__version__,
            "numpy":         np.__version__,
            "pandas":        pd.__version__,
            "biopython":     "1.81",
            "scikit-learn":  "1.3.1",
            "scipy":         "1.11.2",
            "tqdm":          "4.65.0",
        },
        "parameters": {
            "gpu_mode":           int(use_gpu),
            "batch_size":         batch_size,
            "max_peptide_length": 50,
            "num_ensemble_models": len(apex_models),
        },
        "random_seed": 42,
        "decisions": f"Ensemble prediction averaged over {len(apex_models)} pretrained APEX models.",
    }
    with open(os.path.join(ANALYSIS_DIR, "apex_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("APEX workflow complete. Results in", ANALYSIS_DIR)


if __name__ == "__main__":
    main()
