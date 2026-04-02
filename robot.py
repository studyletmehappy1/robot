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
from modules.kws import KWSModule

logger = logging.getLogger(__name__)

class Robot:
    def __init__(self, api_key, wake_word="小艺小艺"):
        logger.info("正在初始化机器人系统 (KWS 唤醒模式)...")
        self.wake_word = wake_word
        self.api_key = api_key
        
        # 初始化各个模块
        self.kws = KWSModule()
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
        
        # 状态机: SLEEP (监听唤醒词), AWAKE (监听指令)
        self.state = "SLEEP"
        self.silence_chunks = 0
        self.max_silence_chunks = 60  # 约 1.92 秒静音判定结束
        self.streaming_text = ""
        
        # 记忆管理
        self.messages = [
            {"role": "system", "content": self.llm.create_system_prompt()}
        ]
        
        logger.info(f"机器人系统初始化完成。当前状态: {self.state}")

    def _tts_worker(self):
        """后台播放工作线程"""
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
        """打断当前的播放和思考逻辑"""
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

    def process_speech_text(self, text):
        """处理识别出的文本"""
        self.speech_buffer = []
        if not text or not text.strip():
            self.state = "SLEEP" # 没听清，回休眠
            return
        
        logger.info(f"最终识别结果: {text}")
        self.chat_lock = True
        self.executor.submit(self.chat, text)

    def chat(self, text):
        """处理对话逻辑"""
        self.messages[0] = {"role": "system", "content": self.llm.create_system_prompt()}
        self.messages.append({"role": "user", "content": text})
        
        if len(self.messages) > 21:
            self.messages = [self.messages[0]] + self.messages[-20:]
            
        logger.info("正在请求 LLM 生成响应...")
        response_text = ""
        sentence_buffer = ""
        
        try:
            for chunk in self.llm.call_deepseek_api(self.messages):
                if not self.chat_lock: break
                response_text += chunk
                sentence_buffer += chunk
                
                if any(p in chunk for p in ["。", "？", "！", ".", "?", "!"]):
                    segment = sentence_buffer.strip()
                    if segment:
                        future = self.executor.submit(self.tts.to_tts, segment)
                        self.tts_queue.put(future)
                    sentence_buffer = ""
            
            if sentence_buffer.strip() and self.chat_lock:
                future = self.executor.submit(self.tts.to_tts, sentence_buffer.strip())
                self.tts_queue.put(future)
                
            if response_text:
                self.messages.append({"role": "assistant", "content": response_text})
                
        except Exception as e:
            logger.error(f"对话处理出错: {e}")
        finally:
            self.chat_lock = False
            self.state = "SLEEP" # 对话结束，回休眠
            logger.info("对话结束，系统进入 SLEEP 状态监听唤醒词...")

    def run(self):
        """主循环"""
        self.is_running = True
        self.recorder.start_recording(self.audio_queue)
        threading.Thread(target=self._tts_worker, daemon=True).start()
        
        logger.info(f"机器人主循环已启动。当前状态: {self.state}")
        
        try:
            while not self.stop_event.is_set():
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    
                    if self.state == "SLEEP":
                        # 仅进行 KWS 唤醒检测
                        keyword = self.kws.detect(audio_chunk)
                        if keyword:
                            print(f"\n\033[92m[唤醒] 检测到唤醒词: {keyword}，正在倾听...\033[0m")
                            self.state = "AWAKE"
                            self.interrupt()
                            self.asr.reset_cache()
                            self.streaming_text = ""
                            self.silence_chunks = 0
                            # 播放唤醒提示音 (可选，这里简化为打印)
                            
                    elif self.state == "AWAKE":
                        # 进行 VAD 和 ASR 指令识别
                        has_speech = self.vad.is_speech(audio_chunk)
                        
                        if has_speech:
                            self.silence_chunks = 0
                            text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                            if text_chunk:
                                self.streaming_text += text_chunk
                                print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)
                        else:
                            self.silence_chunks += 1
                            # 即使在静音期间也继续识别
                            text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                            if text_chunk:
                                self.streaming_text += text_chunk
                                print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)
                            
                            if self.silence_chunks > self.max_silence_chunks:
                                print() # 换行
                                print("\033[92m\n[系统] 听您说完了，正在思考中...\033[0m")
                                final_chunk = self.asr.transcribe_chunk(b"", is_final=True)
                                if final_chunk:
                                    self.streaming_text += final_chunk
                                
                                final_text = self.streaming_text
                                # 进入处理中状态，不再接收新指令直到对话结束回 SLEEP
                                self.state = "PROCESSING" 
                                threading.Thread(target=self.process_speech_text, args=(final_text,), daemon=True).start()
                                
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"主循环出错: {e}")
                    
        except KeyboardInterrupt:
            logger.info("收到退出指令...")
        finally:
            self.shutdown()

    def shutdown(self):
        """关闭系统"""
        self.stop_event.set()
        self.recorder.shutdown()
        self.player.shutdown()
        self.executor.shutdown(wait=False)
        logger.info("系统已安全关闭。")
