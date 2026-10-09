"""Voice lab contracts. Fake models, real PCM and (where stated) a local HTTP server."""
import array
import base64
import io
import json
import math
import threading
import time
import wave
from types import SimpleNamespace

import httpx
import pytest

from studio.providers.stepfun_voice import StepFunDialogueVoice, StepFunVoicePreview, VoiceServiceError, article_parts, join_wavs
from studio.ops.voice_lab import Session, VoiceLab, VoiceLabServer, read_wav, reference_clip, resample, wav_bytes


def recording(seconds=8, rate=24000, amplitude=6000):
    return wav_bytes(array.array("h", (int(amplitude * math.sin(i * 2 * math.pi * 180 / rate))
                                      for i in range(int(seconds * rate)))), rate)


class Ears:
    def hear(self, data, language, filename):
        pcm, rate = read_wav(data)
        assert rate == 16000
        return SimpleNamespace(text="这是完整回答。" if filename == "answer.wav" else "这是参考片段。")


class Chat:
    def chat(self, prompt, **kwargs):
        assert "这是完整回答" in prompt
        return SimpleNamespace(text="当时你最注意到的是什么？")


def test_voice_dialogue_keeps_the_local_model_when_the_classroom_uses_qwen(monkeypatch):
    from studio.ops import voice_lab
    from studio.core.slots import load_profile

    assert load_profile("local")["vlm.studio"].provider == "openrouter"
    calls = []

    def answer(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "接下来呢？"}}]})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        def local_client(**kwargs):
            assert kwargs == {"timeout": 65, "trust_env": False}
            return client

        monkeypatch.setattr(voice_lab.httpx, "Client", local_client)
        lab = VoiceLab(ears=Ears())
        assert lab.chat.chat("成人测试对话").text == "接下来呢？"
    assert len(calls) == 1
    assert str(calls[0].url) == "http://127.0.0.1:7100/v1/chat/completions"
    body = json.loads(calls[0].content)
    assert body["model"] == "step3-vl-10b"
    assert body["max_tokens"] == 2200
    assert [message["role"] for message in body["messages"]] == ["user"]


def test_voice_dialogue_rejects_a_hosted_slot_before_building_a_local_client(monkeypatch):
    from dataclasses import replace
    from studio.ops import voice_lab
    from studio.core.slots import load_profile

    profile = load_profile("local")
    profile["vlm.voice_lab"] = replace(profile["vlm.voice_lab"], provider="openrouter")
    monkeypatch.setattr(voice_lab, "load_profile", lambda name: profile)
    monkeypatch.setattr(voice_lab, "LlamaCppClient", lambda *a, **kw: pytest.fail("built a mismatched client"))
    with pytest.raises(ValueError, match="vlm.voice_lab requires the local llamacpp provider"):
        VoiceLab(ears=Ears())


def test_an_injected_dialogue_client_does_not_load_runtime_configuration(monkeypatch):
    from studio.ops import voice_lab

    monkeypatch.setattr(voice_lab, "load_profile", lambda name: pytest.fail("loaded runtime configuration"))
    chat = Chat()
    assert VoiceLab(ears=Ears(), chat=chat).chat is chat


def test_reference_requires_real_energy_and_enough_speech_not_just_a_wav_header():
    for duration, amplitude, usable in [(8, 6000, True), (3, 6000, False), (8, 0, False)]:
        pcm, rate = read_wav(recording(duration, amplitude=amplitude))
        clip, quality = reference_clip(pcm, rate)
        assert quality["usable"] is usable
        if usable:
            assert 5 <= len(read_wav(clip)[0]) / rate <= 10
    overloaded = array.array("h", [32767, -32768] * (24000 * 4))
    assert not reference_clip(overloaded, 24000)[1]["usable"]


def test_long_answer_yields_one_bounded_clip_and_resampling_preserves_duration():
    pcm, rate = read_wav(recording(20))
    clip, quality = reference_clip(pcm, rate)
    assert quality["usable"]
    assert quality["seconds"] == 9
    reduced, new_rate = read_wav(resample(pcm, rate))
    assert len(reduced) / new_rate == 20


def test_bad_and_overlong_recordings_are_refused():
    with pytest.raises(ValueError):
        read_wav(b"not a recording")
    with pytest.raises(ValueError):
        read_wav(recording(46))


