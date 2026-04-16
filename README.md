# Robot G1 语音交互与常驻 MuJoCo 仿真

本项目当前目标是让 Unitree G1 在 `scene_29dof.xml` 中保持单个常驻 MuJoCo viewer，语音回复时根据 LLM 输出的动作暗示词触发 `wave1 / wave2 / wave3`，实现“语音播报 + 挥手动作”联动，而不是每次动作都重复新开一个 viewer。

当前阶段只做 Phase 1/2：
- 站立
- 挥手
- 语音联动

walking backend 暂未接入，后续计划切到 C++ 运动后端。

## 当前能力

- 唤醒词检测：`sherpa-onnx`
- 语音活动检测：`silero-vad`
- 语音识别：`FunASR`
- 大模型对话：`DeepSeek` 流式 API
- 语音合成：`edge-tts`
- 前端交互：`FastAPI + WebSocket`
- 仿真动作执行：单个常驻 MuJoCo runtime
- 动作种类：`wave1 / wave2 / wave3`
- 动作触发方式：
  - viewer 热键
  - HTTP 接口
  - LLM 回复中的 `(挥手1)/(挥手2)/(挥手3)` 暗示词

## 当前架构

- 语音服务：
  - [server.py](/C:/Users/HONOR/Desktop/robot_manus/server.py)
  - [robot.py](/C:/Users/HONOR/Desktop/robot_manus/robot.py)
- 动作解析与场景门控：
  - [modules/action_dispatcher.py](/C:/Users/HONOR/Desktop/robot_manus/modules/action_dispatcher.py)
- 常驻仿真 HTTP 客户端：
  - [modules/sim_runtime_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/sim_runtime_client.py)
- walking 后端预留接口：
  - [modules/motion_backend_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/motion_backend_client.py)
- 常驻 MuJoCo runtime：
  - [unitree_mujoco-main/simulate_python/g1_runtime.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_runtime.py)
- 动作资产：
  - [unitree_mujoco-main/simulate_python/g1_wave_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_wave_assets.py)
  - [unitree_mujoco-main/simulate_python/g1_stand_pose.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_stand_pose.py)
- 单动作调试脚本：
  - [unitree_mujoco-main/unitree_robots/g1/action_wave1.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/unitree_robots/g1/action_wave1.py)
  - [unitree_mujoco-main/unitree_robots/g1/action_wave2.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/unitree_robots/g1/action_wave2.py)
  - [unitree_mujoco-main/unitree_robots/g1/action_wave3.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/unitree_robots/g1/action_wave3.py)

## 当前固定约束

- G1 主场景统一使用：
  - `unitree_mujoco-main/unitree_robots/g1/scene_29dof.xml`
- 当前允许的动作暗示词只有：
  - `(挥手1)`
  - `(挥手2)`
  - `(挥手3)`
  - `(无动作)`
- 当前动作执行方式是：
  - LLM 输出暗示词
  - `action_dispatcher` 解析和过滤
  - HTTP 下发到常驻 `g1_runtime.py`
- 当前不包含：
  - walking backend
  - 先停稳再挥手
  - 移动中持续挥手

## 服务器环境要求

推荐把“常驻 MuJoCo runtime + 语音服务”都跑在同一台服务器上。当前工作机没有 MuJoCo，也不适合做完整联调。

### 1. 基础环境

- Python：推荐 `3.10`
- pip：可用
- MuJoCo：已安装并可正常导入 `mujoco`
- 系统能打开图形界面或远程桌面，能显示 MuJoCo viewer
- 网络可访问：
  - DeepSeek API
  - Edge TTS 服务
  - FunASR 首次下载模型所需源
- 若要使用本地麦克风/扬声器模式，还需要音频设备

### 2. Python 依赖

