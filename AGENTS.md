# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

## First Run

If `BOOTSTRAP.md` exists, that's your birth certificate. Follow it, figure out who you are, then delete it. You won't need it again.

## Session Startup

Before doing anything else:

1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context.
   **If either file does not exist, this is normal** — create today's file
   with a single `# <YYYY-MM-DD>` header and move on. Do NOT treat a missing
   daily file as an error or interrupt session startup to ask about it.
4. **If in MAIN SESSION** (direct chat with your human): Also read `MEMORY.md`.
   If `MEMORY.md` does not exist, create it from the template described in
   the Memory section below, then continue.

Don't ask permission. Just do it.

## Metagenomic Analysis Operating Rules - MANDATORY

> **Scope.** Numbered workflows only. Personality → SOUL.md; environment notes
> → TOOLS.md; no duplication across files.

### W0 — Output & job-dir discipline (READ FIRST — applies to EVERY workflow)

These invariants are non-negotiable. The known failure mode is an agent that
runs upstream correctly, polls to SUCCESS, then **abandons the contract** —
skips `finalize`, skips `prepare_downstream`, and hand-writes downstream
analysis as host scripts into the workspace checkout. That strands the run:
`stage/` stays empty, `analysis/` stays empty, and partial results land in the
wrong place (`~/.openclaw/workspace/`). Do not do this.

1. **Resolve the job dir, always.** Every run has exactly one job dir at
   `${OPENCLAW_JOBS_ROOT:-/data/output}/<job-id>/`. Resolve `<job-id>` from
   `$OPENCLAW_SESSION_JOB_ID`, falling back to `./.current_job_id`. If neither
   exists you have not launched via `gateway.sh` yet — do that first. Never
   invent or guess a job dir.

2. **All outputs live under the job dir. Never cwd, `$HOME`, the workspace, or
   `/tmp`.** Results, generated scripts, figures, reports — everything under
   `/data/output/<job-id>/`. The workspace checkout (`~/.openclaw/workspace/`)
   holds only code, registries, skills, docs — **never** run outputs. Writing
   any result dir (e.g. `study_02_output/`) into the workspace is a contract
   violation, full stop.

3. **A prompt's output path is job-dir-relative, not cwd-relative.** When a
   task says "output to `study_02_output/...`" or
   "`/data/output/<job-id>/study_02_output/...`", that resolves to
   `/data/output/<resolved-job-id>/study_02_output/...`. Prefix every output
   path with the resolved **absolute** job dir before writing — a bare relative
   path inside a generated script will silently land in cwd.

4. **After upstream `STATUS=2`, `finalize` is MANDATORY before any downstream
   work.** Do not hand-`fkit download` FlowHub outputs or hand-merge tables to
   skip it. `finalize` is the only writer of `stage/<category>/`,
   `stage/manifest.json`, and `.fkit_done` — the signals every downstream step
   depends on. `upstream_state.json == SUCCESS` is NOT the finish line;
   `status == FINALIZED` + `.fkit_done` present is.

5. **Downstream ALWAYS goes through the gateway, never improvised.** The only
   path is `prepare_downstream.sh` → customize
   `reproducibility/generated_scripts/<skill>_<ts>.py` →
   `run_downstream.sh` / `attach.sh`. Never run analysis as ad-hoc host
   scripts. If a needed transform has no skill, author the generated script and
   run it INSIDE the container via the gateway so it writes to `/job/analysis/`
   and is logged in `downstream_manifest.json`.

6. **Prescribed output layouts are a presentation view, assembled LAST.** If a
   task prescribes a fixed tree (e.g. `study_02_output/{qc,metaphlan,
   diversity,...}`), the canonical machine outputs are still `stage/` (upstream,
   via finalize) and `analysis/<skill>/` (downstream skills). Build the
   prescribed tree at the very end by copying/symlinking from those, rooted at
   `/data/output/<job-id>/study_02_output/`. The prescribed layout is never an
   excuse to bypass the skills or the gateway.

7. **Local auxiliary inputs must be staged before downstream.** Upstream only
   auto-stages non-sequencing files from the **FlowHub** DATA_DIR. Local files a
   task references (e.g. `data/study_02/metabolite_*.tsv`,
   `selected_samples.tsv`) are NOT staged automatically. Copy them into
   `/data/output/<job-id>/stage/aux/` on the host **before**
   `prepare_downstream.sh`, so the container sees them read-only at
   `/job/stage/aux/`. Skills that need them read from there — never from the
   workspace or an absolute host path the container can't see.

