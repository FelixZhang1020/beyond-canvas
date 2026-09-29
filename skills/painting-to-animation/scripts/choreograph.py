"""Plan gentle local movement on a continuous sheet of the original drawing.

The model chooses up to three regions; the browser deforms them with anchored
boundaries and seamless loops. No generated background or detached rectangles.
Inference latency is separate from rendering latency; see the measured report
for real timings and the limits of automatic region selection.

    uv run python skills/painting-to-animation/scripts/choreograph.py DRAWING --lang zh
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from studio.core.env import load_dotenv
from studio.core.images import to_data_uri
from studio.providers import build_client
from studio.providers.base import VisionChatClient
from studio.core.slots import load_profile, resolve

LANGUAGE_NAMES = {"en": "English", "zh": "Chinese"}
PROMPTS = Path(__file__).parent.parent / "assets" / "prompts"

# A closed vocabulary, so the page can execute every move without interpreting
# anything, and so a gate can reject a move nobody has implemented.
MOVES = ("drift", "sway", "rise", "grow", "breathe")
# Older saved plans can still play as gentle local movement, never as cut-outs.
LEGACY_MOVES = ("enter", "exit")

# A child's drawing has a few things in it, not a cast. More layers than this is
# the model inventing detail to fill a schema.
MAX_LAYERS = 3
MIN_SECONDS, MAX_SECONDS = 2.0, 10.0

JUDGE_SYSTEM = "You are a precise annotator. Reply with JSON only. No prose, no code fences."
CHOREOGRAPHY_MAX_TOKENS = 8000


@dataclass(frozen=True)
class Layer:
    """One piece of the drawing, and what it does.

    `box` is the region of the photograph that deforms, in fractions of the
    image. Its boundary stays fixed; the centre moves most. No cut-out or fill.
    """

    name: str
    box: tuple[float, float, float, float]
    move: str
    start_s: float
    end_s: float
    distance: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class Choreography:
    duration_s: float
    layers: tuple[Layer, ...]

    def as_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "layers": [
                {
                    "name": layer.name,
                    "box": list(layer.box),
                    "move": layer.move,
                    "start_s": layer.start_s,
                    "end_s": layer.end_s,
                    "distance": list(layer.distance),
                }
                for layer in self.layers
            ],
        }


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


def build_prompt(language: str, child_said: str = "") -> str:
    """The choreography prompt, with the child's sentence when there is one.

    Their sentence is the whole point when it exists: "he flew back" becomes the
    dragon layer entering from the right, and the child sees that because they
    said it, the world changed.
    """
    prompt = _prompt("choreography").format(
        language=LANGUAGE_NAMES[language], moves=", ".join(MOVES), max_layers=MAX_LAYERS
    )
    if child_said.strip():
        prompt += _prompt("said-clause").format(child_said=child_said)
    return prompt


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    return stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()


def parse(payload: str) -> Choreography:
    """Read the model's answer into the shape the page executes."""
    document = json.loads(_strip_fences(payload))
    if not isinstance(document, dict) or not isinstance(document.get("layers"), list):
        raise ValueError("expected an object with a layers array")
    if len(document["layers"]) > MAX_LAYERS:
        raise ValueError(f"more than the {MAX_LAYERS} supported layers")
    layers = []
    for entry in document.get("layers", []):
        if not isinstance(entry, dict):
            raise ValueError("each layer must be an object")
        box = _vector(entry.get("box"), 4, "box")
        distance = _vector(entry.get("distance", [0, 0]), 2, "distance")
        layers.append(
            Layer(
                name=str(entry.get("name", "")),
                box=tuple(box),  # type: ignore[arg-type]
                move=str(entry.get("move", "")),
                start_s=float(entry.get("start_s", 0.0)),
                end_s=float(entry.get("end_s", 0.0)),
                distance=tuple(distance),  # type: ignore[arg-type]
            )
        )
    return Choreography(float(document.get("duration_s", 0.0)), tuple(layers))


def _vector(value, length: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain exactly {length} numbers")
    return [float(number) for number in value]


def problems(plan: Choreography) -> list[str]:
    """Everything wrong with a choreography, in words a person can act on.

    This is the deterministic half of the gate. It runs before any judge,
    because a plan that would move a rectangle off the edge of the paper is
    wrong whatever a model thinks of it.
    """
    found: list[str] = []
    if not plan.layers:
        found.append("nothing moves")
    if len(plan.layers) > MAX_LAYERS:
        found.append(f"{len(plan.layers)} layers, more than the {MAX_LAYERS} a drawing needs")
    if not MIN_SECONDS <= plan.duration_s <= MAX_SECONDS:
        found.append(f"duration {plan.duration_s}s is outside {MIN_SECONDS} to {MAX_SECONDS}")
    for layer in plan.layers:
        label = layer.name or "an unnamed layer"
        left, top, width, height = layer.box
        if not all(math.isfinite(value) for value in (
            *layer.box, *layer.distance, layer.start_s, layer.end_s
        )):
            found.append(f"{label}: all coordinates and times must be finite")
            continue
        if layer.move not in MOVES + LEGACY_MOVES:
            found.append(f"{label}: {layer.move!r} is not one of {', '.join(MOVES)}")
        if width <= 0 or height <= 0:
            found.append(f"{label}: an empty box")
        elif not (0 <= left <= 1 and 0 <= top <= 1 and left + width <= 1.001 and top + height <= 1.001):
            found.append(f"{label}: the box {list(layer.box)} is not inside the picture")
        if not 0 <= layer.start_s < layer.end_s <= plan.duration_s:
            found.append(f"{label}: {layer.start_s}s to {layer.end_s}s does not fit the clip")
        if max(abs(value) for value in layer.distance) > 1:
            found.append(f"{label}: moves further than the whole picture")
    return found


def choreograph(
    image_path: str,
    language: str,
    client: VisionChatClient,
    child_said: str = "",
) -> Choreography:
    """One call. What moves, when, and how far."""
    reply = client.chat(
        build_prompt(language, child_said),
        [to_data_uri(image_path)],
        system=JUDGE_SYSTEM,
        max_tokens=CHOREOGRAPHY_MAX_TOKENS,
    )
    return parse(reply.text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Make a child's drawing move, using their own lines"
    )
    parser.add_argument("drawing", help="path to a photograph of the drawing")
    parser.add_argument("--lang", default="en", choices=sorted(LANGUAGE_NAMES))
    parser.add_argument("--slot", default="vlm.studio")
    parser.add_argument("--profile", default="cloud")
    parser.add_argument("--said", default="", help="what the child said; it drives the motion")
    arguments = parser.parse_args()

    load_dotenv()
    client = build_client(resolve(arguments.slot, load_profile(arguments.profile)))
    plan = choreograph(arguments.drawing, arguments.lang, client, arguments.said)
    print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
    for problem in problems(plan):
        print("PROBLEM:", problem)


if __name__ == "__main__":
    main()
