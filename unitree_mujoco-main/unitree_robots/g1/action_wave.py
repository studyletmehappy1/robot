import argparse
import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCENE = BASE_DIR / "scene_23dof.xml"

PREP_DURATION = 1.35
WAVE_FREQUENCY = 1.5
WAVE_CYCLES = 3
WAVE_DURATION = WAVE_CYCLES / WAVE_FREQUENCY
RETURN_DURATION = 1.35
TOTAL_DURATION = PREP_DURATION + WAVE_DURATION + RETURN_DURATION


def rad_to_deg(value):
    return value * 180.0 / math.pi


# 稳定站立姿态。单位全部是弧度。
BASE_POSE = {
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

# 右臂自然下垂。
RIGHT_ARM_NEUTRAL = {
    "right_shoulder_pitch_joint": 0.20,
    "right_shoulder_roll_joint": -0.18,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_joint": 0.35,
    "right_wrist_roll_joint": 0.0,
    "right_wrist_pitch_joint": 0.0,
    "right_wrist_yaw_joint": 0.0,
}

# 右臂抬手准备姿态。目标是“前举招手”，不是侧平举摆臂。
# 结合当前用户反馈，shoulder_pitch 的正方向会把手臂带向后方，
# 因此前举动作需要使用负值把肘部带到身体斜前方。
# 注意：G1 当前 23DOF/29DOF 模型都没有独立的 elbow roll，
# 因此后续挥手主自由度使用 right_shoulder_yaw_joint 作为最接近的等效旋转自由度。
RIGHT_ARM_PREP = {
    "right_shoulder_pitch_joint": -0.68,
    "right_shoulder_roll_joint": -0.24,
    "right_shoulder_yaw_joint": -0.08,
    "right_elbow_joint": 1.52,
    "right_wrist_roll_joint": 0.42,
    "right_wrist_pitch_joint": -0.08,
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


def build_neutral_pose():
    pose = dict(BASE_POSE)
    pose.update(RIGHT_ARM_NEUTRAL)
    return pose


def build_preparation_pose():
    pose = dict(BASE_POSE)
    pose.update(RIGHT_ARM_PREP)
    return pose


def build_wave_center_pose():
    return build_preparation_pose()


def get_wave_target_pose(t):
    neutral_pose = build_neutral_pose()
    prep_pose = build_preparation_pose()

    if t <= PREP_DURATION:
        return interpolate_pose(neutral_pose, prep_pose, t / PREP_DURATION)

    if t <= PREP_DURATION + WAVE_DURATION:
        tau = t - PREP_DURATION
        phase = 2.0 * math.pi * WAVE_FREQUENCY * tau

        wave_pose = dict(prep_pose)
        # 机械约束说明：
        # 当前 G1 模型没有独立 elbow roll，所以用 shoulder_yaw 作为最接近的
        # “前臂左右招手”的主自由度。肩 pitch/roll 与肘 pitch 在挥手阶段保持稳定，
        # 只通过 shoulder_yaw + wrist_roll 做礼貌、克制的社交挥手。
        wave_signal = float(np.sin(phase))
        wave_pose["right_shoulder_yaw_joint"] = RIGHT_ARM_PREP["right_shoulder_yaw_joint"] + 0.26 * wave_signal
        wave_pose["right_shoulder_pitch_joint"] = RIGHT_ARM_PREP["right_shoulder_pitch_joint"]
        wave_pose["right_shoulder_roll_joint"] = RIGHT_ARM_PREP["right_shoulder_roll_joint"]
        wave_pose["right_elbow_joint"] = RIGHT_ARM_PREP["right_elbow_joint"]
        wave_pose["right_wrist_pitch_joint"] = RIGHT_ARM_PREP["right_wrist_pitch_joint"]
        wave_pose["right_wrist_yaw_joint"] = RIGHT_ARM_PREP["right_wrist_yaw_joint"]
        # 手腕只做很小的同步修正，让掌面更像朝前打招呼，而不是主导摆动。
        wave_pose["right_wrist_roll_joint"] = RIGHT_ARM_PREP["right_wrist_roll_joint"] + 0.10 * wave_signal
        return wave_pose

    if t <= TOTAL_DURATION:
        # 恰好 3 个完整周期后，sin 回到 0，因此末态与 prep_pose 一致，可直接平滑回位。
        tau = t - (PREP_DURATION + WAVE_DURATION)
        return interpolate_pose(prep_pose, neutral_pose, tau / RETURN_DURATION)

    return neutral_pose


def set_initial_pose(data, joint_handles, joint_targets):
    data.qpos[:7] = np.array([0.0, 0.0, 0.78, 1.0, 0.0, 0.0, 0.0], dtype=np.float64)
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
        candidate = BASE_DIR / candidate
    return candidate.resolve()


def parse_args():
    parser = argparse.ArgumentParser(description="Unitree G1 natural wave demo for MuJoCo")
    parser.add_argument(
        "--scene",
        default=str(DEFAULT_SCENE),
        help="要加载的 MuJoCo 场景 XML，默认 scene_23dof.xml",
    )
    parser.add_argument(
        "--print-targets",
        action="store_true",
        help="打印关键右臂姿态的弧度和角度，方便调参",
    )
    return parser.parse_args()


def print_pose_summary(title, pose):
    print(title)
    for joint_name in (
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
        "right_wrist_pitch_joint",
    ):
        value = pose[joint_name]
        print(f"  {joint_name}: {value:.3f} rad ({rad_to_deg(value):.1f} deg)")


def main():
    args = parse_args()
    scene_path = resolve_scene_path(args.scene)
    print(f"正在加载 G1 场景: {scene_path}")

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)
    joint_handles = build_joint_handles(model)

    required_joints = [
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
    ]
    missing_joints = [joint_name for joint_name in required_joints if joint_name not in joint_handles]
    if missing_joints:
        raise RuntimeError(f"缺少必要右臂关节，无法执行挥手动作: {missing_joints}")

    if args.print_targets:
        print_pose_summary("Neutral pose:", build_neutral_pose())
        print_pose_summary("Preparation pose:", build_preparation_pose())
        print_pose_summary("Wave center pose:", build_wave_center_pose())

    initial_pose = get_wave_target_pose(0.0)
    set_initial_pose(data, joint_handles, initial_pose)
    mujoco.mj_forward(model, data)

    print("开始执行三阶段挥手：Preparation -> Oscillation(3 cycles) -> Return")
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            target_pose = get_wave_target_pose(data.time)
            apply_pd_control(data, joint_handles, target_pose)
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)


if __name__ == "__main__":
    main()
