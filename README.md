# Robot G1 语音交互与常驻 MuJoCo 仿真

本项目当前主线是：

- 用 Python 保持一套稳定的 G1 常驻 MuJoCo 仿真
- 通过语音问答驱动上半身动作反馈
- 先把“站立 + 动作 + 语音联动”做稳
- walking backend 暂不在这条 Python 主线上实现

当前已经支持：

- 单个常驻 MuJoCo viewer
- 语音回复时根据模型输出的动作标记执行动作
- 多种家庭/社交场景动作
- 动作执行期间使用不同级别的 balance assist，尽量避免摔倒

## 当前能力边界

当前这套 `simulate_python` runtime 不是 walking controller。

它可以做：

- 站立
- 上半身动作叠加
- 语音联动

它目前不能直接做：

- 真正的下半身行走控制
- 边走边挥手
- 先走再停稳再挥手的 locomotion state machine

后续如果要做 walking：

1. 运动后端切到 C++ / 官方 walking backend
2. 当前 Python 动作资产继续保留
3. walking backend 负责下半身推进、停稳、恢复
4. 上半身动作通过接口叠加进去

## 当前支持的动作

### 社交场景

- `挥手1`
  远距离、大幅度欢迎
- `挥手2`
  近距离、小幅度挥手
- `挥手3`
  更亲和、面向儿童、轻微弯腰挥手
- `点头1`
  简短礼貌回应、确认
- `点头2`
  更正式的认可或致意
- `致意1`
  轻度鞠躬致意，适合欢迎或感谢
- `致意2`
  更正式的鞠躬，适合正式迎宾或正式感谢

### 家庭场景

- `安抚1`
  轻柔单手安抚，适合“别着急”“慢慢说”
- `安抚2`
  双手安抚，适合更需要安慰感的场景
- `邀请1`
  单手引导，适合“请进”“请坐”“请看这边”
- `邀请2`
  双手欢迎或引导，适合“欢迎回家”“请到这边”

## 关键文件

- 语音服务入口：[server.py](/C:/Users/HONOR/Desktop/robot_manus/server.py)
- 机器人主流程：[robot.py](/C:/Users/HONOR/Desktop/robot_manus/robot.py)
- 动作解析与下发：[modules/action_dispatcher.py](/C:/Users/HONOR/Desktop/robot_manus/modules/action_dispatcher.py)
- LLM prompt：[modules/llm.py](/C:/Users/HONOR/Desktop/robot_manus/modules/llm.py)
- runtime 客户端：[modules/sim_runtime_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/sim_runtime_client.py)
- walking 预留接口：[modules/motion_backend_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/motion_backend_client.py)
- 常驻仿真入口：[unitree_mujoco-main/simulate_python/g1_runtime.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_runtime.py)
- 通用动作资产：[unitree_mujoco-main/simulate_python/g1_motion_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_motion_assets.py)
- 兼容层：[unitree_mujoco-main/simulate_python/g1_wave_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_wave_assets.py)
- 站姿与 PD 控制：[unitree_mujoco-main/simulate_python/g1_stand_pose.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_stand_pose.py)

## 模型与场景

当前统一使用：

- `unitree_mujoco-main/unitree_robots/g1/scene_29dof.xml`

这条线默认就是 29DOF，不再混用 23DOF。

## 动作协议

LLM 只能输出以下动作标记之一：

- `(挥手1)`
- `(挥手2)`
- `(挥手3)`
- `(点头1)`
- `(点头2)`
- `(致意1)`
- `(致意2)`
- `(安抚1)`
- `(安抚2)`
- `(邀请1)`
- `(邀请2)`
- `(无动作)`

一轮回复只允许一个动作。

## runtime HTTP 接口

常驻仿真默认地址：

- `http://127.0.0.1:18080`

接口：

- `GET /state`
- `POST /action`

`POST /action` 支持这些动作码：

- `wave1`
- `wave2`
- `wave3`
- `nod1`
- `nod2`
- `bow1`
- `bow2`
- `soothe1`
- `soothe2`
- `invite1`
- `invite2`
- `reset`

