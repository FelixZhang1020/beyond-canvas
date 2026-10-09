import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.fal import FalClient

MODEL = "fal-ai/qwen-image-edit"
STATUS_URL = f"https://queue.fal.run/{MODEL}/requests/abc/status"
RESPONSE_URL = f"https://queue.fal.run/{MODEL}/requests/abc"

HANDLE = {
    "request_id": "abc",
    "status_url": STATUS_URL,
    "response_url": RESPONSE_URL,
    "queue_position": 0,
}
FINISHED = {"images": [{"url": "https://fal.media/files/page.png", "width": 1024}]}


def make_client(handler, options=None, sleeps=None):
    """A client whose HTTP and whose clock are both under the test's control."""
    client = FalClient(
        MODEL,
        options=options,
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client._sleep = sleeps.append if sleeps is not None else lambda seconds: None
    return client


def queue_handler(states):
    """Replays a submit, then one status per state, then the finished answer."""
    remaining = list(states)

    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json=HANDLE)
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"status": remaining.pop(0)})
        return httpx.Response(200, json=FINISHED)

    return handle


def test_a_finished_job_returns_its_urls_and_the_declared_price():
    client = make_client(queue_handler(["COMPLETED"]), options={"price_usd": 0.15})
    result = client.make({"prompt": "make it a storybook page"})
    assert result.urls == ["https://fal.media/files/page.png"]
    assert result.price_usd == pytest.approx(0.15)
    assert result.provider == "fal"
    assert result.model == MODEL
    assert result.payload == FINISHED
    assert result.latency_s >= 0


def test_a_price_the_profile_did_not_declare_is_zero_not_a_guess():
    client = make_client(queue_handler(["COMPLETED"]))
    assert client.make({"prompt": "x"}).price_usd == 0.0


def test_it_waits_through_the_queue_before_reading_the_answer():
    sleeps = []
    client = make_client(queue_handler(["IN_QUEUE", "IN_PROGRESS", "COMPLETED"]), sleeps=sleeps)
    assert client.make({"prompt": "x"}).urls == ["https://fal.media/files/page.png"]
    assert len(sleeps) == 2


def test_the_authorization_header_uses_fals_key_scheme_not_bearer():
    seen = {}

    def handle(request):
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=HANDLE) if request.method == "POST" else (
            httpx.Response(200, json={"status": "COMPLETED"})
            if request.url.path.endswith("/status")
            else httpx.Response(200, json=FINISHED)
        )

    make_client(handle).make({"prompt": "x"})
    assert seen["auth"] == "Key test-key"


def test_a_missing_key_says_where_to_get_one(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(ModelRefused) as caught:
        FalClient(MODEL)
    assert "FAL_KEY" in str(caught.value)
    assert "fal.ai" in str(caught.value)


def test_a_rejected_key_is_not_reported_as_a_model_fault():
    client = make_client(lambda request: httpx.Response(401, text="unauthorized"))
    with pytest.raises(ModelRefused) as caught:
        client.make({"prompt": "x"})
    assert "FAL_KEY" in str(caught.value)


def test_rate_limiting_is_retryable():
    client = make_client(lambda request: httpx.Response(429, text="slow down"))
    with pytest.raises(ModelUnavailable):
        client.make({"prompt": "x"})


def test_a_bad_request_is_not_retryable():
    client = make_client(lambda request: httpx.Response(400, text="bad input"))
    with pytest.raises(ModelRefused):
        client.make({"prompt": "x"})


def test_a_submit_with_no_queue_handle_is_refused_rather_than_polled():
    client = make_client(lambda request: httpx.Response(200, json={"request_id": "abc"}))
    with pytest.raises(ModelRefused) as caught:
        client.make({"prompt": "x"})
    assert "queue handle" in str(caught.value)


def test_running_out_of_patience_says_the_job_is_still_there():
    """A timeout here is not a lost job, and the message has to say so.

    fal holds the result at its own URL after the client stops waiting. A
    message that only said "timed out" would send someone to pay for the work
    a second time.
    """
    client = make_client(queue_handler(["IN_PROGRESS"] * 5), options={"timeout_s": 0})
    with pytest.raises(ModelUnavailable) as caught:
        client.make({"prompt": "x"})
    assert RESPONSE_URL in str(caught.value)
    assert "timeout_s" in str(caught.value)
