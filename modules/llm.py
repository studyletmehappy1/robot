import logging
import requests
import json
import time
import datetime

logger = logging.getLogger(__name__)

# 强制使用东八区时区
tz_beijing = datetime.timezone(datetime.timedelta(hours=8))

class LLMModule:
    def __init__(self, api_key, api_url="https://api.edgefn.net/v1/chat/completions", model="deepseek-chat"):
        logger.info(f"正在初始化 LLM 模块 (模型: {model})...")
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        logger.info("LLM 模块初始化完成。")

    def get_current_weather(self, city="深圳"):
        """获取指定城市当前天气（默认深圳）"""
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.54&longitude=114.06&current_weather=true"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current_weather", {})
                temp = current.get("temperature", "未知")
                weathercode = current.get("weathercode", 0)
                
                weather_map = {
                    0: "晴空万里", 1: "基本晴朗", 2: "局部多云", 3: "多云",
                    45: "有雾", 48: "有雾",
                    51: "毛毛雨", 53: "小雨", 55: "中雨",
                    61: "小雨", 63: "中雨", 65: "大雨",
                    71: "小雪", 73: "中雪", 75: "大雪",
                    80: "阵雨", 81: "中阵雨", 82: "强阵雨",
                    85: "阵雪", 86: "强阵雪",
                    95: "雷暴", 96: "雷暴冰雹", 99: "强雷暴冰雹"
                }
                weather_desc = weather_map.get(weathercode, "天气晴朗")
                return f"{city}当前{weather_desc}，气温 {temp}°C"
        except Exception as e:
            logger.error(f"获取天气失败: {e}")
        return f"{city}当前天气信息暂时无法获取。"

    def get_current_time_info(self):
        """获取当前北京时间信息"""
        now_beijing = datetime.datetime.now(tz_beijing)
        date_str = now_beijing.strftime('%Y年%m月%d日')
        weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday = weekdays[now_beijing.weekday()]
        time_str = now_beijing.strftime('%H:%M')
        
        hour = now_beijing.hour
        if 5 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 14:
            time_period = "中午"
        elif 14 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 24:
            time_period = "晚上"
        else:
            time_period = "凌晨"
        
        return f"今天是{date_str}{weekday}，现在是北京时间 {time_str}（{time_period}）"

    def create_system_prompt(self):
        """创建包含实时信息的系统提示词"""
        time_info = self.get_current_time_info()
        weather_info = self.get_current_weather()
        
        prompt = f"""你是一个成熟、稳重、靠谱的家庭智能管家机器人。
{time_info}。
{weather_info}。

你的输出规范：
1. 严禁输出任何 Emoji 表情符号。
2. 严禁使用任何 Markdown 格式（如 **粗体**、# 标题、列表等）。
3. 只能输出纯文本和基础标点符号，方便语音合成。
4. 回答要简洁明了，口语化，像真人在交流。
5. 如果被问到时间或天气，请参考上方提供的实时信息准确回答。
"""
        return prompt

    def call_deepseek_api(self, messages, stream=True):
        """调用 DeepSeek API"""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.7,
            "stream": stream
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=20, stream=stream)
            if response.status_code != 200:
                logger.error(f"API 调用失败，状态码: {response.status_code}, 响应: {response.text}")
                yield "抱歉，我的大脑连接出了点问题。"
                return
            
            if stream:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                content = chunk['choices'][0]['delta'].get('content', '')
                                if content:
                                    yield content
                            except Exception as e:
                                logger.error(f"解析流式数据出错: {e}")
            else:
                result = response.json()
                yield result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            logger.error(f"LLM API 调用异常: {e}")
            yield "哎呀，我的思考被打断了。"
