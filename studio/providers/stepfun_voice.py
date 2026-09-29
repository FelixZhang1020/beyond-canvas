"""Temporary voice previews, without creating a permanent voice asset.

Official contracts checked:
https://platform.stepfun.com/docs/zh/api-reference/audio/voices-preview
https://platform.stepfun.com/docs/zh/api-reference/files/create
https://platform.stepfun.com/docs/zh/api-reference/files/delete
The preview recommends <= 50 characters, and reference uploads 5–10 seconds.
Only this tool's own uploads are deleted. Responses and recordings are not logged.
"""

from __future__ import annotations

import base64
import io
import re
import threading
import wave
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.stepfun import API_URL, StepFunMediaClient, _require_key
from studio.voice.audio_in import UnreadableAudio, as_mp3


class VoiceServiceError(RuntimeError):
    """A displayable error that contains no provider response or personal text."""


def rejection_reason(response: httpx.Response) -> str:
    """Classify provider feedback without returning its free-form message.

    Error messages can echo the submitted transcript, credentials or file IDs.
    Only fixed descriptions leave this boundary; unknown errors stay unknown.
    """
    reasons = {
        401: "账号凭据不可用", 402: "账号余额不足", 404: "云端接口或参考文件不存在",
        429: "请求较多，请稍后重试", 451: "云端内容检查未通过",
        500: "云端服务发生错误", 503: "云端服务暂时繁忙",
    }
    if response.status_code in reasons:
        return reasons[response.status_code]
    if response.status_code == 400:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        if isinstance(error, dict):
            param = error.get("param")
            parameters = {
                "text": "参考录音对应文字被拒绝，请核对文字与录音是否一致",
                "sample_text": "要朗读的文字被拒绝，请缩短后试用",
                "file_id": "云端无法使用这份参考录音文件",
                "model": "当前账号无法使用所选语音模型",
                "sample_rate": "云端不接受当前音频采样率",
                "response_format": "云端不接受当前输出音频格式",
                "instruction": "云端不接受当前朗读指令",
                "speed": "云端不接受当前朗读速度",
            }
            if isinstance(param, str) and param in parameters:
                return parameters[param]
            # Match only technical phrases; never display an echoed user string.
            message = error.get("message", "")
            if isinstance(message, str):
                message = message.lower()
                if "audio" in message and "duration" in message:
                    return "云端认为参考录音时长不符合要求，请使用 5–10 秒的录音"
                if "signal-to-noise" in message or "snr" in message:
                    return "云端认为参考录音的背景噪声偏大"
                if "no speech" in message or "no voice detected" in message:
                    return "云端没有识别到可用的人声"
        return "云端拒绝了请求参数，尚不能确定是录音、文字还是模型配置导致"
    return "请求未完成，请稍后再试"


def article_parts(text: str) -> list[str]:
    text = text.strip()
    if not text or len(text) > 500:
        raise ValueError("请输入 1–500 字的短文。")
    # StepAudio treats parentheses as instructions. Removing only the delimiters
    # keeps the enclosed words audible instead of silently omitting them.
    text = text.translate(str.maketrans({"(": "，", ")": "，", "（": "，", "）": "，"}))
    parts: list[str] = []
    while text:
        end = min(48, len(text))
        if len(text) > end:
            boundaries = [i + 1 for i, ch in enumerate(text[:end]) if ch in "。！？；，.!?;\n "]
            if boundaries and boundaries[-1] >= 12:
                end = boundaries[-1]
        part, text = text[:end].strip(), text[end:].lstrip()
        if part:
            parts.append(part)
    return parts


