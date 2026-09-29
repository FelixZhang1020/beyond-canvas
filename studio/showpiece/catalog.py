"""The six showpiece skills as an agent sees them, and the tools they offer as plain argv lists.

A skill is its SKILL.md: the description is what goes into the index the model chooses from,
the body is what it reads once it has chosen. A tool is a script with named arguments; the
registry says which keys exist, so a model's JSON becomes a list the operating system runs,
never a shell string.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from studio.showpiece.blender_bin import find_blender

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
SIX = ("model-anatomy", "shot-judge", "joint-reveal", "structure-tour", "raise-the-hall", "load-path")
# What a from-nothing rebuild runs with: the six that read and check a model, and the one that makes it.
CARPENTRY = ("hall-carpenter", "model-anatomy", "load-path", "shot-judge")
BLENDER_TIMEOUT, PLAIN_TIMEOUT = 3600, 120   # the hall's tour alone renders for 1,353 s on the Mac (docs/measured)
PATH_KEYS = {"out_dir", "out", "image", "anatomy", "bearing", "loads", "scenes", "joints", "survey", "brief", "photo"}
INPUT_KEYS = PATH_KEYS - {"out_dir", "out"}   # files a tool reads, which must exist before it starts
# The file each input is, when the run folder already holds it. The protocol used to ask the model to
# remember these; the first from-nothing run spent a turn on "the following arguments are required: --anatomy".
KNOWN_INPUTS = {"anatomy": "anatomy.json", "bearing": "bearing.json", "survey": "survey.json", "brief": "brief.json",
                "photo": "photo.jpg"}
# What a live run on a stage renders with, unless the model asks otherwise: a quarter of the pixels
# and a third of the frames of a recording, so the hall's tools answer in minutes, not half hours.
QUICK = {"fps": "10", "width": "960", "height": "540", "seconds": "3", "seconds-per": "3"}
# The repeatable flags one use of which takes several values, named as their tools name them.
WORDS = {"tenon": ("COLUMN", "INTO"), "crosslap": ("A", "B"), "dovetail": ("BEAM", "INTO", "END"),
         "near": ("XYZ", "RADIUS"), "joint": ("COLUMN", "PIECE")}


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    folder: Path
    # What this skill declares it may run, from `allowed-tools` in its own SKILL.md — the
    # key NVIDIA's Skill format reserves for exactly this and which every skill here once
    # left empty. It is the skill's own statement, not the catalog's: a tool
    # that exists under this skill but is not named here is refused before it runs, so a
    # tool added to the catalog and never declared cannot be reached by accident.
    allowed: tuple[str, ...] = ()

    def may_run(self, skill: str, tool: str) -> bool:
        return f"{skill}/{tool}" in self.allowed


@dataclass(frozen=True)
class ToolSpec:
    skill: str
    tool: str
    kind: str
    script: str
    positional: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    repeat: tuple[str, ...] = ()
    needs_model: bool = True
    timeout_s: int = BLENDER_TIMEOUT
    outputs: tuple[str, ...] = ()
    fixed: tuple[str, ...] = ()      # words the tool always gets first: one script, one part per tool
    work: bool = False               # this tool writes the hall being made, and is told where it is
    reference: bool = False          # this tool reads the standing model, never the hall being made


def _frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md does not open with front matter")
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, "\n".join(lines[end + 1:]).strip()


def load_skills(root: Path = SKILLS, names=SIX) -> dict[str, Skill]:
    out = {}
    for name in names:
        meta, body = _frontmatter((root / name / "SKILL.md").read_text(encoding="utf-8"))
        allowed = tuple(t.strip() for t in meta.get("allowed-tools", "").split(",") if t.strip())
        out[name] = Skill(meta["name"], meta["description"], body, root / name, allowed)
    return out


def quick_args(spec, args: dict, quick: dict | None = QUICK) -> dict:
    """The model's args with the quick defaults filled in for the flags this tool has and the model
    left unsaid; a tool without render flags is untouched."""
    if not quick or spec.work:      # a beam's width and a column's height are not a picture's
        return args
    return {**{k: v for k, v in quick.items() if k in spec.flags}, **args}


def known_inputs(spec, args: dict, run_dir: Path) -> dict:
    """The args with every input this tool takes and the model left out, when the folder holds its file.
    A yes or no where a file belongs names none and is left out: a live run wrote "joints": true, and
    was told the folder held no file called True."""
    args = {k: v for k, v in args.items() if not (k in INPUT_KEYS and isinstance(v, bool))}
    takes = set(spec.positional) | set(spec.flags)
    found = {k: name for k, name in KNOWN_INPUTS.items() if k in takes and k not in args and (run_dir / name).is_file()}
    return {**found, **args}


def _spec(skill, tool, kind, script, positional=(), flags=(), repeat=(), needs_model=True, outputs=(), **more):
    timeout = BLENDER_TIMEOUT if kind == "blender" else PLAIN_TIMEOUT
    return ToolSpec(skill, tool, kind, script, positional, flags, repeat, needs_model, timeout, outputs, **more)


def _part(tool, flags=(), repeat=()):
    """One part of the hall: the same placing script, told which part, writing the hall and its record."""
    return _spec("hall-carpenter", tool, "blender", "scripts/place.py", ("out_dir",), flags, repeat,
                 needs_model=False, outputs=("hall.json",), fixed=(tool,), work=True)


SPECS = (
    _spec("model-anatomy", "inventory", "blender", "scripts/inventory.py", ("out_dir",), outputs=("anatomy.json",)),
    _spec("model-anatomy", "bearing", "blender", "scripts/bearing.py", ("out_dir",), outputs=("bearing.json",)),
    _spec("shot-judge", "judge", "python", "scripts/judge.py", (), ("image", "meant", "out", "profile", "slot"),
          needs_model=False, outputs=("verdict.json",)),
    _spec("joint-reveal", "joints", "blender", "scripts/joints.py", ("out_dir",), ("stem",),
          ("tenon", "crosslap", "dovetail"), outputs=("joints.json",)),
    _spec("joint-reveal", "closeup", "blender", "scripts/closeup.py", ("out",),
          ("at", "look", "lens", "hide-beyond", "hide-above", "style", "width", "height"), ("move", "hide")),
    _spec("joint-reveal", "explode", "blender", "scripts/explode.py", ("out_dir",),
          ("anatomy", "assembly", "pieces", "joints", "closeups", "seconds", "fps", "width", "height", "at", "look", "style"),
          ("near",), outputs=("explode.json", "explode-open.png", "explode.mp4")),
    _spec("structure-tour", "tour", "blender", "scripts/tour.py", ("out_dir",),
          ("anatomy", "segments", "seconds-per", "fps", "width", "height", "style"), outputs=("tour.json", "tour.mp4")),
    _spec("raise-the-hall", "stages", "python", "scripts/stages.py", ("bearing", "anatomy", "out_dir"), ("max-scenes",),
          needs_model=False, outputs=("scenes.json",)),
    _spec("raise-the-hall", "raise", "blender", "scripts/raise.py", ("out_dir",),
          ("scenes", "anatomy", "drop", "scene-seconds", "settle-seconds", "fps", "width", "height", "orbit-degrees",
           "style"), outputs=("raise.json", "raise.mp4")),
    _spec("load-path", "weights", "python", "scripts/weights.py", ("anatomy", "bearing", "out_dir"), needs_model=False,
          outputs=("loads.json",)),
    _spec("load-path", "flow", "blender", "scripts/flow.py", ("out_dir",),
          ("anatomy", "loads", "seconds", "hold", "fps", "width", "height", "lo-kN", "hi-kN", "orbit-degrees", "style"),
          outputs=("flow.json", "flow-end.png", "flow.mp4")),
    _spec("load-path", "collapse", "blender", "scripts/collapse.py", ("out_dir",),
          ("anatomy", "bearing", "step", "fps", "width", "height", "style"), ("joint",),
          outputs=("collapse.json", "collapse-end.png", "collapse.mp4")),
    _spec("load-path", "settle", "blender", "scripts/settle.py", ("out_dir",),
          ("anatomy", "bearing", "seconds", "fps", "width", "height", "camera", "style"),
          outputs=("settle.json", "settle-end.png", "settle.mp4")),
    # No seconds or fps here: the stage's quick three seconds at ten frames would cut the shaking short
    # and turn its wave into a saw. The shake test keeps its own six seconds at twenty-four.
    _spec("load-path", "shake", "blender", "scripts/shake.py", ("out_dir",),
          ("anatomy", "bearing", "width", "height", "camera", "style"), outputs=("shake.json", "shake-end.png")),
    # Advice from a model of another company, read from numbers alone. Not in adoption.CHECKS, by design.
    _spec("hall-carpenter", "review", "python", "scripts/review.py", ("out_dir",), ("profile", "slot"), needs_model=False,
          outputs=("review.json",)),
    _spec("hall-carpenter", "survey", "blender", "scripts/survey.py", ("out_dir",), outputs=("survey.json", "temple.png"),
          reference=True),
    _part("platform", ("size", "top", "thickness")),
    _part("columns", ("xs", "ys", "rings", "foot", "height", "diameter")),
    _part("ties", ("top", "depth", "width")),
    _part("walls", ("sides", "foot", "top", "thickness", "infill-top")),
    _part("brackets", ("seat", "tiers", "rise", "reach", "block", "arm", "inter"), ("outrigger",)),
    _part("frames", ("seat", "king", "width", "depth", "lines", "end-lines", "end-beams"), ("beam",)),
    _part("purlins", ("ridge", "size", "overhang"), ("ring",)),
    _part("rafters", ("spacing", "size", "eave-out")),
    _part("roof", ("thickness", "ridge-cap", "finial")),
    _spec("hall-carpenter", "likeness", "blender", "scripts/likeness.py", ("out_dir",), ("survey",),
          outputs=("likeness.json", "likeness.png")),
    # A design's likeness: the hall against its written brief and the brief's photograph; no temple is read.
    _spec("hall-carpenter", "brief", "blender", "scripts/brief.py", ("out_dir",), ("brief", "photo"),
          outputs=("brief-check.json", "brief.png")),
    _spec("hall-carpenter", "faults", "python", "scripts/faults.py", ("out_dir",), needs_model=False,
          outputs=("faults.json",)),
)
TOOLS = {(spec.skill, spec.tool): spec for spec in SPECS}


def _clean(key: str, value) -> str:
    text = ",".join(str(v) for v in value) if isinstance(value, list) else str(value)
    if "\n" in text or "\0" in text:
        raise ValueError(f"argument {key!r} holds a newline or a null")
    return text


def inside_run(run_dir: Path, text: str) -> str:
    """A path the model wrote, made relative to the run folder: models copy the folder's own path
    from the prompt ("<run_dir>/anatomy.json"), which would nest a second run folder inside the first."""
    text = text.removeprefix("./")
    for prefix in {str(run_dir), str(run_dir.resolve()), run_dir.as_posix()}:
        if text == prefix:
            return "."
        if text.startswith(prefix + "/"):
            return text[len(prefix) + 1:] or "."
    return text


def input_path(run_dir: Path, value) -> Path:
    """Where a path the model wrote points, which must be inside the run folder: a model steered by its request
    could otherwise name any file the studio can read, to be judged and sent on, or written over (code review)."""
    text = inside_run(run_dir, str(value))
    path = Path(text) if text.startswith("/") else run_dir / text
    where, home = path.resolve(), run_dir.resolve()
    if where != home and home not in where.parents:
        raise ValueError(f"{str(value)!r} is outside the run folder; every file a tool uses is in it")
    return path


def jointed(args: dict, run_dir: Path) -> Path | None:
    """The copy a tool given a joints file works on: the model that file names, when the joints tool
    wrote it inside this run's folder. The joints are cut into that copy, never into the hall, so on
    the hall itself a live pull-apart of the joints would film pieces that are not there."""
    if "joints" not in args:
        return None
    try:
        named = Path(json.loads(input_path(run_dir, args["joints"]).read_text(encoding="utf-8"))["model"]).resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return named if named.is_file() and run_dir.resolve() in named.parents else None


def _path(key: str, value, run_dir: Path) -> str:
    """Paths in args are taken relative to the run folder unless absolute."""
    text = _clean(key, value)
    return str(input_path(run_dir, text)) if key in PATH_KEYS else text


def _uses(key: str, given) -> list[list]:
    """A repeatable flag's value as its uses, each a list of words. A flag of WORDS reads a flat list of
    its words as one use, and a bare string is always one word: a string used to be taken
    letter by letter and a flat list a word per use, so a live run could never name a joint's pieces."""
    if given is None or given == "":
        return []
    given = given if isinstance(given, list) else [given]
    words = WORDS.get(key)
    if words is None:
        return [v if isinstance(v, list) else [v] for v in given]
    if not any(isinstance(v, list) for v in given):
        given = [given[i:i + len(words)] for i in range(0, len(given), len(words))]
    if any(not isinstance(v, list) or len(v) != len(words) for v in given):
        example = ", ".join(f'"{w}"' for w in words)
        raise ValueError(f"{key} takes {len(words)} values each time, one list per use: {{\"{key}\": [[{example}]]}}")
    return given


