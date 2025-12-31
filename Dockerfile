# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2025, Levente Hunyadi
# https://github.com/hunyadi/md2conf

# How do I use this `Dockerfile`?
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

# install git to allow setuptools_scm to determine version
RUN apk add --update git

COPY ./ ./

RUN PIP_DISABLE_PIP_VERSION_CHECK=1 python3 -m pip install --upgrade pip && \
    pip install build
RUN python -m build --wheel --outdir wheel

# ===== Stage 2: base (minimal) =====
# Minimal image with md2conf but no diagram rendering support
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS base

# Install minimal dependencies
RUN apk upgrade && apk add --update curl

# Create md2conf user
RUN addgroup md2conf && adduser -D -G md2conf md2conf
USER md2conf
WORKDIR /home/md2conf

# Install md2conf Python package
COPY --from=builder /wheel/*.whl wheel/
RUN python3 -m pip install `ls -1 wheel/*.whl`

# Set working directory and entrypoint
WORKDIR /data
ENTRYPOINT ["python3", "-m", "md2conf"]

# ===== Stage 3: mermaid =====
# Base image + Mermaid diagram rendering support
FROM base AS mermaid

# Switch to root to install packages
USER root

# Install Mermaid dependencies
# https://github.com/mermaid-js/mermaid-cli/blob/master/install-dependencies.sh
RUN apk add --update nodejs npm chromium \
        font-noto-cjk font-noto-emoji terminus-font \
        ttf-dejavu ttf-freefont ttf-font-awesome \
        ttf-inconsolata ttf-linux-libertine \
    && fc-cache -f

# Switch back to md2conf user
USER md2conf
WORKDIR /home/md2conf

# Set environment for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/Dockerfile
ENV CHROME_BIN="/usr/bin/chromium-browser" \
    PUPPETEER_SKIP_DOWNLOAD="true"

# Install mermaid-cli
ARG MERMAID_VERSION
RUN npm install @mermaid-js/mermaid-cli@${MERMAID_VERSION} \
    && node_modules/.bin/mmdc --version

WORKDIR /data

# ===== Stage 4: plantuml =====
# Base image + PlantUML diagram rendering support
FROM base AS plantuml

# Switch to root to install packages
USER root

# Install PlantUML dependencies
RUN apk add --update openjdk17-jre-headless graphviz

# Switch back to md2conf user
USER md2conf
WORKDIR /home/md2conf

# Download PlantUML JAR directly
ARG PLANTUML_VERSION
RUN curl -L -o /home/md2conf/plantuml.jar \
       "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && java -jar /home/md2conf/plantuml.jar -version

WORKDIR /data

# ===== Stage 5: all (default) =====
# Base image + both Mermaid and PlantUML support
FROM base AS all

# Switch to root to install packages
USER root

# Install all dependencies (Mermaid + PlantUML)
RUN apk add --update nodejs npm chromium \
        font-noto-cjk font-noto-emoji terminus-font \
        ttf-dejavu ttf-freefont ttf-font-awesome \
        ttf-inconsolata ttf-linux-libertine \
        openjdk17-jre-headless graphviz \
    && fc-cache -f

# Switch back to md2conf user
USER md2conf
WORKDIR /home/md2conf

# Set environment for both Mermaid and PlantUML
ENV CHROME_BIN="/usr/bin/chromium-browser" \
    PUPPETEER_SKIP_DOWNLOAD="true"

# Install mermaid-cli
ARG MERMAID_VERSION
RUN npm install @mermaid-js/mermaid-cli@${MERMAID_VERSION} \
    && node_modules/.bin/mmdc --version

# Download PlantUML JAR
ARG PLANTUML_VERSION
RUN curl -L -o /home/md2conf/plantuml.jar \
       "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && java -jar /home/md2conf/plantuml.jar -version

WORKDIR /data
