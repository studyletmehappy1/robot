import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from modules.asr import ASRModule
from modules.kws import KWSModule
from modules.llm import LLMModule
from modules.player import PlayerModule
from modules.recorder import RecorderModule
from modules.tts import TTSModule
from modules.vad import VADModule

logger = logging.getLogger(__name__)

SENTENCE_CUT_PUNCTUATIONS = ("。", "？", "！", ".", "?", "!", "；", ";")
FIRST_SENTENCE_EXTRA_PUNCTUATIONS = ("，", ",", "：", ":")


class Robot:
    def __init__(self, api_key, wake_word="小艺小艺"):
        logger.info("正在初始化机器人系统 (KWS 唤醒模式)...")
        self.wake_word = wake_word
        self.api_key = api_key

        self.kws = KWSModule()
        self.asr = ASRModule()
        self.vad = VADModule()
        self.llm = LLMModule(api_key=api_key)
        self.tts = TTSModule()
        self.player = PlayerModule()
        self.recorder = RecorderModule()

        self.audio_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=5)

        self.is_running = False
        self.stop_event = threading.Event()
        self.chat_lock = False
        self.speech_buffer = []

        self.state = "SLEEP"
        self.silence_chunks = 0
        self.max_silence_chunks = 60
        self.streaming_text = ""

        self.messages = [{"role": "system", "content": self.llm.create_system_prompt()}]
        logger.info("机器人系统初始化完成。当前状态: %s", self.state)

    def _tts_worker(self):
        while not self.stop_event.is_set():
            try:
                future, action = self.tts_queue.get(timeout=1)
                audio_results = future.result() or []
                for _, audio_file in audio_results:
                    if audio_file:
                        self.player.play(audio_file)
                        self.tts.clean_up(audio_file)
                if action:
                    self.dispatch_action(action)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("TTS 播放线程出错: %s", exc)

    def _has_pending_action_marker(self, text):
        return max(text.rfind("("), text.rfind("（")) > max(text.rfind(")"), text.rfind("）"))

    def _should_flush_segment(self, chunk, is_first_sentence):
        punctuations = list(SENTENCE_CUT_PUNCTUATIONS)
        if is_first_sentence:
            punctuations.extend(FIRST_SENTENCE_EXTRA_PUNCTUATIONS)
        return any(punctuation in chunk for punctuation in punctuations)

    def _queue_tts(self, text, action="无动作"):
        if not text:
            return
        future = self.executor.submit(self.tts.to_tts_many, text)
        action_value = action if action and action != "无动作" else None
        self.tts_queue.put((future, action_value))

    def dispatch_action(self, action):
        if not action or action == "无动作":
            return
        logger.info("动作占位分发: %s", action)

    def interrupt(self):
        if self.player.is_playing() or self.chat_lock:
            logger.info("检测到打断信号，停止播放和思考。")
            self.player.stop()
            self.chat_lock = False
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                except queue.Empty:
                    break
            return True
        return False

    def process_speech_text(self, text):
        self.speech_buffer = []
        if not text or not text.strip():
            self.state = "SLEEP"
            return

        logger.info("最终识别结果: %s", text)
        self.chat_lock = True
        self.executor.submit(self.chat, text)

    def chat(self, text):
        self.messages[0] = {"role": "system", "content": self.llm.create_system_prompt()}
        self.messages.append({"role": "user", "content": text})

        if len(self.messages) > 21:
            self.messages = [self.messages[0]] + self.messages[-20:]

        logger.info("正在请求 LLM 生成响应...")
        response_text = ""
        sentence_buffer = ""
        is_first_sentence = True
        action_queued = False

        try:
            for chunk in self.llm.call_deepseek_api(self.messages):
                if not self.chat_lock:
                    break

                response_text += chunk
                sentence_buffer += chunk

                if self._should_flush_segment(chunk, is_first_sentence):
                    if self._has_pending_action_marker(sentence_buffer):
                        continue

                    segment = sentence_buffer.strip()
                    if segment:
                        reply_text, action = self.llm.extract_reply_and_action(segment)
                        if reply_text:
                            self._queue_tts(reply_text, action)
                            is_first_sentence = False
                            if action != "无动作":
                                action_queued = True
                        elif action != "无动作":
                            self.dispatch_action(action)
                            action_queued = True
                    sentence_buffer = ""

            if sentence_buffer.strip() and self.chat_lock:
                reply_text, action = self.llm.extract_reply_and_action(sentence_buffer.strip())
                if reply_text:
                    self._queue_tts(reply_text, action)
                    if action != "无动作":
                        action_queued = True
                elif action != "无动作":
                    self.dispatch_action(action)
                    action_queued = True

            clean_response, final_action = self.llm.extract_reply_and_action(response_text)
            if clean_response:
                self.messages.append({"role": "assistant", "content": clean_response})

            if final_action != "无动作" and not action_queued:
                self.dispatch_action(final_action)
        except Exception as exc:
            logger.error("对话处理出错: %s", exc)
        finally:
            self.chat_lock = False
            self.state = "SLEEP"
            logger.info("对话结束，系统进入 SLEEP 状态监听唤醒词。")

    def run(self):
        self.is_running = True
        self.recorder.start_recording(self.audio_queue)
        threading.Thread(target=self._tts_worker, daemon=True).start()

        logger.info("机器人主循环已启动。当前状态: %s", self.state)

        try:
            while not self.stop_event.is_set():
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)

                    if self.state == "SLEEP":
                        keyword = self.kws.detect(audio_chunk)
                        if keyword:
                            print(f"\n\033[92m[唤醒] 检测到唤醒词: {keyword}，正在倾听...\033[0m")
                            self.state = "AWAKE"
                            self.interrupt()
                            self.asr.reset_cache()
                            self.streaming_text = ""
                            self.silence_chunks = 0

                    elif self.state == "AWAKE":
                        has_speech = self.vad.is_speech(audio_chunk)

                        if has_speech:
                            self.silence_chunks = 0
                            text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                            if text_chunk:
                                self.streaming_text += text_chunk
                                print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)
                        else:
                            self.silence_chunks += 1
                            text_chunk = self.asr.transcribe_chunk(audio_chunk, is_final=False)
                            if text_chunk:
                                self.streaming_text += text_chunk
                                print(f"\r[正在识别] {self.streaming_text}", end="", flush=True)

                            if self.silence_chunks > self.max_silence_chunks:
                                print()
                                print("\033[92m\n[系统] 听您说完了，正在思考中...\033[0m")
                                final_chunk = self.asr.transcribe_chunk(b"", is_final=True)
                                if final_chunk:
                                    self.streaming_text += final_chunk

                                final_text = self.streaming_text
                                self.state = "PROCESSING"
                                threading.Thread(
                                    target=self.process_speech_text,
                                    args=(final_text,),
                                    daemon=True,
                                ).start()
                except queue.Empty:
                    continue
                except Exception as exc:
                    logger.error("主循环出错: %s", exc)
        except KeyboardInterrupt:
            logger.info("收到退出指令。")
        finally:
            self.shutdown()

    def shutdown(self):
        self.stop_event.set()
        self.recorder.shutdown()
        self.player.shutdown()
        self.executor.shutdown(wait=False)
        logger.info("系统已安全关闭。")
