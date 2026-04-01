import logging
import requests
import json
import time

logger = logging.getLogger(__name__)

class LLMModule:
    def __init__(self, api_key, api_url="https://api.edgefn.net/v1/chat/completions", model="DeepSeek-V3.2"):
        logger.info(f"正在初始化 LLM 模块 (模型: {model})...")
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        logger.info("LLM 模块初始化完成。")

    def call_deepseek_api(self, messages, stream=True):
        """
        调用 DeepSeek API。
        messages: 对话历史
        stream: 是否流式输出
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7,
            "stream": stream
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=15, stream=stream)
            if response.status_code != 200:
                logger.error(f"API 调用失败，状态码: {response.status_code}")
                return None
            
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
            return None
