"""Resident VoxCPM2 for the adult lab. Model state belongs to one worker.

Only public synthetic preset references are retained. Personal
references are encoded from memory and their conditioning/KV state is erased
on success, failure and cancellation. No hosted fallback or file uploads.
"""
from concurrent.futures import ThreadPoolExecutor
import io
import queue
import threading
import time
from pathlib import Path

from studio.providers.stepfun_voice import VoiceServiceError, join_wavs


class VoxCPMRuntime:
    sample_rate = 48000

    def __init__(self, model_path, voices_path, device="mps"):
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxcpm-voice")
        try:
            self.run(self._load, model_path, voices_path, device)
        except Exception:
            self.close()
            raise

    def _load(self, model_path, voices_path, device):
        import numpy as np
        import soundfile as sf
        import torch
        from voxcpm import VoxCPM
        self.np, self.sf, self.torch = np, sf, torch
        torch.set_num_threads(8)
        started = time.monotonic()
        pipeline = VoxCPM.from_pretrained(str(Path(model_path).resolve()), load_denoiser=False,
                                         local_files_only=True, optimize=False, device=device)
        self.model = pipeline.tts_model
        if type(self.model).__name__ != "VoxCPM2Model" or self.model.sample_rate != self.sample_rate:
            raise ValueError("请选择 VoxCPM2 的完整本地权重。")
        self.references = {}
        self.load_seconds = time.monotonic() - started
        started = time.monotonic()
        for voice in VoxCPMDialogueVoice.voices:
            self.references[voice] = self.model.build_prompt_cache(
                reference_wav_path=str(Path(voices_path) / f"{voice}.wav"))
            # Warm the actual reference and streaming decode path before serving.
            self._speak("你好，准备好了我们就慢慢聊。", voice, lambda _: None, lambda: False)
        # Warm in-memory reference/continuation encoding as used by article reading.
        reference = (Path(voices_path) / "gentle-female.wav").read_bytes()
        self.read_article(reference, "晚上好，今天过得怎么样？我们可以坐下来，轻松地聊一会儿。",
                          ["你好，我们可以开始了。"], lambda _: None, lambda: False)
        self.warmup_seconds = time.monotonic() - started

    def run(self, function, *args):
        try:
            return self.worker.submit(function, *args).result()
        except VoiceServiceError:
            raise
        except Exception:
            raise VoiceServiceError("本机 VoxCPM2 没有完成这一步，请检查本地模型后重试。") from None

    def close(self):
        self.worker.shutdown(wait=True, cancel_futures=True)

    def _clear_state(self):
        with self.torch.inference_mode():
            for lm in (self.model.base_lm, self.model.residual_lm):
                lm.kv_cache.kv_cache.zero_()
                lm.kv_cache.current_length = 0
        if self.model.device == "mps":
            self.torch.mps.synchronize()

    def _generate(self, text, cache, emit, cancelled):
        if cancelled():
            raise VoiceServiceError("本次朗读已停止。")
        text = text.replace("（", "，").replace("）", "，").replace("(", "，").replace(")", "，")
        token_limit = min(len(self.model.text_tokenizer(text)) * 6 + 10, 750)
        results = self.model.generate_with_prompt_cache_streaming(
            target_text=text, prompt_cache=cache, cfg_value=2.0, inference_timesteps=10,
            max_len=750, retry_badcase=False, seed=42)
        frames, count, peak = 0, 0, 0.
        try:
            for wav, _, _ in results:
                if cancelled():
                    raise VoiceServiceError("本次朗读已停止。")
                data = wav.detach().cpu().float().numpy().reshape(-1)
                if not self.np.isfinite(data).all():
                    raise VoiceServiceError("生成的声音无效，请重试。")
                if not len(data):
                    continue
                frames += len(data)
                count += 1
                peak = max(peak, float(self.np.max(self.np.abs(data))))
                if frames > self.sample_rate * 120 or count >= token_limit:
                    raise VoiceServiceError("模型没有完整读完，请缩短文字再试。")
                pcm = (self.np.clip(data, -1, 1) * 32767).astype("<i2").tobytes()
                emit(pcm)
            if not frames or peak < .001:
                raise VoiceServiceError("生成的声音为空或过轻，请重试。")
        finally:
            results.close()
            self._clear_state()

    def _speak(self, text, voice, emit, cancelled):
        self._generate(text, self.references[voice], emit, cancelled)

    def stream(self, text, voice, cancelled=lambda: False):
        """Bounded producer queue; closing the consumer also stops its model job."""
        items = queue.Queue(maxsize=8)
        stopped = threading.Event()
        def is_stopped():
            return stopped.is_set() or cancelled()
        def put(item):
            while not is_stopped():
                try:
                    items.put(item, timeout=.1)
                    return
                except queue.Full:
                    pass
            raise VoiceServiceError("本次朗读已停止。")
        def work():
            try:
                self._speak(text, voice, lambda pcm: put(("pcm", pcm)), is_stopped)
                put(("done", None))
            except Exception as error:
                message = str(error) if isinstance(error, VoiceServiceError) else "本机声音生成中断，请重试。"
                if not is_stopped():
                    try:
                        put(("error", message))
                    except VoiceServiceError:
                        pass
        future = self.worker.submit(work)
        try:
            while not is_stopped():
                try:
                    kind, value = items.get(timeout=.2)
                except queue.Empty:
                    continue
                if kind == "error":
                    raise VoiceServiceError(value)
                if kind == "done":
                    return
                yield value
            raise VoiceServiceError("本次朗读已停止。")
        finally:
            stopped.set()
            future.cancel()

    def read_article(self, reference, transcript, parts, progress, cancelled):
        cache = {}
        try:
            if cancelled():
                raise VoiceServiceError("本次朗读已停止。")
            info = self.sf.info(io.BytesIO(reference))
            if info.channels != 1 or not 3 <= info.duration <= 10:
                raise VoiceServiceError("请使用一段清晰的单人参考声音。")
            # librosa/soundfile accept file-like streams; no personal WAV on disk.
            cache = self.model.build_prompt_cache(prompt_text=transcript,
                prompt_wav_path=io.BytesIO(reference), reference_wav_path=io.BytesIO(reference))
            outputs = []
            for index, part in enumerate(parts):
                chunks = []
                self._generate(part, cache, chunks.append, cancelled)
                outputs.append(pcm_wav(b"".join(chunks), self.sample_rate))
                progress(index + 1)
            return join_wavs(outputs)
        finally:
            with self.torch.inference_mode():
                for value in cache.values():
                    if isinstance(value, self.torch.Tensor):
                        value.zero_()
            cache.clear()
            self._clear_state()


