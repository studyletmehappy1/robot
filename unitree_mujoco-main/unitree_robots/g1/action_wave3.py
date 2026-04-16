import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SIM_PYTHON_DIR = BASE_DIR.parents[1] / "simulate_python"
if str(SIM_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_PYTHON_DIR))

from g1_stand_pose import resolve_scene_path, run_motion_demo
from g1_wave_assets import get_motion

DEFAULT_SCENE = BASE_DIR / "scene_29dof.xml"


def parse_args():
    parser = argparse.ArgumentParser(description="Unitree G1 child-friendly wave demo for MuJoCo")
    parser.add_argument("--scene", default=str(DEFAULT_SCENE), help="Scene XML path, default scene_29dof.xml")
    parser.add_argument("--print-targets", action="store_true", help="Print key arm poses for tuning")
    return parser.parse_args()


def main():
    args = parse_args()
    scene_path = resolve_scene_path(args.scene)
    print(f"Loading G1 scene: {scene_path}")
    print("Running wave3 demo")
    run_motion_demo(scene_path, get_motion("wave3"), print_targets=args.print_targets)


if __name__ == "__main__":
    main()
