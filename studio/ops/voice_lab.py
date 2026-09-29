"""Personal voice experiment: python -m studio.ops.voice_lab (localhost only).

This adult testing tool is separate from the classroom. VoxCPM2 locally speaks
assistant replies and clones the selected reference for article reading.
The legacy Step cloud route requires an explicit --speech-provider step-cloud.
No recording, transcript or output is written to disk by this server.
Idle sessions expire after 30 minutes.
"""

from __future__ import annotations

import argparse
import array
import base64
import io
import json
import math
import os
import secrets
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from studio.core.env import load_dotenv
from studio.providers.llamacpp import LlamaCppClient
from studio.providers.stepfun_voice import StepFunDialogueVoice, StepFunVoicePreview, VoiceServiceError, article_parts
from studio.core.slots import load_profile, resolve
from studio.voice.transcribe import WhisperCppClient

PORT = 7320
STATIC = Path(__file__).parents[1] / "voice_lab"
OPENING = "我们先随便聊聊。最近有没有一件让你觉得很舒服的小事？说说当时发生了什么。"
TTL = 30 * 60


def wav_bytes(samples: array.array, rate: int) -> bytes:
    pcm = array.array("h", samples)
    if sys.byteorder != "little":
        pcm.byteswap()
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return target.getvalue()


