"""The safety look runs once, when a photo arrives, and no step pays for it again.

Operator: it cost the first thing a teacher pressed 4-7 s on the
Spark. A request for the drawing waits for a look still in flight instead of
starting a second one.
"""
import threading
from pathlib import Path

from studio.classroom.classroom import Classroom
from studio.classroom.portfolio import Portfolio
from studio.providers.base import ChatResult

ALLOW = '{"verdict":"allow","reason":"drawing","text_found":[]}'
BLANK = '{"verdict":"blank_page","reason":"blank","text_found":[]}'
TEXT = ('画面以明亮的黄色太阳和蓝色背景形成清晰的色彩对照，主体轮廓在背景中显得突出。'
        '画中的线条沿着主体展开，重复的形状让视线自然集中到画面中央。' * 4)
DRAWING = Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes()


class Screen:
    def __init__(self, reply, gate=None): self.reply, self.gate, self.calls = reply, gate, 0
    def chat(self, prompt, images=(), **kwargs):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(5)
        return ChatResult(self.reply, 2, 3, 0, 0, 0, 'test', 'test')


class Teacher:
    def __init__(self): self.calls = 0
    def chat(self, prompt, images=(), **kwargs):
        self.calls += 1
        return ChatResult(TEXT, 2, 3, 0, 0, 0, 'test', 'test')


def room(tmp_path, screen, teacher):
    classroom = Classroom(tmp_path / 'ledger.jsonl', clients={'vlm.studio': screen, 'vlm.director': screen,
                          'vlm.teacher': teacher}, portfolio=Portfolio(tmp_path / 'p.sqlite3'))
    classroom.look_on_arrival = True
    return classroom


def review(classroom, sid, did):
    rid = classroom.request(sid, 'teacher-review', [did], {})['request_id']
    classroom.run_request(rid)
    return next(data for name, data in classroom.follow(rid) if name == 'done')


def test_the_look_happens_on_upload_and_is_not_paid_for_again(tmp_path):
    screen, teacher = Screen(ALLOW), Teacher()
    classroom = room(tmp_path, screen, teacher)
    sid = classroom.begin({'language': 'zh', 'entrance': 'colour'})
    did = classroom.add_drawing(sid, DRAWING)
    classroom.sessions[sid].conversations[did].arrival.join(5)
    assert screen.calls == 1, 'looked at before anyone pressed anything'
    assert review(classroom, sid, did)['outputs']['text'] == TEXT
    assert review(classroom, sid, did)['outputs']['text'] == TEXT
    assert screen.calls == 1, 'no step looks a second time'
    assert [line['stage'] for line in classroom.ledger_lines(sid)].count('studio-safety') == 1
    classroom.end(sid)
    assert list(classroom.ledger.entries()) == [], 'the look is forgotten with the class'


def test_a_request_made_during_the_look_waits_for_it_rather_than_looking_again(tmp_path):
    released = threading.Event()
    screen, teacher = Screen(ALLOW, gate=released), Teacher()
    classroom = room(tmp_path, screen, teacher)
    sid = classroom.begin({'language': 'zh', 'entrance': 'colour'})
    did = classroom.add_drawing(sid, DRAWING)
    threading.Timer(0.2, released.set).start()
    assert review(classroom, sid, did)['outputs']['text'] == TEXT
    assert screen.calls == 1
    classroom.end(sid)


def test_a_refusal_found_on_upload_still_stops_the_first_step(tmp_path):
    screen, teacher = Screen(BLANK), Teacher()
    classroom = room(tmp_path, screen, teacher)
    sid = classroom.begin({'language': 'zh', 'entrance': 'colour'})
    did = classroom.add_drawing(sid, DRAWING)
    done = review(classroom, sid, did)
    assert done['status'] == 'stopped'
    assert teacher.calls == 0, 'a refused drawing never reaches a writer'
    classroom.end(sid)


def test_a_look_still_out_when_the_class_ends_leaves_no_record_behind(tmp_path):
    """Found in review: end() forgot the class's lines while the look was still
    waiting on the model, and the look then wrote a line nothing would remove."""
    released = threading.Event()
    screen, teacher = Screen(ALLOW, gate=released), Teacher()
    classroom = room(tmp_path, screen, teacher)
    sid = classroom.begin({'language': 'zh', 'entrance': 'colour'})
    did = classroom.add_drawing(sid, DRAWING)
    arrival = classroom.sessions[sid].conversations[did].arrival
    classroom.end(sid)
    released.set()
    arrival.join(5)
    assert list(classroom.ledger.entries()) == []
