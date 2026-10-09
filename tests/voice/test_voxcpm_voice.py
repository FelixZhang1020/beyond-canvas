"""Streaming/cleanup boundaries with fake inference; real MPS runs are separate."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import io
import threading
from types import SimpleNamespace

import pytest

from studio.providers.voxcpm_voice import VoxCPMRuntime, VoxCPMDialogueVoice, pcm_wav
from studio.providers.stepfun_voice import VoiceServiceError
from studio.ops.voice_lab import VoiceLab, Session


def runtime_fixture():
    runtime = VoxCPMRuntime.__new__(VoxCPMRuntime)
    runtime.worker = ThreadPoolExecutor(max_workers=1)
    return runtime


def test_stream_preserves_pcm_order_and_serializes_model_access():
    runtime = runtime_fixture()
    threads = []
    def speak(text, voice, emit, cancelled):
        threads.append(threading.get_ident())
        emit(b'first'); emit(b'second')
    runtime._speak = speak
    try:
        with ThreadPoolExecutor(max_workers=3) as callers:
            rows = list(callers.map(lambda _: list(runtime.stream('hello', 'gentle-female')), range(3)))
        assert rows == [[b'first', b'second']] * 3
        assert len(set(threads)) == 1
    finally:
        runtime.close()


def test_closing_stream_stops_producer_and_releases_worker_for_next_request():
    runtime = runtime_fixture(); stopped = threading.Event()
    def speak(text, voice, emit, cancelled):
        try:
            for _ in range(1000):
                if cancelled():
                    raise VoiceServiceError('已停止')
                emit(b'audio')
        finally:
            stopped.set()
    runtime._speak = speak
    try:
        output = runtime.stream('hello', 'gentle-female')
        assert next(output) == b'audio'
        output.close()
        assert stopped.wait(2)
        assert runtime.run(lambda: 'next request') == 'next request'
    finally:
        runtime.close()


def test_stream_errors_do_not_echo_private_model_messages():
    runtime = runtime_fixture()
    runtime._speak = lambda *args: (_ for _ in ()).throw(RuntimeError('private transcript'))
    try:
        with pytest.raises(VoiceServiceError) as error:
            list(runtime.stream('hello', 'gentle-female'))
        assert 'private' not in str(error.value)
    finally:
        runtime.close()


def test_cancelled_generation_closes_decoder_and_erases_both_kv_buffers():
    from contextlib import nullcontext
    runtime = runtime_fixture(); closed = []
    class Buffer:
        value = 'private'
        def zero_(self): self.value = 0
    caches = [SimpleNamespace(kv_cache=Buffer(), current_length=20) for _ in range(2)]
    def outputs(**kwargs):
        try: yield (object(), None, None)
        finally: closed.append(True)
    runtime.model = SimpleNamespace(text_tokenizer=list, device='cpu',
        generate_with_prompt_cache_streaming=outputs,
        base_lm=SimpleNamespace(kv_cache=caches[0]), residual_lm=SimpleNamespace(kv_cache=caches[1]))
    runtime.torch = SimpleNamespace(inference_mode=nullcontext)
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 1
    try:
        with pytest.raises(VoiceServiceError): runtime._generate('hello', {}, lambda _: None, cancelled)
        assert closed == [True]
        assert all(cache.kv_cache.value == 0 and cache.current_length == 0 for cache in caches)
    finally: runtime.close()


@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancelled'])
def test_article_reference_stays_in_memory_and_is_erased_on_each_exit(outcome, monkeypatch):
    runtime = runtime_fixture()
    class Tensor:
        cleared = False
        def zero_(self):
            self.cleared = True
    feature = Tensor(); cache = {'ref_audio_feat': feature, 'prompt_text': 'private'}
    resets = []
    def build(**kwargs):
        assert isinstance(kwargs['prompt_wav_path'], io.BytesIO)
        assert isinstance(kwargs['reference_wav_path'], io.BytesIO)
        return cache
    runtime.model = SimpleNamespace(build_prompt_cache=build)
    runtime.torch = SimpleNamespace(Tensor=Tensor, inference_mode=nullcontext)
    runtime.sf = SimpleNamespace(info=lambda _: SimpleNamespace(channels=1, duration=6))
    runtime._clear_state = lambda: resets.append(True)
    def generate(text, cache, emit, cancelled):
        if outcome == 'failure': raise RuntimeError('failure')
        if cancelled(): raise VoiceServiceError('已停止')
        emit(b'\x01\x00' * 100)
    runtime._generate = generate
    checks = 0
    def cancelled():
        nonlocal checks
        checks += 1
        return outcome == 'cancelled' and checks > 1
    try:
        if outcome == 'success':
            assert runtime.read_article(b'wav', 'reference', ['article'], lambda _: None, cancelled).startswith(b'RIFF')
        else:
            with pytest.raises((RuntimeError, VoiceServiceError)):
                runtime.read_article(b'wav', 'reference', ['article'], lambda _: None, cancelled)
        assert cache == {} and feature.cleared and resets
    finally:
        runtime.close()


def test_lab_stream_validates_question_voice_cache_and_session_cancellation():
    calls = []
    runtime = SimpleNamespace(stream=lambda *args: calls.append(args[:2]) or iter([b'\x01\x00'*200]))
    voice = VoxCPMDialogueVoice(runtime)
    # Use a true generator because stream consumers close their producers.
    def generate(*args):
        calls.append(args[:2]); yield b'\x01\x00'*200
    runtime.stream = generate
    lab = VoiceLab(ears=object(), chat=object(), dialogue_voice=voice)
    session = Session()
    for invalid in ['Serena', [], 'missing']:
        with pytest.raises(ValueError): list(lab.stream_speech(session, 0, invalid))
    session.history.append({'role': 'user', 'text': 'private'})
    for invalid in [1, True, -1, '0']:
        with pytest.raises(ValueError): list(lab.stream_speech(session, invalid))
    first = list(lab.stream_speech(session, 0))
    assert first[-1] == {'type': 'done'} and len(calls) == 1
    assert list(lab.stream_speech(session, 0))[0]['cached'] is True
    assert len(calls) == 1
    list(lab.stream_speech(session, 0, 'gentle-male')); assert len(calls) == 2
    session.cancelled.set()
    with pytest.raises(KeyError): list(lab.stream_speech(session, 0))


def test_partial_or_failed_speech_is_never_cached():
    class Voice(VoxCPMDialogueVoice):
        def stream(self, *args):
            yield b'\x01\x00' * 200
            raise VoiceServiceError('failed')
    session = Session()
    lab = VoiceLab(ears=object(), chat=object(), dialogue_voice=Voice(None))
    with pytest.raises(VoiceServiceError): list(lab.stream_speech(session, 0))
    assert not session.speech


def test_http_delivers_first_audio_before_completion_and_end_cancels_remaining_audio():
    import httpx
    from studio.ops.voice_lab import VoiceLabServer
    released = threading.Event()
    class Voice(VoxCPMDialogueVoice):
        def stream(self, text, voice_id, cancelled):
            yield b'\x01\x00' * 200
            assert released.wait(3)
            if cancelled(): raise VoiceServiceError('已停止')
            yield b'\x02\x00' * 200
    lab = VoiceLab(ears=object(), chat=object(), dialogue_voice=Voice(None))
    server = VoiceLabServer(('127.0.0.1', 0), lab)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}'
        with httpx.Client(base_url=url, trust_env=False, timeout=5) as client:
            assert client.post('/api/speech-stream', json={'question_id': 0}).status_code == 404
            token = client.post('/api/session').json()['session_id']
            headers = {'X-Lab-Session': token}
            assert client.post('/api/speech-stream', headers={**headers, 'Origin': 'https://other.test'}, json={'question_id':0}).status_code == 403
            for invalid in [-1, True, '0']:
                assert client.post('/api/speech-stream', headers=headers, json={'question_id':invalid}).status_code == 400
            with client.stream('POST', '/api/speech-stream', headers=headers, json={'question_id':0}) as response:
                import json
                assert response.status_code == 200
                events = response.iter_lines()
                assert json.loads(next(events))['type'] == 'format'
                assert json.loads(next(events))['type'] == 'pcm'
                assert not released.is_set()  # Provider is still blocked mid-generation.
                session = lab.get(token)
                assert not session.speech
                assert client.post('/api/end', json={'session_id':token}).status_code == 200
                released.set()
                assert json.loads(next(events))['type'] == 'error'
                assert not session.speech
            assert client.post('/api/speech-stream', headers=headers, json={'question_id':0}).status_code == 404
    finally:
        released.set(); server.shutdown(); server.server_close(); thread.join(timeout=2)
