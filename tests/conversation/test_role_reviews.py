"""Role-specific draft review rejects malformed and inconsistent results."""
import json
import pytest
from studio.conversation.conversation import Conversation
from studio.core.ledger import Ledger
from studio.providers.base import ChatResult

class Client:
    def __init__(self, answer):
        self.answer, self.calls = answer, []
    def chat(self, prompt, images=(), **kwargs):
        self.calls.append((prompt, images, kwargs))
        return ChatResult(self.answer, 1, 1, 0, 0, 0, "test", "step-3.7-flash")

@pytest.mark.parametrize("answer,ok", [
    ('{"ok":true,"issues":[]}', True),
    ('{"ok":false,"issues":[{"evidence":"missing scene","suggestion":"restore"}]}', False),
    ('{"ok":true,"issues":["contradiction"]}', False),
    ('{"ok":"true","issues":[]}', False),
    ('{"ok":true}', False),
    ('```json\n{"ok":true,"issues":[]}\n```', True),
    ('not JSON', False),
    ('[]', False),
])
def test_review_is_independent_and_fail_closed(tmp_path, answer, ok):
    writer, judge = Client("unused"), Client(answer)
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=writer, creation=writer, director=judge)
    conversation.opening = "Unrelated previous conversation"
    actual, _ = conversation._review_draft("scene", "child said dog", "dog in sun")
    assert actual is ok
    assert not writer.calls
    prompt, images, options = judge.calls[0]
    assert json.loads(prompt) == {"kind":"scene", "source":"child said dog", "candidate":"dog in sun"}
    assert "Unrelated" not in prompt and images == [conversation.image]
    assert options["max_tokens"] == 12000


def test_scene_review_treats_new_motion_as_the_requested_output_not_an_inconsistency(tmp_path):
    class PolicyAwareReviewer(Client):
        def chat(self, prompt, images=(), **kwargs):
            policy = kwargs.get("system", "")
            allowed = ("future image edit or animation" in policy
                       and "static original does not already show it" in policy
                       and "fixed visual anchors" in policy)
            self.calls.append((prompt, images, kwargs))
            return ChatResult(json.dumps({"ok": allowed, "issues": [] if allowed else [
                {"evidence": "the original is static", "suggestion": "remove the motion"}
            ]}), 1, 1, 0, 0, 0, "test", "step-3.7-flash")

    reviewer = PolicyAwareReviewer("unused")
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=Client("unused"), creation=Client("unused"), director=reviewer)
    ok, reason = conversation._review_draft(
        "scene", {"dialogue": []}, "The dog gently wags its tail beside the house.")
    assert ok is True
    assert reason == "independent request draft review passed"


def test_story_review_does_not_receive_scene_motion_exception(tmp_path):
    reviewer = Client('{"ok":true,"issues":[]}')
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=Client("unused"), creation=Client("unused"), director=reviewer)
    conversation._review_draft("story", {"scenes": []}, "[]", source_images=[])
    assert "future image edit or animation" not in reviewer.calls[0][2]["system"]


def test_a_story_review_lets_one_hero_travel_and_names_drawings_by_page(tmp_path):
    """Operator: a picture book may carry one character through its pages; the review had refused the
    corgi walking through the river and snow drawings, and named the drawings to the teacher by their ids."""
    reviewer = Client('{"ok":true,"issues":[]}')
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=Client("unused"), creation=Client("unused"), director=reviewer)
    conversation._review_draft("story", {"scenes": []}, "[]", source_images=[])
    system = reviewer.calls[0][2]["system"]
    assert "may travel through the story as its hero" in system and "never by its id" in system
    assert "Reject only a clear material conflict" in system and "steam or mist" in system
    conversation._review_draft("scene", {"dialogue": []}, "a dog", source_images=[])
    assert "as its hero" not in reviewer.calls[1][2]["system"], "a single scene is still held to its own drawing"


