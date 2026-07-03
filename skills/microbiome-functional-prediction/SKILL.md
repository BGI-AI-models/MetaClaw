---
name: microbiome-functional-prediction
description: >
  Use this skill when the user wants PICRUSt2-based functional prediction from 16S or other marker-gene ASVs, including KO, EC, and pathway inference and NSTI quality review.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# Functional Prediction

## Responsibilities
This skill handles PICRUSt2 input preparation, functional inference, pathway reconstruction, and NSTI quality control. It consumes staged inputs under `/job/stage/microbiome-functional-prediction/` and optional `/job/stage/metadata.tsv`, and it writes reproducible results to `/job/analysis/microbiome-functional-prediction/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it to infer KEGG orthologs, EC numbers, or pathway abundances from marker-gene data. Do not use it to describe predicted functions as directly observed measurements or to hide high-NSTI warnings.

## Companion Documents
- `references/usage-guide.md` — quick-start guidance, NSTI notes, output file descriptions, and limitations.
- `scripts/run_picrust2.sh` — example shell workflow for running PICRUSt2.

If a companion document conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0 
- Network access: none (`--network none`, per gateway default)
- Mounted paths:

| Path | Permission | Contents |
|---|---|---|
| `/job/stage/` | ro | upstream artifacts + non-FASTQ files from DATA_DIR (e.g. `metadata.tsv`, hardlinked by `orchestrator.sh`) |
| `/job/analysis/` | rw | this skill's analysis outputs |
| `/job/reproducibility/` | rw | generated scripts, logs, *_meta.json |
| `/pipeline/scripts/` | ro | reference scripts (templates) |

If the concrete skill runs outside a container, replace the table with the equivalent runtime layout.

## Input Conventions
This skill expects the following layout under `/job/stage/`:

```text
/job/stage/
  microbiome-functional-prediction/
    data/         # required ASV sequences and abundance table, or exports ready for PICRUSt2
    options.yaml  # optional threads, output, pathway, or stratification hints
    notes.txt     # optional study notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. ASV sequences and an abundance table are required. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate NSTI values, pathway outputs, or input files.

If optional metadata is absent, proceed without it and focus on the prediction and NSTI outputs.

## Output Conventions
Write all results to `/job/analysis/microbiome-functional-prediction/`:

- `results/ko_metagenome.tsv`
- `results/ec_metagenome.tsv`
- `results/pathway_abundance.tsv`
- `results/nsti_summary.tsv`
- `reports/functional_prediction_summary.md`
- `figures/nsti_distribution.png`
- `microbiome-functional-prediction_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-functional-prediction_<YYYYMMDD-HHMMSS>.sh`
- `logs/microbiome-functional-prediction.log`

The metadata file must record package versions, input paths, output paths, PICRUSt2 parameters, NSTI summaries, reference files consulted, and a brief explanation of the inference choices. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read the request
Determine whether the user wants a full PICRUSt2 pipeline, a specific output type, or a downstream comparison of predicted pathways. If the request is ambiguous, ask for the minimum needed details before running the pipeline.

### Step 2 — Analysis
Validate the ASV sequences and abundance table, run PICRUSt2, and capture the requested outputs and NSTI quality metrics.

### Step 3 — Archiving
Summarize the prediction outputs and quality metrics, make the limitations explicit, and save the script and metadata so another analyst can reproduce the workflow.

## Available Libraries / 可用库
Python: `pandas` `biopython` `pyyaml`
R: optional downstream visualization only
External tools: PICRUSt2 CLI

## Strict Rules / 严格规则
1. Never describe predicted functions as directly measured.
2. Always report NSTI and the interpretation of prediction confidence.
3. Do not hide high-NSTI or low-confidence taxa.
4. Do not fabricate pathway abundances or database outputs.
5. Report the marker-gene basis and the major limitation that predictions are inferred from phylogeny.
6. Keep prediction outputs separate from downstream statistical comparisons.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-functional-prediction.sh` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/microbiome-functional-prediction_<YYYYMMDD-HHMMSS>.sh` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with PICRUSt2-prep tooling to confirm ASV and abundance table compatibility.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's PICRUSt2 parameters and output selection.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/microbiome-functional-prediction/scripts/`; that directory is for templates, not job artifacts.
