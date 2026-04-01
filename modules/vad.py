import logging
import torch
import numpy as np
import os

logger = logging.getLogger(__name__)

class VADModule:
    def __init__(self, threshold=0.5, sampling_rate=16000, model_path=None):
        logger.info(f"正在初始化 VAD 模块 (阈值: {threshold})...")
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        
        # 默认使用 torchhub 加载，如果提供了本地路径则从本地加载
        if model_path and os.path.exists(model_path):
            self.model = torch.jit.load(model_path, map_location="cpu")
        else:
            self.model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                          model='silero_vad',
                                          force_reload=False,
                                          onnx=False)
        self.model.eval()
        logger.info("VAD 模块初始化完成。")

    def is_speech(self, audio_chunk):
        """
        判断音频块是否包含人声。
        audio_chunk: 16k, 16bit, mono PCM 数据 (bytes)
        """
        try:
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            tensor_chunk = torch.from_numpy(audio_float32)
            
            # 模型输入需要 [batch, time] 形状
            if len(tensor_chunk.shape) == 1:
                tensor_chunk = tensor_chunk.unsqueeze(0)
                
            confidence = self.model(tensor_chunk, self.sampling_rate).item()
            return confidence > self.threshold
        except Exception as e:
            logger.error(f"VAD 检测出错: {e}")
            return False
