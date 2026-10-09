"""What the model may read and see: a JSON result from the run folder or its digest, a skill's own
reference document, the folder's listing when it names a file that is not there, and whether a
file is really a picture.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

READ_LIMIT = 6000


def _digest(data: dict) -> dict:
    """What a model needs from a big result: per piece the role, kind and size (the first sixty),
    the stages, the loads, the summary; never the raw contact lists."""
    out = {}
    for key, value in data.items():
        if key == "pieces" and isinstance(value, dict):
            names = sorted(value, key=lambda n: -value[n].get("moved_m", 0)) if any(
                "moved_m" in p for p in value.values()) else list(value)     # what moved most comes first
            out["pieces_total"] = len(names)
            out["pieces"] = {}
            for n in names[:60]:
                p = value[n]
                if "role" in p:
                    out["pieces"][n] = [p["role"], p.get("kind"), [round(e, 2) for e in p.get("extents", [])]]
                elif "carries_N" in p:
                    out["pieces"][n] = {"carries_kN": round(p["carries_N"] / 1e3, 1), "weight_kN": round(p["weight_N"] / 1e3, 1)}
                else:
                    out["pieces"][n] = p
        elif key in ("rests_on", "near", "overlaps", "carried_by", "landmarks", "cameras"):
            out[key] = f"({len(value)} entries, not shown)"
        elif key == "order" and isinstance(value, list):
            out[key] = value[:40] + ([f"... {len(value) - 40} more"] if len(value) > 40 else [])
        else:
            out[key] = value
    return out


def listing(run_dir: Path) -> str:
    """The run folder's files by name, a folder as its name and frame count: what the model may open."""
    names = []
    for p in sorted(run_dir.iterdir()):
        names.append(f"{p.name}/ ({sum(1 for _ in p.iterdir())} files)" if p.is_dir() else p.name)
    return ", ".join(names[:60]) or "(nothing yet)"


def is_picture(path: Path) -> bool:
    """A real image file, not a verdict the model asked the judge to write under a .png name."""
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError, Image.UnidentifiedImageError):
        return False


def read_reference(skill_folder: Path, name: str) -> str:
    """One of a skill's own reference documents, which its instructions point to by name: the third
    level of an Agent Skill, opened only when the model asks for it. At first nothing could
    open one, so every "see references/method.md" in a skill's instructions pointed at nothing.
    Markdown inside that skill's references/ folder and nothing else."""
    root = (Path(skill_folder) / "references").resolve()
    target = (Path(skill_folder) / name).resolve()
    if root not in target.parents or target.suffix != ".md" or not target.is_file():
        found = ", ".join(sorted(f"references/{p.name}" for p in root.glob("*.md"))) if root.is_dir() else "none"
        return f"no such reference {name!r}; this skill's references are: {found}"
    text = target.read_text(encoding="utf-8")
    note = " (the first part of a long reference; this is all the read tool returns)"
    return text if len(text) <= READ_LIMIT else text[:READ_LIMIT - len(note)] + note


def read_file(run_dir: Path, name: str) -> str:
    """A JSON result from the run folder, for the model to read; a big one comes back as a digest,
    and the digest is all there is: reading again returns the same."""
    target = (run_dir / name).resolve()
    if run_dir.resolve() not in target.parents or not target.is_file() or target.suffix != ".json":
        return f"no such JSON file in the run folder: {name!r}"
    data = json.loads(target.read_text(encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False)
    if len(text) <= READ_LIMIT:
        return text
    digest = json.dumps(_digest(data) if isinstance(data, dict) else data, ensure_ascii=False)
    note = " (digest of a large file; this is all the read tool returns)"
    return digest[:READ_LIMIT - len(note)] + note