def test_article_chunking_keeps_unicode_and_parenthetical_words_audible():
    text = "你好🙂，这里是测试。" * 25 + "（这些字也要读出来）"
    parts = article_parts(text)
    assert max(map(len, parts)) <= 48
    assert "".join(parts) == text.replace("（", "，").replace("）", "，")
    assert "🙂" in "".join(parts)
    for invalid in (" ", "字" * 501):
        with pytest.raises(ValueError):
            article_parts(invalid)


def provider_mock(fail_preview=False, fail_delete=False):
    calls = []
    wav = recording(1)
    def handler(request):
        calls.append(request)
        if request.method == "DELETE":
            assert request.url.path == "/v1/files/file-this-test"
            return httpx.Response(500 if fail_delete else 200, json={"deleted": not fail_delete})
        if request.url.path == "/v1/files":
            assert b"storage" in request.content
            return httpx.Response(200, json={"id": "file-this-test"})
        assert request.url.path == "/v1/audio/voices/preview"
        if fail_preview:
            return httpx.Response(400, json={"error": "private text that must never appear"})
        body = json.loads(request.content)
        assert body["file_id"] == "file-this-test"
        assert body["text"] == "参考原文"
        assert body["response_format"] == "wav"
        assert "voice_label" not in body
        return httpx.Response(200, json={"sample_audio": base64.b64encode(wav).decode()})
    return StepFunVoicePreview("fake", httpx.Client(transport=httpx.MockTransport(handler))), calls


def test_preview_uploads_once_deletes_its_own_file_and_returns_all_segments():
    provider, calls = provider_mock()
    progress = []
    output = provider.synthesize(recording(), "参考原文", ["第一句。", "第二句。"], progress.append)
    with wave.open(io.BytesIO(output)) as wav:
        assert wav.getnframes() / wav.getframerate() == pytest.approx(2.12)
    assert [r.method for r in calls] == ["POST", "POST", "POST", "DELETE"]
    assert progress == [1, 2]
    assert not provider.pending_cleanup


def test_preview_failure_still_cleans_up_and_redacts_vendor_error():
    provider, calls = provider_mock(fail_preview=True)
    with pytest.raises(VoiceServiceError) as error:
        provider.synthesize(recording(), "参考原文", ["句子。"])
    assert "private text" not in str(error.value)
    assert "合成朗读失败" in str(error.value)
    assert calls[-1].method == "DELETE"


@pytest.mark.parametrize("param,hint", [
    ("text", "文字与录音是否一致"), ("file_id", "无法使用这份参考录音"),
    ("model", "无法使用所选语音模型"), ("private-field", "尚不能确定"),
])
def test_rejection_identifies_safe_parameter_and_never_echoes_private_message(param, hint):
    def reject(request):
        return httpx.Response(400, json={"error": {
            "param": param, "message": "private transcript and secret token", "code": "private-code",
        }})
    provider = StepFunVoicePreview("fake", httpx.Client(transport=httpx.MockTransport(reject)))
    with pytest.raises(VoiceServiceError) as error:
        provider.synthesize(recording(), "参考原文", ["句子。"])
    message = str(error.value)
    assert "上传原声失败" in message and hint in message
    assert "private" not in message and "secret" not in message


def test_uncertain_upload_reports_cleanup_uncertainty_without_repeating_upload():
    calls = []
    def lost(request):
        calls.append(request)
        raise httpx.ReadTimeout("private transport information")
    provider = StepFunVoicePreview("fake", httpx.Client(transport=httpx.MockTransport(lost)))
    with pytest.raises(VoiceServiceError, match="上传结果不确定") as error:
        provider.synthesize(recording(), "参考原文", ["句子。"])
    assert len(calls) == 1
    assert "private transport" not in str(error.value)


def test_failed_deletion_is_pending_and_janitor_never_deletes_an_active_reference():
    provider, calls = provider_mock(fail_delete=True)
    def progress(_):
        assert provider.retry_cleanup()
        assert all(r.method != "DELETE" for r in calls)
    provider.synthesize(recording(), "参考原文", ["句子。"], progress)
    assert provider.pending_cleanup
    assert not provider.retry_cleanup()
    assert calls[-1].method == "DELETE"


def test_cancellation_stops_further_paid_segments_and_cleans_upload():
    provider, calls = provider_mock()
    stop = threading.Event()
    with pytest.raises(VoiceServiceError, match="停止"):
        provider.synthesize(recording(), "参考原文", ["第一句。", "第二句。"], lambda _: stop.set(), stop.is_set)
    assert len([r for r in calls if r.url.path.endswith("/preview")]) == 1
    assert calls[-1].method == "DELETE"


