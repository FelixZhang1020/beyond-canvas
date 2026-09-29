"""Provider boundaries with fake MLX objects; real model checks are measured separately."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import pytest

from studio.providers.qwen_voice import QwenDialogueVoice, QwenVoiceRuntime
from studio.providers.stepfun_voice import VoiceServiceError
from studio.ops.voice_lab import Session, VoiceLab


def test_qwen_voice_allowlist_and_cache_do_not_fall_back_to_cloud_ids():
    calls = []
    runtime = SimpleNamespace(speak=lambda text, speaker: calls.append(speaker) or speaker.encode())
    runtime.run = lambda fn, *args: fn(*args)
    voice = QwenDialogueVoice(runtime)
    lab = VoiceLab(dialogue_voice=voice)
    session = Session()
    assert lab.speak(session, 0) == b"Serena"
    assert lab.speak(session, 0, "Uncle_Fu") == b"Uncle_Fu"
    assert lab.speak(session, 0) == b"Serena"
    for invalid in ("elegantgentle-female", "wenrounansheng", [], "unlisted"):
        with pytest.raises(ValueError):
            lab.speak(session, 0, invalid)
    assert calls == ["Serena", "Uncle_Fu"]


def test_worker_serializes_model_access_and_does_not_echo_internal_errors():
    runtime = QwenVoiceRuntime.__new__(QwenVoiceRuntime)
    runtime.worker = ThreadPoolExecutor(max_workers=1)
    try:
        with ThreadPoolExecutor(max_workers=3) as callers:
            ids = list(callers.map(lambda _: runtime.run(threading.get_ident), range(8)))
        assert len(set(ids)) == 1 and ids[0] != threading.get_ident()
        def fail():
            raise RuntimeError("private reference transcript")
        with pytest.raises(VoiceServiceError) as error:
            runtime.run(fail)
        assert "private" not in str(error.value)
    finally:
        runtime.close()


@pytest.mark.parametrize("outcome", ["success", "failed", "cancelled"])
def test_article_clears_reference_and_decoder_state_on_every_exit(outcome):
    runtime = QwenVoiceRuntime.__new__(QwenVoiceRuntime)
    resets = []
    cache = {"previous_session": "private"}
    clone = SimpleNamespace(_icl_cache=cache, sample_rate=24000,
                            speech_tokenizer=SimpleNamespace(decoder=SimpleNamespace(reset_streaming_state=lambda: resets.append(1))))
    class Audio:
        ndim = 1
        def __len__(self):
            return 24000 * 6
    runtime.sf = SimpleNamespace(read=lambda *args, **kwargs: (Audio(), 24000))
    runtime.mx = SimpleNamespace(array=lambda value, **kwargs: value, float32=None, clear_cache=lambda: None)
    runtime.clone = clone
    def generate(**kwargs):
        cache["current_session"] = "private"
        yield b"audio"
    clone.generate = generate
    def collect(results, cancelled):
        value = next(results)
        if outcome == "failed":
            raise RuntimeError("decoder failed")
        return value
    runtime._collect = collect
    progress = []
    from unittest.mock import patch
    with patch("studio.providers.qwen_voice.join_wavs", side_effect=lambda parts: b"".join(parts)):
        if outcome == "success":
            assert runtime.read_article(b"wav", "reference", ["target"], progress.append, lambda: False) == b"audio"
            assert progress == [1]
        else:
            with pytest.raises((RuntimeError, VoiceServiceError)):
                runtime.read_article(b"wav", "reference", ["target"], progress.append, lambda: outcome == "cancelled")
            assert not progress
    assert not cache and len(resets) == 2


def test_interrupted_chunk_collection_closes_generator():
    runtime = QwenVoiceRuntime.__new__(QwenVoiceRuntime)
    closed = []
    def generate():
        try:
            yield object()
        finally:
            closed.append(True)
    with pytest.raises(VoiceServiceError, match="已结束"):
        runtime._collect(generate(), lambda: True)
    assert closed == [True]
