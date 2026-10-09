import json as jsonlib

import httpx
import pytest

from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable, UnknownProvider
from studio.providers import build_client, build_media_client
from studio.providers.stepfun import StepFunClient, StepFunMediaClient
from studio.core.slots import SlotConfig

DIRECTOR = "step-3.7-flash"
VOICE = "stepaudio-2.5-tts"

MP3 = b"ID3\x04\x00\x00\x00fake audio bytes"

# Shaped from a live response. Note what is NOT here: no `cost`, and
# no `provider`. Both exist on OpenRouter and neither does on this platform.
OK_BODY = {
    "id": "chatcmpl-x",
    "model": DIRECTOR,
    "choices": [{"message": {"content": "  太阳、骆驼  ", "role": "assistant"}, "finish_reason": "stop"}],
    "usage": {
        "prompt_tokens": 196,
        "completion_tokens": 995,
        "total_tokens": 1191,
        "completion_tokens_details": {"reasoning_tokens": 0},
    },
}


def chat_client(handler, options=None):
    return StepFunClient(
        DIRECTOR,
        options=options,
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def media_client(handler, options=None):
    return StepFunMediaClient(
        VOICE,
        options={"endpoint": "audio/speech", **(options or {})},
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def audio(request):
    return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})


# --- the chat half --------------------------------------------------------


def test_a_successful_call_returns_trimmed_text_and_usage():
    result = chat_client(lambda request: httpx.Response(200, json=OK_BODY)).chat("hello")
    assert result.text == "太阳、骆驼"
    assert result.input_tokens == 196
    assert result.output_tokens == 995
    assert result.provider == "stepfun"
    assert result.model == DIRECTOR
    assert result.latency_s >= 0


def test_cost_is_computed_from_the_profile_because_stepfun_reports_none():
    """OpenRouter returns usage.cost; this platform returns nothing at all.

    Without this the benchmark would publish 0.0 for every StepFun call and the
    cost column would quietly read as free.
    """
    assert "cost" not in OK_BODY["usage"]
    result = chat_client(
        lambda request: httpx.Response(200, json=OK_BODY),
        options={"price_usd_per_m_in": 0.19, "price_usd_per_m_out": 1.14},
    ).chat("hello")
    assert result.cost_usd == pytest.approx((196 * 0.19 + 995 * 1.14) / 1_000_000)


def test_a_profile_that_declares_no_price_reports_zero_rather_than_guessing():
    result = chat_client(lambda request: httpx.Response(200, json=OK_BODY)).chat("hello")
    assert result.cost_usd == 0.0


def test_reasoning_effort_rides_at_the_TOP_LEVEL_not_nested():
    """The one shape difference from OpenRouter, and it fails silently.

    OpenRouter takes {"reasoning": {"effort": "low"}}. StepFun takes a top-level
    "reasoning_effort" and ACCEPTS the nested form while ignoring it, so a copy
    of the OpenRouter body would look like it worked and think at full effort.
    """
    seen = {}

    def handle(request):
        seen.update(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    chat_client(handle, options={"reasoning_effort": "low"}).chat("hello")
    assert seen["reasoning_effort"] == "low"
    assert "reasoning" not in seen


def test_empty_content_raises_an_error_that_names_the_budget_and_the_useless_field():
    """Measured at max_tokens 200: content "", finish_reason "length", 200 spent.

    reasoning_tokens reads 0 while the thinking is billed as completion, so the
    error has to say so or the next reader will trust that field.
    """
    body = {
        **OK_BODY,
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 19, "completion_tokens": 200,
                  "completion_tokens_details": {"reasoning_tokens": 0}},
    }
    with pytest.raises(EmptyCompletion) as caught:
        chat_client(lambda request: httpx.Response(200, json=body)).chat("hello")
    message = str(caught.value)
    assert "max_tokens" in message
    assert "200" in message
    assert "length" in message
    assert "reasoning_tokens" in message


