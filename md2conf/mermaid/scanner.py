"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass

from md2conf.frontmatter import extract_frontmatter_object

from .config import MermaidConfigProperties


@dataclass
class MermaidProperties:
    """
    An object that holds the front-matter properties structure for Mermaid diagrams.

    :param title: The title of the diagram.
    :param config: Configuration options for rendering.
    """

    title: str | None = None
    config: MermaidConfigProperties | None = None


class MermaidScanner:
    """
    Extracts properties from the JSON/YAML front-matter of a Mermaid diagram.
    """

    def read(self, content: str) -> MermaidProperties:
        """
        Extracts rendering preferences from a Mermaid front-matter content.

        ```
        ---
        title: Tiny flow diagram
        config:
            scale: 1
        ---
        flowchart LR
            A[Component A] --> B[Component B]
            B --> C[Component C]
        ```
        """

        properties, _ = extract_frontmatter_object(MermaidProperties, content)
        if properties is not None:
            config = properties.config or MermaidConfigProperties()
            return MermaidProperties(title=properties.title, config=config)

        return MermaidProperties()
