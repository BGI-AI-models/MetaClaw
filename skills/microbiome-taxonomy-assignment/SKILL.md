---
name: microbiome-taxonomy-assignment
description: >
  Use this skill when the user needs taxonomic assignment of ASVs or OTUs using databases such as SILVA, GTDB, UNITE, or RDP, including naive Bayes, IDTAXA, exact matching, and QIIME2 classifier workflows.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# Taxonomy Assignment

## Responsibilities
This skill handles database selection, classifier selection, confidence filtering, and taxonomy table formatting for microbiome data. It consumes staged inputs under `/job/stage/microbiome-taxonomy-assignment/` and optional `/job/stage/metadata.tsv`, and it writes reproducible results to `/job/analysis/microbiome-taxonomy-assignment/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it to assign bacterial, archaeal, fungal, or protist taxonomy after amplicon processing. Do not use it to overstate species-level certainty or to hide incomplete or low-confidence assignments.

## Companion Documents
- `references/usage-guide.md` — quick-start guidance, database comparisons, classifier notes, and confidence thresholds.
- `scripts/assign_silva.R` — example R workflow for SILVA-based assignment.

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
  microbiome-taxonomy-assignment/
    data/         # required ASV sequences, sequence tables, or phyloseq exports
    options.yaml  # optional database, classifier, confidence, or marker hints
    notes.txt     # optional study notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. ASV sequences or an equivalent feature table are required. The marker type and intended database family must be clear enough to select a classifier. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate taxonomy, confidence scores, or database versions.

If optional metadata is absent, proceed without it and keep confidence reporting conservative.

## Output Conventions
Write all results to `/job/analysis/microbiome-taxonomy-assignment/`:

- `results/taxonomy.tsv`
- `results/taxonomy_filtered.tsv`
- `results/assignment_summary.tsv`
- `reports/taxonomy_summary.md`
- `figures/confidence_distribution.png`
- `microbiome-taxonomy-assignment_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-taxonomy-assignment_<YYYYMMDD-HHMMSS>.R`
- `logs/microbiome-taxonomy-assignment.log`

The metadata file must record package versions, input paths, output paths, classifier and database identifiers, confidence thresholds, and a brief explanation of the assignment choices. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read the request
Determine whether the user wants database-backed naive Bayes assignment, IDTAXA, exact matching, or a QIIME2 classifier workflow. If the request is ambiguous, ask for the minimum needed details before choosing the classifier path.

### Step 2 — Assign taxonomy
Select the database and method that best matches the marker and organism group, run the assignment, and filter low-confidence calls when appropriate.

### Step 3 — Report and archive
Summarize rank coverage, confidence thresholds, and any unclassified levels, then save the script and metadata so another analyst can reproduce the taxonomy call.

## Available Libraries / 可用库
R: `dada2` `DECIPHER` `phyloseq` `vsearch` `qiime2R`

## Strict Rules / 严格规则
1. Never overstate species-level certainty.
2. Report the database, classifier, and confidence threshold used.
3. Do not hide low-confidence or unclassified taxa.
4. Do not fabricate taxonomy tables or bootstrap values.
5. Match the database to the marker type and taxonomic domain.
6. Keep confidence thresholds and rank-specific decisions explicit in the archived script.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-taxonomy-assignment.R` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/microbiome-taxonomy-assignment_<YYYYMMDD-HHMMSS>.R` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the appropriate taxonomy tooling to confirm marker type, database match, and feature-table shape.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's database, classifier, and confidence settings.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/microbiome-taxonomy-assignment/scripts/`; that directory is for templates, not job artifacts.
