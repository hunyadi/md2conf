set -e

# clean up output from previous runs
if [ -d dist ]; then rm -rf dist; fi
if [ -d *.egg-info ]; then rm -rf *.egg-info; fi

# create PyPI package for distribution
python3 -m build

# test PyPI package with various Python versions
# pass environment variables from the file `.env`
for PYTHON_VERSION in 3.8 3.9 3.10 3.11 3.12
do
    docker build -t py-$PYTHON_VERSION-image --build-arg PYTHON_VERSION=$PYTHON_VERSION .
    docker run -it --env-file .env --rm py-$PYTHON_VERSION-image python3 -m unittest discover tests
    docker rmi py-$PYTHON_VERSION-image
done
