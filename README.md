# Robot 智能语音助手 (Bailing 架构版)

这是一个参考 `bailing` 项目架构重新编写的智能语音对话机器人。它集成了最新的开源模型，实现了流畅的全双工语音交互体验。

## 核心特性

- **ASR (语音识别)**: 使用 `FunASR` 实现高精度实时语音转文字。
- **VAD (语音活动检测)**: 使用 `Silero-VAD` 进行毫秒级人声检测。
- **LLM (大语言模型)**: 接入 `DeepSeek-V3.2` API 处理输入并生成响应。
- **TTS (语音合成)**: 使用 `Edge-TTS` 提供自然流畅的语音输出。
- **核心控制器 (Robot)**: 负责任务和记忆管理，智能处理用户的打断请求，实现模块间的无缝衔接。

## 环境依赖

请确保安装了以下依赖：
```bash
pip install funasr modelscope torch numpy pyaudio edge-tts pygame requests
```

## 运行方法

```bash
python main.py
```

## 交互说明

- 启动后，机器人将处于静默监听状态。
- 说出唤醒词 **"小艺小艺"** 即可打断机器人当前的动作并开始新的对话。
- 机器人在说话时，您可以随时说话进行打断。
