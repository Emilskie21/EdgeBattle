import json
import math
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

from game.paths import repo_root
from game.gameplay.game_app import ShadowBoxingGame


@dataclass
class PoseConfig:
    yaw_threshold_deg: float = 10.0
    pitch_threshold_deg: float = 10.0
    smoothing_window: int = 3
    max_pitch_deg: float = 25.0
    max_yaw_deg: float = 35.0


@dataclass
class CalibrationState:
    calibrated: bool = False
    neutral_pitch: float = 0.0
    neutral_yaw: float = 0.0
    timestamp: float = 0.0


class HeadPoseEstimator:
    """MediaPipe Tasks face-landmarker based head pose estimator."""

    LANDMARK_IDS = (33, 263, 1, 61, 291, 199)

    def __init__(self, config: PoseConfig, model_path: Path) -> None:
        self.config = config
        self.calibration = CalibrationState()
        self.pitch_history: Deque[float] = deque(maxlen=config.smoothing_window)
        self.yaw_history: Deque[float] = deque(maxlen=config.smoothing_window)

        base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def calibrate_neutral(self, pitch: float, yaw: float) -> None:
        self.calibration = CalibrationState(
            calibrated=True,
            neutral_pitch=pitch,
            neutral_yaw=yaw,
            timestamp=time.time(),
        )

    def _smooth(self, pitch: float, yaw: float) -> Tuple[float, float]:
        self.pitch_history.append(pitch)
        self.yaw_history.append(yaw)
        return (
            float(np.mean(self.pitch_history)),
            float(np.mean(self.yaw_history)),
        )

    def _normalize_against_neutral(self, pitch: float, yaw: float) -> Tuple[float, float]:
        if not self.calibration.calibrated:
            return pitch, yaw
        return (
            pitch - self.calibration.neutral_pitch,
            yaw - self.calibration.neutral_yaw,
        )

    def classify_direction(self, pitch: float, yaw: float) -> str:
        if yaw <= -self.config.yaw_threshold_deg:
            return "LEFT"
        if yaw >= self.config.yaw_threshold_deg:
            return "RIGHT"
        if pitch <= -self.config.pitch_threshold_deg:
            return "DOWN"
        if pitch >= self.config.pitch_threshold_deg:
            return "UP"
        return "FORWARD"

    def estimate_from_frame(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Optional[Dict[str, float | str]]:
        frame_bgr = cv2.flip(frame_bgr, 1)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.face_landmarks:
            return None

        img_h, img_w = frame_bgr.shape[:2]
        face_2d = []
        face_3d = []
        face_points = []

        landmarks = result.face_landmarks[0]
        for idx in self.LANDMARK_IDS:
            lm = landmarks[idx]
            x_px, y_px = int(lm.x * img_w), int(lm.y * img_h)
            face_2d.append([x_px, y_px])
            face_3d.append([x_px, y_px, lm.z])
            face_points.append((float(x_px), float(y_px)))


        face_2d_np = np.array(face_2d, dtype=np.float64)
        face_3d_np = np.array(face_3d, dtype=np.float64)

        focal_length = 1.0 * img_w
        cam_matrix = np.array(
            [[focal_length, 0, img_h / 2], [0, focal_length, img_w / 2], [0, 0, 1]],
            dtype=np.float64,
        )
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        success, rot_vec, trans_vec = cv2.solvePnP(
<<<<<<< HEAD
            face_3d_np,
            face_2d_np,
            cam_matrix,
            dist_matrix,
            flags=cv2.SOLVEPNP_SQPNP,
=======
            face_3d_np, face_2d_np, cam_matrix, dist_matrix, flags=cv2.SOLVEPNP_SQPNP
>>>>>>> origin/copilot/identify-in-game-files
        )
        if not success:
            return None

        rmat, _ = cv2.Rodrigues(rot_vec)
        angles, *_ = cv2.RQDecomp3x3(rmat)
        pitch = float(angles[0] * 360)
        yaw = float(angles[1] * 360)

        pitch, yaw = self._smooth(pitch, yaw)
        pitch, yaw = self._normalize_against_neutral(pitch, yaw)
        pitch = float(np.clip(pitch, -self.config.max_pitch_deg, self.config.max_pitch_deg))
        yaw = float(np.clip(yaw, -self.config.max_yaw_deg, self.config.max_yaw_deg))
        direction = self.classify_direction(pitch, yaw)

        return {
            "pitch": pitch,
            "yaw": yaw,
            "direction": direction,
            "face_points": face_points,
            "tx": float(trans_vec[0][0]),
            "ty": float(trans_vec[1][0]),
            "tz": float(trans_vec[2][0]),
            "frame": frame_bgr,
        }


def _face_guide_geometry(w: int, h: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Center and axis lengths (semi-axes) for a portrait face oval; centered on screen."""
    base = float(min(w, h))
    axis_x = int(base * 0.31)
    axis_y = int(base * 0.41)
    cx = w // 2
    cy = h // 2
    return (cx, cy), (axis_x, axis_y)


def _composite_calibration_background(
    frame_bgr: np.ndarray,
    center: Tuple[int, int],
    axes: Tuple[int, int],
) -> np.ndarray:
    """Blur and darken outside the face oval; keep inside sharp."""
    h, w = frame_bgr.shape[:2]
    blurred = cv2.GaussianBlur(frame_bgr, (41, 41), 0)
    dim = (blurred.astype(np.float32) * 0.4).astype(np.uint8)
    bg = cv2.addWeighted(blurred, 0.55, dim, 0.45, 0)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, center, axes, 0.0, 0.0, 360.0, 255, -1)
    inv = cv2.bitwise_not(mask)
    out = frame_bgr.copy()
    for c in range(3):
        out[:, :, c] = np.where(inv > 0, bg[:, :, c], frame_bgr[:, :, c])
    return out


def _nose_in_face_oval(face_points, center, axes):
    if not face_points:
        return False

    cx, cy = center
    ax, ay = axes

    # check that ALL face points lie inside the oval
    for x, y in face_points:
        dx = (x - cx) / ax
        dy = (y - cy) / ay
        if dx * dx + dy * dy > 1.0:
            return False

    return True


def _primary_instruction_scale(w: int) -> float:
    return float(np.clip(w / 1280.0 * 0.62, 0.38, 0.72))


def _wrap_text_to_width(text: str, font: int, scale: float, thick: int, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + " " + w
        (tw, _), _ = cv2.getTextSize(trial, font, scale, thick)
        if tw <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _draw_script_text_top_left(
    frame_bgr: np.ndarray,
    primary: str,
    w: int,
) -> None:
    """Direction / step instructions only; plain white, top-left."""
    h = frame_bgr.shape[0]
    font = cv2.FONT_HERSHEY_DUPLEX
    scale = _primary_instruction_scale(w)
    thick = 1
    color = (255, 255, 255)
    x0 = 20
    max_line_w = int(w * 0.40)
    y = max(32, int(h * 0.04))
    line_gap = int(8 + scale * 18)
    for line in _wrap_text_to_width(primary, font, scale, thick, max_line_w):
        cv2.putText(frame_bgr, line, (x0, y), font, scale, color, thick, cv2.LINE_AA)
        (_, th), _ = cv2.getTextSize(line, font, scale, thick)
        y += th + line_gap


def _draw_calibration_footer(
    frame_bgr: np.ndarray,
    footer: str,
    w: int,
    h: int,
    oval_center: Tuple[int, int],
    oval_axes: Tuple[int, int],
) -> None:
    """Constant reminder below the face oval, centered."""
    _, ay = oval_axes
    _, cy = oval_center
    font = cv2.FONT_HERSHEY_DUPLEX
    scale = float(np.clip(w / 1280.0 * 0.52, 0.34, 0.58))
    thick = 1
    color = (235, 235, 240)
    y_base = min(h - 28, cy + ay + int(h * 0.06))
    max_line_w = int(w * 0.82)
    lines = _wrap_text_to_width(footer, font, scale, thick, max_line_w)
    y = y_base
    for line in lines:
        (tw, th), _ = cv2.getTextSize(line, font, scale, thick)
        x = (w - tw) // 2
        cv2.putText(frame_bgr, line, (x, y), font, scale, color, thick, cv2.LINE_AA)
        y += th + int(6 + scale * 10)


def _draw_intro_white_screen(
    frame_bgr: np.ndarray,
    w: int,
    h: int,
    seconds_left: float,
) -> None:
    """Notice before calibration; black text on white."""
    font = cv2.FONT_HERSHEY_DUPLEX
    scale = float(np.clip(w / 1000.0 * 0.9, 0.65, 1.1))
    thick = 2
    lines = [
        "Calibration will begin shortly.",
        "Please follow the on-screen instructions.",
        f"Starting in {max(0, int(math.ceil(seconds_left)))}...",
    ]
    y = h // 2 - int(len(lines) * scale * 28)
    for line in lines:
        (tw, th), _ = cv2.getTextSize(line, font, scale, thick)
        x = (w - tw) // 2
        cv2.putText(frame_bgr, line, (x, y), font, scale, (30, 30, 35), thick, cv2.LINE_AA)
        y += th + int(14 + scale * 6)


def _draw_oval_calibration_progress(
    frame_bgr: np.ndarray,
    center: Tuple[int, int],
    axes: Tuple[int, int],
    ring_fill_fraction: float,
    face_in_guide: bool,
) -> None:
    """White oval border; green arc only for verified progress (not just face-in-frame)."""
    _ = face_in_guide  # face position does not change ring color
    outline = (250, 250, 252)
    cv2.ellipse(
        frame_bgr,
        center,
        axes,
        0.0,
        0.0,
        360.0,
        outline,
        2,
        lineType=cv2.LINE_AA,
    )
    pf = float(np.clip(ring_fill_fraction, 0.0, 1.0))
    if pf <= 0.001:
        return
    sweep = 360.0 * pf
    start = -90.0
    end = start + sweep
    cv2.ellipse(
        frame_bgr,
        center,
        axes,
        0.0,
        start,
        end,
        (60, 205, 95),
        5,
        lineType=cv2.LINE_AA,
    )


def ensure_face_landmarker_model(model_path: Path) -> None:
    if model_path.exists():
        return
    model_path.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    )
    urllib.request.urlretrieve(url, str(model_path))


CAL_SCRIPT_PRIMARY = [
    "Please center your face in the frame.",
    "Please look straight ahead.",
    "Turn your head slightly to the left.",
    "Turn your head slightly to the right.",
    "Tilt your head up.",
    "Tilt your head down.",
]
CAL_SCRIPT_FOOTER = "Keep your face within the frame while moving."
INTRO_SECONDS = 4.0
STABLE_FRAMES_CENTER = 14
STABLE_FRAMES_STRAIGHT = 18
STABLE_FRAMES_VERIFY = 14


def run(camera_index: int = 0, save_path: str = "head_pose_calibration.json") -> bool:
    game = ShadowBoxingGame()
    game.play_music("calibration", 0.7)
    win_name = "Verification"
    config = PoseConfig()
    root = repo_root()
    model_path = root / "assets" / "models" / "face_landmarker.task"
    ensure_face_landmarker_model(model_path)
    estimator = HeadPoseEstimator(config=config, model_path=model_path)
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check camera permissions.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    for _ in range(5):
        cap.read()

    calibration_file = Path(save_path)
    if not calibration_file.is_absolute():
        calibration_file = root / "data" / calibration_file.name
    if calibration_file.exists():
        try:
            calibration_data = json.loads(calibration_file.read_text(encoding="utf-8"))
            estimator.calibration = CalibrationState(
                calibrated=bool(calibration_data.get("calibrated", False)),
                neutral_pitch=float(calibration_data.get("neutral_pitch", 0.0)),
                neutral_yaw=float(calibration_data.get("neutral_yaw", 0.0)),
                timestamp=float(calibration_data.get("timestamp", 0.0)),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    verify_order = ["LEFT", "RIGHT", "UP", "DOWN"]
    phase = "intro"
    intro_end: Optional[float] = None
    verify_step = 0
    straight_hold = 0
    center_hold = 0
    verify_hold = 0
    ring_smooth = 0.0
    calibration_completed = False

    while True:
        now = time.time()

        if phase == "intro":
            ok, raw_frame = cap.read()
            if not ok:
                break
            h, w = raw_frame.shape[:2]
            if intro_end is None:
                intro_end = now + INTRO_SECONDS
            frame_for_display = np.full((h, w, 3), 255, dtype=np.uint8)
            _draw_intro_white_screen(frame_for_display, w, h, max(0.0, (intro_end or now) - now))
            cv2.imshow(win_name, frame_for_display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                cap.release()
                cv2.destroyAllWindows()
                return False
            if now >= (intro_end or 0.0):
                phase = "center"
            continue

        ok, raw_frame = cap.read()
        if not ok:
            break
        timestamp_ms = int(now * 1000)
        pose = estimator.estimate_from_frame(raw_frame, timestamp_ms)
        if pose is None:
            frame_for_display = cv2.flip(raw_frame, 1)
        else:
            frame_for_display = pose["frame"].copy()

        h, w = frame_for_display.shape[:2]
        center, axes = _face_guide_geometry(w, h)
        direction = str(pose["direction"]) if pose is not None else "NONE"
        face_in_guide = False
        if pose is not None:
            face_in_guide = _nose_in_face_oval(
                pose["face_points"],
                # float(pose["nose_x"]),
                # float(pose["nose_y"]),
                center,
                axes,
            )

        if phase == "center":
            if pose is not None and face_in_guide:
                center_hold += 1
            else:
                center_hold = 0
            if center_hold >= STABLE_FRAMES_CENTER:
                phase = "straight"
                straight_hold = 0
                center_hold = 0

        elif phase == "straight":
            if pose is not None and face_in_guide and direction == "FORWARD":
                straight_hold += 1
            else:
                straight_hold = 0
            if straight_hold >= STABLE_FRAMES_STRAIGHT:
                phase = "verify"
                verify_step = 0
                verify_hold = 0
                straight_hold = 0
                game.play_sound("choose", 0.2)

        elif phase == "verify":
            if verify_step >= len(verify_order):
                calibration_completed = True
                break
            if (
                pose is not None
                and face_in_guide
                and direction == verify_order[verify_step]
            ):
                verify_hold += 1
            else:
                verify_hold = 0
            if verify_hold >= STABLE_FRAMES_VERIFY:
                verify_step += 1
                verify_hold = 0
                game.play_sound("choose", 0.2)
            if verify_step >= len(verify_order):
                calibration_completed = True
                break

        if phase == "center":
            script_idx = 0
        elif phase == "straight":
            script_idx = 1
        else:
            script_idx = 2 + verify_step

        ring_target = (verify_step / 4.0) if phase == "verify" else 0.0
        ring_smooth += (ring_target - ring_smooth) * 0.2

        frame_for_display = _composite_calibration_background(
            frame_for_display, center, axes
        )
        _draw_oval_calibration_progress(
            frame_for_display,
            center,
            axes,
            ring_smooth,
            face_in_guide,
        )
        primary = CAL_SCRIPT_PRIMARY[script_idx]
        _draw_script_text_top_left(frame_for_display, primary, w)
        _draw_calibration_footer(
            frame_for_display,
            CAL_SCRIPT_FOOTER,
            w,
            h,
            center,
            axes,
        )

        cv2.imshow(win_name, frame_for_display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            return False

    cap.release()
    cv2.destroyAllWindows()
    for _ in range(12):
        cv2.waitKey(1)
    time.sleep(0.3)

    if calibration_completed:
        try:
            calibration_file.parent.mkdir(parents=True, exist_ok=True)
            cal = estimator.calibration
            payload = {
                "calibrated": True,
                "neutral_pitch": float(cal.neutral_pitch) if cal.calibrated else 0.0,
                "neutral_yaw": float(cal.neutral_yaw) if cal.calibrated else 0.0,
                "timestamp": time.time(),
            }
            calibration_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except (OSError, TypeError, ValueError):
            pass
    
    game.stop_music()

    return calibration_completed


if __name__ == "__main__":
    ok = run()
    raise SystemExit(0 if ok else 1)
