import asyncio
import json
import logging
import os

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from robot import Robot

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs("temp_audio", exist_ok=True)

api_key = "sk-ZqcUw3Viws3jvOOn6748A3C3719b4c18Ae26D1D7E1B87299"
robot = Robot(api_key=api_key)

SENTENCE_CUT_PUNCTUATIONS = ("。", "？", "！", ".", "?", "!", "；", ";")
FIRST_SENTENCE_EXTRA_PUNCTUATIONS = ("，", ",", "：", ":")


def has_pending_action_marker(text):
    return max(text.rfind("("), text.rfind("（")) > max(text.rfind(")"), text.rfind("）"))


def should_flush_segment(chunk, is_first_sentence):
    punctuations = list(SENTENCE_CUT_PUNCTUATIONS)
    if is_first_sentence:
        punctuations.extend(FIRST_SENTENCE_EXTRA_PUNCTUATIONS)
    return any(punctuation in chunk for punctuation in punctuations)


@app.get("/")
async def get():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read())
    return HTMLResponse(content="index.html not found", status_code=404)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket 已连接。")

    state = {
        "status": "SLEEP",
        "silence_chunks": 0,
        "streaming_text": "",
        "chat_lock": False,
        "has_started_speech": False,
    }

    await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    robot.asr.reset_cache()

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "text":
                    state["status"] = "PROCESSING"
                    await websocket.send_json({"type": "status", "content": "正在思考中..."})
                    asyncio.create_task(handle_chat(websocket, data.get("content", ""), state))

            elif "bytes" in message:
                audio_chunk = message["bytes"]

                if state["status"] == "SLEEP":
                    if robot.kws.detect(audio_chunk):
                        logger.info("唤醒成功。")
                        state.update(
                            {
                                "status": "AWAKE",
                                "streaming_text": "",
                                "silence_chunks": 0,
                                "has_started_speech": False,
                            }
                        )
                        robot.asr.reset_cache()
                        await websocket.send_json({"type": "status", "content": "已唤醒，正在倾听..."})

                elif state["status"] == "AWAKE":
                    if robot.vad.is_speech(audio_chunk):
                        state["has_started_speech"] = True
                        state["silence_chunks"] = 0
                    elif state["has_started_speech"]:
                        state["silence_chunks"] += 1

                    text_chunk = robot.asr.transcribe_chunk(audio_chunk, is_final=False)
                    if text_chunk:
                        state["streaming_text"] += text_chunk
                        await websocket.send_json({"type": "asr_chunk", "content": state["streaming_text"]})

                    if state["has_started_speech"] and state["silence_chunks"] > 8:
                        logger.info("判定说话结束。")
                        final_text = state["streaming_text"] + robot.asr.transcribe_chunk(b"", is_final=True)
                        state["status"] = "PROCESSING"

                        if final_text.strip():
                            await websocket.send_json({"type": "asr_final", "content": final_text})
                            await websocket.send_json({"type": "status", "content": "正在思考中..."})
                            asyncio.create_task(handle_chat(websocket, final_text, state))
                        else:
                            robot.kws.reset()
                            state["status"] = "SLEEP"
                            await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    except WebSocketDisconnect:
        logger.info("连接断开。")
    except Exception as exc:
        logger.error("WS 异常: %s", exc)


async def handle_chat(websocket, text, state):
    if state["chat_lock"]:
        return
    state["chat_lock"] = True

    try:
        robot.messages[0] = {"role": "system", "content": robot.llm.create_system_prompt()}
        robot.messages.append({"role": "user", "content": text})

        if len(robot.messages) > 21:
            robot.messages = [robot.messages[0]] + robot.messages[-20:]

        response_text = ""
        sentence_buffer = ""
        is_first_sentence = True
        action_sent = False
        audio_task_queue = asyncio.Queue()

        async def audio_worker():
            while True:
                item = await audio_task_queue.get()
                try:
                    if item is None:
                        return

                    segment, action = item
                    audio_results = await robot.tts.to_tts_many_async(segment)
                    for chunk_text, audio_file in audio_results:
                        await websocket.send_json({"type": "sentence_text", "content": chunk_text})
                        with open(audio_file, "rb") as file:
                            await websocket.send_bytes(file.read())
                        robot.tts.clean_up(audio_file)

                    if action and action != "无动作":
                        robot.dispatch_action(action)
                        await websocket.send_json({"type": "action", "content": action})
                finally:
                    audio_task_queue.task_done()

        worker_task = asyncio.create_task(audio_worker())

        for chunk in robot.llm.call_deepseek_api(robot.messages):
            response_text += chunk
            sentence_buffer += chunk

            if should_flush_segment(chunk, is_first_sentence):
                if has_pending_action_marker(sentence_buffer):
                    continue

                segment = sentence_buffer.strip()
                if segment:
                    reply_text, action = robot.llm.extract_reply_and_action(segment)
                    if reply_text:
                        await audio_task_queue.put((reply_text, action))
                        is_first_sentence = False
                        if action != "无动作":
                            action_sent = True
                    elif action != "无动作":
                        robot.dispatch_action(action)
                        await websocket.send_json({"type": "action", "content": action})
                        action_sent = True
                sentence_buffer = ""

        if sentence_buffer.strip():
            reply_text, action = robot.llm.extract_reply_and_action(sentence_buffer.strip())
            if reply_text:
                await audio_task_queue.put((reply_text, action))
                if action != "无动作":
                    action_sent = True
            elif action != "无动作":
                robot.dispatch_action(action)
                await websocket.send_json({"type": "action", "content": action})
                action_sent = True

        await audio_task_queue.put(None)
        await worker_task

        clean_response, final_action = robot.llm.extract_reply_and_action(response_text)
        if clean_response:
            robot.messages.append({"role": "assistant", "content": clean_response})

        if final_action != "无动作" and not action_sent:
            robot.dispatch_action(final_action)
            await websocket.send_json({"type": "action", "content": final_action})

        await websocket.send_json({"type": "done"})
        robot.kws.reset()
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    except Exception as exc:
        logger.error("对话处理失败: %s", exc)
        robot.kws.reset()
        state["status"] = "SLEEP"
        await websocket.send_json({"type": "status", "content": "已进入休眠，等待唤醒..."})
    finally:
        state["chat_lock"] = False


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
