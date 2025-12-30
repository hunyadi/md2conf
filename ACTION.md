# `md2conf` GitHub Action

This action provides a convenient way to run the `md2conf` tool within your GitHub Actions workflows, allowing you to automatically publish Markdown documentation to Confluence.

For a full list of all available inputs and their descriptions, please see the [`action.yml`](action.yml) file.

## Basic Usage

This example synchronizes the contents of the `./docs` directory with Confluence every time a push is made to the `main` branch. It uses the `v1` major version tag, which is the recommended way to ensure you receive non-breaking updates.

```yaml
name: Publish Docs to Confluence

on:
  push:
    branches:
      - main

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v6

      - name: Publish to Confluence
        uses: hunyadi/md2conf@v1
        with:
          path: './docs'
          space: 'MYSPACE'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
```

## Advanced Usage

### Using a Specific Image Version

By default, the action uses a Docker image tag that matches the action's version (e.g., using `hunyadi/md2conf@v1` will pull the `v1` image tag). You can override this to pin to a specific version or use an optimized image variant (like `-minimal`).

```yaml
      - name: Publish to Confluence
        uses: hunyadi/md2conf@v1
        with:
          # Use a specific, minimal version of the Docker image
          image_tag: 'v1.0.0-minimal'
          path: './docs'
          space: 'MYSPACE'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
```

### Using a Custom or Private Image

You can specify a different Docker image repository, which is useful for forks or private registries. If your registry requires authentication, add a `docker/login-action` step before this one.

```yaml
      - name: Log in to a private registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Publish to Confluence
        uses: hunyadi/md2conf@v1
        with:
          image_repository: ghcr.io/my-org/my-md2conf-fork
          image_tag: 'custom'
          path: './docs'
          space: 'MYSPACE'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
```

### Passing Extra Arguments

For any command-line options not covered by a dedicated input, you can use `extra_args` to pass them directly to the `md2conf` executable.

```yaml
      - name: Publish with extra arguments
        uses: hunyadi/md2conf@v1
        with:
          path: './docs'
          space: 'MYSPACE'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
          extra_args: '--no-render-latex --title-prefix "My Prefix "'
```

