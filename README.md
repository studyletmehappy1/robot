# Robot 智能语音助手 (Bailing 架构版)

这是一个参考 `bailing` 项目架构重新编写的智能语音对话机器人。它集成了最新的开源模型，实现了流畅的全双工语音交互体验。

## 核心特性

- **ASR (语音识别)**: 使用 `FunASR` 实现高精度实时语音转文字。
- **VAD (语音活动检测)**: 使用 `Silero-VAD` 进行毫秒级人声检测。
- **LLM (大语言模型)**: 接入 `DeepSeek-V3.2` API 处理输入并生成响应。
- **TTS (语音合成)**: 使用 `Edge-TTS` 提供自然流畅的语音输出。
- **核心控制器 (Robot)**: 负责任务和记忆管理，智能处理用户的打断请求，实现模块间的无缝衔接。
- **动态环境感知**: 机器人现在能够准确识别当前的北京时间和深圳实时天气。
- **输出规范化**: 强制要求模型不输出 Emoji 和 Markdown 格式，专为语音播报优化。
- **全双工打断**: 无论是终端模式还是 Web 模式，均支持在播报中途通过新输入进行打断。

---

## 运行环境要求 (重要)

- **操作系统**: Windows, macOS 或 Linux (推荐 Ubuntu 20.04+)
- **Python 版本**: **必须使用 Python 3.11.x** (低于此版本会导致依赖安装失败)
- **硬件要求**: 至少 4GB 内存，推荐具备音频采集（麦克风）和播放（扬声器）设备。

---

## 环境搭建指南

### 1. 安装系统依赖 (Linux/Ubuntu 用户)

由于涉及音频采集和播放，需要安装以下系统库：
```bash
sudo apt-get update
sudo apt-get install -y libasound2-dev libportaudio2 portaudio19-dev build-essential gcc g++ python3.11-dev
```

### 2. 创建并激活虚拟环境 (推荐)

使用 Conda 或 venv 创建环境：
```bash
# 使用 Conda (推荐)
conda create -n robot_env python=3.11
conda activate robot_env

# 或使用 venv
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 3. 安装 Python 依赖 (推荐使用清华源加速)

```bash
pip install --upgrade pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
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

## 常见问题排查

1. **报错: Could not find a version that satisfies the requirement EOF**
   - 原因: 之前的 requirements.txt 曾被错误写入 EOF 字符。
   - 解决: 当前版本已物理修复，请确保拉取的是最新 master 分支代码。
2. **报错: Requires-Python >=3.11**
   - 原因: FunASR 和部分依赖库要求 Python 3.11 及以上版本。
   - 解决: 请确保 `python --version` 显示为 3.11.x，推荐使用 Conda 重新创建 3.11 环境。
