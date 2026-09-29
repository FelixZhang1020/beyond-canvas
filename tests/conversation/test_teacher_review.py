"""Teacher reports use their own model and preserve the child conversation."""
from pathlib import Path
import pytest
from studio.classroom.classroom import Classroom
from studio.classroom.portfolio import Portfolio
from studio.providers.base import ChatResult
from studio.conversation.teacher_review import check, prompt

ALLOW = '{"verdict":"allow","reason":"drawing","text_found":[]}'
TEXT = ('画面以明亮的黄色太阳和蓝色背景形成清晰的色彩对照，主体轮廓在背景中显得突出。'
        '画中的线条沿着主体展开，重复的形状让视线自然集中到画面中央。'*4)

class Writer:
    def __init__(self, replies): self.replies, self.calls = list(replies), []
    def chat(self, prompt, images=(), **kwargs):
        self.calls.append((prompt, images))
        return ChatResult(self.replies.pop(0), 2, 3, 0, 0, 0, 'test', 'test')

def execute(room, sid, did):
    rid = room.request(sid, 'teacher-review', [did], {})['request_id']
    room.run_request(rid)
    return next(data for name, data in room.follow(rid) if name == 'done')

@pytest.fixture(params=["colour", "sketch"])
def setup(tmp_path, request):
    screen, teacher = Writer([ALLOW]), Writer([TEXT])
    room = Classroom(tmp_path/'ledger.jsonl', clients={'vlm.studio':screen,'vlm.director':screen,'vlm.teacher':teacher}, portfolio=Portfolio(tmp_path/'portfolio.sqlite3'))
    sid = room.begin({'language':'zh','entrance':request.param})
    did = room.add_drawing(sid, Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes())
    yield room, sid, did, screen, teacher
    room.end(sid)

def test_report_is_one_image_pass_saved_without_changing_dialogue(setup):
    """One writing pass now: the critique and rewrite cost 54 s a report."""
    room,sid,did,screen,teacher = setup
    out=execute(room,sid,did)['outputs']
    assert out['text'] == TEXT and 'question' not in out
    assert len(teacher.calls)==1 and teacher.calls[0][1]
    assert '"entrance": "' + room.sessions[sid].entrance + '"' in teacher.calls[0][0]
    assert len(screen.calls)==1
    c=room.sessions[sid].conversations[did]
    assert not c.opening and not room.sessions[sid].dialogue
    course=room.portfolio.course(room.sessions[sid].course_id)
    assert course['activities'][-1]['skill']=='teacher-review'
    assert course['activities'][-1]['summary']['text']==TEXT
    assert sum(x['tokens'] for x in room.ledger_lines(sid)) >= 2

def test_the_report_names_the_model_that_wrote_it(setup):
    """Code review: every report was labelled Step 3.7 Flash, and the Portfolio kept that, though under StepFun
    First Qwen3.6 on the Spark writes them."""
    room, sid, did, screen, teacher = setup
    teacher.model = "qwen3.6-35b-a3b"
    assert execute(room, sid, did)["outputs"]["model"] == "qwen3.6-35b-a3b"

def test_safety_refusal_never_reaches_teacher(setup):
    room,sid,did,screen,teacher=setup
    screen.replies=['{"verdict":"blank_page","reason":"blank","text_found":[]}']
    out=execute(room,sid,did)
    assert out['status']=='stopped' and not teacher.calls

def test_question_is_rejected_not_published(setup):
    room,sid,did,screen,teacher=setup
    teacher.replies=[TEXT+'你想说什么？']*2
    out=execute(room,sid,did)
    assert out['status']=='stopped' and 'outputs' not in out

SENTENCE_EN = 'The painting uses contrasting colours to separate its main subject from the background. '


def test_format_controls():
    assert check(TEXT,'zh')[0]
    assert not check('很好看。','zh')[0]
    assert not check(TEXT+'为什么？','zh')[0]
    assert not check('This is a detailed review. '*30,'zh')[0]
    assert check(SENTENCE_EN*13,'en')[0]
    assert '不提问' in prompt('zh','colour','色彩课')


def test_a_report_is_measured_in_the_unit_its_language_is_written_in():
    """English used to be counted in Latin letters, and 100 of them passed.

    That is about twenty words, so a two-sentence reply was saved as a complete
    teacher report. The ceiling sits above the prompt's documented 300-500
    characters because the two reports accepted against a real drawing
    ran 535 and 578.
    """
    assert not check(SENTENCE_EN*4,'en')[0]      # 52 words: a reply, not a report
    assert check(SENTENCE_EN*13,'en')[0]         # 169 words
    assert not check(SENTENCE_EN*30,'en')[0]     # 390 words: a wall of text
    assert not check('画'*200,'zh')[0]
    assert check('画'*535,'zh')[0] and check('画'*578,'zh')[0]
    assert not check('画'*700,'zh')[0]


def test_cancel_before_the_first_pass_spends_nothing():
    from studio.conversation.teacher_review import write
    from studio.core.errors import ModelCancelled
    client=Writer([TEXT])
    with pytest.raises(ModelCancelled):
        write(client,'data:image/png;base64,x','zh','colour','',lambda:True)
    assert len(client.calls)==0

