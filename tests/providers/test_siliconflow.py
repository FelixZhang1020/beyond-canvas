import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.siliconflow import SiliconFlowClient

VOICE = "FunAudioLLM/CosyVoice2-0.5B"
PICTURE = "Qwen/Qwen-Image-Edit"

MP3 = b"ID3\x04\x00\x00\x00fake audio bytes"
IMAGES = {"images": [{"url": "https://sf.example/out.png"}], "seed": 7}


def make_client(handler, model=VOICE, endpoint="audio/speech", options=None):
    return SiliconFlowClient(
        model,
        options={"endpoint": endpoint, **(options or {})},
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def audio(request):
    return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})


def test_speech_comes_back_as_the_recording_itself_not_a_link():
    """The difference that made this provider need its own reader.

    Replicate and fal answer with a URL; this one answers with the file. A
    client that only knew about URLs would report success and hand the caller
    nothing.
    """
    result = make_client(audio).make({"input": "你好"})
    assert result.content == MP3
    assert result.urls == []
    assert result.provider == "siliconflow"
    assert result.latency_s >= 0


def test_image_editing_comes_back_as_json_holding_a_link():
    def handle(request):
        return httpx.Response(200, json=IMAGES)

    result = make_client(handle, PICTURE, "images/generations").make({"prompt": "x"})
    assert result.urls == ["https://sf.example/out.png"]
    assert result.content == b""
    assert result.payload["seed"] == 7


def test_the_model_rides_in_the_body_with_the_callers_fields():
    seen = {}

    def handle(request):
        import json as jsonlib
        seen.update(jsonlib.loads(request.content))
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    make_client(handle, options={"extra_ignored": 1}).make({"input": "你好", "voice": "anna"})
    assert seen["model"] == VOICE
    assert seen["input"] == "你好"
    assert seen["voice"] == "anna"
    assert seen["url"] == "https://api.siliconflow.cn/v1/audio/speech"
    assert seen["auth"] == "Bearer test-key"


def test_a_slot_that_names_no_endpoint_is_refused_at_build_time():
    """Two shapes share this client, so the path is not guessable."""
    with pytest.raises(ModelRefused) as caught:
        SiliconFlowClient(VOICE, options={}, api_key="k")
    assert "endpoint" in str(caught.value)


def test_a_missing_key_says_where_to_get_one(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    with pytest.raises(ModelRefused) as caught:
        SiliconFlowClient(VOICE, options={"endpoint": "audio/speech"})
    assert "SILICONFLOW_API_KEY" in str(caught.value)
    assert "siliconflow.cn" in str(caught.value)


def test_an_empty_balance_is_told_apart_from_a_bad_key():
    client = make_client(lambda request: httpx.Response(402, text="no balance"))
    with pytest.raises(ModelRefused) as caught:
        client.make({"input": "x"})
    assert "balance" in str(caught.value).lower()
    assert "SILICONFLOW_API_KEY" not in str(caught.value)


def test_a_rejected_key_is_not_reported_as_a_model_fault():
    client = make_client(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(ModelRefused) as caught:
        client.make({"input": "x"})
    assert "SILICONFLOW_API_KEY" in str(caught.value)


def test_rate_limiting_is_retryable():
    client = make_client(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(ModelUnavailable):
        client.make({"input": "x"})


def test_an_empty_recording_is_an_error_rather_than_silence():
    """A zero-byte answer would otherwise reach a child as a voice that says nothing."""
    client = make_client(
        lambda request: httpx.Response(200, content=b"", headers={"content-type": "audio/mpeg"})
    )
    with pytest.raises(ModelRefused) as caught:
        client.make({"input": "x"})
    assert "empty" in str(caught.value)


def test_the_chinese_cloud_is_the_default_and_the_other_is_reachable():
    """A .cn key gets "Token is invalid" from the .com host, which reads as a
    bad key rather than the wrong country."""
    seen = {}

    def handle(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    make_client(handle).make({"input": "x"})
    assert seen["url"].startswith("https://api.siliconflow.cn/")

    make_client(handle, options={"base_url": "https://api.siliconflow.com/v1"}).make({"input": "x"})
    assert seen["url"].startswith("https://api.siliconflow.com/")
