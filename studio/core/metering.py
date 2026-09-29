"""What a stage cost, and how much of the box was in use while it ran.

The ledger promised tokens, cost and memory from the day it was written and
recorded zero for all three, because the numbers were thrown away one layer
below it: a skill returns the model's text and drops everything else the model
reported. Rather than change what every skill returns, the client is wrapped.

The meter sits between a skill and its model, adds up what passes through, and
the harness reads it once per stage. That also catches the judges, which is the
honest total: a beat's real cost is what the writer spent plus what checking it
spent, and checking it is most of the bill.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from studio.providers.base import ChatResult, VisionChatClient
from studio.providers.media import MediaClient, MediaResult


@dataclass
class Spend:
    tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def __add__(self, other: "Spend") -> "Spend":
        return Spend(
            self.tokens + other.tokens,
            round(self.cost_usd + other.cost_usd, 6),
            self.calls + other.calls,
        )


# Which request a call is counted for. Since there are two lanes, a drawing's conversation can serve a
# chat and a clip at once, and both share its meters; the code review of that change found the stage that
# finished first taking the other request's spending into its own ledger line. Each request's run sets
# this, a meter keeps one total per request, and a stage takes only its own. Outside any request the key
# is None, which is the one shared total everything used before.
_counting: ContextVar[object] = ContextVar("metering_counting", default=None)


def counting_for(key: object):
    """Count what is spent on this thread for `key` from now on; returns the token to hand to `stop_counting`."""
    return _counting.set(key)


def stop_counting(token) -> None:
    _counting.reset(token)


def carried(call: Callable[[], object]) -> Callable[[], object]:
    """`call`, counted for the request that asked for it even on another thread (the rubric's judges)."""
    key = _counting.get()

    def run():
        token = _counting.set(key)
        try:
            return call()
        finally:
            _counting.reset(token)
    return run


class _Totals:
    """One Spend per request, behind a lock: the judges can finish two calls at once."""

    def __init__(self) -> None:
        self._spent: dict[object, Spend] = {}
        self._lock = threading.Lock()

    def add(self, spend: Spend) -> None:
        key = _counting.get()
        with self._lock:
            self._spent[key] = self._spent.get(key, Spend()) + spend

    def take(self) -> Spend:
        with self._lock:
            return self._spent.pop(_counting.get(), Spend())


class Meter(VisionChatClient):
    """A client that counts what goes through it and forwards everything else."""

    def __init__(self, inner: VisionChatClient) -> None:
        self.inner = inner
        self._totals = _Totals()

    def chat(
        self,
        prompt: str,
        images: Sequence[str] = (),
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        result = self.inner.chat(prompt, images, system=system, max_tokens=max_tokens)
        self._totals.add(Spend(tokens=result.input_tokens + result.output_tokens, cost_usd=result.cost_usd, calls=1))
        return result

    def take(self) -> Spend:
        """Read this request's total and set it back to zero, ready for its next stage."""
        return self._totals.take()


class MediaMeter:
    """Include configured media price estimates in the same stage ledger."""

    def __init__(self, inner: MediaClient) -> None:
        self.inner, self._totals = inner, _Totals()

    def make(self, inputs: dict) -> MediaResult:
        result = self.inner.make(inputs)
        self._totals.add(Spend(cost_usd=result.price_usd, calls=1))
        return result

    def take(self) -> Spend:
        return self._totals.take()


def used_memory_gb() -> float:
    """How much of the machine is in use right now, in gigabytes.

    Not this process: the whole box. On the Spark the models are separate
    processes and the number that matters is how close the machine is to
    freezing, which is exactly what section 7's ceiling is about. Zero when the
    host cannot be read, which is honest rather than invented.
    """
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        values = {}
        for line in meminfo.read_text().splitlines():
            name, _, rest = line.partition(":")
            values[name] = int(rest.split()[0])
        total, available = values.get("MemTotal", 0), values.get("MemAvailable", 0)
        return round((total - available) / 1024 / 1024, 2)
    return _macos_used_gb()


def _macos_used_gb() -> float:
    """The Mac equivalent, so the same number exists while developing."""
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return 0.0
        page = 4096
        pages = {}
        for line in out.stdout.splitlines():
            if line.startswith("Mach Virtual Memory Statistics"):
                if "page size of" in line:
                    page = int(line.split("page size of")[1].split()[0])
                continue
            name, _, rest = line.partition(":")
            digits = rest.strip().rstrip(".")
            if digits.isdigit():
                pages[name.strip()] = int(digits)
        used = sum(
            pages.get(name, 0)
            for name in ("Pages active", "Pages wired down", "Pages occupied by compressor")
        )
        return round(used * page / 1024**3, 2)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0
