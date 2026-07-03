---
name: metabolomics-quantification
description: >
  Use this skill when imputing missing values and normalizing a feature × sample metabolomics table in one pass. It stays local and offline.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Quantification

## Responsibilities
This skill imputes missing values in a wide feature × sample table and then normalizes the result with the chosen method, writing the quantified table, report, and JSON summary. Use it when both imputation and normalization are needed; do not use it as a raw-spectrum preprocessing step.

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
  metabolomics-quantification/
    data/
      features.csv      # wide feature × sample table
    options.yaml        # optional imputation or normalization hints
    notes.txt           # optional study notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the default imputation-then-normalization workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-quantification/`:

```text
/job/analysis/metabolomics-quantification/
  tables/quantified_features.csv
  report.md
  metabolomics-quantification_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-quantification_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-quantification_meta.json
/job/reproducibility/logs/metabolomics-quantification.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-quantification.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Detect sample columns by case-sensitive prefixes `sample` or `intensity`, impute missing values first, then normalize the imputed matrix with the configured method.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-quantification.py` to interpret parameter semantics and exact CLI behavior.
Use `--impute {min,median,knn}` and `--normalize {tic,median,log}` exactly as implemented.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| sample columns start with `sample` or `intensity` | Proceed with the quantified table | auto-detection is case-sensitive |
| no sample columns are found | Halt | do not invent a sample layout |
| `--impute min` | Half-minimum imputation | replace with half the global non-zero minimum |
| `--impute median` | Per-column median imputation | replace with per-column median of non-zero values |
| `--impute knn` | KNN imputation | use `sklearn.impute.KNNImputer` across the matrix |
| `--normalize tic` | Total-ion-count normalization | scale by column sums after imputation |
| `--normalize median` | Median normalization | scale by column medians after imputation |
| `--normalize log` | `log2(x+1)` transform | keep the transform explicit in the report and metadata |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-quantification.py` to `/job/reproducibility/generated_scripts/metabolomics-quantification_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
Use `references/output_contract.md` to verify output names and archived artifacts before saving the generated script and metadata.
Run the generated script with the skill's documented runtime command, then capture logs under `/job/reproducibility/logs/`.
Save the metadata JSON after the run completes.

## Available Libraries / 可用库
Python: `numpy`, `pandas`, `scikit-learn`
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

9. Apply imputation before normalization.
10. Treat zeros as missing alongside NaN in the imputation step.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-quantification.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-quantification_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-quantification/scripts/`; that directory is for repository reference code.
