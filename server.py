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
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket 连接已建立")
    
    try:
        while True:
            # 接收前端发送的消息 (JSON 格式)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "text":
                user_text = message.get("content", "")
                logger.info(f"收到网页端文本输入: {user_text}")
                
                # 处理对话
                # 动态更新系统提示词
                robot.messages[0] = {"role": "system", "content": robot.llm.create_system_prompt()}
                robot.messages.append({"role": "user", "content": user_text})
                
                response_text = ""
                # 调用 LLM 流式输出
                for chunk in robot.llm.call_deepseek_api(robot.messages):
                    response_text += chunk
                    # 实时发送文本片段到前端
                    await websocket.send_json({"type": "text_chunk", "content": chunk})
                
                robot.messages.append({"role": "assistant", "content": response_text})
                
                # 生成语音并发送给前端
                audio_file = robot.tts.to_tts(response_text)
                if audio_file:
                    with open(audio_file, "rb") as f:
                        audio_bytes = f.read()
                        await websocket.send_bytes(audio_bytes)
                    robot.tts.clean_up(audio_file)
                
                await websocket.send_json({"type": "done"})
                
    except WebSocketDisconnect:
        logger.info("WebSocket 连接已断开")
    except Exception as e:
        logger.error(f"WebSocket 处理出错: {e}")

if __name__ == "__main__":
    # 启动服务器，监听 8000 端口
    uvicorn.run(app, host="0.0.0.0", port=8000)
