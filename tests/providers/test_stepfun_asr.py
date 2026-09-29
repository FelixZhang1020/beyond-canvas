"""Bought hearing says why it failed, and never repeats what it heard.

Every recording in one class came back 503 and the studio's log
held nothing but the number, so nobody could tell a silent microphone from a
dead service. The reason now travels in the error; the free text StepFun writes
beside it does not, because a refusal can quote the recording back.
"""

import httpx
import pytest

from studio.core.errors import ModelRefused
from studio.providers.stepfun_asr import StepFunEars


def ears(status, body):
    handler = lambda request: httpx.Response(status, json=body)
    return StepFunEars(api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_a_silent_recording_is_named_as_one():
    refusal = {"error": {"message": "no speech found", "type": "request_params_invalid"}}
    with pytest.raises(ModelRefused) as caught:
        ears(400, refusal).hear(b"RIFF....WAVE")
    assert "400 request_params_invalid: no speech found" in str(caught.value)


def test_a_refusal_never_carries_stepfun_own_words_about_the_recording():
    refusal = {"error": {"message": "could not parse 我的小熊去雪地", "type": "request_params_invalid"}}
    with pytest.raises(ModelRefused) as caught:
        ears(400, refusal).hear(b"RIFF....WAVE")
    assert "request_params_invalid" in str(caught.value)
    assert "小熊" not in str(caught.value)


def test_a_refusal_with_no_readable_reason_still_says_so():
    with pytest.raises(ModelRefused) as caught:
        ears(400, ["not", "an", "error"]).hear(b"RIFF....WAVE")
    assert "no reason given" in str(caught.value)
