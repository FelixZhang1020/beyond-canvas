"""Opt-in tests that send real audio to the listening model on this machine.

    uv run pytest -m live -k voice -v

The offline tests in tests/voice/test_transcribe.py cover the client: that the
simplified prompt is sent, that whisper's own annotations never reach a skill,
that silence is nothing heard. What no mock can tell you is whether a real
recording comes back as the right words in the right script — and that is the
one failure that hides, because a correct sentence in traditional characters
looks right to everyone except rule 13.

The audio is made on the spot with the system voice, so no child's recording is
stored anywhere. That is also the limit of these tests: a synthetic adult voice
in a silent room is not a five-year-old in a room with twenty other children.
This proves the pipeline and the script. Only real recordings prove accuracy, and the project keeps
none to measure with: the one answer kept per drawing is for its storybook, not for tests.
"""

import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from studio.voice.transcribe import WhisperCppClient

pytestmark = pytest.mark.live

SPOKEN_ZH = "他们要去找他的妈妈，妈妈丢了很久了。路上特别热，所以太阳画得很大。"
SPOKEN_EN = "they are looking for his mum, she got lost a long time ago"

# Characters that only exist in the traditional script, drawn from the words a
# child in an art class actually says. If one of these comes back, the initial
# prompt did not take.
TRADITIONAL_ONLY = "們媽丟熱陽畫這裡沒過來說話個東長時間點顏色"


def _say(text: str, voice: str, into: Path) -> bytes:
    """One line of speech as 16 kHz mono WAV, the format every speech model reads."""
    if not shutil.which("say") or not shutil.which("afconvert"):
        pytest.skip("no system speech tools on this machine")
    line, aiff, wav = into / "line.txt", into / "said.aiff", into / "said.wav"
    line.write_text(text, encoding="utf-8")
    # -f, not an argument: a Chinese sentence on the command line is at the
    # mercy of the shell's locale, and comes out as silence when it loses.
    if subprocess.run(["say", "-v", voice, "-f", str(line), "-o", str(aiff)]).returncode:
        pytest.skip(f"the {voice} voice is not installed")
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                    str(aiff), str(wav)], check=True)
    audio = wav.read_bytes()
    if len(audio) < 32000:  # under a second: the voice rendered nothing
        pytest.skip(f"the {voice} voice produced no audio")
    return audio


def _listening() -> WhisperCppClient:
    client = WhisperCppClient()
    try:
        httpx.get(f"{client.base_url}/", timeout=2)
    except httpx.RequestError:
        pytest.skip("nothing is listening on the speech port; sh studio/ops/localmodels.sh")
    return client


def _pairs(text: str) -> set[str]:
    """Rule 13 compares Chinese by character pairs; so does this."""
    han = "".join(ch for ch in text if "一" <= ch <= "鿿")
    return {han[i:i + 2] for i in range(len(han) - 1)}


def test_a_chinese_sentence_comes_back_in_simplified_characters(tmp_path):
    """The defect that would have been invisible.

    Measured: the same recording came back in traditional characters.
    Nobody would have called that a bug — the teacher reads a correct sentence,
    the skill receives a correct sentence — and rule 13 would quietly match
    nothing, so the reply would be refused for not having heard the child.
    """
    audio = _say(SPOKEN_ZH, "Tingting", tmp_path)
    heard = _listening().hear(audio, language="zh", filename="said.wav").text

    wrong_script = [ch for ch in heard if ch in TRADITIONAL_ONLY]
    assert not wrong_script, f"came back in traditional characters: {''.join(wrong_script)!r} in {heard!r}"

    kept = _pairs(SPOKEN_ZH) & _pairs(heard)
    assert len(kept) >= len(_pairs(SPOKEN_ZH)) * 0.8, (
        f"only {len(kept)} of {len(_pairs(SPOKEN_ZH))} character pairs survived: {heard!r}")


def test_the_prompt_is_what_keeps_the_script_right(tmp_path):
    """Held down so the prompt cannot be dropped as decoration.

    The same audio with no initial prompt, as measured: 14 of 26
    character pairs survive instead of 24. That gap is rule 13 failing silently.
    """
    audio = _say(SPOKEN_ZH, "Tingting", tmp_path)
    client = _listening()
    bare = httpx.post(
        f"{client.base_url}/inference",
        files={"file": ("said.wav", audio, "application/octet-stream")},
        data={"language": "zh", "response_format": "json", "temperature": "0"},
        timeout=180,
    ).json().get("text", "").strip()

    with_prompt = client.hear(audio, language="zh", filename="said.wav").text
    assert len(_pairs(SPOKEN_ZH) & _pairs(with_prompt)) > len(_pairs(SPOKEN_ZH) & _pairs(bare)), (
        "the prompt made no difference, so either it stopped being sent or the "
        f"model changed: with={with_prompt!r} without={bare!r}")


def test_english_comes_back_as_the_words_that_were_spoken(tmp_path):
    """Not "mum": the model writes "mom" for an American voice saying "mum",
    which is the same word heard correctly and spelled its own way. A test that
    fails on that is testing the model's dialect, not whether it heard."""
    audio = _say(SPOKEN_EN, "Samantha", tmp_path)
    heard = _listening().hear(audio, language="en", filename="said.wav").text.lower()
    for word in ("looking", "lost", "long time ago"):
        assert word in heard, f"{word!r} did not survive: {heard!r}"


def test_listening_is_not_the_slow_part(tmp_path):
    """Measured: 0.6 s for English, 0.2 s for Chinese, both faster
    than the page can animate. A child is standing there waiting."""
    audio = _say(SPOKEN_ZH, "Tingting", tmp_path)
    client = _listening()
    started = time.monotonic()
    client.hear(audio, language="zh", filename="said.wav")
    spent = time.monotonic() - started
    assert spent < 5.0, f"transcription took {spent:.1f}s for {len(audio) / 32000:.1f}s of audio"
