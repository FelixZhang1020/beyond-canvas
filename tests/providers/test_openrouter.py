import json as jsonlib

import httpx
import pytest

from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable
from studio.providers.openrouter import OpenRouterClient

OK_BODY = {
    "provider": "StepFun",
    "model": "stepfun/step-3.7-flash",
    "choices": [{"message": {"content": "  I see a yellow circle.  "}}],
    "usage": {
        "prompt_tokens": 215,
        "completion_tokens": 40,
        "cost": 0.00072535,
        "completion_tokens_details": {"reasoning_tokens": 213},
    },
}


def make_client(handler, options=None):
    transport = httpx.MockTransport(handler)
    return OpenRouterClient(
        "stepfun/step-3.7-flash",
        options=options,
        api_key="test-key",
        client=httpx.Client(transport=transport),
    )


def test_a_successful_call_returns_trimmed_text_and_usage():
    client = make_client(lambda request: httpx.Response(200, json=OK_BODY))
    result = client.chat("hello")
    assert result.text == "I see a yellow circle."
    assert result.input_tokens == 215
    assert result.reasoning_tokens == 213
    assert result.cost_usd == pytest.approx(0.00072535)
    assert result.provider == "StepFun"
    assert result.latency_s >= 0


def test_null_content_raises_an_error_that_names_the_token_budget():
    body = {**OK_BODY, "choices": [{"message": {"content": None}}]}
    client = make_client(lambda request: httpx.Response(200, json=body))
    with pytest.raises(EmptyCompletion) as caught:
        client.chat("hello")
    assert "max_tokens" in str(caught.value)


def test_rate_limiting_is_retryable():
    client = make_client(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(ModelUnavailable):
        client.chat("hello")


def test_a_bad_request_is_not_retryable():
    client = make_client(lambda request: httpx.Response(400, text="bad params"))
    with pytest.raises(ModelRefused):
        client.chat("hello")


def test_a_network_failure_is_retryable():
    def explode(request):
        raise httpx.ConnectError("no route to host")

    with pytest.raises(ModelUnavailable):
        make_client(explode).chat("hello")


def test_options_become_reasoning_effort_and_a_pinned_provider():
    seen = {}

    def capture(request):
        seen.update(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    client = make_client(
        capture,
        options={"reasoning_effort": "low", "max_tokens": 1600, "provider_order": ["StepFun"]},
    )
    client.chat("hello", system="be precise")
    assert seen["reasoning"] == {"effort": "low"}
    assert seen["max_tokens"] == 1600
    assert seen["provider"] == {"order": ["StepFun"], "allow_fallbacks": False}
    assert seen["messages"][0] == {"role": "system", "content": "be precise"}


def test_a_missing_api_key_is_refused_before_any_request():
    with pytest.raises(ModelRefused):
        OpenRouterClient("stepfun/step-3.7-flash", api_key="")


def test_images_are_attached_to_the_user_message():
    seen = {}

    def capture(request):
        seen.update(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    make_client(capture).chat("describe", ["data:image/png;base64,AAAA"])
    parts = seen["messages"][-1]["content"]
    assert parts[0]["type"] == "text"
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
