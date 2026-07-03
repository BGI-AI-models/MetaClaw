#!/usr/bin/env bash
# skills/upstream-pipeline-fkit/scripts/run.sh
#
# The upstream skill's own fkit driver. This script lives under the skill so the
# gateway does not encode FlowHub conventions — the skill is the source of
# truth. The agent (per SKILL.md) invokes this in four phases; the gateway
# only sets up the job directory.
#
#   plan     — DRY RUN: resolve flow + run `fkit ls` against the FlowHub
#              DATA_DIR (recorded by the orchestrator in
#              /data/output/<id>/.input_source as a FlowHub absolute path) + run
#              build_spec.py --dry-run. Prints the same Port → input bindings
#              table the agent will see at submit time, plus a "Flow defaults
#              available" table, and writes
#              reproducibility/pipeline_<id>_plan.json + bindings_report.json
#              (mode=plan). Does NOT call `pipeline create`. The agent calls
#              this BEFORE submit so the user can confirm / re-route via
#              input_routing without spawning a real pipeline.
#   submit   — resolve flow, refresh the FlowHub listing (no upload — inputs
#              already live on FlowHub), build spec, submit; write
#              /data/output/<id>/.pipeline_id (status: SUBMITTED). Also folds
#              bindings_report.json's `defaults_used` and `missing_optional`
#              into upstream_state.json so the agent can report
#              silently-applied flow defaults without parsing stderr.
#   poll     — single `fkit pipeline get` call. Prints `STATUS=<code>` on the
#              last stdout line and refreshes /data/output/<id>/upstream_state.json.
#   finalize — download /output/openclaw-<job-id>/, materialize files into
#              /data/output/<id>/stage/<category>/ (file sharing), write
#              stage/manifest.json + .fkit_done (status sharing) so downstream
#              can pick up and the agent knows when to start downstream.
#
# Usage:
#   run.sh plan     <job-id> <pipeline-name>
#   run.sh submit   <job-id> <pipeline-name>
#   run.sh poll     <job-id>
#   run.sh finalize <job-id> <pipeline-name>
set -euo pipefail

SKILL_SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SKILL_SCRIPTS_DIR")"
ROOT_DIR="$(cd "${SKILL_DIR}/../.." && pwd)"
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"

FKIT="${FKIT:-fkit}"
if ! command -v "$FKIT" >/dev/null 2>&1; then
  echo "fkit not found on PATH (FKIT=$FKIT). Install the FlowHub fkit CLI or export FKIT=<path>." >&2
  exit 1
fi

PHASE="${1:?Usage: run.sh <plan|submit|poll|finalize> <job-id> [pipeline-name]}"
JOB_ID="${2:?job-id required}"
PIPELINE="${3:-}"

JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
REPRO="${JOB_DIR}/reproducibility"
STAGE="${JOB_DIR}/stage"
SCRATCH="${JOB_DIR}/.fkit_download"
SPEC="${REPRO}/pipeline_${JOB_ID}_spec.json"
PIPELINE_ID_FILE="${JOB_DIR}/.pipeline_id"
DONE_MARKER="${JOB_DIR}/.fkit_done"
STATE_FILE="${JOB_DIR}/upstream_state.json"
INPUT_SOURCE_FILE="${JOB_DIR}/.input_source"
BATCH_STATE_FILE="${JOB_DIR}/.batch_state.json"
SAMPLES_JSON="${JOB_DIR}/reproducibility/samples.json"

# `DATA_DIR` is a FlowHub absolute path (e.g. `/Store/cohorts/gut/`,
# `/personal/<user>/runs/gut/`, `/openclaw/cohorts/gut/`). Inputs live on
# FlowHub; this driver never uploads from a local filesystem.
REMOTE_OUTPUT_DIR="/output/openclaw-${JOB_ID}/"

mkdir -p "$REPRO" "$STAGE"

# Is the current pipeline a batch (per-sample fan-out) pipeline?
#   Reads upstream.batch.mode from pipelines.yaml. Empty / absent → single-job.
is_batch_pipeline() {
  [ -n "$PIPELINE" ] || return 1
  local mode
  mode="$(python3 -c "
import yaml
try:
    p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines'].get('${PIPELINE}', {})
    print(((p.get('upstream') or {}).get('batch') or {}).get('mode', '') or '')
except Exception:
    pass
")"
  [ "$mode" = "per_sample" ]
}

read_pipeline_field() {
  local field="$1"
  python3 -c "
import yaml, json, sys
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines'].get('${PIPELINE}')
if p is None:
    sys.exit('unknown pipeline: ${PIPELINE}')
u = p.get('upstream', {}) or {}
v = u.get('${field}')
print(json.dumps(v) if not isinstance(v, str) else v)
"
}

