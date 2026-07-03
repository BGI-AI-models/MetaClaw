# TOOLS — Environment Notes

> **Scope.** What host and container tools exist and when to reach for each.
> Does NOT grant permissions — that's in openclaw.json.
>
> **Where jobs live.** All per-job state is written under
> `/data/output/<job-id>/` on the host. The workspace checkout (this repo)
> holds only code, registries, skills, docs, and the session bookmark
> `.current_job_id`. The env var `OPENCLAW_JOBS_ROOT` overrides
> `/data/output` for tests / CI; gateway scripts and the upstream skill
> resolve it at runtime — every script defaults to `/data/output` if it's
> unset.

## Host tools (Gateway process)

### `bash gateway/gateway.sh <pipeline> <data-dir> [overrides.yaml]`
Primary launcher. Call when W1 step 7 confirms. Thin coordination only — sets
up `/data/output/<id>/{stage,reproducibility,…}`, records the input directory in
`/data/output/<id>/.input_source` and its kind (`local` or `flowhub`) in
`/data/output/<id>/.input_source_kind`, populates `stage/`, then hands off:

> **DATA_DIR convention.** Depends on the pipeline:
>
> | Pipeline kind | Allowed `<data-dir>` | What orchestrator does |
> |---|---|---|
> | upstream (FlowHub flow) | **FlowHub** absolute path only (`/Store/...`, `/personal/<user>/...`, `/openclaw/...`) | `fkit download`s top-level non-sequencing files into `stage/`; FASTQ stays on FlowHub and is consumed there by the flow. |
> | downstream-only | **local** absolute path (`/data/<name>/`) **or** **FlowHub** absolute path | local → `cp -al` (hardlink) the whole tree into `stage/`. FlowHub → `fkit download -s <path> -t stage/` the whole tree. |
>
> Gateway auto-detects local vs FlowHub by trying `[ -d ]` first, then
> `fkit ls --limit 1`. Upstream pipelines reject a local `<data-dir>`
> with an explicit "upload first" error.

- If the pipeline has an `upstream:` block → orchestrator stops after staging
  and prints the upstream skill's entry points. The agent then drives the
  `upstream-pipeline-fkit` skill (`scripts/run.sh submit/poll/finalize`); the
  gateway never embeds fkit / FlowHub logic itself.
- If the pipeline is downstream-only → hardlinks the full DATA_DIR into
  `stage/`, stamps `.fkit_done`, and falls through to `prepare_downstream.sh`.

Exit 0 = launched (not = complete).

### `bash skills/upstream-pipeline-fkit/scripts/run.sh <plan|submit|poll|finalize> <job-id> [pipeline]`
Four-phase fkit driver — **lives inside the skill**, not the gateway. The
agent invokes it per `skills/upstream-pipeline-fkit/SKILL.md`:
- `plan`     — **DRY RUN, mandatory before `submit`.** Resolves the flow
  (`flow list` + `flow inspect`, both free), runs `fkit ls
  <flowhub-data-dir>` (recursing one level into top-level folders) to
  produce a `file_search_plan.json` with REAL fileIds, then runs
  `build_spec.py --dry-run`. Writes
  `reproducibility/pipeline_<id>_plan.json` + structured
  `reproducibility/bindings_report.json`, and prints the **Port → input
  bindings** table plus a **Flow defaults available** table to stdout.
  Never calls `pipeline create`. The agent shows both tables to the user
  and waits for explicit confirmation before `submit`.
- `submit`   — resolve flow, refresh the FlowHub listing for the path
  recorded in `/data/output/<id>/.input_source` (no upload — inputs already live
  on FlowHub), build spec, `pipeline create`; writes
  `/data/output/<id>/.pipeline_id`, refreshes `bindings_report.json` with the real
  fileIds, and folds the report's `defaults_used` / `missing_optional` into
  `/data/output/<id>/upstream_state.json` (`status=SUBMITTED`).
