---
name: statistical-analysis
description: >
  Use this skill when the user needs help choosing statistical tests, checking assumptions, planning power, interpreting effect sizes, or writing APA-style statistical results for academic research. Trigger it for t-tests, ANOVA, chi-square, correlation, regression, Bayesian analyses, diagnostics, and reporting of experimental or observational data.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  skill-author: K-Dense Inc.
  version: 1.0.0
---

# Statistical Analysis

## Responsibilities
This skill combines the decision logic from the source test-selection guide with the assumption-checking workflow, effect-size and power guidance, Bayesian alternatives, and reporting standards. It consumes staged inputs under `/job/stage/statistical-analysis/` and optional `/job/stage/metadata.tsv`, and it writes a reproducible package to `/job/analysis/statistical-analysis/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it for choosing tests, checking assumptions, running or explaining analyses, reporting results, or writing concise figure/table-ready statistical summaries. Do not use it to invent data, hide assumption failures, or report significance without the supporting magnitude and uncertainty.

## Companion Documents
- `references/test-selection-guide.md` — quick decision tree for choosing tests.
- `references/assumptions-and-diagnostics.md` — assumption checks and remedies.
- `references/effect-sizes-and-power.md` — effect sizes, confidence intervals, and power.
- `references/bayesian-statistics.md` — Bayesian models, priors, Bayes factors, and diagnostics.
- `references/reporting-standards.md` — APA-style reporting examples and checklist.
- `scripts/assumption_checks.py` — helper module for normality, homogeneity, linearity, and outlier checks.

If a reference conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0
- Network access: none (`--network none`, per gateway default)
- Repository-level requirements: `pipelines.yaml` must provide `random_seed`; `SOUL.md` must define the exploratory threshold.
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
  statistical-analysis/
    data/         # optional input tables or analysis-ready files
    options.yaml  # optional test, alpha, power, or reporting hints
    notes.txt     # optional draft hypotheses or reporting notes
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. Exactly one primary dataset or analysis request is expected unless the user explicitly requests a coordinated multi-file analysis. If `options.yaml` is present, its settings must match the actual data and requested test path. If draft notes are present, treat them as analysis context, not as a source for new claims. If any required input or control file is missing, unreadable, or contradictory, report the problem and halt; do not fabricate data, assumptions, thresholds, or results.

If optional metadata is absent, proceed without it and keep the selected test path focused on the staged request.

## Output Conventions
Write all results to `/job/analysis/statistical-analysis/`:

- `results/statistical_summary.md`
- `results/apa_results.md`
- `tables/descriptives.csv`
- `tables/model_summary.csv`
- `figures/diagnostics.png`
- `statistical-analysis_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/statistical-analysis_<YYYYMMDD-HHMMSS>.py`
- `logs/statistical-analysis.log`

The metadata file must record package versions, input paths, output paths, parameters, any `random_seed` used, reference files consulted, and a brief explanation of the analysis choices, assumption checks, and reporting decisions. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read the request
Read the staged inputs and identify the research question, outcome type, predictor structure, study design, and whether the user needs test selection, diagnostics, power planning, or reporting help. If the input is ambiguous, narrow it by asking for the minimum needed details.

### Step 2 — Choose and check the analysis
Use the decision guide to select the appropriate test family, then check the relevant assumptions before interpreting results. For regression and grouped comparisons, use the helper script when appropriate and document any violations plus remedial actions. If Bayesian analysis is requested, use the Bayesian reference and report priors, posterior uncertainty, and convergence diagnostics.

### Step 3 — Report and archive
Report effect sizes and confidence intervals alongside any p-values, and present APA-style results when the user wants publication-ready wording. Save the script and metadata so another analyst can reproduce the workflow and see which assumptions, corrections, and reporting choices were made.

## Available Libraries / 可用库
Python: `scipy` `statsmodels` `pingouin` `pymc` `arviz` `pandas` `numpy` `matplotlib` `seaborn` `pyyaml`

## Strict Rules / 严格规则
1. Never silently skip missing data, assumption violations, or diagnostic failures.
2. Any statistical test or inferential summary must report the effect size and confidence interval, not just the p-value.
3. If the sample size is below the `SOUL.md` threshold, label the analysis exploratory where applicable.
4. All stochastic or random steps must use `random_seed` from `pipelines.yaml`.
5. Do not report significance without stating the test, degrees of freedom when relevant, and the effect magnitude.
6. Do not upgrade exploratory findings into confirmatory claims.
7. Use the selected framework consistently; do not mix frequentist and Bayesian reporting unless the user explicitly requests both.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_statistical-analysis.py` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/statistical-analysis_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the appropriate statistical tooling to confirm the data shape and test selection.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's test choice, diagnostics, power, and reporting settings.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/statistical-analysis/scripts/`; that directory is for templates, not job artifacts.
