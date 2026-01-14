# Contributing

We want to make contributing to this project as easy and transparent as possible.

## Install latest version

Before you request a feature or report an issue, verify whether the proposal has already been implemented in one of the commits on the branch `master`. Instruct `pip` to install the package directly from source control rather than PyPI:

```sh
pip install git+https://github.com/hunyadi/md2conf.git@master
```

Due to constrained capacity, we only support the latest release of *md2conf*.

## Pull requests

We actively welcome your pull requests. Keep changes concise to help reviewers. Make sure you focus on a single bugfix or a single feature.

### Prerequisites

Python is installed. Minimum version we support is Python 3.10.

### Helping you get set up

1. Create a GitHub issue proposing the feature you would like to have added.
2. Fork the repo and create your branch from `master`.
3. Set up your environment:

   ```sh
   git clone git@github.com:<your github username>/md2conf.git
   python -m venv ".venv"
   source .venv/bin/activate
   python -m pip install ".[formulas,dev]"
   ```

4. If you've added code that should be tested, add tests to either `tests` or `integration_tests` directory.
   Note: The directory `integration_tests` assumes you have an active Confluence instance to run those against.

#### Test Organization

- `tests/`: Unit tests that run without external dependencies.
- `tests/source/`: Markdown files with hardcoded Confluence page IDs used exclusively for unit tests (e.g., testing front-matter and HTML comment parsing). These files should *not* be used by integration tests.
- `tests/target/`: Confluence Storage Format (XHTML) files used as reference to compare against.
- `sample/`: Sample Markdown files used by integration tests. These should *not* contain hardcoded `confluence-page-id` comments or `page_id` front-matter properties, as integration tests dynamically create and manage pages.
- `integration_tests/`: Tests that interact with a live Confluence instance.

### Running unit tests

```sh
python -m unittest discover -s tests
```

### Running integration tests

Before running these tests, you must set up your environment variables (e.g. add to your `~/.profile` on Linux, or `~/.bash_profile` or `~/.zshenv` on MacOS, or *System properties* on Windows.):

```sh
CONFLUENCE_DOMAIN='<your domain>.atlassian.net'
CONFLUENCE_PATH='/wiki/'
CONFLUENCE_USER_NAME='<your email>'
CONFLUENCE_API_KEY='0123456789abcdef'
CONFLUENCE_SPACE_KEY='<your space key>'
```

Running the tests:

```sh
python -m unittest discover -s integration_tests
```

#### Running integration tests via GitHub Actions

You can trigger integration tests remotely using GitHub Actions workflow. This is useful for testing different rendering modes without setting up local dependencies like PlantUML or Mermaid.

**Important for forked repositories:** When running from a clone of a forked repository, you **must** specify the `--repo` option. Without it, `gh` will attempt to trigger the workflow on the upstream repository instead of your fork.

Basic command structure:

```sh
gh workflow run integration-tests.yml \
  --ref <branch-name> \
  --repo <owner>/<repo-name> \
  --field render_plantuml=<true|false> \
  --field render_mermaid=<true|false> \
  --field diagram_output_format=<png|svg>
```

Example for testing PlantUML with SVG rendering on a forked repository:

```sh
gh workflow run integration-tests.yml \
  --ref add-plantuml-support \
  --repo my-github-account/hunyadi-md2conf \
  --field render_plantuml=true \
  --field diagram_output_format=svg
```

Available workflow inputs:

- `render_plantuml`: Render PlantUML diagrams to images (true/false, default: false)
- `render_mermaid`: Render Mermaid diagrams to images (true/false, default: false)
- `diagram_output_format`: Output format for rendered diagrams (png/svg, default: svg)

Test different scenarios:

```sh
# Test PlantUML macro mode (no rendering)
gh workflow run integration-tests.yml --ref <branch> --repo <owner>/<repo>

# Test PlantUML with PNG rendering
gh workflow run integration-tests.yml --ref <branch> --repo <owner>/<repo> \
  --field render_plantuml=true --field diagram_output_format=png

# Test PlantUML with SVG rendering
gh workflow run integration-tests.yml --ref <branch> --repo <owner>/<repo> \
  --field render_plantuml=true --field diagram_output_format=svg

# Test both Mermaid and PlantUML rendering
gh workflow run integration-tests.yml --ref <branch> --repo <owner>/<repo> \
  --field render_mermaid=true --field render_plantuml=true --field diagram_output_format=svg
```

