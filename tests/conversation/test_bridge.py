"""The quick line a child hears while the studio looks again (studio/conversation/bridge.py).

It is spoken before any model judge reads it, so it may only say the child's own
words back; anything the instant checks cannot vouch for becomes the fixed line.
"""
from pathlib import Path

from studio.conversation import bridge
from studio.classroom.classroom import Classroom
from studio.core.errors import ModelUnavailable
from studio.classroom.portfolio import Portfolio
from studio.providers.base import ChatResult
from studio.conversation.words import say

SAID = '它要去找朋友玩'


class Fast:
    def __init__(self, reply): self.reply, self.prompts = reply, []
    def chat(self, prompt, images=(), **kwargs):
        self.prompts.append((prompt, images))
        if isinstance(self.reply, Exception):
            raise self.reply
        return ChatResult(self.reply, 2, 3, 0, 0, 0, 'test', 'test')


def test_the_model_writes_the_echo_and_the_studio_adds_that_it_is_looking():
    text, written = bridge.line(Fast('你说它要去找朋友玩呀。'), SAID, 'zh')
    assert written and text == '你说它要去找朋友玩呀。' + say('zh', 'bridge_tail')


def test_the_fast_model_never_sees_the_drawing():
    fast = Fast('你说它要去找朋友玩呀。')
    bridge.line(fast, SAID, 'zh')
    assert fast.prompts[0][1] == () and SAID in fast.prompts[0][0]


def test_stage_directions_are_taken_out_before_the_line_is_checked():
    text, written = bridge.line(Fast('（温柔亲切）你说它要去找朋友玩呀！(smiling)'), SAID, 'zh')
    assert written and text == '你说它要去找朋友玩呀！' + say('zh', 'bridge_tail')


def test_quotation_marks_around_the_echo_are_not_spoken():
    text, written = bridge.line(Fast('\u201c你说它要去找朋友玩呀。\u201d'), SAID, 'zh')
    assert written and text.startswith('你说它要去找朋友玩呀。')


def test_anything_the_instant_checks_cannot_vouch_for_becomes_the_fixed_line():
    fixed = say('zh', 'bridge')
    for reply in ('树叶变成了橙色，真漂亮。',                      # describes a drawing it never saw
                  '你说它要去找朋友玩，它的朋友在哪里呢？',          # asks a question
                  '你说它要去找朋友玩，' + '我们一起慢慢看' * 10,     # too long
                  '你说它要去找朋友玩，你真是个天才！',              # praises the child, not the work
                  ModelUnavailable('down')):
        assert bridge.line(Fast(reply), SAID, 'zh') == (fixed, False), reply
    assert bridge.line(None, SAID, 'zh') == (fixed, False)


DRAWING = Path('skills/art-feedback/evals/files/dog-sun.png').read_bytes()
ALLOW = '{"verdict":"allow","reason":"drawing","text_found":[]}'


class Studio:
    """Writes the opening, then the reply; judges say every rule passed."""
    def __init__(self, order): self.order = order
    def chat(self, prompt, images=(), **kwargs):
        if 'verdict' in prompt or 'submitted by a teacher' in prompt:
            return ChatResult(ALLOW, 1, 1, 0, 0, 0, 't', 't')
        if kwargs.get('system'):
            return ChatResult('{"grounded": true, "details": ["a", "b"], "presumes": false, "invented": [], '
                              '"connected": true, "why": "x"}', 1, 1, 0, 0, 0, 't', 't')
        self.order.append('write')
        return ChatResult('你说它要去找朋友玩，太阳黄黄的。它的朋友住在哪里？', 1, 1, 0, 0, 0, 't', 't')


def test_the_bridge_reaches_the_page_before_the_reply_is_written(tmp_path):
    order = []
    fast = Fast('你说它要去找朋友玩呀。')
    original = fast.chat
    fast.chat = lambda *a, **k: (order.append('bridge'), original(*a, **k))[1]
    studio = Studio(order)
    room = Classroom(tmp_path / 'l.jsonl', clients={'vlm.studio': studio, 'vlm.director': studio,
                     'chat.bridge': fast}, portfolio=Portfolio(tmp_path / 'p.sqlite3'))
    room.ceiling_gb = float('inf')  # fake models do not use the Spark's shared model memory
    sid = room.begin({'language': 'zh', 'entrance': 'colour'})
    did = room.add_drawing(sid, DRAWING)
    room.sessions[sid].conversations.setdefault(did, room._conversation(room.sessions[sid], did)).opening = '我看见一只狗。'
    rid = room.request(sid, 'art-feedback', [did], {'transcript': SAID})['request_id']
    room.run_request(rid)
    events = [data for name, data in room.follow(rid)]
    bridges = [e['partial']['bridge'] for e in events if 'bridge' in (e.get('partial') or {})]
    assert bridges == ['你说它要去找朋友玩呀。' + say('zh', 'bridge_tail')]
    assert order.index('bridge') < order.index('write'), 'the child hears the bridge while the reply is written'
    room.end(sid)
