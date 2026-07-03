---
name: metabolomics-de
description: >
  Use this skill when running two-group metabolomics differential analysis on a feature × sample table with Welch t-tests, log2 fold change, BH-FDR, and a best-effort PCA summary. It stays local and offline.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Differential Analysis

## Responsibilities
This skill compares two sample groups in a wide feature × sample table, computes Welch t-tests, log2 fold change, BH-FDR, and a best-effort PCA plot, and writes the results bundle. Use it for local two-group differential analysis; do not use it as a substitute for a broader multivariate biomarker workflow.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0
- Network access: none (`--network none`, per gateway default)
- Mounted paths:

| Path | Permission | Contents |
|---|---|---|
| `/job/stage/` | ro | upstream staged inputs and manifest files |
| `/job/analysis/` | rw | analysis outputs for this skill |
| `/job/reproducibility/` | rw | generated scripts, logs, and metadata |
| `/pipeline/scripts/` | ro | read-only reference scripts mounted by the harness |

## Input Conventions
This skill expects the following layout under `/job/stage/`:

```text
/job/stage/
  manifest.json
  metabolomics-de/
    data/
      quantified_features.csv   # primary wide feature × sample table
    options.yaml                # optional group-prefix or threshold hints
    notes.txt                   # optional study notes
/job/input/metadata.tsv         # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the default two-group workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-de/`:

```text
/job/analysis/metabolomics-de/
  tables/differential_features.csv
  tables/significant_features.csv
  figures/pca_scores.png
  report.md
  metabolomics-de_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-de_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-de_meta.json
/job/reproducibility/logs/metabolomics-de.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-de.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Resolve the two sample groups from `--group-a-prefix` and `--group-b-prefix` (defaults `ctrl` and `treat`), run Welch t-tests feature-by-feature, and try the PCA scores plot on the same samples.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-de.py` to interpret parameter semantics and exact CLI behavior.
The significant subset is filtered at BH-FDR < 0.05.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| Both group prefixes match columns and the groups are non-empty | Run Welch t-tests, compute log2 fold change (group B - group A), and apply BH-FDR | write `differential_features.csv` and `significant_features.csv` |
| Both groups have at least 3 samples | Attempt `figures/pca_scores.png` | keep the differential tables even if the figure fails later |
| Group prefixes are missing or match no columns | Halt | do not invent groups |
| Group sizes are very small or variance is degenerate | Label the run exploratory | keep the tables, and treat PCA as best-effort only |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-de.py` to `/job/reproducibility/generated_scripts/metabolomics-de_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
Use `references/output_contract.md` to verify output names and archived artifacts before saving the generated script and metadata.
Run the generated script with the skill's documented runtime command, then capture logs under `/job/reproducibility/logs/`.
Save the metadata JSON after the run completes.

## Available Libraries / 可用库
Python: `matplotlib`, `numpy`, `pandas`, `scikit-learn`, `scipy`
R（通过 rpy2）: not used

## Strict Rules / 严格规则
1. Never silently skip data anomalies such as NaNs, missing samples, or schema mismatches.
2. If a statistical test is reported, include the effect size alongside the p-value.
3. If multiple comparisons are performed, apply BH-FDR or the skill’s documented correction method.
4. If the sample size is below the documented threshold, label the analysis exploratory and avoid asymptotic tests.
5. Document NA handling, filtering, and transformation choices in the generated script.
6. All stochastic steps must use the configured `random_seed` or equivalent pipeline setting.
7. Never write outside `/job/analysis/` and `/job/reproducibility/` for outputs and run artifacts.
8. Never run the reference script directly; always run the generated copy.

9. Keep the workflow two-group only; do not claim PLS-DA, OPLS-DA, RF, or ROC outputs.
10. If PCA fails, keep the differential tables and note the failure rather than dropping the analysis.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-de.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-de_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-de/scripts/`; that directory is for repository reference code.
