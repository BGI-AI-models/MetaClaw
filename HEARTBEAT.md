# HEARTBEAT — Periodic Checks

> The gateway fires this file according to `agents.defaults.heartbeat.every`
> in `openclaw.json` (currently 10m). The per-task `interval:` values below
> further gate which checks actually run on each tick. Keep checks short —
> each one burns tokens. Reply `HEARTBEAT_OK` if nothing fires.

tasks:
  - name: upstream-poll
    interval: 20m
    prompt: |
      For each `/data/output/<id>/.pipeline_id` whose `.fkit_done` marker is absent:
      run `bash skills/upstream-pipeline-fkit/scripts/run.sh poll <id>` and:
        - STATUS=2  (SUCCESS) → tell the user upstream is done and propose
          `skills/upstream-pipeline-fkit/scripts/run.sh finalize <id> <pipeline>` next.
        - STATUS=-1 (FAIL) / -2 (STOP) → tell the user, point at the latest
          `reproducibility/poll_*.json`.
        - STATUS=1  (RUNNING) for longer than the pipeline's
          `timeout_minutes × 1.5` → message: "Job `<id>` looks stuck on
          FlowHub; consider stopping from the FlowHub UI."
      If there is no active upstream job, reply HEARTBEAT_OK.

  - name: downstream-container
    interval: 10m
    prompt: |
      Reap stale / orphaned downstream containers. PID 1 already self-exits
      after `timeout_minutes × 2` (TTL set by prepare_downstream.sh), but
      Docker may keep them around past that, and the agent itself may forget
      W6. This task is the safety net.

      For each container `openclaw-down-<id>` returned by
      `docker ps --filter name=openclaw-down- --format '{{.Names}}\t{{.RunningFor}}'`:

      1. Look up the job:  JOB_DIR=${OPENCLAW_JOBS_ROOT:-/data/output}/<id>
      2. Read the pipeline's `timeout_minutes` from the resolved spec at
         `$JOB_DIR/reproducibility/pipeline.yaml` (field `spec.timeout_minutes`,
         default 240). Wallclock-since-launch comes from
         `$JOB_DIR/.container_started_at` (Unix seconds, written by
         prepare_downstream.sh).
      3. Decide:
         - **Active.** Container age ≤ `timeout_minutes × 1.5`
           AND `$JOB_DIR/.fkit_done` does not exist OR was stamped within
           the last `timeout_minutes × 0.5` minutes → leave alone.
         - **Done, agent forgot W6.** `$JOB_DIR/.fkit_done` exists AND was
           stamped > 30 min ago AND no `downstream_<skill>.log` has been
           modified in the last 30 min → run
           `bash gateway/stop_downstream.sh <id>` and tell the user:
           "Stopped orphaned downstream container for job `<id>` (job
           finished, no recent activity)."
         - **Looks stuck mid-run.** Container age > `timeout_minutes × 1.5`
           AND a `downstream_<skill>.log` was modified in the last 5 min →
           message: "Job `<id>` downstream still running past its budget
           (`<minutes>` min). Let me know if it should be stopped." Do
           NOT auto-stop — work might be legitimate.
         - **Over hard TTL.** Container age > `timeout_minutes × 2.5` →
           run `bash gateway/stop_downstream.sh <id>` regardless of
           activity (the TTL Docker enforced should already have killed
           it; this catches misconfigured restart policies). Message:
           "Hard-stopped downstream container for job `<id>` (over TTL)."

      If no downstream containers are running, reply HEARTBEAT_OK.

  - name: disk-check
    interval: 1h
    prompt: |
      Run `df` on `${OPENCLAW_JOBS_ROOT:-/data/output}`. If <10% free, message the user with
      the 3 oldest job IDs and their sizes. Particularly call out
      `/data/output/<id>/.fkit_download/` — raw FlowHub downloads can be re-pulled if
      needed. Otherwise HEARTBEAT_OK.

  - name: memory-rotation
    interval: 24h
    activeHours:
      start: "03:00"
      end: "04:00"
      timezone: "Asia/Shanghai"
    prompt: |
      Memory housekeeping. Steps:
        1. If `memory/YYYY-MM-DD.md` for today does not exist, create it with
           a single `# <date>` header. Do NOT treat absence as an error.
        2. If yesterday's `memory/YYYY-MM-DD.md` exists and is non-empty, scan
           for: confirmed bugs, user preference changes, novel pipeline edge
           cases, completed jobs (job id + pipeline + outcome). Distill into
           the appropriate `MEMORY.md` section (`User context` /
           `Operational lessons` / `Recent jobs` / `Open questions`). Tag
           every claim with `[stated]`, `[observed]`, or `[inferred]`.
        3. **Size check.** `wc -l MEMORY.md`. If > 200 lines, compress the
           oldest entries in the largest section: merge similar items, drop
           any `[inferred]` entry older than 30 days that hasn't been
           re-confirmed, trim `Recent jobs` to the newest 30.
        4. Never write credentials, PHI, or raw sample contents into MEMORY.md
           — see the `What NEVER goes into this file` section there.
      If nothing changed, HEARTBEAT_OK.

  - name: weekly-summary
    interval: 7d
    activeHours:
      start: "09:00"
      end: "10:00"
      timezone: "Asia/Shanghai"
    prompt: |
      Weekly summary (Monday morning): jobs run, pipelines used, FlowHub vs
      local compute time, failure rate (upstream vs downstream). Post to the
      last active channel.

## On startup (not a heartbeat task — runs once when the agent boots)

- `yaml.safe_load(...)` `registry/pipelines.yaml`. On parse error: refuse new
  requests, message user.
- `fkit flow list --limit 1 --json` — verify the system-installed fkit and
  its auth still work. (Non-interactive auth probe; never use bare
  `fkit project`, which is an interactive picker and produces TTY noise in
  the agent's non-TTY shell.) If it exits non-zero, surface
  "fkit not logged in — `fkit login -k … -s …`".
- `docker image inspect openclaw/downstream:1.1.0 openclaw/downstream-dl:1.0.0
  openclaw/amplicon:1.0.0 openclaw/base:1.0.0`. For any missing: message
  user; do NOT auto-pull.