def _flag(key: str, value, run_dir: Path) -> list[str]:
    if isinstance(value, bool):     # a switch: said or left out, never "--closeups True"
        return [f"--{key}"] if value else []
    text = _path(key, value, run_dir)
    return [f"--{key}={text}"] if text.startswith("-") else [f"--{key}", text]


def named(action: dict) -> tuple[str, str]:
    """The skill and tool an action names. Models also write "model-anatomy/bearing" in the tool field;
    the driver and the gate must read that the same way, or the lap limit reads a different tool."""
    skill, tool = str(action.get("skill")), str(action.get("tool"))
    if "/" in tool:
        skill, tool = tool.split("/", 1)
    return skill, tool


def argv_for(spec: ToolSpec, args: dict, model: Path | None, run_dir: Path, hall: Path | None = None) -> list[str]:
    """The command for one tool call, as a list the operating system runs directly."""
    args = {str(key).lstrip("-"): value for key, value in args.items()}   # "--image" means "image"
    known = set(spec.positional) | set(spec.flags) | set(spec.repeat)
    for key in args:
        if key not in known:
            raise ValueError(f"tool {spec.skill}/{spec.tool} takes no argument {key!r}")
    script = str(SKILLS / spec.skill / spec.script)
    if spec.kind == "blender":
        blender = find_blender()
        if blender is None:
            raise RuntimeError("no Blender binary: set BLENDER_BIN or install Blender")
        head = [str(blender), "-b", *([str(model)] if model else []), "--python-exit-code", "1", "--python", script, "--"]
    else:
        head = [sys.executable, script]
    tail = list(spec.fixed)
    for key in spec.positional:
        value = args.get(key, "." if key == "out_dir" else None)
        if value is None:
            raise ValueError(f"tool {spec.skill}/{spec.tool} needs {key!r}")
        tail.append(_path(key, value, run_dir))
    for key in spec.flags:
        if key in args and args[key] is not None:
            tail += _flag(key, args[key], run_dir)
    for key in spec.repeat:
        for use in _uses(key, args.get(key)):
            tail += [f"--{key}", *(_clean(key, v) for v in use)]
    if spec.work:
        if hall is None:
            raise RuntimeError(f"tool {spec.skill}/{spec.tool} makes a hall, and this run has none to make")
        tail += ["--hall", str(hall)]
    return head + tail
