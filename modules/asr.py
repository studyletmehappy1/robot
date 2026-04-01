import logging
from funasr import AutoModel
import numpy as np

logger = logging.getLogger(__name__)

class ASRModule:
    def __init__(self, model_name="paraformer-zh-streaming", device="cpu"):
        """
        初始化流式 ASR 模块。
        使用 paraformer-zh-streaming 模型支持流式输出。
        """
        logger.info(f"正在初始化流式 ASR 模块 (模型: {model_name}, 设备: {device})...")
        try:
            # 这里的 model 参数需要指向支持流式的模型，如 damo/speech_paraformer-acoustic-token_streaming-zh-cn-16k-common-vocab8404-pytorch
            self.model = AutoModel(
                model="damo/speech_paraformer-acoustic-token_streaming-zh-cn-16k-common-vocab8404-pytorch",
                device=device,
                disable_update=True
            )
            # 流式识别的状态缓存
            self.chunk_size = [0, 10, 5]  # [60, 10, 5] 对应 600ms 延迟
            self.cache = {}
            logger.info("流式 ASR 模块初始化完成。")
        except Exception as e:
            logger.error(f"ASR 模块初始化失败: {e}")
            self.model = None

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
