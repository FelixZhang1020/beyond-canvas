import json as jsonlib

import httpx
import pytest

from studio.core.errors import EmptyCompletion, ModelUnavailable
from studio.providers import build_client
from studio.providers.llamacpp import LlamaCppClient
from studio.core.slots import SlotConfig

OK_BODY = {
    "model": "step-local",
    "choices": [{"message": {"content": "I notice two purple shapes."}}],
    "usage": {"prompt_tokens": 90, "completion_tokens": 22},
}


def make_client(handler, options=None):
    return LlamaCppClient(
        "step-local", options=options, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_a_local_call_reports_zero_cost_and_real_token_counts():
    result = make_client(lambda request: httpx.Response(200, json=OK_BODY)).chat("hi")
    assert result.text == "I notice two purple shapes."
    assert result.output_tokens == 22
    assert result.cost_usd == 0.0
    assert result.provider == "llamacpp"


def test_the_base_url_option_decides_where_the_request_goes():
    seen = {}

    def capture(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=OK_BODY)

    make_client(capture, {"base_url": "http://127.0.0.1:9099"}).chat("hi")
    assert seen["url"] == "http://127.0.0.1:9099/v1/chat/completions"


def test_a_dead_server_names_llama_server_in_the_error():
    def explode(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ModelUnavailable) as caught:
        make_client(explode).chat("hi")
    assert "llama-server" in str(caught.value)


def test_empty_content_raises_the_same_error_as_the_hosted_client():
    body = {**OK_BODY, "choices": [{"message": {"content": ""}}]}
    with pytest.raises(EmptyCompletion):
        make_client(lambda request: httpx.Response(200, json=body)).chat("hi")


def test_images_are_sent_in_openai_shape():
    seen = {}

    def capture(request):
        seen.update(jsonlib.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    make_client(capture).chat("describe", ["data:image/png;base64,AAAA"])
    assert seen["messages"][-1]["content"][1]["image_url"]["url"].startswith("data:image/png")


def test_the_factory_builds_a_local_client_from_a_slot():
    config = SlotConfig("vlm.studio", "llamacpp", "step-local", {})
    assert isinstance(build_client(config), LlamaCppClient)


def test_an_answer_that_is_all_thinking_says_so(monkeypatch):
    """Measured: Step3-VL-10B spent 200 tokens thinking and wrote
    nothing. A blank answer is useless; "raise max_tokens" is actionable."""
    import httpx

    from studio.core.errors import EmptyCompletion
    from studio.providers.llamacpp import LlamaCppClient

    def reply(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "", "reasoning_content": "x" * 2453}}],
                "usage": {"completion_tokens": 200},
            },
        )

    client = LlamaCppClient("step3-vl-10b", client=httpx.Client(transport=httpx.MockTransport(reply)))
    with pytest.raises(EmptyCompletion) as caught:
        client.chat("hello")
    assert "hidden reasoning" in str(caught.value)
    assert "max_tokens" in str(caught.value)


@pytest.mark.parametrize('base,trust', [
    ('http://127.0.0.1:7100', False), ('http://localhost:7100', False),
    ('http://[::1]:7100', False), ('http://127.0.0.2:7100', False),
    ('https://inference.example.test', True),
])
def test_loopback_inference_ignores_desktop_proxy_variables(monkeypatch, base, trust):
    # A remote endpoint is the control: it still uses the configured environment.
    calls = []
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: calls.append(kwargs) or object())
    LlamaCppClient('local', {'base_url': base})
    assert calls[0]['trust_env'] is trust


def test_assistant_prefill_is_opt_in_and_only_its_exact_prefix_is_removed():
    prefix = '<think>\n</think>\n'
    seen = []
    def reply(request):
        seen.append(jsonlib.loads(request.content))
        return httpx.Response(200, json={**OK_BODY, 'choices':[{'message':{'content':prefix+'{"objects":[]}'}}]})
    result = make_client(reply, {'assistant_prefill':prefix}).chat('locate', ['data:image/png;base64,AAAA'])
    assert seen[-1]['messages'][-1] == {'role':'assistant','content':prefix}
    assert seen[-1]['messages'][-2]['content'][1]['type'] == 'image_url'
    assert result.text == '{"objects":[]}'
    ordinary = make_client(reply).chat('hi')
    assert seen[-1]['messages'][-1]['role'] == 'user'
    assert ordinary.text.startswith(prefix)


def test_prefill_alone_is_not_a_successful_completion():
    prefix = '<think>\n</think>\n'
    body = {**OK_BODY, 'choices':[{'message':{'content':prefix}}]}
    with pytest.raises(EmptyCompletion):
        make_client(lambda _:httpx.Response(200,json=body), {'assistant_prefill':prefix}).chat('locate')


def test_a_slot_caps_what_a_caller_may_ask_for():
    """The rule judges ask for 12000 tokens, written for Step; Qwen's window is 16384 with the picture in it."""
    seen = {}

    def capture(request):
        seen["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json=OK_BODY)

    make_client(capture, {"most_tokens": 4000}).chat("judge this", max_tokens=12000)
    assert seen["body"]["max_tokens"] == 4000
    make_client(capture, {"most_tokens": 4000}).chat("write this", max_tokens=900)
    assert seen["body"]["max_tokens"] == 900


def test_a_server_that_has_answered_before_is_waited_for_and_one_that_never_has_is_not():
    """Qwen steps aside while a Spark clip holds the memory; the clip's screen waits for it to load again."""
    health = []

    def server(request):
        if request.url.path == "/health":
            health.append(request)
            return httpx.Response(200 if len(health) >= 3 else 503)
        return httpx.Response(200, json=OK_BODY)

    client = make_client(server)
    assert not client.wait_ready(30) and len(health) == 1, "a server never seen answering is asked once"
    client.chat("hi")
    assert client.wait_ready(5, pause=0.01) and len(health) == 3, "one seen before is waited for until it is back"
