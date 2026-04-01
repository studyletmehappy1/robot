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
        self.max_silence_chunks = 60  # 约 1.92 秒静音判定结束 (针对音频积压优化)
        self.streaming_text = ""  # 当前流式识别累积文本
        
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

    def process_speech_text(self, text):
        """
        处理识别出的文本。
        """
        self.speech_buffer = [] # 清理音频缓冲区
        
        if not text or not text.strip():
            return
        
        logger.info(f"最终识别结果: {text}")
        
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
                            self.streaming_text = ""
                            self.asr.reset_cache()
                            # 如果正在说话，立即打断
                            self.interrupt()
                        
                        self.speech_buffer.append(audio_chunk)
                        self.silence_chunks = 0
                        
                        # 流式 ASR 识别并打印
                        text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                        if text_chunk:
                            self.streaming_text += text_chunk
                            print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)
                    else:
                        if self.vad_start:
                            self.speech_buffer.append(audio_chunk)
                            self.silence_chunks += 1
                            
                            # 即使在静音期间，也继续尝试识别剩余部分
                            text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                            if text_chunk:
                                self.streaming_text += text_chunk
                                print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)
                            
                            if self.silence_chunks > self.max_silence_chunks:
                                print() # 换行
                                # 触发截断、准备调用 LLM 的那一刻，打印高亮日志
                                print("\033[92m\n[系统] 听您说完了，正在思考中...\033[0m")
                                logger.info("检测到人声结束，准备处理...")
                                
                                # 获取最后一部分结果
                                final_chunk = self.asr.transcribe_chunk(b"", is_final=True)
                                if final_chunk:
                                    self.streaming_text += final_chunk
                                
                                self.vad_start = False
                                self.silence_chunks = 0
                                # 异步处理语音 (这里直接传入已识别的文本)
                                final_text = self.streaming_text
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
        """
        关闭系统。
        """
        self.stop_event.set()
        self.recorder.shutdown()
        self.player.shutdown()
        self.executor.shutdown(wait=False)
        logger.info("系统已安全关闭。")
