"""
Vision Pipeline Module for Burn-Ex.
Integrates MediaPipe Pose estimation with zero raw-video storage.
Includes Exponential Moving Average (EMA) Coordinate Smoothing and 3D World Landmarks extraction.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import urllib.request
import numpy as np
import cv2
import mediapipe as mp

from src.config import (
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    EMA_SMOOTHING_ALPHA,
    MODELS_DIR,
)


MODEL_TASK_PATH: Path = MODELS_DIR / "pose_landmarker_lite.task"
MODEL_TASK_URL: str = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# Landmark Name Mapping to MediaPipe Pose Landmark Indices
LANDMARK_NAMES: Dict[str, int] = {
    "nose": 0,
    "left_eye_inner": 1,
    "left_eye": 2,
    "left_eye_outer": 3,
    "right_eye_inner": 4,
    "right_eye": 5,
    "right_eye_outer": 6,
    "left_ear": 7,
    "right_ear": 8,
    "mouth_left": 9,
    "mouth_right": 10,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_pinky": 17,
    "right_pinky": 18,
    "left_index": 19,
    "right_index": 20,
    "left_thumb": 21,
    "right_thumb": 22,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}


class LandmarkSmoother:
    """
    Exponential Moving Average (EMA) filter for spatial landmark coordinates.
    Filters high-frequency jitter and micro-flickers across consecutive frames.
    """

    def __init__(self, alpha: float = EMA_SMOOTHING_ALPHA) -> None:
        self.alpha = float(alpha)
        self.smoothed_landmarks: Optional[Dict[str, List[float]]] = None

    def reset(self) -> None:
        """Clear smoothed memory when tracking is interrupted."""
        self.smoothed_landmarks = None

    def smooth(
        self, raw_landmarks: Optional[Dict[str, List[float]]]
    ) -> Optional[Dict[str, List[float]]]:
        """
        Apply EMA filter: S_t = alpha * X_t + (1 - alpha) * S_{t-1}
        """
        if raw_landmarks is None:
            self.reset()
            return None

        if self.smoothed_landmarks is None:
            # Initialize with first valid measurement
            self.smoothed_landmarks = {k: list(v) for k, v in raw_landmarks.items()}
            return self.smoothed_landmarks

        smoothed: Dict[str, List[float]] = {}
        for name, current_coords in raw_landmarks.items():
            if name in self.smoothed_landmarks:
                prev_coords = self.smoothed_landmarks[name]
                # Smooth x, y, z
                sx = self.alpha * current_coords[0] + (1.0 - self.alpha) * prev_coords[0]
                sy = self.alpha * current_coords[1] + (1.0 - self.alpha) * prev_coords[1]
                sz = self.alpha * current_coords[2] + (1.0 - self.alpha) * prev_coords[2]
                # Retain latest visibility
                vis = current_coords[3]
                smoothed[name] = [float(sx), float(sy), float(sz), float(vis)]
            else:
                smoothed[name] = list(current_coords)

        self.smoothed_landmarks = smoothed
        return self.smoothed_landmarks


def _ensure_task_model_exists() -> Path:
    """Download pose landmarker task asset if missing."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not MODEL_TASK_PATH.exists() or MODEL_TASK_PATH.stat().st_size == 0:
        print("[Burn-Ex Vision] Downloading MediaPipe PoseLandmarker model asset...")
        urllib.request.urlretrieve(MODEL_TASK_URL, str(MODEL_TASK_PATH))
        print("[Burn-Ex Vision] Model download complete.")
    return MODEL_TASK_PATH