def test_incompatible_or_empty_audio_is_not_presented_as_success():
    with pytest.raises(VoiceServiceError):
        join_wavs([recording(1), recording(1, rate=16000)])
    with pytest.raises(VoiceServiceError):
        join_wavs([b"bad"])


def test_record_is_local_and_generation_requires_confirmation_then_end_forgets_everything():
    class Voice:
        pending_cleanup = False
        called = False
        def synthesize(self, reference, text, parts, progress, cancelled):
            self.called = True
            assert text == "这是参考片段。"  # Never pass the full answer for a cropped clip.
            progress(len(parts))
            return recording(1)
    voice = Voice()
    lab = VoiceLab(Ears(), Chat(), voice)
    token = lab.begin(); session = lab.get(token)
    sample = lab.record(session, recording())
    assert not voice.called
    with pytest.raises(ValueError, match="确认"):
        lab.generate(session, sample["id"], "朗读内容。")
    lab.turn(session, sample["id"], sample["transcript"], sample["reference_text"])
    with pytest.raises(ValueError, match="已确认"):
        lab.turn(session, sample["id"], sample["transcript"], sample["reference_text"])
    lab.generate(session, sample["id"], "朗读内容。")
    deadline = time.monotonic() + 2
    while session.job["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.01)
    assert session.job["status"] == "done"
    assert session.output
    lab.end(token)
    assert not session.samples and not session.history and not session.output
    with pytest.raises(KeyError):
        lab.get(token)


def test_idle_expiry_and_reference_from_another_session():
    lab = VoiceLab(Ears(), Chat())
    first, second = lab.begin(), lab.begin()
    sample = lab.record(lab.get(first), recording())
    with pytest.raises(KeyError):
        lab.turn(lab.get(second), sample["id"], "答案", "参考")
    lab.sessions[first].touched -= 1801
    lab.expire()
    assert first not in lab.sessions
    assert second in lab.sessions


def test_http_session_isolation_origin_guard_and_recording_roundtrip():
    lab = VoiceLab(Ears(), Chat())
    server = VoiceLabServer(("127.0.0.1", 0), lab)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with httpx.Client(base_url=url, trust_env=False) as client:
            assert client.get("/").status_code == 200
            assert client.post("/api/session", headers={"Origin": "https://unrelated.test"}).status_code == 403
            assert client.get("/", headers={"Host": "unrelated.test"}).status_code == 403
            assert client.get("/api/job").status_code == 404
            token = client.post("/api/session").json()["session_id"]
            headers = {"X-Lab-Session": token}
            result = client.post("/api/record", content=recording(), headers=headers)
            assert result.status_code == 200
            sample_id = result.json()["id"]
            assert client.get("/api/sample/" + sample_id).status_code == 404
            assert client.get("/api/sample/" + sample_id, headers=headers).headers["Content-Type"] == "audio/wav"
            assert client.post("/api/discard", json={"sample_id": sample_id}, headers=headers).status_code == 200
            assert client.get("/api/sample/" + sample_id, headers=headers).status_code == 404
            assert client.post("/api/end", json={"session_id": token}).status_code == 200
            assert client.get("/api/job", headers=headers).status_code == 404
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.mark.parametrize("voice_id", ["elegantgentle-female", "wenrounansheng"])
def test_dialogue_voice_matches_selected_audition_and_never_sends_recordings(voice_id):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=recording(1), headers={"Content-Type": "audio/wav"})
    voice = StepFunDialogueVoice("fake", httpx.Client(transport=httpx.MockTransport(handler)))
    assert read_wav(voice.synthesize("你好（慢慢说🙂）", voice_id))[1] == 24000
    assert len(calls) == 1 and calls[0].url.path == "/v1/audio/speech"
    payload = json.loads(calls[0].content)
    assert payload == {
        "model": "stepaudio-2.5-tts", "voice": voice_id,
        "input": "你好，慢慢说🙂，", "instruction": StepFunDialogueVoice.instruction,
        "response_format": "wav", "sample_rate": 24000, "speed": 1,
    }
    for invalid in ("", "字" * 401, None):
        with pytest.raises(ValueError):
            voice.synthesize(invalid)
    assert len(calls) == 1

    for invalid in ("unknown", None, {"voice": "wenrounansheng"}):
        with pytest.raises(ValueError):
            voice.synthesize("你好", invalid)
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["refusal", "timeout", "invalid_audio"])
def test_dialogue_failure_is_redacted_and_not_automatically_retried(failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private transcript and token")
        if failure == "refusal":
            return httpx.Response(400, json={"error": {"message": "private transcript and token"}})
        return httpx.Response(200, content=b"private invalid audio")
    voice = StepFunDialogueVoice("fake", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(VoiceServiceError) as error:
        voice.synthesize("这是一个问题。")
    assert "private" not in str(error.value)
    assert len(calls) == 1


def test_question_replay_caches_only_assistant_text_and_end_erases_audio():
    calls = []
    voice = SimpleNamespace(synthesize=lambda text, voice_id: calls.append(text) or recording(1))
    lab = VoiceLab(Ears(), Chat(), dialogue_voice=voice)
    token = lab.begin(); session = lab.get(token)
    assert lab.speak(session, 0) == lab.speak(session, 0)
    assert len(calls) == 1
    sample = lab.record(session, recording())
    reply = lab.turn(session, sample["id"], sample["transcript"], sample["reference_text"])
    for invalid in (-1, 1, True, "0", 999):
        with pytest.raises(ValueError):
            lab.speak(session, invalid)
    assert len(calls) == 1  # User text and arbitrary IDs never reach the provider.
    lab.speak(session, reply["question_id"])
    assert calls[-1] == reply["reply"]
    assert len(session.speech) == 2
    lab.end(token)
    assert not session.speech
    with pytest.raises(KeyError):
        lab.speak(session, 0)


def test_late_speech_cannot_restore_an_ended_session():
    entered, release = threading.Event(), threading.Event()
    def synthesize(_, voice_id):
        entered.set(); assert release.wait(2)
        return recording(1)
    lab = VoiceLab(Ears(), Chat(), dialogue_voice=SimpleNamespace(synthesize=synthesize))
    token = lab.begin(); session = lab.get(token)
    errors = []
    def work():
        try:
            lab.speak(session, 0)
        except Exception as error:
            errors.append(type(error))
    thread = threading.Thread(target=work); thread.start()
    try:
        assert entered.wait(2)
        lab.end(token)
    finally:
        release.set(); thread.join(timeout=2)
    assert errors == [KeyError] and not session.speech


def test_speech_http_requires_session_and_uses_current_question():
    calls = []
    voice = SimpleNamespace(synthesize=lambda text, voice_id: calls.append(text) or recording(1))
    lab = VoiceLab(Ears(), Chat(), dialogue_voice=voice)
    server = VoiceLabServer(("127.0.0.1", 0), lab)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_address[1]}", trust_env=False) as client:
            assert client.post("/api/speech", json={"question_id": 0}).status_code == 404
            begun = client.post("/api/session").json()
            headers = {"X-Lab-Session": begun["session_id"]}
            for _ in range(2):
                audio = client.post("/api/speech", headers=headers, json={"question_id": begun["question_id"]})
                assert audio.status_code == 200 and audio.headers["Content-Type"] == "audio/wav"
            assert len(calls) == 1
            assert client.post("/api/speech", headers=headers, json={"question_id": 0, "voice_id": "unlisted"}).status_code == 400
            assert len(calls) == 1
            assert client.post("/api/speech", headers=headers, json={"text": "arbitrary"}).status_code == 400
            other = client.post("/api/session").json()["session_id"]
            lab.sessions[begun["session_id"]].history.append({"role": "assistant", "text": "本轮特有问题"})
            assert client.post("/api/speech", headers={"X-Lab-Session": other}, json={"question_id": 1}).status_code == 400
            client.post("/api/end", json={"session_id": begun["session_id"]})
            assert client.post("/api/speech", headers=headers, json={"question_id": 0}).status_code == 404
            assert len(calls) == 1
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_switching_voices_uses_separate_cache_and_preserves_samples_and_history():
    calls = []
    def synthesize(text, voice_id):
        calls.append((text, voice_id))
        return recording(1, amplitude=6000 if voice_id == "wenrounansheng" else 3000)
    lab = VoiceLab(Ears(), Chat(), dialogue_voice=SimpleNamespace(synthesize=synthesize))
    token = lab.begin(); session = lab.get(token)
    lab.record(session, recording())
    history, samples = list(session.history), dict(session.samples)
    female = lab.speak(session, 0, "elegantgentle-female")
    male = lab.speak(session, 0, "wenrounansheng")
    assert female != male
    assert lab.speak(session, 0, "elegantgentle-female") == female
    assert lab.speak(session, 0, "wenrounansheng") == male
    assert [voice for _, voice in calls] == ["elegantgentle-female", "wenrounansheng"]
    assert session.history == history and session.samples == samples
    lab.end(token)
    assert not session.speech
