#!/usr/bin/env bash
# gateway/attach.sh
# Attach to the downstream container of an existing job to run one or more
# additional skills, without creating a new job folder.
#
# Usage:
#   attach.sh [<job-id>] --skills s1,s2,...
#   attach.sh [<job-id>] --shell
#
# If <job-id> is omitted, uses $OPENCLAW_SESSION_JOB_ID or ./.current_job_id.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

JOB_ID=""
MODE="skills"
SKILLS_CSV=""
if [ $# -gt 0 ] && [[ "$1" != --* ]]; then
  JOB_ID="$1"; shift
fi
while [ $# -gt 0 ]; do
  case "$1" in
    --skills) SKILLS_CSV="$2"; shift 2 ;;
    --skills=*) SKILLS_CSV="${1#--skills=}"; shift ;;
    --shell)  MODE="shell"; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$JOB_ID" ]; then
  JOB_ID="${OPENCLAW_SESSION_JOB_ID:-}"
fi
if [ -z "$JOB_ID" ] && [ -f "${ROOT_DIR}/.current_job_id" ]; then
  JOB_ID="$(cat "${ROOT_DIR}/.current_job_id")"
fi
[ -n "$JOB_ID" ] || { echo "attach: no job id given/found." >&2; exit 1; }

JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
[ -f "${JOB_DIR}/.container_name" ] || {
  echo "attach: ${JOB_DIR}/.container_name missing. Run prepare_downstream.sh." >&2
  exit 1; }
CONTAINER="$(cat "${JOB_DIR}/.container_name")"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "attach: container ${CONTAINER} not running." >&2
  exit 1
fi

case "$MODE" in
  shell)
    echo "Entering ${CONTAINER}. Edit scripts under /job/reproducibility/generated_scripts/."
    exec docker exec -it "$CONTAINER" bash ;;
  skills)
    [ -n "$SKILLS_CSV" ] || { echo "attach: --skills required." >&2; exit 2; }
    exec bash "${SCRIPT_DIR}/run_downstream.sh" "$JOB_ID" --skills "$SKILLS_CSV" ;;
esac
