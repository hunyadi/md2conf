ARG PYTHON_VERSION=3.9

FROM python:${PYTHON_VERSION}-alpine as builder

COPY ./ ./

RUN python3 -m pip install --upgrade pip && \
    pip install build && \
    python -m build --wheel

FROM python:${PYTHON_VERSION}-alpine as host

RUN apk add --update nodejs npm && \
    npm install -g @mermaid-js/mermaid-cli

FROM host as runner

COPY --from=builder /dist/*.whl dist/

RUN python3 -m pip install `ls -1 dist/*.whl`

ENTRYPOINT ["python3", "-m", "md2conf"]
