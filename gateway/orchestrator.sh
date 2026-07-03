#!/usr/bin/env bash
# gateway/orchestrator.sh
#
# Thin coordinator. The gateway scaffolds the job directory and writes
# reproducibility metadata; it deliberately does NOT encode FlowHub / fkit
# conventions. All upstream lifecycle (flow resolution, fileId discovery via
# `fkit ls`, spec, pipeline create, poll, download, materialize → stage/)
# lives in the upstream-pipeline-fkit skill at
#   skills/upstream-pipeline-fkit/SKILL.md
#   skills/upstream-pipeline-fkit/scripts/run.sh
#
# Input handling depends on whether the pipeline has an upstream block:
#
#   * upstream PRESENT — DATA_DIR must be a **FlowHub absolute path**.
#     Inputs are consumed in place on FlowHub; the upstream skill discovers
#     fileIds with `fkit ls`. Non-sequencing files (metadata, sample sheets)
#     are pulled into stage/ via `fkit download` so downstream skills can
#     read them. There is no local copy of FASTQ.
#
#   * upstream ABSENT (downstream-only) — DATA_DIR can be EITHER:
#       - a LOCAL absolute path (default convention: `/data/<name>/`) →
#         orchestrator hardlinks (cp -al, falling back to copy) into
#         /data/output/<id>/stage/. No FlowHub round-trip needed.
#       - a FlowHub absolute path → orchestrator `fkit download`s the whole
#         directory into /data/output/<id>/stage/.
#     The kind is auto-detected by gateway.sh (passed in via
#     OPENCLAW_DATA_KIND) and recorded in /data/output/<id>/.input_source_kind.
#
# File sharing  : upstream writes to  /data/output/<id>/stage/<category>/  and emits
#                 /data/output/<id>/stage/manifest.json (read-only by downstream).
# Status sharing: upstream writes    /data/output/<id>/.pipeline_id (after submit)
#                                    /data/output/<id>/upstream_state.json (after poll)
#                                    /data/output/<id>/.fkit_done (after finalize)
#                 Downstream only starts when .fkit_done is present.
#
# Usage: orchestrator.sh <pipeline> <job-id> <data-dir> [overrides.yaml] [skills-csv]
#
# Modes:
#   - With upstream:  prep → hand off to the upstream skill → exit. The agent
#                     then follows SKILL.md to plan / submit / poll / finalize.
#                     When `OPENCLAW_AUTO_SUBMIT=1`, the orchestrator
#                     additionally invokes the skill's `run.sh submit` for
#                     one-shot CI use.
#   - Without upstream: prep → fetch/copy DATA_DIR into stage/ →
#                       prepare_downstream.sh [→ run_downstream.sh if
#                       --skills given].
set -euo pipefail

PIPELINE="$1"
JOB_ID="$2"
DATA_DIR="$3"           # Local OR FlowHub absolute path (see file header).
OVERRIDE_FILE="${4:-}"
SKILLS_OVERRIDE="${5:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
export OPENCLAW_JOBS_ROOT="$JOBS_ROOT"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
UPSTREAM_SKILL_DIR="${ROOT_DIR}/skills/upstream-pipeline-fkit"
FKIT="${FKIT:-fkit}"
mkdir -p "$JOBS_ROOT"

