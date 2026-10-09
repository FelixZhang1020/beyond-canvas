"""Speaking, and the event stream that carries it to the page.

Split out of `studio/serve.py` for room, not for redesign: the file had passed the 500-line limit.

`_speech_events` is the long one, and it is long for a reason the comments in it
record -- a browser gives up on a silent connection at about 7.8 seconds, so the
stream sends keep-alives from its own follow loop rather than from a per-route
thread. That rule was learnt from a real defect, so read those comments before shortening anything here.
"""

from __future__ import annotations

import json
import queue
import threading

from studio.core.errors import ModelError
from studio.providers.stepfun_voice import VoiceServiceError


class SpeechRoutes:
    """Speech synthesis and its event stream, mixed into `StudioHandler`."""

    def _stop_speech(self, session_id):
        self.server.classroom._session(session_id).speech.stop()
        self._bytes(204, b"", "application/json")

    def _speech(self, session_id):
        payload = self._json_body()
        try:
            events = self.server.classroom.speak(session_id, payload.get("text"), payload.get("voice"))
        except VoiceServiceError as error:
            print(f"session speech unavailable before streaming: {error}", flush=True)
            self._json(503, {"error": "Classroom speech is unavailable."})
            return
        self._speech_events(events)

    def _speech_events(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        # VoxCPM2 answers in one block after its own 15-16 s cold load
        # (docs/measured/), and a busy-worker retry can add more silent seconds
        # on top of that. A generator can only be produced from, not polled with
        # a timeout, so the slow producer runs on its own thread and this one
        # writes a heartbeat line whenever it has been quiet too long — measured:
        # Firefox's own fetch() dropped that same silent connection
        # after ~7.8 s with "Error in input stream" where Chromium waited it out,
        # so nothing arriving from a browser's own retry logic on this route.
        pending: queue.Queue = queue.Queue(maxsize=1)
        STOP = object()

        def produce():
            try:
                for event in events:
                    pending.put(("event", event), timeout=10)
                pending.put((STOP, None), timeout=10)
            except VoiceServiceError as error:
                try:
                    pending.put(("voice_error", error), timeout=10)
                except queue.Full:
                    pass  # the consumer already gave up; nothing left to tell.
            except queue.Full:
                pass  # the consumer disconnected mid-generation; stop feeding a queue nobody drains.
            except Exception as error:  # noqa: BLE001 - any other failure also ends the reading
                # This thread used to die on it, and the page waited on keep-alives for ever. Only the kind of
                # failure is said: its message could carry a line of the story.
                try:
                    pending.put(("voice_error", type(error).__name__), timeout=10)
                except queue.Full:
                    pass

        threading.Thread(target=produce, daemon=True).start()
        try:
            while True:
                try:
                    kind, payload = pending.get(timeout=2)
                except queue.Empty:
                    self.wfile.write(b'{"type":"heartbeat"}\n')
                    self.wfile.flush()
                    continue
                if kind is STOP:
                    break
                if kind == "voice_error":
                    print(f"speech interrupted mid-stream: {payload}", flush=True)
                    self.wfile.write(b'{"type":"error","error":"Speech interrupted. Please retry."}\n')
                    self.wfile.flush()
                    break
                self.wfile.write((json.dumps(payload) + "\n").encode())
                self.wfile.flush()
        except OSError:
            pass  # the browser left; see _events for which errors that is
        finally:
            # produce() drives every next() on its own thread and reaches this
            # generator's own cleanup by finishing its for-loop, normally or via
            # VoiceServiceError; closing it again from here, from a different
            # thread, is a race a slow retry can win ("generator already
            # executing") for no benefit — the producer already owns that.
            self.close_connection = True
