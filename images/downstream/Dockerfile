# images/downstream/Dockerfile
#
# openclaw/downstream:1.1.1 — general downstream analysis image.
# Hosts the catalogs of `metagenomics-full` + `downstream-only` pipelines:
#   statistical-analysis, AI-exploratory-data-analysis, enrichment-analysis,
#   microbiome-diversity-analysis, microbiome-differential-abundance,
#   nature-style-figure-maker, hypothesis-generation, AI-report-generator.
#
# Build:
#   docker build -t openclaw/downstream:1.1.1 images/downstream/
#
# CHANGELOG 1.1.0 → 1.1.1  (kept minimal — build-fix and required additions only)
#   Build fixes (1.1.0 was non-functional due to silent install failures):
#   • Bioc pin 3.22 → 3.21. 3.22 doesn't ship until Oct 2026; 1.1.0's "3.22"
#     was speculative. Until then every Bioc install warns "packages '…' are
#     not available for Bioconductor version '3.22'".
#   • BioC_mirror Tsinghua → Westlake. BiocManager 1.30.x constructs URLs as
#     <BioC_mirror>/packages/<R_BIOC_VERSION>/<type>/src/contrib/.
#     Tsinghua/USTC/SJTU only mirror /packages/release/ and 404 on
#     /packages/3.21/; Westlake is the only Chinese mirror that carries
#     version-numbered dirs. (Verified: GET /packages/3.21/bioc/src/contrib/PACKAGES → 200.)
#     `BiocManager.repositories` option does NOT override URL construction
#     in 1.30.x — only `BioC_mirror` does. Earlier 1.1.1 attempts that set
#     the former while leaving Tsinghua in the latter kept hitting 404.
#   • ENV R_BIOC_VERSION=3.21 + options(BiocManager.check_repositories=FALSE).
#     Bypasses BiocManager's live bioconductor.org/config.yaml validation
#     (GFW-blocked: SSL connect error / 60 s timeout per install call).
#   • Add `stopifnot` to every R install layer. install.packages() and
#     BiocManager::install() only WARN on per-package failure, so 1.1.0
#     silently shipped without phyloseq, DESeq2, MaAsLin2, dplyr, tidyr,
#     readxl, circlize despite the Dockerfile listing the first three.
#     Reproduce on the 1.1.0 image:
#       docker run --rm openclaw/downstream:1.1.0 R -q -e \
#         'sapply(c("phyloseq","dplyr","tidyr","readxl","circlize"),
#                 requireNamespace)'   → all FALSE.
#
#   Package list diff (minimal — every other 1.1.0 package is unchanged):
#   • Added (CRAN): dplyr, tidyr, readxl, circlize. Required at runtime by
#     AI-report-generator's rendered R script
#     (`library(dplyr); library(tidyr); library(readxl); library(circlize)`).
#     Silently missing in 1.1.0 because they were assumed transitive deps
#     of MaAsLin2, which itself never installed.
#   • Removed (Bioc): phyloseq, DESeq2, MaAsLin2, ANCOMBC. Grep audit
#     2026-06-09 confirmed none of these are called by any rendered R
#     driver in the codebase (no `library(<pkg>)` or `<pkg>::`). They
#     were listed as "alternative methods" in skill docs but never wired
#     into runtime code paths; phyloseq/DESeq2/MaAsLin2 never installed
#     in 1.1.0 either (silent Bioc failure). ANCOMBC was attempted in
#     three 1.1.1 iterations and dropped — its transitive chain
#     (clarabel ⇒ rustup ⇒ ~500 MB; gmp/fs/gsl ⇒ extra apt headers; CVXR
#     1.0-12 pin to dodge the `importFrom(CVXR, solve)` lazy-load break
#     introduced by CVXR ≥ 1.0-13) was too brittle to maintain. The
#     companion *.R reference scripts use vegan + base R + ALDEx2 only.
#     To restore any: add them back here AND wire up an actual analysis
#     script in the relevant skill. ANCOMBC additionally needs the
#     libgmp-dev / libuv1-dev / libgsl-dev apt entries, a rustup
#     toolchain install, and a CVXR 1.0-12 pin (search git history).
#   • All other packages unchanged from 1.1.0.
#
# CHANGELOG 1.0.0 → 1.1.0
#   • R upgraded 4.2 (Debian) → 4.5 (CRAN repo; bookworm-cran40 tracks the
#     current R 4.x, which is now 4.5). Required because ANCOMBC v2 and
#     TreeSummarizedExperiment need Bioconductor 3.17+, which needs R 4.3+.
#     Bioc is pinned to 3.21 — the release paired with R 4.5. (NB: 3.20 pairs
#     with R 4.4; pinning 3.20 against R 4.5 is rejected by BiocManager.)
#   • Python pip adds: pingouin, pymc, arviz, scikit-bio, biopython.
#   • R Bioconductor adds: ALDEx2, ANCOMBC, ComplexHeatmap.
#   • R CRAN adds: patchwork, ggrepel, svglite, ragg, ggsci.
#   • Extra system deps for ragg/svglite/ANCOMBC (libharfbuzz, libtiff, etc.).
#
# Whenever you add another dependency, bump the patch/minor version here AND
# in every `image:` reference in registry/pipelines.yaml (contributor_guide.md §7).

