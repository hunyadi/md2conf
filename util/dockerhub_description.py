#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path

# Mapping between docker-bake.hcl targets and DOCKER_HUB.md placeholders
TARGET_MAPPING = {
    "base": "TAGS_BASE",
    "mermaid": "TAGS_MERMAID",
    "plantuml": "TAGS_PLANTUML",
    "all": "TAGS_ALL",
}

TEMPLATE_FILE = Path("DOCKER_HUB.md")
BAKE_FILE = Path("docker-bake.hcl")


def error(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def warn(message: str) -> None:
    """Print warning message to stderr."""
    print(f"Warning: {message}", file=sys.stderr)


def get_bake_targets(file_path: Path) -> set[str]:
    """Extract target names from docker-bake.hcl."""
    targets: set[str] = set()
    if not os.path.exists(file_path):
        return targets

    content = file_path.read_text("utf-8")

    # Look for target "name" { ... }
    matches = re.findall(r'target\s+"([^"]+)"\s+\{', content)
    for m in matches:
        targets.add(m)
    return targets


def get_template_placeholders(file_path: Path) -> set[str]:
    """Extract %{PLACEHOLDER} tokens from the template."""
    placeholders: set[str] = set()
    if not os.path.exists(file_path):
        return placeholders

    content = file_path.read_text("utf-8")

    matches = re.findall(r"%\{([^}]+)\}", content)
    for m in matches:
        placeholders.add(m)
    return placeholders


def validate_sync() -> None:
    """Check if the template is in sync with the bake file."""
    targets = get_bake_targets(BAKE_FILE)
    placeholders = get_template_placeholders(TEMPLATE_FILE)

    missing_placeholders: list[str] = []
    for target in targets:
        placeholder = TARGET_MAPPING.get(target)
        if not placeholder:
            warn(f"Target '{target}' in {BAKE_FILE} has no mapping to a placeholder.")
            continue
        if placeholder not in placeholders:
            missing_placeholders.append(placeholder)

    if missing_placeholders:
        error(f"The following placeholders are missing from {TEMPLATE_FILE}:\n" + "\n".join(f"  - %{{{p}}}" for p in missing_placeholders))
        sys.exit(1)

    print(f"Success: {TEMPLATE_FILE} is in sync with {BAKE_FILE}.")


class Arguments(argparse.Namespace):
    check: bool
    git_tag: str | None
    image_name: str | None
    github_repo: str | None
    github_repo_url: str | None
    tags_base: str | None
    tags_mermaid: str | None
    tags_plantuml: str | None
    tags_all: str | None
    output: str


def generate_description(args: Arguments) -> None:
    """Generate the final description by replacing placeholders."""
    if not os.path.exists(TEMPLATE_FILE):
        error(f"{TEMPLATE_FILE} not found.")
        sys.exit(1)

    with open(TEMPLATE_FILE, "r") as f:
        content = f.read()

    # Required metadata placeholders
    replacements = {
        "GIT_TAG": args.git_tag,
        "DOCKER_IMAGE_NAME": args.image_name,
        "GITHUB_REPOSITORY": args.github_repo,
        "GITHUB_REPO_URL": args.github_repo_url,
        "TAGS_BASE": args.tags_base,
        "TAGS_MERMAID": args.tags_mermaid,
        "TAGS_PLANTUML": args.tags_plantuml,
        "TAGS_ALL": args.tags_all,
    }

    for key, value in replacements.items():
        if value is not None:
            content = content.replace(f"%{{{key}}}", value)

    with open(args.output, "w") as f:
        f.write(content)
    print(f"Generated {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Docker Hub Description Generator & Validator")
    parser.add_argument("--check", action="store_true", help="Validate template synchronization")
    parser.add_argument("--git-tag", help="Git tag for versioning")
    parser.add_argument("--image-name", help="Docker image name")
    parser.add_argument("--github-repo", help="GitHub repository (owner/repo)")
    parser.add_argument("--github-repo-url", help="GitHub repository URL")
    parser.add_argument("--tags-base", help="Tags for base variant")
    parser.add_argument("--tags-mermaid", help="Tags for mermaid variant")
    parser.add_argument("--tags-plantuml", help="Tags for plantuml variant")
    parser.add_argument("--tags-all", help="Tags for all variant")
    parser.add_argument("--output", default="DOCKER_HUB_FINAL.md", help="Output file path")

    args = Arguments()
    parser.parse_args(namespace=args)

    if args.check:
        validate_sync()
    else:
        # If not just checking, we need some args to actually generate something useful
        # but let's allow it to run with defaults/nones if needed.
        generate_description(args)


if __name__ == "__main__":
    main()
