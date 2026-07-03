---
name: hypothesis-generation
description: >
  Use this skill when the user wants help generating testable scientific hypotheses, comparing competing explanations, grounding ideas in literature, designing discriminating experiments, or turning observations into falsifiable predictions.
allowed-tools: Read Write Edit Bash
disable-model-invocation: true
metadata:
  version: 1.0.0
---

# Scientific Hypothesis Generation

## Responsibilities
This skill converts an observation or question into a structured set of competing hypotheses from staged inputs under `/job/stage/hypothesis-generation/` and optional `/job/stage/metadata.tsv`, and it writes a reproducible package to `/job/analysis/hypothesis-generation/` with generated code archived under `/job/reproducibility/generated_scripts/`.

Use it to clarify the phenomenon, ground the discussion in literature, generate 3–5 mechanistic hypotheses, assess quality, propose experiments, and state falsifiable predictions. Do not use it to invent evidence, claim certainty where the literature is weak, or replace the scientific argument with polished but unsupported prose.

## Companion Documents
- `references/hypothesis_quality_criteria.md` — testability, falsifiability, parsimony, scope, and novelty.
- `references/experimental_design_patterns.md` — experimental designs for testing hypotheses.
- `references/literature_search_strategies.md` — literature search and evidence-gathering workflow.
- `assets/FORMATTING_GUIDE.md` — optional formatting help if preserved.

If a companion document conflicts with this `SKILL.md`, follow `SKILL.md` and report the inconsistency.

## Runtime Environment / 运行环境
- Container image: openclaw/downstream:1.1.0 
- Network access: none (`--network none`); literature lookup is NOT performed inline — supply pre-fetched references under `/job/stage/hypothesis-generation/`
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
  hypothesis-generation/
    question.txt     # required; the phenomenon, observation, or research question
    context.md       # optional background notes or constraints
    notes.txt        # optional draft hypotheses or observations
    options.yaml     # optional controls such as hypothesis count or output style
/job/stage/metadata.tsv  # optional, read if present
```

If a manifest is present, read it first and use it to locate the actual files. The request must contain a clear observation, phenomenon, or question to explain. If the request is too vague, ask for the minimum missing details. If any required input is missing, unreadable, or contradictory, report the problem and halt; do not fabricate data, literature support, or test conditions.

If optional metadata is absent, proceed without it and keep the output focused on the staged request.

## Output Conventions
Write all results to `/job/analysis/hypothesis-generation/`:

- `reports/hypothesis_report.md`
- `tables/hypothesis_comparison.csv`
- `tables/testable_predictions.csv`
- `tables/experiment_plan.csv`
- `hypothesis-generation_meta.json`

Write reproducibility artifacts to `/job/reproducibility/`:

- `generated_scripts/hypothesis_generation_<YYYYMMDD-HHMMSS>.py`
- `logs/hypothesis-generation.log`

The metadata file must record package versions, input paths, output paths, parameters, reference files consulted, and a brief explanation of the major reasoning decisions. If the run halts, write the metadata file when possible and record the blocker.

## Workflow
### Step 1 — Read Data
Read the staged question and context, identify the phenomenon, and determine what is already known versus uncertain. If the request is too vague, ask for the smallest amount of missing context.

### Step 2 — Analysis
Use the references to structure literature-backed evidence, then generate 3–5 competing mechanistic hypotheses. Evaluate each hypothesis against the quality criteria and note strengths, weaknesses, and discriminating predictions. For each viable hypothesis, propose specific experiments or studies, including controls and measurable outcomes.

### Step 3 — Archiving
Save the report, any generated script, and metadata so the workflow is reproducible and easy to review. If a reference script exists, copy it to the job-specific generated-script path before editing; otherwise create the generated script as the archival artifact for this run.

## Available Libraries / 可用库
Python: `pyyaml` `pandas` `numpy` `scipy`
R（通过 rpy2）: not typically required

## Strict Rules / 严格规则
1. Never invent literature support, mechanisms, or experimental results.
2. Every hypothesis must be testable and falsifiable.
3. Do not hide weak evidence behind polished language.
4. If evidence is limited, label the output exploratory or provisional.
5. Any stochastic or random step must use `random_seed` from `pipelines.yaml` when such a file is present.
6. Do not require figures, LaTeX, or special schematic tools unless the user explicitly asks for them.
7. Never write outside `/job/analysis/` and `/job/reproducibility/` for outputs and run artifacts.

## Execution Model (Two-Stage) / 执行模型（两阶段）
This skill follows the two-stage downstream pattern when a reference script is available.

Two paths are strictly separated; mixing them will fail:

| Path | Permission | Purpose |
|---|---|---|
| `/pipeline/scripts/reference_hypothesis-generation.py` | ro | repository-published template, mounted ro by `prepare_downstream.sh`; do not modify |
| `/job/reproducibility/generated_scripts/hypothesis-generation_<YYYYMMDD-HHMMSS>.py` | rw | job-specific customized copy; `run_downstream.sh` executes the most recent one |

Standard flow:

1. `bash gateway/attach.sh --shell` to enter the already-running container (or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`).
2. Inspect `/job/stage/` with the appropriate libraries to confirm the request, context, and sample size or evidence base.
3. Copy the reference script into `/job/reproducibility/generated_scripts/`.
4. Edit the copy with the current job's question framing, hypothesis count, and output options.
5. Run the job-specific script with the documented runtime command and archive the log.

**Do not** run the reference script directly; it bypasses customization and metadata archiving. **Do not** write generated scripts under `Skills/hypothesis-generation/scripts/`; that directory is for templates, not job artifacts.

## Style Defaults
- Prefer concise, mechanistic explanations.
- Make competing hypotheses distinct from one another.
- State clear predictions and falsifiers.
- Keep the literature grounding explicit.
- Prefer Markdown output by default.
