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
* Link to [sections on the same page](#getting-started) or [external locations](http://example.com/)
* Subscript and superscript
* Math formulas with LaTeX notation
* Emoji
* Ordered and unordered lists
* Block quotes
* Code blocks (e.g. Python, JSON, XML)
* Images (uploaded as Confluence page attachments or hosted externally)
* Tables
* Footnotes
* [Table of contents](https://docs.gitlab.com/ee/user/markdown.html#table-of-contents)
* [Admonitions](https://python-markdown.github.io/extensions/admonition/) and alert boxes in [GitHub](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts) and [GitLab](https://docs.gitlab.com/ee/development/documentation/styleguide/#alert-boxes)
* [Collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)
* [Tasklists](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists)
* draw\.io diagrams
* [Mermaid diagrams](https://mermaid.live/)
* Confluence status labels and date widget

Whenever possible, the implementation uses [Confluence REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/) to fetch space properties, and get, create or update page content.

## Installation

**Required.** Install the core package from [PyPI](https://pypi.org/project/markdown-to-confluence/):

```sh
pip install markdown-to-confluence
```

### Command-line utilities

**Optional.** Converting `*.drawio` diagrams to PNG or SVG images before uploading to Confluence as attachments requires installing [draw.io](https://www.drawio.com/). (Refer to `--render-drawio`.)

**Optional.** Converting code blocks of Mermaid diagrams to PNG or SVG images before uploading to Confluence as attachments requires [mermaid-cli](https://github.com/mermaid-js/mermaid-cli). (Refer to `--render-mermaid`.)

```sh
npm install -g @mermaid-js/mermaid-cli
```

**Optional.** Pre-rendering PlantUML diagrams into PNG or SVG images requires Java, Graphviz and [PlantUML](https://plantuml.com/). (Refer to `--render-plantuml`.)

1. **Install Java**: Version 8 or later from [Adoptium](https://adoptium.net/) or [Oracle](https://www.oracle.com/java/technologies/downloads/)
2. **Install Graphviz**: Required for most diagram types in PlantUML (except sequence diagrams)
   * **Ubuntu/Debian**: `sudo apt-get install Graphviz`
   * **macOS**: `brew install graphviz`
   * **Windows**: Download from [graphviz.org](https://graphviz.org/download/)
3. **Download PlantUML JAR**: Download [plantuml.jar](https://github.com/plantuml/plantuml/releases) and set `PLANTUML_JAR` environment variable to point to it

**Optional.** Converting formulas and equations to PNG or SVG images requires [Matplotlib](https://matplotlib.org/):

```sh
pip install matplotlib
```

### Marketplace apps

As authors of *md2conf*, we don't endorse or support any particular Confluence marketplace apps.

**Optional.** Editable draw\.io diagrams require [draw.io Diagrams marketplace app](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-uml-bpmn-aws-erd-flowcharts). (Refer to `--no-render-drawio`.)

**Optional.** Displaying Mermaid diagrams in Confluence without pre-rendering in the synchronization phase requires a [marketplace app](https://marketplace.atlassian.com/apps/1226567/mermaid-diagrams-for-confluence). (Refer to `--no-render-mermaid`.)

**Optional.** PlantUML diagrams are embedded with compressed source data and are displayed using the [PlantUML Diagrams for Confluence](https://marketplace.atlassian.com/apps/1215115/plantuml-diagrams-for-confluence) app (if installed). (Refer to `--no-render-plantuml`.)

Installing `plantuml.jar` (see above) helps display embedded diagrams with pre-calculated optimal dimensions.

**Optional.** Displaying formulas and equations in Confluence requires [marketplace app](https://marketplace.atlassian.com/apps/1226109/latex-math-for-confluence-math-formula-equations), refer to [LaTeX Math for Confluence - Math Formula & Equations](https://help.narva.net/latex-math-for-confluence/). (Refer to `--no-render-latex`.)

## Getting started

In order to get started, you will need

* your organization domain name (e.g. `example.atlassian.net`),
* base path for Confluence wiki (typically `/wiki/` for managed Confluence, `/` for on-premise)
* your Confluence username (e.g. `levente.hunyadi@instructure.com`) (only if required by your deployment),
* a Confluence API token (a string of alphanumeric characters), and
* the space key in Confluence (e.g. `SPACE`) you are publishing content to.

### Obtaining an API token

1. Log in to <https://id.atlassian.com/manage/api-tokens>.
2. Click *Create API token*.
3. From the dialog that appears, enter a memorable and concise *Label* for your token and click *Create*.
4. Click *Copy to clipboard*, then paste the token to your script, or elsewhere to save.

### Setting up the environment

Confluence organization domain, base path, username, API token and space key can be specified at runtime or set as Confluence environment variables (e.g. add to your `~/.profile` on Linux, or `~/.bash_profile` or `~/.zshenv` on MacOS):

```sh
export CONFLUENCE_DOMAIN='example.atlassian.net'
export CONFLUENCE_PATH='/wiki/'
export CONFLUENCE_USER_NAME='levente.hunyadi@instructure.com'
export CONFLUENCE_API_KEY='0123456789abcdef'
export CONFLUENCE_SPACE_KEY='SPACE'
```

On Windows, these can be set via system properties.

If you use Atlassian scoped API tokens, you may want to set API URL directly, substituting `CLOUD_ID` with your own Cloud ID:

```sh
export CONFLUENCE_API_URL='https://api.atlassian.com/ex/confluence/CLOUD_ID/'
```

In this case, *md2conf* can automatically determine `CONFLUENCE_DOMAIN` and `CONFLUENCE_PATH`.

If you can't find your `CLOUD_ID` but assign both `CONFLUENCE_DOMAIN` and `CONFLUENCE_PATH`, *md2conf* makes a best-effort attempt to determine `CONFLUENCE_API_URL`.

### Permissions

The tool requires appropriate permissions in Confluence in order to invoke endpoints.

We recommend the following scopes for scoped API tokens:

* `read:attachment:confluence`
* `read:content:confluence`
* `read:content-details:confluence`
* `read:label:confluence`
* `read:page:confluence`
* `read:space:confluence`
* `write:attachment:confluence`
* `write:content:confluence`
* `write:label:confluence`
* `write:page:confluence`
* `delete:attachment:confluence`
* `delete:content:confluence`
* `delete:page:confluence`

If a Confluence username is set, the tool uses HTTP *Basic* authentication to pass the username and the API key to Confluence REST API endpoints. If no username is provided, the tool authenticates with HTTP *Bearer*, and passes the API key as the bearer token.

If you lack appropriate permissions, you will get an *Unauthorized* response from Confluence. The tool will emit a message that looks as follows:

```
2023-06-30 23:59:59,000 - ERROR - <module> [80] - 401 Client Error: Unauthorized for url: ...
```

### Associating a Markdown file with a wiki page

Each Markdown file is associated with a Confluence wiki page with a Markdown comment:

```markdown
<!-- confluence-page-id: 20250001023 -->
```

The above tells the tool to synchronize the Markdown file with the given Confluence page ID. This implies that the Confluence wiki page must exist such that it has an ID. The comment can be placed anywhere in the source file.

### Setting the Confluence space

If you work in an environment where there are multiple Confluence spaces, and some Markdown pages may go into one space, whereas other pages may go into another, you can set the target space on a per-document basis:

```markdown
<!-- confluence-space-key: SPACE -->
```

This overrides the default space set via command-line arguments or environment variables.

### Setting generated-by prompt text for wiki pages

In order to ensure readers are not editing a generated document, the tool adds a warning message at the top of the Confluence page as an *info panel*. You can customize the text that appears. The text can contain markup as per the [Confluence Storage Format](https://confluence.atlassian.com/doc/confluence-storage-format-790796544.html), and is emitted directly into the *info panel* macro.

Provide generated-by prompt text in the Markdown file with a tag:

```markdown
<!-- generated-by: Do not edit! Check out the <a href="https://example.com/project">original source</a>. -->
```

Alternatively, use the `--generated-by GENERATED_BY` option. The tag takes precedence.

The generated-by text can also be templated with the following variables:

- `%{filename}`: the name of the Markdown file
- `%{filestem}`: the name of the Markdown file without the extension
- `%{filepath}`: the path of the Markdown file relative to the _source root_
- `%{filedir}`: the dirname of the `%{filepath}` (the path without the filename)

When publishing a directory hierarchy, the *source root* is the directory in which *md2conf* is launched. When publishing a single file, this is the directory in which the Markdown file resides.

It can be used with the CLI `--generated-by` option or directly in the files:

```markdown
<!-- generated-by: Do not edit! Check out the file %{filepath} in the repo -->
```

### Publishing a single page

*md2conf* has two modes of operation: *single-page mode* and *directory mode*.

In single-page mode, you specify a single Markdown file as the source, which can contain absolute links to external locations (e.g. `https://example.com`) but not relative links to other pages (e.g. `local.md`). In other words, the page must be stand-alone.

### Publishing a directory

*md2conf* allows you to convert and publish a directory of Markdown files rather than a single Markdown file in *directory mode* if you pass a directory as the source. This will traverse the specified directory recursively, and synchronize each Markdown file.

First, *md2conf* builds an index of pages in the directory hierarchy. The index maps each Markdown file path to a Confluence page ID. Whenever a relative link is encountered in a Markdown file, the relative link is replaced with a Confluence URL to the referenced page with the help of the index. All relative links must point to Markdown files that are located in the directory hierarchy.

If a Markdown file doesn't yet pair up with a Confluence page, *md2conf* creates a new page and assigns a parent. Parent-child relationships are reflected in the navigation panel in Confluence. You can set a root page ID with the command-line option `-r`, which constitutes the topmost parent. (This could correspond to the landing page of your Confluence space. The Confluence page ID is always revealed when you edit a page.) Whenever a directory contains the file `index.md` or `README.md`, this page becomes the future parent page, and all Markdown files in this directory (and possibly nested directories) become its child pages (unless they already have a page ID). However, if an `index.md` or `README.md` file is subsequently found in one of the nested directories, it becomes the parent page of that directory, and any of its subdirectories.

The top-level directory to be synchronized must always have an `index.md` or `README.md`, which maps to the root of the corresponding sub-tree in Confluence (specified with `-r`).

The concepts above are illustrated in the following sections.

#### File-system directory hierarchy

The title of each Markdown file (either the text of the topmost unique heading (`#`), or the title specified in front-matter) is shown next to the file name. `docs` is the top-level directory to be synchronized.

```
docs
├── index.md: Root page
├── computer-science
│   ├── index.md: Introduction to computer science
│   ├── algebra.md: Linear algebra
│   └── algorithms.md: Theory of algorithms
├── machine-learning
│   ├── README.md: AI and ML
│   ├── awareness.md: Consciousness and intelligence
│   └── statistics
│       ├── index.md: Introduction to statistics
│       └── median.md: Mean vs. median
└── ethics.md: Ethical considerations
```

#### Page hierarchy in Confluence

Observe how `index.md` and `README.md` files have assumed parent (or ancestor) role for any Markdown files in the same directory (or below).

```
Root page
├── Introduction to computer science
│   ├── Linear algebra
│   └── Theory of algorithms
├── AI and ML
│   ├── Consciousness and intelligence
│   └── Introduction to statistics
│       └── Mean vs. median
└── Ethical considerations
```

### Subscript and superscript

Subscripts may either use the character *tilde* (e.g. `CH~3~CH~2~OH`) or the HTML tag `<sub>`.

Superscripts may either use the character *caret* (e.g. `e^-ix^`) or the HTML tag `<sup>`.

### Emoji

The short name notation `:smile:` in a Markdown document is converted into the corresponding emoji 😄 when publishing to Confluence.

*md2conf* relies on the [Emoji extension](https://facelessuser.github.io/pymdown-extensions/extensions/emoji/) of [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/) to parse the short name notation with colons, and generate Confluence Storage Format output such as

```xml
<ac:emoticon ac:name="smile" ac:emoji-shortname=":smile:" ac:emoji-id="1f604" ac:emoji-fallback="&#128516;"/>
```

### Colors

Confluence allows setting text color and highlight color. Even though Markdown doesn't directly support colors, it is possible to set text and highlight color via the HTML element `<span>` and the CSS attributes `color` and `background-color`, respectively:

Text in <span style="color: rgb(255,86,48);">red</span>, <span style="color: rgb(54,179,126);">green</span> and <span style="color: rgb(76,154,255);">blue</span>:

```markdown
Text in <span style="color: rgb(255,86,48);">red</span>, <span style="color: rgb(54,179,126);">green</span> and <span style="color: rgb(76,154,255);">blue</span>.
```

Highlight in <span style="background-color: rgb(198,237,251);">teal</span>, <span style="background-color: rgb(211,241,167);">lime</span> and <span style="background-color: rgb(254,222,200);">yellow</span>:

```markdown
Highlight in <span style="background-color: rgb(198,237,251);">teal</span>, <span style="background-color: rgb(211,241,167);">lime</span> and <span style="background-color: rgb(254,222,200);">yellow</span>.
```

Highlighting is also supported via `==marks==`. However, the background color is not customizable.

The following table shows standard text colors (CSS `color`) that are available via Confluence UI:

| Color name    | CSS attribute value |
| :------------ | :------------------ |
| bold blue     | rgb(7,71,166)       |
| blue          | rgb(76,154,255)     |
| subtle blue   | rgb(179,212,255)    |
| bold teal     | rgb(0,141,166)      |
| teal          | rgb(0,184,217)      |
| subtle teal   | rgb(179,245,255)    |
| bold green    | rgb(0,102,68)       |
| green         | rgb(54,179,126)     |
| subtle green  | rgb(171,245,209)    |
| bold orange   | rgb(255,153,31)     |
| yellow        | rgb(255,196,0)      |
| subtle yellow | rgb(255,240,179)    |
| bold red      | rgb(191,38,0)       |
| red           | rgb(255,86,48)      |
| subtle red    | rgb(255,189,173)    |
| bold purple   | rgb(64,50,148)      |
| purple        | rgb(101,84,192)     |
| subtle purple | rgb(234,230,255)    |

The following table shows standard highlight colors (CSS `background-color`) that are available via Confluence UI:

| Color name    | CSS attribute value |
| ------------- | ------------------- |
| teal          | rgb(198,237,251)    |
| lime          | rgb(211,241,167)    |
| yellow        | rgb(254,222,200)    |
| magenta       | rgb(253,208,236)    |
| purple        | rgb(223,216,253)    |

### Lists and tables

If your Markdown lists or tables don't appear in Confluence as expected, verify that the list or table is delimited by a blank line both before and after, as per strict Markdown syntax. While some previewers accept a more lenient syntax (e.g. an itemized list immediately following a paragraph), *md2conf* uses [Python-Markdown](https://python-markdown.github.io/) internally to convert Markdown into XHTML, which expects the Markdown document to adhere to the stricter syntax.

Likewise, if you have a nested list, make sure that nested items are indented by exactly ***four*** spaces as compared to the parent node:

```markdown
1. List item 1
    * Nested item 1
        1. Item 1
        2. Item 2
    * Nested item 2
        - Item 3
        - Item 4
2. List item 2
    1. Nested item 3
    2. Nested item 4
```

### Publishing images

Local images referenced in a Markdown file are automatically published to Confluence as attachments to the page.

* Relative paths (e.g. `path/to/image.png` or `../to/image.png`) resolve to absolute paths w.r.t. the Markdown document location.
* Absolute paths (e.g. `/path/to/image.png`) are interpreted w.r.t. to the synchronization root (typically the shell current directory).

As a security measure, resolved paths can only reference files that are in the directory hierarchy of the synchronization root; you can't use `..` to leave the top-level directory of the synchronization root.

Unfortunately, Confluence struggles with SVG images, e.g. they may only show in *edit* mode, display in a wrong size or text labels in the image may be truncated. (This seems to be a known issue in Confluence.) In order to mitigate the issue, whenever *md2conf* encounters a reference to an SVG image in a Markdown file, it checks whether a corresponding PNG image also exists in the same directory, and if a PNG image is found, it is published instead.

External images referenced with an absolute URL retain the original URL.

### LaTeX math formulas

Inline formulas can be enclosed with `$` signs, or delimited with `\(` and `\)`, i.e.

* the code `$\sum_{i=1}^{n} i = \frac{n(n+1)}{2}$` is shown as $\sum_{i=1}^{n} i = \frac{n(n+1)}{2}$,
* and `\(\lim _{x\rightarrow \infty }\frac{1}{x}=0\)` is shown as $\lim _{x\rightarrow \infty }\frac{1}{x}=0$.

Block formulas can be enclosed with `$$`, or wrapped in code blocks specifying the language `math`:

```markdown
$$\int _{a}^{b}f(x)dx=F(b)-F(a)$$
```

is shown as

$$\int _{a}^{b}f(x)dx=F(b)-F(a)$$

Displaying math formulas in Confluence requires the extension [LaTeX Math for Confluence - Math Formula & Equations](https://help.narva.net/latex-math-for-confluence/).

### HTML in Markdown

*md2conf* relays HTML elements nested in Markdown content to Confluence (such as `e<sup>x</sup>` for superscript). However, Confluence uses an extension of XHTML, i.e. the content must qualify as valid XML too. In particular, unterminated tags (e.g. `<br>` or `<img ...>`) or inconsistent nesting (e.g. `<b><i></b></i>`) are not permitted, and will raise an XML parsing error. When an HTML element has no content such as `<br>` or `<img>`, use a self-closing tag:

```html
<br/>
<img src="image.png" width="24" height="24" />
```

### Confluence widgets

*md2conf* supports some Confluence widgets. If the appropriate code is found when a Markdown document is processed, it is automatically replaced with Confluence Storage Format XML that produces the corresponding widget.

| Markdown code                              | Confluence equivalent                                   |
| :----------------------------------------- | :------------------------------------------------------ |
| `[[_TOC_]]`                                | table of contents (based on headings)                   |
| `[[_LISTING_]]`                            | child pages (of current page)                           |
| `![My label][STATUS-GRAY]`                 | gray status label (with specified label text)           |
| `![My label][STATUS-PURPLE]`               | purple status label                                     |
| `![My label][STATUS-BLUE]`                 | blue status label                                       |
| `![My label][STATUS-RED]`                  | red status label                                        |
| `![My label][STATUS-YELLOW]`               | yellow status label                                     |
| `![My label][STATUS-GREEN]`                | green status label                                      |
| `<input type="date" value="YYYY-MM-DD" />` | date widget (with year, month and day set as specified) |

Use the pseudo-language `csf` in a Markdown code block to pass content directly to Confluence. The content must be a single XML node that conforms to Confluence Storage Format (typically an `ac:structured-macro`) but is otherwise not validated. The following example shows how to create a panel similar to an *info panel* but with custom background color and emoji. Notice that `ac:rich-text-body` uses XHTML, not Markdown.

````markdown
```csf
<ac:structured-macro ac:name="panel" ac:schema-version="1">
  <ac:parameter ac:name="panelIcon">:slight_smile:</ac:parameter>
  <ac:parameter ac:name="panelIconId">1f642</ac:parameter>
  <ac:parameter ac:name="panelIconText">&#128578;</ac:parameter>
  <ac:parameter ac:name="bgColor">#FFF0B3</ac:parameter>
  <ac:rich-text-body>
    <p>A <em>custom colored panel</em> with a 🙂 emoji</p>
  </ac:rich-text-body>
</ac:structured-macro>
```
````

### Ignoring files

Skip files and subdirectories in a directory with rules defined in `.mdignore`. Each rule should occupy a single line. Rules follow the syntax (and constraints) of [fnmatch](https://docs.python.org/3/library/fnmatch.html#fnmatch.fnmatch). Specifically, `?` matches any single character, and `*` matches zero or more characters. For example, use `up-*.md` to exclude Markdown files that start with `up-`. Lines that start with `#` are treated as comments.

Files that don't have the extension `*.md` are skipped automatically. Hidden directories (whose name starts with `.`) are not recursed into. To skip an entire directory, add the name of the directory without a trailing `/`.

Relative paths to items in a nested directory are not supported. You must put `.mdignore` in the same directory where the items to be skipped reside.

If you add the `synchronized` attribute to JSON or YAML front-matter with the value `false`, the document content (including attachments) and metadata (e.g. tags) will not be synchronized with Confluence:

```yaml
---
title: "Collaborating with other teams"
page_id: "19830101"
synchronized: false
---

This Markdown document is neither parsed, nor synchronized with Confluence.
```

This is useful if you have a page in a hierarchy that participates in parent-child relationships but whose content is edited directly in Confluence. Specifically, these documents can be referenced with relative links from other Markdown documents in the file system tree.

### Page title

*md2conf* makes a best-effort attempt at setting the Confluence wiki page title when it publishes a Markdown document the first time. The following act as sources for deriving a page title:

1. The `title` attribute set in the [front-matter](https://daily-dev-tips.com/posts/what-exactly-is-frontmatter/). Front-matter is a block delimited by `---` at the beginning of a Markdown document. Both JSON and YAML syntax are supported.
2. The text of the topmost unique Markdown heading (`#`). For example, if a document has a single first-level heading (e.g. `# My document`), its text is used. However, if there are multiple first-level headings, this step is skipped.
3. The file name (without the extension `.md`) and a digest. The digest is included to ensure the title is unique across the Confluence space.

If the `title` attribute (in the front-matter) or the topmost unique heading (in the document body) changes, the Confluence page title is updated. A warning is raised if the new title conflicts with the title of another page, and thus cannot be updated.

#### Avoiding duplicate titles

By default, when *md2conf* extracts a page title from the first unique heading in a Markdown document, the heading remains in the document body. This means the title appears twice on the Confluence page: once as the page title at the top, and once as the first heading in the content.

To avoid this duplication, use the `--skip-title-heading` option. When enabled, *md2conf* removes the first heading from the document body if it was used as the page title. This option only takes effect when:

1. The title was extracted from the document's first unique heading (not from front-matter), AND
2. There is exactly one top-level heading in the document.

If the title comes from the `title` attribute in front-matter, the heading is preserved in the document body regardless of this setting, as the heading and title are considered separate.

**Example without `--skip-title-heading` (default):**

Markdown:
```markdown
# Installation Guide

Follow these steps...
```

Confluence displays:
- Page title: "Installation Guide"
- Content: Starts with heading "Installation Guide", followed by "Follow these steps..."

**Example with `--skip-title-heading`:**

Same Markdown source, but Confluence displays:
- Page title: "Installation Guide"
- Content: Starts directly with "Follow these steps..." (heading removed)

**Edge case: Abstract or introductory text before the title:**

When a document has content before the first heading (like an abstract), removing the heading eliminates the visual separator between the introductory text and the main content:

```markdown
This is an abstract paragraph providing context.

# Document Title

This is the main document content.
```

With `--skip-title-heading`, the output becomes:
- Page title: "Document Title"
- Content: "This is an abstract paragraph..." flows directly into "This is the main document content..." (no heading separator)

While the structure remains semantically correct, the visual separation is lost. If you need to maintain separation, consider these workarounds:

1. **Use a horizontal rule:** Add `---` after the abstract to create visual separation
2. **Use an admonition block:** Wrap the abstract in an info/note block
3. **Use front-matter title:** Set `title` in front-matter to keep the heading in the body

### Labels

If a Markdown document has the front-matter attribute `tags`, *md2conf* assigns the specified tags to the Confluence page as labels.

```yaml
---
title: "Example document"
tags: ["markdown", "md", "wiki"]
---
```

Any previously assigned labels are discarded. As per Confluence terminology, new labels have the `prefix` of `global`.

If a document has no `tags` attribute, existing Confluence labels are left intact.

### Content properties

The front-matter attribute `properties` in a Markdown document allows setting Confluence content properties on a page. Confluence content properties are a way to store structured metadata in the form of key-value pairs directly on Confluence content. The values in content properties are represented as JSON objects.

Some content properties have special meaning to Confluence. For example, the following properties cause Confluence to display a wiki page with content confined to a fixed width in regular view mode, and taking the full page width in draft mode:

```yaml
---
properties:
  content-appearance-published: fixed-width
  content-appearance-draft: full-width
---
```

The attribute `properties` is parsed as a dictionary with keys of type string and values of type JSON. *md2conf* passes JSON values to Confluence REST API unchanged.

### draw\.io diagrams

With the command-line option `--no-render-drawio` (default), editable diagram data is extracted from images with embedded draw\.io diagrams (`*.drawio.png` and `*.drawio.svg`), and uploaded to Confluence as attachments. Files that match `*.drawio` or `*.drawio.xml` are uploaded as-is. You need a [marketplace app](https://marketplace.atlassian.com/apps/1210933/draw-io-diagrams-uml-bpmn-aws-erd-flowcharts) to view and edit these diagrams on a Confluence page.

With the command-line option `--render-drawio`, images with embedded draw\.io diagrams (`*.drawio.png` and `*.drawio.svg`) are uploaded unchanged, and shown on the Confluence page as images. These diagrams are not editable in Confluence. When both an SVG and a PNG image is available, PNG is preferred. Files that match `*.drawio` or `*.drawio.xml` are converted into PNG or SVG images by invoking draw\.io as a command-line utility, and the generated images are uploaded to Confluence as attachments, and shown as images.

### Mermaid diagrams

You can add [Mermaid diagrams](https://mermaid.js.org/) to your Markdown documents to create visual representations of systems, processes, and relationships. There are two ways to include a Mermaid diagram:

* an image reference to a `.mmd` or `.mermaid` file, i.e. `![My diagram](figure/diagram.mmd)`, or
* a fenced code block with the language specifier `mermaid`.

*md2conf* offers two options to publish the diagram:

1. Pre-render into an image (command-line option `--render-mermaid`). The source file or code block is interpreted by and converted into a PNG or SVG image with the Mermaid diagram utility [mermaid-cli](https://github.com/mermaid-js/mermaid-cli). The generated image is then uploaded to Confluence as an attachment to the page.
2. Display on demand (command-line option `--no-render-mermaid`). The code block is transformed into a [diagram macro](https://stratus-addons.atlassian.net/wiki/spaces/MDFC/overview), which is processed by Confluence. You need a separate [marketplace app](https://marketplace.atlassian.com/apps/1226567/mermaid-diagrams-for-confluence) to turn macro definitions into images when a Confluence page is visited.

If you are running into issues with the pre-rendering approach (e.g. misaligned labels in the generated image), verify if `mermaid-cli` can process the Mermaid source:

```sh
mmdc -i sample.mmd -o sample.png -b transparent --scale 2
```

Ensure that `mermaid-cli` is set up, refer to *Installation* for instructions.

Note that `mermaid-cli` has some implicit dependencies (e.g. a headless browser) that may not be immediately available in a CI/CD environment such as GitHub Actions. Refer to the `Dockerfile` in the *md2conf* project root, or [mermaid-cli documentation](https://github.com/mermaid-js/mermaid-cli) on how to install these dependencies such as a `chromium-browser` and various fonts.

### Alignment

You can configure diagram and image alignment using the JSON/YAML front-matter attribute `alignment` or the command-line argument of the same name. Possible values are `center` (default), `left` and `right`. The value configured in the Markdown file front-matter takes precedence.

Unfortunately, not every third-party app supports every alignment variant. For example, the draw\.io marketplace app supports left and center but not right alignment; and diagrams produced by the Mermaid marketplace app are always centered, ignoring the setting for alignment.

### Links to attachments

If *md2conf* encounters a Markdown link that points to a file in the directory hierarchy being synchronized, it automatically uploads the file as an attachment to the Confluence page. Activating the link in Confluence downloads the file. Typical examples include PDFs (`*.pdf`), word processor documents (`*.docx`), spreadsheets (`*.xlsx`), plain text files (`*.txt`) or logs (`*.log`). The MIME type is set based on the file type.

### Implicit URLs

*md2conf* implicitly defines some URLs, as if you included the following at the start of the Markdown document for each URL:

```markdown
[CUSTOM-URL]: https://example.com/path/to/resource
```

Specifically, image references for status labels (e.g. `![My label][STATUS-RED]`) are automatically resolved into internally defined URLs via this mechanism.

### Local output

*md2conf* supports local output, in which the tool doesn't communicate with the Confluence REST API. Instead, it reads a single Markdown file or a directory of Markdown files, and writes Confluence Storage Format (`*.csf`) output for each document. (Confluence Storage Format is a derivative of XHTML with Confluence-specific tags for complex elements such as images with captions, code blocks, info panels, collapsed sections, etc.) You can push the generated output to Confluence by invoking the API (e.g. with `curl`).

### Running the tool

#### Command line

You can synchronize a (directory of) Markdown file(s) with Confluence using the command-line tool `md2conf`:

```sh
$ python3 -m md2conf sample/index.md
```

Use the `--help` switch to get a full list of supported command-line options:

```console
$ python3 -m md2conf --help
usage: md2conf mdpath [OPTIONS]

positional arguments:
  mdpath                Path to Markdown file or directory to convert and publish.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -d, --domain DOMAIN   Confluence organization domain.
  -p, --path PATH       Base path for Confluence (default: '/wiki/').
  --api-url API_URL     Confluence API URL. Required for scoped tokens. Refer to documentation how to obtain one.
  -u, --username USERNAME
                        Confluence user name.
  -a, --api-key API_KEY
                        Confluence API key. Refer to documentation how to obtain one.
  -s, --space SPACE     Confluence space key for pages to be published. If omitted, will default to user space.
  -l, --loglevel {debug,info,warning,error,critical}
                        Use this option to set the log verbosity.
  -r ROOT_PAGE          Root Confluence page to create new pages. If omitted, will raise exception when creating new pages.
  --keep-hierarchy      Maintain source directory structure when exporting to Confluence.
  --flatten-hierarchy   Flatten directories with no index.md or README.md when exporting to Confluence.
  --generated-by MARKDOWN
                        Add prompt to pages (default: 'This page has been generated with a tool.').
  --no-generated-by     Do not add 'generated by a tool' prompt to pages.
  --render-drawio       Render draw.io diagrams as image files. (Installed utility required to covert.)
  --no-render-drawio    Upload draw.io diagram sources as Confluence page attachments. (Marketplace app required to display.)
  --render-mermaid      Render Mermaid diagrams as image files. (Installed utility required to convert.)
  --no-render-mermaid   Upload Mermaid diagram sources as Confluence page attachments. (Marketplace app required to display.)
  --render-plantuml     Render PlantUML diagrams as image files. (Installed utility required to convert.)
  --no-render-plantuml  Upload PlantUML diagram sources as Confluence page attachments. (Marketplace app required to display.)
  --render-latex        Render LaTeX formulas as image files. (Matplotlib required to convert.)
  --no-render-latex     Inline LaTeX formulas in Confluence page. (Marketplace app required to display.)
  --diagram-output-format {png,svg}
                        Format for rendering Mermaid and draw.io diagrams (default: 'png').
  --prefer-raster       Prefer PNG over SVG when both exist (default: enabled).
  --no-prefer-raster    Use SVG files directly instead of preferring PNG equivalents.
  --heading-anchors     Place an anchor at each section heading with GitHub-style same-page identifiers.
  --no-heading-anchors  Don't place an anchor at each section heading.
  --ignore-invalid-url  Emit a warning but otherwise ignore relative URLs that point to ill-specified locations.
  --skip-title-heading  Skip the first heading from document body when it is used as the page title (does not apply if title comes from front-matter).
  --no-skip-title-heading
                        Keep the first heading in document body even when used as page title (default).
  --title-prefix TEXT   String to prepend to Confluence page title for each published page.
  --webui-links         Enable Confluence Web UI links. (Typically required for on-prem versions of Confluence.)
  --alignment {center,left,right}
                        Alignment for block-level images and formulas (default: 'center').
  --max-image-width MAX_IMAGE_WIDTH
                        Maximum display width for images [px]. Wider images are scaled down for page display. Original size kept for full-size viewing.
  --use-panel           Transform admonitions and alerts into a Confluence custom panel.
  --local               Write XHTML-based Confluence Storage Format files locally without invoking Confluence API.
  --headers KEY=VALUE [KEY=VALUE ...]
                        Apply custom headers to all Confluence API requests.
```

#### Python

*md2conf* has a Python interface. Create a `ConnectionProperties` object to set connection parameters to the Confluence server, and a `DocumentOptions` object to configure how Markdown files are converted into pages on a Confluence wiki site. Open a connection to the Confluence server with the context manager `ConfluenceAPI`, and instantiate a `Publisher` to start converting documents.

```python
from md2conf.api import ConfluenceAPI
from md2conf.environment import ConnectionProperties
from md2conf.options import ConverterOptions, DocumentOptions, ImageLayoutOptions, LayoutOptions, TableLayoutOptions
from md2conf.publisher import Publisher

properties = ConnectionProperties(
    api_url=...,
    domain=...,
    base_path=...,
    user_name=...,
    api_key=...,
    space_key=...,
    headers=...,
)
options = DocumentOptions(
    root_page_id=...,
    keep_hierarchy=...,
    title_prefix=...,
    generated_by=...,
    converter=ConverterOptions(
        heading_anchors=...,
        ignore_invalid_url=...,
        skip_title_heading=...,
        prefer_raster=...,
        render_drawio=...,
        render_mermaid=...,
        render_plantuml=...,
        render_latex=...,
        diagram_output_format=...,
        webui_links=...,
        use_panel=...,
        layout=LayoutOptions(
            image=ImageLayoutOptions(
                alignment=...,
                max_width=...,
            ),
            table=TableLayoutOptions(
                width=...,
                display_mode=...,
            ),
        ),
    ),
)
with ConfluenceAPI(properties) as api:
    Publisher(api, options).process(mdpath)
```

### Confluence REST API v1 vs. v2

*md2conf* version 0.3.0 has switched to using [Confluence REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/) for API calls such as retrieving current page content. Earlier versions used [Confluence REST API v1](https://developer.atlassian.com/cloud/confluence/rest/v1/) exclusively. Unfortunately, Atlassian has decommissioned Confluence REST API v1 for several endpoints in Confluence Cloud as of due date March 31, 2025, and we don't have access to an environment where we could test retired v1 endpoints.

If you are restricted to an environment with Confluence REST API v1, we recommend *md2conf* [version 0.2.7](https://pypi.org/project/markdown-to-confluence/0.2.7/). Even though we don't actively support it, we are not aware of any major issues, making it a viable option in an on-premise environment with only Confluence REST API v1 support.

### Using the Docker container

You can run the Docker container via `docker run` or via `Dockerfile`. Either can accept the environment variables or arguments similar to the Python options. The final argument `./` corresponds to `mdpath` in the command-line utility.

With `docker run`, you can pass Confluence domain, user, API and space key directly to `docker run`:

```sh
docker run --rm --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest -d example.atlassian.net -u levente.hunyadi@instructure.com -a 0123456789abcdef -s SPACE ./
```

Alternatively, you can use a separate file `.env` to pass these parameters as environment variables:

```sh
docker run --rm --env-file .env --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest ./
```

In each case, `-v $(pwd):/data` maps the current directory to Docker container's `WORKDIR` such *md2conf* can scan files and directories in the local file system.

Note that the entry point for the Docker container's base image is `ENTRYPOINT ["python3", "-m", "md2conf"]`.

With the `Dockerfile` approach, you can extend the base image:

```Dockerfile
FROM leventehunyadi/md2conf:latest

ENV CONFLUENCE_DOMAIN='example.atlassian.net'
ENV CONFLUENCE_PATH='/wiki/'
ENV CONFLUENCE_USER_NAME='levente.hunyadi@instructure.com'
ENV CONFLUENCE_API_KEY='0123456789abcdef'
ENV CONFLUENCE_SPACE_KEY='SPACE'

CMD ["./"]
```

Alternatively,

```Dockerfile
FROM leventehunyadi/md2conf:latest

CMD ["-d", "example.atlassian.net", "-u", "levente.hunyadi@instructure.com", "-a", "0123456789abcdef", "-s", "SPACE", "./"]
```
