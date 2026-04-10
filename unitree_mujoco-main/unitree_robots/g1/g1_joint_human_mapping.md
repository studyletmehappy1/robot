# G1 Joint Human Mapping

这份对照用于把 MuJoCo / 代码里的 G1 关节名，映射到更接近人体动作的理解方式。

## Core Principle

- 代码里用的是机器人关节自由度名称，不是人体解剖学标准名。
- 当前 G1 23DOF / 29DOF 模型里，没有独立的 `elbow roll`。
- 所以很多“看起来像前臂左右摆动”的动作，要用 `shoulder_yaw + wrist_roll` 去近似实现。

## Upper Body

| Robot Joint | Human Meaning | Typical Use |
| --- | --- | --- |
| `right_shoulder_pitch_joint` | 肩前举 / 后摆 | 把整条右臂抬到身体前方或放回侧边 |
| `right_shoulder_roll_joint` | 肩外展 / 内收 | 让右臂离开身体一点，避免贴躯干 |
| `right_shoulder_yaw_joint` | 上臂绕自身轴旋转的近似 | 当前最适合做“社交挥手主摆动”的自由度 |
| `right_elbow_joint` | 肘部屈伸 | 把小臂弯起来，让手更像招手姿态 |
| `right_wrist_roll_joint` | 手掌翻转 / 前臂末端旋转近似 | 辅助把掌面调整到朝前，增加招手味道 |
| `right_wrist_pitch_joint` | 手腕上下折 | 微调掌面朝向，避免手部垂落 |
| `right_wrist_yaw_joint` | 手腕平面内偏转 | 细微修正，不适合作为主挥手动力源 |

左臂对应关系完全一致，只需把 `right_` 换成 `left_`。

## Torso

| Robot Joint | Human Meaning | Typical Use |
| --- | --- | --- |
| `waist_yaw_joint` | 转腰 | 身体左右转向 |
| `waist_roll_joint` | 侧腰倾斜 | 身体左右侧倾 |
| `waist_pitch_joint` | 弯腰 / 挺身 | 身体前后俯仰 |

## Lower Body

| Robot Joint | Human Meaning | Typical Use |
| --- | --- | --- |
| `left_hip_pitch_joint` / `right_hip_pitch_joint` | 髋前后摆 | 抬腿、迈步、站立俯仰调整 |
| `left_hip_roll_joint` / `right_hip_roll_joint` | 髋外展内收 | 保持左右平衡、侧向调整 |
| `left_hip_yaw_joint` / `right_hip_yaw_joint` | 髋旋转 | 调整腿部朝向 |
| `left_knee_joint` / `right_knee_joint` | 膝屈伸 | 下蹲、站立缓冲 |
| `left_ankle_pitch_joint` / `right_ankle_pitch_joint` | 踝前后摆 | 站立稳定、脚尖前后压 |
| `left_ankle_roll_joint` / `right_ankle_roll_joint` | 踝内外翻 | 站立侧向稳定 |

## Practical Advice

- 想让手臂到身体前方：
  优先调 `shoulder_pitch`
- 想避免像侧平举摆臂：
  减小 `shoulder_roll`
- 想更像挥手：
  让 `shoulder_yaw` 做主摆动，`wrist_roll` 只做小幅协同
- 想让小臂竖起来：
  增大 `elbow_joint`
- 想让掌面更像朝前：
  优先调 `wrist_roll` 和 `wrist_pitch`