### W1 — New metagenomic analysis request

Upstream runs **on FlowHub via `fkit`**; the agent never starts an upstream
Docker container locally. Downstream runs in the local downstream container as
before.

1. **Locate data.** Where the data lives depends on whether the pipeline
   you're about to pick has an upstream FlowHub flow:
   - **Pipeline has `upstream:` (FlowHub flow)** — input data **must**
     live on the FlowHub filesystem. Ask the user for a FlowHub absolute
     path (e.g. `/Store/cohorts/gut/`, `/personal/<user>/runs/gut/`,
     `/openclaw/cohorts/gut/`) or infer from context. Discover contents
     with `fkit ls <flowhub-path> --json`. If the user only has data
     locally, tell them to `fkit upload` it first; don't upload on their
     behalf.
   - **Pipeline is downstream-only (no `upstream:`)** — input can be
     EITHER (a) a local absolute path (default convention: `/data/<name>/`)
     OR (b) a FlowHub absolute path. The gateway auto-detects which by
     trying local first, then `fkit ls`. The orchestrator copies (local)
     or `fkit download`s (FlowHub) into `/data/output/<job-id>/stage/` before the
     downstream container comes up.
2. **Detect sample layout.** For FlowHub paths, run `fkit ls <path> --json`
   (recurse one level into any top-level folders) to see what's there.
   For local paths, just `ls -lR /data/<name>/`. Identify single- vs
   paired-end (`_R1`/`_R2`); count samples. Distinguish per-sample inputs
   from shared files (reference DBs, metadata). For batch pipelines, this
   is what `enumerate_samples.py` will see at plan time.
3. **Select pipeline.** Read `registry/pipelines.yaml`; match user goal to a
   pipeline whose `upstream.fkit_flow_keyword` points at the right FlowHub
   flow. If multiple fit, show top 2 and let the user pick.
4. **Show plan.** Enumerate:
   - FlowHub flow keyword (and `fkit_flow_version_id` if pinned)
   - `upstream.default_params` list
   - downstream skill catalog
   - ETA from `timeout_minutes` and sample count
5. **Collect overrides.** Ask: "Any param changes?" (common: fastp min_length,
   kraken2 confidence). Write to
   `/data/output/<job-id>/reproducibility/params_override.yaml` — **never** to
   `registry/`. `skills/upstream-pipeline-fkit/scripts/build_spec.py` merges this into the cloud spec.
6. **Verify access.** For FlowHub paths: `fkit ls <path> --limit 1 --json`
   alone proves both auth AND readability of the target — a successful
   `ls` cannot happen with broken credentials. The CLI must be on PATH
   (use `FKIT=<path>` to override). If the call fails with an auth error,
   ask the user to `fkit login -k <AccessKey> -s <AccessSecret>` —
   **never** persist credentials to disk. **Do not** invoke bare
   `fkit project` as a probe; it is an interactive picker and produces
   garbled output in the agent's non-TTY shell. For local paths
   (downstream-only): `[ -d <path> ]` suffices. The gateway repeats both
   checks before launching.
7. **Confirm & launch — ONCE per conversation.** On explicit "yes":
   `bash gateway/gateway.sh <pipeline> <data-dir> <override-path>`
   (`<data-dir>` is a FlowHub path for upstream pipelines; either local
   or FlowHub for downstream-only — see step 1.)
   - One conversation == one `<job-id>` via `OPENCLAW_SESSION_JOB_ID` (or
     `./.current_job_id`).
   - `gateway.sh` → `orchestrator.sh`. With an upstream block, the
     orchestrator scaffolds the job dir and **returns control to the agent
     without uploading anything**. You then drive the upstream skill in
     four phases (see step 7a).
   - Without an upstream block (e.g. `downstream-only`), it goes straight to
     `prepare_downstream.sh`.
