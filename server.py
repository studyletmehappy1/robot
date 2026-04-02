import os
import logging
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import json
from robot import Robot

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# 初始化机器人 (不启动录音循环，仅用于逻辑处理)
api_key = "sk-ZqcUw3Viws3jvOOn6748A3C3719b4c18Ae26D1D7E1B87299"
robot = Robot(api_key=api_key)

@app.get("/")
async def get():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket 连接已建立")
    
    # 每个连接维护自己的状态机
    state = {
        "status": "SLEEP", # SLEEP, AWAKE, PROCESSING
        "vad_start": False,
        "silence_chunks": 0,
        "streaming_text": "",
        "chat_lock": False
    }
    
    # 初始状态同步给前端
    await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    
    # 重置 ASR 缓存
    robot.asr.reset_cache()

    try:
        while True:
            message = await websocket.receive()
            
            if "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "text":
                    user_text = data.get("content", "")
                    logger.info(f"收到网页端文本输入: {user_text}")
                    # 文本输入强制唤醒并处理
                    state["status"] = "PROCESSING"
                    await websocket.send_json({"type": "status", "content": "正在思考中..."})
                    asyncio.create_task(handle_chat(websocket, user_text, state))
            
            elif "bytes" in message:
                audio_chunk = message["bytes"]
                
                if state["status"] == "SLEEP":
                    # KWS 监听
                    keyword = robot.kws.detect(audio_chunk)
                    if keyword:
                        logger.info(f"Web 端检测到唤醒词: {keyword}")
                        state["status"] = "AWAKE"
                        state["streaming_text"] = ""
                        state["silence_chunks"] = 0
                        robot.asr.reset_cache()
                        await websocket.send_json({"type": "status", "content": "已唤醒，正在倾听..."})
                        
                elif state["status"] == "AWAKE":
                    # VAD + ASR 监听
                    has_speech = robot.vad.is_speech(audio_chunk)
                    
                    if has_speech:
                        state["silence_chunks"] = 0
                        text_chunk = robot.asr.transcribe_chunk(audio_chunk, is_final=False)
                        if text_chunk:
                            state["streaming_text"] += text_chunk
                            await websocket.send_json({"type": "asr_chunk", "content": state["streaming_text"]})
                    else:
                        state["silence_chunks"] += 1
                        text_chunk = robot.asr.transcribe_chunk(audio_chunk, is_final=False)
                        if text_chunk:
                            state["streaming_text"] += text_chunk
                            await websocket.send_json({"type": "asr_chunk", "content": state["streaming_text"]})
                        
                        # 【重要修复】优化了这里的静音判定延迟，从默认的 60 改为了 5
                        if state["silence_chunks"] > 5:
                            logger.info("Web 端检测到人声结束，准备处理...")
                            final_chunk = robot.asr.transcribe_chunk(b"", is_final=True)
                            if final_chunk:
                                state["streaming_text"] += final_chunk
                            
                            final_text = state["streaming_text"]
                            state["status"] = "PROCESSING"
                            state["silence_chunks"] = 0
                            
                            if final_text.strip():
                                await websocket.send_json({"type": "asr_final", "content": final_text})
                                await websocket.send_json({"type": "status", "content": "正在思考中..."})
                                asyncio.create_task(handle_chat(websocket, final_text, state))
                            else:
                                # 没听清指令，回休眠
                                state["status"] = "SLEEP"
                                await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})

    except WebSocketDisconnect:
        logger.info("WebSocket 连接已断开")
    except Exception as e:
        logger.error(f"WebSocket 处理出错: {e}")

async def handle_chat(websocket, text, state):
    """处理对话逻辑并发送 TTS (完整大段生成模式)"""
    if state["chat_lock"]: return
    state["chat_lock"] = True
    try:
        robot.messages[0] = {"role": "system", "content": robot.llm.create_system_prompt()}
        robot.messages.append({"role": "user", "content": text})
        
        if len(robot.messages) > 21:
            robot.messages = [robot.messages[0]] + robot.messages[-20:]
            
        response_text = ""
        
        # 1. 默默接收大模型的全部回复，期间不发送任何内容
        for chunk in robot.llm.call_deepseek_api(robot.messages):
            response_text += chunk
            
        if response_text.strip():
            # 2. 一次性将完整的回答送去合成语音
            audio_file = await robot.tts.to_tts_async(response_text.strip())
            
            if audio_file:
                # 3. 将完整文字一次性发给前端（前端会暂存）
                await websocket.send_json({"type": "sentence_text", "content": response_text.strip()})
                
                # 4. 紧接着发送完整的二进制音频，触发前端同步显示文字和播放声音
                with open(audio_file, "rb") as f:
                    await websocket.send_bytes(f.read())
                robot.tts.clean_up(audio_file)
                
            robot.messages.append({"role": "assistant", "content": response_text})
            
        await websocket.send_json({"type": "done"})
        
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
        
    except Exception as e:
        logger.error(f"Web 对话处理出错: {e}")
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    finally:
        state["chat_lock"] = False
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)