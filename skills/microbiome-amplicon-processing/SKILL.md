---
name: microbiome-amplicon-processing
description: >
  Use this skill when the user needs DADA2-based processing of 16S or ITS amplicon FASTQ files into ASVs, including quality filtering, error learning, denoising, merging, and chimera removal.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# Amplicon Processing

## Responsibilities
This skill handles paired-end 16S and ITS processing with quality inspection, filtering, error learning, denoising, merging, chimera removal, and read tracking. It consumes staged inputs under `/job/stage/microbiome-amplicon-processing/` and optional `/job/stage/metadata.tsv`, and it writes reproducible results to `/job/analysis/microbiome-amplicon-processing/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it to produce ASV tables, representative sequences, and QC summaries. Do not use it to guess trimming parameters without inspecting the quality profiles or to claim success when read retention or merge rates are poor.

## Companion Documents
- `references/usage-guide.md` — quick-start DADA2 workflow notes, parameters, and troubleshooting.
- `scripts/dada2_workflow.R` — example R workflow for paired-end DADA2 processing.

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
  microbiome-amplicon-processing/
    raw_reads/    # required paired-end FASTQ.gz files
    options.yaml  # optional truncation, filtering, primer, or threading hints
    notes.txt     # optional sample or assay notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual read pairs. Demultiplexed paired-end FASTQ files are required. If ITS primer trimming is requested, primer sequences or a primer-removal note must be present. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate QC values, parameters, or results.

If optional metadata is absent, proceed without it and focus on the read-level QC and ASV workflow.

## Output Conventions
Write all results to `/job/analysis/microbiome-amplicon-processing/`:

- `results/seqtab_nochim.rds`
- `results/seqtab_nochim.tsv`
- `results/read_tracking.csv`
- `results/quality_profiles.pdf`
- `reports/quality_summary.md`
- `figures/error_rates.png`
- `microbiome-amplicon-processing_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-amplicon-processing_<YYYYMMDD-HHMMSS>.R`
- `logs/microbiome-amplicon-processing.log`

The metadata file must record package versions, input paths, output paths, parameters, any primer trimming decisions, reference files consulted, and a brief explanation of the QC choices. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read Data
Inspect the raw reads and quality profiles, identify the marker and chemistry, and determine whether primer trimming or ITS-specific handling is needed. If the request is ambiguous, ask for the minimum needed details before choosing trim points.

### Step 2 — Analysis
Filter and trim reads, learn error rates, denoise forward and reverse reads, merge pairs when paired-end overlap is sufficient, and remove chimeras with a conservative method. Inspect quality before truncation and do not choose parameters blindly.

### Step 3 — Archiving
Summarize read retention at each stage, flag weak overlap or excessive read loss, and save the script and metadata so the analysis can be reproduced.

## Available Libraries / 可用库
R: `dada2` `Biostrings` `phyloseq` `DECIPHER` `phangorn` `picante`
External helper: `cutadapt` for primer trimming when needed

## Strict Rules / 严格规则
1. Never silently skip quality review, read loss, merge failures, or chimera burden.
2. Do not guess truncation settings without inspecting the actual quality profiles.
3. Do not claim ITS should be truncated to a fixed length unless the data and request justify it.
4. Report read tracking and retention statistics explicitly.
5. Do not fabricate ASVs, representative sequences, or downstream counts.
6. Keep primer trimming and chimera filtering conservative unless the request specifies otherwise.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-amplicon-processing.R` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/microbiome-amplicon-processing_<YYYYMMDD-HHMMSS>.R` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with DADA2 and quality-profile tooling to confirm the read pairing and sample structure.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's trimming, filtering, and chimera settings.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/microbiome-amplicon-processing/scripts/`; that directory is for templates, not job artifacts.
