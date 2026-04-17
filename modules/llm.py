import datetime
import json
import logging
import re

import requests

from modules.action_dispatcher import parse_llm_actions

logger = logging.getLogger(__name__)

tz_beijing = datetime.timezone(datetime.timedelta(hours=8))


class LLMModule:
    ACTION_PATTERN = re.compile(
        r"^(?P<reply>.*?)(?:\s*)[\(（](?P<action>[\w\u4e00-\u9fff-]{1,32})[\)）]\s*$",
        re.DOTALL,
    )

    def __init__(self, api_key, api_url="https://api.edgefn.net/v1/chat/completions", model="DeepSeek-V3.2"):
        logger.info("正在初始化 LLM 模块 (model=%s)...", model)
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        logger.info("LLM 模块初始化完成。")

    def get_current_weather(self, city="深圳"):
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.54&longitude=114.06&current_weather=true"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current_weather", {})
                temp = current.get("temperature", "未知")
                weathercode = current.get("weathercode", 0)
                weather_map = {
                    0: "晴空万里",
                    1: "基本晴朗",
                    2: "局部多云",
                    3: "多云",
                    45: "有雾",
                    48: "有雾",
                    51: "毛毛雨",
                    53: "小雨",
                    55: "中雨",
                    61: "小雨",
                    63: "中雨",
                    65: "大雨",
                    71: "小雪",
                    73: "中雪",
                    75: "大雪",
                    80: "阵雨",
                    81: "中阵雨",
                    82: "强阵雨",
                    85: "阵雪",
                    86: "强阵雪",
                    95: "雷暴",
                    96: "雷暴伴冰雹",
                    99: "强雷暴伴冰雹",
                }
                weather_desc = weather_map.get(weathercode, "天气平稳")
                return f"{city}当前{weather_desc}，气温{temp}摄氏度。"
        except Exception as exc:
            logger.error("获取天气失败: %s", exc)
        return f"{city}当前天气信息暂时无法获取。"

    def get_current_time_info(self):
        now_beijing = datetime.datetime.now(tz_beijing)
        date_str = now_beijing.strftime("%Y年%m月%d日")
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[now_beijing.weekday()]
        time_str = now_beijing.strftime("%H:%M")

        hour = now_beijing.hour
        if 5 <= hour < 12:
            period = "上午"
        elif 12 <= hour < 14:
            period = "中午"
        elif 14 <= hour < 18:
            period = "下午"
        elif 18 <= hour < 24:
            period = "晚上"
        else:
            period = "凌晨"

        return f"今天是{date_str}，{weekday}，现在是北京时间{time_str}，属于{period}。"

    def create_system_prompt(self):
        time_info = self.get_current_time_info()
        weather_info = self.get_current_weather()

        return (
            "你是 Unitree G1 语音交互机器人，形象成熟、自然、礼貌、亲和。\n"
            "你的表达要简洁、口语化、适合语音播报，不要使用 Markdown，不要使用 Emoji。\n"
            f"{time_info}\n"
            f"{weather_info}\n"
            "输出规则如下：\n"
            "1. 每次回复必须使用“自然语言正文 + 一个动作括号”的格式，动作括号放在整句最后。\n"
            "2. 每次回复结尾只能输出一个动作标记，且只能是：(挥手1)、(挥手2)、(挥手3)、(无动作)。\n"
            "3. 挥手1表示远距离欢迎、大幅度挥手，适合欢迎大家、欢迎来到展厅、远距离招呼等场景。\n"
            "4. 挥手2表示近距离、小幅度挥手，适合普通打招呼、近距离问候、轻度回应等场景。\n"
            "5. 挥手3表示更亲和、面向儿童或轻微弯腰挥手，适合小朋友、儿童互动、温柔欢迎等场景。\n"
            "6. 如果不需要任何动作，就输出(无动作)。\n"
            "7. 严禁输出任何未定义动作名或额外括号内容，例如(点头)、(解释动作)、(配合回答动作)。\n"
            "8. 正文只输出面向用户的话，不要解释你为什么选择某个动作。\n"
        )

    def extract_reply_and_action(self, text):
        reply, action_list = parse_llm_actions(text)
        action = action_list[0] if action_list else "无动作"
        return reply, action

    def call_deepseek_api(self, messages, stream=True):
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.7,
            "stream": stream,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=20,
                stream=stream,
            )
            if response.status_code != 200:
                logger.error("API 调用失败，status=%s, response=%s", response.status_code, response.text)
                yield "抱歉，我现在有点忙，请稍后再试。(无动作)"
                return

            if stream:
                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if not decoded.startswith("data: "):
                        continue
                    payload_line = decoded[6:]
                    if payload_line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload_line)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except Exception as exc:
                        logger.error("解析流式数据出错: %s", exc)
            else:
                result = response.json()
                yield result["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("LLM API 调用异常: %s", exc)
            yield "抱歉，我刚才短暂走神了，请再说一次。(无动作)"