def test_a_stop_during_the_draft_is_not_asked_again():
    # Code review: cancellation raised the base model error, which the
    # harness retries once, and write() paid for its draft before ever checking the
    # flag. A stopped report therefore bought a second full draft. The stop is a
    # refusal now, checked before the first call too.
    from studio.conversation.teacher_review import write
    from studio.core.errors import ModelCancelled
    from studio.core.harness import Harness, Stage
    client=Writer([TEXT, TEXT])
    def run(_):
        return write(client,'data:image/png;base64,x','zh','colour','',lambda: len(client.calls)>=1)
    stage=Stage('teacher-review','teacher-review',run,gate=lambda _:(True,''),retries=1,retry_model_errors=True)
    class Ledger:
        session='t'
        def completed_stages(self,_): return set()
        def append(self,*a,**k): pass
        def entries(self,_): return []
    outcome=Harness(Ledger()).run([stage],{})[0]
    assert not outcome.ok and outcome.errored and 'cancelled' in outcome.reason
    assert len(client.calls)==1, 'the draft that was in flight is paid for once; nothing after a stop is'


SHORT = '画面有太阳。'  # far under the bounded-report floor


class FlakyWriter(Writer):
    """A writer whose reply list may contain an exception, raised in its turn."""
    def chat(self, prompt, images=(), **kwargs):
        reply = self.replies[0]
        if isinstance(reply, Exception):
            self.replies.pop(0); self.calls.append((prompt, images)); raise reply
        return super().chat(prompt, images, **kwargs)


def test_a_report_outside_its_bounds_is_written_again_before_the_teacher_is_told(setup):
    """Live, colour course, drawing 2: the first report came out outside
    300-500 characters and the activity stopped with the hiccup line. That is a
    length that varies from run to run, not a decision about the child, so it gets
    the one retry every other beat already has.
    """
    room, sid, did, screen, teacher = setup
    teacher.replies = [SHORT, TEXT]
    out = execute(room, sid, did)
    assert out.get('outputs', {}).get('text') == TEXT
    assert len(teacher.calls) == 2, "one report, then one more"
    assert [x['gate'] for x in room.ledger_lines(sid) if x['stage'] == 'teacher-review'] == ['fail', 'pass']


def test_an_empty_completion_is_tried_again_rather_than_shown_as_a_hiccup(setup):
    """Same drawing, second press: Step 3.7 Flash spent all 16,000 tokens on hidden
    reasoning and returned no text. An empty completion is the textbook flaky call;
    the harness can retry it only if the stage says model errors may be retried.
    """
    from studio.core.errors import EmptyCompletion
    room, sid, did, screen, teacher = setup
    teacher.__class__ = FlakyWriter
    teacher.replies = [EmptyCompletion('step-3.7-flash returned no text after spending 16000 completion tokens'),
                       TEXT]
    out = execute(room, sid, did)
    assert out.get('outputs', {}).get('text') == TEXT
    # The harness asks once more without writing a line for the empty answer —
    # that is _call's own documented choice — so the proof is in the calls.
    assert len(teacher.calls) == 2, "the empty answer, then one report"
    assert [x['gate'] for x in room.ledger_lines(sid) if x['stage'] == 'teacher-review'] == ['pass']


def test_what_the_teacher_typed_about_the_subject_reaches_the_writer(tmp_path):
    """The lesson line is the only thing that tells the report what it is looking at.

    A child's barbershop, drawn in ink and read without it, came back
    as a kitchen, a hospital ward, and an arrangement of doors and
    deity figures; with one line naming the subject it came back as a barbershop
    three times out of three. The field for that line already existed and already
    reached here, so the wording was changed to ask for the subject rather than
    only the technique — which is worth nothing if the line stops arriving.
    """
    screen, teacher = Writer([ALLOW]), Writer([TEXT])
    room = Classroom(tmp_path/'ledger.jsonl',
                     clients={'vlm.studio':screen,'vlm.director':screen,'vlm.teacher':teacher},
                     portfolio=Portfolio(tmp_path/'portfolio.sqlite3'))
    sid = room.begin({'language':'zh','entrance':'colour','lesson_intent':'今天画理发店，用超轻粘土'})
    did = room.add_drawing(sid, Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes())
    try:
        execute(room, sid, did)
        assert '今天画理发店，用超轻粘土' in teacher.calls[0][0]
    finally:
        room.end(sid)


def test_a_class_that_says_nothing_about_its_subject_still_writes_a_report(tmp_path):
    """The field is optional and stays optional: an empty line is not an error."""
    screen, teacher = Writer([ALLOW]), Writer([TEXT])
    room = Classroom(tmp_path/'ledger.jsonl',
                     clients={'vlm.studio':screen,'vlm.director':screen,'vlm.teacher':teacher},
                     portfolio=Portfolio(tmp_path/'portfolio.sqlite3'))
    sid = room.begin({'language':'zh','entrance':'colour'})
    did = room.add_drawing(sid, Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes())
    try:
        assert execute(room, sid, did)['outputs']['text'] == TEXT
        assert '"lesson_context": ""' in teacher.calls[0][0]
    finally:
        room.end(sid)
