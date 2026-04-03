import logging
import sys
from robot import Robot

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    # 替换为您在仓库中已经写好的 DeepSeek API Key
    api_key = "sk-fbf6eaff0cfc46338de931f747cca79d"
    
    print("=== 正在启动智能语音助手 (参考 bailing 架构) ===")
    print("核心组件: FunASR, Silero-VAD, DeepSeek-V3.2, Edge-TTS")
    print("支持打断、任务管理和记忆管理。")
    print("唤醒词: '小艺小艺'")
    print("按 Ctrl+C 退出程序。")
    
    robot = Robot(api_key=api_key)
    
    try:
        robot.run()
    except KeyboardInterrupt:
        print("\n[系统] 已手动退出，再见！")
    except Exception as e:
        print(f"\n[系统] 运行出错: {e}")

if __name__ == "__main__":
    main()
