import logging
import asyncio
import edge_tts
import os
import time

logger = logging.getLogger(__name__)

class TTSModule:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural", rate="+0%"):
        logger.info(f"正在初始化 TTS 模块 (音色: {voice}, 语速: {rate})...")
        self.voice = voice
        self.rate = rate
        self.output_dir = "temp_audio"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info("TTS 模块初始化完成。")

    async def _generate_audio(self, text, output_file):
        """
        异步生成语音文件。
        """
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await communicate.save(output_file)

    def to_tts(self, text):
        """
        同步封装 TTS 生成过程。
        """
        if not text or not text.strip():
            return None
        
        filename = f"tts_{int(time.time() * 1000)}.mp3"
        output_path = os.path.join(self.output_dir, filename)
        
        try:
            asyncio.run(self._generate_audio(text, output_path))
            if os.path.exists(output_path):
                return output_path
            return None
        except Exception as e:
            logger.error(f"TTS 生成出错: {e}")
            return None

    def clean_up(self, file_path):
        """
        清理生成的临时语音文件。
        """
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"清理 TTS 文件失败: {e}")