def join_wavs(clips: list[bytes]) -> bytes:
    if not clips:
        raise VoiceServiceError("没有收到可播放的声音，请重试。")
    target = io.BytesIO()
    try:
        with wave.open(target, "wb") as out:
            expected = None
            for index, clip in enumerate(clips):
                with wave.open(io.BytesIO(clip), "rb") as audio:
                    shape = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                    if audio.getcomptype() != "NONE" or audio.getnframes() == 0:
                        raise ValueError("invalid PCM")
                    if expected is None:
                        expected = shape
                        out.setnchannels(shape[0])
                        out.setsampwidth(shape[1])
                        out.setframerate(shape[2])
                    if shape != expected:
                        raise ValueError("inconsistent audio")
                    if index:
                        out.writeframes(b"\0" * (int(shape[2] * .12) * shape[0] * shape[1]))
                    out.writeframes(audio.readframes(audio.getnframes()))
    except (wave.Error, EOFError, ValueError) as error:
        raise VoiceServiceError("服务返回的音频格式不一致，请重新生成。") from error
    return target.getvalue()


class StepFunDialogueVoice:
    """The presets selected in the adult audition; never accepts reference audio.

    Contract: https://platform.stepfun.com/docs/zh/api-reference/audio/create-audio
    Keep the voice, instruction and audio settings identical to that audition.
    """
    model = "stepaudio-2.5-tts"
    voice = "elegantgentle-female"
    voices = {"elegantgentle-female": "气质温婉女声", "wenrounansheng": "温柔男声"}
    instruction = "用自然、放松、亲切的中文与一位成年人面对面闲聊，语气温柔，有自然的停顿，提问时带一点好奇。"

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        *,
        base_url: str | None = None,
        included_in_plan: bool = False,
    ):
        # `base_url` so speech can follow the deployment it belongs to: StepFun
        # First speaks through the subscription endpoint, api through the
        # pay-as-you-go one. None means the module default, which is what every
        # caller that has no profile in hand — the voice lab, the --speech-provider
        # override — passes. `base_url` is also read as an attribute by
        # studio/voice/speech.py, which keys its clip cache on it.
        self.base_url = (base_url or API_URL).rstrip("/")
        self._media = StepFunMediaClient(
            self.model,
            {"endpoint": "audio/speech", "base_url": self.base_url,
             "included_in_plan": included_in_plan},
            api_key,
            client or httpx.Client(timeout=60.0),
        )

    @classmethod
    def validate_voice(cls, voice_id: str) -> str:
        if not isinstance(voice_id, str) or voice_id not in cls.voices:
            raise ValueError("请选择设置中提供的对话声音。")
        return voice_id

    def synthesize(self, text: str, voice_id: str = voice) -> bytes:
        voice_id = self.validate_voice(voice_id)
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError("对话问题需要是 1–400 字的文字。")
        # Parenthesized text is otherwise treated as a StepAudio instruction.
        text = text.strip().translate(str.maketrans({"(": "，", ")": "，", "（": "，", "）": "，"}))
        try:
            result = self._media.make({
                "input": text, "voice": voice_id, "instruction": self.instruction,
                "response_format": "wav", "sample_rate": 24000, "speed": 1,
            })
        except (ModelRefused, ModelUnavailable) as error:
            # The generic media client's errors may include provider text.
            raise VoiceServiceError("Step 对话语音暂未生成，请稍后重试；没有自动重复请求。") from error
        return join_wavs([result.content])


