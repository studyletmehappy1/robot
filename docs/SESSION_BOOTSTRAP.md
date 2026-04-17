# Session Bootstrap

## 项目定位

- 项目：Unitree G1 语音交互 + 常驻 MuJoCo 动作反馈
- 当前阶段：Phase 1 / Phase 2
- 当前主线：Python runtime 做站立和上半身动作，语音服务按 LLM 动作标记驱动 runtime

## 当前核心结论

- 当前 Python `simulate_python` 只负责：
  - 站立
  - 上半身动作叠加
  - 语音联动
- 当前不负责：
  - walking controller
  - 步态生成
  - 边走边挥手
- 后续 walking 路线固定为：
  - 切到 C++ backend
  - 保留当前 Python 动作资产复用

## 当前动作集

### 社交场景

- `挥手1`
- `挥手2`
- `挥手3`
- `点头1`
- `点头2`
- `致意1`
- `致意2`

### 家庭场景

- `安抚1`
- `安抚2`
- `邀请1`
- `邀请2`

## 当前动作协议

LLM 只能输出这些动作标记之一：

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

一轮回复最多执行一个动作。

## 当前关键文件

- [README.md](/C:/Users/HONOR/Desktop/robot_manus/README.md)
- [server.py](/C:/Users/HONOR/Desktop/robot_manus/server.py)
- [robot.py](/C:/Users/HONOR/Desktop/robot_manus/robot.py)
- [modules/action_dispatcher.py](/C:/Users/HONOR/Desktop/robot_manus/modules/action_dispatcher.py)
- [modules/llm.py](/C:/Users/HONOR/Desktop/robot_manus/modules/llm.py)
- [modules/sim_runtime_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/sim_runtime_client.py)
- [modules/motion_backend_client.py](/C:/Users/HONOR/Desktop/robot_manus/modules/motion_backend_client.py)
- [unitree_mujoco-main/simulate_python/g1_runtime.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_runtime.py)
- [unitree_mujoco-main/simulate_python/g1_motion_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_motion_assets.py)
- [unitree_mujoco-main/simulate_python/g1_wave_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_wave_assets.py)
- [unitree_mujoco-main/simulate_python/g1_stand_pose.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_stand_pose.py)

## 当前启动顺序

1. 启动常驻 runtime
   - `python unitree_mujoco-main/simulate_python/g1_runtime.py`
2. 确认 runtime 健康检查
   - `GET /state`
3. 启动语音服务
   - `python server.py`
4. 打开网页
   - `http://localhost:8000`

## 当前测试入口

- viewer 热键
  - `1 / 2 / 3`
  - `Q / W`
  - `A / S`
  - `Z / X`
  - `C / V`
  - `0 / 7 / 8 / 9`
- HTTP 动作接口
  - `POST /action`
  - `GET /state`
- 语音联动
  - 文本输入
  - 麦克风输入

## 接手提醒

- 不要再按“每次动作开一个新 viewer”的思路开发。
- 新增动作优先改 [g1_motion_assets.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_motion_assets.py)。
- 站立稳定性优先改 [g1_stand_pose.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_stand_pose.py) 和 [g1_runtime.py](/C:/Users/HONOR/Desktop/robot_manus/unitree_mujoco-main/simulate_python/g1_runtime.py)。
- walking 不要继续在 `simulate_python` 上硬堆，后续请单开 C++ backend 方案。
