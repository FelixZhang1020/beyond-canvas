import importlib.util
import sys
from pathlib import Path

import pytest

from studio.providers.base import ChatResult


def load_script(path: str | Path, name: str):
    """Import a skill script by path, the way a harness would run it.

    The module is registered in sys.modules before it executes. Without that,
    a dataclass inside the script fails at definition time: dataclasses resolves
    annotations through sys.modules[cls.__module__], which is None for a module
    that was created but never registered.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    """A VisionChatClient that replays canned replies and records its calls."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        self.calls.append(
            {
                "prompt": prompt,
                "images": list(images),
                "system": system,
                "max_tokens": max_tokens,
            }
        )
        if not self.replies:
            raise AssertionError("FakeClient ran out of replies")
        return ChatResult(
            text=self.replies.pop(0),
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=0,
            cost_usd=0.0,
            latency_s=0.01,
            provider="fake",
            model="fake",
        )


@pytest.fixture
def fake_client():
    return FakeClient