# Read DATA_DIR (a FlowHub absolute path) from .input_source. Validation is
# minimal — the real check is whether `fkit ls` returns anything sensible.
read_data_dir() {
  [ -f "$INPUT_SOURCE_FILE" ] || {
    echo "${INPUT_SOURCE_FILE} missing — orchestrator must record the FlowHub DATA_DIR there." >&2
    return 1
  }
  local v
  v="$(tr -d '\r\n' < "$INPUT_SOURCE_FILE" | sed 's/[[:space:]]*$//')"
  if [ -z "$v" ]; then
    echo "${INPUT_SOURCE_FILE} is empty." >&2
    return 1
  fi
  case "$v" in
    /*) printf '%s' "$v" ;;
    *)  echo "DATA_DIR in ${INPUT_SOURCE_FILE} is not a FlowHub absolute path: ${v}" >&2; return 1 ;;
  esac
}

# Build a comprehensive FlowHub listing for DATA_DIR. fkit `ls` returns the
# immediate children; for any top-level folder we additionally recurse one
# level so that `subdirectories` batch mode (each top folder == one sample)
# sees the files. Output: file_search-shaped JSON whose entry `name` is the
# path RELATIVE to DATA_DIR (e.g. ``sampleA/R1.fq.gz`` or ``metadata.tsv``).
fkit_listing() {
  local data_dir="$1" out="$2"
  local top="${REPRO}/.ls_top.json"
  if ! "$FKIT" ls "$data_dir" --limit 1000 --json > "$top" 2>"${REPRO}/ls_err.log"; then
    echo "[fkit] 'fkit ls ${data_dir}' failed:" >&2
    sed 's/^/    /' "${REPRO}/ls_err.log" >&2 || true
    return 1
  fi
  # Recurse one level into any top-level folder, merging entries into a flat
  # listing keyed by relative path. We intentionally cap the recursion at 1
  # level — flat (paired_by_basename, single_file) and one-deep
  # (subdirectories) cover every batch detection mode supported today.
  python3 - "$top" "$REPRO" "$out" "$data_dir" "$FKIT" <<'PY'
import json, os, subprocess, sys
top_path, repro, out_path, data_dir, fkit = sys.argv[1:6]
top = json.load(open(top_path))
def unwrap(o):
    return o["data"] if isinstance(o, dict) and "data" in o else o
def items(o):
    o = unwrap(o)
    if isinstance(o, list): return o
    return (o.get("files") or o.get("items") or []) if isinstance(o, dict) else []
def is_dir(it):
    k = str(it.get("type") or it.get("kind") or it.get("fileType") or "").lower()
    return k in {"dir","folder","directory"} or it.get("isFolder") is True or it.get("isDir") is True
flat = []
for it in items(top):
    name = (it.get("name") or it.get("fileName") or "").strip().lstrip("/")
    if not name: continue
    fid = it.get("fileId") or it.get("id") or ""
    if is_dir(it):
        flat.append({"name": name, "type": "folder", "fileId": fid})
        # one-level recursion
        sub_dir = data_dir.rstrip("/") + "/" + name + "/"
        sub_path = os.path.join(repro, f".ls_{name.replace('/','_')}.json")
        try:
            subprocess.run([fkit, "ls", sub_dir, "--limit", "1000", "--json"],
                           check=True, stdout=open(sub_path,"w"),
                           stderr=open(os.path.join(repro,"ls_err.log"),"a"))
        except subprocess.CalledProcessError as e:
            print(f"[fkit] recursion into {sub_dir} failed (rc={e.returncode}); "
                  f"that folder will be treated as opaque.", file=sys.stderr)
            continue
        try:
            sub = json.load(open(sub_path))
        except Exception:
            continue
        for s in items(sub):
            sub_name = (s.get("name") or s.get("fileName") or "").strip().lstrip("/")
            if not sub_name: continue
            sub_fid = s.get("fileId") or s.get("id") or ""
            sub_type = "folder" if is_dir(s) else "file"
            # Store relpath: <topfolder>/<basename>. Strip any leading
            # absolute prefix fkit might echo back.
            base = sub_name.rsplit("/",1)[-1]
            flat.append({"name": f"{name}/{base}", "type": sub_type, "fileId": sub_fid})
    else:
        flat.append({"name": name, "type": "file", "fileId": fid})
json.dump({"data": flat}, open(out_path,"w"), indent=2)
print(f"[fkit] listing → {out_path}  ({len(flat)} entries)", file=sys.stderr)
PY
}

# Confirm the FlowHub DATA_DIR resolves and is non-empty. Cheaper than
# fkit_listing; used by `plan` purely for early-exit messaging.
fkit_check_dir() {
  local data_dir="$1"
  if ! "$FKIT" ls "$data_dir" --limit 1 --json >/dev/null 2>"${REPRO}/ls_err.log"; then
    echo "[fkit] cannot list ${data_dir} on FlowHub:" >&2
    sed 's/^/    /' "${REPRO}/ls_err.log" >&2 || true
    return 1
  fi
}

write_state() {
  local status="$1" code="${2:-}" extra="$3"
  [ -n "$extra" ] || extra='{}'
  STATE_STATUS="$status" STATE_CODE="$code" STATE_EXTRA="$extra" \
  STATE_JOB_ID="$JOB_ID" STATE_PIPELINE="$PIPELINE" \
  STATE_PID_FILE="$PIPELINE_ID_FILE" STATE_OUT="$STATE_FILE" \
  python3 - <<'PY'
import json, os, time
pid_path = os.environ["STATE_PID_FILE"]
state = {
    "job_id":      os.environ["STATE_JOB_ID"],
    "pipeline":    os.environ["STATE_PIPELINE"],
    "status":      os.environ["STATE_STATUS"],
    "status_code": os.environ["STATE_CODE"],
    "pipeline_id": open(pid_path).read().strip() if os.path.exists(pid_path) else "",
    "updated_at":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
extra = json.loads(os.environ["STATE_EXTRA"])
if isinstance(extra, dict):
    state.update(extra)
open(os.environ["STATE_OUT"], "w").write(json.dumps(state, indent=2))
PY
}

# ════════════════════════════════════════════════════════════════════════
#                  Common phase: resolve flow keyword + version
# ════════════════════════════════════════════════════════════════════════
resolve_flow_version() {
  local kw vid
  kw="$(read_pipeline_field fkit_flow_keyword)"
  vid="$(read_pipeline_field fkit_flow_version_id || true)"
  [ -n "$kw" ] && [ "$kw" != "null" ] || { echo "pipelines.yaml ${PIPELINE}.upstream.fkit_flow_keyword missing" >&2; exit 2; }

  "$FKIT" flow list --keyword "$kw" --limit 100 --json \
    > "${REPRO}/flow_list.json"

  if [ -z "$vid" ] || [ "$vid" = "null" ]; then
    vid="$(jq -r --arg kw "$kw" '
      ([.[]? // .[]? | select(.flowName == $kw)] | .[0].versions | sort_by(.version) | last // empty | .flowVersionId)
      // ([.[]? // .[]?] | .[0].versions | sort_by(.version) | last | .flowVersionId)
    ' "${REPRO}/flow_list.json")"
  fi
  [ -n "$vid" ] && [ "$vid" != "null" ] || { echo "could not resolve flowVersionId for keyword '$kw'" >&2; exit 1; }
  echo "$vid" > "${REPRO}/.flow_version_id"
  "$FKIT" flow inspect "$vid" --json > "${REPRO}/flow_inspect.json"
  printf '%s' "$vid"
}

phase_plan() {
  [ -n "$PIPELINE" ] || { echo "plan: pipeline-name required" >&2; exit 2; }
  DATA_DIR="$(read_data_dir)" || exit 1

  echo "[plan] FlowHub DATA_DIR: ${DATA_DIR}  (no local copy — inputs live on FlowHub)"
  echo "[plan] resolving flow for pipeline=${PIPELINE}  (no submit, just flow list/inspect + ls)"
  local vid; vid="$(resolve_flow_version)"
  echo "[plan] flowVersionId = ${vid}"

  # Real fkit ls — inputs are already on FlowHub, so the listing is the same
  # one build_spec.py will see at submit time. Real fileIds, not placeholders.
  echo "[plan] listing FlowHub contents under ${DATA_DIR}"
  local plan_files="${REPRO}/file_search_plan.json"
  fkit_listing "$DATA_DIR" "$plan_files" || {
    write_state "PLAN_FAILED" "" "{\"reason\": \"fkit ls failed\", \"data_dir\": \"$DATA_DIR\"}"
    exit 1
  }

  # build_spec --dry-run writes pipeline_<id>_plan.json + bindings_report.json
  # without contacting FlowHub. Errors → exit 2 (same as submit).
  local plan_spec="${REPRO}/pipeline_${JOB_ID}_plan.json"
  local plan_report="${REPRO}/bindings_report.json"
  set +e
  python3 "${SKILL_SCRIPTS_DIR}/build_spec.py" \
      --job-id     "$JOB_ID" \
      --pipeline   "$PIPELINE" \
      --inspect    "${REPRO}/flow_inspect.json" \
      --files      "$plan_files" \
      --pipelines  "${ROOT_DIR}/registry/pipelines.yaml" \
      --overrides  "${REPRO}/params_override.yaml" \
      --flow-vid   "$vid" \
      --output     "$plan_spec" \
      --report     "$plan_report" \
      --dry-run
  local bs_rc=$?
  set -e

  # Always print the "Flow defaults available" table so the agent can offer
  # them to the user even when nothing was bound to `default`.
  python3 - <<'PY' "${REPRO}/flow_inspect.json"
import json, sys
inspect = json.load(open(sys.argv[1]))
data = inspect.get("data", inspect)
open_nodes = {n.get("nodeName"): int(n.get("openStatus", 0))
              for n in (data.get("nodes") or [])}
rows = []
for inp in (data.get("inputs") or []):
    task, port = inp.get("taskName"), inp.get("name")
    if open_nodes.get(task, 0) != 1:
        continue
    for field in ("defaultFiles", "defaultDirs"):
        for entry in (inp.get(field) or []):
            kind = "DIR" if field == "defaultDirs" else "FILE"
            rows.append((task, port, kind,
                         entry.get("name") or entry.get("fileName") or "(unnamed)",
                         entry.get("fileId") or ""))
print()
print("Flow defaults available (Phase 3 fallback candidates):")
if not rows:
    print("  (none — flow ships no defaults; every open port needs an explicit binding)")
for (t, p, k, n, fid) in rows:
    print(f"  {t}.{p:<20} [{k:>4}]  default = {n}  [{fid}]")
PY

  if [ $bs_rc -ne 0 ]; then
    write_state "PLAN_FAILED" "" "{\"plan_report\": \"$plan_report\", \"flow_version_id\": \"$vid\", \"data_dir\": \"$DATA_DIR\"}"
    echo "[plan] build_spec.py reported errors (see above). FIX input_routing and re-run plan." >&2
    exit $bs_rc
  fi

  write_state "PLANNED" "" "{\"plan_spec\": \"$plan_spec\", \"plan_report\": \"$plan_report\", \"flow_version_id\": \"$vid\", \"data_dir\": \"$DATA_DIR\"}"
  echo ""
  echo "[plan] DRY RUN complete. No FlowHub pipeline was created."
  echo "       Plan spec:  $plan_spec"
  echo "       Bindings:   $plan_report"
  echo "       Show the bindings table + flow defaults to the user; collect any"
  echo "       re-routing in /data/output/<id>/reproducibility/params_override.yaml (params)"
  echo "       or via a pipelines.yaml PR (input_routing). When the user confirms:"
  echo "         bash skills/upstream-pipeline-fkit/scripts/run.sh submit ${JOB_ID} ${PIPELINE}"
}

phase_submit() {
  [ -n "$PIPELINE" ] || { echo "submit: pipeline-name required" >&2; exit 2; }
  DATA_DIR="$(read_data_dir)" || exit 1

  echo "[fkit] FlowHub DATA_DIR: ${DATA_DIR}  (no upload — inputs already live there)"
  echo "[fkit] resolving flow for pipeline=${PIPELINE}"
  local vid; vid="$(resolve_flow_version)"

  REMOTE_OUTPUT_DIR="/output/openclaw-${JOB_ID}/"
  printf 'input_dir: %s\noutput_dir: %s\nmode: flowhub-resident\n' \
    "$DATA_DIR" "$REMOTE_OUTPUT_DIR" \
    > "${REPRO}/.remote_paths"

  # Refresh the listing so build_spec sees the live FlowHub state (in case
  # files were added between `plan` and `submit`).
  echo "[fkit] refreshing FlowHub listing for ${DATA_DIR}"
  fkit_listing "$DATA_DIR" "${REPRO}/file_search.json" || {
    echo "submit: 'fkit ls ${DATA_DIR}' failed — cannot resolve fileIds." >&2
    exit 1
  }

  local bind_report="${REPRO}/bindings_report.json"
  python3 "${SKILL_SCRIPTS_DIR}/build_spec.py" \
      --job-id     "$JOB_ID" \
      --pipeline   "$PIPELINE" \
      --inspect    "${REPRO}/flow_inspect.json" \
      --files      "${REPRO}/file_search.json" \
      --pipelines  "${ROOT_DIR}/registry/pipelines.yaml" \
      --overrides  "${REPRO}/params_override.yaml" \
      --flow-vid   "$vid" \
      --output     "$SPEC" \
      --report     "$bind_report"

  echo "[fkit] submitting"
  "$FKIT" pipeline create "$SPEC" --json | tee "${REPRO}/pipeline_create.json"

  local pid
  pid="$(jq -r '.pipelineId // .data.pipelineId // empty' "${REPRO}/pipeline_create.json")"
  [ -n "$pid" ] || { echo "could not extract pipelineId from response" >&2; exit 1; }
  echo "$pid" > "$PIPELINE_ID_FILE"

  # Fold the structured bindings report into upstream_state.json so the agent
  # can surface silently-used flow defaults and unbound optional ports in its
  # status reports without parsing stderr.
  local state_extra
  state_extra="$(BIND_REPORT="$bind_report" VID="$vid" DD="$DATA_DIR" python3 - <<'PY'
import json, os
rep_path = os.environ["BIND_REPORT"]
extra = {"flow_version_id": os.environ["VID"], "bindings_report": rep_path,
         "data_dir": os.environ["DD"]}
try:
    rep = json.load(open(rep_path))
    extra["defaults_used"]    = rep.get("defaults_used", [])
    extra["missing_optional"] = rep.get("missing_optional", [])
except Exception:
    pass
print(json.dumps(extra))
PY
)"
  write_state "SUBMITTED" "" "$state_extra"
  echo "[fkit] submitted: pipelineId=${pid}"
  if [ -f "$bind_report" ]; then
    local n_def
    n_def="$(jq '.defaults_used | length' "$bind_report" 2>/dev/null || echo 0)"
    if [ "${n_def:-0}" -gt 0 ]; then
      echo "[fkit] NOTE: ${n_def} port(s) bound to flow-provided defaults — see"
      echo "       upstream_state.json \`.defaults_used\` and report to the user."
    fi
  fi
  echo "Poll with:  bash skills/upstream-pipeline-fkit/scripts/run.sh poll ${JOB_ID}"
}

phase_poll() {
  [ -f "$PIPELINE_ID_FILE" ] || { echo "poll: ${PIPELINE_ID_FILE} not found; submit first" >&2; exit 1; }
  local pid; pid="$(cat "$PIPELINE_ID_FILE")"
  local ts; ts="$(date +%Y%m%d-%H%M%S)"
  local out="${REPRO}/poll_${ts}.json"
  "$FKIT" pipeline get "$pid" --json > "$out"

  # Human summary + machine-readable last line "STATUS=<code>".
  jq -r '
    "pipelineId: \(.pipelineId // "?")",
    "status: \(.status) (total=\(.summary.total // 0) closed=\(.summary.closed // 0) success=\(.summary.success // 0) running=\(.summary.running // 0) pending=\(.summary.pending // 0) failed=\(.summary.failed // 0) stopped=\(.summary.stopped // 0))",
    "STATUS=\(.status)"
  ' "$out"

  local code; code="$(jq -r '.status' "$out")"
  local label
  case "$code" in
    -3) label=STOPPING ;;
    -2) label=STOP ;;
    -1) label=FAIL ;;
     0) label=WAITING ;;
     1) label=RUNNING ;;
     2) label=SUCCESS ;;
     *) label=UNKNOWN ;;
  esac
  local summary; summary="$(jq -c '.summary // {}' "$out")"
  write_state "$label" "$code" "{\"last_poll\": \"$out\", \"summary\": $summary}"
}

phase_finalize() {
  [ -n "$PIPELINE" ] || { echo "finalize: pipeline-name required" >&2; exit 2; }
  [ -f "$PIPELINE_ID_FILE" ] || { echo "finalize: no pipelineId on disk" >&2; exit 1; }

  # Selective download (single-job mode): only files matching
  # upstream.output_to_stage globs are pulled — NOT the whole `/output/<outdir>/`
  # tree. This is the fix for the 2026-06-09 metagenomics-full × 20 finalize
  # blocker, where the bulk `-r` download tried to drag every intermediate
  # FASTQ/BAM/kraken table back to host disk before the glob filter ran.
  # Resumability is now per-file (skip if exists+non-empty) instead of an
  # all-or-nothing `.dl_done` marker.
  mkdir -p "$SCRATCH"
  echo "[fkit] selective download from ${REMOTE_OUTPUT_DIR} → ${SCRATCH}"
  python3 "${SKILL_SCRIPTS_DIR}/selective_download.py" \
      --pipelines     "${ROOT_DIR}/registry/pipelines.yaml" \
      --pipeline      "$PIPELINE" \
      --remote-outdir "$REMOTE_OUTPUT_DIR" \
      --local-root    "$SCRATCH" \
      --fkit          "$FKIT" \
      --summary       "${REPRO}/selective_download.json"
  date -u +%FT%TZ > "${SCRATCH}/.dl_done"

  echo "[stage] materializing into ${STAGE}/"
  python3 "${SKILL_SCRIPTS_DIR}/materialize_stage.py" \
      --job-id    "$JOB_ID" \
      --pipeline  "$PIPELINE" \
      --pipelines "${ROOT_DIR}/registry/pipelines.yaml" \
      --src       "$SCRATCH" \
      --stage     "$STAGE"

  date -u +%FT%TZ > "$DONE_MARKER"
  write_state "FINALIZED" "2" "{\"stage\": \"${STAGE}\", \"manifest\": \"${STAGE}/manifest.json\"}"
  echo "[fkit] finalize complete — stage/ ready, manifest written, .fkit_done stamped"
  echo "Stage:    ${STAGE}/"
  echo "Manifest: ${STAGE}/manifest.json"
  echo "Marker:   ${DONE_MARKER}"
  echo "Downstream can now be triggered (e.g. bash gateway/prepare_downstream.sh ${JOB_ID} ${PIPELINE})."
}

# ════════════════════════════════════════════════════════════════════════
#                       BATCH (per-sample) phases
# ════════════════════════════════════════════════════════════════════════
#
# A batch pipeline declares `upstream.batch.mode: per_sample` in
# pipelines.yaml. The local job dir still has a single job-id; what changes
# is that the skill submits N FlowHub pipelines (one per sample), each named
# `openclaw-<job-id>-<sample-id>`, with outputs landing at
# `/output/openclaw-<job-id>-<sample-id>/` so they don't collide.
#
# Inputs already live on FlowHub. `enumerate_samples.py` consumes the
# FlowHub listing (`file_search.json`) instead of a local FS walk; the
# per-sample fileId subset is sliced by basename from that same listing.

phase_plan_batch() {
  [ -n "$PIPELINE" ] || { echo "plan: pipeline-name required" >&2; exit 2; }
  DATA_DIR="$(read_data_dir)" || exit 1

  echo "[plan/batch] FlowHub DATA_DIR: ${DATA_DIR}"

  local vid; vid="$(resolve_flow_version)"

  # The same listing serves enumerate_samples + every sample's build_spec.
  local listing="${REPRO}/file_search_plan.json"
  echo "[plan/batch] listing FlowHub contents under ${DATA_DIR}"
  fkit_listing "$DATA_DIR" "$listing" || {
    write_state "PLAN_FAILED" "" "{\"reason\": \"fkit ls failed\", \"data_dir\": \"$DATA_DIR\", \"batch\": true}"
    exit 1
  }

  echo "[plan/batch] enumerating samples in FlowHub listing"
  python3 "${SKILL_SCRIPTS_DIR}/enumerate_samples.py" \
      --listing   "$listing" \
      --data-dir  "$DATA_DIR" \
      --pipelines "${ROOT_DIR}/registry/pipelines.yaml" \
      --pipeline  "$PIPELINE" \
      --out       "$SAMPLES_JSON"

  # Preview ONE representative sample's bindings (the first sorted sample);
  # all other samples bind identically by construction (same flow + same
  # input_routing globs + same shared files).
  local rep_sid
  rep_sid="$(jq -r '.samples | keys | sort | .[0]' "$SAMPLES_JSON")"
  echo "[plan/batch] preview sample: ${rep_sid}"

  # Slice the listing → entries whose basename belongs to this sample group
  # or to shared files. build_spec.py keys by basename.
  local per_file="${REPRO}/file_search_${rep_sid}.json"
  SAMPLES_JSON_PATH="$SAMPLES_JSON" SID="$rep_sid" \
  LS_PATH="$listing" OUT_PATH="$per_file" python3 - <<'PY'
import json, os
samples = json.load(open(os.environ["SAMPLES_JSON_PATH"]))
sid = os.environ["SID"]
keep = {os.path.basename(p) for p in samples["shared"]} \
     | {os.path.basename(p) for p in samples["samples"][sid]}
payload = json.load(open(os.environ["LS_PATH"]))
items = payload.get("data") if isinstance(payload, dict) else payload
if isinstance(items, dict):
    items = items.get("files") or items.get("items") or []
filtered = [it for it in (items or [])
            if (it.get("name") or it.get("fileName") or "").rsplit("/",1)[-1] in keep]
json.dump({"data": filtered}, open(os.environ["OUT_PATH"], "w"), indent=2)
PY

  local plan_spec="${REPRO}/pipeline_${JOB_ID}_${rep_sid}_plan.json"
  local plan_report="${REPRO}/bindings_report_${rep_sid}.json"
  set +e
  python3 "${SKILL_SCRIPTS_DIR}/build_spec.py" \
      --job-id     "$JOB_ID" \
      --pipeline   "$PIPELINE" \
      --sample-id  "$rep_sid" \
      --inspect    "${REPRO}/flow_inspect.json" \
      --files      "$per_file" \
      --pipelines  "${ROOT_DIR}/registry/pipelines.yaml" \
      --overrides  "${REPRO}/params_override.yaml" \
      --flow-vid   "$vid" \
      --output     "$plan_spec" \
      --report     "$plan_report" \
      --dry-run
  local bs_rc=$?
  set -e

  # Batch summary so the agent knows N and the sample IDs.
  SAMPLES_JSON_PATH="$SAMPLES_JSON" python3 - <<'PY'
import json, os
samples = json.load(open(os.environ["SAMPLES_JSON_PATH"]))
sids = sorted(samples["samples"])
print("")
print(f"BATCH PLAN: {len(sids)} sample(s) detected via {samples['detect_mode']}.")
print(f"  Submission count: {len(sids)} (one FlowHub pipeline per sample).")
print(f"  Naming: spec.name = spec.outputDir = openclaw-<job-id>-<sample-id>")
print(f"  FlowHub data dir: {samples['data_dir']}")
print(f"  Sample IDs:")
for sid in sids:
    nfiles = len(samples["samples"][sid])
    print(f"    - {sid:<24}  ({nfiles} file{'s' if nfiles!=1 else ''})")
print(f"  Shared files (referenced by every sample, never re-uploaded):")
for path in samples["shared"]:
    print(f"    - {path}")
PY

  if [ $bs_rc -ne 0 ]; then
    write_state "PLAN_FAILED" "" "{\"plan_report\": \"$plan_report\", \"flow_version_id\": \"$vid\", \"batch\": true, \"representative_sample\": \"$rep_sid\", \"data_dir\": \"$DATA_DIR\"}"
    echo "[plan/batch] preview sample ${rep_sid} reported binding errors above." >&2
    echo "[plan/batch] All other samples bind identically — fix input_routing then re-plan." >&2
    exit $bs_rc
  fi

  write_state "PLANNED" "" "{\"plan_report\": \"$plan_report\", \"flow_version_id\": \"$vid\", \"batch\": true, \"representative_sample\": \"$rep_sid\", \"samples_json\": \"$SAMPLES_JSON\", \"data_dir\": \"$DATA_DIR\"}"
  echo ""
  echo "[plan/batch] DRY RUN complete. No FlowHub submissions were created."
  echo "  Samples:        $SAMPLES_JSON"
  echo "  Preview spec:   $plan_spec"
  echo "  Preview bind:   $plan_report"
  echo "  Show the per-sample bindings + the BATCH PLAN summary above to the"
  echo "  user. After confirmation:"
  echo "    bash skills/upstream-pipeline-fkit/scripts/run.sh submit ${JOB_ID} ${PIPELINE}"
}

phase_submit_batch() {
  [ -n "$PIPELINE" ] || { echo "submit: pipeline-name required" >&2; exit 2; }
  DATA_DIR="$(read_data_dir)" || exit 1

  echo "[fkit/batch] FlowHub DATA_DIR: ${DATA_DIR}  (no upload — inputs already live there)"

  local vid; vid="$(resolve_flow_version)"

  REMOTE_OUTPUT_DIR=""
  printf 'input_dir: %s\nmode: flowhub-resident\nbatch: true\n' \
    "$DATA_DIR" > "${REPRO}/.remote_paths"

  # Refresh the listing — both for enumerate_samples and for every sample's
  # build_spec input — to catch any files added since `plan`.
  local listing="${REPRO}/file_search.json"
  echo "[fkit/batch] refreshing FlowHub listing for ${DATA_DIR}"
  fkit_listing "$DATA_DIR" "$listing" || {
    echo "submit: 'fkit ls ${DATA_DIR}' failed — cannot resolve fileIds." >&2
    exit 1
  }

  echo "[fkit/batch] enumerating samples"
  python3 "${SKILL_SCRIPTS_DIR}/enumerate_samples.py" \
      --listing   "$listing" \
      --data-dir  "$DATA_DIR" \
      --pipelines "${ROOT_DIR}/registry/pipelines.yaml" \
      --pipeline  "$PIPELINE" \
      --out       "$SAMPLES_JSON"

  # Build N per-sample specs and submit each.
  echo '{"mode":"batch","pipeline":"'"$PIPELINE"'","flow_version_id":"'"$vid"'","data_dir":"'"$DATA_DIR"'","samples":[]}' \
    > "$BATCH_STATE_FILE"

  local n_total n_ok n_fail
  n_total=0; n_ok=0; n_fail=0
  while IFS= read -r sid; do
    [ -n "$sid" ] || continue
    n_total=$((n_total + 1))
    echo ""
    echo "[fkit/batch] ── sample ${sid}  (${n_total}) ──"

    # Subset listing → entries whose basename belongs to this sample group
    # or to shared files.
    local per_file="${REPRO}/file_search_${sid}.json"
    SAMPLES_JSON_PATH="$SAMPLES_JSON" SID="$sid" \
    LS_PATH="$listing" OUT_PATH="$per_file" python3 - <<'PY'
import json, os
samples = json.load(open(os.environ["SAMPLES_JSON_PATH"]))
sid = os.environ["SID"]
keep = {os.path.basename(p) for p in samples["shared"]} \
     | {os.path.basename(p) for p in samples["samples"][sid]}
payload = json.load(open(os.environ["LS_PATH"]))
items = payload.get("data") if isinstance(payload, dict) else payload
if isinstance(items, dict):
    items = items.get("files") or items.get("items") or []
filtered = [it for it in (items or [])
            if (it.get("name") or it.get("fileName") or "").rsplit("/",1)[-1] in keep]
json.dump({"data": filtered}, open(os.environ["OUT_PATH"], "w"), indent=2)
PY

    local spec="${REPRO}/pipeline_${JOB_ID}_${sid}_spec.json"
    local bind_report="${REPRO}/bindings_report_${sid}.json"
    set +e
    python3 "${SKILL_SCRIPTS_DIR}/build_spec.py" \
        --job-id     "$JOB_ID" \
        --pipeline   "$PIPELINE" \
        --sample-id  "$sid" \
        --inspect    "${REPRO}/flow_inspect.json" \
        --files      "$per_file" \
        --pipelines  "${ROOT_DIR}/registry/pipelines.yaml" \
        --overrides  "${REPRO}/params_override.yaml" \
        --flow-vid   "$vid" \
        --output     "$spec" \
        --report     "$bind_report"
    local bs_rc=$?
    set -e
    if [ $bs_rc -ne 0 ]; then
      echo "[fkit/batch] build_spec failed for sample ${sid} (rc=$bs_rc) — see $bind_report" >&2
      n_fail=$((n_fail + 1))
      jq --arg s "$sid" --arg r "$bind_report" \
         '.samples += [{sample_id: $s, status: "BUILD_FAILED", report_path: $r}]' \
         "$BATCH_STATE_FILE" > "${BATCH_STATE_FILE}.tmp" && mv "${BATCH_STATE_FILE}.tmp" "$BATCH_STATE_FILE"
      continue
    fi

    local create_resp="${REPRO}/pipeline_create_${sid}.json"
    echo "[fkit/batch]   submitting ${sid}"
    if ! "$FKIT" pipeline create "$spec" --json > "$create_resp" 2>>"${REPRO}/submit_errors.log"; then
      echo "[fkit/batch]   create failed for ${sid} — see ${create_resp}" >&2
    fi
    local pid
    pid="$(jq -r '.pipelineId // .data.pipelineId // empty' "$create_resp")"
    if [ -z "$pid" ]; then
      echo "[fkit/batch]   no pipelineId in response for ${sid}" >&2
      n_fail=$((n_fail + 1))
      jq --arg s "$sid" --arg sp "$spec" --arg r "$bind_report" \
         '.samples += [{sample_id: $s, status: "SUBMIT_FAILED", spec_path: $sp, report_path: $r}]' \
         "$BATCH_STATE_FILE" > "${BATCH_STATE_FILE}.tmp" && mv "${BATCH_STATE_FILE}.tmp" "$BATCH_STATE_FILE"
      continue
    fi
    n_ok=$((n_ok + 1))
    local outdir="openclaw-${JOB_ID}-${sid}"
    jq --arg s "$sid" --arg pid "$pid" --arg name "$outdir" \
       --arg out "/output/${outdir}/" --arg sp "$spec" --arg r "$bind_report" \
       '.samples += [{sample_id: $s, pipeline_id: $pid, pipeline_name: $name,
                       output_dir: $out, spec_path: $sp, report_path: $r,
                       status: "SUBMITTED"}]' \
       "$BATCH_STATE_FILE" > "${BATCH_STATE_FILE}.tmp" && mv "${BATCH_STATE_FILE}.tmp" "$BATCH_STATE_FILE"
    echo "[fkit/batch]   submitted ${sid}: pipelineId=${pid}  outputDir=/output/${outdir}/"
  done < <(jq -r '.samples | keys | sort | .[]' "$SAMPLES_JSON")

  echo ""
  echo "[fkit/batch] submission summary: total=${n_total} ok=${n_ok} failed=${n_fail}"
  write_state "SUBMITTED" "" \
    "{\"batch\": true, \"flow_version_id\": \"$vid\", \"batch_state\": \"$BATCH_STATE_FILE\", \"total\": $n_total, \"submitted\": $n_ok, \"failed_submit\": $n_fail, \"data_dir\": \"$DATA_DIR\"}"
  if [ "$n_fail" -gt 0 ]; then
    echo "[fkit/batch] WARNING: ${n_fail} sample(s) failed to submit. Inspect" >&2
    echo "  ${BATCH_STATE_FILE} and per-sample bindings_report_*.json." >&2
  fi
  echo "Poll with:  bash skills/upstream-pipeline-fkit/scripts/run.sh poll ${JOB_ID}"
}

phase_poll_batch() {
  [ -f "$BATCH_STATE_FILE" ] || { echo "poll: ${BATCH_STATE_FILE} not found; submit first" >&2; exit 1; }
  local ts; ts="$(date +%Y%m%d-%H%M%S)"
  local poll_dir="${REPRO}/poll_${ts}"
  mkdir -p "$poll_dir"

  # Refresh status for every submitted sample.
  local tmp; tmp="$(mktemp)"
  cp "$BATCH_STATE_FILE" "$tmp"
  local i=0
  while IFS=$'\t' read -r sid pid prev_status; do
    [ -n "$pid" ] || continue
    case "$prev_status" in BUILD_FAILED|SUBMIT_FAILED) continue ;; esac
    local out="${poll_dir}/${sid}.json"
    if ! "$FKIT" pipeline get "$pid" --json > "$out" 2>>"${REPRO}/poll_errors.log"; then
      echo "[fkit/batch] poll failed for ${sid} (pid=${pid})" >&2
      continue
    fi
    local code
    code="$(jq -r '.status' "$out")"
    jq --arg s "$sid" --arg c "$code" --arg lp "$out" \
       '(.samples[] | select(.sample_id == $s)) |= (. + {status_code: ($c|tonumber), last_poll: $lp})' \
       "$tmp" > "${tmp}.next" && mv "${tmp}.next" "$tmp"
    i=$((i + 1))
  done < <(jq -r '.samples[] | [.sample_id, (.pipeline_id // ""), (.status // "")] | @tsv' "$BATCH_STATE_FILE")

  mv "$tmp" "$BATCH_STATE_FILE"

  # Aggregate status. Worst-of:
  #   -1 (FAIL)  >  -2/-3 (STOP/STOPPING)  >  1/0 (RUNNING/WAITING)  >  2 (SUCCESS)
  # build/submit failures are treated as -1.
  AGG_STATE="$BATCH_STATE_FILE" python3 - <<'PY'
import json, os, sys
state = json.load(open(os.environ["AGG_STATE"]))
codes = []
for s in state["samples"]:
    if s.get("status") in ("BUILD_FAILED", "SUBMIT_FAILED"):
        codes.append(-1)
    elif "status_code" in s:
        codes.append(int(s["status_code"]))
total = len(state["samples"])
def lab(c):
    return {-3:"STOPPING",-2:"STOP",-1:"FAIL",0:"WAITING",1:"RUNNING",2:"SUCCESS"}.get(c, f"?{c}")
if any(c == -1 for c in codes):
    agg = -1
elif any(c in (-2, -3) for c in codes):
    agg = -2 if -2 in codes else -3
elif any(c in (0, 1) for c in codes):
    agg = 1
elif codes and all(c == 2 for c in codes):
    agg = 2
else:
    agg = 1
buckets = {-1:0,-2:0,-3:0,0:0,1:0,2:0}
for c in codes: buckets[c] = buckets.get(c, 0) + 1
print(f"BATCH POLL: total={total}  "
      f"success={buckets.get(2,0)}  running={buckets.get(1,0)}  "
      f"waiting={buckets.get(0,0)}  failed={buckets.get(-1,0)}  "
      f"stopped={buckets.get(-2,0)+buckets.get(-3,0)}")
for s in state["samples"]:
    sid = s["sample_id"]
    if s.get("status") in ("BUILD_FAILED", "SUBMIT_FAILED"):
        print(f"  ✗ {sid:<24}  {s['status']}")
    elif "status_code" in s:
        c = int(s["status_code"])
        mark = "✓" if c == 2 else ("✗" if c == -1 else "▶" if c == 1 else "…")
        print(f"  {mark} {sid:<24}  {lab(c)}")
print(f"STATUS={agg}")
PY

  local agg_code
  agg_code="$(AGG_STATE="$BATCH_STATE_FILE" python3 -c "
import json, os
state = json.load(open(os.environ['AGG_STATE']))
codes = []
for s in state['samples']:
    if s.get('status') in ('BUILD_FAILED','SUBMIT_FAILED'):
        codes.append(-1)
    elif 'status_code' in s:
        codes.append(int(s['status_code']))
if any(c == -1 for c in codes): print(-1)
elif any(c in (-2,-3) for c in codes): print(-2 if -2 in codes else -3)
elif any(c in (0,1) for c in codes): print(1)
elif codes and all(c == 2 for c in codes): print(2)
else: print(1)
")"
  local lab
  case "$agg_code" in
    -3) lab=STOPPING ;; -2) lab=STOP ;; -1) lab=FAIL ;;
     0) lab=WAITING ;;   1) lab=RUNNING ;; 2) lab=SUCCESS ;;
     *) lab=UNKNOWN ;;
  esac
  write_state "$lab" "$agg_code" "{\"batch\": true, \"last_poll_dir\": \"$poll_dir\"}"
}

phase_finalize_batch() {
  [ -f "$BATCH_STATE_FILE" ] || { echo "finalize: ${BATCH_STATE_FILE} not found" >&2; exit 1; }
  if [ -z "$PIPELINE" ]; then
    PIPELINE="$(jq -r '.pipeline // ""' "$BATCH_STATE_FILE")"
    [ -n "$PIPELINE" ] || { echo "finalize: pipeline name missing on cli AND in .batch_state.json" >&2; exit 2; }
  fi

  REQ_STATE="$BATCH_STATE_FILE" python3 - <<'PY' || exit 1
import json, os, sys
state = json.load(open(os.environ["REQ_STATE"]))
bad = []
for s in state["samples"]:
    if s.get("status") in ("BUILD_FAILED", "SUBMIT_FAILED"):
        bad.append(f"{s['sample_id']} ({s['status']})")
    elif s.get("status_code", 1) != 2:
        bad.append(f"{s['sample_id']} (code={s.get('status_code','?')})")
if bad:
    print("finalize: refusing to materialize — these sample(s) are not in SUCCESS:", file=sys.stderr)
    for b in bad: print(f"  - {b}", file=sys.stderr)
    print("Run `poll` again and only finalize once every sample reaches STATUS=2.", file=sys.stderr)
    sys.exit(1)
PY

  # Resumable & idempotent — DO NOT wipe $SCRATCH or prior manifest fragments.
  # The batch loop downloads N samples sequentially (each `fkit download` takes
  # ~30–90 s, so 20 samples can run 15–30 min); a process TTL / OOM kill must
  # not throw that work away. Each sample keeps a per-sample `.dl_done` marker
  # and writes its manifest fragment on materialize; a fully-finalized sample
  # (both present) is skipped on re-run. If killed mid-batch, just call
  # `finalize` again — only the still-missing samples are fetched.
  mkdir -p "$SCRATCH" "${STAGE}/.manifest_fragments"

  local n_total=0 n_skip=0 n_done=0 n_fail=0
  while IFS=$'\t' read -r sid outdir; do
    [ -n "$sid" ] || continue
    n_total=$((n_total + 1))
    local target="${SCRATCH}/${sid}"
    local frag="${STAGE}/.manifest_fragments/${sid}.json"

    if [ -f "$frag" ] && [ -f "${target}/.dl_done" ]; then
      echo "[fkit/batch] ✓ ${sid} already finalized — skip"
      n_skip=$((n_skip + 1))
      continue
    fi

    if [ -f "${target}/.dl_done" ]; then
      echo "[fkit/batch] ${sid} already downloaded — re-materializing only"
    else
      # Per-sample selective download. We do NOT `rm -rf "$target"` here so a
      # previous partial finalize (e.g. the bulk-pull blocker from 2026-06-09
      # that left a half-populated openclaw-<job-id>-<sid>/ tree under $target)
      # can be re-used: any file that already lines up under the expected
      # local path with non-zero size is skipped, and only the missing
      # output_to_stage matches are pulled.
      mkdir -p "$target"
      echo "[fkit/batch] selective download ${outdir} → ${target}"
      if ! python3 "${SKILL_SCRIPTS_DIR}/selective_download.py" \
              --pipelines     "${ROOT_DIR}/registry/pipelines.yaml" \
              --pipeline      "$PIPELINE" \
              --remote-outdir "$outdir" \
              --local-root    "$target" \
              --fkit          "$FKIT" \
              --summary       "${REPRO}/selective_download_${sid}.json"; then
        echo "[fkit/batch] ✗ selective download failed for ${sid} — will retry on next finalize run" >&2
        n_fail=$((n_fail + 1))
        continue
      fi
      date -u +%FT%TZ > "${target}/.dl_done"
    fi

    echo "[stage/batch] materializing ${sid}"
    python3 "${SKILL_SCRIPTS_DIR}/materialize_stage.py" \
        --job-id    "$JOB_ID" \
        --pipeline  "$PIPELINE" \
        --pipelines "${ROOT_DIR}/registry/pipelines.yaml" \
        --src       "$target" \
        --stage     "$STAGE" \
        --sample-id "$sid"
    n_done=$((n_done + 1))
  done < <(jq -r '.samples[] | [.sample_id, .output_dir] | @tsv' "$BATCH_STATE_FILE")

  echo "[fkit/batch] pass complete: total=${n_total} new=${n_done} skipped=${n_skip} failed=${n_fail}"
  if [ "${n_fail:-0}" -gt 0 ]; then
    write_state "FINALIZE_PARTIAL" "" \
      "{\"batch\": true, \"total\": $n_total, \"materialized\": $n_done, \"skipped\": $n_skip, \"failed\": $n_fail}"
    echo "[fkit/batch] ${n_fail} sample(s) still missing — re-run finalize to resume" >&2
    echo "             (completed samples are skipped; nothing is re-downloaded)." >&2
    exit 1
  fi

  MERGE_STAGE="$STAGE" MERGE_JOB="$JOB_ID" MERGE_PIPE="$PIPELINE" \
  MERGE_BATCH="$BATCH_STATE_FILE" python3 - <<'PY'
import json, os
stage = os.environ["MERGE_STAGE"]
frag_dir = os.path.join(stage, ".manifest_fragments")
manifest = {"job_id": os.environ["MERGE_JOB"],
            "pipeline": os.environ["MERGE_PIPE"],
            "mode": "batch", "samples": []}
cats = set()
frags = sorted(os.listdir(frag_dir)) if os.path.isdir(frag_dir) else []
loaded = []
for fn in frags:
    if not fn.endswith(".json"): continue
    data = json.load(open(os.path.join(frag_dir, fn)))
    loaded.append(data)
    cats.update(data.get("categories", {}).keys())
manifest["samples"] = sorted(d["sample_id"] for d in loaded)
for cat in sorted(cats):
    per_sample = {}
    for d in loaded:
        files = d.get("categories", {}).get(cat) or []
        if files:
            per_sample[d["sample_id"]] = files[0] if len(files) == 1 else files
    manifest[cat] = per_sample
batch = json.load(open(os.environ["MERGE_BATCH"]))
manifest["flowhub"] = [
    {"sample_id": s["sample_id"],
     "pipeline_id": s.get("pipeline_id"),
     "output_dir":  s.get("output_dir")}
    for s in batch["samples"] if s.get("pipeline_id")
]
open(os.path.join(stage, "manifest.json"), "w").write(
    json.dumps(manifest, indent=2, ensure_ascii=False))
print(f"merged manifest: {len(loaded)} sample(s), {len(cats)} categor{'ies' if len(cats)!=1 else 'y'}")
PY

  date -u +%FT%TZ > "$DONE_MARKER"
  write_state "FINALIZED" "2" \
    "{\"batch\": true, \"stage\": \"${STAGE}\", \"manifest\": \"${STAGE}/manifest.json\"}"
  echo "[fkit/batch] finalize complete — merged manifest written, .fkit_done stamped"
  echo "Stage:    ${STAGE}/"
  echo "Manifest: ${STAGE}/manifest.json"
  echo "Marker:   ${DONE_MARKER}"
}

case "$PHASE" in
  plan)
      if [ -n "$PIPELINE" ] && is_batch_pipeline; then phase_plan_batch
      else                                              phase_plan
      fi ;;
  submit)
      if [ -n "$PIPELINE" ] && is_batch_pipeline; then phase_submit_batch
      else                                              phase_submit
      fi ;;
  poll)
      if [ -f "$BATCH_STATE_FILE" ]; then              phase_poll_batch
      else                                              phase_poll
      fi ;;
  finalize)
      if [ -f "$BATCH_STATE_FILE" ]; then              phase_finalize_batch
      else                                              phase_finalize
      fi ;;
  *) echo "Usage: run.sh <plan|submit|poll|finalize> <job-id> [pipeline-name]" >&2; exit 2 ;;
esac