- `poll`     — one `fkit pipeline get` call. Last stdout line is
  `STATUS=<code>`; refreshes `upstream_state.json` with status / summary.
- `finalize` — `fkit download /output/openclaw-<job-id>/` and materialize into
  `/data/output/<id>/stage/<category>/` per `upstream.output_to_stage`; writes
  `stage/manifest.json`, stamps `.fkit_done` (the only signal downstream
  waits on), and sets `upstream_state.json` to `status=FINALIZED`.

### `fkit` (system PATH)
FlowHub CLI. Pre-installed system-wide (no longer bundled in the repo). The
skill's `scripts/run.sh` resolves it via `command -v fkit`; override with
`FKIT=<path>` if you need a non-default binary. Don't call its
`pipeline create` / `flow inspect` subcommands directly from chat —
`skills/upstream-pipeline-fkit/scripts/run.sh` wraps them. Direct use is
allowed for diagnostics: `fkit flow list --limit 1 --json` (non-interactive
auth probe — preferred over bare `fkit project`, which is an interactive
project picker and produces TTY noise in the agent's shell),
`fkit ls <flowhub-path> --limit 1 --json` (auth + readability in one call),
`fkit pipeline get <id> --json`.

### `docker`
Gateway has rootless Docker access. Used only for downstream containers.
- **Never `docker run` an upstream tool image.** Upstream is FlowHub-only.
- Never `docker exec` a container outside an active job.
- `docker ps -a --filter name=openclaw-down-` to inspect downstream containers.

### `python3` + `jq` + `yq`
For parsing YAML/JSON registries and manifests.

## Registries (read-only from chat)

- `registry/pipelines.yaml` — pipeline recipes (upstream FlowHub flow keyword
  + output→stage map + downstream image + skill catalog)

Changes go through a PR. Chat-initiated edits are refused (W4).

## Container capabilities

### Upstream — none locally
All upstream containers (fastp, kraken2, bracken, humann, megahit, prodigal,
eggnog-mapper, …) live on FlowHub. The agent never starts or `docker exec`s
into them.

### `openclaw/downstream:1.1.0`
Most downstream skills run here. Libs: pandas, scipy, statsmodels,
scikit-learn, xgboost, shap, scikit-bio, plotly, seaborn, rpy2 + R with
vegan/phyloseq/DESeq2/MaAsLin2. Mounts: `/job` (rw), `/job/stage` (ro,
populated by `skills/upstream-pipeline-fkit/scripts/run.sh finalize`), `/pipeline` (ro, reference
scripts).

### `openclaw/downstream-dl:1.0.0`
PyTorch / transformer / protein-LM stack for the `downstream-dl` pipeline.

### `openclaw/amplicon:1.0.0`
ASV-based 16S/ITS amplicon analysis stack for the `amplicon-asv` pipeline.
Base: official `quay.io/qiime2/amplicon:2024.10`. Adds: PICRUSt2 in its
own `picrust2` conda env (invoke via `conda run -n picrust2 ...`), plus
R packages `DECIPHER`, `phangorn`, `picante`. Reference DBs
(SILVA / GTDB / UNITE / PICRUSt2 default ref) are NOT baked in — mount
them ro at `/refdb/...` per `runtime.mounts` in `registry/pipelines.yaml`.

### `openclaw/base:1.0.0`
Minimal (pyyaml/jinja2/markdown/pandas/numpy) for text/config-processing skills.

If a skill needs a lib not in these images → add to
`images/<image>/Dockerfile` and rebuild. **Do not** `pip install` at runtime
(ephemeral, not reproducible).

## What's NOT available
- No internet in downstream containers (`--network none`).
- No LLM access inside containers (prompt-injection containment). All LLM
  reasoning happens at the Gateway layer.
- No persistent state across jobs. Job directories are the only storage.
- No local upstream tooling. If FlowHub is unreachable, upstream cannot run.

