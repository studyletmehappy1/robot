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

REPO_ROOT = Path(__file__).resolve().parent.parent
G1_ACTION_DIR = REPO_ROOT / "unitree_mujoco-main" / "unitree_robots" / "g1"
WAVE1_SCRIPT = G1_ACTION_DIR / "action_wave1.py"
DEFAULT_SCENE = "scene_23dof.xml"


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


def filter_allowed_actions(action_list, user_text="", clean_text=""):
    filtered = []
    for action_name in action_list:
        if action_name == "挥手1":
            if should_allow_wave(user_text, clean_text):
                filtered.append(action_name)
            else:
                logger.warning("当前场景不允许执行动作 %s，已忽略。", action_name)
        elif action_name in {"挥手2", "挥手3"}:
            logger.warning("动作 %s 已识别，但当前 MVP 未接线，已忽略。", action_name)
        else:
            logger.warning("动作 %s 不在当前白名单内，已忽略。", action_name)
    return filtered


def run_wave_action_1():
    if not WAVE1_SCRIPT.exists():
        logger.warning("挥手1 动作脚本不存在: %s", WAVE1_SCRIPT)
        return False

    python_executable = sys.executable or "python"
    command = [python_executable, str(WAVE1_SCRIPT), "--scene", DEFAULT_SCENE]

    try:
        subprocess.Popen(command, cwd=str(G1_ACTION_DIR))
        logger.info("ActionDispatcher: launching wave1 viewer")
        return True
    except Exception as exc:
        logger.error("启动挥手1动作失败: %s", exc)
        return False


ACTION_MAP = {
    "挥手1": run_wave_action_1,
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