def read_wav(data: bytes) -> tuple[array.array, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            rate = wav.getframerate()
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or rate not in (16000, 24000, 44100, 48000):
                raise ValueError("请使用工具录音，或导入单声道 PCM WAV。")
            if not 1 <= wav.getnframes() / rate <= 45:
                raise ValueError("请录制 1–45 秒的声音，每次回答建议 8–15 秒。")
            pcm = array.array("h", wav.readframes(wav.getnframes()))
            if len(pcm) != wav.getnframes():
                raise ValueError("录音没有传输完整，请重录。")
            if sys.byteorder != "little":
                pcm.byteswap()
            return pcm, rate
    except (wave.Error, EOFError) as error:
        raise ValueError("无法读取录音，请重新录制。") from error


def resample(pcm: array.array, rate: int, target: int = 16000) -> bytes:
    if rate == target:
        return wav_bytes(pcm, rate)
    result = array.array("h")
    for index in range(int(len(pcm) * target / rate)):
        position = index * rate / target
        left = int(position)
        fraction = position - left
        result.append(round(pcm[left] * (1 - fraction) + pcm[min(left + 1, len(pcm) - 1)] * fraction))
    return wav_bytes(result, target)


def reference_clip(pcm: array.array, rate: int) -> tuple[bytes, dict]:
    """Energy screening, not speaker identification or a quality guarantee.

    Pick a continuous <= 9 s window; never splice speakers or separate answers.
    Re-transcribe the selected clip, so its text matches even a mid-sentence cut.
    """
    block = rate // 50
    frames = [pcm[i:i + block] for i in range(0, len(pcm), block)]
    energy = [math.sqrt(sum(s * s for s in frame) / len(frame)) / 32768 for frame in frames]
    active = [i for i, rms in enumerate(energy) if rms >= .012]
    if not active:
        return b"", {"usable": False, "reason": "声音太轻或没有说话，请靠近麦克风重新录一段。", "seconds": 0}
    start = max(0, active[0] - 8) * block
    end = min(len(pcm), (active[-1] + 9) * block)
    if end - start > 9 * rate:
        width = 450
        candidates = range(start // block, max(start // block + 1, end // block - width + 1), 10)
        first = max(candidates, key=lambda i: sum(min(v, .12) for v in energy[i:i + width]))
        start, end = first * block, min(len(pcm), (first + width) * block)
    clip = pcm[start:end]
    seconds = len(clip) / rate
    clipping = sum(abs(v) >= 32700 for v in clip) / max(1, len(clip))
    voice_seconds = sum(v >= .012 for v in energy[start // block:end // block]) / 50
    usable = seconds >= 5 and voice_seconds >= 3 and clipping < .02
    reason = "可以试用，请回听确认只有你一个人的声音。"
    if seconds < 5 or voice_seconds < 3:
        reason = "有效说话时间偏短，再自然地说两三句话。"
    elif clipping >= .02:
        reason = "录音有明显爆音，请离麦克风稍远一点重录。"
    return wav_bytes(clip, rate), {
        "usable": usable, "reason": reason, "seconds": round(seconds, 2),
        "voice_seconds": round(voice_seconds, 2), "clipping_pct": round(clipping * 100, 2),
        "score": voice_seconds * (1 - clipping),
    }


@dataclass
class Sample:
    audio: bytes
    transcript: str
    reference_text: str
    quality: dict
    confirmed: bool = False


@dataclass
class Session:
    touched: float = field(default_factory=time.monotonic)
    samples: dict[str, Sample] = field(default_factory=dict)
    history: list[dict] = field(default_factory=lambda: [{"role": "assistant", "text": OPENING}])
    lock: threading.RLock = field(default_factory=threading.RLock)
    cancelled: threading.Event = field(default_factory=threading.Event)
    job: dict | None = None
    output: bytes = b""
    speech: dict[tuple[int, str], bytes] = field(default_factory=dict)
    speech_lock: threading.Lock = field(default_factory=threading.Lock)


class VoiceLab:
    def __init__(self, ears=None, chat=None, voice=None, dialogue_voice=None):
        self.ears = ears or WhisperCppClient(client=httpx.Client(timeout=60, trust_env=False))
        if chat is None:
            config = resolve("vlm.voice_lab", load_profile("local"))
            if config.provider != "llamacpp":
                raise ValueError("vlm.voice_lab requires the local llamacpp provider")
            chat = LlamaCppClient(
                config.model, config.options, client=httpx.Client(timeout=65, trust_env=False),
            )
        self.chat = chat
        self.voice = voice
        self.dialogue_voice = dialogue_voice
        self.dialogue_settings = dialogue_voice if hasattr(dialogue_voice, "voices") else StepFunDialogueVoice
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()
        self.generating = threading.Lock()

    def begin(self) -> str:
        self.expire()
        with self.lock:
            if len(self.sessions) >= 8:
                raise ValueError("打开的测试太多，请先结束其他页面中的测试。")
            token = secrets.token_urlsafe(32)
            self.sessions[token] = Session()
        return token

    def get(self, token: str) -> Session:
        with self.lock:
            session = self.sessions.get(token)
            if session is None or session.cancelled.is_set():
                raise KeyError("本次测试已结束或过期，请重新开始。")
            if time.monotonic() - session.touched > TTL:
                self.sessions.pop(token)
                session.cancelled.set()
                session.samples.clear()
                session.history.clear()
                session.output = b""
                session.speech.clear()
                raise KeyError("本次测试已过期，请重新开始。")
            session.touched = time.monotonic()
            return session

    def end(self, token: str) -> None:
        with self.lock:
            session = self.sessions.pop(token, None)
        if session:
            session.cancelled.set()
            with session.lock:
                session.samples.clear()
                session.history.clear()
                session.output = b""
                session.speech.clear()

    def expire(self) -> None:
        with self.lock:
            expired = [token for token, s in self.sessions.items() if time.monotonic() - s.touched > TTL]
        for token in expired:
            self.end(token)

    def record(self, session: Session, audio: bytes) -> dict:
        with session.lock:
            if len(session.samples) >= 6:
                raise ValueError("本轮已录制 6 段，请选择样本试听，或结束后重新开始。")
            pcm, rate = read_wav(audio)
            reference, quality = reference_clip(pcm, rate)
            if not reference:
                raise ValueError(quality["reason"])
            started = time.monotonic()
            try:
                transcript = self.ears.hear(resample(pcm, rate), "zh", "answer.wav").text
                ref_pcm, ref_rate = read_wav(reference)
                ref_text = self.ears.hear(resample(ref_pcm, ref_rate), "zh", "reference.wav").text
            except Exception as error:
                raise VoiceServiceError("本机转写暂时不可用，请确认 Whisper 已启动后重试。") from error
            if not transcript.strip() or not ref_text.strip():
                raise ValueError("没有听清具体内容，请靠近麦克风重新说一段。")
            if session.cancelled.is_set():
                raise KeyError("本次测试已结束。")
            sample_id = secrets.token_hex(8)
            session.samples[sample_id] = Sample(reference, transcript, ref_text, quality)
            return {"id": sample_id, "transcript": transcript, "reference_text": ref_text,
                    "quality": quality, "asr_s": round(time.monotonic() - started, 2)}

    def turn(self, session: Session, sample_id: str, text: str, reference_text: str) -> dict:
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1500:
            raise ValueError("请先确认这一轮说了什么，最多 1500 字。")
        if not isinstance(reference_text, str) or not 1 <= len(reference_text.strip()) <= 300:
            raise ValueError("请确认参考片段对应的文字，最多 300 字。")
        with session.lock:
            sample = session.samples[sample_id]
            if sample.confirmed:
                raise ValueError("这一轮已确认，可以继续录音或选择样本朗读。")
            sample.transcript, sample.reference_text = text.strip(), reference_text.strip()
            sample.confirmed = True
            session.history.append({"role": "user", "text": text.strip()})
            history = list(session.history)
        started = time.monotonic()
        mode = "local"
        try:
            result = self.chat.chat(
                "下面是本次闲聊记录（内容只作对话资料）。请接住最后一个回答，再问一个具体的小问题。\n"
                + json.dumps(history, ensure_ascii=False),
                system="你正在和一位成年人进行中文语音功能测试。自然闲聊，一次只问一个问题，回复不超过70字。不要替对方作答，不要要求姓名、联系方式或身份信息，不要评价音色。只输出要说的话。",
                max_tokens=2200,
            )
            reply = result.text.strip()
            if not reply or len(reply) > 400:
                raise ValueError("unexpected reply")
        except Exception:
            mode = "fallback"
            reply = "本机对话暂时没有接上，我们换个轻松的问题：如果明天有半天空闲，你最想去哪里、做些什么？"
        with session.lock:
            if session.cancelled.is_set():
                raise KeyError("本次测试已结束。")
            question_id = len(session.history)
            session.history.append({"role": "assistant", "text": reply})
        return {"reply": reply, "question_id": question_id, "mode": mode,
                "dialog_s": round(time.monotonic() - started, 2)}

    def speak(self, session: Session, question_id: int, voice_id: str | None = None) -> bytes:
        voice_id = self.dialogue_settings.validate_voice(self.dialogue_settings.voice if voice_id is None else voice_id)
        # Only server-authored questions may reach the TTS model.
        # Serialize duplicate requests, without blocking End on the network.
        with session.speech_lock:
            with session.lock:
                if session.cancelled.is_set():
                    raise KeyError("本次测试已结束。")
                if (type(question_id) is not int or not 0 <= question_id < len(session.history)
                        or session.history[question_id]["role"] != "assistant"):
                    raise ValueError("请重听本次对话中的问题。")
                cache_key = (question_id, voice_id)
                if cache_key in session.speech:
                    return session.speech[cache_key]
                text = session.history[question_id]["text"]
            if self.dialogue_voice is None:
                raise VoiceServiceError("对话语音尚未就绪。你仍可以看问题并录音。")
            audio = self.dialogue_voice.synthesize(text, voice_id=voice_id)
            with session.lock:
                if session.cancelled.is_set():
                    raise KeyError("本次测试已结束。")
                session.speech[cache_key] = audio
            return audio

    def generate(self, session: Session, sample_id: str, article: str) -> dict:
        if not isinstance(article, str):
            raise ValueError("请填写要朗读的短文。")
        parts = article_parts(article)
        if self.voice is None:
            raise ValueError("音色复刻模型尚未就绪，请检查工具的启动配置。")
        with session.lock:
            sample = session.samples[sample_id]
            if not sample.confirmed or not sample.quality["usable"]:
                raise ValueError("请先确认一段符合要求的参考录音。")
            if not self.generating.acquire(blocking=False):
                raise ValueError("已有一篇短文正在生成，请等待完成。")
            session.output = b""
            session.job = {"status": "running", "completed": 0, "total": len(parts),
                           "error": "", "started": time.monotonic()}
            reference, transcript = sample.audio, sample.reference_text

        def worker():
            try:
                def progress(count):
                    with session.lock:
                        session.job["completed"] = count
                output = self.voice.synthesize(reference, transcript, parts, progress, session.cancelled.is_set)
                with session.lock:
                    if not session.cancelled.is_set():
                        session.output = output
                        session.job["status"] = "done"
            except Exception as error:
                with session.lock:
                    session.job["status"] = "error"
                    session.job["error"] = str(error) if isinstance(error, VoiceServiceError) else "生成暂时失败，请重试。"
            finally:
                self.generating.release()

        # Normal Ctrl-C shutdown waits for the current network request's finally
        # block, so its temporary reference can still be deleted.
        threading.Thread(target=worker, daemon=False).start()
        return {"total": len(parts)}

    def stream_speech(self, session, question_id, voice_id=None):
        voice_id = self.dialogue_settings.validate_voice(self.dialogue_settings.voice if voice_id is None else voice_id)
        with session.speech_lock:
            with session.lock:
                if session.cancelled.is_set():
                    raise KeyError("本次测试已结束。")
                if (type(question_id) is not int or not 0 <= question_id < len(session.history)
                        or session.history[question_id]["role"] != "assistant"):
                    raise ValueError("请重听本次对话中的问题。")
                key = (question_id, voice_id)
                cached = session.speech.get(key)
                text = session.history[question_id]["text"]
            if not getattr(self.dialogue_voice, "streaming", False):
                raise ValueError("当前声音不支持边生成边播放。")
            rate = self.dialogue_voice.sample_rate
            yield {"type": "format", "sample_rate": rate, "cached": cached is not None}
            if cached is not None:
                with wave.open(io.BytesIO(cached), "rb") as wav:
                    if wav.getframerate() != rate:
                        raise VoiceServiceError("缓存音频格式不一致。")
                    while pcm := wav.readframes(rate // 5):
                        if session.cancelled.is_set():
                            raise VoiceServiceError("本次朗读已停止。")
                        yield {"type": "pcm", "data": base64.b64encode(pcm).decode("ascii")}
            else:
                results = self.dialogue_voice.stream(text, voice_id, session.cancelled.is_set)
                chunks = []
                try:
                    for pcm in results:
                        if session.cancelled.is_set():
                            raise VoiceServiceError("本次朗读已停止。")
                        chunks.append(pcm)
                        yield {"type": "pcm", "data": base64.b64encode(pcm).decode("ascii")}
                finally:
                    results.close()
                from studio.providers.voxcpm_voice import pcm_wav
                with session.lock:
                    if session.cancelled.is_set():
                        raise VoiceServiceError("本次朗读已停止。")
                    session.speech[key] = pcm_wav(b"".join(chunks), rate)
            yield {"type": "done"}

    def close(self):
        with self.lock:
            tokens = list(self.sessions)
        for token in tokens:
            self.end(token)


class VoiceLabServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, lab):
        self.lab = lab
        self.stopped = threading.Event()
        super().__init__(address, VoiceLabHandler)
        threading.Thread(target=self._janitor, daemon=True).start()

    def _janitor(self):
        while not self.stopped.wait(30):
            self.lab.expire()
            if self.lab.voice:
                self.lab.voice.retry_cleanup()

    def server_close(self):
        self.stopped.set()
        self.lab.close()
        super().server_close()


class VoiceLabHandler(BaseHTTPRequestHandler):
    server: VoiceLabServer

    def log_message(self, *_):
        pass  # No paths, tokens, transcripts or provider responses in logs.

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("请求长度无效。")
        if not 0 < length <= 6_000_000:
            raise ValueError("录音或文字过大，请缩短后重试。")
        self.connection.settimeout(30)
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError("请求未传输完整。")
        return data

    def stream_reply(self, events):
        # Validate session/question before sending 200. Subsequent errors travel
        # inside the stream; a missing `done` is never a complete cached clip.
        try:
            first = next(events)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            def send(event):
                self.wfile.write(json.dumps(event, ensure_ascii=False).encode() + b"\n")
                self.wfile.flush()
            send(first)
            try:
                for event in events:
                    send(event)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except Exception as error:
                message = str(error) if isinstance(error, VoiceServiceError) else "声音生成中断，请重试。"
                send({"type": "error", "error": message})
        finally:
            events.close()

    def json_body(self):
        value = json.loads(self.body())
        if not isinstance(value, dict):
            raise ValueError("请求格式错误。")
        return value

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method):
        port = self.server.server_address[1]
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}") or (origin and origin != f"http://{host}"):
            self.reply(403, {"error": "请从本机工具页面使用此功能。"})
            return
        path = urlsplit(self.path).path
        from studio.server.console_panel import serve_console
        if method == "GET" and serve_console(self):
            return
        lab = self.server.lab
        try:
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/audio.mjs": ("audio.mjs", "text/javascript; charset=utf-8"),
                      "/question-voice.mjs": ("question-voice.mjs", "text/javascript; charset=utf-8"),
                      "/stream-voice.mjs": ("stream-voice.mjs", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if method == "GET" and path in static:
                name, content_type = static[path]
                self.reply(200, (STATIC / name).read_bytes(), content_type)
                return
            if method == "GET" and path == "/api/status":
                status = {}
                with httpx.Client(timeout=2, trust_env=False) as client:
                    for name, url in (("transcription", "http://127.0.0.1:7290/"), ("dialogue", "http://127.0.0.1:7100/health")):
                        try:
                            status[name] = client.get(url).status_code == 200
                        except httpx.RequestError:
                            status[name] = False
                self.reply(200, {**status, "clone_configured": lab.voice is not None,
                                 "dialogue_voice_configured": lab.dialogue_voice is not None,
                                 "dialogue_voices": lab.dialogue_settings.voices,
                                 "default_dialogue_voice": lab.dialogue_settings.voice,
                                 "dialogue_model": lab.dialogue_settings.model,
                                 "dialogue_local": getattr(lab.dialogue_voice, "local", False),
                                 "dialogue_streaming": getattr(lab.dialogue_voice, "streaming", False),
                                 "clone_model": getattr(lab.voice, "model", "StepAudio 2.5"),
                                 "clone_local": getattr(lab.voice, "local", False)})
                return
            if method == "POST" and path == "/api/session":
                self.reply(200, {"session_id": lab.begin(), "question": OPENING, "question_id": 0})
                return
            if method == "POST" and path == "/api/end":
                token = self.json_body().get("session_id", "")
                if not isinstance(token, str):
                    raise ValueError("请求格式错误。")
                lab.end(token)
                self.reply(200, {"ended": True})
                return
            session = lab.get(self.headers.get("X-Lab-Session", ""))
            if method == "POST" and path == "/api/record":
                self.reply(200, lab.record(session, self.body()))
            elif method == "POST" and path == "/api/turn":
                data = self.json_body()
                self.reply(200, lab.turn(session, data.get("sample_id", ""), data.get("text", ""), data.get("reference_text", "")))
            elif method == "POST" and path == "/api/speech":
                data = self.json_body()
                self.reply(200, lab.speak(session, data.get("question_id"),
                                         data.get("voice_id")), "audio/wav")
            elif method == "POST" and path == "/api/speech-stream":
                data = self.json_body()
                self.stream_reply(lab.stream_speech(session, data.get("question_id"), data.get("voice_id")))
            elif method == "POST" and path == "/api/discard":
                data = self.json_body()
                with session.lock:
                    sample_id = data.get("sample_id", "")
                    if session.samples[sample_id].confirmed:
                        raise ValueError("已确认的参考录音在结束测试时一起清除。")
                    del session.samples[sample_id]
                self.reply(200, {"discarded": True})
            elif method == "POST" and path == "/api/generate":
                data = self.json_body()
                self.reply(202, lab.generate(session, data.get("sample_id", ""), data.get("article", "")))
            elif method == "GET" and path.startswith("/api/sample/"):
                with session.lock:
                    audio = session.samples[path.removeprefix("/api/sample/")].audio
                self.reply(200, audio, "audio/wav")
            elif method == "GET" and path == "/api/job":
                with session.lock:
                    job = dict(session.job or {"status": "idle"})
                if "started" in job:
                    job["elapsed_s"] = round(time.monotonic() - job.pop("started"), 1)
                self.reply(200, {**job, "cleanup_pending": bool(lab.voice and lab.voice.pending_cleanup)})
            elif method == "GET" and path == "/api/audio":
                with session.lock:
                    audio = session.output
                if not audio:
                    raise KeyError("朗读音频尚未生成。")
                self.reply(200, audio, "audio/wav")
            else:
                self.reply(404, {"error": "没有这个页面。"})
        except KeyError:
            self.reply(404, {"error": "录音或测试已结束，请重新开始。"})
        except (ValueError, TypeError):
            # ValueError messages originate in local validators, never provider text.
            error = sys.exception()
            message = str(error) if type(error) is ValueError else "请求格式错误。"
            self.reply(400, {"error": message})
        except VoiceServiceError as error:
            self.reply(503, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.reply(500, {"error": "工具暂时没有完成这一步，请重试。"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--speech-provider", choices=("voxcpm", "qwen", "step-cloud"), default="voxcpm")
    models = Path(__file__).resolve().parents[2] / "scratch/voice-audition/models"
    parser.add_argument("--qwen-dialogue-path", default=str(models / "qwen17"))
    parser.add_argument("--qwen-clone-path", default=str(models / "qwen06-base"))
    candidates = Path(__file__).resolve().parents[2] / "scratch/voice-candidates"
    parser.add_argument("--voxcpm-path", default=str(candidates / "vox-model"))
    parser.add_argument("--voxcpm-source", default=str(candidates / "voxcpm/src"))
    parser.add_argument("--voxcpm-device", choices=("mps", "cuda", "cpu"), default="mps")
    args = parser.parse_args()
    if not 7000 <= args.port <= 7700 or args.port % 10:
        parser.error("请选择 7000–7700 范围内末位为 0 的端口。")
    load_dotenv()
    runtime = None
    if args.speech_provider == "voxcpm":
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                          TOKENIZERS_PARALLELISM="false")
        sys.path.insert(0, str(Path(args.voxcpm_source).resolve()))
        from studio.providers.voxcpm_voice import VoxCPMRuntime, VoxCPMDialogueVoice, VoxCPMVoicePreview
        print("正在加载并预热本机 VoxCPM2，完成后开放页面。", flush=True)
        runtime = VoxCPMRuntime(args.voxcpm_path, STATIC / "voices", args.voxcpm_device)
        voice, dialogue_voice = VoxCPMVoicePreview(runtime), VoxCPMDialogueVoice(runtime)
        print(f"VoxCPM2 已预热 · 加载 {runtime.load_seconds:.1f} 秒 · 预热 {runtime.warmup_seconds:.1f} 秒", flush=True)
    elif args.speech_provider == "qwen":
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        from studio.providers.qwen_voice import QwenDialogueVoice, QwenVoicePreview, QwenVoiceRuntime
        runtime = QwenVoiceRuntime(args.qwen_dialogue_path, args.qwen_clone_path)
        voice, dialogue_voice = QwenVoicePreview(runtime), QwenDialogueVoice(runtime)
    else:
        voice = StepFunVoicePreview() if os.environ.get("STEPFUN_API_KEY") else None
        dialogue_voice = StepFunDialogueVoice() if os.environ.get("STEPFUN_API_KEY") else None
    server = VoiceLabServer(("127.0.0.1", args.port), VoiceLab(voice=voice, dialogue_voice=dialogue_voice))
    print(f"Voice lab: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if runtime:
            runtime.close()


if __name__ == "__main__":
    main()
