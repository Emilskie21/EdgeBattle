r"""
Entry point: run head calibration first, then the game.

If the venv is broken (pip points at an old path), recreate it:
  Remove-Item -Recurse -Force .venv
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt

Optional (developers only): set env SHADOW_BOXING_SKIP_CAL=1 to skip calibration.
"""

import os
import sys


def main() -> None:
    if os.environ.get("SHADOW_BOXING_SKIP_CAL") == "1":
        pass
    else:
        from calibration.head_pose_app import run as run_calibration

        if not run_calibration():
            print("Calibration did not finish. Run again when ready.")
            sys.exit(1)

    from shadow_boxing.gameplay.game_app import ShadowBoxingGame

    ShadowBoxingGame().run()


if __name__ == "__main__":
    main()
