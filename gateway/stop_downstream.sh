#!/usr/bin/env bash
# gateway/stop_downstream.sh — tear down the downstream container for a job.
# Call this at end-of-session (W6), NOT between skill invocations.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

JOB_ID="${1:-${OPENCLAW_SESSION_JOB_ID:-}}"
if [ -z "$JOB_ID" ] && [ -f "${ROOT_DIR}/.current_job_id" ]; then
  JOB_ID="$(cat "${ROOT_DIR}/.current_job_id")"
fi
[ -n "$JOB_ID" ] || { echo "stop_downstream: no job id." >&2; exit 1; }

JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
[ -f "${JOB_DIR}/.container_name" ] || exit 0
CONTAINER="$(cat "${JOB_DIR}/.container_name")"

docker stop "$CONTAINER" >/dev/null 2>&1 || true
docker rm   "$CONTAINER" >/dev/null 2>&1 || true
rm -f "${JOB_DIR}/.container_name"
echo "Stopped ${CONTAINER}"
