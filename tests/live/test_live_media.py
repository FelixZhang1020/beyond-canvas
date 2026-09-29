"""Opt-in tests that spend real money on the media keys.

    uv run pytest -m live -k voice -v
    uv run pytest -m live -k replicate -v

This is the answer to "did the key I just bought actually work". Everything
else about these providers is covered offline against a mock transport; what
no mock can tell you is whether the value in .env is accepted, whether the
model IDs written into the profile still exist, and whether the field names
read out of each published schema are the ones the model actually wants. Those
three are what this file buys.

Each test skips rather than fails when its key is absent, so buying one key
does not make the other one's test look broken.
"""

import os

import httpx
import pytest

from studio.core.env import load_dotenv
from studio.providers import build_media_slot, key_for
from studio.core.slots import load_profile, resolve

pytestmark = pytest.mark.live

SAFETY_MODEL = "google-deepmind/shieldgemma-2-4b-it"


def key_or_skip(name: str) -> str:
    load_dotenv()
    value = os.environ.get(name, "")
    if not value:
        pytest.skip(f"{name} is not set in .env, so there is nothing to prove here")
    return value


def test_the_voice_slot_speaks_chinese_kindly():
    """One real call, in the language and the tone the product actually needs.

    This proves four things a mock cannot: the key is accepted, the model ID
    still resolves, the field names read out of the published schema are the
    ones the model wants, and something audible comes back rather than an
    argument error. The line is Chinese on purpose — an English smoke test would
    pass on a voice nobody in this product will ever hear.

    It follows whichever provider the profile gives `tts.studio`, so moving the
    voice between SiliconFlow and Replicate does not need this file edited.
    """
    key_or_skip(key_for(resolve("tts.studio", load_profile("cloud")).provider))
    voice = build_media_slot(resolve("tts.studio", load_profile("cloud")))
    result = voice.speak("你今天画的这只小狗，颜色真好看。")

    assert result.urls or result.content, "neither a link nor a file came back"
    assert result.latency_s > 0


def test_the_replicate_token_opens_the_safety_model():
    """Proves the token and the model name without running a prediction.

    Reading a model costs nothing and answers both questions that matter before
    ShieldGemma is wired in: whether Replicate accepts this token, and whether
    the name written into .env.example and cloud.yaml's closing note still
    resolves. Running the model itself is deliberately not done here — its
    input schema could not be verified when this was written, and a live test
    that guesses at field names fails for the wrong reason.
    """
    token = key_or_skip("REPLICATE_API_KEY")
    response = httpx.get(
        f"https://api.replicate.com/v1/models/{SAFETY_MODEL}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )

    assert response.status_code == 200, f"replicate said {response.status_code}: {response.text[:200]}"
    assert response.json().get("name") == SAFETY_MODEL.split("/")[1]