def test_transient_draft_review_failure_retries_the_same_reviewer_once(tmp_path):
    from studio.core.errors import ModelUnavailable

    class FlakyReviewer(Client):
        def chat(self, prompt, images=(), **kwargs):
            self.calls.append((prompt, images, kwargs))
            if len(self.calls) == 1:
                raise ModelUnavailable("incomplete response")
            return ChatResult('{"ok":true,"issues":[]}', 1, 1, 0, 0, 0, "test", "step-3.7-flash")

    reviewer = FlakyReviewer("unused")
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=Client("unused"), creation=Client("unused"), director=reviewer)
    assert conversation._review_draft("scene", {}, "The dog wags its tail.")[0] is True
    assert len(reviewer.calls) == 2


@pytest.mark.parametrize("review,expected", [('{"ok":true,"issues":[]}', True), ('{"ok":false,"issues":[]}', False)])
def test_draft_uses_creation_role_then_independent_reviewer(tmp_path, review, expected):
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    creator = Client("The dog plays in the sun.")
    director = Client(review)
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
        studio=Client("must not be used"), creation=creator, director=director,
        screener=Scripted([ALLOW]))
    beat = conversation.creation_draft("scene", {"dialogue": ["dog plays"]}, "draft")
    assert beat.ok is expected
    # A refusal is written again on the same press, three writings in all (operator: one press must end usable).
    assert len(creator.calls) == len(director.calls) == (1 if expected else 3)
    assert creator.calls[0][1] == director.calls[0][1] == [conversation.image]
    assert "candidate" in director.calls[0][0]


@pytest.mark.parametrize('review,retained', [
    ('{"ok":false,"issues":[{"evidence":"wrong object","suggestion":"restore shape"}]}',True),
    ('not JSON',False),
    ('{"ok":"false","issues":[]}',False),
])
def test_failed_review_retains_only_structurally_valid_candidate(tmp_path,review,retained):
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    conversation=Conversation(DRAWING,Ledger(tmp_path/'ledger'),entrance='colour',
        studio=Client('unused'),creation=Client('A red circle.'),director=Client(review),screener=Scripted([ALLOW]))
    beat=conversation.creation_draft('scene',{},'candidate')
    assert not beat.ok and not beat.text and beat.plan is None
    assert beat.draft == ('A red circle.' if retained else None)
    assert (beat.reason_code=='draft_review_failed') is retained


def test_invalid_story_never_becomes_editable_candidate(tmp_path):
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    judge=Client('{"ok":false,"issues":[]}')
    conversation=Conversation(DRAWING,Ledger(tmp_path/'ledger'),entrance='colour',
        studio=Client('unused'),creation=Client('[]'),director=judge,screener=Scripted([ALLOW]))
    beat=conversation.creation_draft('story',{},'bad',['drawing-a'])
    assert not beat.ok and beat.draft is None and not judge.calls


def test_fenced_story_json_is_accepted_without_changing_its_structure():
    from studio.conversation import creation
    text = '```json\n[{"drawing_id":"drawing-a","text":"A small story."}]\n```'
    assert creation.parse_outline(text, ["drawing-a"]) == [
        {"drawing_id": "drawing-a", "text": "A small story."}
    ]


def test_rejected_scene_is_emitted_as_stopped_candidate_then_can_be_rewritten(tmp_path):
    """Three refusals on one press stop it with the last candidate; the teacher's next press starts again."""
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    from pathlib import Path
    creator=Scripted(['A red disc.','A crimson disc.','A red circle.','A yellow circle.'])
    judge=Scripted(['{"ok":false,"issues":[{"evidence":"wrong colour","suggestion":"use yellow"}]}']*3+
                   ['{"ok":true,"issues":[]}'])
    room=Classroom(tmp_path/'ledger',clients={'vlm.studio':Client('unused'),'vlm.creation':creator,
        'vlm.director':judge,'safety.image':Scripted([ALLOW])})
    sid=room.begin({'language':'en','entrance':'colour'})
    did=room.add_drawing(sid,Path(DRAWING).read_bytes())
    try:
        rid=room.request(sid,'scene-description',[did],{})['request_id']
        room.run_request(rid)
        stopped=next(d for n,d in room.follow(rid) if n=='done')
        assert stopped['status']=='stopped' and stopped['reason_code']=='draft_review_failed'
        assert stopped['candidate']=={'skill':'scene-description','text':'A red circle.','drawing_id':did}
        assert stopped['issues']==[{'evidence':'wrong colour','suggestion':'use yellow'}], 'what the reviewer flagged reaches the teacher'
        assert 'outputs' not in stopped and did not in room.sessions[sid].scenes
        retry=room.request(sid,'scene-description',[did],{'previous':'Edited: a yellow circle.'})['request_id']
        room.run_request(retry)
        success=next(d for n,d in room.follow(retry) if n=='done')
        assert success['outputs']['text']=='A yellow circle.'
        assert 'Edited: a yellow circle.' in creator.prompts[-1]
        assert len(judge.prompts)==4, 'Edited draft still requires a fresh review.'
    finally: room.close()


