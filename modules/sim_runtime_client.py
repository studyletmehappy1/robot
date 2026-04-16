import logging
import os

import requests

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME_URL = os.getenv("SIM_RUNTIME_URL", "http://127.0.0.1:18080")
ACTION_ENDPOINT = f"{DEFAULT_RUNTIME_URL.rstrip('/')}/action"
STATE_ENDPOINT = f"{DEFAULT_RUNTIME_URL.rstrip('/')}/state"


def send_action(action_code, timeout=1.0):
    try:
        response = requests.post(ACTION_ENDPOINT, json={"action": action_code}, timeout=timeout)
        if response.status_code != 200:
            logger.warning("Sim runtime action request failed: status=%s body=%s", response.status_code, response.text)
            return False
        payload = response.json()
        return bool(payload.get("accepted"))
    except Exception as exc:
        logger.warning("Sim runtime is unavailable when dispatching %s: %s", action_code, exc)
        return False


def get_runtime_state(timeout=1.0):
    try:
        response = requests.get(STATE_ENDPOINT, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("Failed to query sim runtime state: %s", exc)
        return {"ok": False, "runtime_available": False}
