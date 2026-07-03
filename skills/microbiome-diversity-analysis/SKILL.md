---
name: microbiome-diversity-analysis
description: >
  Use this skill when the user wants alpha or beta diversity analysis, ordination, rarefaction, or PERMANOVA for microbiome community data.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# Diversity Analysis

## Responsibilities
This skill handles alpha diversity, beta diversity, ordination, rarefaction, dispersion checks, and PERMANOVA-style testing. It consumes staged inputs under `/job/stage/microbiome-diversity-analysis/` and optional `/job/stage/metadata.tsv`, and it writes reproducible results to `/job/analysis/microbiome-diversity-analysis/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it to compare microbial communities, assess sampling depth, and summarize diversity patterns across groups. Do not use it to report PERMANOVA findings without checking dispersion or to treat rarefied and unrarefied results as interchangeable.

## Companion Documents
- `references/usage-guide.md` — quick-start guidance, metric comparison, rarefaction notes, and testing tips.
- `scripts/diversity_analysis.R` — example R workflow for alpha and beta diversity analysis.

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
  microbiome-diversity-analysis/
    data/         # required phyloseq object, ASV table, taxonomy, or analysis-ready diversity inputs
    options.yaml  # optional metric, tree, rarefaction, or testing hints
    notes.txt     # optional study notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. A microbiome table and sample grouping information are required. A phylogenetic tree must be present if UniFrac or Faith's PD is requested. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate metrics, distances, or group labels.

If optional metadata is absent, proceed without it and keep the report focused on the staged sample structure.

## Output Conventions
Write all results to `/job/analysis/microbiome-diversity-analysis/`:

- `results/alpha_diversity.tsv`
- `results/beta_distance_matrices.tsv`
- `results/permanova_results.tsv`
- `reports/diversity_summary.md`
- `figures/alpha_boxplots.png`
- `figures/beta_ordination.png`
- `microbiome-diversity-analysis_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-diversity-analysis_<YYYYMMDD-HHMMSS>.R`
- `logs/microbiome-diversity-analysis.log`

The metadata file must record package versions, input paths, output paths, metrics computed, rarefaction decisions, tree requirements, PERMANOVA settings, and a brief explanation of the analysis choices. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read Data
Determine whether the user needs alpha diversity, beta diversity, ordination, rarefaction, or hypothesis testing. If the request is ambiguous, ask for the minimum needed details before choosing metrics or distances.

### Step 2 — Analysis
Compute the requested alpha and beta metrics, build ordinations when needed, and run PERMANOVA only after checking dispersion homogeneity. Use rarefaction only when it is justified by the request or the analysis context.

### Step 3 — Archiving
Summarize the metrics, clearly separate richness from evenness and distance-based results, and save the script and metadata so another analyst can reproduce the workflow.

## Available Libraries / 可用库
R: `phyloseq` `vegan` `ggplot2` `picante` `DECIPHER` `phangorn`

## Strict Rules / 严格规则
1. Never interpret PERMANOVA without checking dispersion homogeneity.
2. Do not treat rarefied and unrarefied results as interchangeable.
3. Do not compute phylogenetic metrics without a tree.
4. Do not fabricate distances, diversity values, or sample group labels.
5. Report the metric family and statistical test used for each conclusion.
6. Keep alpha-diversity, beta-diversity, and ordination interpretations separate.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-diversity-analysis.R` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/microbiome-diversity-analysis_<YYYYMMDD-HHMMSS>.R` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the relevant diversity tooling to confirm the table shape, grouping, and tree availability.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's metric choices, rarefaction decision, and test settings.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/microbiome-diversity-analysis/scripts/`; that directory is for templates, not job artifacts.
