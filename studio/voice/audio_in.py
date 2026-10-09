"""A recording as the browser made it, turned into the one format every hearing service reads.

The page used to do this itself: it unpacked the browser's recording into 16 kHz WAV
before sending, about eight times the size of what the browser had made (32 KB a second against
roughly 4). Getting that file to the Spark was most of the wait between Stop and the words;
StepFun itself answers in under half a second on the node
(docs/measured/hearing-on-the-node.md). Now the browser sends its own small recording
and it is unpacked here, in memory: ffmpeg reads it from a pipe and writes plain samples to a
pipe, so the recording is never written to disk on the way. What is kept is only
the first answer said about a drawing, once it is sent, for the storybook's voice (studio/voice/child_voice.py).

Only a recording that plainly is WebM or Ogg (the two a browser records into and ffmpeg reads
from a pipe) is converted. Anything else, a WAV above all, goes on exactly as it came, as every
recording did before.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import time

RATE = 16000
# The first bytes of the two containers a browser records into: WebM (EBML) and Ogg.
COMPRESSED = (b"\x1a\x45\xdf\xa3", b"OggS")


class UnreadableAudio(ValueError):
    """The studio could not unpack a recording, which is its own failing, not the child's.

    A ValueError with a code, so the route answers 400 with `unreadable_audio` (studio/serve.py)
    rather than the 503 that reads as "nothing was heard": the page, which still holds the
    recording, unpacks it itself and sends it once more, as every recording went before.
    """

    code = "unreadable_audio"


def as_wav(audio: bytes) -> bytes:
    """16 kHz mono WAV for a browser's WebM or Ogg recording; anything else unchanged."""
    if not audio.startswith(COMPRESSED):
        return audio
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
               "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"]
    try:
        done = subprocess.run(command, input=audio, capture_output=True, timeout=30)
    except FileNotFoundError:
        raise UnreadableAudio("ffmpeg is not installed here, so a compressed recording cannot be read") from None
    except subprocess.TimeoutExpired:
        raise UnreadableAudio("reading the recording took more than 30 s") from None
    if done.returncode != 0 or not done.stdout:
        raise UnreadableAudio("the recording could not be read")
    return wav_header(len(done.stdout)) + done.stdout


def as_mp3(wav: bytes, bitrate: str = "64k") -> bytes:
    """A WAV as the MP3 the page plays, in memory like as_wav: a storybook page read in a child's voice
    (studio/voice/child_voice.py). 64 kbit/s, 8 KB for each second, which the classroom's link keeps ahead of.
    Any sound ffmpeg reads will do: StepFun's own 128 kbit/s MP3 is made smaller with it (stepfun_voice.smaller)."""
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
               "-ac", "1", "-codec:a", "libmp3lame", "-b:a", bitrate, "-f", "mp3", "pipe:1"]
    try:
        done = subprocess.run(command, input=wav, capture_output=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise UnreadableAudio("the page's voice could not be made into MP3") from None
    if done.returncode != 0 or not done.stdout:
        raise UnreadableAudio("the page's voice could not be made into MP3")
    return done.stdout


def wav_header(size: int) -> bytes:
    """The 44 bytes in front of `size` bytes of 16-bit mono samples at RATE."""
    return (b"RIFF" + struct.pack("<I", 36 + size) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16)
            + b"data" + struct.pack("<I", size))


def hear(ears, audio: bytes, language: str):
    """What was heard in a recording; `listen` for the unpacked recording as well."""
    return listen(ears, audio, language)[1]


def listen(ears, audio: bytes, language: str):
    """The recording unpacked, and what was heard in it; logs how long each took: sizes and seconds, never words.

    The log line exists because once a teacher waited for a recording with nothing to
    say where the time went, and the studio's log showed only that the answer was 200.
    """
    started = time.monotonic()
    try:
        wav = as_wav(audio)
    except UnreadableAudio as error:
        say(f"hearing: {len(audio) // 1024} KB compressed could not be unpacked ({error}); the page sends it again as WAV")
        raise
    unpacked = time.monotonic()
    heard = ears.hear(wav, language)
    done = time.monotonic()
    kind = "compressed" if wav is not audio else "as sent"
    say(f"hearing: {len(audio) // 1024} KB {kind}, unpacked in {unpacked - started:.2f} s, heard in {done - unpacked:.2f} s")
    return wav, heard


def say(line: str) -> None:
    """One dated line in the studio's log, which never costs the class anything if nobody reads it."""
    try:
        print(f"{time.strftime('%d/%b/%Y %H:%M:%S')} {line}", file=sys.stderr, flush=True)
    except OSError:
        pass  # Nobody is reading the log (studio/serve.py's log_message says why this matters).
