---
name: apex
description: >
    Use when an agent needs to predict species-specific antimicrobial activity
    (MICs) of peptides against pathogens using the APEX deep-learning model.
    Triggered for peptide FASTA input <= 50 amino acids.
allowed-tools: Bash(python *) Read Write
disable-model-invocation: false
---

# APEX

## Responsibilities

This skill operates APEX (Antimicrobial Peptide EXpert) to predict
species-specific minimum inhibitory concentrations (MICs) of peptides
against 11 pathogens. It consumes peptide FASTA sequences from
`/job/stage/apex/`, runs an ensemble of 8 pretrained deep-learning models,
and outputs predicted MIC values.

It does **not** design novel peptides, perform molecular docking, or
predict activity against pathogens outside the built-in list. Inputs
must be peptide sequences of 50 amino acids or fewer.

## Input Conventions

This skill expects the following layout under `/job/stage/`:

```
/job/stage/apex/
  peptides.fasta         # peptide FASTA file (sequences <= 50 aa)
  metadata.tsv           # optional, read if present
```

If required inputs are missing, this skill must report the issue and halt;
it **must not** fabricate data.

## Output Conventions

This skill writes its results to `/job/analysis/apex/`:

```
/job/analysis/apex/
Predicted_MICs.csv       # predicted MICs for 11 pathogens (unit: uM)
figures/                 # optional visualization outputs
apex_meta.json           # must record package versions, parameters,
                         # and a brief explanation of decisions
```

## Workflow

### Step 1 — Read Data

Read peptide sequences from `/job/stage/apex/peptides.fasta`.
Verify that all sequences are 50 amino acids or fewer; truncate or
filter longer sequences as appropriate.
Confirm that pretrained APEX model files exist under
`/repositories/apex-pathogen-main/APEX_pathogen_models/`.

### Step 2 — Analysis

Run APEX prediction using the reference script. Reference scripts under
`/pipeline/scripts/` can be cited here.

```bash
python APEX_predict.py -i /job/stage/apex/peptides.fasta -g 1 -o /job/analysis/apex/Predicted_MICs.csv
```

Use `-g 1` for GPU mode and `-g 0` for CPU mode.
Predictions from 8 base learners are averaged to generate the final
activity prediction.

### Step 3 — Archiving

Save the generated script to `/job/reproducibility/generated_scripts/` and
write out `apex_meta.json`:

```json
{
  "skill": "apex",
  "packages": {
    "torch": "2.0.1",
    "numpy": "1.24.3",
    "pandas": "2.0.3",
    "biopython": "1.81",
    "scikit-learn": "1.3.1",
    "scipy": "1.11.2",
    "tqdm": "4.65.0"
  },
  "parameters": {"gpu_mode": 1, "batch_size": 8192, "max_peptide_length": 50},
  "random_seed": 42,
  "decisions": "Ensemble prediction averaged over 8 pretrained APEX models."
}
```

## Strict Rules

1. Never silently skip data anomalies (e.g., NaNs, missing samples) — they
   must be reported.
2. All stochastic/random processes must use the `random_seed` specified in the metadata.
3. Sequences longer than 50 amino acids must be truncated or filtered; do
   not silently skip them.
4. Verify GPU availability before enabling `-g 1`.
5. Peptide FASTA must contain amino-acid sequences, not nucleotide sequences.
