import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCENE = (BASE_DIR.parent / "unitree_robots" / "g1" / "scene_29dof.xml").resolve()

ROOT_QPOS = np.array([0.0, 0.0, 0.78, 1.0, 0.0, 0.0, 0.0], dtype=np.float64)
DISPLAY_JOINTS = (
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
)

STAND_POSE = {
    "left_hip_pitch_joint": -0.35,
    "left_hip_roll_joint": 0.0,
    "left_hip_yaw_joint": 0.0,
    "left_knee_joint": 0.72,
    "left_ankle_pitch_joint": -0.37,
    "left_ankle_roll_joint": 0.0,
    "right_hip_pitch_joint": -0.35,
    "right_hip_roll_joint": 0.0,
    "right_hip_yaw_joint": 0.0,
    "right_knee_joint": 0.72,
    "right_ankle_pitch_joint": -0.37,
    "right_ankle_roll_joint": 0.0,
    "waist_yaw_joint": 0.0,
    "waist_roll_joint": 0.0,
    "waist_pitch_joint": 0.0,
    "left_shoulder_pitch_joint": 0.20,
    "left_shoulder_roll_joint": 0.18,
    "left_shoulder_yaw_joint": 0.0,
    "left_elbow_joint": 0.35,
    "left_wrist_roll_joint": 0.0,
    "left_wrist_pitch_joint": 0.0,
    "left_wrist_yaw_joint": 0.0,
    "right_shoulder_pitch_joint": 0.20,
    "right_shoulder_roll_joint": -0.18,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_joint": 0.35,
    "right_wrist_roll_joint": 0.0,
    "right_wrist_pitch_joint": 0.0,
    "right_wrist_yaw_joint": 0.0,
}

KP = {
    "leg": 220.0,
    "waist": 180.0,
    "arm": 70.0,
    "wrist": 35.0,
}

KD = {
    "leg": 18.0,
    "waist": 14.0,
    "arm": 8.0,
    "wrist": 4.0,
}


def rad_to_deg(value):
    return value * 180.0 / math.pi


def joint_group(joint_name):
    if any(name in joint_name for name in ("hip", "knee", "ankle")):
        return "leg"
    if "waist" in joint_name:
        return "waist"
    if "wrist" in joint_name:
        return "wrist"
    return "arm"


def clamp01(value):
    return max(0.0, min(1.0, value))


def smoothstep(value):
    x = clamp01(value)
    return x * x * (3.0 - 2.0 * x)


def interpolate_pose(pose_a, pose_b, alpha):
    ratio = smoothstep(alpha)
    keys = set(pose_a) | set(pose_b)
    return {
        key: pose_a.get(key, 0.0) + (pose_b.get(key, 0.0) - pose_a.get(key, 0.0)) * ratio
        for key in keys
    }


def build_joint_handles(model):
    handles = {}
    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id][0])
        joint_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        actuator_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id)
        handles[joint_name] = {
            "actuator_id": actuator_id,
            "actuator_name": actuator_name,
            "joint_id": joint_id,
            "qpos_adr": int(model.jnt_qposadr[joint_id]),
            "qvel_adr": int(model.jnt_dofadr[joint_id]),
            "ctrl_min": float(model.actuator_ctrlrange[actuator_id][0]),
            "ctrl_max": float(model.actuator_ctrlrange[actuator_id][1]),
        }
    return handles


def ensure_required_joints(joint_handles):
    required_joints = (
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
    )
    missing_joints = [joint_name for joint_name in required_joints if joint_name not in joint_handles]
    if missing_joints:
        raise RuntimeError(f"Missing required G1 arm joints: {missing_joints}")


def build_stand_pose():
    return dict(STAND_POSE)


def set_initial_pose(data, joint_handles, joint_targets):
    data.qpos[:7] = ROOT_QPOS.copy()
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    for joint_name, target in joint_targets.items():
        handle = joint_handles.get(joint_name)
        if handle is not None:
            data.qpos[handle["qpos_adr"]] = target


def apply_pd_control(data, joint_handles, joint_targets):
    for joint_name, target in joint_targets.items():
        handle = joint_handles.get(joint_name)
        if handle is None:
            continue
        q = data.qpos[handle["qpos_adr"]]
        qd = data.qvel[handle["qvel_adr"]]
        group = joint_group(joint_name)
        torque = KP[group] * (target - q) - KD[group] * qd
        data.ctrl[handle["actuator_id"]] = float(np.clip(torque, handle["ctrl_min"], handle["ctrl_max"]))


def resolve_scene_path(scene_arg):
    candidate = Path(scene_arg) if scene_arg else DEFAULT_SCENE
    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()
    return candidate


def print_pose_summary(title, pose):
    print(title)
    for joint_name in DISPLAY_JOINTS:
        value = pose.get(joint_name, 0.0)
        print(f"  {joint_name}: {value:.3f} rad ({rad_to_deg(value):.1f} deg)")


def run_motion_demo(scene_path, motion, print_targets=False):
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    joint_handles = build_joint_handles(model)
    ensure_required_joints(joint_handles)

    if print_targets:
        print_pose_summary("Neutral pose:", motion.neutral_pose)
        print_pose_summary("Preparation pose:", motion.preparation_pose)

    initial_pose = motion.sample_pose(0.0)
    set_initial_pose(data, joint_handles, initial_pose)
    mujoco.mj_forward(model, data)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            target_pose = motion.sample_pose(data.time)
            apply_pd_control(data, joint_handles, target_pose)
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)
