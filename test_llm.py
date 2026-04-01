import logging
import sys
import os
import re

# 将当前目录添加到路径以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.llm import LLMModule

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def contains_emoji(text):
    """检测文本中是否包含 Emoji"""
    # 简单的正则检测，覆盖常见的 Emoji 范围
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
    return bool(emoji_pattern.search(text))

def test_llm():
    api_key = "sk-ZqcUw3Viws3jvOOn6748A3C3719b4c18Ae26D1D7E1B87299"
    llm = LLMModule(api_key=api_key)
    
    print("\n--- 测试 1: 系统提示词生成 ---")
    system_prompt = llm.create_system_prompt()
    print(f"System Prompt:\n{system_prompt}")
    
    test_queries = [
        "现在几点了？",
        "深圳今天天气怎么样？",
        "给我讲个笑话，不要带表情。"
    ]
    
    print("\n--- 测试 2: 对话响应测试 ---")
    for query in test_queries:
        print(f"\n用户: {query}")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        print("管家: ", end="", flush=True)
        full_response = ""
        for chunk in llm.call_deepseek_api(messages):
            print(chunk, end="", flush=True)
            full_response += chunk
        print()
        
        if contains_emoji(full_response):
            print("⚠️ 警告: 响应中检测到 Emoji 表情！")
        else:
            print("✅ 验证通过: 未检测到 Emoji。")
        
        if "**" in full_response or "###" in full_response:
            print("⚠️ 警告: 响应中检测到 Markdown 格式！")
        else:
            print("✅ 验证通过: 未检测到 Markdown。")

if __name__ == "__main__":
    test_llm()
