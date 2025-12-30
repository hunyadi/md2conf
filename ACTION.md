# `md2conf` GitHub Action

This action provides a convenient way to run the `md2conf` tool within your GitHub Actions workflows, allowing you to automatically publish Markdown documentation to Confluence.

## Usage

### Basic Example

This example synchronizes the contents of the `./docs` directory with Confluence every time a push is made to the `main` branch. It uses the `v1` major version of the action, which is the recommended way to ensure you receive non-breaking updates.

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
        uses: actions/checkout@v4

      - name: Publish to Confluence
        uses: hunyadi/md2conf@v1
        with:
          path: './docs'
          space: 'MYSPACE'
          root_page: 'My Project Documentation'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
```

### Advanced Configuration

This example demonstrates more advanced features:

*   **Pinning to a specific version:** The action uses a specific patch version (`v1.0.0`) of the `md2conf` Docker image.
*   **Using an optimized image:** By specifying the `-minimal` tag, a smaller Docker image is used since diagram rendering is disabled.
*   **Skipping the title heading:** `skip_title_heading` is set to `true` to avoid title duplication on the Confluence page.

```yaml
# .github/workflows/publish.yml
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
        uses: actions/checkout@v4

      - name: Publish to Confluence
        uses: hunyadi/md2conf@v1
        with:
          # Use a specific, minimal version of the Docker image
          image_tag: 'v1.0.0-minimal'

          # Standard inputs
          path: './docs'
          space: 'MYSPACE'
          root_page: 'My Project Documentation'
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}

          # Publishing options
          skip_title_heading: true
          render_diagrams: false
```

## Configuration Guide

For a full list of all available inputs and their descriptions, please see the [`action.yml`](action.yml) file. The following sections highlight key configuration concepts.

### Versioning

The action is designed to be version-aware.

-   When you use a major version tag like `uses: hunyadi/md2conf@v1`, the action will automatically use the `v1` Docker image tag. This is the recommended approach for stability.
-   To use a specific version of the `md2conf` tool, set the `image_tag` input (e.g., `image_tag: 'v1.0.0'`).
-   To use an optimized image variant, append the suffix to the tag (e.g., `image_tag: 'v1-minimal'`).

### Using with Private Docker Registries

The action fully supports using private Docker images. Before running the `md2conf` action, add a step to your workflow to log in to your private registry using the `docker/login-action`.

```yaml
# ... (steps) ...
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Publish to Confluence using private image
        uses: hunyadi/md2conf@v1
        with:
          image_repository: ghcr.io/my-org/my-md2conf-fork
          image_tag: 'custom'
          path: './docs'
          # ... other inputs
          api_key: ${{ secrets.CONFLUENCE_API_KEY }}
```
