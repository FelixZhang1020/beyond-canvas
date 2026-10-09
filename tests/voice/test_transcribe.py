"""Hearing the child: what is sent, what comes back, and what noise looks like.

The live behaviour is recorded in docs/measured/hearing-the-child.md.
These hold the parts that would fail silently: a Chinese transcript in the wrong
script, and whisper's own annotations reaching a skill as if a child had said
them.
"""

import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.voice.transcribe import PROMPT_ZH_SIMPLIFIED, WhisperCppClient, clean


def server(handler):
    return WhisperCppClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def answering(text, status=200):
    return lambda request: httpx.Response(status, json={"text": text})


def test_a_transcript_comes_back_as_text_for_a_person_to_read():
    heard = server(answering(" they are looking for his mum. "))
    result = heard.hear(b"audio", "en")
    assert result.text == "they are looking for his mum."
    assert result.is_something


def test_chinese_is_asked_for_in_simplified_characters():
    """Measured: the same recording came back in traditional
    characters without this prompt. The rubric's Chinese is all simplified, so a
    traditional transcript would fail rule 13 by matching nothing."""
    sent = {}

    def capture(request):
        sent["body"] = request.content.decode("utf-8", "replace")
        return httpx.Response(200, json={"text": "x"})

    server(capture).hear(b"audio", "zh")
    assert PROMPT_ZH_SIMPLIFIED in sent["body"]


def test_english_is_not_given_a_chinese_prompt():
    sent = {}

    def capture(request):
        sent["body"] = request.content.decode("utf-8", "replace")
        return httpx.Response(200, json={"text": "x"})

    server(capture).hear(b"audio", "en")
    assert PROMPT_ZH_SIMPLIFIED not in sent["body"]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("[BLANK_AUDIO]", ""),
        (" [ Silence ] ", ""),
        ("[MUSIC] the dragon flew away", "the dragon flew away"),
        ("  spaced   out  ", "spaced out"),
    ],
)
def test_whisper_own_annotations_never_reach_a_skill(raw, expected):
    """A reply built on "[BLANK_AUDIO]" would answer a child who said nothing."""
    assert clean(raw) == expected


def test_a_silent_room_is_nothing_heard_rather_than_something_said():
    result = server(answering("[BLANK_AUDIO]")).hear(b"audio", "en")
    assert not result.is_something


def test_an_unreachable_model_is_told_apart_from_a_refused_request():
    def dead(request):
        raise httpx.ConnectError("nothing listening")

    with pytest.raises(ModelUnavailable):
        server(dead).hear(b"audio", "en")
    with pytest.raises(ModelRefused):
        server(answering("", 400)).hear(b"audio", "en")
    with pytest.raises(ModelUnavailable):
        server(answering("", 503)).hear(b"audio", "en")


def test_the_launcher_does_not_pass_the_flag_that_breaks_every_upload():
    """`--convert` makes whisper-server shell out to ffmpeg on every request.

    Measured and recorded in docs/measured/hearing-the-child.md:
    that shell-out failed on every single upload, including a correctly formed
    16 kHz mono WAV, and took the whole listening path down while reading like a
    model fault. The page encodes that format itself, so the flag buys nothing.

    Found still in the launcher by sending real audio at the
    running server: every request came back 500 "FFmpeg conversion failed". The
    record said don't; the script still did.
    """
    from pathlib import Path

    launcher = Path("studio/ops/localmodels.sh").read_text(encoding="utf-8")
    offenders = [line.strip() for line in launcher.splitlines()
                 if "whisper-server" in line and "--convert" in line]
    assert not offenders, "the launcher still starts whisper with --convert:\n" + "\n".join(offenders)


def test_local_recordings_bypass_environment_proxies(monkeypatch):
    """An unreachable proxy is the control: local inference must still arrive."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers['Content-Length'])))
            data = b'{"text":"The bird sings."}'
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', ''); monkeypatch.setenv('no_proxy', '')
    try:
        from studio.voice.transcribe import WhisperCppClient
        import httpx
        endpoint = f'http://127.0.0.1:{server.server_address[1]}'
        with httpx.Client(timeout=2) as through_proxy:
            with pytest.raises(httpx.RequestError):
                through_proxy.post(endpoint + '/inference', content=b'control')
        assert received == []
        client = WhisperCppClient(endpoint)
        assert client.hear(b'test-recording', 'en').text == 'The bird sings.'
        assert b'test-recording' in received[0]
    finally:
        server.shutdown(); server.server_close()
