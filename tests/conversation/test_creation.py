"""Real classroom orchestration with scripted models; no external generation."""
import json
from pathlib import Path

import pytest

from studio.classroom.classroom import Classroom
from studio.conversation.creation import pages
from studio.classroom.portfolio import Portfolio
from studio.providers.base import ChatResult

ALLOW = '{"verdict":"allow","reason":"drawing","text_found":[]}'


class Writer:
    def __init__(self):
        self.replies, self.prompts = [], []

    def chat(self, prompt, images=(), **kwargs):
        self.prompts.append((prompt, images))
        return ChatResult(self.replies.pop(0), 1, 1, 0, 0, 0, "test", "test")


@pytest.fixture
def setup(tmp_path):
    writer = Writer()
    room = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": writer, "vlm.director": writer})
    sid = room.begin({"language": "zh", "entrance": "colour"})
    image = Path("skills/art-feedback/evals/files/dog-sun.png").read_bytes()
    ids = [room.add_drawing(sid, image) for _ in range(2)]
    yield room, sid, ids, writer
    room.end(sid)


def execute(room, sid, skill, ids, options=None):
    rid = room.request(sid, skill, ids, options or {})["request_id"]
    room.run_request(rid)
    return next(data for name, data in room.follow(rid) if name == "done")


def test_scene_uses_full_dialogue_and_never_calls_media(setup):
    room, sid, ids, writer = setup
    room.sessions[sid].dialogue[ids[0]] = ["Child: 小兔去找朋友", "Companion: 怎么去？", "Child: 跳过去"]
    writer.replies = [ALLOW, "小兔跳向花园。"]
    first = execute(room, sid, "scene-description", ids[:1])
    assert first["outputs"]["text"] == "小兔跳向花园。"
    assert all(part in writer.prompts[-1][0] for part in ("小兔去找朋友", "怎么去", "跳过去"))
    assert writer.prompts[-1][1], "The original image must ground the scene."
    assert room.sessions[sid].conversations[ids[0]]._animation is None
    writer.replies = ["小兔轻轻跳了两下。"]
    second = execute(room, sid, "scene-description", ids[:1], {"previous": first["outputs"]["text"]})
    assert second["outputs"]["text"] != first["outputs"]["text"]
    assert "小兔跳向花园" in writer.prompts[-1][0]


def test_missing_scene_is_supplied_and_story_respects_order(setup):
    room, sid, ids, writer = setup
    order = list(reversed(ids))
    expected = [{"drawing_id": did, "text": text} for did, text in zip(order, ["遇见朋友。", "一起回家。"])]
    writer.replies = [ALLOW, ALLOW, "小屋亮起了灯。", json.dumps(expected, ensure_ascii=False)]
    out = execute(room, sid, "story-outline", order, {"scenes": {order[0]: "小兔遇见小猫。"}})["outputs"]
    assert out["outline"] == expected
    assert [s["supplemented"] for s in out["scenes"]] == [False, True]
    assert "小屋亮起了灯" in writer.prompts[-1][0]
    assert not any(c._animation for c in room.sessions[sid].conversations.values())
    # Confirming edited passages must not ask the writer to rewrite them again.
    expected[0]["text"] = "孩子修改的句子🌷。"
    calls = len(writer.prompts)
    book = execute(room, sid, "drawings-to-storybook", order, {"pages": expected})["outputs"]
    assert book["pages"] == expected
    assert len(writer.prompts) == calls


def test_a_story_written_page_after_page_without_its_list_is_still_the_story(setup):
    # The shape Qwen3.6 gave for four of ten five-picture books: every page right and in
    # order, but written one after another with no brackets or commas, and each one was refused.
    room, sid, ids, writer = setup
    expected = [{"drawing_id": did, "text": text} for did, text in zip(ids, ["遇见朋友。", "一起回家。"])]
    written = "\n".join(json.dumps(page, ensure_ascii=False, indent=2) for page in expected)
    writer.replies = [ALLOW, ALLOW, written]
    out = execute(room, sid, "story-outline", ids, {"scenes": {did: "已有场景" for did in ids}})["outputs"]
    assert out["outline"] == expected


def test_a_story_in_a_code_block_is_read_after_the_writing_on_its_first_drawing_is_taken_out(setup):
    # Live: the first drawing said "ZOO". Taking it out of the answer joins every line, so
    # "```json" and the story's "[" shared one, and six stories in a row were refused as unusable.
    room, sid, ids, writer = setup
    written = [{"drawing_id": ids[0], "text": "小鸟飞回了ZOO。"}, {"drawing_id": ids[1], "text": "一起回家。"}]
    fenced = "```json\n" + json.dumps(written, ensure_ascii=False, indent=2) + "\n```"
    writer.replies = [ALLOW.replace("[]", '["ZOO"]'), ALLOW, fenced]
    out = execute(room, sid, "story-outline", ids, {"scenes": {did: "已有场景" for did in ids}})["outputs"]
    assert out["outline"] == [{"drawing_id": ids[0], "text": "小鸟飞回了。"}, written[1]]