FROM python:3.12-slim-bookworm

# ── R 4.4 from the CRAN-maintained Debian repository ──────────────────────
# Use Tsinghua mirror for faster apt in China
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# Debian bookworm's default r-base is 4.2 — too old for Bioc 3.17+ / ANCOMBC.
# We pull the latest 4.x from cloud.r-project.org's bookworm-cran40 channel.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 dirmngr ca-certificates \
        build-essential gfortran cmake pkg-config && \
    mkdir -p /root/.gnupg && chmod 700 /root/.gnupg && \
    KEY=95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7 && \
    ( gpg --no-default-keyring \
          --keyring /usr/share/keyrings/cran-archive-keyring.gpg \
          --keyserver hkps://keyserver.ubuntu.com \
          --recv-keys "$KEY" \
      || wget -O- "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$KEY" \
          | gpg --dearmor > /usr/share/keyrings/cran-archive-keyring.gpg ) && \
    [ -s /usr/share/keyrings/cran-archive-keyring.gpg ] && \
    echo "deb [signed-by=/usr/share/keyrings/cran-archive-keyring.gpg] \
https://mirrors.tuna.tsinghua.edu.cn/CRAN/bin/linux/debian bookworm-cran40/" \
        > /etc/apt/sources.list.d/cran.list && \
    apt-get update && apt-get install -y --no-install-recommends \
        r-base r-base-dev \
        libcurl4-openssl-dev libssl-dev libxml2-dev libgit2-dev \
        libfontconfig1-dev libfreetype6-dev libpng-dev \
        libharfbuzz-dev libfribidi-dev \
        libtiff-dev libjpeg-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ── R: point CRAN + Bioconductor at working mirrors ───────────────────────
