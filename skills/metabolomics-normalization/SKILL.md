---
name: metabolomics-normalization
description: >
  Use this skill when normalizing a feature × sample metabolomics table with median, quantile, total/TIC, PQN, or log transforms. It does not perform imputation or internet-backed processing.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Normalization

## Responsibilities
This skill normalizes a wide feature × sample table with the chosen offline method and writes the normalized matrix, report, and JSON summary. Use it for normalization only; do not use it when imputation or raw-spectrum preprocessing is still required.

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
  metabolomics-normalization/
    data/
      features.csv      # wide feature × sample table
    options.yaml        # optional normalization hints
    notes.txt           # optional study notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the default normalization workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-normalization/`:

```text
/job/analysis/metabolomics-normalization/
  tables/normalized.csv
  report.md
  metabolomics-normalization_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-normalization_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-normalization_meta.json
/job/reproducibility/logs/metabolomics-normalization.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-normalization.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Select the configured normalization method and apply it across the wide feature table.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-normalization.py` to interpret parameter semantics and exact CLI behavior.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `--method median` | Median normalization | scale each sample so its median equals the global median-of-medians |
| `--method quantile` | Quantile normalization | make all column distributions identical |
| `--method total` | Total-ion-count normalization | scale by column sums |
| `--method pqn` | Probabilistic Quotient Normalization | use the median spectrum and median quotients |
| `--method log` | `log2(x+1)` transform | keep the transform explicit in the report and metadata |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-normalization.py` to `/job/reproducibility/generated_scripts/metabolomics-normalization_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
Use `references/output_contract.md` to verify output names and archived artifacts before saving the generated script and metadata.
Run the generated script with the skill's documented runtime command, then capture logs under `/job/reproducibility/logs/`.
Save the metadata JSON after the run completes.

## Available Libraries / 可用库
Python: `numpy`, `pandas`
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

9. This skill does not impute missing values; route unresolved missingness upstream to quantification.
10. Treat `log` as `log2(x+1)` and do not hide negative-value problems.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-normalization.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-normalization_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-normalization/scripts/`; that directory is for repository reference code.
