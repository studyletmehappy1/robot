import logging
import torch
import numpy as np
from silero_vad import load_silero_vad

logger = logging.getLogger(__name__)

class VADModule:
    def __init__(self, threshold=0.5, sampling_rate=16000):
        """
        初始化 VAD 模块。
        直接使用 silero_vad pip 包加载模型，避免访问 GitHub API 触发 403 错误。
        """
        logger.info("正在初始化 VAD 模块 (使用 silero-vad 本地加载)...")
        try:
            # 弃用 torch.hub.load，改用 silero_vad 包提供的本地加载函数
            self.model = load_silero_vad()
            self.threshold = threshold
            self.sampling_rate = sampling_rate
            logger.info("VAD 模块初始化完成。")
        except Exception as e:
            logger.error(f"VAD 模块初始化失败: {e}")
            self.model = None

    def is_speech(self, audio_chunk):
        """
        判断音频块是否包含人声。
        audio_chunk: 16k, 16bit, mono PCM 数据 (bytes)
        """
        if self.model is None:
            return False
            
        try:
            # 将 bytes 转换为 float32 numpy 数组
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            tensor_chunk = torch.from_numpy(audio_float32)
            
            # 模型输入需要 [batch, time] 形状
            if len(tensor_chunk.shape) == 1:
                tensor_chunk = tensor_chunk.unsqueeze(0)
                
            # 使用模型直接推理获取置信度
            with torch.no_grad():
                confidence = self.model(tensor_chunk, self.sampling_rate).item()
            return confidence > self.threshold
        except Exception as e:
            logger.error(f"VAD 检测出错: {e}")
            return False
