"""Every instruction the studio gives an AI model, read fresh for the prompt page.

The list of what to show lives in `prompt_book.json`; the wording itself stays
where the studio reads it — a prompt file, or a named line in the code — so the
page can never show a copy that has drifted from what a model is sent. Named
lines are read with `ast`, never imported: a skill script is not a package, and
reading a constant should not load a model client or a Blender helper.

This only reads. It keeps no record of what was actually sent for any drawing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BOOK = Path(__file__).with_name("prompt_book.json")


def constants(path: Path) -> dict[str, Any]:
    """Module-level names assigned a plain literal, by name; anything computed is skipped."""
    found = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                continue
    return found


def _part(names: dict[str, Any], part: str) -> str:
    """A blank such as {child_said} is shown as written; anything else names a line."""
    if part.startswith("{"):
        return part
    name, _, key = part.partition(".")
    value = names[name]
    value = value[key] if key else value
    if not isinstance(value, str):
        raise TypeError(f"{part} is not text")
    return value


def text_of(entry: dict) -> str:
    """The wording one entry points at. Raises when it cannot be found."""
    if "code" in entry:
        names = constants(ROOT / entry["code"])
        return "".join(_part(names, part) for part in entry["parts"])
    if "json" in entry:
        value = json.loads((ROOT / entry["json"]).read_text(encoding="utf-8"))
        for key in entry["key"].split("."):
            value = value[key]
        return value
    text = (ROOT / entry["file"]).read_text(encoding="utf-8")
    if "between" in entry:
        start, end = entry["between"]
        text = text.split(start, 1)[1].split(end, 1)[0]
    return text.strip("\n")


def read() -> dict:
    """The whole book. An entry that cannot be read says so instead of vanishing."""
    groups = []
    for group in json.loads(BOOK.read_text(encoding="utf-8"))["groups"]:
        entries = []
        for entry in group["entries"]:
            shown = {"label": entry["label"], "source": entry.get("code") or entry.get("json") or entry["file"]}
            try:
                shown["text"] = text_of(entry)
            except (OSError, KeyError, IndexError, TypeError, ValueError, SyntaxError):
                shown["text"], shown["missing"] = "", True
            entries.append(shown)
        groups.append({"id": group["id"], "name": group["name"], "note": group.get("note"), "entries": entries})
    return {"groups": groups}
