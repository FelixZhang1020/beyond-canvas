"""The recordings the dashboard replays are made by the tools themselves, one run folder each."""
import json
from pathlib import Path

import pytest

from studio.showpiece import record


def test_a_recorded_build_up_has_the_run_shape_and_every_third_frame(blender, stack_model, tmp_path):
    folder = record.record(stack_model, tmp_path / "runs", "raise", "none", quick=True)
    assert folder.name == "recorded-raise"
    request = json.loads((folder / "request.json").read_text())
    assert request["agent"] == "recorded" and request["request"]
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()]
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "think" and kinds[-1] == "final" and kinds.count("act") == 4, "inventory, bearing, stages, raise"
    raise_act = next(e for e in events if e.get("tool") == "raise")
    assert raise_act["seconds"] > 0 and "raise.mp4" in raise_act["files"] and raise_act["picture"]
    assert (folder / "scenes.json").is_file() and (folder / "anatomy.json").is_file()
    frames = sorted(p.name for p in (folder / "raise").iterdir() if p.name.endswith(".png"))
    assert frames and all(int(n[1:5]) % 3 == 1 for n in frames), "every third frame kept"


def _fake_tool(calls, code=0):
    def run_tool(argv, timeout_s, cwd=None):
        calls.append(timeout_s)
        return code, "boom" if code else "ok"
    return run_tool


def test_a_recording_is_built_aside_and_replaces_the_old_one_only_when_it_is_whole(monkeypatch, tmp_path):
    runs = tmp_path / "runs"
    old = runs / "recorded-raise"
    old.mkdir(parents=True)
    (old / "events.jsonl").write_text("{}\n")
    calls = []
    monkeypatch.setattr(record, "run_tool", _fake_tool(calls, code=1))
    with pytest.raises(RuntimeError):
        record.record(tmp_path / "hall.blend", runs, "raise", "none", timeout_s=42)
    assert (old / "events.jsonl").read_text() == "{}\n", "the page keeps the last good recording"
    assert (runs / "recorded-raise.part").is_dir(), "the failed attempt stays aside, for reading"
    assert calls == [42], "the caller's time limit reaches the tool"
    monkeypatch.setattr(record, "run_tool", _fake_tool(calls))
    folder = record.record(tmp_path / "hall.blend", runs, "raise", "none")
    assert folder == old and (old / "events.jsonl").read_text() != "{}\n"
    assert not (runs / "recorded-raise.part").exists()


def test_a_recorded_act_keeps_the_tools_result_line_however_much_it_printed_after(monkeypatch, tmp_path):
    result = "SETTLE 6264 pieces fell 0 shifted 0"
    tail = result + "\n" + "\n".join(f"bake: frame {i} :: 96" for i in range(1, 97)) + "\nBlender quit\n"
    assert len(tail) - len(result) > 1200, "the result line sits further back than the recorder used to keep"
    monkeypatch.setattr(record, "run_tool", lambda argv, timeout_s, cwd=None: (0, tail))
    folder = record.record(tmp_path / "hall.blend", tmp_path / "runs", "settle", "none")
    acts = [json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines() if '"act"' in line]
    assert all(result in act["text"] for act in acts), "the card line the page looks for is in the transcript"


def test_a_recording_speaks_the_chosen_language_and_can_be_reworded_without_rerunning(monkeypatch, tmp_path):
    monkeypatch.setattr(record, "run_tool", lambda argv, timeout_s, cwd=None: (0, "RAISE 3 scenes 9 frames"))
    folder = record.record(tmp_path / "hall.blend", tmp_path / "runs", "raise", "none", lang="en")
    first = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert first[0]["text"].isascii() and first[-1]["text"].isascii(), "English words"
    acts_before = [e for e in first if e["kind"] == "act"]
    record.reword(tmp_path / "runs", "raise", "zh")
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    after = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert request["lang"] == "zh" and not request["request"].isascii(), "the request is in Chinese now"
    assert not after[0]["text"].isascii() and not after[-1]["text"].isascii(), "so are the thought and the answer"
    assert [e for e in after if e["kind"] == "act"] == acts_before, "the tool steps are untouched"


def test_a_recorded_step_carries_the_command_it_ran_and_reword_fills_it_into_an_older_recording(monkeypatch, tmp_path):
    monkeypatch.setattr(record, "run_tool", lambda argv, timeout_s, cwd=None: (0, "RAISE 3 scenes 9 frames"))
    folder = record.record(tmp_path / "hall.blend", tmp_path / "runs", "raise", "none")
    acts = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"act"' in line]
    assert all("scripts/" in a["command"] and ".py" in a["command"] for a in acts), "each step says the script it ran"
    assert "inventory.py" in acts[0]["command"] and "hall.blend" in acts[0]["command"]
    for a in acts:
        del a["command"]
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    for e in events:
        e.pop("command", None)
    (folder / "events.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    record.reword(tmp_path / "runs", "raise", "zh")
    after = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"act"' in line]
    assert all("inventory.py" in after[0]["command"] for _ in [0]) and all(a.get("command") for a in after), "an older recording gains its commands"


def test_the_pull_apart_recording_films_the_joints_on_the_jointed_copy_and_keeps_no_copy(monkeypatch, tmp_path):
    """The corner set's recording cuts its three joints on a copy of the hall and films them
    close; the close-ups and their anatomy run on that copy, which the replay never reads and is not kept."""
    ran = []

    def run_tool(argv, timeout_s, cwd=None):
        ran.append(argv)
        if "joints.py" in " ".join(argv):
            (argv_dir := Path(argv[argv.index("--") + 1])).mkdir(parents=True, exist_ok=True)
            (argv_dir / "hall-joints.blend").write_bytes(b"x" * 10)
        return 0, "ok"
    monkeypatch.setattr(record, "run_tool", run_tool)
    folder = record.record(tmp_path / "hall.blend", tmp_path / "runs", "explode", "Column -12.50 -8.83")
    tools = [a[a.index("--python") + 1].rsplit("/", 1)[-1] for a in ran]
    assert tools == ["inventory.py", "bearing.py", "joints.py", "inventory.py", "explode.py"]
    models = [a[2] for a in ran]
    assert models[:3] == [str(tmp_path / "hall.blend")] * 3
    assert all(m.endswith("hall-joints.blend") for m in models[3:]), "the jointed anatomy and the close-ups"
    assert "--closeups" in ran[-1] and ran[-1][ran[-1].index("--anatomy") + 1].endswith("jointed/anatomy.json")
    assert not list(folder.glob("*-joints.blend*")), "47 MB the replay never reads"
    acts = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"act"' in line]
    assert [a.get("on") for a in acts][-2:] == ["jointed", "jointed"]
    record.reword(tmp_path / "runs", "explode", "zh")
    acts = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"act"' in line]
    assert "hall-joints.blend" in acts[-1]["command"], "a reworded recording still says which copy it ran on"