class VisionPipeline:
    """
    Handles real-time skeletal pose extraction with EMA coordinate smoothing
    and 3D world metric landmark extraction (meters).
    """

    def __init__(
        self,
        min_detection_confidence: float = MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = MIN_TRACKING_CONFIDENCE,
        smoothing_alpha: float = EMA_SMOOTHING_ALPHA,
    ) -> None:
        self.use_tasks_api: bool = False
        self.legacy_pose: Optional[Any] = None
        self.task_landmarker: Optional[Any] = None

        self.smoother_2d = LandmarkSmoother(alpha=smoothing_alpha)
        self.smoother_3d = LandmarkSmoother(alpha=smoothing_alpha)

        # Check if legacy solutions API is present
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self.mp_pose = mp.solutions.pose
            self.legacy_pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
                enable_segmentation=False,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self.use_tasks_api = False
        else:
            # Modern MediaPipe Tasks API (MediaPipe 1.0+)
            from mediapipe.tasks.python.vision import (
                PoseLandmarker,
                PoseLandmarkerOptions,
                RunningMode,
            )
            from mediapipe.tasks.python import BaseOptions

            model_path = _ensure_task_model_exists()
            base_options = BaseOptions(model_asset_path=str(model_path))
            options = PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=RunningMode.IMAGE,
                min_pose_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                num_poses=1,
            )
            self.task_landmarker = PoseLandmarker.create_from_options(options)
            self.use_tasks_api = True

    def process_frame(
        self, frame: np.ndarray
    ) -> Tuple[Optional[Dict[str, List[float]]], Optional[Dict[str, List[float]]], Any]:
        """
        Process a single BGR video frame, extract 33 skeletal 2D and 3D world landmarks.
        Applies EMA smoothing filter.

        Args:
            frame: BGR image from cv2.VideoCapture.

        Returns:
            Tuple:
                - Dict mapping landmark name to smoothed [x, 2D normalized, y, z, visibility] or None.
                - Dict mapping landmark name to smoothed [x, y, z in meters (3D world), visibility] or None.
                - Raw MediaPipe results object.
        """
        if frame is None or frame.size == 0:
            self.smoother_2d.reset()
            self.smoother_3d.reset()
            return None, None, None

        # Convert to RGB in-memory (ephemeral)
        rgb_frame: np.ndarray = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False

        raw_2d: Dict[str, List[float]] = {}
        raw_3d: Dict[str, List[float]] = {}

        if not self.use_tasks_api and self.legacy_pose:
            results = self.legacy_pose.process(rgb_frame)
            if not results.pose_landmarks:
                self.smoother_2d.reset()
                self.smoother_3d.reset()
                return None, None, None

            for name, idx in LANDMARK_NAMES.items():
                lm = results.pose_landmarks.landmark[idx]
                raw_2d[name] = [
                    float(lm.x),
                    float(lm.y),
                    float(lm.z),
                    float(getattr(lm, "visibility", 0.9)),
                ]

            # Extract 3D world landmarks if available
            if hasattr(results, "pose_world_landmarks") and results.pose_world_landmarks:
                for name, idx in LANDMARK_NAMES.items():
                    wlm = results.pose_world_landmarks.landmark[idx]
                    raw_3d[name] = [
                        float(wlm.x),
                        float(wlm.y),
                        float(wlm.z),
                        float(getattr(wlm, "visibility", 0.9)),
                    ]
            else:
                raw_3d = raw_2d

            smoothed_2d = self.smoother_2d.smooth(raw_2d)
            smoothed_3d = self.smoother_3d.smooth(raw_3d)
            return smoothed_2d, smoothed_3d, results

        elif self.use_tasks_api and self.task_landmarker:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.task_landmarker.detect(mp_image)

            if not results.pose_landmarks or len(results.pose_landmarks) == 0:
                self.smoother_2d.reset()
                self.smoother_3d.reset()
                return None, None, None

            pose_lms = results.pose_landmarks[0]
            for name, idx in LANDMARK_NAMES.items():
                if idx < len(pose_lms):
                    lm = pose_lms[idx]
                    vis = getattr(lm, "visibility", 0.9)
                    if vis is None:
                        vis = 0.9
                    raw_2d[name] = [
                        float(lm.x),
                        float(lm.y),
                        float(lm.z),
                        float(vis),
                    ]

            # 3D World landmarks
            if results.pose_world_landmarks and len(results.pose_world_landmarks) > 0:
                world_lms = results.pose_world_landmarks[0]
                for name, idx in LANDMARK_NAMES.items():
                    if idx < len(world_lms):
                        wlm = world_lms[idx]
                        vis = getattr(wlm, "visibility", 0.9)
                        if vis is None:
                            vis = 0.9
                        raw_3d[name] = [
                            float(wlm.x),
                            float(wlm.y),
                            float(wlm.z),
                            float(vis),
                        ]
            else:
                raw_3d = raw_2d

            smoothed_2d = self.smoother_2d.smooth(raw_2d)
            smoothed_3d = self.smoother_3d.smooth(raw_3d)
            return smoothed_2d, smoothed_3d, results

        return None, None, None

    def close(self) -> None:
        """Safely release MediaPipe resources."""
        if self.legacy_pose:
            self.legacy_pose.close()
        if self.task_landmarker:
            self.task_landmarker.close()
