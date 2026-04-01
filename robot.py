import logging
import queue
import threading
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor

from modules.asr import ASRModule
from modules.vad import VADModule
from modules.llm import LLMModule
from modules.tts import TTSModule
from modules.player import PlayerModule
from modules.recorder import RecorderModule

logger = logging.getLogger(__name__)

class Robot:
    def __init__(self, api_key, wake_word="小艺小艺"):
        logger.info("正在初始化机器人系统...")
        self.wake_word = wake_word
        self.api_key = api_key
        
        # 初始化各个模块
        self.asr = ASRModule()
        self.vad = VADModule()
        self.llm = LLMModule(api_key=api_key)
        self.tts = TTSModule()
        self.player = PlayerModule()
        self.recorder = RecorderModule()
        
        # 队列和线程池
        self.audio_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # 状态管理
        self.is_running = False
        self.stop_event = threading.Event()
        self.chat_lock = False
        self.speech_buffer = []
        self.vad_start = False
        self.silence_chunks = 0
        self.max_silence_chunks = 10  # 约 320ms 静音判定结束
        
        # 记忆管理 (简单实现)
        self.messages = [
            {"role": "system", "content": self.llm.create_system_prompt()}
        ]
        
        logger.info("机器人系统初始化完成。")

    def _tts_worker(self):
        """
        后台播放工作线程。
        """
        while not self.stop_event.is_set():
            try:
                future = self.tts_queue.get(timeout=1)
                audio_file = future.result()
                if audio_file:
                    self.player.play(audio_file)
                    self.tts.clean_up(audio_file)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS 播放线程出错: {e}")

    def interrupt(self):
        """
        打断当前的播放和思考逻辑。
        """
        if self.player.is_playing() or self.chat_lock:
            logger.info("检测到打断信号，停止播放和思考...")
            self.player.stop()
            self.chat_lock = False
            # 清理 TTS 队列
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                except queue.Empty:
                    break
            return True
        return False

    def process_speech(self):
        """
        处理收集到的语音片段。
        """
        if not self.speech_buffer:
            return
        
        full_audio = b"".join(self.speech_buffer)
        self.speech_buffer = []
        
        # ASR 识别
        text = self.asr.transcribe(full_audio)
        if not text or not text.strip():
            return
        
        logger.info(f"识别结果: {text}")
        
        # 唤醒词过滤逻辑 (简单实现)
        if self.wake_word in text:
            # 如果在说话中，触发打断
            self.interrupt()
            # 剔除唤醒词
            text = text.replace(self.wake_word, "").strip()
            if not text:
                # 仅唤醒，可以回复一个打招呼
                text = "你好，请问有什么可以帮您的？"
                future = self.executor.submit(self.tts.to_tts, text)
                self.tts_queue.put(future)
                return
        
        # 如果当前不是在听状态 (比如 IDLE)，且没有唤醒词，则忽略
        # 这里简化逻辑，默认全双工监听
        
        self.chat_lock = True
        self.executor.submit(self.chat, text)

    def chat(self, text):
        """
        处理对话逻辑。
        """
        # 每次对话前动态更新一次系统提示词以同步最新时间
        self.messages[0] = {"role": "system", "content": self.llm.create_system_prompt()}
        self.messages.append({"role": "user", "content": text})
        
        # 限制上下文长度
        if len(self.messages) > 21:
            self.messages = [self.messages[0]] + self.messages[-20:]
            
        logger.info("正在请求 LLM 生成响应...")
        response_text = ""
        sentence_buffer = ""
        
        try:
            # 这里的 call_deepseek_api 需要修复 header 拼写错误
            for chunk in self.llm.call_deepseek_api(self.messages):
                if not self.chat_lock: # 被打断了
                    break
                
                response_text += chunk
                sentence_buffer += chunk
                
                # 简单的句子分割逻辑 (。？！. ? !)
                if any(p in chunk for p in ["。", "？", "！", ".", "?", "!"]):
                    segment = sentence_buffer.strip()
                    if segment:
                        # 提交 TTS 任务
                        future = self.executor.submit(self.tts.to_tts, segment)
                        self.tts_queue.put(future)
                    sentence_buffer = ""
            
            # 处理剩余部分
            if sentence_buffer.strip() and self.chat_lock:
                future = self.executor.submit(self.tts.to_tts, sentence_buffer.strip())
                self.tts_queue.put(future)
                
            if response_text:
                self.messages.append({"role": "assistant", "content": response_text})
                
        except Exception as e:
            logger.error(f"对话处理出错: {e}")
        finally:
            self.chat_lock = False

    def run(self):
        """
        主循环。
        """
        self.is_running = True
        self.recorder.start_recording(self.audio_queue)
        
        # 启动后台线程
        threading.Thread(target=self._tts_worker, daemon=True).start()
        
        logger.info("机器人主循环已启动，正在监听...")
        
        try:
            while not self.stop_event.is_set():
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    has_speech = self.vad.is_speech(audio_chunk)
                    
                    if has_speech:
                        if not self.vad_start:
                            logger.info("检测到人声开始...")
                            self.vad_start = True
                            # 如果正在说话，立即打断
                            self.interrupt()
                        
                        self.speech_buffer.append(audio_chunk)
                        self.silence_chunks = 0
                    else:
                        if self.vad_start:
                            self.speech_buffer.append(audio_chunk)
                            self.silence_chunks += 1
                            
                            if self.silence_chunks > self.max_silence_chunks:
                                logger.info("检测到人声结束，准备处理...")
                                self.vad_start = False
                                self.silence_chunks = 0
                                # 异步处理语音
                                threading.Thread(target=self.process_speech, daemon=True).start()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"主循环出错: {e}")
                    
        except KeyboardInterrupt:
            logger.info("收到退出指令...")
        finally:
            self.shutdown()

    def shutdown(self):
        """
        关闭系统。
        """
        self.stop_event.set()
        self.recorder.shutdown()
        self.player.shutdown()
        self.executor.shutdown(wait=False)
        logger.info("系统已安全关闭。")
