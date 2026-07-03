# images/base/Dockerfile
#
# Lightweight downstream image for skills that only need text/config
# processing or trivial tabular work. Use this instead of
# openclaw/downstream:1.0.0 (~2 GB, R + scientific stack) when scipy,
# statsmodels, R/Bioconductor, plotting, or ML libs aren't actually used.
#
# Build:
#   docker build -t openclaw/base:1.0.0 images/base/
#
# Skills currently targeting this image: skill-adapter

FROM python:3.12-slim-bookworm

LABEL maintainer="BioLine"
LABEL description="Lightweight image: stdlib + yaml/jinja2/markdown + pandas/numpy"

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.timeout 300 && \
    pip config set global.retries 10

# Versions kept aligned with openclaw/downstream:1.0.0 so skills can be
# promoted to the heavier image without semantic drift.
RUN pip install --no-cache-dir \
      pyyaml==6.0.1 \
      jinja2==3.1.4 \
      markdown==3.6 \
      pandas==2.2.2 \
      numpy==1.26.4

RUN mkdir -p /job /pipeline
WORKDIR /job