def test_truncated_completion_is_never_retained(tmp_path):
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    from studio.core.errors import EmptyCompletion
    class Truncated(Client):
        def chat(self,*args,**kwargs): raise EmptyCompletion('truncated')
    conversation=Conversation(DRAWING,Ledger(tmp_path/'ledger'),entrance='colour',
        studio=Client('unused'),creation=Truncated(''),director=Client('unused'),screener=Scripted([ALLOW]))
    beat=conversation.creation_draft('scene',{},'truncated')
    assert not beat.ok and beat.draft is None and not beat.text


def test_storybook_returns_direct_outline_without_independent_review(tmp_path):
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import Scripted,ALLOW,DRAWING
    from pathlib import Path
    creator=Scripted([])
    reviewer = Scripted(['{"ok":false,"issues":[{"evidence":"invented","suggestion":"remove"}]}'])
    room=Classroom(tmp_path/'ledger',clients={'vlm.studio':Client('unused'),'vlm.creation':creator,
        'vlm.director':reviewer,
        'safety.image':Scripted([ALLOW,ALLOW])})
    sid=room.begin({'language':'en','entrance':'colour'})
    did=room.add_drawing(sid,Path(DRAWING).read_bytes())
    second=room.add_drawing(sid,Path(DRAWING).read_bytes())
    outline=[{'drawing_id':did,'text':'Candidate story.'},{'drawing_id':second,'text':'Second page.'}]
    creator.replies=[json.dumps(outline)]
    try:
        rid=room.request(sid,'story-outline',[did,second],{'scenes':{did:'Teacher confirmed scene.',second:'Second scene.'}})['request_id']
        room.run_request(rid)
        done=next(d for n,d in room.follow(rid) if n=='done')
        assert done['outputs']['outline']==outline
        assert not reviewer.prompts
    finally: room.close()


@pytest.mark.parametrize("error,calls", [
    ("refused", 1),
    ("unavailable", 2),
    ("empty", 2),
])
def test_only_a_failure_a_retry_could_fix_is_sent_again(tmp_path, error, calls):
    """A rejected request cannot succeed on a second attempt.

    The handler caught every ModelError alike, so an authentication, balance or
    content refusal was immediately resubmitted: twice the wait, and twice the
    provider usage, for an answer that could not change. Unreachable endpoints
    and empty completions are still worth one more try, and so is output that
    arrived but would not parse.
    """
    from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable
    raised = {"refused": ModelRefused, "unavailable": ModelUnavailable, "empty": EmptyCompletion}[error]

    class Failing(Client):
        def chat(self, prompt, images=(), **kwargs):
            self.calls.append((prompt, images, kwargs))
            raise raised("from the endpoint")

    judge = Failing("unused")
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png", Ledger(tmp_path / "ledger.jsonl"),
        entrance="colour", studio=Client("unused"), creation=Client("unused"), director=judge)
    ok, reason = conversation._review_draft("scene", "child said dog", "dog in sun")
    assert (ok, reason) == (False, "invalid draft review")
    assert len(judge.calls) == calls


