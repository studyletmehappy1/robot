import logging
import pyaudio
import threading
import queue

logger = logging.getLogger(__name__)

class RecorderModule:
    def __init__(self, rate=16000, channels=1, chunk=512):
        logger.info(f"正在初始化录音模块 (采样率: {rate}, 通道数: {channels}, 块大小: {chunk})...")
        self.rate = rate
        self.channels = channels
        self.chunk = chunk
        self.format = pyaudio.paInt16
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.recording_thread = None
        self.audio_queue = None
        logger.info("录音模块初始化完成。")

    def _record_thread(self):
        """
        后台录音线程。
        """
        self.stream = self.pyaudio_instance.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        
        while self.is_recording:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                if self.audio_queue:
                    self.audio_queue.put(data)
            except Exception as e:
                logger.error(f"录音线程读取出错: {e}")
                break
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def start_recording(self, audio_queue):
        """
        启动录音。
        """
        if self.is_recording:
            return
        
        self.audio_queue = audio_queue
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._record_thread, daemon=True)
        self.recording_thread.start()
        logger.info("录音已启动。")

    def stop_recording(self):
        """
        停止录音。
        """
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        logger.info("录音已停止。")

    def shutdown(self):
        """
        释放资源。
        """
        self.stop_recording()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
