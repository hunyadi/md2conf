# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2025, Levente Hunyadi
# https://github.com/hunyadi/md2conf

# How do I use this `Dockerfile`?
#
# This Dockerfile is optimized for build caching. System dependencies are
# installed in separate stages to ensure that application code changes
# do not trigger a full rebuild of heavy layers (like Chromium or Java).
#
# 1. Build image (default includes all diagram renderers):
#    > docker build --tag md2conf .
#
# 2. Build minimal image (no diagram rendering):
#    > docker build --target base --tag md2conf:minimal .
#
# 3. Build with only Mermaid support:
#    > docker build --target mermaid --tag md2conf:mermaid .
#
# 4. Build with only PlantUML support:
#    > docker build --target plantuml --tag md2conf:plantuml .
#
# 5. Run application, mapping a local volume to a container volume:
#    > docker run --rm --env-file .env -v $PWD/tests/source:/data md2conf --render-mermaid --local /data/mermaid.md
#
# Replace `$PWD` with `%CD%` on Windows.

ARG PYTHON_VERSION=3.13
ARG ALPINE_VERSION=3.22
ARG MERMAID_VERSION=11.12
ARG PLANTUML_VERSION=1.2025.10

# ===== Stage 1: builder =====
# Builds Python wheel from source
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apk \
    apk upgrade && apk add --update git && \
    python3 -m pip install --upgrade pip && \
    pip install build

# Create a working directory
WORKDIR /build

# Copy source code
COPY ./ ./

# Build wheel
RUN python -m build --wheel --outdir wheel

# ===== Stage 2: runtime-base =====
# Common base for all runtime images
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS runtime-base

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Create md2conf user
RUN addgroup md2conf && adduser -D -G md2conf md2conf

# Set working directory and entrypoint
WORKDIR /data
ENTRYPOINT ["python3", "-m", "md2conf"]

# ===== Stage 3: mermaid-deps =====
# Runtime base + Mermaid diagram rendering support
FROM runtime-base AS mermaid-deps

# Install Mermaid dependencies
# https://github.com/mermaid-js/mermaid-cli/blob/master/install-dependencies.sh
RUN apk add --update nodejs npm chromium \
        font-noto-cjk font-noto-emoji terminus-font \
        ttf-dejavu ttf-freefont ttf-font-awesome \
        ttf-inconsolata ttf-linux-libertine \
    && fc-cache -f

# Install mermaid-cli
ARG MERMAID_VERSION
RUN mkdir -p /opt/mermaid && \
    npm install --prefix /opt/mermaid @mermaid-js/mermaid-cli@${MERMAID_VERSION} && \
    /opt/mermaid/node_modules/.bin/mmdc --version

# Set environment for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/Dockerfile
ENV CHROME_BIN="/usr/bin/chromium-browser" \
    PUPPETEER_SKIP_DOWNLOAD="true" \
    PATH="/opt/mermaid/node_modules/.bin:${PATH}"

# ===== Stage 4: plantuml-deps =====
# Runtime base + PlantUML diagram rendering support
FROM runtime-base AS plantuml-deps

# Install PlantUML dependencies (including font support)
# Note: openjdk17-jre (not headless) is required for libfontmanager.so
RUN apk add --update openjdk17-jre graphviz fontconfig ttf-dejavu \
    && fc-cache -f

# Download PlantUML JAR
ARG PLANTUML_VERSION
RUN mkdir -p /opt/plantuml && \
    wget -O /opt/plantuml/plantuml.jar \
       "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && java -jar /opt/plantuml/plantuml.jar -version

# Set PlantUML JAR location
ENV PLANTUML_JAR=/opt/plantuml/plantuml.jar

# ===== Stage 5: all-deps =====
# Runtime base + both Mermaid and PlantUML support
FROM mermaid-deps AS all-deps

# Install PlantUML dependencies (including font support)
# Note: openjdk17-jre (not headless) is required for libfontmanager.so
RUN apk add --update openjdk17-jre graphviz fontconfig \
    && fc-cache -f

# Copy PlantUML JAR from plantuml-deps stage
COPY --from=plantuml-deps /opt/plantuml /opt/plantuml

# Set PlantUML JAR location
ENV PLANTUML_JAR=/opt/plantuml/plantuml.jar

# ===== Stage 6: base (minimal) =====
# Minimal image with md2conf but no diagram rendering support
FROM runtime-base AS base
RUN --mount=type=bind,from=builder,source=/build/wheel,target=/tmp/wheel \
    python3 -m pip install /tmp/wheel/*.whl
USER md2conf

# ===== Stage 7: mermaid =====
# Base image + Mermaid diagram rendering support
FROM mermaid-deps AS mermaid
RUN --mount=type=bind,from=builder,source=/build/wheel,target=/tmp/wheel \
    python3 -m pip install /tmp/wheel/*.whl
USER md2conf

# ===== Stage 8: plantuml =====
# Base image + PlantUML diagram rendering support
FROM plantuml-deps AS plantuml
RUN --mount=type=bind,from=builder,source=/build/wheel,target=/tmp/wheel \
    python3 -m pip install /tmp/wheel/*.whl
USER md2conf

# ===== Stage 9: all (default) =====
# Base image + both Mermaid and PlantUML support
FROM all-deps AS all
RUN --mount=type=bind,from=builder,source=/build/wheel,target=/tmp/wheel \
    python3 -m pip install /tmp/wheel/*.whl
USER md2conf