case "$DATA_DIR" in
  /*) ;;
  *)  echo "orchestrator: <data-dir> must be an absolute path. Got: ${DATA_DIR}" >&2
      exit 2 ;;
esac

mkdir -p "${JOB_DIR}/stage" "${JOB_DIR}/analysis" \
         "${JOB_DIR}/reproducibility/logs" \
         "${JOB_DIR}/reproducibility/generated_scripts" \
         "${JOB_DIR}/reproducibility/Dockerfile.pinned"

HAS_UPSTREAM=$(python3 -c "
import yaml
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
print('1' if p.get('upstream') else '0')
")

IS_BATCH=$(python3 -c "
import yaml
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
print('1' if (((p.get('upstream') or {}).get('batch') or {}).get('mode') == 'per_sample') else '0')
")

# Resolve DATA_KIND. Trust the env var from gateway.sh if present; otherwise
# detect locally (orchestrator can be invoked directly by reproducer scripts).
DATA_KIND="${OPENCLAW_DATA_KIND:-}"
if [ -z "$DATA_KIND" ]; then
  if [ "$HAS_UPSTREAM" = "1" ]; then
    DATA_KIND="flowhub"
  elif [ -d "$DATA_DIR" ]; then
    DATA_KIND="local"
  elif command -v "$FKIT" >/dev/null 2>&1 \
       && "$FKIT" ls "$DATA_DIR" --limit 1 --json >/dev/null 2>&1; then
    DATA_KIND="flowhub"
  else
    echo "orchestrator: cannot resolve <data-dir> as either a local directory or a FlowHub path: ${DATA_DIR}" >&2
    exit 1
  fi
fi

# Hard rule: upstream-bearing pipelines require FlowHub-resident inputs.
if [ "$HAS_UPSTREAM" = "1" ] && [ "$DATA_KIND" != "flowhub" ]; then
  echo "orchestrator: pipeline '${PIPELINE}' has an upstream FlowHub flow — DATA_KIND must be flowhub, got '${DATA_KIND}'." >&2
  exit 1
fi

# 1) Record the DATA_DIR + kind. The upstream skill reads .input_source to
#    drive `fkit ls`. The reproducer in run.sh can replay against the same
#    source.
echo "$DATA_DIR" > "${JOB_DIR}/.input_source"
echo "$DATA_KIND" > "${JOB_DIR}/.input_source_kind"

# 2) Params override (consumed by the skill's build_spec.py and downstream scripts).
if [ -n "$OVERRIDE_FILE" ] && [ -f "$OVERRIDE_FILE" ]; then
  cp "$OVERRIDE_FILE" "${JOB_DIR}/reproducibility/params_override.yaml"
else
  echo "# no overrides" > "${JOB_DIR}/reproducibility/params_override.yaml"
fi

# 3) Pipeline manifest (the resolved pipeline spec, for audit).
DATA_SOURCE="$DATA_DIR" DATA_KIND="$DATA_KIND" python3 -c "
import yaml, os
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
meta = {'pipeline': '${PIPELINE}', 'job_id': '${JOB_ID}',
        'spec': p, 'data_source': os.environ['DATA_SOURCE'],
        'data_source_kind': os.environ['DATA_KIND']}
open('${JOB_DIR}/reproducibility/pipeline.yaml','w').write(yaml.safe_dump(meta))
"

# 4) Pin downstream Dockerfiles for reproducibility (upstream lives on FlowHub —
#    no local Dockerfiles to pin for it).
python3 -c "
import yaml, shutil, os
p = yaml.safe_load(open('${ROOT_DIR}/registry/pipelines.yaml'))['pipelines']['${PIPELINE}']
dst = '${JOB_DIR}/reproducibility/Dockerfile.pinned'
os.makedirs(dst, exist_ok=True)
for img in ('downstream', 'downstream-dl', 'base'):
    src = '${ROOT_DIR}/images/' + img + '/Dockerfile'
    if os.path.exists(src):
        shutil.copy(src, os.path.join(dst, img + '.Dockerfile'))
"

# Pre-stage non-sequencing files from a FlowHub DATA_DIR into stage/ so
# downstream skills can read metadata/sample sheets at /job/stage/. Only
# small files are pulled (skip FASTQ/BAM/CRAM/SRA — upstream itself will
# process those). Best-effort: a failure here just means downstream may
# need to fetch metadata itself.
prestage_flowhub_metadata() {
  local listing="${JOB_DIR}/reproducibility/.prestage_ls.json"
  if ! "$FKIT" ls "$DATA_DIR" --limit 1000 --json \
        > "$listing" 2>"${JOB_DIR}/reproducibility/.prestage_err.log"; then
    echo "orchestrator: 'fkit ls ${DATA_DIR}' failed during prestage; skipping metadata fetch." >&2
    sed 's/^/    /' "${JOB_DIR}/reproducibility/.prestage_err.log" >&2 || true
    return 0
  fi

  python3 - "$listing" "$DATA_DIR" "$JOB_DIR/stage" "$FKIT" <<'PY'
import json, os, re, subprocess, sys
listing_path, data_dir, stage_dir, fkit = sys.argv[1:5]
SEQ_RE = re.compile(r"\.(?:fastq|fq|bam|cram|sra)(?:\.(?:gz|bz2|xz))?$", re.IGNORECASE)
try:
    payload = json.load(open(listing_path))
except Exception as e:
    print(f"orchestrator: cannot parse FlowHub listing ({e}); skipping prestage.",
          file=sys.stderr); sys.exit(0)
if isinstance(payload, dict) and "data" in payload:
    payload = payload["data"]
items = payload if isinstance(payload, list) else \
        (payload.get("files") or payload.get("items") or []) if isinstance(payload, dict) else []
fetched = 0
for it in items:
    name = (it.get("name") or it.get("fileName") or "").strip().lstrip("/")
    if not name or "/" in name:           # only top-level
        continue
    kind = str(it.get("type") or it.get("kind") or it.get("fileType") or "").lower()
    if kind in {"dir","folder","directory"} or it.get("isFolder") is True:
        continue                          # subdirs = per-sample groups, leave to upstream
    if SEQ_RE.search(name):
        continue                          # sequencing files are upstream's job, not downstream's
    remote = data_dir.rstrip("/") + "/" + name
    try:
        subprocess.run([fkit, "download", "-s", remote, "-t", stage_dir],
                       check=True, capture_output=True)
        fetched += 1
    except subprocess.CalledProcessError as e:
        print(f"orchestrator: failed to prestage {name} from FlowHub "
              f"(rc={e.returncode}); downstream may be missing it.",
              file=sys.stderr)
print(f"orchestrator: prestaged {fetched} non-sequencing file(s) from FlowHub → stage/")
PY
}

# ════════ Upstream — handed off to the skill ════════
if [ "$HAS_UPSTREAM" = "1" ]; then
  prestage_flowhub_metadata || true

  echo "═══ Upstream phase → handing off to upstream-pipeline-fkit skill ═══"
  echo "  Skill:        ${UPSTREAM_SKILL_DIR}/SKILL.md"
  echo "  Driver:       ${UPSTREAM_SKILL_DIR}/scripts/run.sh"
  echo "  Job dir:      ${JOB_DIR}"
  echo "  Input source: ${DATA_DIR}  (FlowHub-resident; no local copy)"
  echo "  Stage target: ${JOB_DIR}/stage/      (downstream input; metadata pre-staged from FlowHub)"
  echo "  Status:       ${JOB_DIR}/.pipeline_id  ${JOB_DIR}/upstream_state.json  ${JOB_DIR}/.fkit_done"
  echo ""
  if [ "$IS_BATCH" = "1" ]; then
    echo "  Mode:         BATCH (per-sample fan-out)"
    echo "                Each sample becomes one FlowHub pipeline named"
    echo "                openclaw-${JOB_ID}-<sample-id>; outputs land at"
    echo "                /output/openclaw-${JOB_ID}-<sample-id>/ on FlowHub."
    echo "                State across samples: ${JOB_DIR}/.batch_state.json"
  else
    echo "  Mode:         SINGLE-JOB"
  fi
  echo ""
  echo "Agent: follow SKILL.md, then invoke phase-by-phase:"
  echo "  bash skills/upstream-pipeline-fkit/scripts/run.sh plan     ${JOB_ID} ${PIPELINE}   # DRY RUN — show bindings (and BATCH PLAN if batch) to user FIRST"
  echo "  bash skills/upstream-pipeline-fkit/scripts/run.sh submit   ${JOB_ID} ${PIPELINE}   # only after user confirms bindings"
  echo "  bash skills/upstream-pipeline-fkit/scripts/run.sh poll     ${JOB_ID}        # every 10 min; batch aggregates per-sample STATUS into one code"
  echo "  bash skills/upstream-pipeline-fkit/scripts/run.sh finalize ${JOB_ID} ${PIPELINE}   # batch: refused until ALL samples reach SUCCESS"
  echo "Downstream only starts once ${JOB_DIR}/.fkit_done is present."

  if [ "${OPENCLAW_AUTO_SUBMIT:-0}" = "1" ]; then
    echo ""
    echo "[OPENCLAW_AUTO_SUBMIT=1] auto-invoking skill's submit phase…"
    bash "${UPSTREAM_SKILL_DIR}/scripts/run.sh" submit "$JOB_ID" "$PIPELINE"
  fi
  exit 0
fi

# ════════ No upstream — populate stage/ from DATA_DIR ════════
echo "═══ No upstream steps for downstream-only pipeline ═══"

case "$DATA_KIND" in
  local)
    [ -d "$DATA_DIR" ] || { echo "orchestrator: local DATA_DIR not a directory: ${DATA_DIR}" >&2; exit 1; }
    echo "[stage] copying local ${DATA_DIR} → ${JOB_DIR}/stage/"
    # Hardlink when possible (zero copy, instant) and fall back to a real copy
    # when DATA_DIR sits on a different filesystem than /data/output/.
    cp -al "${DATA_DIR}/." "${JOB_DIR}/stage/" 2>/dev/null || \
      cp -a  "${DATA_DIR}/." "${JOB_DIR}/stage/"
    ;;
  flowhub)
    echo "[fetch] downloading FlowHub DATA_DIR ${DATA_DIR} → ${JOB_DIR}/stage/"
    # Downstream-only pipelines treat the FlowHub DATA_DIR as a directory of
    # precomputed analysis inputs (abundance tables, metadata, …). Pull the
    # whole thing before bringing the downstream container up.
    "$FKIT" download -s "$DATA_DIR" -t "${JOB_DIR}/stage/"
    ;;
  *)
    echo "orchestrator: unknown DATA_KIND='${DATA_KIND}'" >&2; exit 1 ;;
esac

# Mark stage as ready so the rest of the toolchain (prepare_downstream,
# heartbeat checks) treats it uniformly.
date -u +%FT%TZ > "${JOB_DIR}/.fkit_done"

# ════════ Downstream — two-phase ════════
echo "═══ Downstream prepare ═══"
bash "${SCRIPT_DIR}/prepare_downstream.sh" "$JOB_ID" "$PIPELINE"

if [ -n "$SKILLS_OVERRIDE" ]; then
  echo "═══ Downstream execute (--skills ${SKILLS_OVERRIDE}) ═══"
  bash "${SCRIPT_DIR}/run_downstream.sh" "$JOB_ID" --skills "$SKILLS_OVERRIDE"
else
  echo "Downstream container is up. Customize scripts then run:"
  echo "  bash gateway/run_downstream.sh ${JOB_ID} --skills <skill1,skill2,...>"
fi

# ════════ Reproducibility runner ════════
# Pin the workspace path at job-creation time so replay still works even when
# the job dir sits under /data/output/ (../../../ from there would land at /).
cat > "${JOB_DIR}/reproducibility/run.sh" <<EOF
#!/usr/bin/env bash
# Reproduce job ${JOB_ID}
# Prerequisites:
#   1) For upstream: the FlowHub flow referenced in pipelines.yaml still
#      exists (same fkit_flow_keyword / fkit_flow_version_id) AND the
#      FlowHub DATA_DIR still contains the same input files.
#   2) For downstream-only with a LOCAL DATA_DIR: the same local directory
#      must still exist at the path recorded in .input_source.
#   3) For downstream-only with a FlowHub DATA_DIR: the FlowHub path must
#      still be readable.
#   4) Downstream Docker images rebuilt to match the digests in
#      tool_manifest.json / downstream_manifest.json.
set -euo pipefail
cd "${ROOT_DIR}"
OPENCLAW_JOBS_ROOT="${JOBS_ROOT}" \\
OPENCLAW_AUTO_SUBMIT=1 \\
OPENCLAW_DATA_KIND="$(cat "${JOB_DIR}/.input_source_kind")" \\
bash gateway/orchestrator.sh ${PIPELINE} ${JOB_ID}-replay \\
  "$(cat "${JOB_DIR}/.input_source")" \\
  "\$(dirname "\$0")/params_override.yaml"
EOF
chmod +x "${JOB_DIR}/reproducibility/run.sh"

echo "╔═════════════════════════════════════════════╗"
echo "║ Job ${JOB_ID} complete"
echo "║ Analysis:        ${JOB_DIR}/analysis/"
echo "║ Reproducibility: ${JOB_DIR}/reproducibility/"
echo "╚═════════════════════════════════════════════╝"
