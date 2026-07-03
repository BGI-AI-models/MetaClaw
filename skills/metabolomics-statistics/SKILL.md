---
name: metabolomics-statistics
description: >
  Use this skill when running univariate two-group metabolomics tests on a feature × sample table with t-test, Wilcoxon, ANOVA, or Kruskal-Wallis. It stays local and offline.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Statistics

## Responsibilities
This skill runs univariate tests on a feature × sample table, computes group means, log2 fold change, BH-FDR, and a best-effort PCA summary, and writes the statistics bundle. Use it for local inferential testing only; do not use it as a substitute for a broader multivariate biomarker workflow.

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
  metabolomics-statistics/
    data/
      features.csv      # wide feature × sample table with feature IDs in the first column
    options.yaml        # optional group or alpha hints
    notes.txt           # optional study notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with prefix-based grouping or midpoint fallback.

## Output Conventions
Write all results to `/job/analysis/metabolomics-statistics/`:

```text
/job/analysis/metabolomics-statistics/
  tables/statistics.csv
  tables/significant.csv
  report.md
  metabolomics-statistics_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-statistics_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-statistics_meta.json
/job/reproducibility/logs/metabolomics-statistics.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-statistics.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Resolve the two sample groups from `--group1-prefix` and `--group2-prefix`, or use the midpoint fallback when either prefix is missing, then run the requested univariate test feature-by-feature.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-statistics.py` to interpret parameter semantics and exact CLI behavior.
Use `--method {ttest,anova,wilcoxon,kruskal}` exactly as implemented, and use `--alpha` to filter the significant subset (default 0.05).

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `--group1-prefix` and `--group2-prefix` both match columns | Use those columns as the two groups | keep the explicit grouping decision in the report |
| prefixes are missing or incomplete | Midpoint fallback | if fallback fails, halt rather than invent groups |
| `--method ttest` | Welch t-test | preferred two-group inference with `log2fc` and BH-FDR; respect group order |
| `--method wilcoxon` | Mann-Whitney / Wilcoxon rank-sum | use on the same two inferred groups |
| `--method anova` | One-way ANOVA | still applied to the same two inferred groups |
| `--method kruskal` | Kruskal-Wallis | non-parametric alternative on the same two inferred groups |
| `--alpha` provided | Filter `tables/significant.csv` at that cutoff | default is 0.05 |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-statistics.py` to `/job/reproducibility/generated_scripts/metabolomics-statistics_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
Use `references/output_contract.md` to verify output names and archived artifacts before saving the generated script and metadata.
Run the generated script with the skill's documented runtime command, then capture logs under `/job/reproducibility/logs/`.
Save the metadata JSON after the run completes.

## Available Libraries / 可用库
Python: `numpy`, `pandas`, `scipy`
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

9. Keep the two-group fallback explicit; `anova` and `kruskal` are method labels on the same inferred groups, not support for arbitrary multi-group designs.
10. Report `log2fc` as the effect size alongside the inferential result.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-statistics.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-statistics_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-statistics/scripts/`; that directory is for repository reference code.
