"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
import os.path
import re
import unittest
from dataclasses import dataclass
from pathlib import Path

from md2conf.attachment import attachment_name
from md2conf.collection import ConfluencePageCollection
from md2conf.compatibility import override
from md2conf.converter import ConfluenceDocument
from md2conf.csf import elements_from_string, elements_to_string
from md2conf.latex import LATEX_ENABLED
from md2conf.matcher import Matcher, MatcherOptions
from md2conf.mermaid.render import has_mmdc
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.options import ConverterOptions, DocumentOptions, ImageLayoutOptions, LayoutOptions
from md2conf.plantuml.render import compress_plantuml_data, has_plantuml, render_diagram
from md2conf.svg import get_svg_dimensions_from_bytes
from tests import emoji
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


def canonicalize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format."

    root = elements_from_string(content)
    return elements_to_string(root)


@dataclass
class Dimensions:
    width: int | None
    height: int | None


def substitute(root_dir: Path, content: str) -> str:
    "Converts a Confluence Storage Format (CSF) expectation template into a concrete match."

    def _repl_embed(m: re.Match[str]) -> str:
        "Replaces an embedding placeholder with the concrete attachment file name computed using a hash algorithm."

        relative_path = m.group(1)
        absolute_path = root_dir / relative_path
        with open(absolute_path, "r", encoding="utf-8") as f:
            file_content = f.read().rstrip()
        hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
        extension = absolute_path.suffix if absolute_path.suffix != ".puml" else ".svg"
        return attachment_name(f"embedded_{hash}{extension}")

    embed_pattern = re.compile(r"EMBED\(([^()]+)\)")
    content = embed_pattern.sub(_repl_embed, content)

    def _repl_data(m: re.Match[str]) -> str:
        "Replaces a DATA placeholder with compressed PlantUML source."

        relative_path = m.group(1)
        absolute_path = root_dir / relative_path
        with open(absolute_path, "r", encoding="utf-8") as f:
            file_content = f.read().rstrip()
        return compress_plantuml_data(file_content)

    data_pattern = re.compile(r"DATA\(([^()]+)\)")
    content = data_pattern.sub(_repl_data, content)

    dims_cache: dict[Path, Dimensions] = {}

    def _repl_dimensions(m: re.Match[str]) -> str:
        "Replaces WIDTH/HEIGHT placeholders with actual SVG dimensions."

        relative_path = m.group(2)
        absolute_path = root_dir / relative_path

        dims = dims_cache.get(absolute_path)
        if dims is not None:
            width = dims.width
            height = dims.height
        else:
            with open(absolute_path, "r", encoding="utf-8") as f:
                file_content = f.read().rstrip()
            svg_data = render_diagram(file_content, "svg")
            width, height = get_svg_dimensions_from_bytes(svg_data)
            dims_cache[absolute_path] = Dimensions(width, height)

        dimension_type = m.group(1)  # "WIDTH" or "HEIGHT"
        match dimension_type:
            case "WIDTH":
                return str(width)
            case "HEIGHT":
                return str(height)
            case _:
                return dimension_type  # return placeholder

    if has_plantuml():
        dimension_pattern = re.compile(r"(WIDTH|HEIGHT)\(([^()]+)\)")
        content = dimension_pattern.sub(_repl_dimensions, content)
    else:
        plantuml_pattern = re.compile(r"<!-- if plantuml -->.*?<!-- endif plantuml -->", re.DOTALL)
        content = plantuml_pattern.sub("", content)

    return canonicalize(content)


def standardize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format, removing unique identifiers."

    uuid_pattern = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F-]{36})(?![0-9a-fA-F])")
    content = uuid_pattern.sub("UUID", content)

    return canonicalize(content)


