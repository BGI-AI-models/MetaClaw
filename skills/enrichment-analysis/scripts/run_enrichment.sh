#!/usr/bin/env bash
# scripts/run_enrichment.sh
# Wrapper for the enrichment analysis pipeline.
# Called inside the Docker container by the orchestrator.
set -euo pipefail

THREADS="${THREADS:-8}"
KRAKEN2_DB="${KRAKEN2_DB:-/db/kraken2/standard}"
HUMANN_DB="${HUMANN_DB:-/db/humann/chocophlan}"

echo "=== Enrichment Analysis ==="
echo "Threads: ${THREADS}"
echo "Kraken2 DB: ${KRAKEN2_DB}"
echo "HUMAnN DB: ${HUMANN_DB}"

# ── Discover samples ─────────────────────────────────────────
SAMPLES=()
for f in /data/*_R1.fastq.gz /data/*_R1.fq.gz; do
  [ -f "$f" ] || continue
  SAMPLE=$(basename "$f" | sed -E 's/_(R1|1)\.(fastq|fq)\.gz$//')
  SAMPLES+=("$SAMPLE")
done

if [ ${#SAMPLES[@]} -eq 0 ]; then
  echo "ERROR: No paired-end FASTQ files found in /data/"
  exit 1
fi

echo "Found ${#SAMPLES[@]} sample(s): ${SAMPLES[*]}"

mkdir -p /output/qc /output/taxonomy /output/functional

# ── Process each sample ──────────────────────────────────────
for SAMPLE in "${SAMPLES[@]}"; do
  echo ""
  echo "--- Processing: ${SAMPLE} ---"

  # QC
  R1=$(ls /data/${SAMPLE}*R1*.f*q.gz 2>/dev/null | head -1)
  R2=$(echo "$R1" | sed 's/R1/R2/')

  fastp \
    -i "$R1" -I "$R2" \
    -o "/output/qc/${SAMPLE}_R1.clean.fq.gz" \
    -O "/output/qc/${SAMPLE}_R2.clean.fq.gz" \
    -h "/output/qc/${SAMPLE}_fastp.html" \
    -j "/output/qc/${SAMPLE}_fastp.json" \
    --thread "$THREADS" \
    --qualified_quality_phred 20 \
    --length_required 50

  # Taxonomy
  kraken2 \
    --db "$KRAKEN2_DB" --paired \
    "/output/qc/${SAMPLE}_R1.clean.fq.gz" \
    "/output/qc/${SAMPLE}_R2.clean.fq.gz" \
    --output "/output/taxonomy/${SAMPLE}_kraken2.out" \
    --report "/output/taxonomy/${SAMPLE}_kraken2.report" \
    --threads "$THREADS" --confidence 0.2

  bracken -d "$KRAKEN2_DB" \
    -i "/output/taxonomy/${SAMPLE}_kraken2.report" \
    -o "/output/taxonomy/${SAMPLE}_bracken.tsv" \
    -r 150 -l S

  # Functional profiling
  cat "/output/qc/${SAMPLE}_R1.clean.fq.gz" \
      "/output/qc/${SAMPLE}_R2.clean.fq.gz" \
    > "/output/qc/${SAMPLE}_merged.fq.gz"

  humann \
    --input "/output/qc/${SAMPLE}_merged.fq.gz" \
    --output "/output/functional/${SAMPLE}_humann/" \
    --threads "$THREADS" \
    --nucleotide-database "$HUMANN_DB"

  rm -f "/output/qc/${SAMPLE}_merged.fq.gz"
done

# ── Tool versions for reproducibility ────────────────────────
python3 -c "
import json, subprocess, datetime

def v(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode().strip()
    except:
        return 'unknown'

meta = {
    'skill': 'enrichment-analysis',
    'samples': '${SAMPLES[*]}'.split(),
    'tools': {
        'fastp': v('fastp --version 2>&1'),
        'kraken2': v('kraken2 --version 2>&1 | head -1'),
        'bracken': v('bracken --version 2>&1 | head -1'),
        'humann': v('humann --version 2>&1'),
    },
    'parameters': {
        'threads': ${THREADS},
        'kraken2_db': '${KRAKEN2_DB}',
        'humann_db': '${HUMANN_DB}',
    },
    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
}
with open('/reproducibility/enrichment_meta.json', 'w') as f:
    json.dump(meta, f, indent=2)
"

echo ""
echo "=== Enrichment analysis complete ==="