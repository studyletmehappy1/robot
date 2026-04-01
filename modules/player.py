import logging
import pygame
import time
import os
import threading

logger = logging.getLogger(__name__)

class PlayerModule:
    def __init__(self):
        logger.info("正在初始化播放器模块 (Pygame)...")
        pygame.mixer.init()
        self.stop_event = threading.Event()
        self.playing = False
        logger.info("播放器模块初始化完成。")

    def play(self, audio_file):
        """
        播放音频文件。
        """
        if not audio_file or not os.path.exists(audio_file):
            logger.error(f"播放失败，文件不存在: {audio_file}")
            return
        
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            self.playing = True
            
            while pygame.mixer.music.get_busy():
                if self.stop_event.is_set():
                    pygame.mixer.music.stop()
                    logger.info("播放已停止 (外部打断)。")
                    break
                time.sleep(0.05)
            
            self.playing = False
            self.stop_event.clear()
            
        except Exception as e:
            logger.error(f"播放音频出错: {e}")
            self.playing = False

    def stop(self):
        """
        设置停止标志。
        """
        if self.playing:
            self.stop_event.set()

    def is_playing(self):
        """
        获取播放状态。
        """
        return self.playing or pygame.mixer.music.get_busy()

    def shutdown(self):
        """
        关闭播放器。
        """
        pygame.mixer.quit()