class TestConversion(TypedTestCase):
    source_dir: Path
    target_dir: Path
    site_metadata: ConfluenceSiteMetadata

    @override
    def setUp(self) -> None:
        self.maxDiff = None

        test_dir = Path(__file__).parent
        self.source_dir = test_dir / "source"
        self.target_dir = test_dir / "target"
        self.site_metadata = ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY")
        self.page_metadata = ConfluencePageCollection()

    def test_markdown(self) -> None:
        emoji.generate_source(self.source_dir / "emoji.md")
        emoji.generate_target(self.target_dir / "emoji.xml")

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), self.source_dir)

        entries: list[os.DirEntry[str]] = []
        for entry in os.scandir(self.source_dir):
            if entry.is_dir():
                continue

            if matcher.is_excluded(entry):
                continue

            entries.append(entry)

        entries.sort(key=lambda e: e.name)
        for entry in entries:
            name, _ = os.path.splitext(entry.name)

            with self.subTest(name=name):
                _, doc = ConfluenceDocument.create(
                    self.source_dir / f"{name}.md",
                    DocumentOptions(converter=ConverterOptions(prefer_raster=False, render_drawio=True)),
                    self.source_dir,
                    self.site_metadata,
                    self.page_metadata,
                )
                actual = standardize(doc.xhtml())

                with open(self.target_dir / f"{name}.xml", "r", encoding="utf-8") as f:
                    expected = substitute(self.target_dir, f.read())

                self.assertEqual(actual, expected)

    def test_admonitions(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "admonition.md",
            DocumentOptions(converter=ConverterOptions(use_panel=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Admonitions")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "panel.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_broken_links(self) -> None:
        with self.assertLogs(level=logging.WARNING) as cm:
            _, doc = ConfluenceDocument.create(
                self.source_dir / "missing.md",
                DocumentOptions(converter=ConverterOptions(ignore_invalid_url=True)),
                self.source_dir,
                self.site_metadata,
                self.page_metadata,
            )
            self.assertEqual(doc.title, "Broken links")
            actual = standardize(doc.xhtml())

        # check if 2 broken links have been found (anchor `href` & image `src`)
        self.assertEqual(len(cm.records), 5)

        with open(self.target_dir / "missing.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_heading_anchors(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "anchors.md",
            DocumentOptions(converter=ConverterOptions(heading_anchors=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Anchors")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "anchors.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_images(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "images" / "images.md",
            DocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "images" / "images.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_missing_title(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "title.md",
            DocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertIsNone(doc.title)

    def test_unique_title(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "sections.md",
            DocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Sections")

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    @unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
    def test_mermaid_embedded_svg(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "mermaid.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_mermaid=True,
                    diagram_output_format="svg",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        figure_dir = self.target_dir / "mermaid"
        self.assertEqual(len(document.embedded_files), sum(1 for _ in figure_dir.glob("*.mmd")))

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    @unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
    def test_mermaid_embedded_png(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "mermaid.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_mermaid=True,
                    diagram_output_format="png",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        figure_dir = self.target_dir / "mermaid"
        self.assertEqual(len(document.embedded_files), sum(1 for _ in figure_dir.glob("*.mmd")))

    @unittest.skipUnless(has_plantuml(), "plantuml is not available")
    @unittest.skipUnless(os.getenv("TEST_PLANTUML"), "plantuml tests are disabled")
    def test_plantuml_embedded_svg(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "plantuml.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_plantuml=True,
                    diagram_output_format="svg",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        figure_dir = self.target_dir / "plantuml"
        self.assertEqual(len(document.embedded_files), sum(1 for _ in figure_dir.glob("*.puml")))

    @unittest.skipUnless(has_plantuml(), "plantuml is not available")
    @unittest.skipUnless(os.getenv("TEST_PLANTUML"), "plantuml tests are disabled")
    def test_plantuml_embedded_png(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "plantuml.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_plantuml=True,
                    diagram_output_format="png",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        figure_dir = self.target_dir / "plantuml"
        self.assertEqual(len(document.embedded_files), sum(1 for _ in figure_dir.glob("*.puml")))

    @unittest.skipUnless(LATEX_ENABLED, "matplotlib not installed")
    def test_latex_svg(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "math.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_latex=True,
                    diagram_output_format="svg",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 4)

    @unittest.skipUnless(LATEX_ENABLED, "matplotlib not installed")
    def test_latex_png(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "math.md",
            DocumentOptions(
                converter=ConverterOptions(
                    render_latex=True,
                    diagram_output_format="png",
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 4)

    def test_max_image_width(self) -> None:
        "Test that max_image_width constrains display width while preserving original dimensions."
        _, doc = ConfluenceDocument.create(
            self.source_dir / "images.md",
            DocumentOptions(
                converter=ConverterOptions(
                    prefer_raster=False,
                    layout=LayoutOptions(image=ImageLayoutOptions(max_width=100)),
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        xhtml = doc.xhtml()

        # The vector.svg has natural dimensions of 200x200
        # With max_image_width=100, display width should be constrained to 100
        # but original-width should still be 200
        self.assertIn('ac:original-width="200"', xhtml)
        self.assertIn('ac:original-height="200"', xhtml)
        self.assertIn('ac:width="100"', xhtml)

    def test_max_image_width_no_constraint(self) -> None:
        "Test that images smaller than max_image_width are not constrained."
        _, doc = ConfluenceDocument.create(
            self.source_dir / "images.md",
            DocumentOptions(
                converter=ConverterOptions(
                    prefer_raster=False,
                    layout=LayoutOptions(image=ImageLayoutOptions(max_width=500)),
                )
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        xhtml = doc.xhtml()

        # The vector.svg has natural dimensions of 200x200
        # With max_image_width=500, no constraint should be applied
        # so ac:width should equal the natural width
        self.assertIn('ac:original-width="200"', xhtml)
        self.assertIn('ac:width="200"', xhtml)

    def test_generated_by_templated(self) -> None:
        "Test that generated_by option supports templating."
        test_file_path = self.source_dir / "images" / "images.md"
        _, doc = ConfluenceDocument.create(
            test_file_path,
            DocumentOptions(generated_by="File: %{filename} | Path: %{filepath} | Stem: %{filestem} | Dirname: %{filedir}"),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        xhtml = doc.xhtml()
        self.assertIn("File: images.md", xhtml)
        self.assertIn(f"Path: {test_file_path.relative_to(self.source_dir).as_posix()}", xhtml)
        self.assertIn("Stem: images", xhtml)
        self.assertIn("Dirname: images", xhtml)

    def test_skip_title_heading_enabled(self) -> None:
        """Test that the first heading is removed when skip_title_heading is enabled."""
        _, doc = ConfluenceDocument.create(
            self.source_dir / "skip_title_heading.md",
            DocumentOptions(converter=ConverterOptions(skip_title_heading=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Document Title")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "skip_title_heading_removed.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_skip_title_heading_disabled(self) -> None:
        """Test that the first heading is preserved when skip_title_heading is disabled (default)."""
        _, doc = ConfluenceDocument.create(
            self.source_dir / "skip_title_heading.md",
            DocumentOptions(converter=ConverterOptions(skip_title_heading=False)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Document Title")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "skip_title_heading_preserved.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_skip_title_heading_frontmatter(self) -> None:
        """Test that heading is preserved when title comes from front-matter, even with flag enabled."""
        _, doc = ConfluenceDocument.create(
            self.source_dir / "skip_title_heading_frontmatter.md",
            DocumentOptions(converter=ConverterOptions(skip_title_heading=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Title from Front-matter")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "skip_title_heading_frontmatter.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_skip_title_heading_multiple(self) -> None:
        """Test that headings are preserved when there are multiple top-level headings."""
        _, doc = ConfluenceDocument.create(
            self.source_dir / "skip_title_heading_multiple.md",
            DocumentOptions(converter=ConverterOptions(skip_title_heading=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertIsNone(doc.title)  # No unique title can be extracted
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "skip_title_heading_multiple.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_skip_title_heading_abstract(self) -> None:
        """Test that abstract text before heading flows into content when heading is removed."""
        _, doc = ConfluenceDocument.create(
            self.source_dir / "skip_title_heading_abstract.md",
            DocumentOptions(converter=ConverterOptions(skip_title_heading=True)),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Document Title")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "skip_title_heading_abstract_removed.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
