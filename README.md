# Robot 智能语音助手

这是一个围绕 Unitree G1 搭建的语音交互机器人项目。当前仓库已经从“基础语音链路跑通”推进到了“LLM 输出带动作括号文本，并在合理社交场景下触发 MuJoCo 挥手动作”的阶段。

## 当前进度

### 已跑通的主链路

- 唤醒词检测：`sherpa-onnx (Zipformer)`，固定唤醒词为 `小艺小艺`
- 语音活动检测：`Silero-VAD`
- 语音识别：`FunASR`
- 大模型对话：`DeepSeek` 流式 API
- 语音合成：`Edge-TTS`
- WebSocket 前端：支持浏览器麦克风输入、ASR 实时显示、流式回复气泡拼接

### 已完成的稳定性修复

- TTS 长文本分段与顺序播放
- ASR 热词提示和轻量词汇归一化
- Web 前端流式文本同一气泡拼接
- LLM 输出中的动作括号不会再被 TTS 读出来

### 已完成的动作最小 MVP

- 新增动作解析与分发模块：[modules/action_dispatcher.py](C:\Users\HONOR\Desktop\robot_manus\modules\action_dispatcher.py)
- 当前已接线三种挥手动作：
  - `挥手1` -> [unitree_mujoco-main/unitree_robots/g1/action_wave1.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave1.py)
  - `挥手2` -> [unitree_mujoco-main/unitree_robots/g1/action_wave2.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave2.py)
  - `挥手3` -> [unitree_mujoco-main/unitree_robots/g1/action_wave3.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave3.py)
- 本地规则优先：
  - 远距欢迎 / 展厅迎宾 -> 优先 `挥手1`
  - 普通近距打招呼 -> 优先 `挥手2`
  - 儿童 / 亲和欢迎 -> 优先 `挥手3`
- 对知识问答、解释区别、天气时间等非社交场景，即使模型误输出动作括号，也会被本地拦截，不执行动作

## 当前架构

- 唤醒层：`sherpa-onnx (Zipformer)`，本地部署
- 检测层：`Silero-VAD`，服务端本地部署
- 识别层：`FunASR`，服务端本地部署
- 大脑层：`DeepSeek`，外部云端流式 API
- 发声层：`Edge-TTS`，外部接口调用
- 动作仿真层：`MuJoCo + action_wave1/2/3.py`
- 客户端：当前为 Web 测试端，后续可接物理开发板或真机控制层

## 固定约束

- 当前唤醒词固定且唯一：`小艺小艺`
- 当前动作白名单只允许：
  - `挥手1`
  - `挥手2`
  - `挥手3`
  - `无动作`
- 当前动作反馈固定通过 MuJoCo viewer 可视化验证

## 关键文件

### 语音与对话

- [modules/asr.py](C:\Users\HONOR\Desktop\robot_manus\modules\asr.py)
- [modules/tts.py](C:\Users\HONOR\Desktop\robot_manus\modules\tts.py)
- [modules/llm.py](C:\Users\HONOR\Desktop\robot_manus\modules\llm.py)
- [modules/action_dispatcher.py](C:\Users\HONOR\Desktop\robot_manus\modules\action_dispatcher.py)
- [robot.py](C:\Users\HONOR\Desktop\robot_manus\robot.py)
- [server.py](C:\Users\HONOR\Desktop\robot_manus\server.py)
- [static/index.html](C:\Users\HONOR\Desktop\robot_manus\static\index.html)

### 动作与仿真

- [unitree_mujoco-main/unitree_robots/g1/action_wave1.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave1.py)
- [unitree_mujoco-main/unitree_robots/g1/action_wave2.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave2.py)
- [unitree_mujoco-main/unitree_robots/g1/action_wave3.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave3.py)
- [unitree_mujoco-main/unitree_robots/g1/scene_23dof.xml](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\scene_23dof.xml)
- [unitree_mujoco-main/unitree_robots/g1/g1_joint_human_mapping.md](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\g1_joint_human_mapping.md)

## 三种挥手语义

- `挥手1`
  远距欢迎 / 远距离示意。手举得更高、摆幅更大，更容易被远处看到。
- `挥手2`
  近距正常打招呼。最接近日常面对面寒暄，当前可视为“标准社交挥手”。
- `挥手3`
  儿童 / 亲和场景。动作更柔和、手腕协同更多，但不过分夸张卖萌。

## LLM 输出规则

当前 prompt 已约束模型：

- 输出必须包含正文和动作括号
- 当前只允许输出：
  - `(挥手1)`
  - `(挥手2)`
  - `(挥手3)`
  - `(无动作)`
- 场景建议：
  - 远距欢迎、欢迎大家、展厅迎宾等场景建议输出 `(挥手1)`
  - 普通近距打招呼建议输出 `(挥手2)`
  - 儿童 / 亲和欢迎建议输出 `(挥手3)`
- 解释知识、比较概念、查询信息、天气时间等场景默认输出 `(无动作)`
- 禁止输出 `(解释区别手势)` 这类未定义括号内容

## Action Dispatcher 说明

