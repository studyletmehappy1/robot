import os
import logging
import urllib.request
import tarfile
import numpy as np
import sherpa_onnx

logger = logging.getLogger(__name__)

class KWSModule:
    def __init__(self, keywords_file="keywords.txt"):
        self.model_dir = "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01"
        self.keywords_file = keywords_file
        
        self._ensure_keywords_file()
        self._check_and_download_model()
        self._init_spotter()

    def _ensure_keywords_file(self):
        # 如果没有 keywords.txt，自动生成一个
        if not os.path.exists(self.keywords_file):
            with open(self.keywords_file, "w", encoding="utf-8") as f:
                # 默认唤醒词：小艺小艺。拼音之间必须有空格，@ 符号后面跟中文字符
                f.write("x iǎo y ì x iǎo y ì @小艺小艺\n")
            logger.info(f"已自动生成唤醒词配置文件: {self.keywords_file}")

    def _check_and_download_model(self):
        # 如果本地没有模型目录，则自动下载（带国内代理加速）
        if not os.path.exists(self.model_dir):
            logger.info("正在下载 KWS 极速唤醒模型 (约 3MB)，请稍候...")
            base_url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/"
            filename = "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01.tar.bz2"
            url = f"https://mirror.ghproxy.com/{base_url}{filename}"
            
            if not os.path.exists(filename):
                try:
                    urllib.request.urlretrieve(url, filename)
                except Exception as e:
                    logger.warning(f"代理下载失败，尝试原链接直连: {e}")
                    urllib.request.urlretrieve(f"{base_url}{filename}", filename)
                    
            logger.info("模型下载完成，正在解压...")
            with tarfile.open(filename, "r:bz2") as tar:
                tar.extractall(path=".")
            logger.info("唤醒模型准备完毕。")

    def _init_spotter(self):
        logger.info("正在加载 sherpa-onnx 唤醒引擎...")
        try:
            # 【修复重点】Python 版本没有 Config 类，直接传参给 KeywordSpotter
            self.kws = sherpa_onnx.KeywordSpotter(
                tokens=os.path.join(self.model_dir, "tokens.txt"),
                encoder=os.path.join(self.model_dir, "encoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
                decoder=os.path.join(self.model_dir, "decoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
                joiner=os.path.join(self.model_dir, "joiner-epoch-12-avg-2-chunk-16-left-64.onnx"),
                num_threads=1,
                keywords_file=self.keywords_file,
                provider="cpu"
            )
            # 初始化一个专属音频接收流
            self.stream = self.kws.create_stream()
            logger.info("唤醒引擎加载成功！当前处于 [SLEEP] 静默监听状态。")
        except Exception as e:
            logger.error(f"KWS 初始化失败: {e}")
            raise

    def detect(self, audio_chunk, sample_rate=16000):
        """
        接收前端或本地的 PCM 音频块，判断是否命中唤醒词
        """
        if not audio_chunk or not hasattr(self, 'kws'):
            return False

        try:
            # 1. 将网络/本地传来的 int16 字节流转换为 float32 格式 (-1.0 ~ 1.0)
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # 2. 将音频块持续喂给底层的流
            self.stream.accept_waveform(sample_rate, audio_float32)

            # 3. 驱动底层引擎进行快速解码
            while self.kws.is_ready(self.stream):
                self.kws.decode_stream(self.stream)

            # 4. 获取当前有没有匹配上的结果
            result = self.kws.get_result(self.stream)
            
            # 5. 如果不为空，说明抓到了设定的唤醒词
            if result != "":
                logger.info(f"✨ 唤醒成功！命中: {result}")
                # 【极其重要】识别到之后必须重置这条流，否则它会卡在命中状态无限循环
                self.kws.reset_stream(self.stream)
                return True

            return False
        except Exception as e:
            logger.error(f"KWS 检测出错: {e}")
            return False