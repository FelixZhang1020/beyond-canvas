"""Integration boundaries, with scripted models and real loopback HTTP transport."""
import base64
import json
import urllib.error

import pytest

from studio.voice.speech import SpeechSession
from studio.providers.stepfun_voice import VoiceServiceError
from test_classroom import room, png, CLASS, ALLOW, outputs_of
from tests.server.test_serve import studio, call, open_class


class Voice:
    local = True
    sample_rate = 48000
    voice = 'gentle-female'
    voices = {'gentle-female': 'Female', 'gentle-male': 'Male'}
    def __init__(self):
        self.calls = []
        self.closed = 0
    @classmethod
    def validate_voice(cls, value):
        if value not in cls.voices:
            raise ValueError('bad voice')
        return value
    def stream(self, text, voice_id, cancelled):
        self.calls.append((text, voice_id))
        try:
            yield b'\x01\x00' * 100
            if not cancelled():
                yield b'\x02\x00' * 100
        finally:
            self.closed += 1


def test_speech_replays_cache_but_isolates_voices_and_clears_at_end():
    speech, voice = SpeechSession(), Voice()
    first = list(speech.stream(voice, 'Hello', None))
    assert first[-1]['type'] == 'done'
    assert base64.b64decode(first[1]['data']) == b'\x01\x00' * 100
    assert list(speech.stream(voice, 'Hello', None))[0]['cached']
    list(speech.stream(voice, 'Hello', 'gentle-male'))
    assert len(voice.calls) == 2
    speech.stop(close=True)
    assert not speech.cache
    with pytest.raises(KeyError):
        speech.stream(voice, 'Hello', None)


def test_cancelled_and_replaced_speech_never_cache_partial_audio():
    speech, voice = SpeechSession(), Voice()
    events = speech.stream(voice, 'First', None)
    next(events); next(events)
    replacement = speech.stream(voice, 'Second', None)
    assert list(events) == []
    assert not speech.cache
    assert list(replacement)[-1]['type'] == 'done'
    assert [key[-2:] for key in speech.cache] == [('Second', voice.voice)]
    events = speech.stream(voice, 'Disconnect', None)
    next(events); next(events); events.close()
    assert all(key[-2:] != ('Disconnect', voice.voice) for key in speech.cache)
    assert voice.closed == 3


def test_speech_rejects_unavailable_invalid_voice_and_overlong_text():
    speech = SpeechSession()
    with pytest.raises(VoiceServiceError):
        speech.stream(None, 'Hi', None)
    for text, voice in [('', None), ('你' * 401, None), ('Hi', 'unknown')]:
        with pytest.raises(ValueError):
            speech.stream(Voice(), text, voice)
    assert list(speech.stream(Voice(), '你' * 400, None))[-1]['type'] == 'done'


def book(room, sid, ids):
    request = room.request(sid, 'drawings-to-storybook', ids, {})
    room.run_request(request['request_id'])
    return list(room.follow(request['request_id']))


def test_book_screens_each_drawing_keeps_confirmed_words_and_allows_silent_pages(room, png):
    classroom = room([ALLOW, ALLOW])
    try:
        sid = classroom.begin(CLASS)
        ids = [classroom.add_drawing(sid, png) for _ in range(2)]
        classroom.sessions[sid].transcripts[ids[0]] = 'The bird said <hello> 🌻.'
        output = outputs_of(book(classroom, sid, ids))
        assert output['pages'] == [{'drawing_id': ids[0], 'text': 'The bird said <hello> 🌻.'},
                                   {'drawing_id': ids[1], 'text': ''}]
        assert len(classroom.client.prompts) == 2
        assert outputs_of(book(classroom, sid, ids)) == output
        assert len(classroom.client.prompts) == 2
    finally:
        classroom.close()


def test_book_cannot_reuse_first_drawings_safety_for_a_blocked_second_page(room, png):
    blank = '{"verdict":"empty","reason":"blank","text_found":[]}'
    classroom = room([ALLOW, blank, blank])
    try:
        sid = classroom.begin(CLASS)
        ids = [classroom.add_drawing(sid, png) for _ in range(2)]
        classroom.sessions[sid].transcripts = dict.fromkeys(ids, 'The bird is happy.')
        events = book(classroom, sid, ids)
        assert any(data.get('reason_code') == 'blank_page' for _, data in events)
        assert not any(data.get('outputs', {}).get('pages') for _, data in events)
        assert len(classroom.client.prompts) == 3
    finally:
        classroom.close()


def test_settings_reach_existing_conversations_and_refuse_during_work(room, png):
    classroom = room([])
    try:
        sid = classroom.begin(CLASS)
        drawing = classroom.add_drawing(sid, png)
        conversation = classroom._conversation(classroom.sessions[sid], drawing)
        classroom.update_settings(sid, {'language': 'zh', 'lesson_intent': 'Light'})
        assert conversation.language == conversation.settings.language == 'zh'
        assert conversation.lesson_intent == 'Light'
        with classroom.sessions[sid].talk_lock:
            with pytest.raises(ValueError):
                classroom.update_settings(sid, {'language': 'en'})
        assert conversation.language == 'zh'
    finally:
        classroom.close()


def test_http_settings_speech_validation_and_ended_session(studio):
    sid = open_class(studio)
    assert call(studio, 'PATCH', f'/api/session/{sid}', {'language': 'zh'})[0] == 204
    with pytest.raises(urllib.error.HTTPError) as error:
        call(studio, 'POST', f'/api/session/{sid}/speech', {'text': 'Hello'})
    assert error.value.code == 503
    call(studio, 'DELETE', f'/api/session/{sid}')
    with pytest.raises(urllib.error.HTTPError) as error:
        call(studio, 'POST', f'/api/session/{sid}/speech', {'text': 'Hello'})
    assert error.value.code == 404


