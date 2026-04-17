import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mujoco
import mujoco.viewer
import numpy as np

import config
from g1_motion_assets import get_motion, get_motion_names
from g1_stand_pose import (
    DEFAULT_SCENE,
    apply_pd_control,
    build_joint_handles,
    build_stand_pose,
    ensure_required_joints,
    resolve_scene_path,
    set_initial_pose,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 18080
ACTION_NAMES = set(get_motion_names())
ASSIST_PROFILE_SPECS = {
    "default": {
        "anchor_offset": np.array([0.06, 0.0, 1.02], dtype=np.float64),
        "rest_bias": 0.18,
        "stiffness": 220.0,
        "damping": 36.0,
    },
    "medium": {
        "anchor_offset": np.array([0.08, 0.0, 1.05], dtype=np.float64),
        "rest_bias": 0.22,
        "stiffness": 245.0,
        "damping": 40.0,
    },
    "strong": {
        "anchor_offset": np.array([0.10, 0.0, 1.08], dtype=np.float64),
        "rest_bias": 0.27,
        "stiffness": 272.0,
        "damping": 45.0,
    },
}
HOTKEY_ACTIONS = {
    "1": "wave1",
    "2": "wave2",
    "3": "wave3",
    "Q": "nod1",
    "W": "nod2",
    "A": "bow1",
    "S": "bow2",
    "Z": "soothe1",
    "X": "soothe2",
    "C": "invite1",
    "V": "invite2",
    "0": "reset",
}


class BalanceAssist:
    def __init__(self, anchor_point, rest_length, stiffness=220.0, damping=36.0):
        self.anchor_point = np.array(anchor_point, dtype=np.float64)
        self.rest_length = float(rest_length)
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.enabled = True

    def compute_force(self, position, velocity):
        displacement = self.anchor_point - position
        distance = float(np.linalg.norm(displacement))
        if distance < 1e-6:
            return np.zeros(3, dtype=np.float64)
        direction = displacement / distance
        speed_along_band = float(np.dot(velocity, direction))
        extension = distance - self.rest_length
        if extension <= 0.0:
            return np.zeros(3, dtype=np.float64)
        return (self.stiffness * extension - self.damping * speed_along_band) * direction

    def configure(self, anchor_point, rest_length, stiffness, damping):
        self.anchor_point = np.array(anchor_point, dtype=np.float64)
        self.rest_length = float(rest_length)
        self.stiffness = float(stiffness)
        self.damping = float(damping)


class RuntimeController:
    def __init__(self, model, data):
        self.model = model
        self.data = data
        self.joint_handles = build_joint_handles(model)
        ensure_required_joints(self.joint_handles)
        self.state_lock = threading.Lock()
        self.status = "idle"
        self.active_action = None
        self.motion = None
        self.motion_start_time = 0.0
        self.last_completed_action = None
        self.previous_ctrl = np.zeros(model.nu, dtype=np.float64)

    def request_action(self, action_name):
        with self.state_lock:
            if action_name == "reset":
                self.status = "idle"
                self.active_action = None
                self.motion = None
                self.motion_start_time = self.data.time
                self.previous_ctrl[:] = 0.0
                logger.info("Accepted motion request: reset")
                return True, self.status

            if self.motion is not None:
                logger.info("Rejected motion request: %s (runtime busy with %s)", action_name, self.active_action)
                return False, self.status

            self.motion = get_motion(action_name)
            self.active_action = action_name
            self.motion_start_time = self.data.time
            self.status = "busy"
            logger.info(
                "Accepted motion request: %s (assist_profile=%s)",
                action_name,
                self.motion.assist_profile,
            )
            return True, self.status

    def _finish_motion_if_needed(self):
        if self.motion is None:
            return
        elapsed = self.data.time - self.motion_start_time
        if elapsed > self.motion.total_duration:
            self.last_completed_action = self.active_action
            logger.info("Motion completed: %s", self.last_completed_action)
            self.status = "idle"
            self.active_action = None
            self.motion = None

    def current_target_pose(self):
        with self.state_lock:
            self._finish_motion_if_needed()
            base_pose = build_stand_pose()
            if self.motion is None:
                return base_pose
            elapsed = max(0.0, self.data.time - self.motion_start_time)
            overlay_pose = self.motion.sample_pose(elapsed)
            base_pose.update(overlay_pose)
            return base_pose

    def current_assist_profile(self):
        with self.state_lock:
            self._finish_motion_if_needed()
            if self.motion is None:
                return "default"
            return self.motion.assist_profile

    def current_state(self):
        with self.state_lock:
            self._finish_motion_if_needed()
            return {
                "ok": True,
                "status": self.status,
                "active_action": self.active_action,
                "assist_profile": self.motion.assist_profile if self.motion is not None else "default",
                "last_completed_action": self.last_completed_action,
                "sim_time": round(float(self.data.time), 4),
            }

    def reset_control_memory(self):
        self.previous_ctrl[:] = 0.0


class RuntimeHttpHandler(BaseHTTPRequestHandler):
    controller = None

    def _write_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/state":
            self._write_json(404, {"ok": False, "error": "not_found"})
            return
        self._write_json(200, self.controller.current_state())

    def do_POST(self):
        if self.path != "/action":
            self._write_json(404, {"ok": False, "error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json(400, {"ok": False, "error": "invalid_json"})
            return

        action_name = payload.get("action")
        if action_name not in ACTION_NAMES | {"reset"}:
            self._write_json(400, {"ok": False, "error": "invalid_action"})
            return

        accepted, state = self.controller.request_action(action_name)
        self._write_json(
            200,
            {
                "ok": True,
                "accepted": accepted,
                "state": state,
                "action": action_name,
            },
        )

    def log_message(self, format_, *args):
        logger.debug("runtime http: " + format_, *args)


def start_http_server(controller):
    RuntimeHttpHandler.controller = controller
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), RuntimeHttpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("G1 runtime HTTP server started at http://%s:%s", HTTP_HOST, HTTP_PORT)
    return server


def build_assist_profiles(torso_position):
    profiles = {}
    for name, spec in ASSIST_PROFILE_SPECS.items():
        anchor_point = torso_position + spec["anchor_offset"]
        initial_distance = float(np.linalg.norm(anchor_point - torso_position))
        profiles[name] = {
            "name": name,
            "anchor_point": anchor_point,
            "rest_length": max(0.2, initial_distance - spec["rest_bias"]),
            "stiffness": spec["stiffness"],
            "damping": spec["damping"],
        }
    return profiles


def main():
    scene_path = resolve_scene_path(config.ROBOT_SCENE or str(DEFAULT_SCENE))
    logger.info("Loading G1 runtime scene: %s", scene_path)
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    model.opt.timestep = config.SIMULATE_DT
    controller = RuntimeController(model, data)
    set_initial_pose(data, controller.joint_handles, build_stand_pose())
    mujoco.mj_forward(model, data)
    controller.reset_control_memory()

    torso_body_id = model.body("torso_link").id
    balance_assist = None
    assist_profiles = None
    assist_adjustment = {"rest_length_delta": 0.0}
    last_assist_profile = None
    if config.ENABLE_ELASTIC_BAND:
        torso_position = data.xpos[torso_body_id].copy()
        assist_profiles = build_assist_profiles(torso_position)
        default_profile = assist_profiles["default"]
        balance_assist = BalanceAssist(
            anchor_point=default_profile["anchor_point"],
            rest_length=default_profile["rest_length"],
            stiffness=default_profile["stiffness"],
            damping=default_profile["damping"],
        )
        logger.info(
            "Balance assist enabled. Hotkeys: 7 loosen, 8 tighten, 9 toggle support. "
            "Profiles: default=%s medium=%s strong=%s",
            round(assist_profiles["default"]["rest_length"], 3),
            round(assist_profiles["medium"]["rest_length"], 3),
            round(assist_profiles["strong"]["rest_length"], 3),
        )

    glfw = mujoco.glfw.glfw

    def current_profile_name():
        if controller.motion is None:
            return "default"
        return controller.motion.assist_profile

    def apply_assist_profile(profile_name, reason):
        nonlocal last_assist_profile
        if balance_assist is None or assist_profiles is None:
            return
        base_profile = assist_profiles[profile_name]
        balance_assist.configure(
            anchor_point=base_profile["anchor_point"],
            rest_length=max(0.2, base_profile["rest_length"] + assist_adjustment["rest_length_delta"]),
            stiffness=base_profile["stiffness"],
            damping=base_profile["damping"],
        )
        last_assist_profile = profile_name
        logger.info(
            "Using assist profile=%s rest_length=%.3f stiffness=%.1f damping=%.1f anchor=%s reason=%s action=%s",
            profile_name,
            balance_assist.rest_length,
            balance_assist.stiffness,
            balance_assist.damping,
            np.round(balance_assist.anchor_point, 3).tolist(),
            reason,
            controller.active_action or "idle",
        )

    def key_callback(key):
        key_map = {
            glfw.KEY_1: "wave1",
            glfw.KEY_2: "wave2",
            glfw.KEY_3: "wave3",
            glfw.KEY_Q: "nod1",
            glfw.KEY_W: "nod2",
            glfw.KEY_A: "bow1",
            glfw.KEY_S: "bow2",
            glfw.KEY_Z: "soothe1",
            glfw.KEY_X: "soothe2",
            glfw.KEY_C: "invite1",
            glfw.KEY_V: "invite2",
            glfw.KEY_0: "reset",
        }
        if balance_assist is not None:
            if key == glfw.KEY_7:
                assist_adjustment["rest_length_delta"] += 0.05
                apply_assist_profile(current_profile_name(), "manual_loosen")
                return
            if key == glfw.KEY_8:
                assist_adjustment["rest_length_delta"] -= 0.05
                apply_assist_profile(current_profile_name(), "manual_tighten")
                return
            if key == glfw.KEY_9:
                balance_assist.enabled = not balance_assist.enabled
                logger.info("Balance assist enabled=%s", balance_assist.enabled)
                return
        action_name = key_map.get(key)
        if action_name is None:
            return
        accepted, _ = controller.request_action(action_name)
        logger.info("Hotkey %s -> %s (accepted=%s)", key, action_name, accepted)

    server = start_http_server(controller)

    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        logger.info(
            "G1 runtime started. Hotkeys: 1/2/3=wave, Q/W=nod, A/S=bow, Z/X=soothe, C/V=invite, 0=reset."
        )
        while viewer.is_running():
            target_pose = controller.current_target_pose()
            data.xfrc_applied[:] = 0.0
            if balance_assist is not None and balance_assist.enabled:
                assist_profile_name = controller.current_assist_profile()
                if assist_profile_name != last_assist_profile:
                    apply_assist_profile(assist_profile_name, "profile_switch")
                support_force = balance_assist.compute_force(data.xpos[torso_body_id], data.qvel[:3])
                data.xfrc_applied[torso_body_id, :3] = support_force
            controller.previous_ctrl = apply_pd_control(
                data,
                controller.joint_handles,
                target_pose,
                previous_ctrl=controller.previous_ctrl,
            )
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)

    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
