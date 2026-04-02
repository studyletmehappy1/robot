# Robot 智能语音助手 (Bailing 架构版)

这是一个参考 `bailing` 项目架构重新编写的智能语音对话机器人。它集成了最新的开源模型，实现了流畅的全双工语音交互体验。

## 核心特性

- **ASR (语音识别)**: 使用 `FunASR` 实现高精度实时语音转文字，支持 **GPU 硬件加速**。
- **VAD (语音活动检测)**: 使用 `Silero-VAD` 进行毫秒级人声检测，支持 **异步处理** 逻辑。
- **LLM (大语言模型)**: 接入 `DeepSeek-V3.2` API 处理输入并生成响应。
- **TTS (语音合成)**: 使用 `Edge-TTS` 提供自然流畅的语音输出。
- **Web 流式交互**: 支持浏览器端实时麦克风收音，通过 WebSocket 与后端进行流式音频与文本交换。
- **全双工打断**: 无论是终端模式还是 Web 模式，均支持在播报中途通过新输入进行打断。

## 性能与稳定性优化

1.  **硬件加速与容错**: ASR 模块优先使用 `CUDA`，并具备自动降级至 CPU 的容错机制。
2.  **Web 实时音频流**: 升级了 `server.py` 和 `index.html`，实现基于 Web Audio API 的 16kHz 采样率实时录音与流式识别。
3.  **VAD 优化**: 提高了抗噪阈值至 **0.65**，并将静音切断时间优化为约 1.92 秒。

---

## 运行环境要求

- **操作系统**: Windows, macOS 或 Linux (推荐 Ubuntu 20.04+)
- **Python 版本**: **Python 3.10** 或 **Python 3.11**
- **硬件要求**: 
    *   **推荐配置**: 配备 **NVIDIA 独立显卡**（RTX 系列）以开启 GPU 加速。
    *   **显卡选型提示**: 
        *   **RTX 50 系列**: 必须安装 **CUDA 12.4 (`cu124`)** 或以上版本的 PyTorch。
        *   **RTX 20/30/40 系列**: 推荐安装兼容性最佳的 **CUDA 12.1 (`cu121`)**。

---

## 环境搭建指南

### 1. 安装系统依赖

*   **Linux/Ubuntu 用户**:
    ```bash
    sudo apt-get update
    sudo apt-get install -y libasound2-dev libportaudio2 portaudio19-dev build-essential gcc g++
    ```
*   **Windows 用户**:
    *   无需安装上述 Linux 系统库。
    *   直接执行 `pip install -r requirements.txt`。
    *   **排坑**: 若安装 `pyaudio` 失败，请尝试执行：
        ```bash
        pip install pipwin
        pipwin install pyaudio
        ```

### 2. 安装 PyTorch (区分显卡型号)

请根据您的显卡型号选择对应的国内镜像高速安装命令：

*   **RTX 50 系列等最新架构**:
    ```bash
    pip install torch torchvision torchaudio --index-url https://mirrors.nju.edu.cn/pytorch/whl/cu124
    ```
*   **RTX 20 / 30 / 40 系列 (如 2060S, 3060, 4090)**:
    ```bash
    pip install torch torchvision torchaudio --index-url https://mirrors.nju.edu.cn/pytorch/whl/cu121 --extra-index-url https://mirrors.aliyun.com/pypi/simple/ --default-timeout=60 --no-cache-dir
    ```
*   **CPU 用户**:
    ```bash
    pip install torch torchvision torchaudio
    ```

### 3. 安装其他依赖

```bash
pip install -r requirements.txt
```

---

## 运行方法

### 1. 终端语音模式 (本地全双工对话)
适合本地测试，使用本地麦克风和扬声器。
```bash
python main.py
```

### 2. Web 流式模式 (浏览器交互)
支持远程访问，通过浏览器麦克风进行交互。
```bash
python server.py
```
启动后访问：`http://localhost:8000`

**注意**: 若内网 IP 访问无法调用麦克风，请在 Chrome 浏览器地址栏输入：
`chrome://flags/#unsafely-treat-insecure-origin-as-secure`
将当前地址加入白名单并开启。

---

## 验证 GPU 加速是否开启

```bash
python -c "import torch; print(torch.cuda.is_available())"
```
输出 `True` 即代表显卡加速成功。

## 🛠️ 常见问题与架构修补记录 (Troubleshooting)

在项目从单机终端向 Web 端/前后端分离架构迁移的过程中，我们修复了以下核心兼容性问题：

### 1. Web 录音流导致 VAD 模块崩溃
* **现象**：浏览器发送 4096 字节的音频大包，导致底层 Silero-VAD 维度不匹配报错。
* **修复方案**：在 `modules/vad.py` 中引入“循环切片机”，将大尺寸 PCM 数据流动态切分为标准的 512 字节小块，无缝兼容本地小包与 Web 大包。

### 2. TTS 语音合成在 Web 模式下死锁
* **现象**：FastAPI (Uvicorn) 环境下运行 `asyncio.run()` 引发事件循环冲突，导致生成音频时程序卡死，前端一直显示“正在识别”。
* **修复方案**：重构 `modules/tts.py`，加入环境探测机制。若处于异步事件循环中，则使用 `ThreadPoolExecutor` 将 TTS 任务剥离到独立线程；若处于本地终端模式，则正常运行。

### 3. KWS 唤醒词解析失败 (Cannot find ID for token)
* **现象**：`sherpa-onnx` 初始化时报错无法识别中文连续词组。
* **修复方案**：WenetSpeech 模型的 `tokens.txt` 为拼音级词典。必须将 `keywords.txt` 配置严格改为 `拼音(带空格) @ 输出中文字符` 的格式。
  * ❌ 错误格式：`小艺小艺 @ x iǎo y ì x iǎo y ì`
  * ✅ 正确格式：`x iǎo y ì x iǎo y ì @小艺小艺`

### 4. 硬盘爆满与无声音反馈
* **现象**：`temp_audio/` 目录下产生大量 MP3 堆积，且 Web 前端无声音播放。
* **修复方案**：确保服务端在调用 TTS 后，以 `rb` (二进制) 模式读取文件，并通过 `websocket.send_bytes()` 推送给前端浏览器，**推送完成后必须立刻执行 `os.remove()` 清理临时文件**。