[modules/action_dispatcher.py](C:\Users\HONOR\Desktop\robot_manus\modules\action_dispatcher.py) 负责三件事：

1. 正则解析动作括号
- `parse_llm_actions(raw_text)`
- 输入 LLM 原始文本
- 输出：
  - `clean_text`
  - `action_list`

2. 合理性场景门控与动作重映射
- `should_allow_wave(user_text, clean_text)`
- `infer_wave_action(user_text, clean_text)`
- 本地规则优先，不完全信任 LLM 原始动作编号

3. 动作执行
- `dispatch_actions(action_list)`
- 当前通过子进程拉起对应 MuJoCo viewer：
  - `wave1`
  - `wave2`
  - `wave3`

## 运行方式

### Web 模式

启动服务端：

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python server.py
```

浏览器访问：

```text
http://localhost:8000
```

当前 Web 前端支持：

- 文本输入
- 麦克风输入
- ASR 流式显示
- 机器人回复流式气泡拼接
- 服务端 `action` 事件下发

### 终端模式

```powershell
cd C:\Users\HONOR\Desktop\robot_manus
python main.py
```

## MuJoCo 动作单测

如果你想先单独验证三个挥手动作本身，不走语音链路：

```powershell
cd C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1
python action_wave1.py --scene scene_23dof.xml --print-targets
python action_wave2.py --scene scene_23dof.xml --print-targets
python action_wave3.py --scene scene_23dof.xml --print-targets
```

说明：

- `--scene scene_23dof.xml`
  指定当前默认测试场景
- `--print-targets`
  打印 `Neutral pose`、`Preparation pose`、`Wave center pose` 的关键右臂目标角，方便调参

如果 MuJoCo viewer 弹出，且机器人完整执行对应挥手，说明动作脚本本身是通的。

## 语音 -> 动作 联调测试

### 文本联调

1. 启动 `server.py`
2. 打开浏览器前端
3. 在输入框输入：

```text
你好，很高兴见到你
```

预期现象：

- LLM 返回正文，并可能附带 `(挥手2)`
- 前端只显示净化后的正文
- TTS 只播报正文
- 如果判定为合理社交场景：
  - 日志中出现 `ActionDispatcher: launching wave2 viewer`
  - MuJoCo 窗口弹出
  - G1 执行一次 `action_wave2.py` 定义的挥手

### 麦克风联调

1. 点击前端“开启环境监听”
2. 说：

```text
小艺小艺，你好
```

预期现象：

- KWS 唤醒成功
- ASR 正常识别
- LLM 生成带括号动作的文本
- 文本被拦截拆分
- TTS 发声时不读动作名
- 合理场景下弹出 MuJoCo viewer 并执行对应的 `挥手1 / 挥手2 / 挥手3`

你还可以分别测试：

```text
欢迎大家来到展厅
```

预期执行 `挥手1`

```text
小朋友你好，欢迎你来玩
```

预期执行 `挥手3`

### 反例联调

输入：

```text
白切鸡和清远鸡有什么区别
```

预期现象：

- 正常知识回答
- 不弹 MuJoCo 窗口
- 不执行任何挥手

## 如何判断当前 MVP 跑通

当前“跑通”的标准不是只看括号被识别，而是以下 4 点同时满足：

1. LLM 原文里的动作括号被解析成功
2. TTS 只播报 `clean_text`，不会读出 `(挥手1)` / `(挥手2)` / `(挥手3)`
3. 日志出现动作调度记录和最终 wave 重映射结果
4. MuJoCo viewer 被拉起，并在窗口中完整执行一次对应的 [action_wave1.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave1.py) / [action_wave2.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave2.py) / [action_wave3.py](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\action_wave3.py)

## 关节动作理解

见：

- [unitree_mujoco-main/unitree_robots/g1/g1_joint_human_mapping.md](C:\Users\HONOR\Desktop\robot_manus\unitree_mujoco-main\unitree_robots\g1\g1_joint_human_mapping.md)

这份文档把机器人关节名映射成更接近人体动作的理解，比如：

- `right_shoulder_pitch_joint`：肩前举 / 后摆
- `right_shoulder_roll_joint`：肩外展 / 内收
- `right_shoulder_yaw_joint`：上臂绕自身轴旋转近似
- `right_elbow_joint`：肘部屈伸
- `right_wrist_roll_joint`：掌面翻转近似

## 当前限制

- 当前执行方式是“语音链路解析后，本地规则重映射到 wave1 / wave2 / wave3”
- 当前动作执行方式仍是“触发时拉起 MuJoCo viewer”
- 还不是常驻动作进程，也不是实机控制器
- 后续若切到真机，应保留动作代号层不变，仅替换动作执行后端

## 下一步建议

- 把三种挥手从“弹出单独 MuJoCo viewer”升级为“连接已有 MuJoCo 常驻进程”
- 继续优化 prompt，让模型在非社交场景更稳定输出 `(无动作)`
- 后续扩展到真机时，把 `挥手1 / 2 / 3` 的执行后端从 MuJoCo 脚本切换到机器人 SDK/ROS2 控制接口
