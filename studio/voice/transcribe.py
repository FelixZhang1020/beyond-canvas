"""Hear the child, and write down what was heard.

Section 5a wants the child's own words in the loop, and it wants them as text
first: *"either way it is transcribed to text first so the teacher can see what
was heard and the transcript is auditable."* That sentence decides the whole
shape of this file. The machine does not act on audio. It turns audio into a
sentence, shows the sentence to the teacher, and the teacher decides whether
that is what the child said.

A recording is held in memory long enough to be converted and transcribed, and then it is gone, with one
exception: the first spoken answer about a drawing, at most ten seconds, is kept for the storybook to read
that page in the child's voice (studio/voice/child_voice.py). A recording of a child is the most sensitive
thing the studio holds, so nothing else is.

Who hears is decided by the deployment, and the answer is now a
company every time: StepFun First, the studio's only deployment, buys it from
StepFun's `stepaudio-2.5-asr`. Local First used to keep a child's voice
on hardware the operator owns, Whisper on the 4090 at 7290; it was archived by
operator decision with that consequence stated (studio/profiles/archive/).

That reverses what this file used to promise. It said a child's
recorded voice would never go to another computer and called it a selling point
rather than a limitation; the operator chose otherwise, having been shown the
sentence. It is written here rather than only in the profile because the old
wording is quotable and someone will quote it. studio/providers/stepfun_asr.py
carries the rest.

The Whisper clients below stay for the development profiles, which declare no
`speech.in` and hear on this Mac:

    sh studio/ops/localmodels.sh speech                 # the Mac, port 7130 — model deleted
    bash deploy/gpu-media/extra/start-hearing.sh    # the 4090, port 7290 — no deployment uses it now
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.conversation.words import say

PROMPT_ZH_SIMPLIFIED = say("zh", "transcribe_prompt")

# The fallback only. Every selectable deployment now declares `speech.in` and
# hearing_for() below reads it; this is what a profile that declares none gets,
# and the Mac is the right default for that because it is the machine the studio
# is running on.
DEFAULT_BASE_URL = "http://127.0.0.1:7130"
# whisper.cpp writes this when it hears nothing but silence or noise. It is not
# an error and must not be shown to anyone as a transcript.
NOISE = ("[BLANK_AUDIO]", "[ Silence ]", "(silence)", "[MUSIC]", "[SOUND]")
LANGUAGES = {"zh": "zh", "en": "en"}

# Whisper writes Chinese in traditional characters unless its initial prompt is
# in simplified, and this product is simplified throughout: the rubric's Chinese
# lexicons, the page's strings, and the bigram overlap rule 13 counts are all
# simplified. A traditional transcript would quietly fail rule 13 by matching
# nothing the model wrote back. Measured: the same recording came
# back traditional with no prompt and simplified with this one.
PROMPTS = {"zh": PROMPT_ZH_SIMPLIFIED}


@dataclass(frozen=True)
class Heard:
    """What the machine thinks it heard, for a person to confirm."""

    text: str
    language: str
    # Set by the class for a recording it holds until the answer is sent (studio/voice/child_voice.py).
    sample: str | None = None

    @property
    def is_something(self) -> bool:
        return bool(self.text.strip())


class WhisperCppClient:
    """A whisper-server over its inference route, wherever the deployment puts it.

    This used to be pinned to the classroom Mac and said a child's voice
    would never go to another computer, calling that a selling point rather than
    a limitation. Hearing is now a slot like any other. This client still serves
    the two deployments that hear on hardware the operator owns; the third buys
    it, through StepFunEars rather than this class.

    So the sentence above is no longer true of the product as a whole, only of
    the options that use this client. Do not restore the old wording here without
    checking studio/profiles/stepfun.yaml.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # Recordings stay on the local worker even when the classroom process
        # inherits a system or dotenv HTTP proxy for its hosted models.
        self._client = client or httpx.Client(timeout=180.0, trust_env=False)

    def hear(self, audio: bytes, language: str = "zh", filename: str = "said.webm") -> Heard:
        """Transcribe one recording. Raises rather than guessing at silence."""
        files = {"file": (filename, audio, "application/octet-stream")}
        data = {
            "language": LANGUAGES.get(language, "auto"),
            "response_format": "json",
            "temperature": "0",
        }
        if language in PROMPTS:
            data["prompt"] = PROMPTS[language]
        try:
            response = self._client.post(f"{self.base_url}/inference", files=files, data=data)
        except httpx.RequestError as error:
            raise ModelUnavailable(
                f"whisper-server at {self.base_url} did not answer: {error}"
            ) from error
        if response.status_code >= 500:
            raise ModelUnavailable(f"whisper-server {response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise ModelRefused(f"whisper-server {response.status_code}: {response.text[:200]}")
        return Heard(clean(response.json().get("text", "")), language)


def clean(text: str) -> str:
    """Strip whisper's own annotations, so noise reads as nothing heard.

    A transcript of "[BLANK_AUDIO]" handed to the feedback skill would become a
    reply about a child who said nothing at all, which is worse than admitting
    the room was too loud.
    """
    cleaned = text.strip()
    for marker in NOISE:
        cleaned = cleaned.replace(marker, " ")
    return " ".join(cleaned.split())


def hearing_for(profile) -> WhisperCppClient:
    """The transcription worker this deployment listens on.

    Per-deployment, so the picker and the checks can show where
    a child's voice actually goes. A profile that declares no `speech.in` — the
    development profiles, or a caller passing a path — gets the Mac, which is
    where this ran before the slot existed.
    """
    from studio.core.slots import load_profile

    try:
        config = load_profile(profile).get("speech.in")
    except (OSError, ValueError, KeyError, TypeError):
        return WhisperCppClient()
    if config is None:
        return WhisperCppClient()
    if config.provider == "stepfun":
        # The one provider that is a vendor rather than a machine you own. Kept
        # behind a local import so this module stays importable by the provider,
        # which reads Heard and clean() from here.
        from studio.providers.stepfun_asr import StepFunEars, API_URL

        # The profile's address, not the module default: StepFun First hears
        # through the subscription endpoint, and this line used to
        # drop any base_url the slot named, so hearing would have kept
        # billing against the account balance while everything else moved.
        return StepFunEars(
            config.model,
            base_url=config.options.get("base_url") or API_URL,
            hotwords=config.options.get("hotwords"),
        )
    base_url = config.options.get("base_url")
    return WhisperCppClient(base_url) if base_url else WhisperCppClient()
