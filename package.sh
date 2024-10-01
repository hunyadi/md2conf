set -e
#
# Builds a Python package and runs unit tests in Docker
#

PYTHON=python3

# clean up output from previous runs
if [ -d dist ]; then rm -rf dist; fi
if [ -d *.egg-info ]; then rm -rf *.egg-info; fi

# create PyPI package for distribution
$PYTHON -m build

VERSION=`$PYTHON -c "from md2conf import __version__; print(__version__)"`
docker build -f Dockerfile -t leventehunyadi/md2conf:latest -t leventehunyadi/md2conf:$VERSION .
docker run -i -t --rm --env-file .env --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest sample/index.md --ignore-invalid-url

# test PyPI package with various Python versions
# pass environment variables from the file `.env`
for PYTHON_VERSION in 3.8 3.9 3.10 3.11 3.12
do
    docker build -f test.dockerfile -t py-$PYTHON_VERSION-image --build-arg PYTHON_VERSION=$PYTHON_VERSION .
    docker run -i -t --rm --env-file .env py-$PYTHON_VERSION-image python3 -m unittest discover tests
    docker rmi py-$PYTHON_VERSION-image
done
