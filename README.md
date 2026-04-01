# Robot 智能语音助手 (Bailing 架构版)

这是一个参考 `bailing` 项目架构重新编写的智能语音对话机器人。它集成了最新的开源模型，实现了流畅的全双工语音交互体验。

## 核心特性

- **ASR (语音识别)**: 使用 `FunASR` 实现高精度实时语音转文字。
- **VAD (语音活动检测)**: 使用 `Silero-VAD` 进行毫秒级人声检测。
- **LLM (大语言模型)**: 接入 `DeepSeek-V3.2` API 处理输入并生成响应。
- **TTS (语音合成)**: 使用 `Edge-TTS` 提供自然流畅处语音输出。
- **核心控制器 (Robot)**: 负责任务和记忆管理，智能处理用户的打断请求，实现模块间的无缝衔接。
- **动态环境感知**: 机器人现在能够准确识别当前的北京时间和深圳实时天气。
- **输出规范化**: 强制要求模型不输出 Emoji 和 Markdown 格式，专为语音播报优化。
- **全双工打断**: 无论是终端模式还是 Web 模式，均支持在播报中途通过新输入进行打断。

## 2026-04-01 性能与稳定性优化更新

针对 CPU 算力不足导致的音频积压及 VAD 检测不精准问题，进行了以下深度优化：

1.  **全面开启 GPU 极限加速**:
    *   在 `ASR` 和 `VAD` 模块中增加了硬件检测逻辑，优先使用 `CUDA` 加速。
    *   强制将 `FunASR` 的 `AutoModel` 和 `Silero-VAD` 推理挂载到 GPU 上，极大提升了识别速度，彻底解决音频队列积压问题。
2.  **优化 VAD 尾点检测逻辑**:
    *   将 `max_silence_chunks` 从 10 增加到 **60**（约 1.92 秒），提供更自然的停顿空间，防止话没说完就被截断。
    *   新增高亮日志：在检测到说话结束并提交 LLM 思考时，终端会打印 `[系统] 听您说完了，正在思考中...`，方便实时掌握交互状态。
3.  **提升 VAD 抗噪稳定性**:
    *   将 VAD 默认阈值 `threshold` 从 0.5 提高到 **0.65**，有效过滤环境底噪（如风扇声），确保静音结算更加精准。
4.  **净化终端日志**:
    *   初始化 ASR 时启用了 `disable_pbar=True`，屏蔽了冗余的进度条和 `rtf_avg` 日志，使调试界面更加清爽。

---

## 运行环境要求

- **操作系统**: Windows, macOS 或 Linux (推荐 Ubuntu 20.04+)
- **Python 版本**: **Python 3.10** 或 **Python 3.11** (推荐 3.10.x)
- **硬件要求**: 至少 4GB 内存，推荐具备音频采集（麦克风）和播放（扬声器）设备。**推荐配备支持 CUDA 的 NVIDIA GPU 以获得最佳性能。**

---

## 环境搭建指南

### 1. 安装系统依赖 (Linux/Ubuntu 用户)

由于涉及音频采集和播放，需要安装以下系统库：
```bash
sudo apt-get update
sudo apt-get install -y libasound2-dev libportaudio2 portaudio19-dev build-essential gcc g++
```

### 2. 创建并激活虚拟环境 (推荐)

使用 Conda 或 venv 创建环境：
```bash
# 使用 Conda
conda create -n robot_env python=3.10
conda activate robot_env

# 或使用 venv
python3.10 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 3. 安装 Python 依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 运行方法

### 1. 终端语音模式 (全双工对话)
适合本地测试，支持唤醒词“小艺小艺”。
```bash
python main.py
```

### 2. Web 测试端 (浏览器交互)
适合服务器远程部署测试，监听 **8000** 端口。
```bash
python server.py
```
启动后访问：`http://服务器IP:8000`

---

## 项目结构说明

- `main.py`: 终端语音交互入口。
- `server.py`: Web 测试端入口。
- `robot.py`: 核心调度类，负责打断逻辑与状态管理。
- `modules/`: 核心技术模块封装 (ASR, VAD, LLM, TTS, Player, Recorder)。
- `static/`: Web 端前端界面文件。
- `test_llm.py`: LLM 响应格式与功能测试脚本。

## 交互说明

- **唤醒词**: 说出 **"小艺小艺"** 即可打断机器人当前的动作并开始新的对话。
- **即时打断**: 机器人在说话或思考时，您可以随时说话进行打断，它会立即响应您的最新指令。
