import asyncio
import logging
import os
import re
import time

import edge_tts

logger = logging.getLogger(__name__)


class TTSModule:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural", rate="+0%", max_chunk_chars=80):
        logger.info("正在初始化 TTS 模块 (voice=%s, rate=%s)...", voice, rate)
        self.voice = voice
        self.rate = rate
        self.max_chunk_chars = max_chunk_chars
        self.output_dir = "temp_audio"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info("TTS 模块初始化完成。")

    async def _generate_audio(self, text, output_file):
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await communicate.save(output_file)

    def _build_output_path(self, prefix):
        filename = f"{prefix}_{time.time_ns()}.mp3"
        return os.path.join(self.output_dir, filename)

    def _hard_split(self, text, max_chars):
        text = text.strip()
        if not text:
            return []

        chunks = []
        separators = ("，", ",", "；", ";", "：", ":", " ")
        remaining = text

        while len(remaining) > max_chars:
            split_at = -1
            for separator in separators:
                candidate = remaining.rfind(separator, 0, max_chars + 1)
                if candidate > split_at:
                    split_at = candidate

            if split_at <= 0:
                split_at = max_chars

            chunk = remaining[:split_at].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[split_at:].strip()

        if remaining:
            chunks.append(remaining)

        return chunks

    def split_for_tts(self, text, max_chars=None):
        if not text or not text.strip():
            return []

        max_chars = max_chars or self.max_chunk_chars
        normalized = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"([。！？；：，,.!?;:])", normalized)

        sentence_like_parts = []
        index = 0
        while index < len(parts):
            content = parts[index].strip()
            punctuation = parts[index + 1] if index + 1 < len(parts) else ""
            piece = f"{content}{punctuation}".strip()
            if piece:
                sentence_like_parts.append(piece)
            index += 2

        if not sentence_like_parts and normalized:
            sentence_like_parts = [normalized]

        chunks = []
        current = ""
        for piece in sentence_like_parts:
            if len(piece) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._hard_split(piece, max_chars))
                continue

            if not current:
                current = piece
            elif len(current) + len(piece) <= max_chars:
                current = f"{current}{piece}"
            else:
                chunks.append(current.strip())
                current = piece

        if current:
            chunks.append(current.strip())

        return [chunk for chunk in chunks if chunk]

    def _finalize_audio_file(self, output_path, segment):
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path

        logger.error("TTS 未生成有效音频，片段内容: %s", segment)
        if os.path.exists(output_path):
            self.clean_up(output_path)
        return None

    def _generate_single_sync(self, segment):
        output_path = self._build_output_path("tts")
        try:
            asyncio.run(self._generate_audio(segment, output_path))
            return self._finalize_audio_file(output_path, segment)
        except Exception as exc:
            logger.error("TTS 生成出错，片段内容: %s, error=%s", segment, exc)
            if os.path.exists(output_path):
                self.clean_up(output_path)
            return None

    async def _generate_single_async(self, segment):
        output_path = self._build_output_path("tts_async")
        try:
            await self._generate_audio(segment, output_path)
            return self._finalize_audio_file(output_path, segment)
        except Exception as exc:
            logger.error("异步 TTS 生成出错，片段内容: %s, error=%s", segment, exc)
            if os.path.exists(output_path):
                self.clean_up(output_path)
            return None

    def to_tts_many(self, text):
        results = []
        for segment in self.split_for_tts(text):
            audio_file = self._generate_single_sync(segment)
            if audio_file:
                results.append((segment, audio_file))
        return results

    async def to_tts_many_async(self, text):
        results = []
        for segment in self.split_for_tts(text):
            audio_file = await self._generate_single_async(segment)
            if audio_file:
                results.append((segment, audio_file))
        return results

    def to_tts(self, text):
        results = self.to_tts_many(text)
        if results:
            return results[0][1]
        return None

    async def to_tts_async(self, text):
        results = await self.to_tts_many_async(text)
        if results:
            return results[0][1]
        return None

    def clean_up(self, file_path):
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as exc:
                logger.error("清理 TTS 文件失败: %s", exc)