示例：

```bash
curl -X POST http://127.0.0.1:18080/action \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"invite1\"}"
```

## 服务器环境要求

建议把 `g1_runtime.py` 和 `server.py` 都跑在同一台带图形界面的服务器上。

基础要求：

- Python 3.10 左右
- 已安装 `mujoco`
- 能打开 MuJoCo viewer
- 能访问 DeepSeek API、Edge TTS、FunASR 模型下载所需网络
- 如果要测试麦克风，需要可用音频输入输出设备

建议依赖：

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

## 启动顺序

### 1. 启动常驻 MuJoCo runtime

```powershell
cd C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\simulate_python
python g1_runtime.py
```

预期：

- 自动弹出一个 MuJoCo viewer
- 终端打印 runtime HTTP 服务启动日志
- 模型默认保持站立

### 2. 检查 runtime 健康状态

```bash
curl http://127.0.0.1:18080/state
```

### 3. 启动语音服务

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python server.py
```

### 4. 打开网页

- `http://localhost:8000`

## viewer 热键

- `1 / 2 / 3`
  触发 `wave1 / wave2 / wave3`
- `Q / W`
  触发 `nod1 / nod2`
- `A / S`
  触发 `bow1 / bow2`
- `Z / X`
  触发 `soothe1 / soothe2`
- `C / V`
  触发 `invite1 / invite2`
- `0`
  回到中立站姿
- `7`
  放松 balance assist
- `8`
  收紧 balance assist
- `9`
  开关 balance assist

## 当前稳定性策略

runtime 按动作风险自动切换支撑配置：

- `default`
  用于 `wave1`、`wave2`、`nod1`、`nod2`、`soothe1`
- `medium`
  用于 `invite1`、`invite2`、`soothe2`、`bow1`
- `strong`
  用于 `wave3`、`bow2`

这样做是为了在不引入 walking controller 的前提下，尽量保证动作执行时不摔倒。

## 推荐测试流程

### 测试 1：静态站立

- 启动 runtime 后静止观察 10 秒
- 预期不前倒、不侧倒、不明显腿抖

### 测试 2：viewer 热键动作

建议逐个测试：

- `1 2 3`
- `Q W`
- `A S`
- `Z X`
- `C V`

每个动作至少连按 3 到 5 次，确认：

- 能执行
- 能回中
- 不摔倒

### 测试 3：HTTP 动作测试

示例：

```bash
curl -X POST http://127.0.0.1:18080/action \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"bow1\"}"
```

### 测试 4：网页文本联动

启动 runtime 和 `server.py` 后，网页输入这些句子做场景验证：

- `欢迎大家来到展厅`
  更偏 `挥手1` 或 `致意1`
- `谢谢大家的到来`
  更偏 `致意1` 或 `致意2`
- `好的，我明白了`
  更偏 `点头1`
- `别着急，我来帮你`
  更偏 `安抚1` 或 `安抚2`
- `请到这边坐`
  更偏 `邀请1` 或 `邀请2`
- `小朋友们大家好`
  更偏 `挥手3`

### 测试 5：单轮动作限制

构造一条长回复中包含两个动作标记，预期只执行第一个动作。

## 常见问题

### 网页能回复，但模型不动

优先检查：

- `http://127.0.0.1:18080/state` 是否正常
- `SIM_RUNTIME_URL` 是否指向正确地址
- LLM 回复末尾是否真的带了动作标记
- runtime 是否正在忙，导致新动作返回 `accepted=false`

### viewer 会倒

处理顺序建议：

1. 先按 `8` 收紧 balance assist
2. 再复测 `wave3`、`bow2` 这类高风险动作
3. 若仍不稳，再调动作资产本身的前倾和手臂幅度

## 当前开发阶段

### Phase 1

- 常驻仿真
- 站立稳定
- 上半身动作库

### Phase 2

- 语音唤醒
- 语音回复
- 动作同步触发

### Phase 3

- 接入 C++ walking backend
- 实现“先停稳再挥手”

### Phase 4

- 如果确实需要“移动中持续做动作”，再评估 whole-body controller 或 RL
