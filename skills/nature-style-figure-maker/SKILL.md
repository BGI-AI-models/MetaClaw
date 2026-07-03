---
name: nature-style-figure-maker
description: >
  Use this skill when the user wants Nature-style publication figures, multi-panel scientific plots, figure revisions, figure legends, titles, captions, or figure-adjacent prose that must follow the figure logic. Trigger it for figure creation, figure cleanup, backend-aware export, QA, or when the user asks for Nature-family style and has not yet chosen Python or R.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  author: Yuan1z skill rebuilt from source skills
  version: 1.0.0
---

# Nature-Style Figure Maker

## Responsibilities
This skill combines the claim-first figure workflow from the source figure skill with the language-control rules from the writing skill. It consumes staged inputs under `/job/stage/nature-style-figure-maker/` and optional `/job/stage/metadata.tsv`, and it writes a reproducible package to `/job/analysis/nature-style-figure-maker/` with generated code under `/job/reproducibility/generated_scripts/`.

Use it for figure creation, revisions, QA, export, and short prose around the figure, including titles, legends, captions, and concise manuscript-facing text. Do not use it to invent data, claim novelty, or hide weak evidence under heavy styling.

## Companion Documents
- `references/figure-playbook.md` — figure contract, backend gate, layout hierarchy, export and QA rules.
- `references/writing-playbook.md` — hourglass writing strategy, section roles, phrase families, and style guardrails.

If a reference conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0
- Network access: none (`--network none`, per gateway default)
- Backend requirement: pick Python (matplotlib/seaborn) OR R (ggplot2) before plotting begins; do not mix backends within a single panel
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
  nature-style-figure-maker/
    data/        # optional source data for charts
    images/      # optional raster inputs, source panels, or plates
    text/        # optional draft titles, captions, legends, or notes
    options.yaml # optional backend, size, journal, or export hints
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. If the user has not chosen Python or R, ask one concise question: `Python or R?` and stop. Exactly one primary figure package is expected unless the user explicitly requests a coordinated multi-file figure. If `options.yaml` is present, its settings must match the real inputs and requested output. If staged text is present, treat it as draft figure text to improve, not as a source for new claims. If any required input or control file is missing, unreadable, or contradictory, report the problem and halt; do not fabricate data, claims, or file support.

If optional metadata is absent, proceed without it and keep the figure brief focused on the staged inputs.

## Output Conventions
Write all results to `/job/analysis/nature-style-figure-maker/`:

- `figures/figure.svg`
- `figures/figure.pdf`
- `figures/figure.tiff`
- `figures/preview.png`
- `text/polished_caption.md`
- `text/title_options.md`
- `reports/figure_contract.md`
- `reports/qa_notes.md`
- `nature-style-figure-maker_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/nature-style-figure-maker_<YYYYMMDD-HHMMSS>.py`
- `logs/nature-style-figure-maker.log`

The metadata file must record package versions, input paths, output paths, parameters, the selected backend, any `random_seed` used, reference files consulted, and a brief explanation of the figure logic and wording decisions. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read the contract
Read the staged inputs and determine the core conclusion, figure archetype, backend, panel map, and reviewer risk. If the backend is not already chosen, ask `Python or R?` and wait.

### Step 2 — Build the figure and polish the text
Use the selected backend exclusively for all plotting, previews, exports, and visual QA. Keep the layout claim-first: one hero panel, supporting evidence panels, restrained colours, direct labels where possible, and editable text in SVG/PDF output. If prose is involved, polish it to match the figure logic rather than to mask weak evidence.

### Step 3 — QA and archive
Check source-data traceability, sample sizes or n, intervals or error bars, statistics, scale bars, image integrity, and final readability at export size. Save the script and metadata, and make sure the output bundle can be reproduced.

## Available Libraries / 可用库
Python: `matplotlib` `seaborn` `pandas` `numpy` `Pillow`
R: `ggplot2` `patchwork` `ComplexHeatmap` `ggrepel` `svglite` `cairo_pdf` `ragg`

## Strict Rules / 严格规则
1. Never invent data, statistics, claims, or references.
2. Never switch backends after one has been selected.
3. Never use the non-selected backend for plotting, previewing, exporting, or QA renders.
4. Never let polished prose overstate the evidence.
5. Any stochastic or random step must use `random_seed` from `pipelines.yaml` when such a file is present.
6. If the sample size is below the `SOUL.md` threshold, label the output exploratory where applicable.
7. Do not disclose private local paths, template provenance, or internal filenames in user-facing prose unless the user explicitly asks.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_nature-style-figure-maker.py` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/nature-style-figure-maker_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the selected backend and data-structure tooling to confirm the figure inputs and backend choice.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's panel map, backend selection, and caption language.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/nature-style-figure-maker/scripts/`; that directory is for templates, not job artifacts.