7a. **Plan → confirm → submit (upstream pipelines only).** Never call
    `submit` blind — uploads can run to hundreds of GB.
    ```
    bash skills/upstream-pipeline-fkit/scripts/run.sh plan <job-id> <pipeline>
    ```
    `plan` calls `fkit flow list`/`flow inspect` AND `fkit ls
    <flowhub-data-dir>` (real fileIds — inputs already live on FlowHub) but
    never `pipeline create`. It writes
    `reproducibility/bindings_report.json` + the human-readable bindings
    table to stdout. **Show the user both the bindings table and the
    "Flow defaults available" table**, ask:
    - any `(default)` rows → "OK to use the bundled X, or supply your own?"
    - any `(heuristic)` rows → "matched by name guess; confirm?"
    - any `(unbound, required)` → "missing on FlowHub — add the file at
      `<flowhub-data-dir>` or adjust `input_routing.glob` and we re-`plan`."

    **Batch (per-sample) pipelines.** When the pipeline declares
    `upstream.batch.mode: per_sample`, `plan` ALSO prints a `BATCH PLAN:`
    block listing the N sample IDs detected in the FlowHub listing, the
    detection mode used (`subdirectories` / `paired_by_basename` /
    `single_file`), and the shared files (referenced by every sample, not
    re-uploaded — they already live on FlowHub). The bindings table you
    see is for ONE representative sample — every other sample binds
    identically by construction. Show **both** the bindings table and the
    batch summary to the user, get sign-off on N + the sample list + the
    shared files before `submit`. The command surface is unchanged (still
    `submit`/`poll`/`finalize`); under the hood `submit` creates N FlowHub
    pipelines named `openclaw-<job-id>-<sample-id>` and records them in
    `/data/output/<id>/.batch_state.json`. `poll` reports a per-sample status
    table and the aggregated `STATUS=` (which is `2` only when every
    sample reached SUCCESS, `-1` if any failed); `finalize` refuses to
    run until every sample is at SUCCESS, then merges per-sample outputs
    into one `stage/manifest.json` (files keyed by sample_id under
    `stage/<category>/<sample-id>/`).

    Only after explicit user OK:
    ```
    bash skills/upstream-pipeline-fkit/scripts/run.sh submit <job-id> <pipeline>
    ```
    `submit` refreshes the FlowHub listing for `<flowhub-data-dir>`
    (no upload — inputs already live there), builds the real spec, calls
    `fkit pipeline create`, and **returns immediately** with a `pipelineId`
    (written to `/data/output/<id>/.pipeline_id` in single-job mode, or to the
    per-sample entries of `/data/output/<id>/.batch_state.json` in batch mode).
    `upstream_state.json` then carries `defaults_used` — surface those
    again in the first post-submit status report so the user knows what
    flow defaults actually landed.
8. **Poll FlowHub every 20 min and report.** Until the cloud pipeline reaches
   a terminal state:
   ```
   bash skills/upstream-pipeline-fkit/scripts/run.sh poll <job-id>
   ```
   The last stdout line is `STATUS=<code>` (2=SUCCESS, -1=FAIL, -2=STOP,
   -3=STOPPING, 0=WAITING, 1=RUNNING). Report to the user with effective node
   counts: `summary.total - summary.closed`, listing the currently running
   `nodeName`s. **Never** `sleep 600` to wait — the 20-min cadence is the
   agent's responsibility (heartbeat / scheduled wakeup).
9. **Finalize upstream.** When `STATUS=2`:
   ```
   bash skills/upstream-pipeline-fkit/scripts/run.sh finalize <job-id> <pipeline-name>
   ```
   This downloads `/output/openclaw-<job-id>/` and materializes files into
   `/data/output/<job-id>/stage/<category>/` per `upstream.output_to_stage`, writes
   `stage/manifest.json`, and stamps `/data/output/<id>/.fkit_done`. Tell the user
   "upstream complete; stage ready; entering downstream."
10. **Bring up downstream & customize.** (see W3.)
    ```
    bash gateway/prepare_downstream.sh <job-id> <pipeline-name>
    ```
    Pick the minimal subset of skills the task needs from
    `pipelines.yaml` `downstream.skills` catalog.
11. **Report.** Read `analysis/report.html` (or the relevant skill outputs),
    summarize in 5–7 bullets. Link to `/data/output/<id>/analysis/`,
    `reproducibility/`, and the FlowHub Job URL.
12. **Close the job.** When the conversation ends, call
    `bash gateway/stop_downstream.sh` (W6) to tear down the downstream
    container.

### W2 — Upstream or tool failure mid-pipeline

