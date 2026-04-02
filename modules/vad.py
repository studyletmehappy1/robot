import logging
import torch
import numpy as np
from silero_vad import load_silero_vad

logger = logging.getLogger(__name__)

class VADModule:
    def __init__(self, threshold=0.65, sampling_rate=16000):
        """
        初始化 VAD 模块。
        直接使用 silero_vad pip 包加载模型，避免访问 GitHub API 触发 403 错误。
        """
        # 强制使用 CPU 推理，避免 CUDA error: no kernel image is available 报错
        # Silero-VAD 模型非常轻量，在 CPU 上运行已足够快
        self.device = torch.device("cpu")
        logger.info(f"正在初始化 VAD 模块 (使用 silero-vad 本地加载, 强制设备: {self.device})...")
        try:
            # 弃用 torch.hub.load，改用 silero_vad 包提供的本地加载函数
            self.model = load_silero_vad()
            # 强制将模型挂载到 CPU 上运行
            self.model.to(self.device)
            self.threshold = threshold
            self.sampling_rate = sampling_rate
            logger.info(f"VAD 模块初始化完成，运行设备: {self.device}。")
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
            
            # 【核心修复】循环切片机：将 Web 传来的大包 (4096 采样) 切分为 512 的小包推理
            chunk_size = 512
            has_speech = False
            
            for i in range(0, len(audio_float32), chunk_size):
                small_chunk = audio_float32[i:i+chunk_size]
                if len(small_chunk) < chunk_size:
                    break # 丢弃尾部不足 512 的数据，防止模型报错
                    
                tensor_chunk = torch.from_numpy(small_chunk).to(self.device)
                if len(tensor_chunk.shape) == 1:
                    tensor_chunk = tensor_chunk.unsqueeze(0)
                    
                with torch.no_grad():
                    # 使用模型直接推理获取置信度
                    confidence = self.model(tensor_chunk, self.sampling_rate).item()
                    
                # 只要这 8 个切片中有一个检测到人声，就认为这段音频有人声
                if confidence > self.threshold:
                    has_speech = True
                    break 
                    
            return has_speech
        except Exception as e:
            logger.error(f"VAD 检测出错: {e}")
            return False