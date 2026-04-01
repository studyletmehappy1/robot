# Robot 智能语音助手 (Bailing 架构版)

这是一个参考 `bailing` 项目架构重新编写的智能语音对话机器人。它集成了最新的开源模型，实现了流畅的全双工语音交互体验。

## 核心特性

- **ASR (语音识别)**: 使用 `FunASR` 实现高精度实时语音转文字，支持 **GPU 硬件加速**，识别速度远超人类语速。
- **VAD (语音活动检测)**: 使用 `Silero-VAD` 进行毫秒级人声检测，支持 **异步处理** 逻辑，确保交互灵敏。
- **LLM (大语言模型)**: 接入 `DeepSeek-V3.2` API 处理输入并生成响应。
- **TTS (语音合成)**: 使用 `Edge-TTS` 提供自然流畅的语音输出。
- **核心控制器 (Robot)**: 负责任务和记忆管理，智能处理用户的打断请求，实现模块间的无缝衔接。
- **动态环境感知**: 机器人现在能够准确识别当前的北京时间和深圳实时天气。
- **输出规范化**: 强制要求模型不输出 Emoji 和 Markdown 格式，专为语音播报优化。
- **全双工打断**: 无论是终端模式还是 Web 模式，均支持在播报中途通过新输入进行打断。

## 性能与稳定性优化

针对最新系列显卡（如 RTX 50 系列）及 CPU 算力不足导致的音频积压问题，进行了以下深度优化：

1.  **硬件加速与容错降级**:
    *   **ASR 模块**: 优先使用 `CUDA` 加速。新增 **GPU 容错降级逻辑**：若检测到显卡架构不兼容（常见于 RTX 50 系列用户安装旧版 CUDA），系统将自动打印高亮警告并降级至 CPU 运行，确保程序不崩溃。
    *   **VAD 模块**: 强制运行在 **CPU** 上。由于 Silero-VAD 模型极其轻量，CPU 推理已足够快，且能彻底避开显卡架构的 CUDA 指令集兼容问题。
2.  **优化 VAD 尾点检测逻辑**:
    *   将 `max_silence_chunks` 提升至 **60**（约 1.92 秒），提供更自然的停顿空间。
    *   新增高亮日志：在触发 LLM 思考时，终端会打印 `[系统] 听您说完了，正在思考中...`。
3.  **提升 VAD 抗噪稳定性**:
    *   将 VAD 默认阈值 `threshold` 提高到 **0.65**，有效过滤环境底噪。
4.  **净化终端日志**:
    *   屏蔽了冗余的 ASR 进度条和 `rtf_avg` 日志，使界面更加清爽。

---

## 运行环境要求

- **操作系统**: Windows, macOS 或 Linux (推荐 Ubuntu 20.04+)
- **Python 版本**: **Python 3.10** 或 **Python 3.11**
- **硬件要求**: 
    *   **推荐配置**: 配备 **NVIDIA 独立显卡**（如 RTX 30/40/50 系列）以开启 GPU 加速。
    *   **排坑提示**: 对于 **RTX 50 系列** 等最新架构显卡，若使用旧版 CUDA (如 12.1) 可能会触发 `no kernel image is available` 报错。强烈建议安装 **CUDA 12.4 (`cu124`)** 或以上版本的 PyTorch。

---

## 环境搭建指南

### 1. 安装系统依赖 (Linux/Ubuntu 用户)

```bash
sudo apt-get update
sudo apt-get install -y libasound2-dev libportaudio2 portaudio19-dev build-essential gcc g++
```

### 2. 安装 PyTorch (区分 CPU/GPU)

根据您的硬件选择安装方式：

*   **GPU 版本 (推荐, 针对 RTX 30/40/50 系列用户)**:
    使用国内镜像高速安装 **CUDA 12.4** 版本（推荐新显卡用户）：
    ```bash
    pip install torch torchvision torchaudio --index-url https://mirrors.aliyun.com/pytorch-wheels/cu124
    ```
*   **CPU 版本**:
    ```bash
    pip install torch torchvision torchaudio
    ```

### 3. 安装其他依赖

```bash
pip install -r requirements.txt
```

---

## 验证 GPU 加速是否开启

在安装完环境后，可以运行以下命令检查：
```bash
python -c "import torch; print(torch.cuda.is_available())"
```
*   输出 `True`: 代表显卡加速环境配置成功，ASR 将自动开启 GPU 加速。
*   输出 `False`: 代表当前运行在 CPU 模式。

---

## 运行方法

### 1. 终端语音模式 (全双工对话)
```bash
python main.py
```

### 2. Web 测试端 (浏览器交互)
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