def test_a_story_that_stops_after_its_first_page_is_asked_for_again_before_the_teacher_hears_of_it(setup):
    # On the Spark: Qwen3.6 opened about a third of its stories with a bare "{" and stopped after
    # page 1, in about 2.5 s. The same request again wrote the whole story as often as the first did.
    room, sid, ids, writer = setup
    expected = [{"drawing_id": did, "text": text} for did, text in zip(ids, ["遇见朋友。", "一起回家。"])]
    writer.replies = [ALLOW, ALLOW, json.dumps(expected[0], ensure_ascii=False),
                      json.dumps(expected[:1], ensure_ascii=False), json.dumps(expected, ensure_ascii=False)]
    out = execute(room, sid, "story-outline", ids, {"scenes": {did: "已有场景" for did in ids}})["outputs"]
    assert out["outline"] == expected
    assert writer.prompts[-3][0] == writer.prompts[-1][0], "the same story was asked for three times"


@pytest.mark.parametrize("written", [
    '{"drawing_id": "a", "text": "One."}\n{"drawing_id": "b", "text": "Tw',
    '{"drawing_id": "b", "text": "Two."}\n{"drawing_id": "a", "text": "One."}',
    '{"drawing_id": "a", "text": "One."}\nThe end.',
])
def test_pages_one_after_another_are_still_refused_when_cut_off_reordered_or_followed_by_prose(written):
    from studio.conversation.creation import parse_outline
    with pytest.raises(ValueError):
        parse_outline(written, ["a", "b"])


def test_accepted_scenes_survive_outline_failure_but_changed_dialogue_rewrites_that_page(setup):
    room, sid, ids, writer = setup
    first, second = ids
    writer.replies = [ALLOW, "First accepted scene.", ALLOW, "Second accepted scene.", "[]", "[]", "[]"]
    stopped = execute(room, sid, "story-outline", ids)
    assert stopped["status"] == "stopped"
    assert room.sessions[sid].scenes == {}, "an unfinished outline must not publish its scenes"
    assert set(room.sessions[sid].accepted_scene_drafts) == set(ids)

    room.sessions[sid].dialogue[first] = ["Child: the dog goes home"]
    outline = [{"drawing_id": first, "text": "Home."}, {"drawing_id": second, "text": "The end."}]
    writer.replies = ["Revised first scene.", json.dumps(outline)]
    result = execute(room, sid, "story-outline", ids)
    assert result["outputs"]["outline"] == outline
    assert [page["text"] for page in result["outputs"]["scenes"]] == [
        "Revised first scene.", "Second accepted scene."]
    assert [page["supplemented"] for page in result["outputs"]["scenes"]] == [True, True]
    assert room.sessions[sid].accepted_scene_drafts == {}


def test_storybook_skips_director_but_standalone_scene_still_uses_it(tmp_path):
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import ALLOW, DRAWING, Scripted

    creator = Scripted(["First scene.", "Second scene."])
    reviewer = Scripted(['{"ok":true,"issues":[]}'])
    room = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": creator,
                      "vlm.creation": FrontFirst(creator, creator),
                      "vlm.director": reviewer, "safety.image": Scripted([ALLOW, ALLOW])})
    sid = room.begin({"language": "en", "entrance": "colour"})
    ids = [room.add_drawing(sid, Path(DRAWING).read_bytes()) for _ in range(2)]
    outline = [{"drawing_id": did, "text": f"Page {index}."} for index, did in enumerate(ids, 1)]
    creator.replies.extend((json.dumps(outline), "A revised scene."))
    try:
        result = execute(room, sid, "story-outline", ids)
        assert result["outputs"]["outline"] == outline
        assert len(creator.prompts) == 3 and not reviewer.prompts
        scene = execute(room, sid, "scene-description", ids[:1])
        assert scene["outputs"]["text"] == "A revised scene."
        assert len(reviewer.prompts) == 1, "animation descriptions keep independent review"
    finally:
        room.close()