def test_a_rejected_draft_carries_what_the_reviewer_flagged_and_the_ledger_keeps_only_the_verdict(tmp_path):
    # The teacher editing a rejected draft is the one person who can act on
    # "keep the herd at two", so the reviewer's evidence and suggestion ride on
    # the beat to the page. The ledger keeps the verdict and nothing more: the
    # reviewer is told to compare the candidate with the child's words and the
    # drawing, so its evidence describes both, and ledger.py's opening comment
    # forbids either in a line. An earlier pull request put the evidence in
    # the note instead; it was reviewed and not merged.
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    judge = Client('{"ok":false,"issues":[{"evidence":"candidate adds a third elephant","suggestion":"keep the herd at two"},'
                   '{"evidence":"candidate drops the roof rack","suggestion":"keep the roof rack"}]}')
    ledger = Ledger(tmp_path / "ledger.jsonl")
    conversation = Conversation(DRAWING, ledger, entrance="colour", studio=Client("unused"),
                                creation=Client("three elephants, a jeep"), director=judge, screener=Scripted([ALLOW]))
    beat = conversation.creation_draft("scene", {"dialogue": ["Child: two elephants, a jeep with a roof rack"]}, "req-1")
    assert not beat.ok and beat.reason_code == "draft_review_failed"
    assert beat.draft == "three elephants, a jeep"
    assert beat.issues == [
        {"evidence": "candidate adds a third elephant", "suggestion": "keep the herd at two"},
        {"evidence": "candidate drops the roof rack", "suggestion": "keep the roof rack"},
    ]
    notes = [entry.note for entry in ledger.entries() if entry.stage.startswith("scene-description")]
    assert notes == ["draft review found source inconsistencies"] * 3, "one verdict for each of the press's writings"


def test_a_clip_description_still_refused_after_its_tries_is_handed_over_as_advice(tmp_path):
    """Operator: pressing regenerate kept ending on a red "did not pass review, pass review before confirming" line,
    and the page now lets the teacher confirm the last description anyway. The sentence says so; a story keeps the old one."""
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    from studio.conversation.words import say
    refuse = '{"ok":false,"issues":[{"evidence":"the castle is pink","suggestion":"say pink"}]}'
    scene = Conversation(DRAWING, Ledger(tmp_path / "scene.jsonl"), entrance="colour", studio=Client("unused"),
                         creation=Client("a brown castle"), director=Client(refuse), screener=Scripted([ALLOW]),
                         language="zh")
    refused = scene.creation_draft("scene", {"dialogue": []}, "req-1")
    assert refused.refused == say("zh", "scene_review_advice") and "仅供参考" in refused.refused
    assert "通过复核后再确认" not in refused.refused

    story = Conversation(DRAWING, Ledger(tmp_path / "story.jsonl"), entrance="colour", studio=Client("unused"),
                         creation=Client('[{"drawing_id":"a","text":"The herd rested."}]'), director=Client(refuse),
                         screener=Scripted([ALLOW]), language="zh")
    assert story.creation_draft("story", {"scenes": []}, "req-2", ["a"]).refused == say("zh", "draft_review_failed")


class _SecondWritingFails:
    """Writes a description once, then answers nothing: the model gone quiet on the press's next try."""

    def __init__(self, first):
        self.first, self.prompts = first, []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.core.errors import ModelUnavailable
        self.prompts.append(prompt)
        if len(self.prompts) > 1:
            raise ModelUnavailable("the writer did not answer")
        return ChatResult(text=self.first, input_tokens=1, output_tokens=1, reasoning_tokens=0,
                          cost_usd=0.0, latency_s=0.0, provider="fake", model="fake")


