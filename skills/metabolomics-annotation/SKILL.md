---
name: metabolomics-annotation
description: >
  Use this skill when annotating LC-MS features against bundled offline metabolite dictionaries by m/z and ppm tolerance. It does not query live databases or web services.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Annotation

## Responsibilities
This skill matches query m/z values against the bundled local metabolite dictionaries by ppm tolerance and expands one row per adduct/database match. Use it for local m/z matching only; do not use it for live database lookups or exhaustive identification.

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
  manifest.json             # required when upstream outputs are registered
  metabolomics-annotation/
    data/
      features.csv          # required unless --demo; must include an mz column
    options.yaml             # optional adduct or ppm hints
    notes.txt                # optional sample or assay notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the default offline workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-annotation/`:

```text
/job/analysis/metabolomics-annotation/
  tables/annotations.csv
  report.md
  metabolomics-annotation_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-annotation_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-annotation_meta.json
/job/reproducibility/logs/metabolomics-annotation.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-annotation.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Match staged `mz` values against the bundled local databases and keep every hit explicit.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-annotation.py` to interpret parameter semantics and exact CLI behavior.
Treat `--database` as a recorded label only and use `--ppm` as the m/z tolerance.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `--database` provided | Record the selected database label | do not change the lookup table |
| `--ppm` provided | Apply the tolerance to every query m/z | report every match within the configured window |
| `--demo` is set or staged `features.csv` contains `mz` values | Match query m/z values against the bundled local metabolite dictionaries by ppm tolerance | write one row per query/adduct/database match |
| `--adducts` provided | Evaluate the requested adduct list | keep multiple matches separate |
| query m/z has no match | Emit `Unknown` rows | keep unmatched features visible in the report and summary |
| request needs live database, MS2, RT, or isotope-confirmation lookup | Halt | not supported by this offline skill |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-annotation.py` to `/job/reproducibility/generated_scripts/metabolomics-annotation_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
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

9. Keep multiple matches as separate rows instead of collapsing them.
10. Never claim live database, MS2, RT, or isotope confirmation.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-annotation.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-annotation_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-annotation/scripts/`; that directory is for repository reference code.
