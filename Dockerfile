# Example commands how to use this `Dockerfile`:
# > docker build --tag md2conf .
# > docker run --rm --env-file .env -v %CD%/tests/source:/data md2conf --render-mermaid --local /data/mermaid.md

ARG PYTHON_VERSION=3.9
ARG ALPINE_VERSION=3.22
ARG MERMAID_VERSION=11.6

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS builder

COPY ./ ./

RUN PIP_DISABLE_PIP_VERSION_CHECK=1 python3 -m pip install --upgrade pip && \
    pip install build
RUN python -m build --wheel

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS host

# set environment for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/Dockerfile
ENV CHROME_BIN="/usr/bin/chromium-browser" \
    PUPPETEER_SKIP_DOWNLOAD="true"

# install dependencies for @mermaid-js/mermaid-cli
# https://github.com/mermaid-js/mermaid-cli/blob/master/install-dependencies.sh
RUN apk upgrade \
    && apk add --update nodejs npm \
    && apk add chromium font-noto-cjk font-noto-emoji terminus-font ttf-dejavu ttf-freefont ttf-font-awesome ttf-inconsolata ttf-linux-libertine \
    && fc-cache -f

RUN addgroup md2conf && adduser -D -G md2conf md2conf
USER md2conf
WORKDIR /home/md2conf
RUN npm install @mermaid-js/mermaid-cli@${MERMAID_VERSION} \
    && node_modules/.bin/mmdc --version

FROM host AS runner

COPY --from=builder /dist/*.whl dist/

RUN python3 -m pip install `ls -1 dist/*.whl`

WORKDIR /data
ENTRYPOINT ["python3", "-m", "md2conf"]
