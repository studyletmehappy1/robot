import os
import logging
import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from robot import Robot

# ==========================================
# 1. 日志与基础配置
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# 确保必要的目录存在
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs("temp_audio", exist_ok=True)

# ==========================================
# 2. 机器人组件初始化 (加载模型较慢，请耐心等待)
# ==========================================
api_key = "sk-ZqcUw3Viws3jvOOn6748A3C3719b4c18Ae26D1D7E1B87299"
robot = Robot(api_key=api_key)

# ==========================================
# 3. 路由处理
# ==========================================
@app.get("/")
async def get():
    """渲染前端页面"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="index.html not found", status_code=404)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 核心流式处理"""
    await websocket.accept()
    logger.info("WebSocket 已连接")
    
    # 维护当前连接的状态
    state = {
        "status": "SLEEP",           # SLEEP, AWAKE, PROCESSING
        "silence_chunks": 0,         # 静音计数
        "streaming_text": "",        # 累积 ASR 文本
        "chat_lock": False,          # 对话锁
        "has_started_speech": False  # 关键修复：追踪用户是否已开始说话
    }
    
    await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    robot.asr.reset_cache()

    try:
        while True:
            message = await websocket.receive()
            
            # 处理文本输入
            if "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "text":
                    state["status"] = "PROCESSING"
                    await websocket.send_json({"type": "status", "content": "正在思考中..."})
                    asyncio.create_task(handle_chat(websocket, data.get("content", ""), state))
            
            # 处理音频字节流
            elif "bytes" in message:
                audio_chunk = message["bytes"]
                
                if state["status"] == "SLEEP":
                    # KWS 唤醒检测
                    if robot.kws.detect(audio_chunk):
                        logger.info("✨ 唤醒成功")
                        state.update({"status": "AWAKE", "streaming_text": "", "silence_chunks": 0, "has_started_speech": False})
                        robot.asr.reset_cache()
                        await websocket.send_json({"type": "status", "content": "已唤醒，正在倾听..."})
                        
                elif state["status"] == "AWAKE":
                    # VAD 判定 (已在 vad.py 修复 4096 字节切片问题)
                    if robot.vad.is_speech(audio_chunk):
                        state["has_started_speech"] = True # 只有开始说话了，才进行后续的静音判定
                        state["silence_chunks"] = 0
                    elif state["has_started_speech"]:
                        state["silence_chunks"] += 1
                    
                    # 实时 ASR
                    text_chunk = robot.asr.transcribe_chunk(audio_chunk, is_final=False)
                    if text_chunk:
                        state["streaming_text"] += text_chunk
                        await websocket.send_json({"type": "asr_chunk", "content": state["streaming_text"]})
                    
                    # 结束判定：用户说过话且静音满 8 块 (约 2 秒)
                    if state["has_started_speech"] and state["silence_chunks"] > 8:
                        logger.info("判定说话结束")
                        final_text = state["streaming_text"] + robot.asr.transcribe_chunk(b"", is_final=True)
                        state["status"] = "PROCESSING"
                        
                        if final_text.strip():
                            await websocket.send_json({"type": "asr_final", "content": final_text})
                            await websocket.send_json({"type": "status", "content": "正在思考中..."})
                            asyncio.create_task(handle_chat(websocket, final_text, state))
                        else:
                            # 唤醒后没说话，重置 KWS 记忆并回休眠
                            robot.kws.reset()
                            state["status"] = "SLEEP"
                            await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})

    except WebSocketDisconnect:
        logger.info("连接断开")
    except Exception as e:
        logger.error(f"WS 异常: {e}")

async def handle_chat(websocket, text, state):
    """对话逻辑与 TTS 同步下发"""
    if state["chat_lock"]: return
    state["chat_lock"] = True
    try:
        # 准备对话
        robot.messages[0] = {"role": "system", "content": robot.llm.create_system_prompt()}
        robot.messages.append({"role": "user", "content": text})
        
        # 截断历史记录
        if len(robot.messages) > 21:
            robot.messages = [robot.messages[0]] + robot.messages[-20:]
            
        # 1. 完整获取 LLM 回复
        response_text = ""
        for chunk in robot.llm.call_deepseek_api(robot.messages):
            response_text += chunk
            
        if response_text.strip():
            # 2. 合成完整音频
            audio_file = await robot.tts.to_tts_async(response_text.strip())
            
            if audio_file:
                # 3. 字音同步：先发文字 JSON，再发二进制音频
                await websocket.send_json({"type": "sentence_text", "content": response_text.strip()})
                with open(audio_file, "rb") as f:
                    await websocket.send_bytes(f.read())
                robot.tts.clean_up(audio_file)
                
            robot.messages.append({"role": "assistant", "content": response_text})
            
        await websocket.send_json({"type": "done"})
        
        # 关键点：重置 KWS 记忆，防止二次唤醒失败
        robot.kws.reset()
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
        
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        robot.kws.reset()
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    finally:
        state["chat_lock"] = False

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)