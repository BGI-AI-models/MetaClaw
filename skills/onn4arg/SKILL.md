---
name: onn4arg
description: >
    Use when an agent needs to run or explain ONN4ARG for ontology-aware ARG
    prediction, including environment setup, sequence alignment, feature
    preparation, and final inference.
allowed-tools: Bash(python *) Read Write
disable-model-invocation: false
---

# ONN4ARG

## Responsibilities

This skill operates ONN4ARG for ontology-aware antibiotic resistance gene
(ARG) annotation. It consumes protein FASTA sequences from `/job/stage/onn4arg/`,
runs alignment-based feature generation (Diamond, HHblits), and performs
model inference to produce ARG predictions.

It does **not** assemble contigs, call genes, or perform taxonomic
classification. Input must be protein sequences in FASTA format.

## Input Conventions

This skill expects the following layout under `/job/stage/`:

```
/job/stage/onn4arg/
   input.fasta            # query protein FASTA file (single or multiple seqs)
   model/                 # model assets directory (if not globally installed)
   metadata.tsv           # optional, read if present
```

If required inputs are missing, this skill must report the issue and halt;
it **must not** fabricate data.

## Output Conventions

This skill writes its results to `/job/analysis/onn4arg/`:

```
/job/analysis/onn4arg/
*.lst                    # sequence list files
*-seq.aln                # Diamond alignment output
*-prof.aln               # HHblits alignment output
*-seq.txt                # converted sequence alignment features
*-prof.txt               # converted profile alignment features
*.out                    # final ARG prediction output
onn4arg_meta.json        # must record package versions, parameters,
                         # and a brief explanation of decisions
```

## Workflow

### Step 1 — Read Data

Read the query FASTA file from `/job/stage/onn4arg/input.fasta`.
Verify that model assets (Diamond database, HHblits database, tree file,
model `.sav`) are available under `/repositories/ONN4ARG/model/`.

### Step 2 — Analysis

Run the ONN4ARG workflow. Reference scripts under `/pipeline/scripts/` can be
cited here. Two modes are supported:

**Quick mode** (single-sequence):
```bash
predict.sh model/example
```

**Batch mode**:
```bash
run.sh Multiple_FASTA_filename
```

**Step-by-step mode**:
1. `fa2lst.pl` — generate sequence list.
2. `diamond blastp` — sequence alignment.
3. `aln2txt.pl` — convert alignment to features.
4. `hhblits` — profile alignment.
5. `aln2txt.pl` — convert profile alignment.
6. `predict.py` — run ONNX model inference.

### Step 3 — Archiving

Save the generated script to `/job/reproducibility/generated_scripts/` and
write out `onn4arg_meta.json`:

```json
{
  "skill": "onn4arg",
  "packages": {
    "torch": "2.0.1",
    "h5py": "3.9.0",
    "numpy": "1.24.3",
    "tqdm": "4.65.0"
  },
  "parameters": {"identity": 30, "max_target_seqs": 0, "cpu": 1},
  "random_seed": 42,
  "decisions": "Brief explanation of alignment and prediction choices."
}
```

## Strict Rules

1. Never silently skip data anomalies (e.g., NaNs, missing samples) — they
   must be reported.
2. All stochastic/random processes must use the `random_seed` specified in the metadata.
3. Verify Diamond and HHblits are installed before running alignment steps.
4. Ensure model assets are downloaded before attempting prediction.
5. Do not proceed if FASTA inputs do not match the expected script assumptions.
