"""Hearing bought from StepFun, for the deployment that buys everything Step sells.

This is the one place a child's recorded voice leaves the operator's own
machines. At first nothing here did: `studio/voice/transcribe.py` said the
recording would never go to another computer and called that a selling point.
The operator chose this, having been shown that sentence and what
buying transcription would cost. It is now how the studio always
hears: StepFun First is the only deployment, and Local First — the one that kept
recordings on the 4090 — was archived with this consequence stated.
Said plainly because the old promise is quotable and someone will quote it.

Request shape read from platform.stepfun.com/docs/zh/api-reference/audio/
transcriptions, not guessed: multipart to /v1/audio/transcriptions
with `model`, `response_format` and `file`, and an optional `hotwords` JSON
array. There is NO language field — unlike whisper.cpp, which stands beside this
in the same slot, StepFun decides the language itself. `hear()` still takes one
so the two are interchangeable, and ignores it rather than pretending.
"""

from __future__ import annotations

import json
import os

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.voice.transcribe import Heard, clean

API_URL = "https://api.stepfun.com/v1"


class StepFunEars:
    """Transcription over StepFun's audio API, shaped like WhisperCppClient.

    Exposes `base_url` because the status board and the deployment checks read
    it to say where hearing is answering from.
    """

    def __init__(
        self,
        model: str = "stepaudio-2.5-asr",
        base_url: str = API_URL,
        api_key: str | None = None,
        hotwords: list[str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.hotwords = list(hotwords or [])
        self._api_key = api_key if api_key is not None else os.environ.get("STEPFUN_API_KEY", "")
        # trust_env=False for the same reason the local client sets it: a proxy
        # inherited for the hosted vision models must not silently carry audio.
        self._client = client or httpx.Client(timeout=180.0, trust_env=False)

    def hear(self, audio: bytes, language: str = "zh", filename: str = "said.wav") -> Heard:
        """Transcribe one recording. `language` is accepted and unused; see the module note."""
        if not self._api_key:
            raise ModelUnavailable("STEPFUN_API_KEY is not set, so bought transcription cannot run")
        files = {"file": (filename, audio, "application/octet-stream")}
        data = {"model": self.model, "response_format": "json"}
        if self.hotwords:
            data["hotwords"] = json.dumps(self.hotwords, ensure_ascii=False)
        try:
            response = self._client.post(
                f"{self.base_url}/audio/transcriptions",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.RequestError as error:
            raise ModelUnavailable(f"StepFun transcription did not answer: {error}") from error
        if response.status_code >= 500:
            raise ModelUnavailable(f"StepFun transcription {response.status_code}")
        if response.status_code >= 400:
            # Never echo the body: it can quote the audio's own transcript back.
            raise ModelRefused(f"StepFun transcription refused the request ({response.status_code} {_why(response)})")
        try:
            text = response.json().get("text", "")
        except ValueError:
            raise ModelUnavailable("StepFun transcription returned no JSON") from None
        return Heard(clean(text), language)


# StepFun's own messages that are safe to repeat: fixed text, never words heard.
# "no speech found" is what a silent recording gets back (measured).
_KNOWN_MESSAGES = {"no speech found"}


def _why(response: httpx.Response) -> str:
    """StepFun's error code for a refusal, with its message only when it is a known fixed one."""
    try:
        error = response.json()["error"]
        message = error.get("message")
        return str(error["type"])[:60] + (f": {message}" if message in _KNOWN_MESSAGES else "")
    except (ValueError, KeyError, TypeError, AttributeError):
        return "no reason given"
