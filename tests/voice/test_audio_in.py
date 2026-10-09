"""A browser's own recording is unpacked on the studio, in memory, and only when it plainly is one.

A teacher once waited for a recording to become words with nothing on screen, and the wait
was mostly the page sending an unpacked WAV eight times the size of what the browser recorded.
"""
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from studio.voice import audio_in
from studio.voice.transcribe import Heard

ROOT = Path(__file__).resolve().parents[2]
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32


def never_run(*args, **kwargs):
    raise AssertionError("nothing needed converting, so nothing may be run")


@pytest.mark.parametrize("audio", [b"RIFF....WAVEfmt ", b"pretend-audio", b""])
def test_a_wav_or_anything_unrecognised_goes_on_exactly_as_it_came(monkeypatch, audio):
    monkeypatch.setattr(audio_in.subprocess, "run", never_run)
    assert audio_in.as_wav(audio) is audio


def test_no_converter_here_says_so_instead_of_sending_what_no_service_can_read(monkeypatch):
    monkeypatch.setenv("PATH", "")
    with pytest.raises(audio_in.UnreadableAudio, match="ffmpeg"):
        audio_in.as_wav(WEBM)


def test_a_recording_the_converter_cannot_read_is_refused_not_passed_on(monkeypatch):
    monkeypatch.setattr(audio_in.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"bad"))
    with pytest.raises(audio_in.UnreadableAudio, match="could not be read"):
        audio_in.as_wav(WEBM)


def test_the_header_describes_16_khz_mono_16_bit_samples_of_the_given_length():
    header = audio_in.wav_header(32000)
    assert len(header) == 44 and header[:4] == b"RIFF" and header[8:16] == b"WAVEfmt "
    assert struct.unpack("<HHIIHH", header[20:36]) == (1, 1, 16000, 32000, 2, 16)
    assert struct.unpack("<I", header[40:44]) == (32000,)


def test_a_real_webm_recording_becomes_16_khz_mono_wav_of_the_same_length(monkeypatch):
    """The node's own ffmpeg (a container on the Spark), fed and read through pipes only."""
    monkeypatch.setenv("PATH", f"{ROOT / 'deploy/spark/bin'}:{os.environ['PATH']}")
    if not shutil.which("docker") and not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg here; the Spark runs this")
    made = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                           "-i", "sine=frequency=440:duration=3", "-c:a", "libopus", "-b:a", "24k", "-f", "webm", "pipe:1"],
                          capture_output=True)
    if made.returncode != 0:
        pytest.skip(f"ffmpeg did not run here: {made.stderr[:200]!r}")
    wav = audio_in.as_wav(made.stdout)
    assert wav[:4] == b"RIFF"
    seconds = (len(wav) - 44) / 32000
    assert 2.9 < seconds < 3.1, seconds
    # 24 kbps is what the page asks the browser for (27b-listen.js); at that rate the upload is
    # about a tenth of the WAV, which is the whole point of sending it.
    assert len(made.stdout) * 6 < len(wav), (len(made.stdout), len(wav))


def test_every_hearing_logs_its_size_and_times_but_never_the_words(capsys):
    class Ears:
        def hear(self, audio, language):
            return Heard("the bear goes fishing", language)

    heard = audio_in.hear(Ears(), b"RIFF" + b"\x00" * 3000, "zh")
    assert heard.text == "the bear goes fishing"
    line = capsys.readouterr().err
    assert "hearing: 2 KB as sent, unpacked in " in line and " s, heard in " in line
    assert "bear" not in line, "a child's words never go into the log"


def test_a_converter_that_hangs_is_given_up_on_and_the_page_is_told_it_was_the_studio(monkeypatch):
    def hangs(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 30)

    monkeypatch.setattr(audio_in.subprocess, "run", hangs)
    with pytest.raises(audio_in.UnreadableAudio) as caught:
        audio_in.as_wav(WEBM)
    assert caught.value.code == "unreadable_audio"


def test_an_unreadable_recording_is_logged_with_its_reason_and_never_reaches_the_ears(monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")

    class Ears:
        def hear(self, audio, language):
            raise AssertionError("nothing unreadable may be sent to be transcribed")

    with pytest.raises(audio_in.UnreadableAudio):
        audio_in.hear(Ears(), WEBM, "zh")
    assert "could not be unpacked (ffmpeg is not installed here" in capsys.readouterr().err


def test_the_converter_never_lets_docker_keep_what_it_prints():
    """What ffmpeg prints here is a child's voice; Docker's default logger would save it to disk."""
    wrapper = (ROOT / "deploy/spark/bin/ffmpeg").read_text()
    assert "--log-driver none" in wrapper

