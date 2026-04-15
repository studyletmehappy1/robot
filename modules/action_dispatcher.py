import asyncio
import inspect
import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ACTION_PATTERN = re.compile(r"[\(（]\s*([^()（）]{1,32}?)\s*[\)）]")
VALID_ACTIONS = {"挥手1", "挥手2", "挥手3", "无动作"}
GREETING_KEYWORDS = (
    "你好",
    "您好",
    "嗨",
    "hello",
    "欢迎",
    "迎宾",
    "欢迎来到",
    "欢迎光临",
    "欢迎回来",
    "很高兴见到你",
    "见到你",
    "初次见面",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
)
DISTANCE_WELCOME_KEYWORDS = (
    "欢迎大家",
    "欢迎各位",
    "展厅",
    "参观",
    "来宾",
    "嘉宾",
    "远处",
    "各位朋友",
)
CHILD_FRIENDLY_KEYWORDS = (
    "小朋友",
    "小朋友们",
    "小孩",
    "孩子",
    "宝宝",
    "小宝贝",
    "小朋友你好",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
G1_ACTION_DIR = REPO_ROOT / "unitree_mujoco-main" / "unitree_robots" / "g1"
WAVE1_SCRIPT = G1_ACTION_DIR / "action_wave1.py"
WAVE2_SCRIPT = G1_ACTION_DIR / "action_wave2.py"
WAVE3_SCRIPT = G1_ACTION_DIR / "action_wave3.py"
DEFAULT_SCENE = "scene_29dof.xml"


def _clean_text_spacing(text):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"\s*([，。！？；：,.!?;:])\s*", r"\1", cleaned)
    cleaned = re.sub(r"([，；：,.!?;:])([，；：,.!?;:])+", r"\1", cleaned)
    cleaned = re.sub(r"^[，。！？；：,.!?;:\s]+", "", cleaned)
    return cleaned.strip()


def parse_llm_actions(raw_text):
    raw_text = raw_text or ""
    action_list = []

    for match in ACTION_PATTERN.finditer(raw_text):
        action_name = match.group(1).strip()
        if action_name in VALID_ACTIONS:
            if action_name != "无动作":
                action_list.append(action_name)
        else:
            logger.warning("忽略未定义动作指令: %s", action_name)

    clean_text = ACTION_PATTERN.sub("", raw_text)
    clean_text = _clean_text_spacing(clean_text)
    return clean_text, action_list


def should_allow_wave(user_text, clean_text):
    combined = f"{user_text or ''} {clean_text or ''}".lower()
    return any(keyword.lower() in combined for keyword in GREETING_KEYWORDS)


def infer_wave_action(user_text="", clean_text=""):
    combined = f"{user_text or ''} {clean_text or ''}".lower()
    if any(keyword.lower() in combined for keyword in CHILD_FRIENDLY_KEYWORDS):
        return "挥手3"
    if any(keyword.lower() in combined for keyword in DISTANCE_WELCOME_KEYWORDS):
        return "挥手1"
    return "挥手2"


def filter_allowed_actions(action_list, user_text="", clean_text=""):
    wave_actions = [action_name for action_name in action_list if action_name in {"挥手1", "挥手2", "挥手3"}]
    other_actions = [action_name for action_name in action_list if action_name not in {"挥手1", "挥手2", "挥手3"}]

    for action_name in other_actions:
        logger.warning("动作 %s 不在当前白名单内，已忽略。", action_name)

    if not wave_actions:
        return []

    if not should_allow_wave(user_text, clean_text):
        logger.warning("当前场景不允许执行挥手动作，已全部忽略。")
        return []

    selected_action = infer_wave_action(user_text, clean_text)
    if selected_action not in wave_actions:
        logger.info("本地规则将动作从 %s 重映射为 %s。", wave_actions[0], selected_action)
    return [selected_action]


def _run_wave_script(script_path, action_name):
    if not script_path.exists():
        logger.warning("%s 动作脚本不存在: %s", action_name, script_path)
        return False

    python_executable = sys.executable or "python"
    command = [python_executable, str(script_path), "--scene", DEFAULT_SCENE]

    try:
        subprocess.Popen(command, cwd=str(G1_ACTION_DIR))
        logger.info("ActionDispatcher: launching %s viewer", action_name)
        return True
    except Exception as exc:
        logger.error("启动 %s 动作失败: %s", action_name, exc)
        return False


def run_wave_action_1():
    return _run_wave_script(WAVE1_SCRIPT, "wave1")


def run_wave_action_2():
    return _run_wave_script(WAVE2_SCRIPT, "wave2")


def run_wave_action_3():
    return _run_wave_script(WAVE3_SCRIPT, "wave3")


ACTION_MAP = {
    "挥手1": run_wave_action_1,
    "挥手2": run_wave_action_2,
    "挥手3": run_wave_action_3,
}


def dispatch_action(action_name):
    action_func = ACTION_MAP.get(action_name)
    if action_func is None:
        logger.warning("动作 %s 未映射到可执行入口。", action_name)
        return False
    return action_func()


def dispatch_actions(action_list):
    executed = []
    for action_name in action_list:
        if dispatch_action(action_name):
            executed.append(action_name)
    return executed


async def _call_callback(callback, *args):
    result = callback(*args)
    if inspect.isawaitable(result):
        await result


async def process_llm_response(raw_text, user_text, tts_callback, action_callback):
    clean_text, action_list = parse_llm_actions(raw_text)
    filtered_actions = filter_allowed_actions(action_list, user_text=user_text, clean_text=clean_text)

    if clean_text:
        await _call_callback(tts_callback, clean_text)

    for action_name in filtered_actions:
        await _call_callback(action_callback, action_name)

    return clean_text, filtered_actions
