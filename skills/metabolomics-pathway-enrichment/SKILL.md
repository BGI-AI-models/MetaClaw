---
name: metabolomics-pathway-enrichment
description: >
  Use this skill when running offline pathway over-representation analysis on a metabolite list against the embedded demo pathway dictionary. It does not query KEGG, Reactome, or other web services.
allowed-tools: Bash(python *) Bash(Rscript *) Read Write
disable-model-invocation: true
---

# Metabolomics Pathway Enrichment

## Responsibilities
This skill runs offline over-representation analysis on a metabolite list using the embedded demo pathway dictionary and writes the enrichment table, report, and JSON summary. Use it for local ORA only; do not use it for live KEGG/Reactome-style enrichment or topology-based methods.

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
  metabolomics-pathway-enrichment/
    data/
      metabolites.csv   # list of metabolites of interest
    options.yaml        # optional pathway or method hints
    notes.txt           # optional pathway notes
/job/input/metadata.tsv     # optional user metadata
```

Read `/job/stage/manifest.json` first when present and use it to locate the actual files. If optional metadata is absent, proceed with the bundled offline ORA workflow.

## Output Conventions
Write all results to `/job/analysis/metabolomics-pathway-enrichment/`:

```text
/job/analysis/metabolomics-pathway-enrichment/
  tables/pathway_enrichment.csv
  report.md
  metabolomics-pathway-enrichment_summary.json
```

Write reproducibility artifacts to `/job/reproducibility/`:

```text
/job/reproducibility/generated_scripts/metabolomics-pathway-enrichment_<YYYYMMDD-HHMMSS>.py
/job/reproducibility/metabolomics-pathway-enrichment_meta.json
/job/reproducibility/logs/metabolomics-pathway-enrichment.log
```

## Workflow

### Step 1 — Read Data
Inspect the staged inputs, confirm the expected schema, and read `/job/stage/manifest.json` first when present.
Use `references/methodology.md`, `references/parameters.md`, and `scripts/reference_metabolomics-pathway-enrichment.py` to interpret the staged inputs, parameter names, defaults, and validation rules.

### Step 2 — Analysis
Normalize the metabolite names, select the `metabolite` column when present (otherwise the first column), compare them with the bundled pathway members, compute the hypergeometric p-value for each pathway, and apply BH-FDR.
Use `references/methodology.md` as the primary method guide and `references/parameters.md` plus `scripts/reference_metabolomics-pathway-enrichment.py` to interpret parameter semantics and exact CLI behavior.

| Condition | Method / Action | Notes / Output expectations |
|---|---|---|
| `metabolite` column is present | Use it as the metabolite list column | otherwise fall back to the first column |
| Metabolite list is present | Run offline ORA with the hypergeometric test | report pathway hits and BH-FDR values |
| `--method` is set to any supported label | Record the label only | do not switch away from the ORA computation |
| Request mentions KEGG, Reactome, topology, or a live API | Halt | not supported by this offline skill |
| Names do not map to any bundled pathway member | Keep them visible as unmatched | surface them in the report and summary |

### Step 3 — Archiving
Copy `/pipeline/scripts/reference_metabolomics-pathway-enrichment.py` to `/job/reproducibility/generated_scripts/metabolomics-pathway-enrichment_<YYYYMMDD-HHMMSS>.py`, edit the copy for the current job, and keep the reference script untouched.
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

9. Treat `--method` as a recorded label unless the code path is expanded later.
10. Never claim live KEGG, Reactome, MetaboAnalyst, or topology-based enrichment.

## Execution Model (Two-Stage) / 执行模型（两阶段）

This skill follows the two-stage downstream pattern and is not meant to be run directly from the reference script.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_metabolomics-pathway-enrichment.py` | ro | repository-published template; do not modify |
| `/job/reproducibility/generated_scripts/metabolomics-pathway-enrichment_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy executed for this run |

Standard flow:

1. Load the staged inputs under `/job/stage/` and confirm the schema and sample count.
2. Copy the reference script into `/job/reproducibility/generated_scripts/`.
3. Edit the copy with the current job’s parameters and thresholds.
4. Run the generated script and capture the log.
5. Save the metadata JSON after the run completes.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `skills/metabolomics-pathway-enrichment/scripts/`; that directory is for repository reference code.
