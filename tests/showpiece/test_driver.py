"""The driver: one JSON action per turn, tools run as argv, every step in the ledger, a cap."""
import json

from conftest import FakeClient
from studio.showpiece import driver as drv


def script(*replies):
    return FakeClient([json.dumps(r) for r in replies])


def test_a_two_step_run_reaches_final_and_is_ledgered(blender, stack_model, tmp_path):
    client = script(
        {"think": "read the model first", "skill": "model-anatomy", "tool": "inventory", "args": {"out_dir": "."}},
        {"think": "done", "final": "eleven pieces, anatomy.json written"},
    )
    d = drv.Driver(client, stack_model, tmp_path, cap=5)
    run = d.run_sync("What is in this model?")
    kinds = [e["kind"] for e in run.events]
    assert kinds == ["think", "act", "think", "final"]
    assert (run.dir / "anatomy.json").is_file()
    assert "ANATOMY 11 pieces" in run.events[1]["text"]
    assert "inventory.py" in run.events[1]["command"] and "stack" in run.events[1]["command"], "the step says the command it ran"
    lines = (run.dir / "events.jsonl").read_text().splitlines()
    assert len(lines) == 4 and json.loads(lines[-1])["kind"] == "final"
    assert drv.replay(run.dir)[1]["tool"] == "inventory"
    assert client.calls[1]["prompt"].count("1. think") == 1 and "ANATOMY 11" in client.calls[1]["prompt"]


def test_an_unreadable_answer_is_returned_once_then_the_run_stops(tmp_path):
    d = drv.Driver(FakeClient(["not json", "still not json"]), None, tmp_path, cap=5)
    run = d.run_sync("anything")
    assert run.events[-1]["kind"] == "stop" and "could not be read" in run.events[-1]["text"]
    assert [e["kind"] for e in run.events] == ["think", "stop"], "one retry with a hint, then stop"


def test_the_retry_is_for_each_answer_so_two_strays_apart_do_not_end_a_run(tmp_path):
    """A live 松开手 was stopped by one unreadable answer at step 5 and another at step 10,
    with good ones between: the count never started again."""
    look = {"think": "look", "skill": "showpiece", "tool": "read", "args": {"file": "request.json"}}
    done = {"think": "done", "final": "done"}
    d = drv.Driver(FakeClient(["not json", json.dumps(look), "still not json", json.dumps(done)]), None, tmp_path, cap=5)
    run = d.run_sync("anything")
    assert [e["kind"] for e in run.events] == ["think", "think", "act", "think", "think", "final"]


def test_an_action_is_read_from_a_reply_with_two_objects_or_a_brace_after_it():
    """Everything from the first brace to the last was read as one object, so these read as nothing."""
    act = {"think": "look", "skill": "showpiece", "tool": "read", "args": {"file": "a.json"}}
    assert drv.parse_action(json.dumps({"note": "first"}) + "\n" + json.dumps(act)) == act
    assert drv.parse_action(json.dumps(act) + " then I will judge {the still}") == act
    assert drv.parse_action("```json\n" + json.dumps(act) + "\n```") == act
    assert drv.parse_action('{"think": "cut off') is None


def test_an_unreadable_answer_is_kept_so_the_stop_can_be_read(tmp_path):
    run = drv.Driver(FakeClient(["prose {not json", "more prose"]), None, tmp_path, cap=5).run_sync("anything")
    assert [e.get("raw") for e in run.events] == ["prose {not json", "more prose"]


def test_the_cap_stops_a_looping_model(blender, stack_model, tmp_path):
    action = {"think": "again", "skill": "model-anatomy", "tool": "inventory", "args": {"out_dir": "."}}
    d = drv.Driver(script(*([action] * 6)), stack_model, tmp_path, cap=2)
    run = d.run_sync("loop")
    assert run.events[-1]["kind"] == "stop" and "cap" in run.events[-1]["text"]
    assert sum(1 for e in run.events if e["kind"] == "act") == 2


def test_a_picture_is_shown_to_the_model_on_the_next_turn(blender, stack_model, tmp_path):
    client = script(
        {"think": "look", "skill": "joint-reveal", "tool": "closeup",
         "args": {"out": "shot.png", "at": "9,-9,5", "look": "0,0,1.7", "width": 160, "height": 90}},
        {"think": "done", "final": "one shot"},
    )
    run = drv.Driver(client, stack_model, tmp_path, cap=5).run_sync("show me")
    assert run.events[1]["picture"] == "shot.png"
    assert client.calls[1]["images"] and client.calls[1]["images"][0].startswith("data:image/")


def test_a_failing_step_ends_the_run_with_a_stop_not_a_crash(tmp_path):
    class Broken:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            raise RuntimeError("the socket closed")
    run = drv.Driver(Broken(), None, tmp_path, cap=3).run_sync("anything")
    assert run.done and run.events[-1]["kind"] == "stop" and "socket closed" in run.events[-1]["text"]
    assert (tmp_path / run.id / "events.jsonl").is_file()