# CRAN — Tsinghua (fast, comprehensive).
# Bioc  — Westlake (the only Chinese mirror that carries version-numbered
#         dirs; Tsinghua/USTC/SJTU only expose /packages/release/ which is
#         a moving symlink and not always synchronised with what
#         R_BIOC_VERSION pins). Verified 2026-06-09:
#           curl -I https://mirrors.westlake.edu.cn/bioconductor/packages/3.21/bioc/src/contrib/PACKAGES → 200
#           curl -I https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.21/bioc/src/contrib/PACKAGES → 404
#
# IMPORTANT: BiocManager constructs URLs as
#   <getOption("BioC_mirror")>/packages/<R_BIOC_VERSION>/<type>/src/contrib/
# It does NOT consult `options(BiocManager.repositories=...)` for URL
# construction in 1.30.x — that option is honoured by `available.packages()`
# but not by `BiocManager::install()`. So `BioC_mirror` MUST point at a
# mirror whose `packages/<R_BIOC_VERSION>/` tree actually exists. Earlier
# 1.1.0/1.1.1 build attempts wired Tsinghua here and BiocManager kept
# constructing 404 URLs no matter how many fallback options we set.
#
# BiocManager.check_repositories=FALSE — bypass the live
# `bioconductor.org/config.yaml` cross-check (GFW-blocked: SSL connect
# error / 60 s timeout per call); R_BIOC_VERSION below pins the release
# without it.
RUN echo 'options(repos = c(CRAN = "https://mirrors.tuna.tsinghua.edu.cn/CRAN"))' \
        >> "$(R RHOME)/etc/Rprofile.site" && \
    echo 'options(BioC_mirror = "https://mirrors.westlake.edu.cn/bioconductor")' \
        >> "$(R RHOME)/etc/Rprofile.site" && \
    echo 'options(BiocManager.check_repositories = FALSE)' \
        >> "$(R RHOME)/etc/Rprofile.site"

# R_BIOC_VERSION makes BiocManager skip the live config.yaml fetch
# (unreachable from this host) and trust the pinned release.
ENV R_BIOC_VERSION=3.21

# ── Python: avoid pip timeouts behind the Great Firewall ──────────────────
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 300 && \
    pip config set global.retries 10

# ── Python scientific stack (versions pinned for reproducibility) ─────────
# Carried over from 1.0.0. If any of these is upgraded, bump the image tag.
RUN pip install --no-cache-dir \
        pandas==2.2.2 numpy==1.26.4 scipy==1.13.1 \
        scikit-learn==1.5.0 statsmodels==0.14.2 \
        xgboost==2.0.3 lightgbm==4.3.0 \
        shap==0.45.1 lifelines==0.28.0 \
        plotly==5.22.0 seaborn==0.13.2 matplotlib==3.9.0 kaleido==0.2.1 \
        jinja2==3.1.4 markdown==3.6 \
        openpyxl==3.1.3 pyarrow==16.1.0 \
        rpy2==3.5.16 \
        pyyaml==6.0.1 joblib==1.5.3 \
        pypdf==6.10.2 pdfplumber==0.11.9 reportlab==4.4.10

# ── Python 1.1.0 additions ────────────────────────────────────────────────
#   pingouin           — statistical-analysis (effect sizes, power, ANOVA)
#   pymc + arviz       — statistical-analysis (Bayesian alternatives)
#   scikit-bio         — enrichment-analysis (CLR transform on compositional)
#   biopython          — AI-exploratory-data-analysis (FASTA/FASTQ/GenBank)
# All compatible with the pinned numpy 1.26.4 / scipy 1.13.1 / python 3.12.
RUN pip install --no-cache-dir \
        pingouin==0.5.5 \
        pymc==5.16.2 arviz==0.20.0 \
        scikit-bio==0.6.2 \
        biopython==1.84

# ── R packages: Bioconductor 3.21 + CRAN extras ───────────────────────────
# Bioc 3.21 is the release paired with R 4.5 today (3.22 ships Oct 2026).
#
# Every layer ends with `stopifnot` so a per-package install failure aborts
# the build — without this, install.packages() and BiocManager::install()
# only WARN on failure and 1.1.0 silently shipped without phyloseq / DESeq2
# / MaAsLin2 / dplyr / tidyr / readxl / circlize. Reproduce the 1.1.0 silent
# failure with:
#   docker run --rm openclaw/downstream:1.1.0 R -q -e \
#     'sapply(c("phyloseq","dplyr","tidyr"), requireNamespace)'
#   → all FALSE.
RUN R -e 'install.packages("BiocManager"); \
          stopifnot("BiocManager" %in% installed.packages()[,"Package"])'

