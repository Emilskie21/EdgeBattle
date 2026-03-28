from __future__ import annotations

import json
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Optional, Tuple

from shadow_boxing.constants import Direction
from shadow_boxing.paths import repo_root


@dataclass
class PoseTrackingResult:
    camera_ok: bool
    detection_ok: bool
    direction: Optional[Direction] = None
    # Instant facing (UI / stickman), not gated by emit cooldown.
    visual_direction: Optional[Direction] = None
    # Debug-friendly fields (harmless for gameplay logic).
    pitch: float = 0.0
    yaw: float = 0.0


class PoseTracker:
    """
    Head-pose direction tracker (LEFT/RIGHT/UP/DOWN) for the game.

    Uses MediaPipe Tasks + FaceLandmarker with neutral "origin" calibration.
    """

    def __init__(self) -> None:
        self._camera_index = 0
        self._frame_w = 640
        self._frame_h = 480

        # Thresholds (degrees) tuned to match the standalone head pose script.
        self._yaw_threshold_deg = 10.0
        self._pitch_threshold_deg = 10.0

        self._smoothing_window = 5
        self._pitch_history: Deque[float] = deque(maxlen=self._smoothing_window)
        self._yaw_history: Deque[float] = deque(maxlen=self._smoothing_window)

        # Input stability/cooldown to prevent rapid repeated triggers.
        self._stable_frames_required = 3
        self._emit_cooldown_frames = 10
        self._stable_count = 0
        self._pending_dir: Optional[Direction] = None
        self._cooldown_frames = 0
        self._last_emitted: Optional[Direction] = None

        self._neutral_calibrated = False
        self._neutral_pitch = 0.0
        self._neutral_yaw = 0.0
        self._calibration_path = self._resolve_calibration_path()

        self._cap = None
        self._landmarker = None
        self._mediapipe_ok = self._init_mediapipe()

        if self._mediapipe_ok:
            self._init_camera()
            self._load_or_seed_calibration()

    def _resolve_calibration_path(self) -> Path:
        root = repo_root()
        return root / "data" / "head_pose_calibration.json"

    def _init_mediapipe(self) -> bool:
        try:
            import cv2  # noqa: F401
            import mediapipe as mp  # noqa: F401
            import numpy as np  # noqa: F401
        except Exception:
            return False

        # Imported late so unit tests / environments without deps don't crash.
        import mediapipe as mp

        self._mp = mp

        model_path = self._resolve_model_path()
        self._ensure_face_landmarker_model(model_path)

        base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        return True

    def _resolve_model_path(self) -> Path:
        model_path = repo_root() / "assets" / "models" / "face_landmarker.task"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        return model_path

    def _ensure_face_landmarker_model(self, model_path: Path) -> None:
        if model_path.exists():
            return
        url = (
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/1/face_landmarker.task"
        )
        urllib.request.urlretrieve(url, str(model_path))

    def _init_camera(self) -> None:
        import cv2

        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            # Keep camera_ok False; game will pause progression.
            self._cap = None
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_h)
        for _ in range(15):
            self._cap.read()

    def _load_or_seed_calibration(self) -> None:
        """
        Load neutral calibration if available.

        If missing, we auto-seed neutral on the first valid detection
        (so gameplay works without manually running the calibration app first).
        """
        if not self._calibration_path.exists():
            return
        try:
            payload = json.loads(self._calibration_path.read_text(encoding="utf-8"))
            self._neutral_pitch = float(payload.get("neutral_pitch", 0.0))
            self._neutral_yaw = float(payload.get("neutral_yaw", 0.0))
            self._neutral_calibrated = bool(payload.get("calibrated", True))
        except Exception:
            # Corrupt calibration shouldn't break the game.
            self._neutral_calibrated = False

    def _classify_direction(self, pitch: float, yaw: float) -> Optional[Direction]:
        if yaw <= -self._yaw_threshold_deg:
            return Direction.LEFT
        if yaw >= self._yaw_threshold_deg:
            return Direction.RIGHT
        if pitch <= -self._pitch_threshold_deg:
            return Direction.DOWN
        if pitch >= self._pitch_threshold_deg:
            return Direction.UP
        return None  # FORWARD / centered -> no input

    def _smooth_and_normalize(self, pitch: float, yaw: float) -> Tuple[float, float]:
        self._pitch_history.append(pitch)
        self._yaw_history.append(yaw)
        smoothed_pitch = float(sum(self._pitch_history) / len(self._pitch_history))
        smoothed_yaw = float(sum(self._yaw_history) / len(self._yaw_history))

        if not self._neutral_calibrated:
            return smoothed_pitch, smoothed_yaw

        return (
            smoothed_pitch - self._neutral_pitch,
            smoothed_yaw - self._neutral_yaw,
        )

    def _emit_gated_direction(self, raw_dir: Optional[Direction]) -> Optional[Direction]:
        if self._cooldown_frames > 0:
            self._cooldown_frames -= 1
            return None

        if raw_dir is None:
            self._stable_count = 0
            self._pending_dir = None
            return None

        # Direction must persist for a few frames.
        if raw_dir != self._pending_dir:
            self._pending_dir = raw_dir
            self._stable_count = 1
            return None

        self._stable_count += 1
        if self._stable_count < self._stable_frames_required:
            return None

        # Avoid spamming the same direction back-to-back.
        if self._last_emitted == raw_dir:
            self._cooldown_frames = self._emit_cooldown_frames
            return None

        self._last_emitted = raw_dir
        self._cooldown_frames = self._emit_cooldown_frames
        return raw_dir

    def update(self) -> PoseTrackingResult:
        if not self._mediapipe_ok or self._landmarker is None:
            return PoseTrackingResult(camera_ok=False, detection_ok=False)

        import cv2
        import numpy as np

        if self._cap is None:
            return PoseTrackingResult(camera_ok=False, detection_ok=False)

        ok, frame_bgr = self._cap.read()
        if not ok:
            return PoseTrackingResult(camera_ok=False, detection_ok=False)

        timestamp_ms = int(time.time() * 1000)
        frame_bgr = cv2.flip(frame_bgr, 1)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        if not result.face_landmarks:
            return PoseTrackingResult(camera_ok=True, detection_ok=False)

        img_h, img_w = frame_bgr.shape[:2]
        face_landmarks = result.face_landmarks[0]

        # Indices matched to the head-pose code you already prototyped.
        landmark_ids = (33, 263, 1, 61, 291, 199)
        face_2d = []
        face_3d = []
        nose_xy = None

        for idx in landmark_ids:
            lm = face_landmarks[idx]
            x_px, y_px = int(lm.x * img_w), int(lm.y * img_h)
            face_2d.append([x_px, y_px])
            face_3d.append([x_px, y_px, lm.z])
            if idx == 1:
                nose_xy = (float(lm.x * img_w), float(lm.y * img_h))

        if nose_xy is None:
            return PoseTrackingResult(camera_ok=True, detection_ok=False)

        face_2d_np = np.asarray(face_2d, dtype=np.float32).reshape((-1, 2))
        face_3d_np = np.asarray(face_3d, dtype=np.float32).reshape((-1, 3))
        if face_2d_np.shape[0] < 4 or face_2d_np.shape[0] != face_3d_np.shape[0]:
            return PoseTrackingResult(camera_ok=True, detection_ok=False)

        focal_length = 1.0 * img_w
        cam_matrix = np.array(
            [[focal_length, 0, img_h / 2], [0, focal_length, img_w / 2], [0, 0, 1]],
            dtype=np.float64,
        )
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        try:
            success, rot_vec, trans_vec = cv2.solvePnP(
                face_3d_np,
                face_2d_np,
                cam_matrix,
                dist_matrix,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        except cv2.error:
            return PoseTrackingResult(camera_ok=True, detection_ok=False)
        if not success:
            return PoseTrackingResult(camera_ok=True, detection_ok=False)

        rmat, _ = cv2.Rodrigues(rot_vec)
        angles, *_ = cv2.RQDecomp3x3(rmat)
        pitch_raw = float(angles[0] * 360)
        yaw_raw = float(angles[1] * 360)

        if not self._neutral_calibrated:
            # Seed neutral from the first detected face.
            self._neutral_pitch = pitch_raw
            self._neutral_yaw = yaw_raw
            self._neutral_calibrated = True
            try:
                self._calibration_path.parent.mkdir(parents=True, exist_ok=True)
                self._calibration_path.write_text(
                    json.dumps(
                        {
                            "calibrated": True,
                            "neutral_pitch": self._neutral_pitch,
                            "neutral_yaw": self._neutral_yaw,
                            "timestamp": time.time(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                # Saving calibration is optional; gameplay should still work.
                pass

            # Skip emitting input on the calibration frame.
            return PoseTrackingResult(camera_ok=True, detection_ok=True, visual_direction=None)

        pitch_norm, yaw_norm = self._smooth_and_normalize(pitch_raw, yaw_raw)
        raw_dir = self._classify_direction(pitch_norm, yaw_norm)
        direction = self._emit_gated_direction(raw_dir)

        return PoseTrackingResult(
            camera_ok=True,
            detection_ok=True,
            direction=direction,
            visual_direction=raw_dir,
            pitch=pitch_norm,
            yaw=yaw_norm,
        )

    def __del__(self) -> None:
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
