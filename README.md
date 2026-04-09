# Robot 智能语音助手

这是一个已经跑通的 Unitree G1 语音交互项目，当前链路保持轻量化，只做定点修复与文档同步。

## 当前架构

- 唤醒层：`sherpa-onnx (Zipformer)`，本地部署
- 检测层：`Silero-VAD`，服务端本地部署
- 识别层：`FunASR`，服务端本地部署
- 大脑层：`DeepSeek`，外部云端流式 API
- 发声层：`Edge-TTS`，外部接口调用
- 客户端：当前为 Web 测试端，后续可对接物理开发板

## 固定约束

- 当前唤醒词固定且唯一：`小艺小艺`
- 本次补丁不扩展新的唤醒词配置入口
- 不重构既有 KWS / VAD / ASR / LLM / TTS 主链路

## 本次补丁内容

### 1. TTS 长文本稳定性修复

- 在 `modules/tts.py` 中加入 TTS 内部二次分段
- 优先按 `。！？；：，,.!?;:` 分段，单段仍过长时再硬切
- 新增多片段音频生成接口，外层按顺序播放或下发
- 单段失败时只记录日志并跳过，不再让整轮播报因 `No audio was received.` 直接中断

### 2. ASR 识别优化

- 在 `modules/asr.py` 中增加轻量领域提示词
- 默认覆盖：`小艺小艺`、`Unitree`、`G1`、`机器人`、`DeepSeek`、`FunASR`、`Silero`、`Edge-TTS`
- 优先尝试 `initial_prompt`，不兼容时自动回退到其他兼容参数或普通调用
- 仅增加非常轻量的项目词汇归一化，不做通用纠错

### 3. LLM 输出格式与动作解析

- 在 `modules/llm.py` 中重写 system prompt
- 强制模型输出格式：`自然语言回复(动作指令)`
- 无动作时固定输出：`(无动作)`
- 明确机器人交互性格为“正常成年人”，自然、大方、稳重，适合儿童、成年人和老人
- 新增统一正则解析器，安全剥离结尾动作指令，正文交给 TTS，动作单独留给机器人执行

### 4. 运行时接线

- `robot.py`：终端模式下先做正文 / 动作拆分，正文送 TTS，动作进入最小占位钩子 `dispatch_action`
- `server.py`：WebSocket 链路中同样拆分正文与动作
- 服务端新增 `action` 事件，供未来开发板接入实体动作执行
- 对话历史只保存净化后的正文，避免动作标签污染后续上下文

## 新增接口

- `LLMModule.extract_reply_and_action(text) -> tuple[str, str]`
- `TTSModule.split_for_tts(text, max_chars=...) -> list[str]`
- `TTSModule.to_tts_many(text)`
- `TTSModule.to_tts_many_async(text)`
- `Robot.dispatch_action(action)`
- WebSocket 消息类型：`action`

## 验证建议

- 长文本、多句文本、无标点长句都要验证 TTS 是否稳定输出
- 测试 `你好，欢迎回来。(挥手1)` 是否能正确播报正文并单独下发动作
- 测试 `好的，我来帮你看看。(无动作)` 是否只播报正文
- 测试包含项目词汇的口语输入，确认 ASR 对 `小艺小艺`、`Unitree G1`、`DeepSeek` 等词更稳定
