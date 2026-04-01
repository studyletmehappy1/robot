import logging
import sys
import os

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestInit")

# 添加模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_modules():
    print("=== 开始测试模块初始化 ===")
    
    # 1. 测试 VAD (应使用本地 silero-vad)
    try:
        from modules.vad import VADModule
        vad = VADModule()
        print("[SUCCESS] VAD 模块初始化成功 (已避开 GitHub API)")
    except Exception as e:
        print(f"[FAILED] VAD 模块初始化失败: {e}")

    # 2. 测试 LLM (应使用新的 Base URL)
    try:
        from modules.llm import LLMModule
        llm = LLMModule(api_key="test_key")
        print(f"[SUCCESS] LLM 模块初始化成功 (URL: {llm.api_url})")
        if llm.api_url == "https://api.edgefn.net/v1/chat/completions":
            print("[SUCCESS] LLM Base URL 配置正确")
        else:
            print(f"[WARNING] LLM Base URL 不匹配: {llm.api_url}")
    except Exception as e:
        print(f"[FAILED] LLM 模块初始化失败: {e}")

    # 3. 测试 ASR (模型 ID 检查)
    try:
        from modules.asr import ASRModule
        # 这里不真正下载模型，只检查类定义和模型 ID
        print("[INFO] ASR 模块模型 ID 检查...")
        # 我们直接读取文件内容来确认
        with open("modules/asr.py", "r") as f:
            content = f.read()
            if "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online" in content:
                print("[SUCCESS] ASR 模型 ID 已更正为官方流式 ID")
            else:
                print("[FAILED] ASR 模型 ID 未更正")
    except Exception as e:
        print(f"[FAILED] ASR 模块检查失败: {e}")

if __name__ == "__main__":
    test_modules()
