import logging
import torch
from funasr import AutoModel
import numpy as np

logger = logging.getLogger(__name__)

class ASRModule:
    def __init__(self, model_name="paraformer-zh-streaming"):
        """
        初始化流式 ASR 模块。
        使用 paraformer-zh-streaming 官方模型 ID 支持流式输出。
        """
        # 增加硬件检测逻辑，优先尝试使用 CUDA
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"正在尝试初始化流式 ASR 模块 (模型: {model_name}, 目标设备: {device})...")
        
        try:
            self._init_model(device)
        except RuntimeError as e:
            # 针对 RTX 50 系列等最新显卡，捕获架构不兼容导致的 RuntimeError
            if "no kernel image is available" in str(e).lower() or "cuda" in str(e).lower():
                print("\033[93m\n[警告] 检测到当前 PyTorch 版本不支持该显卡架构，正在自动降级为 CPU 运行...\033[0m")
                logger.warning(f"CUDA 初始化失败，尝试降级到 CPU: {e}")
                self._init_model("cpu")
            else:
                raise e
        except Exception as e:
            logger.error(f"ASR 模块初始化遇到非预期错误: {e}")
            self.model = None

    def _init_model(self, device):
        """内部模型初始化逻辑"""
        self.model = AutoModel(
            model="damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
            device=device,
            disable_update=True,
            disable_pbar=True  # 屏蔽底层刷屏日志
        )
        # 流式识别的状态缓存
        self.chunk_size = [0, 10, 5]  # [60, 10, 5] 对应 600ms 延迟
        self.cache = {}
        logger.info(f"流式 ASR 模块初始化完成，实际运行设备: {device}。")

    def transcribe_chunk(self, audio_chunk, is_final=False):
        """
        流式识别音频切片。
        audio_chunk: 原始音频字节流 (16k, 16bit, mono)
        is_final: 是否是最后一段
        返回: 识别到的文本增量
        """
        if self.model is None:
            return ""
        
        try:
            # 将字节流转换为 numpy 数组
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            
            # 调用流式推理
            res = self.model.generate(
                input=audio_data,
                cache=self.cache,
                chunk_size=self.chunk_size,
                is_final=is_final
            )
            
            if res and len(res) > 0:
                text = res[0].get('text', '')
                return text
            
            return ""
        except RuntimeError as e:
            # 推理阶段也可能触发 CUDA 架构不兼容错误
            if "no kernel image is available" in str(e).lower() and self.model.device != "cpu":
                print("\033[93m\n[警告] 推理时检测到显卡架构不兼容，正在紧急切换至 CPU 模式...\033[0m")
                logger.warning("推理阶段触发 CUDA 错误，尝试重新初始化模型至 CPU")
                self._init_model("cpu")
                return self.transcribe_chunk(audio_chunk, is_final)
            logger.error(f"流式 ASR 识别出错: {e}")
            return ""
        except Exception as e:
            logger.error(f"流式 ASR 识别出错: {e}")
            return ""

    def transcribe(self, full_audio):
        """
        保留非流式识别接口，用于兼容旧代码或最终校准。
        """
        if self.model is None:
            return ""
        
        try:
            audio_data = np.frombuffer(full_audio, dtype=np.int16).astype(np.float32) / 32768.0
            res = self.model.generate(input=audio_data, batch_size_s=300)
            if res and len(res) > 0:
                return res[0].get('text', '')
            return ""
        except Exception as e:
            logger.error(f"批量 ASR 识别出错: {e}")
            return ""

    def reset_cache(self):
        """重置流式缓存，用于新的一轮对话"""
        self.cache = {}
        logger.info("ASR 流式缓存已重置。")