def test_images_are_sent_as_image_url_parts_beside_the_text():
    seen = {}

    def handle(request):
        seen.update(jsonlib.loads(request.content))
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=OK_BODY)

    chat_client(handle).chat("什么颜色", images=["data:image/png;base64,AAA"])
    parts = seen["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "什么颜色"}
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,AAA"
    assert seen["url"] == "https://api.stepfun.com/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"


def test_a_system_prompt_becomes_its_own_message():
    seen = {}

    def handle(request):
        seen.update(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    chat_client(handle).chat("hi", system="you are kind")
    assert [m["role"] for m in seen["messages"]] == ["system", "user"]


# --- the media half -------------------------------------------------------


def test_speech_comes_back_as_the_recording_itself():
    result = media_client(audio).make({"input": "你好"})
    assert result.content == MP3
    assert result.urls == []
    assert result.provider == "stepfun"


def test_the_voice_and_the_instruction_ride_in_the_body():
    """The instruction field is the entire reason this slot left SiliconFlow."""
    seen = {}

    def handle(request):
        seen.update(jsonlib.loads(request.content))
        seen["url"] = str(request.url)
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    media_client(handle).make(
        {"input": "你好", "voice": "wenrounvsheng", "instruction": "温柔一点"}
    )
    assert seen["model"] == VOICE
    assert seen["voice"] == "wenrounvsheng"
    assert seen["instruction"] == "温柔一点"
    assert seen["url"] == "https://api.stepfun.com/v1/audio/speech"


def test_a_slot_that_names_no_endpoint_is_refused_at_build_time():
    with pytest.raises(ModelRefused) as caught:
        StepFunMediaClient(VOICE, options={}, api_key="k")
    assert "endpoint" in str(caught.value)


def test_an_empty_recording_is_an_error_rather_than_silence():
    client = media_client(
        lambda request: httpx.Response(200, content=b"", headers={"content-type": "audio/mpeg"})
    )
    with pytest.raises(ModelRefused) as caught:
        client.make({"input": "x"})
    assert "empty" in str(caught.value)


# --- what both halves share -----------------------------------------------


@pytest.mark.parametrize("build", [chat_client, media_client])
def test_rate_limiting_is_retryable(build):
    client = build(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(ModelUnavailable):
        _call(client)


@pytest.mark.parametrize("build", [chat_client, media_client])
def test_a_rejected_key_is_not_reported_as_a_model_fault(build):
    client = build(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(ModelRefused) as caught:
        _call(client)
    assert "STEPFUN_API_KEY" in str(caught.value)


@pytest.mark.parametrize("build", [chat_client, media_client])
def test_an_empty_balance_is_told_apart_from_a_bad_key(build):
    client = build(lambda request: httpx.Response(402, text="no balance"))
    with pytest.raises(ModelRefused) as caught:
        _call(client)
    assert "balance" in str(caught.value).lower()
    assert "STEPFUN_API_KEY is not set" not in str(caught.value)


def test_a_missing_key_says_where_to_get_one(monkeypatch):
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
    with pytest.raises(ModelRefused) as caught:
        StepFunClient(DIRECTOR)
    assert "STEPFUN_API_KEY" in str(caught.value)
    assert "platform.stepfun.com" in str(caught.value)


def _call(client):
    if isinstance(client, StepFunClient):
        return client.chat("hello")
    return client.make({"input": "x"})


# --- the registry, which has to tell one shape from the other -------------


def _slot(name, options):
    return SlotConfig(slot=name, provider="stepfun", model="m", options=options)


def test_a_voice_slot_sent_to_the_chat_builder_is_named_not_guessed(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "k")
    with pytest.raises(UnknownProvider) as caught:
        build_client(_slot("tts.studio", {"task": "speak", "endpoint": "audio/speech"}))
    assert "build_media_client" in str(caught.value)


def test_a_chat_slot_sent_to_the_media_builder_is_named_not_guessed(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "k")
    with pytest.raises(UnknownProvider) as caught:
        build_media_client(_slot("vlm.director", {"max_tokens": 8000}))
    assert "build_client" in str(caught.value)


def test_each_builder_returns_the_right_client_for_its_shape(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "k")
    chat = build_client(_slot("vlm.director", {"max_tokens": 8000}))
    voice = build_media_client(
        _slot("tts.studio", {"task": "speak", "endpoint": "audio/speech"})
    )
    assert isinstance(chat, StepFunClient)
    assert isinstance(voice, StepFunMediaClient)


def test_partial_completion_cannot_pass_as_a_valid_review():
    payload = {**OK_BODY, "choices": [{"message": {"content": '{"ok":true,"issues":[]}'}, "finish_reason": "length"}]}
    with pytest.raises(EmptyCompletion, match="truncated"):
        chat_client(lambda request: httpx.Response(200, json=payload)).chat("review")


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_role_requests_are_stateless_and_send_their_own_effort(effort):
    requests = []
    def handle(request):
        requests.append(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)
    client = chat_client(handle, {"reasoning_effort": effort})
    client.chat("writer context must not leak", system="writer")
    client.chat("candidate only", system="reviewer")
    assert requests[-1]["reasoning_effort"] == effort
    assert len(requests[-1]["messages"]) == 2
    assert "writer context" not in jsonlib.dumps(requests[-1])


# --- the subscription -----------------------------------------------------
#
# StepFun sells a plan that answers on its own base URL,
# `.../step_plan/v1`, beside the pay-as-you-go `.../v1` this module
# already used. Both take the same key and answer the same way, so nothing
# at runtime can tell you which one you bought from. Only the address does.

PLAN = "https://api.stepfun.com/step_plan/v1"


def test_a_slot_may_send_its_calls_to_the_subscription_instead():
    seen = {}

    def handle(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=OK_BODY)

    chat_client(handle, {"base_url": PLAN}).chat("什么颜色")
    assert seen["url"] == PLAN + "/chat/completions"


def test_speech_follows_the_same_address():
    seen = {}

    def handle(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    media_client(handle, {"endpoint": "audio/speech", "base_url": PLAN}).make({"input": "你好"})
    assert seen["url"] == PLAN + "/audio/speech"


def test_a_plan_call_costs_nothing_per_call_even_where_a_price_is_written_down():
    """The price pair in the profile is a list price, and a plan is paid before
    the call. Computing dollars from tokens here would invent a bill nobody
    receives — which is the mirror of the earlier defect, where the absence of
    a price made real spending read as free.
    """
    priced = {"price_usd_per_m_in": 0.19, "price_usd_per_m_out": 1.14}
    billed = chat_client(lambda r: httpx.Response(200, json=OK_BODY), priced).chat("hi")
    assert billed.cost_usd > 0
    covered = chat_client(lambda r: httpx.Response(200, json=OK_BODY),
                          {**priced, "included_in_plan": True}).chat("hi")
    assert covered.cost_usd == 0.0
    # The tokens are still counted: what the plan removes is the price, not the use.
    assert covered.input_tokens == billed.input_tokens == 196
    assert covered.output_tokens == billed.output_tokens == 995


def test_a_plan_recording_costs_nothing_per_call_too():
    def handle(request):
        return httpx.Response(200, content=MP3, headers={"content-type": "audio/mpeg"})

    options = {"endpoint": "audio/speech", "price_usd": 0.0025}
    assert media_client(handle, options).make({"input": "你好"}).price_usd == 0.0025
    covered = media_client(handle, {**options, "included_in_plan": True})
    assert covered.make({"input": "你好"}).price_usd == 0.0


def test_a_slot_can_give_a_slow_task_more_time_and_every_other_slot_keeps_three_minutes():
    """The 3D figure's writing took 61-151 s and timed out at the old fixed 180 s when six
    ran at once; the limit is now a slot option, and a slot that names none keeps the old three minutes."""
    slow = StepFunClient(DIRECTOR, options={"timeout_s": 360}, api_key="test-key")
    usual = StepFunClient(DIRECTOR, options={}, api_key="test-key")
    assert slow._client.timeout.read == 360 and usual._client.timeout.read == 180
