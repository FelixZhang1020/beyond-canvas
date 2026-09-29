"""The first hour on the Spark, as a script rather than a memory.

Section 9 lists what day zero must measure. The point of writing it now, before
the box exists, is that the first hour on unfamiliar hardware is exactly when
nobody has time to design a benchmark — so the questions are settled here and
the box only has to answer them.

Every check reports rather than asserts. A failure on day zero is a finding, not
a bug: this script's job is to replace the estimates in the design record with
measurements, including the unwelcome ones.

    uv run python -m studio.ops.dayzero              # everything that needs no model
    uv run python -m studio.ops.dayzero --full       # also loads models and times them
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from studio.core.images import to_data_uri
from studio.providers import LOCAL, build_client
from studio.core.slots import SlotConfig, load_profile, resolve
from studio.core.watchdog import STUDIO_CEILING_GB, USABLE_CEILING_GB, Watchdog, WouldNotFit

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"
SWITCHES = 10
TOKENS_PROMPT = "Describe this drawing in two sentences."


@dataclass
class Finding:
    """One question day zero answers, and what the box said."""

    name: str
    ok: bool
    detail: str
    numbers: dict[str, Any] = field(default_factory=dict)

    def line(self) -> str:
        return f"[{'ok  ' if self.ok else 'FAIL'}] {self.name}: {self.detail}"


def usable_memory_gb() -> tuple[float, str]:
    """What the box says it has. The number section 2 could only guess at.

    On Linux this reads MemTotal; on a Mac it reads the same sysctl the design
    record's 64 GB came from, so the script is runnable here before it matters
    there.
    """
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1), "/proc/meminfo MemTotal"
    out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
    if out.returncode == 0 and out.stdout.strip().isdigit():
        return round(int(out.stdout.strip()) / 1024**3, 1), "sysctl hw.memsize"
    return 0.0, "unknown"


def check_the_box() -> Finding:
    """What we are standing on. Recorded so a number can never be orphaned."""
    total, source = usable_memory_gb()
    detail = f"{platform.system()} {platform.machine()}, {total} GB by {source}"
    return Finding("the box", total > 0, detail, {"total_gb": total, "source": source})


def check_the_ceiling() -> Finding:
    """The one number every memory decision rests on, and nobody has measured.

    Section 2 says 108 to 119 GB usable of 128. The watchdog's studio ceiling is
    90 and its director ceiling is the optimistic end of that range, because the
    109 GB director model does not fit under the pessimistic end. This reports
    which end the box actually landed on, which settles whether director mode is
    a mode or a wish.
    """
    total, _ = usable_memory_gb()
    fits = total >= 109 + 2
    detail = (
        f"{total} GB total; studio ceiling {STUDIO_CEILING_GB}, director ceiling "
        f"{USABLE_CEILING_GB}. Director model is 109 GB, so director mode "
        + ("has room" if fits else "does NOT fit and section 7 needs revisiting")
    )
    return Finding("the memory ceiling", fits, detail, {"total_gb": total})


def check_the_studio_fits(profile: dict[str, SlotConfig]) -> Finding:
    """Load the whole studio set on paper before loading it for real.

    The sizes come from the profile, so a profile edited to something the box
    cannot hold fails here rather than by freezing the machine.
    """
    watchdog = Watchdog()
    loaded, refused = [], []
    # A model marked `outside_class` is never loaded while a class runs (the showpiece's engineer),
    # so it is kept out of the class arithmetic; it must still fit the box by itself, and is named.
    outside = {slot: float(c.options.get("size_gb") or 0) for slot, c in profile.items() if c.options.get("outside_class")}
    for slot, config in sorted(profile.items()):
        size = float(config.options.get("size_gb") or 0)
        if not size or slot in outside or config.options.get("director_mode") or config.options.get("rotating_slot"):
            continue
        try:
            watchdog.load(slot, size)
            loaded.append(f"{slot} {size}")
        except WouldNotFit as error:
            refused.append(f"{slot}: {error}")
    rotating = max(
        (float(c.options.get("size_gb") or 0) for slot, c in profile.items()
         if c.options.get("rotating_slot") and slot not in outside),
        default=0.0,
    )
    peak = watchdog.peak_for(rotating)
    detail = (
        f"resident {watchdog.used_gb} GB, biggest rotating slot {rotating} GB, "
        f"peak {peak} GB against {watchdog.limit_gb}"
    )
    refused += [f"{slot}: {size:g} GB alone is over the ceiling" for slot, size in outside.items() if size > watchdog.limit_gb]
    if outside:
        detail += "; outside class: " + ", ".join(f"{slot} {size:g}" for slot, size in sorted(outside.items()))
    if refused:
        detail += " — REFUSED: " + "; ".join(refused)
    return Finding(
        "the studio set fits",
        not refused and peak <= watchdog.limit_gb,
        detail,
        {"resident_gb": watchdog.used_gb, "peak_gb": peak, "loaded": loaded},
    )


def check_mode_switching() -> Finding:
    """Ten switches and back without a refusal. Section 9's last item.

    This exercises the state machine, not the hardware: the real test is whether
    the box survives ten real loads, which needs the models. What it proves here
    is that the arithmetic never traps the studio in director mode.
    """
    watchdog = Watchdog()
    for slot, size in (("safety.image", 8.0), ("vlm.studio", 24.0)):
        watchdog.load(slot, size)
    for _ in range(SWITCHES):
        try:
            watchdog.enter_director_mode("vlm.director", 109.0)
            watchdog.restore_studio_mode()
            watchdog.load("safety.image", 8.0)
            watchdog.load("vlm.studio", 24.0)
        except WouldNotFit as error:
            return Finding("mode switching", False, str(error))
    return Finding(
        "mode switching", True, f"{SWITCHES} switches to director and back, no refusal"
    )


def check_nothing_leaves_the_box(profile: dict[str, SlotConfig]) -> Finding:
    """The privacy claim, checked mechanically rather than promised in prose.

    A profile that resolves any slot to a hosted provider breaks section 1a, and
    this is the check that says so before a child's drawing is sent anywhere.
    """
    hosted = sorted(slot for slot, config in profile.items() if config.provider not in LOCAL)
    detail = (
        "every slot resolves to a local provider"
        if not hosted
        else f"these slots leave the box: {', '.join(hosted)}"
    )
    return Finding("nothing leaves the box", not hosted, detail, {"hosted": hosted})


def check_tokens_per_second(profile: dict[str, SlotConfig], slot: str) -> Finding:
    """One real call, timed. Needs the model actually serving."""
    try:
        client = build_client(resolve(slot, profile))
        started = time.monotonic()
        result = client.chat(TOKENS_PROMPT, [to_data_uri(DRAWING)])
    except Exception as error:
        return Finding(f"{slot} answers", False, f"{type(error).__name__}: {error}")
    elapsed = time.monotonic() - started
    rate = result.output_tokens / elapsed if elapsed else 0.0
    return Finding(
        f"{slot} answers",
        bool(result.text.strip()),
        f"{result.output_tokens} tokens in {elapsed:.1f}s, {rate:.1f} tokens/s",
        {"tokens": result.output_tokens, "seconds": round(elapsed, 2), "tokens_per_s": round(rate, 1)},
    )


def check_the_page_is_built() -> Finding:
    """The demo is a page. A box with no page on it demos nothing."""
    page = Path(__file__).parents[1] / "page" / "index.html"
    size = page.stat().st_size if page.is_file() else 0
    return Finding(
        "the page is built",
        size > 0,
        f"{page} is {size} bytes" if size else f"{page} is missing; run sh studio/page/build.sh",
    )


def check_the_tools_are_here() -> Finding:
    """What has to be installed before any of the above can be tried for real."""
    wanted = ("llama-server", "python3")
    missing = [tool for tool in wanted if not shutil.which(tool)]
    detail = "all present" if not missing else f"missing: {', '.join(missing)}"
    return Finding("the tools are here", not missing, detail, {"missing": missing})


def run(profile_name: str = "spark", full: bool = False) -> list[Finding]:
    profile = load_profile(profile_name)
    findings = [
        check_the_box(),
        check_the_ceiling(),
        check_the_studio_fits(profile),
        check_mode_switching(),
        check_nothing_leaves_the_box(profile),
        check_the_page_is_built(),
        check_the_tools_are_here(),
    ]
    if full:
        findings.append(check_tokens_per_second(profile, "vlm.studio"))
    return findings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Measure the box on the first day")
    parser.add_argument("--profile", default="spark")
    parser.add_argument("--full", action="store_true", help="also call the models; needs them serving")
    parser.add_argument("--json", dest="as_json", action="store_true", help="print findings as JSON")
    arguments = parser.parse_args(argv)

    findings = run(arguments.profile, arguments.full)
    if arguments.as_json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
        return
    for finding in findings:
        print(finding.line())
    failed = [finding.name for finding in findings if not finding.ok]
    print()
    print(
        f"{len(findings) - len(failed)} of {len(findings)} answered as expected"
        + (f"; look at: {', '.join(failed)}" if failed else "")
    )
    print("Every number above belongs in docs/measured/ before anything is built on it.")


if __name__ == "__main__":
    main()