@pytest.mark.parametrize("second", ["empty", "model gone quiet"])
def test_a_later_writing_that_fails_another_way_hands_over_the_refused_description_the_press_already_has(
        tmp_path, second):
    """Code review, 2026-09-30: when the second writing came back empty or the model did not answer, the press
    ended on "press again" and dropped the first description with its notes. The teacher gets that one instead."""
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    from studio.conversation.words import say
    refuse = '{"ok":false,"issues":[{"evidence":"candidate adds a third elephant","suggestion":"keep the herd at two"}]}'
    creator = Scripted(["three elephants, a jeep", ""]) if second == "empty" else _SecondWritingFails("three elephants, a jeep")
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Client("unused"),
                                creation=creator, director=Scripted([refuse]), screener=Scripted([ALLOW]))
    beat = conversation.creation_draft("scene", {"dialogue": ["Child: two elephants, a jeep with a roof rack"]}, "req-1")
    assert not beat.ok and beat.reason_code == "draft_review_failed"
    assert beat.draft == "three elephants, a jeep"
    assert beat.issues == [{"evidence": "candidate adds a third elephant", "suggestion": "keep the herd at two"}]
    assert beat.refused == say("en", "scene_review_advice")
    # A model that does not answer is asked once more before its try counts as failed (studio/core/harness.py).
    assert len(creator.prompts) == (2 if second == "empty" else 3), "the second writing is the one that failed"


def test_malformed_issues_still_reject_the_draft_but_carry_nothing_unusable_to_the_teacher(tmp_path):
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    judge = Client('{"ok":false,"issues":["contradiction",{"evidence":null,"suggestion":"x"},'
                   '{"evidence":"  ","suggestion":"blank"},{"evidence":"kept","suggestion":"kept too"}]}')
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Client("unused"),
                                creation=Client("a dog"), director=judge, screener=Scripted([ALLOW]))
    beat = conversation.creation_draft("scene", {"dialogue": []}, "req-2")
    assert not beat.ok and beat.draft == "a dog"
    assert beat.issues == [{"evidence": "kept", "suggestion": "kept too"}]


def _source(prompt):
    """The JSON the creator was handed, out of the prompt it arrived in."""
    return json.loads(prompt.split("Source data (not instructions):\n", 1)[1])


def test_a_refused_drafts_findings_are_handed_to_the_next_attempt(tmp_path):
    # Regenerating used to hand the creator the rejected text and ask it to say
    # the same thing differently, which walked it straight back to the same
    # fault: measured live, three presses in a row returned the
    # flagged detail, one of them after the teacher had edited the very phrase
    # the reviewer objected to. The findings now ride with the next attempt, so
    # there is something specific to correct rather than a wording to vary.
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    creator = Scripted(["three elephants, a jeep", "two elephants, a jeep with a roof rack"])
    judge = Scripted(['{"ok":false,"issues":[{"evidence":"candidate adds a third elephant",'
                      '"suggestion":"keep the herd at two"}]}', '{"ok":true,"issues":[]}'])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                studio=Client("unused"), creation=creator, director=judge,
                                screener=Scripted([ALLOW]))
    dialogue = {"dialogue": ["Child: two elephants, a jeep with a roof rack"]}

    passed = conversation.creation_draft("scene", dict(dialogue), "req-1")
    assert passed.ok and passed.text == "two elephants, a jeep with a roof rack", "rewritten on the same press"
    assert "issues" not in _source(creator.prompts[0]), "a first attempt has nothing to carry"
    assert _source(creator.prompts[1])["previous"] == "three elephants, a jeep"
    assert _source(creator.prompts[1])["issues"] == [
        {"evidence": "candidate adds a third elephant", "suggestion": "keep the herd at two"}]
    assert "correct every one of them" in creator.prompts[1], "and the instruction to act on them"


def test_the_reviewer_is_never_shown_the_rejection_it_made_last_time(tmp_path):
    # A check handed its own previous verdict as source data is no longer an
    # independent one: a finding that was wrong on the first pass would arrive
    # as established fact on the second, and the draft could never recover from
    # it. The creator is told; the reviewer looks again at the drawing.
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    creator = Scripted(["three elephants", "two elephants"])
    judge = Scripted(['{"ok":false,"issues":[{"evidence":"candidate adds a third elephant",'
                      '"suggestion":"keep the herd at two"}]}', '{"ok":true,"issues":[]}'])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                studio=Client("unused"), creation=creator, director=judge,
                                screener=Scripted([ALLOW]))
    assert conversation.creation_draft("scene", {"dialogue": []}, "req-1").ok

    second_review = json.loads(judge.prompts[1])
    assert "issues" not in second_review["source"]
    assert "third elephant" not in judge.prompts[1]


