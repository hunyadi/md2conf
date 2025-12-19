# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2025, Levente Hunyadi
# https://github.com/hunyadi/md2conf

# How do I use this `Dockerfile`?
#
# 1. Build image:
#    > docker build --tag md2conf .
#
# 2. Run application, mapping a local volume to a container volume:
#    > docker run --rm --env-file .env -v $PWD/tests/source:/data md2conf --render-mermaid --local /data/mermaid.md
#
# Replace `$PWD` with `%CD%` on Windows.

ARG PYTHON_VERSION=3.13
ARG ALPINE_VERSION=3.22
ARG MERMAID_VERSION=11.12

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

COPY ./ ./

RUN PIP_DISABLE_PIP_VERSION_CHECK=1 python3 -m pip install --upgrade pip && \
    pip install build
RUN python -m build --wheel --outdir wheel

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS host

# set environment for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/Dockerfile
ENV CHROME_BIN="/usr/bin/chromium-browser" \
    PUPPETEER_SKIP_DOWNLOAD="true"

# install dependencies for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/install-dependencies.sh
RUN apk upgrade \
    && apk add --update nodejs npm curl openjdk17-jre-headless graphviz \
    && apk add chromium font-noto-cjk font-noto-emoji terminus-font ttf-dejavu ttf-freefont ttf-font-awesome ttf-inconsolata ttf-linux-libertine \
    && fc-cache -f

RUN addgroup md2conf && adduser -D -G md2conf md2conf
USER md2conf
WORKDIR /home/md2conf

# Copy plantuml.sh script and set it up
COPY --chown=md2conf:md2conf plantuml.sh /home/md2conf/
RUN chmod +x /home/md2conf/plantuml.sh \
    && /home/md2conf/plantuml.sh --version

# Add plantuml.sh to PATH
ENV PATH="/home/md2conf:${PATH}"

RUN npm install @mermaid-js/mermaid-cli@${MERMAID_VERSION} \
    && node_modules/.bin/mmdc --version

FROM host AS runner

COPY --from=builder /wheel/*.whl wheel/

RUN python3 -m pip install `ls -1 wheel/*.whl`

WORKDIR /data
ENTRYPOINT ["python3", "-m", "md2conf"]
