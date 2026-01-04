"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass

from md2conf.frontmatter import extract_frontmatter_object

from .config import PlantUMLConfigProperties


@dataclass
class PlantUMLProperties:
    """
    An object that holds the front-matter properties structure
    for PlantUML diagrams.

    :param title: The title of the diagram.
    :param config: Configuration options for rendering.
    """

    title: str | None = None
    config: PlantUMLConfigProperties | None = None


class PlantUMLScanner:
    """
    Extracts properties from the JSON/YAML front-matter of a PlantUML diagram.
    """

    def read(self, content: str) -> PlantUMLProperties:
        """
        Extracts rendering preferences from a PlantUML front-matter content.

        ```
        ---
        title: Class diagram
        config:
            scale: 1
        ---
        @startuml
        class Example
        @enduml
        ```
        """

        properties, _ = extract_frontmatter_object(PlantUMLProperties, content)
        if properties is not None:
            config = properties.config or PlantUMLConfigProperties()
            return PlantUMLProperties(title=properties.title, config=config)

        return PlantUMLProperties()
