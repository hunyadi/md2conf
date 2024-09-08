# Contributing

We want to make contributing to this project as easy and transparent as possible.

## Pull requests

We actively welcome your pull requests. Keep changes concise to help reviewers. Make sure you focus on a single bugfix
or a single feature.

### Prerequisites

Python is installed. Minimum version we support is Python 3.8.

### Helping you get set up

1. Create a GitHub issue proposing the feature you would like to have added.
2. Fork the repo and create your branch from `master`.
3. Set up your environment:

   ```
   git clone git@github.com:<your github username>/md2conf.git
   python -m venv ".venv"
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. If you've added code that should be tested, add tests to either `tests` or `integration_tests` directory.
   Note: The directory `integration_tests` assumes you have an active Confluence instance to run those against. 

### Running unit tests

```
python -m unittest discover -s tests
```

### Running integration tests

Before running these tests, you must set up your environment variables (e.g. add to your `~/.profile` on Linux, or `~/.bash_profile` or `~/.zshenv` on MacOS, or *System properties* on Windows.):

```bash
CONFLUENCE_DOMAIN='<your domain>.atlassian.net'
CONFLUENCE_PATH='/wiki/'
CONFLUENCE_USER_NAME='<your email>'
CONFLUENCE_API_KEY='0123456789abcdef'
CONFLUENCE_SPACE_KEY='<your space key>'
```

Runing the tests:
```
python -m unittest discover -s integration_tests
```

### Running static code checks

Verify that all code you have added passes static code checks. Depending on your OS, there is a script for you to use. If using Windows, run `check.bat`, otherwise run `./check.sh`.

