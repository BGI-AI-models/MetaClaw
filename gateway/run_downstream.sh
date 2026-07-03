#!/usr/bin/env bash
# gateway/run_downstream.sh
# Phase B: execute a caller-chosen SUBSET of downstream skills inside the
# already-running container (started by prepare_downstream.sh).
#
# Usage: run_downstream.sh <job-id> [--skills s1,s2,...] [--pipeline <name>]
#
# Skill selection precedence (highest first):
#   1) --skills on the CLI
#   2) pipelines.yaml downstream.skills  (only when --pipeline is given)
#   3) every reference_*.py currently staged under /pipeline/scripts/
#
# The skill list is treated as a CATALOG, not a mandatory ordered run —
# callers pass whatever subset is relevant to the task.
set -euo pipefail

JOB_ID="${1:?Usage: run_downstream.sh <job-id> [--skills s1,s2,...] [--pipeline <name>]}"
shift

SKILLS_CSV=""
PIPELINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --skills)    SKILLS_CSV="$2"; shift 2 ;;
    --skills=*)  SKILLS_CSV="${1#--skills=}"; shift ;;
    --pipeline)  PIPELINE="$2"; shift 2 ;;
    --pipeline=*) PIPELINE="${1#--pipeline=}"; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
[ -d "$JOB_DIR" ] || { echo "Job dir missing: ${JOB_DIR}" >&2; exit 1; }

# --- Resolve container --------------------------------------------------------
if [ ! -f "${JOB_DIR}/.container_name" ]; then
  echo "run_downstream: ${JOB_DIR}/.container_name not found." >&2
  echo "Run gateway/prepare_downstream.sh first." >&2
  exit 1
fi
CONTAINER="$(cat "${JOB_DIR}/.container_name")"
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "run_downstream: container ${CONTAINER} is not running." >&2
  echo "Re-run prepare_downstream.sh or start the container manually." >&2
  exit 1
fi

# --- Resolve skill list -------------------------------------------------------
SKILLS_ARR=()
if [ -n "$SKILLS_CSV" ]; then
  IFS=',' read -ra SKILLS_ARR <<< "$SKILLS_CSV"
elif [ -n "$PIPELINE" ]; then
  read -a SKILLS_ARR <<< "$(python3 -c "
import yaml
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
print(' '.join(p.get('downstream', {}).get('skills', [])))
")"
else
  # Fallback: whatever reference_*.py is staged.
  while IFS= read -r f; do
    base="$(basename "$f" .py)"
    SKILLS_ARR+=("${base#reference_}")
  done < <(ls "${JOB_DIR}/.pipeline_scripts/scripts/"reference_*.py 2>/dev/null || true)
fi

if [ ${#SKILLS_ARR[@]} -eq 0 ]; then
  echo "run_downstream: no skills selected (pass --skills or --pipeline)." >&2
  exit 2
fi

echo "Downstream execute — job=${JOB_ID} skills=${SKILLS_ARR[*]}"

DM="${JOB_DIR}/reproducibility/downstream_manifest.json"
[ -f "$DM" ] || echo '{"skills":[]}' > "$DM"
mkdir -p "${JOB_DIR}/reproducibility/logs"

OVERALL_RC=0
for skill in "${SKILLS_ARR[@]}"; do
  echo "[$(date -u +%H:%M:%S)] Downstream skill: ${skill}"
  LOG="${JOB_DIR}/reproducibility/logs/downstream_${skill}.log"

  # Prefer the most recent LLM-customized script; else fall back to the
  # read-only reference under /pipeline/scripts/.
  LATEST="$(docker exec "$CONTAINER" bash -c \
    "ls -t /job/reproducibility/generated_scripts/${skill}_*.py 2>/dev/null | head -1" || true)"

  set +e
  if [ -n "$LATEST" ]; then
    echo "  Using LLM-customized: $LATEST"
    docker exec "$CONTAINER" python "$LATEST" 2>&1 | tee "$LOG"
    RC=${PIPESTATUS[0]}
    USED="$LATEST"
  else
    REF="/pipeline/scripts/reference_${skill}.py"
    # Validate the reference exists before invoking.
    if ! docker exec "$CONTAINER" test -f "$REF"; then
      echo "  ERROR: no customized script and reference missing: $REF" >&2
      echo "         Copy /pipeline/scripts/reference_${skill}.py →" \
           "/job/reproducibility/generated_scripts/${skill}_<ts>.py first." >&2
      RC=127
      USED=""
    else
      echo "  Using reference (no customization): $REF"
      docker exec "$CONTAINER" python "$REF" --job-dir /job 2>&1 | tee "$LOG"
      RC=${PIPESTATUS[0]}
      USED="$REF"
    fi
  fi
  set -e

  jq --arg s "$skill" --arg ec "$RC" --arg log "$LOG" --arg used "$USED" \
     '.skills += [{skill: $s, exit_code: ($ec|tonumber), log: $log, script: $used}]' \
     "$DM" > "${DM}.tmp" && mv "${DM}.tmp" "$DM"

  if [ "$RC" -ne 0 ]; then
    echo "Downstream skill ${skill} failed (rc=${RC})" >&2
    OVERALL_RC=$RC
    break
  fi
done

# NOTE: container is NOT stopped here. Keep it alive for additional skills in
# the same session (see gateway/attach.sh). Use gateway/stop_downstream.sh or
# W6 end-of-job cleanup to tear it down.
exit $OVERALL_RC
