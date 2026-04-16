# Session Bootstrap

- 项目：Unitree G1 语音交互 + 常驻 MuJoCo 挥手反馈
- 当前阶段：Phase 1/2
- 当前目标：语音回复时在单个常驻 MuJoCo viewer 中同步触发挥手，不再重复开 viewer

## 当前主链路
- KWS：`sherpa-onnx`
- VAD：`Silero-VAD`
- ASR：`FunASR`
- LLM：`DeepSeek`
- TTS：`Edge-TTS`
- 前端：`FastAPI + WebSocket`
- 动作执行：常驻 MuJoCo runtime + HTTP 动作桥

## 当前核心结论
- 当前 G1 主模型统一为 `scene_29dof.xml`
- 当前动作只支持：
  - `挥手1`
  - `挥手2`
  - `挥手3`
  - `无动作`
- 当前动作后端已经不是“开独立 wave 脚本”，而是：
  - `modules/action_dispatcher.py`
  - `modules/sim_runtime_client.py`
  - `unitree_mujoco-main/simulate_python/g1_runtime.py`
- 当前 walking 不在这条 Python 主线内
- 后续 walking 计划切到 C++ backend，Python 保留语音链路和动作资产

## 当前关键文件
- `README.md`
- `server.py`
- `robot.py`
- `modules/action_dispatcher.py`
- `modules/sim_runtime_client.py`
- `unitree_mujoco-main/simulate_python/config.py`
- `unitree_mujoco-main/simulate_python/g1_runtime.py`
- `unitree_mujoco-main/simulate_python/g1_wave_assets.py`
- `unitree_mujoco-main/simulate_python/g1_stand_pose.py`
- `unitree_mujoco-main/unitree_robots/g1/action_wave1.py`
- `unitree_mujoco-main/unitree_robots/g1/action_wave2.py`
- `unitree_mujoco-main/unitree_robots/g1/action_wave3.py`

## 当前启动顺序
1. 启动常驻 runtime
   - `python unitree_mujoco-main/simulate_python/g1_runtime.py`
2. 启动语音服务
   - `python server.py`
3. 打开网页
   - `http://localhost:8000`

## 当前测试入口
- viewer 热键：
  - `1 / 2 / 3 / 0`
- HTTP 接口：
  - `POST /action`
  - `GET /state`
- 语音联动：
  - 问候语触发挥手
  - 非社交问句不触发动作

## 接手提醒
- 不要再按“每次动作开一个新 viewer”的思路继续开发
- 继续扩展动作时，优先改 `g1_wave_assets.py`
- 继续调站立稳定性时，优先改 `g1_stand_pose.py`
- 如果要做 walking，请单独开启 C++ backend 方案，不要把 `simulate_python` 直接硬扩成 walking controller