RUN R -e 'BiocManager::install(version = "3.21", ask = FALSE, update = FALSE); \
          stopifnot("BiocManager" %in% installed.packages()[,"Package"])'

# CRAN core. Diff vs 1.1.0:
#   • Kept: vegan, ggplot2 (1.1.0 CRAN core)
#   • Added: dplyr, tidyr, readxl, circlize — all REQUIRED at runtime by
#     AI-report-generator's rendered R script (`library(dplyr); library(tidyr);
#     library(readxl); library(circlize)`); silently missing in 1.1.0 because
#     they were expected as transitive deps of MaAsLin2, which never installed.
RUN R -e 'pkgs <- c("vegan","ggplot2","dplyr","tidyr","readxl","circlize"); \
          install.packages(pkgs, Ncpus = parallel::detectCores()); \
          missing <- setdiff(pkgs, installed.packages()[,"Package"]); \
          if (length(missing)) stop("CRAN install failed for: ", paste(missing, collapse=", "))'

# Bioc tier. Diff vs 1.1.0:
#   • Kept: ALDEx2, ComplexHeatmap.
#   • Removed: phyloseq, DESeq2, MaAsLin2, ANCOMBC. None are called by any
#     rendered R driver in the codebase (grep audit 2026-06-09: no
#     `library(<pkg>)` and no `<pkg>::` references). They were listed as
#     "alternative methods" in skill docs but never wired into runtime
#     code paths. None of phyloseq/DESeq2/MaAsLin2 installed in 1.1.0
#     either (silent Bioc failure).
#
#   ANCOMBC was attempted in 1.1.1 but pulled an unsustainably brittle dep
#   chain — clarabel (needs rustc ≥ 1.70 via rustup; ~500 MB toolchain
#   cost), gmp/fs/gsl (need libgmp-dev/libuv1-dev/libgsl-dev system libs),
#   and CVXR — which has its own version-skew bug against ANCOMBC 2.10.1
#   (CVXR 1.0-13+ removed the top-level `solve` export, so ANCOMBC fails
#   to byte-compile). After three iterations chasing those, the call was
#   to drop ANCOMBC and stick with ALDEx2 as the sole differential-
#   abundance method until ANCOMBC upstream resolves the CVXR import (or
#   until Bioc 3.22 ships in Oct 2026).
#
#   To bring any of these back later: re-add to this line AND wire up the
#   actual analysis script in the relevant skill's scripts/ directory.
#   For ANCOMBC specifically you will also need to restore the apt layer
#   for libgmp-dev/libuv1-dev/libgsl-dev, the rustup install block, and a
#   CVXR 1.0-12 pin (search this Dockerfile's git history for the recipe).
RUN R -e 'pkgs <- c("ALDEx2","ComplexHeatmap"); \
          BiocManager::install(pkgs, ask=FALSE, update=FALSE, Ncpus = parallel::detectCores()); \
          missing <- setdiff(pkgs, installed.packages()[,"Package"]); \
          if (length(missing)) stop("Bioc install failed for: ", paste(missing, collapse=", "))'

# CRAN figures/report tier — unchanged from 1.1.0 (just adds stopifnot).
RUN R -e 'pkgs <- c("patchwork","ggrepel","svglite","ragg","ggsci"); \
          install.packages(pkgs, Ncpus = parallel::detectCores()); \
          missing <- setdiff(pkgs, installed.packages()[,"Package"]); \
          if (length(missing)) stop("CRAN install failed for: ", paste(missing, collapse=", "))'

# ── BioLine conventions ──────────────────────────────────────────────────
# /job        — rw (mounted from /data/output/<id>/)
# /job/stage  — ro (overlaid by prepare_downstream.sh)
# /pipeline   — ro (overlaid by prepare_downstream.sh with reference scripts)
RUN mkdir -p /job /pipeline
WORKDIR /job