def pcm_wav(pcm, rate=48000):
    import wave
    target = io.BytesIO()
    with wave.open(target, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return target.getvalue()


class VoxCPMDialogueVoice:
    model = "VoxCPM2 · 本机"
    voice = "gentle-female"
    voices = {"gentle-female": "温柔女声", "gentle-male": "温和男声", "soft-child": "软糯童声"}
    local = True
    streaming = True
    sample_rate = 48000

    def __init__(self, runtime):
        self.runtime = runtime

    @classmethod
    def validate_voice(cls, voice_id):
        if not isinstance(voice_id, str) or voice_id not in cls.voices:
            raise ValueError("请选择设置中的一种声音。")
        return voice_id

    def stream(self, text, voice_id=voice, cancelled=lambda: False):
        self.validate_voice(voice_id)
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError("朗读文字需为 1–400 字。")
        return self.runtime.stream(text, voice_id, cancelled)

    def synthesize(self, text, voice_id=voice):
        return pcm_wav(b"".join(self.stream(text, voice_id)), self.sample_rate)


class VoxCPMVoicePreview:
    model = "VoxCPM2 · 本机参考音色朗读"
    local = True
    pending_cleanup = False

    def __init__(self, runtime):
        self.runtime = runtime

    def retry_cleanup(self):
        return True

    def synthesize(self, reference, transcript, parts, progress, cancelled=lambda: False):
        return self.runtime.run(self.runtime.read_article, reference, transcript, parts, progress, cancelled)
