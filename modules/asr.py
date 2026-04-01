import logging
from funasr import AutoModel
import numpy as np

logger = logging.getLogger(__name__)

class ASRModule:
    def __init__(self, model_name="paraformer-zh", device="cpu"):
        logger.info(f"正在初始化 ASR 模块 (模型: {model_name}, 设备: {device})...")
        self.model = AutoModel(model=model_name, device=device)
        logger.info("ASR 模块初始化完成。")

    def transcribe(self, audio_data):
        """
        将音频数据转换为文本。
        audio_data: 16k, 16bit, mono PCM 数据 (bytes)
        """
        try:
            # 将 bytes 转换为 float32 numpy 数组
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            res = self.model.generate(input=audio_float32, batch_size_s=300)
            if res and len(res) > 0:
                text = res[0].get('text', '')
                return text
            return ""
        except Exception as e:
            logger.error(f"ASR 识别出错: {e}")
            return ""