class StepFunVoicePreview:
    model = "stepaudio-2.5-tts"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self._headers = {"Authorization": f"Bearer {_require_key(api_key)}"}
        self._client = client or httpx.Client(timeout=120.0)
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, API_URL + path, headers=self._headers, **kwargs)
        except httpx.RequestError as error:
            if path == "/files":
                raise VoiceServiceError("上传结果不确定，请在阶跃星辰控制台检查本次临时文件；工具不会自动重复上传。") from error
            raise VoiceServiceError("阶跃星辰连接中断，请稍后重试；不自动重复收费请求。") from error
        if response.status_code >= 400:
            stage = "上传原声" if path == "/files" else "合成朗读"
            raise VoiceServiceError(
                f"{stage}失败：{rejection_reason(response)}（HTTP {response.status_code}）。"
                "原声仍保留，可以回听；本次没有自动重试。"
            )
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            value = response.json()
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
        raise VoiceServiceError("阶跃星辰返回了无法读取的结果，请重试。")

    @property
    def pending_cleanup(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def delete_upload(self, file_id: str) -> bool:
        with self._lock:
            if file_id not in self._pending:
                return True
        try:
            response = self._client.delete(
                API_URL + "/files/" + quote(file_id, safe=""), headers=self._headers, timeout=15.0,
            )
            gone = response.status_code == 404 or (
                response.is_success and self._json(response).get("deleted") is True
            )
        except (httpx.RequestError, VoiceServiceError):
            gone = False
        if gone:
            with self._lock:
                self._pending.discard(file_id)
        return gone

    def retry_cleanup(self) -> bool:
        with self._lock:
            pending = list(self._pending)
        for file_id in pending:
            self.delete_upload(file_id)
        return not self.pending_cleanup

    def synthesize(
        self, reference: bytes, transcript: str, parts: list[str],
        progress: Callable[[int], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> bytes:
        if cancelled():
            raise VoiceServiceError("本次生成已停止。")
        upload = self._json(self._request(
            "POST", "/files", data={"purpose": "storage"},
            files={"file": ("voice-lab-reference.wav", reference, "audio/wav")},
        ))
        file_id = upload.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise VoiceServiceError("未收到上传文件编号，无法自动清理；请在阶跃星辰控制台检查本次上传。")
        try:
            clips = []
            for index, part in enumerate(parts):
                if cancelled():
                    raise VoiceServiceError("本次生成已停止。")
                result = self._json(self._request("POST", "/audio/voices/preview", json={
                    "model": self.model, "file_id": file_id, "text": transcript,
                    "sample_text": part, "response_format": "wav", "sample_rate": 24000,
                    "speed": 1.0,
                    "instruction": "保持参考录音中说话者本人的音色，自然、清楚地朗读。不要添加原文之外的词语。",
                }))
                try:
                    clip = base64.b64decode(result["sample_audio"], validate=True)
                except (ValueError, KeyError, TypeError) as error:
                    raise VoiceServiceError("没有收到有效音频，请重新生成。") from error
                if len(clip) > 12_000_000:
                    raise VoiceServiceError("返回音频超过本工具的大小限制。")
                clips.append(clip)
                progress(index + 1)
            return join_wavs(clips)
        finally:
            # Only finished uploads enter the retry queue. A janitor must never
            # delete the reference while another preview segment still uses it.
            with self._lock:
                self._pending.add(file_id)
            self.delete_upload(file_id)


class StepFunClassroomVoice(StepFunDialogueVoice):
    """Preset-only classroom speech, sent a whole sentence at a time as MP3."""
    local = False
    sample_rate = 24000
    # Each sentence travels as the MP3 StepFun makes, not as raw sound: raw sound needs
    # 64 KB for every second spoken, and the relay between the Spark and a classroom delivered 29 KB/s
    # at one point, so the page played, ran dry and played again. MP3 is 13 KB/s; Opus and a lower sample
    # rate came back no smaller. studio/voice/speech.py sends these as "mp3" events. StepFun's MP3 is 128 kbit/s, and
    # at a slow moment on the link a press waited 32 s for its first sentence: each is made again here at
    # 48 kbit/s, 2.6 times smaller, which a spoken voice does not miss (operator: "go ahead").
    compressed = True
    bitrate = '48k'
    voice = 'gentle-female'
    voices = {'gentle-female': '温柔女声', 'gentle-male': '温柔男声', 'soft-child': '故事朗读（预设声音）'}
    instruction = '像幼儿园美术老师一样说话：温柔、清楚、慢一点，带着笑意。'

    def stream(self, text, voice_id=voice, cancelled=lambda: False):
        """Speak sentence by sentence, the first as soon as it is made.

        StepFun answers with one whole file, so asking for everything at once
        kept a class silent for the whole synthesis: measured on the Spark,
        1.8 s for one sentence, 4 s for 56 characters and 10-11 s
        for 150. The next sentence is made while the one before it plays. Each
        is yielded whole, as MP3, so the page plays a sentence only once all of
        it has arrived, and a slow link delays the next one instead of cutting it.
        """
        voice_id = self.validate_voice(voice_id)
        if cancelled():
            return
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError('Speech requires 1–400 characters.')
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='speech')
        try:
            pending = [pool.submit(self._made, part, voice_id) for part in sentences(text.strip())]
            size = 0
            for clip in pending:
                if cancelled():
                    return
                mp3 = clip.result()
                size += len(mp3)
                if size > MP3_LIMIT:
                    raise ValueError('Speech too long')
                yield mp3
        except (ModelRefused, ModelUnavailable, ValueError):
            raise VoiceServiceError('StepFun speech is unavailable; no automatic retry.') from None
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def clip(self, text, voice_id=voice):
        """One piece of speech as one MP3, never split again: a sentence a book keeps (studio/voice/book_voice.py)."""
        voice_id = self.validate_voice(voice_id)
        try:
            return self._made(text.strip(), voice_id)
        except (ModelRefused, ModelUnavailable, ValueError):
            raise VoiceServiceError('StepFun speech is unavailable; no automatic retry.') from None

    def _made(self, text, voice_id):
        """One piece as StepFun made it, checked to be MP3 before anything else, then at the speech bitrate."""
        mp3 = self._clip(text, voice_id)
        if not (mp3[:3] == b'ID3' or (mp3[:1] == b'\xff' and mp3[1:2] >= b'\xe0')):
            raise ValueError('Unexpected speech format')
        return smaller(mp3, self.bitrate)

    def _clip(self, text, voice_id):
        return self._media.make({
            'input': text,
            'voice': {'gentle-female': 'wenrounvsheng', 'gentle-male': 'wenrounansheng', 'soft-child': 'wenrounvsheng'}[voice_id],
            'instruction': ('像在念一本睡前故事书：温柔、清楚，慢慢讲给五岁的孩子听。' if voice_id == 'soft-child' else self.instruction), 'response_format': 'mp3',
            'sample_rate': self.sample_rate, 'speed': .95,
        }).content


def smaller(mp3, bitrate):
    """StepFun's MP3 at a speech bitrate, or as it came when ffmpeg cannot read it: a voice is never lost to this."""
    try:
        return as_mp3(mp3, bitrate)
    except (UnreadableAudio, OSError):   # OSError: a busy node that could not start ffmpeg (EAGAIN)
        return mp3


# A sentence ends at Chinese or Latin end punctuation. Pieces under MIN_SENTENCE
# characters ride with the next, so a lone "哇！" is not its own request. A first
# sentence over FIRST_MAX breaks at its first comma: the first sound waits on the
# first piece alone, and a 44-character opener kept a class silent 3.5 s.
SENTENCE_END = re.compile(r'(?<=[。！？!?；;…])')
MIN_SENTENCE = 8
FIRST_MAX = 24
COMMA = re.compile(r'[，,、]')


# Two minutes at 40 KB/s, the highest MP3 bitrate there is (320 kbps), so no valid MP3 is refused for
# its quality; StepFun's measured 13 KB/s. The page holds the two-minute limit by duration once
# decoded, and speech is capped at 400 characters anyway (review).
MP3_LIMIT = 120 * 40_000


def sentences(text):
    """Split what is to be spoken into sentences, in order, none of them empty."""
    parts, carry = [], ''
    for piece in SENTENCE_END.split(text):
        carry += piece
        if len(carry.strip()) >= MIN_SENTENCE:
            parts.append(carry.strip())
            carry = ''
    if carry.strip():
        if parts:
            parts[-1] += carry.strip()
        else:
            parts.append(carry.strip())
    comma = COMMA.search(parts[0], MIN_SENTENCE) if parts and len(parts[0]) > FIRST_MAX else None
    if comma and comma.end() < len(parts[0]):
        parts[:1] = [parts[0][:comma.end()], parts[0][comma.end():]]
    return parts