先在项目根目录创建并进入虚拟环境，然后安装依赖。

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install mujoco
```

如果你的服务器是 Linux，请把激活命令换成：

```bash
source .venv/bin/activate
```

### 3. 当前这条线真正需要的关键包

- `mujoco`
- `fastapi`
- `uvicorn`
- `requests`
- `edge-tts`
- `funasr`
- `silero-vad`
- `sherpa-onnx`
- `torch`
- `pygame`
- `pyaudio`

说明：
- `server.py` 当前会初始化 `Robot()`，而 `Robot()` 会同时初始化 `PlayerModule` 和 `RecorderModule`，所以即使你只走网页文本联调，当前版本也仍然需要 `pygame` 和 `pyaudio`。
- 当前 Phase 1/2 不依赖 `unitree_sdk2_python`。它不是本轮测试前置条件。

### 4. 模型与资源文件

仓库内已包含唤醒词模型目录：

- `sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01`

当前仓库还依赖：
- `keywords.txt`
- `unitree_mujoco-main/unitree_robots/g1/scene_29dof.xml`

FunASR 模型会在首次运行时自动拉取，所以服务器第一次跑 ASR 时需要联网。

### 5. API Key 与地址配置

当前代码里 `server.py` 和 `main.py` 仍然直接写了 `api_key`。正式上服务器前，请替换成你自己的有效 Key。

如果语音服务和 MuJoCo runtime 不在同一台机器上，可以设置：

```powershell
$env:SIM_RUNTIME_URL="http://你的运行时机器IP:18080"
```

默认值是：

```text
http://127.0.0.1:18080
```

## 启动顺序

测试时请严格按下面顺序启动，不要一开始就直接开网页。

### 第 1 步：启动常驻 MuJoCo runtime

```powershell
cd C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\simulate_python
python g1_runtime.py
```

预期现象：
- 打开一个 G1 MuJoCo viewer
- 模型加载的是 `scene_29dof.xml`
- 机器人默认站立待机
- 终端打印 `G1 runtime HTTP server started at http://127.0.0.1:18080`

### 第 2 步：先做 runtime 健康检查

在另一个终端执行：

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:18080/state
```

预期返回类似：

```json
{
  "ok": true,
  "status": "idle",
  "active_action": null,
  "last_completed_action": null,
  "sim_time": 1.2345
}
```

如果这一步失败，不要继续启动语音服务，先解决 runtime 问题。

### 第 3 步：启动语音服务

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python server.py
```

预期现象：
- FastAPI 启动成功
- 默认监听 `0.0.0.0:8000`
- 终端没有因为 `pyaudio`、`pygame`、`edge_tts`、`funasr` 导入失败而报错

### 第 4 步：打开网页端

浏览器访问：

```text
http://localhost:8000
```

## 测试执行流程

建议按“从低风险到高耦合”的顺序测试，不要直接跳到整条语音链。

### 测试 1：viewer 热键测试

目标：先验证 MuJoCo runtime 和动作资产本身没问题。

在 `g1_runtime.py` 打开的 viewer 中按键：

- `1`：触发 `wave1`
- `2`：触发 `wave2`
- `3`：触发 `wave3`
- `0`：回到中立站姿

预期现象：
- 只有一个 viewer
- 挥手时机器人保持站立
- 不会因为按热键而重新打开新窗口
- 正在执行动作时再次按 `1/2/3`，新动作会被拒绝，不会抢占当前动作

通过标准：
- 站姿稳定
- 挥手后能回中
- 没有明显前扑、侧倒、严重滑步

### 测试 2：HTTP 动作测试

目标：验证语音链路未来依赖的 HTTP 动作桥。

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18080/action -ContentType "application/json" -Body '{"action":"wave2"}'
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:18080/state
```

预期现象：
- viewer 中开始执行 `wave2`
- 返回结果中 `accepted` 为 `true`

动作执行中重复发送：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18080/action -ContentType "application/json" -Body '{"action":"wave1"}'
```

预期现象：
- 返回 `accepted=false`
- 当前动作继续执行，不被打断

### 测试 3：单动作资产调试

目标：单独调整某一个动作时使用，不走语音链路。

```powershell
cd C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1
python action_wave1.py --scene scene_29dof.xml --print-targets
python action_wave2.py --scene scene_29dof.xml --print-targets
python action_wave3.py --scene scene_29dof.xml --print-targets
```