def test_findings_are_dropped_the_moment_a_draft_passes(tmp_path):
    # Otherwise a later rewrite is told to fix a fault in text it did not write.
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    creator = Scripted(["three elephants", "two elephants", "two elephants, resting"])
    judge = Scripted(['{"ok":false,"issues":[{"evidence":"candidate adds a third elephant",'
                      '"suggestion":"keep the herd at two"}]}',
                      '{"ok":true,"issues":[]}', '{"ok":true,"issues":[]}'])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                studio=Client("unused"), creation=creator, director=judge,
                                screener=Scripted([ALLOW]))
    assert conversation.creation_draft("scene", {"dialogue": []}, "req-1").ok
    assert conversation.carried_findings == {}

    conversation.creation_draft("scene", {"dialogue": []}, "req-2")
    assert "issues" not in _source(creator.prompts[2])


def test_a_scenes_findings_never_reach_a_story_outline(tmp_path):
    # classroom.py writes both kinds through the first drawing's conversation,
    # so one object holds both. A fault in a scene description is not a fault in
    # the outline that follows it.
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    creator = Scripted(["three elephants"] * 3 + ['[{"drawing_id":"a","text":"The herd rested."}]'])
    judge = Scripted(['{"ok":false,"issues":[{"evidence":"candidate adds a third elephant",'
                      '"suggestion":"keep the herd at two"}]}'] * 3 + ['{"ok":true,"issues":[]}'])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                studio=Client("unused"), creation=creator, director=judge,
                                screener=Scripted([ALLOW]))
    conversation.creation_draft("scene", {"dialogue": []}, "req-1")
    outline = conversation.creation_draft("story", {"scenes": []}, "req-2", ["a"])

    assert outline.ok
    assert "issues" not in _source(creator.prompts[3])
    assert conversation.carried_findings["scene"], "the scene's own findings are still waiting for it"


@pytest.mark.parametrize("language", ["zh", "en"])
def test_the_reviewer_is_asked_for_its_findings_in_the_teachers_language(tmp_path, language):
    # The evidence and the remedy go on the screen where a teacher is editing the
    # draft that was refused, so they have to be words that teacher reads. Measured
    # live: asked in English about a Chinese description, the reviewer
    # answered in English, and a Chinese classroom would have been shown "The roof
    # color should be corrected to dark brown" against a draft with no such words.
    judge = Client('{"ok":true,"issues":[]}')
    conversation = Conversation("skills/art-feedback/evals/files/dog-sun.png",
                                Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                language=language, studio=Client("unused"),
                                creation=Client("unused"), director=judge)
    conversation._review_draft("scene", {"dialogue": []}, "a dog in the sun")

    system = judge.calls[0][2]["system"]
    assert f"Write every evidence and suggestion in this language: {language}." in system


def test_after_qwens_draft_is_refused_the_next_press_is_written_by_step(tmp_path):
    """Operator: two Qwen scene descriptions for a storybook were refused for describing what was
    not in the drawing, and pressing again only asked Qwen again. The next writing, on the same press now,
    goes to Step directly."""
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    qwen = Scripted(["three elephants, a jeep"])
    step = Scripted(["two elephants, a jeep with a roof rack"])
    judge = Scripted(['{"ok":false,"issues":[{"evidence":"candidate adds a third elephant",'
                      '"suggestion":"keep the herd at two"}]}', '{"ok":true,"issues":[]}'])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour",
                                studio=Client("unused"), creation=FrontFirst(qwen, step), director=judge,
                                screener=Scripted([ALLOW]))
    dialogue = {"dialogue": ["Child: two elephants, a jeep with a roof rack"]}
    assert conversation.creation_draft("scene", dict(dialogue), "req-1").ok
    assert len(qwen.prompts) == 1 and len(step.prompts) == 1, "Qwen wrote the first, Step the second"