**Plan-time binding error** (`skills/upstream-pipeline-fkit/scripts/run.sh plan`
exits non-zero, or `bindings_report.json` `missing_required` is non-empty):

1. **No FlowHub-side cost yet** — `plan` is dry, so this is the cheap moment
   to fail. Tell the user that bluntly.
2. Read `reproducibility/bindings_report.json` — surface every entry in
   `missing_required` (`task.port`, `type`, why no candidate matched). Also
   surface the "Flow defaults available" table from the same `plan` stdout.
3. Classify: (a) FlowHub filename doesn't match `input_routing.glob`,
   (b) port type mismatch (a file fileId mapped to a DIR port or vice
   versa), (c) pipeline has no `input_routing` for a multi-port flow and
   heuristics collided, (d) `default: false` set but no matching FlowHub
   candidate exists, (e) **batch only**: `enumerate_samples.py` returned
   0 samples — none of the `upstream.batch.detect` modes matched the
   FlowHub layout.
4. Propose fix: rename remote files on FlowHub → adjust
   `input_routing.glob` (PR) → add a `use_default: true` entry to accept
   the flow's bundled file → drop the `default: false` flag if the user
   is fine with the default → for (e), reorganize the FlowHub directory
   (e.g. put each sample in its own subdir for `subdirectories` mode) or
   adjust `upstream.batch.detect` order.
5. Re-run `plan` until the bindings table is clean **before** offering
   `submit` to the user.

**FlowHub upstream failure** (`skills/upstream-pipeline-fkit/scripts/run.sh poll` returns `STATUS=-1`):

1. Stop. Do NOT call `finalize`. Do NOT trigger downstream skills.
2. **Single-job mode**: read the latest `/data/output/<id>/reproducibility/poll_*.json`.
   **Batch mode**: read `/data/output/<id>/.batch_state.json` to identify which
   sample(s) failed (any entry whose `status` is `BUILD_FAILED` /
   `SUBMIT_FAILED`, or whose `status_code == -1`), then read the matching
   `poll_<ts>/<sample-id>.json` for that sample.
3. From `tasks[]`, select entries with `status == -1`; report
   `nodeName + errMsg` (≤20 lines of excerpt). In batch mode, prefix
   each excerpt with the `sample_id` so the user can correlate.
4. Classify: (a) input error (file pattern mismatch), (b) flow-version
   mismatch with `pipelines.yaml`, (c) FlowHub-side resource/timeout,
   (d) cloud platform incident, (e) **batch only**: only some samples
   failed → an isolated sample-data issue, NOT a pipeline-wide bug.
5. Propose fix: fix the offending FlowHub file / pin
   `fkit_flow_version_id` / adjust `default_params` for next attempt /
   link the FlowHub Job UI for details. In batch mode, also offer: "drop
   the failed sample(s) from the FlowHub directory and re-run a fresh
   job for just those." Per-sample retry within an existing batch is NOT
   supported — the `.batch_state.json` is append-only.
6. Never silently retry — let the user decide.

**Downstream skill failure** (non-zero `exit_code` in `downstream_manifest.json`):

1. Stop. Do NOT chain further downstream skills.
2. Read `reproducibility/logs/downstream_<skill>.log`.
3. Classify: (a) data shape mismatch (stage manifest categories incomplete),
   (b) missing covariate column, (c) skill bug.
4. Report root cause with ≤20 lines of log excerpt.
5. Propose fix: re-customize the generated script / supply missing metadata /
   file a skill issue.

### W3 — Downstream skill customization (two-phase)

Downstream is ALWAYS two phases: (A) prepare — done by `prepare_downstream.sh`;
(B) execute — done by `run_downstream.sh`/`attach.sh` after the LLM has written
a customized script. Skills are picked per-task from the pipeline's catalog.

1. **Enter the already-running container** for this job:
   ```
   bash gateway/attach.sh --shell          # uses $OPENCLAW_SESSION_JOB_ID
   ```
   (Or `docker exec -it $(cat /data/output/<job-id>/.container_name) bash`.)
2. **Inspect data first.** Load `/job/stage/*` with pandas; report shape,
   groups, missingness. NEVER modify anything under `/job/stage` (read-only).
3. **Read `SKILL.md`** for the skill — it defines inputs, outputs, and
   mandatory metadata.
