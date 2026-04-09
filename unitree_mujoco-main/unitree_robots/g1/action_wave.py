import argparse
import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCENE = BASE_DIR / "scene.xml"

# 用一组稳定的关节目标把机器人维持在站立姿态。
# 这里的 actuator 是 torque motor，不是 position motor，
# 所以必须自己做一层 PD 控制，不能把 data.ctrl 当作目标角直接写。
STAND_TARGETS = {
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
    "right_shoulder_pitch_joint": 0.20,
    "right_shoulder_roll_joint": -0.18,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_joint": 0.35,
    "right_wrist_roll_joint": 0.0,
    "right_wrist_pitch_joint": 0.0,
    "right_wrist_yaw_joint": 0.0,
    "left_wrist_pitch_joint": 0.0,
    "left_wrist_yaw_joint": 0.0,
}

ARM_BASE_TARGETS = {
    "left_shoulder_pitch_joint": 0.25,
    "left_shoulder_roll_joint": 1.15,
    "left_shoulder_yaw_joint": 0.18,
    "left_elbow_joint": 1.40,
    "left_wrist_roll_joint": 0.0,
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


def joint_group(joint_name):
    if "hip" in joint_name or "knee" in joint_name or "ankle" in joint_name:
        return "leg"
    if "waist" in joint_name:
        return "waist"
    if "wrist" in joint_name:
        return "wrist"
    return "arm"


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


def set_initial_pose(data, joint_handles, joint_targets):
    data.qpos[:7] = np.array([0.0, 0.0, 0.78, 1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    for joint_name, target in joint_targets.items():
        if joint_name in joint_handles:
            data.qpos[joint_handles[joint_name]["qpos_adr"]] = target


def compute_wave_targets(sim_time):
    phase = 2.0 * math.pi * 1.15 * sim_time
    targets = dict(STAND_TARGETS)
    targets.update(ARM_BASE_TARGETS)

    # 这里让“挥手”更像常规认知中的招手，而不是上下摆臂：
    # 大臂先抬起固定，前臂和腕部做小幅周期摆动。
    targets["left_shoulder_pitch_joint"] = 0.28 + 0.06 * math.sin(phase * 0.5)
    targets["left_shoulder_roll_joint"] = 1.18
    targets["left_shoulder_yaw_joint"] = 0.22 + 0.32 * math.sin(phase)
    targets["left_elbow_joint"] = 1.42 + 0.10 * math.sin(phase + 0.55)
    targets["left_wrist_roll_joint"] = 0.28 * math.sin(phase)
    return targets


def apply_pd_control(model, data, joint_handles, joint_targets):
    for joint_name, target in joint_targets.items():
        handle = joint_handles.get(joint_name)
        if handle is None:
            continue

        q = data.qpos[handle["qpos_adr"]]
        qd = data.qvel[handle["qvel_adr"]]
        group = joint_group(joint_name)
        torque = KP[group] * (target - q) - KD[group] * qd
        data.ctrl[handle["actuator_id"]] = float(
            np.clip(torque, handle["ctrl_min"], handle["ctrl_max"])
        )


def resolve_scene_path(scene_arg):
    if not scene_arg:
        return DEFAULT_SCENE

    candidate = Path(scene_arg)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate.resolve()


def parse_args():
    parser = argparse.ArgumentParser(description="G1 MuJoCo wave demo")
    parser.add_argument(
        "--scene",
        default=str(DEFAULT_SCENE),
        help="要加载的 MuJoCo 场景 XML，可以是 scene.xml / scene_23dof.xml / scene_29dof.xml",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    scene_path = resolve_scene_path(args.scene)
    print(f"正在加载 G1 场景: {scene_path}")
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    joint_handles = build_joint_handles(model)

    required_joints = [
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_joint",
        "left_wrist_roll_joint",
    ]
    missing_joints = [name for name in required_joints if name not in joint_handles]
    if missing_joints:
        raise RuntimeError(f"缺少必要关节，无法执行挥手动作: {missing_joints}")

    print("已识别控制关节，开始进入站立+挥手控制。")
    set_initial_pose(data, joint_handles, compute_wave_targets(0.0))
    mujoco.mj_forward(model, data)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        start = time.perf_counter()
        while viewer.is_running():
            sim_time = time.perf_counter() - start
            joint_targets = compute_wave_targets(sim_time)
            apply_pd_control(model, data, joint_handles, joint_targets)
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)


if __name__ == "__main__":
    main()
