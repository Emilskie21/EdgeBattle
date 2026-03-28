"""Calibration only (no game). Use ``main.py`` for calibrate-then-play."""

from calibration.head_pose_app import run


def main() -> None:
    ok = run()
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
