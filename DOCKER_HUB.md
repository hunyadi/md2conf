# md2conf - Markdown to Confluence

[Browse code at %{GIT_TAG}](%{GITHUB_REPO_URL}/tree/%{GIT_TAG})

### Why md2conf?

Contributors typically write documentation in Markdown and host it in version control systems (VCS) like GitHub or GitLab. However, not everyone in an organization has access to VCS, and documents are often shared via Confluence.

Manually replicating documentation is tedious and leads to synchronization issues. `md2conf` solves this by parsing Markdown, converting it to Confluence Storage Format (XHTML), and using the Confluence API to automate the upload of content and assets.


## Features

- **Standard Markdown Support**: Tables, lists, tasklists, footnotes, and more.
- **Diagram Rendering**: Built-in support for **Mermaid**, **PlantUML**, and **draw.io** diagrams.
- **LaTeX Formulas**: Pre-render math formulas into images for Confluence.
- **Confluence Macros**: Support for TOC, child pages, status labels, and custom macros.
- **Advanced Layout**: Control image alignment, maximum width, and page appearance.

> [!NOTE]
> While `md2conf` supports **draw.io** diagrams, the pre-built Docker images do not include the necessary dependencies to render them. If you need draw.io support, you will need to extend these images with the required libraries.

## Docker Image Variants

We provide several image variants to allow you to balance between features and image size:

| Variant | Description | Tags |
| :--- | :--- | :--- |
| **Minimal** | Python 3 Alpine image with `md2conf`. No diagram renderers. | %{TAGS_BASE} |
| **Mermaid** | _Minimal_ plus `mermaid-cli` and its dependencies (Chromium, Node.js). | %{TAGS_MERMAID} |
| **PlantUML** | _Minimal_ plus PlantUML and its dependencies (Java, Graphviz). | %{TAGS_PLANTUML} |
| **Full** | All of the above. | %{TAGS_ALL} |


## How to Use This Image

The image is designed to be used as a CLI tool. You typically mount your source directory to `/data` in the container.

### Basic Usage

Synchronize a local Markdown file to Confluence using environment variables for authentication:

```bash
docker run --rm \
  -v $(pwd):/data \
  --env-file .env \
  %{DOCKER_IMAGE_NAME}:latest \
  ./my-document.md
```

### With Diagram Rendering

If your documents use Mermaid or PlantUML, use the corresponding variants and enable rendering:

```bash
docker run --rm \
  -v $(pwd):/data \
  --env-file .env \
  %{DOCKER_IMAGE_NAME}:latest-mermaid \
  --render-mermaid \
  ./my-document.md
```

## Configuration

### Environment Variables

| Variable | Description |
| :--- | :--- |
| `CONFLUENCE_DOMAIN` | Your organization domain (e.g., `your-domain.atlassian.net`) |
| `CONFLUENCE_USER_NAME` | Your Confluence username / email |
| `CONFLUENCE_API_KEY` | Your Atlassian API Token |
| `CONFLUENCE_SPACE_KEY` | The target space key |
| `CONFLUENCE_API_URL` | (Optional) Required for scoped tokens |

### Volumes

| Path | Description |
| :--- | :--- |
| `/data` | Working directory where your Markdown files are located. |

## More Information

- **GitHub Repository**: [%{GITHUB_REPOSITORY}](%{GITHUB_REPO_URL})
- **PyPI Package**: [markdown-to-confluence](https://pypi.org/project/markdown-to-confluence/)
- **Full Documentation**: See the [README on GitHub](%{GITHUB_REPO_URL}#readme) for advanced usage and CLI options.
