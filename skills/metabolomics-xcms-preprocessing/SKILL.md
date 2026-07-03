---
name: metabolomics-xcms-preprocessing
description: >
  Use this skill when producing an offline XCMS-style preprocessing summary and peak table from staged LC-MS inputs. It is a local Python surrogate, not real XCMS or CAMERA.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics XCMS Preprocessing

## Responsibilities
This skill turns staged LC-MS file references into a synthetic-shaped peak table and preprocessing summary using the configured ppm and peak-width settings. Use it as an offline surrogate for an XCMS-style workflow; do not use it to claim a real R/XCMS/CAMERA run.

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
  metabolomics-xcms-preprocessing/
    raw_files/
      sample1.mzML        # raw or vendor-converted LC-MS files
    options.yaml           # optional ppm or peak-width hints
    notes.txt              # optional assay notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the offline surrogate workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-xcms-preprocessing/`:

```text
/job/analysis/metabolomics-xcms-preprocessing/
  tables/peak_table.csv
  report.md
  metabolomics-xcms-preprocessing_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-xcms-preprocessing_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-xcms-preprocessing_meta.json
/job/reproducibility/logs/metabolomics-xcms-preprocessing.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-xcms-preprocessing.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Use `--input <file1> [<file2> ...]` or `--demo`, then apply the configured `--ppm`, `--peakwidth-min`, and `--peakwidth-max` settings in the Python surrogate.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-xcms-preprocessing.py` to interpret parameter semantics and exact CLI behavior.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `--input` provides one or more LC-MS file references | Run the Python surrogate preprocessing workflow | generate the synthetic-shaped peak table and summary |
| `--demo` is enabled | Use demo file references | keep the run offline and reproducible |
| `--ppm` is provided | Apply the m/z tolerance to the surrogate | record it in metadata |
| `--peakwidth-min` / `--peakwidth-max` are provided | Apply the peak-width bounds | record them in metadata |
| request asks for real XCMS/CAMERA processing | Halt | this skill is surrogate-only |
| `--input` is absent and demo is off | Halt | do not fabricate file references |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-xcms-preprocessing.py` to `/job/reproducibility/generated_scripts/metabolomics-xcms-preprocessing_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
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

9. Never claim a real R/XCMS/CAMERA run.
10. Keep the surrogate nature of the workflow explicit in the report and metadata.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-xcms-preprocessing.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-xcms-preprocessing_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-xcms-preprocessing/scripts/`; that directory is for repository reference code.
