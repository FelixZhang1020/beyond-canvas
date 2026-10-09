"""Validate a skill folder against the Agent Skills specification.

The pack claims to follow a standard, and until this existed nothing checked
that claim. Every rule below comes from the specification itself rather than
from taste:

    name          1 to 64 characters, lowercase letters, digits and hyphens,
                  no leading, trailing or doubled hyphen, and it must equal the
                  directory name
    description   present, non-empty, at most 1024 characters
    frontmatter   a closed set. name and description are required; license,
                  compatibility, metadata and allowed-tools are optional; any
                  other top-level key is invalid
    SKILL.md      under 500 lines, because the body loads whole on activation
    evals         at one of four accepted paths

The four eval paths are the specification's own flexibility, not four formats.
There is one format.

Publication to NVIDIA's catalog additionally wants skill-card.md and a
skill.oms.sig signature. Those are reported as missing rather than invalid,
because a skill can be correct and simply not published yet.

Usage:
    uv run python -m evalkit.packaging skills/art-feedback
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
BODY_MAX_LINES = 500

REQUIRED_KEYS = {"name", "description"}
OPTIONAL_KEYS = {"license", "compatibility", "metadata", "allowed-tools"}

EVAL_PATHS = ("evals/evals.json", "eval", "evals", "benchmark/evals.json")
CATALOG_EXTRAS = ("skill-card.md", "skill.oms.sig")


@dataclass
class Report:
    """What a skill folder got right, wrong, and has not published yet."""

    skill: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"{'PASS' if self.valid else 'FAIL'}  {self.skill}"]
        lines += [f"    error: {message}" for message in self.errors]
        lines += [f"    note:  {message}" for message in self.warnings]
        return "\n".join(lines)


def _split_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Return the parsed frontmatter and the body lines."""
    if not text.startswith("---"):
        raise ValueError("SKILL.md does not open with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("the frontmatter block is not closed")
    parsed = yaml.safe_load(parts[1]) or {}
    if not isinstance(parsed, dict):
        raise ValueError("the frontmatter is not a mapping")
    return parsed, parts[2].splitlines()


def _check_name(name: object, directory: Path, report: Report) -> None:
    if not isinstance(name, str) or not name:
        report.errors.append("name is missing")
        return
    if len(name) > NAME_MAX:
        report.errors.append(f"name is {len(name)} characters, over the {NAME_MAX} limit")
    if not NAME_PATTERN.match(name):
        report.errors.append(
            f"name {name!r} must be lowercase letters, digits and single hyphens, "
            "with no leading or trailing hyphen"
        )
    if name != directory.name:
        report.errors.append(f"name {name!r} does not match its directory {directory.name!r}")


def _check_description(description: object, report: Report) -> None:
    if not isinstance(description, str) or not description.strip():
        report.errors.append("description is missing or empty")
        return
    if len(description) > DESCRIPTION_MAX:
        report.errors.append(
            f"description is {len(description)} characters, over the {DESCRIPTION_MAX} limit"
        )


def _check_keys(frontmatter: dict, report: Report) -> None:
    invented = set(frontmatter) - REQUIRED_KEYS - OPTIONAL_KEYS
    for key in sorted(invented):
        report.errors.append(
            f"frontmatter key {key!r} is not in the specification; "
            "put it under metadata or compatibility"
        )
    compatibility = frontmatter.get("compatibility")
    if isinstance(compatibility, str) and len(compatibility) > COMPATIBILITY_MAX:
        report.errors.append(
            f"compatibility is {len(compatibility)} characters, over {COMPATIBILITY_MAX}"
        )


def _check_evals(directory: Path, report: Report) -> None:
    for candidate in EVAL_PATHS:
        path = directory / candidate
        if path.is_file():
            return
        if path.is_dir() and list(path.glob("*.json")):
            return
    report.errors.append(
        "no evals found at any accepted path: " + ", ".join(EVAL_PATHS)
    )


def validate(directory: Path) -> Report:
    """Check one skill folder. Errors block publication; notes do not."""
    report = Report(skill=directory.name)
    manifest = directory / "SKILL.md"
    if not manifest.is_file():
        report.errors.append("there is no SKILL.md")
        return report

    text = manifest.read_text(encoding="utf-8")
    try:
        frontmatter, body = _split_frontmatter(text)
    except ValueError as error:
        report.errors.append(str(error))
        return report

    _check_name(frontmatter.get("name"), directory, report)
    _check_description(frontmatter.get("description"), report)
    _check_keys(frontmatter, report)
    _check_evals(directory, report)

    if len(body) > BODY_MAX_LINES:
        report.errors.append(
            f"SKILL.md body is {len(body)} lines, over the {BODY_MAX_LINES} limit; "
            "move detail into references/"
        )
    for extra in CATALOG_EXTRAS:
        if not (directory / extra).exists():
            report.warnings.append(f"{extra} is absent, so this cannot be published yet")
    return report


def validate_all(root: Path) -> list[Report]:
    return [validate(child) for child in sorted(root.iterdir()) if child.is_dir()]


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    root = Path(arguments[0]) if arguments else Path("skills")
    reports = validate_all(root) if root.name == "skills" else [validate(root)]
    for report in reports:
        print(report.render())
    failed = [report for report in reports if not report.valid]
    print(f"\n{len(reports) - len(failed)} of {len(reports)} valid")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
