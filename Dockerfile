ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-alpine
RUN python3 -m pip install --upgrade pip
COPY dist/*.whl dist/
RUN python3 -m pip install `ls -1 dist/*.whl`
COPY sample/ sample/
COPY tests/*.py tests/