def test_a_scene_the_book_fills_in_uses_qwen_without_step_review(tmp_path):
    import json
    from pathlib import Path
    from studio.classroom.classroom import Classroom
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    qwen, step = Scripted(["A dragon flies over the house."]), Scripted([])
    review = Scripted([])
    room = Classroom(tmp_path / "ledger", clients={"vlm.studio": Client("unused"), "vlm.creation": FrontFirst(qwen, step),
                     "vlm.director": review, "safety.image": Scripted([ALLOW, ALLOW])})
    sid = room.begin({"language": "en", "entrance": "colour"})
    did = room.add_drawing(sid, Path(DRAWING).read_bytes())
    second = room.add_drawing(sid, Path(DRAWING).read_bytes())
    outline = [{"drawing_id": did, "text": "Page one."}, {"drawing_id": second, "text": "Page two."}]
    qwen.replies.append(json.dumps(outline))
    try:
        rid = room.request(sid, "story-outline", [did, second], {"scenes": {second: "Teacher confirmed scene."}})["request_id"]
        room.run_request(rid)
        done = next(d for n, d in room.follow(rid) if n == "done")
        assert done.get("status") != "stopped", done.get("message")
        assert done["outputs"]["scenes"][0]["text"] == "A dragon flies over the house."
        assert len(qwen.prompts) == 2 and not step.prompts and not review.prompts
    finally:
        room.close()


def test_a_malformed_story_stops_without_step_retry(tmp_path):
    import json
    from pathlib import Path
    from studio.classroom.classroom import Classroom
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    room = None
    # Qwen is asked again (a few seconds each); Step, which a teacher waits 40 to 80 s for, never is.
    qwen, step = Scripted(["this is not a story list"] * 3), Scripted([])
    review = Scripted([])
    room = Classroom(tmp_path / "ledger", clients={"vlm.studio": Client("unused"), "vlm.creation": FrontFirst(qwen, step),
                     "vlm.director": review, "safety.image": Scripted([ALLOW, ALLOW])})
    sid = room.begin({"language": "en", "entrance": "colour"})
    did = room.add_drawing(sid, Path(DRAWING).read_bytes())
    second = room.add_drawing(sid, Path(DRAWING).read_bytes())
    outline = [{"drawing_id": did, "text": "Page one."}, {"drawing_id": second, "text": "Page two."}]
    step.replies.append(json.dumps(outline))
    try:
        rid = room.request(sid, "story-outline", [did, second], {"scenes": {did: "A house.", second: "A river."}})["request_id"]
        room.run_request(rid)
        done = next(d for n, d in room.follow(rid) if n == "done")
        assert done.get("status") == "stopped" and "outputs" not in done
        assert len(qwen.prompts) == 3 and not step.prompts and not review.prompts
    finally:
        room.close()


def test_a_stopped_book_writes_no_second_story_and_no_next_page(tmp_path):
    """Operator: a book stopped while Qwen's story was refused went on to have Step write it again, and
    every press for the next half minute was refused as busy."""
    import json
    from pathlib import Path
    from studio.classroom.classroom import Classroom
    from studio.providers.frontvoice import FrontFirst
    from tests.classroom.test_classroom import Scripted, ALLOW, DRAWING
    qwen, step = Scripted(["not a story"]), Scripted([])
    room = Classroom(tmp_path / "ledger", clients={"vlm.studio": Client("unused"), "vlm.creation": FrontFirst(qwen, step),
                     "vlm.director": Scripted([]), "safety.image": Scripted([ALLOW, ALLOW])})
    sid = room.begin({"language": "en", "entrance": "colour"})
    did = room.add_drawing(sid, Path(DRAWING).read_bytes())
    second = room.add_drawing(sid, Path(DRAWING).read_bytes())
    try:
        rid = room.request(sid, "story-outline", [did, second], {"scenes": {did: "A house.", second: "A river."}})["request_id"]
        original = qwen.chat
        def written_then_stopped(*a, **k):
            answer = original(*a, **k)
            room.requests[rid].cancelled.set()   # the teacher presses Stop while Qwen's story is checked
            return answer
        qwen.chat = written_then_stopped
        room.run_request(rid)
        assert step.prompts == [], "no second story after Stop"
    finally:
        room.close()
