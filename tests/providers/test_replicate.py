import json as jsonlib

import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.replicate import ReplicateClient

MODEL = "google-deepmind/shieldgemma-2-4b-it"
GET_URL = "https://api.replicate.com/v1/predictions/xyz"

RUNNING = {"id": "xyz", "status": "processing", "urls": {"get": GET_URL}}
DONE = {
    "id": "xyz",
    "status": "succeeded",
    "output": ["https://replicate.delivery/out/mesh.glb"],
    "metrics": {"predict_time": 3.2},
    "urls": {"get": GET_URL},
}


def make_client(handler, options=None, sleeps=None):
    # Pinned by default so a test stages prediction responses only. The version
    # lookup has its own tests below.
    options = {"version": "v1", **(options or {})}
    client = ReplicateClient(
        MODEL,
        options=options,
        api_key="test-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client._sleep = sleeps.append if sleeps is not None else lambda seconds: None
    return client


def replaying(*payloads):
    """Answers each call with the next payload, so a test can stage a wait."""
    remaining = list(payloads)

    def handle(request):
        return httpx.Response(200, json=remaining.pop(0))

    return handle


def test_a_prediction_that_answers_inline_needs_no_polling():
    sleeps = []
    client = make_client(replaying(DONE), sleeps=sleeps)
    result = client.make({"image": "data:image/png;base64,xx"})
    assert result.urls == ["https://replicate.delivery/out/mesh.glb"]
    assert result.provider == "replicate"
    assert result.payload["metrics"]["predict_time"] == 3.2
    assert sleeps == []


def test_a_prediction_still_running_is_polled_until_it_finishes():
    sleeps = []
    client = make_client(replaying(RUNNING, RUNNING, DONE), sleeps=sleeps)
    assert client.make({"image": "x"}).urls == ["https://replicate.delivery/out/mesh.glb"]
    assert len(sleeps) == 2


def test_a_failed_prediction_is_an_error_and_not_an_empty_answer():
    """Replicate returns HTTP 200 for a prediction that failed.

    A client that only read the status code would hand its caller an empty
    output and call the call a success, which is the failure this asserts is
    impossible.
    """
    failed = {"id": "xyz", "status": "failed", "error": "image too large", "output": None}
    client = make_client(replaying(failed))
    with pytest.raises(ModelRefused) as caught:
        client.make({"image": "x"})
    assert "image too large" in str(caught.value)


def test_a_verdict_with_no_files_keeps_the_answer_and_reports_no_urls():
    """ShieldGemma returns a judgement, not a file. Both must survive."""
    verdict = {"id": "xyz", "status": "succeeded", "output": {"safe": True, "score": 0.02}}
    client = make_client(replaying(verdict))
    result = client.make({"image": "x"})
    assert result.urls == []
    assert result.payload["output"] == {"safe": True, "score": 0.02}


def test_the_request_asks_replicate_to_wait_and_authenticates_as_a_bearer():
    seen = {}

    def handle(request):
        seen["auth"] = request.headers.get("Authorization")
        seen["prefer"] = request.headers.get("Prefer")
        seen["url"] = str(request.url)
        seen["body"] = jsonlib.loads(request.content)
        return httpx.Response(200, json=DONE)

    make_client(handle).make({"image": "x"})
    assert seen["auth"] == "Bearer test-token"
    assert seen["prefer"] == "wait=60"
    # The version route, NOT /v1/models/{model}/predictions. That endpoint is
    # for official models only and 404s for everything else — which is exactly
    # how the first live call against CosyVoice 2 failed.
    assert seen["url"] == "https://api.replicate.com/v1/predictions"
    assert seen["body"] == {"version": "v1", "input": {"image": "x"}}


def test_an_unpinned_model_has_its_latest_version_looked_up_once():
    """Two calls, one lookup. A model must not change voice mid-class."""
    asked = []

    def handle(request):
        asked.append(str(request.url))
        if request.url.path.endswith(f"/models/{MODEL}"):
            return httpx.Response(200, json={"latest_version": {"id": "abc123"}})
        return httpx.Response(200, json=DONE)

    client = ReplicateClient(
        MODEL, options={}, api_key="t",
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    client.make({"image": "x"})
    client.make({"image": "y"})
    assert sum(1 for url in asked if url.endswith(f"/models/{MODEL}")) == 1
    assert asked[-1] == "https://api.replicate.com/v1/predictions"


def test_a_model_that_publishes_no_version_falls_back_to_the_official_route():
    def handle(request):
        if request.url.path.endswith(f"/models/{MODEL}"):
            return httpx.Response(200, json={"latest_version": None})
        return httpx.Response(200, json=DONE)

    client = ReplicateClient(
        MODEL, options={}, api_key="t",
        client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    assert client.make({"image": "x"}).urls == ["https://replicate.delivery/out/mesh.glb"]


def test_a_missing_token_says_where_to_get_one(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_KEY", raising=False)
    with pytest.raises(ModelRefused) as caught:
        ReplicateClient(MODEL)
    assert "REPLICATE_API_KEY" in str(caught.value)
    assert "replicate.com" in str(caught.value)


def test_a_rejected_token_is_not_reported_as_a_model_fault():
    client = make_client(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(ModelRefused) as caught:
        client.make({"image": "x"})
    assert "REPLICATE_API_KEY" in str(caught.value)


def test_rate_limiting_is_retryable():
    client = make_client(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(ModelUnavailable):
        client.make({"image": "x"})


def test_a_prediction_with_nowhere_to_read_it_is_refused():
    orphan = {"id": "xyz", "status": "processing", "urls": {}}
    client = make_client(replaying(orphan))
    with pytest.raises(ModelRefused) as caught:
        client.make({"image": "x"})
    assert "nowhere to read it" in str(caught.value)


def test_running_out_of_patience_names_the_option_that_extends_it():
    client = make_client(replaying(RUNNING), options={"timeout_s": 0})
    with pytest.raises(ModelUnavailable) as caught:
        client.make({"image": "x"})
    assert "timeout_s" in str(caught.value)


def test_an_empty_account_is_told_apart_from_a_bad_key():
    """402 and 401 are different problems with different fixes.

    An operator who reads "rejected your key" when the real answer is "add
    credit" will go and regenerate a key that was never wrong.
    """
    client = make_client(lambda request: httpx.Response(402, text="Insufficient credit"))
    with pytest.raises(ModelRefused) as caught:
        client.make({"image": "x"})
    assert "credit" in str(caught.value).lower()
    assert "REPLICATE_API_KEY" not in str(caught.value)


def test_official_route_skips_version_lookup_and_posts_only_once():
    calls=[]
    def handle(request):
        calls.append(request)
        assert request.method == 'POST'
        assert request.url.path == '/v1/models/black-forest-labs/flux-2-klein-4b/predictions'
        assert jsonlib.loads(request.content) == {'input':{'prompt':'synthetic'}}
        return httpx.Response(200,json=DONE)
    client=ReplicateClient('black-forest-labs/flux-2-klein-4b',{'official':True},'test',
        httpx.Client(transport=httpx.MockTransport(handle)))
    assert client.make({'prompt':'synthetic'}).provider=='replicate'
    assert len(calls)==1


def test_official_cannot_claim_a_pinned_version():
    with pytest.raises(ModelRefused,match='pinned version'):
        ReplicateClient('owner/model',{'official':True,'version':'v1'},'test')