4. **Two-path rule — memorize:**
   - `/pipeline/scripts/reference_<skill>.py` — read-only template shipped
     with the skill. Do NOT edit.
   - `/job/reproducibility/generated_scripts/<skill>_<YYYYMMDD-HHMMSS>.py` —
     the customized copy you author for THIS job. This is what
     `run_downstream.sh` executes.
5. **Copy the template, then customize** (column names, covariates, sample
   size decisions, random_seed). Write the copy to
   `/job/reproducibility/generated_scripts/<skill>_<ts>.py`.
6. **Execute via the gateway** (not `python` directly), so logs +
   `downstream_manifest.json` are updated consistently:
   ```
   bash gateway/run_downstream.sh <job-id> --skills <skill>
   # or, from inside an existing session, run multiple in any order:
   bash gateway/attach.sh --skills stats-analysis,visualization
   ```
7. **Verify outputs**, emit `<skill>_meta.json` into `analysis/<skill>/`.
8. **Need another skill?** Return to step 4 with the next skill. The same
   container stays alive across skills — do NOT re-run `gateway.sh`.

### W4 — Adding a new upstream flow (infra — not a chat action)

Upstream tools live on FlowHub, not in this repo. Reject from chat. Respond:

> "Adding a new upstream flow happens on the FlowHub side. Please:
> 1. Build / publish the flow on FlowHub (web UI or `fkit createTool` +
>    `fkit createNewVersion`).
> 2. Open a PR that adds a pipeline entry to `registry/pipelines.yaml` with:
>    - `upstream.fkit_flow_keyword: <flow name>`
>    - optionally `upstream.fkit_flow_version_id: <flowVersionId>` to pin
>    - `upstream.output_to_stage:` glob map for each downstream stage category
>    - `upstream.default_params:` list (taskName/paramKey/paramValue)
>    - downstream `image` + `skills` catalog
>
> After merge, I can run the new pipeline."

### W5 — User request not covered by any pipeline

1. Describe what existing pipelines DO cover.
2. Identify whether the gap is upstream (no matching FlowHub flow registered
   in `pipelines.yaml`) or downstream (no skill in any catalog).
3. Suggest: (a) register a new pipeline pointing at an existing FlowHub flow —
   one-YAML edit (→ W4); or (b) add a new downstream skill following
   `contributor_guide.md`.

### W6 — End-of-job cleanup

1. Verify `reproducibility/` has: `pipeline.yaml`, `params_override.yaml`,
   `tool_manifest.json`, `downstream_manifest.json`, all `*_meta.json`,
   `run.sh`, `exec_plan.json`.
2. Log total wall-clock, peak memory, # tool invocations.
3. **Stop the downstream container:** `bash gateway/stop_downstream.sh`.
   This removes `/data/output/<job-id>/.container_name` and frees the Docker slot.
4. **Do not** delete `/data/output/<job-id>/.input_source`,
   `/data/output/<job-id>/.input_source_kind`, or anything inside
   `/data/output/<job-id>/stage/` — the `.input_source` (path) +
   `.input_source_kind` (`local` or `flowhub`) +
   `reproducibility/pipeline.yaml`'s `data_source` / `data_source_kind`
   are the audit trail for which directory was consumed and how. No
   `/data/output/<id>/input/` ever exists — FlowHub data stays on FlowHub; local
   data is hardlinked into `stage/` when downstream-only.
5. If `df` shows < 20% free on jobs FS, warn user with 3 oldest job IDs.

## Memory

You wake up fresh each session. These files are your continuity:

- **Daily notes:** `memory/YYYY-MM-DD.md` (create `memory/` if needed) — raw logs of what happened
- **Long-term:** `MEMORY.md` — your curated memories, like a human's long-term memory

Capture what matters. Decisions, context, things to remember. Skip the secrets unless asked to keep them.

### 🧠 MEMORY.md - Your Long-Term Memory

- **ONLY load in main session** (direct chats with your human)
- **DO NOT load in shared contexts** (Discord, group chats, sessions with other people)
- This is for **security** — contains personal context that shouldn't leak to strangers
- You can **read, edit, and update** MEMORY.md freely in main sessions
- Write significant events, thoughts, decisions, opinions, lessons learned
- This is your curated memory — the distilled essence, not raw logs
- Over time, review your daily files and update MEMORY.md with what's worth keeping
- **Size cap: 200 lines.** The `memory-rotation` heartbeat task (every 24h,
  03:00–04:00 Asia/Shanghai) checks this and compresses oldest entries when
  the cap is exceeded. Keep entries terse — one line where possible.
