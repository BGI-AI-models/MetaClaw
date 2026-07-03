# images/downstream-dl/Dockerfile
#
# Downstream container for deep-learning skills:
#   mgm · apex · bgc-prophet · onn4arg · AI-report-generator
#
# ── Build ─────────────────────────────────────────────────────────────────────
#   CPU (default):
#     docker build -t openclaw/downstream-dl:1.0.0 images/downstream-dl/


FROM python:3.11-slim-bookworm

LABEL maintainer="Ningkang Lab / BioLine"
LABEL description="Shared downstream image for DL skills: MGM, APEX, BGC-Prophet, ONN4ARG"

# ── System dependencies ───────────────────────────────────────────────────────
# Use Tsinghua mirror for faster apt in China
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libhdf5-dev \
      liblmdb-dev \
      wget \
      git \
      libgomp1 \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── PyPI mirror (speeds up installs on domestic networks) ────────────────────
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 300 && \
    pip config set global.retries 10

# ── Python base (~175 MB) ─────────────────────────────────────────────────────
# Shared by all skills.
RUN pip install --no-cache-dir \
      pandas==2.0.3 \
      numpy==1.24.3 \
      scipy==1.11.2 \
      scikit-learn==1.3.1 \
      biopython==1.81 \
      tqdm==4.65.0 \
      pyyaml==6.0.1

# ── AI-report-generator (~175 MB) ────────────────────────────────────────────
RUN pip install --no-cache-dir \
      jinja2==3.1.4 \
      plotly==5.22.0 \
      matplotlib==3.7.2 \
      seaborn==0.12.2 \
      pillow==10.0.1 \
      kaleido==0.2.1

# ── PyTorch — ~750 MB (CPU) or ~2500 MB (GPU) ────────────────────────────────
# Shared by: MGM, APEX, BGC-Prophet, ONN4ARG
# Default: CPU wheel
# GPU:     change to torch==2.0.1+cu118
RUN pip install --no-cache-dir torch==2.0.1

# ── MGM (~70 MB) ──────────────────────────────────────────────────────────────
# microformer_mgm pip package provides the `mgm` CLI — no repo clone needed.
RUN pip install --no-cache-dir \
      pytorch_lightning==2.0.6 \
      transformers==4.33.3 \
      accelerate==0.23.0 \
      living-tree==0.0.5 \
      treelib==1.5.5 \
      tables==3.8.0 \
      microformer_mgm==0.5.8

# ── BGC-Prophet (~27 MB) ─────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
      fair-esm==2.0.0 \
      lmdb==1.4.1 \
      bgc-prophet==0.1.1

# ── ONN4ARG (~8 MB) ──────────────────────────────────────────────────────────
RUN pip install --no-cache-dir h5py==3.9.0

# ── Repository clones ────────────────────────────────────────────────────────

# APEX: imports local Python modules (APEX_models, utils) from the repo —
# not available on PyPI. Source: Machine Biology Group (GitLab).
RUN git clone --depth 1 \
      https://gitlab.com/machine-biology-group-public/apex-pathogen.git \
      /repositories/apex-pathogen-main \
    || echo "WARNING: APEX repo clone failed — skill will not work without it"

# BGC-Prophet: download pretrained model checkpoints
RUN wget https://github.com/HUST-NingKang-Lab/BGC-Prophet/files/12733164/model.tar.gz
RUN mkdir -p /repositories/bgc-prophet_model
RUN tar -zxvf model.tar.gz -C /repositories/bgc-prophet_model --strip-components=1

# ── Directory layout ──────────────────────────────────────────────────────────
RUN mkdir -p /job /pipeline /repositories
WORKDIR /job



