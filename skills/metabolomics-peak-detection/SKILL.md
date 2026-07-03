---
name: metabolomics-peak-detection
description: >
  Use this skill when detecting peaks per sample in a feature × intensity table with scipy.signal.find_peaks. It stays local and offline.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Peak Detection

## Responsibilities
This skill scans each sample column in a wide intensity matrix with `scipy.signal.find_peaks`, records the detected peaks, and writes the detection table, report, and JSON summary. Use it for local peak picking only; do not use it for raw chromatogram processing or vendor-format conversion.

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
  metabolomics-peak-detection/
    data/
      features.csv      # wide table with mz, rt, and sample/intensity columns
    options.yaml        # optional threshold hints
    notes.txt           # optional study notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the default peak-picking workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-peak-detection/`:

```text
/job/analysis/metabolomics-peak-detection/
  tables/detected_peaks.csv
  report.md
  metabolomics-peak-detection_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-peak-detection_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-peak-detection_meta.json
/job/reproducibility/logs/metabolomics-peak-detection.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-peak-detection.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Identify the sample columns, sort by `rt`, and run `scipy.signal.find_peaks` with the configured thresholds.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-peak-detection.py` to interpret parameter semantics and exact CLI behavior.
Auto-detect sample columns case-insensitively by matching `sample` or `intensity`; if NaNs affect detection, pre-impute or filter because the detector treats them as 0.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `--sample-prefix` provided | Use matching sample columns | detect peaks for each selected sample column |
| no prefix provided | Auto-detect columns containing `intensity` or starting with `sample` | keep the detection rules explicit in the report |
| `mz` or `rt` columns missing | Halt | input schema is invalid |
| `prominence`, optional `height`, and `distance` provided | Run `scipy.signal.find_peaks` with those thresholds | `distance` is row-order spacing, not chromatographic time |
| NaNs are present in a way that affects peak picking | Pre-impute or filter | do not assume the detector will handle them safely |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-peak-detection.py` to `/job/reproducibility/generated_scripts/metabolomics-peak-detection_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
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

9. Keep the sample-column detection rules explicit when `--sample-prefix` is provided or omitted.
10. Do not claim raw-scan preprocessing or vendor-file support that the code does not implement.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-peak-detection.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-peak-detection_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-peak-detection/scripts/`; that directory is for repository reference code.
