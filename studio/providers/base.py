from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatResult:
    """One completed model call, with the numbers a benchmark needs."""

    text: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float
    latency_s: float
    provider: str
    model: str


class VisionChatClient(Protocol):
    """What every provider offers. Images are data URIs, never file paths."""

    def chat(
        self,
        prompt: str,
        images: Sequence[str] = (),
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult: ...
