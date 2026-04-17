import inspect
import logging
import re

from modules.sim_runtime_client import send_action

logger = logging.getLogger(__name__)

ACTION_PATTERN = re.compile(r"[\(（]\s*([^()（）]{1,32}?)\s*[\)）]")
VALID_ACTIONS = {"挥手1", "挥手2", "挥手3", "无动作"}
WAVE_ACTIONS = {"挥手1", "挥手2", "挥手3"}


def _clean_text_spacing(text):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"\s*([，。！？；,.!?;:])\s*", r"\1", cleaned)
    cleaned = re.sub(r"([，。！？；,.!?;:])([，。！？；,.!?;:])+", r"\1", cleaned)
    cleaned = re.sub(r"^[，。！？；,.!?;:\s]+", "", cleaned)
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


def filter_allowed_actions(action_list, user_text="", clean_text=""):
    logger.info("LLM解析动作: %s", action_list)

    wave_actions = [action_name for action_name in action_list if action_name in WAVE_ACTIONS]
    other_actions = [action_name for action_name in action_list if action_name not in WAVE_ACTIONS]

    for action_name in other_actions:
        logger.warning("动作 %s 不在当前白名单内，已忽略。", action_name)

    if not wave_actions:
        logger.info("本段没有可执行的挥手动作。user_text=%s clean_text=%s", user_text, clean_text)
        return []

    filtered_actions = [wave_actions[0]]
    logger.info("本段过滤后动作: %s", filtered_actions)
    return filtered_actions


def _dispatch_runtime_action(action_code, action_name):
    ok = send_action(action_code)
    if ok:
        logger.info("ActionDispatcher: 成功下发 %s (%s)", action_name, action_code)
    else:
        logger.warning("ActionDispatcher: 下发失败 %s (%s)", action_name, action_code)
    return ok


def run_wave_action_1():
    return _dispatch_runtime_action("wave1", "挥手1")


def run_wave_action_2():
    return _dispatch_runtime_action("wave2", "挥手2")


def run_wave_action_3():
    return _dispatch_runtime_action("wave3", "挥手3")


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
    logger.info("准备下发动作列表: %s", action_list)
    for action_name in action_list:
        if dispatch_action(action_name):
            executed.append(action_name)
    logger.info("实际执行动作: %s", executed)
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
