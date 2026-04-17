from dataclasses import dataclass, field

from g1_stand_pose import build_stand_pose, interpolate_pose


@dataclass(frozen=True)
class MotionAsset:
    name: str
    neutral_pose: dict
    preparation_pose: dict
    active_pose: dict
    prep_duration: float
    active_duration: float
    return_duration: float
    oscillation_frequency: float = 0.0
    oscillation_targets: dict = field(default_factory=dict)
    assist_profile: str = "default"

    @property
    def total_duration(self):
        return self.prep_duration + self.active_duration + self.return_duration

    def sample_pose(self, t):
        neutral_pose = self.neutral_pose
        prep_pose = self.preparation_pose
        active_pose = self.active_pose

        if t <= self.prep_duration:
            return interpolate_pose(neutral_pose, prep_pose, t / self.prep_duration)

        if t <= self.prep_duration + self.active_duration:
            tau = t - self.prep_duration
            if self.active_duration <= 0:
                base_pose = dict(active_pose)
            else:
                transition_duration = min(0.25, max(0.08, self.active_duration * 0.35))
                if tau < transition_duration:
                    base_pose = interpolate_pose(prep_pose, active_pose, tau / transition_duration)
                else:
                    base_pose = dict(active_pose)

            if self.oscillation_targets and self.oscillation_frequency > 0:
                import math

                phase = 2.0 * math.pi * self.oscillation_frequency * tau
                wave_signal = math.sin(phase)
                for joint_name, amplitude in self.oscillation_targets.items():
                    base_pose[joint_name] = base_pose.get(joint_name, 0.0) + amplitude * wave_signal
            return base_pose

        if t <= self.total_duration:
            tau = t - (self.prep_duration + self.active_duration)
            return interpolate_pose(active_pose, neutral_pose, tau / self.return_duration)

        return dict(neutral_pose)


def _neutral_pose():
    return build_stand_pose()


def _pose(overrides):
    pose = build_stand_pose()
    pose.update(overrides)
    return pose


