#!/usr/bin/env bash
# gateway/recover_finalize.sh — Unblock a finalize that's stuck on a bulk download.
#
# Symptom this fixes (observed 2026-06-09 on metagenomics-full × 20):
#   upstream FlowHub status = SUCCESS
#   .fkit_done MISSING, stage/manifest.json MISSING
#   .fkit_download/ is huge (or partial), trying to grow forever
#
# Root cause: the legacy finalize did `fkit download <remote_outdir> -r`, pulling
# the entire per-sample output tree (host-removed BAMs, cleaned FASTQ, kraken
# intermediates) just to extract the one MetaPhlAn4 profile that output_to_stage
# actually wants. For batch finalize on a cohort, that's tens of GB × N samples.
#
# What this script does:
#   1. Reads `.batch_state.json` (or falls back to single-job mode) to recover
#      the per-sample remote outdirs.
#   2. Clears the bloated `.fkit_download/` content (NOT the parent dir — keeps
#      anything else the user staged manually).
#   3. Invokes the patched `run.sh finalize` which now uses
#      `selective_download.py` under the hood — only the files matching
#      `upstream.output_to_stage` (e.g. `*/metaphlan4/out_dir/*.txt`, which
#      catches `<sid>.profiled_metagenome.txt`) are pulled.
#   4. Lets `materialize_stage.py` populate `stage/<category>/<sid>/` and stamp
#      `.fkit_done` as usual.
#
# Usage:
#   bash gateway/recover_finalize.sh <job-id> [pipeline-name]
#
# Pipeline name is optional — picked up from `.batch_state.json` (`.pipeline`)
# if absent. Required only if you're recovering a single-job (non-batch)
# finalize, where there's no batch state file.
set -euo pipefail

JOB_ID="${1:?usage: recover_finalize.sh <job-id> [pipeline-name]}"
PIPELINE="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
JOBS_ROOT="${OPENCLAW_JOBS_ROOT:-/data/output}"
JOB_DIR="${JOBS_ROOT}/${JOB_ID}"
SCRATCH="${JOB_DIR}/.fkit_download"
STAGE="${JOB_DIR}/stage"
BATCH_STATE="${JOB_DIR}/.batch_state.json"
PIPELINE_ID_FILE="${JOB_DIR}/.pipeline_id"
DONE_MARKER="${JOB_DIR}/.fkit_done"

[ -d "$JOB_DIR" ] || { echo "[recover] job dir not found: $JOB_DIR" >&2; exit 1; }

# Resolve pipeline name from batch state if not given.
if [ -z "$PIPELINE" ] && [ -f "$BATCH_STATE" ]; then
  PIPELINE="$(jq -r '.pipeline // ""' "$BATCH_STATE")"
fi
[ -n "$PIPELINE" ] || { echo "[recover] pipeline name required (no .batch_state.json to infer from)" >&2; exit 2; }

echo "[recover] job=${JOB_ID}  pipeline=${PIPELINE}"
echo "[recover] job_dir=${JOB_DIR}"

# Safety: never run if .fkit_done is already there — finalize already finished,
# we'd needlessly re-download.
if [ -f "$DONE_MARKER" ]; then
  echo "[recover] ${DONE_MARKER} already exists — nothing to recover. Aborting." >&2
  exit 0
fi

# Pre-flight: confirm patched run.sh is in place.
if ! grep -q 'selective_download.py' "${ROOT_DIR}/skills/upstream-pipeline-fkit/scripts/run.sh"; then
  echo "[recover] WARNING: run.sh does not look patched (no selective_download.py reference)." >&2
  echo "[recover] Pull the latest skills/upstream-pipeline-fkit/ first, then re-run." >&2
  exit 3
fi

# Step 1: clear bloated bulk download (keep the directory itself + any per-sample
# `.dl_done` markers so the selective re-pull can skip files that *did* land
# under the right relpath during the broken bulk attempt).
if [ -d "$SCRATCH" ]; then
  echo "[recover] clearing bulk .fkit_download/ contents at $SCRATCH"
  # Preserve files that already match the wanted layout (cheap heuristic:
  # anything ≤ 50 MB is plausibly a profile/QC text; FASTQ/BAM are large).
  # The selective downloader will skip-if-exists anyway, so wiping everything
  # is the safe default. Comment this out and run by hand if you want to
  # cherry-pick salvageable bytes.
  find "$SCRATCH" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

# Step 2: invoke the patched finalize.
echo "[recover] calling patched finalize"
bash "${ROOT_DIR}/skills/upstream-pipeline-fkit/scripts/run.sh" finalize "$JOB_ID" "$PIPELINE"

# Step 3: sanity check.
if [ -f "$DONE_MARKER" ] && [ -f "${STAGE}/manifest.json" ]; then
  echo "[recover] ✓ recovered — .fkit_done and stage/manifest.json present"
  echo "[recover]   next: bash gateway/prepare_downstream.sh ${JOB_ID} ${PIPELINE}"
else
  echo "[recover] ✗ finalize completed but ${DONE_MARKER} or stage/manifest.json is missing" >&2
  echo "[recover]   check selective_download_<sid>.json under reproducibility/ to see what fkit ls returned" >&2
  exit 4
fi
