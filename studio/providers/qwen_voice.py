"""Optional local MLX voices for the adult voice lab; no hosted fallback.

Install MLX Audio in the isolated voice environment, not the studio environment.
All MLX work runs on one worker so concurrent sessions cannot share decoder state.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import math
from pathlib import Path
import time

from studio.providers.stepfun_voice import VoiceServiceError, join_wavs


class QwenVoiceRuntime:
    def __init__(self, dialogue_path: str, clone_path: str):
        for path in (dialogue_path, clone_path):
            if not (Path(path) / "config.json").is_file():
                raise ValueError("Qwen 本地模型尚未下载完整，请检查模型目录。")
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qwen-voice")
        try:
            self.worker.submit(self._load, dialogue_path, clone_path).result()
        except Exception:
            self.worker.shutdown(wait=True)
            raise

    def _load(self, dialogue_path, clone_path):
        import mlx.core as mx
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model

        self.mx, self.np, self.sf = mx, np, sf
        started = time.monotonic()
        self.dialogue = load_model(str(Path(dialogue_path).resolve()))
        self.clone = load_model(str(Path(clone_path).resolve()))
        if (self.dialogue.config.tts_model_type != "custom_voice"
                or self.dialogue.config.tts_model_size != "1b7"
                or self.clone.config.tts_model_type != "base"
                or self.clone.config.tts_model_size != "0b6"
                or not self.clone.speech_tokenizer.has_encoder):
            raise ValueError("请分别选择 Qwen CustomVoice 和带编码器的 Base 模型。")
        mx.eval(self.dialogue.parameters(), self.clone.parameters())
        self.load_seconds = time.monotonic() - started
        self.last_metrics = {}

    def close(self):
        self.worker.shutdown(wait=True, cancel_futures=True)

    def run(self, function, *args):
        try:
            return self.worker.submit(function, *args).result()
        except VoiceServiceError:
            raise
        except Exception:
            raise VoiceServiceError("本机 Qwen 暂时没有完成合成，请重试。") from None

    def _clear(self, model):
        # MLX Audio caches reference codes and the reference transcript for ICL.
        # They must not survive a synthesis job or cancellation.
        model._icl_cache.clear()
        model.speech_tokenizer.decoder.reset_streaming_state()
        self.mx.clear_cache()

    def _collect(self, results, cancelled=lambda: False):
        started = time.monotonic()
        chunks, rate, count, first = [], None, 0, None
        try:
            for result in results:
                if cancelled():
                    raise VoiceServiceError("本次测试已结束，合成已停止。")
                self.mx.eval(result.audio)
                data = self.np.asarray(result.audio, dtype=self.np.float32).reshape(-1)
                count += result.token_count
                if not len(data):
                    continue
                if rate is not None and rate != result.sample_rate:
                    raise VoiceServiceError("本机模型返回了不一致的音频格式。")
                rate = result.sample_rate
                first = first if first is not None else time.monotonic() - started
                chunks.append(data)
        finally:
            results.close()
        if not chunks or count >= 700:
            raise VoiceServiceError("本机模型没有完整读完，请缩短文字再试。")
        data = self.np.concatenate(chunks)
        if not self.np.isfinite(data).all() or float(self.np.max(self.np.abs(data))) < .001:
            raise VoiceServiceError("生成的声音无效，请重试。")
        target = io.BytesIO()
        self.sf.write(target, data, rate, format="WAV", subtype="PCM_16")
        self.last_metrics = {"first_chunk_s": round(first, 4),
                             "total_s": round(time.monotonic() - started, 3),
                             "duration_s": round(len(data) / rate, 3)}
        return target.getvalue()

    def speak(self, text, voice):
        try:
            return self._collect(self.dialogue.generate_custom_voice(
                text=text, speaker=voice, language="Chinese",
                instruct="用温柔、放松、亲切的语气和我面对面聊天，语速自然，停顿自然，不要播音腔。",
                stream=True, streaming_interval=.32, max_tokens=700, verbose=False,
            ))
        finally:
            self._clear(self.dialogue)

    def read_article(self, reference, transcript, parts, progress, cancelled):
        self._clear(self.clone)
        try:
            if cancelled():
                raise VoiceServiceError("本次测试已结束，合成已停止。")
            audio, rate = self.sf.read(io.BytesIO(reference), dtype="float32")
            if audio.ndim != 1 or not 3 <= len(audio) / rate <= 10:
                raise VoiceServiceError("请使用一段清晰的单人参考声音。")
            if rate != self.clone.sample_rate:
                from scipy.signal import resample_poly
                divisor = math.gcd(rate, self.clone.sample_rate)
                audio = resample_poly(audio, self.clone.sample_rate // divisor, rate // divisor)
            ref = self.mx.array(audio, dtype=self.mx.float32)
            outputs = []
            for index, part in enumerate(parts):
                if cancelled():
                    raise VoiceServiceError("本次测试已结束，合成已停止。")
                outputs.append(self._collect(self.clone.generate(
                    text=part, ref_audio=ref, ref_text=transcript, lang_code="Chinese",
                    stream=True, streaming_interval=.32, max_tokens=700, verbose=False,
                ), cancelled))
                progress(index + 1)
            return join_wavs(outputs)
        finally:
            self._clear(self.clone)


class QwenDialogueVoice:
    model = "Qwen3-TTS 1.7B CustomVoice · 本机"
    voice = "Serena"
    voices = {"Serena": "温柔女声 · Serena", "Uncle_Fu": "温和男声 · Uncle Fu"}
    local = True

    def __init__(self, runtime):
        self.runtime = runtime

    @classmethod
    def validate_voice(cls, voice_id):
        if not isinstance(voice_id, str) or voice_id not in cls.voices:
            raise ValueError("请选择设置中的一种声音。")
        return voice_id

    def synthesize(self, text, voice_id=voice):
        voice_id = self.validate_voice(voice_id)
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 400:
            raise ValueError("朗读文字需为 1–400 字。")
        return self.runtime.run(self.runtime.speak, text, voice_id)


class QwenVoicePreview:
    model = "Qwen3-TTS 0.6B Base · 本机"
    local = True
    pending_cleanup = False

    def __init__(self, runtime):
        self.runtime = runtime

    def retry_cleanup(self):
        return True

    def synthesize(self, reference, transcript, parts, progress, cancelled=lambda: False):
        return self.runtime.run(self.runtime.read_article, reference, transcript, parts, progress, cancelled)
