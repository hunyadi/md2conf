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

docker build -f Dockerfile -t md2conf-image .
docker run -i -t --rm --env-file .env --name md2conf -v $(pwd):/data md2conf-image sample/index.md --ignore-invalid-url

# test PyPI package with various Python versions
# pass environment variables from the file `.env`
for PYTHON_VERSION in 3.8 3.9 3.10 3.11 3.12
do
    docker build -f test.dockerfile -t py-$PYTHON_VERSION-image --build-arg PYTHON_VERSION=$PYTHON_VERSION .
    docker run -i -t --rm --env-file .env py-$PYTHON_VERSION-image python3 -m unittest discover tests
    docker rmi py-$PYTHON_VERSION-image
done
