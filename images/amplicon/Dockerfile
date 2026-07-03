# images/amplicon/Dockerfile
#
# openclaw/amplicon:1.0.0 — ASV-based 16S/ITS amplicon analysis image.
# Hosts: microbiome-amplicon-processing, microbiome-taxonomy-assignment,
#        microbiome-functional-prediction, microbiome-qiime2-workflow.
#
# Base: official QIIME2 amplicon distribution (already ships QIIME2 plugins
# for DADA2, classify-sklearn, phylogeny, diversity, plus a working
# Bioconductor R stack with dada2 / Biostrings / phyloseq, plus scikit-bio,
# scikit-learn, biopython, cutadapt). We only layer on what QIIME2 omits:
#   • PICRUSt2 (own conda env to avoid dep clashes with QIIME2 pins)
#   • A few extra R packages the skills request (DECIPHER, phangorn, picante)
#
# Build:
#   docker build -t openclaw/amplicon:1.0.0 images/amplicon/
#
# Reference DBs (SILVA / GTDB / UNITE / PICRUSt2 default ref) are NOT baked
# in — mount them at runtime per registry/pipelines.yaml `runtime.mounts`.
FROM quay.io/qiime2/amplicon:2024.10

# Tsinghua mirror for pip — match openclaw/downstream Dockerfile convention
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 300 && \
    pip config set global.retries 10

# ── PICRUSt2 in its own conda env ──────────────────────────────────────────
# Skills invoke it via:  conda run -n picrust2 picrust2_pipeline.py ...
# Pinning picrust2 2.5.2 (stable, KO + EC + MetaCyc support).
RUN conda create -n picrust2 -c bioconda -c conda-forge -y \
      python=3.9 picrust2=2.5.2 && \
    conda clean -afy

# ── Extra R packages not bundled in the QIIME2 amplicon image ─────────────
# QIIME2 amplicon image already provides R + dada2 + Biostrings + phyloseq
# (via q2-dada2 / q2-phylogeny). We add the remaining packages that
# microbiome-amplicon-processing / -diversity-analysis / -taxonomy-assignment
# import directly from R scripts.
RUN R -e 'if (!requireNamespace("BiocManager", quietly=TRUE)) install.packages("BiocManager", repos="https://cloud.r-project.org")' && \
    R -e 'BiocManager::install(c("DECIPHER"), ask=FALSE, update=FALSE)' && \
    R -e 'install.packages(c("phangorn", "picante"), repos="https://cloud.r-project.org")'

# ── Extra Python helpers the skills' requirements.txt files list ──────────
# (pyyaml + pandas already ship with QIIME2; biopython is bundled too.)
# This line is intentionally minimal — anything else needed by a future
# skill should be added here AND a tag bump done (1.0.0 → 1.1.0).
RUN pip install --no-cache-dir \
      pyyaml==6.0.1 \
      pandas==2.2.2

# ── BioLine conventions ──────────────────────────────────────────────────
# Skills read /job/stage (ro), write /job/analysis + /job/reproducibility.
# /pipeline/scripts/ is mounted ro by gateway/prepare_downstream.sh with the
# reference_<skill>.py wrappers for the 4 amplicon skills.
RUN mkdir -p /job /pipeline
WORKDIR /job

# Default entrypoint stays as the QIIME2 base image's (a login shell that
# auto-activates the QIIME2 conda env). Skills that need PICRUSt2 must
# wrap their call with `conda run -n picrust2 ...`.
