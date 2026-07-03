---
name: bgc-prophet
description: >
    Use when an agent needs to work with the BGC-Prophet pipeline for BGC
    detection, embedding extraction, genome organization, prediction, output
    generation, or classification from amino-acid FASTA inputs.
allowed-tools: Bash(python *) Read Write
disable-model-invocation: false
---

# BGC-Prophet

## Responsibilities

This skill operates BGC-Prophet for identifying and classifying biosynthetic
gene clusters (BGCs) from amino-acid FASTA inputs. It consumes protein
sequences from `/job/stage/bgc_prophet/`, extracts ESM embeddings, organizes
and splits genome inputs, predicts BGC genes, and applies classification models.

It does **not** accept nucleotide FASTA files directly or perform gene
calling. Inputs must be amino-acid sequences produced upstream.

## Input Conventions

This skill expects the following layout under `/job/stage/`:

```
/job/stage/
bgc_prophet/
  genomes/               # directory of amino-acid FASTA files (.fasta)
  annotator.pt           # pretrained detection model checkpoint
  classifier.pt          # pretrained classification model checkpoint
  metadata.tsv           # optional, read if present
```

If required inputs are missing, this skill must report the issue and halt;
it **must not** fabricate data.

## Output Conventions

This skill writes its results to `/job/analysis/bgc_prophet/`:

```
/job/analysis/bgc_prophet/
organize.csv
split.csv
intermediate_prediction.npy
output.csv                 # final detection results
classify_output.csv        # classification results
figures/                   # optional visualization outputs
bgc_prophet_meta.json      # must record package versions, parameters,
                           # and a brief explanation of decisions
```

## Workflow

### Step 1 — Read Data

Read amino-acid FASTA files from `/job/stage/bgc_prophet/genomes/`.
Verify that sequences contain valid amino-acid characters.
Confirm model checkpoints (`annotator.pt`, `classifier.pt`) are present.

### Step 2 — Analysis

Run the BGC-Prophet workflow using the CLI. Reference scripts under
`/pipeline/scripts/` can be cited here. Typical sequence:

1. `bgc_prophet organize` — organize and split genome inputs.
2. `bgc_prophet split` — split sequences for batch processing.
3. `bgc_prophet extract` — extract ESM embeddings (if not pre-computed).
4. `bgc_prophet predict` — detect BGC genes.
5. `bgc_prophet output` — postprocess detections into output tables.
6. `bgc_prophet classify` — classify predicted BGCs.

Alternatively, run the end-to-end `bgc_prophet pipeline` command.

### Step 3 — Archiving

Save the generated script to `/job/reproducibility/generated_scripts/` and
write out `bgc_prophet_meta.json`:

```json
{
  "skill": "bgc-prophet",
  "packages": {
    "bgc_prophet": "0.1.1",
    "torch": "2.0.1",
    "fair-esm": "2.0.0",
    "biopython": "1.81",
    "lmdb": "1.4.1",
    "pandas": "2.0.3",
    "numpy": "1.24.3",
    "scikit-learn": "1.3.1",
    "tqdm": "4.65.0"
  },
  "parameters": {"threshold": 0.5, "max_gap": 3, "min_count": 2, "device": "cuda"},
  "random_seed": 42,
  "decisions": "Brief explanation of detection and classification thresholds."
}
```

## Strict Rules

1. Never silently skip data anomalies (e.g., NaNs, missing samples) — they
   must be reported.
2. All stochastic/random processes must use the `random_seed` specified in the metadata.
3. Input must be amino-acid FASTA, not nucleotide FASTA.
4. Replace unsupported amino-acid symbols before embedding extraction.
5. Verify CUDA availability before setting `--device cuda`.
