"""Read an OpenAI-shaped streamed chat answer back into the shape of an ordinary one.

Both text providers the class runs on stream the same way (measured
on the Spark): `data: {...}` lines whose `choices[0].delta.content` carries the
next words, and `data: [DONE]` at the end. Step 3.7 Flash puts its hidden
thinking in `delta.reasoning_content`, which is kept for the empty-answer message
and never shown. StepFun repeats `usage` on every line; vLLM sends it once, on a
last line with no choices, when asked with `stream_options.include_usage`.

What comes back is the payload a non-streamed call would have returned, so each
provider's own checks — no text, a truncated answer — run unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from studio.core.errors import ModelUnavailable
from studio.server.textstream import Listener


def read(lines: Iterable[str], listener: Listener, model: str) -> dict[str, Any]:
    text: list[str] = []
    thinking: list[str] = []
    finish, usage, named, done = None, {}, model, False
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            break
        try:
            chunk = json.loads(data)
        except ValueError as error:
            raise ModelUnavailable(f"{model} sent an unreadable line while streaming") from error
        usage = chunk.get("usage") or usage
        named = chunk.get("model") or named
        for choice in chunk.get("choices") or ():
            delta = choice.get("delta") or {}
            thinking.append(delta.get("reasoning_content") or "")
            finish = choice.get("finish_reason") or finish
            if delta.get("content"):
                text.append(delta["content"])
                listener("".join(text))
    # Code review: a connection that closed cleanly partway through handed back the words
    # so far as a finished answer. Neither a finish reason nor the closing line means it never finished,
    # which is a model outage, so the provider's own retry or the fallback voice takes it.
    if not done and finish is None:
        raise ModelUnavailable(f"{model} stopped streaming before its answer was finished")
    return {
        "model": named,
        "usage": usage,
        "choices": [{"message": {"content": "".join(text), "reasoning_content": "".join(thinking)},
                     "finish_reason": finish}],
    }
