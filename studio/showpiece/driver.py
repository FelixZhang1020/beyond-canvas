"""The agent loop for the showpiece skills: one JSON action per turn, run as a plain argv
list, the result and any picture shown back to the model, every step written to the ledger and
to the run's event list, and a cap so a looping model stops. Any chat model that returns text
can drive it; native tool calling is not needed.
"""
from __future__ import annotations

import json
import shutil
import shlex
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from studio.core.errors import EmptyCompletion, ModelUnavailable
from studio.core.images import to_data_uri
from studio.core.ledger import Entry, Ledger, hash_inputs
from studio.showpiece import catalog
from studio.showpiece.blender_bin import run_tool
from studio.showpiece.files import is_picture, listing, read_file, read_reference

PROTOCOL = Path(__file__).with_name("prompts") / "protocol.txt"
# Every turn's message, named so the prompt page in system management can show it.
ASK_PROMPT = "Request: {request}\n\nSo far:\n{so_far}\n\nYour next action:"
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
# Step 3.7 Flash bills its hidden thinking as completion tokens; a long prompt makes it think long.
MAX_TOKENS, RETRY_TOKENS = 6000, 12000
RATE_PAUSE_S = 7.0
PICTURE = (".png", ".jpg", ".jpeg")
RECENT = 8      # a file read longer ago than this many events is shown as a stub: nine full reads thought a run to death


@dataclass
class Run:
    id: str
    dir: Path
    request: str
    model: str
    agent_name: str
    events: list = field(default_factory=list)
    done: bool = False
    busy: dict | None = None        # what the run is doing between events, for the exhibit's heartbeat
    cond: threading.Condition = field(default_factory=threading.Condition)

    def push(self, event: dict) -> None:
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.done = True
            self.cond.notify_all()


def parse_action(text: str) -> dict | None:
    """The first JSON object in the reply that is an action. Everything from the first brace to the
    last was read as one, so two objects, or an object and a sentence with a brace in it, read as
    nothing; a live run was stopped by two such replies in a row."""
    text, decoder = text or "", json.JSONDecoder()
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        try:
            data, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("final" in data or ("skill" in data and "tool" in data)):
            return data
    return None


def transcript(events: list[dict], pictures: bool = True) -> str:
    lines = []
    for e in events:
        if e["kind"] == "think":
            lines.append(f"{e['step']}. think: {e['text']}")
        elif e["kind"] == "act":
            shown = e["text"] if e.get("tool") == "read" else e["text"][-600:]
            if e.get("tool") == "read" and e is not events[-1] and events.index(e) < len(events) - RECENT:
                shown = shown[:240] + " ... (read in full at that step; read it again if you need it)"
            lines.append(f"{e['step']}. act {e['skill']}/{e['tool']} {json.dumps(e['args'])} -> {shown}"
                         + (f" [wrote {', '.join(e['files'])}]" if e.get("files") else "")
                         + ((f" [picture {e['picture']} attached]" if pictures else
                             f" [picture {e['picture']} made; you are not shown pictures]") if e.get("picture") else ""))
        elif e["kind"] == "look":
            lines.append(f"{e['step']}. look: {json.dumps(e['verdict'])}")
        elif e["kind"] == "bounce":
            lines.append(f"{e['step']}. harness: {e['text']}")
    return "\n".join(lines)


def command_line(argv: list[str]) -> str:
    """The argv as the shell line it amounts to: the binary by its name, paths relative to the
    repository, arguments with spaces quoted."""
    root = str(catalog.ROOT) + "/"
    words = [a[len(root):] if a.startswith(root) else a for a in argv]
    if words and words[0].lower().endswith(("/blender", "/blender.exe")):
        words[0] = "blender"
    return shlex.join(words)


def replay(run_dir: Path) -> list[dict]:
    path = Path(run_dir) / "events.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event(step, kind, text="", **more) -> dict:
    return {"step": step, "kind": kind, "text": text, "tokens": 0, **more}