def test_cancelling_a_request_stops_later_stages_without_publishing_a_result(room, png):
    import threading
    from studio.providers.base import ChatResult
    from test_classroom import Scripted
    entered, release = threading.Event(), threading.Event()
    class Slow(Scripted):
        def chat(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().chat(*args, **kwargs)
    classroom = room([])
    slow = Slow([ALLOW])
    classroom.clients = {'vlm.studio': slow, 'vlm.director': slow}
    try:
        sid = classroom.begin(CLASS)
        drawing = classroom.add_drawing(sid, png)
        request = classroom.request(sid, 'art-feedback', [drawing], {})['request_id']
        thread = classroom.start(request)
        assert entered.wait(5)
        classroom.cancel(sid, request)
        release.set(); thread.join(5)
        assert not thread.is_alive()
        events = list(classroom.follow(request))
        assert any(data.get('reason_code') == 'cancelled' for _, data in events)
        assert not any(data.get('outputs') for _, data in events)
        assert len(slow.prompts) == 1, 'no writer or grader after the cancelled safety call'
    finally:
        release.set(); classroom.close()


def test_http_voice_stream_sends_heartbeats_through_a_slow_generation(room):
    # VoxCPM2 answers in one block after 15-16 s (docs/measured/); Firefox's own
    # fetch() dropped that same silence at ~7.8 s with "Error in input stream"
    # where Chromium waited it out (measured). A slow fake voice
    # stands in for that wait; the heartbeat lines are what keep the connection
    # looking alive to a browser this strict, on either side of a real chunk.
    import threading
    import time
    from studio.serve import make_server

    class SlowVoice(Voice):
        def stream(self, text, voice_id, cancelled):
            time.sleep(2.5)
            yield from super().stream(text, voice_id, cancelled)

    classroom = room([])
    classroom.voice = SlowVoice()
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        sid = open_class(base)
        status, data = call(base, 'POST', f'/api/session/{sid}/speech', {'text': 'Hi', 'voice': 'gentle-male'})
        events = [json.loads(line) for line in data.splitlines()]
        assert status == 200
        assert events[-1]['type'] == 'done'
        assert sum(event['type'] == 'heartbeat' for event in events) >= 1
        assert [event['type'] for event in events if event['type'] != 'heartbeat'] == ['format', 'pcm', 'pcm', 'done']
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_http_voice_stream_is_same_origin_and_uses_session_voice(room):
    import threading
    import urllib.request
    from studio.serve import make_server
    classroom = room([])
    classroom.voice = Voice()
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        sid = open_class(base)
        status, data = call(base, 'POST', f'/api/session/{sid}/speech', {'text': 'Hi', 'voice': 'gentle-male'})
        events = [json.loads(line) for line in data.splitlines()]
        assert status == 200 and events[-1]['type'] == 'done'
        assert classroom.voice.calls == [('Hi', 'gentle-male')]
        request = urllib.request.Request(base + f'/api/session/{sid}/speech',
            data=json.dumps({'text': 'Hi'}).encode(), headers={'Content-Type': 'application/json', 'Origin': 'https://unrelated.invalid'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 403
        assert len(classroom.voice.calls) == 1
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_http_request_events_stay_alive_through_a_slow_stage_and_still_finish(room, png, monkeypatch):
    # A video stage sits silent for minutes (docs/measured/three-deployments.md:
    # 457 s on Replicate) and a browser as strict about silence
    # as the one measured on the speech route above would give up. SSE has a
    # comment line for exactly this, and the stream already wakes every tick to
    # look for news, so the route needs no second thread: a follower asked to
    # report quiet yields None and the route writes the comment. The run must
    # then END on the same connection, with its outputs; a keep-alive that lost
    # the last event would not show that.
    import threading
    import urllib.request
    from studio import serve as serve_module
    from studio.server import stream as stream_module
    from studio.serve import make_server
    from test_classroom import Scripted, GOOD, GROUNDED, CLEAN

    monkeypatch.setattr(stream_module, "TICK_S", 0.01)
    monkeypatch.setattr(serve_module, "KEEP_ALIVE_S", 0.05)
    entered, release, kept_alive = threading.Event(), threading.Event(), threading.Event()

    class Slow(Scripted):
        def chat(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().chat(*args, **kwargs)

    classroom = room([])
    slow = Slow([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.clients = {'vlm.studio': slow, 'vlm.director': slow}
    server = make_server(classroom, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    lines: list[str] = []
    try:
        sid = classroom.begin(CLASS)
        drawing = classroom.add_drawing(sid, png)
        request_id = classroom.request(sid, 'art-feedback', [drawing], {})['request_id']
        worker = classroom.start(request_id)
        assert entered.wait(5)

        def read_stream():
            with urllib.request.urlopen(f'{base}/api/requests/{request_id}/events', timeout=30) as reply:
                for raw in reply:
                    line = raw.decode('utf-8').strip()
                    lines.append(line)
                    if line == ': keep-alive':
                        kept_alive.set()

        reader = threading.Thread(target=read_stream, daemon=True); reader.start()
        assert kept_alive.wait(5), 'a silent stage is kept alive on the wire'
        release.set()
        worker.join(5); reader.join(5)
        assert not worker.is_alive() and not reader.is_alive(), 'the stream ends when the run ends'
        done = json.loads(lines[lines.index('event: done') + 1].removeprefix('data: '))
        assert done.get('outputs'), 'the same connection carried the finished result'
    finally:
        release.set(); server.shutdown(); server.server_close(); classroom.close()
