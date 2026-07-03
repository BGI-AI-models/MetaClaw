#!/usr/bin/env bash
# Usage: gateway.sh <pipeline> <data-dir> [overrides.yaml] [--skills s1,s2,...]
#
# <data-dir> semantics depend on whether the pipeline has an upstream block:
#
#   * pipeline.upstream IS SET  — must be a FlowHub absolute path (e.g.
#     `/Store/cohorts/gut/`, `/personal/<user>/runs/gut/`). FlowHub flows can
#     only consume FlowHub-resident inputs. The gateway validates with
#     `fkit ls --limit 1`.
#
#   * pipeline.upstream IS ABSENT (downstream-only) — accepts EITHER:
#         (a) a local absolute path (default convention: `/data/<name>/`) —
#             orchestrator hardlinks/copies into /data/output/<id>/stage/.
#         (b) a FlowHub absolute path — orchestrator `fkit download`s into
#             /data/output/<id>/stage/.
#     Auto-detected: tried as local first; if no such directory, tried as
#     FlowHub via `fkit ls`. Whichever resolves is what's used. Recorded in
#     /data/output/<id>/.input_source_kind for downstream audit.
#
# Session JOB_ID: one conversation == one job. If OPENCLAW_SESSION_JOB_ID is
# already set (exported by a previous call in the same shell/session), reuse it
# instead of generating a new folder each invocation.
#
# Upstream phase (when present) runs on FlowHub via `fkit`. This wrapper just
# delegates to orchestrator.sh, which records the data-dir and returns
# control so the agent can plan → submit → poll on a 10-minute cadence.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

PIPELINE="${1:?Usage: gateway.sh <pipeline> <data-dir> [overrides.yaml] [--skills s1,s2,...]}"
DATA_DIR="${2:?}"
OVERRIDES="${3:-}"
SKILLS_OVERRIDE=""

# Optional: --skills s1,s2,... restricts downstream execution to a subset.
shift 2
[ $# -gt 0 ] && shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --skills) SKILLS_OVERRIDE="$2"; shift 2 ;;
    --skills=*) SKILLS_OVERRIDE="${1#--skills=}"; shift ;;
    *) shift ;;
  esac
done

# Validate pipeline + read upstream flag in one shot.
HAS_UPSTREAM="$(python3 -c "
import yaml, sys
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml')).get('pipelines', {})
if '${PIPELINE}' not in p:
    print(f'Unknown pipeline. Available: {list(p.keys())}', file=sys.stderr); sys.exit(1)
print('1' if p['${PIPELINE}'].get('upstream') else '0')
")"

# Path must be absolute either way (local /data/... or FlowHub /Store/...).
case "$DATA_DIR" in
  /*) ;;
  *)  echo "gateway: <data-dir> must be an absolute path. Got: ${DATA_DIR}" >&2
      echo "        Examples:  /data/gut_cohort/  (local)  /Store/cohorts/gut/  (FlowHub)" >&2
      exit 1 ;;
esac

FKIT="${FKIT:-fkit}"

# Smoke-test the data-dir according to the pipeline's needs.
if [ "$HAS_UPSTREAM" = "1" ]; then
  # FlowHub-only: upstream consumers can't read local files.
  if [ -d "$DATA_DIR" ]; then
    echo "gateway: pipeline '${PIPELINE}' has an upstream FlowHub flow — <data-dir>" >&2
    echo "        must be a FlowHub path, not a local directory (${DATA_DIR})." >&2
    echo "        Upload first:  fkit upload ${DATA_DIR} /personal/<user>/<dest>/" >&2
    echo "        Then re-run with the FlowHub path." >&2
    exit 1
  fi
  if ! command -v "$FKIT" >/dev/null 2>&1; then
    echo "gateway: fkit not on PATH (FKIT=$FKIT). Install the FlowHub fkit CLI or export FKIT=<path>." >&2
    exit 1
  fi
  if ! "$FKIT" ls "$DATA_DIR" --limit 1 --json >/dev/null 2>"${ROOT_DIR}/.ls_smoke_err.log"; then
    echo "gateway: cannot list FlowHub path ${DATA_DIR}." >&2
    echo "        Verify the path exists on FlowHub and your project has read access." >&2
    echo "        Last 5 lines of fkit error:" >&2
    tail -n 5 "${ROOT_DIR}/.ls_smoke_err.log" 2>/dev/null | sed 's/^/        /' >&2 || true
    rm -f "${ROOT_DIR}/.ls_smoke_err.log"
    exit 1
  fi
  rm -f "${ROOT_DIR}/.ls_smoke_err.log"
  DATA_KIND="flowhub"
else
  # Downstream-only: try local first, then FlowHub.
  if [ -d "$DATA_DIR" ]; then
    DATA_KIND="local"
  elif command -v "$FKIT" >/dev/null 2>&1 \
       && "$FKIT" ls "$DATA_DIR" --limit 1 --json \
            >/dev/null 2>"${ROOT_DIR}/.ls_smoke_err.log"; then
    DATA_KIND="flowhub"
    rm -f "${ROOT_DIR}/.ls_smoke_err.log"
  else
    echo "gateway: <data-dir> not found as local directory and could not be" >&2
    echo "        listed on FlowHub: ${DATA_DIR}" >&2
    if [ -f "${ROOT_DIR}/.ls_smoke_err.log" ]; then
      echo "        fkit error (last 5 lines):" >&2
      tail -n 5 "${ROOT_DIR}/.ls_smoke_err.log" 2>/dev/null | sed 's/^/          /' >&2 || true
      rm -f "${ROOT_DIR}/.ls_smoke_err.log"
    fi
    echo "        For local inputs:  place data under /data/<name>/ and pass /data/<name>/" >&2
    echo "        For FlowHub data:  pass a valid FlowHub absolute path (e.g. /Store/...)." >&2
    exit 1
  fi
fi

# --- Jobs root --------------------------------------------------------------
# All per-job state lives OUTSIDE the agent's git checkout. Default location
# is /data/output/<job-id>. Override with OPENCLAW_JOBS_ROOT for tests / CI.
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
export OPENCLAW_JOBS_ROOT="$JOBS_ROOT"
mkdir -p "$JOBS_ROOT" || { echo "gateway: cannot create JOBS_ROOT=${JOBS_ROOT}" >&2; exit 1; }

# --- Session JOB_ID ----------------------------------------------------------
if [ -n "${OPENCLAW_SESSION_JOB_ID:-}" ]; then
  JOB_ID="$OPENCLAW_SESSION_JOB_ID"
  echo "Reusing session job: ${JOB_ID}"
else
  JOB_ID="$(date +%Y%m%d-%H%M%S)-$(head -c 4 /dev/urandom | xxd -p)"
  export OPENCLAW_SESSION_JOB_ID="$JOB_ID"
  # Session bookmark stays in the workspace (it's a pointer, not an output).
  echo "$JOB_ID" > "${ROOT_DIR}/.current_job_id"
fi

echo "Launching ${PIPELINE} — Job ${JOB_ID}"
echo "  Job dir:    ${JOBS_ROOT}/${JOB_ID}"
echo "  DATA_DIR:   ${DATA_DIR}"
echo "  Source:     ${DATA_KIND}  (auto-detected)"
# Pass the resolved kind to orchestrator via env so it doesn't have to re-detect.
export OPENCLAW_DATA_KIND="$DATA_KIND"
bash "${SCRIPT_DIR}/orchestrator.sh" "$PIPELINE" "$JOB_ID" "$DATA_DIR" "$OVERRIDES" "$SKILLS_OVERRIDE"
