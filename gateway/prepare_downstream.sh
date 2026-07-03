#!/usr/bin/env bash
# gateway/prepare_downstream.sh
# Phase A: start the downstream container with a bounded TTL (sleep <ttl>),
# stage reference scripts, record container name. Does NOT execute any skill —
# the Planner/LLM is expected to customize reference scripts into
# generated_scripts/ and then invoke run_downstream.sh with an explicit
# --skills list.
#
# TTL: container PID 1 sleeps for `pipelines.yaml::timeout_minutes × 2`
# (override with OPENCLAW_DOWNSTREAM_TTL_MULTIPLIER), then exits — Docker
# stops the container automatically. This bounds orphan lifetime when the
# agent forgets W6 cleanup or the session ends abnormally. `stop_downstream.sh`
# still works for early manual stop; nothing else changes inside the TTL
# window. If a downstream job legitimately needs longer than the TTL, bump
# `timeout_minutes` in pipelines.yaml — the heartbeat reads the same field
# and will keep both in sync.
#
# Usage: prepare_downstream.sh <job-id> <pipeline-name>
set -euo pipefail

JOB_ID="${1:?}"
PIPELINE="${2:?}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"

# Gate: if this pipeline declares an upstream block, the upstream skill must
# have finished (/data/output/<id>/.fkit_done stamped + stage/manifest.json present)
# before we bring up the downstream container. This is the status-sharing
# contract — the upstream skill is the only writer of .fkit_done, the gateway
# is the only reader.
HAS_UPSTREAM=$(python3 -c "
import yaml
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
print('1' if p.get('upstream') else '0')
")
if [ "$HAS_UPSTREAM" = "1" ]; then
  if [ ! -f "${JOB_DIR}/.fkit_done" ]; then
    echo "prepare_downstream: upstream not finalized yet for job ${JOB_ID}." >&2
    echo "  Expected marker: ${JOB_DIR}/.fkit_done" >&2
    echo "  Drive the upstream skill first:" >&2
    echo "    bash skills/upstream-pipeline-fkit/scripts/run.sh poll     ${JOB_ID}" >&2
    echo "    bash skills/upstream-pipeline-fkit/scripts/run.sh finalize ${JOB_ID} ${PIPELINE}" >&2
    exit 1
  fi
  if [ ! -f "${JOB_DIR}/stage/manifest.json" ]; then
    echo "prepare_downstream: ${JOB_DIR}/.fkit_done is set but stage/manifest.json is missing." >&2
    echo "  Rerun: bash skills/upstream-pipeline-fkit/scripts/run.sh finalize ${JOB_ID} ${PIPELINE}" >&2
    exit 1
  fi
fi

# Resolve downstream image + skill CATALOG + optional runtime tuning.
# Single YAML→JSON pass; the `runtime:` block is optional and any absent field
# falls back to the historical default. See pipelines.yaml header for schema.
META_JSON="$(python3 -c "
import json, yaml
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
d = p.get('downstream', {}) or {}
print(json.dumps({
    'image':           d.get('image', 'openclaw/downstream:1.1.1'),
    'skills':          d.get('skills', []) or [],
    'runtime':         d.get('runtime', {}) or {},
    'timeout_minutes': p.get('timeout_minutes', 240),
}))
")"

IMAGE="$(jq -r '.image' <<< "$META_JSON")"
mapfile -t SKILLS_ARR < <(jq -r '.skills[]?' <<< "$META_JSON")
TIMEOUT_MIN="$(jq -r '.timeout_minutes // 240' <<< "$META_JSON")"
TTL_MULT="${OPENCLAW_DOWNSTREAM_TTL_MULTIPLIER:-2}"
TTL_SECONDS=$(( TIMEOUT_MIN * 60 * TTL_MULT ))

RT_MEMORY="$(jq  -r '.runtime.memory  // "16g"'  <<< "$META_JSON")"
RT_CPUS="$(jq    -r '.runtime.cpus    // "8"'    <<< "$META_JSON")"
RT_NETWORK="$(jq -r '.runtime.network // "none"' <<< "$META_JSON")"
RT_GPUS="$(jq    -r '.runtime.gpus    // ""'     <<< "$META_JSON")"
mapfile -t RT_CAP_DROP < <(jq -r '(.runtime.cap_drop // ["ALL"])[]' <<< "$META_JSON")
mapfile -t RT_CAP_ADD  < <(jq -r '(.runtime.cap_add  // [])[]'      <<< "$META_JSON")
mapfile -t RT_ENV      < <(jq -r '(.runtime.env      // {}) | to_entries[] | "\(.key)=\(.value)"' <<< "$META_JSON")
mapfile -t RT_MOUNTS   < <(jq -r '(.runtime.mounts   // [])[]'      <<< "$META_JSON")

STAGE_DIR="${JOB_DIR}/.pipeline_scripts"
mkdir -p "${STAGE_DIR}/scripts" \
         "${JOB_DIR}/reproducibility/skill_snapshots" \
         "${JOB_DIR}/reproducibility/generated_scripts" \
         "${JOB_DIR}/reproducibility/logs" \
         "${JOB_DIR}/analysis"

# -- Fail fast when reference scripts are missing ------------
MISSING=0
for skill in "${SKILLS_ARR[@]}"; do
  SRC="${ROOT_DIR}/skills/${skill}"
  if [ ! -d "$SRC" ]; then
    echo "prepare_downstream: skill folder missing: ${SRC}" >&2
    MISSING=1; continue
  fi
  # Snapshot the skill (SKILL.md + assets) for audit.
  cp -r "$SRC" "${JOB_DIR}/reproducibility/skill_snapshots/${skill}"

  # Reference script naming convention: reference_<skill-name-with-dashes>.py
  REF_SRC="${SRC}/scripts/reference_${skill}.py"
  if [ -f "$REF_SRC" ]; then
    cp "$REF_SRC" "${STAGE_DIR}/scripts/reference_${skill}.py"
  else
    # Also copy any other helper scripts the skill ships with.
    if [ -d "${SRC}/scripts" ]; then
      cp -r "${SRC}/scripts/." "${STAGE_DIR}/scripts/" || true
    fi
    # Warn loudly: reference template is the canonical starting point.
    echo "prepare_downstream: WARNING — ${REF_SRC} not found; LLM must author" \
         "/job/reproducibility/generated_scripts/${skill}_<ts>.py from scratch." >&2
  fi
done

if [ $MISSING -ne 0 ]; then
  echo "prepare_downstream: aborting — one or more skills missing" >&2
  exit 2
fi

CONTAINER="openclaw-down-${JOB_ID}"

# Idempotent: reuse an already-running container for this job.
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "prepare_downstream: container ${CONTAINER} already running; reusing."
else
  # Clean any stopped leftover with the same name.
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

  # Assemble docker run argv from the (possibly empty) runtime block. Standard
  # mounts/env are always present; everything else comes from pipelines.yaml.
  DOCKER_ARGS=(
      --name "$CONTAINER"
      --network "$RT_NETWORK"
      --memory "$RT_MEMORY"
      --cpus "$RT_CPUS"
      -e "JOB_ID=${JOB_ID}"
      -v "${JOB_DIR}:/job"
      -v "${JOB_DIR}/stage:/job/stage:ro"
      -v "${STAGE_DIR}:/pipeline:ro"
  )
  for cap in ${RT_CAP_DROP[@]+"${RT_CAP_DROP[@]}"}; do
    [ -n "$cap" ] && DOCKER_ARGS+=( --cap-drop "$cap" )
  done
  for cap in ${RT_CAP_ADD[@]+"${RT_CAP_ADD[@]}"}; do
    [ -n "$cap" ] && DOCKER_ARGS+=( --cap-add "$cap" )
  done
  for kv in ${RT_ENV[@]+"${RT_ENV[@]}"}; do
    [ -n "$kv" ] && DOCKER_ARGS+=( -e "$kv" )
  done
  for mnt in ${RT_MOUNTS[@]+"${RT_MOUNTS[@]}"}; do
    [ -n "$mnt" ] && DOCKER_ARGS+=( -v "$mnt" )
  done
  [ -n "$RT_GPUS" ] && DOCKER_ARGS+=( --gpus "$RT_GPUS" )

  # Bounded TTL — see file header. PID 1 self-exits when the sleep ends,
  # Docker stops the container. Guarantees orphan reaping; manual stop
  # (stop_downstream.sh) still works for early shutdown.
  docker run -d "${DOCKER_ARGS[@]}" "$IMAGE" sleep "$TTL_SECONDS"
  echo "prepare_downstream: container TTL = ${TTL_SECONDS}s (${TIMEOUT_MIN}m × ${TTL_MULT})"
fi

echo "$CONTAINER" > "${JOB_DIR}/.container_name"
# Record container launch wallclock so the heartbeat can stop containers that
# outlive their TTL (in case Docker is configured to keep them around past
# PID 1 exit, e.g. with custom restart policies).
date -u +%s > "${JOB_DIR}/.container_started_at"

# Seed an empty downstream_manifest.json (appended by run_downstream.sh).
DM="${JOB_DIR}/reproducibility/downstream_manifest.json"
[ -f "$DM" ] || echo '{"skills":[]}' > "$DM"

cat <<EOF
Downstream container ready: ${CONTAINER}
  Job dir     : ${JOB_DIR}
  Reference   : /pipeline/scripts/reference_<skill>.py  (read-only in container)
  Customize → : /job/reproducibility/generated_scripts/<skill>_<YYYYMMDD-HHMMSS>.py
  Catalog     : ${SKILLS_ARR[*]:-<none>}
  TTL         : ${TTL_SECONDS}s (auto-stop deadline; bump timeout_minutes if work needs longer)
Next step (Planner):
  1. docker exec -it ${CONTAINER} bash   # inspect data under /job/stage
  2. Copy /pipeline/scripts/reference_<skill>.py → /job/reproducibility/generated_scripts/<skill>_<ts>.py
  3. Edit for this dataset, then run:
     bash gateway/run_downstream.sh ${JOB_ID} --skills <skill1,skill2,...>
EOF
