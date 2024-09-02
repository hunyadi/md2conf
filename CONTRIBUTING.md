# Contributing

We want to make contributing to this project as easy and transparent as
possible.

## Pull Requests

We actively welcome your pull requests.

### Pre-reqs

1. Python is setup. Minimum version we support is 3.8 so you should develop using that. 

### Helping you get setup

0. Create a GitHub issue proposing the issue or feature you would like to have added.
1. Fork the repo and create your branch from `master`.
2. Setup your enviornment

   ```
   git clone git@github.com:<your github username>/md2conf.git
   python -m venv ".venv"
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. If you've added code that should be tested, add tests to either `tests` or `integration_tests` directory.
   Note: The `integration_tests` directory assumes you have an active confluence instance to run those against. 

#### Running Unit tests
```
python -m unittest discover -s tests
```

#### Running integration tests

```
python -m unittest discover -s integration_tests
```

4. Verify all code you have added passes static and code checks. Depending on your OS there is a script for you to use. If using windows `check.bat`, otherwise use `check.sh`. 

