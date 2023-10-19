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
* [Table of Contents](https://docs.gitlab.com/ee/user/markdown.html#table-of-contents)
* [Admonitions](https://python-markdown.github.io/extensions/admonition/) (converted into *info*, *tip*, *note* and *warning* Confluence panels)

## Getting started

In order to get started, you will need
* your organization domain name (e.g. `instructure.atlassian.net`),
* base path for Confluence wiki (typically `/wiki/` for managed Confluence, `/` for on-premise)
* your Confluence username (e.g. `levente.hunyadi@instructure.com`) (only if required by your deployment),
* a Confluence API token (a string of alphanumeric characters), and
* the space key in Confluence (e.g. `DAP`) you are publishing content to.

### Obtaining an API token

1. Log in to https://id.atlassian.com/manage/api-tokens.
2. Click *Create API token*.
3. From the dialog that appears, enter a memorable and concise *Label* for your token and click *Create*.
4. Click *Copy to clipboard*, then paste the token to your script, or elsewhere to save.

### Setting up the environment

Confluence organization domain, base path, username, API token and space key can be specified at runtime or set as Confluence environment variables (e.g. add to your `~/.profile` on Linux, or `~/.bash_profile` or `~/.zshenv` on MacOS):
```bash
export CONFLUENCE_DOMAIN='instructure.atlassian.net'
export CONFLUENCE_PATH='/wiki/'
export CONFLUENCE_USER_NAME='levente.hunyadi@instructure.com'
export CONFLUENCE_API_KEY='0123456789abcdef'
export CONFLUENCE_SPACE_KEY='DAP'
```

On Windows, these can be set via system properties.

### Permissions

The tool requires appropriate permissions in Confluence in order to invoke endpoints.

If a Confluence username is set, the tool uses HTTP *Basic* authentication to pass the username and the API key to Confluence REST API endpoints. If no username is provided, the tool authenticates with HTTP *Bearer*, and passes the API key as the bearer token.

If you lack appropriate permissions, you will get an *Unauthorized* response from Confluence. The tool will emit a message that looks as follows:

```
2023-06-30 23:59:59,000 - ERROR - <module> [80] - 401 Client Error: Unauthorized for url: ...
```

### Associating a Markdown file with a wiki page

Each Markdown file is associated with a Confluence wiki page with a Markdown comment:

```markdown
<!-- confluence-page-id: 85668266616 -->
```

The above tells the tool to synchronize the Markdown file with the given Confluence page ID. This implies that the Confluence wiki page must exist such that it has an ID. The comment can be placed anywhere in the source file.

### Setting the Confluence space

If you work in an environment where there are multiple Confluence spaces, and some Markdown pages may go into one space, whereas other pages may go into another, you can set the target space on a per-document basis:

```markdown
<!-- confluence-space-key: DAP -->
```

This overrides the default space set via command-line arguments or environment variables.

### Setting generated-by prompt text for wiki pages

In order to ensure readers are not editing a generated document, the tool adds a warning message at the top of the Confluence page as an *info panel*. You can customize the text that appears. The text can contain markup as per the [Confluence Storage Format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html), and is emitted directly into the *info panel* macro.

Provide generated-by prompt text in the Markdown file with a tag:

```markdown
<!-- generated-by: Do not edit! Check out the <a href="https://example.com/project">original source</a>. -->
```

Alternatively, use the `--generated-by GENERATED_BY` option. The tag takes precedence.

### Running the tool

You execute the command-line tool `md2conf` to synchronize the Markdown file with Confluence:

```console
$ python3 -m md2conf sample/example.md
```

Use the `--help` switch to get a full list of supported command-line options:

```console
$ python3 -m md2conf --help
usage: md2conf [-h] [-d DOMAIN] [-p PATH] [-u USERNAME] [-a APIKEY] [-s SPACE]
               [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--generated-by GENERATED_BY] [--no-generated-by]
               mdpath

positional arguments:
  mdpath                Path to Markdown file or directory to convert and publish.

options:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Confluence organization domain.
  -p PATH, --path PATH  Base path for Confluece wiki.
  -u USERNAME, --username USERNAME
                        Confluence user name.
  -a APIKEY, --apikey APIKEY
                        Confluence API key. Refer to documentation how to obtain one.
  -s SPACE, --space SPACE
                        Confluence space key for pages to be published. If omitted, will default to user
                        space.
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Use this option to set the log verbosity.
  --generated-by GENERATED_BY
                        Add prompt to pages (default: 'This page has been generated with a tool.').
  --no-generated-by     Do not add 'generated by a tool' prompt to pages.
```