MOTION_LIBRARY = {
    "wave1": MotionAsset(
        name="wave1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "right_shoulder_pitch_joint": -1.20,
                "right_shoulder_roll_joint": -0.40,
                "right_shoulder_yaw_joint": -0.10,
                "right_elbow_joint": -0.60,
                "right_wrist_roll_joint": -1.20,
                "right_wrist_pitch_joint": -0.10,
                "right_wrist_yaw_joint": 0.0,
            }
        ),
        active_pose=_pose(
            {
                "right_shoulder_pitch_joint": -1.20,
                "right_shoulder_roll_joint": -0.40,
                "right_shoulder_yaw_joint": -0.10,
                "right_elbow_joint": -0.60,
                "right_wrist_roll_joint": -1.20,
                "right_wrist_pitch_joint": -0.10,
                "right_wrist_yaw_joint": 0.0,
            }
        ),
        prep_duration=1.2,
        active_duration=3 / 1.25,
        return_duration=1.25,
        oscillation_frequency=1.25,
        oscillation_targets={
            "right_shoulder_yaw_joint": 0.40,
            "right_shoulder_roll_joint": 0.15,
            "right_elbow_joint": 0.10,
            "right_wrist_roll_joint": 0.10,
            "right_wrist_yaw_joint": 0.25,
        },
        assist_profile="default",
    ),
    "wave2": MotionAsset(
        name="wave2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.60,
                "right_shoulder_roll_joint": 0.0,
                "right_shoulder_yaw_joint": 0.0,
                "right_elbow_joint": -0.70,
                "right_wrist_roll_joint": -1.70,
                "right_wrist_pitch_joint": 0.0,
                "right_wrist_yaw_joint": 0.0,
            }
        ),
        active_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.60,
                "right_shoulder_roll_joint": 0.0,
                "right_shoulder_yaw_joint": 0.0,
                "right_elbow_joint": -0.70,
                "right_wrist_roll_joint": -1.70,
                "right_wrist_pitch_joint": 0.0,
                "right_wrist_yaw_joint": 0.0,
            }
        ),
        prep_duration=1.35,
        active_duration=3 / 1.5,
        return_duration=1.35,
        oscillation_frequency=1.5,
        oscillation_targets={
            "right_shoulder_yaw_joint": 0.26,
            "right_shoulder_roll_joint": 0.18,
            "right_wrist_roll_joint": 0.10,
            "right_wrist_pitch_joint": -0.20,
        },
        assist_profile="default",
    ),
    "wave3": MotionAsset(
        name="wave3",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "waist_pitch_joint": 0.12,
                "waist_roll_joint": 0.0,
                "right_shoulder_pitch_joint": -0.32,
                "right_shoulder_roll_joint": -0.06,
                "right_shoulder_yaw_joint": -0.04,
                "right_elbow_joint": -0.78,
                "right_wrist_roll_joint": -1.10,
                "right_wrist_pitch_joint": -0.12,
                "right_wrist_yaw_joint": 0.08,
            }
        ),
        active_pose=_pose(
            {
                "waist_pitch_joint": 0.12,
                "waist_roll_joint": 0.0,
                "right_shoulder_pitch_joint": -0.32,
                "right_shoulder_roll_joint": -0.06,
                "right_shoulder_yaw_joint": -0.04,
                "right_elbow_joint": -0.78,
                "right_wrist_roll_joint": -1.10,
                "right_wrist_pitch_joint": -0.12,
                "right_wrist_yaw_joint": 0.08,
            }
        ),
        prep_duration=1.20,
        active_duration=3 / 1.05,
        return_duration=1.25,
        oscillation_frequency=1.05,
        oscillation_targets={
            "right_shoulder_yaw_joint": 0.12,
            "right_shoulder_roll_joint": 0.08,
            "right_elbow_joint": 0.05,
            "right_wrist_roll_joint": 0.05,
            "right_wrist_pitch_joint": -0.06,
            "right_wrist_yaw_joint": 0.10,
        },
        assist_profile="strong",
    ),
    "nod1": MotionAsset(
        name="nod1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "waist_pitch_joint": 0.05,
            }
        ),
        active_pose=_pose(
            {
                "waist_pitch_joint": 0.07,
            }
        ),
        prep_duration=0.45,
        active_duration=2 / 1.8,
        return_duration=0.55,
        oscillation_frequency=1.8,
        oscillation_targets={
            "waist_pitch_joint": -0.03,
        },
        assist_profile="default",
    ),
    "nod2": MotionAsset(
        name="nod2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "waist_pitch_joint": 0.06,
                "left_shoulder_pitch_joint": 0.12,
                "right_shoulder_pitch_joint": 0.12,
            }
        ),
        active_pose=_pose(
            {
                "waist_pitch_joint": 0.09,
                "left_shoulder_pitch_joint": 0.12,
                "right_shoulder_pitch_joint": 0.12,
            }
        ),
        prep_duration=0.55,
        active_duration=2 / 1.25,
        return_duration=0.65,
        oscillation_frequency=1.25,
        oscillation_targets={
            "waist_pitch_joint": -0.035,
        },
        assist_profile="default",
    ),
    "bow1": MotionAsset(
        name="bow1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "waist_pitch_joint": 0.08,
                "left_shoulder_pitch_joint": 0.10,
                "right_shoulder_pitch_joint": 0.10,
                "left_elbow_joint": 0.38,
                "right_elbow_joint": 0.38,
            }
        ),
        active_pose=_pose(
            {
                "waist_pitch_joint": 0.14,
                "left_shoulder_pitch_joint": 0.08,
                "right_shoulder_pitch_joint": 0.08,
                "left_elbow_joint": 0.45,
                "right_elbow_joint": 0.45,
            }
        ),
        prep_duration=0.75,
        active_duration=0.55,
        return_duration=0.85,
        assist_profile="medium",
    ),
    "bow2": MotionAsset(
        name="bow2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "waist_pitch_joint": 0.10,
                "left_shoulder_pitch_joint": 0.08,
                "right_shoulder_pitch_joint": 0.08,
                "left_elbow_joint": 0.42,
                "right_elbow_joint": 0.42,
            }
        ),
        active_pose=_pose(
            {
                "waist_pitch_joint": 0.18,
                "left_shoulder_pitch_joint": 0.05,
                "right_shoulder_pitch_joint": 0.05,
                "left_elbow_joint": 0.48,
                "right_elbow_joint": 0.48,
            }
        ),
        prep_duration=0.90,
        active_duration=0.65,
        return_duration=0.95,
        assist_profile="strong",
    ),
    "soothe1": MotionAsset(
        name="soothe1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.10,
                "right_shoulder_roll_joint": -0.02,
                "right_elbow_joint": -0.42,
                "right_wrist_pitch_joint": -0.04,
            }
        ),
        active_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.20,
                "right_shoulder_roll_joint": -0.05,
                "right_elbow_joint": -0.62,
                "right_wrist_pitch_joint": -0.10,
                "right_wrist_yaw_joint": 0.06,
            }
        ),
        prep_duration=0.70,
        active_duration=0.90,
        return_duration=0.80,
        assist_profile="default",
    ),
    "soothe2": MotionAsset(
        name="soothe2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "left_shoulder_pitch_joint": -0.06,
                "right_shoulder_pitch_joint": -0.06,
                "left_elbow_joint": 0.10,
                "right_elbow_joint": -0.10,
            }
        ),
        active_pose=_pose(
            {
                "left_shoulder_pitch_joint": -0.18,
                "right_shoulder_pitch_joint": -0.18,
                "left_shoulder_roll_joint": 0.14,
                "right_shoulder_roll_joint": -0.14,
                "left_elbow_joint": 0.26,
                "right_elbow_joint": -0.26,
            }
        ),
        prep_duration=0.80,
        active_duration=1.05,
        return_duration=0.90,
        assist_profile="medium",
    ),
    "invite1": MotionAsset(
        name="invite1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.12,
                "right_elbow_joint": -0.30,
            }
        ),
        active_pose=_pose(
            {
                "right_shoulder_pitch_joint": -0.26,
                "right_shoulder_roll_joint": -0.22,
                "right_shoulder_yaw_joint": 0.10,
                "right_elbow_joint": -0.52,
                "right_wrist_roll_joint": -0.38,
            }
        ),
        prep_duration=0.75,
        active_duration=0.95,
        return_duration=0.85,
        assist_profile="medium",
    ),
    "invite2": MotionAsset(
        name="invite2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_pose(
            {
                "left_shoulder_pitch_joint": 0.04,
                "right_shoulder_pitch_joint": 0.04,
                "left_elbow_joint": 0.16,
                "right_elbow_joint": -0.16,
            }
        ),
        active_pose=_pose(
            {
                "left_shoulder_pitch_joint": -0.14,
                "right_shoulder_pitch_joint": -0.14,
                "left_shoulder_roll_joint": 0.26,
                "right_shoulder_roll_joint": -0.26,
                "left_elbow_joint": 0.08,
                "right_elbow_joint": -0.08,
                "left_wrist_roll_joint": 0.18,
                "right_wrist_roll_joint": -0.18,
            }
        ),
        prep_duration=0.80,
        active_duration=1.05,
        return_duration=0.95,
        assist_profile="medium",
    ),
}


def get_motion(name):
    motion = MOTION_LIBRARY.get(name)
    if motion is None:
        raise KeyError(f"Unknown motion asset: {name}")
    return motion


def get_motion_names():
    return tuple(MOTION_LIBRARY.keys())