class Driver:
    def __init__(self, client, model_path, runs_root, skills=None, cap: int = 40, agent_name="Step 3.7 Flash",
                 quick: dict | None = None, *, protocol: Path = PROTOCOL, always=("model-anatomy", "shot-judge"), gate=None,
                 withheld: dict | None = None, pictures: bool = True, keep: bool = False,
                 think: tuple[int, int] = (MAX_TOKENS, RETRY_TOKENS)):
        self.client = client
        self.think = think                       # a turn's token budget, and the one retry's when it all went on thinking
        self.keep = keep                         # keep the hall after every placing call and every picture, by step
        self.pictures = pictures                 # False for a builder that reads text only: told, never sent
        self.withheld = dict(withheld or {})     # (skill, tool) -> the sentence that refuses it in this kind of run
        self.protocol, self.always = protocol, frozenset(always)
        self.gate = gate                         # who decides a "final" is a hand-over; None takes the model's word
        self.model_path = Path(model_path) if model_path else None
        self.quick = quick                       # render defaults for a live run on a stage, or None for full size
        self.runs_root = Path(runs_root)
        self.skills, self.cap, self.agent_name = skills or catalog.load_skills(), cap, agent_name
        self.runs: dict[str, Run] = {}

    def system_prompt(self, run_dir: Path, used: set[str] = frozenset()) -> str:
        """The protocol and the index of every skill; the full instructions only of the skills the
        run has used or is about to use, the way a skill loads on trigger rather than all at once."""
        index = "\n".join(f"- {s.name}: {s.description}" for s in self.skills.values())
        text = self.protocol.read_text(encoding="utf-8").replace("{skills}", index).replace("{run_dir}", str(run_dir))
        bodies = [f"### {name}\n{self.skills[name].body}" for name in self.skills if name in used]
        if not self.pictures:
            text += ("\n\nYou are not shown pictures: you read text only. Judge a picture by the checks' numbers "
                     "and the eyes' verdicts on it (shot-judge), which look for you.")
        return text + ("\n\nInstructions of the skills in use:\n\n" + "\n\n".join(bodies) if bodies else "")

    def start(self, request: str, model: Path | None = None) -> Run:
        run = self._new_run(request, model)
        threading.Thread(target=self._loop, args=(run,), daemon=True).start()
        return run

    def run_sync(self, request: str, model: Path | None = None, from_nothing: bool = False,
                 seed: dict[str, Path] | None = None, show: str | None = None) -> Run:
        """`show` names a picture in the run folder the model is shown with its first turn, such as a brief's photograph."""
        run = self._new_run(request, model, from_nothing, seed)
        self._loop(run, show)
        return run

    def _new_run(self, request: str, model: Path | None = None, from_nothing: bool = False,
                 seed: dict[str, Path] | None = None) -> Run:
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        for name, source in (seed or {}).items():     # files the runner made before the run, such as the temple's loads
            shutil.copyfile(source, run_dir / name)
        if from_nothing:                         # the run's model is the hall it makes; the standing one is reference only
            model = run_dir / "hall.blend"
        run = Run(run_id, run_dir, request, str(model or self.model_path or ""), self.agent_name)
        (run_dir / "request.json").write_text(json.dumps({
            "request": request, "model": run.model, "agent": run.agent_name,
            "started": datetime.now(UTC).isoformat()}), encoding="utf-8")
        self.runs[run_id] = run
        return run

    def _record(self, run: Run, ledger: Ledger, event: dict) -> None:
        event["at"] = datetime.now(UTC).isoformat()
        run.push(event)
        with open(run.dir / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        ledger.append(Entry(session=run.id, stage=f"{event['step']:02d}", skill=event.get("skill") or "showpiece",
                            gate=event["kind"], inputs_hash=hash_inputs(run.request, event["step"]),
                            outputs_path=str(run.dir / (event.get("picture") or "")), tokens=event.get("tokens", 0)))

    def _ask(self, run: Run, picture: str | None):
        used = {e["skill"] for e in run.events if e.get("skill")} | self.always
        prompt = ASK_PROMPT.format(request=run.request, so_far=transcript(run.events, self.pictures) or "(nothing yet)")
        shown = run.dir / picture if picture and self.pictures else None
        images = [to_data_uri(shown, max_edge=1024)] if shown is not None and shown.is_file() else []
        system = self.system_prompt(run.dir, used)
        for attempt in range(4):
            try:
                return self.client.chat(prompt, images, system=system, max_tokens=self.think[0])
            except EmptyCompletion:
                return self.client.chat(prompt, images, system=system, max_tokens=self.think[1])
            except ModelUnavailable as error:
                if "429" not in str(error) or attempt == 3:
                    raise
                time.sleep(RATE_PAUSE_S)   # StepFun allows ten requests a minute on this key
        raise ModelUnavailable("the model stayed rate-limited")

    def _loop(self, run: Run, picture: str | None = None) -> None:
        ledger = Ledger(run.dir / "ledger.jsonl")
        step, acts, unreadable, bounced = 0, 0, 0, 0
        try:
            while True:
                run.busy = {"phase": "thinking", "started": time.monotonic()}
                try:
                    reply = self._ask(run, picture)
                except EmptyCompletion as error:
                    self._record(run, ledger, _event(step + 1, "stop", f"the model spent its whole budget thinking: {error}"))
                    return
                picture = None
                action = parse_action(reply.text)
                tokens = reply.input_tokens + reply.output_tokens
                step += 1
                if action is None:
                    unreadable += 1
                    if unreadable >= 2:
                        self._record(run, ledger, _event(step, "stop", "the answer could not be read twice; stopped", tokens=tokens,
                                                         raw=(reply.text or "")[:600]))
                        return
                    self._record(run, ledger, _event(step, "think", "(the answer could not be read as one JSON object; answer again with JSON only)",
                                                     tokens=tokens, raw=(reply.text or "")[:600]))   # kept, so a stop can be read
                    continue
                unreadable = 0      # one retry for each answer; two strays five steps apart once ended a run
                self._record(run, ledger, _event(step, "think", str(action.get("think", "")), tokens=tokens))
                if "final" in action:
                    step += 1
                    bounced += 1
                    ending = self._hand_over(run, action, step, bounced)
                    self._record(run, ledger, ending)
                    if ending["kind"] == "bounce":
                        continue
                    return
                spent = self.gate.refuses(run.events, action) if self.gate else None
                if spent:
                    step += 1
                    self._record(run, ledger, _event(step, "stop", spent))
                    return
                if acts >= self.cap:
                    step += 1
                    self._record(run, ledger, _event(step, "stop", f"the cap of {self.cap} actions was reached"))
                    return
                acts += 1
                step += 1
                event = self._act(run, action)
                event["step"] = step
                if self.gate:
                    event["text"] += self.gate.lap_opened(run.events + [event])
                self._record(run, ledger, event)
                if self.keep:
                    self._keep(run, event)
                picture = event.get("picture")
                if event.get("verdict") is not None:
                    step += 1
                    self._record(run, ledger, _event(step, "look", event["verdict"].get("seen", ""), skill="shot-judge",
                                                     verdict=event["verdict"]))
        except Exception as error:   # noqa: BLE001 - a run must end with a recorded stop, never vanish
            self._record(run, ledger, _event(step + 1, "stop", f"the run failed: {type(error).__name__}: {error}"))
        finally:
            run.finish()

    def _hand_over(self, run: Run, action: dict, step: int, asked: int) -> dict:
        """What a "final" becomes. With no gate it is the model's word, as it always was; with one,
        the run folder decides: handed over, sent back with the reasons, or stopped as not adopted."""
        owed = self.gate.outstanding(run.dir, run.events) if self.gate else []
        if not owed:
            return _event(step, "final", str(action["final"]), adopted=self.gate is not None)
        if asked <= self.gate.bounces:
            return _event(step, "bounce", "not handed over yet: " + "; ".join(owed), skill="adoption")
        return _event(step, "stop", f"not adopted after {asked - 1} refusals: " + "; ".join(owed))

    @staticmethod
    def _keep(run: Run, event: dict) -> None:
        """What a run overwrites, kept under the step that made it: the hall after every placing call
        (stages/step-N.blend) and every picture and video a tool wrote (media/step-N-<name>), so a replay
        can show each step as it was and not only the last."""
        spec = catalog.TOOLS.get((event.get("skill"), event.get("tool")))
        if spec is None or "command" not in event or str(event.get("text", "")).startswith("exit "):
            return
        step, since = event["step"], time.time() - float(event.get("seconds") or 0) - 2
        if spec.work and run.model and Path(run.model).is_file():
            (run.dir / "stages").mkdir(exist_ok=True)
            shutil.copyfile(run.model, run.dir / "stages" / f"step-{step}.blend")
        for name in {*spec.outputs, *([event["picture"]] if event.get("picture") else [])}:
            made = run.dir / name
            if name.lower().endswith((*PICTURE, ".mp4")) and made.is_file() and made.stat().st_mtime >= since:
                (run.dir / "media").mkdir(exist_ok=True)
                shutil.copyfile(made, run.dir / "media" / f"step-{step}-{name}")

    @staticmethod
    def _makes_its_own_hall(run: Run) -> bool:
        """Only a from-nothing run does: its model is a hall.blend inside its own folder. Any other run's
        model is a file it was handed, such as the standing temple, and a tool that saves over it destroys it."""
        return bool(run.model) and Path(run.model).resolve().parent == run.dir.resolve()

    def _refuse(self, run: Run, skill: str, tool: str) -> str:
        """Write down who wanted what, and which rule stopped them, then say so to the model.

        The record is the point. A refusal nobody can read afterwards is indistinguishable
        from a tool that was never asked for, and the whole reason to declare a limit is to
        be able to show, later, that it held.
        """
        declared = ", ".join(self.skills[skill].allowed) or "nothing"
        receipt = {"at": datetime.now(UTC).isoformat(), "run": run.id, "agent": run.agent_name,
                   "wanted": f"{skill}/{tool}", "stopped_by": f"{skill}/SKILL.md allowed-tools",
                   "declared": declared}
        path = run.dir / "refusals.json"
        kept = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        path.write_text(json.dumps(kept + [receipt], indent=1), encoding="utf-8")
        return (f"REFUSED {skill}/{tool}: {skill} does not declare it. Its SKILL.md allows {declared}. "
                f"The refusal is written to refusals.json.")

    def _act(self, run: Run, action: dict) -> dict:
        skill, tool = catalog.named(action)   # "model-anatomy/bearing" means the bearing tool of that skill
        args = {str(k).lstrip("-"): v for k, v in dict(action.get("args") or {}).items()}
        base = {"kind": "act", "skill": skill, "tool": tool, "args": args, "files": [], "picture": None,
                "verdict": None, "tokens": 0, "seconds": 0.0}
        if tool == "read":
            wanted = str(args.get("file", ""))
            if skill in self.skills and wanted.startswith("references/"):     # the skill's own document, not a run file
                return {**base, "command": f"read {skill}/{wanted}",
                        "text": read_reference(self.skills[skill].folder, wanted)}
            name = catalog.inside_run(run.dir, wanted)
            return {**base, "skill": "showpiece", "command": f"read {name}", "text": read_file(run.dir, name)}
        if (skill, tool) in self.withheld:          # refused before anything runs: no command, so no check and no lap
            return {**base, "text": self.withheld[(skill, tool)]}
        spec = catalog.TOOLS.get((skill, tool))
        if spec is None or skill not in self.skills:     # a run has the tools of the skills it was given, no others
            return {**base, "text": f"no such tool {skill}/{tool}; the tools are "
                    + ", ".join("/".join(k) for k in catalog.TOOLS if k[0] in self.skills)}
        if not self.skills[skill].may_run(skill, tool):   # the skill's own `allowed-tools`, before anything runs
            return {**base, "text": self._refuse(run, skill, tool)}
        if spec.work and not self._makes_its_own_hall(run):
            return {**base, "text": f"REFUSED {skill}/{tool} writes a hall, and this run makes none: it may only "
                                    "write the hall.blend in its own run folder, never the model it was given"}
        model = self.model_path if spec.reference else Path(run.model) if run.model else self.model_path
        if "joints" in spec.flags:              # the joints were cut into a copy, and that copy is what it shows
            model = catalog.jointed(args, run.dir) or model
        if spec.needs_model and model is not None and not model.is_file():
            return {**base, "text": f"there is no {model.name} yet: place a part of the hall first"}
        args = catalog.known_inputs(spec, args, run.dir)
        effective = catalog.quick_args(spec, args, self.quick)   # what the tool really runs with; the heartbeat counts frames by it
        try:
            argv = catalog.argv_for(spec, effective, model if spec.needs_model else None, run.dir,
                                    hall=Path(run.model) if spec.work and run.model else None)
        except (ValueError, RuntimeError) as error:
            return {**base, "text": str(error)}
        absent = [str(args[k]) for k in sorted(catalog.INPUT_KEYS) if k in args and not catalog.input_path(run.dir, args[k]).is_file()]
        if absent:
            return {**base, "text": f"no such file {absent[0]!r} in the run folder, which holds: {listing(run.dir)}"}
        before = {p.name for p in run.dir.iterdir()}
        started = time.monotonic()
        run.busy = {"phase": "tool", "skill": skill, "tool": tool, "args": effective, "started": started}
        base["command"] = command_line(argv)       # the page shows exactly what ran, so nobody mistakes it for a script
        code, tail = run_tool(argv, spec.timeout_s, cwd=catalog.ROOT)
        run.busy = None
        seconds = round(time.monotonic() - started, 1)
        new = sorted(p.name for p in run.dir.iterdir() if p.name not in before)
        picture = next((n for n in new if n.lower().endswith(PICTURE) and is_picture(run.dir / n)), None)
        if spec.tool == "closeup" and args.get("out"):
            named = catalog.inside_run(run.dir, str(args["out"]))
            picture = named if is_picture(run.dir / named) else picture
        verdict = None
        if spec.tool == "judge":
            match = JSON_BLOCK.search(tail)
            try:
                verdict = json.loads(match.group(0)) if match else None
            except json.JSONDecodeError:
                verdict = None
        text = tail if code == 0 else f"exit {code}: {tail}"
        if self.gate and code == 0:
            text += self.gate.explain(run.dir, skill, tool)     # a check's answer comes back with its reasons
        return {**base, "text": text, "files": new, "picture": picture, "verdict": verdict, "seconds": seconds}
