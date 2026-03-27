import json
import time
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np


@dataclass
class PoseConfig:
    yaw_threshold_deg: float = 10.0
    pitch_threshold_deg: float = 10.0
    smoothing_window: int = 5
    max_pitch_deg: float = 35.0
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
        nose_2d = None

        landmarks = result.face_landmarks[0]
        for idx in self.LANDMARK_IDS:
            lm = landmarks[idx]
            x_px, y_px = int(lm.x * img_w), int(lm.y * img_h)
            face_2d.append([x_px, y_px])
            face_3d.append([x_px, y_px, lm.z])
            if idx == 1:
                nose_2d = (float(lm.x * img_w), float(lm.y * img_h))

        if nose_2d is None:
            return None

        face_2d_np = np.array(face_2d, dtype=np.float64)
        face_3d_np = np.array(face_3d, dtype=np.float64)

        focal_length = 1.0 * img_w
        cam_matrix = np.array(
            [[focal_length, 0, img_h / 2], [0, focal_length, img_w / 2], [0, 0, 1]],
            dtype=np.float64,
        )
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        success, rot_vec, trans_vec = cv2.solvePnP(face_3d_np, face_2d_np, cam_matrix, dist_matrix)
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

        p1 = (int(nose_2d[0]), int(nose_2d[1]))
        p2 = (int(nose_2d[0] + yaw * 10), int(nose_2d[1] - pitch * 10))
        cv2.line(frame_bgr, p1, p2, (255, 0, 0), 2)

        return {
            "pitch": pitch,
            "yaw": yaw,
            "direction": direction,
            "nose_x": nose_2d[0],
            "nose_y": nose_2d[1],
            "tx": float(trans_vec[0][0]),
            "ty": float(trans_vec[1][0]),
            "tz": float(trans_vec[2][0]),
            "frame": frame_bgr,
        }


def _draw_overlay(frame: np.ndarray, pose: Optional[Dict[str, float | str]], calibration: CalibrationState, fps: float) -> None:
    cv2.putText(frame, f"FPS: {int(fps)}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    if pose is None:
        cv2.putText(frame, "Face: Not detected", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    else:
        cv2.putText(frame, f"Dir: {pose['direction']}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, f"Pitch: {pose['pitch']:.1f}", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Yaw: {pose['yaw']:.1f}", (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    calibration_label = "Calibrated" if calibration.calibrated else "Not calibrated"
    cv2.putText(frame, f"Neutral: {calibration_label}", (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    cv2.putText(frame, "Press C calibrate, R reset, Q quit", (20, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)


def ensure_face_landmarker_model(model_path: Path) -> None:
    if model_path.exists():
        return
    model_path.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    )
    urllib.request.urlretrieve(url, str(model_path))


def run(camera_index: int = 0, save_path: str = "head_pose_calibration.json") -> None:
    config = PoseConfig()
    model_path = Path("shadow_boxing/models/face_landmarker.task")
    ensure_face_landmarker_model(model_path)
    estimator = HeadPoseEstimator(config=config, model_path=model_path)
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check camera index and permissions.")

    calibration_file = Path(save_path)
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

    prev = time.time()
    while cap.isOpened():
        ok, raw_frame = cap.read()
        if not ok:
            break

        now = time.time()
        fps = 1.0 / max(now - prev, 1e-6)
        prev = now
        timestamp_ms = int(now * 1000)
        pose = estimator.estimate_from_frame(raw_frame, timestamp_ms)

        frame_for_display = raw_frame if pose is None else pose["frame"]
        _draw_overlay(frame_for_display, pose, estimator.calibration, fps)
        cv2.imshow("Head Pose Calibration + Direction", frame_for_display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c") and pose is not None:
            estimator.calibrate_neutral(float(pose["pitch"]), float(pose["yaw"]))
            calibration_file.write_text(json.dumps(estimator.calibration.__dict__, indent=2), encoding="utf-8")
        if key == ord("r"):
            estimator.calibration = CalibrationState()
            if calibration_file.exists():
                calibration_file.unlink()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