def test_only_a_real_image_is_shown_back(tmp_path):
    (tmp_path / "verdict.png").write_text('{"verdict": "pass"}')
    assert drv.is_picture(tmp_path / "verdict.png") is False, "a verdict the judge wrote under a .png name"
    from PIL import Image
    Image.new("RGB", (4, 4), (10, 20, 30)).save(tmp_path / "real.png")
    assert drv.is_picture(tmp_path / "real.png") is True
    assert drv.is_picture(tmp_path / "missing.png") is False


def test_the_transcript_names_what_each_act_wrote():
    events = [{"step": 1, "kind": "think", "text": "go"},
              {"step": 2, "kind": "act", "skill": "joint-reveal", "tool": "explode", "args": {"out_dir": "."},
               "text": "EXPLODE 9 pieces", "files": ["explode-open.png", "explode.mp4", "explode"], "picture": "explode-open.png"}]
    line = drv.transcript(events).splitlines()[1]
    assert "[wrote explode-open.png, explode.mp4, explode]" in line and "[picture explode-open.png attached]" in line


def test_a_missing_input_file_is_named_with_what_the_folder_holds(tmp_path):
    client = script({"think": "stage it", "skill": "raise-the-hall", "tool": "stages",
                     "args": {"--bearing": "tour/bearing.json", "anatomy": "anatomy.json", "out_dir": "."}},
                    {"think": "oh", "final": "stopped"})
    d = drv.Driver(client, None, tmp_path, cap=3)
    run = d._new_run("stage the stack")
    (run.dir / "anatomy.json").write_text("{}")
    (run.dir / "tour").mkdir()
    (run.dir / "tour" / "f0001.png").write_bytes(b"")
    d._loop(run)
    act = run.events[1]
    assert act["kind"] == "act" and "no such file 'tour/bearing.json'" in act["text"]
    assert "anatomy.json" in act["text"] and "tour/ (1 files)" in act["text"]
    assert act["args"] == {"bearing": "tour/bearing.json", "anatomy": "anatomy.json", "out_dir": "."}, "dashes dropped"


def test_a_skill_reference_is_read_on_request_and_nothing_outside_it_is(tmp_path):
    """The third level of an Agent Skill: the instructions name references/method.md, and the model
    can now open it. SKILL.md reached by climbing out of references/ is not a reference."""
    reads = [{"file": "references/method.md"}, {"file": "references/../SKILL.md"}, {"file": "references/nope.md"}]
    client = script(*[{"think": "look it up", "skill": "load-path", "tool": "read", "args": a} for a in reads],
                    {"think": "done", "final": "read"})
    run = drv.Driver(client, None, tmp_path, cap=5).run_sync("what does the settle test claim?")
    acts = [e for e in run.events if e["kind"] == "act"]
    assert acts[0]["text"].startswith("# What the three tests do") and acts[0]["command"] == "read load-path/references/method.md"
    assert "no such reference" in acts[1]["text"] and "references/method.md" in acts[1]["text"]
    assert "no such reference" in acts[2]["text"]
    assert "# Load path" in client.calls[1]["system"], "opening a skill's reference engages that skill's instructions"


def test_a_builder_that_reads_only_text_is_told_a_picture_was_made_and_is_never_sent_one(tmp_path):
    """NVIDIA's Nemotron 3 Nano on the Spark reads text only, and a picture in its request is refused
    there. Such a builder is told the picture exists; the eyes (shot-judge) still look at it."""
    from PIL import Image

    Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
    client = FakeClient([json.dumps({"think": "done", "final": "ok"})] * 2)
    run = drv.Run(id="r", dir=tmp_path, request="q", model="", agent_name="Nemotron")
    run.events.append({"kind": "act", "step": 1, "skill": "joint-reveal", "tool": "closeup", "args": {},
                       "text": "CLOSEUP ok", "files": ["shot.png"], "picture": "shot.png"})
    drv.Driver(client, None, tmp_path, cap=5, pictures=False)._ask(run, "shot.png")
    assert client.calls[0]["images"] == []
    assert "[picture shot.png made; you are not shown pictures]" in client.calls[0]["prompt"]
    drv.Driver(client, None, tmp_path, cap=5)._ask(run, "shot.png")
    assert client.calls[1]["images"] and "[picture shot.png attached]" in client.calls[1]["prompt"]


def test_a_builder_that_reads_only_text_is_told_so_before_it_starts(tmp_path):
    """The carpenter's protocol says the builder looks at the pictures its tools make; one that reads
    text only is told in the same instructions that the checks and the eyes' verdicts are what it has."""
    text_only = drv.Driver(FakeClient([]), None, tmp_path, pictures=False).system_prompt(tmp_path)
    seeing = drv.Driver(FakeClient([]), None, tmp_path).system_prompt(tmp_path)
    assert "not shown pictures" in text_only and "not shown pictures" not in seeing
