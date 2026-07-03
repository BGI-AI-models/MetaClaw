---
name: mgm
description: >
    Use when an agent needs to work with the MGM microbiome foundation model for
    corpus construction, pretraining, finetuning, prediction, generation, or
    reconstruction from abundance tables.
allowed-tools: Bash(python *) Read Write
disable-model-invocation: false
---

# MGM

## Responsibilities

This skill operates the MGM (Microbiome Generative Model) toolchain for
microbiome modeling tasks. It consumes abundance tables from `/job/stage/mgm/`,
constructs corpora, runs pretraining or supervised training, performs
prediction or synthetic generation, and reconstructs abundance-style outputs.

It does **not** handle raw sequencing reads, metagenomic assembly, or
taxonomic profiling. Those steps must be completed upstream and their outputs
placed in `/job/stage/` before this skill is invoked.

## Input Conventions

This skill expects the following layout under `/job/stage/`:

```
/job/stage/
mgm/
  abundance.csv       # or .tsv, .hdf5 — sample-by-taxa abundance table
  labels.csv          # optional, sample identifiers + labels for supervised tasks
  metadata.tsv        # optional, read if present
```

If required inputs are missing, this skill must report the issue and halt;
it **must not** fabricate data.

## Output Conventions

This skill writes its results to `/job/analysis/mgm/`:

```
/job/analysis/mgm/
corpus.pkl            # constructed MicroCorpus
models/               # pretrained, finetuned, or supervised model checkpoints
predictions.csv       # prediction outputs
reconstruction/       # abundance reconstruction outputs
mgm_meta.json         # must record package versions, parameters,
                      # and a brief explanation of decisions
```

## Workflow

### Step 1 — Read Data

Read the abundance table from `/job/stage/mgm/abundance.{csv,tsv,h5}`.
Verify the file type and ensure sample identifiers are present.
If labels are required for supervised tasks, read `/job/stage/mgm/labels.csv`.

### Step 2 — Analysis

Run the MGM workflow using the CLI or Python API. Reference scripts under
`/pipeline/scripts/` can be cited here. Typical sequence:

1. `mgm construct` — build corpus from abundance table.
2. `mgm pretrain` or `mgm train` / `mgm finetune` — model training.
3. `mgm predict` or `mgm generate` — inference or synthetic data.
4. `mgm reconstruct` — convert generated corpora back to abundance format.

### Step 3 — Archiving

Save the generated script to `/job/reproducibility/generated_scripts/` and
write out `mgm_meta.json`:

```json
{
  "skill": "mgm",
  "packages": {
    "mgm": "0.5.8",
    "torch": "2.0.1",
    "transformers": "4.33.3",
    "pytorch_lightning": "2.0.6",
    "accelerate": "0.23.0",
    "pandas": "2.0.3",
    "numpy": "1.24.3",
    "scikit-learn": "1.3.1",
    "tqdm": "4.65.0"
  },
  "parameters": {"mode": "construct|pretrain|train|finetune|predict|generate|reconstruct", "max_len": 512},
  "random_seed": 42,
  "decisions": "Brief explanation of the analysis choices made."
}
```

## Strict Rules

1. Never silently skip data anomalies (e.g., NaNs, missing samples) — they
   must be reported.
2. All stochastic/random processes must use the `random_seed` specified in the metadata.
3. Distinguish `train` (supervised from scratch) from `finetune` (adapt a pretrained model).
4. Do not use this skill for unrelated microbiome tools in this repository.