def test_stopping_a_storybook_scene_discards_unpublished_scenes(tmp_path):
    from threading import Event, Thread
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import ALLOW, DRAWING, Scripted

    next_started, release = Event(), Event()

    class Creator:
        calls = 0

        def chat(self, prompt, images=(), **kwargs):
            self.calls += 1
            if self.calls == 2:
                next_started.set()
                assert release.wait(5)
            return ChatResult(f"Scene {self.calls}.", 1, 1, 0, 0, 0, "test", "test")

    creator = Creator()
    reviewer = Scripted([])
    room = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": creator,
                      "vlm.creation": FrontFirst(creator, creator), "vlm.director": reviewer,
                      "safety.image": Scripted([ALLOW, ALLOW])})
    sid = room.begin({"language": "en", "entrance": "colour"})
    ids = [room.add_drawing(sid, Path(DRAWING).read_bytes()) for _ in range(2)]
    rid = room.request(sid, "story-outline", ids, {})["request_id"]
    worker = Thread(target=room.run_request, args=(rid,))
    try:
        worker.start()
        assert next_started.wait(5)
        room.cancel(sid, rid)
        release.set()
        worker.join(5)
        assert not worker.is_alive()
        assert room.sessions[sid].accepted_scene_drafts == {}
        assert room.sessions[sid].scenes == {}
        assert not reviewer.prompts, "storybook drafts must not use the independent reviewer"
    finally:
        release.set()
        worker.join(5)
        room.close()


def test_wrong_order_and_empty_passages_are_rejected_before_work(setup):
    room, sid, ids, writer = setup
    valid = [{"drawing_id": did, "text": "故事"} for did in ids]
    assert pages(valid, ids) == valid
    for bad in (list(reversed(valid)), valid[:1], [dict(valid[0], text=""), valid[1]]):
        with pytest.raises(ValueError):
            room.request(sid, "drawings-to-storybook", ids, {"pages": bad})
    assert not writer.prompts


def test_invalid_model_outline_is_not_published(setup):
    room, sid, ids, writer = setup
    writer.replies = [ALLOW, ALLOW, '[]', '[]', '[]']
    event = execute(room, sid, "story-outline", ids, {"scenes": {did: "已有场景" for did in ids}})
    assert event["status"] == "stopped"
    assert "outputs" not in event
    assert not writer.replies, "three tries, then the teacher is told"


def test_cancelled_draft_cannot_change_saved_scene(setup):
    room, sid, ids, writer = setup
    writer.replies = [ALLOW, "新的描述"]
    rid = room.request(sid, "scene-description", ids[:1], {})["request_id"]
    room.cancel(sid, rid)
    room.run_request(rid)
    assert not writer.prompts
    assert not room.sessions[sid].scenes


def test_plans_are_not_dialogue_or_completed_books(tmp_path):
    portfolio = Portfolio(tmp_path / "courses.sqlite3")
    # Exercise the same storage interface used by real classes, on a disposable DB.
    writer = Writer()
    room = Classroom(tmp_path / "ledger", clients={"vlm.studio": writer, "vlm.director": writer}, portfolio=portfolio)
    sid = room.begin({"language": "zh", "entrance": "colour"})
    did = room.add_drawing(sid, Path("skills/art-feedback/evals/files/dog-sun.png").read_bytes())
    writer.replies = [ALLOW, "小兔轻轻跳。"]
    execute(room, sid, "scene-description", [did])
    course_id = room.sessions[sid].course_id
    activity = portfolio.course(course_id)["activities"][-1]
    assert activity["summary"]["kind"] == "draft"
    room.end(sid)
    restored = room.edit_course(course_id)
    assert room.sessions[restored["session_id"]].scenes[did] == "小兔轻轻跳。"
    room.end(restored["session_id"])


def test_a_story_tells_the_story_and_leaves_the_picture_out_of_it_but_the_teacher_s_words_alone(setup):
    # Stories read "画面右侧，…" and "背景中，…", copied from descriptions written for an animation.
    room, sid, ids, writer = setup
    written = [{"drawing_id": ids[0], "text": "画面右侧，一群老鼠推着大炮。右侧背景处的小山上，松树覆盖着白雪。"},
               {"drawing_id": ids[1], "text": "在画面左侧，三名士兵微笑着。画面左侧站着公主。画面中央是一棵圣诞树。画面远处飘着雪。"}]
    writer.replies = [ALLOW, ALLOW, json.dumps(written, ensure_ascii=False)]
    out = execute(room, sid, "story-outline", ids, {"scenes": {did: "已有场景" for did in ids}})["outputs"]
    assert [p["text"] for p in out["outline"]] == [
        "一群老鼠推着大炮。小山上，松树覆盖着白雪。",
        "三名士兵微笑着。一旁站着公主。画面中央是一棵圣诞树。远处飘着雪。",   # a side before a verb reads "to one side"; before "is" it stays
    ]
    book = execute(room, sid, "drawings-to-storybook", ids, {"pages": written})["outputs"]
    assert [p["text"] for p in book["pages"]] == [p["text"] for p in written], "a teacher's words are bound as written"


def test_a_page_the_cleanup_would_empty_keeps_its_words():
    from studio.conversation.creation import told
    assert told([{"drawing_id": "a", "text": "画面右侧，"}], "zh") == [{"drawing_id": "a", "text": "画面右侧，"}]
    assert told([{"drawing_id": "a", "text": "On the right of the picture, a mouse."}], "en")[0]["text"].startswith("On the right")
