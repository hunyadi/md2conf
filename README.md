# Publish Markdown files to Confluence wiki

Contributors to software projects typically write documentation in Markdown format and host Markdown files in collaborative version control systems (VCS) such as GitHub or GitLab to track changes and facilitate the review process. However, not everyone at a company has access to VCS, and documents are often circulated in Confluence wiki instead.

Replicating documentation to Confluence by hand is tedious, and a lack of automated synchronization with the project repositories where the documents live leads to outdated documentation.

This Python package
* parses Markdown files,
* converts Markdown content into the Confluence Storage Format (XHTML),
* invokes Confluence API endpoints to upload images and content.

## Features

* Sections and subsections
* Text with **bold**, *italic*, `monospace`, <ins>underline</ins> and ~~strikethrough~~
* Link to [external locations](http://example.com/)
* Ordered and unordered lists
* Code blocks (e.g. Python, JSON, XML)
* Image references (uploaded as Confluence page attachments)

## Getting started

In order to get started, you will need
* your organization domain name (e.g. `instructure.atlassian.net`),
* your Confluence username (e.g. `levente.hunyadi@instructure.com`),
* a Confluence API token (a string of alphanumeric characters), and
* the space key in Confluence (e.g. `DAP`) you are publishing content to.

### Obtaining an API token

1. Log in to https://id.atlassian.com/manage/api-tokens.
2. Click *Create API token*.
3. From the dialog that appears, enter a memorable and concise *Label* for your token and click *Create*.
4. Click *Copy to clipboard*, then paste the token to your script, or elsewhere to save.

### Setting up the environment

Confluence organization URL, username, API token and space key can be specified at runtime or set as Confluence environment variables (e.g. add to your `~/.profile` on Linux, or `~/.bash_profile` or `~/.zshenv` on MacOS):
```bash
export CONFLUENCE_DOMAIN='instructure.atlassian.net'
export CONFLUENCE_USER_NAME='levente.hunyadi@instructure.com'
export CONFLUENCE_API_KEY='0123456789abcdef'
export CONFLUENCE_SPACE_KEY='DAP'
```

On Windows, these can be set via system properties.

The tool requires appropriate permissions in Confluence in order to invoke endpoints.

### Associating a Markdown file with a wiki page

Each Markdown file is associated with a Confluence wiki page with a Markdown comment:

```markdown
<!-- confluence-page-id: 85668266616 -->
```

The above tells the tool to synchronize the Markdown file with the given Confluence page ID. This implies that the Confluence wiki page must exist such that it has an ID. The comment can be placed anywhere in the source file.

### Running the tool

You execute the command-line tool `md2conf` to synchronize the Markdown file with Confluence:
```bash
python3 -m md2conf example.md
```
