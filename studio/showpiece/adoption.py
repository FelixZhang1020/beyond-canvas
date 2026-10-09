"""Whether a hall made from nothing may be handed over, decided by the harness and not the model.

The protocol has always asked the model to check its work; nothing made it. This is the part
that does: when the model says it has finished, the run folder is read, and the hand-over is
refused while any check is missing, older than the last change to the hall, or failed. The
reasons go back to the model as its next turn. The harness also counts the repair laps and the
refusals itself, so a model that loops is stopped by a number it cannot argue with.

Adopted means all of: nothing hangs in mid-air (bearing), nothing fell or shifted when every
piece was let go for at least three seconds (settle), the three shadows each share enough of the
temple's outline and every column stands in its place (likeness), and a separate pair of eyes
passed the side-by-side picture (shot-judge). Likeness includes the frame: tie beams at the column
heads, the roof rings, ridge and rafters, and a bracket set on every column, so a box with the
temple's outline and its columns inside is not adopted. And no column may carry more than its
timber can bear, snow on the roof and the column's slenderness counted (load-path weights), and
nothing may come down when the ground shakes like the design earthquake at the temple's site and the
hall is then pulled steadily sideways as hard as that site's frequent earthquake (load-path shake).
What this does not promise: that the hall is the temple piece for piece, or that a real building
drawn this way would stand.

A hall designed from a written brief has no temple to be alike: there the last check is the brief's
(hall-carpenter brief: its bays, its size, its rings of columns, its bracket sets, a whole frame, nothing
through the roof) and the eyes judge the brief's photograph above the hall. Everything else is the same.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from studio.showpiece import catalog
from studio.showpiece.blender_bin import run_tool

CHECKS = (("model-anatomy", "inventory"), ("model-anatomy", "bearing"), ("load-path", "weights"),
          ("load-path", "settle"), ("load-path", "shake"), ("hall-carpenter", "likeness"))
LIKENESS = CHECKS[-1]
PICTURE = "likeness.png"


@dataclass(frozen=True)
class Look:
    """The check that says the hall is the building that was asked for, the file it writes, and the
    picture the eyes must pass: the temple's likeness in a rebuild, the brief's in a design."""
    check: tuple[str, str]
    verdict: str
    ok: str
    short: str
    picture: str
    claim: str                # what the check's file must say, in the sentence when it does not


TEMPLE = Look(LIKENESS, "likeness.json", "alike", "short_of_the_temple", PICTURE, "the hall is alike")
BRIEF = Look(("hall-carpenter", "brief"), "brief-check.json", "meets", "short_of_the_brief", "brief.png",
             "the hall meets the brief")


def ran(event: dict) -> bool:
    """A tool that really ran and exited clean; a refusal before the run has no command."""
    return event.get("kind") == "act" and "command" in event and not str(event.get("text", "")).startswith("exit ")


def placing(event: dict) -> bool:
    spec = catalog.TOOLS.get((event.get("skill"), event.get("tool")))
    return bool(spec and spec.work and ran(event))


def in_the_run(event: dict, run_dir: Path) -> bool:
    """A check looked at this hall only if it wrote into the run folder, whose files are what the gate reads."""
    out = str((event.get("args") or {}).get("out_dir", "."))
    return (Path(run_dir) / out).resolve() == Path(run_dir).resolve()


def _last(events: list[dict], skill: str, tool: str, after: int, run_dir: Path) -> int | None:
    found = [i for i, e in enumerate(events) if i > after and ran(e) and in_the_run(e, run_dir)
             and (e.get("skill"), e.get("tool")) == (skill, tool)]
    return found[-1] if found else None


def _json(run_dir: Path, name: str) -> dict:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


@dataclass(frozen=True)
class Adoption:
    bounces: int = 3          # refusals of a hand-over before the run is stopped as not adopted
    laps: int = 6             # times the hall may be changed again after a check has looked at it
    min_seconds: float = 3.0  # how long every piece must be let go for; settle writes it into its summary
    look: Look = TEMPLE       # what "the building asked for" means: the temple's likeness, or a brief

    @property
    def checks(self) -> tuple[tuple[str, str], ...]:
        return CHECKS[:-1] + (self.look.check,)

    def explain(self, run_dir: Path, skill: str, tool: str) -> str:
        """After a check, the fault report's one line, so the reasons arrive with the answer instead
        of waiting for the model to ask. The first live run asked once, then read a stale faults.json."""
        if (skill, tool) not in self.checks[1:]:
            return ""
        spec = catalog.TOOLS[("hall-carpenter", "faults")]
        code, tail = run_tool(catalog.argv_for(spec, {"out_dir": "."}, None, run_dir), spec.timeout_s, cwd=catalog.ROOT)
        lines = [line for line in tail.splitlines() if line.startswith("FAULTS")]
        return "\n" + lines[-1] if code == 0 and lines else ""

    def laps_used(self, events: list[dict]) -> int:
        laps, checked = 0, False
        for e in events:
            if placing(e):
                laps, checked = laps + checked, False
            elif ran(e) and (e.get("skill"), e.get("tool")) in self.checks[1:]:     # inventory reads; it finds no fault
                checked = True
        return laps

    def lap_opened(self, events: list[dict]) -> str:
        """Said with the placing call that opened a repair lap, as it happens. Design run 3 checked
        a half-built hall after nearly every part, every check passing, and each part placed after a check
        opened a lap: all six were gone before its roof was on, while run 4, on the same code, placed the whole
        hall first and was adopted. The rule was the gate's and was never said to the builder."""
        used = self.laps_used(events)
        if used and used > self.laps_used(events[:-1]):
            return (f"\n(this change came after a check, so it opens repair lap {used} of {self.laps}: every part placed "
                    "after any check opens one, even after a check that passed; place the whole hall before checking it)")
        return ""

    def refuses(self, events: list[dict], action: dict) -> str | None:
        """The sentence that stops the run when this action would open one repair lap too many."""
        spec = catalog.TOOLS.get(catalog.named(action))
        if not (spec and spec.work):
            return None
        checked_since = False
        for e in reversed(events):
            if placing(e):
                break
            if ran(e) and (e.get("skill"), e.get("tool")) in self.checks[1:]:
                checked_since = True
        if checked_since and self.laps_used(events) >= self.laps:
            return f"not adopted: all {self.laps} repair laps are used and the hall still has faults"
        return None

    def outstanding(self, run_dir: Path, events: list[dict]) -> list[str]:
        """Every reason the hall cannot be handed over yet; empty means adopted."""
        changed = [i for i, e in enumerate(events) if placing(e)]
        if not changed:
            return ["nothing has been placed yet"]
        at = {check: _last(events, *check, after=changed[-1], run_dir=run_dir) for check in self.checks}
        reasons = [f"the hall changed after the last {skill}/{tool}, or it never ran: run it" for (skill, tool), i
                   in at.items() if i is None]
        inventory, bearing, weights, settle = (at[c] for c in self.checks[:4])
        if None not in (inventory, bearing, settle) and not inventory < bearing < settle:
            reasons.append("inventory, bearing and settle must run in that order, each reading the one before")
        if None not in (bearing, weights) and weights < bearing:
            reasons.append("weights must run after bearing, reading its bearing.json")
        shake = at[("load-path", "shake")]
        if None not in (bearing, shake) and shake < bearing:
            reasons.append("shake must run after bearing, reading its bearing.json")
        if reasons:
            return reasons
        carrying = _json(run_dir, "bearing.json")
        if not carrying:            # a missing file once read as nothing hanging
            reasons.append("bearing.json is missing from the run folder: run model-anatomy bearing again")
        floating = len(carrying.get("floating", {}))
        if floating:
            reasons.append(f"{floating} pieces hang in mid-air (hall-carpenter/faults says which and by how much)")
        loads = _json(run_dir, "loads.json").get("summary", {})
        if not loads:               # and a missing one as nothing overloaded
            reasons.append("loads.json is missing from the run folder: run load-path weights again")
        for what, remedy in (("column", "make the columns thicker"),
                             ("post", "a frame post's size is fixed, so lighten what stands on it")):
            weak = [c for c in loads.get("overloaded", []) if c.get("what", "column") == what]
            if weak:
                many, name = len(weak) > 1, "column" if what == "column" else "frame post"
                reasons.append(f"{len(weak)} {name}{'s' if many else ''} carr{'y' if many else 'ies'} more than "
                               f"{'their' if many else 'its'} timber can bear (over {loads.get('allowed_MPa', 10):g} MPa): "
                               + ", ".join(f"{c['name']} at {c.get('design_MPa') or c['stress_MPa']:.1f} MPa" for c in weak[:4])
                               + f"; {remedy}")
        summary = _json(run_dir, "settle.json").get("summary", {})
        seconds = summary.get("seconds")      # it counted thirty frames once, and 1.25 s at 24 a second passed
        if seconds is None:
            reasons.append("the gravity test does not say how long it ran: run it again")
        elif seconds < self.min_seconds:
            reasons.append(f"the gravity test ran for {seconds:g} s, less than three seconds")
        if summary.get("fell", 1) or summary.get("shifted", 1):
            reasons.append(f"under gravity {summary.get('fell', '?')} pieces fell and {summary.get('shifted', '?')} shifted")
        shaken = _json(run_dir, "shake.json").get("summary", {}).get("shake", {})
        if shaken.get("came_down", 1):
            reasons.append(f"{shaken.get('came_down', '?')} pieces came down when the ground shook at {shaken.get('peak_g', '?')} g "
                           f"and the hall was pulled sideways at {shaken.get('pull_g', '?')} g: "
                           + ", ".join(shaken.get("came_down_names", [])[:4])
                           + "; a piece only stood on end is pulled over, so cut it into what carries it or make it stockier")
        look = self.look
        likeness = _json(run_dir, look.verdict)
        if not likeness.get(look.ok):
            reasons += likeness.get(look.short) or [f"{look.verdict} does not say {look.claim}"]
        picture = (Path(run_dir) / look.picture).resolve()     # this run's picture, not any file of that name
        looks = [e for i, e in enumerate(events) if i > at[look.check] and (e.get("skill"), e.get("tool")) == (
            "shot-judge", "judge") and (Path(run_dir) / str((e.get("args") or {}).get("image", ""))).resolve() == picture
            and e.get("verdict")]
        if not looks:
            reasons.append(f"the eyes have not looked at {look.picture} since it was made: judge it")
        elif looks[-1]["verdict"].get("verdict") != "pass":
            reasons.append(f"the eyes did not pass {look.picture}: {looks[-1]['verdict'].get('change', '')}")
        return reasons
