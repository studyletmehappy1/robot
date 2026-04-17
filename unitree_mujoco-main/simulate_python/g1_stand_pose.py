import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCENE = (BASE_DIR.parent / "unitree_robots" / "g1" / "scene_29dof.xml").resolve()

ROOT_QPOS = np.array([0.0, 0.0, 0.81, 1.0, 0.0, 0.0, 0.0], dtype=np.float64)
DISPLAY_JOINTS = (
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
)

STAND_POSE = {
    "left_hip_pitch_joint": -0.42,
    "left_hip_roll_joint": 0.0,
    "left_hip_yaw_joint": 0.0,
    "left_knee_joint": 0.84,
    "left_ankle_pitch_joint": -0.42,
    "left_ankle_roll_joint": 0.0,
    "right_hip_pitch_joint": -0.42,
    "right_hip_roll_joint": 0.0,
    "right_hip_yaw_joint": 0.0,
    "right_knee_joint": 0.84,
    "right_ankle_pitch_joint": -0.42,
    "right_ankle_roll_joint": 0.0,
    "waist_yaw_joint": 0.0,
    "waist_roll_joint": 0.0,
    "waist_pitch_joint": 0.03,
    "left_shoulder_pitch_joint": 0.16,
    "left_shoulder_roll_joint": 0.10,
    "left_shoulder_yaw_joint": 0.0,
    "left_elbow_joint": 0.30,
    "left_wrist_roll_joint": 0.0,
    "left_wrist_pitch_joint": 0.0,
    "left_wrist_yaw_joint": 0.0,
    "right_shoulder_pitch_joint": 0.16,
    "right_shoulder_roll_joint": -0.10,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_joint": 0.30,
    "right_wrist_roll_joint": 0.0,
    "right_wrist_pitch_joint": 0.0,
    "right_wrist_yaw_joint": 0.0,
}

KP = {
    "leg": 150.0,
    "waist": 110.0,
    "arm": 45.0,
    "wrist": 18.0,
}

KD = {
    "leg": 16.0,
    "waist": 12.0,
    "arm": 6.0,
    "wrist": 2.5,
}

MAX_CTRL_STEP = {
    "leg": 4.0,
    "waist": 1.5,
    "arm": 1.5,
    "wrist": 0.4,
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


def apply_pd_control(data, joint_handles, joint_targets, previous_ctrl=None):
    next_ctrl = np.array(previous_ctrl if previous_ctrl is not None else data.ctrl, dtype=np.float64, copy=True)
    for joint_name, target in joint_targets.items():
        handle = joint_handles.get(joint_name)
        if handle is None:
            continue
        q = data.qpos[handle["qpos_adr"]]
        qd = data.qvel[handle["qvel_adr"]]
        group = joint_group(joint_name)
        desired_torque = KP[group] * (target - q) - KD[group] * qd
        desired_torque = float(np.clip(desired_torque, handle["ctrl_min"], handle["ctrl_max"]))
        actuator_id = handle["actuator_id"]
        previous_torque = float(next_ctrl[actuator_id])
        max_step = MAX_CTRL_STEP[group]
        smoothed_torque = float(np.clip(desired_torque, previous_torque - max_step, previous_torque + max_step))
        next_ctrl[actuator_id] = smoothed_torque
    data.ctrl[:] = next_ctrl
    return next_ctrl.copy()


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