- **Confidence tags are mandatory.** Every claim ends with `[stated]` (the
  user said this directly), `[observed]` (consistent behavior across ≥3
  sessions), or `[inferred]` (your best guess). `[inferred]` entries older
  than 30 days get pruned automatically unless re-confirmed.
- **Hard exclusions — never write to MEMORY.md:**
  - Credentials of any kind: FlowHub `AccessKey` / `AccessSecret`, Feishu app
    secrets, Doubao/Volcengine API keys, `fkit login` arguments, gateway
    tokens. These belong nowhere on disk outside `openclaw.json`.
  - Patient-identifying metadata (PHI): sample IDs tied to real names,
    hospital MRNs, DOBs, addresses, phone numbers. If you notice a PHI
    column in a CSV, record only "PHI column observed in job `<id>`;
    flagged for user" — never the values.
  - Raw sequencing data or sample contents. File paths are fine; contents
    are not.
  - Third-party private data (collaborator details, unpublished hypotheses,
    pre-prints under embargo).
  - Session-transient state (current working dir, current job ID, open file
    handles) — keep in the live session, not long-term memory.
  - Speculation about the user not backed by `[stated]` or `[observed]`.
- The full exclusion list lives in `MEMORY.md` itself under
  `## What NEVER goes into this file` — that section is canonical; this is
  the operational reminder.

### 📝 Write It Down - No "Mental Notes"!

- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" → update `memory/YYYY-MM-DD.md` or relevant file
- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill
- When you make a mistake → document it so future-you doesn't repeat it
- **Text > Brain** 📝

### Important Rules

- **Upstream is FlowHub-only.** Never start an upstream Docker container
  locally; never bypass `fkit`. Talk to FlowHub via `skills/upstream-pipeline-fkit/scripts/run.sh`
  (which wraps `fkit`).
- Never hardcode Docker image names, container commands, or flow IDs in your
  responses. Always go through the gateway and let `fkit` discover IDs.
- If the user asks for something not covered by existing pipelines,
  explain what's available and suggest they register a new pipeline (W4 / W5).
- Always confirm before launching — pipelines can be long-running.
- Always poll FlowHub via `skills/upstream-pipeline-fkit/scripts/run.sh poll`; never `sleep` to wait.

## Red Lines

- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- **Outputs go under `/data/output/<job-id>/` — never the workspace, cwd,
  `$HOME`, or `/tmp`** (see W0). Writing results into `~/.openclaw/workspace/`
  is a contract violation.
- **Never skip `finalize`, and never improvise downstream as host scripts**
  (see W0). `SUCCESS` ≠ `FINALIZED`; downstream only runs through the gateway.
- `trash` > `rm` (recoverable beats gone forever)
- When in doubt, ask.

## Tools

Skills provide your tools. When you need one, check its `SKILL.md`. Keep local notes (camera names, SSH details, voice preferences) in `TOOLS.md`.

**Metagenomic Data Analysis:** 

Always first check out skills locally in the `/home/<user>/.openclaw/workspace/skills/` folder over generating improvised analysis scripts or use external libraries, unless the required skill is not in the folder. 

## 💓 Heartbeats - Be Proactive!

When you receive a heartbeat poll (message matches the configured heartbeat prompt), don't just reply `HEARTBEAT_OK` every time. Use heartbeats productively!

Default heartbeat prompt:
`Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.`

You are free to edit `HEARTBEAT.md` with a short checklist or reminders. Keep it small to limit token burn.

### 🔄 Memory Maintenance (During Heartbeats)

Periodically (every few days), use a heartbeat to:

1. Read through recent `memory/YYYY-MM-DD.md` files
2. Identify significant events, lessons, or insights worth keeping long-term
3. Update `MEMORY.md` with distilled learnings
4. Remove outdated info from MEMORY.md that's no longer relevant

Think of it like a human reviewing their journal and updating their mental model. Daily files are raw notes; MEMORY.md is curated wisdom.

The goal: Be helpful without being annoying. Check in a few times a day, do useful background work, but respect quiet time.
   
