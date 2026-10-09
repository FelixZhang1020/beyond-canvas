"""What a media provider returns, and the one shape they all return it in.

Deliberately not `VisionChatClient`. The models behind these slots take a job
description and hand back a file — an edited picture, a five-second video, a
line of narration, a mesh. Squeezing them into the chat protocol would put a
`max_tokens` on a request to build a 3D model, and would make `text` the field
every caller reads when not one of these models returns any.

The price field is the honest half of this file. Neither fal nor Replicate says
what a call cost in its response: fal reports `inference_time`, Replicate
reports `predict_time`, and both bill from their own price list afterwards. So
the number here is the list price written in the profile, not a measurement,
and it is named to say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from studio.core.errors import UnknownTask


@dataclass(frozen=True)
class MediaResult:
    """One completed generation: what came back, and what the list says it cost."""

    urls: list[str]
    payload: dict[str, Any] = field(default_factory=dict)
    # Some vendors answer with a link and some with the file. Replicate and fal
    # return a URL; SiliconFlow hands back the recording itself. A caller reads
    # whichever is filled, and one of them always is.
    content: bytes = b""
    # The profile's declared price for one call, never a figure the vendor
    # reported. Zero means the profile did not declare one, which is not the
    # same as free.
    price_usd: float = 0.0
    latency_s: float = 0.0
    provider: str = ""
    model: str = ""


class MediaClient(Protocol):
    """What every media provider offers: one job in, the files it produced out."""

    def make(self, inputs: dict[str, Any]) -> MediaResult: ...


def urls_in(value: Any) -> list[str]:
    """Every URL inside a vendor's answer, in the order it appears.

    Each vendor shapes its output differently, and each model within a vendor
    shapes it differently again: fal returns `{"images": [{"url": ...}]}` for a
    picture, `{"audio": {"url": ...}}` for a voice and `{"model_mesh": {...}}`
    for a mesh, while Replicate returns a bare string, a list of strings, or an
    object. Walking the whole answer reads all of them without this module
    holding a table of output shapes — a table that would need an edit every
    time a slot changed model, and would be wrong quietly when it did not.
    """
    if isinstance(value, str):
        return [value] if value.startswith(("http://", "https://")) else []
    if isinstance(value, dict):
        return [found for item in value.values() for found in urls_in(item)]
    if isinstance(value, list):
        return [found for item in value for found in urls_in(item)]
    return []


# The canonical arguments each task takes. A slot declares its task in the
# profile and maps these names onto whatever its vendor happens to call them,
# so that changing model is an edit to a profile rather than to skill code.
TASKS: dict[str, tuple[str, ...]] = {
    "speak": ("text", "voice"),
    "edit_image": ("image", "instruction"),
    "to_mesh": ("image",),
    "to_video": ("image", "instruction"),
    "screen_image": ("image",),
    # Several pictures redrawn in one job, so the model loads once: a storybook's pages.
    "restyle_pictures": ("pictures",),
}


@dataclass(frozen=True)
class MediaSlot:
    """A media model addressed by what it does, not by what its vendor calls things.

    This exists because the operator expects to swap these models: if the
    pictures or the voice are not good enough, the model behind the slot
    changes. Passing a vendor's own field names through skill code would make
    every such swap a code change in several files, which is exactly what the
    slot design is for.

    So a skill says `speak(text=...)`. The profile says that this vendor calls
    that field `tts_text`, and that every call also carries `task: zero-shot
    voice clone`. Swapping CosyVoice for Step-Audio then edits three lines of
    YAML and no Python at all.
    """

    client: MediaClient
    task: str
    fields: dict[str, str]
    extra: dict[str, Any]
    array_fields: tuple[str, ...] = ()

    def speak(self, text: str, voice: str | None = None) -> MediaResult:
        """Say something. `voice` is a reference recording when cloning."""
        return self._run("speak", text=text, voice=voice)

    def edit_image(self, image: str, instruction: str) -> MediaResult:
        """Redraw or alter one picture, following an instruction."""
        return self._run("edit_image", image=image, instruction=instruction)

    def to_mesh(self, image: str, subject: str | None = None, model_choice: str | None = None) -> MediaResult:
        """Turn one picture into a 3D object."""
        return self._run("to_mesh", image=image, subject=subject, model_choice=model_choice)

    def to_video(self, image: str, instruction: str | None = None, seed: int | None = None,
                 clip_maker: str | None = None) -> MediaResult:
        """Turn one picture into a short clip; a seed asks for another start than the service's own, and
        clip_maker which of the class's clip makers to ask (ClipChoices), where it has more than one."""
        return self._run("to_video", image=image, instruction=instruction, seed=seed, clip_maker=clip_maker)

    def restyle_pictures(self, pictures: list[dict[str, Any]]) -> MediaResult:
        """Redraw several pictures, each by its own instruction, in one job; `payload["pictures"]` in order."""
        return self._run("restyle_pictures", pictures=pictures)

    def screen_image(self, image: str) -> MediaResult:
        """Ask whether one picture is safe to show."""
        return self._run("screen_image", image=image)

    def _run(self, task: str, **arguments: Any) -> MediaResult:
        """Translate canonical arguments into this vendor's field names."""
        if task != self.task:
            raise UnknownTask(
                f"this slot serves {self.task!r}, so it has no {task!r} to offer; "
                f"a slot does one job and the profile says which"
            )
        body = {k: v for k, v in self.extra.items() if k != "instruction_limit"}
        for name, value in arguments.items():
            if value is not None:
                body[self.fields.get(name, name)] = [value] if name in self.array_fields else value
        return self.client.make(body)
