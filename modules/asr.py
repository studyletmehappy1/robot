import logging
import re

import numpy as np
import torch
from funasr import AutoModel

logger = logging.getLogger(__name__)


class ASRModule:
    def __init__(self, model_name="paraformer-zh-streaming"):
        self.model_name = model_name
        self.model = None
        self.device = "cpu"
        self.chunk_size = [0, 10, 5]
        self.cache = {}
        self.hotwords = [
            "小艺小艺",
            "Unitree",
            "G1",
            "机器人",
            "DeepSeek",
            "FunASR",
            "Silero",
            "Edge-TTS",
        ]
        self.initial_prompt = "，".join(self.hotwords)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("正在初始化流式 ASR 模块 (model=%s, device=%s)...", model_name, device)

        try:
            self._init_model(device)
        except RuntimeError as exc:
            message = str(exc).lower()
            if "no kernel image is available" in message or "cuda" in message:
                logger.warning("CUDA 初始化失败，自动回退到 CPU: %s", exc)
                self._init_model("cpu")
            else:
                raise
        except Exception as exc:
            logger.error("ASR 模块初始化异常: %s", exc)
            self.model = None

    def _init_model(self, device):
        self.device = device
        self.model = AutoModel(
            model="damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
            device=device,
            disable_update=True,
            disable_pbar=True,
        )
        self.cache = {}
        logger.info("流式 ASR 模块初始化完成，实际运行设备: %s。", device)

    def _normalize_text(self, text):
        if not text:
            return ""

        normalized = text.strip()
        replacements = {
            "小艺 小艺": "小艺小艺",
            "小艺小易": "小艺小艺",
            "小易小艺": "小艺小艺",
            "小意小艺": "小艺小艺",
            "小艺晓艺": "小艺小艺",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)

        regex_replacements = [
            (r"\bunitree\s*g1\b", "Unitree G1"),
            (r"\bunitree\b", "Unitree"),
            (r"\bdeep\s*seek\b", "DeepSeek"),
            (r"\bdeepseek\b", "DeepSeek"),
            (r"\bedge\s*tts\b", "Edge-TTS"),
            (r"\bsilero\b", "Silero"),
            (r"\bfun\s*asr\b", "FunASR"),
        ]
        for pattern, target in regex_replacements:
            normalized = re.sub(pattern, target, normalized, flags=re.IGNORECASE)

        return normalized

    def _call_generate(self, kwargs):
        attempts = [
            {"initial_prompt": self.initial_prompt},
            {"hotword": self.initial_prompt},
            {},
        ]
        last_type_error = None

        for extra_kwargs in attempts:
            try:
                return self.model.generate(**kwargs, **extra_kwargs)
            except TypeError as exc:
                last_type_error = exc
                continue

        if last_type_error:
            raise last_type_error

        return self.model.generate(**kwargs)

    def _generate_with_context(self, audio_data, is_final=False, batch_size_s=None):
        if self.model is None:
            return []

        kwargs = {"input": audio_data}
        if batch_size_s is not None:
            kwargs["batch_size_s"] = batch_size_s
        else:
            kwargs["cache"] = self.cache
            kwargs["chunk_size"] = self.chunk_size
            kwargs["is_final"] = is_final

        return self._call_generate(kwargs)

    def transcribe_chunk(self, audio_chunk, is_final=False):
        if self.model is None:
            return ""

        try:
            audio_bytes = audio_chunk or b""
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            res = self._generate_with_context(audio_data, is_final=is_final)
            if res and len(res) > 0:
                return self._normalize_text(res[0].get("text", ""))
            return ""
        except RuntimeError as exc:
            message = str(exc).lower()
            if "no kernel image is available" in message and self.device != "cpu":
                logger.warning("ASR 推理触发 CUDA 错误，切换至 CPU 重试。")
                self._init_model("cpu")
                return self.transcribe_chunk(audio_chunk, is_final=is_final)
            logger.error("流式 ASR 识别出错: %s", exc)
            return ""
        except Exception as exc:
            logger.error("流式 ASR 识别出错: %s", exc)
            return ""

    def transcribe(self, full_audio):
        if self.model is None:
            return ""

        try:
            audio_data = np.frombuffer(full_audio, dtype=np.int16).astype(np.float32) / 32768.0
            res = self._generate_with_context(audio_data, batch_size_s=300)
            if res and len(res) > 0:
                return self._normalize_text(res[0].get("text", ""))
            return ""
        except Exception as exc:
            logger.error("批量 ASR 识别出错: %s", exc)
            return ""

    def reset_cache(self):
        self.cache = {}
        logger.info("ASR 流式缓存已重置。")