Monitor workflow status:

```sh
gh run list --workflow=integration-tests.yml --repo <owner>/<repo>
gh run watch <run-id> --repo <owner>/<repo>
```

### Running static code checks

Verify that all code you have added passes static code checks. Depending on your OS, there is a script for you to use. If using Windows, run `check.bat`, otherwise run `./check.sh`.

> [!NOTE]
> Documentation generation in the check scripts is skipped if the Python version is older than 3.13 to maintain consistent formatting. You can still run `python documentation.py` manually if needed.

### Generating documentation

Verify that newly contributed classes, data-classes and functions have a doc-string, including public members, parameters, return values and exceptions raised. You can generate human-readable Markdown documentation with [markdown_doc](https://github.com/hunyadi/markdown_doc):

```sh
python -m markdown_doc -d md2conf
```

### Building Docker images

The Docker image can be customized to include only the dependencies you need, significantly reducing image size:

**Build Targets:**

Use `--target <stage>` to build specific variants:

- `base` - Minimal image with no diagram rendering (~87MB)
- `mermaid` - Include Mermaid diagram support only (~1.6GB)
- `plantuml` - Include PlantUML diagram support only (~334MB)
- `all` - Full image with both renderers (~1.8GB, default)

**Building Individual Images:**

Minimal image (no diagram rendering):

```sh
docker build --target base --tag md2conf:minimal .
```

Mermaid only:

```sh
docker build --target mermaid --tag md2conf:mermaid .
```

PlantUML only:

```sh
docker build --target plantuml --tag md2conf:plantuml .
```

Full image (default):

```sh
docker build --target all --tag md2conf:full .
```

or

```sh
docker build --tag md2conf .
```

**Building All Variants in Parallel with Docker Bake:**

Docker Bake builds all 4 image variants simultaneously with shared layer caching:

```bash
docker buildx bake
```

This builds all targets defined in `docker-bake.hcl` in parallel, significantly reducing total build time compared to sequential builds.

**Build Performance and Caching:**

The Dockerfile is structured to optimize build caching:

- Heavy system dependencies (Chromium for Mermaid, Java for PlantUML) are installed in separate `*-deps` stages that rarely change
- Application code changes only trigger a fast pip install of the Python wheel (~2-3 seconds with cache)
- BuildKit cache mounts are used for package manager caches (apk) and wheel installation
- With layer caching, incremental builds complete in under a minute instead of 2+ minutes for full rebuilds

When you modify Python code, only the final stage rebuilds - the expensive system dependency layers remain cached. This architecture enables rapid iteration during development.

**Configuring GitHub Actions for Custom Docker Hub:**

To publish images to your own Docker Hub account, configure the following in your GitHub repository:

1. **Repository Secrets** (Settings → Secrets and variables → Actions → Secrets):
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_PASSWORD`: Your Docker Hub access token or password

2. **Repository Variables** (Settings → Secrets and variables → Actions → Variables):
   - `DOCKER_IMAGE_NAME`: Your image name (e.g., `yourusername/md2conf`)

If `DOCKER_IMAGE_NAME` is not set, it defaults to `leventehunyadi/md2conf`.

**Triggering Docker Builds:**

1. **Push a Git tag** (production release):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Builds and pushes all variants with version and latest tags:
   - `yourusername/md2conf:latest` & `yourusername/md2conf:1.0.0`
   - `yourusername/md2conf:latest-minimal` & `yourusername/md2conf:1.0.0-minimal`
   - `yourusername/md2conf:latest-plantuml` & `yourusername/md2conf:1.0.0-plantuml`
   - `yourusername/md2conf:latest-mermaid` & `yourusername/md2conf:1.0.0-mermaid`

2. **Manual workflow dispatch** (testing):
   - Go to: **Actions** → **Publish Docker image** → **Run workflow**
   - Select your branch
   - Choose "Push images to Docker Hub" (true/false)
   - Builds all 4 variants tagged with commit SHA (e.g., `yourusername/md2conf:sha-abc1234-minimal`)