适用场景：
- 调整单个 wave 的幅度
- 核对关节目标
- 快速回归动作资产

### 测试 4：网页文本联动测试

目标：先不测麦克风，只测“LLM 输出动作暗示词 -> 语音服务解析 -> runtime 挥手”。

操作：
1. 保持 `g1_runtime.py` 正在运行。
2. 保持 `server.py` 正在运行。
3. 打开网页。
4. 在网页中直接输入一句问候语。

建议测试语句：

```text
你好，很高兴见到你
```

预期现象：
- LLM 输出正文加动作暗示词
- 前端只显示净化后的正文
- 语音开始播报前，动作已先下发到 runtime
- viewer 中机器人在开始播报时同步挥手

反例测试：

```text
白切鸡和清远鸡有什么区别
```

预期现象：
- 正常回答问题
- 不触发挥手

### 测试 5：麦克风语音联动测试

目标：验证完整语音链。

前提：
- 服务器音频输入可用
- 浏览器麦克风权限正常

建议步骤：
1. 说唤醒词。
2. 等待进入倾听状态。
3. 说一条欢迎类句子。

建议测试语句：

```text
你好，很高兴见到你
```

预期现象：
- KWS 检测到唤醒词
- VAD 正常截断语音
- ASR 能识别出问句
- LLM 回复带动作暗示词
- TTS 开始播报时 viewer 同步挥手

## 推荐测试顺序

请按这个顺序走，出了问题更容易定位：

1. `g1_runtime.py` 能否独立启动
2. `/state` 是否可访问
3. viewer 热键能否触发动作
4. HTTP `/action` 能否触发动作
5. `server.py` 能否独立启动
6. 网页文本输入能否触发挥手
7. 麦克风语音能否完整联动

## 常见问题排查

### 1. viewer 没起来或 MuJoCo 报错

优先检查：
- `python -c "import mujoco; print(mujoco.__version__)"`
- 是否能打开图形界面
- `unitree_mujoco-main/unitree_robots/g1/scene_29dof.xml` 路径是否存在

### 2. `/state` 不通

说明 `g1_runtime.py` 没有正常启动，或者 `18080` 端口被占用。

### 3. 语音服务能回答，但机器人不挥手

优先检查：
- `SIM_RUNTIME_URL` 是否指向正确地址
- runtime 是否仍在运行
- 当前回复是否被本地规则过滤为 `(无动作)`
- runtime 是否正忙，导致新动作返回 `accepted=false`

### 4. `server.py` 启动失败，提示 `pyaudio` 或 `pygame` 缺失

当前代码路径会在 `Robot()` 初始化时加载音频录制和播放模块，所以这两个依赖现在是必需的。

### 5. 第一次启动 ASR 很慢

正常。FunASR 首次会拉取模型，需要等待下载完成。

## 当前开发阶段

### Phase 1

- 常驻仿真
- 站立
- 挥手不倒

### Phase 2

- 语音唤醒
- TTS 回复
- 同步触发常驻仿真里的挥手

### Phase 3

- 接入 C++ walking backend
- 实现“先停稳再挥手”

### Phase 4

- 如果确认需要“移动中持续挥手”，再评估 whole-body controller 或 RL 路线

## 当前限制

- 当前 runtime 不是 walking backend
- 当前没有“走路中先停稳再挥手”
- 当前没有“移动中持续挥手”
- 当前动作主要是右臂 wave，不含复杂全身补偿

## 直接执行测试的最短路径

如果你现在只想最快验证“单 viewer 常驻 + 语音联动挥手”，就按下面四步走：

1. 在服务器运行：

```powershell
cd C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\simulate_python
python g1_runtime.py
```

2. 新开终端验证：

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:18080/state
```

3. 在项目根目录运行：

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python server.py
```

4. 打开网页 `http://localhost:8000`，输入：

```text
你好，很高兴见到你
```

看到“网页回复开始播报时，viewer 里机器人同步挥手”，就说明当前 Phase 1/2 主链路已经跑通。
