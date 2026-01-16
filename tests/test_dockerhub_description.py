import os
import tempfile
import unittest

from util.dockerhub_description import TARGET_MAPPING, get_bake_targets, get_template_placeholders


class TestDockerHubDescription(unittest.TestCase):
    def test_get_bake_targets(self) -> None:
        content = """
target "base" {
  tags = ["foo"]
}
target "mermaid" {
}
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            targets = get_bake_targets(temp_path)
            self.assertIn("base", targets)
            self.assertIn("mermaid", targets)
            self.assertEqual(len(targets), 2)
        finally:
            os.remove(temp_path)

    def test_get_template_placeholders(self) -> None:
        content = """
# Title %{GIT_TAG}
| Row | %{TAGS_BASE} |
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            placeholders = get_template_placeholders(temp_path)
            self.assertIn("GIT_TAG", placeholders)
            self.assertIn("TAGS_BASE", placeholders)
            self.assertEqual(len(placeholders), 2)
        finally:
            os.remove(temp_path)

    def test_target_mapping_completeness(self) -> None:
        # Ensure all known targets have a mapping
        known_targets = ["base", "mermaid", "plantuml", "all"]
        for t in known_targets:
            self.assertIn(t, TARGET_MAPPING)


if __name__ == "__main__":
    unittest.main()
