from dataclasses import dataclass

from g1_stand_pose import build_stand_pose, interpolate_pose


@dataclass(frozen=True)
class MotionAsset:
    name: str
    neutral_pose: dict
    preparation_pose: dict
    prep_duration: float
    wave_frequency: float
    wave_cycles: int
    return_duration: float
    shoulder_yaw_amp: float
    shoulder_roll_amp: float
    elbow_amp: float
    wrist_roll_amp: float
    wrist_pitch_amp: float
    wrist_yaw_amp: float

    @property
    def wave_duration(self):
        return self.wave_cycles / self.wave_frequency

    @property
    def total_duration(self):
        return self.prep_duration + self.wave_duration + self.return_duration

    def sample_pose(self, t):
        neutral_pose = self.neutral_pose
        prep_pose = self.preparation_pose

        if t <= self.prep_duration:
            return interpolate_pose(neutral_pose, prep_pose, t / self.prep_duration)

        if t <= self.prep_duration + self.wave_duration:
            import math

            tau = t - self.prep_duration
            phase = 2.0 * math.pi * self.wave_frequency * tau
            wave_signal = math.sin(phase)

            wave_pose = dict(prep_pose)
            wave_pose["right_shoulder_yaw_joint"] = prep_pose["right_shoulder_yaw_joint"] + self.shoulder_yaw_amp * wave_signal
            wave_pose["right_shoulder_roll_joint"] = prep_pose["right_shoulder_roll_joint"] + self.shoulder_roll_amp * wave_signal
            wave_pose["right_elbow_joint"] = prep_pose["right_elbow_joint"] + self.elbow_amp * wave_signal
            wave_pose["right_wrist_roll_joint"] = prep_pose["right_wrist_roll_joint"] + self.wrist_roll_amp * wave_signal
            wave_pose["right_wrist_pitch_joint"] = prep_pose["right_wrist_pitch_joint"] + self.wrist_pitch_amp * wave_signal
            wave_pose["right_wrist_yaw_joint"] = prep_pose["right_wrist_yaw_joint"] + self.wrist_yaw_amp * wave_signal
            return wave_pose

        if t <= self.total_duration:
            tau = t - (self.prep_duration + self.wave_duration)
            return interpolate_pose(prep_pose, neutral_pose, tau / self.return_duration)

        return dict(neutral_pose)


def _neutral_pose():
    return build_stand_pose()


def _prep_pose(overrides):
    pose = build_stand_pose()
    pose.update(overrides)
    return pose


MOTION_LIBRARY = {
    "wave1": MotionAsset(
        name="wave1",
        neutral_pose=_neutral_pose(),
        preparation_pose=_prep_pose(
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
        wave_frequency=1.25,
        wave_cycles=3,
        return_duration=1.25,
        shoulder_yaw_amp=0.40,
        shoulder_roll_amp=0.15,
        elbow_amp=0.10,
        wrist_roll_amp=0.10,
        wrist_pitch_amp=0.0,
        wrist_yaw_amp=0.25,
    ),
    "wave2": MotionAsset(
        name="wave2",
        neutral_pose=_neutral_pose(),
        preparation_pose=_prep_pose(
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
        wave_frequency=1.5,
        wave_cycles=3,
        return_duration=1.35,
        shoulder_yaw_amp=0.26,
        shoulder_roll_amp=0.18,
        elbow_amp=0.0,
        wrist_roll_amp=0.10,
        wrist_pitch_amp=-0.20,
        wrist_yaw_amp=0.0,
    ),
    "wave3": MotionAsset(
        name="wave3",
        neutral_pose=_neutral_pose(),
        preparation_pose=_prep_pose(
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
        wave_frequency=1.5,
        wave_cycles=3,
        return_duration=1.35,
        shoulder_yaw_amp=0.26,
        shoulder_roll_amp=0.18,
        elbow_amp=0.0,
        wrist_roll_amp=0.10,
        wrist_pitch_amp=-0.20,
        wrist_yaw_amp=0.0,
    ),
}


def get_motion(name):
    motion = MOTION_LIBRARY.get(name)
    if motion is None:
        raise KeyError(f"Unknown motion asset: {name}")
    return motion
