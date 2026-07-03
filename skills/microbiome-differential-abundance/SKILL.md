---
name: microbiome-differential-abundance
description: >
  Use this skill when the user needs microbiome differential abundance testing with ALDEx2 (compositional Dirichlet-MC Wilcoxon) on integer count data for 2-group comparisons.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.1.1
---

# Differential Abundance Testing

## Responsibilities
This skill handles method selection, filtering, modeling, result extraction, and interpretation for microbiome differential abundance analyses. It consumes staged inputs under `/job/stage/microbiome-differential-abundance/` and optional `/job/stage/metadata.tsv`, and it writes reproducible results to `/job/analysis/microbiome-differential-abundance/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it to compare taxa across groups, include covariates, or handle longitudinal or mixed designs. Do not use it to ignore compositionality, hide failed models, or present p-values without effect sizes and multiple-testing correction.

## Companion Documents
- `references/usage-guide.md` — quick-start guidance, filtering recommendations, and interpretation notes.
- `scripts/aldex2_analysis.R` — example ALDEx2 workflow (2-group compositional Dirichlet-MC Wilcoxon) using plain count + metadata TSVs.

If a companion document conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.1
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
  microbiome-differential-abundance/
    data/         # required: an integer count table (rows=taxa, cols=samples,
                  # or transposed — script auto-orients). Prefer
                  # `merged_count_table.tsv` from microbiome-profile-merge.
    options.yaml  # optional grouping, formula, covariate, filtering, or threshold hints
    notes.txt     # optional design notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. A feature table and group or design definition are required. If covariates or repeated measures are part of the request, the design information must be present. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate groups, formulas, or results.

If optional metadata is absent, proceed without it and keep the model choice focused on the staged design.

## Output Conventions
Write all results to `/job/analysis/microbiome-differential-abundance/`:

- `results/differential_abundance.tsv`
- `results/method_summary.tsv`
- `reports/differential-abundance_summary.md`
- `figures/volcano_plot.png`
- `microbiome-differential-abundance_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/microbiome-differential-abundance_<YYYYMMDD-HHMMSS>.R`
- `logs/microbiome-differential-abundance.log`

The metadata file must record package versions, input paths, output paths, filtering choices, model formulas, covariates, effect-size thresholds, and a brief explanation of the statistical choices. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read Data
Determine whether the user needs a simple two-group comparison, a covariate-adjusted model, or a longitudinal or mixed-effects analysis. If the request is ambiguous, ask for the minimum needed details before selecting the method.

### Step 2 — Analysis
Use **ALDEx2** (`scripts/aldex2_analysis.R`) — 2-group compositional comparison; Dirichlet Monte-Carlo Wilcoxon on CLR-transformed counts. Returns `effect`, `we.ep`, `we.eBH`.

`ANCOM-BC2`, `MaAsLin2`, `DESeq2`, and `phyloseq`-based pipelines are NOT installed in `openclaw/downstream:1.1.1`. If a user explicitly requests one of these, halt and report the method isn't installed (do not silently substitute another method). To add them, edit `images/downstream/Dockerfile` (see CHANGELOG for the ANCOMBC recipe specifically — it needs rustup + libgmp-dev/libuv1-dev/libgsl-dev + a CVXR 1.0-12 pin) and the skill's `requirements_r.txt`.

If a user has a design that ALDEx2 can't handle (covariates, >2 groups, longitudinal), report the limitation rather than running ALDEx2 on a design it's not appropriate for. Document the prevalence / mean-count filters in the metadata file.

### Step 3 — Archiving
Report FDR, effect size, covariates, and any filtering choices explicitly, then save the script and metadata so another analyst can reproduce the workflow and see the design decisions.

## Available Libraries / 可用库
R (in `openclaw/downstream:1.1.1`): `ALDEx2`, `ggplot2`.

NOT installed (would error if `library()`'d): `ANCOMBC`, `phyloseq`, `DESeq2`, `MaAsLin2`. See `images/downstream/Dockerfile` CHANGELOG for the rationale + the recipe to add them.

## Strict Rules / 严格规则
1. Never silently skip compositional limitations, low-prevalence filtering, or failed model fits.
2. Always report effect size and FDR or adjusted p-value, not just raw p-values.
3. If the user asks for ANCOM-BC2, MaAsLin2, DESeq2, or phyloseq workflows, halt and report the package is not installed — do not silently substitute another method.
4. If the user's design needs covariates, >2 groups, or random effects, halt and report that ALDEx2 isn't appropriate for that design (do not run it anyway).
5. Do not fabricate taxa, estimates, or significance calls.
6. Keep filtering thresholds explicit in the archived script.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_microbiome-differential-abundance.py` | ro | Python wrapper template that renders an inline R driver for ALDEx2; mounted ro by `prepare_downstream.sh`; do not modify |
| `/pipeline/scripts/aldex2_analysis.R` | ro | standalone ALDEx2 R reference (used by the LLM as a starting template for hand-customization) |
| `/job/reproducibility/generated_scripts/microbiome-differential-abundance_<YYYYMMDD-HHMMSS>.{py,R}` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the appropriate compositional-statistics tooling to confirm the design matrix and sample structure.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's formulas, covariates, prevalence filters, and effect-size thresholds.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/microbiome-differential-abundance/scripts/`; that directory is for templates, not job artifacts.
