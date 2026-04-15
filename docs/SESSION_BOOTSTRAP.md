# Session Bootstrap

- 项目：Unitree G1 语音交互 + MuJoCo 动作反馈
- 当前目标：让语音输入经过 LLM 后，输出净化文本给 TTS，同时在合理社交场景下触发 G1 挥手动作
- 唤醒词：`小艺小艺`

## 当前主链路

- KWS：`sherpa-onnx (Zipformer)`
- VAD：`Silero-VAD`
- ASR：`FunASR`
- LLM：`DeepSeek` 流式 API
- TTS：`Edge-TTS`
- 前端：WebSocket + 浏览器麦克风
- 动作反馈：MuJoCo + G1 挥手动作脚本

## 当前已完成

- 基础语音链路已跑通：唤醒、识别、对话、播报
- TTS 长文本分段已修复
- ASR 热词提示与轻量词汇归一化已加入
- Web 前端流式文本同一气泡拼接已修复
- LLM 文本中的括号动作不会再被 TTS 读出来
- 新增动作解析与分发模块：`modules/action_dispatcher.py`
- 当前已接线三种挥手动作：
  - `挥手1`：远距欢迎
  - `挥手2`：近距正常打招呼
  - `挥手3`：儿童 / 亲和欢迎
- 本地规则优先决定最终执行哪个 wave，不完全信任 LLM 原始动作编号

## 关键文件

- `README.md`
- `modules/action_dispatcher.py`
- `modules/llm.py`
- `robot.py`
- `server.py`
- `static/index.html`
- `unitree_mujoco-main/unitree_robots/g1/action_wave1.py`
- `unitree_mujoco-main/unitree_robots/g1/action_wave2.py`
- `unitree_mujoco-main/unitree_robots/g1/action_wave3.py`
- `unitree_mujoco-main/unitree_robots/g1/scene_29dof.xml`
- `unitree_mujoco-main/unitree_robots/g1/g1_joint_human_mapping.md`

## 当前动作规则

- 允许动作代号：
  - `(挥手1)`
  - `(挥手2)`
  - `(挥手3)`
  - `(无动作)`
- 合理场景：
  - 远距欢迎 / 展厅迎宾 -> `挥手1`
  - 普通近距打招呼 -> `挥手2`
  - 儿童 / 亲和欢迎 -> `挥手3`
- 非社交场景：
  - 知识问答
  - 概念解释
  - 对比说明
  - 天气时间查询
  - 一律应走 `(无动作)`

## 当前测试入口

- 启动 Web 服务：
  - `python server.py`
- 前端地址：
  - `http://localhost:8000`
- 单独测试动作：
  - `python unitree_mujoco-main/unitree_robots/g1/action_wave1.py --scene scene_29dof.xml --print-targets`
  - `python unitree_mujoco-main/unitree_robots/g1/action_wave2.py --scene scene_29dof.xml --print-targets`
  - `python unitree_mujoco-main/unitree_robots/g1/action_wave3.py --scene scene_29dof.xml --print-targets`

## 当前跑通标准

- TTS 只播报净化后的正文，不读动作括号
- 日志能看到动作解析与最终重映射结果
- 合理社交场景下会拉起 MuJoCo viewer
- G1 在 viewer 中执行对应的 `wave1 / wave2 / wave3`

## 当前限制

- 动作执行方式仍是“触发时拉起 MuJoCo viewer”
- 还不是常驻 MuJoCo 动作进程
- 还不是真机控制器
- 后续切真机时，应保留动作代号层，仅替换动作执行后端

## 建议的新会话启动语

- `先看 README.md 和 docs/SESSION_BOOTSTRAP.md，再继续当前项目。`
