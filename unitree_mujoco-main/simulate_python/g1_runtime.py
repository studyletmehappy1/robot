import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mujoco
import mujoco.viewer
import numpy as np

import config
from g1_stand_pose import (
    DEFAULT_SCENE,
    apply_pd_control,
    build_joint_handles,
    build_stand_pose,
    ensure_required_joints,
    resolve_scene_path,
    set_initial_pose,
)
from g1_wave_assets import get_motion

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 18080
WAVE3_ASSIST_SCALE = {
    "rest_length_delta": -0.07,
    "stiffness_mult": 1.18,
    "damping_mult": 1.22,
    "anchor_offset": np.array([0.09, 0.0, 1.06], dtype=np.float64),
}


class BalanceAssist:
    def __init__(self, anchor_point, rest_length, stiffness=220.0, damping=36.0):
        self.anchor_point = np.array(anchor_point, dtype=np.float64)
        self.rest_length = float(rest_length)
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.enabled = True

    def retune(self, delta_length):
        self.rest_length = max(0.2, self.rest_length + delta_length)

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
                return True, self.status

            if self.motion is not None:
                return False, self.status

            self.motion = get_motion(action_name)
            self.active_action = action_name
            self.motion_start_time = self.data.time
            self.status = "busy"
            logger.info("Accepted motion request: %s", action_name)
            return True, self.status

    def _finish_motion_if_needed(self):
        if self.motion is None:
            return
        elapsed = self.data.time - self.motion_start_time
        if elapsed > self.motion.total_duration:
            self.last_completed_action = self.active_action
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

    def current_state(self):
        with self.state_lock:
            self._finish_motion_if_needed()
            return {
                "ok": True,
                "status": self.status,
                "active_action": self.active_action,
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
        if action_name not in {"wave1", "wave2", "wave3", "reset"}:
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
    default_assist_profile = None
    wave3_assist_profile = None
    last_assist_profile = None
    if config.ENABLE_ELASTIC_BAND:
        torso_position = data.xpos[torso_body_id].copy()
        default_anchor = torso_position + np.array([0.06, 0.0, 1.02], dtype=np.float64)
        default_initial_distance = float(np.linalg.norm(default_anchor - torso_position))
        default_rest_length = max(0.2, default_initial_distance - 0.18)
        default_assist_profile = {
            "name": "default",
            "anchor_point": default_anchor,
            "rest_length": default_rest_length,
            "stiffness": 220.0,
            "damping": 36.0,
        }
        wave3_anchor = torso_position + WAVE3_ASSIST_SCALE["anchor_offset"]
        wave3_initial_distance = float(np.linalg.norm(wave3_anchor - torso_position))
        wave3_assist_profile = {
            "name": "wave3",
            "anchor_point": wave3_anchor,
            "rest_length": max(0.2, wave3_initial_distance - 0.25),
            "stiffness": default_assist_profile["stiffness"] * WAVE3_ASSIST_SCALE["stiffness_mult"],
            "damping": default_assist_profile["damping"] * WAVE3_ASSIST_SCALE["damping_mult"],
        }
        balance_assist = BalanceAssist(
            anchor_point=default_assist_profile["anchor_point"],
            rest_length=default_assist_profile["rest_length"],
            stiffness=default_assist_profile["stiffness"],
            damping=default_assist_profile["damping"],
        )
        logger.info(
            "Balance assist enabled. default_anchor=%s default_rest_length=%.3f wave3_anchor=%s wave3_rest_length=%.3f. Hotkeys: 7 loosen, 8 tighten, 9 toggle support.",
            np.round(default_assist_profile["anchor_point"], 3).tolist(),
            default_assist_profile["rest_length"],
            np.round(wave3_assist_profile["anchor_point"], 3).tolist(),
            wave3_assist_profile["rest_length"],
        )

    glfw = mujoco.glfw.glfw

    def key_callback(key):
        key_map = {
            glfw.KEY_1: "wave1",
            glfw.KEY_2: "wave2",
            glfw.KEY_3: "wave3",
            glfw.KEY_0: "reset",
        }
        if balance_assist is not None:
            if key == glfw.KEY_7:
                balance_assist.retune(+0.05)
                logger.info("Balance assist rest length loosened to %.3f", balance_assist.rest_length)
                return
            if key == glfw.KEY_8:
                balance_assist.retune(-0.05)
                logger.info("Balance assist rest length tightened to %.3f", balance_assist.rest_length)
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
        logger.info("G1 runtime started. Hotkeys: 1/2/3 trigger wave, 0 resets pose.")
        while viewer.is_running():
            target_pose = controller.current_target_pose()
            data.xfrc_applied[:] = 0.0
            if balance_assist is not None and balance_assist.enabled:
                assist_profile = wave3_assist_profile if controller.active_action == "wave3" else default_assist_profile
                if assist_profile["name"] != last_assist_profile:
                    balance_assist.configure(
                        anchor_point=assist_profile["anchor_point"],
                        rest_length=assist_profile["rest_length"],
                        stiffness=assist_profile["stiffness"],
                        damping=assist_profile["damping"],
                    )
                    last_assist_profile = assist_profile["name"]
                    logger.info(
                        "Using assist profile=%s rest_length=%.3f stiffness=%.1f damping=%.1f anchor=%s action=%s",
                        assist_profile["name"],
                        balance_assist.rest_length,
                        balance_assist.stiffness,
                        balance_assist.damping,
                        np.round(balance_assist.anchor_point, 3).tolist(),
                        controller.active_action or "idle",
                    )
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
